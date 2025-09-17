# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    기본 로그인: username / password
    추가 필드: name, phone (선택)
    """
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "user"  # 테이블 이름 명시 (선택)