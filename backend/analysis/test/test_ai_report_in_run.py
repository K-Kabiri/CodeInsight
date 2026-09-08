import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from analysis.models import Analysis, AnalysisMetric
from analysis.services.analysis_service import AnalysisService
from projects.models import Project, ProjectVersion
from reports.ai_errors import LLMRequestError
from reports.models import AIReport
from reports.services.ai_report_service import AIReportService


class _ExplodingEngine:
    """A metric engine that always fails — drives the metric-failure path."""

    def calculate(self, python_files, scope=None):
        raise RuntimeError("engine exploded")

    def calculate_detailed(self, python_files, scope=None):
        raise RuntimeError("engine exploded")


class FakeLLMClient:
    def __init__(self, response_text: str, model: str = "glm-4.5-flash"):
        self.response_text = response_text
        self.model = model
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.response_text


def _fixture_text(summary="Solid overall.") -> str:
    return json.dumps(
        {
            "summary": summary,
            "metric_content": {
                "LOC": {
                    "explanation": "The file is compact.",
                    "suggestions": ["Keep it small."],
                }
            },
        }
    )


class AiReportInRunTest(TestCase):
    """
    Ticket 03: the Analysis run itself generates the AI report —
    while still RUNNING, only when `ai_requested` and at least one
    selected metric succeeded. Any generation failure still completes
    the Analysis with its metrics intact and no report row.

    Metric failures are isolated to the metric row: the Analysis is
    FAILED only when every selected metric failed; when some succeed,
    the Analysis completes and (if requested) the AI report explains
    exactly those completed metrics.
    """

    def setUp(self):
        self._media_root = tempfile.mkdtemp(
            prefix="codeinsight-test-media-"
        )
        self._media_override = override_settings(
            MEDIA_ROOT=self._media_root
        )
        self._media_override.enable()
        self.addCleanup(self._media_override.disable)
        self.addCleanup(
            shutil.rmtree,
            self._media_root,
            ignore_errors=True,
        )

        owner = User.objects.create_user(
            username="alice",
            password="pass-alice",
        )
        project = Project.objects.create(
            owner=owner,
            name="Project",
        )
        self.version = ProjectVersion.objects.create(
            project=project,
            version_number=1,
            source_file=SimpleUploadedFile(
                "main.py",
                b"def answer():\n    return 42\n",
            ),
        )

    def _analysis(self, ai_requested: bool, metrics=("LOC",)) -> Analysis:
        from analysis.models import MetricDefinition

        analysis = Analysis.objects.create(
            project_version=self.version,
            ai_requested=ai_requested,
        )
        for name in metrics:
            AnalysisMetric.objects.create(
                analysis=analysis,
                metric=MetricDefinition.objects.get(name=name),
                selected=True,
            )
        return analysis

    def test_report_is_generated_while_running_before_completed(self):
        analysis = self._analysis(ai_requested=True)
        fake_llm = FakeLLMClient(response_text=_fixture_text())
        seen = []

        def fake_generator(target):
            seen.append((target.id, target.status))
            AIReportService.generate(target, client=fake_llm)

        with mock.patch(
                "analysis.services.analysis_service.ai_report_generator",
                side_effect=fake_generator,
        ):
            AnalysisService.run(analysis)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, Analysis.Status.COMPLETED)

        # Generation happened mid-run: the Analysis was still RUNNING
        # and its metric had already settled.
        self.assertEqual(
            seen,
            [(analysis.id, Analysis.Status.RUNNING)],
        )

        report = AIReport.objects.get(analysis=analysis)
        self.assertEqual(report.summary, "Solid overall.")
        self.assertIn("LOC", report.metric_content)
        self.assertEqual(AIReport.objects.count(), 1)
        self.assertEqual(len(fake_llm.calls), 1)

    def test_not_requested_runs_skip_generation(self):
        analysis = self._analysis(ai_requested=False)
        generator = mock.Mock(
            side_effect=AssertionError("must not be called")
        )

        with mock.patch(
                "analysis.services.analysis_service.ai_report_generator",
                generator,
        ):
            AnalysisService.run(analysis)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, Analysis.Status.COMPLETED)
        generator.assert_not_called()
        self.assertFalse(AIReport.objects.exists())

    def test_all_metrics_failed_fails_analysis_and_skips_ai(self):
        # Every selected metric fails -> the Analysis itself fails and
        # no AI report is attempted.
        analysis = self._analysis(ai_requested=True)
        generator = mock.Mock(
            side_effect=AssertionError("must not be called")
        )

        with mock.patch(
                "analysis.services.analysis_service.ai_report_generator",
                generator,
        ), mock.patch(
                "analysis.services.analysis_service.get_engine",
                return_value=_ExplodingEngine(),
        ):
            AnalysisService.run(analysis)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, Analysis.Status.FAILED)

        metric = analysis.metrics.get()
        self.assertEqual(metric.status, AnalysisMetric.Status.FAILED)

        generator.assert_not_called()
        self.assertFalse(AIReport.objects.exists())

    def test_partial_metric_failure_completes_analysis(self):
        # One failed metric never fails the whole Analysis: the
        # successful metrics keep their results and the run completes.
        analysis = self._analysis(
            ai_requested=False,
            metrics=("LOC", "CYCLOMATIC"),
        )
        generator = mock.Mock(
            side_effect=AssertionError("must not be called")
        )

        with mock.patch(
                "analysis.services.analysis_service.ai_report_generator",
                generator,
        ), mock.patch(
                "analysis.services.analysis_service.get_engine",
                side_effect=self._selective_engine,
        ):
            AnalysisService.run(analysis)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, Analysis.Status.COMPLETED)

        loc = analysis.metrics.get(metric__name="LOC")
        self.assertEqual(loc.status, AnalysisMetric.Status.COMPLETED)
        self.assertIsNotNone(loc.value)

        cyclic = analysis.metrics.get(metric__name="CYCLOMATIC")
        self.assertEqual(cyclic.status, AnalysisMetric.Status.FAILED)
        self.assertIsNone(cyclic.value)
        self.assertIn("engine exploded", cyclic.error_message)

        generator.assert_not_called()
        self.assertFalse(AIReport.objects.exists())

    def test_partial_metric_failure_ai_covers_successful_metrics(self):
        # With a partial failure and ai_requested, the run completes
        # and the AI report is generated from the metrics that
        # actually succeeded.
        analysis = self._analysis(
            ai_requested=True,
            metrics=("LOC", "CYCLOMATIC"),
        )
        fake_llm = FakeLLMClient(response_text=_fixture_text())
        seen = []

        def fake_generator(target):
            seen.append((target.id, target.status))
            AIReportService.generate(target, client=fake_llm)

        with mock.patch(
                "analysis.services.analysis_service.ai_report_generator",
                side_effect=fake_generator,
        ), mock.patch(
                "analysis.services.analysis_service.get_engine",
                side_effect=self._selective_engine,
        ):
            AnalysisService.run(analysis)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, Analysis.Status.COMPLETED)

        loc = analysis.metrics.get(metric__name="LOC")
        self.assertEqual(loc.status, AnalysisMetric.Status.COMPLETED)

        cyclic = analysis.metrics.get(metric__name="CYCLOMATIC")
        self.assertEqual(cyclic.status, AnalysisMetric.Status.FAILED)

        # Generation happened mid-run while the Analysis was RUNNING.
        self.assertEqual(
            seen,
            [(analysis.id, Analysis.Status.RUNNING)],
        )

        report = AIReport.objects.get(analysis=analysis)
        self.assertEqual(report.summary, "Solid overall.")
        self.assertIn("LOC", report.metric_content)
        self.assertEqual(len(fake_llm.calls), 1)

    def _selective_engine(self, metric_name):
        """Real engines except CYCLOMATIC, which always explodes."""
        from analysis.engines import get_engine as real_get_engine

        if metric_name == "CYCLOMATIC":
            return _ExplodingEngine()
        return real_get_engine(metric_name)

    def test_llm_failure_still_completes_with_metrics_intact(self):
        analysis = self._analysis(ai_requested=True)

        with self.assertLogs(
                "analysis.services.analysis_service",
                level="ERROR",
        ):
            with mock.patch(
                    "analysis.services.analysis_service.ai_report_generator",
                    side_effect=LLMRequestError("provider exploded"),
            ):
                AnalysisService.run(analysis)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, Analysis.Status.COMPLETED)

        metric = analysis.metrics.get()
        self.assertEqual(metric.status, AnalysisMetric.Status.COMPLETED)
        self.assertIsNotNone(metric.value)

        self.assertFalse(AIReport.objects.exists())

    def test_unexpected_generation_error_still_completes(self):
        analysis = self._analysis(ai_requested=True)

        with self.assertLogs(
                "analysis.services.analysis_service",
                level="ERROR",
        ):
            with mock.patch(
                    "analysis.services.analysis_service.ai_report_generator",
                    side_effect=RuntimeError("internal bug"),
            ):
                AnalysisService.run(analysis)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, Analysis.Status.COMPLETED)
        self.assertEqual(
            analysis.metrics.get().status,
            AnalysisMetric.Status.COMPLETED,
        )
        self.assertFalse(AIReport.objects.exists())
