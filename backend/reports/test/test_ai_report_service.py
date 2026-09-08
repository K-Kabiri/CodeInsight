import json
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from analysis.models import Analysis, AnalysisMetric
from projects.models import Project, ProjectVersion
from reports.ai_errors import (
    AIReportError,
    AIResponseParseError,
    LLMNotConfiguredError,
)
from reports.models import AIReport
from reports.services.ai_report_service import AIReportService


class FakeLLMClient:
    """Injected seam: returns canned text or raises a canned error."""

    def __init__(
            self,
            response_text: str = "",
            error: Exception | None = None,
            model: str = "glm-4.5-flash",
    ):
        self.response_text = response_text
        self.error = error
        self.model = model
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)

        if self.error is not None:
            raise self.error

        return self.response_text


def _fixture_text(summary="Solid overall.") -> str:
    return json.dumps(
        {
            "summary": summary,
            "metric_content": {
                "LOC": {
                    "explanation": "The file is compact.",
                    "suggestions": ["Keep functions short."],
                }
            },
        }
    )


class AIReportServiceTest(TestCase):

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
        version = ProjectVersion.objects.create(
            project=project,
            version_number=1,
            source_file=SimpleUploadedFile(
                "main.py",
                b"def answer():\n    return 42\n",
            ),
        )
        self.analysis = Analysis.objects.create(
            project_version=version,
            ai_requested=True,
        )

    def _completed_loc(self):
        metric = AnalysisMetric.objects.create(
            analysis=self.analysis,
            metric_id=self._definition_id("LOC"),
            selected=True,
            status=AnalysisMetric.Status.COMPLETED,
            value=12,
            detail={"metric": "LOC"},
        )
        return metric

    def _definition_id(self, name):
        from analysis.models import MetricDefinition
        return MetricDefinition.objects.get(name=name).id

    def test_generate_persists_report_and_uses_the_client_model(self):
        self._completed_loc()
        client = FakeLLMClient(
            response_text=_fixture_text(),
            model="glm-test",
        )

        AIReportService.generate(self.analysis, client=client)

        report = AIReport.objects.get(analysis=self.analysis)
        self.assertEqual(report.summary, "Solid overall.")
        self.assertEqual(
            report.metric_content,
            {
                "LOC": {
                    "explanation": "The file is compact.",
                    "suggestions": ["Keep functions short."],
                }
            },
        )
        self.assertEqual(report.model_name, "glm-test")
        self.assertEqual(report.strengths, "")
        self.assertEqual(report.weaknesses, "")
        self.assertEqual(report.recommendations, "")
        self.assertIsNotNone(report.generated_at)
        self.assertEqual(AIReport.objects.count(), 1)

        self.assertEqual(len(client.calls), 1)
        self.assertIn("LOC", client.calls[0][1]["content"])

    def test_generate_requires_at_least_one_completed_metric(self):
        # A metric row exists but never ran.
        AnalysisMetric.objects.create(
            analysis=self.analysis,
            metric_id=self._definition_id("LOC"),
            selected=True,
            status=AnalysisMetric.Status.PENDING,
        )
        client = FakeLLMClient(response_text=_fixture_text())

        with self.assertRaises(AIReportError):
            AIReportService.generate(self.analysis, client=client)

        self.assertEqual(client.calls, [])
        self.assertFalse(AIReport.objects.exists())

    def test_not_configured_error_propagates_and_saves_nothing(self):
        self._completed_loc()
        client = FakeLLMClient(
            error=LLMNotConfiguredError(
                "LLM_API_KEY is not configured."
            )
        )

        with self.assertRaises(LLMNotConfiguredError):
            AIReportService.generate(self.analysis, client=client)

        self.assertFalse(AIReport.objects.exists())

    def test_unparseable_response_propagates_and_saves_nothing(self):
        self._completed_loc()
        client = FakeLLMClient(response_text="certainly not json")

        with self.assertRaises(AIResponseParseError):
            AIReportService.generate(self.analysis, client=client)

        self.assertFalse(AIReport.objects.exists())

    def test_regeneration_updates_the_single_report_row(self):
        self._completed_loc()
        AIReportService.generate(
            self.analysis,
            client=FakeLLMClient(response_text=_fixture_text("First.")),
        )

        AIReportService.generate(
            self.analysis,
            client=FakeLLMClient(response_text=_fixture_text("Second.")),
        )

        report = AIReport.objects.get(analysis=self.analysis)
        self.assertEqual(report.summary, "Second.")
        self.assertEqual(AIReport.objects.count(), 1)

    @override_settings(LLM_API_KEY="")
    def test_default_client_without_key_reports_not_configured(self):
        self._completed_loc()

        with self.assertRaises(LLMNotConfiguredError):
            AIReportService.generate(self.analysis)

        self.assertFalse(AIReport.objects.exists())
