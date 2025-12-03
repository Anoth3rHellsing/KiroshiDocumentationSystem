# -*- coding: utf-8 -*-
"""
Kiroshi Release 1.8.0 – IT Case Documentation Helper
Run:
    streamlit run case_documentation_app.py
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path
from dataclasses import asdict
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from logging.handlers import RotatingFileHandler

# Ensure local helper modules remain importable
APP_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = APP_DIR.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

# Kiroshi Imports
from KiroshiApp.constants import (
    VERSION, LOG_FILE, PROGRAM_DATA_DIR, DATABASE_DIR, PROGRAM_DATA_SENTINEL,
    DATABASE_DIR_PREEXISTED, PERSISTENT_SETTINGS_DEFAULTS, KIROSHI_LOGO_PATH,
    CASE_ATTACHMENTS_ROOT, DEFAULT_WELLNESS_SETTINGS, DEFAULT_OPENAI_API_KEY,
    DEFAULT_AI_BASE_URL, DEFAULT_AI_MODE, HOTKEY_TARGET_SESSION_KEY
)
from KiroshiApp.models import CaseData, CaseSession, _default_attachments_index, UpdateCheckResult
from KiroshiApp.utils import (
    determine_active_theme, apply_theme_palette, get_kiroshi_message
)
from KiroshiApp.services.data_manager import (
    _ensure_case_attachments_root, load_recent_cases,
    create_case_autosave_snapshot
)
from KiroshiApp.services.update_manager import (
    _discover_default_branch, _discover_remote_app_paths,
    _iter_remote_app_paths, check_for_updates
)
from KiroshiApp.views.dashboard_view import render_dashboard
from KiroshiApp.views.settings_view import render_settings_panel
from KiroshiApp.views.report_view import render_report_panel
from KiroshiApp.views.sprint.sprint_view import render_sprint_tab
from KiroshiApp.views.case_view import render_case_ui, render_screenshot_capture_footer

# Legacy imports for startup checks
# (kiroshi_chat, kiroshi_cloud_sync, kiroshi_hotkeys are external modules)
from kiroshi_chat import load_memory, get_assistant_notes, load_manual_docs, SYSTEM_PROMPT
from kiroshi_hotkeys import ensure_hotkey_listener, update_hotkey_snapshot

# ----------------- CONFIG & LOGGING -----------------

st.set_page_config(
    page_title=f"Kiroshi {VERSION}",
    layout="wide",
    page_icon=str(KIROSHI_LOGO_PATH),
)

def _setup_logging():
    candidates = []
    if os.name == "nt":
        program_data_root = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
        candidates.append(program_data_root / "Kiroshi" / "logs")
        candidates.append(PROGRAM_DATA_DIR / "logs")
    else:
        candidates.append(PROGRAM_DATA_DIR / "logs")
        candidates.append(Path.home() / "Kiroshi" / "logs")
    candidates.append(APP_DIR / "logs")

    log_path = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            prospective = candidate / LOG_FILE
            with open(prospective, "a", encoding="utf-8"):
                pass
            log_path = prospective
            break
        except OSError:
            continue

    handlers = [logging.StreamHandler()]
    if log_path:
        handlers.append(RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"))

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s [%(name)s:%(lineno)d] %(message)s",
        handlers=handlers,
    )
    logging.info("Kiroshi app started. Version: %s", VERSION)

_setup_logging()

def _check_installation_status() -> None:
    if os.name != "nt":
        DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        _ensure_case_attachments_root()
        return

    program_data_missing = not PROGRAM_DATA_DIR.exists() or not PROGRAM_DATA_SENTINEL.exists()
    program_files_missing = not DATABASE_DIR_PREEXISTED

    if program_data_missing or (program_data_missing and program_files_missing):
        st.error("Kiroshi installation incomplete. Please run KiroshiInstaller.")
        st.stop()

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_case_attachments_root()

_check_installation_status()

# ----------------- SESSION STATE -----------------

def _init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

_init_state("case", CaseData())
_init_state("case_sessions", [CaseSession(case=st.session_state.case)])
_init_state("uploads", [])
_init_state("log_uploads", [])
_init_state("screenshots", [])
_init_state("email_type", "Recap (Customer)")
_init_state("email_extra", {})
_init_state("include_escalations", False)
_init_state("include_hardware", False)
_init_state("debug_mode", False)
_init_state("openai_api_key", DEFAULT_OPENAI_API_KEY)
_init_state("openai_model", "gpt-4o")
_init_state("ai_base_url", DEFAULT_AI_BASE_URL)
_init_state("ai_mode", DEFAULT_AI_MODE)
_init_state("enable_holiday_theme", True)
_init_state("dark_mode_enabled", False)
_init_state("kiroshi_chat_history", load_memory())
_init_state("assistant_notes", get_assistant_notes())
_init_state("manual_docs", load_manual_docs())
_init_state("system_prompt", SYSTEM_PROMPT)
_init_state("kiroshi_sarcasm_mode", False)
_init_state("wellness_reminders", DEFAULT_WELLNESS_SETTINGS)
_init_state("tutorial_completed", False)
_init_state("show_tutorial", False)
_init_state("last_rendered_tab", "Dashboard")
_init_state("last_rendered_case", None)
_init_state("track_case", False)

# Theme application
CURRENT_THEME = determine_active_theme()
apply_theme_palette(CURRENT_THEME)

# ----------------- UI RENDERING -----------------

def inject_base_styles():
    st.markdown(
        """
        <style>
        .dashboard-title { font-size: 2.25rem; font-weight: 700; color: var(--kiroshi-primary); margin-bottom: 1.25rem; }
        .dashboard-section { margin: 1.5rem 0; padding: 1.5rem; background: var(--kiroshi-surface); border-radius: 1.1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        </style>
        """,
        unsafe_allow_html=True
    )

def render_logo():
    # Simplified logo header
    cols = st.columns([1, 4, 1])
    with cols[0]:
        st.image(str(KIROSHI_LOGO_PATH), width=150)
    with cols[1]:
        st.caption(f"Version {VERSION}")
        st.markdown(f"**{get_kiroshi_message(CURRENT_THEME)}**")
    with cols[2]:
        st.markdown(f"**{datetime.now().strftime('%A, %m/%d/%Y')}**")

def render_with_monitor(name, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except Exception as e:
        logging.error(f"Error rendering {name}: {e}", exc_info=True)
        st.error(f"Error loading {name}. Please check logs.")

# ----------------- MAIN APP -----------------

inject_base_styles()
render_logo()

# Handle case sessions
if "case_sessions" not in st.session_state or not st.session_state.case_sessions:
    st.session_state.case_sessions = [CaseSession(case=CaseData())]

visible_indices = [i for i in range(len(st.session_state.case_sessions))]
case_labels = [f"Case {i+1}" for i in visible_indices] + ["+ New Case"]

tab_labels = ["Dashboard", "Sprint", "Saved Cases", "Settings"]
if st.session_state.debug_mode:
    tab_labels.append("Debug")
tab_labels.append("Report")
tab_labels += case_labels

all_tabs = st.tabs(tab_labels)
tab_idx = 0

with all_tabs[tab_idx]:
    render_with_monitor("Dashboard", render_dashboard)
tab_idx += 1

with all_tabs[tab_idx]:
    render_with_monitor("Sprint", render_sprint_tab)
tab_idx += 1

with all_tabs[tab_idx]:
    from KiroshiApp.views.dashboard_view import render_saved_cases_page
    render_with_monitor("Saved Cases", render_saved_cases_page)
tab_idx += 1

with all_tabs[tab_idx]:
    render_with_monitor("Settings", render_settings_panel)
tab_idx += 1

if st.session_state.debug_mode:
    with all_tabs[tab_idx]:
        st.info("Debug panel moved to Settings > Workflow modes.")
        # We can re-implement full debug view here if needed
    tab_idx += 1

with all_tabs[tab_idx]:
    render_with_monitor("Report", render_report_panel)
tab_idx += 1

# Case Tabs
for i, tab in enumerate(all_tabs[tab_idx:]):
    with tab:
        if i == len(visible_indices):
            if st.button("Create New Case"):
                st.session_state.case_sessions.append(CaseSession(case=CaseData()))
                st.rerun()
        else:
            case_idx = visible_indices[i]
            render_with_monitor(f"Case {case_idx}", render_case_ui, case_idx)

# Global Hotkeys
ensure_hotkey_listener()
# We should update hotkey snapshot based on active case
active_idx = st.session_state.get(HOTKEY_TARGET_SESSION_KEY) # defined in constants/utils?
# Using a fallback if not defined
hotkey_target = st.session_state.get("hotkey_target_idx", 0)
if 0 <= hotkey_target < len(st.session_state.case_sessions):
    # We need category map for hotkeys.
    from KiroshiApp.views.case_view import active_category_map
    cat_map = active_category_map()
    update_hotkey_snapshot(
        st.session_state.case_sessions,
        hotkey_target,
        cat_map,
        st.session_state.get("last_prompt", "")
    )
