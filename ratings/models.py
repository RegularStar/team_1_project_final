# ratings/models.py
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from certificates.models import CertificatePhase  # ✅ 참조 대상 확정

User = settings.AUTH_USER_MODEL

class Rating(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ratings"
    )
    cert_phase = models.ForeignKey(
        CertificatePhase,
        on_delete=models.CASCADE,
        related_name="ratings",
        null=True,
        blank=True,   # ✅ 초기 마이그레이션 통과를 위해 허용
    )
    score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1~5 점수 범위"   # ✅ 점수 범위 설명 추가
    )
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rating"  # ✅ 테이블 이름 명시 (선택)
        unique_together = ("user", "cert_phase")
        ordering = ["-created_at"]

    def __str__(self):
        username = getattr(self.user, "username", str(self.user))
        phase_name = getattr(self.cert_phase, "phase_name", str(self.cert_phase))
        return f"Rating(user={username}, phase={phase_name}, score={self.score})"