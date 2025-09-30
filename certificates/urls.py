from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TagViewSet,
    CertificateViewSet,
    CertificatePhaseViewSet,
    CertificateStatisticsViewSet,
    UserTagViewSet,
    UserCertificateViewSet,
)

router = DefaultRouter()
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"certificates", CertificateViewSet, basename="certificate")
router.register(r"phases", CertificatePhaseViewSet, basename="certificate-phase")
router.register(r"statistics", CertificateStatisticsViewSet, basename="certificate-statistics")
router.register(r"user-tags", UserTagViewSet, basename="user-tag")
router.register(r"user-certificates", UserCertificateViewSet, basename="user-certificate")

urlpatterns = [
    path("", include(router.urls)),
]
