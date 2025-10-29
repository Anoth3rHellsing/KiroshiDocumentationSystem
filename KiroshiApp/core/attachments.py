"""Attachment helpers for the desktop prototype."""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
from pathlib import Path
from typing import ClassVar, Iterable, Iterator


_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    """Return a filesystem friendly version of ``name`` preserving extensions."""

    candidate = Path(name).name.strip()
    if not candidate:
        return "attachment"
    sanitized = _SANITIZE_PATTERN.sub("_", candidate)
    sanitized = sanitized.strip("._") or "attachment"
    if len(sanitized) > 255:
        root, suffix = os.path.splitext(sanitized)
        sanitized = f"{root[:240]}{suffix}" if suffix else sanitized[:255]
    if sanitized in {"", ".", ".."}:
        return "attachment"
    return sanitized


@dataclass(frozen=True)
class AttachmentStorage:
    """Helper that manages the on-disk structure for persisted attachments."""

    base_path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_path", Path(self.base_path))
        self.base_path.mkdir(parents=True, exist_ok=True)

    SUBDIRECTORIES: ClassVar[dict[str, str]] = {
        "uploads": "uploads",
        "log_uploads": "logs",
        "screenshots": "screenshots",
    }

    def _ensure_subdir(self, key: str) -> Path:
        try:
            folder_name = self.SUBDIRECTORIES[key]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unsupported attachment kind: {key}") from exc
        subdir = self.base_path / folder_name
        subdir.mkdir(parents=True, exist_ok=True)
        return subdir

    def store_bytes(self, key: str, filename: str, data: bytes, *, overwrite: bool = True) -> Path:
        """Write ``data`` for ``filename`` into the subdirectory mapped by ``key``."""

        subdir = self._ensure_subdir(key)
        sanitized = sanitize_filename(filename)
        stem, suffix = os.path.splitext(sanitized)
        target = subdir / sanitized
        if target.exists() and not overwrite:
            counter = 1
            while True:
                candidate = subdir / f"{stem}_{counter}{suffix}"
                if not candidate.exists():
                    target = candidate
                    break
                counter += 1
        with open(target, "wb") as fh:
            fh.write(data)
        return target

    def list_paths(self, key: str) -> list[Path]:
        """Return sorted file paths stored for ``key``."""

        subdir = self._ensure_subdir(key)
        return sorted(path for path in subdir.iterdir() if path.is_file())

    def remove(self, path: Path) -> None:
        """Delete ``path`` if it exists inside the storage tree."""

        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            return
        try:
            resolved.relative_to(self.base_path)
        except ValueError:  # pragma: no cover - defensive guard
            raise ValueError("Attempted to delete a path outside the attachment root")
        resolved.unlink(missing_ok=True)

    def relative_path(self, path: Path) -> str:
        """Return the POSIX path for ``path`` relative to the case storage root."""

        return path.relative_to(self.base_path).as_posix()

    def iter_all(self) -> Iterator[Path]:
        """Yield every file stored under the case's attachment tree."""

        for key in self.SUBDIRECTORIES:
            yield from self.list_paths(key)


def list_attachments(case_folder: Path) -> Iterable[Path]:
    """Yield attachment files stored for a case across all categories."""

    if not case_folder.exists():
        return []
    storage = AttachmentStorage(case_folder)
    return list(storage.iter_all())
