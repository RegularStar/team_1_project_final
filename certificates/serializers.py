from rest_framework import serializers
from .models import (
    Tag,
    Certificate,
    CertificatePhase,
    CertificateStatistics,
    UserTag,
    UserCertificate,
)

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class CertificateSerializer(serializers.ModelSerializer):
    # 태그는 기본적으로 읽기 전용 PK 리스트(쓰기 시는 별도 API로 처리하거나 커스텀 create/update에서 연결)
    tags = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Certificate
        fields = [
            "id", "name", "overview", "job_roles", "exam_method", "eligibility",
            "authority", "type", "homepage", "rating",
            "expected_duration", "expected_duration_major", "tags",
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
            "registered", "applicants", "passers", "pass_rate",
        ]


class UserTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTag
        fields = ["id", "user", "tag"]
        read_only_fields = ["user"]


class UserCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCertificate
        fields = ["id", "user", "certificate", "acquired_at", "created_at"]
        read_only_fields = ["id", "user", "created_at"]
