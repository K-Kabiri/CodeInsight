import json
from unittest import mock

from analysis.models import Analysis
from analysis.test.test_api_analysis import AnalysisApiTestCase
from reports.ai_errors import (
    LLMNotConfiguredError,
    LLMRequestError,
)
from reports.models import AIReport
from reports.services.ai_report_service import AIReportService


class FakeLLMClient:
    def __init__(self, response_text: str, model: str = "glm-4.5-flash"):
        self.response_text = response_text
        self.model = model
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.response_text


def _fixture_text(summary: str) -> str:
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


def _generate_with(client):
    def generate(analysis):
        return AIReportService.generate(analysis, client=client)

    return generate


class AIReportEndpointTest(AnalysisApiTestCase):
    """
    GET/POST /api/analyses/{id}/ai-report/ — owner-scoped (401
    anonymous, indistinguishable 404 for non-owners), POST only for
    COMPLETED runs, LLM failures a clear 503 that preserves any
    previously stored report. The generation seam is faked — no
    network in tests.
    """

    def _completed_analysis(self):
        version = self._version(self.alice)
        created = self.alice_client.post(
            "/api/analyses/",
            {
                "project_version": version.id,
                "metrics": ["LOC"],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)

        analysis = Analysis.objects.get(id=created.data["id"])
        self.assertEqual(analysis.status, Analysis.Status.COMPLETED)
        return analysis, version

    def test_post_generates_report_and_get_returns_serializer_shape(self):
        analysis, _version = self._completed_analysis()
        client = FakeLLMClient(_fixture_text("Alpha."))

        with mock.patch(
                "analysis.views.ai_report_generator",
                _generate_with(client),
        ):
            response = self.alice_client.post(
                f"/api/analyses/{analysis.id}/ai-report/"
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            set(response.data.keys()),
            {
                "summary",
                "metric_content",
                "model_name",
                "generated_at",
            },
        )
        self.assertEqual(response.data["summary"], "Alpha.")
        self.assertEqual(
            response.data["metric_content"]["LOC"]["explanation"],
            "The file is compact.",
        )
        self.assertEqual(response.data["model_name"], "glm-4.5-flash")
        self.assertIsNotNone(response.data["generated_at"])
        self.assertEqual(AIReport.objects.count(), 1)

        # The stored report is readable back without any generation.
        response = self.alice_client.get(
            f"/api/analyses/{analysis.id}/ai-report/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"], "Alpha.")

    def test_post_regenerates_and_overwrites_the_single_row(self):
        analysis, _version = self._completed_analysis()

        with mock.patch(
                "analysis.views.ai_report_generator",
                _generate_with(FakeLLMClient(_fixture_text("Alpha."))),
        ):
            first = self.alice_client.post(
                f"/api/analyses/{analysis.id}/ai-report/"
            )
        self.assertEqual(first.status_code, 201)

        with mock.patch(
                "analysis.views.ai_report_generator",
                _generate_with(FakeLLMClient(_fixture_text("Beta."))),
        ):
            second = self.alice_client.post(
                f"/api/analyses/{analysis.id}/ai-report/"
            )

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["summary"], "Beta.")
        self.assertEqual(AIReport.objects.count(), 1)

    def test_get_returns_404_when_report_never_generated(self):
        analysis, _version = self._completed_analysis()

        response = self.alice_client.get(
            f"/api/analyses/{analysis.id}/ai-report/"
        )
        self.assertEqual(response.status_code, 404)

    def test_anonymous_requests_are_rejected_with_401(self):
        analysis, _version = self._completed_analysis()

        get_response = self.client.get(
            f"/api/analyses/{analysis.id}/ai-report/"
        )
        post_response = self.client.post(
            f"/api/analyses/{analysis.id}/ai-report/"
        )
        self.assertEqual(get_response.status_code, 401)
        self.assertEqual(post_response.status_code, 401)

    def test_non_owner_gets_an_indistinguishable_404(self):
        analysis, _version = self._completed_analysis()

        response = self.bob_client.get(
            f"/api/analyses/{analysis.id}/ai-report/"
        )
        self.assertEqual(response.status_code, 404)

        response = self.bob_client.post(
            f"/api/analyses/{analysis.id}/ai-report/"
        )
        self.assertEqual(response.status_code, 404)

    def test_post_rejects_non_completed_analyses(self):
        version = self._version(self.alice)

        for raw_status in (
                Analysis.Status.PENDING,
                Analysis.Status.RUNNING,
                Analysis.Status.FAILED,
        ):
            analysis = Analysis.objects.create(
                project_version=version,
                status=raw_status,
            )

            response = self.alice_client.post(
                f"/api/analyses/{analysis.id}/ai-report/"
            )
            self.assertEqual(response.status_code, 409)
            self.assertIn(
                "COMPLETED",
                response.data["detail"],
            )
            self.assertFalse(
                AIReport.objects.filter(analysis=analysis).exists()
            )

    def test_llm_failure_returns_503_and_preserves_previous_report(self):
        analysis, _version = self._completed_analysis()

        with mock.patch(
                "analysis.views.ai_report_generator",
                _generate_with(FakeLLMClient(_fixture_text("Alpha."))),
        ):
            created = self.alice_client.post(
                f"/api/analyses/{analysis.id}/ai-report/"
            )
        self.assertEqual(created.status_code, 201)

        for error in (
                LLMRequestError("provider exploded"),
                LLMNotConfiguredError("LLM_API_KEY is not configured."),
        ):
            with mock.patch(
                    "analysis.views.ai_report_generator",
                    side_effect=error,
            ):
                response = self.alice_client.post(
                    f"/api/analyses/{analysis.id}/ai-report/"
                )

            self.assertEqual(response.status_code, 503)
            self.assertTrue(response.data["detail"])

            report = AIReport.objects.get(analysis=analysis)
            self.assertEqual(report.summary, "Alpha.")

        self.assertEqual(AIReport.objects.count(), 1)
