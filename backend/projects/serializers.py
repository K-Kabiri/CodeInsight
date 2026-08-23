from rest_framework import serializers

from analysis.loaders import get_loader
from projects.models import Project, ProjectVersion


class ProjectSerializer(serializers.ModelSerializer):
    """Owner is never client-supplied: it comes from the request."""

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class ProjectVersionSerializer(serializers.ModelSerializer):
    """
    Uploading a version of a project.

    The Input kind (one `.py` file or a `.zip` archive) is validated by
    the same loader the analysis engines use, so the API can never
    accept a file the engines cannot analyze. Version numbers are
    assigned by the server (1, 2, 3, ... per project), never by the
    client.
    """

    class Meta:
        model = ProjectVersion
        fields = [
            "id",
            "version_number",
            "source_file",
            "uploaded_at",
        ]
        read_only_fields = [
            "id",
            "version_number",
            "uploaded_at",
        ]

    def validate_source_file(self, value):
        try:
            get_loader(value.name)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def create(self, validated_data):
        project = self.context["project"]
        last_version = (
            ProjectVersion.objects
            .filter(project=project)
            .order_by("version_number")
            .last()
        )
        validated_data["version_number"] = (
            last_version.version_number + 1
            if last_version
            else 1
        )
        validated_data["project"] = project
        return super().create(validated_data)
