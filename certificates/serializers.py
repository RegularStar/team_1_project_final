from rest_framework import serializers
from .models import (
    Tag, Certificate, CertificateTag,
    CertificatePhase, CertificateStatistics, UserTag
)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class CertificateSerializer(serializers.ModelSerializer):
    # 읽기 시 태그 목록을 포함(쓰기 시 태그는 별도 업로드/관리로 처리)
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Certificate
        fields = [
            "id", "name", "description", "authority", "cert_type", "homepage",
            "rating", "expected_duration", "expected_duration_major", "tags"
        ]


class CertificatePhaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificatePhase
        fields = ["id", "certificate", "phase_name", "phase_type"]


class CertificateStatisticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateStatistics
        fields = [
            "id", "certificate", "exam_type", "year", "session",
            "registered", "applicants", "passers", "pass_rate"
        ]


class UserTagSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)  # 본인만
    class Meta:
        model = UserTag
        fields = ["id", "user", "tag"]
        read_only_fields = ["id", "user"]