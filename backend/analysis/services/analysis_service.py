import logging
import time

from django.utils import timezone

from analysis.engines import get_engine
from analysis.loaders import get_loader
from analysis.models import Analysis, AnalysisMetric

logger = logging.getLogger(__name__)


def _generate_ai_report(analysis: Analysis) -> None:
    # Imported lazily so the analysis package never depends on the
    # reports package at module load time (reports already imports
    # analysis models; this keeps the import graph one-directional).
    from reports.services.ai_report_service import AIReportService

    AIReportService.generate(analysis)


# The report-generation hook the run calls after the metrics settle.
# Production default: the real service. Tests swap this module-level
# attribute for a fake — same injection pattern as the dispatcher.
ai_report_generator = _generate_ai_report


class AnalysisService:

    @staticmethod
    def run(analysis: Analysis) -> None:

        analysis_metrics = (
            AnalysisMetric.objects
            .select_related("metric")
            .filter(
                analysis=analysis,
                selected=True,
            )
        )

        if not analysis_metrics.exists():
            analysis.status = Analysis.Status.FAILED
            analysis.finished_at = timezone.now()

            analysis.save(
                update_fields=[
                    "status",
                    "finished_at",
                ]
            )

            raise ValueError(
                "At least one metric must be selected for analysis."
            )

        AnalysisService._execute_analysis(
            analysis,
            analysis_metrics,
        )

    @staticmethod
    def _execute_analysis(
            analysis: Analysis,
            analysis_metrics,
    ) -> None:
        """
        Run every selected metric and settle the Analysis.

        Deliberately NOT wrapped in `@transaction.atomic`: each status
        transition commits independently so a polling client observes
        the Analysis moving PENDING -> RUNNING -> COMPLETED/FAILED
        (api-layer spec user story 8). Per-metric failures are already
        contained by `_run_metric` and never abort the run.

        Metric failures are isolated to the failing metric row: one
        failed metric never fails the whole Analysis — the metrics
        that succeeded keep their results and the Analysis completes
        (FAILED only when every selected metric failed). When
        `ai_requested` is set and at least one metric succeeded, the
        AI report is generated here while the Analysis is still
        RUNNING — the Analysis flips to COMPLETED only after the
        report row exists (or generation failed and was logged), so
        the completed result shows metrics and AI text at once.

        The Input (`.py` / ZIP) is loaded exactly once and shared by
        all metrics — a project ZIP is extracted a single time, and
        the loader's temporary directory is cleaned up afterwards.
        """

        loader = get_loader(
            analysis.project_version.source_file.path
        )

        try:
            python_files = loader.load()

            scope = loader.scope

            analysis.status = Analysis.Status.RUNNING
            analysis.started_at = timezone.now()

            analysis.save(
                update_fields=[
                    "status",
                    "started_at",
                ]
            )

            # Metric failures are isolated to the metric row: one
            # failed metric never fails the whole Analysis — the
            # others keep their results. The Analysis is FAILED only
            # when every selected metric failed (the no-metrics case
            # was already rejected above).
            any_succeeded = False

            for analysis_metric in analysis_metrics:
                success = AnalysisService._run_metric(
                    analysis_metric,
                    python_files,
                    scope,
                )

                if success:
                    any_succeeded = True

            # The AI report explains only metrics that actually
            # completed, so generation runs whenever the Analysis
            # completes (at least one metric succeeded) and
            # `ai_requested` is set.
            if any_succeeded and analysis.ai_requested:
                AnalysisService._generate_report(analysis)

            analysis.status = (
                Analysis.Status.COMPLETED
                if any_succeeded
                else Analysis.Status.FAILED
            )

            analysis.finished_at = timezone.now()

            analysis.save(
                update_fields=[
                    "status",
                    "finished_at",
                ]
            )

        finally:
            cleanup = getattr(loader, "cleanup", None)

            if cleanup is not None:
                cleanup()

    @staticmethod
    def _generate_report(analysis: Analysis) -> None:
        """
        Generate the AI report while the Analysis is still RUNNING.

        Called only when every selected metric succeeded and
        `ai_requested` is True (the dispatcher decides). A failure —
        timeout, provider error, malformed JSON, missing key, or any
        unexpected error — is logged and swallowed: the Analysis
        still completes with its real metrics intact and no report
        row, which the UI later surfaces as "unavailable / retry"
        (the `ai_requested` flag makes that distinguishable from a
        run that never asked for AI).
        """
        try:
            ai_report_generator(analysis)
        except Exception as exc:
            logger.exception(
                "AI report generation failed for Analysis #%s: %s",
                analysis.id,
                exc,
            )

    @staticmethod
    def _run_metric(
            analysis_metric: AnalysisMetric,
            python_files,
            scope: str | None,
    ) -> bool:

        start_time = time.perf_counter()

        analysis_metric.status = AnalysisMetric.Status.RUNNING
        analysis_metric.error_message = ""

        analysis_metric.save(
            update_fields=[
                "status",
                "error_message",
            ]
        )

        try:
            engine = get_engine(
                analysis_metric.metric.name
            )

            value = engine.calculate(
                python_files,
                scope=scope,
            )

            analysis_metric.value = value
            analysis_metric.detail = (
                engine.calculate_detailed(
                    python_files,
                    scope=scope,
                )
            )
            analysis_metric.status = (
                AnalysisMetric.Status.COMPLETED
            )

            return True

        except Exception as exc:
            analysis_metric.status = (
                AnalysisMetric.Status.FAILED
            )
            analysis_metric.value = None
            analysis_metric.detail = None
            analysis_metric.error_message = str(exc)

            return False

        finally:
            analysis_metric.execution_time = (
                    time.perf_counter() - start_time
            )

            analysis_metric.save(
                update_fields=[
                    "status",
                    "value",
                    "detail",
                    "execution_time",
                    "error_message",
                ]
            )
