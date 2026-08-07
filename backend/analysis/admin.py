from django.contrib import admin
from .models import Analysis, MetricDefinition, AnalysisMetric


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "project_version", "status", "overall_score", "created_at")
    list_filter = ("status",)
    search_fields = ("project_version__project__name",)


@admin.register(MetricDefinition)
class MetricDefinitionAdmin(admin.ModelAdmin):
    list_display = ("display_name", "category", "unit", "supports_llm")
    list_filter = ("category", "supports_llm")
    search_fields = ("name", "display_name")


@admin.register(AnalysisMetric)
class AnalysisMetricAdmin(admin.ModelAdmin):
    list_display = ("analysis", "metric", "status", "value")
    list_filter = ("status", "metric")