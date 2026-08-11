import tempfile

from django.contrib.auth.models import User
from django.core.files import File
from django.test import TestCase

from analysis.models import (
    Analysis,
    AnalysisMetric,
    MetricDefinition,
)
from analysis.services.analysis_service import AnalysisService
from projects.models import Project, ProjectVersion


class AnalysisServiceTest(TestCase):

    def test_loc_analysis(self):
        user = User.objects.create_user(
            username="testuser",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".py",
            delete=False,
        )

        analysis_file.write(
            b'''def hello():
    name = "Kimia"
    print(name)

hello()
'''
        )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="test.py",
                ),
            )

        metric = MetricDefinition.objects.create(
            name="LOC",
            display_name="Lines of Code",
            category="Complexity & Size",
            description="Source lines of code",
            unit="lines",
            higher_is_better=False,
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        analysis_metric = AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis.refresh_from_db()
        analysis_metric.refresh_from_db()

        self.assertEqual(
            analysis.status,
            Analysis.Status.COMPLETED,
        )

        self.assertEqual(
            analysis_metric.status,
            AnalysisMetric.Status.COMPLETED,
        )

        self.assertEqual(
            analysis_metric.value,
            4,
        )

        self.assertIsNotNone(
            analysis_metric.execution_time,
        )

        self.assertIsNotNone(
            analysis.started_at,
        )

        self.assertIsNotNone(
            analysis.finished_at,
        )

    def test_analysis_fails_when_no_metric_is_selected(self):
        user = User.objects.create_user(
            username="testuser2",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".py",
            delete=False,
        )

        analysis_file.write(
            b"print('Hello')\n"
        )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="test.py",
                ),
            )

        metric = MetricDefinition.objects.create(
            name="LOC",
            display_name="Lines of Code",
            category="Complexity & Size",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=False,
        )

        with self.assertRaises(ValueError):
            AnalysisService.run(analysis)

        analysis.refresh_from_db()

        self.assertEqual(
            analysis.status,
            Analysis.Status.FAILED,
        )
