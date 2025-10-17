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
