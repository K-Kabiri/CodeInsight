from django.contrib.auth.models import User
from django.db import models
from django.core.validators import FileExtensionValidator

# ========== Project ==========
class Project(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="projects"
    )

    name = models.CharField(max_length=150)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


#  ========== Project Version ==========
class ProjectVersion(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="versions"
    )

    version_number = models.PositiveIntegerField()

    source_file = models.FileField(
        upload_to="projects/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["py", "zip"]
            )
        ]
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-uploaded_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["project", "version_number"],
                name="unique_project_version",
            )
        ]

    def __str__(self):
        return f"{self.project.name} v{self.version_number}"
