"""Helpers to inspect and read application log files."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class LogSnapshot:
    """Container representing the current view of a log file."""

    path: Path
    content: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Return ``True`` when the snapshot contains valid log content."""

        return self.error is None


def _iter_file_handlers() -> Iterable[logging.FileHandler]:
    """Yield all file handlers registered with known loggers."""

    handlers: List[logging.FileHandler] = []

    root = logging.getLogger()
    handlers.extend(
        handler for handler in root.handlers if isinstance(handler, logging.FileHandler)
    )

    manager = logging.Logger.manager
    for logger in manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            handlers.extend(
                handler for handler in logger.handlers if isinstance(handler, logging.FileHandler)
            )

    # Iterate in reverse order so the most recently attached handlers take precedence.
    for handler in reversed(handlers):
        yield handler


def resolve_log_file_path(*, default: str = "app.log") -> Path:
    """Return the most relevant log file path configured for the app."""

    env_override = os.environ.get("KIROSHI_LOG_FILE")
    if env_override:
        return Path(env_override)

    devnull = Path(os.devnull).resolve()
    for handler in _iter_file_handlers():
        try:
            filename = getattr(handler, "baseFilename", None)
        except Exception:  # pragma: no cover - defensive fallback for custom handlers
            filename = None
        if not filename:
            continue
        candidate = Path(filename)
        try:
            if candidate.resolve() == devnull:
                continue
        except OSError:  # pragma: no cover - defensive
            continue
        return candidate

    return Path(default)


def tail_log_file(path: str | os.PathLike[str], *, max_bytes: int = 65_536) -> LogSnapshot:
    """Read and return the tail of ``path`` limited to ``max_bytes``."""

    log_path = Path(path)
    if not log_path.exists():
        return LogSnapshot(path=log_path, content="", error="El archivo de log no existe.")

    try:
        with log_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            file_size = handle.tell()
            start = max(file_size - max_bytes, 0)
            handle.seek(start)
            data = handle.read().decode("utf-8", errors="replace")
            if start > 0:
                newline = data.find("\n")
                if newline >= 0:
                    data = data[newline + 1 :]
        return LogSnapshot(path=log_path, content=data.strip())
    except OSError as exc:  # pragma: no cover - defensive
        return LogSnapshot(path=log_path, content="", error=f"No se pudieron leer los logs: {exc}")


def load_recent_logs(*, default: str = "app.log", max_bytes: int = 65_536) -> LogSnapshot:
    """Return the latest log snapshot using the configured log file."""

    log_path = resolve_log_file_path(default=default)
    return tail_log_file(log_path, max_bytes=max_bytes)
