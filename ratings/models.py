from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from certificates.models import Certificate

User = settings.AUTH_USER_MODEL

class Rating(models.Model):
    # ERD: rating
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="ratings")
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rating"
        unique_together = ("user", "certificate")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.certificate} ({self.rating})"