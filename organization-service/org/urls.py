from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AssignmentRequestViewSet, OrganizationalUnitViewSet, ServiceViewSet

router = DefaultRouter()
router.register(r"org-units", OrganizationalUnitViewSet, basename="org-unit")
router.register(r"services", ServiceViewSet, basename="service")
router.register(r"assignment-requests", AssignmentRequestViewSet, basename="assignment-request")

urlpatterns = [
    path("", include(router.urls)),
]
