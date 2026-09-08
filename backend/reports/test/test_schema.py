import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from analysis.models import Analysis
from projects.models import Project, ProjectVersion
from reports.models import AIReport


class AIReportMetricContentTest(TestCase):
    """
    Ticket 01 (ai-report): the AIReport row stores per-metric
    explanation/suggestions content in `metric_content` alongside the
    unchanged existing text columns.
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
        )

    def _report(self, analysis=None, **overrides):
        defaults = {
            "analysis": analysis or self.analysis,
            "summary": "Overall summary.",
            "recommendations": "Split the long functions.",
            "model_name": "glm-4.5-flash",
        }
        defaults.update(overrides)
        return AIReport.objects.create(**defaults)

    def test_metric_content_defaults_to_empty_dict(self):
        report = self._report()
        self.assertEqual(report.metric_content, {})

        report.refresh_from_db()
        self.assertEqual(report.metric_content, {})

    def test_metric_content_persists_and_loads(self):
        content = {
            "LOC": {
                "explanation": "The file is compact.",
                "suggestions": [
                    "Keep functions short and focused."
                ],
            },
            "CYCLOMATIC": {
                "explanation": "Complexity is moderate.",
                "suggestions": [
                    "Split the deeply nested branches.",
                    "Extract helper methods.",
                ],
            },
        }
        report = self._report(metric_content=content)

        report.refresh_from_db()
        self.assertEqual(report.metric_content, content)

    def test_existing_columns_are_unchanged_and_coexist(self):
        report = self._report(
            summary="A balanced codebase.",
            strengths="Clear module boundaries.",
            weaknesses="Long functions in utils.",
            recommendations="Refactor utils.py.",
            metric_content={"LOC": {"explanation": "x", "suggestions": []}},
        )

        report.refresh_from_db()
        self.assertEqual(report.summary, "A balanced codebase.")
        self.assertEqual(report.strengths, "Clear module boundaries.")
        self.assertEqual(report.weaknesses, "Long functions in utils.")
        self.assertEqual(report.recommendations, "Refactor utils.py.")
        self.assertEqual(report.model_name, "glm-4.5-flash")
        self.assertIsNotNone(report.generated_at)
        self.assertEqual(
            report.metric_content,
            {"LOC": {"explanation": "x", "suggestions": []}},
        )

    def test_default_dict_is_not_shared_between_rows(self):
        first = self._report()

        second_analysis = Analysis.objects.create(
            project_version=self.analysis.project_version,
        )
        second = self._report(analysis=second_analysis)

        first.metric_content["LOC"] = {"explanation": "x", "suggestions": []}
        first.save()

        second.refresh_from_db()
        self.assertEqual(second.metric_content, {})
