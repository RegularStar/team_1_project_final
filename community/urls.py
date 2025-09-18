from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PostViewSet, PostCommentCreateView, CommentDetailView

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')

urlpatterns = [
    # /api/posts, /api/posts/{id}, /api/posts/{id}/like 는 router가 생성
    # 댓글 생성: POST /api/posts/{post_id}/comments
    path('posts/<int:post_id>/comments', PostCommentCreateView.as_view(), name='post-comments-create'),
    # 댓글 수정/삭제: PATCH/DELETE /api/comments/{comment_id}
    path('comments/<int:comment_id>', CommentDetailView.as_view(), name='comment-detail'),
]

urlpatterns += router.urls