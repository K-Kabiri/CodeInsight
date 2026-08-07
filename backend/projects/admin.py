from django.contrib import admin
from .models import Project, ProjectVersion


class ProjectVersionInline(admin.TabularInline):
    model = ProjectVersion
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "created_at",
    )

    search_fields = (
        "name",
        "owner__username",
    )

    list_filter = (
        "created_at",
    )

    inlines = [
        ProjectVersionInline,
    ]


@admin.register(ProjectVersion)
class ProjectVersionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "version_number",
        "uploaded_at",
    )

    search_fields = (
        "project__name",
    )