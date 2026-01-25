"""Global hotkey helpers for the Kiroshi case documentation app."""

from __future__ import annotations

import logging
import threading
import time
from copy import copy, deepcopy
from dataclasses import dataclass
from functools import partial
from typing import Iterable, Mapping, Sequence

import pyperclip

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

__all__ = [
    "copy_active_case_build_title",
    "copy_active_case_tables",
    "copy_active_case_category",
    "copy_active_case_chatgpt_prompt",
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
    chatgpt_prompt: str = ""
    updated_at: float | None = None

    def clear(self) -> None:
        self.session = None
        self.category_map = None
        self.active_index = -1
        self.chatgpt_prompt = ""
        self.updated_at = None


_snapshot_lock = threading.Lock()
_snapshot_state = HotkeySnapshot()

STALE_SNAPSHOT_WARNING_SECONDS = 30.0


def _iter_category_tables(
    case_obj,
    cat_map: Mapping[str, list[str]] | None,
    categories: Sequence[str] | None = None,
) -> Iterable[str]:
    from case_documentation_app import table_plain_text  # Local import to avoid circular deps

    ordered_keys: Sequence[str]
    if categories is not None:
        ordered_keys = categories
    else:
        ordered_keys = list((cat_map or {}).keys())

    for category in ordered_keys:
        if cat_map is not None and category not in cat_map:
            logging.info("Clipboard hotkey ignored: missing category %s in snapshot", category)
            continue
        try:
            yield table_plain_text(category, case_obj, cat_map)
        except Exception:
            logging.exception("Failed to build plain text for category %s", category)


def update_hotkey_snapshot(
    case_sessions: Sequence[object] | None,
    active_idx: int,
    category_map: dict[str, list[str]] | None,
    chatgpt_prompt: str | None = None,
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
            # Bolt Optimization: Use shallow copy + explicit deepcopy of 'case' to avoid
            # blocking main thread with heavy assets (screenshots, uploads)
            source_session = case_sessions[active_idx]
            session_copy = copy(source_session)

            if hasattr(session_copy, "case"):
                session_copy.case = deepcopy(session_copy.case)

            # Clear heavy collections to avoid memory retention in snapshot
            # (Use setattr to be safe against missing attributes)
            for attr in ("screenshots", "uploads", "log_uploads"):
                if hasattr(session_copy, attr):
                    setattr(session_copy, attr, [])
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

        prompt_text = chatgpt_prompt if isinstance(chatgpt_prompt, str) else ""

        _snapshot_state.session = session_copy
        _snapshot_state.category_map = category_map_copy
        _snapshot_state.active_index = active_idx
        _snapshot_state.chatgpt_prompt = prompt_text
        _snapshot_state.updated_at = time.monotonic()


def _copy_tables_from_snapshot(
    *,
    categories: Sequence[str] | None,
    log_label: str,
) -> None:
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

        table_chunks = [
            chunk
            for chunk in _iter_category_tables(case_obj, cat_map, categories)
            if chunk
        ]
        if not table_chunks:
            logging.info(
                "Clipboard hotkey ignored: no table content to copy for %s",
                log_label,
            )
            return

        payload = "\n\n".join(table_chunks)
        pyperclip.copy(payload)
        logging.info("Copied case tables to clipboard for %s", log_label)
    except pyperclip.PyperclipException as exc:
        logging.warning("Failed to copy case tables to clipboard for %s: %s", log_label, exc)
    except Exception:
        logging.exception(
            "Unexpected error while copying case tables to clipboard for %s",
            log_label,
        )


def copy_active_case_tables() -> None:
    """Copy every table for the active case into the system clipboard."""

    _copy_tables_from_snapshot(categories=None, log_label="all tables")


def copy_active_case_build_title() -> None:
    """Copy the build title for the active case into the system clipboard."""

    try:
        with _snapshot_lock:
            session = _snapshot_state.session
            updated_at = _snapshot_state.updated_at

        if session is None:
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

        from case_documentation_app import build_title  # Local import to avoid cycles

        title = build_title(case_obj)
        if not title:
            logging.info("Clipboard hotkey ignored: build title is empty")
            return

        pyperclip.copy(title)
        logging.info("Copied build title to clipboard")
    except pyperclip.PyperclipException as exc:
        logging.warning("Failed to copy build title to clipboard: %s", exc)
    except Exception:
        logging.exception("Unexpected error while copying build title to clipboard")


def copy_active_case_category(category_key: str, *, display_name: str | None = None) -> None:
    """Copy a single category table for the active case."""

    label = display_name or category_key
    _copy_tables_from_snapshot(categories=[category_key], log_label=label)


_HOTKEY_CATEGORY_BINDINGS: dict[str, tuple[str, str]] = {
    "<ctrl>+<alt>+2": ("DESCRIPTION", "Description"),
    "<ctrl>+<alt>+3": ("PHONECALL", "Phonecall"),
    "<ctrl>+<alt>+4": ("INTERNAL NOTES", "Internal Notes"),
    "<ctrl>+<alt>+5": ("REMOTE SESSION", "Remote Session"),
    "<ctrl>+<alt>+6": ("ADDITIONAL INFORMATION", "Additional Information"),
    "<ctrl>+<alt>+7": ("CONCLUSION", "Root Cause & Conclusion"),
}


def copy_active_case_chatgpt_prompt() -> None:
    """Copy the most recently generated ChatGPT prompt into the clipboard."""

    try:
        with _snapshot_lock:
            prompt = _snapshot_state.chatgpt_prompt
            updated_at = _snapshot_state.updated_at

        if not isinstance(prompt, str) or not prompt.strip():
            logging.info("Clipboard hotkey ignored: ChatGPT prompt is empty")
            return

        if updated_at is not None:
            age = time.monotonic() - updated_at
            if age > STALE_SNAPSHOT_WARNING_SECONDS:
                logging.info(
                    "Hotkey snapshot data may be stale (last updated %.1fs ago)",
                    age,
                )

        pyperclip.copy(prompt)
        logging.info("Copied ChatGPT prompt to clipboard")
    except pyperclip.PyperclipException as exc:
        logging.warning("Failed to copy ChatGPT prompt to clipboard: %s", exc)
    except Exception:
        logging.exception(
            "Unexpected error while copying ChatGPT prompt to clipboard",
        )


def _run_hotkey_listener() -> None:
    if keyboard is None:
        logging.warning("pynput not available; hotkey listener disabled")
        return

    try:
        bindings: dict[str, object] = {
            "<ctrl>+<alt>+c": copy_active_case_tables,
        }
        bindings["<ctrl>+<alt>+1"] = copy_active_case_build_title
        bindings["<ctrl>+<alt>+8"] = copy_active_case_chatgpt_prompt
        for combo, (category, label) in _HOTKEY_CATEGORY_BINDINGS.items():
            bindings[combo] = partial(
                copy_active_case_category,
                category,
                display_name=label,
            )

        with keyboard.GlobalHotKeys(bindings) as listener:
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

    if keyboard is None:
        return

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
