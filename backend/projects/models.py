from django.contrib.auth.models import User
from django.db import models

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

    zip_file = models.FileField(
        upload_to="projects/"
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.project.name} v{self.version_number}"