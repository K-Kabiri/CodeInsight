import time

from django.db import transaction
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
    @transaction.atomic
    def _execute_analysis(
            analysis: Analysis,
            analysis_metrics,
    ) -> None:

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
                analysis.project_version.source_file,
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

    @staticmethod
    def _run_metric(
            analysis_metric: AnalysisMetric,
            source_file,
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
            loader = get_loader(source_file.path)

            scope = loader.scope

            python_files = loader.load()

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