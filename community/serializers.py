from rest_framework import serializers
from .models import Post, PostComment, PostLike

class PostSerializer(serializers.ModelSerializer):
    comment_count = serializers.IntegerField(read_only=True)
    like_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = ["id", "user", "certificate", "title", "body", "created_at", "updated_at",
                  "comment_count", "like_count"]

class PostCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostComment
        fields = ["id", "user", "post", "body", "created_at"]

class PostLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostLike
        fields = ["id", "user", "post", "created_at"]