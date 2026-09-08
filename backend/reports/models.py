from django.db import models
from analysis.models import Analysis


class AIReport(models.Model):
    analysis = models.OneToOneField(
        Analysis,
        on_delete=models.CASCADE,
        related_name="report"
    )

    summary = models.TextField()

    # Structured per-metric content keyed by canonical metric name,
    # each entry {"explanation": ..., "suggestions": [...]}. The overall
    # prose stays in `summary`; existing rows default to an empty dict.
    metric_content = models.JSONField(
        default=dict,
        blank=True,
    )

    strengths = models.TextField(
        blank=True
    )

    weaknesses = models.TextField(
        blank=True
    )

    recommendations = models.TextField()

    model_name = models.CharField(
        max_length=100
    )

    generated_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"AI Report for Analysis #{self.analysis.id}"