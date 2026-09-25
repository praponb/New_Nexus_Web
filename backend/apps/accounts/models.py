import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.crypto import get_random_string


class NexusUserManager(UserManager):
    """User manager that authenticates by email and auto-derives usernames."""

    def _unique_username(self, email: str) -> str:
        base = (email.split("@")[0] or "user")[:120]
        candidate = base
        while self.model.objects.filter(username=candidate).exists():
            candidate = f"{base}-{get_random_string(6).lower()}"
        return candidate

    def create_user(self, email=None, password=None, username=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        username = username or self._unique_username(email)
        return super().create_user(username=username, email=email, password=password, **extra_fields)

    def create_superuser(self, email=None, password=None, username=None, **extra_fields):
        email = self.normalize_email(email).lower()
        username = username or self._unique_username(email)
        return super().create_superuser(username=username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = NexusUserManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email
