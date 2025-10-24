"""Global hotkey helpers for the Kiroshi case documentation app."""

from __future__ import annotations

import logging
import threading
from typing import Iterable

import pyperclip
import streamlit as st
from pynput import keyboard

__all__ = ["copy_active_case_tables", "ensure_hotkey_listener"]


_listener_lock = threading.Lock()
_listener_thread: threading.Thread | None = None
_listener_started = False


def _iter_category_tables(case_obj, cat_map) -> Iterable[str]:
    from case_documentation_app import table_plain_text  # Local import to avoid circular deps

    for category in (cat_map or {}):
        try:
            yield table_plain_text(category, case_obj, cat_map)
        except Exception:
            logging.exception("Failed to build plain text for category %s", category)


def copy_active_case_tables() -> None:
    """Copy the active case's tables into the system clipboard."""

    try:
        sessions = st.session_state.get("case_sessions")
        if not sessions:
            logging.info("Clipboard hotkey ignored: no case sessions available")
            return

        from case_documentation_app import CURRENT_CASE_IDX, active_category_map

        if not isinstance(CURRENT_CASE_IDX, int) or CURRENT_CASE_IDX < 0:
            logging.info("Clipboard hotkey ignored: invalid active case index")
            return
        if CURRENT_CASE_IDX >= len(sessions):
            logging.info("Clipboard hotkey ignored: case index %s out of range", CURRENT_CASE_IDX)
            return

        session = sessions[CURRENT_CASE_IDX]
        case_obj = getattr(session, "case", None)
        if case_obj is None:
            logging.info("Clipboard hotkey ignored: active session missing case data")
            return

        cat_map = active_category_map()
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
