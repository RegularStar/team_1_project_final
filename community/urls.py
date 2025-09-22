from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PostViewSet, PostCommentListCreateView, CommentDetailView

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')

urlpatterns = [
    path('posts/<int:post_id>/comments', PostCommentListCreateView.as_view(), name='post-comments'),
    path('comments/<int:comment_id>', CommentDetailView.as_view(), name='comment-detail'),
]
urlpatterns += router.urls