from rest_framework import serializers
from .models import Post, PostComment, PostLike

class PostSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)  
    comment_count = serializers.IntegerField(read_only=True)
    like_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = ["id", "user", "cert_level", "title", "body", "created_at", "updated_at", "comment_count", "like_count"]
        read_only_fields = ["id", "user", "created_at", "updated_at", "comment_count", "like_count"]  # ✅

class PostCommentSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)  
    post = serializers.PrimaryKeyRelatedField(read_only=True)  

    class Meta:
        model = PostComment
        fields = ["id", "user", "post", "body", "created_at"]
        read_only_fields = ["id", "user", "post", "created_at"]  

class PostLikeSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)  
    post = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = PostLike
        fields = ["id", "user", "post", "created_at"]
        read_only_fields = ["id", "user", "post", "created_at"]