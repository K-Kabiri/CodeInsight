from django.urls import path

from accounts import views

urlpatterns = [
    path(
        "auth/token/",
        views.ObtainTokenView.as_view(),
        name="api-token-obtain",
    ),
    path(
        "auth/register/",
        views.RegisterView.as_view(),
        name="api-register",
    ),
    path(
        "me/",
        views.MeView.as_view(),
        name="api-me",
    ),
]
