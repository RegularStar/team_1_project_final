from rest_framework import serializers
from .models import Certificate, CertificateLevel, CertificateStats, UserCertificate, Tag, UserTag

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]

class CertificateSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Certificate
        fields = ["id", "name", "description", "authority", "cert_type", "tags"]

class CertificateLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateLevel
        fields = ["id", "certificate", "level_name", "level_description", "homepage"]

class CertificateStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateStats
        fields = ["id", "cert_level", "year", "applicants", "passers", "pass_rate"]

class UserCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCertificate
        fields = ["id", "user", "certificate", "acquired_at"]

class UserTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTag
        fields = ["id", "user", "tag"]