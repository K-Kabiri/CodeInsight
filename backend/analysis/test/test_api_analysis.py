import shutil
import tempfile
import time
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from analysis.models import (
    Analysis,
    AnalysisMetric,
    MetricDefinition,
)
from analysis.services.analysis_service import AnalysisService
from analysis.services.dispatcher import InlineAnalysisDispatcher
from projects.models import Project, ProjectVersion


def _client_for(user):
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Token {token.key}"
    )
    return client


class AnalysisApiTestCase(APITestCase):
    """
    Deterministic API tests: the dispatcher runs the Analysis inline
    in the request, so every test observes the completed Analysis.
    """

    def setUp(self):
        self._media_root = tempfile.mkdtemp(
            prefix="codeinsight-test-media-"
        )
        self._media_override = override_settings(
            MEDIA_ROOT=self._media_root
        )
        self._media_override.enable()

        self.alice = User.objects.create_user(
            username="alice",
            password="pass-alice",
        )
        self.bob = User.objects.create_user(
            username="bob",
            password="pass-bob",
        )
        self.alice_client = _client_for(self.alice)
        self.bob_client = _client_for(self.bob)

        self.dispatcher_patcher = mock.patch(
            "analysis.views.dispatcher",
            InlineAnalysisDispatcher(),
        )
        self.dispatcher_patcher.start()

    def tearDown(self):
        self.dispatcher_patcher.stop()
        self._media_override.disable()
        shutil.rmtree(
            self._media_root,
            ignore_errors=True,
        )

    def _version(self, owner):
        project = Project.objects.create(
            owner=owner,
            name="Project",
        )
        return ProjectVersion.objects.create(
            project=project,
            version_number=1,
            source_file=SimpleUploadedFile(
                "main.py",
                b"def answer():\n    return 42\n",
            ),
        )

    def _create(self, client, version, metrics):
        return client.post(
            "/api/analyses/",
            {
                "project_version": version.id,
                "metrics": metrics,
            },
            format="json",
        )


class AnalysisCreateTest(AnalysisApiTestCase):

    def test_create_returns_201_with_pending_analysis(self):
        version = self._version(self.alice)
        response = self._create(
            self.alice_client,
            version,
            ["LOC", "CYCLOMATIC"],
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertEqual(
            response.data["project_version"],
            version.id,
        )

        analysis = Analysis.objects.get(id=response.data["id"])
        metric_names = set(
            AnalysisMetric.objects.filter(
                analysis=analysis,
            ).values_list(
                "metric__name",
                flat=True,
            )
        )
        self.assertEqual(
            metric_names,
            {"LOC", "CYCLOMATIC"},
        )
        self.assertTrue(
            all(
                metric.selected
                for metric in analysis.metrics.all()
            )
        )

    def test_create_with_no_metrics_returns_400(self):
        version = self._version(self.alice)
        response = self._create(
            self.alice_client,
            version,
            [],
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Analysis.objects.exists())

    def test_create_without_metrics_field_returns_400(self):
        version = self._version(self.alice)
        response = self.alice_client.post(
            "/api/analyses/",
            {"project_version": version.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_with_unknown_metric_returns_400(self):
        version = self._version(self.alice)
        response = self._create(
            self.alice_client,
            version,
            ["LOC", "NOT_A_METRIC"],
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("NOT_A_METRIC", str(response.data))
        self.assertFalse(Analysis.objects.exists())

    def test_create_on_other_users_version_returns_404(self):
        version = self._version(self.alice)
        response = self._create(
            self.bob_client,
            version,
            ["LOC"],
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Analysis.objects.exists())

    def test_create_requires_authentication(self):
        version = self._version(self.alice)
        response = self._create(
            self.client,
            version,
            ["LOC"],
        )
        self.assertEqual(response.status_code, 401)


class AnalysisRunAndResultsTest(AnalysisApiTestCase):

    def test_analysis_runs_and_detail_returns_per_metric_results(self):
        version = self._version(self.alice)
        created = self._create(
            self.alice_client,
            version,
            ["LOC"],
        )

        analysis = Analysis.objects.get(id=created.data["id"])
        self.assertEqual(analysis.status, "COMPLETED")

        response = self.alice_client.get(
            f"/api/analyses/{analysis.id}/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertIsNotNone(response.data["started_at"])
        self.assertIsNotNone(response.data["finished_at"])

        self.assertEqual(len(response.data["metrics"]), 1)
        metric = response.data["metrics"][0]
        self.assertEqual(metric["name"], "LOC")
        self.assertEqual(metric["display_name"], "Lines of Code")
        self.assertEqual(metric["status"], "COMPLETED")
        self.assertIsNotNone(metric["value"])
        self.assertIsNotNone(metric["execution_time"])
        self.assertEqual(metric["error_message"], "")
        self.assertIsNotNone(metric["detail"])

    def test_not_applicable_metric_is_reported_gracefully(self):
        version = self._version(self.alice)
        created = self._create(
            self.alice_client,
            version,
            ["LOC", "DUPLICATION"],
        )

        analysis = Analysis.objects.get(id=created.data["id"])
        self.assertEqual(analysis.status, "COMPLETED")

        response = self.alice_client.get(
            f"/api/analyses/{analysis.id}/"
        )
        metrics = {
            metric["name"]: metric
            for metric in response.data["metrics"]
        }

        duplication = metrics["DUPLICATION"]
        self.assertEqual(duplication["status"], "COMPLETED")
        self.assertIsNone(duplication["value"])
        self.assertEqual(
            duplication["detail"]["completeness"],
            "not_applicable",
        )
        self.assertIn("reason", duplication["detail"])

        loc = metrics["LOC"]
        self.assertEqual(loc["status"], "COMPLETED")
        self.assertIsNotNone(loc["value"])


class AnalysisOwnershipTest(AnalysisApiTestCase):

    def test_list_analyses_is_owner_scoped(self):
        version = self._version(self.alice)
        created = self._create(
            self.alice_client,
            version,
            ["LOC"],
        )

        response = self.alice_client.get("/api/analyses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            created.data["id"],
        )

        response = self.bob_client.get("/api/analyses/")
        self.assertEqual(response.data["results"], [])

    def test_detail_of_other_users_analysis_returns_404(self):
        version = self._version(self.alice)
        created = self._create(
            self.alice_client,
            version,
            ["LOC"],
        )

        response = self.bob_client.get(
            f"/api/analyses/{created.data['id']}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_list_analyses_requires_authentication(self):
        response = self.client.get("/api/analyses/")
        self.assertEqual(response.status_code, 401)

    def test_detail_requires_authentication(self):
        version = self._version(self.alice)
        created = self._create(
            self.alice_client,
            version,
            ["LOC"],
        )

        response = self.client.get(
            f"/api/analyses/{created.data['id']}/"
        )
        self.assertEqual(response.status_code, 401)


class AnalysisPaginationTest(AnalysisApiTestCase):

    def test_analyses_list_is_paginated(self):
        version = self._version(self.alice)

        for _ in range(25):
            Analysis.objects.create(
                project_version=version,
            )

        response = self.alice_client.get("/api/analyses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNone(response.data["previous"])

        response = self.alice_client.get("/api/analyses/?page=2")
        self.assertEqual(len(response.data["results"]), 5)
        self.assertIsNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])


class RealThreadAnalysisTest(TransactionTestCase):
    """
    The production execution path: the real background dispatcher runs
    the Analysis on a daemon thread while the client polls for the
    result. TransactionTestCase (no wrapping transaction) so the
    thread's own connection sees the committed rows.
    """

    def setUp(self):
        self._media_root = tempfile.mkdtemp(
            prefix="codeinsight-test-media-"
        )
        self._media_override = override_settings(
            MEDIA_ROOT=self._media_root
        )
        self._media_override.enable()

        self.alice = User.objects.create_user(
            username="alice",
            password="pass-alice",
        )
        self.alice_client = _client_for(self.alice)

        # TransactionTestCase flushes the whole database between
        # tests, which also wipes the MetricDefinition rows seeded by
        # data migrations — so re-seed the definitions the API needs.
        MetricDefinition.objects.get_or_create(
            name="LOC",
            defaults={
                "display_name": "Lines of Code",
                "category": "Complexity & Size",
                "description": "Source lines of code.",
                "unit": "lines",
                "higher_is_better": False,
                "supports_llm": True,
            },
        )

    def tearDown(self):
        self._media_override.disable()
        shutil.rmtree(
            self._media_root,
            ignore_errors=True,
        )

    def test_background_execution_completes_and_is_pollable(self):
        project = Project.objects.create(
            owner=self.alice,
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

        created = self.alice_client.post(
            "/api/analyses/",
            {
                "project_version": version.id,
                "metrics": ["LOC"],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        analysis_id = created.data["id"]

        deadline = time.time() + 10
        response = None

        while time.time() < deadline:
            response = self.alice_client.get(
                f"/api/analyses/{analysis_id}/"
            )
            if response.data["status"] in (
                "COMPLETED",
                "FAILED",
            ):
                break
            time.sleep(0.05)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertEqual(len(response.data["metrics"]), 1)
        self.assertEqual(
            response.data["metrics"][0]["status"],
            "COMPLETED",
        )
        self.assertIsNotNone(
            response.data["metrics"][0]["value"]
        )

    def test_polling_observes_running_before_completed(self):
        """
        api-layer user story 8: a polling client must observe the
        Analysis moving through RUNNING to COMPLETED. The service is
        deliberately NOT wrapped in one transaction, so the RUNNING
        transition commits before the metrics finish. `_run_metric`
        is slowed down to make the window observable; this pins the
        fix for ticket 03 (backend-hardening).
        """
        project = Project.objects.create(
            owner=self.alice,
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

        original_run_metric = AnalysisService._run_metric

        def slow_run_metric(analysis_metric, python_files, scope):
            time.sleep(0.4)
            return original_run_metric(
                analysis_metric,
                python_files,
                scope,
            )

        # The background thread keeps running after the create call
        # returns, so the patch must stay active for the whole poll
        # loop — closing it inside a `with` right after POST would
        # remove the slowdown before the thread reaches `_run_metric`.
        patcher = mock.patch.object(
            AnalysisService,
            "_run_metric",
            side_effect=slow_run_metric,
        )
        patcher.start()

        created = self.alice_client.post(
            "/api/analyses/",
            {
                "project_version": version.id,
                "metrics": ["LOC"],
            },
            format="json",
        )

        self.assertEqual(
            created.status_code,
            201,
            created.data,
        )
        analysis_id = created.data["id"]

        deadline = time.time() + 10
        observed_statuses = set()

        while time.time() < deadline:
            response = self.alice_client.get(
                f"/api/analyses/{analysis_id}/"
            )
            observed_statuses.add(
                response.data["status"]
            )
            if response.data["status"] in (
                "COMPLETED",
                "FAILED",
            ):
                break
            time.sleep(0.05)

        patcher.stop()

        self.assertIn("RUNNING", observed_statuses)
        self.assertIn("COMPLETED", observed_statuses)
