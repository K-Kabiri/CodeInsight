from rest_framework.routers import DefaultRouter

from analysis import views

router = DefaultRouter()
router.register(
    "metrics",
    views.MetricDefinitionViewSet,
    basename="metric",
)
router.register(
    "analyses",
    views.AnalysisViewSet,
    basename="analysis",
)

urlpatterns = router.urls
