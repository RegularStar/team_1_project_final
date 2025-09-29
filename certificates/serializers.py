from rest_framework import serializers
from .models import (
    Certificate, Tag, CertificateTag, UserCertificate, UserTag,
    CertificatePhase, CertificateStatistics
)

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]

class CertificateSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True, source="certificatetag_set__tag")

    class Meta:
        model = Certificate
        fields = [
            "id", "name", "overview", "job_roles", "exam_method", "eligibility",
            "rating", "expected_duration", "expected_duration_major",
            "authority", "type", "homepage", "tags"
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
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = UserTag
        fields = ["id", "user", "tag"]
        read_only_fields = ["id", "user"]