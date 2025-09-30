from django.db.models import Count
from rest_framework import viewsets, permissions, generics, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Post, PostComment, PostLike
from .serializers import PostSerializer, PostCommentSerializer, PostLikeSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    """작성자 또는 관리자만 수정/삭제 가능"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user and request.user.is_staff:
            return True
        return getattr(obj, "user_id", None) == request.user.id


class PostViewSet(viewsets.ModelViewSet):
    """
    /api/posts/  (GET, POST)
    /api/posts/{id}/ (GET, PATCH, DELETE)
    """
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Post.objects.select_related("certificate", "user")
            .annotate(
                comment_count=Count("comments", distinct=True),
                like_count=Count("likes", distinct=True),
            )
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # ---- 좋아요 추가/취소 ----
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        post = self.get_object()
        like, created = PostLike.objects.get_or_create(post=post, user=request.user)
        if created:
            return Response({"detail": "liked"}, status=status.HTTP_201_CREATED)
        return Response({"detail": "already liked"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], permission_classes=[permissions.IsAuthenticated])
    def unlike(self, request, pk=None):
        post = self.get_object()
        deleted, _ = PostLike.objects.filter(post=post, user=request.user).delete()
        if deleted:
            return Response({"detail": "unliked"}, status=status.HTTP_200_OK)
        return Response({"detail": "not liked"}, status=status.HTTP_400_BAD_REQUEST)


class PostCommentListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/posts/<post_id>/comments/
    """
    serializer_class = PostCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return PostComment.objects.filter(post_id=self.kwargs["post_id"]).order_by("id")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, post_id=self.kwargs["post_id"])