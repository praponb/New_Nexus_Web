"""Live pipeline stream for one project.

On connect: `history` (logs of the latest task, optionally after `?after=<seq>`, split over as
many messages as needed to stay under the WebSocket frame limit) followed by a `phase_update`
snapshot. Then every event the engine broadcasts: `log_event`, `phase_update`,
`file_created`, `pipeline_complete`, `pipeline_failed`.
Close codes: 4401 unauthenticated, 4404 project not found / not owned.
"""

import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.projects.models import AgentStepLog, GeneratedArtifact, Project
from apps.projects.serializers import GeneratedArtifactSerializer
from engine.broadcast import group_name
from engine.events import log_payload

HISTORY_LIMIT = 5000
# Daphne/autobahn drop the connection on messages over 1 MiB; a long live run's history is larger.
HISTORY_BATCH_BYTES = 256 * 1024


def history_batches(logs: list[dict], budget: int | None = None) -> list[list[dict]]:
    """Split `logs` into consecutive batches whose JSON size stays near `budget` (always >= 1 batch)."""
    budget = budget or HISTORY_BATCH_BYTES
    batches, batch, size = [], [], 0
    for log in logs:
        n = len(json.dumps(log, default=str).encode()) + 1
        if batch and size + n > budget:
            batches.append(batch)
            batch, size = [], 0
        batch.append(log)
        size += n
    batches.append(batch)
    return batches


class ProjectLogConsumer(AsyncJsonWebsocketConsumer):
    group = None

    async def connect(self):
        user = self.scope.get("user")
        await self.accept()
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.project_id = self.scope["url_route"]["kwargs"]["project_id"]
        if not await self._owns_project(user):
            await self.close(code=4404)
            return
        self.group = group_name(self.project_id)
        # Join first, then replay: clients dedupe by sequence_num, so nothing falls in the gap.
        await self.channel_layer.group_add(self.group, self.channel_name)
        params = parse_qs(self.scope.get("query_string", b"").decode())
        try:
            after = int((params.get("after") or ["0"])[0])
        except ValueError:
            after = 0
        history, snapshot = await self._snapshot(after)
        for batch in history_batches(history["logs"]):
            await self.send_json({"type": "history", "data": {"task_id": history["task_id"], "logs": batch}})
        await self.send_json({"type": "phase_update", "data": snapshot})

    async def disconnect(self, code):
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def relay_event(self, message):
        await self.send_json(message["event"])

    @database_sync_to_async
    def _owns_project(self, user) -> bool:
        return Project.objects.filter(id=self.project_id, owner=user).exists()

    @database_sync_to_async
    def _snapshot(self, after: int):
        project = Project.objects.get(id=self.project_id)
        task = project.latest_task()
        logs = []
        if task is not None:
            qs = AgentStepLog.objects.filter(task=task, sequence_num__gt=after).order_by("sequence_num")[:HISTORY_LIMIT]
            logs = [log_payload(log) for log in qs]
        artifact = GeneratedArtifact.objects.filter(project=project).first()
        history = {"task_id": str(task.id) if task else None, "logs": logs}
        snapshot = {
            "task_id": str(task.id) if task else None,
            "status": project.status,
            "current_phase": task.current_phase if task else project.status,
            "progress_percentage": task.progress_percentage if task else 0,
            "qa_iterations": task.qa_iterations if task else 0,
            "active_agents": [],
            "files_created_count": None,
            "error_message": project.error_message,
            "artifact": GeneratedArtifactSerializer(artifact).data if artifact else None,
            "snapshot": True,
        }
        return history, snapshot
