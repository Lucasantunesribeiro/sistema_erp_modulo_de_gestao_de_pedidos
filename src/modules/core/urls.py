from django.urls import path

from modules.core.views import ProtectedView, health_check

urlpatterns = [
    path("health", health_check, name="health_check"),
    path("api/v1/me", ProtectedView.as_view(), name="protected_me"),
]
