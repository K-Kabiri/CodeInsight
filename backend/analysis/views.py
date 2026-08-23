from rest_framework import mixins, status, viewsets
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


# The dispatcher every Analysis create goes through. Tests swap this
# module-level instance for the inline dispatcher.
dispatcher = BackgroundAnalysisDispatcher()


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
    viewsets.GenericViewSet,
):
    """
    Owner-scoped Analysis lifecycle: create (returns immediately with
    a PENDING Analysis), list, and detail with per-metric results.
    Analyses are immutable once created — no update/destroy endpoints.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return (
            Analysis.objects
            .filter(
                project_version__project__owner=self.request.user,
            )
            .select_related("project_version")
            .prefetch_related("metrics__metric")
        )

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
