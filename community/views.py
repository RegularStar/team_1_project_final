from django.db.models import Count
from rest_framework import viewsets, permissions, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound

from .models import Post, PostComment, PostLike
from .serializers import PostSerializer, PostCommentSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    읽기: 모두 허용
    쓰기/수정/삭제: 작성자 본인 또는 관리자(superuser/staff) 허용
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # ✅ 관리자 우선 허용
        if request.user and (request.user.is_superuser or request.user.is_staff):
            return True
        # 작성자 본인만
        return getattr(obj, "user_id", None) == request.user.id


class PostViewSet(viewsets.ModelViewSet):
    """
    /api/posts
    /api/posts/{id}
    /api/posts/{id}/like  (POST, DELETE)
    """
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Post.objects
            .select_related("cert_level")
            .annotate(
                comment_count=Count("comments", distinct=True),
                like_count=Count("likes", distinct=True),
            )
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # 명세: 삭제 200으로 응답
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # ✅ 관리자 허용
        if not (request.user.is_superuser or request.user.is_staff) and instance.user_id != request.user.id:
            raise PermissionDenied("작성자만 삭제할 수 있습니다.")
        self.perform_destroy(instance)
        return Response({"detail": "deleted"}, status=status.HTTP_200_OK)

    # 좋아요 ON
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        post = self.get_object()
        PostLike.objects.get_or_create(user=request.user, post=post)
        return Response({"detail": "liked"}, status=status.HTTP_200_OK)

    # 좋아요 OFF
    @like.mapping.delete
    def unlike(self, request, pk=None):
        post = self.get_object()
        PostLike.objects.filter(user=request.user, post=post).delete()
        return Response({"detail": "unliked"}, status=status.HTTP_200_OK)


class PostCommentListCreateView(generics.ListCreateAPIView):
    """
    GET /api/posts/{post_id}/comments   -> 해당 게시글의 댓글 목록
    POST /api/posts/{post_id}/comments  -> 해당 게시글에 댓글 작성
    """
    serializer_class = PostCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        post_id = self.kwargs.get("post_id")
        return (
            PostComment.objects
            .select_related("post")
            .filter(post_id=post_id)
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        post_id = self.kwargs.get("post_id")
        try:
            post = Post.objects.get(pk=post_id)
        except Post.DoesNotExist:
            raise NotFound("post not found")
        serializer.save(user=self.request.user, post=post)


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/comments/{comment_id}
    """
    serializer_class = PostCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    lookup_url_kwarg = "comment_id"

    def get_queryset(self):
        return PostComment.objects.select_related("post")

    # 명세: 삭제 200으로 응답
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        # ✅ 관리자 허용
        if not (request.user.is_superuser or request.user.is_staff) and obj.user_id != request.user.id:
            raise PermissionDenied("작성자만 삭제할 수 있습니다.")
        self.perform_destroy(obj)
        return Response({"detail": "deleted"}, status=status.HTTP_200_OK)