from rest_framework import serializers

from .models import AgentStepLog, GeneratedArtifact, GenerationTask, Project, RequirementDoc

REQUIREMENT_PREVIEW_CHARS = 600


class RequirementDocSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementDoc
        fields = ("id", "original_filename", "raw_content", "word_count", "uploaded_at", "updated_at")
        read_only_fields = fields


class GenerationTaskSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = GenerationTask
        fields = (
            "id",
            "current_phase",
            "progress_percentage",
            "qa_iterations",
            "started_at",
            "finished_at",
            "created_at",
            "duration_seconds",
        )
        read_only_fields = fields


class GeneratedArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedArtifact
        fields = (
            "id",
            "file_name",
            "file_size_bytes",
            "sha256_checksum",
            "total_files_count",
            "total_lines_of_code",
            "frontend_framework",
            "backend_framework",
            "created_at",
        )
        read_only_fields = fields


class AgentStepLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentStepLog
        fields = ("id", "agent_name", "log_type", "content", "metadata", "sequence_num", "created_at")
        read_only_fields = fields


def _artifact_or_none(project: Project):
    try:
        return project.artifact
    except GeneratedArtifact.DoesNotExist:
        return None


def _requirement_or_none(project: Project):
    try:
        return project.requirement_doc
    except RequirementDoc.DoesNotExist:
        return None


class ProjectSerializer(serializers.ModelSerializer):
    """List/create representation."""

    has_requirement = serializers.SerializerMethodField()
    download_ready = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "status",
            "error_message",
            "has_requirement",
            "download_ready",
            "progress_percentage",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "slug", "status", "error_message", "created_at", "updated_at")

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Project name cannot be blank.")
        return value

    def get_has_requirement(self, obj) -> bool:
        return _requirement_or_none(obj) is not None

    def get_download_ready(self, obj) -> bool:
        return _artifact_or_none(obj) is not None

    def get_progress_percentage(self, obj) -> int:
        task = obj.latest_task()
        return task.progress_percentage if task else 0


class ProjectDetailSerializer(ProjectSerializer):
    requirement = serializers.SerializerMethodField()
    latest_task = serializers.SerializerMethodField()
    artifact = serializers.SerializerMethodField()

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ("requirement", "latest_task", "artifact")

    def get_requirement(self, obj):
        doc = _requirement_or_none(obj)
        if doc is None:
            return None
        preview = doc.raw_content[:REQUIREMENT_PREVIEW_CHARS]
        return {
            "id": str(doc.id),
            "original_filename": doc.original_filename,
            "word_count": doc.word_count,
            "preview": preview,
            "truncated": len(doc.raw_content) > len(preview),
            "raw_content": doc.raw_content,
            "updated_at": doc.updated_at,
        }

    def get_latest_task(self, obj):
        task = obj.latest_task()
        return GenerationTaskSerializer(task).data if task else None

    def get_artifact(self, obj):
        artifact = _artifact_or_none(obj)
        return GeneratedArtifactSerializer(artifact).data if artifact else None
