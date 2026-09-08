import shutil
import tempfile
import zipfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files import File
from django.test import TestCase, override_settings

from analysis.models import (
    Analysis,
    AnalysisMetric,
    MetricDefinition,
)
from analysis.services.analysis_service import AnalysisService
from projects.models import Project, ProjectVersion


class _ScopeRecordingEngine:
    """
    Test double that records the scope the service passes
    to an engine for each interface call.
    """

    def __init__(self):
        self.calls = []

    def calculate(
            self,
            python_files,
            scope=None,
    ) -> float:
        self.calls.append(("calculate", scope))
        return 1.0

    def calculate_detailed(
            self,
            python_files,
            scope=None,
    ) -> dict:
        self.calls.append(("calculate_detailed", scope))
        return {"spy": True}


class AnalysisServiceTest(TestCase):

    def setUp(self):
        # Isolate uploads: without this, ProjectVersion.source_file writes
        # land in the real MEDIA_ROOT (with random suffixed names on every
        # run, since files from previous runs are never cleaned up) and
        # pollute the repo. Route them to a throwaway temp dir instead.
        self._media_root = tempfile.mkdtemp(
            prefix="codeinsight-test-media-"
        )
        self._media_override = override_settings(
            MEDIA_ROOT=self._media_root
        )
        self._media_override.enable()

    def tearDown(self):
        self._media_override.disable()
        shutil.rmtree(
            self._media_root,
            ignore_errors=True,
        )

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

        metric = MetricDefinition.objects.get(
            name="LOC",
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
            5,
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

    def test_detailed_output_is_persisted(self):
        analysis, analysis_metric = self._create_loc_analysis()

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

        self.assertIsNotNone(
            analysis_metric.detail,
        )

        detail = analysis_metric.detail

        self.assertEqual(
            detail["totals"]["loc"],
            5,
        )

        self.assertEqual(
            detail["totals"]["lloc"],
            4,
        )

        self.assertEqual(
            detail["totals"]["sloc"],
            4,
        )

        self.assertEqual(
            detail["totals"]["blank"],
            1,
        )

        self.assertEqual(
            len(detail["files"]),
            1,
        )

        self.assertEqual(
            detail["files"][0]["file"],
            analysis.project_version.source_file.path,
        )

        self.assertEqual(
            detail["files"][0]["sloc"],
            4,
        )

    def test_service_passes_single_file_scope_for_py_input(self):
        analysis, analysis_metric = self._create_loc_analysis()

        spy = _ScopeRecordingEngine()

        with mock.patch(
            "analysis.services.analysis_service.get_engine",
            return_value=spy,
        ):
            AnalysisService.run(analysis)

        analysis_metric.refresh_from_db()

        self.assertEqual(
            spy.calls,
            [
                ("calculate", "single_file"),
                ("calculate_detailed", "single_file"),
            ],
        )

        self.assertEqual(
            analysis_metric.status,
            AnalysisMetric.Status.COMPLETED,
        )

    def test_service_passes_project_scope_for_one_file_zip(self):
        user = User.objects.create_user(
            username="testuser4",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".zip",
            delete=False,
        )

        with zipfile.ZipFile(
                analysis_file.name,
                "w",
        ) as zip_file:
            zip_file.writestr(
                "main.py",
                "print('hello')\n",
            )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="project.zip",
                ),
            )

        metric = MetricDefinition.objects.get(
            name="LOC",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        spy = _ScopeRecordingEngine()

        with mock.patch(
            "analysis.services.analysis_service.get_engine",
            return_value=spy,
        ):
            AnalysisService.run(analysis)

        analysis.refresh_from_db()

        self.assertEqual(
            spy.calls,
            [
                ("calculate", "project"),
                ("calculate_detailed", "project"),
            ],
        )

        self.assertEqual(
            analysis.status,
            Analysis.Status.COMPLETED,
        )

    def test_instability_analysis_on_zip_project(self):
        user = User.objects.create_user(
            username="testuser5",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".zip",
            delete=False,
        )

        with zipfile.ZipFile(
                analysis_file.name,
                "w",
        ) as zip_file:
            zip_file.writestr(
                "main.py",
                "import core\n",
            )
            zip_file.writestr(
                "core.py",
                "import x\n",
            )
            zip_file.writestr(
                "x.py",
                "",
            )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="project.zip",
                ),
            )

        metric = MetricDefinition.objects.get(
            name="INSTABILITY",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis_metric = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=metric,
        )

        self.assertEqual(
            analysis_metric.status,
            AnalysisMetric.Status.COMPLETED,
        )

        # The scalar value is the project average
        # I = (1.0 + 0.5 + 0.0) / 3 = 0.5
        self.assertAlmostEqual(
            analysis_metric.value,
            0.5,
        )

        detail = analysis_metric.detail

        self.assertEqual(
            detail["scope"],
            "project",
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        by_module = {
            item["module"]: item
            for item in detail["files"]
        }

        self.assertEqual(
            set(by_module.keys()),
            {"main", "core", "x"},
        )

        self.assertEqual(
            by_module["core"]["ca"],
            1,
        )

        self.assertAlmostEqual(
            by_module["core"]["i"],
            0.5,
        )

    def test_cyclic_analysis_on_zip_project(self):
        user = User.objects.create_user(
            username="testuser6",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".zip",
            delete=False,
        )

        with zipfile.ZipFile(
                analysis_file.name,
                "w",
        ) as zip_file:
            zip_file.writestr(
                "a.py",
                "import b\n",
            )
            zip_file.writestr(
                "b.py",
                "import a\n",
            )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="project.zip",
                ),
            )

        metric = MetricDefinition.objects.get(
            name="CYCLIC",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis_metric = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=metric,
        )

        self.assertEqual(
            analysis_metric.status,
            AnalysisMetric.Status.COMPLETED,
        )

        # The scalar value is the number of cycles
        self.assertEqual(
            analysis_metric.value,
            1,
        )

        detail = analysis_metric.detail

        self.assertEqual(
            detail["scope"],
            "project",
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["cycles"],
            [["a", "b"]],
        )

        self.assertEqual(
            detail["self_loops"],
            [],
        )

    def test_cbo_analysis_on_zip_project(self):
        user = User.objects.create_user(
            username="testuser8",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".zip",
            delete=False,
        )

        with zipfile.ZipFile(
                analysis_file.name,
                "w",
        ) as zip_file:
            zip_file.writestr(
                "a.py",
                "class A:\n    pass\n",
            )
            zip_file.writestr(
                "b.py",
                "from a import A\n"
                "\n"
                "class B:\n"
                "    def use(self):\n"
                "        return A()\n",
            )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="project.zip",
                ),
            )

        metric = MetricDefinition.objects.get(
            name="CBO",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis_metric = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=metric,
        )

        self.assertEqual(
            analysis_metric.status,
            AnalysisMetric.Status.COMPLETED,
        )

        # Only B references A: total CBO = 1
        self.assertEqual(
            analysis_metric.value,
            1,
        )

        detail = analysis_metric.detail

        self.assertEqual(
            detail["metric"],
            "CBO",
        )

        self.assertEqual(
            detail["total"],
            1,
        )

        self.assertEqual(
            len(detail["files"]),
            2,
        )

    def test_lcom_analysis_on_zip_project(self):
        user = User.objects.create_user(
            username="testuser9",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".zip",
            delete=False,
        )

        with zipfile.ZipFile(
                analysis_file.name,
                "w",
        ) as zip_file:
            zip_file.writestr(
                "calc.py",
                "class Calculator:\n"
                "    def add(self):\n"
                "        self.total = 1\n"
                "\n"
                "    def subtract(self):\n"
                "        self.other = 2\n",
            )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="project.zip",
                ),
            )

        metric = MetricDefinition.objects.get(
            name="LCOM",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis_metric = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=metric,
        )

        self.assertEqual(
            analysis_metric.status,
            AnalysisMetric.Status.COMPLETED,
        )

        # One method pair (add, subtract) sharing no attribute:
        # P = 1, Q = 0, LCOM = max(1 - 0, 0) = 1
        self.assertEqual(
            analysis_metric.value,
            1,
        )

        detail = analysis_metric.detail

        self.assertEqual(
            detail["metric"],
            "LCOM",
        )

        self.assertEqual(
            detail["total"],
            1,
        )

        self.assertEqual(
            len(detail["files"]),
            1,
        )

    def test_dit_analysis_on_zip_project(self):
        user = User.objects.create_user(
            username="testuser10",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".zip",
            delete=False,
        )

        with zipfile.ZipFile(
                analysis_file.name,
                "w",
        ) as zip_file:
            zip_file.writestr(
                "animals.py",
                "class Animal:\n"
                "    pass\n"
                "\n"
                "class Dog(Animal):\n"
                "    pass\n",
            )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="project.zip",
                ),
            )

        metric = MetricDefinition.objects.get(
            name="DIT",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis_metric = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=metric,
        )

        self.assertEqual(
            analysis_metric.status,
            AnalysisMetric.Status.COMPLETED,
        )

        # DIT(Animal) = 0, DIT(Dog) = 1: total DIT = 1
        self.assertEqual(
            analysis_metric.value,
            1,
        )

        detail = analysis_metric.detail

        self.assertEqual(
            detail["metric"],
            "DIT",
        )

        self.assertEqual(
            detail["total"],
            1,
        )

        self.assertEqual(
            detail["max"],
            1,
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

        metric = MetricDefinition.objects.get(
            name="LOC",
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

    def _create_loc_analysis(self):
        user = User.objects.create_user(
            username="testuser3",
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

        metric = MetricDefinition.objects.get(
            name="LOC",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        analysis_metric = AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        return analysis, analysis_metric

    def test_not_applicable_metric_does_not_block_analysis(self):
        user = User.objects.create_user(
            username="testuser7",
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
            b"print('hello')\n"
        )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="single.py",
                ),
            )

        loc_metric = MetricDefinition.objects.get(
            name="LOC",
        )

        cyclic_metric = MetricDefinition.objects.get(
            name="CYCLIC",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=loc_metric,
            selected=True,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=cyclic_metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis.refresh_from_db()

        self.assertEqual(
            analysis.status,
            Analysis.Status.COMPLETED,
        )

        loc_result = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=loc_metric,
        )

        self.assertEqual(
            loc_result.status,
            AnalysisMetric.Status.COMPLETED,
        )

        self.assertIsNotNone(
            loc_result.value,
        )

        cyclic_result = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=cyclic_metric,
        )

        self.assertEqual(
            cyclic_result.status,
            AnalysisMetric.Status.COMPLETED,
        )

        self.assertIsNone(
            cyclic_result.value,
        )

        self.assertEqual(
            cyclic_result.detail["completeness"],
            "not_applicable",
        )

        self.assertTrue(
            cyclic_result.detail["reason"],
        )

    def test_code_smells_analysis_on_zip_project(self):
        user = User.objects.create_user(
            username="testuser11",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".zip",
            delete=False,
        )

        long_method = (
            "def long():\n"
            + "".join(
                f"    x{i} = 0\n"
                for i in range(31)
            )
            + "long()\n"
        )

        with zipfile.ZipFile(
                analysis_file.name,
                "w",
        ) as zip_file:
            zip_file.writestr(
                "module.py",
                long_method,
            )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="project.zip",
                ),
            )

        metric = MetricDefinition.objects.get(
            name="CODE_SMELLS",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis.refresh_from_db()
        analysis_metric = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=metric,
        )

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
            1,
        )

        detail = analysis_metric.detail

        self.assertEqual(
            detail["scope"],
            "project",
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["by_type"],
            {
                "long-method": 1,
            },
        )

        self.assertTrue(
            detail["files"][0]["file"].endswith("module.py"),
        )

        self.assertTrue(
            detail["files"][0]["parsed"],
        )

    def test_violations_analysis_on_zip_project(self):
        user = User.objects.create_user(
            username="testuser12",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".zip",
            delete=False,
        )

        with zipfile.ZipFile(
                analysis_file.name,
                "w",
        ) as zip_file:
            zip_file.writestr(
                "main.py",
                "import os\n"
                "print(os.path)\n",
            )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="project.zip",
                ),
            )

        metric = MetricDefinition.objects.get(
            name="VIOLATIONS",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        ruff_output = (
            '[{"code": "F401", "severity": "error", '
            '"filename": "main.py", "location": {"row": 1}}]'
        )

        bandit_output = (
            '{"results": [{"test_id": "B110", '
            '"issue_severity": "LOW", "filename": "main.py", '
            '"line_number": 1}]}'
        )

        with mock.patch(
                "analysis.engines.violations._run_ruff",
                return_value=ruff_output,
        ), mock.patch(
                "analysis.engines.violations._run_bandit",
                return_value=bandit_output,
        ):
            AnalysisService.run(analysis)

        analysis.refresh_from_db()
        analysis_metric = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=metric,
        )

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
            2,
        )

        detail = analysis_metric.detail

        self.assertEqual(
            detail["scope"],
            "project",
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["totals"]["violations"],
            2,
        )

        self.assertEqual(
            detail["by_rule"],
            {
                "B110": 1,
                "F401": 1,
            },
        )

        self.assertEqual(
            detail["totals"]["rules"],
            2,
        )

    def test_duplication_analysis_on_zip_project(self):
        user = User.objects.create_user(
            username="testuser13",
            password="testpass",
        )

        project = Project.objects.create(
            owner=user,
            name="Test Project",
        )

        analysis_file = tempfile.NamedTemporaryFile(
            suffix=".zip",
            delete=False,
        )

        duplicated_function = (
            "def dup():\n"
            + "".join(
                f"    v{i} = 0\n"
                for i in range(28)
            )
            + "    return v0\n"
        )

        with zipfile.ZipFile(
                analysis_file.name,
                "w",
        ) as zip_file:
            zip_file.writestr(
                "a.py",
                duplicated_function,
            )
            zip_file.writestr(
                "b.py",
                duplicated_function,
            )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="project.zip",
                ),
            )

        metric = MetricDefinition.objects.get(
            name="DUPLICATION",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis.refresh_from_db()
        analysis_metric = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=metric,
        )

        self.assertEqual(
            analysis.status,
            Analysis.Status.COMPLETED,
        )

        self.assertEqual(
            analysis_metric.status,
            AnalysisMetric.Status.COMPLETED,
        )

        self.assertAlmostEqual(
            analysis_metric.value,
            100.0,
        )

        detail = analysis_metric.detail

        self.assertEqual(
            detail["scope"],
            "project",
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            60,
        )

        self.assertEqual(
            len(detail["blocks"]),
            2,
        )

    def test_duplication_single_file_reports_internal_copies(self):
        user = User.objects.create_user(
            username="testuser14",
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

        duplicated_function = (
            "def dup():\n"
            + "".join(
                f"    v{i} = 0\n"
                for i in range(28)
            )
            + "    return v0\n"
        )

        # The function is copied twice inside the one uploaded file:
        # the metric must self-compare the file and report the copy.
        analysis_file.write(
            (
                duplicated_function
                + "\n"
                + duplicated_function
            ).encode("utf-8")
        )

        analysis_file.close()

        with open(analysis_file.name, "rb") as file:
            project_version = ProjectVersion.objects.create(
                project=project,
                version_number=1,
                source_file=File(
                    file,
                    name="single.py",
                ),
            )

        loc_metric = MetricDefinition.objects.get(
            name="LOC",
        )

        duplication_metric = MetricDefinition.objects.get(
            name="DUPLICATION",
        )

        analysis = Analysis.objects.create(
            project_version=project_version,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=loc_metric,
            selected=True,
        )

        AnalysisMetric.objects.create(
            analysis=analysis,
            metric=duplication_metric,
            selected=True,
        )

        AnalysisService.run(analysis)

        analysis.refresh_from_db()

        self.assertEqual(
            analysis.status,
            Analysis.Status.COMPLETED,
        )

        loc_result = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=loc_metric,
        )

        self.assertEqual(
            loc_result.status,
            AnalysisMetric.Status.COMPLETED,
        )

        self.assertIsNotNone(
            loc_result.value,
        )

        duplication_result = AnalysisMetric.objects.get(
            analysis=analysis,
            metric=duplication_metric,
        )

        self.assertEqual(
            duplication_result.status,
            AnalysisMetric.Status.COMPLETED,
        )

        self.assertAlmostEqual(
            duplication_result.value,
            60 / 61 * 100,
        )

        detail = duplication_result.detail

        self.assertEqual(
            detail["scope"],
            "single_file",
        )

        self.assertEqual(
            detail["completeness"],
            "full",
        )

        self.assertEqual(
            detail["duplicated_blocks"],
            1,
        )

        self.assertEqual(
            detail["duplicated_lines"],
            60,
        )

        self.assertEqual(
            len(detail["blocks"]),
            2,
        )

        self.assertTrue(
            all(
                block["file"].endswith("single.py")
                for block in detail["blocks"]
            ),
        )
