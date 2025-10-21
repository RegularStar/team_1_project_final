from django.contrib import admin

from .models import JobTagContribution, SupportInquiry


@admin.register(SupportInquiry)
class SupportInquiryAdmin(admin.ModelAdmin):
    list_display = ("id", "intent", "user", "summary", "status", "created_at")
    list_filter = ("intent", "status", "created_at")
    search_fields = ("summary", "detail", "user__username", "user__email")
    readonly_fields = ("conversation", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("user", "intent", "summary", "detail", "status")}),
        ("대화 기록", {"fields": ("conversation",), "classes": ("collapse",)}),
        ("메타", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(JobTagContribution)
class JobTagContributionAdmin(admin.ModelAdmin):
    list_display = ("id", "tag", "user", "created_at")
    list_filter = ("tag", "created_at")
    search_fields = ("tag__name", "user__username", "user__email")
