from analysis.models import Analysis, AnalysisMetric
from reports.ai_errors import AIReportError
from reports.llm import LLMClient
from reports.models import AIReport
from reports.prompt_builder import build_messages
from reports.response_parser import parse_response


class AIReportService:
    """
    Turns one Analysis's completed, persisted results into the one
    AIReport row: build the evidence prompt, call the LLM seam, parse
    the structured JSON, and create-or-update the report.

    The LLM client is injectable so tests pass a fake (ADR-0002
    spirit); the default reads the provider settings. Whether a
    failure should abort or be contained is the caller's decision —
    the Analysis run swallows it (ticket 03), while the regenerate
    endpoint surfaces it (ticket 04).
    """

    @staticmethod
    def generate(
            analysis: Analysis,
            client=None,
    ) -> AIReport:
        completed = (
            analysis.metrics
            .filter(
                selected=True,
                status=AnalysisMetric.Status.COMPLETED,
            )
            .count()
        )

        if completed == 0:
            raise AIReportError(
                "An AI report requires at least one completed "
                "metric result."
            )

        if client is None:
            client = LLMClient()

        messages = build_messages(analysis)
        text = client.chat(messages)
        parsed = parse_response(text)

        # The four-category superset layout is not produced: the old
        # columns stay blank and only the agreed summary +
        # per-metric content are stored (ticket 01 note).
        report, _created = AIReport.objects.update_or_create(
            analysis=analysis,
            defaults={
                "summary": parsed["summary"],
                "metric_content": parsed["metric_content"],
                "strengths": "",
                "weaknesses": "",
                "recommendations": "",
                "model_name": client.model,
            },
        )

        return report
