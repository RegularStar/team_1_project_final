from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from certificates.models import Certificate

class Rating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings")
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="ratings")
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "certificate")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.certificate} ({self.rating})"

    @property
    def perceived_score(self) -> int:
        """Return the derived difficulty on a 10-point scale.

        Existing rows may still store legacy 5-point values, so we detect those
        and scale them up to keep the public API stable.
        """
        if self.rating is None:
            return 0
        return self.rating if self.rating > 5 else self.rating * 2
