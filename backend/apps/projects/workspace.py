"""Filesystem helpers for per-project sandboxed workspaces.

Layout: MEDIA_ROOT/workspaces/{user_id}/{project_id}/
    generated/   -> the generated application root (agents' "./")
    packages/    -> packaged .zip archives
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

EXCLUDED_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    ".git",
    ".nuxt",
    ".output",
    ".cache",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
}
EXCLUDED_FILES = {".DS_Store", "db.sqlite3"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".sqlite3"}

MAX_PREVIEW_BYTES = 1024 * 1024  # 1 MB


class UnsafePathError(ValueError):
    pass


def generated_dir(workspace: Path) -> Path:
    return Path(workspace) / "generated"


def packages_dir(workspace: Path) -> Path:
    return Path(workspace) / "packages"


def safe_join(root: Path, relative: str) -> Path:
    """Join `relative` onto `root`, refusing anything that escapes `root`."""
    if relative is None or "\x00" in relative:
        raise UnsafePathError("Invalid path.")
    rel = relative.replace("\\", "/").lstrip("/")
    root_resolved = Path(root).resolve()
    candidate = (root_resolved / rel).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise UnsafePathError("Path escapes the project workspace.")
    return candidate


def is_excluded(rel_parts: tuple[str, ...]) -> bool:
    if any(part in EXCLUDED_DIRS for part in rel_parts[:-1]):
        return True
    name = rel_parts[-1]
    if name in EXCLUDED_DIRS or name in EXCLUDED_FILES:
        return True
    return Path(name).suffix in EXCLUDED_SUFFIXES


def iter_files(root: Path, include_hidden_agents: bool = True):
    """Yield (relative_posix_path, absolute_path) for all non-excluded files."""
    root = Path(root)
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            # Agent notes never ship, wherever an agent happened to write them.
            if d not in EXCLUDED_DIRS and (include_hidden_agents or d != ".agents")
        )
        for fname in sorted(filenames):
            abs_path = Path(dirpath) / fname
            rel = abs_path.relative_to(root)
            if is_excluded(rel.parts) or abs_path.is_symlink():
                continue
            yield rel.as_posix(), abs_path


def build_file_tree(root: Path) -> dict:
    """Return a nested tree {name, path, type, children|size, extension}."""
    tree: dict = {"name": "", "path": "", "type": "directory", "children": []}
    index: dict[str, dict] = {"": tree}
    total_files = 0
    total_bytes = 0
    for rel, abs_path in iter_files(root):
        parts = rel.split("/")
        parent_path = ""
        for depth, part in enumerate(parts[:-1]):
            cur_path = "/".join(parts[: depth + 1])
            if cur_path not in index:
                node = {"name": part, "path": cur_path, "type": "directory", "children": []}
                index[parent_path]["children"].append(node)
                index[cur_path] = node
            parent_path = cur_path
        size = abs_path.stat().st_size
        total_files += 1
        total_bytes += size
        index[parent_path]["children"].append(
            {
                "name": parts[-1],
                "path": rel,
                "type": "file",
                "size": size,
                "extension": Path(parts[-1]).suffix.lstrip(".").lower(),
            }
        )

    def _sort(node):
        if node["type"] == "directory":
            node["children"].sort(key=lambda n: (n["type"] != "directory", n["name"].lower()))
            for child in node["children"]:
                _sort(child)

    _sort(tree)
    return {"root": tree, "total_files": total_files, "total_bytes": total_bytes}


def looks_binary(data: bytes) -> bool:
    if b"\x00" in data[:8192]:
        return True
    try:
        data[:8192].decode("utf-8")
    except UnicodeDecodeError as exc:
        # A multi-byte char cut at the sample boundary is still text.
        return exc.start < len(data[:8192]) - 4
    return False


def count_lines(root: Path) -> int:
    total = 0
    for _rel, abs_path in iter_files(root):
        try:
            with open(abs_path, "rb") as fh:
                chunk = fh.read(MAX_PREVIEW_BYTES)
            if not looks_binary(chunk):
                total += chunk.count(b"\n")
        except OSError:
            continue
    return total


def reset_dir(path: Path) -> None:
    path = Path(path)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
