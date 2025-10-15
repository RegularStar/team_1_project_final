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

certificate_phase_upload = CertificatePhaseViewSet.as_view({"post": "upload_phases"})
certificate_statistics_upload = CertificateStatisticsViewSet.as_view({"post": "upload_statistics"})

urlpatterns = [
    path("certificates/upload/phases/", certificate_phase_upload, name="certificate-upload-phases"),
    path("certificates/upload/statistics/", certificate_statistics_upload, name="certificate-upload-statistics"),
    path("", include(router.urls)),
]
