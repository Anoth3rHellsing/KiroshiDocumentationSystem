"""Global hotkey helpers for the Kiroshi case documentation app."""

from __future__ import annotations

import logging
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable, Sequence

import pyperclip
from pynput import keyboard

__all__ = [
    "copy_active_case_tables",
    "ensure_hotkey_listener",
    "update_hotkey_snapshot",
]


_listener_lock = threading.Lock()
_listener_thread: threading.Thread | None = None
_listener_started = False


@dataclass
class HotkeySnapshot:
    """Container for the clipboard payload built on the UI thread."""

    session: object | None = None
    category_map: dict[str, list[str]] | None = None
    active_index: int = -1
    updated_at: float | None = None

    def clear(self) -> None:
        self.session = None
        self.category_map = None
        self.active_index = -1
        self.updated_at = None


_snapshot_lock = threading.Lock()
_snapshot_state = HotkeySnapshot()

STALE_SNAPSHOT_WARNING_SECONDS = 30.0


def _iter_category_tables(case_obj, cat_map) -> Iterable[str]:
    from case_documentation_app import table_plain_text  # Local import to avoid circular deps

    for category in (cat_map or {}):
        try:
            yield table_plain_text(category, case_obj, cat_map)
        except Exception:
            logging.exception("Failed to build plain text for category %s", category)


def update_hotkey_snapshot(
    case_sessions: Sequence[object] | None,
    active_idx: int,
    category_map: dict[str, list[str]] | None,
) -> None:
    """Persist a deep copy of the active case session for use on the listener thread."""

    with _snapshot_lock:
        if not isinstance(case_sessions, Sequence) or not case_sessions:
            _snapshot_state.clear()
            return
        if not isinstance(active_idx, int) or not (0 <= active_idx < len(case_sessions)):
            _snapshot_state.clear()
            return

        try:
            session_copy = deepcopy(case_sessions[active_idx])
        except Exception:
            logging.exception("Unable to capture case session snapshot for hotkey clipboard")
            _snapshot_state.clear()
            return

        try:
            category_map_copy = deepcopy(category_map or {})
        except Exception:
            logging.exception("Unable to clone category map for hotkey clipboard")
            _snapshot_state.clear()
            return

        _snapshot_state.session = session_copy
        _snapshot_state.category_map = category_map_copy
        _snapshot_state.active_index = active_idx
        _snapshot_state.updated_at = time.monotonic()


def copy_active_case_tables() -> None:
    """Copy the active case's tables into the system clipboard."""

    try:
        with _snapshot_lock:
            session = _snapshot_state.session
            cat_map = _snapshot_state.category_map
            updated_at = _snapshot_state.updated_at

        if session is None or cat_map is None:
            logging.info("Clipboard hotkey ignored: hotkey snapshot is empty")
            return

        if updated_at is not None:
            age = time.monotonic() - updated_at
            if age > STALE_SNAPSHOT_WARNING_SECONDS:
                logging.info(
                    "Hotkey snapshot data may be stale (last updated %.1fs ago)",
                    age,
                )

        case_obj = getattr(session, "case", None)
        if case_obj is None:
            logging.info("Clipboard hotkey ignored: snapshot missing case data")
            return

        table_chunks = [chunk for chunk in _iter_category_tables(case_obj, cat_map) if chunk]
        if not table_chunks:
            logging.info("Clipboard hotkey ignored: no table content to copy")
            return

        payload = "\n\n".join(table_chunks)
        pyperclip.copy(payload)
        logging.info("Copied case tables to clipboard")
    except pyperclip.PyperclipException as exc:
        logging.warning("Failed to copy case tables to clipboard: %s", exc)
    except Exception:
        logging.exception("Unexpected error while copying case tables to clipboard")


def _run_hotkey_listener() -> None:
    try:
        with keyboard.GlobalHotKeys({"<ctrl>+<alt>+c": copy_active_case_tables}) as listener:
            listener.join()
    except Exception:
        logging.exception("Hotkey listener terminated unexpectedly")
    finally:
        global _listener_started, _listener_thread
        with _listener_lock:
            _listener_started = False
            _listener_thread = None


def ensure_hotkey_listener() -> None:
    """Ensure the global hotkey listener thread is running."""

    global _listener_started, _listener_thread
    with _listener_lock:
        if _listener_started:
            return

        thread = threading.Thread(
            target=_run_hotkey_listener,
            name="KiroshiHotkeyListener",
            daemon=True,
        )
        thread.start()
        _listener_thread = thread
        _listener_started = True
