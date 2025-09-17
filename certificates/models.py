from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Tag(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Certificate(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    authority = models.CharField(max_length=255, blank=True)
    cert_type = models.CharField(max_length=100, blank=True)
    tags = models.ManyToManyField(Tag, through="CertificateTag")

    def __str__(self):
        return self.name


class CertificateTag(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("certificate", "tag")


class CertificateLevel(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="levels")
    level_name = models.CharField(max_length=255)
    level_description = models.TextField(blank=True)
    homepage = models.URLField(blank=True)

    def __str__(self):
        return f"{self.certificate.name} - {self.level_name}"


class CertificateStats(models.Model):
    cert_level = models.ForeignKey(CertificateLevel, on_delete=models.CASCADE, related_name="stats")
    year = models.CharField(max_length=10)
    applicants = models.IntegerField(null=True, blank=True)
    passers = models.IntegerField(null=True, blank=True)
    pass_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)


class UserCertificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="certificates")
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE)
    acquired_at = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "certificate")

class UserTag(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="user_tags")

    class Meta:
        db_table = "user_tag"
        unique_together = ("user", "tag")

    def __str__(self):
        return f"{self.user.username} - {self.tag.name}"