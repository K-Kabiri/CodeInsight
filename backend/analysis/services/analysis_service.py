import time

from django.utils import timezone

from analysis.engines import get_engine
from analysis.loaders import get_loader
from analysis.models import Analysis, AnalysisMetric


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

            has_failed_metric = False

            for analysis_metric in analysis_metrics:
                success = AnalysisService._run_metric(
                    analysis_metric,
                    python_files,
                    scope,
                )

                if not success:
                    has_failed_metric = True

            analysis.status = (
                Analysis.Status.FAILED
                if has_failed_metric
                else Analysis.Status.COMPLETED
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
