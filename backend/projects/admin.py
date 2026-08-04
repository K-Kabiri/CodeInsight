from django.contrib import admin

from .models import Project, ProjectVersion

admin.site.register(Project)
admin.site.register(ProjectVersion)