from django.contrib import admin
from .models import AIReport


@admin.register(AIReport)
class AIReportAdmin(admin.ModelAdmin):
    list_display = ("analysis", "model_name", "generated_at", "metric_summary")
    search_fields = ("analysis__id", "model_name")

    @admin.display(description="Per-metric content")
    def metric_summary(self, obj):
        content = obj.metric_content or {}
        if not content:
            return "— (empty)"
        return f"{len(content)} metric(s): {', '.join(sorted(content))}"
