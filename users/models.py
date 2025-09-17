# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):

    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "user" 