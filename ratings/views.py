# ratings/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from .models import Rating
from .serializers import RatingSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    작성자 본인 or 관리자만 수정/삭제 가능
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

    def get_queryset(self):
        return Rating.objects.select_related("cert_phase", "user")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # DELETE 시 200 반환
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not (instance.user_id == request.user.id or request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("작성자만 삭제할 수 있습니다.")
        self.perform_destroy(instance)
        return Response({"detail": "deleted"}, status=status.HTTP_200_OK)