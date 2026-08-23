from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.pagination import StandardResultsSetPagination
from projects.models import Project
from projects.serializers import (
    ProjectSerializer,
    ProjectVersionSerializer,
)


class ProjectViewSet(viewsets.ModelViewSet):
    """
    Owner-scoped project management.

    Every queryset is filtered by the authenticated owner, so reading,
    changing, or uploading a version of someone else's project surfaces
    as a 404 — the existence of other users' data is never leaked.
    """

    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Project.objects.filter(
            owner=self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="versions",
    )
    def versions(self, request, pk=None):
        project = self.get_object()

        if request.method == "POST":
            serializer = ProjectVersionSerializer(
                data=request.data,
                context={
                    "request": request,
                    "project": project,
                },
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        serializer = ProjectVersionSerializer(
            self.paginate_queryset(
                project.versions.all()
            ),
            many=True,
            context={"request": request},
        )
        return self.get_paginated_response(serializer.data)
