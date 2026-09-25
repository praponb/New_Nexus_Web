"""Entry points for running a generation task (Celery, background thread or inline)."""

from __future__ import annotations

import asyncio
import logging
import threading

from django.conf import settings

from .celery_app import app

logger = logging.getLogger(__name__)


def run_generation(task_id: str) -> None:
    from .orchestrator import run_pipeline

    asyncio.run(run_pipeline(task_id))


@app.task(name="engine.run_generation_task", bind=True)
def run_generation_task(self, task_id: str) -> str:
    logger.info("Starting generation task %s (celery id %s)", task_id, self.request.id)
    run_generation(task_id)
    return task_id


def dispatch(task) -> str | None:
    """Schedule `task` for execution and return the job id, if any.

    NEXUS_TASK_BACKEND: "celery" (default), "thread" (in-process background thread) or
    "inline" (blocking; tests only).
    """
    backend = getattr(settings, "NEXUS_TASK_BACKEND", "celery")
    task_id = str(task.id)
    if backend == "inline":
        run_generation(task_id)
        return None
    if backend == "thread":
        thread = threading.Thread(target=run_generation, args=(task_id,), name=f"nexus-gen-{task_id}", daemon=True)
        thread.start()
        return thread.name
    result = run_generation_task.delay(task_id)
    return result.id
