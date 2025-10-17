import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class Tag(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Certificate(models.Model):
    name = models.CharField(max_length=255, unique=True)
    overview = models.TextField(blank=True)
    job_roles = models.TextField(blank=True)
    exam_method = models.TextField(blank=True)
    eligibility = models.TextField(blank=True)
    authority = models.CharField(max_length=255, blank=True)
    type = models.CharField(max_length=255, blank=True)
    homepage = models.TextField(blank=True)
    rating = models.IntegerField(null=True, blank=True)
    expected_duration = models.IntegerField(null=True, blank=True)
    expected_duration_major = models.IntegerField(null=True, blank=True)
    tags = models.ManyToManyField(Tag, through="CertificateTag", related_name="certificates")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CertificateTag(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("certificate", "tag")


class CertificatePhase(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="phases")
    phase_name = models.CharField(max_length=255)
    phase_type = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("certificate", "phase_name", "phase_type")
        ordering = ["certificate_id", "phase_name"]

    def __str__(self):
        return f"{self.certificate.name} - {self.phase_name}"


class CertificateStatistics(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="statistics")
    exam_type = models.CharField(max_length=255, default="필기")
    year = models.CharField(max_length=10)  # 문자열 저장
    session = models.IntegerField(null=True, blank=True)
    registered = models.IntegerField(null=True, blank=True)
    applicants = models.IntegerField(null=True, blank=True)
    passers = models.IntegerField(null=True, blank=True)
    pass_rate = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    class Meta:
        unique_together = ("certificate", "exam_type", "year", "session")
        ordering = ["certificate_id", "year", "session"]


class UserTag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="user_tags")

    class Meta:
        db_table = "user_tag"
        unique_together = ("user", "tag")
        ordering = ["id"]

    def __str__(self):
        return f"{self.user.username} - {self.tag.name}"


def user_certificate_upload_to(instance, filename):
    extension = filename.split(".")[-1] if "." in filename else ""
    unique_name = uuid.uuid4().hex
    suffix = f".{extension}" if extension else ""
    return f"user_certificates/{instance.user_id}/{unique_name}{suffix}"


class UserCertificate(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = (
        (STATUS_PENDING, "심사중"),
        (STATUS_APPROVED, "등록완료"),
        (STATUS_REJECTED, "반려"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_certificates")
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="certificate_holders")
    acquired_at = models.DateField(null=True, blank=True)
    evidence = models.FileField(upload_to=user_certificate_upload_to, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    review_note = models.CharField(max_length=255, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_certificates",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_certificate"
        unique_together = ("user", "certificate")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.certificate.name} ({self.status})"

    @property
    def is_pending(self) -> bool:
        return self.status == self.STATUS_PENDING

    @property
    def is_approved(self) -> bool:
        return self.status == self.STATUS_APPROVED

    @property
    def is_rejected(self) -> bool:
        return self.status == self.STATUS_REJECTED

    def mark_approved(self, reviewer, note: str | None = None):
        self.status = self.STATUS_APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = (note or "")[:255]
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

    def mark_rejected(self, reviewer, note=""):
        self.status = self.STATUS_REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = note[:255]
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])
