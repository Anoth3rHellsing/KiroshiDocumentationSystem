"""Storage helpers for the experimental desktop prototype."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Optional

from .model import CaseData

AUTOSAVE_FILENAME = "autosave.json"
CASES_DIRNAME = "Cases"


def _utc_now_iso() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.isoformat().replace("+00:00", "Z")


def get_database_root(base_path: Optional[Path | str] = None) -> Path:
    """Return the default directory used for local data storage."""

    if base_path is not None:
        return Path(base_path)
    return Path.home() / "KiroshiDatabase"


def cases_root(base_path: Optional[Path | str] = None) -> Path:
    """Return the directory where persistent case files are stored."""

    return get_database_root(base_path) / CASES_DIRNAME


def _autosave_path(base_path: Optional[Path | str] = None) -> Path:
    return get_database_root(base_path) / AUTOSAVE_FILENAME


def _case_payload(case: CaseData) -> dict[str, object]:
    payload = case.to_dict()
    last_modified = payload.get("last_modified")
    if not isinstance(last_modified, str) or not last_modified.strip():
        payload["last_modified"] = _utc_now_iso()
    return payload


def save_autosave(case: CaseData, *, base_path: Optional[Path | str] = None) -> Path:
    """Persist the latest draft case to the autosave file."""

    path = _autosave_path(base_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_case_payload(case), handle, ensure_ascii=False, indent=2)
    return path


def _coerce_case_payload(payload: Mapping[str, object]) -> Mapping[str, object]:
    case_payload = payload
    if "case" in payload and isinstance(payload["case"], Mapping):
        case_payload = payload["case"]  # type: ignore[index]
    return case_payload


def load_autosave(*, base_path: Optional[Path | str] = None) -> CaseData | None:
    """Load the autosave file if it exists."""

    path = _autosave_path(base_path)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(data, Mapping):
        return None

    case_payload = dict(_coerce_case_payload(data))
    remote_steps = case_payload.get("remote_steps")
    if isinstance(remote_steps, str) and remote_steps.strip():
        sessions = case_payload.get("remote_sessions")
        if not isinstance(sessions, Iterable) or isinstance(sessions, (str, bytes)):
            case_payload["remote_sessions"] = [remote_steps]
    return CaseData.from_dict(case_payload)


def save_case(case: CaseData, *, destination: Optional[Path] = None) -> Path:
    """Compat wrapper that mirrors the previous API signature."""

    if destination is None:
        destination = _autosave_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(_case_payload(case), ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def load_case(source: Optional[Path] = None) -> CaseData:
    """Compat wrapper returning the autosaved case if present."""

    if source is None:
        case = load_autosave()
        return case or CaseData()

    if not source.exists():
        return CaseData()

    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return CaseData()

    if isinstance(data, Mapping) and "case" in data and isinstance(data["case"], Mapping):
        data = data["case"]
    if isinstance(data, Mapping):
        return CaseData.from_dict(data)
    return CaseData()


def _safe_case_filename(case_id: str) -> str:
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in case_id or "case")
    return f"{sanitized}.json"


def save_case_to_db(case: CaseData, *, base_path: Optional[Path | str] = None) -> Path:
    """Persist the case as a JSON document in the database directory."""

    root = cases_root(base_path)
    root.mkdir(parents=True, exist_ok=True)
    filename = _safe_case_filename(case.case_id or "case")
    destination = root / filename
    payload = {
        "case": _case_payload(case),
        "saved_at": _utc_now_iso(),
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def iter_case_files(*, base_path: Optional[Path | str] = None) -> Iterator[Path]:
    """Yield saved case files ordered by most recent modification time."""

    root = cases_root(base_path)
    if not root.exists():
        return iter(())
    files = sorted(
        (path for path in root.glob("*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return iter(files)
