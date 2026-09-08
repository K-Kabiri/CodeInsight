from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from analysis.models import Analysis, MetricDefinition
from analysis.serializers import (
    AnalysisCreateSerializer,
    AnalysisSerializer,
    MetricDefinitionSerializer,
)
from analysis.services.dispatcher import BackgroundAnalysisDispatcher
from config.pagination import StandardResultsSetPagination
from projects.models import ProjectVersion
from reports.ai_errors import AIReportError
from reports.models import AIReport
from reports.serializers import AIReportSerializer


# The dispatcher every Analysis create goes through. Tests swap this
# module-level instance for the inline dispatcher.
dispatcher = BackgroundAnalysisDispatcher()


def _generate_ai_report(analysis):
    # Lazy import so this module never loads the reports service
    # graph at import time (reports already depends on analysis).
    from reports.services.ai_report_service import AIReportService

    return AIReportService.generate(analysis)


# The report-generation callable the ai-report POST goes through.
# Tests swap this module-level attribute for a fake that injects an
# LLM client (same injection pattern as `dispatcher` above).
ai_report_generator = _generate_ai_report


class MetricDefinitionViewSet(ReadOnlyModelViewSet):
    """
    Public metric catalog: the 12 seeded metric definitions.

    Readable without authentication so the frontend can render metric
    selection before a user logs in.
    """

    queryset = MetricDefinition.objects.all().order_by("name")
    serializer_class = MetricDefinitionSerializer
    permission_classes = [AllowAny]


class AnalysisViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Owner-scoped Analysis lifecycle: create (returns immediately with
    a PENDING Analysis), list, and detail with per-metric results.
    Analyses cannot be edited once created, but a settled run
    (COMPLETED/FAILED) may be deleted; a PENDING/RUNNING run is
    refused with 409 because its worker thread is still writing rows.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = (
            Analysis.objects
            .filter(
                project_version__project__owner=self.request.user,
            )
            .select_related("project_version")
            .prefetch_related("metrics__metric")
        )

        # Owner-scoped filter by project version (the comparison screen
        # fetches one version's Analyses). A version that is not the
        # caller's — or does not exist, or is not even a number — is
        # indistinguishable from nothing: 404, never leaking other
        # users' data, matching the create-endpoint contract.
        version_id = self.request.query_params.get("project_version")

        if version_id is not None:
            try:
                owned_version = (
                    ProjectVersion.objects
                    .filter(
                        pk=version_id,
                        project__owner=self.request.user,
                    )
                    .first()
                )
            except ValueError:
                # Malformed filter value (e.g. "?project_version=abc"):
                # the PK conversion never succeeds, so there is nothing
                # to filter by — treat it like a missing version.
                owned_version = None

            if owned_version is None:
                raise Http404

            queryset = queryset.filter(
                project_version=owned_version,
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return AnalysisCreateSerializer

        return AnalysisSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        analysis = serializer.save()

        # The response reflects the state at creation time (PENDING);
        # execution is dispatched only after the response is built so
        # the contract is stable whether the dispatcher is background
        # (production) or inline (tests).
        output = AnalysisSerializer(
            analysis,
            context={"request": request},
        )
        response = Response(
            output.data,
            status=status.HTTP_201_CREATED,
        )

        dispatcher.dispatch(analysis)

        return response

    def destroy(self, request, *args, **kwargs):
        """
        Delete one of the caller's settled Analyses. Runs that are
        still PENDING or RUNNING cannot be removed: their background
        worker is mid-write, so deleting the row would race it.
        """
        analysis = self.get_object()

        if analysis.status in (
            Analysis.Status.PENDING,
            Analysis.Status.RUNNING,
        ):
            return Response(
                {
                    "detail": (
                        "An analysis that is still pending or running "
                        "cannot be deleted. Wait for it to finish and "
                        "try again."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        return super().destroy(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="ai-report",
    )
    def ai_report(self, request, pk=None):
        """
        The owner-scoped AI report surface for one Analysis.

        GET returns the stored report, or 404 when it was never
        generated. POST synchronously generates-or-regenerates the
        whole report for a COMPLETED Analysis (the UI's retry and
        regenerate actions); PENDING/RUNNING/FAILED runs are rejected
        with a clear 409, and an LLM failure surfaces as a 503 that
        leaves any previously stored report intact. A non-owner (or
        nonexistent) Analysis is an indistinguishable 404 via the
        owner-scoped `get_object`.
        """
        analysis = self.get_object()

        if request.method == "POST":
            if analysis.status != Analysis.Status.COMPLETED:
                return Response(
                    {
                        "detail": (
                            "The AI report can only be generated for "
                            "a COMPLETED analysis (current status: "
                            f"{analysis.status})."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            existed = AIReport.objects.filter(
                analysis=analysis
            ).exists()

            try:
                report = ai_report_generator(analysis)
            except AIReportError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            return Response(
                AIReportSerializer(report).data,
                status=(
                    status.HTTP_200_OK
                    if existed
                    else status.HTTP_201_CREATED
                ),
            )

        try:
            report = analysis.report
        except AIReport.DoesNotExist:
            raise Http404

        return Response(AIReportSerializer(report).data)
