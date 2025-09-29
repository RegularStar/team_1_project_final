from rest_framework import serializers
from .models import Rating

class RatingSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Rating
        fields = ["id", "user", "certificate", "rating", "content", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def validate(self, attrs):
        # (user, certificate) 중복 사전 차단 → 400으로 응답
        request = self.context.get("request")
        user = getattr(request, "user", None)
        certificate = attrs.get("certificate")
        if self.instance is None and user and certificate:
            if Rating.objects.filter(user=user, certificate=certificate).exists():
                raise serializers.ValidationError({"non_field_errors": ["이미 이 자격증에 평점을 남겼습니다."]})
        return attrs