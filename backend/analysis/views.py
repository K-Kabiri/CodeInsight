from django.http import Http404
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
from projects.models import ProjectVersion


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
