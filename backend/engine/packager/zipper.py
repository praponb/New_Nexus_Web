"""Builds the clean delivery archive and computes its checksum."""

from __future__ import annotations

import hashlib
import os
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path

from apps.projects.workspace import iter_files, looks_binary

EXECUTABLE_SUFFIXES = {".sh"}
_READ_CHUNK = 1024 * 1024


@dataclass
class ArchiveInfo:
    path: Path
    file_name: str
    size_bytes: int
    sha256: str
    file_count: int
    line_count: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_archive(source: Path, dest: Path, top_dir: str) -> ArchiveInfo:
    """Zip `source` into `dest` under `top_dir/`, skipping build output and agent notes.

    Unix permissions are stored so start_servers.sh stays executable after unzip.
    """
    source = Path(source)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    file_count = 0
    line_count = 0
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel, abs_path in iter_files(source, include_hidden_agents=False):
            info = zipfile.ZipInfo.from_file(abs_path, arcname=f"{top_dir}/{rel}")
            mode = stat.S_IMODE(os.stat(abs_path).st_mode) | 0o644
            if abs_path.suffix in EXECUTABLE_SUFFIXES or mode & 0o111:
                mode |= 0o755
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(abs_path, "rb") as src, zf.open(info, "w") as out:
                head = src.read(_READ_CHUNK)
                if not looks_binary(head):
                    line_count += head.count(b"\n")
                out.write(head)
                for chunk in iter(lambda: src.read(_READ_CHUNK), b""):
                    out.write(chunk)
            file_count += 1
    tmp.replace(dest)
    return ArchiveInfo(
        path=dest,
        file_name=dest.name,
        size_bytes=dest.stat().st_size,
        sha256=sha256_file(dest),
        file_count=file_count,
        line_count=line_count,
    )
