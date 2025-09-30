from rest_framework import viewsets, permissions, filters
from .models import Rating
from .serializers import RatingSerializer

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user and request.user.is_staff:
            return True
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
        return Rating.objects.select_related("certificate", "user")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)