from django.db import models
from django.conf import settings
from certificates.models import CertificateLevel

User = settings.AUTH_USER_MODEL

class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    cert_level = models.ForeignKey(CertificateLevel, on_delete=models.CASCADE, related_name="ratings")
    score = models.IntegerField()
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "cert_level")
        ordering = ["-created_at"]