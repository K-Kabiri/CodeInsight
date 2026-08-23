import threading

from django.db import connections

from analysis.services.analysis_service import AnalysisService


class BackgroundAnalysisDispatcher:
    """
    Runs the synchronous AnalysisService on a daemon thread so the
    create endpoint can return immediately with a PENDING Analysis.

    This is the injection point for the API layer: tests replace the
    module-level dispatcher with the inline dispatcher (or patch
    `dispatch`) so API tests stay deterministic.

    The worker thread closes its own database connections when the
    run finishes — otherwise its Postgres session lingers and blocks
    the test runner from dropping the test database.
    """

    def dispatch(self, analysis) -> None:
        thread = threading.Thread(
            target=self._run_and_close,
            args=(analysis,),
            daemon=True,
        )
        thread.start()

    @staticmethod
    def _run_and_close(analysis) -> None:
        try:
            AnalysisService.run(analysis)
        finally:
            connections.close_all()


class InlineAnalysisDispatcher:
    """
    Runs the Analysis synchronously in the calling thread. Used by
    tests to exercise the full run without threads.
    """

    def dispatch(self, analysis) -> None:
        AnalysisService.run(analysis)
