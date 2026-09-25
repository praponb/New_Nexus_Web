"""EventSink: the single place pipeline events are persisted and broadcast.

Each event is written as an ``AgentStepLog`` row first (so reconnecting clients can
replay history) and then pushed to the project's Channels group.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from asgiref.sync import sync_to_async
from django.db.models import Max
from django.utils import timezone as dj_timezone

from apps.projects.models import AgentStepLog, GenerationTask, LogType, Project, ProjectStatus

from . import broadcast

MAX_CONTENT_CHARS = 20_000

PHASE_PROGRESS = {
    ProjectStatus.QUEUED: 0,
    ProjectStatus.PLANNING: 5,
    ProjectStatus.GENERATING: 25,
    ProjectStatus.TESTING: 65,
    ProjectStatus.PACKAGING: 90,
    ProjectStatus.COMPLETED: 100,
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def log_payload(log: AgentStepLog) -> dict:
    return {
        "id": log.id,
        "task_id": str(log.task_id),
        "agent_name": log.agent_name,
        "log_type": log.log_type,
        "content": log.content,
        "metadata": log.metadata,
        "sequence_num": log.sequence_num,
        "timestamp": _iso(log.created_at),
    }


def phase_payload(task: GenerationTask, *, status: str, active_agents: list[str], files_created_count: int) -> dict:
    return {
        "task_id": str(task.id),
        "status": status,
        "current_phase": task.current_phase,
        "progress_percentage": task.progress_percentage,
        "qa_iterations": task.qa_iterations,
        "active_agents": active_agents,
        "files_created_count": files_created_count,
    }


class EventSink:
    def __init__(self, task_id, project_id):
        self.task_id = task_id
        self.project_id = project_id
        self._lock = asyncio.Lock()
        self._seq: int | None = None
        self.files_created: set[str] = set()
        self.active_agents: list[str] = []
        self.status: str = ProjectStatus.QUEUED

    # ------------------------------------------------------------------ logs
    async def log(self, agent_name: str, log_type: str, content: str, metadata: dict | None = None) -> dict:
        content = content if len(content) <= MAX_CONTENT_CHARS else content[:MAX_CONTENT_CHARS] + "\n… [truncated]"
        async with self._lock:
            if self._seq is None:
                self._seq = await sync_to_async(self._max_seq)()
            self._seq += 1
            log = await sync_to_async(AgentStepLog.objects.create)(
                task_id=self.task_id,
                agent_name=agent_name,
                log_type=log_type,
                content=content,
                metadata=metadata or {},
                sequence_num=self._seq,
            )
        payload = log_payload(log)
        await broadcast.send_event(self.project_id, "log_event", payload)
        return payload

    def _max_seq(self) -> int:
        return AgentStepLog.objects.filter(task_id=self.task_id).aggregate(m=Max("sequence_num"))["m"] or 0

    async def system(self, content: str, agent_name: str = "System", **metadata) -> None:
        await self.log(agent_name, LogType.SYSTEM, content, metadata)

    async def file_created(self, agent_name: str, rel_path: str, tool: str = "") -> None:
        is_new = rel_path not in self.files_created
        self.files_created.add(rel_path)
        await broadcast.send_event(
            self.project_id,
            "file_created",
            {
                "task_id": str(self.task_id),
                "agent_name": agent_name,
                "path": rel_path,
                "tool": tool,
                "is_new": is_new,
                "files_created_count": len(self.files_created),
            },
        )

    # ------------------------------------------------------------------ phases
    async def phase(
        self,
        status: str,
        *,
        progress: int | None = None,
        active_agents: list[str] | None = None,
        announce: bool = True,
    ) -> None:
        self.status = status
        if active_agents is not None:
            self.active_agents = active_agents
        pct = PHASE_PROGRESS.get(status, 0) if progress is None else progress
        task = await sync_to_async(self._save_phase)(status, pct)
        if announce:
            await self.log("System", LogType.PHASE_CHANGE, f"Phase → {ProjectStatus(status).label}", {"phase": status})
        await self._send_phase(task)

    async def progress(self, pct: int, active_agents: list[str] | None = None) -> None:
        if active_agents is not None:
            self.active_agents = active_agents
        task = await sync_to_async(self._save_progress)(pct)
        await self._send_phase(task)

    async def set_qa_iterations(self, n: int) -> None:
        await sync_to_async(GenerationTask.objects.filter(id=self.task_id).update)(qa_iterations=n)

    async def _send_phase(self, task: GenerationTask) -> None:
        await broadcast.send_event(
            self.project_id,
            "phase_update",
            phase_payload(
                task,
                status=self.status,
                active_agents=self.active_agents,
                files_created_count=len(self.files_created),
            ),
        )

    def _save_phase(self, status: str, pct: int) -> GenerationTask:
        task = GenerationTask.objects.get(id=self.task_id)
        task.current_phase = status
        task.progress_percentage = max(0, min(100, pct))
        fields = ["current_phase", "progress_percentage"]
        if status in (ProjectStatus.PLANNING, ProjectStatus.TESTING) and task.started_at is None:
            task.started_at = dj_timezone.now()
            fields.append("started_at")
        if status in (ProjectStatus.COMPLETED, ProjectStatus.FAILED):
            task.finished_at = dj_timezone.now()
            fields.append("finished_at")
        task.save(update_fields=fields)
        Project.objects.filter(id=self.project_id).update(status=status, updated_at=dj_timezone.now())
        return task

    def _save_progress(self, pct: int) -> GenerationTask:
        task = GenerationTask.objects.get(id=self.task_id)
        task.progress_percentage = max(task.progress_percentage, min(100, pct))
        task.save(update_fields=["progress_percentage"])
        return task

    # ------------------------------------------------------------------ terminal events
    async def complete(self, artifact_data: dict) -> None:
        self.active_agents = []
        await self.phase(ProjectStatus.COMPLETED, progress=100)
        await broadcast.send_event(
            self.project_id, "pipeline_complete", {"task_id": str(self.task_id), "artifact": artifact_data}
        )

    async def fail(self, message: str) -> None:
        self.active_agents = []
        await self.log("System", LogType.ERROR, message)
        task = await sync_to_async(self._save_failure)(message)
        await self._send_phase(task)
        await broadcast.send_event(
            self.project_id, "pipeline_failed", {"task_id": str(self.task_id), "error_message": message}
        )

    def _save_failure(self, message: str) -> GenerationTask:
        self.status = ProjectStatus.FAILED
        task = GenerationTask.objects.get(id=self.task_id)
        task.current_phase = ProjectStatus.FAILED
        task.finished_at = dj_timezone.now()
        task.save(update_fields=["current_phase", "finished_at"])
        Project.objects.filter(id=self.project_id).update(
            status=ProjectStatus.FAILED, error_message=message[:5000], updated_at=dj_timezone.now()
        )
        return task
