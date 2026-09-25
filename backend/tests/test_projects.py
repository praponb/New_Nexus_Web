import io
import zipfile

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.serializers import tokens_for
from apps.projects import workspace as ws
from apps.projects.models import GeneratedArtifact, GenerationTask, Project, ProjectStatus

GOOD_REQUIREMENT = (
    "# Todo App\n\nBuild a simple todo list application where users can create, edit, complete and "
    "delete tasks. Tasks have a title, an optional description and a due date. Show a filterable list."
)
BASE = "/api/v1/projects/"


@pytest.fixture
def dispatched(monkeypatch):
    calls = []

    def fake_dispatch(task):
        calls.append(task.id)
        return "job-123"

    monkeypatch.setattr("engine.tasks.dispatch", fake_dispatch)
    return calls


@pytest.fixture
def project(user):
    return Project.objects.create(owner=user, name="Inventory SaaS App", description="Tracker")


def _client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_for(user)['access']}")
    return client


def _upload(client, project, content=GOOD_REQUIREMENT, name="user_requirement.md", content_type="text/markdown"):
    data = content if isinstance(content, bytes) else content.encode()
    upload = SimpleUploadedFile(name, data, content_type=content_type)
    return client.post(f"{BASE}{project.id}/requirement/", {"file": upload}, format="multipart")


# --------------------------------------------------------------------------- CRUD
def test_requires_authentication(api_client, db):
    assert api_client.get(BASE).status_code == 401


def test_create_list_retrieve(auth_client):
    res = auth_client.post(BASE, {"name": "  Inventory SaaS App ", "description": "Tracker"}, format="json")
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    created = body["data"]
    assert created["name"] == "Inventory SaaS App"
    assert created["slug"] == "inventory-saas-app"
    assert created["status"] == ProjectStatus.DRAFT
    assert created["requirement"] is None and created["latest_task"] is None

    listing = auth_client.get(BASE).json()["data"]
    assert [p["id"] for p in listing] == [created["id"]]
    assert listing[0]["download_ready"] is False

    detail = auth_client.get(f"{BASE}{created['id']}/").json()["data"]
    assert detail["artifact"] is None


def test_create_rejects_blank_name(auth_client):
    res = auth_client.post(BASE, {"name": "   "}, format="json")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "validation_error"


def test_ownership_isolation(project, make_user):
    intruder = _client_for(make_user(email="mallory@example.com"))
    assert intruder.get(BASE).json()["data"] == []
    for suffix in ("", "files/", "download/", "logs/", "requirement/"):
        assert intruder.get(f"{BASE}{project.id}/{suffix}").status_code == 404
    assert intruder.post(f"{BASE}{project.id}/generate/", {}, format="json").status_code == 404
    assert intruder.delete(f"{BASE}{project.id}/").status_code == 404
    assert Project.objects.filter(id=project.id).exists()


def test_invalid_uuid_is_404(auth_client):
    assert auth_client.get(f"{BASE}not-a-uuid/").status_code == 404


def test_destroy_removes_workspace(auth_client, project):
    gen = ws.generated_dir(project.workspace)
    gen.mkdir(parents=True)
    (gen / "README.md").write_text("hi")
    res = auth_client.delete(f"{BASE}{project.id}/")
    assert res.status_code == 204
    assert not project.workspace.exists()
    assert not Project.objects.filter(id=project.id).exists()


# --------------------------------------------------------------------------- requirement
def test_upload_markdown_file(auth_client, project):
    res = _upload(auth_client, project)
    assert res.status_code == 200, res.json()
    data = res.json()["data"]
    assert data["word_count"] == len(GOOD_REQUIREMENT.split())
    assert data["original_filename"] == "user_requirement.md"

    detail = auth_client.get(f"{BASE}{project.id}/").json()["data"]
    assert detail["has_requirement"] is True
    assert detail["requirement"]["preview"].startswith("# Todo App")


def test_upload_raw_content_and_replace(auth_client, project):
    res = auth_client.post(f"{BASE}{project.id}/requirement/", {"content": GOOD_REQUIREMENT}, format="json")
    assert res.status_code == 200
    updated = GOOD_REQUIREMENT + " Also add user accounts."
    res = auth_client.post(f"{BASE}{project.id}/requirement/", {"content": updated}, format="multipart")
    assert res.status_code == 200
    project.refresh_from_db()
    assert project.requirement_doc.raw_content == updated
    assert auth_client.get(f"{BASE}{project.id}/requirement/").json()["data"]["raw_content"] == updated


@pytest.mark.parametrize(
    "kwargs, code, status",
    [
        ({"name": "requirements.txt"}, "invalid_file_type", 400),
        ({"name": "payload.sh", "content_type": "application/x-sh"}, "invalid_file_type", 400),
        ({"name": "spec.md", "content_type": "application/x-msdownload"}, "invalid_file_type", 400),
        ({"content": b"\x00\x01binary" * 20}, "invalid_file_type", 400),
        ({"content": "# Too short\n\nOnly a few words here."}, "requirement_too_short", 400),
    ],
)
def test_upload_validation(auth_client, project, kwargs, code, status):
    res = _upload(auth_client, project, **kwargs)
    assert res.status_code == status
    assert res.json()["error"]["code"] == code


def test_upload_rejects_oversize(auth_client, project, settings):
    settings.REQUIREMENT_MAX_BYTES = 1024
    res = _upload(auth_client, project, content=GOOD_REQUIREMENT * 20)
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"


def test_upload_requires_file_or_content(auth_client, project):
    res = auth_client.post(f"{BASE}{project.id}/requirement/", {}, format="json")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "requirement_empty"


def test_upload_decodes_invalid_utf8_with_replacement(auth_client, project):
    res = _upload(auth_client, project, content=GOOD_REQUIREMENT.encode() + b" caf\xe9 done")
    assert res.status_code == 200
    project.refresh_from_db()
    assert "caf�" in project.requirement_doc.raw_content


# --------------------------------------------------------------------------- generate
def test_generate_requires_requirement(auth_client, project, dispatched):
    res = auth_client.post(f"{BASE}{project.id}/generate/", {}, format="json")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "requirement_missing"
    assert dispatched == []


def test_generate_queues_and_blocks_concurrent_runs(auth_client, project, dispatched):
    _upload(auth_client, project)
    res = auth_client.post(f"{BASE}{project.id}/generate/", {"force_restart": False}, format="json")
    assert res.status_code == 202
    data = res.json()["data"]
    assert data["status"] == ProjectStatus.QUEUED
    task = GenerationTask.objects.get(id=data["task_id"])
    assert task.celery_task_id == "job-123"
    assert dispatched == [task.id]
    project.refresh_from_db()
    assert project.status == ProjectStatus.QUEUED

    res = auth_client.post(f"{BASE}{project.id}/generate/", {}, format="json")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "generation_in_progress"

    res = auth_client.post(f"{BASE}{project.id}/generate/", {"force_restart": True}, format="json")
    assert res.status_code == 202
    assert len(dispatched) == 2


def test_generate_replaces_old_artifact(auth_client, project, dispatched):
    _upload(auth_client, project)
    artifact = GeneratedArtifact(project=project, file_name="old.zip")
    artifact.zip_file.save("old.zip", ContentFile(b"PK"), save=True)
    old_path = artifact.zip_file.path
    assert auth_client.post(f"{BASE}{project.id}/generate/", {}, format="json").status_code == 202
    assert not GeneratedArtifact.objects.filter(project=project).exists()
    assert not ws.Path(old_path).exists()


def test_generate_enforces_quota(auth_client, project, dispatched, settings):
    settings.NEXUS_MONTHLY_GENERATION_QUOTA = 1
    _upload(auth_client, project)
    assert auth_client.post(f"{BASE}{project.id}/generate/", {}, format="json").status_code == 202
    res = auth_client.post(f"{BASE}{project.id}/generate/", {"force_restart": True}, format="json")
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "quota_exceeded"


def test_requirement_locked_while_active(auth_client, project):
    project.status = ProjectStatus.GENERATING
    project.save()
    res = _upload(auth_client, project)
    assert res.status_code == 409


# --------------------------------------------------------------------------- logs
def test_logs_after_cursor(auth_client, project):
    task = GenerationTask.objects.create(project=project)
    for i in range(1, 4):
        task.logs.create(agent_name="Team Lead", log_type="THOUGHT", content=f"step {i}", sequence_num=i)
    data = auth_client.get(f"{BASE}{project.id}/logs/").json()["data"]
    assert [log["sequence_num"] for log in data["logs"]] == [1, 2, 3]
    data = auth_client.get(f"{BASE}{project.id}/logs/?after=2").json()["data"]
    assert [log["content"] for log in data["logs"]] == ["step 3"]
    assert auth_client.get(f"{BASE}{project.id}/logs/?after=x").status_code == 400


# --------------------------------------------------------------------------- files
@pytest.fixture
def generated_files(project):
    root = ws.generated_dir(project.workspace)
    (root / "frontend").mkdir(parents=True)
    (root / "backend").mkdir()
    (root / "frontend" / "app.vue").write_text("<template><div /></template>\n")
    (root / "backend" / "manage.py").write_text("print('hi')\n")
    (root / "frontend" / "node_modules").mkdir()
    (root / "frontend" / "node_modules" / "junk.js").write_text("x")
    (root / "logo.png").write_bytes(b"\x89PNG\x00\x00binary")
    (project.workspace / "secret.txt").write_text("outside the generated root")
    return root


def test_file_tree(auth_client, project, generated_files):
    data = auth_client.get(f"{BASE}{project.id}/files/").json()["data"]
    assert data["total_files"] == 3
    names = [child["name"] for child in data["root"]["children"]]
    assert names == ["backend", "frontend", "logo.png"]
    frontend = data["root"]["children"][1]
    assert [c["path"] for c in frontend["children"]] == ["frontend/app.vue"]


def test_file_tree_empty_before_generation(auth_client, project):
    data = auth_client.get(f"{BASE}{project.id}/files/").json()["data"]
    assert data["total_files"] == 0


def test_file_content(auth_client, project, generated_files):
    res = auth_client.get(f"{BASE}{project.id}/files/content/", {"path": "frontend/app.vue"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["content"].startswith("<template>")
    assert data["extension"] == "vue" and data["is_binary"] is False

    data = auth_client.get(f"{BASE}{project.id}/files/content/", {"path": "logo.png"}).json()["data"]
    assert data["is_binary"] is True and data["content"] is None


@pytest.mark.parametrize(
    "path, status",
    [
        ("../secret.txt", 400),
        ("frontend/../../secret.txt", 400),
        ("/etc/passwd", 404),
        ("frontend", 404),
        ("frontend/node_modules/junk.js", 404),
        ("missing.py", 404),
        ("", 400),
    ],
)
def test_file_content_rejects_bad_paths(auth_client, project, generated_files, path, status):
    res = auth_client.get(f"{BASE}{project.id}/files/content/", {"path": path})
    assert res.status_code == status
    assert "outside the generated root" not in res.content.decode()


# --------------------------------------------------------------------------- download
def test_download_404_before_artifact(auth_client, project):
    res = auth_client.get(f"{BASE}{project.id}/download/")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "artifact_not_found"


def test_download_streams_zip(auth_client, project):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("README.md", "hello")
    artifact = GeneratedArtifact(project=project, file_name="bundle.zip", sha256_checksum="abc")
    artifact.zip_file.save("bundle.zip", ContentFile(buf.getvalue()), save=True)

    res = auth_client.get(f"{BASE}{project.id}/download/")
    assert res.status_code == 200
    assert res["Content-Type"] == "application/zip"
    assert 'filename="nexus_project_inventory-saas-app.zip"' in res["Content-Disposition"]
    assert res["X-Checksum-SHA256"] == "abc"
    payload = b"".join(res.streaming_content)
    assert zipfile.ZipFile(io.BytesIO(payload)).read("README.md") == b"hello"
