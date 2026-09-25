"""Celery application. Worker: `celery -A engine.celery_app worker --pool=threads -l info`."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus_backend.settings")

app = Celery("nexus", include=["engine.tasks"])
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.update(
    task_acks_late=False,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)
