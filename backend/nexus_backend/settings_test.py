"""Settings for the automated test-suite: SQLite, in-memory channels, temp media."""

import tempfile
from pathlib import Path

from .settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="nexus-test-media-"))
WORKSPACES_ROOT = MEDIA_ROOT / "workspaces"
NEXUS_ENGINE_MODE = "mock"
NEXUS_TASK_BACKEND = "inline"
CELERY_TASK_ALWAYS_EAGER = True
