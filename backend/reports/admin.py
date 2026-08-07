from django.contrib import admin
from .models import AIReport


@admin.register(AIReport)
class AIReportAdmin(admin.ModelAdmin):
    list_display = ("analysis", "model_name", "generated_at")
    search_fields = ("analysis__id", "model_name")