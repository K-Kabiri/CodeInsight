from rest_framework import serializers

from reports.models import AIReport


class AIReportSerializer(serializers.ModelSerializer):
    """
    The stored report exactly as the results screen needs it: the
    overall summary, the per-metric content, and how/when it was
    produced. Read-only surface — the report is created by the
    pipeline run (ticket 03) or regenerated via POST.
    """

    class Meta:
        model = AIReport
        fields = [
            "summary",
            "metric_content",
            "model_name",
            "generated_at",
        ]
        read_only_fields = fields
