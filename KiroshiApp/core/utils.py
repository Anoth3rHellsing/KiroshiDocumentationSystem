"""Utility helpers for the experimental desktop client."""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

APP_NAME = "KiroshiDatabase"
CONFIG_FILENAME = "settings.json"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with a sensible default format."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def utc_now() -> datetime:
    """Return the current UTC timestamp as a ``datetime`` object."""

    return datetime.now(tz=UTC)


def utc_now_iso() -> str:
    """Return the current UTC timestamp formatted as an ISO-8601 string."""

    return utc_now().replace(microsecond=0).isoformat()


def format_timestamp(value: datetime | str, *, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Normalise a timestamp value to a human friendly string."""

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
    else:
        parsed = value
    return parsed.strftime(fmt)


def ensure_directory(path: Path) -> Path:
    """Guarantee that ``path`` exists on disk and return it."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_database_root(base_path: Path | None = None) -> Path:
    """Resolve the root folder used to persist local application data."""

    if base_path is not None:
        return ensure_directory(base_path)

    appdata = Path.home()
    if os_appdata := os.getenv("APPDATA"):
        appdata = Path(os_appdata)
    return ensure_directory(appdata / APP_NAME)


def read_json(path: Path) -> Any:
    """Read a JSON file returning ``None`` when the payload is invalid."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as exc:  # pragma: no cover - defensive logging
        logging.getLogger(__name__).warning("Failed to read %s: %s", path, exc)
        return None


def write_json(path: Path, payload: Any) -> None:
    """Persist a JSON serialisable payload to ``path``."""

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")


def load_global_config(base_path: Path | None = None) -> dict[str, Any]:
    """Load the desktop client's persisted configuration."""

    config_path = get_database_root(base_path) / CONFIG_FILENAME
    data = read_json(config_path)
    if isinstance(data, dict):
        return data
    return {}


def save_global_config(config: dict[str, Any], base_path: Path | None = None) -> Path:
    """Persist the application configuration and return the path used."""

    config_path = get_database_root(base_path) / CONFIG_FILENAME
    write_json(config_path, config)
    return config_path
