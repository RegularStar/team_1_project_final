from django.contrib import admin

from .models import (
    Certificate,
    CertificatePhase,
    CertificateStatistics,
    CertificateTag,
    Tag,
    UserCertificate,
    UserTag,
)


class CertificateTagInline(admin.TabularInline):
    model = CertificateTag
    extra = 1


class CertificatePhaseInline(admin.TabularInline):
    model = CertificatePhase
    extra = 1


class CertificateStatisticsInline(admin.TabularInline):
    model = CertificateStatistics
    extra = 1


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "type",
        "authority",
        "rating",
        "expected_duration",
    )
    search_fields = (
        "name",
        "overview",
        "job_roles",
        "exam_method",
        "eligibility",
        "authority",
        "type",
        "tags__name",
    )
    list_filter = ("type", "authority")
    inlines = [CertificateTagInline, CertificatePhaseInline, CertificateStatisticsInline]
    exclude = ("tags",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(CertificatePhase)
class CertificatePhaseAdmin(admin.ModelAdmin):
    list_display = ("id", "certificate", "phase_name", "phase_type")
    list_filter = ("phase_type",)
    search_fields = ("phase_name", "certificate__name")


@admin.register(CertificateStatistics)
class CertificateStatisticsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "certificate",
        "exam_type",
        "year",
        "session",
        "registered",
        "applicants",
        "passers",
        "pass_rate",
    )
    list_filter = ("exam_type", "year")
    search_fields = ("certificate__name", "exam_type", "year")


@admin.register(CertificateTag)
class CertificateTagAdmin(admin.ModelAdmin):
    list_display = ("id", "certificate", "tag")
    search_fields = ("certificate__name", "tag__name")


@admin.register(UserTag)
class UserTagAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "tag")
    search_fields = ("user__username", "tag__name")


@admin.register(UserCertificate)
class UserCertificateAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "certificate", "acquired_at", "created_at")
    list_filter = ("acquired_at", "created_at")
    search_fields = ("user__username", "certificate__name")
