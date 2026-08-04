from django.contrib import admin

from .models import Analysis, AnalysisMetric, MetricDefinition

admin.site.register(Analysis)
admin.site.register(AnalysisMetric)
admin.site.register(MetricDefinition)