from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class Certificate(models.Model):
    # ERD: certificate
    name = models.CharField(max_length=255, unique=True, db_index=True)
    overview = models.TextField(blank=True)
    job_roles = models.TextField(blank=True)
    exam_method = models.TextField(blank=True)
    eligibility = models.TextField(blank=True)

    rating = models.IntegerField(null=True, blank=True)
    expected_duration = models.IntegerField(null=True, blank=True)
    expected_duration_major = models.IntegerField(null=True, blank=True)

    authority = models.CharField(max_length=255, blank=True)
    type = models.CharField(max_length=255, blank=True)
    homepage = models.TextField(blank=True)

    class Meta:
        db_table = "certificate"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    # ERD: tag
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "tag"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CertificateTag(models.Model):
    # ERD: certificate_tag
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        db_table = "certificate_tag"
        unique_together = ("certificate", "tag")


class UserCertificate(models.Model):
    # ERD: user_certificate
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="certificates")
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE)
    acquired_at = models.DateField(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "user_certificate"
        unique_together = ("user", "certificate")


class UserTag(models.Model):
    # ERD: user_tag
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="user_tags")

    class Meta:
        db_table = "user_tag"
        unique_together = ("user", "tag")
        ordering = ["id"]  # 페이지네이션 경고 방지


class CertificatePhase(models.Model):
    # ERD: certificate_phase
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="phases")
    phase_name = models.CharField(max_length=255)
    phase_type = models.CharField(max_length=255)

    class Meta:
        db_table = "certificate_phase"
        unique_together = ("certificate", "phase_name", "phase_type")

    def __str__(self):
        return f"{self.certificate.name} - {self.phase_name}({self.phase_type})"


class CertificateStatistics(models.Model):
    # ERD: certificate_statistics
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="statistics")
    exam_type = models.CharField(max_length=255)
    year = models.CharField(max_length=255)              # ERD: VARCHAR
    session = models.IntegerField(null=True, blank=True)
    registered = models.IntegerField(null=True, blank=True)  # ERD 표기 'registerd'는 오타로 보고 보정
    applicants = models.IntegerField(null=True, blank=True)
    passers = models.IntegerField(null=True, blank=True)
    pass_rate = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    class Meta:
        db_table = "certificate_statistics"
        unique_together = ("certificate", "exam_type", "year", "session")
        ordering = ["-year", "exam_type", "session"]