from django.db import models
from projects.models import ProjectVersion

# ========== Analysis ==========
class Analysis(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"


    project_version = models.ForeignKey(
        ProjectVersion,
        on_delete=models.CASCADE,
        related_name="analyses"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # Whether the caller asked for AI explanations on this run. Set at
    # creation from the dialog checkbox; default False so existing rows
    # and default paths are untouched.
    ai_requested = models.BooleanField(
        default=False
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True
    )

    overall_score = models.FloatField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )


    class Meta:
        ordering = ["-created_at"]


    def __str__(self):
        return f"Analysis #{self.id}"


# ========== Metric Definition ==========
class MetricDefinition(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    display_name = models.CharField(
        max_length=150
    )

    category = models.CharField(
        max_length=100
    )

    description = models.TextField(
        blank=True
    )

    unit = models.CharField(
        max_length=50,
        blank=True
    )

    higher_is_better = models.BooleanField(
        default=True
    )

    supports_llm = models.BooleanField(
        default=False
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):
        return self.display_name


# ========== Analysis Metric ==========
class AnalysisMetric(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"


    analysis = models.ForeignKey(
        Analysis,
        on_delete=models.CASCADE,
        related_name="metrics"
    )

    metric = models.ForeignKey(
        MetricDefinition,
        on_delete=models.PROTECT,
        related_name="analysis_results"
    )

    selected = models.BooleanField(
        default=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    value = models.FloatField(
        null=True,
        blank=True
    )

    detail = models.JSONField(
        null=True,
        blank=True
    )

    execution_time = models.FloatField(
        null=True,
        blank=True
    )

    error_message = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["analysis", "metric"],
                name="unique_analysis_metric"
            )
        ]


    def __str__(self):
        return f"{self.metric} - Analysis {self.analysis.id}"
