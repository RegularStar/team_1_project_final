# ratings/views.py
from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from .models import Rating
from .serializers import RatingSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    읽기: 모두 허용
    수정/삭제: 작성자 본인 또는 관리자만 허용
    """
    def has_object_permission(self, request, view, obj):
        # 읽기 권한은 모두 허용
        if request.method in permissions.SAFE_METHODS:
            return True
        # 관리자 허용
        if request.user and (request.user.is_staff or request.user.is_superuser):
            return True
        # 본인만 가능
        return obj.user_id == request.user.id


class RatingViewSet(viewsets.ModelViewSet):
    """
    /api/ratings/
    /api/ratings/{id}/
    """
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        # ✅ cert_phase → certificate 로 수정
        return Rating.objects.select_related("certificate", "user")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # 삭제 정책: 기본(ModelViewSet) 204 No Content 사용
    # (스펙상 200을 원하면 아래 오버라이드 주석 해제)
    # def destroy(self, request, *args, **kwargs):
    #     instance = self.get_object()
    #     if not (instance.user_id == request.user.id or request.user.is_staff or request.user.is_superuser):
    #         raise PermissionDenied("작성자만 삭제할 수 있습니다.")
    #     self.perform_destroy(instance)
    #     return Response({"detail": "deleted"}, status=status.HTTP_200_OK)