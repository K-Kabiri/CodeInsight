from rest_framework.routers import DefaultRouter

from projects import views

router = DefaultRouter()
router.register(
    "projects",
    views.ProjectViewSet,
    basename="project",
)

urlpatterns = router.urls
