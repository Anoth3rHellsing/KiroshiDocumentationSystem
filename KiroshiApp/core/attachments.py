"""Attachment management helpers for case records."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Iterable

from .model import CaseData
from .utils import get_database_root

INVALID_FILENAME_CHARS = set('<>:"/\\|?*')


def sanitize_filename(name: str) -> str:
    """Return ``name`` stripped from characters that are invalid on Windows."""

    safe = "".join("_" if ch in INVALID_FILENAME_CHARS else ch for ch in name)
    safe = safe.strip().rstrip(".")
    return safe or "attachment"


def attachments_root(case_id: str, base_path: Path | None = None) -> Path:
    """Return the folder where attachments for ``case_id`` are stored."""

    safe_case_id = sanitize_filename(case_id or "case")
    root = get_database_root(base_path) / "attachments" / safe_case_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def add_attachment(
    case: CaseData, source: Path, base_path: Path | None = None
) -> Path:
    """Copy ``source`` to the case attachment directory."""

    if not source.exists():
        raise FileNotFoundError(source)
    if not source.is_file():
        raise IsADirectoryError(source)

    destination_dir = attachments_root(case.case_id, base_path)
    filename = sanitize_filename(source.name)
    destination = destination_dir / filename
    base_name = destination.stem
    suffix = destination.suffix
    counter = 1
    while destination.exists():
        destination = destination_dir / f"{base_name}_{counter}{suffix}"
        counter += 1
    shutil.copy2(source, destination)
    return destination


def remove_attachment(
    case: CaseData, attachment_name: str, base_path: Path | None = None
) -> bool:
    """Delete an attachment file returning ``True`` when it existed."""

    root = attachments_root(case.case_id, base_path)
    candidates = [root / attachment_name, root / sanitize_filename(attachment_name)]
    for target in candidates:
        if target.exists():
            target.unlink()
            return True
    return False


def iter_attachments(
    case: CaseData, base_path: Path | None = None
) -> Iterable[Path]:
    """Yield all attachment paths registered for ``case``."""

    root = attachments_root(case.case_id, base_path)
    for path in sorted(root.glob("**/*")):
        if path.is_file():
            yield path


def create_zip(
    case: CaseData, destination: Path, base_path: Path | None = None
) -> Path:
    """Create a ZIP archive bundling all attachments for ``case``."""

    attachment_paths = list(iter_attachments(case, base_path))
    destination = destination.with_suffix(".zip")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in attachment_paths:
            archive.write(path, arcname=path.name)
    return destination
