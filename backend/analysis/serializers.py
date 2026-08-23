from django.db import transaction
from django.http import Http404
from rest_framework import serializers

from analysis.models import Analysis, AnalysisMetric, MetricDefinition
from projects.models import ProjectVersion


class MetricDefinitionSerializer(serializers.ModelSerializer):
    """The seeded catalog entry exactly as the frontend needs it."""

    class Meta:
        model = MetricDefinition
        fields = [
            "name",
            "display_name",
            "category",
            "description",
            "unit",
            "higher_is_better",
            "supports_llm",
        ]


class AnalysisMetricSerializer(serializers.ModelSerializer):
    """One metric's result inside an Analysis detail."""

    name = serializers.CharField(
        source="metric.name",
        read_only=True,
    )
    display_name = serializers.CharField(
        source="metric.display_name",
        read_only=True,
    )

    class Meta:
        model = AnalysisMetric
        fields = [
            "name",
            "display_name",
            "status",
            "value",
            "execution_time",
            "error_message",
            "detail",
        ]


class AnalysisSerializer(serializers.ModelSerializer):
    """
    Analysis list/detail: the status lifecycle plus per-metric
    results. `detail` carries the persisted engine output, including
    scope/completeness (ADR-0001); `not_applicable` metrics appear
    with a null value and their reason, never blocking the Analysis.
    """

    project_version = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )
    metrics = AnalysisMetricSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Analysis
        fields = [
            "id",
            "project_version",
            "status",
            "started_at",
            "finished_at",
            "overall_score",
            "created_at",
            "metrics",
        ]


class AnalysisCreateSerializer(serializers.ModelSerializer):
    """
    Creating an Analysis: an owned project version plus at least one
    metric selected by canonical name. The Analysis and its metric
    rows are created together in one transaction; execution is left
    to the dispatcher so the endpoint returns immediately with the
    PENDING Analysis.
    """

    metrics = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
    )

    class Meta:
        model = Analysis
        fields = ["project_version", "metrics"]

    def validate_project_version(self, value):
        request = self.context["request"]
        owned = ProjectVersion.objects.filter(
            pk=value.pk,
            project__owner=request.user,
        ).exists()

        # A version that is not the caller's is indistinguishable
        # from one that does not exist (spec: 404, never leak).
        if not owned:
            raise Http404

        return value

    def validate_metrics(self, value):
        names = list(dict.fromkeys(value))

        if not names:
            raise serializers.ValidationError(
                "At least one metric must be selected."
            )

        definitions = {
            definition.name: definition
            for definition in MetricDefinition.objects.filter(
                name__in=names,
            )
        }

        missing = set(names) - set(definitions)

        if missing:
            raise serializers.ValidationError(
                "Unknown metric(s): "
                + ", ".join(sorted(missing))
            )

        return names

    def create(self, validated_data):
        metric_names = validated_data.pop("metrics")

        with transaction.atomic():
            analysis = Analysis.objects.create(
                project_version=validated_data["project_version"],
            )

            definitions = MetricDefinition.objects.filter(
                name__in=metric_names,
            )

            AnalysisMetric.objects.bulk_create(
                [
                    AnalysisMetric(
                        analysis=analysis,
                        metric=definition,
                        selected=True,
                    )
                    for definition in definitions
                ]
            )

        return analysis
