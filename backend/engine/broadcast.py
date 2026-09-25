"""Fan-out of pipeline events to WebSocket clients via the Channels layer.

Every event is sent to group ``project_{project_id}`` as
``{"type": "relay.event", "event": {"type": <event type>, "data": {...}}}``;
``ProjectLogConsumer.relay_event`` forwards ``event`` to the browser unchanged.
"""

from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def group_name(project_id) -> str:
    return f"project_{project_id}"


async def send_event(project_id, event_type: str, data: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        await layer.group_send(group_name(project_id), {"type": "relay.event", "event": {"type": event_type, "data": data}})
    except Exception:  # Redis hiccups must never break a generation run.
        logger.warning("Broadcast of %s for project %s failed", event_type, project_id, exc_info=True)


def send_event_sync(project_id, event_type: str, data: dict) -> None:
    async_to_sync(send_event)(project_id, event_type, data)
