from rest_framework import serializers
from .models import Rating

class RatingSerializer(serializers.ModelSerializer):
    def validate_certificate(self, certificate):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or user.is_anonymous:
            return certificate

        qs = Rating.objects.filter(user=user, certificate=certificate)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("이미 해당 자격증에 대한 평가가 존재합니다.")

        return certificate

    class Meta:
        model = Rating
        fields = ["id", "user", "certificate", "rating", "content", "created_at"]
        read_only_fields = ["id", "user", "created_at"]
