from django.db import models
from django.conf import settings

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


class UserCertificate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_certificates")
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="certificate_holders")
    acquired_at = models.DateField(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "user_certificate"
        unique_together = ("user", "certificate")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.certificate.name}"
