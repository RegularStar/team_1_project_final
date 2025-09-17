from rest_framework import serializers
from .models import Rating

class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ["id", "user", "cert_level", "score", "content", "created_at"]
        read_only_fields = ["created_at"]