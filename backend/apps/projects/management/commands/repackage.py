"""Rebuild completed projects' zips with the current delivery files (start_servers.sh, README...).

Usage: manage.py repackage <project_id> [<project_id> ...] | --all
"""

from django.core.management.base import BaseCommand, CommandError

from apps.projects.models import Project, ProjectStatus
from engine.orchestrator import GenerationPipelineError, repackage


class Command(BaseCommand):
    help = "Rebuild the download zip of completed projects without rerunning the agents."

    def add_arguments(self, parser):
        parser.add_argument("project_ids", nargs="*")
        parser.add_argument("--all", action="store_true", help="Repackage every completed project.")

    def handle(self, *args, project_ids, all, **options):
        if all:
            project_ids = [str(pk) for pk in Project.objects.filter(status=ProjectStatus.COMPLETED).values_list("id", flat=True)]
        if not project_ids:
            raise CommandError("Give one or more project ids, or --all.")
        for project_id in project_ids:
            try:
                result = repackage(project_id)
            except (Project.DoesNotExist, GenerationPipelineError) as exc:
                raise CommandError(f"{project_id}: {exc}") from exc
            self.stdout.write(
                f"{project_id}: {result['file_name']} {result['total_files_count']} files, "
                f"sha256 {result['sha256_checksum']} (refreshed: {', '.join(result['files_written'])})"
            )
