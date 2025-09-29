from django.db import models
from django.conf import settings
from certificates.models import Certificate

User = settings.AUTH_USER_MODEL

class Post(models.Model):
    # ERD: post
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    certificate = models.ForeignKey(Certificate, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class PostComment(models.Model):
    # ERD: post_comment
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class PostLike(models.Model):
    # ERD: post_like (PK 이름이 comment_id로 찍힌 건 오타로 보고 무시)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "post")