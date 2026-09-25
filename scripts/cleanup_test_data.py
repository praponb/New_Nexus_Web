"""Remove Nexus e2e test users, their projects/files, and kept e2e log dirs.

Dry run by default. Pass --yes to delete. Pass --include-old-test-accounts to also remove the four
session-1 test accounts (smoke14225, celery-smoke, ws4045, ui-demo7896 @example.com).
Never touches prapon@gmail.com.

Run from the repo root:  .venv/bin/python scripts/cleanup_test_data.py [--yes] [--include-old-test-accounts]
"""
import glob
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
os.chdir(REPO / "backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus_backend.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.projects.models import GeneratedArtifact, RequirementDoc  # noqa: E402

APPLY = "--yes" in sys.argv
OLD = {"smoke14225@example.com", "celery-smoke@example.com", "ws4045@example.com", "ui-demo7896@example.com"}
KEEP = "prapon@gmail.com"  # the owner's real account; never deleted

root = Path(settings.WORKSPACES_ROOT).resolve()
users = [u for u in User.objects.all() if re.fullmatch(r"e2e-\d+-\d+@example\.com", u.email)]
if "--include-old-test-accounts" in sys.argv:
    users += [u for u in User.objects.filter(email__in=OLD)]
assert all(u.email != KEEP for u in users)

print(("DELETING" if APPLY else "DRY RUN (add --yes to delete)") + f": {len(users)} user(s)")
for u in users:
    user_dir = None
    for p in u.projects.all():
        ws = p.workspace.resolve()
        assert root in ws.parents, ws
        user_dir = ws.parent
        print(f"  {u.email}: project {p.name!r} + {ws.relative_to(root)}")
        if APPLY:
            a = GeneratedArtifact.objects.filter(project=p).first()
            if a and a.zip_file:
                a.zip_file.delete(save=False)
            d = RequirementDoc.objects.filter(project=p).first()
            if d and d.file:
                d.file.delete(save=False)
            p.delete()
            shutil.rmtree(ws, ignore_errors=True)
    if APPLY:
        u.delete()
        if user_dir and user_dir.exists() and not any(user_dir.iterdir()):
            user_dir.rmdir()

logs = glob.glob(os.path.join(tempfile.gettempdir(), "nexus-e2e-*"))
for d in logs:
    print(f"  log dir {d}")
    if APPLY:
        shutil.rmtree(d, ignore_errors=True)
print("done." if APPLY else "nothing deleted.")
