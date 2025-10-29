"""Utility helpers for the experimental desktop client."""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

APP_NAME = "KiroshiDatabase"
CONFIG_FILENAME = "settings.json"
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILENAME = "kiroshi.log"


def setup_logging(level: int = logging.INFO) -> Path:
    """Configure rotating file logging for the desktop client."""

    log_path = get_log_path()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_048_576,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    return log_path


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


def get_log_path() -> Path:
    """Return the path used by the rotating log handler."""

    return LOG_DIR / LOG_FILENAME


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
