# ratings/serializers.py
from rest_framework import serializers
from .models import Rating

class RatingSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Rating
        fields = ["id", "user", "cert_phase", "score", "content", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def validate(self, attrs):
        """
        (user, cert_phase) 중복을 DRF 단계에서 400으로 처리
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        cert_phase = attrs.get("cert_phase")

        # 생성 시에만 중복 체크 (수정 시에는 자기 자신 제외)
        if self.instance is None and user and cert_phase:
            if Rating.objects.filter(user=user, cert_phase=cert_phase).exists():
                raise serializers.ValidationError({"non_field_errors": ["이미 이 단계에 평점을 남겼습니다."]})

        return attrs