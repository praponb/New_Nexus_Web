import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class ProjectStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    QUEUED = "QUEUED", "Queued"
    PLANNING = "PLANNING", "Planning & Architecture"
    GENERATING = "GENERATING", "Generating Code (FE & BE)"
    TESTING = "TESTING", "Testing & Self-Correction"
    PACKAGING = "PACKAGING", "Packaging Archive"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


ACTIVE_STATUSES = {
    ProjectStatus.QUEUED,
    ProjectStatus.PLANNING,
    ProjectStatus.GENERATING,
    ProjectStatus.TESTING,
    ProjectStatus.PACKAGING,
}


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.DRAFT)
    error_message = models.TextField(blank=True, null=True)
    workspace_dir = models.CharField(max_length=500, blank=True)  # Isolated disk path
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "-created_at"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = (slugify(self.name) or "project")[:200]
        if not self.workspace_dir:
            self.workspace_dir = str(Path(settings.WORKSPACES_ROOT) / str(self.owner_id) / str(self.id))
        super().save(*args, **kwargs)

    @property
    def workspace(self) -> Path:
        return Path(self.workspace_dir)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def latest_task(self):
        return self.generation_tasks.order_by("-created_at").first()


class RequirementDoc(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="requirement_doc")
    file = models.FileField(upload_to="requirements/%Y/%m/%d/", max_length=500)
    original_filename = models.CharField(max_length=255, default="user_requirement.md")
    raw_content = models.TextField(help_text="Extracted plain text of user_requirement.md")
    word_count = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.project_id})"


class GenerationTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="generation_tasks")
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    current_phase = models.CharField(max_length=50, default="INITIALIZING")
    progress_percentage = models.PositiveSmallIntegerField(default=0)  # 0 to 100
    qa_iterations = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Task {self.id} [{self.current_phase}]"

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class LogType(models.TextChoices):
    THOUGHT = "THOUGHT", "Thought"
    TOOL_CALL = "TOOL_CALL", "Tool Call"
    TOOL_RESULT = "TOOL_RESULT", "Tool Result"
    TEXT = "TEXT", "Text Output"
    PHASE_CHANGE = "PHASE_CHANGE", "Phase Change"
    SYSTEM = "SYSTEM", "System Notification"
    ERROR = "ERROR", "Error"


class AgentStepLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    task = models.ForeignKey(GenerationTask, on_delete=models.CASCADE, related_name="logs")
    agent_name = models.CharField(max_length=100)  # 'Team Lead', 'Frontend Dev', 'Backend Dev', 'QA'
    log_type = models.CharField(max_length=20, choices=LogType.choices)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)  # Tool arguments, return codes, file paths
    sequence_num = models.PositiveIntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence_num"]
        indexes = [models.Index(fields=["task", "sequence_num"])]

    def __str__(self) -> str:
        return f"#{self.sequence_num} {self.agent_name} {self.log_type}"


class GeneratedArtifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="artifact")
    zip_file = models.FileField(upload_to="artifacts/%Y/%m/%d/", max_length=500)
    file_name = models.CharField(max_length=255)
    file_size_bytes = models.BigIntegerField(default=0)
    sha256_checksum = models.CharField(max_length=64, blank=True)
    total_files_count = models.PositiveIntegerField(default=0)
    total_lines_of_code = models.PositiveIntegerField(default=0)
    frontend_framework = models.CharField(max_length=50, default="Nuxt 3")
    backend_framework = models.CharField(max_length=50, default="Django 5")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.file_name
