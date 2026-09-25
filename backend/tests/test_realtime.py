import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator

from apps.accounts.serializers import tokens_for
from apps.projects.models import GenerationTask, LogType, Project, ProjectStatus
from engine.events import EventSink
from nexus_backend.asgi import application

pytestmark = pytest.mark.django_db(transaction=True)


def _communicator(project_id, token=None, origin=b"http://localhost:3000", after=None):
    query = []
    if token:
        query.append(f"token={token}")
    if after is not None:
        query.append(f"after={after}")
    path = f"/ws/projects/{project_id}/logs/" + (f"?{'&'.join(query)}" if query else "")
    return WebsocketCommunicator(application, path, headers=[(b"origin", origin), (b"host", b"localhost:8000")])


@pytest.fixture
def setup(user):
    project = Project.objects.create(owner=user, name="Live Stream")
    task = GenerationTask.objects.create(project=project)
    for i in range(1, 4):
        task.logs.create(agent_name="Team Lead", log_type=LogType.THOUGHT, content=f"thought {i}", sequence_num=i)
    return project, task, tokens_for(user)["access"]


async def _expect_close(comm, code):
    connected, _ = await comm.connect()
    assert connected  # accepted, then closed with an application code
    message = await comm.receive_output()
    assert message == {"type": "websocket.close", "code": code}
    await comm.disconnect()


async def test_rejects_missing_or_bad_token(setup):
    project, _, _ = setup
    await _expect_close(_communicator(project.id), 4401)
    await _expect_close(_communicator(project.id, token="not-a-jwt"), 4401)


async def test_rejects_other_users_project(setup, make_user):
    project, _, _ = setup
    other = await sync_to_async(make_user)(email="eve@example.com")
    token = await sync_to_async(lambda: tokens_for(other)["access"])()
    await _expect_close(_communicator(project.id, token=token), 4404)


async def test_rejects_foreign_origin(setup):
    project, _, token = setup
    comm = _communicator(project.id, token=token, origin=b"http://evil.example.com")
    connected, _ = await comm.connect()
    assert not connected


async def test_history_snapshot_and_live_events(setup):
    project, task, token = setup
    comm = _communicator(project.id, token=token)
    connected, _ = await comm.connect()
    assert connected

    history = await comm.receive_json_from()
    assert history["type"] == "history"
    assert [log["sequence_num"] for log in history["data"]["logs"]] == [1, 2, 3]
    assert history["data"]["logs"][0]["timestamp"].endswith("Z")
    snapshot = await comm.receive_json_from()
    assert snapshot["type"] == "phase_update" and snapshot["data"]["snapshot"] is True

    sink = EventSink(task.id, project.id)
    await sink.log("Backend Dev", LogType.TOOL_CALL, "filesystem-backend.write_file → backend/api/models.py")
    event = await comm.receive_json_from()
    assert event["type"] == "log_event"
    assert event["data"]["sequence_num"] == 4
    assert event["data"]["agent_name"] == "Backend Dev"

    await sink.file_created("Backend Dev", "backend/api/models.py", "write_file")
    event = await comm.receive_json_from()
    assert event == {
        "type": "file_created",
        "data": {
            "task_id": str(task.id),
            "agent_name": "Backend Dev",
            "path": "backend/api/models.py",
            "tool": "write_file",
            "is_new": True,
            "files_created_count": 1,
        },
    }

    await sink.phase(ProjectStatus.GENERATING, active_agents=["Frontend Dev", "Backend Dev"], announce=False)
    event = await comm.receive_json_from()
    assert event["type"] == "phase_update"
    assert event["data"]["current_phase"] == ProjectStatus.GENERATING
    assert event["data"]["progress_percentage"] == 25
    assert event["data"]["active_agents"] == ["Frontend Dev", "Backend Dev"]

    await comm.send_json_to({"type": "ping"})
    assert await comm.receive_json_from() == {"type": "pong"}
    await comm.disconnect()


async def test_history_after_cursor(setup):
    project, _, token = setup
    comm = _communicator(project.id, token=token, after=2)
    connected, _ = await comm.connect()
    assert connected
    history = await comm.receive_json_from()
    assert [log["content"] for log in history["data"]["logs"]] == ["thought 3"]
    await comm.disconnect()
