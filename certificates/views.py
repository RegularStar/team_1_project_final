from rest_framework import viewsets, permissions, filters
from .models import (
    Tag,
    Certificate,
    CertificatePhase,
    CertificateStatistics,
    UserTag,
    UserCertificate,
)
from .serializers import (
    TagSerializer,
    CertificateSerializer,
    CertificatePhaseSerializer,
    CertificateStatisticsSerializer,
    UserTagSerializer,
    UserCertificateSerializer,
)

class IsAdminOrReadOnly(permissions.BasePermission):
    """GET은 모두, POST/PATCH/DELETE는 관리자만"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


# ---- Tag ----
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    permission_classes = [IsAdminOrReadOnly]


# ---- Certificate ----
class CertificateViewSet(viewsets.ModelViewSet):
    queryset = Certificate.objects.all().order_by("name")
    serializer_class = CertificateSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "overview", "job_roles", "exam_method", "eligibility", "authority", "type"]
    ordering_fields = ["name"]


# ---- Phase ----
class CertificatePhaseViewSet(viewsets.ModelViewSet):
    queryset = CertificatePhase.objects.select_related("certificate").all()
    serializer_class = CertificatePhaseSerializer
    permission_classes = [IsAdminOrReadOnly]


# ---- Statistics ----
class CertificateStatisticsViewSet(viewsets.ModelViewSet):
    queryset = CertificateStatistics.objects.select_related("certificate").all()
    serializer_class = CertificateStatisticsSerializer
    permission_classes = [IsAdminOrReadOnly]


# ---- UserTag (내 태그만 관리) ----
class UserTagViewSet(viewsets.ModelViewSet):
    serializer_class = UserTagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserTag.objects.select_related("tag").filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserCertificateViewSet(viewsets.ModelViewSet):
    serializer_class = UserCertificateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserCertificate.objects.select_related("certificate").filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
