"""
Django settings for the Nexus backend.

Configuration is driven by environment variables loaded from the repository
root `.env` file (see `.env.example`).
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent

load_dotenv(REPO_ROOT / ".env")


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return str(os.environ.get(name, default)).lower() in ("1", "true", "yes", "on")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me-nexus-secret-key-0123456789")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,testserver")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    "apps.accounts",
    "apps.projects",
    "apps.realtime",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nexus_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "nexus_backend.wsgi.application"
ASGI_APPLICATION = "nexus_backend.asgi.application"

# --- Database -----------------------------------------------------------------
# PostgreSQL when DB_ENGINE=postgres (docker-compose default), otherwise SQLite.
if env("DB_ENGINE", "sqlite").lower() in ("postgres", "postgresql"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "nexus"),
            "USER": env("POSTGRES_USER", "nexus"),
            "PASSWORD": env("POSTGRES_PASSWORD", "nexus"),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5433"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = REPO_ROOT / "static"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("NEXUS_MEDIA_ROOT", str(REPO_ROOT / "media")))
WORKSPACES_ROOT = MEDIA_ROOT / "workspaces"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Requirement uploads: 5 MB limit (validated in the serializer as well).
REQUIREMENT_MAX_BYTES = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# --- REST framework & JWT -----------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "nexus_backend.api.EnvelopeJSONRenderer",
    ],
    "EXCEPTION_HANDLER": "nexus_backend.api.envelope_exception_handler",
    "UNAUTHENTICATED_USER": None,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS ---------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
CORS_EXPOSE_HEADERS = ["Content-Disposition", "X-Checksum-SHA256"]

# --- Channels -----------------------------------------------------------------
REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
if env("CHANNEL_LAYER", "redis").lower() == "memory":
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            # redis-py >= 8 defaults socket_timeout to 5s, the same as channels_redis's 5s BZPOPMIN
            # block, so idle WebSocket consumers die with "Timeout reading". Keep the socket timeout
            # well above the blocking-pop window.
            "CONFIG": {
                "hosts": [{"address": REDIS_URL, "socket_timeout": 30, "socket_connect_timeout": 5}],
                "capacity": 5000,
                "expiry": 60,
            },
        }
    }

# --- Celery -------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_TIME_LIMIT = int(env("CELERY_TASK_TIME_LIMIT", str(90 * 60)))
CELERY_TASK_SOFT_TIME_LIMIT = int(env("CELERY_TASK_SOFT_TIME_LIMIT", str(85 * 60)))
# Workers consume this queue (`celery ... -Q <queue>`); test runs use a private queue so a
# developer's worker on the same Redis never picks up their jobs.
CELERY_TASK_DEFAULT_QUEUE = env("NEXUS_CELERY_QUEUE", "nexus")

# --- Nexus engine -------------------------------------------------------------
NEXUS_ENGINE_MODE = env("NEXUS_ENGINE_MODE", "mock")  # mock | live
NEXUS_TASK_BACKEND = env("NEXUS_TASK_BACKEND", "celery")  # celery | thread
NEXUS_MAX_QA_ITERATIONS = int(env("NEXUS_MAX_QA_ITERATIONS", "3"))
NEXUS_MONTHLY_GENERATION_QUOTA = int(env("NEXUS_MONTHLY_GENERATION_QUOTA", "25"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        "engine": {"level": env("ENGINE_LOG_LEVEL", "INFO")},
    },
}
