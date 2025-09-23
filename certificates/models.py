from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings

User = settings.AUTH_USER_MODEL


class Tag(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "tag"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Certificate(models.Model):
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    authority = models.CharField(max_length=255, blank=True)
    cert_type = models.CharField(max_length=100, blank=True)
    homepage = models.URLField(blank=True)

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    expected_duration = models.PositiveIntegerField(null=True, blank=True, help_text="예상 학습기간(주)")
    expected_duration_major = models.PositiveIntegerField(null=True, blank=True, help_text="전공자 기준(주)")

    tags = models.ManyToManyField("Tag", through="CertificateTag", related_name="certificates", blank=True)

    class Meta:
        db_table = "certificate"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CertificateTag(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        db_table = "certificate_tag"
        unique_together = ("certificate", "tag")


class CertificatePhase(models.Model):
    PHASE_TYPE_CHOICES = (("필기", "필기"), ("실기", "실기"))

    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="phases")
    phase_name = models.CharField(max_length=50)  # '1차', '2차' 등
    phase_type = models.CharField(max_length=10, choices=PHASE_TYPE_CHOICES)  # 필기/실기

    class Meta:
        db_table = "certificate_phase"
        unique_together = ("certificate", "phase_name", "phase_type")
        indexes = [models.Index(fields=["certificate", "phase_type"])]

    def __str__(self):
        return f"{self.certificate.name} - {self.phase_name} ({self.phase_type})"


class CertificateStatistics(models.Model):
    EXAM_TYPE_CHOICES = (("필기", "필기"), ("실기", "실기"))

    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="statistics")
    exam_type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES)
    year = models.PositiveIntegerField()
    session = models.CharField(max_length=20, blank=True, null=True)  # 회차

    registered = models.PositiveIntegerField(null=True, blank=True)  # 접수
    applicants = models.PositiveIntegerField(null=True, blank=True)  # 응시
    passers = models.PositiveIntegerField(null=True, blank=True)     # 합격
    pass_rate = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)  # 0~1

    class Meta:
        db_table = "certificate_statistics"
        ordering = ["-year", "exam_type", "session"]
        unique_together = ("certificate", "exam_type", "year", "session")
        indexes = [models.Index(fields=["certificate", "exam_type", "year"])]

    def __str__(self):
        s = f"{self.certificate.name} {self.year} {self.exam_type}"
        return f"{s} ({self.session})" if self.session else s


class UserTag(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="user_tags")

    class Meta:
        db_table = "user_tag"
        unique_together = ("user", "tag")

    def __str__(self):
        return f"{self.user} - {self.tag.name}"