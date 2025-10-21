from django.conf import settings
from django.db import models

from certificates.models import Certificate, Tag


class JobTagContribution(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_tag_contributions",
    )
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        related_name="job_contributions",
    )
    certificates = models.ManyToManyField(
        Certificate,
        related_name="job_tag_contributions",
    )
    job_excerpt = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tag.name} by {self.user}" if self.tag_id else "JobTagContribution"


class SupportInquiry(models.Model):
    class Intent(models.TextChoices):
        TAG_REQUEST = "tag_request", "자격증 추가 요청"
        INFO_UPDATE = "info_update", "정보 수정"
        STATS_REQUEST = "stats_request", "통계 요청"
        BUG_REPORT = "bug_report", "시스템 오류 신고"
        GENERAL_HELP = "general_help", "기타 문의"

    class Status(models.TextChoices):
        PENDING = "pending", "대기"
        IN_PROGRESS = "in_progress", "처리 중"
        REJECTED = "rejected", "반려"
        RESOLVED = "resolved", "처리 완료"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_inquiries",
    )
    intent = models.CharField(max_length=32, choices=Intent.choices)
    summary = models.CharField(max_length=255)
    detail = models.TextField()
    conversation = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_intent_display()}] {self.summary}"
