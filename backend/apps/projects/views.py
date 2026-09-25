import shutil
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.http import FileResponse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from nexus_backend.api import ApiError, ok

from . import workspace as ws
from .models import AgentStepLog, GeneratedArtifact, GenerationTask, Project, ProjectStatus, RequirementDoc
from .serializers import (
    AgentStepLogSerializer,
    GenerationTaskSerializer,
    ProjectDetailSerializer,
    ProjectSerializer,
    RequirementDocSerializer,
)

MIN_REQUIREMENT_WORDS = 20
ALLOWED_REQUIREMENT_SUFFIXES = {".md"}
# Browsers label .md inconsistently, so only clearly non-text types are refused.
ALLOWED_REQUIREMENT_MIME_PREFIXES = ("text/",)
ALLOWED_REQUIREMENT_MIME_TYPES = {"", "application/octet-stream", "application/markdown", "application/x-markdown"}
MAX_LOG_PAGE = 5000


def _requirement_bytes_limit() -> int:
    return int(getattr(settings, "REQUIREMENT_MAX_BYTES", 5 * 1024 * 1024))


# Bytes that never appear in a text document (tab, LF, FF and CR excluded).
_CONTROL_BYTES = bytes(b for b in range(32) if b not in (9, 10, 12, 13)) + b"\x7f"


def _is_binary_upload(data: bytes) -> bool:
    """Reject executables/images, but tolerate stray non-UTF-8 bytes (decoded with replacement)."""
    sample = data[:8192]
    if b"\x00" in sample:
        return True
    return bool(sample) and sum(sample.count(bytes([b])) for b in _CONTROL_BYTES) / len(sample) > 0.05


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class ProjectViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return (
            Project.objects.filter(owner=self.request.user)
            .select_related("requirement_doc", "artifact")
            .prefetch_related("generation_tasks")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProjectDetailSerializer
        return ProjectSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return ok(ProjectDetailSerializer(serializer.instance).data, status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        if serializer.instance.is_active:
            raise ApiError("Cannot edit a project while generation is running.", "generation_in_progress", 409)
        serializer.save()

    def perform_destroy(self, instance):
        workspace = instance.workspace
        artifact = GeneratedArtifact.objects.filter(project=instance).first()
        if artifact:
            artifact.zip_file.delete(save=False)
        doc = RequirementDoc.objects.filter(project=instance).first()
        if doc:
            doc.file.delete(save=False)
        instance.delete()
        # Only ever remove directories inside the workspaces root.
        root = Path(settings.WORKSPACES_ROOT).resolve()
        if workspace.exists() and root in workspace.resolve().parents:
            shutil.rmtree(workspace, ignore_errors=True)

    # ------------------------------------------------------------------ requirement
    @action(detail=True, methods=["get", "post"])
    def requirement(self, request, pk=None):
        project = self.get_object()
        if request.method == "GET":
            doc = RequirementDoc.objects.filter(project=project).first()
            if doc is None:
                raise ApiError("No requirement has been uploaded yet.", "requirement_missing", 404)
            return ok(RequirementDocSerializer(doc).data)

        if project.is_active:
            raise ApiError("Cannot change the requirement while generation is running.", "generation_in_progress", 409)

        upload = request.FILES.get("file")
        limit = _requirement_bytes_limit()
        if upload is not None:
            filename = Path(upload.name or "").name or "user_requirement.md"
            if Path(filename).suffix.lower() not in ALLOWED_REQUIREMENT_SUFFIXES:
                raise ApiError("Only Markdown (.md) files are accepted.", "invalid_file_type", 400)
            content_type = (upload.content_type or "").split(";")[0].strip().lower()
            if not (
                content_type.startswith(ALLOWED_REQUIREMENT_MIME_PREFIXES)
                or content_type in ALLOWED_REQUIREMENT_MIME_TYPES
            ):
                raise ApiError(f"Unsupported file type '{content_type}'.", "invalid_file_type", 400)
            if upload.size > limit:
                raise ApiError("Requirement file exceeds the 5 MB limit.", "file_too_large", 413)
            data = upload.read()
            if _is_binary_upload(data):
                raise ApiError("The uploaded file does not look like a text document.", "invalid_file_type", 400)
        else:
            content = request.data.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ApiError("Provide a Markdown `file` or non-empty `content`.", "requirement_empty", 400)
            filename = "user_requirement.md"
            data = content.encode("utf-8")
            if len(data) > limit:
                raise ApiError("Requirement content exceeds the 5 MB limit.", "file_too_large", 413)

        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
        word_count = len(text.split())
        if word_count < MIN_REQUIREMENT_WORDS:
            raise ApiError(
                f"Requirement must contain at least {MIN_REQUIREMENT_WORDS} words (found {word_count}).",
                "requirement_too_short",
                400,
            )

        doc = RequirementDoc.objects.filter(project=project).first()
        if doc is None:
            doc = RequirementDoc(project=project)
        elif doc.file:
            doc.file.delete(save=False)
        doc.original_filename = filename
        doc.raw_content = text
        doc.word_count = word_count
        doc.file.save(filename, ContentFile(text.encode("utf-8")), save=False)
        doc.save()
        return ok(RequirementDocSerializer(doc).data)

    # ------------------------------------------------------------------ generation
    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        project = self.get_object()
        if not RequirementDoc.objects.filter(project=project).exists():
            raise ApiError("Upload a requirement document before generating.", "requirement_missing", 400)
        if project.is_active and not _truthy(request.data.get("force_restart", False)):
            raise ApiError("A generation run is already in progress.", "generation_in_progress", 409)

        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        quota = int(getattr(settings, "NEXUS_MONTHLY_GENERATION_QUOTA", 25))
        used = GenerationTask.objects.filter(project__owner=request.user, created_at__gte=month_start).count()
        if used >= quota:
            raise ApiError(f"Monthly generation quota of {quota} reached.", "quota_exceeded", 429)

        artifact = GeneratedArtifact.objects.filter(project=project).first()
        if artifact:
            artifact.zip_file.delete(save=False)
            artifact.delete()

        task = GenerationTask.objects.create(project=project, current_phase=ProjectStatus.QUEUED)
        project.status = ProjectStatus.QUEUED
        project.error_message = None
        project.save(update_fields=["status", "error_message", "updated_at"])

        from engine import tasks as engine_tasks

        job_id = engine_tasks.dispatch(task)
        if job_id:
            task.celery_task_id = str(job_id)
            task.save(update_fields=["celery_task_id"])
        return ok({"task_id": str(task.id), "status": ProjectStatus.QUEUED}, status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        project = self.get_object()
        task_id = request.query_params.get("task_id")
        tasks = project.generation_tasks.all()
        task = tasks.filter(id=task_id).first() if task_id else tasks.order_by("-created_at").first()
        if task is None:
            return ok({"task": None, "logs": []})
        qs = AgentStepLog.objects.filter(task=task)
        after = request.query_params.get("after")
        if after is not None:
            try:
                qs = qs.filter(sequence_num__gt=int(after))
            except ValueError:
                raise ApiError("`after` must be an integer.", "invalid_parameter", 400)
        logs = qs.order_by("sequence_num")[:MAX_LOG_PAGE]
        return ok({"task": GenerationTaskSerializer(task).data, "logs": AgentStepLogSerializer(logs, many=True).data})

    # ------------------------------------------------------------------ files
    @action(detail=True, methods=["get"])
    def files(self, request, pk=None):
        project = self.get_object()
        return ok(ws.build_file_tree(ws.generated_dir(project.workspace)))

    @action(detail=True, methods=["get"], url_path="files/content")
    def file_content(self, request, pk=None):
        project = self.get_object()
        rel = request.query_params.get("path")
        if not rel:
            raise ApiError("Query parameter `path` is required.", "invalid_parameter", 400)
        root = ws.generated_dir(project.workspace)
        try:
            target = ws.safe_join(root, rel)
        except ws.UnsafePathError as exc:
            raise ApiError(str(exc), "unsafe_path", 400)
        rel_parts = target.relative_to(root.resolve()).parts if target != root.resolve() else ()
        if not rel_parts or ws.is_excluded(rel_parts) or not target.is_file() or target.is_symlink():
            raise ApiError("File not found.", "not_found", 404)

        size = target.stat().st_size
        with open(target, "rb") as fh:
            data = fh.read(ws.MAX_PREVIEW_BYTES)
        is_binary = ws.looks_binary(data)
        return ok(
            {
                "path": "/".join(rel_parts),
                "size": size,
                "extension": target.suffix.lstrip(".").lower(),
                "is_binary": is_binary,
                "truncated": size > ws.MAX_PREVIEW_BYTES,
                "content": None if is_binary else data.decode("utf-8", errors="replace"),
            }
        )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        project = self.get_object()
        artifact = GeneratedArtifact.objects.filter(project=project).first()
        if artifact is None or not artifact.zip_file:
            raise ApiError("No generated archive is available for this project yet.", "artifact_not_found", 404)
        try:
            handle = artifact.zip_file.open("rb")
        except (FileNotFoundError, OSError):
            raise ApiError("The generated archive is missing on disk.", "artifact_not_found", 404)
        response = FileResponse(
            handle,
            as_attachment=True,
            filename=f"nexus_project_{project.slug}.zip",
            content_type="application/zip",
        )
        if artifact.sha256_checksum:
            response["X-Checksum-SHA256"] = artifact.sha256_checksum
        return response
