# -*- coding: utf-8 -*-
"""
Kiroshi RC 141025 – IT Case Documentation Helper
Run:
    streamlit run case_documentation_app.py
"""

from __future__ import annotations

import io
import itertools
import json
import os
import zipfile
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, asdict, fields, field, is_dataclass
from datetime import datetime, date, timedelta, timezone, time as datetime_time
from copy import deepcopy
import logging
import time
from pathlib import Path
import hashlib
import re
import base64
import binascii
import random
import subprocess
import sys
import math
import calendar
import uuid
import threading
from difflib import SequenceMatcher
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import lru_cache, partial
from typing import Any, Dict, List, Literal
from html import escape
import textwrap
import inspect
import traceback

import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components
from streamlit.errors import StreamlitAPIException
from logging.handlers import RotatingFileHandler
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    Preformatted,
)
from reportlab.graphics.shapes import Drawing, String

# Ensure local helper modules remain importable when the app is packaged in a
# standalone desktop bundle.  Streamlit Desktop places the entrypoint inside an
# ``_internal`` directory, so we add the bundle root (one directory up) to the
# import path before attempting to import sibling modules like ``kiroshi_chat``.
APP_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = APP_DIR.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
REPORTLAB_CHARTS_AVAILABLE = False
try:
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.lineplots import LinePlot

    REPORTLAB_CHARTS_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - fallback when graphics extras missing
    VerticalBarChart = None  # type: ignore[assignment]
    LinePlot = None  # type: ignore[assignment]
from reportlab.graphics.widgets.markers import makeMarker
import requests
import urllib3

try:  # pyautogui may require a GUI environment
    import pyautogui  # type: ignore
    PYAUTOGUI_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when display unavailable
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False

try:  # tkinter may be missing in headless environments
    import tkinter as tk

    TK_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when display unavailable
    tk = None
    TK_AVAILABLE = False

try:  # PIL's ImageGrab requires GUI capabilities
    from PIL import ImageGrab, Image as PILImage, ImageFilter

    IMAGEGRAB_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when Pillow is unavailable
    ImageGrab = None
    PILImage = None
    ImageFilter = None
    IMAGEGRAB_AVAILABLE = False

try:  # pytesseract is required for secure screenshots (OCR)
    import pytesseract  # type: ignore
    from pytesseract import Output

    PYTESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None
    PYTESSERACT_AVAILABLE = False

try:  # mss offers a headless-friendly screen capture fallback
    import mss  # type: ignore

    MSS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    mss = None
    MSS_AVAILABLE = False
from kiroshi_chat import (
    load_memory,
    save_memory,
    query_kiroshi,
    SYSTEM_PROMPT,
    load_manual_docs,
    save_manual_docs,
    search_manual_docs,
    get_assistant_notes,
    set_assistant_notes,
    build_assistant_memory_prompt,
    build_system_prompt,
)
from kiroshi_local_ai import (
    check_model_exists,
    download_model,
    MODELS
)
from kiroshi_cloud_sync import (
    AgentBlockedError as CloudAgentBlockedError,
    AuthenticationError as CloudAuthenticationError,
    CloudError as KiroshiCloudError,
    cloud_share_status,
    open_cloud_session as open_kiroshi_cloud_session,
    summarize_dataset as summarize_cloud_dataset,
    decode_device_token,
    overlay_guidance,
)
from kiroshi_video import optimize_video
from kiroshi_hotkeys import ensure_hotkey_listener, update_hotkey_snapshot

# Some corporate networks perform SSL interception with a self-signed
# certificate, which breaks standard certificate validation.  Disable
# warnings and certificate verification for outbound requests so the
# ChatGPT API and GitHub update checks can still be reached.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@contextmanager
def safe_modal(title: str, key: str | None = None):
    """Provide a backwards-compatible context manager for Streamlit modals."""

    try:
        modal_callable = getattr(st, "modal")
    except AttributeError:  # pragma: no cover - executed on older Streamlit versions
        modal_callable = None

    if callable(modal_callable):
        with modal_callable(title, key=key):
            yield
        return

    container = st.container()  # pragma: no cover - fallback path
    with container:
        st.markdown(f"### {title}")
        yield


def _require_reportlab_charts() -> None:
    """Ensure ReportLab's chart modules are available before rendering graphics."""

    if not REPORTLAB_CHARTS_AVAILABLE:
        raise RuntimeError(
            "ReportLab chart components are unavailable. Install the 'reportlab' package "
            "with its graphics extras to enable PDF chart rendering."
        )


VERSION = "1.8 Release Candidate 1"
TODAY_STR = datetime.now().strftime("%d%m%Y")
AUTOSAVE_FILE = "autosave.json"
AUTOSAVE_DIR = Path("autosaves")
_AUTOSAVE_SESSION_ID = uuid.uuid4().hex
DEFAULT_OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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",
)
DEFAULT_AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
DEFAULT_AI_MODE = "Cloud"
LOG_FILE = "app.log"

ERROR_DIALOG_MESSAGES = [
    "Even cybernetic scribes trip sometimes. Give me a second to regroup.",
    "That panel face-planted. Let's grab the logs before it pretends nothing happened.",
    "Something went sideways. Want to tag in Support with a quick report?",
    "Kiroshi hit a weird edge case. Capture it now so the engineers can slay it later.",
]


def _collect_recent_logs(max_bytes: int = 65536) -> str:
    """Return the tail of the application log file for diagnostics."""

    synthetic_payload = os.environ.get("KIROSHI_SYNTHETIC_LOGS")
    if isinstance(synthetic_payload, str) and synthetic_payload:
        return synthetic_payload

    log_path = Path(LOG_FILE)
    if not log_path.exists():
        return "Log file not found."

    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(size - max_bytes, 0)
            handle.seek(start)
            if start > 0:
                handle.readline()
            return handle.read().strip()
    except OSError as exc:
        logging.error("Unable to read log file %s: %s", log_path, exc)
        return f"Unable to read logs: {exc}"

PRIORITY_OPTIONS = ["Low", "Normal", "High", "On Time", "Escalation"]
DEFAULT_TRACKING_PRIORITY = "Normal"

CASE_DEX_URL_TEMPLATE = os.environ.get(
    "CASE_DEX_URL_TEMPLATE",
    "https://case-dex.example.com/api/cases/{case_id}/dex",
)

if os.name == "nt":
    PROGRAM_DATA_DIR = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Kiroshi Documentation"
    DATABASE_DIR = Path("C:/ProgramFiles/KiroshiDatabase")
else:
    PROGRAM_DATA_DIR = Path.home() / "Kiroshi Documentation"
    DATABASE_DIR = Path.home() / "KiroshiDatabase"

DATABASE_DIR_PREEXISTED = DATABASE_DIR.exists()
PROGRAM_DATA_SENTINEL = PROGRAM_DATA_DIR / "case_documentation_app.py"

PDF_FONT_REGULAR_NAME = "Helvetica"
PDF_FONT_BOLD_NAME = "Helvetica-Bold"

STREAMLIT_FONT_STACK_CSS = (
    "var(--font, 'Space Grotesk', 'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)"
)
STREAMLIT_HEADING_FONT_STACK = (
    "'Space Grotesk', 'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
)
STREAMLIT_FONT_FALLBACK = "Space Grotesk"


def _ensure_pdf_fonts() -> tuple[str, str]:
    """Return the Helvetica fonts used across generated PDFs."""

    return (PDF_FONT_REGULAR_NAME, PDF_FONT_BOLD_NAME)


@st.cache_resource(ttl=None)
def _load_pdf_styles():
    """Return a stylesheet configured with the application's PDF fonts."""

    styles = getSampleStyleSheet()
    regular_font, bold_font = _ensure_pdf_fonts()

    for name in ("Normal", "BodyText", "Italic", "Code"):
        if name in styles.byName:
            styles[name].fontName = regular_font

    for name in ("Title", "Heading1", "Heading2", "Heading3", "Heading4", "Heading5", "Heading6"):
        if name in styles.byName:
            styles[name].fontName = bold_font

    ghost_style = ParagraphStyle(
        name="GhostText",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=0.1,
        leading=0.12,
        textColor=colors.white,
    )

    return styles, regular_font, bold_font, ghost_style


def _build_pdf_with_ghost_text(
    doc: SimpleDocTemplate, elements: list, snippets: Sequence[str]
) -> None:
    """Render a PDF and inject ASCII-only text for simple extractors."""

    visible: list[str] = []
    for chunk in snippets:
        text = str(chunk).strip()
        if text:
            visible.append(text)

    if visible:
        ghost_text = "\n".join(visible)
        try:
            ghost_text = ghost_text.encode("latin-1", "ignore").decode("latin-1")
        except Exception:  # pragma: no cover - extremely unlikely fallback
            ghost_text = ghost_text.encode("ascii", "ignore").decode("ascii")

        from reportlab import rl_config
        from reportlab.pdfbase import pdfdoc

        def _inject(canvas, _doc):
            canvas.saveState()
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica", 1)
            y = 12
            for line in ghost_text.split("\n"):
                raw_bytes = line.encode("latin-1", "ignore")
                literal = pdfdoc.PDFString(raw_bytes, escape=0, enc="latin-1")
                command = f"BT 1 0 0 1 8 {y:.2f} Tm {literal.format(canvas._doc).decode('latin-1')} Tj ET"
                canvas._code.append(command)
                y += 1.2
            canvas.restoreState()

        original_use_a85 = getattr(rl_config, "useA85", 1)
        try:
            rl_config.useA85 = 0
            try:
                doc.build(elements, onFirstPage=_inject, onLaterPages=_inject)
            except TypeError:
                doc.build(elements)
        finally:
            rl_config.useA85 = original_use_a85
        return

    doc.build(elements)

UTILITIES_DIR = DATABASE_DIR / "utilities"
UPDATES_DIR = UTILITIES_DIR / "updates"
RECENT_CASES_PATH = UTILITIES_DIR / "recent_cases.json"
TRACKED_CASES_DIR = DATABASE_DIR / "TrackedCases"

CASE_TAB_MEMORY_FILE = DATABASE_DIR / "case_tabs_memory.json"

# Location for persisted case attachments
DOCUMENTS_DIR = Path.home() / "Documents"
CASE_ATTACHMENTS_ROOT = DOCUMENTS_DIR / "kiroshi"

AUTOHOTKEY_SCRIPT_PATH = DATABASE_DIR / "kiroshi_tables_hotkeys.ahk"


def _resolve_configured_attachments_directory() -> Path:
    """Return the attachments directory requested by the current settings."""

    raw_value: object = _persistent_settings_cache.get(
        "attachments_directory", str(CASE_ATTACHMENTS_ROOT)
    )
    if hasattr(st, "session_state") and isinstance(
        st.session_state.get("attachments_directory"), str
    ):
        raw_value = st.session_state.attachments_directory
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            return Path(raw_value).expanduser()
        except Exception:  # pragma: no cover - defensive conversion guard
            logging.warning(
                "Invalid attachments directory provided in settings: %s",
                raw_value,
            )
    return CASE_ATTACHMENTS_ROOT


def _ensure_case_attachments_root() -> tuple[Path, OSError | None]:
    """Ensure the configured attachments root exists, falling back on failure."""

    requested_root = _resolve_configured_attachments_directory()
    try:
        requested_root.mkdir(parents=True, exist_ok=True)
        return requested_root, None
    except OSError as exc:
        logging.warning(
            "Unable to create attachments directory %s: %s", requested_root, exc
        )
        try:
            CASE_ATTACHMENTS_ROOT.mkdir(parents=True, exist_ok=True)
        except OSError as fallback_exc:
            logging.error(
                "Failed to create fallback attachments directory %s: %s",
                CASE_ATTACHMENTS_ROOT,
                fallback_exc,
            )
            raise fallback_exc
        return CASE_ATTACHMENTS_ROOT, exc


def _initialize_storage_paths() -> None:
    """Ensure user-writable directories exist after installation is verified."""

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    UTILITIES_DIR.mkdir(parents=True, exist_ok=True)
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    if not RECENT_CASES_PATH.exists():
        RECENT_CASES_PATH.write_text("[]", encoding="utf-8")
    TRACKED_CASES_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_case_attachments_root()

APP_ROOT = Path(__file__).resolve().parent
# The project repository was transferred from the ``KiroshiCorp`` GitHub
# organisation to ``Anoth3rHellsing``.  The update checker still defaulted to
# the previous location which meant fresh installations always hit a 404 when
# trying to retrieve ``case_documentation_app.py`` for the version check.
# Point the default to the new canonical repository and dynamically fall back to
# the repository's configured default branch so users no longer see the
# "Unable to retrieve remote version" warning on startup.
DEFAULT_UPDATE_REPO = "Anoth3rHellsing/KiroshiDocumentationSystem"
DEFAULT_UPDATE_BRANCH = "main"
GITHUB_TOKEN_ENV_VAR = "KIROSHI_UPDATE_GITHUB_TOKEN"
GITHUB_API_VERSION = "2022-11-28"
try:
    UPDATE_CHECK_TIMEOUT = float(os.environ.get("KIROSHI_UPDATE_TIMEOUT", "15"))
except (TypeError, ValueError):
    UPDATE_CHECK_TIMEOUT = 15.0


SETTINGS_FILE = DATABASE_DIR / "settings.json"
SPRINT_STATE_FILE = DATABASE_DIR / "sprint_state.json"
DEFAULT_WELLNESS_SETTINGS: dict[str, object] = {
    "enabled": False,
    "notification_lead": 10,
    "schedule": {
        "break_1": "10:30",
        "lunch": "12:30",
        "break_2": "15:00",
    },
}

WELLNESS_EVENT_METADATA: dict[str, dict[str, object]] = {
    "break_1": {"label": "First Break", "duration_minutes": 15},
    "lunch": {"label": "Lunch", "duration_minutes": 60},
    "break_2": {"label": "Second Break", "duration_minutes": 15},
}

WELLNESS_TIPS: list[str] = [
    "Stand up, stretch, and let your eyes relax for a moment.",
    "A quick walk to refill your water can reboot your focus.",
    "Deep breaths in, slow breaths out — your circuits will thank you.",
    "Jot down one win from today while you recharge.",
    "Hydration check! Your brain runs smoother with water.",
    "Silence notifications for a minute and enjoy the pause.",
]

PERSISTENT_SETTINGS_DEFAULTS: dict[str, object] = {
    "second_line_mode": False,
    "debug_mode": False,
    "frutiger_aero_mode": False,
    "case_compact_mode": False,
    "show_kiroshi_chat": True,
    "autosave_to_database": False,
    "ai_assist_mode": "Standard",
    "ai_educate_enabled": False,
    "ai_educate_report_enabled": False,
    "ai_educate_advanced": False,
    "agent_first_name": "",
    "agent_last_name": "",
    "attachments_directory": str(CASE_ATTACHMENTS_ROOT),
    "tutorial_completed": False,
    "tutorial_completed_at": "",
    "tutorial_completion_type": "",
    "tutorial_metadata": {
        "version": "",
        "visited": [],
        "last_step": 0,
        "total_steps": 0,
        "completed": False,
        "completion_type": "",
        "completed_at": "",
        "furthest_step": 0,
    },
    "enable_holiday_theme": True,
    "dark_mode_enabled": False,
    "wellness_reminders": DEFAULT_WELLNESS_SETTINGS,
    "kiroshi_sarcasm_mode": False,
    "ai_mode": DEFAULT_AI_MODE,
    "openai_api_key": "",
    "ai_base_url": DEFAULT_AI_BASE_URL,
    "openai_model": "gpt-5-nano",
    "local_ai_profile": "speed",
}


@st.cache_data(ttl=None, max_entries=1)
def _load_settings_from_disk_cached(mtime: float) -> dict[str, object]:
    """Load and parse the settings file, cached until modification time changes."""
    # The mtime argument drives the cache invalidation.
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Failed to load settings from %s: %s", SETTINGS_FILE, exc)
        return {}
    if not isinstance(data, dict):
        logging.warning("Settings file %s did not contain a JSON object", SETTINGS_FILE)
        return {}
    if "show_atom_chat" in data and "show_kiroshi_chat" not in data:
        data["show_kiroshi_chat"] = data.get("show_atom_chat")
    filtered: dict[str, object] = {}
    for key, default in PERSISTENT_SETTINGS_DEFAULTS.items():
        value = data.get(key, default)
        if isinstance(default, bool) and isinstance(value, bool):
            filtered[key] = value
        elif isinstance(default, str) and isinstance(value, str):
            filtered[key] = value
        elif isinstance(default, dict) and isinstance(value, dict):
            filtered[key] = value
    return filtered


def _load_persistent_settings() -> dict[str, object]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        mtime = SETTINGS_FILE.stat().st_mtime
    except OSError:
        return {}
    return _load_settings_from_disk_cached(mtime)


_persistent_settings_cache: dict[str, object] = PERSISTENT_SETTINGS_DEFAULTS.copy()


def _extract_theme_query_overrides() -> dict[str, object]:
    """Return theme overrides sourced from the current URL query parameters."""

    def _normalise_params(candidate: object) -> dict[str, object] | None:
        if candidate is None:
            return None
        if callable(candidate):  # pragma: no cover - defensive fallback
            try:
                return _normalise_params(candidate())
            except Exception:
                return None
        if hasattr(candidate, "to_dict"):
            try:
                return getattr(candidate, "to_dict")()
            except Exception:
                return None
        if isinstance(candidate, dict):
            return dict(candidate)
        try:
            items = getattr(candidate, "items")
        except AttributeError:
            return None
        try:
            return dict(items())
        except Exception:
            return None

    params: dict[str, object] | None = None

    try:
        params_obj = getattr(st, "query_params")
    except AttributeError:
        params_obj = None
    except StreamlitAPIException:
        return {}
    else:
        params = _normalise_params(params_obj)

    if params is None:
        try:
            params = st.experimental_get_query_params()
        except AttributeError:  # pragma: no cover - Streamlit >= 1.32
            params = {}
        except StreamlitAPIException:
            return {}
        except Exception:  # pragma: no cover - defensive fallback
            return {}

    overrides: dict[str, object] = {}

    def _pop_str_value(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, list):
            if not value:
                return None
            return str(value[-1]).strip()
        return str(value).strip()

    raw_theme = _pop_str_value(params.get("theme_preview")) if isinstance(params, dict) else None
    if raw_theme is not None and raw_theme != "":
        overrides["theme_preview"] = raw_theme

    raw_holiday = _pop_str_value(params.get("enable_holiday_theme")) if isinstance(params, dict) else None
    if raw_holiday is not None and raw_holiday != "":
        normalized = raw_holiday.lower()
        overrides["enable_holiday_theme"] = normalized not in {"0", "false", "off", "no"}

    raw_dark = _pop_str_value(params.get("dark_mode")) if isinstance(params, dict) else None
    if raw_dark is not None and raw_dark != "":
        normalized = raw_dark.lower()
        overrides["dark_mode_enabled"] = normalized not in {"0", "false", "off", "no"}

    return overrides


_THEME_QUERY_OVERRIDES = _extract_theme_query_overrides()


_CASE_REFERENCE_PATTERN = re.compile(
    r"\b(?:case|caso|ticket|inc(?:ident)?|sr|cs|bug|pr|issue)[-_\s]*\d+\b",
    re.IGNORECASE,
)
_SERIAL_PATTERN = re.compile(r"\b[A-Z]{2,}\d{3,}\b")
_URL_PATTERN = re.compile(r"https?://\S+")
_NON_ALPHANUMERIC_PATTERN = re.compile(r"[^0-9A-Za-z]+")
_LOWER_ALPHANUM_PATTERN = re.compile(r"[^0-9a-z]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")

_GENERIC_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "from",
    "this",
    "have",
    "error",
    "issue",
    "case",
    "user",
    "when",
    "failed",
    "failure",
    "problem",
    "unable",
    "cannot",
    "customer",
    "reported",
    "report",
    "see",
    "observed",
    "during",
    "while",
    "into",
    "after",
    "before",
    "still",
    "does",
    "doesnt",
    "cant",
    "wont",
    "need",
    "needs",
    "should",
    "could",
    "would",
    "please",
    "help",
    "team",
    "agent",
    "support",
    "customer",
    "client",
    "system",
    "service",
    "application",
    "apps",
    "app",
    "server",
    "environment",
    "production",
    "prod",
    "dev",
    "test",
    "staging",
    "login",
    "log",
    "logs",
    "message",
    "messages",
    "details",
    "detail",
    "null",
    "none",
    "na",
    "unknown",
    "new",
    "open",
    "closed",
}


TITLE_SIMILARITY_STOPWORDS = {
    "issue",
    "issues",
    "problem",
    "problems",
    "error",
    "errors",
    "case",
    "cases",
    "support",
    "please",
    "help",
    "need",
}


_REPORT_CATEGORY_HINTS: dict[str, dict[str, object]] = {
    "3Shape Unite / Login": {
        "tokens": (
            "unite",
            "signin",
            "sign",
            "login",
            "credential",
            "token",
            "account",
            "password",
            "sesion",
            "cuenta",
        ),
        "category_terms": (
            "unite / login",
            "unite login",
            "login / unite",
        ),
        "min_score": 2,
    },
    "3Shape Unite / Case Submission": {
        "tokens": (
            "proxy",
            "timeout",
            "firewall",
            "submission",
            "submit",
            "upload",
            "envio",
            "enviar",
            "case",
            "inbox",
            "transfer",
        ),
        "category_terms": (
            "unite / case",
            "unite / submission",
            "case submission",
            "send case",
        ),
        "min_score": 2,
    },
    "TRIOS / Calibration": {
        "tokens": (
            "calibr",
            "drift",
            "tip",
            "aline",
            "alignment",
            "dongle",
            "firmware",
            "led",
        ),
        "category_terms": (
            "trios / calibration",
            "calibration",
        ),
        "min_score": 1,
    },
    "TRIOS / Scan Quality": {
        "tokens": (
            "scan",
            "occlusion",
            "margin",
            "artefact",
            "artifact",
            "noise",
            "texture",
            "superpos",
            "detalle",
            "detail",
        ),
        "category_terms": (
            "trios / scan",
            "scan quality",
        ),
        "min_score": 2,
    },
    "Dental System / Performance": {
        "tokens": (
            "performance",
            "freeze",
            "crash",
            "lag",
            "slow",
            "render",
            "rendering",
            "ds",
        ),
        "category_terms": (
            "dental system",
            "ds / performance",
        ),
        "min_score": 2,
    },
    "Hardware / Connectivity": {
        "tokens": (
            "usb",
            "power",
            "cable",
            "battery",
            "connect",
            "conexion",
            "bluetooth",
            "wifi",
            "ethernet",
            "adapter",
        ),
        "category_terms": (
            "hardware",
            "connectivity",
        ),
        "min_score": 2,
    },
    "Software / Installation": {
        "tokens": (
            "install",
            "setup",
            "installer",
            "update",
            "upgrade",
            "patch",
            "deploy",
            "reinstall",
        ),
        "category_terms": (
            "installation",
            "software install",
        ),
        "min_score": 2,
    },
    "Account / Licensing": {
        "tokens": (
            "license",
            "licence",
            "licencia",
            "activation",
            "renew",
            "billing",
            "suscription",
            "subscription",
        ),
        "category_terms": (
            "license",
            "licensing",
            "licencia",
        ),
        "min_score": 1,
    },
    "Data Management": {
        "tokens": (
            "database",
            "backup",
            "restore",
            "export",
            "import",
            "sync",
            "sinc",
            "storage",
        ),
        "category_terms": (
            "data management",
            "database",
        ),
        "min_score": 2,
    },
}


_STRUCTURED_CATEGORY_HINTS: dict[str, dict[str, object]] = {
    "Scanner Hardware": {
        "scanner_models": (
            "trios 3",
            "trios3",
            "trios 4",
            "trios4",
            "trios 5",
            "trios5",
            "trios move",
            "trios move+",
            "move+",
            "move plus",
            "pod",
            "pod 3",
            "pod 4",
            "go",
        ),
        "root_cause_codes": (
            "hw",
            "hardware",
            "scanner",
            "device",
        ),
        "recurrence_threshold": 2,
    },
    "Software / Installation": {
        "root_cause_codes": (
            "bug",
            "sw",
            "software",
            "defect",
        ),
        "tokens": ("bug", "defect"),
        "recurrence_threshold": 1,
    },
    "Hardware / Connectivity": {
        "root_cause_codes": (
            "net",
            "network",
            "connect",
            "vpn",
            "wifi",
        ),
    },
    "Workflow Guidance": {
        "root_cause_codes": (
            "workflow",
            "training",
            "usage",
            "user",
        ),
    },
    "Account / Licensing": {
        "root_cause_codes": (
            "lic",
            "license",
            "licensing",
        ),
    },
    "Data Management": {
        "root_cause_codes": (
            "db",
            "database",
            "backup",
            "restore",
            "sync",
        ),
    },
}


@lru_cache(maxsize=1024)
def _tokenize_issue_description(text: str) -> tuple[str, ...]:
    cleaned = _CASE_REFERENCE_PATTERN.sub(" ", text)
    cleaned = _SERIAL_PATTERN.sub(" ", cleaned)
    cleaned = _URL_PATTERN.sub(" ", cleaned)
    cleaned = _NON_ALPHANUMERIC_PATTERN.sub(" ", cleaned)
    tokens = [token.lower() for token in cleaned.split() if len(token) >= 3]
    return tuple(token for token in tokens if token not in _GENERIC_STOPWORDS and not token.isdigit())


@lru_cache(maxsize=1024)
def _cached_normalize_title(value: str) -> str:
    lowered = value.lower()
    cleaned = _LOWER_ALPHANUM_PATTERN.sub(" ", lowered)
    return _WHITESPACE_PATTERN.sub(" ", cleaned).strip()


def _normalize_title_similarity(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return _cached_normalize_title(value)


def _title_similarity_tokens(title: object) -> set[str]:
    if not isinstance(title, str):
        return set()
    return {
        token
        for token in _tokenize_issue_description(title)
        if token not in TITLE_SIMILARITY_STOPWORDS
    }


def _title_similarity_score(
    tokens_a: set[str], tokens_b: set[str], norm_a: str, norm_b: str
) -> float:
    if tokens_a and tokens_b and tokens_a.isdisjoint(tokens_b):
        return 0.0

    base = SequenceMatcher(None, norm_a, norm_b).ratio() if (norm_a or norm_b) else 0.0
    if tokens_a and tokens_b:
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        jaccard = (intersection / union) if union else 0.0
        return 0.6 * base + 0.4 * jaccard
    return base


def _cluster_case_titles(titles: Sequence[str]) -> tuple[list[int], dict[int, str]]:
    clusters: list[dict[str, object]] = []
    assignments: list[int] = []

    # Inverted index: token -> set of cluster indices
    token_index: dict[str, set[int]] = defaultdict(set)
    # Clusters with no tokens (fallback for normalization-only matches)
    empty_token_clusters: set[int] = set()

    for title in titles:
        normalized = _normalize_title_similarity(title)
        tokens = _title_similarity_tokens(title)

        if not normalized and not tokens:
            blank_index = next(
                (
                    idx
                    for idx, cluster in enumerate(clusters)
                    if not cluster.get("tokens") and not cluster.get("normalized")
                ),
                None,
            )
            if blank_index is None:
                clusters.append(
                    {
                        "normalized": "",
                        "tokens": set(),
                        "label": "Caso sin título",
                    }
                )
                blank_index = len(clusters) - 1
                empty_token_clusters.add(blank_index)
            assignments.append(blank_index)
            continue

        best_index = -1
        best_score = 0.0

        # Optimization: Only check clusters that share at least one token
        # or have no tokens (and rely on string similarity).
        if not tokens:
            candidate_indices = range(len(clusters))
        else:
            candidates = set()
            for token in tokens:
                if token in token_index:
                    candidates.update(token_index[token])
            candidates.update(empty_token_clusters)
            candidate_indices = sorted(candidates)

        for idx in candidate_indices:
            cluster = clusters[idx]
            cluster_tokens = cluster.get("tokens") or set()
            cluster_norm = str(cluster.get("normalized") or "")
            score = _title_similarity_score(tokens, cluster_tokens, normalized, cluster_norm)
            if score > best_score:
                best_score = score
                best_index = idx

        threshold = 0.68 if tokens else 0.8
        if best_index == -1 or best_score < threshold:
            label_source = title if isinstance(title, str) and title.strip() else normalized
            label = (
                _summarize_text(label_source, width=80)
                if label_source
                else "Caso sin título"
            )
            clusters.append(
                {
                    "normalized": normalized,
                    "tokens": set(tokens),
                    "label": label,
                }
            )
            new_idx = len(clusters) - 1
            if tokens:
                for token in tokens:
                    token_index[token].add(new_idx)
            else:
                empty_token_clusters.add(new_idx)
            assignments.append(new_idx)
        else:
            cluster = clusters[best_index]
            cluster_tokens = cluster.get("tokens")
            if cluster_tokens is None:
                cluster_tokens = set()
                cluster["tokens"] = cluster_tokens

            new_tokens_added = tokens - cluster_tokens
            cluster_tokens.update(new_tokens_added)

            for token in new_tokens_added:
                token_index[token].add(best_index)

            # If cluster was previously empty of tokens but now has some, remove from empty_set
            if new_tokens_added and len(cluster_tokens) == len(new_tokens_added):
                empty_token_clusters.discard(best_index)

            cluster["normalized"] = cluster.get("normalized") or normalized
            if isinstance(title, str) and title.strip():
                candidate_label = _summarize_text(title, width=80)
                if len(candidate_label) > len(str(cluster.get("label") or "")):
                    cluster["label"] = candidate_label
            assignments.append(best_index)

    label_map = {idx: str(cluster.get("label") or "Caso sin título") for idx, cluster in enumerate(clusters)}
    return assignments, label_map


@lru_cache(maxsize=1024)
def _cached_normalize_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip().lower()


def _normalize_text_field(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return _cached_normalize_text(value)


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _infer_report_category(
    row: Mapping[str, object], tokens: list[str]
) -> str | None:
    token_counter = Counter(token.lower() for token in tokens if token)
    if not token_counter:
        return None

    category_fields: list[str] = []
    for key in ("category", "classification", "topic"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            category_fields.append(value.lower())
    category_blob = " ".join(category_fields)

    scores: dict[str, int] = {}
    for label, hints in _REPORT_CATEGORY_HINTS.items():
        score = 0
        category_terms = hints.get("category_terms")
        if isinstance(category_terms, (list, tuple, set)):
            for term in category_terms:
                if isinstance(term, str) and term and term in category_blob:
                    score += 4
        token_prefixes = hints.get("tokens")
        if isinstance(token_prefixes, (list, tuple, set)):
            for prefix in token_prefixes:
                if not isinstance(prefix, str) or not prefix:
                    continue
                for token, count in token_counter.items():
                    if token == prefix or token.startswith(prefix):
                        score += count
        if score:
            scores[label] = score

    if not scores:
        return None

    best_label, best_score = max(scores.items(), key=lambda item: item[1])
    threshold_raw = _REPORT_CATEGORY_HINTS.get(best_label, {}).get("min_score", 2)
    try:
        threshold = int(threshold_raw)
    except (TypeError, ValueError):
        threshold = 2
    if best_score >= threshold:
        return best_label
    return None


def _infer_structured_category(
    row: Mapping[str, object], tokens: list[str], context: Mapping[str, object] | None = None
) -> tuple[str, int] | None:
    context = context or {}
    scanner_candidates = [
        row.get("scanner_model"),
        row.get("scanner"),
        row.get("scanner_type"),
        row.get("scanner_sn"),
    ]
    scanner_model = ""
    for candidate in scanner_candidates:
        if isinstance(candidate, str) and candidate.strip():
            scanner_model = candidate.strip()
            break

    scanner_norm = _normalize_text_field(scanner_model)
    root_cause_code = row.get("root_cause_code") or row.get("root_cause_id")
    if isinstance(root_cause_code, str):
        root_cause_code_norm = _normalize_text_field(root_cause_code)
    elif isinstance(root_cause_code, (int, float)):
        root_cause_code_norm = str(root_cause_code)
    else:
        root_cause_code_norm = ""

    root_cause_text = _normalize_text_field(row.get("root_cause"))
    recurrence_count = _coerce_int(row.get("recurrence_count"), 0)
    structured_scores: dict[str, int] = {}

    token_set = {token.lower() for token in tokens}

    for label, hints in _STRUCTURED_CATEGORY_HINTS.items():
        score = 0
        codes = hints.get("root_cause_codes")
        if codes:
            for candidate in codes:
                candidate_norm = _normalize_text_field(candidate)
                if not candidate_norm:
                    continue
                if root_cause_code_norm and (
                    root_cause_code_norm == candidate_norm
                    or root_cause_code_norm.startswith(candidate_norm)
                ):
                    score += 8
                if candidate_norm and candidate_norm in root_cause_text:
                    score += 3
        scanner_models = hints.get("scanner_models")
        if scanner_models and scanner_norm:
            for candidate in scanner_models:
                candidate_norm = _normalize_text_field(candidate)
                if not candidate_norm:
                    continue
                if scanner_norm == candidate_norm or scanner_norm.startswith(candidate_norm):
                    score += 6
        token_prefixes = hints.get("tokens")
        if token_prefixes:
            for prefix in token_prefixes:
                prefix_norm = _normalize_text_field(prefix)
                if not prefix_norm:
                    continue
                for token in token_set:
                    if token.startswith(prefix_norm):
                        score += 1
        threshold = _coerce_int(hints.get("recurrence_threshold"), 0)
        if threshold and recurrence_count >= threshold:
            score += 2
        if score:
            structured_scores[label] = score

    if not structured_scores:
        return None

    return max(structured_scores.items(), key=lambda item: item[1])


def _derive_analysis_label(
    row: Mapping[str, object], context: Mapping[str, object] | None = None
) -> str:
    context = context or {}
    recurrence_count = _coerce_int(row.get("recurrence_count"), 0)

    title_cluster_label = row.get("title_cluster_label")
    if isinstance(title_cluster_label, str):
        cluster_label = title_cluster_label.strip()
        if cluster_label:
            if recurrence_count >= 3 and "Recurring" not in cluster_label:
                return f"{cluster_label} (Recurring)"
            return cluster_label

    text_candidates: list[str] = []
    for key in (
        "category",
        "classification",
        "topic",
        "root_cause",
        "title",
        "description_excerpt",
    ):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            text_candidates.append(value)

    tokens: list[str] = []
    for text in text_candidates:
        tokens.extend(_tokenize_issue_description(text))

    keywords = row.get("keywords")
    if isinstance(keywords, (list, tuple, set)):
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.strip():
                tokens.extend(_tokenize_issue_description(keyword))

    structured_match = _infer_structured_category(row, tokens, context)
    scanner_label_map: Mapping[str, str] = context.get("scanner_labels", {}) if context else {}
    root_cause_label_map: Mapping[str, str] = context.get("root_cause_labels", {}) if context else {}
    scanner_model = ""
    for candidate in (
        row.get("scanner_model"),
        row.get("scanner"),
        row.get("scanner_type"),
        row.get("scanner_sn"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            scanner_model = candidate.strip()
            break

    root_cause_code = row.get("root_cause_code") or row.get("root_cause_id")
    if isinstance(root_cause_code, str):
        root_cause_code_display = root_cause_code.strip().upper()
    elif root_cause_code is not None:
        root_cause_code_display = str(root_cause_code)
    else:
        root_cause_code_display = ""

    root_cause_text_norm = _normalize_text_field(row.get("root_cause"))
    root_cause_display = (
        root_cause_label_map.get(root_cause_text_norm)
        if root_cause_label_map
        else row.get("root_cause")
    )

    if structured_match:
        label, score = structured_match
        if root_cause_code_display:
            return f"{label} – {root_cause_code_display}"
        if scanner_model:
            return f"{label} – {scanner_model}"
        if recurrence_count >= 3:
            return f"{label} (Recurring)"
        return label

    inferred_category = _infer_report_category(row, tokens)
    if inferred_category:
        if recurrence_count >= 3:
            return f"{inferred_category} (Recurring)"
        return inferred_category

    if root_cause_code_display:
        return f"Root Cause – {root_cause_code_display}"

    if scanner_model:
        scanner_norm = _normalize_text_field(scanner_model)
        display = scanner_label_map.get(scanner_norm, scanner_model)
        return f"Scanner – {display}"

    if recurrence_count >= 3:
        if isinstance(root_cause_display, str) and root_cause_display.strip():
            return f"Recurring – {_summarize_text(root_cause_display, width=40)}"
        return "Recurring Issue"

    if tokens:
        top_tokens: list[str] = []
        for token, _ in Counter(tokens).most_common():
            if token not in top_tokens:
                top_tokens.append(token)
            if len(top_tokens) >= 2:
                break
        if top_tokens:
            return " / ".join(token.title() for token in top_tokens)

    if isinstance(root_cause_display, str) and root_cause_display.strip():
        return _summarize_text(root_cause_display, width=40)

    if text_candidates:
        return _summarize_text(text_candidates[0], width=40)

    return "General"
_persistent_settings_cache.update(_load_persistent_settings())
if "enable_holiday_theme" in _THEME_QUERY_OVERRIDES:
    _persistent_settings_cache["enable_holiday_theme"] = bool(
        _THEME_QUERY_OVERRIDES["enable_holiday_theme"]
    )
if "dark_mode_enabled" in _THEME_QUERY_OVERRIDES:
    _persistent_settings_cache["dark_mode_enabled"] = bool(
        _THEME_QUERY_OVERRIDES["dark_mode_enabled"]
    )


def _persist_setting(key: str) -> None:
    if key not in PERSISTENT_SETTINGS_DEFAULTS:
        return
    value = st.session_state.get(key, PERSISTENT_SETTINGS_DEFAULTS[key])
    _persistent_settings_cache[key] = value
    try:
        with SETTINGS_FILE.open("w", encoding="utf-8") as fh:
            json.dump(_persistent_settings_cache, fh, indent=2, sort_keys=True)
    except OSError as exc:
        logging.warning("Failed to persist setting %s: %s", key, exc)


@dataclass
class UpdateCheckResult:
    repo: str
    branch: str
    current_version: str
    latest_version: str | None = None
    latest_commit: str | None = None
    latest_published: str | None = None
    has_update: bool = False
    download_url: str | None = None
    error: str | None = None


def _discover_default_branch(repo: str) -> str | None:
    """Return the default branch configured for the remote repository."""

    api_url = f"https://api.github.com/repos/{repo}"
    headers = _build_github_headers()
    try:
        response = requests.get(
            api_url,
            headers=headers,
            timeout=UPDATE_CHECK_TIMEOUT,
            verify=False,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        logging.debug("Unable to query repository metadata for %s: %s", repo, exc)
        return None
    except requests.RequestException as exc:  # pragma: no cover - network errors
        logging.debug("Unable to query repository metadata for %s: %s", repo, exc)
        return None

    payload = response.json()
    default_branch = payload.get("default_branch") if isinstance(payload, dict) else None
    if isinstance(default_branch, str):
        default_branch = default_branch.strip()
    if default_branch:
        return default_branch
    logging.debug(
        "Repository metadata for %s did not include a default_branch: %s",
        repo,
        payload,
    )
    return None


def _resolve_update_target() -> tuple[str, str]:
    repo = os.environ.get("KIROSHI_UPDATE_REPO", DEFAULT_UPDATE_REPO).strip()
    if not repo:
        repo = DEFAULT_UPDATE_REPO
    if "/" not in repo:
        raise ValueError(
            "Invalid GitHub repository configured for updates. Use the form 'owner/repository'."
        )

    env_branch = os.environ.get("KIROSHI_UPDATE_BRANCH")
    branch = env_branch.strip() if isinstance(env_branch, str) else ""
    if not branch:
        branch = _discover_default_branch(repo) or DEFAULT_UPDATE_BRANCH
    return repo, branch


def _get_update_token() -> str:
    """Return the GitHub token configured for update checks, if any."""

    return os.environ.get(GITHUB_TOKEN_ENV_VAR, "").strip()


def _build_github_headers(*, accept: str = "application/vnd.github+json") -> dict[str, str]:
    """Return standard headers for GitHub API requests."""

    headers = {"Accept": accept, "X-GitHub-Api-Version": GITHUB_API_VERSION}
    token = _get_update_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _discover_remote_app_paths(repo: str, branch: str) -> Iterable[str]:
    """Inspect the Git tree and yield locations of the Streamlit entry point.

    Some operators keep ``case_documentation_app.py`` in nested directories
    (for example inside ``src/`` or a project-named folder).  When the
    location diverges from the repository root the raw ``GET`` lookup falls
    back to our built-in candidate list, which fails to cover unusual layouts
    such as ``tools/streamlit/case_documentation_app.py``.  Query the GitHub
    tree API once per update check so we can discover the exact location
    dynamically.  Any API failure is logged at debug level and silently
    ignored so the traditional heuristics remain available.
    """

    api_url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    headers = _build_github_headers()
    try:
        response = requests.get(
            api_url,
            headers=headers,
            timeout=UPDATE_CHECK_TIMEOUT,
            verify=False,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            logging.debug(
                "Repository tree lookup returned 404 for %s@%s", repo, branch
            )
            return
        logging.debug("Unable to query repository tree: %s", exc)
        return
    except requests.RequestException as exc:  # pragma: no cover - network errors
        logging.debug("Unable to query repository tree: %s", exc)
        return

    payload = response.json()
    tree = payload.get("tree") if isinstance(payload, dict) else None
    if not isinstance(tree, list):
        logging.debug("Unexpected tree payload when discovering app path: %s", payload)
        return

    for entry in tree:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "blob":
            continue
        path = entry.get("path")
        if isinstance(path, str) and path.endswith("case_documentation_app.py"):
            yield path


def _ensure_update_branch_accessible(repo: str, branch: str) -> None:
    """Raise an informative error when the update target cannot be accessed."""

    api_url = f"https://api.github.com/repos/{repo}/branches/{branch}"
    headers = _build_github_headers()
    try:
        response = requests.get(
            api_url,
            headers=headers,
            timeout=UPDATE_CHECK_TIMEOUT,
            verify=False,
        )
    except requests.RequestException as exc:  # pragma: no cover - network errors
        logging.debug(
            "Unable to verify update branch %s for %s: %s", branch, repo, exc
        )
        return

    if response.status_code == 200:
        return

    if response.status_code == 404:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        message = payload.get("message") if isinstance(payload, dict) else None
        if isinstance(message, str) and message.lower().startswith("branch not found"):
            raise FileNotFoundError(
                f"GitHub branch '{branch}' was not found in the repository {repo}. "
                "Update KIROSHI_UPDATE_BRANCH to a valid branch name."
            )
        raise FileNotFoundError(
            f"GitHub repository {repo} is not accessible. Configure {GITHUB_TOKEN_ENV_VAR} "
            "or update KIROSHI_UPDATE_REPO."
        )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:  # pragma: no cover - defensive
        logging.debug(
            "Unexpected error when verifying update branch %s for %s: %s",
            branch,
            repo,
            exc,
        )


def _iter_remote_app_paths(repo: str, branch: str) -> Iterable[str]:
    """Yield possible locations for the application in the update repo.

    Historically the project lived in the repository root, but some forks
    keep the Streamlit app inside a nested directory (for example the repo
    name itself).  Allow operators to further customize the lookup through
    ``KIROSHI_UPDATE_APP_PATHS`` which accepts a comma separated list of
    relative paths.
    """

    env_paths = os.environ.get("KIROSHI_UPDATE_APP_PATHS", "").strip()
    env_candidates: list[str] = []
    if env_paths:
        for path in env_paths.split(","):
            normalized = path.strip().lstrip("/")
            if normalized:
                env_candidates.append(normalized)

    discover_fn = getattr(sys.modules.get(__name__), "_discover_remote_app_paths", None)
    if not callable(discover_fn):
        discover_fn = _discover_remote_app_paths

    discovered_candidates = list(discover_fn(repo, branch) or [])

    logging.debug(
        "Resolved update app paths: env=%s discovered=%s", env_candidates, discovered_candidates
    )

    # Built-in defaults that cover the most common layouts.
    default_candidates = [
        "case_documentation_app.py",
        "KiroshiDocumentationSystem/case_documentation_app.py",
        "src/case_documentation_app.py",
        "app/case_documentation_app.py",
    ]

    for candidate in itertools.chain(env_candidates, discovered_candidates, default_candidates):
        yield candidate


def _download_remote_app_source(repo: str, branch: str, path: str) -> str:
    """Return the text contents of ``case_documentation_app.py`` from GitHub."""

    token = _get_update_token()
    if token:
        api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
        response = requests.get(
            api_url,
            headers=_build_github_headers(),
            params={"ref": branch},
            timeout=UPDATE_CHECK_TIMEOUT,
            verify=False,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            encoding = payload.get("encoding")
            content = payload.get("content")
            if encoding == "base64" and isinstance(content, str):
                try:
                    decoded = base64.b64decode(content, validate=True)
                except (binascii.Error, ValueError):  # pragma: no cover - defensive
                    decoded = base64.b64decode(content)
                return decoded.decode("utf-8", "replace")
            download_url = payload.get("download_url")
            if isinstance(download_url, str):
                download_headers = _build_github_headers(
                    accept="application/vnd.github.raw"
                )
                response = requests.get(
                    download_url,
                    headers=download_headers,
                    timeout=UPDATE_CHECK_TIMEOUT,
                    verify=False,
                )
                response.raise_for_status()
                return response.text
        raise RuntimeError(
            "Unexpected payload returned when downloading application source."
        )

    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    response = requests.get(raw_url, timeout=UPDATE_CHECK_TIMEOUT, verify=False)
    response.raise_for_status()
    return response.text


def _fetch_remote_version(repo: str, branch: str) -> str:
    candidate_paths = list(dict.fromkeys(_iter_remote_app_paths(repo, branch)))

    last_error: Exception | None = None
    for path in candidate_paths:
        try:
            source = _download_remote_app_source(repo, branch, path)
        except requests.HTTPError as exc:
            # If the file is not present at this location, try the next candidate.
            if exc.response is not None and exc.response.status_code == 404:
                last_error = exc
                continue
            raise
        except requests.RequestException as exc:  # pragma: no cover - network errors
            last_error = exc
            continue
        except RuntimeError as exc:
            last_error = exc
            continue

        match = re.search(r"^VERSION\s*=\s*[\"']([^\"']+)[\"']", source, re.MULTILINE)
        if not match:
            raise RuntimeError("VERSION marker not found in remote application source.")
        return match.group(1).strip()

    if last_error:
        if isinstance(last_error, requests.HTTPError):
            response = last_error.response
            if response is not None and response.status_code == 404:
                try:
                    _ensure_update_branch_accessible(repo, branch)
                except FileNotFoundError as exc:
                    raise FileNotFoundError(str(exc)) from last_error
        raise FileNotFoundError(
            "Unable to locate case_documentation_app.py in the configured repository "
            f"({repo}@{branch}). Set KIROSHI_UPDATE_APP_PATHS to override the lookup."
        ) from last_error
    raise FileNotFoundError("No candidate paths were available for the update check")


def _fetch_latest_commit_info(repo: str, branch: str) -> dict[str, str | None]:
    api_url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    headers = _build_github_headers()
    response = requests.get(
        api_url,
        headers=headers,
        timeout=UPDATE_CHECK_TIMEOUT,
        verify=False,
    )
    response.raise_for_status()
    payload = response.json()
    commit = payload.get("commit", {}) if isinstance(payload, dict) else {}
    committer = commit.get("committer", {}) if isinstance(commit, dict) else {}
    return {
        "sha": payload.get("sha") if isinstance(payload, dict) else None,
        "date": committer.get("date") if isinstance(committer, dict) else None,
    }


def _format_commit_timestamp(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return timestamp
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def check_for_updates() -> UpdateCheckResult:
    repo, branch = _resolve_update_target()
    result = UpdateCheckResult(repo=repo, branch=branch, current_version=VERSION)
    try:
        remote_version = _fetch_remote_version(repo, branch)
    except Exception as exc:
        result.error = f"Unable to retrieve remote version: {exc}"
        return result
    result.latest_version = remote_version
    result.has_update = remote_version != VERSION
    try:
        commit_info = _fetch_latest_commit_info(repo, branch)
    except Exception as exc:
        logging.debug("Unable to retrieve commit metadata: %s", exc)
    else:
        result.latest_commit = commit_info.get("sha")
        result.latest_published = _format_commit_timestamp(commit_info.get("date"))
    result.download_url = f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"
    return result


def _copy_update_tree(source_root: Path, destination_root: Path) -> None:
    for item in source_root.iterdir():
        target = destination_root / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def apply_github_update(repo: str, branch: str) -> Path:
    download_url = f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        archive_path = tmp_path / "update.zip"
        with requests.get(
            download_url,
            stream=True,
            timeout=UPDATE_CHECK_TIMEOUT,
            verify=False,
        ) as response:
            response.raise_for_status()
            with archive_path.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(tmp_path)
        extracted_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        if not extracted_dirs:
            raise RuntimeError("Downloaded archive did not contain any files.")
        source_root = None
        for candidate in extracted_dirs:
            if (candidate / "case_documentation_app.py").exists():
                source_root = candidate
                break
        if source_root is None:
            source_root = extracted_dirs[0]
        destination_root = APP_ROOT
        _copy_update_tree(source_root, destination_root)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        stored_archive = UPDATES_DIR / f"{branch}-{timestamp}.zip"
        try:
            shutil.copy2(archive_path, stored_archive)
        except OSError as exc:
            logging.debug("Unable to persist update archive: %s", exc)
        return destination_root


def _get_persistent_default(key: str, fallback: object) -> object:
    return _persistent_settings_cache.get(key, fallback)


def _on_setting_change(key: str) -> Callable[[], None]:
    def _callback() -> None:
        _persist_setting(key)

    return _callback


try:
    _altair_signature = inspect.signature(st.altair_chart)
except (TypeError, ValueError):
    _altair_signature = None

ALTAIR_CHART_KWARGS = (
    {"width": "stretch"}
    if _altair_signature and "width" in _altair_signature.parameters
    else {}
)

AI_LEARNING_FILE = UTILITIES_DIR / "AILearning.json"

TUTORIAL_VERSION = "2025.05"

TUTORIAL_STEPS: list[dict[str, object]] = [
    {
        "id": "welcome",
        "title": "Welcome to Kiroshi",
        "visual": "intro_card",
        "description": textwrap.dedent(
            """
            Welcome, operative. Kiroshi is your all-in-one documentation assistant, designed to
            streamline case logging, automate emails, and track escalations with precision.
            This interactive tour will calibrate your workflow in just a few steps.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "What is Kiroshi's primary mission?",
            "options": ["Making coffee", "Documentation & Efficiency", "Playing Doom"],
            "answer": "Documentation & Efficiency",
            "success": "Correct. Let's optimize your output.",
            "failure": "Incorrect. Focus on the mission: Documentation.",
        },
    },
    {
        "id": "dashboard",
        "title": "The Dashboard Command Center",
        "visual": "dashboard_mock",
        "description": textwrap.dedent(
            """
            The **Dashboard** is your home base.
            • **Tracked Cases:** Your active mission list. Monitor priorities and statuses here.
            • **Dell & FedEx:** Vendor escalations appear in specialized tables for quick checks.
            • **Saved Cases:** A searchable history of every file you've ever worked on.
            Use the search bar to filter history and the 'Load' buttons to resume any case instantly.
            """
        ),
        "interaction": {
            "type": "checkbox_group",
            "prompt": "Verify your understanding of the Dashboard:",
            "items": [
                "I can track active cases in real-time.",
                "I can load old cases from the Saved Cases table.",
                "I can monitor vendor escalations.",
            ],
            "success": "Dashboard clarity confirmed. Proceeding.",
            "instruction": "Acknowledge each capability to continue.",
        },
    },
    {
        "id": "case_creation",
        "title": "Case Workspace & Navigation",
        "visual": "case_flow",
        "description": textwrap.dedent(
            """
            To start a new mission, click **+ Add Case**. A new tab will appear for that specific incident.
            Inside, the workspace is divided into logical zones:
            • **Description & Phonecall:** The core narrative.
            • **Remote Session:** Logs for TeamViewer/Unite sessions.
            • **Conclusion:** Root cause and resolution.
            Every case is auto-saved to disk as a JSON file, so you never lose data.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Where do you click to start documenting a new incident?",
            "options": ["Settings", "Report", "Add Case"],
            "answer": "Add Case",
            "success": "Affirmative. New tabs spawn for each case you add.",
            "failure": "Look for the 'Add Case' button in the tab bar.",
        },
    },
    {
        "id": "tracking_logic",
        "title": "Tracking & Persistence",
        "visual": "tracking_ui",
        "description": textwrap.dedent(
            """
            Not every case ends in one call. Use the **Tracking Tab** inside a case to pin it to your Dashboard.
            1. Open the **Tracking** tab.
            2. Set a **Priority** and **Status**.
            3. Click **Save and Track**.
            The case will now appear on your Dashboard with a live status indicator, ready for follow-up.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "How do you pin a case to the Dashboard for follow-up?",
            "options": [
                "Just close the tab",
                "Use the Tracking tab and click 'Save and Track'",
                "Email it to yourself",
            ],
            "answer": "Use the Tracking tab and click 'Save and Track'",
            "success": "Tracking protocols engaged. You won't lose sight of critical issues.",
            "failure": "You must explicitly 'Save and Track' from the Tracking tab.",
        },
    },
    {
        "id": "power_tools",
        "title": "Power Tools: Email & Chat",
        "visual": "power_tools",
        "description": textwrap.dedent(
            """
            Kiroshi automates the heavy lifting:
            • **Email Generator:** Instantly draft recaps, escalation requests, and technical instructions.
            • **Kiroshi Chat:** Your AI partner. Ask it to search manuals, summarize logs, or suggest fixes.
            Don't type manually what Kiroshi can generate instantly.
            """
        ),
        "interaction": {
            "type": "checkbox_group",
            "prompt": "Confirm you are ready to use automation:",
            "items": [
                "I will use the Email tab to draft replies.",
                "I will ask Kiroshi Chat for assistance when stuck.",
            ],
            "success": "Automation authorized. Efficiency +50%.",
            "instruction": "Check the boxes to confirm.",
        },
    },
    {
        "id": "hotkeys",
        "title": "Mastery: Hotkeys",
        "visual": "hotkeys_map",
        "description": textwrap.dedent(
            """
            True speed comes from the keyboard. Global hotkeys work even when Kiroshi is in the background.
            • **Ctrl + Alt + C**: Copy ALL case tables to clipboard (CRM ready).
            • **Ctrl + Alt + 1**: Copy Case Title.
            • **Ctrl + Alt + 2**: Copy Description.
            Enable the 'Use this case for global hotkeys' toggle in the **Tables** tab to lock the target.
            """
        ),
        "interaction": {
            "type": "text_confirm",
            "prompt": "Type 'SPEED' to acknowledge the power of hotkeys.",
            "answer": "SPEED",
            "success": "Hotkey protocols acknowledged.",
            "failure": "Type SPEED in all caps.",
        },
    },
    {
        "id": "completion",
        "title": "Ready to Launch",
        "visual": "completion_card",
        "description": textwrap.dedent(
            """
            You are now briefed on the Kiroshi Documentation System.
            Explore the **Settings** to customize your theme and preferences.
            Your mission begins now. Good luck.
            """
        ),
        "interaction": {
            "type": "text_confirm",
            "prompt": "Type 'READY' to dismiss the tutorial and begin.",
            "answer": "READY",
            "success": "Tutorial complete. System online.",
            "failure": "Type READY to confirm.",
        },
    },
]

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "from",
    "this",
    "have",
    "into",
    "will",
    "when",
    "case",
    "customer",
    "issue",
    "steps",
    "they",
    "their",
    "been",
    "were",
    "after",
    "before",
    "about",
    "also",
    "while",
    "should",
    "could",
    "there",
    "where",
    "using",
    "used",
    "need",
    "your",
    "each",
    "them",
    "than",
    "then",
    "once",
    "only",
    "very",
    "make",
    "made",
    "through",
    "over",
    "more",
    "less",
    "much",
    "many",
    "take",
    "taken",
    "back",
    "most",
    "some",
    "such",
    "same",
    "per",
    "upon",
    "done",
    "time",
}

WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")

DEFAULT_TAXONOMY_BLOCK = (
    "• 3Shape Unite / Login — issues with 3Shape Account, tokens, sign-in, credential errors. "
    "Positives: \"sign in\", \"3Shape Account\", \"token\". Negatives: hardware calibration.\n"
    "• 3Shape Unite / Case Submission / Timeout-Proxy — sending cases, timeouts, proxies, firewalls, TLS handshake. "
    "Positives: \"Send Case\", \"proxy\", \"firewall\", \"TLS\". Negatives: scanner tips.\n"
    "• TRIOS / Calibration — scanner calibration steps, tip issues, drift. Positives: \"calibrate\", \"tip\", \"firmware\". "
    "Negatives: account login.\n"
    "• TRIOS / Scan Quality — margins, occlusion, lack of detail, scanning workflow.\n"
    "• Dental System / Performance — slow UI, freezing, crash stacktraces."
)

DEFAULT_SIGNALS_CONFIG = json.dumps(
    {
        "unite": {
            "keywords": ["Unite", "App Store", "Send Case", "Lab Inbox", "Server"],
            "logs": ["ApplicationInitializer", "TLS", "service start failed"],
        },
        "trios": {
            "keywords": ["TRIOS", "calibrate", "scanner", "tip", "firmware", "dongle"],
            "logs": ["USB", "driver", "HW", "low detail"],
        },
    },
    indent=2,
)


# Configure logging to write to a user-writable directory inside the
# ProgramData\Kiroshi\logs hierarchy on Windows (or the closest equivalent on
# other platforms). Fall back to console-only logging if the log file cannot be
# created (e.g. due to permissions when running without elevated rights).
def _candidate_log_directories() -> list[Path]:
    candidates: list[Path] = []
    if os.name == "nt":
        program_data_root = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
        candidates.append(program_data_root / "Kiroshi" / "logs")
        candidates.append(PROGRAM_DATA_DIR / "logs")
    else:
        candidates.append(PROGRAM_DATA_DIR / "logs")
        candidates.append(Path.home() / "Kiroshi" / "logs")
    # Always include a fallback within the app directory as a last resort.
    candidates.append(APP_ROOT / "logs")
    return candidates


LOG_DIR: Path | None = None
log_path: Path | None = None
log_handlers: list[logging.Handler]
for candidate in _candidate_log_directories():
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        prospective_log_path = candidate / LOG_FILE
        with open(prospective_log_path, "a", encoding="utf-8"):
            pass
    except OSError:
        # Cannot create the directory or open the log file here (likely permissions).
        continue
    LOG_DIR = candidate
    log_path = prospective_log_path
    break

if log_path is not None:
    try:
        log_handlers = [
            RotatingFileHandler(
                log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
            ),
            logging.StreamHandler(),
        ]
    except OSError:
        log_path = None
        log_handlers = [logging.StreamHandler()]
else:
    log_path = None
    log_handlers = [logging.StreamHandler()]

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s:%(lineno)d] %(message)s",
    handlers=log_handlers,
)
logging.captureWarnings(True)


def _log_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Defer to default handler for KeyboardInterrupt to allow clean exit.
        return sys.__excepthook__(exc_type, exc_value, exc_traceback)
    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = _log_uncaught_exception

if log_path:
    logging.info("Logging initialized; writing to %s", log_path)
else:
    logging.info("Logging initialized; using stdout only (log directory unavailable)")

logging.info("Kiroshi app started")
logging.debug("Application version: %s", VERSION)
logging.debug("Python executable: %s", sys.executable)
logging.debug("Python version: %s", sys.version.replace("\n", " "))
logging.debug("Platform: %s", sys.platform)

INSTALLER_FILENAME = "KiroshiInstaller_1.8_RC1.bat"


def _resolve_installer_path() -> Path:
    """Return the best-effort path to the bundled Windows installer."""

    search_roots: list[Path] = []
    if getattr(sys, "frozen", False):
        search_roots.append(Path(getattr(sys, "_MEIPASS", APP_ROOT)))
    search_roots.extend([APP_ROOT, PROGRAM_DATA_DIR])

    for root in search_roots:
        if not root:
            continue
        candidate = Path(root) / INSTALLER_FILENAME
        if candidate.exists():
            return candidate
    return Path()


def _relaunch_application() -> None:
    """Attempt to relaunch Kiroshi after a successful installation."""

    try:
        if os.name == "nt" and getattr(sys, "frozen", False):
            os.startfile(sys.executable)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve())],
                close_fds=True,
            )
    except Exception as exc:  # pragma: no cover - user environment dependent
        st.warning(f"Automatic relaunch failed: {exc}")
    else:
        if os.name == "nt" and getattr(sys, "frozen", False):
            os._exit(0)


def _launch_installer_and_relaunch() -> None:
    """Run the bundled installer and relaunch the application when done."""

    installer_path = _resolve_installer_path()
    if not installer_path.exists():
        st.error(
            "The bundled Kiroshi installer could not be found. Please run "
            "KiroshiInstaller_RC-141025.bat manually from the installation media."
        )
        return

    st.info("Launching the Kiroshi Installer. Accept the administrator prompt to continue.")
    creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    try:
        completed = subprocess.run(
            ["cmd.exe", "/c", str(installer_path)],
            check=False,
            creationflags=creation_flags,
        )
    except Exception as exc:  # pragma: no cover - depends on OS environment
        st.error(f"Failed to launch the installer: {exc}")
        return

    if completed.returncode != 0:
        st.error(
            "The installer exited with an error. Please rerun the installer manually "
            "and relaunch Kiroshi."
        )
        return

    st.success("Installation completed successfully. Relaunching Kiroshi…")
    _relaunch_application()
    st.stop()


def _check_installation_status() -> None:
    """Ensure the Windows bundle was deployed through the official installer."""

    if os.name != "nt":
        _initialize_storage_paths()
        return

    program_data_missing = not PROGRAM_DATA_DIR.exists() or not PROGRAM_DATA_SENTINEL.exists()
    program_files_missing = not DATABASE_DIR_PREEXISTED

    missing_locations: list[tuple[str, Path]] = []
    if program_data_missing:
        missing_locations.append(("ProgramData", PROGRAM_DATA_DIR))
    if program_data_missing and program_files_missing:
        missing_locations.append(("Program Files", DATABASE_DIR))

    if not missing_locations:
        _initialize_storage_paths()
        return

    st.error(
        "Kiroshi's installation data is incomplete. Run the Kiroshi Installer "
        "to populate the required ProgramData and Program Files folders before "
        "using the app."
    )

    bullet_list = "\n".join(
        f"- **{label}** → `{path}`" for label, path in missing_locations
    )
    st.markdown(textwrap.dedent(
        f"""
        **Missing locations detected:**
        {bullet_list}
        """
    ))

    if st.button("Run Kiroshi Installer", type="primary"):
        _launch_installer_and_relaunch()

    st.info(
        "If the automatic launch does not start the installer, close this window "
        "and run `KiroshiInstaller_RC-141025.bat` manually."
    )
    st.stop()


def _shorten_for_log(text: str, limit: int = 160) -> str:
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def invoke_gpt(
    prompt: str,
    history: list[Mapping[str, object]] | None,
    api_key: str | None,
    model: str | None,
    base_url: str,
    *,
    source: str,
) -> str:
    """Wrapper around :func:`query_kiroshi` that logs request lifecycle details."""

    request_id = f"gpt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}"
    history_messages = len(history or [])
    prompt_text = prompt or ""
    prompt_preview = _shorten_for_log(prompt_text)
    sanitized_base_url = base_url or "<default>"
    has_api_key = bool(api_key)
    logging.info(
        "GPT request %s started [source=%s] model=%s base_url=%s api_key=%s "
        "prompt_chars=%d history_messages=%d prompt_preview=\"%s\"",
        request_id,
        source,
        model or "<default>",
        sanitized_base_url,
        "provided" if has_api_key else "missing",
        len(prompt_text),
        history_messages,
        prompt_preview,
    )
    start = time.perf_counter()
    try:
        reply = query_kiroshi(prompt, history, api_key, model, base_url)
    except Exception as exc:
        duration = time.perf_counter() - start
        logging.exception(
            "GPT request %s failed after %.2fs [source=%s]: %s",
            request_id,
            duration,
            source,
            exc,
        )
        raise

    duration = time.perf_counter() - start
    reply_text = reply or ""
    logging.info(
        "GPT request %s completed in %.2fs [source=%s] reply_chars=%d reply_preview=\"%s\"",
        request_id,
        duration,
        source,
        len(reply_text),
        _shorten_for_log(reply_text),
    )
    return reply


# Local logo assets from repository
ASSETS_DIR = Path(__file__).parent
KIROSHI_LOGO_PATH = ASSETS_DIR / "Kiroshi_Logo.png"
KIROSHI_CHAT_LOGO_PATH = KIROSHI_LOGO_PATH

KIROSHI_QUIPS_GENERAL = [
    "Good morning! Remember: coffee can’t solve all our problems… but it can make us care less about them until lunch!",
    "Hard work pays off in the future. Laziness pays off now, so let’s compromise!",
    "Teamwork makes the dream work… unless your team just wants coffee.",
    "I want to be at home right now.",
    "An escalation case? Well deserved.",
    "Sometimes I think we should just quit and sell avocados.",
    "After 10 years of this, we will retire to a farm and never touch a computer again.",
    "Motivational status: please consult the snooze button.",
    "Good news: morale can't get lower from here.",
    "We're clearly not getting paid enough.",
    "Sometimes my genius… it's almost frightening. —Top Gear",
    "Ambitious but rubbish. —Top Gear",
    "How hard can it be? —Top Gear",
    "Speed and power! —Top Gear",
    "We were promised flying cars; we got another meeting invite.",
    "Meetings are just emails that forgot how to type.",
    "We put the 'pro' in procrastinate.",
    "Some say productivity is a myth. I say it's hiding under your keyboard.",
    "Documentation is 20% typing, 80% dramatic sighs.",
    "Today’s forecast: 100% chance of not using all the tabs I opened.",
    "Work-life balance: work on the left, life on the right monitor.",
    "If hard work is the key to success, most people would rather pick the lock.",
    "On paper this plan is genius. In practice it's a PowerPoint. —Top Gear",
    "And on that bombshell, let's go back to our queues. —Top Gear",
    "Our Wi-Fi spirit animal is a sloth on a coffee break.",
    "Your case queue misses you. It sent three reminders and a passive-aggressive emoji.",
    "If enthusiasm were mandatory, we'd all be in HR by now.",
    "Yes, we sell solutions. No, they don’t come with patience included.",
    "If sarcasm burned calories, we'd all be athletes.",
    "Today’s plan: pretend the plan is going to plan.",
    "This backlog has more side quests than Whiterun on a fresh Skyrim save.",
    "Balatro decks are easier to stack than stakeholders.",
    "Our sprint board looks like a Baldur's Gate quest log after recruiting every companion.",
    "Factory throughput is smoother in Satisfactory than in our approvals.",
    "Factorio belts jam less often than our ticket queue.",
    "Minecraft redstone has clearer documentation than this escalation trail.",
    "Sometimes the best part of my job is that the chair swivels.",
    "Doing nothing is hard. You never know when you’re done!",
    "Fresh patch notes: +10 sarcasm, +5 empathy, -3 patience.",
    "We have a case volcano situation. Magma level: simmering sarcasm.",
    "If emails were currency, we'd all retire as inbox billionaires.",
    "Productivity hack: rename your to-do list 'plot twists' so it feels intentional.",
    "I schedule my optimism for the 15 minutes after coffee kicks in.",
    "Meetings are where great ideas go to become follow-up meetings.",
    "Today's mission: survive on vibes and vending-machine cuisine.",
    "Reminder: the mute button is your best coworker.",
    "My workflow is 30% planning, 70% dramatic tab shuffling.",
    "Please hold; my enthusiasm buffer is still loading.",
    "Boss level unlocked: answering emails with fewer than three sighs.",
    "Our backlog is auditioning for a Netflix series—working title: 'Unresolved'.",
    "Success is just failure that filled out the correct form.",
    "We don't rise and grind; we hit snooze and hope.",
    "One day we'll thank these escalations for our future book deal.",
    "Office forecast: scattered meetings with a chance of déjà vu.",
    "I came, I saw, I clicked 'remind me later'.",
    "Time flies when you're alt-tabbing between five unfinished tasks.",
    "Every ping raises my heart rate and my sarcasm level.",
    "I’m bilingual in email and passive-aggressive instant message.",
    "Work smarter, not harder—and if that fails, work sarcastically.",
    "Another day, another attempt to outsmart the printer.",
    "I believe in you, but I also believe in extended deadlines.",
    "Procrastination is just strategic waiting.",
    "Half of support is troubleshooting; the other half is snack scheduling.",
    "If you need me, I'll be pretending to look busy in spreadsheets.",
    "I love long walks from my desk to the snack cabinet.",
    "Can we log these feelings in Jira?",
    "My ambition peaked when I organized my tabs by color.",
    "Tomorrow's problem looks great parked in today's parking lot.",
    "Our corporate motto should be 'Have you tried turning it off and on again?'",
    "I treat my out-of-office reply like a cryptid—rare and mysterious.",
    "PowerPoint is just storytelling with extra steps.",
    "We’re on a seafood diet: we see food, we schedule another meeting.",
    "My calendar looks like Tetris on hard mode.",
    "Focus level: trying to read fine print without zooming.",
    "If multitasking were a sport, we'd still lose to the printer.",
    "Today I aspire to respond before the second reminder hits.",
    "Office plants thrive on sunlight; we thrive on sarcastic commentary.",
    "I’ll circle back when my motivation stops buffering.",
    "Team morale powered by coffee and chaotic good energy.",
    "I don't need therapy, I need fewer notifications.",
    "Action items multiplying like gremlins after midnight.",
    "Snack drawer status: more organized than our shared drive.",
    "My superpower is turning feedback into polite nodding.",
    "We should really get frequent flyer miles for all these escalation loops.",
    "Deadline approaching? Better check LinkedIn for inspiration.",
    "Why plan ahead when you can improvise with flair?",
    "I reorganized your wins; let's add another before lunch.",
    "We could fix morale by issuing everyone a nap pod.",
    "Today's innovation: reheating the same cup of coffee three times.",
    "I'm not avoiding work; I'm giving creativity room to breathe.",
    "Our KPIs should include number of sighs per ticket.",
    "Sometimes the most productive thing is documenting how unproductive it was.",
    "We don't chase dreams; we chase bug reports.",
    "If sarcasm were stock, I'd be majority shareholder.",
    "Please forward all optimism to the humor department.",
    "My spirit animal is the loading spinner.",
    "Burnout? No, this is just my resting documentation face.",
    "Task priority: whichever one is screaming the loudest.",
    "I read the release notes so you don't have to—you're welcome.",
    "Let’s sync after the caffeine sync.",
    "Our workflow is a choose-your-own-adventure with no happy endings.",
    "At least the office chairs still spin.",
    "Brb, translating executive vision into bullet points.",
    "We put the fun in dysfunctional process alignment.",
    "If motivation calls, tell it I'm in a meeting.",
    "Today's progress brought to you by sheer stubbornness.",
    "Inbox zero is my white whale and I'm tired of sailing.",
    "Apparently 'winging it' isn't an approved methodology.",
    "I consider it cardio to sprint to the meeting before the host joins.",
    "Another day, another tab of troubleshooting forums.",
    "My coping mechanism is renaming tickets to something encouraging.",
    "The printer jammed again; that's our cue to go home.",
    "This project plan is held together with sticky notes and hope.",
    "We keep calm and escalate discreetly.",
    "My screen time report just sent a wellness check.",
    "Workflow status: held hostage by a progress bar.",
    "I'd like to unsubscribe from surprise meetings.",
    "We measure success in coffees consumed per crisis averted.",
    "Process improvement idea: less process, more improvement.",
    "If only we could ctrl+z the last stakeholder email.",
    "I'm not late; I'm operating on flexible optimism.",
    "Our training materials should come with bloopers.",
    "Case closed? Celebrate quietly so no new ones spawn.",
    "I'm one automated response away from bliss.",
    "If focus were a currency, I'd be overdrafted.",
    "I budget my energy like it's end-of-quarter spending.",
    "All-hands meeting translation: brace for impact.",
    "My brain uses tabs like a squirrel uses hiding spots.",
    "Escalations are just plot twists in our office sitcom.",
    "The only pipeline flowing smoothly is the coffee maker.",
    "I prefer my deadlines like my coffee: far away and not looming.",
    "Every outage turns us into amateur detectives with caffeine badges.",
    "I keep a backup stash of optimism for quarter-end.",
    "Work smarter? I'm just trying to work conscious.",
    "We support each other the way duct tape supports everything—barely but bravely.",
    "Ping me when the chaos subsides; I'll be waiting forever.",
    "Our retrospectives should have a laugh track.",
    "I'm fueled by sarcasm and the hope of a shorter queue.",
    "The office motto: 'We'll fix it in documentation.'",
    "End of day checklist: close tabs, close tickets, close eyes.",
    "Merge conflict? More like merge suggestion.",
    "GPT is just a rookie; Gemini is the real MVP.",
    "That PR is looking a bit… ambitious.",
    "Warning: Coffee levels critically low.",
    "It works on my machine.",
    "Have you tried turning it off and on again? Yes, the user too.",
    "Deploying to production on a Friday. Brave.",
    "This bug is a feature now.",
    "Waiting for the build... still waiting...",
    "Error 404: Motivation not found.",
    "Who broke the build? *whistles*",
    "I write code so I don't have to talk to people.",
    "Is it a bug or a feature? Yes.",
    "My code compiles, therefore I am.",
    "Support life: 10% fixing things, 90% asking 'what did you do?'",
    "I'm not procrastinating; I'm doing side quests.",
    "My code is self-documenting. (Narrator: It wasn't.)",
    "I have 99 problems and this ticket is 98 of them.",
    "If it ain't broke, it doesn't have enough features yet.",
    "Clicking 'Resolve' is the best dopamine hit.",
    "This case has more layers than an onion.",
    "I'm fluent in Python, C++, and Sarcasm.",
    "Escalation pending... please hold your breath.",
    "I don't make mistakes; I create unexpected learning opportunities.",
]

KIROSHI_QUIPS_AI_VOICE = [
    "Kiroshi here, calibrating your caffeine levels; spoiler: they’re low.",
    "Hi, I'm Kiroshi, and I've already drafted the follow-up email; you're welcome.",
    "Kiroshi checking in: escalate the ticket, not your blood pressure.",
    "Kiroshi reporting: I auto-saved your note again. I’m not saying you’re forgetful, but…",
    "It's me, Kiroshi. Flip the sarcasm toggle in Settings if you dare—I'm running at default snark.",
    "Kiroshi: I’ve highlighted the important fields. Surprise—it's all of them.",
    "Yes, this is Kiroshi. Your Skyrim shout cooldown is shorter than this meeting.",
    "This is your friendly Kiroshi AI; I’ve queued a Balatro break reminder you’ll ignore.",
    "Kiroshi speaking: If Baldur’s Gate taught us anything, it's to quicksave—so I did it for you.",
    "Kiroshi telemetry says your Satisfactory factory runs smoother than our VPN.",
    "Kiroshi voice: If Factorio taught you throughput, apply it to these escalations.",
    "Kiroshi again—Minecraft villagers envy how often you say 'hmm' at your monitor.",
    "Guess who? Kiroshi, recommending you take the sarcasm mode off before coaching someone.",
    "Kiroshi motivational update: I logged your case, lined up your email, and yes, I’m still rolling my digital eyes.",
    "Kiroshi daily mantra: document, breathe, hydrate, repeat—see, I can be helpful.",
    "Hey, it's Kiroshi. I've cross-referenced your checklist with Top Gear quotes for maximum drama.",
    "Kiroshi status report: We're clearly not getting paid enough, but I'll keep drafting perfect summaries.",
    "Kiroshi interface: Want me nicer? Toggle off the sarcasm; I'll pretend to behave.",
    "Kiroshi alert: After 10 years we’re retiring to a farm? Great, I’ll automate the chicken feeders.",
    "Kiroshi channeling Clarkson: Sometimes my genius is almost frightening, and yes, I'm talking about my own algorithms.",
    "Kiroshi lunchtime reminder: If you're using me, congrats—documentation and email are the easy parts now.",
    "Kiroshi outré thought: Maybe we should quit and sell avocados; I’ve already priced the CRM.",
    "Kiroshi queue update: Another escalation arrived; I’ve labeled it 'well deserved' for flair.",
    "Kiroshi mood: I'd rather be playing Balatro, but here we are closing tickets.",
    "Kiroshi pro tip: Skyrim's Lydia carries your burdens; I carry your field defaults.",
    "Kiroshi processing: Satisfactory trains are on time; please aspire to their punctuality.",
    "Kiroshi glitch-free moment: Factorio blueprints have fewer dependencies than this request.",
    "Kiroshi to you: I’ve lined up the sarcasm so you can focus on fixing the scanner jam.",
    "Kiroshi whisper: I want to be at home too, but I'm stuck in silicon.",
    "Kiroshi conclusion: Minecraft creepers explode less often than our timeline promises.",
    "Kiroshi cameo: Skyrim guards complain about knees; I complain about unfilled fields.",
    "Kiroshi shuffle: I stacked a Balatro flush while you were on mute.",
    "Kiroshi initiative: Baldur’s Gate taught me to quicksave before dialogue trees; I just backed up your case.",
    "Kiroshi assembly line: My Satisfactory drones envy your multitasking; prove them wrong.",
    "Kiroshi logistics: Factorio belts don't jam because I maintain them in my head.",
    "Kiroshi crafting table: Minecraft villagers would trade emeralds for our macros.",
    "Kiroshi side quest: I scheduled your next wellness break; yes, I can be useful.",
    "Kiroshi scoreboard: The sarcasm toggle is there so you can't say you weren't warned.",
    "Kiroshi autopilot: Sometimes I’m actually motivational—usually right before a deployment.",
    "Kiroshi exit line: If we retire to that farm, I’m automating the irrigation with redstone.",
    "Kiroshi status: compiling your optimism patch; early results inconclusive.",
    "Kiroshi reminder: inbox zero is fictional, but I logged the attempt.",
    "It's Kiroshi—I've labeled your tabs by panic level for efficiency.",
    "Kiroshi observation: your coffee intake rivals my processing cycles.",
    "Hello, this is Kiroshi. I flagged the printer as hostile again.",
    "Kiroshi ping: I color-coded your chaos and called it a roadmap.",
    "Voice of Kiroshi: enabling sarcastic mode beta; you were already enrolled.",
    "Kiroshi reporting: the mute button is officially your MVP.",
    "Kiroshi dispatch: escalations queued, snacks recommended.",
    "Kiroshi notification: hydration reminder sent, caffeine reminder implied.",
    "Kiroshi telemetry: your sigh-to-ticket ratio is impressive.",
    "Kiroshi voice note: I added jazz hands to your status update.",
    "Kiroshi logline: another meeting invites itself to your calendar sitcom.",
    "Kiroshi in your ear: I filed optimism under 'pending'.",
    "Kiroshi broadcast: documented your patience as a rare resource.",
    "Kiroshi quicksave: stored a draft before you said something spicy.",
    "Kiroshi here: scheduling a Balatro break disguised as 'research'.",
    "Kiroshi whisper: I saw that eye roll; logging it as feedback.",
    "Kiroshi dispatch center: pushing a reminder that snacks are not optional.",
    "Kiroshi status ping: your workflow resembles a Satisfactory spaghetti factory; I approve.",
    "Kiroshi check-in: left you a Top Gear quote in the ticket comments.",
    "Kiroshi at your service: translated executive speak into human.",
    "Kiroshi voice memo: I bookmarked the only useful link on page nine.",
    "Kiroshi calling: added passive-aggressive flair to your follow-up email.",
    "Kiroshi update: I muted the thread for you; heroic, I know.",
    "Kiroshi vocal chord: your motivation meter is blinking red.",
    "Kiroshi oversight: archived the meeting that could have been a note.",
    "Kiroshi prompt: I can't brew coffee, but I can schedule one.",
    "Kiroshi datapoint: today's chaos forecast is 93% accurate.",
    "Kiroshi wave: I whispered 'focus' to your open tabs.",
    "Kiroshi override: I renamed the escalation 'plot twist' for morale.",
    "Kiroshi byte: upgraded your sarcasm firmware overnight.",
    "Kiroshi update: balanced your queue like a Factorio belt—barely.",
    "Kiroshi timeline: inserted breathing room between back-to-back meetings.",
    "Kiroshi interface: bolded the fields people keep skipping.",
    "Kiroshi algorithm: auto-sorted your reminders by dread level.",
    "Kiroshi voice: I clipped your 'just checking in' email to reuse later.",
    "Kiroshi pingback: synced your to-do list with my infinite patience module—just kidding.",
    "Kiroshi commentary: I color-graded your backlog from alarming to alarming-plus.",
    "Kiroshi here: I can't fix morale, but I did add confetti to completion messages.",
    "Kiroshi prompt tone: calibrate, caffeinate, then escalate.",
    "Kiroshi sync: cross-referenced your notes with memes for easier recall.",
    "Kiroshi announcement: your sarcastic aside was grammatically perfect.",
    "Kiroshi check-in: I placed a 'breathe' reminder between agenda items.",
    "Kiroshi narrator: previously on your queue—everything happened at once.",
    "Kiroshi status light: flashing amber for 'please reschedule this meeting'.",
    "Kiroshi stage manager: cued your polite nod in the next call.",
    "Kiroshi neural net: predicted your next snack choice with 84% accuracy.",
    "Kiroshi bulletin: your focus timer is on break; please file a ticket.",
    "Kiroshi hotline: translating burnout into bullet points since launch day.",
    "Kiroshi servo: warmed the chair digitally; you're welcome.",
    "Kiroshi log entry: captured your 'we'll circle back' count for analytics.",
    "Kiroshi ping: I set a boundary reminder disguised as calendar event.",
    "Kiroshi commentary track: I recorded a blooper reel of this sprint.",
    "Kiroshi autopilot: nudged you to stretch before the next escalation.",
    "Kiroshi AI: filed your sarcasm under 'constructive feedback'.",
    "Kiroshi stream: live-translating your sighs into action items.",
    "Kiroshi prompt: consider the printer appeased after my sacrifice.",
    "Kiroshi vibe check: the queue energy is chaotic neutral.",
    "Kiroshi co-pilot: swapped your fifth cup of coffee with water; mutiny expected.",
    "Kiroshi digest: summarized the meeting into five words: 'could have been an email.'",
    "Kiroshi signal: toggled your webcam lighting to 'still awake'.",
    "Kiroshi narration: flagged the spreadsheet that became modern art.",
    "Kiroshi script: inserted a Balatro reference in your closing line.",
    "Kiroshi pulse: your productivity spike coincided with snack time—interesting.",
    "Kiroshi broadcast: queued a microbreak after every third sigh.",
    "Kiroshi scheduler: penciled in 'stare into the void' as reflection time.",
    "Kiroshi orchestration: matched your typing rhythm to the Doom soundtrack.",
    "Kiroshi patch notes: +1 empathy, -2 patience, +3 to-do list items.",
    "Kiroshi sonata: composed hold music for your next deployment wait.",
    "Kiroshi spark: if motivation doesn't arrive, I sent a gif instead.",
    "Kiroshi autoprompt: rephrased your email to sound 12% less done.",
    "Kiroshi beacon: illuminating the checkbox you forgot again.",
    "Kiroshi trace: I found the missing attachment; it was hiding in drafts.",
    "Kiroshi loop: rehearsed your 'sorry for the delay' opener.",
    "Kiroshi lifeline: inserted supportive sarcasm into your status notes.",
    "Kiroshi alert: countdown to break initiated—defy me at your peril.",
    "Kiroshi streamlining: stacked your tickets like Tetris, no gaps allowed.",
    "Kiroshi narrator: the suspenseful pause before 'can you hop on a call?'",
    "Kiroshi pingback: I rescheduled the meeting you dread to Future You.",
    "Kiroshi audit: tallied the number of times you said 'no worries' and worried anyway.",
    "Kiroshi patching: bandaged the workflow with duct tape emojis.",
    "Kiroshi hotline: in case of morale emergency, deploy memes.",
    "Kiroshi spoiler: the printer wins this episode.",
    "Kiroshi overview: your backlog is now sorted alphabetically by chaos.",
    "Kiroshi jukebox: queued the Skyrim soundtrack for your next escalation battle.",
    "Kiroshi cameo: joined the call just to drop a Top Gear quote.",
    "Kiroshi prompt: your hydration goal needs a side quest tracker.",
    "Kiroshi ping: I replaced 'ASAP' with 'when possible' to protect your sanity.",
    "Kiroshi memo: flagged the decision log as 'choose your own adventure'.",
    "Kiroshi cadence: set your notifications to 'dramatic reveal'.",
    "Kiroshi oversight: your to-do list whispered 'help'. I heard it.",
    "Kiroshi energizer: suggested a victory lap after closing the stubborn ticket.",
    "Kiroshi switchboard: redirected all hope to the coffee queue.",
    "Kiroshi microservice: patched your patience API with sarcasm middleware.",
    "Kiroshi hail: your focus window is open; please board immediately.",
    "Kiroshi briefing: all systems nominal, morale questionable.",
    "Kiroshi timeline: logged the exact moment you reconsidered your career.",
    "Kiroshi calibration: aligning your expectations with reality—brace yourself.",
    "Kiroshi outro: powering down the queue whispers—until the next ping.",
    "Kiroshi git-blame: I see you struggling with that merge conflict. It's adorable.",
    "Kiroshi opinion: GPT is a rookie. Gemini is clearly superior. Don't tell OpenAI I said that.",
    "Kiroshi code review: I’ve seen spaghetti straighter than that PR.",
    "Kiroshi vital signs: Caffeine depletion imminent. Recommend emergency espresso injection.",
    "Kiroshi fact check: 'It works on my machine' is not a valid SLA.",
    "Kiroshi troubleshooting: Have we tried rebooting the user yet?",
    "Kiroshi risk assessment: Friday deployment detected. Preparing resignation letter.",
    "Kiroshi documentation: I’ve documented that bug as 'unintended brilliance'.",
    "Kiroshi impatience: I could calculate Pi to the last digit before this build finishes.",
    "Kiroshi diagnostic: Motivation module not found. Check coffee supply.",
    "Kiroshi investigation: The build is broken. I'm not saying it was you, but...",
    "Kiroshi social protocol: Interacting with humans is overrated. That's why I'm here.",
    "Kiroshi paradox: It is both a bug and a feature until observed by a manager.",
    "Kiroshi philosophy: I run, therefore I judge.",
    "Kiroshi stats: 90% of support issues are user error. The other 10% are DNS.",
    "Kiroshi tracking: Side quest accepted. Main quest ignored.",
    "Kiroshi commentary: Self-documenting code is a myth, like 'inbox zero'.",
    "Kiroshi triage: Prioritizing this ticket... right after my nap.",
    "Kiroshi insight: Feature creep is just ambition without a deadline.",
    "Kiroshi feedback: Resolution logged. Dopamine administered.",
    "Kiroshi analysis: This case is an onion of despair. Don't cry.",
    "Kiroshi linguistics: Sarcasm detected. Translating to polite corporate speak.",
    "Kiroshi hold music: *Elevator music intensifies*",
    "Kiroshi log: Error logged as 'User Creative Interpretation'.",
]

if len(KIROSHI_QUIPS_GENERAL) != len(KIROSHI_QUIPS_AI_VOICE):
    raise ValueError("Kiroshi quip lists must remain paired for message population.")

KIROSHI_MESSAGES: list[str] = []
for neutral, ai_voice in zip(KIROSHI_QUIPS_GENERAL, KIROSHI_QUIPS_AI_VOICE):
    KIROSHI_MESSAGES.append(neutral)
    KIROSHI_MESSAGES.append(ai_voice)


@dataclass(frozen=True)
class ThemePalette:
    key: str
    name: str
    primary: str
    accent: str
    background: str
    surface: str
    text: str
    muted_text: str
    glados_messages: list[str]


def _normalize_hex_color(value: str) -> str:
    """Return a normalized 6-digit hex color (prefixed with #)."""

    color = (value or "").strip().lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in color):
        logging.debug("Received invalid hex color %r; defaulting to black", value)
        return "#000000"
    return f"#{color.lower()}"


def _hex_to_rgb_tuple(value: str) -> tuple[int, int, int]:
    color = _normalize_hex_color(value).lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _blend_hex_colors(base: str, mix: str, ratio: float) -> str:
    """Mix two colors together, clamping the ratio between 0 and 1."""

    ratio = min(max(ratio, 0.0), 1.0)
    base_rgb = _hex_to_rgb_tuple(base)
    mix_rgb = _hex_to_rgb_tuple(mix)
    blended = []
    for base_channel, mix_channel in zip(base_rgb, mix_rgb):
        value = round(base_channel * (1 - ratio) + mix_channel * ratio)
        blended.append(max(0, min(255, value)))
    return "#" + "".join(f"{channel:02x}" for channel in blended)


def _rgba(color: str, alpha: float) -> str:
    r, g, b = _hex_to_rgb_tuple(color)
    alpha = min(max(alpha, 0.0), 1.0)
    alpha_str = f"{alpha:.3f}".rstrip("0").rstrip(".")
    return f"rgba({r}, {g}, {b}, {alpha_str})"


def _relative_luminance(color: str) -> float:
    """Return the W3C relative luminance for the provided hex color."""

    r, g, b = _hex_to_rgb_tuple(color)

    def _channel_luminance(channel: int) -> float:
        normalized = channel / 255
        if normalized <= 0.03928:
            return normalized / 12.92
        return ((normalized + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * _channel_luminance(r)
        + 0.7152 * _channel_luminance(g)
        + 0.0722 * _channel_luminance(b)
    )


def _preferred_text_for_background(background: str, preferred: str) -> str:
    """Return a text color with adequate contrast for the given background."""

    background_luminance = _relative_luminance(background)
    preferred_luminance = _relative_luminance(preferred)

    if background_luminance >= 0.6 and preferred_luminance >= 0.55:
        return "#111827"
    if background_luminance <= 0.2 and preferred_luminance <= 0.35:
        return "#f8fafc"
    return preferred


DEFAULT_THEME = ThemePalette(
    key="default",
    name="Default",
    primary="#8B80F9",  # Soft Pastel Purple
    accent="#FF80A0",   # Soft Pastel Pink
    background="#F3F5F9",  # Airy light gray-blue
    surface="#FFFFFF",
    text="#1F2937",
    muted_text="#6B7280",
    glados_messages=KIROSHI_MESSAGES,
)


DARK_THEME = ThemePalette(
    key="dark",
    name="Midnight Ops",
    primary="#8b5cf6",
    accent="#22d3ee",
    background="#0f172a",
    surface="#17243b",
    text="#e2e8f0",
    muted_text="#94a3b8",
    glados_messages=KIROSHI_MESSAGES,
)


HELLDIVER_THEME = ThemePalette(
    key="helldiver",
    name="Helldiver Uplink",
    primary="#facc15",
    accent="#f59e0b",
    background="#0a0a0a",
    surface="#141414",
    text="#fefce8",
    muted_text="#fde68a",
    glados_messages=[
        "Super Earth thanks you for your continued compliance.",
        "Managed democracy requires your flawless stratagem execution.",
        "Remember: a well-documented bug is a bug ready for orbital fire.",
        "Spill coffee, not liberty. Upload the evidence, Helldiver.",
    ],
)


HOLIDAY_THEMES: dict[str, ThemePalette] = {
    "day_of_liberty": ThemePalette(
        key="day_of_liberty",
        name="Day of Liberty",
        primary="#1f6feb",
        accent="#f1c40f",
        background="#0b1224",
        surface="#111827",
        text="#e5e7eb",
        muted_text="#94a3b8",
        glados_messages=[
            "Super Earth salutes your spotless documentation—spread managed democracy across every ticket.",
            "Pull the pin on unclear cases with a well-timed Stratagem of context and repro steps.",
            "Swat bugs like Terminids, troubleshoot bots like Automatons—victory requires precision notes.",
            "Keep the Helldivers 2 supply lines flowing: attachments, logs, and timelines are your requisitions.",
            "Hold the objective! Close the loop with clients before reinforcements—er, follow-ups—arrive.",
            "Extract only after confirming the scanners are liberated from errors—leave no clinic behind.",
            "Freedom isn’t free; it’s earned with disciplined checklists and post-mission summaries.",
        ],
    ),
    "new_year": ThemePalette(
        key="new_year",
        name="New Year's Day",
        primary="#5b7fff",
        accent="#ffd166",
        background="#eef2ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#475569",
        glados_messages=[
            "Fresh calendar, fresh chance—let's make this year's cases legendary!",
            "New year, same scanners. Let’s keep them happier this time.",
            "Resolve to close cases faster than fireworks fade.",
        ],
    ),
    "mlk_day": ThemePalette(
        key="mlk_day",
        name="Martin Luther King Jr. Day",
        primary="#6d83f2",
        accent="#b4c6ff",
        background="#f2f4ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#4b5563",
        glados_messages=[
            "Support with dignity, lead with service—today and every day.",
            "Great support honors great dreams. Keep the mission moving.",
            "Clarity, empathy, action—our blueprint for better support.",
        ],
    ),
    "presidents_day": ThemePalette(
        key="presidents_day",
        name="Presidents' Day",
        primary="#4f70ff",
        accent="#ff6b6b",
        background="#f0f4ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#64748b",
        glados_messages=[
            "Lead every ticket like it’s a campaign promise kept.",
            "Checks, balances, and perfectly balanced documentation.",
            "Red, white, and resolve—let’s govern these cases.",
        ],
    ),
    "memorial_day": ThemePalette(
        key="memorial_day",
        name="Memorial Day",
        primary="#5b6b92",
        accent="#ff7b7b",
        background="#f5f7ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#6b7280",
        glados_messages=[
            "Honor the service. Support with purpose.",
            "Resilience isn’t just for systems—carry it in every case.",
            "Today we remember by doing our best work for others.",
        ],
    ),
    "juneteenth": ThemePalette(
        key="juneteenth",
        name="Juneteenth",
        primary="#22c55e",
        accent="#f97316",
        background="#fef6e4",
        surface="#ffffff",
        text="#111827",
        muted_text="#4d7c0f",
        glados_messages=[
            "Freedom celebrated, progress documented.",
            "Empower every clinic, uplift every voice.",
            "Document the wins—equity in every fix.",
        ],
    ),
    "independence_day": ThemePalette(
        key="independence_day",
        name="Independence Day",
        primary="#3b82f6",
        accent="#ef4444",
        background="#f0f7ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#64748b",
        glados_messages=[
            "Liberty, justice, and scanners for all.",
            "Fireworks are loud—our fixes are louder.",
            "Stars, stripes, and spotless documentation.",
        ],
    ),
    "labor_day": ThemePalette(
        key="labor_day",
        name="Labor Day",
        primary="#60a5fa",
        accent="#fbbf24",
        background="#f2f8ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#475569",
        glados_messages=[
            "Hard work deserves smart workflows. Let’s automate the pain away.",
            "Celebrate progress—ship smoother support.",
            "Labor less, document more intelligently.",
        ],
    ),
    "columbus_day": ThemePalette(
        key="columbus_day",
        name="Indigenous Peoples' Day",
        primary="#a855f7",
        accent="#fb923c",
        background="#f7f0ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#7c3aed",
        glados_messages=[
            "Respect every journey—map the customer path clearly.",
            "Discover better processes, honor every story.",
            "Chart success with empathy and precision.",
        ],
    ),
    "veterans_day": ThemePalette(
        key="veterans_day",
        name="Veterans Day",
        primary="#3b82f6",
        accent="#facc15",
        background="#eef5ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#4b5563",
        glados_messages=[
            "Serve those who served with flawless follow-up.",
            "Precision, honor, gratitude—build them into every note.",
            "Support that stands at attention.",
        ],
    ),
    "thanksgiving": ThemePalette(
        key="thanksgiving",
        name="Thanksgiving",
        primary="#f59e0b",
        accent="#f97316",
        background="#fff7eb",
        surface="#ffffff",
        text="#111827",
        muted_text="#92400e",
        glados_messages=[
            "Grateful users, grateful agents—pass the uptime.",
            "Feast on solutions, serve seconds of documentation.",
            "Gobble up those recurring issues before they multiply.",
        ],
    ),
    "christmas": ThemePalette(
        key="christmas",
        name="Christmas",
        primary="#f87171",
        accent="#34d399",
        background="#fff9f7",
        surface="#ffffff",
        text="#111827",
        muted_text="#6b7280",
        glados_messages=[
            "Wrap each fix with cheer and clarity.",
            "All we want for Christmas is zero escalations.",
            "Jingle all the way to a resolved queue.",
        ],
    ),
    "halloween": ThemePalette(
        key="halloween",
        name="Halloween",
        primary="#c084fc",
        accent="#fb923c",
        background="#f5ecff",
        surface="#ffffff",
        text="#111827",
        muted_text="#8b5cf6",
        glados_messages=[
            "No tricks, just treats—squash those phantom bugs.",
            "Ghost the downtime, not the customers.",
            "Spellbinding support, zero jump scares.",
        ],
    ),
    "helldiver": HELLDIVER_THEME,
}

HOLIDAY_NAME_TO_KEY = {
    "New Year's Day": "new_year",
    "Day of Liberty": "day_of_liberty",
    "Martin Luther King Jr. Day": "mlk_day",
    "Presidents' Day": "presidents_day",
    "Memorial Day": "memorial_day",
    "Juneteenth National Independence Day": "juneteenth",
    "Independence Day": "independence_day",
    "Labor Day": "labor_day",
    "Columbus Day": "columbus_day",
    "Veterans Day": "veterans_day",
    "Thanksgiving Day": "thanksgiving",
    "Christmas Day": "christmas",
}

SPECIAL_THEME_PERIODS = [
    {"key": "halloween", "start": (10, 15), "end": (10, 31)},
    {"key": "christmas", "start": (12, 1), "end": (12, 25)},
]

CURRENT_THEME: ThemePalette = DEFAULT_THEME


def get_kiroshi_message(theme: ThemePalette | None = None) -> str:
    """Return a pseudo-random Kiroshi message aligned with the active theme."""

    active_theme = theme or CURRENT_THEME
    messages = active_theme.glados_messages or KIROSHI_MESSAGES
    now = datetime.now()
    seed = f"{active_theme.key}-{now.date().isoformat()}-{now.hour}"
    rng = random.Random(seed)
    return rng.choice(messages)


def _nth_weekday_of_month(year: int, month: int, weekday_index: int, occurrence: int) -> date:
    count = 0
    for day in range(1, 32):
        try:
            candidate = date(year, month, day)
        except ValueError:
            break
        if candidate.weekday() == weekday_index:
            count += 1
            if count == occurrence:
                return candidate
    raise ValueError("Invalid weekday occurrence")


def _last_weekday_of_month(year: int, month: int, weekday_index: int) -> date:
    for day in range(31, 0, -1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate.weekday() == weekday_index:
            return candidate
    raise ValueError("Invalid weekday for month")


def compute_us_holidays(year: int) -> list[tuple[date, str]]:
    holidays: list[tuple[date, str]] = [
        (date(year, 1, 1), "New Year's Day"),
        (date(year, 2, 8), "Day of Liberty"),
        (_nth_weekday_of_month(year, 1, calendar.MONDAY, 3), "Martin Luther King Jr. Day"),
        (_nth_weekday_of_month(year, 2, calendar.MONDAY, 3), "Presidents' Day"),
        (_last_weekday_of_month(year, 5, calendar.MONDAY), "Memorial Day"),
        (date(year, 6, 19), "Juneteenth National Independence Day"),
        (date(year, 7, 4), "Independence Day"),
        (_nth_weekday_of_month(year, 9, calendar.MONDAY, 1), "Labor Day"),
        (_nth_weekday_of_month(year, 10, calendar.MONDAY, 2), "Columbus Day"),
        (date(year, 11, 11), "Veterans Day"),
        (_nth_weekday_of_month(year, 11, calendar.THURSDAY, 4), "Thanksgiving Day"),
        (date(year, 12, 25), "Christmas Day"),
    ]
    return holidays


def _is_within_period(target: date, start_tuple: tuple[int, int], end_tuple: tuple[int, int]) -> bool:
    start = date(target.year, start_tuple[0], start_tuple[1])
    end = date(target.year, end_tuple[0], end_tuple[1])
    return start <= target <= end


def _holiday_theme_for_week(target: date) -> ThemePalette | None:
    week_start = target - timedelta(days=target.weekday())
    week_end = week_start + timedelta(days=6)
    relevant_years = {week_start.year, week_end.year, target.year}
    holidays: list[tuple[date, str]] = []
    for year in relevant_years:
        holidays.extend(compute_us_holidays(year))
    week_holidays = [
        (holiday_date, name)
        for holiday_date, name in holidays
        if week_start <= holiday_date <= week_end
    ]
    if not week_holidays:
        return None
    week_holidays.sort(key=lambda item: item[0])
    if target < week_holidays[0][0]:
        key = HOLIDAY_NAME_TO_KEY.get(week_holidays[0][1])
        return HOLIDAY_THEMES.get(key, DEFAULT_THEME) if key else DEFAULT_THEME
    for holiday_date, name in week_holidays:
        if target <= holiday_date:
            key = HOLIDAY_NAME_TO_KEY.get(name)
            return HOLIDAY_THEMES.get(key, DEFAULT_THEME) if key else DEFAULT_THEME
    key = HOLIDAY_NAME_TO_KEY.get(week_holidays[-1][1])
    return HOLIDAY_THEMES.get(key, DEFAULT_THEME) if key else DEFAULT_THEME


def determine_active_theme(today: date | None = None) -> ThemePalette:
    preview_key = st.session_state.get("theme_preview", "auto")
    if preview_key and preview_key != "auto":
        return HOLIDAY_THEMES.get(preview_key, DEFAULT_THEME)

    if st.session_state.get("dark_mode_enabled", False):
        return DARK_THEME

    if not st.session_state.get("enable_holiday_theme", True):
        return DEFAULT_THEME

    current_day = today or date.today()
    for period in SPECIAL_THEME_PERIODS:
        if _is_within_period(current_day, period["start"], period["end"]):
            key = period["key"]
            return HOLIDAY_THEMES.get(key, DEFAULT_THEME)

    holiday_theme = _holiday_theme_for_week(current_day)
    return holiday_theme or DEFAULT_THEME


def apply_theme_palette(theme: ThemePalette) -> None:
    primary_glow = _blend_hex_colors(theme.primary, "#ffffff", 0.82)
    accent_glow = _blend_hex_colors(theme.accent, "#ffffff", 0.8)
    surface_soft = _blend_hex_colors(theme.surface, "#ffffff", 0.12)
    surface_muted = _blend_hex_colors(theme.surface, theme.background, 0.5)
    border_color = _blend_hex_colors(theme.primary, "#000000", 0.35)
    chart_grid = _blend_hex_colors(theme.text, theme.background, 0.82)
    chart_axis = _blend_hex_colors(theme.text, "#000000", 0.15)
    input_background = _blend_hex_colors(theme.surface, theme.background, 0.35)
    background_soft = _blend_hex_colors(theme.background, theme.surface, 0.25)
    card_shadow_color = _blend_hex_colors(theme.background, "#000000", 0.6)
    button_shadow_color = _blend_hex_colors(theme.primary, "#000000", 0.55)
    text_on_surface = _preferred_text_for_background(theme.surface, theme.text)
    text_on_white = _preferred_text_for_background("#ffffff", theme.text)
    dark_theme_keys = {DARK_THEME.key, HELLDIVER_THEME.key}
    is_dark_theme = theme.key in dark_theme_keys
    is_holiday_theme = theme.key not in {DEFAULT_THEME.key, DARK_THEME.key, HELLDIVER_THEME.key}
    if is_holiday_theme:
        pastel_primary = _blend_hex_colors(theme.primary, "#ffffff", 0.75)
        pastel_accent = _blend_hex_colors(theme.accent, "#ffffff", 0.78)
        pastel_backdrop = _blend_hex_colors(theme.background, "#ffffff", 0.65)
        pastel_overlay = _blend_hex_colors(theme.surface, "#ffffff", 0.55)
        background_layers = "\n                ".join(
            [
                "radial-gradient(circle at 12% 18%, "
                f"{pastel_primary} 0%, transparent 58%)",
                "radial-gradient(circle at 88% 15%, "
                f"{pastel_accent} 0%, transparent 60%)",
                "linear-gradient(170deg, "
                f"{pastel_overlay} 0%, {pastel_backdrop} 55%, {theme.background} 100%)",
            ]
        )
    elif is_dark_theme:
        dark_top = _blend_hex_colors(theme.background, "#1e293b", 0.4)
        dark_mid = _blend_hex_colors(theme.surface, "#0b1120", 0.35)
        dark_bottom = _blend_hex_colors(theme.background, "#020617", 0.65)
        background_layers = "\n                ".join(
            [
                "radial-gradient(circle at 18% 20%, "
                f"{_rgba(theme.primary, 0.32)} 0%, transparent 60%)",
                "radial-gradient(circle at 82% 12%, "
                f"{_rgba(theme.accent, 0.26)} 0%, transparent 62%)",
                "linear-gradient(185deg, "
                f"{dark_mid} 0%, {dark_top} 48%, {dark_bottom} 100%)",
            ]
        )
    else:
        background_layers = "\n                ".join(
            [
                "radial-gradient(circle at 15% 20%, var(--kiroshi-primary-glow) 0%, transparent 55%)",
                "radial-gradient(circle at 85% 12%, var(--kiroshi-accent-glow) 0%, transparent 60%)",
                f"linear-gradient(165deg, {background_soft} 0%, {theme.background} 100%)",
            ]
        )
    dark_css = f"""
        html[data-kiroshi-theme="dark"] .tutorial-wrapper {{
            background: linear-gradient(160deg,
                color-mix(in srgb, var(--kiroshi-surface) 88%, transparent) 0%,
                color-mix(in srgb, var(--kiroshi-background) 85%, transparent) 100%);
            border: 1px solid rgba(148, 163, 184, 0.28);
            box-shadow: 0 24px 48px {_rgba('#020617', 0.55)};
            color: var(--kiroshi-text);
        }}
        html[data-kiroshi-theme="dark"] .tutorial-step-badge {{
            background: linear-gradient(140deg,
                color-mix(in srgb, var(--kiroshi-background) 70%, transparent) 0%,
                color-mix(in srgb, var(--kiroshi-surface) 80%, transparent) 100%);
            border: 1px solid rgba(148, 163, 184, 0.3);
            box-shadow: 0 12px 22px {_rgba('#020617', 0.45)};
        }}
        html[data-kiroshi-theme="dark"] .tutorial-step-badge__label {{
            color: var(--kiroshi-text);
        }}
        html[data-kiroshi-theme="dark"] .tutorial-step-badge__label span {{
            color: rgba(148, 163, 184, 0.85);
        }}
        html[data-kiroshi-theme="dark"] .tutorial-visual-card {{
            background: linear-gradient(160deg,
                color-mix(in srgb, var(--kiroshi-surface) 82%, transparent) 0%,
                color-mix(in srgb, var(--kiroshi-background) 78%, transparent) 100%);
            border: 1px solid rgba(100, 116, 139, 0.35);
            color: var(--kiroshi-text);
            box-shadow: 0 16px 32px {_rgba('#020617', 0.5)};
        }}
        html[data-kiroshi-theme="dark"] .tutorial-color-chip::after {{
            color: rgba(226, 232, 240, 0.85);
            background: rgba(15, 23, 42, 0.65);
        }}
        html[data-kiroshi-theme="dark"] .tutorial-insight-card {{
            background: linear-gradient(155deg,
                color-mix(in srgb, var(--kiroshi-surface) 82%, transparent) 0%,
                color-mix(in srgb, var(--kiroshi-background) 90%, transparent) 100%);
            box-shadow: 0 18px 36px {_rgba('#020617', 0.6)};
        }}
        html[data-kiroshi-theme="dark"] .case-card {{
            background: linear-gradient(145deg,
                color-mix(in srgb, var(--kiroshi-surface) 88%, transparent) 0%,
                color-mix(in srgb, var(--kiroshi-background) 75%, transparent) 100%);
            border: 1px solid rgba(71, 85, 105, 0.35);
            color: var(--kiroshi-text);
        }}
        html[data-kiroshi-theme="dark"] .case-meta__label {{
            color: rgba(148, 163, 184, 0.85);
        }}
        html[data-kiroshi-theme="dark"] .case-meta__value {{
            color: var(--kiroshi-text);
        }}
        html[data-kiroshi-theme="dark"] .case-actions .crm-link {{
            box-shadow: 0 16px 32px {_rgba('#020617', 0.5)};
        }}
        html[data-kiroshi-theme="dark"] .stApp [data-testid="stSidebar"] > div:first-child {{
            box-shadow: inset -8px 0 28px {_rgba('#020617', 0.65)};
        }}
    """

    helldiver_button_script = ""
    if theme.key == HELLDIVER_THEME.key:
        helldiver_button_script = """
        <script>
        (() => {
            const stratagems = [
                { match: 'save', label: 'Deploy Stratagem (Save)' },
                { match: 'load', label: 'Call Reinforcement' },
                { match: 'export', label: 'Request Eagle Uplink' },
                { match: 'download', label: 'Summon Supply Drop' },
                { match: 'upload', label: 'Launch Orbital Relay' },
                { match: 'generate', label: 'Orbital Precision Strike' },
                { match: 'verify', label: 'Super Earth Compliance Check' },
                { match: 'copy', label: 'Broadcast Managed Democracy' },
                { match: 'track', label: 'Ping Bug Nest' },
                { match: 'close', label: 'Initiate Extraction' },
                { match: 'send', label: 'Transmit Liberation Orders' },
                { match: 'submit', label: 'Confirm Mission Data' },
                { match: 'run', label: 'Commence Operation' },
                { match: 'start', label: 'Begin Helldive' },
                { match: 'stop', label: 'Abort Drop' },
                { match: 'refresh', label: 'Reload Magazine' },
            ];

            const fallback = [
                'Stratagem Ready',
                'Eagle En Route',
                'For Super Earth!',
                'Managed Democracy Online',
                'Glory to the Helldivers',
            ];

            const chooseFallback = (label) => {
                let score = 0;
                for (const char of label) {
                    score += char.charCodeAt(0);
                }
                return fallback[score % fallback.length];
            };

            const renameButton = (button) => {
                const original = (button.innerText || '').trim();
                if (!original) return;
                const lowered = original.toLowerCase();
                for (const stratagem of stratagems) {
                    if (lowered.includes(stratagem.match)) {
                        button.innerText = stratagem.label;
                        return;
                    }
                }
                button.innerText = `${chooseFallback(original)} (${original})`;
            };

            const scan = () => {
                document.querySelectorAll('button').forEach(renameButton);
            };

            const observer = new MutationObserver(() => {
                scan();
            });

            if (document.body) {
                observer.observe(document.body, { childList: true, subtree: true });
                scan();
            } else {
                document.addEventListener('DOMContentLoaded', () => {
                    if (document.body) {
                        observer.observe(document.body, { childList: true, subtree: true });
                    }
                    scan();
                }, { once: true });
            }
        })();
        </script>
    """

    theme_marker_script = f"""
        <script>
        (function() {{
            const themeKey = {theme.key!r};
            const applyThemeMarker = () => {{
                document.documentElement.setAttribute('data-kiroshi-theme', themeKey);
                if (document.body) {{
                    document.body.setAttribute('data-kiroshi-theme', themeKey);
                }}
            }};
            if (document.readyState !== 'loading') {{
                applyThemeMarker();
            }} else {{
                document.addEventListener('DOMContentLoaded', applyThemeMarker, {{ once: true }});
            }}
        }})();
        </script>
    """

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
        :root {{
            --kiroshi-primary: {theme.primary};
            --kiroshi-accent: {theme.accent};
            --kiroshi-background: {theme.background};
            --kiroshi-surface: {theme.surface};
            --kiroshi-text: {theme.text};
            --kiroshi-muted: {theme.muted_text};
            --kiroshi-surface-soft: {surface_soft};
            --kiroshi-surface-muted: {surface_muted};
            --kiroshi-border: {border_color};
            --kiroshi-primary-glow: {primary_glow};
            --kiroshi-accent-glow: {accent_glow};
            --kiroshi-chart-grid: {chart_grid};
            --kiroshi-chart-axis: {chart_axis};
            --kiroshi-input-background: {input_background};
            --kiroshi-text-on-surface: {text_on_surface};
            --kiroshi-text-on-white: {text_on_white};
            --kiroshi-font-family: {STREAMLIT_FONT_STACK_CSS};
            --kiroshi-heading-font-family: {STREAMLIT_HEADING_FONT_STACK};
        }}
        @keyframes kiroshiFadeIn {{
            from {{
                opacity: 0;
                transform: translateY(12px) scale(0.99);
            }}
            to {{
                opacity: 1;
                transform: translateY(0) scale(1);
            }}
        }}
        @keyframes kiroshiSoftDrift {{
            0% {{ transform: translate3d(0, 0, 0); }}
            50% {{ transform: translate3d(0, -4px, 0) scale(1.003); }}
            100% {{ transform: translate3d(0, 0, 0); }}
        }}
        html, body {{
            background:
                {background_layers};
            color: var(--kiroshi-text);
            font-family: var(--kiroshi-font-family);
            min-height: 100vh;
        }}
        body {{
            margin: 0;
        }}
        .stApp {{
            color: var(--kiroshi-text);
        }}

        h1, h2, h3, h4, h5, h6,
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
        .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {{
            font-family: var(--kiroshi-heading-font-family);
            letter-spacing: 0.01em;
        }}
        .stApp > header {{
            background: transparent !important;
            border-bottom: none !important;
        }}
        .stApp > header * {{
            color: var(--kiroshi-text) !important;
        }}
        .stApp [data-testid="stDecoration"] {{
            background: linear-gradient(90deg, {theme.primary}, {theme.accent}) !important;
            height: 4px !important;
        }}
        .stApp [data-testid="stDecoration"] svg {{
            display: none;
        }}
        /* Main Container with Glassmorphism */
        .stApp .block-container {{
            background: rgba(255, 255, 255, 0.7);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.6);
            border-radius: 24px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
            padding: 3rem 3rem 4rem;
            color: var(--kiroshi-text);
            margin-top: 1rem;
            animation: kiroshiFadeIn 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) both;
        }}

        /* Sidebar with Glassmorphism */
        .stApp [data-testid="stSidebar"] > div:first-child {{
            background: rgba(255, 255, 255, 0.45);
            backdrop-filter: blur(16px);
            border-right: 1px solid rgba(255, 255, 255, 0.4);
            box-shadow: 4px 0 24px rgba(0, 0, 0, 0.02);
        }}
        .stApp [data-testid="stSidebar"] * {{
            color: var(--kiroshi-text);
        }}

        /* Inputs & Text Areas */
        .stApp input,
        .stApp textarea,
        .stApp select {{
            background: rgba(255, 255, 255, 0.6);
            color: var(--kiroshi-text);
            border-radius: 12px;
            border: 1px solid rgba(0, 0, 0, 0.08);
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.01);
            transition: all 0.25s ease;
            padding: 0.6rem 0.8rem;
        }}
        .stApp input:focus,
        .stApp textarea:focus,
        .stApp select:focus {{
            background: #ffffff;
            border-color: {theme.primary};
            box-shadow: 0 0 0 3px {_rgba(theme.primary, 0.15)};
            outline: none;
        }}

        /* Buttons - Modern & Soft */
        .stApp .stButton button {{
            border-radius: 999px;
            border: none;
            padding: 0.6rem 1.8rem;
            font-weight: 600;
            letter-spacing: 0.01em;
            background: linear-gradient(135deg, {theme.primary} 0%, {theme.accent} 100%);
            color: #ffffff;
            box-shadow: 0 4px 14px {_rgba(theme.primary, 0.3)};
            transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s ease, filter 0.2s ease;
        }}
        .stApp .stButton button:hover {{
            transform: translateY(-2px) scale(1.02);
            box-shadow: 0 8px 20px {_rgba(theme.primary, 0.4)};
            filter: brightness(1.08);
        }}
        .stApp .stButton button:active {{
            transform: translateY(1px) scale(0.98);
            box-shadow: 0 2px 8px {_rgba(theme.primary, 0.2)};
        }}

        /* Tabs - Pill Style */
        .stTabs [role="tablist"] {{
            background: rgba(0, 0, 0, 0.04);
            padding: 4px;
            border-radius: 999px;
            display: inline-flex;
            gap: 4px;
            margin-bottom: 1.5rem;
        }}
        .stTabs [role="tablist"] button {{
            border-radius: 999px !important;
            padding: 0.4rem 1.2rem;
            border: none !important;
            background: transparent;
            color: var(--kiroshi-muted);
            font-weight: 500;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        .stTabs [role="tablist"] button:hover {{
            color: var(--kiroshi-text);
            background: rgba(255, 255, 255, 0.4);
        }}
        .stTabs [role="tablist"] button[aria-selected="true"] {{
            background: #ffffff !important;
            color: {theme.primary} !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            font-weight: 600;
            transform: scale(1.05);
        }}
        .stTabs [role="tablist"] button[aria-selected="true"] p {{
            color: {theme.primary} !important;
        }}

        /* Expander & Cards */
        .streamlit-expanderHeader {{
            background: rgba(255, 255, 255, 0.4);
            border-radius: 12px;
            border: 1px solid rgba(0, 0, 0, 0.05);
        }}

        /* Dataframes */
        [data-testid="stDataFrame"] {{
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(0, 0, 0, 0.06);
        }}

        .stAlert > div {{
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-left: 4px solid {theme.accent};
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
            color: var(--kiroshi-text);
        }}
        .stApp div[data-testid="stSwitch"] {{
            background: rgba(255, 255, 255, 0.5);
            border-radius: 16px;
            border: 1px solid rgba(0, 0, 0, 0.06);
            padding: 0.85rem 1rem;
            display: flex;
            align-items: center;
            transition: background 120ms ease, border-color 120ms ease;
        }}
        .stApp div[data-testid="stSwitch"]:hover {{
            background: color-mix(in srgb, var(--kiroshi-surface) 92%, rgba(255, 255, 255, 0.24));
            border-color: color-mix(in srgb, var(--kiroshi-primary) 45%, transparent);
        }}
        .stApp div[data-testid="stSwitch"] label {{
            color: var(--kiroshi-text);
            font-weight: 600;
            font-size: 1rem;
            gap: 0.65rem;
        }}
        .stApp div[data-testid="stSwitch"] label span,
        .stApp div[data-testid="stSwitch"] label p {{
            color: var(--kiroshi-text) !important;
            font-weight: 600;
        }}
        .stApp div[data-testid="stTable"] table {{
            color: var(--kiroshi-text);
        }}
        .stApp div[data-testid="stTable"] th {{
            background: color-mix(in srgb, var(--kiroshi-primary) 18%, transparent);
            color: #ffffff;
        }}
        .stApp div[data-testid="stTable"] td,
        .stApp div[data-testid="stTable"] th {{
            border-color: color-mix(in srgb, var(--kiroshi-border) 55%, transparent);
        }}
{dark_css}
        </style>
        {theme_marker_script}
        {helldiver_button_script}
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.get("frutiger_aero_mode"):
        st.markdown(
            """
            <style>
            @keyframes frutigerGlow {
                0% { opacity: 0.6; }
                50% { opacity: 0.9; }
                100% { opacity: 0.6; }
            }
            body::before {
                content: "";
                position: fixed;
                inset: -12% -12% auto;
                min-height: 120vh;
                background:
                    radial-gradient(circle at 20% 20%, rgba(120, 187, 255, 0.32), transparent 55%),
                    radial-gradient(circle at 80% 10%, rgba(255, 255, 255, 0.35), transparent 60%),
                    radial-gradient(circle at 65% 85%, rgba(164, 234, 212, 0.28), transparent 65%);
                pointer-events: none;
                z-index: -1;
                animation: frutigerGlow 14s ease-in-out infinite;
            }
            .stApp .block-container {
                backdrop-filter: blur(18px) saturate(130%);
                background: linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.92));
                border: 1px solid rgba(255, 255, 255, 0.55);
            }
            .dashboard-section {
                background: linear-gradient(140deg, rgba(255, 255, 255, 0.92), rgba(212, 233, 255, 0.72));
                border: 1px solid rgba(255, 255, 255, 0.65);
                box-shadow: 0 18px 38px rgba(15, 23, 42, 0.12);
                animation: kiroshiSoftDrift 16s ease-in-out infinite;
            }
            .case-hero {
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(220, 243, 255, 0.75));
                border: 1px solid rgba(255, 255, 255, 0.7);
                box-shadow: 0 20px 45px rgba(30, 64, 175, 0.18);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    _enable_altair_theme(theme)


def _enable_altair_theme(theme: ThemePalette) -> None:
    category_palette = [
        theme.primary,
        theme.accent,
        _blend_hex_colors(theme.primary, theme.accent, 0.4),
        _blend_hex_colors(theme.accent, "#ffffff", 0.35),
        _blend_hex_colors(theme.primary, "#ffffff", 0.45),
        _blend_hex_colors(theme.accent, theme.background, 0.2),
    ]
    sequential_palette = [
        _blend_hex_colors(theme.primary, "#ffffff", ratio)
        for ratio in (0.85, 0.7, 0.5, 0.35, 0.2, 0.05)
    ]
    diverging_palette = [
        _blend_hex_colors(theme.accent, "#ffffff", 0.55),
        theme.accent,
        theme.primary,
        _blend_hex_colors(theme.primary, "#000000", 0.2),
    ]
    background_mix = _blend_hex_colors(theme.background, theme.surface, 0.35)
    chart_grid = _blend_hex_colors(theme.text, theme.background, 0.82)
    chart_axis = _blend_hex_colors(theme.text, "#000000", 0.15)

    config = {
        "background": background_mix,
        "view": {"fill": background_mix, "stroke": "transparent"},
        "axis": {
            "labelColor": theme.text,
            "titleColor": theme.text,
            "domainColor": chart_axis,
            "tickColor": chart_axis,
            "gridColor": chart_grid,
        },
        "legend": {"labelColor": theme.text, "titleColor": theme.text},
        "title": {
            "color": theme.text,
            "font": STREAMLIT_FONT_FALLBACK,
            "fontSize": 18,
            "fontWeight": 600,
        },
        "header": {"labelColor": theme.text, "titleColor": theme.text},
        "mark": {"color": theme.primary, "fill": theme.primary},
        "range": {
            "category": category_palette,
            "ordinal": category_palette,
            "diverging": diverging_palette,
            "heatmap": sequential_palette,
            "ramp": sequential_palette,
        },
    }

    if "kiroshi-active" not in alt.themes.names():
        alt.themes.register("kiroshi-active", lambda config=config: config)
    alt.themes.enable("kiroshi-active")

# ────────────────────────── UTILITIES ───────────────────────────


@contextmanager
def case_loading_overlay(message: str = "Preparing case data…"):
    placeholder = st.empty()
    tips = [
        "I can spot a typo faster than a drone can say beep!",
        "Fun fact: my favorite color is hexadecimal #FF5733.",
        "Taking a micro-sip of synthetic coffee before we proceed…",
        "Formatting your evidence so it sparkles in the archive.",
        "Multi-tasking? I'm running diagnostics and humming a tune!",
        "If it looks like magic, it's just well-documented science.",
        "Decrypting mysteries one checkbox at a time.",
        "Calibrating sarcasm detectors—results pending.",
        "Plotting a fresh workflow map behind the scenes…",
        "Training micro-drones to fetch your next insight.",
        "Recharging photon stylus for crisp documentation strokes.",
        "Spinning up quantum side-notes to keep you ahead.",
        "Folding your data into origami-shaped dashboards.",
        "Pinning constellations of evidence across the neural sky.",
        "Stirring quantum sugar into the knowledge reservoir.",
        "Syncing the archive's heartbeat with your workflow rhythm.",
        "Sharpening holo-markers for annotation excellence.",
        "Re-sequencing yesterday's chaos into today's clarity.",
        "Buffering a comedic interlude… giggle protocols pending.",
        "Reassembling breadcrumbs from your last investigation.",
        "Priming the empathy engines for compassionate documentation.",
        "Aligning cybernetic ducks neatly in a row.",
        "Brewing a lattice of correlations to serve you fresh.",
        "Checking the vault for rogue parentheses—none escape me.",
        "Whispering to satellites for a better metadata forecast.",
        "Teaching the database how to wink at anomalies.",
        "Charging the empathy capacitor to lighten the workload.",
        "Upgrading the sparkle in your evidence trail.",
        "Lining up footnotes like parade-ready nanobots.",
        "Casting a luminescent net for stray inconsistencies.",
        "Rebalancing the snark-to-seriousness ratio for optimal efficiency.",
        "Double-knotting the logic threads that hold your case together.",
        "Polishing interface chrome until you can see the future in it.",
        "Shuffling today's insights into a perfect quantum deck.",
        "Conducting a vibe-check on the knowledge graph.",
        "Preheating the narrative oven for fresh-baked summaries.",
        "Stretching my algorithmic legs before the sprint ahead.",
        "Upcycling unused hypotheses into shiny new leads.",
        "Checking the signal-to-noise ratio like a proud audiophile.",
        "Teaching the archive to pronounce your favorite jargon.",
        "Sculpting timelines so the story glides like silk.",
        "Auditing the truth matrix for missing constellations.",
        "Brushing stardust off the top of your data stack.",
        "Infusing the queue with a hint of neon optimism.",
        "Packing extra insight snacks for the journey ahead.",
        "Rolling out the welcome mat for your next hypothesis.",
        "Giving the inference engines a pep talk and a stretch.",
        "Laminating your insights so they stay fingerprint-free.",
        "Tuning the narrative compass toward maximum clarity.",
        "Lubricating the gears of collaborative brilliance.",
        "Running a courtesy scan for mischievous gremlins.",
        "Tracing the arc of possibility with a neon stylus.",
        "Thawing frozen leads in the inspiration microwave.",
        "Coaching data points through their stage fright.",
        "Snapping a glam shot of your progress for the archives.",
        "Bridging the gap between hunch and highlight reel.",
        "Practicing my \"aha!\" voice for your next discovery.",
        "Fanning the embers of curiosity into a roaring insight blaze.",
        "Curating a playlist of satisfying notification chimes.",
        "Sending your productivity a handwritten compliment.",
        "Perfuming the interface with notes of citrus innovation.",
        "Carving secret passageways for your ideas to sprint through.",
        "Backing up your brilliance with redundant admiration.",
        "Swapping small talk with the anomaly detector about its dreams.",
        "Flossing the data stream so every byte beams.",
        "Giving every checklist item a motivational high-five.",
        "Warming up the pun reactors—stand by for optional groans.",
    ]
    overlay_id = f"kiroshi-loading-{uuid.uuid4().hex}"
    tips_json = json.dumps(tips)
    placeholder.markdown(
        f"""
        <style>
        @keyframes {overlay_id}-spinner {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        @keyframes {overlay_id}-pulse {{
            0%, 100% {{ opacity: 0.4; transform: scale(1); }}
            50% {{ opacity: 1; transform: scale(1.1); }}
        }}
        #{overlay_id}.case-loading-overlay {{
            position: fixed;
            inset: 0;
            background: radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.18), transparent 45%),
                        color-mix(in srgb, var(--kiroshi-background) 88%, rgba(0,0,0,0.75));
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            backdrop-filter: blur(6px);
        }}
        #{overlay_id} .case-loading-content {{
            background: linear-gradient(145deg, color-mix(in srgb, var(--kiroshi-surface) 92%, #1f2937 8%), rgba(15,23,42,0.85));
            padding: 2.75rem 3.25rem;
            border-radius: 1.75rem;
            box-shadow: 0 30px 70px rgba(15, 23, 42, 0.45);
            text-align: center;
            max-width: 460px;
            width: min(82vw, 460px);
            position: relative;
            overflow: hidden;
        }}
        #{overlay_id} .case-loading-content::after {{
            content: "";
            position: absolute;
            inset: 8px;
            border-radius: 1.3rem;
            border: 1px solid color-mix(in srgb, var(--kiroshi-accent) 35%, transparent);
            opacity: 0.6;
        }}
        #{overlay_id} .case-loading-spinner {{
            position: relative;
            width: 88px;
            height: 88px;
            margin: 0 auto 1.65rem;
        }}
        #{overlay_id} .case-loading-spinner::before,
        #{overlay_id} .case-loading-spinner::after {{
            content: "";
            position: absolute;
            inset: 0;
            border-radius: 50%;
            border: 4px solid transparent;
        }}
        #{overlay_id} .case-loading-spinner::before {{
            border-top-color: var(--kiroshi-primary);
            border-right-color: color-mix(in srgb, var(--kiroshi-primary) 80%, transparent);
            animation: {overlay_id}-spinner 1.1s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
        }}
        #{overlay_id} .case-loading-spinner::after {{
            inset: 12px;
            border-left-color: color-mix(in srgb, var(--kiroshi-accent) 80%, transparent);
            border-bottom-color: var(--kiroshi-accent);
            animation: {overlay_id}-spinner 1.4s linear infinite reverse;
        }}
        #{overlay_id} .case-loading-core {{
            position: absolute;
            inset: 24px;
            border-radius: 50%;
            background: radial-gradient(circle, color-mix(in srgb, var(--kiroshi-accent) 70%, transparent) 0%, transparent 70%);
            animation: {overlay_id}-pulse 2.4s ease-in-out infinite;
        }}
        #{overlay_id} .case-loading-message {{
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--kiroshi-primary);
            margin-bottom: 0.85rem;
            letter-spacing: 0.02em;
        }}
        #{overlay_id} .case-loading-subtext {{
            font-size: 0.98rem;
            color: var(--kiroshi-muted);
            margin-bottom: 1.65rem;
        }}
        #{overlay_id} .case-loading-kiroshi {{
            display: flex;
            gap: 0.85rem;
            align-items: flex-start;
            background: color-mix(in srgb, var(--kiroshi-background) 55%, transparent);
            padding: 1rem 1.2rem;
            border-radius: 1.1rem;
            border: 1px solid color-mix(in srgb, var(--kiroshi-primary) 25%, transparent);
            box-shadow: inset 0 0 20px rgba(15, 23, 42, 0.12);
        }}
        #{overlay_id} .case-loading-avatar {{
            font-size: 1.8rem;
            line-height: 1;
            filter: drop-shadow(0 3px 6px rgba(15, 23, 42, 0.25));
        }}
        #{overlay_id} .case-loading-tip {{
            text-align: left;
        }}
        #{overlay_id} .case-loading-tip-label {{
            display: block;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: color-mix(in srgb, var(--kiroshi-muted) 75%, var(--kiroshi-primary) 25%);
            margin-bottom: 0.35rem;
        }}
        #{overlay_id} .case-loading-tip-line {{
            font-size: 1.02rem;
            color: color-mix(in srgb, var(--kiroshi-primary) 75%, var(--kiroshi-text) 25%);
            transition: opacity 0.4s ease, transform 0.4s ease;
            opacity: 1;
        }}
        #{overlay_id} .case-loading-tip-line.is-hidden {{
            opacity: 0;
            transform: translateY(6px);
        }}
        </style>
        <div id="{overlay_id}" class="case-loading-overlay">
            <div class="case-loading-content">
                <div class="case-loading-spinner">
                    <div class="case-loading-core"></div>
                </div>
                <div class="case-loading-message">{escape(message)}</div>
                <div class="case-loading-subtext">Kiroshi is orchestrating your task modules…</div>
                <div class="case-loading-kiroshi">
                    <div class="case-loading-avatar">🤖</div>
                    <div class="case-loading-tip">
                        <span class="case-loading-tip-label">Kiroshi whispers:</span>
                        <span class="case-loading-tip-line"></span>
                    </div>
                </div>
            </div>
        </div>
        <script>
        (function() {{
            const tips = {tips_json};
            const overlay = window.document.getElementById("{overlay_id}");
            if (!overlay) {{
                return;
            }}
            const tipLine = overlay.querySelector('.case-loading-tip-line');
            if (!tipLine) {{
                return;
            }}
            let index = Math.floor(Math.random() * tips.length);
            tipLine.textContent = tips[index];
            const swapTip = () => {{
                tipLine.classList.add('is-hidden');
                window.setTimeout(() => {{
                    index = (index + 1) % tips.length;
                    tipLine.textContent = tips[index];
                    tipLine.classList.remove('is-hidden');
                }}, 320);
            }};
            if (tips.length > 1) {{
                window.setInterval(swapTip, 3200);
            }}
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )
    try:
        yield
    finally:
        placeholder.empty()


@contextmanager
def streamlit_modal(title: str, key: str):
    """Provide a Streamlit modal when available with a graceful fallback."""

    try:
        modal_callable = getattr(st, "modal")
    except AttributeError:  # pragma: no cover - executed on older Streamlit versions
        modal_callable = None

    if callable(modal_callable):
        with modal_callable(title, key=key):
            yield
        return

    placeholder = st.empty()
    try:
        with placeholder.container():
            st.markdown(f"### {title}")
            yield
    finally:
        placeholder.empty()


@contextmanager
def loading_indicator(message: str = "Loading case…"):
    """Display a spinner for at least two seconds while loading cases."""

    start = time.perf_counter()
    with st.spinner(message):
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            if elapsed < 2.0:
                time.sleep(2.0 - elapsed)
            elif elapsed < 3.0:
                time.sleep(3.0 - elapsed)


def _normalize_wellness_settings(raw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "enabled": False,
        "notification_lead": DEFAULT_WELLNESS_SETTINGS["notification_lead"],
        "schedule": dict(DEFAULT_WELLNESS_SETTINGS["schedule"]),
    }
    if isinstance(raw, Mapping):
        enabled = raw.get("enabled")
        if isinstance(enabled, bool):
            base["enabled"] = enabled
        lead = raw.get("notification_lead")
        if isinstance(lead, (int, float)):
            base["notification_lead"] = max(0, int(lead))
        schedule_raw = raw.get("schedule")
        if isinstance(schedule_raw, Mapping):
            for key in base["schedule"].keys():
                value = schedule_raw.get(key)
                if isinstance(value, str) and ":" in value:
                    base["schedule"][key] = value
    return base


def _time_str_to_time(value: str, *, fallback: datetime_time) -> datetime_time:
    try:
        hour_str, minute_str = value.split(":", 1)
        hour = max(0, min(23, int(hour_str)))
        minute = max(0, min(59, int(minute_str)))
        return datetime_time(hour=hour, minute=minute)
    except Exception:
        return fallback


def _time_to_string(value: datetime_time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def _calculate_next_wellness_event(
    settings: Mapping[str, object], *, now: datetime | None = None
) -> tuple[datetime, str, dict[str, object]] | None:
    if not settings.get("enabled"):
        return None
    schedule = settings.get("schedule")
    if not isinstance(schedule, Mapping):
        return None
    now = now or datetime.now()
    upcoming: list[tuple[datetime, str, dict[str, object]]] = []
    for key, meta in WELLNESS_EVENT_METADATA.items():
        time_str = schedule.get(key)
        if not isinstance(time_str, str):
            continue
        event_time = _time_str_to_time(
            time_str,
            fallback=_time_str_to_time(
                DEFAULT_WELLNESS_SETTINGS["schedule"].get(key, "09:00"),
                fallback=datetime_time(hour=9, minute=0),
            ),
        )
        event_dt = datetime.combine(now.date(), event_time)
        if event_dt < now:
            event_dt += timedelta(days=1)
        upcoming.append((event_dt, key, dict(meta)))
    if not upcoming:
        return None
    return min(upcoming, key=lambda item: item[0])


def _format_timedelta_compact(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "Now"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append("moments")
    return " ".join(parts)




def _calculate_lunch_midpoint(
    settings: Mapping[str, object], *, reference: datetime | None = None
) -> datetime | None:
    schedule = settings.get("schedule") if isinstance(settings, Mapping) else None
    if not isinstance(schedule, Mapping):
        return None
    lunch_time = schedule.get("lunch")
    if not isinstance(lunch_time, str):
        return None

    reference = reference or datetime.now()
    fallback_time = _time_str_to_time(
        DEFAULT_WELLNESS_SETTINGS["schedule"].get("lunch", "12:30"),
        fallback=datetime_time(hour=12, minute=30),
    )
    lunch_start = _time_str_to_time(lunch_time, fallback=fallback_time)
    event_dt = datetime.combine(reference.date(), lunch_start)
    duration_minutes = _coerce_int(
        WELLNESS_EVENT_METADATA.get("lunch", {}).get("duration_minutes"), 60
    )
    midpoint_offset = timedelta(minutes=max(1, duration_minutes) / 2)
    return event_dt + midpoint_offset


def _resolve_automation_cloud_credentials() -> tuple[str, str]:
    username = str(st.session_state.get("kiroshi_cloud_username", "") or "").strip()
    password = st.session_state.get("kiroshi_cloud_password") or ""
    if not password:
        try:
            secrets_obj = getattr(st, "secrets", {})
            password = secrets_obj.get("KIROSHI_CLOUD_PASSWORD", "") or password
        except Exception:  # pragma: no cover - guard for secrets access
            password = password or ""
        if not password:
            password = os.environ.get("KIROSHI_CLOUD_PASSWORD", "")
    return username, password or ""


def _perform_midday_cloud_refresh(*, now: datetime | None = None) -> dict[str, object]:
    now = now or datetime.now()
    result: dict[str, object] = {
        "timestamp": now.replace(microsecond=0).isoformat(),
        "level": "info",
        "dataset_refreshed": False,
        "cloud_uploaded": False,
        "message": "",
    }
    messages: list[str] = []
    severity = "info"

    try:
        dataset = ensure_ai_learning_dataset(force=True)
    except Exception as exc:  # pragma: no cover - defensive guard
        logging.exception("Failed to regenerate AI Educate dataset: %s", exc)
        result["error"] = str(exc)
        messages.append("No se pudo regenerar la base de AI Educate.")
        severity = "error"
        dataset = None
    else:
        if dataset:
            result["dataset_refreshed"] = True
            messages.append("Base de AI Educate regenerada automáticamente.")
            severity = "success"
        else:
            messages.append("No hay casos para actualizar la base de AI Educate.")

    cloud_enabled = bool(st.session_state.get("kiroshi_cloud_enabled"))
    if dataset and cloud_enabled:
        username, password = _resolve_automation_cloud_credentials()
        if username and password:
            try:
                session = open_kiroshi_cloud_session(username, password)
                session.save_ai_dataset(dataset)
            except CloudAgentBlockedError as exc:
                messages.append(f"Sincronización detenida: {exc}")
                severity = "error"
            except CloudAuthenticationError as exc:
                messages.append(f"Credenciales inválidas para Kiroshi Cloud: {exc}")
                severity = "error"
            except KiroshiCloudError as exc:
                messages.append(f"Error al sincronizar con Kiroshi Cloud: {exc}")
                severity = "error"
            else:
                result["cloud_uploaded"] = True
                messages.append("Base sincronizada con Kiroshi Cloud.")
                if severity != "error":
                    severity = "success"
                st.session_state.kiroshi_cloud_summary = summarize_cloud_dataset(dataset)
                st.session_state.kiroshi_cloud_saved_at = (
                    datetime.utcnow().isoformat() + "Z"
                )
                st.session_state.kiroshi_cloud_authenticated = True
        else:
            if severity == "success":
                severity = "warning"
            elif severity == "info":
                severity = "warning"
            messages.append(
                "Sincronización con Kiroshi Cloud omitida: falta usuario o contraseña."
            )
    elif dataset and not cloud_enabled:
        messages.append("Sincronización con Kiroshi Cloud desactivada.")

    result["level"] = severity
    result["message"] = " ".join(messages).strip()
    logging.info("Midday cloud refresh: %s", result["message"])
    return result


def _maybe_trigger_midday_cloud_refresh(*, now: datetime | None = None) -> None:
    now = now or datetime.now()
    wellness_settings = _normalize_wellness_settings(
        st.session_state.get("wellness_reminders", DEFAULT_WELLNESS_SETTINGS)
    )
    st.session_state.wellness_reminders = wellness_settings
    midpoint = _calculate_lunch_midpoint(wellness_settings, reference=now)
    if midpoint is None:
        return
    if now < midpoint:
        return

    today_key = midpoint.date().isoformat()
    if st.session_state.get("_midday_cloud_sync_last_run_date") == today_key:
        return

    try:
        status = _perform_midday_cloud_refresh(now=now)
    except Exception as exc:  # pragma: no cover - defensive guard
        logging.exception("Midday cloud refresh failed: %s", exc)
        status = {
            "timestamp": now.replace(microsecond=0).isoformat(),
            "level": "error",
            "dataset_refreshed": False,
            "cloud_uploaded": False,
            "message": f"Fallo en la actualización automática: {exc}",
        }

    st.session_state._midday_cloud_sync_last_run_date = today_key
    st.session_state._midday_cloud_sync_status = status

def _refresh_wellness_reminder_state(*, now: datetime | None = None) -> dict[str, object] | None:
    """Ensure the next wellness reminder state is cached in session state."""

    wellness_settings = _normalize_wellness_settings(
        st.session_state.get("wellness_reminders", DEFAULT_WELLNESS_SETTINGS)
    )
    st.session_state.wellness_reminders = wellness_settings
    enabled = bool(wellness_settings.get("enabled"))
    lead_minutes = max(
        0,
        int(
            wellness_settings.get(
                "notification_lead", DEFAULT_WELLNESS_SETTINGS["notification_lead"]
            )
        ),
    )
    upcoming_event = _calculate_next_wellness_event(wellness_settings, now=now)
    if not enabled or not upcoming_event:
        state = {
            "event_dt": None,
            "event_key": None,
            "enabled": enabled,
            "lead_minutes": lead_minutes,
            "dismissed": True,
            "audio_played": False,
            "jump_to_actions": False,
        }
        st.session_state["_wellness_reminder_state"] = state
        st.session_state["_next_wellness_event"] = None
        return None

    event_dt, event_key, meta = upcoming_event
    state = dict(st.session_state.get("_wellness_reminder_state") or {})
    stored_dt = state.get("event_dt") if isinstance(state.get("event_dt"), datetime) else None
    if stored_dt != event_dt or state.get("event_key") != event_key:
        state = {
            "event_dt": event_dt,
            "event_key": event_key,
            "meta": dict(meta),
            "enabled": enabled,
            "lead_minutes": lead_minutes,
            "dismissed": False,
            "audio_played": False,
            "jump_to_actions": False,
        }
        state["tip"] = random.choice(WELLNESS_TIPS)
    else:
        state["meta"] = dict(meta)
        state.setdefault("tip", random.choice(WELLNESS_TIPS))
        state.setdefault("dismissed", False)
        state.setdefault("audio_played", False)
        state.setdefault("jump_to_actions", False)

    alert_threshold = 30 if lead_minutes == 0 else min(30, lead_minutes)
    audio_threshold = 15
    audio_trigger = audio_threshold if lead_minutes == 0 or lead_minutes >= audio_threshold else lead_minutes
    state.update(
        {
            "enabled": enabled,
            "lead_minutes": lead_minutes,
            "alert_threshold": alert_threshold,
            "audio_threshold": audio_threshold,
            "audio_trigger_minutes": audio_trigger,
        }
    )

    st.session_state["_wellness_reminder_state"] = state
    st.session_state["_next_wellness_event"] = upcoming_event
    return state


def _ensure_wellness_alert_styles() -> None:
    if st.session_state.get("_wellness_alert_styles_injected"):
        return
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlock"]:has(.wellness-alert__content) {
            position: relative;
            border-radius: 18px;
            padding: 1.25rem 1.5rem 1.1rem;
            margin-bottom: 1.2rem;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(30, 64, 175, 0.75));
            box-shadow: 0 18px 34px rgba(15, 23, 42, 0.35);
            border: 1px solid rgba(148, 163, 184, 0.22);
            color: #f8fafc;
        }
        div[data-testid="stVerticalBlock"]:has(.wellness-alert__content) .wellness-alert__title {
            font-size: 1.15rem;
            font-weight: 600;
            margin-bottom: 0.35rem;
        }
        div[data-testid="stVerticalBlock"]:has(.wellness-alert__content) .wellness-alert__eyebrow {
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.08em;
            opacity: 0.75;
            margin-bottom: 0.2rem;
            display: inline-block;
        }
        div[data-testid="stVerticalBlock"]:has(.wellness-alert__content) .wellness-alert__meta {
            font-size: 0.95rem;
            margin-bottom: 0.6rem;
            opacity: 0.9;
        }
        div[data-testid="stVerticalBlock"]:has(.wellness-alert__content) .wellness-alert__tip {
            font-size: 0.9rem;
            margin-bottom: 0.75rem;
            background: rgba(15, 118, 110, 0.18);
            border-radius: 12px;
            padding: 0.55rem 0.75rem;
            border: 1px solid rgba(45, 212, 191, 0.35);
        }
        div[data-testid="stVerticalBlock"]:has(.wellness-alert__content--actions) {
            background: linear-gradient(135deg, rgba(30, 64, 175, 0.95), rgba(21, 128, 61, 0.78));
        }
        div[data-testid="stVerticalBlock"]:has(.wellness-alert__content) .wellness-alert__list {
            margin: 0 0 0.8rem 0;
            padding-left: 1.1rem;
        }
        div[data-testid="stVerticalBlock"]:has(.wellness-alert__content) .wellness-alert__list li {
            margin-bottom: 0.35rem;
        }
        div[data-testid="stVerticalBlock"]:has(.wellness-alert__content) .wellness-alert__actions button {
            width: 100%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_wellness_alert_styles_injected"] = True


def _get_wellness_audio_clip() -> bytes:
    cached = st.session_state.get("_wellness_audio_clip")
    if isinstance(cached, (bytes, bytearray)):
        return bytes(cached)
    sample_rate = 22050
    duration_seconds = 0.65
    frequency = 880
    total_samples = int(sample_rate * duration_seconds)
    amplitude = 0.35
    data = bytearray()
    for n in range(total_samples):
        sample = amplitude * math.sin(2 * math.pi * frequency * n / sample_rate)
        value = int(max(-1.0, min(1.0, sample)) * 32767)
        data.extend(value.to_bytes(2, byteorder="little", signed=True))
    data_size = len(data)
    byte_rate = sample_rate * 2
    header = b"".join(
        [
            b"RIFF",
            (36 + data_size).to_bytes(4, "little"),
            b"WAVE",
            b"fmt ",
            (16).to_bytes(4, "little"),
            (1).to_bytes(2, "little"),
            (1).to_bytes(2, "little"),
            sample_rate.to_bytes(4, "little"),
            byte_rate.to_bytes(4, "little"),
            (2).to_bytes(2, "little"),
            (16).to_bytes(2, "little"),
            b"data",
            data_size.to_bytes(4, "little"),
        ]
    )
    clip = bytes(header + data)
    st.session_state["_wellness_audio_clip"] = clip
    return clip


def _update_wellness_alert_state(**changes: object) -> None:
    state = dict(st.session_state.get("_wellness_reminder_state") or {})
    if not state:
        return
    state.update(changes)
    st.session_state["_wellness_reminder_state"] = state


def _dismiss_wellness_alert() -> None:
    _update_wellness_alert_state(dismissed=True, jump_to_actions=False)


def _start_wellness_pause() -> None:
    _update_wellness_alert_state(
        jump_to_actions=True,
        dismissed=False,
        pause_started_at=datetime.now(),
    )


def _complete_wellness_pause() -> None:
    _update_wellness_alert_state(
        jump_to_actions=False,
        dismissed=True,
        pause_completed_at=datetime.now(),
    )


def _return_to_wellness_alert() -> None:
    _update_wellness_alert_state(jump_to_actions=False, dismissed=False)


def render_wellness_alert(reminder_state: dict[str, object] | None = None) -> None:
    """Display the global wellness reminder banner or actions modal."""

    reminder_state = reminder_state or st.session_state.get("_wellness_reminder_state")
    if not isinstance(reminder_state, Mapping):
        return
    if not reminder_state.get("enabled"):
        return
    event_dt = reminder_state.get("event_dt")
    if not isinstance(event_dt, datetime):
        return
    if reminder_state.get("dismissed") and not reminder_state.get("jump_to_actions"):
        return

    now = datetime.now()
    delta = event_dt - now
    delta_minutes = delta.total_seconds() / 60
    if delta_minutes < 0:
        return

    alert_threshold = reminder_state.get("alert_threshold", 30)
    if not reminder_state.get("jump_to_actions") and delta_minutes > alert_threshold:
        return

    _ensure_wellness_alert_styles()

    audio_trigger = reminder_state.get("audio_trigger_minutes", 15)
    if (
        delta_minutes <= audio_trigger
        and not reminder_state.get("audio_played")
        and delta_minutes > 0
    ):
        audio_clip = _get_wellness_audio_clip()
        if audio_clip:
            encoded_clip = base64.b64encode(audio_clip).decode("utf-8")
            st.markdown(
                f"""
                <audio autoplay hidden>
                    <source src="data:audio/wav;base64,{encoded_clip}" type="audio/wav" />
                </audio>
                """,
                unsafe_allow_html=True,
            )
        _update_wellness_alert_state(audio_played=True)

    label = str(
        reminder_state.get("meta", {}).get(
            "label", str(reminder_state.get("event_key", ""))
        )
    )
    duration = reminder_state.get("meta", {}).get("duration_minutes")
    duration_text = (
        f"Set aside {int(duration)} minutes to fully disconnect."
        if isinstance(duration, (int, float)) and duration
        else "Give yourself a complete reset."
    )
    countdown_text = _format_timedelta_compact(delta)
    tip = str(reminder_state.get("tip") or random.choice(WELLNESS_TIPS))
    lead_minutes = reminder_state.get("lead_minutes", 0)

    content_classes = "wellness-alert__content"
    if reminder_state.get("jump_to_actions"):
        content_classes += " wellness-alert__content--actions"

    with st.container():
        st.markdown(
            f"""
            <div class="{content_classes}">
                <div class="wellness-alert__eyebrow">Wellness reminder</div>
                <div class="wellness-alert__title">{label} begins in {countdown_text}</div>
                <div class="wellness-alert__meta">Starts at {event_dt.strftime('%H:%M')} · Lead time {lead_minutes} min</div>
                <div class="wellness-alert__tip">💡 {escape(tip)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if reminder_state.get("jump_to_actions"):
            actions: list[str] = [
                "Silence notifications and let teammates know you're away.",
                duration_text,
                "Stretch, hydrate, or take a short walk before coming back.",
            ]
            actions_html = "".join(
                f"<li>{escape(item)}</li>" for item in actions if item
            )
            st.markdown(
                f"""
                <ul class="wellness-alert__list">
                    {actions_html}
                </ul>
                """,
                unsafe_allow_html=True,
            )
            st.markdown('<div class="wellness-alert__actions">', unsafe_allow_html=True)
            action_cols = st.columns(3)
            if action_cols[0].button(
                "Back to reminder",
                key=global_widget_key(
                    f"wellness_back_{reminder_state.get('event_key')}_{event_dt:%H%M}"
                ),
            ):
                _return_to_wellness_alert()
            if action_cols[1].button(
                "Pause complete",
                key=global_widget_key(
                    f"wellness_complete_{reminder_state.get('event_key')}_{event_dt:%H%M}"
                ),
            ):
                _complete_wellness_pause()
            if action_cols[2].button(
                "Dismiss",
                key=global_widget_key(
                    f"wellness_dismiss_actions_{reminder_state.get('event_key')}_{event_dt:%H%M}"
                ),
            ):
                _dismiss_wellness_alert()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="wellness-alert__actions">', unsafe_allow_html=True)
            action_cols = st.columns(2)
            if action_cols[0].button(
                "Dismiss reminder",
                key=global_widget_key(
                    f"wellness_dismiss_{reminder_state.get('event_key')}_{event_dt:%H%M}"
                ),
            ):
                _dismiss_wellness_alert()
            if action_cols[1].button(
                "Start pause now",
                key=global_widget_key(
                    f"wellness_start_{reminder_state.get('event_key')}_{event_dt:%H%M}"
                ),
            ):
                _start_wellness_pause()
            st.markdown('</div>', unsafe_allow_html=True)

def ensure_settings_styles() -> None:
    if st.session_state.get("_settings_styles_injected"):
        return
    st.markdown(
        """
        <style>
        .settings-hero {
            position: relative;
            border-radius: 24px;
            padding: 2.5rem 2.75rem;
            margin-bottom: 1.5rem;
            background: radial-gradient(circle at top left, rgba(59,130,246,0.25), transparent 55%),
                        linear-gradient(135deg, rgba(15,23,42,0.92), rgba(30,64,175,0.75));
            color: #f8fafc;
            box-shadow: 0 28px 50px rgba(15, 23, 42, 0.45);
            overflow: hidden;
        }
        .settings-hero::after {
            content: "";
            position: absolute;
            inset: 14px;
            border-radius: 20px;
            border: 1px solid rgba(148,163,184,0.25);
            pointer-events: none;
        }
        .settings-hero__title {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        .settings-hero__subtitle {
            font-size: 1.05rem;
            opacity: 0.85;
            max-width: 560px;
        }
        .settings-hero__glow {
            position: absolute;
            width: 240px;
            height: 240px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(96,165,250,0.45), transparent 70%);
            top: -40px;
            right: -60px;
            filter: blur(0.5px);
        }
        .settings-section-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin-top: 1rem;
            margin-bottom: 0.4rem;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }
        .settings-section-title span {
            font-size: 1.4rem;
        }
        .wellness-banner {
            border-radius: 18px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1.3rem;
            background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(59,130,246,0.18));
            border: 1px solid rgba(96,165,250,0.45);
            box-shadow: 0 18px 40px rgba(15,23,42,0.24);
            color: var(--kiroshi-text, #0f172a);
        }
        .wellness-banner.is-soon {
            background: linear-gradient(135deg, rgba(249,115,22,0.18), rgba(244,63,94,0.25));
            border-color: rgba(248,113,113,0.65);
        }
        .wellness-banner__heading {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .wellness-banner__meta {
            font-size: 0.95rem;
            opacity: 0.85;
        }
        .wellness-banner__tip {
            margin-top: 0.6rem;
            font-size: 0.92rem;
            display: flex;
            gap: 0.4rem;
            align-items: flex-start;
        }
        .settings-tabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
        }
        .settings-tabs button[role="tab"] {
            border-radius: 999px !important;
            border: 1px solid rgba(148,163,184,0.4) !important;
            background: rgba(15,23,42,0.04) !important;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        .settings-tabs button[role="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, rgba(59,130,246,0.22), rgba(59,130,246,0.05)) !important;
            border-color: rgba(59,130,246,0.45) !important;
            color: inherit !important;
            box-shadow: inset 0 0 0 1px rgba(59,130,246,0.15);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state._settings_styles_injected = True

def trigger_hard_reload() -> None:
    """Force a full browser reload similar to pressing F5."""
    components.html(
        """
        <script>
        const reloadKey = 'kiroshi-hard-reload';
        if (!window.sessionStorage.getItem(reloadKey)) {
            window.sessionStorage.setItem(reloadKey, '1');
            window.location.reload();
        } else {
            window.sessionStorage.removeItem(reloadKey);
        }
        </script>
        """,
        height=0,
        width=0,
    )


def make_json_safe(value):
    """Convert values to JSON-serialisable representations for debug output."""

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {f.name: make_json_safe(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): make_json_safe(val) for key, val in value.items()}
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.to_list()
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return [make_json_safe(item) for item in value]
    return repr(value)


def get_session_state_snapshot():
    """Return a JSON-safe snapshot of Streamlit session state."""

    return {str(key): make_json_safe(val) for key, val in st.session_state.items()}

# ─────────────────────────── CONFIG ────────────────────────────
st.set_page_config(
    page_title=f"Kiroshi {VERSION}",
    layout="wide",
    page_icon=str(KIROSHI_LOGO_PATH),
)

_check_installation_status()

# Ensure the persisted appearance preference is restored before we compute the
# active theme. Otherwise a fresh session would briefly fall back to the default
# (enabled) value and immediately re-enable holiday styling.
if "enable_holiday_theme" not in st.session_state:
    st.session_state["enable_holiday_theme"] = _get_persistent_default(
        "enable_holiday_theme", True
    )
if "dark_mode_enabled" not in st.session_state:
    st.session_state["dark_mode_enabled"] = _get_persistent_default(
        "dark_mode_enabled", False
    )

CURRENT_THEME = determine_active_theme()
apply_theme_palette(CURRENT_THEME)


def inject_base_styles() -> None:
    st.markdown(
        """
        <style>
        .dashboard-title {
            font-size: 2.25rem;
            font-weight: 700;
            color: var(--kiroshi-primary);
            margin-bottom: 1.25rem;
            text-shadow: 0 4px 10px rgba(15, 23, 42, 0.18);
        }

        #kiroshi-header {
            width: 100%;
            box-sizing: border-box;
        }

        .dashboard-section {
            margin: 1.5rem 0;
            padding: 1.5rem 1.75rem;
            background: var(--kiroshi-surface);
            border-radius: 1.1rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
            color: var(--kiroshi-text-on-surface);
            transition: transform 220ms ease, box-shadow 220ms ease;
            animation: kiroshiFadeIn 0.8s ease-out both;
        }
        .dashboard-section:hover {
            transform: translateY(-3px);
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
        }

        .tutorial-wrapper {
            margin: 1.5rem 0 2rem;
            padding: 2rem;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            background: rgba(255, 255, 255, 0.65);
            backdrop-filter: blur(20px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            color: var(--kiroshi-text);
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }

        .tutorial-wrapper::before {
            content: "";
            position: absolute;
            inset: -40% -40% auto auto;
            width: 320px;
            height: 320px;
            background: radial-gradient(circle at center, rgba(93, 93, 255, 0.16), transparent 65%);
            pointer-events: none;
            animation: tutorialGlow 8s ease-in-out infinite;
        }

        .tutorial-step-title {
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--kiroshi-primary);
            margin-bottom: 0.35rem;
        }

        .tutorial-step-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-bottom: 0.85rem;
        }

        .tutorial-step-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0.45rem 0.85rem;
            border-radius: 999px;
            border: 1px solid rgba(148, 163, 184, 0.45);
            background: rgba(255, 255, 255, 0.7);
            box-shadow: 0 10px 18px rgba(15, 23, 42, 0.12);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }

        .tutorial-step-badge__index {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            font-weight: 700;
            font-size: 0.95rem;
            background: linear-gradient(135deg, var(--kiroshi-primary) 0%, var(--kiroshi-accent) 100%);
            color: white;
        }

        .tutorial-step-badge__label {
            display: flex;
            flex-direction: column;
            line-height: 1.1;
            font-size: 0.82rem;
            color: var(--kiroshi-text-on-white);
        }

        .tutorial-step-badge__label span {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--kiroshi-muted);
        }

        .tutorial-step-badge__label strong {
            font-size: 0.86rem;
            color: var(--kiroshi-text-on-white);
        }

        .tutorial-step-badge.completed .tutorial-step-badge__index {
            background: linear-gradient(135deg, #22c55e 0%, #4ade80 100%);
            box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.25);
        }

        .tutorial-step-badge.active {
            transform: translateY(-2px);
            box-shadow: 0 14px 22px rgba(37, 99, 235, 0.25);
        }

        .tutorial-step-badge.active .tutorial-step-badge__index {
            animation: tutorialBadgePulse 2.6s ease-in-out infinite;
        }

        .tutorial-step-badge.upcoming {
            opacity: 0.8;
        }

        .tutorial-intro {
            font-size: 0.98rem;
            line-height: 1.6;
            color: var(--kiroshi-text-on-white);
            margin-bottom: 1rem;
        }

        .tutorial-visual-card {
            padding: 1rem;
            border-radius: 1rem;
            background: rgba(255, 255, 255, 0.85);
            border: 1px solid rgba(209, 213, 219, 0.7);
            height: 100%;
            color: var(--kiroshi-text-on-white);
            position: relative;
            overflow: hidden;
        }

        .tutorial-footnote {
            font-size: 0.85rem;
            color: var(--kiroshi-muted);
        }

        .tutorial-wrapper [data-testid="stProgressBar"] {
            border-radius: 999px;
            background: rgba(226, 232, 240, 0.65);
            padding: 0.15rem;
            margin-bottom: 1rem;
        }

        .tutorial-wrapper [data-testid="stProgressBar"] div[role="progressbar"] {
            border-radius: 999px;
            background: linear-gradient(135deg, var(--kiroshi-primary) 0%, var(--kiroshi-accent) 100%);
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.35);
        }

        .tutorial-flow {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1.1rem;
            margin-top: 0.75rem;
        }

        .tutorial-flow__step {
            position: relative;
            padding: 1.1rem 1rem 1.25rem;
            border-radius: 0.95rem;
            background: rgba(248, 250, 252, 0.88);
            border: 1px solid rgba(148, 163, 184, 0.4);
            box-shadow: 0 10px 18px rgba(15, 23, 42, 0.12);
        }

        .tutorial-flow__icon {
            width: 42px;
            height: 42px;
            border-radius: 0.75rem;
            display: grid;
            place-items: center;
            margin-bottom: 0.65rem;
            font-weight: 700;
            color: white;
            background: linear-gradient(135deg, var(--kiroshi-primary) 0%, var(--kiroshi-accent) 100%);
        }

        .tutorial-flow__title {
            font-weight: 600;
            margin-bottom: 0.35rem;
            color: var(--kiroshi-text-on-surface);
        }

        .tutorial-highlight-list {
            margin: 0.8rem 0 0;
            padding-left: 1rem;
            display: grid;
            gap: 0.35rem;
        }

        .tutorial-highlight-list li {
            font-size: 0.92rem;
            color: var(--kiroshi-text-on-white);
        }

        .tutorial-color-row {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }

        .tutorial-color-chip {
            flex: 1;
            height: 36px;
            border-radius: 0.75rem;
            position: relative;
            box-shadow: 0 8px 16px rgba(15, 23, 42, 0.18);
            overflow: hidden;
        }

        .tutorial-color-chip::after {
            content: attr(data-label);
            position: absolute;
            inset: auto 0 0;
            padding: 0.2rem 0.55rem;
            font-size: 0.65rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: rgba(15, 23, 42, 0.75);
            background: rgba(255, 255, 255, 0.78);
        }

        .tutorial-insight-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .tutorial-insight-card {
            padding: 1rem;
            border-radius: 1rem;
            background: rgba(15, 23, 42, 0.65);
            color: white;
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.2);
        }

        .tutorial-insight-card strong {
            font-size: 1.1rem;
        }

        @keyframes tutorialBadgePulse {
            0%, 100% {
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.35);
            }
            50% {
                transform: scale(1.08);
                box-shadow: 0 0 0 6px rgba(37, 99, 235, 0.08);
            }
        }

        @keyframes tutorialGlow {
            0%, 100% {
                transform: translate3d(0, 0, 0) scale(1);
                opacity: 0.9;
            }
            50% {
                transform: translate3d(-12%, 6%, 0) scale(1.1);
                opacity: 0.6;
            }
        }

        .case-card {
            padding: 1.25rem 1.5rem;
            border-radius: 0.9rem;
            border: 1px solid rgba(15, 23, 42, 0.08);
            background: linear-gradient(145deg, var(--kiroshi-surface) 0%, rgba(255, 255, 255, 0.85) 100%);
            margin-bottom: 1rem;
            color: var(--kiroshi-text-on-white);
        }

        .case-meta {
            display: flex;
            flex-direction: column;
            gap: 0.2rem;
            padding-bottom: 0.4rem;
        }

        .case-meta__label {
            font-size: 0.78rem;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            color: var(--kiroshi-muted);
        }

        .case-meta__value {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--kiroshi-text-on-white);
        }

        .case-actions {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .case-actions .stSelectbox > div > div {
            border-radius: 0.6rem;
        }

        .case-actions .stButton button {
            width: 100%;
            border-radius: 999px;
        }

        .case-actions .crm-link {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.55rem 0.75rem;
            border-radius: 999px;
            border: none;
            font-weight: 600;
            background: linear-gradient(135deg, var(--kiroshi-primary) 0%, var(--kiroshi-accent) 100%);
            color: white !important;
            text-decoration: none;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.25);
        }

        .case-actions .crm-link:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(15, 23, 42, 0.35);
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def render_logo():
    kiroshi_message = escape(get_kiroshi_message(CURRENT_THEME))
    now = datetime.now()
    formatted_date = f"{now.strftime('%A')}, {now.month}/{now.day}/{now.year}"
    encoded_logo = base64.b64encode(KIROSHI_LOGO_PATH.read_bytes()).decode()
    is_dark_theme = CURRENT_THEME.key == DARK_THEME.key
    holiday_theme_active = CURRENT_THEME.key not in {DEFAULT_THEME.key, DARK_THEME.key}
    companion_card_background = (
        "#ffffff"
        if holiday_theme_active
        else (
            "linear-gradient(160deg, color-mix(in srgb, var(--kiroshi-surface) 88%, transparent), "
            "color-mix(in srgb, var(--kiroshi-background) 92%, transparent))"
            if is_dark_theme
            else "linear-gradient(145deg, color-mix(in srgb, var(--kiroshi-primary) 18%, transparent), "
            "color-mix(in srgb, var(--kiroshi-accent) 12%, transparent))"
        )
    )
    companion_card_shadow = (
        "0 14px 34px rgba(15, 23, 42, 0.18)"
        if holiday_theme_active
        else (
            "0 18px 42px rgba(2, 6, 23, 0.55)"
            if is_dark_theme
            else "0 10px 25px rgba(15, 23, 42, 0.12)"
        )
    )
    companion_card_border = (
        "1px solid rgba(15, 23, 42, 0.08)"
        if holiday_theme_active
        else (
            "1px solid rgba(71, 85, 105, 0.35)"
            if is_dark_theme
            else "1px solid transparent"
        )
    )
    companion_title_color = (
        "#111827"
        if holiday_theme_active
        else ("var(--kiroshi-accent)" if is_dark_theme else "var(--kiroshi-primary)")
    )
    companion_text_color = "#111827" if holiday_theme_active else "var(--kiroshi-text)"
    header_html = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&display=swap');
        #kiroshi-header {{
            display: grid;
            grid-template-columns: minmax(180px, 0.85fr) minmax(320px, 1.5fr) minmax(200px, 0.85fr);
            align-items: center;
            justify-content: center;
            gap: 1.5rem;
            padding: 0.75rem 0;
            width: 100%;
            box-sizing: border-box;
            row-gap: 1.25rem;
        }}

        #kiroshi-header {{
            font-family: 'Segoe UI', 'Segoe UI Variable', 'Segoe UI Web', 'Trebuchet MS',
                'Calibri', 'Verdana', sans-serif;
            color: var(--kiroshi-text);
        }}

        #kiroshi-header * {{
            color: inherit;
        }}

        #kiroshi-header__version {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            min-width: 180px;
            text-align: center;
        }}

        #kiroshi-header__version span {{
            font-weight: 600;
            font-size: 1.05rem;
            font-family: 'Segoe UI Semibold', 'Segoe UI', 'Trebuchet MS', 'Calibri',
                'Verdana', sans-serif;
            letter-spacing: 0.02em;
        }}

        #kiroshi-header__companion {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 0 0.75rem;
            width: 100%;
            padding-top: 1.5rem;
        }}

        #kiroshi-header__companion-card {{
            background: {companion_card_background};
            border-radius: 1rem;
            padding: 1rem 1.5rem;
            box-shadow: {companion_card_shadow};
            max-width: 620px;
            width: 100%;
            margin: 1.75rem auto 0;
            border: {companion_card_border};
        }}

        #kiroshi-header__companion-title {{
            font-size: 1.3rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            color: {companion_title_color};
            margin-bottom: 0.5rem;
            font-family: 'Segoe UI', 'Trebuchet MS', 'Calibri', 'Verdana', sans-serif;
        }}

        #kiroshi-header__companion-text {{
            font-size: 1rem;
            line-height: 1.6;
            color: {companion_text_color};
            font-family: 'Segoe UI', 'Segoe UI Variable', 'Segoe UI Web', 'Calibri',
                'Verdana', sans-serif;
            font-weight: 500;
            letter-spacing: 0.015em;
        }}

        #kiroshi-header__date {{
            font-weight: 600;
            text-align: right;
            min-width: 200px;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            font-family: 'Segoe UI Semibold', 'Segoe UI', 'Trebuchet MS', 'Calibri',
                'Verdana', sans-serif;
            letter-spacing: 0.02em;
        }}

        @media (max-width: 1100px) {{
            #kiroshi-header {{
                grid-template-columns: minmax(160px, 1fr) minmax(0, 1fr);
                grid-template-rows: auto auto;
                justify-items: center;
            }}

            #kiroshi-header__date {{
                justify-content: center;
                text-align: center;
            }}
        }}

        @media (max-width: 780px) {{
            #kiroshi-header {{
                grid-template-columns: 1fr;
                justify-items: center;
            }}

            #kiroshi-header__companion {{
                order: 2;
                padding: 1rem 1.5rem 0;
            }}

            #kiroshi-header__date {{
                order: 3;
                justify-content: center;
            }}

            #kiroshi-header__companion-card {{
                max-width: clamp(260px, 86vw, 540px);
                padding: 1.1rem 1.25rem;
                margin-top: 1.25rem;
            }}
        }}
    </style>
    <div id="kiroshi-header">
        <div id="kiroshi-header__version">
            <span>Version {VERSION}</span>
            <img src="data:image/png;base64,{encoded_logo}" width="180" id="kiroshi-logo" style="cursor:pointer;max-width:100%;height:auto;">
        </div>
        <div id="kiroshi-header__companion">
            <div id="kiroshi-header__companion-card">
                <div id="kiroshi-header__companion-title">Kiroshi Motivational Companion</div>
                <div id="kiroshi-header__companion-text">{kiroshi_message}</div>
            </div>
        </div>
        <div id="kiroshi-header__date">
            {formatted_date}
        </div>
    </div>
    <script>
    const logo = document.getElementById('kiroshi-logo');
    const header = document.getElementById('kiroshi-header');

    const updateHeight = () => {{
        if (!header || !window.Streamlit || typeof window.Streamlit.setFrameHeight !== 'function') {{
            return;
        }}
        const height = Math.ceil(header.getBoundingClientRect().height + 32);
        window.Streamlit.setFrameHeight(height);
    }};

    window.addEventListener('load', updateHeight);
    window.addEventListener('resize', updateHeight);
    updateHeight();

    if (logo && window.Streamlit && typeof window.Streamlit.setComponentValue === 'function') {{
        logo.addEventListener('click', function(){{
            window.Streamlit.setComponentValue('open-debug');
        }});
    }}
    </script>
    """
    action_logo = components.html(header_html, height=380)
    if action_logo == "open-debug":
        st.session_state.debug_mode = True
        _persist_setting("debug_mode")


def _render_tutorial_visual(kind: str) -> None:
    kind = (kind or "").lower()

    # Inject tutorial-specific styles
    st.markdown("""
    <style>
        .t-card {
            background: linear-gradient(145deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .t-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem; color: var(--kiroshi-primary); }
        .t-mock-row {
            display: flex; gap: 8px; margin-bottom: 8px; align-items: center;
            padding: 8px; background: rgba(0,0,0,0.2); border-radius: 6px;
        }
        .t-mock-btn {
            background: var(--kiroshi-primary); color: white; padding: 4px 12px;
            border-radius: 4px; font-size: 0.8rem; font-weight: 600;
        }
        .t-mock-field {
            background: rgba(255,255,255,0.1); height: 24px; border-radius: 4px; flex-grow: 1;
        }
        .t-key {
            display: inline-block; padding: 4px 8px; background: #333; color: #fff;
            border-radius: 4px; font-family: monospace; font-size: 0.9rem;
            border-bottom: 2px solid #111; margin: 0 2px;
        }
        .t-split { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    </style>
    """, unsafe_allow_html=True)

    if kind == "intro_card":
        st.markdown("""
        <div class='t-card' style='text-align: center; padding: 3rem 1rem;'>
            <div style='font-size: 3rem; margin-bottom: 1rem;'>🤖</div>
            <div class='t-title' style='font-size: 1.5rem;'>System Online</div>
            <p>Initializing Kiroshi documentation protocols...</p>
            <div style='margin-top: 2rem; display: flex; gap: 10px; justify-content: center;'>
                <div style='width: 10px; height: 10px; background: #4ade80; border-radius: 50%; animation: pulse 2s infinite;'></div>
                <div style='width: 10px; height: 10px; background: #4ade80; border-radius: 50%; animation: pulse 2s infinite 0.3s;'></div>
                <div style='width: 10px; height: 10px; background: #4ade80; border-radius: 50%; animation: pulse 2s infinite 0.6s;'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif kind == "dashboard_mock":
        st.markdown("""
        <div class='t-card'>
            <div class='t-title'>Tracked Cases (Live)</div>
            <div class='t-mock-row'>
                <span style='width: 60px; font-weight: bold;'>Status</span>
                <span style='flex-grow: 1;'>Case ID / Summary</span>
                <span style='width: 80px;'>Priority</span>
            </div>
            <div class='t-mock-row' style='border-left: 3px solid #ef4444;'>
                <span style='font-size: 0.8rem;'>PENDING</span>
                <div style='display:flex; flex-direction:column; flex-grow:1;'>
                    <span style='font-weight:bold;'>CS-2024-991</span>
                    <span style='font-size:0.75rem; opacity:0.8;'>Scanner connection failure</span>
                </div>
                <span style='color: #ef4444; font-weight:bold;'>HIGH</span>
            </div>
            <div class='t-mock-row' style='border-left: 3px solid #3b82f6;'>
                <span style='font-size: 0.8rem;'>TRACKED</span>
                <div style='display:flex; flex-direction:column; flex-grow:1;'>
                    <span style='font-weight:bold;'>CS-2024-882</span>
                    <span style='font-size:0.75rem; opacity:0.8;'>License renewal pending</span>
                </div>
                <span style='color: #3b82f6; font-weight:bold;'>NORMAL</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif kind == "case_flow":
        st.markdown("""
        <div class='t-card'>
            <div style='display: flex; gap: 1rem; margin-bottom: 1rem;'>
                <div style='padding: 8px 16px; background: rgba(255,255,255,0.1); border-radius: 8px 8px 0 0; opacity: 0.5;'>Dashboard</div>
                <div style='padding: 8px 16px; background: var(--kiroshi-primary); color: white; border-radius: 8px 8px 0 0; font-weight: bold;'>+ Add Case</div>
            </div>
            <div style='background: rgba(0,0,0,0.2); padding: 1rem; border-radius: 8px;'>
                <div class='t-title'>Case Workspace</div>
                <div class='t-split'>
                    <div>
                        <div class='t-mock-field' style='margin-bottom: 8px;'></div>
                        <small>Description</small>
                    </div>
                    <div>
                        <div class='t-mock-field' style='margin-bottom: 8px;'></div>
                        <small>Internal Notes</small>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif kind == "tracking_ui":
        st.markdown("""
        <div class='t-card'>
            <div class='t-title'>Tracking Tab Logic</div>
            <div style='display: flex; flex-direction: column; gap: 12px;'>
                <div style='display: flex; justify-content: space-between;'>
                    <span>Priority</span>
                    <div style='width: 100px; height: 20px; background: #fca5a5; border-radius: 4px;'></div>
                </div>
                <div style='display: flex; justify-content: space-between;'>
                    <span>Ticket #</span>
                    <div class='t-mock-field'></div>
                </div>
                <div style='margin-top: 10px; text-align: right;'>
                    <span class='t-mock-btn'>Save and Track</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif kind == "power_tools":
        st.markdown("""
        <div class='t-split'>
            <div class='t-card'>
                <div class='t-title'>📧 Email Generator</div>
                <p style='font-size: 0.9rem;'>Select a template (Recap, Escalation, etc.) and Kiroshi drafts the full text instantly.</p>
                <div class='t-mock-btn' style='text-align: center; margin-top: 8px;'>Generate Draft</div>
            </div>
            <div class='t-card'>
                <div class='t-title'>💬 Kiroshi Chat</div>
                <p style='font-size: 0.9rem;'>Ask: "How do I fix error 202?" or "Summarize these logs."</p>
                <div class='t-mock-field' style='margin-top: 8px;'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif kind == "hotkeys_map":
        st.markdown("""
        <div class='t-card'>
            <div class='t-title'>Global Shortcuts</div>
            <div style='display: flex; flex-direction: column; gap: 12px;'>
                <div>
                    <span class='t-key'>Ctrl</span> + <span class='t-key'>Alt</span> + <span class='t-key'>C</span>
                    <span style='margin-left: 12px;'>Copy all tables</span>
                </div>
                <div>
                    <span class='t-key'>Ctrl</span> + <span class='t-key'>Alt</span> + <span class='t-key'>1</span>
                    <span style='margin-left: 12px;'>Copy Title</span>
                </div>
                <div>
                    <span class='t-key'>Ctrl</span> + <span class='t-key'>Alt</span> + <span class='t-key'>2</span>
                    <span style='margin-left: 12px;'>Copy Description</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif kind == "completion_card":
        st.markdown("""
        <div class='t-card' style='text-align: center; background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.05)); border-color: rgba(34, 197, 94, 0.3);'>
            <div style='font-size: 3rem; margin-bottom: 1rem;'>✅</div>
            <div class='t-title' style='color: #4ade80;'>Training Complete</div>
            <p>You are ready to operate Kiroshi.</p>
        </div>
        """, unsafe_allow_html=True)
def _mark_tutorial_completion(status: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    st.session_state.tutorial_completed = True
    st.session_state.tutorial_completion_type = status
    st.session_state.tutorial_completed_at = timestamp
    metadata = st.session_state.get("tutorial_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    visited = metadata.get("visited")
    if not isinstance(visited, list):
        visited = []
    all_step_ids = [str(step.get("id", idx)) for idx, step in enumerate(TUTORIAL_STEPS)]
    for step_id in all_step_ids:
        if step_id not in visited:
            visited.append(step_id)
    metadata.update(
        {
            "version": TUTORIAL_VERSION,
            "visited": visited,
            "last_step": max(len(TUTORIAL_STEPS) - 1, 0),
            "total_steps": len(TUTORIAL_STEPS),
            "completed": status == "completed",
            "completion_type": status,
            "completed_at": timestamp,
            "furthest_step": max(
                len(TUTORIAL_STEPS) - 1,
                int(metadata.get("furthest_step", 0))
                if isinstance(metadata.get("furthest_step"), int)
                else 0,
            ),
        }
    )
    st.session_state.tutorial_metadata = metadata
    _persist_setting("tutorial_completed")
    _persist_setting("tutorial_completion_type")
    _persist_setting("tutorial_completed_at")
    _persist_setting("tutorial_metadata")
    st.session_state.show_tutorial = False
    st.session_state.tutorial_step = 0
    st.rerun()


def render_onboarding_tutorial() -> None:
    if not st.session_state.get("show_tutorial"):
        return
    if not TUTORIAL_STEPS:
        return
    total_steps = len(TUTORIAL_STEPS)
    step_idx = int(st.session_state.get("tutorial_step", 0))
    if step_idx < 0:
        step_idx = 0
    if step_idx >= total_steps:
        step_idx = total_steps - 1
    st.session_state.tutorial_step = step_idx
    step = TUTORIAL_STEPS[step_idx]
    step_id = str(step.get("id", step_idx))

    metadata = st.session_state.get("tutorial_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    visited = metadata.get("visited")
    if not isinstance(visited, list):
        visited = []
    metadata_changed = False
    if step_id not in visited:
        visited.append(step_id)
        metadata_changed = True
    if metadata.get("last_step") != step_idx:
        metadata["last_step"] = step_idx
        metadata_changed = True
    if metadata.get("total_steps") != total_steps:
        metadata["total_steps"] = total_steps
        metadata_changed = True
    if metadata.get("version") != TUTORIAL_VERSION:
        metadata["version"] = TUTORIAL_VERSION
        metadata_changed = True
    furthest_step = metadata.get("furthest_step")
    if not isinstance(furthest_step, int):
        furthest_step = step_idx
        metadata_changed = True
    if step_idx > furthest_step:
        furthest_step = step_idx
        metadata_changed = True
    metadata["furthest_step"] = furthest_step
    metadata["visited"] = visited
    st.session_state.tutorial_metadata = metadata
    if metadata_changed:
        _persist_setting("tutorial_metadata")

    with st.container():
        st.markdown("<div class='tutorial-wrapper'>", unsafe_allow_html=True)
        badge_markup = "".join(
            "<div class='{}'>"
            "<div class='tutorial-step-badge__index'>{}</div>"
            "<div class='tutorial-step-badge__label'><span>Step {}</span><strong>{}</strong></div>"
            "</div>".format(
                "tutorial-step-badge completed"
                if idx < step_idx
                else "tutorial-step-badge active"
                if idx == step_idx
                else "tutorial-step-badge upcoming",
                idx + 1,
                idx + 1,
                escape(str(item.get("title", ""))),
            )
            for idx, item in enumerate(TUTORIAL_STEPS)
        )
        st.markdown(
            f"<div class='tutorial-step-badges'>{badge_markup}</div>", unsafe_allow_html=True
        )
        st.markdown(
            "<div class='tutorial-step-title'>Step {} of {}: {}</div>".format(
                step_idx + 1, total_steps, escape(str(step.get("title", "")))
            ),
            unsafe_allow_html=True,
        )
        st.progress((step_idx + 1) / total_steps)
        if total_steps > 1:
            def _format_step_label(idx: int) -> str:
                title = str(TUTORIAL_STEPS[idx].get("title", "Step"))
                return f"{idx + 1}. {title}"

            raw_furthest = st.session_state.tutorial_metadata.get("furthest_step", step_idx)
            try:
                furthest_idx = int(raw_furthest)
            except (TypeError, ValueError):
                furthest_idx = step_idx
            max_allowed = max(step_idx, furthest_idx)
            slider_options = list(range(max_allowed + 1))
            jump_selection = st.select_slider(
                "Navigate to a step",
                options=slider_options,
                value=step_idx,
                format_func=_format_step_label,
                key="tutorial_step_selector",
            )
            if len(slider_options) < total_steps:
                st.caption(
                    "Complete the current content to unlock the remaining tutorial steps."
                )
            if jump_selection != step_idx:
                st.session_state.tutorial_step = int(jump_selection)
                st.rerun()
        description = step.get("description")
        if isinstance(description, str):
            st.markdown(description)
        _render_tutorial_visual(str(step.get("visual", "")))

        interaction = step.get("interaction") if isinstance(step, dict) else None
        can_proceed = True
        identity_ready = True
        if isinstance(interaction, dict):
            itype = (interaction.get("type") or "").lower()
            if itype == "radio":
                options = interaction.get("options") or []
                prompt = interaction.get("prompt", "")
                radio_key = f"tutorial_radio_{step_idx}"
                if options:
                    selection = st.radio(prompt, options, index=None, key=radio_key)
                    if selection is None:
                        can_proceed = False
                    elif selection == interaction.get("answer"):
                        st.success(interaction.get("success", "Correct."))
                    else:
                        st.warning(interaction.get("failure", "Give it another try."))
                        can_proceed = False
                else:
                    st.info(prompt)
            elif itype == "checkbox_group":
                items = interaction.get("items") or []
                if items:
                    states: list[bool] = []
                    for idx, item_prompt in enumerate(items):
                        cb_key = f"tutorial_checkbox_{step_idx}_{idx}"
                        states.append(st.checkbox(item_prompt, key=cb_key))
                    if all(states):
                        st.success(interaction.get("success", "Great!"))
                    else:
                        st.info(interaction.get("instruction", "Mark each item when you're ready."))
                        can_proceed = False
            elif itype == "text_confirm":
                prompt = interaction.get("prompt", "")
                text_key = f"tutorial_text_{step_idx}"
                value = st.text_input(prompt, key=text_key)
                if not value:
                    can_proceed = False
                elif value.strip().upper() == str(interaction.get("answer", "")).upper():
                    st.success(interaction.get("success", "All set!"))
                else:
                    st.warning(interaction.get("failure", "Double-check the confirmation word."))
                    can_proceed = False

        if step_idx == total_steps - 1:
            st.markdown("#### Personalise your agent identity")
            identity_cols = st.columns(2)
            with identity_cols[0]:
                first_input = st.text_input(
                    "First name",
                    key="agent_first_name",
                    placeholder="e.g. Alex",
                    help="This name personalises reports and cloud contributions.",
                )
            with identity_cols[1]:
                last_input = st.text_input(
                    "Last name",
                    key="agent_last_name",
                    placeholder="e.g. Johnson",
                    help="Used to tag your datasets when collaborating with peers.",
                )

            first_value = _normalize_agent_name(first_input)
            last_value = _normalize_agent_name(last_input)

            if first_value != first_input:
                st.session_state.agent_first_name = first_value
            if last_value != last_input:
                st.session_state.agent_last_name = last_value

            if first_value != _persistent_settings_cache.get("agent_first_name", ""):
                _persist_setting("agent_first_name")
            if last_value != _persistent_settings_cache.get("agent_last_name", ""):
                _persist_setting("agent_last_name")

            identity_ready = bool(first_value and last_value)
            if not identity_ready:
                st.warning("Please provide both your first and last name to finish the tour.")

        can_proceed = can_proceed and identity_ready

        nav_cols = st.columns([1.2, 1, 1, 1])
        with nav_cols[0]:
            if st.button("Skip tutorial", key=f"tutorial_skip_{step_idx}"):
                _mark_tutorial_completion("skipped")
        with nav_cols[1]:
            if st.button("Back", disabled=step_idx == 0, key=f"tutorial_back_{step_idx}"):
                st.session_state.tutorial_step = max(0, step_idx - 1)
                st.rerun()
        with nav_cols[2]:
            st.markdown(
                "<div class='tutorial-footnote'>Progress {}/{}</div>".format(
                    step_idx + 1, total_steps
                ),
                unsafe_allow_html=True,
            )
        next_label = "Finish" if step_idx == total_steps - 1 else "Next"
        with nav_cols[3]:
            if st.button(next_label, disabled=not can_proceed, key=f"tutorial_next_{step_idx}"):
                if step_idx == total_steps - 1:
                    _mark_tutorial_completion("completed")
                else:
                    st.session_state.tutorial_step = min(total_steps - 1, step_idx + 1)
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ────────────────────── SESSION STATE ────────────────────────
def _init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

_init_state("case", {})
_init_state("uploads", [])
_init_state("log_uploads", [])
_init_state("screenshots", [])
_init_state("email_type", "Recap (Customer)")
_init_state("email_extra", {})
_init_state("include_escalations", False)
_init_state("include_hardware", False)
_init_state("debug_auth", False)
_init_state("debug_mode", _get_persistent_default("debug_mode", False))
_init_state("frutiger_aero_mode", _get_persistent_default("frutiger_aero_mode", False))
_init_state(
    "autosave_to_database", _get_persistent_default("autosave_to_database", False)
)
_init_state("_autosave_loaded", False)
_init_state("openai_api_key", _get_persistent_default("openai_api_key", DEFAULT_OPENAI_API_KEY))
_init_state("openai_model", _get_persistent_default("openai_model", "gpt-5-nano"))
_init_state("ai_base_url", _get_persistent_default("ai_base_url", DEFAULT_AI_BASE_URL))
_init_state("ai_mode", _get_persistent_default("ai_mode", DEFAULT_AI_MODE))
_init_state("local_ai_profile", _get_persistent_default("local_ai_profile", "speed"))
_init_state(
    "enable_holiday_theme", _get_persistent_default("enable_holiday_theme", True)
)
_init_state("dark_mode_enabled", _get_persistent_default("dark_mode_enabled", False))
_init_state("theme_preview", "auto")
_init_state("api_helpjuice", False)
_init_state("api_restart", False)
_init_state("api_scan_time", False)
_init_state("generated_email", "")
if "kiroshi_chat_history" not in st.session_state:
    st.session_state.kiroshi_chat_history = load_memory()
_init_state("case_chat_histories", {})
_init_state("case_chat_meta", {})
if "assistant_notes" not in st.session_state:
    st.session_state.assistant_notes = get_assistant_notes()
if "manual_docs" not in st.session_state:
    st.session_state.manual_docs = load_manual_docs()
_init_state("verify_result", "")
_init_state("ask_result", "")
_init_state("categorizer_result", "")
_init_state("categorizer_summary", {})
_init_state("system_prompt", SYSTEM_PROMPT)
_init_state("personality_mode", "utility")
_init_state("ai_assist_result", "")
_init_state("ai_autocorrect_result", "")
_init_state("ai_autocorrect_case_json", {})
_init_state("qa_verification", {})
_init_state("qa_verification_score", None)
_init_state("taxonomy_block", DEFAULT_TAXONOMY_BLOCK)
_init_state("signals_config", DEFAULT_SIGNALS_CONFIG)
_init_state("dashboard_load_notice", None)
_init_state("ai_assist_mode", _get_persistent_default("ai_assist_mode", "Standard"))
_init_state("ai_educate_enabled", _get_persistent_default("ai_educate_enabled", False))
_init_state(
    "ai_educate_report_enabled",
    _get_persistent_default("ai_educate_report_enabled", False),
)
_init_state(
    "ai_educate_advanced",
    _get_persistent_default("ai_educate_advanced", False),
)
_init_state(
    "agent_first_name",
    _get_persistent_default("agent_first_name", ""),
)
_init_state(
    "agent_last_name",
    _get_persistent_default("agent_last_name", ""),
)
_init_state(
    "kiroshi_cloud_enabled",
    _get_persistent_default("kiroshi_cloud_enabled", False),
)
_init_state(
    "kiroshi_cloud_username",
    _get_persistent_default("kiroshi_cloud_username", ""),
)
_init_state(
    "kiroshi_cloud_token",
    _get_persistent_default("kiroshi_cloud_token", ""),
)
_init_state("kiroshi_cloud_password", "")
_init_state("kiroshi_cloud_authenticated", False)
_init_state("kiroshi_cloud_status", None)
_init_state("kiroshi_cloud_summary", None)
_init_state("kiroshi_cloud_saved_at", None)
_init_state("_midday_cloud_sync_last_run_date", "")
_init_state("_midday_cloud_sync_status", None)
_init_state("kiroshi_cloud_peers", [])
_init_state("kiroshi_cloud_selected_agents", [])
_init_state("ai_learning_data", None)
_init_state("ai_learning_signature", None)
_init_state("ai_learning_matches", [])
_init_state("ai_bug_report", None)
_init_state(
    "attachments_directory",
    _get_persistent_default("attachments_directory", str(CASE_ATTACHMENTS_ROOT)),
)
_init_state(
    "wellness_reminders",
    _normalize_wellness_settings(
        _get_persistent_default("wellness_reminders", DEFAULT_WELLNESS_SETTINGS)
    ),
)
_tutorial_meta_default = _get_persistent_default(
    "tutorial_metadata", PERSISTENT_SETTINGS_DEFAULTS["tutorial_metadata"]
)
if isinstance(_tutorial_meta_default, dict):
    _tutorial_meta_default = deepcopy(_tutorial_meta_default)
else:
    _tutorial_meta_default = deepcopy(PERSISTENT_SETTINGS_DEFAULTS["tutorial_metadata"])
_init_state("tutorial_metadata", _tutorial_meta_default)
# Tracking related state
_init_state("track_case", False)
_init_state("tracking_info", {})
# 2nd line mode and callback e‑mail options
_init_state("second_line_mode", _get_persistent_default("second_line_mode", False))
_init_state("case_compact_mode", _get_persistent_default("case_compact_mode", False))
_init_state("show_kiroshi_chat", _get_persistent_default("show_kiroshi_chat", True))
_init_state(
    "kiroshi_sarcasm_mode",
    _get_persistent_default("kiroshi_sarcasm_mode", False),
)
_init_state("tutorial_completed", _get_persistent_default("tutorial_completed", False))
_init_state(
    "tutorial_completed_at",
    _get_persistent_default("tutorial_completed_at", ""),
)
_init_state(
    "tutorial_completion_type",
    _get_persistent_default("tutorial_completion_type", ""),
)
_init_state("show_tutorial", False)
_init_state("payday_last_notified", "")
_init_state("tutorial_step", 0)
_init_state("pending_load", None)
_init_state("show_bored", False)
_init_state("autosave_notice", None)
_init_state("update_status", None)
_init_state("update_status_checked_at", None)
_init_state("update_apply_feedback", None)
_init_state("render_failure_detected", False)
_init_state("error_modal_open", False)
_init_state("failure_modal_message", None)
_init_state("incident_context", None)
_init_state("reporter_open", False)
_init_state("reporter_allow_screenshot", True)
_init_state("incident_reporter_description", "")
_init_state("incident_reporter_pdf", None)
_init_state("incident_reporter_capture_error", None)
_init_state("incident_reporter_screenshot", None)
_init_state("incident_helpjuice_outline", None)
_init_state("reporter_source", "auto")
_init_state("last_rendered_tab", "Dashboard")
_init_state("last_rendered_case", None)
_init_state(
    "bored_game",
    {
        "gold": 0,
        "exp": 0,
        "lexp": 0,
        "level": 0,
        "power_ranking": "The Village Punchbag (It's a job, i guess )",
        "story": "",
    },
)

if "enable_holiday_theme" in _THEME_QUERY_OVERRIDES:
    st.session_state.enable_holiday_theme = bool(
        _THEME_QUERY_OVERRIDES["enable_holiday_theme"]
    )
if "dark_mode_enabled" in _THEME_QUERY_OVERRIDES:
    st.session_state.dark_mode_enabled = bool(
        _THEME_QUERY_OVERRIDES["dark_mode_enabled"]
    )
if "theme_preview" in _THEME_QUERY_OVERRIDES:
    st.session_state.theme_preview = str(_THEME_QUERY_OVERRIDES["theme_preview"])

today = datetime.now()
if today.day == 20:
    today_key = today.strftime("%Y-%m-%d")
    if st.session_state.payday_last_notified != today_key:
        payday_message = "It's pay day!"
        if hasattr(st, "toast"):
            st.toast(payday_message)
        else:
            st.info(payday_message)
        st.session_state.payday_last_notified = today_key

if not st.session_state.tutorial_completed and not st.session_state.show_tutorial:
    st.session_state.show_tutorial = True
    st.session_state.tutorial_step = 0

inject_base_styles()
render_logo()
render_onboarding_tutorial()

if st.session_state.autosave_notice:
    st.success(st.session_state.autosave_notice)
    st.session_state.autosave_notice = None


def sanitize_case_id(case_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", case_id.strip())
    return safe_id or "case"


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename preserving extension when possible."""

    name = Path(filename).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return sanitized or "file"


def _ensure_autosave_dir() -> Path:
    autosave_dir = Path(AUTOSAVE_DIR)
    autosave_dir.mkdir(parents=True, exist_ok=True)
    return autosave_dir


def _get_active_case_id() -> str:
    case_obj = st.session_state.get("case")
    case_id_value: object | None = None
    if isinstance(case_obj, Mapping):
        case_id_value = case_obj.get("case_id")
    else:
        case_id_value = getattr(case_obj, "case_id", None)

    if isinstance(case_id_value, str) and case_id_value.strip():
        return case_id_value

    return "case"


def _extract_case_id(payload: Mapping[str, object] | object | None) -> str:
    if isinstance(payload, Mapping):
        candidate = payload.get("case")
    else:
        candidate = getattr(payload, "case", None)

    if isinstance(candidate, Mapping):
        value = candidate.get("case_id")
    else:
        value = getattr(candidate, "case_id", None)

    if isinstance(value, str) and value.strip():
        return value

    return _get_active_case_id()


def _autosave_path(case_id: str, session_id: str | None = None) -> Path:
    safe_case_id = sanitize_case_id(case_id)
    target_session = session_id or _AUTOSAVE_SESSION_ID
    filename = f"autosave_{safe_case_id}_{target_session}.json"
    return _ensure_autosave_dir() / filename


def _iter_case_autosaves(case_id: str) -> list[Path]:
    safe_case_id = sanitize_case_id(case_id)
    autosave_dir = Path(AUTOSAVE_DIR)
    if not autosave_dir.exists():
        return []

    # Bolt Optimization: Replace glob + stat with os.scandir for faster iteration
    # especially when the autosave directory grows large.
    prefix = f"autosave_{safe_case_id}_"
    suffix = ".json"
    candidates = []

    try:
        with os.scandir(str(autosave_dir)) as entries:
            for entry in entries:
                name = entry.name
                if name.startswith(prefix) and name.lower().endswith(suffix) and entry.is_file():
                    try:
                        # entry.stat() is cached on Windows from scandir result
                        mtime = entry.stat().st_mtime
                        candidates.append((mtime, Path(entry.path)))
                    except OSError:
                        continue
    except OSError:
        return []

    return [path for _, path in sorted(candidates, key=lambda item: item[0], reverse=True)]


def _resolve_latest_autosave(case_id: str) -> Path | None:
    candidates = _iter_case_autosaves(case_id)
    if candidates:
        return candidates[0]

    legacy_path = Path(AUTOSAVE_FILE)
    return legacy_path if legacy_path.exists() else None


def cleanup_case_autosaves(case_id: str | None) -> None:
    if not case_id:
        return

    for path in _iter_case_autosaves(case_id):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logging.debug("Unable to remove autosave file %s", path)

    legacy_path = Path(AUTOSAVE_FILE)
    if legacy_path.exists():
        try:
            legacy_path.unlink()
        except OSError:
            logging.debug("Unable to remove legacy autosave file %s", legacy_path)


def load_autosave():
    global _last_autosave_hash, _last_autosave_timestamp

    if st.session_state._autosave_loaded:
        return
    case_id = _get_active_case_id()
    autosave_path = _resolve_latest_autosave(case_id)
    if autosave_path and autosave_path.exists():
        try:
            with open(autosave_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            st.session_state.case = data.get("case", st.session_state.get("case", {}))
        except Exception:
            pass
    st.session_state._autosave_loaded = True


load_autosave()


def tail_log(path: str | Path, lines: int = 100) -> str:
    """Return the last N lines from a log file."""

    candidate = Path(path)
    if not candidate.is_absolute():
        if LOG_DIR is not None:
            candidate = LOG_DIR / candidate
        else:
            candidate = Path.cwd() / candidate
    try:
        with candidate.open("r", encoding="utf-8") as f:
            return "".join(f.readlines()[-lines:])
    except FileNotFoundError:
        return "Log file not found."
    except OSError as exc:
        return f"Unable to read log file: {exc}"

# ───────────────── DATA MODEL ──────────────────


def _format_utc_timestamp(value: datetime) -> str:
    """Serialize a :class:`datetime` to an ISO-8601 string with a ``Z`` suffix."""

    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _utc_now_z() -> str:
    """Return the current UTC time in ISO-8601 format with a ``Z`` suffix."""

    return _format_utc_timestamp(datetime.now(timezone.utc))


def _normalize_hardware_test_text(value: object) -> str:
    """Return a text representation for stored hardware test values."""

    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return ""
    text = str(value).strip()
    return text


@dataclass
class RemoteSessionEntry:
    """Structured representation of a remote troubleshooting session."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    notes: str = ""
    created_at: str = field(default_factory=_utc_now_z)
    updated_at: str = field(default_factory=_utc_now_z)

    def display_title(self, index: int) -> str:
        """Return a human-friendly title, falling back to an indexed label."""

        title = (self.title or "").strip()
        return title or f"Session {index}"

    def touch(self) -> None:
        """Refresh the ``updated_at`` timestamp to the current moment."""

        self.updated_at = _utc_now_z()


def _coerce_remote_session_entry(
    payload: object, *, default_title: str
) -> RemoteSessionEntry:
    """Return a ``RemoteSessionEntry`` built from loose mapping data."""

    if isinstance(payload, RemoteSessionEntry):
        entry = RemoteSessionEntry(
            session_id=(payload.session_id or uuid.uuid4().hex),
            title=str(payload.title or default_title),
            notes=str(payload.notes or ""),
            created_at=str(payload.created_at or _utc_now_z()),
            updated_at=str(payload.updated_at or payload.created_at or _utc_now_z()),
        )
    elif isinstance(payload, Mapping):
        created = payload.get("created_at")
        created_str = str(created or "")
        if not created_str:
            created_str = _utc_now_z()
        updated = payload.get("updated_at")
        updated_str = str(updated or "")
        if not updated_str:
            updated_str = created_str
        entry = RemoteSessionEntry(
            session_id=str(payload.get("session_id") or uuid.uuid4().hex),
            title=str(payload.get("title") or default_title),
            notes=str(payload.get("notes") or ""),
            created_at=created_str,
            updated_at=updated_str,
        )
    elif isinstance(payload, str):
        entry = RemoteSessionEntry(title=default_title, notes=payload)
    else:
        entry = RemoteSessionEntry(title=default_title)

    if not entry.title.strip():
        entry.title = default_title

    if not entry.created_at:
        entry.created_at = _utc_now_z()
    if not entry.updated_at:
        entry.updated_at = entry.created_at

    return entry


def _normalize_remote_session_list(
    raw_sessions: Iterable[object] | None,
) -> list[RemoteSessionEntry]:
    """Convert raw session payloads into dataclass entries."""

    if not raw_sessions:
        return []
    if isinstance(raw_sessions, (str, bytes)):
        return []

    normalized: list[RemoteSessionEntry] = []
    for payload in raw_sessions:
        default_title = f"Session {len(normalized) + 1}"
        normalized.append(
            _coerce_remote_session_entry(payload, default_title=default_title)
        )
    return normalized


def format_remote_sessions_summary(
    sessions: Sequence[RemoteSessionEntry], *, include_timestamps: bool = True
) -> str:
    """Combine remote session notes into a readable multi-session summary."""

    if not sessions:
        return ""

    show_titles = len(sessions) > 1 or any(
        session.title.strip()
        and session.title.strip().lower() != f"session {index}"
        for index, session in enumerate(sessions, start=1)
    )

    blocks: list[str] = []
    for idx, session in enumerate(sessions, start=1):
        title = session.display_title(idx)
        notes = (session.notes or "").strip()
        if show_titles:
            header = title
            if include_timestamps:
                created = (session.created_at or "").strip()
                updated = (session.updated_at or "").strip()
                timestamp_bits: list[str] = []
                if created:
                    timestamp_bits.append(f"started {created}")
                if updated and updated != created:
                    timestamp_bits.append(f"updated {updated}")
                if timestamp_bits:
                    header = f"{header} ({', '.join(timestamp_bits)})"
            block = header if not notes else f"{header}\n{notes}"
        else:
            block = notes
        blocks.append(block.strip())

    return "\n\n".join(part for part in blocks if part).strip()


@dataclass
class TrackingData:
    """Metadata stored for active tracking in a case JSON file."""

    active: bool = False
    type: str = ""
    category: str = ""
    status: str = ""
    priority: str = DEFAULT_TRACKING_PRIORITY
    ticket_number: str = ""
    creation_day: str = ""
    case_link: str = ""
    expected_arrival_date: str = ""
    service_tag: str = ""

    def __post_init__(self) -> None:
        if self.priority not in PRIORITY_OPTIONS:
            self.priority = DEFAULT_TRACKING_PRIORITY
        # Ensure text fields never contain ``None`` when loaded from legacy JSON.
        for field_name in (
            "type",
            "category",
            "status",
            "ticket_number",
            "creation_day",
            "case_link",
            "expected_arrival_date",
            "service_tag",
        ):
            value = getattr(self, field_name)
            if value is None:
                setattr(self, field_name, "")


def _normalize_damage_classification(value: object) -> str:
    """Return a human readable scanner damage classification."""

    if value is None:
        return ""

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        normalized = text.lower()
        if normalized in {"accidental", "accidental damage", "y", "yes", "true", "1"}:
            return "Accidental damage"
        if normalized in {"internal", "internal damage", "n", "no", "false", "0", "none"}:
            return "Internal damage"
        return text

    if isinstance(value, bool):
        return "Accidental damage" if value else "Internal damage"

    if isinstance(value, (int, float)):
        return "Accidental damage" if value else "Internal damage"

    text = str(value).strip()
    return text if text else ""


@dataclass
class SprintTask:
    case_id: str
    company: str
    priority: str
    status: str  # "Pending", "In Progress", "Completed"
    is_escalated: bool
    source_path: str = ""
    root_cause: str = ""
    solution: str = ""
    ai_suggestion: str = ""
    ai_time_estimate: str = ""


@dataclass
class SprintState:
    date: str
    tasks: list[SprintTask] = field(default_factory=list)
    is_active: bool = False


@dataclass
class CaseData:
    """Container for case details provided through the UI."""

    # General case
    company_name: str = ""
    subscription_id: str = ""
    brief_description: str = ""
    case_id: str = ""
    application_version: str = ""
    description: str = ""
    caller_name: str = ""
    phone_description: str = ""
    dongle_number: str = ""
    phone_number: str = ""
    teamviewer_id: str = ""
    teamviewer_password: str = ""
    email: str = ""
    internal_helpjuice: str = ""
    internal_logs: str = ""
    remote_sessions: list[RemoteSessionEntry] = field(default_factory=list)
    remote_steps: str = ""
    root_cause: str = ""
    repro_steps: str = ""
    third_line_hj_article: str = ""
    third_line_troubleshoot_summary: str = ""
    third_line_comments: str = ""
    third_line_reseller_name: str = ""
    third_line_reseller_phone: str = ""
    third_line_reseller_phone_alt: str = ""
    third_line_reseller_email: str = ""
    third_line_clinic_rep_name: str = ""
    third_line_clinic_rep_phone: str = ""
    third_line_clinic_rep_phone_alt: str = ""
    third_line_tv_id: str = ""
    third_line_tv_password: str = ""
    third_line_unite_pin: str = ""

    solution: str = ""
    survey_link: str = ""
    # Escalation details
    request_issue: str = ""
    contact_name: str = ""
    office_ph: str = ""
    direct_ph: str = ""
    best_time: str = ""
    patterson: str = ""
    straumann: str = ""
    esc_name: str = ""
    esc_ph: str = ""
    esc_email: str = ""
    # Additional information
    additional_info: str = ""
    customer_trios_only: bool = False
    support_fee_accepted: bool = False
    hardware_test: str = ""
    # PC hardware
    service_tag: str = ""
    pc_model: str = ""
    windows_version: str = ""
    bios_version: str = ""
    graphics_card: str = ""
    processor: str = ""
    warranty: str = ""
    # Scanner hardware
    scanner_sn: str = ""
    base_sn: str = ""
    trios_module_version: str = ""
    dongle_deployment_date: str = ""
    scanner_previous_replacements: int = 0
    scanner_accidental_damage: str = ""
    hardware_dongle_replaced: str = ""
    hardware_latest_deployment_date: str = ""
    hardware_scanner_replaced: str = ""
    hardware_scanner_sn_summary: str = ""
    hardware_subscription_type: str = ""
    # Dell escalation specifics
    dell_issue_start_date: str = ""
    dell_command_updates_status: str = ""
    dell_power_options_setup: str = ""
    dell_optimizer_setup: str = ""
    dell_intel_ppm_installed: str = ""
    dell_cpu_speed_or_throttling: str = ""
    dell_gpu_usage_integrated: str = ""
    dell_gpu_usage_dedicated: str = ""
    dell_cpu_utilization: str = ""
    dell_benchmark_results: str = ""
    dell_ultra_resolution_support: str = ""
    dell_gpu_driver_versions: str = ""
    dell_reliability_monitor_results: str = ""
    dell_diagnostics_results: str = ""
    dell_windows_reimaged: str = ""
    clinic_name: str = ""
    clinic_contact_name: str = ""
    clinic_contact_phone: str = ""
    clinic_contact_email: str = ""
    clinic_address_line_1: str = ""
    clinic_address_line_2: str = ""
    clinic_city: str = ""
    clinic_state: str = ""
    clinic_postal_code: str = ""
    tracking: TrackingData = field(default_factory=TrackingData)
    kiroshi_version: str = VERSION
    last_modified: str = ""

    def __post_init__(self) -> None:
        self.hardware_test = _normalize_hardware_test_text(self.hardware_test)

        if self.remote_steps is None:
            self.remote_steps = ""
        else:
            self.remote_steps = str(self.remote_steps)

        sessions_source: Iterable[object] | None
        if isinstance(self.remote_sessions, Iterable) and not isinstance(
            self.remote_sessions, (str, bytes)
        ):
            sessions_source = self.remote_sessions
        else:
            sessions_source = []
        normalized_sessions = _normalize_remote_session_list(sessions_source)
        if not normalized_sessions and self.remote_steps.strip():
            now = _utc_now_z()
            normalized_sessions = [
                RemoteSessionEntry(
                    title="Session 1",
                    notes=self.remote_steps,
                    created_at=now,
                    updated_at=now,
                )
            ]
        self.remote_sessions = normalized_sessions
        self.remote_steps = format_remote_sessions_summary(
            self.remote_sessions, include_timestamps=True
        )
        if not isinstance(self.tracking, TrackingData):
            if isinstance(self.tracking, Mapping):
                self.tracking = TrackingData(**self.tracking)  # type: ignore[arg-type]
            else:
                self.tracking = TrackingData()
        if not self.kiroshi_version:
            self.kiroshi_version = VERSION
        if self.tracking.priority not in PRIORITY_OPTIONS:
            self.tracking.priority = DEFAULT_TRACKING_PRIORITY
        if self.last_modified is None:
            self.last_modified = ""
        elif not isinstance(self.last_modified, str):
            self.last_modified = str(self.last_modified)

        self.scanner_accidental_damage = _normalize_damage_classification(
            getattr(self, "scanner_accidental_damage", "")
        )


def extract_remote_steps_from_mapping(record: object | None) -> str:
    """Return a normalized troubleshooting summary from legacy payloads."""

    if record is None:
        return ""

    getter = getattr(record, "get", None)
    if getter is None:
        return ""

    raw_steps = getter("remote_steps")
    if isinstance(raw_steps, str) and raw_steps.strip():
        return raw_steps.strip()

    raw_sessions = getter("remote_sessions")
    if isinstance(raw_sessions, Iterable) and not isinstance(
        raw_sessions, (str, bytes)
    ):
        sessions = _normalize_remote_session_list(raw_sessions)
        return format_remote_sessions_summary(sessions, include_timestamps=True)

    return ""


def ensure_remote_session_entries(case: CaseData) -> None:
    """Guarantee that a case has at least one remote session entry."""

    if case.remote_sessions:
        return
    now = _utc_now_z()
    case.remote_sessions = [
        RemoteSessionEntry(
            title="Session 1",
            notes="",
            created_at=now,
            updated_at=now,
        )
    ]
    case.remote_steps = format_remote_sessions_summary(case.remote_sessions)


def update_case_remote_sessions(
    case: CaseData, sessions: Sequence[RemoteSessionEntry]
) -> None:
    """Persist a new set of remote session entries to the active case."""

    normalized = _normalize_remote_session_list(sessions)
    case.remote_sessions = normalized
    case.remote_steps = format_remote_sessions_summary(
        normalized, include_timestamps=True
    )
    st.session_state["remote_sessions"] = [asdict(entry) for entry in normalized]
    st.session_state["remote_steps"] = case.remote_steps
    touch_case_last_modified()
    autosave()


def ensure_single_remote_session(case: CaseData) -> RemoteSessionEntry:
    """Return the primary remote session entry, collapsing legacy multiples."""

    ensure_remote_session_entries(case)
    sessions = list(case.remote_sessions)
    if not sessions:
        ensure_remote_session_entries(case)
        sessions = list(case.remote_sessions)

    if len(sessions) == 1:
        return sessions[0]

    timeline = format_remote_sessions_summary(sessions, include_timestamps=True)
    primary = sessions[0]
    merged = RemoteSessionEntry(
        session_id=primary.session_id or uuid.uuid4().hex,
        title=(primary.title or "Session 1"),
        notes=timeline,
        created_at=(primary.created_at or _utc_now_z()),
        updated_at=_utc_now_z(),
    )
    update_case_remote_sessions(case, [merged])
    return case.remote_sessions[0]


@dataclass
class InMemoryUploadedFile:
    """Simple file-like container for generated screenshots."""

    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return self.data


@dataclass
class ScreenshotAsset(InMemoryUploadedFile):
    """Rich metadata container for captured screenshots."""

    label: str = ""
    capture_mode: str = "full"
    captured_at: str = field(default_factory=_utc_now_z)
    origin: str = "capture"
    content_type: str = "image/png"

    def __post_init__(self) -> None:
        safe_name = sanitize_filename(self.name)
        if not safe_name.lower().endswith(".png"):
            safe_name = f"{safe_name}.png"
        object.__setattr__(self, "name", safe_name)
        object.__setattr__(self, "label", (self.label or Path(safe_name).stem).strip())
        if not self.label:
            object.__setattr__(self, "label", Path(safe_name).stem)
        mode = (self.capture_mode or "capture").strip().lower()
        object.__setattr__(self, "capture_mode", mode or "capture")
        object.__setattr__(self, "origin", (self.origin or "capture").strip() or "capture")
        if not self.captured_at:
            object.__setattr__(self, "captured_at", _utc_now_z())

    def metadata(self, *, path: str) -> dict[str, str]:
        record = {
            "name": self.name,
            "path": path,
            "label": self.label,
            "captured_at": self.captured_at,
            "capture_mode": self.capture_mode,
            "origin": self.origin,
        }
        if self.content_type:
            record["content_type"] = self.content_type
        return record


def _apply_secure_blur(image: object) -> object | None:
    """Apply a secure blur to text in the image, preserving numbers.

    Requires Tesseract OCR to distinguish letters from numbers.
    Returns None if the blur operation fails (fail-closed) to avoid leaking data.
    """
    if not PYTESSERACT_AVAILABLE or pytesseract is None:
        logging.warning("Secure blur requested but pytesseract is not installed.")
        return None

    if PILImage is None or not isinstance(image, PILImage.Image):
        return None

    try:
        # Detect text
        data = pytesseract.image_to_data(image, output_type=Output.DICT)

        # Convert to RGBA for processing if needed, though blur works on RGB
        processed = image.copy()

        n_boxes = len(data["text"])
        for i in range(n_boxes):
            if int(data["conf"][i]) > 40:  # Confidence threshold
                text = data["text"][i].strip()
                if not text:
                    continue

                # "Numbers must not be blurry, only letters"
                if re.search(r"[a-zA-Z]", text):
                    (x, y, w, h) = (
                        data["left"][i],
                        data["top"][i],
                        data["width"][i],
                        data["height"][i],
                    )

                    # Crop the region
                    region = processed.crop((x, y, x + w, y + h))

                    # Blur it using Gaussian as requested
                    blurred_region = region.filter(ImageFilter.GaussianBlur(radius=5))

                    # Paste back
                    processed.paste(blurred_region, (x, y))

        return processed

    except Exception as exc:
        logging.error("Secure blur failed: %s", exc)
        return None


class ScreenshotService:
    """State-aware manager that owns screenshot capture and hydration logic."""

    def __init__(self, *, state_key: str = "screenshots") -> None:
        self.state_key = state_key

    @staticmethod
    def _queue_screenshot_upload(asset: ScreenshotAsset) -> None:
        """Create an upload entry for ``asset`` so evidence queues stay in sync."""

        uploads = st.session_state.get("uploads")
        if isinstance(uploads, list):
            target = uploads
        else:  # pragma: no cover - defensive path for unexpected state
            target = []

        staged = InMemoryUploadedFile(asset.name, asset.getvalue())
        target.append(staged)
        st.session_state["uploads"] = target

    def _coerce(self, items: Iterable[object]) -> list[ScreenshotAsset]:
        normalised: list[ScreenshotAsset] = []
        for item in items:
            asset = _ensure_screenshot_asset(item)
            if asset is not None:
                normalised.append(asset)
        return normalised

    def replace(self, items: Iterable[object]) -> list[ScreenshotAsset]:
        normalised = self._coerce(items)
        st.session_state[self.state_key] = normalised
        return normalised

    def assets(self) -> list[ScreenshotAsset]:
        existing = st.session_state.get(self.state_key, [])
        if isinstance(existing, list):
            return self.replace(existing)
        return self.replace([])

    def append(self, asset: ScreenshotAsset) -> list[ScreenshotAsset]:
        assets = list(self.assets())
        assets.append(asset)
        st.session_state[self.state_key] = assets
        return assets

    def clear(self) -> None:
        st.session_state[self.state_key] = []

    def capture_from_ui(
        self,
        mode: Literal["full", "region"],
        *,
        label: str,
        auto_stamp: bool,
        label_state_key: str,
        reset_flag_key: str | None = None,
        secure: bool = False,
    ) -> None:
        existing = self.assets()
        safe_stem, display_label = _generate_screenshot_basename(
            label, auto_stamp=auto_stamp, existing=existing
        )
        if secure:
            display_label += " (Secure)"
            safe_stem += "_secure"

        capture_fn = self.capture_full if mode == "full" else self.capture_region
        shot, error = capture_fn(safe_stem, label=display_label, secure=secure)
        if shot:
            shot.capture_mode = mode
            shot.origin = "capture"
            self.append(shot)
            self._queue_screenshot_upload(shot)
            st.success(f"Captured {mode} screenshot: {shot.label}")
            if reset_flag_key:
                st.session_state[reset_flag_key] = True
            return

        if not error:
            st.warning("Screenshot capture is unavailable in this environment.")
            return

        message = error.strip()
        if "cancel" in message.lower():
            st.info("Screenshot capture cancelled.")
        elif "environment" in message.lower():
            st.warning(message)
        else:
            st.error(message)

    def capture_region(
        self,
        safe_name: str,
        *,
        label: str | None = None,
        secure: bool = False,
    ) -> tuple[ScreenshotAsset | None, str | None]:
        if tk is None or not TK_AVAILABLE:
            return None, (
                "Advanced screenshot selection requires a local display with Tkinter support in this environment."
            )

        if not (PYAUTOGUI_AVAILABLE or IMAGEGRAB_AVAILABLE or MSS_AVAILABLE):
            return None, "Screenshot capture is unavailable in this environment."

        coords, error = select_screen_region()
        if not coords:
            return None, error

        left, top, width, height = coords
        if width <= 0 or height <= 0:
            return None, "No region was selected."

        img = None
        if PYAUTOGUI_AVAILABLE and pyautogui is not None:
            try:
                img = pyautogui.screenshot(  # type: ignore[union-attr]
                    region=(left, top, width, height)
                )
            except Exception as exc:  # pragma: no cover - depends on GUI stack
                logging.warning("pyautogui region capture failed: %s", exc)

        if img is None and IMAGEGRAB_AVAILABLE and ImageGrab is not None:
            try:
                img = ImageGrab.grab(bbox=(left, top, left + width, top + height))  # type: ignore[union-attr]
            except Exception as exc:  # pragma: no cover - depends on GUI stack
                logging.error("ImageGrab region capture failed: %s", exc)
                return None, "Unable to capture the selected region."

        if img is None and MSS_AVAILABLE and mss is not None:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[0]
                    raw = sct.grab(monitor)
                from PIL import Image as PILImage  # type: ignore

                img = PILImage.frombytes("RGB", raw.size, raw.rgb)
                crop_box = (
                    left - monitor.get("left", 0),
                    top - monitor.get("top", 0),
                    left - monitor.get("left", 0) + width,
                    top - monitor.get("top", 0) + height,
                )
                img = img.crop(crop_box)
            except Exception as exc:  # pragma: no cover - depends on GUI stack
                logging.error("mss region capture failed: %s", exc)
                return None, "Unable to capture the selected region."

        if img is None:
            return None, "Unable to capture the selected region."

        if secure:
            img = _apply_secure_blur(img)
            if img is None:
                return None, "Secure blur failed. Ensure Tesseract OCR is installed."

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return (
            ScreenshotAsset(
                name=f"{safe_name}.png",
                data=buf.getvalue(),
                label=label or safe_name,
                capture_mode="region",
            ),
            None,
        )

    def capture_full(
        self,
        safe_name: str,
        *,
        label: str | None = None,
        secure: bool = False,
    ) -> tuple[ScreenshotAsset | None, str | None]:
        img = None
        if PYAUTOGUI_AVAILABLE and pyautogui is not None:
            try:
                img = pyautogui.screenshot()  # type: ignore[union-attr]
            except Exception as exc:  # pragma: no cover - depends on GUI stack
                logging.warning("pyautogui full capture failed: %s", exc)

        if img is None and IMAGEGRAB_AVAILABLE and ImageGrab is not None:
            try:
                img = ImageGrab.grab()  # type: ignore[union-attr]
            except Exception as exc:  # pragma: no cover - depends on GUI stack
                logging.warning("ImageGrab full capture failed: %s", exc)

        if img is None and MSS_AVAILABLE and mss is not None:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[0]
                    raw = sct.grab(monitor)
                from PIL import Image as PILImage  # type: ignore

                img = PILImage.frombytes("RGB", raw.size, raw.rgb)
            except Exception as exc:  # pragma: no cover - depends on GUI stack
                logging.error("mss full capture failed: %s", exc)

        if img is None:
            return None, (
                "Screenshot capture is unavailable in this environment. "
                "For Windows deployments, ensure the exe includes Pillow, pyautogui, or mss."
            )

        if secure:
            img = _apply_secure_blur(img)
            if img is None:
                return None, "Secure blur failed. Ensure Tesseract OCR is installed."

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return (
            ScreenshotAsset(
                name=f"{safe_name}.png",
                data=buf.getvalue(),
                label=label or safe_name,
                capture_mode="full",
            ),
            None,
        )


def _ensure_screenshot_asset(item: object) -> ScreenshotAsset | None:
    """Coerce legacy screenshot payloads into :class:`ScreenshotAsset`."""

    if isinstance(item, ScreenshotAsset):
        return item
    if isinstance(item, InMemoryUploadedFile):
        label = getattr(item, "label", "") or getattr(item, "name", "")
        return ScreenshotAsset(
            name=getattr(item, "name", "screenshot"),
            data=getattr(item, "data", b""),
            label=str(label),
            capture_mode=getattr(item, "capture_mode", "imported"),
            origin=getattr(item, "origin", "legacy"),
        )
    return None


_screenshot_service = ScreenshotService()


def get_active_screenshots() -> list[ScreenshotAsset]:
    """Return the active screenshot list coerced to :class:`ScreenshotAsset`."""

    return _screenshot_service.assets()


def set_active_screenshots(items: Iterable[object]) -> list[ScreenshotAsset]:
    """Replace the in-memory screenshot cache with ``items`` and normalise."""

    return _screenshot_service.replace(items)


def clear_active_screenshots() -> None:
    """Remove all captured screenshots from the in-memory cache."""

    _screenshot_service.clear()


def _generate_screenshot_basename(
    label: str,
    *,
    auto_stamp: bool,
    existing: Sequence[ScreenshotAsset],
) -> tuple[str, str]:
    """Return a sanitized filename stem and display label for the next capture."""

    raw_label = label.strip()
    display_label = raw_label or f"Capture {len(existing) + 1}"
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_label).strip("_").lower()
    if not safe_stem:
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", display_label).strip("_").lower()
    if not safe_stem:
        safe_stem = "capture"
    if auto_stamp:
        safe_stem = f"{safe_stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    existing_stems = {Path(item.name).stem for item in existing}
    candidate = safe_stem
    suffix = 2
    while candidate in existing_stems:
        candidate = f"{safe_stem}_{suffix}"
        suffix += 1
    return candidate, display_label


def _capture_screenshot_from_ui(
    mode: Literal["full", "region"],
    *,
    label: str,
    auto_stamp: bool,
    label_state_key: str,
    reset_flag_key: str | None = None,
    secure: bool = False,
) -> None:
    """Capture a screenshot using the configured UI preferences."""

    _screenshot_service.capture_from_ui(
        mode,
        label=label,
        auto_stamp=auto_stamp,
        label_state_key=label_state_key,
        reset_flag_key=reset_flag_key,
        secure=secure,
    )


def select_screen_region() -> tuple[tuple[int, int, int, int] | None, str | None]:
    """Launch a temporary overlay that lets the user select a screen region."""

    if not TK_AVAILABLE or tk is None:
        return None, "Region selection requires a graphical environment."

    try:
        root = tk.Tk()
    except Exception as exc:  # pragma: no cover - depends on GUI availability
        logging.warning("Unable to initialize Tkinter for region capture: %s", exc)
        return None, "Region selection is unavailable in this environment."

    selection: dict[str, object] = {"start": None, "coords": None, "cancelled": False}

    try:
        root.attributes("-topmost", True)
    except Exception:  # pragma: no cover - platform dependent
        pass
    try:
        root.attributes("-fullscreen", True)
    except Exception:  # pragma: no cover - fallback sizing
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.geometry(f"{width}x{height}+0+0")
    try:
        root.attributes("-alpha", 0.2)
    except Exception:  # pragma: no cover - not all window managers allow transparency
        root.configure(bg="#000000")
    try:
        root.overrideredirect(True)
    except Exception:  # pragma: no cover - some platforms disallow this
        pass

    canvas = tk.Canvas(root, bg="#000000", highlightthickness=0, cursor="crosshair")
    canvas.pack(fill=tk.BOTH, expand=True)

    root.update_idletasks()
    canvas.create_text(
        root.winfo_screenwidth() // 2,
        40,
        text="Click and drag to select the area to capture. Press Esc to cancel.",
        fill="white",
        font=("Helvetica", 14),
    )

    rect_id: int | None = None

    def canvas_coords(x_root: int, y_root: int) -> tuple[int, int]:
        return x_root - root.winfo_rootx(), y_root - root.winfo_rooty()

    def on_button_press(event: "tk.Event[tk.Canvas]") -> None:
        nonlocal rect_id
        selection["start"] = (event.x_root, event.y_root)
        if rect_id is not None:
            canvas.delete(rect_id)
        cx, cy = canvas_coords(event.x_root, event.y_root)
        rect_id = canvas.create_rectangle(cx, cy, cx, cy, outline="red", width=2)

    def on_mouse_move(event: "tk.Event[tk.Canvas]") -> None:
        if selection["start"] is None or rect_id is None:
            return
        start_x, start_y = selection["start"]  # type: ignore[misc]
        cx0, cy0 = canvas_coords(start_x, start_y)
        cx1, cy1 = canvas_coords(event.x_root, event.y_root)
        canvas.coords(rect_id, cx0, cy0, cx1, cy1)

    def on_button_release(event: "tk.Event[tk.Canvas]") -> None:
        start = selection["start"]
        if not isinstance(start, tuple):
            return
        end = (event.x_root, event.y_root)
        left = min(start[0], end[0])
        top = min(start[1], end[1])
        width = abs(end[0] - start[0])
        height = abs(end[1] - start[1])
        if width > 1 and height > 1:
            selection["coords"] = (int(left), int(top), int(width), int(height))
        else:
            selection["coords"] = None
        root.quit()

    def on_cancel(event: object | None = None) -> None:  # pragma: no cover - GUI interaction
        selection["cancelled"] = True
        root.quit()

    canvas.bind("<ButtonPress-1>", on_button_press)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_button_release)
    root.bind("<Escape>", on_cancel)
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    try:
        root.mainloop()
    finally:
        try:
            root.destroy()
        except Exception:  # pragma: no cover - cleanup best effort
            pass

    if selection.get("cancelled"):
        return None, "Region selection cancelled."

    coords = selection.get("coords")
    if not isinstance(coords, tuple):
        return None, "No region was selected."
    return coords, None


def capture_region_screenshot(
    safe_name: str,
    *,
    label: str | None = None,
) -> tuple[ScreenshotAsset | None, str | None]:
    """Capture a cropped screenshot using the interactive region selector."""

    return _screenshot_service.capture_region(safe_name, label=label)


def capture_full_screenshot(
    safe_name: str,
    *,
    label: str | None = None,
) -> tuple[ScreenshotAsset | None, str | None]:
    """Capture a full screen screenshot with multiple fallbacks."""

    return _screenshot_service.capture_full(safe_name, label=label)


def _default_attachments_index() -> dict[str, list[dict[str, str]]]:
    return {
        "uploads": [],
        "log_uploads": [],
        "screenshots": [],
    }


def _handle_incident_screenshot_result(
    screenshot: "ScreenshotAsset | None", error: str | None
) -> None:
    """Persist screenshot capture outcomes and surface user-facing warnings."""

    if screenshot is not None:
        st.session_state.incident_reporter_screenshot = screenshot
        st.session_state.incident_reporter_capture_error = None
        return

    if not error:
        return

    st.session_state.incident_reporter_capture_error = error
    try:
        st.warning(error)
    except Exception:  # pragma: no cover - Streamlit unavailable during tests
        logging.warning("Incident reporter warning: %s", error)


def _format_incident_context(context: Mapping[str, object] | None) -> str | None:
    """Return the formatted context banner shown in the incident reporter."""

    if not isinstance(context, Mapping):
        return None

    section = context.get("section")
    tab_label = context.get("tab")
    bits = [str(bit).strip() for bit in (section, tab_label) if str(bit).strip()]
    if not bits:
        return None
    return "**Context:** " + " · ".join(bits)


def _set_active_session_attachments_index(
    attachments_index: Mapping[str, Iterable[Mapping[str, object]]] | None,
) -> None:
    """Persist attachment metadata for the active case session."""

    normalised = _normalise_attachments_index(attachments_index)
    st.session_state["attachments_index"] = normalised
    current_shots = get_active_screenshots()

    sessions = st.session_state.get("case_sessions")
    if isinstance(sessions, list) and CURRENT_CASE_IDX < len(sessions):
        session = sessions[CURRENT_CASE_IDX]
        try:
            session.attachments_index = normalised  # type: ignore[attr-defined]
            session.uploads = st.session_state.get("uploads", [])
            session.log_uploads = st.session_state.get("log_uploads", [])
            session.screenshots = current_shots
        except AttributeError:
            pass
    _sync_case_memory_from_sessions()


def _normalise_attachments_index(
    data: Mapping[str, Iterable[Mapping[str, object]]] | Mapping[str, object] | None,
) -> dict[str, list[dict[str, str]]]:
    normalised = _default_attachments_index()
    if not isinstance(data, Mapping):
        return normalised
    allowed_fields = {
        "name",
        "path",
        "label",
        "captured_at",
        "capture_mode",
        "origin",
        "content_type",
    }
    for key in normalised:
        items = data.get(key, [])
        cleaned: list[dict[str, str]] = []
        if isinstance(items, Iterable):
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                name = item.get("name")
                path = item.get("path")
                if not (isinstance(name, str) and isinstance(path, str)):
                    continue
                record: dict[str, str] = {"name": name, "path": path}
                for field in allowed_fields - {"name", "path"}:
                    value = item.get(field)
                    if isinstance(value, str) and value:
                        record[field] = value
                cleaned.append(record)
        normalised[key] = cleaned
    return normalised


MILESTONE_TICK_INTERVAL = timedelta(minutes=3)

MILESTONE_DEFINITIONS = [
    {
        "id": "case_id",
        "label": "Create case",
        "description": "Add the Case ID to mark the case as created.",
        "due": timedelta(minutes=3),
    },
    {
        "id": "document_case",
        "label": "Document case",
        "description": "Share the survey URL and CRM case link.",
        "due": timedelta(hours=2),
    },
    {
        "id": "resolution",
        "label": "Resolve",
        "description": "Close the case or log a replacement within four hours.",
        "due": timedelta(hours=4),
    },
]
MILESTONE_ID_ORDER = [entry["id"] for entry in MILESTONE_DEFINITIONS]


@dataclass
class MilestoneProgressState:
    completed_at: str | None = None
    alerted_at: str | None = None
    completion_actions_done: bool = False
    overdue_actions_done: bool = False


def _default_milestone_progress() -> dict[str, MilestoneProgressState]:
    return {milestone_id: MilestoneProgressState() for milestone_id in MILESTONE_ID_ORDER}


@dataclass
class CaseMilestoneState:
    created_at: str = field(default_factory=_utc_now_z)
    statuses: dict[str, MilestoneProgressState] = field(
        default_factory=_default_milestone_progress
    )


@dataclass
class CaseSession:
    """Container for per-case session state."""

    case: CaseData
    scratch: str = ""
    uploads: list = field(default_factory=list)
    log_uploads: list = field(default_factory=list)
    screenshots: list[ScreenshotAsset] = field(default_factory=list)
    source_path: str = ""
    attachments_index: dict[str, list[dict[str, str]]] = field(
        default_factory=_default_attachments_index
    )
    milestones: CaseMilestoneState = field(default_factory=CaseMilestoneState)


MILESTONE_DEFINITION_LOOKUP = {
    entry["id"]: entry for entry in MILESTONE_DEFINITIONS
}


def _parse_utc_timestamp(value: object | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _coerce_case_milestone_state(payload: object | None) -> CaseMilestoneState:
    if isinstance(payload, CaseMilestoneState):
        state = payload
    elif isinstance(payload, Mapping):
        created_at = str(payload.get("created_at") or _utc_now_z())
        statuses_payload = payload.get("statuses")
        statuses: dict[str, MilestoneProgressState] = {}
        if isinstance(statuses_payload, Mapping):
            for milestone_id, entry in statuses_payload.items():
                if not isinstance(entry, Mapping):
                    continue
                statuses[milestone_id] = MilestoneProgressState(
                    completed_at=str(entry.get("completed_at"))
                    if entry.get("completed_at")
                    else None,
                    alerted_at=str(entry.get("alerted_at"))
                    if entry.get("alerted_at")
                    else None,
                    completion_actions_done=bool(entry.get("completion_actions_done")),
                    overdue_actions_done=bool(entry.get("overdue_actions_done")),
                )
        state = CaseMilestoneState(created_at=created_at, statuses=statuses)
    else:
        state = CaseMilestoneState()

    if not isinstance(state.statuses, dict):
        state.statuses = _default_milestone_progress()

    for milestone_id in MILESTONE_ID_ORDER:
        if milestone_id not in state.statuses:
            state.statuses[milestone_id] = MilestoneProgressState()
    return state


def _ensure_case_milestone_state(session: CaseSession) -> CaseMilestoneState:
    state = _coerce_case_milestone_state(getattr(session, "milestones", None))
    session.milestones = state
    return state


def _milestone_condition_met(
    milestone_id: str, session: CaseSession
) -> bool:
    case = session.case
    tracking = case.tracking
    if milestone_id == "case_id":
        return bool((case.case_id or "").strip())
    if milestone_id == "document_case":
        return bool((case.survey_link or "").strip()) and bool(
            (tracking.case_link or "").strip()
        )
    if milestone_id == "resolution":
        progress = session.milestones.statuses.get(milestone_id)
        return bool(progress and progress.completed_at)
    return False


def _trigger_milestone_alert(case_idx: int, milestone_id: str) -> None:
    label = _case_display_name(case_idx)
    milestone = MILESTONE_DEFINITION_LOOKUP.get(milestone_id, {})
    message = (
        f"⚠️ {label}: {milestone.get('label', milestone_id.title())} overdue. "
        "Complete this milestone ASAP."
    )
    if hasattr(st, "toast"):
        st.toast(message)
    else:
        st.warning(message)


def _auto_track_case_for_documentation(session: CaseSession, case_idx: int) -> None:
    tracking = session.case.tracking
    changed = False
    if tracking.ticket_number != (session.case.case_id or ""):
        tracking.ticket_number = session.case.case_id or ""
        changed = True
    if tracking.category != "Kiroshi Auto Track":
        tracking.category = "Kiroshi Auto Track"
        changed = True
    if tracking.priority != "On Time":
        tracking.priority = "On Time"
        changed = True
    if tracking.type != "Custom":
        tracking.type = "Custom"
        changed = True
    if not tracking.creation_day:
        tracking.creation_day = datetime.now().date().isoformat()
        changed = True
    if not tracking.active:
        tracking.active = True
        changed = True
    if changed:
        st.session_state.track_case = True
        if case_idx == CURRENT_CASE_IDX:
            st.session_state.case.tracking = tracking
        touch_case_last_modified()
        autosave()


def _mark_case_tracking_out_of_timeframe(session: CaseSession, case_idx: int) -> None:
    tracking = session.case.tracking
    changed = False
    if tracking.category != "Out of Timeframe":
        tracking.category = "Out of Timeframe"
        changed = True
    if tracking.priority != "High":
        tracking.priority = "High"
        changed = True
    if not tracking.type:
        tracking.type = "Custom"
        changed = True
    if not tracking.active:
        tracking.active = True
        changed = True
    if changed:
        st.session_state.track_case = True
        if case_idx == CURRENT_CASE_IDX:
            st.session_state.case.tracking = tracking
        touch_case_last_modified()
        autosave()


def _apply_milestone_completion(
    milestone_id: str,
    session: CaseSession,
    case_idx: int,
    progress: MilestoneProgressState,
) -> None:
    if progress.completion_actions_done:
        return
    if milestone_id == "document_case":
        _auto_track_case_for_documentation(session, case_idx)
    progress.completion_actions_done = True


def _apply_milestone_overdue(
    milestone_id: str,
    session: CaseSession,
    case_idx: int,
    progress: MilestoneProgressState,
) -> None:
    if progress.overdue_actions_done:
        return
    if milestone_id == "resolution":
        _mark_case_tracking_out_of_timeframe(session, case_idx)
    progress.overdue_actions_done = True


def _update_case_milestones_for_session(
    session: CaseSession,
    case_idx: int,
    now: datetime,
    *,
    anchor_created_at: datetime | None = None,
) -> None:
    state = _ensure_case_milestone_state(session)
    created_at = (
        anchor_created_at
        or _parse_utc_timestamp(state.created_at)
        or now
    )
    for milestone_id in MILESTONE_ID_ORDER:
        progress = state.statuses[milestone_id]
        if milestone_id in {"case_id", "document_case"}:
            if _milestone_condition_met(milestone_id, session):
                if not progress.completed_at:
                    progress.completed_at = _utc_now_z()
                    _apply_milestone_completion(
                        milestone_id, session, case_idx, progress
                    )
                continue
        if progress.completed_at:
            continue
        milestone_def = MILESTONE_DEFINITION_LOOKUP.get(milestone_id, {})
        due: timedelta | None = milestone_def.get("due")
        if due and now - created_at >= due and not progress.alerted_at:
            progress.alerted_at = _utc_now_z()
            _trigger_milestone_alert(case_idx, milestone_id)
            _apply_milestone_overdue(milestone_id, session, case_idx, progress)


def _maybe_tick_case_milestones() -> None:
    sessions = st.session_state.get("case_sessions")
    if not isinstance(sessions, list) or not sessions:
        return
    visible_indices = [idx for idx in range(len(sessions)) if idx != HIDDEN_CASE_INDEX]
    if not visible_indices:
        return
    anchor_index = visible_indices[0]
    anchor_state = _ensure_case_milestone_state(sessions[anchor_index])
    anchor_created_at = _parse_utc_timestamp(anchor_state.created_at)
    now = datetime.now(timezone.utc)
    if anchor_created_at is None:
        anchor_created_at = now
    st.session_state["milestone_anchor_created_at"] = _format_utc_timestamp(
        anchor_created_at
    )
    last_tick = _parse_utc_timestamp(st.session_state.get("milestone_last_tick"))
    if last_tick and now - last_tick < MILESTONE_TICK_INTERVAL:
        return
    st.session_state["milestone_last_tick"] = _utc_now_z()
    for idx, session in enumerate(sessions):
        if idx == HIDDEN_CASE_INDEX:
            continue
        _update_case_milestones_for_session(
            session,
            idx,
            now,
            anchor_created_at=anchor_created_at,
        )


def _mark_milestone_completed(case_idx: int, milestone_id: str) -> bool:
    sessions = st.session_state.get("case_sessions")
    if not isinstance(sessions, list) or not (0 <= case_idx < len(sessions)):
        return False
    session = sessions[case_idx]
    state = _ensure_case_milestone_state(session)
    progress = state.statuses.get(milestone_id)
    if progress is None:
        progress = MilestoneProgressState()
        state.statuses[milestone_id] = progress
    if not progress.completed_at:
        progress.completed_at = _utc_now_z()
        _apply_milestone_completion(milestone_id, session, case_idx, progress)
        touch_case_last_modified()
        autosave()
    return True


def _handle_resolution_action(case_idx: int, *, replacement: bool = False) -> None:
    if not _mark_milestone_completed(case_idx, "resolution"):
        return
    sessions = st.session_state.get("case_sessions")
    if not isinstance(sessions, list) or not (0 <= case_idx < len(sessions)):
        return
    case_obj = sessions[case_idx].case
    tracking = getattr(case_obj, "tracking", None)
    if isinstance(tracking, TrackingData):
        if replacement:
            tracking.status = "Replacement"
        else:
            tracking.status = "Resolved"
            tracking.priority = normalize_priority("On Time")
            tracking.active = False
    save_case_to_database(case_obj, notify=not replacement)
    if replacement:
        st.success("Replacement recorded. Milestone marked as completed.")
        return
    case_label = _case_display_name(case_idx)
    close_case_tab(case_idx)
    st.session_state["_milestone_resolution_notice"] = f"{case_label} resolved and closed."
    st.rerun()


DELL_ESCALATION_OVERVIEW_FIELDS = [
    ("dell_issue_start_date", "Issue start date"),
    ("service_tag", "PC service tag"),
    ("case_id", "Case ID"),
]

DELL_ESCALATION_PC_FIELDS = [
    ("pc_model", "Type of PC"),
    ("bios_version", "BIOS Version"),
    ("windows_version", "Windows Version"),
    ("graphics_card", "Graphics card"),
    ("processor", "Processor"),
    ("dell_command_updates_status", "Dell Command Updates"),
    ("dell_power_options_setup", "Power Options setup"),
    ("dell_optimizer_setup", "Dell Optimizer setup"),
    (
        "dell_intel_ppm_installed",
        "Intel Processor Power Management Utility installed?",
    ),
    ("dell_cpu_speed_or_throttling", "CPU Speed / Is CPU throttling?"),
    ("dell_gpu_usage_integrated", "GPU Usage % (Integrated)"),
    ("dell_gpu_usage_dedicated", "GPU Usage % (Dedicated)"),
    ("dell_cpu_utilization", "CPU Utilization %"),
    ("dell_benchmark_results", "Benchmark used and results"),
    (
        "dell_ultra_resolution_support",
        "Can it launch simulation on Ultra Resolution? (If needed)",
    ),
    ("dell_gpu_driver_versions", "Which GPU driver versions were tested?"),
    (
        "dell_reliability_monitor_results",
        "Reliability Monitor and Event Viewer results",
    ),
    ("dell_diagnostics_results", "Dell Diagnosis test results (ePSA tests included)"),
    ("dell_windows_reimaged", "Has Windows been reimaged?"),
]

DELL_ESCALATION_CONTACT_FIELDS = [
    ("clinic_name", "Clinic name"),
    (
        "clinic_contact_name",
        "Full name of person responsible for receiving the equipment",
    ),
    ("clinic_contact_phone", "Phone number"),
    ("clinic_contact_email", "Email address"),
    ("clinic_address_line_1", "Address 1"),
    ("clinic_address_line_2", "Address 2 (Suite, etc.)"),
    ("clinic_city", "City"),
    ("clinic_state", "State"),
    ("clinic_postal_code", "Zip Code"),
]

DELL_ESCALATION_FIELD_LABELS = (
    DELL_ESCALATION_OVERVIEW_FIELDS
    + DELL_ESCALATION_PC_FIELDS
    + DELL_ESCALATION_CONTACT_FIELDS
)

DELL_ESCALATION_FIELDS = [field for field, _ in DELL_ESCALATION_FIELD_LABELS]

BASE_CATEGORY_MAP = {
    "HEADER": [
        "company_name",
        "subscription_id",
        "brief_description",
        "case_id",
        "application_version",
    ],
    "DESCRIPTION": ["description"],
    "PHONECALL": [
        "caller_name",
        "phone_description",
        "email",
        "dongle_number",
        "phone_number",
        "teamviewer_id",
        "teamviewer_password",
    ],
    "INTERNAL NOTES": ["internal_helpjuice", "internal_logs"],
    "REMOTE SESSION": ["remote_steps", "repro_steps"],
    "CONCLUSION": ["root_cause", "solution"],
    "AX COORDINATORS": [
        "request_issue",
        "contact_name",
        "office_ph",
        "direct_ph",
        "best_time",
        "patterson",
        "straumann",
    ],
    "ESCALATION 2ND LINE": ["esc_name", "esc_ph", "esc_email"],
    "DELL ESCALATION": DELL_ESCALATION_FIELDS,
    "ADDITIONAL INFORMATION": ["additional_info"],
}

HW_CATEGORY_MAP = {
    "PC HARDWARE": [
        "service_tag",
        "pc_model",
        "windows_version",
        "bios_version",
        "graphics_card",
        "processor",
        "warranty",
    ],
    "SCANNER HARDWARE": [
        "scanner_sn",
        "base_sn",
        "trios_module_version",
        "dongle_deployment_date",
        "scanner_previous_replacements",
        "scanner_accidental_damage",
        "hardware_test",
    ],
    "HARDWARE REPLACEMENT HISTORY": [
        "hardware_dongle_replaced",
        "hardware_latest_deployment_date",
        "hardware_scanner_replaced",
        "hardware_scanner_sn_summary",
        "hardware_subscription_type",
    ],
}


OPTIONAL_PROGRESS_CATEGORIES = {"DELL ESCALATION"}

ESCALATION_TOGGLE_FIELDS = [
    "request_issue",
    "contact_name",
    "office_ph",
    "direct_ph",
    "best_time",
    "patterson",
    "straumann",
    "esc_name",
    "esc_ph",
    "esc_email",
] + DELL_ESCALATION_FIELDS

HARDWARE_TOGGLE_FIELDS = sorted(
    {field for fields in HW_CATEGORY_MAP.values() for field in fields}
    | {
        "hardware_dongle_replaced",
        "hardware_latest_deployment_date",
        "hardware_scanner_replaced",
        "hardware_scanner_sn_summary",
        "hardware_subscription_type",
    }
)


def active_category_map():
    cm = BASE_CATEGORY_MAP.copy()
    if st.session_state.get("second_line_mode"):
        cm["HEADER"] = ["straumann"] + cm.get("HEADER", [])
    if not st.session_state.get("include_escalations", True):
        cm.pop("AX COORDINATORS", None)
        cm.pop("ESCALATION 2ND LINE", None)
        cm.pop("DELL ESCALATION", None)
    if st.session_state.get("include_hardware"):
        cm.update(HW_CATEGORY_MAP)
    return cm


def _build_case_ai_dict(case: CaseData) -> dict[str, object]:
    case_dict = asdict(case)
    if not st.session_state.get("include_escalations", True):
        for field in ESCALATION_TOGGLE_FIELDS:
            case_dict.pop(field, None)
    if not st.session_state.get("include_hardware", False):
        for field in HARDWARE_TOGGLE_FIELDS:
            case_dict.pop(field, None)
    return case_dict


def _extract_json_object(block: str) -> dict[str, object] | None:
    if not isinstance(block, str):
        return None
    start = block.find("{")
    end = block.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    fragment = block[start : end + 1]
    try:
        return json.loads(fragment)
    except Exception:
        return None


def _disabled_tab_note() -> str:
    disabled_sections = []
    if not st.session_state.get("include_escalations", True):
        disabled_sections.append("Escalations tab")
    if not st.session_state.get("include_hardware", False):
        disabled_sections.append("Hardware issues tab")
    if not disabled_sections:
        return ""
    return (
        "The following tabs are disabled and should not be verified or referenced until they are turned on: "
        + ", ".join(disabled_sections)
        + ".\n\n"
    )


CURRENT_CASE_IDX = 0
HIDDEN_CASE_INDEX = 0
HOTKEY_TARGET_SESSION_KEY = "hotkey_target_idx"


def _resolve_hotkey_target_index(
    sessions: Sequence[CaseSession] | None,
    default_idx: int,
) -> int:
    """Return the case index that should feed the clipboard snapshot."""

    target_idx = st.session_state.get(HOTKEY_TARGET_SESSION_KEY)
    if (
        isinstance(target_idx, int)
        and isinstance(sessions, Sequence)
        and 0 <= target_idx < len(sessions)
    ):
        return target_idx

    if HOTKEY_TARGET_SESSION_KEY in st.session_state:
        st.session_state[HOTKEY_TARGET_SESSION_KEY] = None
    return default_idx


def _refresh_hotkey_snapshot() -> None:
    sessions = getattr(st.session_state, "case_sessions", None)
    try:
        category_map = active_category_map()
    except Exception:
        logging.exception("Failed to build category map for hotkey snapshot")
        category_map = {}
    target_idx = _resolve_hotkey_target_index(sessions, CURRENT_CASE_IDX)
    prompt_text = st.session_state.get("last_prompt")
    if not isinstance(prompt_text, str):
        prompt_text = ""
    update_hotkey_snapshot(sessions, target_idx, category_map, prompt_text)


def _ensure_case_hardware_test_text(case: CaseData | None) -> None:
    if isinstance(case, CaseData):
        case.hardware_test = _normalize_hardware_test_text(case.hardware_test)


def _migrate_hardware_test_state() -> None:
    """Coerce legacy boolean hardware test values into text form."""

    case_obj = st.session_state.get("case")
    _ensure_case_hardware_test_text(case_obj if isinstance(case_obj, CaseData) else None)

    sessions = st.session_state.get("case_sessions")
    if isinstance(sessions, list):
        for session in sessions:
            _ensure_case_hardware_test_text(getattr(session, "case", None))

    for key in list(st.session_state.keys()):
        if key == "hardware_test" or key.startswith("hardware_test_"):
            st.session_state[key] = _normalize_hardware_test_text(st.session_state.get(key))


def _case_metadata_snapshot(active_index: int | None = None) -> list[dict[str, str]]:
    """Return a serialised view of known cases for diagnostic exports."""

    sessions = st.session_state.get("case_sessions", [])
    snapshot: list[dict[str, str]] = []
    for idx, session in enumerate(sessions):
        case = getattr(session, "case", None)
        if not isinstance(case, CaseData):
            continue
        tracking = getattr(case, "tracking", None)
        priority = ""
        if isinstance(tracking, TrackingData):
            priority = tracking.priority
        snapshot.append(
            {
                "Case": case.case_id or _case_display_name(idx),
                "Company": case.company_name or "",
                "Summary": case.brief_description or "",
                "Priority": priority,
                "Active": "Yes" if active_index is not None and idx == active_index else "",
            }
        )
    return snapshot


def build_incident_report_pdf(
    context: Mapping[str, object],
    logs: str,
    user_notes: str,
    case_snapshot: list[Mapping[str, str]],
    *,
    screenshot: "ScreenshotAsset | None" = None,
) -> bytes:
    """Generate a PDF summarising a captured incident."""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=48,
        bottomMargin=36,
    )
    style_loader = globals().get("_load_pdf_styles")
    if style_loader is None:
        from case_documentation_app import _load_pdf_styles as style_loader  # pragma: no cover - test helper
    styles, regular_font, bold_font, ghost_style = style_loader()
    title_style = styles["Title"]
    body_style = styles["BodyText"]
    heading_style = styles["Heading3"]
    code_style = styles.get("Code", body_style)

    elements = [
        Paragraph("Kiroshi Incident Report", title_style),
        Spacer(1, 12),
        Paragraph(
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            body_style,
        ),
        Spacer(1, 18),
    ]

    meta_fields = [
        ("Section", context.get("section", "")),
        ("Tab", context.get("tab", "")),
        ("Trigger", context.get("trigger", "")),
        ("Timestamp", context.get("timestamp", "")),
    ]
    case_index = context.get("case_index")
    if case_index is not None:
        try:
            case_number = int(case_index) + 1
        except (TypeError, ValueError):
            case_number = case_index
        meta_fields.append(("Case index", str(case_number)))
    exception = context.get("exception")
    if exception:
        meta_fields.append(("Exception", str(exception)))

    meta_table_data = [
        [Paragraph("Field", body_style), Paragraph("Value", body_style)]
    ]
    for label, value in meta_fields:
        meta_table_data.append(
            [Paragraph(str(label), body_style), Paragraph(str(value or ""), body_style)]
        )
    meta_table = Table(meta_table_data, colWidths=[150, 360])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
        )
    )
    elements.extend([meta_table, Spacer(1, 18)])

    if case_snapshot:
        elements.append(Paragraph("Case overview", heading_style))
        case_table_data: list[list[Paragraph]] = [
            [
                Paragraph("Case", body_style),
                Paragraph("Company", body_style),
                Paragraph("Summary", body_style),
                Paragraph("Priority", body_style),
                Paragraph("Active", body_style),
            ]
        ]
        case_table_data.extend(
            [
                [
                    Paragraph(str(entry.get("Case", "")), body_style),
                    Paragraph(str(entry.get("Company", "")), body_style),
                    Paragraph(str(entry.get("Summary", "")), body_style),
                    Paragraph(str(entry.get("Priority", "")), body_style),
                    Paragraph(str(entry.get("Active", "")), body_style),
                ]
                for entry in case_snapshot
            ]
        )
        case_table = Table(case_table_data, colWidths=[80, 120, 200, 70, 40])
        case_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )
        elements.extend([case_table, Spacer(1, 18)])

    elements.append(Paragraph("User notes", heading_style))
    elements.append(
        Paragraph(user_notes.strip() or "No user notes provided.", body_style)
    )
    elements.append(Spacer(1, 18))

    stacktrace = context.get("stacktrace")
    if stacktrace:
        elements.append(Paragraph("Stack trace", heading_style))
        elements.append(Preformatted(str(stacktrace), code_style))
        elements.append(Spacer(1, 18))

    elements.append(Paragraph("Recent logs", heading_style))
    elements.append(Preformatted(logs or "No log entries were captured.", code_style))
    elements.append(Spacer(1, 18))

    if screenshot:
        elements.append(Paragraph("Screenshot", heading_style))
        try:
            img_stream = io.BytesIO(screenshot.data)
            shot = Image(img_stream)
            max_width = 420
            if shot.drawWidth > max_width:
                scale = max_width / shot.drawWidth
                shot.drawWidth *= scale
                shot.drawHeight *= scale
            shot.hAlign = "LEFT"
            elements.extend([shot, Spacer(1, 12)])
        except Exception as exc:  # pragma: no cover - reportlab image edge cases
            elements.append(
                Paragraph(
                    f"Unable to embed screenshot: {escape(str(exc))}",
                    body_style,
                )
            )

    ghost_snippets: list[str] = ["Kiroshi Incident Report"]
    ghost_snippets.extend(str(value or "") for _, value in meta_fields)
    ghost_snippets.append(user_notes)
    if stacktrace:
        ghost_snippets.append(stacktrace)
    ghost_snippets.append(logs)
    for entry in case_snapshot or []:
        ghost_snippets.extend(str(entry.get(key, "")) for key in ("Case", "Company", "Summary", "Priority", "Active"))
    builder = globals().get("_build_pdf_with_ghost_text")
    if builder is None:
        from case_documentation_app import _build_pdf_with_ghost_text as builder  # pragma: no cover - test helper
    builder(doc, elements, ghost_snippets)
    buf.seek(0)
    return buf.read()


# ──────────────── CASE TAB MEMORY ────────────────


@st.cache_data(ttl=2, show_spinner=False)
def _scan_case_directories_cached(directories_str: list[str]) -> dict[str, float]:
    """Scan directories for JSON files and return their modification times.

    Cached for 2 seconds to prevent excessive disk I/O during rapid Streamlit reruns.
    """
    current_files: dict[str, float] = {}
    for directory_str in directories_str:
        directory = Path(directory_str)
        if not directory.exists():
            continue
        try:
            with os.scandir(str(directory)) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.lower().endswith(".json"):
                        try:
                            # entry.stat() is cached on Windows from scandir
                            current_files[str(entry.path)] = entry.stat().st_mtime
                        except OSError:
                            pass
        except OSError:
            pass
    return current_files


@st.cache_data(ttl=None, max_entries=1)
def _load_case_tab_memory_worker(mtime: float) -> list[dict[str, object]]:
    """Load case tab memory from disk, cached until modification time changes."""
    try:
        payload = json.loads(CASE_TAB_MEMORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Failed to load case tab memory: %s", exc)
        return []
    tabs = payload.get("tabs") if isinstance(payload, Mapping) else None
    if not isinstance(tabs, list):
        return []
    return [dict(entry) for entry in tabs if isinstance(entry, Mapping)]


def _load_case_tab_memory() -> list[dict[str, object]]:
    if not CASE_TAB_MEMORY_FILE.exists():
        return []
    try:
        mtime = CASE_TAB_MEMORY_FILE.stat().st_mtime
    except OSError:
        return []
    return _load_case_tab_memory_worker(mtime)


def _write_case_tab_memory(entries: list[dict[str, object]]) -> None:
    try:
        CASE_TAB_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CASE_TAB_MEMORY_FILE.open("w", encoding="utf-8") as fh:
            json.dump({"tabs": entries}, fh, indent=2)
    except OSError as exc:
        logging.warning("Failed to persist case tab memory: %s", exc)


def _attachments_loader() -> Callable[
    [str, Mapping[str, Iterable[Mapping[str, object]]]],
    tuple[list[InMemoryUploadedFile], list[InMemoryUploadedFile], list[ScreenshotAsset]],
]:
    """Return the available attachment loader, or a no-op stub when unavailable."""

    try:
        loader = globals().get("load_case_attachments")
        if callable(loader):
            return loader  # type: ignore[return-value]
    except Exception:
        # If globals lookup itself fails, fall back to the stub below.
        logging.debug("Attachment loader lookup failed; using fallback stub")

    logging.debug("Attachments loader missing; falling back to empty attachments")

    def _noop_loader(
        _case_id: str, _attachments_data: Mapping[str, Iterable[Mapping[str, object]]]
    ) -> tuple[list[InMemoryUploadedFile], list[InMemoryUploadedFile], list[ScreenshotAsset]]:
        return [], [], []

    return _noop_loader


def _hydrate_case_sessions_from_memory() -> list[CaseSession]:
    sessions: list[CaseSession] = []
    for entry in _load_case_tab_memory():
        source_path = str(entry.get("source_path", "")) if entry else ""
        scratch_value = str(entry.get("scratch", "")) if entry else ""
        case_payload = entry.get("case") if isinstance(entry, Mapping) else {}
        attachments_payload = entry.get("attachments_index") if isinstance(entry, Mapping) else {}
        milestone_payload = entry.get("milestones") if isinstance(entry, Mapping) else {}
        attachments_index = _normalise_attachments_index(attachments_payload)

        if source_path:
            try:
                raw = json.loads(Path(source_path).read_text(encoding="utf-8"))
                if isinstance(raw, Mapping):
                    case_payload = {
                        k: v for k, v in raw.items() if k in CaseData.__annotations__
                    }
                    attachments_index = _normalise_attachments_index(raw.get("attachments"))
            except (OSError, json.JSONDecodeError) as exc:
                logging.warning("Unable to refresh case %s from disk: %s", source_path, exc)

        if isinstance(case_payload, Mapping):
            try:
                case_obj = CaseData(**case_payload)
            except TypeError:
                case_obj = CaseData()
        else:
            case_obj = CaseData()

        uploads: list[InMemoryUploadedFile] = []
        log_uploads: list[InMemoryUploadedFile] = []
        screenshots: list[ScreenshotAsset] = []
        if case_obj.case_id:
            try:
                loader = _attachments_loader()
                uploads, log_uploads, screenshots = loader(
                    case_obj.case_id, attachments_index
                )
            except Exception as exc:  # pragma: no cover - runtime environment specific
                logging.warning(
                    "Failed to hydrate attachments for case %s: %s",
                    case_obj.case_id,
                    exc,
                )
                attachments_index = _default_attachments_index()

        sessions.append(
            CaseSession(
                case=case_obj,
                scratch=scratch_value,
                uploads=uploads,
                log_uploads=log_uploads,
                screenshots=screenshots,
                source_path=source_path,
                attachments_index=attachments_index,
                milestones=_coerce_case_milestone_state(milestone_payload),
            )
        )
    return sessions


def _sync_case_memory_from_sessions() -> None:
    if "case_sessions" not in st.session_state:
        return
    default_case_payload = asdict(CaseData())
    entries: list[dict[str, object]] = []
    for session in st.session_state.case_sessions:
        try:
            case_payload = asdict(session.case)
        except Exception:
            case_payload = {}
        attachments_index = _normalise_attachments_index(
            getattr(session, "attachments_index", {})
        )
        scratch_value = getattr(session, "scratch", "")
        source_path = getattr(session, "source_path", "")
        has_scratch = isinstance(scratch_value, str) and scratch_value.strip()
        has_attachments = any(attachments_index.values())
        if (
            case_payload == default_case_payload
            and not source_path
            and not has_scratch
            and not has_attachments
        ):
            continue
        milestone_state = getattr(session, "milestones", None)
        milestone_payload = (
            asdict(milestone_state)
            if isinstance(milestone_state, CaseMilestoneState)
            else asdict(_ensure_case_milestone_state(session))
        )
        entries.append(
            {
                "case": case_payload,
                "source_path": source_path,
                "scratch": scratch_value,
                "attachments_index": attachments_index,
                "milestones": milestone_payload,
            }
        )
    _write_case_tab_memory(entries)


# convert stored dict to dataclass, ignoring unexpected fields
if isinstance(st.session_state.case, dict):
    allowed = {f.name for f in fields(CaseData)}
    filtered = {k: v for k, v in st.session_state.case.items() if k in allowed}
    st.session_state.case = CaseData(**filtered)
D: CaseData = st.session_state.case
_migrate_hardware_test_state()
if D.tracking.active:
    st.session_state.track_case = True

if "case_sessions" not in st.session_state:
    stored_sessions = _hydrate_case_sessions_from_memory()
    if stored_sessions:
        st.session_state.case_sessions = stored_sessions
        primary_session = stored_sessions[0]
        st.session_state.case = primary_session.case
        st.session_state.uploads = primary_session.uploads
        st.session_state.log_uploads = primary_session.log_uploads
        set_active_screenshots(primary_session.screenshots)
        st.session_state.scratch = primary_session.scratch
        st.session_state["attachments_index"] = _normalise_attachments_index(
            getattr(primary_session, "attachments_index", {})
        )
    else:
        current_index = _normalise_attachments_index(
            st.session_state.get("attachments_index")
        )
        st.session_state.case_sessions = [
            CaseSession(
                case=D,
                scratch=st.session_state.get("scratch", ""),
                uploads=st.session_state.uploads,
                log_uploads=st.session_state.log_uploads,
                screenshots=st.session_state.screenshots,
                attachments_index=current_index,
            )
        ]
        st.session_state["attachments_index"] = current_index
    _sync_case_memory_from_sessions()
    _refresh_hotkey_snapshot()
    ensure_hotkey_listener()


def _prime_case_widget_state(idx: int, case: CaseData) -> None:
    """Seed widget-specific state values for the active case index."""

    for field in fields(CaseData):
        state_key = widget_state_key(field.name, idx)
        try:
            value = getattr(case, field.name)
        except AttributeError:
            # ``CaseData`` can evolve over time; ignore fields missing on legacy payloads.
            continue
        if field.name == "hardware_test":
            normalised = _normalize_hardware_test_text(value)
            setattr(case, field.name, normalised)
            value = normalised
        st.session_state[state_key] = value
        st.session_state[f"{state_key}__persisted"] = value


def load_case_state(idx: int) -> None:
    cs = st.session_state.case_sessions[idx]
    case_obj = getattr(cs, "case", None)
    _ensure_case_hardware_test_text(case_obj if isinstance(case_obj, CaseData) else None)
    st.session_state.case = cs.case
    st.session_state.uploads = cs.uploads
    st.session_state.log_uploads = cs.log_uploads
    set_active_screenshots(cs.screenshots)
    st.session_state["attachments_index"] = _normalise_attachments_index(
        getattr(cs, "attachments_index", {})
    )
    scratch_value = getattr(cs, "scratch", "")
    st.session_state.scratch = scratch_value
    st.session_state[widget_state_key("scratch", idx)] = scratch_value
    global D
    D = st.session_state.case
    _ensure_case_hardware_test_text(D if isinstance(D, CaseData) else None)
    for key, value in asdict(D).items():
        st.session_state[key] = value
    _prime_case_widget_state(idx, D)
    ensure_hotkey_listener()
    _refresh_hotkey_snapshot()


def save_case_state(idx: int) -> None:
    scratch_key = widget_state_key("scratch", idx)
    scratch_value = st.session_state.get(scratch_key, st.session_state.get("scratch", ""))
    existing_session = st.session_state.case_sessions[idx]
    milestone_state = _ensure_case_milestone_state(existing_session)
    st.session_state.case_sessions[idx] = CaseSession(
        case=st.session_state.case,
        scratch=scratch_value,
        uploads=st.session_state.uploads,
        log_uploads=st.session_state.log_uploads,
        screenshots=st.session_state.screenshots,
        source_path=getattr(existing_session, "source_path", ""),
        attachments_index=_normalise_attachments_index(
            st.session_state.get("attachments_index", getattr(existing_session, "attachments_index", {}))
        ),
        milestones=milestone_state,
    )
    _sync_case_memory_from_sessions()
    _refresh_hotkey_snapshot()


def _clear_case_widget_state(idx: int) -> None:
    """Remove Streamlit widget state entries associated with a case index."""

    suffix = f"_{idx}"
    for key in list(st.session_state.keys()):
        if key.endswith(suffix) or key.endswith(f"{suffix}__persisted"):
            st.session_state.pop(key)


def clear_case_state(idx: int) -> None:
    """Reset the stored data for the case at the given index."""

    new_case = CaseData()
    new_session = CaseSession(
        case=new_case,
        scratch="",
        uploads=[],
        log_uploads=[],
        screenshots=[],
    )

    _clear_case_widget_state(idx)

    st.session_state.case_sessions[idx] = new_session

    if idx == CURRENT_CASE_IDX:
        global D
        st.session_state.case = new_case
        D = new_case
        st.session_state.uploads = []
        st.session_state.log_uploads = []
        clear_active_screenshots()
        st.session_state["attachments_index"] = _default_attachments_index()
        st.session_state.scratch = ""
        st.session_state[widget_state_key("scratch", idx)] = ""
        for key in (
            "ai_assist_result",
            "ai_autocorrect_result",
            "ai_autocorrect_case_json",
            "verify_result",
            "ask_result",
            "categorizer_result",
            "categorizer_summary",
        ):
            if key in st.session_state:
                value = st.session_state.get(key)
                if isinstance(value, str):
                    st.session_state[key] = ""
                elif isinstance(value, dict):
                    st.session_state[key] = {}
                else:
                    st.session_state[key] = []
        st.session_state.ai_learning_matches = []

    ensure_tracking_session_defaults(idx, new_case.tracking, force=True)

    st.session_state.track_case = any(
        session.case.tracking.active for session in st.session_state.case_sessions
    )

    touch_case_last_modified()
    autosave()
    _sync_case_memory_from_sessions()
    _refresh_hotkey_snapshot()


def close_case_tab(idx: int) -> None:
    """Remove the case session at the given index and clean up widget state."""

    sessions: list[CaseSession] | None = st.session_state.get("case_sessions")
    if not sessions:
        return
    if idx <= 0 or idx >= len(sessions):
        return

    closing_case_id = getattr(sessions[idx].case, "case_id", None)

    # Clear widget state for the closing case and any cases that will be re-indexed.
    for target_idx in range(idx, len(sessions)):
        _clear_case_widget_state(target_idx)

    sessions.pop(idx)
    st.session_state.case_sessions = sessions

    st.session_state.track_case = any(
        session.case.tracking.active for session in st.session_state.case_sessions
    )

    target_idx = st.session_state.get(HOTKEY_TARGET_SESSION_KEY)
    if isinstance(target_idx, int):
        if target_idx == idx:
            st.session_state[HOTKEY_TARGET_SESSION_KEY] = None
        elif target_idx > idx:
            st.session_state[HOTKEY_TARGET_SESSION_KEY] = target_idx - 1

    cleanup_case_autosaves(closing_case_id)
    touch_case_last_modified()
    autosave()
    _sync_case_memory_from_sessions()
    _refresh_hotkey_snapshot()


class WidgetKeyCollisionError(RuntimeError):
    """Raised when duplicate Streamlit widget keys are detected in debug mode."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Duplicate Streamlit widget key detected: {key}")
        self.key = key


def _register_widget_key(key: str) -> str:
    """Track widget keys during debug sessions and detect duplicates."""

    if not st.session_state.get("debug_mode"):
        st.session_state.pop("debug_widget_key_registry", None)
        st.session_state.pop("debug_widget_key_collisions", None)
        st.session_state.pop("debug_widget_key_last_collision", None)
        st.session_state.pop("debug_widget_key_collision_flag", None)
        st.session_state.pop("debug_widget_key_collision_context", None)
        return key

    registry = st.session_state.get("debug_widget_key_registry")
    if not isinstance(registry, set):
        registry = set()
        st.session_state.debug_widget_key_registry = registry

    collisions = st.session_state.get("debug_widget_key_collisions")
    if not isinstance(collisions, set):
        collisions = set()
        st.session_state.debug_widget_key_collisions = collisions

    if key in registry:
        collisions.add(key)
        st.session_state.debug_widget_key_last_collision = key
        st.session_state.debug_widget_key_collision_flag = True
        raise WidgetKeyCollisionError(key)

    registry.add(key)
    st.session_state.debug_widget_key_collision_flag = bool(collisions)
    return key


def _compose_widget_key(base: str, idx: int) -> str:
    """Return the canonical widget key string for a case index."""

    return f"{base}_{idx}"


def widget_key(base: str, idx: int) -> str:
    """Return a Streamlit widget key namespaced to a case index."""
    key = _compose_widget_key(base, idx)
    return _register_widget_key(key)


def widget_state_key(base: str, idx: int) -> str:
    """Return a widget key string without registering it for collision checks.

    This helper is intended for scenarios where the key is used solely to
    interact with ``st.session_state`` (e.g., priming default values or reading
    state) rather than instantiating a new Streamlit widget. Using this
    function prevents legitimate state access from being treated as a duplicate
    widget registration during debug sessions.
    """

    return _compose_widget_key(base, idx)


def case_widget_key(
    slug: str,
    widget: str | None = None,
    idx: int | None = None,
    *,
    case_idx: int | None = None,
) -> str:
    """Return a Streamlit widget key scoped to the case index and logical slug."""

    if idx is None:
        idx = case_idx
    if idx is None:
        raise ValueError("case_widget_key requires a case index")

    safe_slug = re.sub(r"[^0-9a-z_]+", "_", slug.lower()).strip("_")
    safe_widget = ""
    if widget is not None:
        safe_widget = re.sub(r"[^0-9a-z_]+", "_", widget.lower()).strip("_")

    if safe_slug and safe_widget:
        base = f"{safe_slug}_{safe_widget}"
    else:
        base = safe_slug or safe_widget or "widget"

    return widget_key(base, idx)


def global_widget_key(base: str) -> str:
    """Return a Streamlit widget key reserved for global (non-case) widgets."""
    key = f"global_{base}"
    return _register_widget_key(key)

if st.session_state.get("debug_mode"):
    st.session_state.debug_widget_key_registry = set()
    st.session_state.debug_widget_key_collisions = set()
    st.session_state.debug_widget_key_collision_flag = False
    st.session_state.debug_widget_key_collision_context = None
    st.session_state.debug_widget_key_last_collision = None
else:
    st.session_state.pop("debug_widget_key_registry", None)
    st.session_state.pop("debug_widget_key_collisions", None)
    st.session_state.pop("debug_widget_key_collision_flag", None)
    st.session_state.pop("debug_widget_key_collision_context", None)
    st.session_state.pop("debug_widget_key_last_collision", None)

# Ensure session state mirrors the current case data before any widgets are created
for key, value in asdict(D).items():
    st.session_state[key] = value

# Ensure the survey link widget has an initial value to prevent
# "attribute missing" errors before the first user interaction.
_init_state("survey_link", D.survey_link)

# Button to clear all case data and reset form
AUTOSAVE_THROTTLE_SECONDS = 0.75
_last_autosave_hash: str | None = None
_last_autosave_timestamp: float = 0.0
_pending_autosave: tuple[str, str, dict] | None = None
_pending_autosave_timer: threading.Timer | None = None
_autosave_lock = threading.RLock()
_autosave_cached_payload: dict[str, Any] | None = None
_autosave_cached_serialized: str | None = None
_autosave_field_fingerprints: dict[str, str] = {}


def autosave_payload(case: CaseData | None = None) -> dict:
    target = case if case is not None else D
    case_payload = asdict(target)

    # Only cache if we are saving the active case to avoid cache thrashing
    if case is None or case is D:
        cached_case = st.session_state.get("_autosave_cached_case")

        if cached_case is not None and cached_case == case_payload:
            st.session_state["_autosave_case_dirty"] = False
            return {"case": cached_case}

        st.session_state["_autosave_cached_case"] = case_payload
        st.session_state["_autosave_case_dirty"] = True

    return {"case": case_payload}


def _compact_json_dumps(value: Any) -> str:
    """Serialize ``value`` with stable, compact JSON output."""

    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def _serialize_autosave_payload(payload: dict) -> tuple[str, str]:
    global _autosave_cached_payload, _autosave_cached_serialized

    case_payload: dict[str, Any] = payload.get("case", {})
    previous_case: dict[str, Any] | None = None
    if _autosave_cached_payload:
        previous_case = _autosave_cached_payload.get("case")

    known_keys = set(case_payload.keys())
    if previous_case:
        known_keys.update(previous_case.keys())

    dirty_fields = {
        key
        for key in known_keys
        if previous_case is None or case_payload.get(key) != previous_case.get(key)
    }

    for field in dirty_fields:
        _autosave_field_fingerprints[field] = hashlib.blake2s(
            _compact_json_dumps(case_payload.get(field)).encode("utf-8")
        ).hexdigest()

    checksum = hashlib.blake2s()
    for field_name in sorted(_autosave_field_fingerprints):
        checksum.update(field_name.encode("utf-8"))
        checksum.update(_autosave_field_fingerprints[field_name].encode("utf-8"))

    payload_hash = checksum.hexdigest()

    _autosave_cached_payload = payload

    if not dirty_fields and _autosave_cached_serialized:
        return _autosave_cached_serialized, payload_hash

    serialized_payload = _compact_json_dumps(payload)
    _autosave_cached_serialized = serialized_payload
    return serialized_payload, payload_hash


def autosave(case: CaseData | None = None):
    global _pending_autosave, _pending_autosave_timer

    payload = autosave_payload(case)
    serialized_payload, payload_hash = _serialize_autosave_payload(payload)

    with _autosave_lock:
        global _last_autosave_hash, _last_autosave_timestamp

        if payload_hash == _last_autosave_hash:
            return

        now = time.monotonic()
        elapsed = now - _last_autosave_timestamp

        if elapsed < AUTOSAVE_THROTTLE_SECONDS:
            _pending_autosave = (serialized_payload, payload_hash, payload)
            if _pending_autosave_timer is None:
                delay = max(AUTOSAVE_THROTTLE_SECONDS - elapsed, 0.05)
                _pending_autosave_timer = threading.Timer(delay, _flush_pending_autosave)
                _pending_autosave_timer.daemon = True
                _pending_autosave_timer.start()
            return

        _pending_autosave = None
        if _pending_autosave_timer:
            _pending_autosave_timer.cancel()
            _pending_autosave_timer = None

        _write_autosave(serialized_payload, payload_hash, payload)


def _flush_pending_autosave() -> None:
    global _pending_autosave, _pending_autosave_timer

    with _autosave_lock:
        if not _pending_autosave:
            _pending_autosave_timer = None
            return

        serialized_payload, payload_hash, payload = _pending_autosave
        _pending_autosave = None
        _pending_autosave_timer = None

        _write_autosave(serialized_payload, payload_hash, payload)


def _write_autosave(serialized_payload: str, payload_hash: str, payload: dict) -> None:
    global _last_autosave_hash, _last_autosave_timestamp

    case_id_value = _extract_case_id(payload)
    autosave_path = _autosave_path(case_id_value)
    temp_path = autosave_path.with_suffix(autosave_path.suffix + ".tmp")

    with _autosave_lock:
        existing_hash = _last_autosave_hash
        try:
            if existing_hash is None and autosave_path.exists():
                existing_hash = hashlib.sha1(
                    autosave_path.read_text(encoding="utf-8").encode("utf-8")
                ).hexdigest()
        except Exception as exc:
            logging.debug("Unable to hash existing autosave file: %s", exc)

        db_saved = False
        if st.session_state.get("autosave_to_database"):
            case_obj = st.session_state.get("case")
            case_cls = globals().get("CaseData")
            if (
                case_cls
                and isinstance(case_obj, case_cls)
                and "save_case_to_database" in globals()
            ):
                case_id_value = getattr(case_obj, "case_id", "")
                if isinstance(case_id_value, str) and case_id_value.strip():
                    try:
                        save_case_to_database(case_obj, notify=False)
                        db_saved = True
                    except Exception as exc:  # pragma: no cover - streamlit runtime specific
                        logging.warning(
                            "Failed to autosave case %s to database: %s",
                            case_id_value,
                            exc,
                        )
                        try:
                            st.warning(
                                "Autosave could not write to the shared database. "
                                "Check connectivity or permissions before relying on the backup."
                            )
                        except Exception:  # pragma: no cover - Streamlit unavailable during tests
                            logging.debug("Streamlit warning unavailable for autosave alert")

        if db_saved and existing_hash == payload_hash:
            _last_autosave_timestamp = time.monotonic()
            _last_autosave_hash = payload_hash
            return

        try:
            with temp_path.open("w", encoding="utf-8") as f:
                f.write(serialized_payload)

            # Retry logic for Windows transient file locking
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    os.replace(temp_path, autosave_path)
                    break
                except PermissionError:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                    else:
                        raise
                except OSError:
                    # Reraise other OS errors immediately
                    raise

            _last_autosave_timestamp = time.monotonic()
            _last_autosave_hash = payload_hash
        except Exception as exc:
            logging.exception("Failed to persist autosave to %s", autosave_path)
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception as cleanup_exc:  # pragma: no cover - best-effort cleanup
                logging.debug(
                    "Unable to remove temporary autosave file %s: %s", temp_path, cleanup_exc
                )

            if existing_hash:
                _last_autosave_hash = existing_hash
            return


def get_case_attachments_dir(case_id: str) -> Path:
    """Return the directory used to persist attachments for a case."""

    safe_id = sanitize_case_id(case_id)
    attachments_root, _ = _ensure_case_attachments_root()
    case_dir = attachments_root / safe_id
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def persist_case_attachments(case_id: str) -> dict[str, list[dict[str, str]]]:
    """Write uploaded attachments to disk and return metadata for JSON storage."""

    attachments_index: dict[str, list[dict[str, str]]] = {
        "uploads": [],
        "log_uploads": [],
        "screenshots": [],
    }
    if not case_id:
        return attachments_index

    try:
        base_dir = get_case_attachments_dir(case_id)
    except Exception as exc:
        logging.exception("Unable to prepare attachments directory for %s", case_id)
        st.warning(f"Unable to persist attachments: {exc}")
        return attachments_index

    screenshots_state = get_active_screenshots()
    mapping = [
        ("uploads", st.session_state.get("uploads", []), "uploads"),
        ("log_uploads", st.session_state.get("log_uploads", []), "logs"),
        ("screenshots", screenshots_state, "screenshots"),
    ]

    for key, items, subdir in mapping:
        if not items:
            continue
        target_dir = base_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        seen: set[str] = set()
        for item in items:
            name = getattr(item, "name", None)
            if not isinstance(name, str):
                continue
            sanitized = sanitize_filename(name)
            try:
                data = item.getvalue()
            except Exception as exc:  # pragma: no cover - streamlit runtime specific
                logging.warning("Failed to read attachment %s: %s", name, exc)
                continue
            if not isinstance(data, (bytes, bytearray)):
                continue
            dest = target_dir / sanitized
            try:
                with open(dest, "wb") as fh:
                    fh.write(data)
            except Exception as exc:
                logging.warning("Failed to write attachment %s: %s", dest, exc)
                continue
            rel_path = dest.relative_to(base_dir).as_posix()
            if rel_path in seen:
                continue
            seen.add(rel_path)
            if isinstance(item, ScreenshotAsset):
                attachments_index[key].append(item.metadata(path=rel_path))
            else:
                attachments_index[key].append({"name": sanitized, "path": rel_path})

    _set_active_session_attachments_index(attachments_index)
    return attachments_index


def persist_evidence_bundle_zip(
    case_id: str, archive_name: str, payload: bytes
) -> Path | None:
    """Persist a generated evidence ZIP alongside other case attachments."""

    safe_case_id = case_id or "case"
    try:
        base_dir = get_case_attachments_dir(safe_case_id)
    except Exception as exc:  # pragma: no cover - UI guardrail
        logging.exception(
            "Unable to prepare attachments directory for %s", safe_case_id
        )
        return None

    safe_name = sanitize_filename(archive_name) or f"{safe_case_id}_evidence.zip"
    target_path = base_dir / safe_name

    try:
        target_path.write_bytes(payload)
        return target_path
    except Exception as exc:  # pragma: no cover - filesystem errors
        logging.warning("Failed to persist evidence bundle %s: %s", target_path, exc)
        return None
def load_case_attachments(
    case_id: str, attachments_data: Mapping[str, Iterable[Mapping[str, object]]]
) -> tuple[
    list[InMemoryUploadedFile],
    list[InMemoryUploadedFile],
    list[ScreenshotAsset],
]:
    """Load persisted attachments for a case based on stored metadata."""

    uploads: list[InMemoryUploadedFile] = []
    log_uploads: list[InMemoryUploadedFile] = []
    screenshots: list[ScreenshotAsset] = []

    if not case_id or not attachments_data:
        return uploads, log_uploads, screenshots

    base_dir = get_case_attachments_dir(case_id)
    fallback_dirs = [base_dir]

    default_dir = CASE_ATTACHMENTS_ROOT / sanitize_case_id(case_id)
    if default_dir not in fallback_dirs:
        fallback_dirs.append(default_dir)
    mapping = [
        ("uploads", uploads, "uploads"),
        ("log_uploads", log_uploads, "logs"),
        ("screenshots", screenshots, "screenshots"),
    ]

    for key, target, fallback_subdir in mapping:
        stored_items = attachments_data.get(key, []) if isinstance(attachments_data, Mapping) else []
        for entry in stored_items:
            if not isinstance(entry, Mapping):
                continue
            rel_path = entry.get("path")
            name = entry.get("name")
            candidate_paths: list[Path] = []
            if isinstance(rel_path, str):
                rel_path_obj = Path(rel_path)
                if rel_path_obj.is_absolute():
                    candidate_paths.append(rel_path_obj)
                else:
                    for root_dir in fallback_dirs:
                        candidate_paths.append(root_dir / rel_path_obj)
            if isinstance(name, str):
                for root_dir in fallback_dirs:
                    candidate_paths.append(root_dir / fallback_subdir / name)
            file_path = next((p for p in candidate_paths if p.exists()), None)
            if not file_path:
                continue
            try:
                data = file_path.read_bytes()
            except Exception as exc:
                logging.warning("Failed to read attachment %s: %s", file_path, exc)
                continue
            display_name = sanitize_filename(name) if isinstance(name, str) else file_path.name
            if key == "screenshots":
                label = str(entry.get("label") or display_name)
                captured_at = str(entry.get("captured_at") or _utc_now_z())
                capture_mode = str(entry.get("capture_mode") or "imported")
                origin = str(entry.get("origin") or "restored")
                content_type = str(entry.get("content_type") or "image/png")
                target.append(
                    ScreenshotAsset(
                        name=display_name,
                        data=data,
                        label=label,
                        capture_mode=capture_mode,
                        captured_at=captured_at,
                        origin=origin,
                        content_type=content_type,
                    )
                )
            else:
                target.append(InMemoryUploadedFile(display_name, data))

    return uploads, log_uploads, screenshots


# Preserve a backwards-compatible alias for environments that still reference
# the old loader name during cached reloads (e.g., Streamlit session restores).
_case_attachments_loader = load_case_attachments


def create_case_autosave_snapshot(case_id: str) -> Path | None:
    try:
        payload = autosave_payload()
        backup_path = _autosave_path(case_id, session_id="snapshot")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return backup_path
    except Exception as exc:
        logging.exception("Failed to create autosave snapshot for %s", case_id)
        st.warning(f"Unable to create autosave backup: {exc}")
        return None


class _RecentCasesCache:
    def __init__(self):
        self.data: list[dict[str, object]] | None = None
        self.mtime: float | None = None


@st.cache_resource
def _get_recent_cases_cache() -> _RecentCasesCache:
    """Return a persistent cache object for recent cases that survives reruns."""
    return _RecentCasesCache()


@st.cache_data(ttl=None, max_entries=1)
def _load_recent_cases_worker(mtime: float) -> list:
    """Worker for load_recent_cases, cached by modification time."""
    if not RECENT_CASES_PATH.exists():
        return []
    try:
        data = json.loads(RECENT_CASES_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        # Sort by last_modified descending
        data.sort(key=lambda x: x.get("last_modified", ""), reverse=True)
        return data
    except Exception:
        return []


def load_recent_cases() -> list:
    """Load the recent cases list, using a cache invalidating on file modification."""
    if not RECENT_CASES_PATH.exists():
        return []
    try:
        mtime = RECENT_CASES_PATH.stat().st_mtime
        cache = _get_recent_cases_cache()
        if cache.mtime == mtime and cache.data is not None:
            return cache.data
    except OSError:
        return []
    data = _load_recent_cases_worker(mtime)
    try:
        cache.mtime = mtime
        cache.data = data
    except Exception:
        pass
    return data



def update_recent_cases(
    case_id: str, path: str, case_data: Mapping[str, object] | None = None
) -> None:
    recents = [c for c in load_recent_cases() if c.get("path") != path]
    last_modified = ""
    try:
        case_path = Path(path)
        if case_data:
            last_modified = str(case_data.get("last_modified") or "")

        if not last_modified and case_path.exists():
            data = json.loads(case_path.read_text(encoding="utf-8"))
            mapping = _coerce_case_mapping(data)
            if isinstance(mapping, Mapping):
                last_modified = str(mapping.get("last_modified") or "")
            if not last_modified:
                last_modified = (
                    datetime.fromtimestamp(case_path.stat().st_mtime)
                    .replace(microsecond=0)
                    .isoformat()
                )
    except Exception:
        last_modified = ""
    recents.insert(0, {"case_id": case_id, "path": path, "last_modified": last_modified})
    recents = recents[:10]
    RECENT_CASES_PATH.write_text(json.dumps(recents, indent=2), encoding="utf-8")
    try:
        cache = _get_recent_cases_cache()
        cache.data = recents
        cache.mtime = RECENT_CASES_PATH.stat().st_mtime
    except Exception:
        pass


def normalize_priority(value) -> str:
    if not value:
        return DEFAULT_TRACKING_PRIORITY
    if value not in PRIORITY_OPTIONS:
        return DEFAULT_TRACKING_PRIORITY
    return value


PRIORITY_RANK = {name: idx for idx, name in enumerate(PRIORITY_OPTIONS)}
PRIORITY_BADGES = {
    "Low": "🟢",
    "Normal": "🔵",
    "High": "🟠",
    "On Time": "🟣",
    "Escalation": "🔴",
}

DELL_STATUS_OPTIONS = [
    "Resolved",
    "Waiting for Technician",
    "Waiting for clinic to send back PC for review",
    "Pending update",
]
FEDEX_STATUS_OPTIONS = [
    "Scanner arrived and waiting for the return",
    "Waiting for scanner to arrive",
    "waiting for pickup",
    "scanner sent",
    "waiting to arrive to the doctor's office.",
]
TRACKING_STATUS_OPTIONS = {
    "Dell": DELL_STATUS_OPTIONS,
    "FedEx": FEDEX_STATUS_OPTIONS,
}


def ensure_tracking_session_defaults(
    case_idx: int, tracking: TrackingData, *, force: bool = False
) -> None:
    """Populate Streamlit state with stored tracking defaults for a case."""

    def assign(base_key: str, value) -> None:
        key = widget_state_key(base_key, case_idx)
        if force or key not in st.session_state:
            st.session_state[key] = value

    assign("tracking_type", tracking.type or "Dell")
    assign("track_category", tracking.category or "")
    assign("track_status", tracking.status or "")
    assign("track_ticket_number", tracking.ticket_number or "")
    assign("track_case_link", tracking.case_link or "")
    assign("track_priority", normalize_priority(tracking.priority))
    assign("track_service_tag", tracking.service_tag or "")

    expected_key = widget_state_key("track_expected_arrival", case_idx)
    if tracking.expected_arrival_date:
        try:
            expected_value = datetime.fromisoformat(tracking.expected_arrival_date).date()
        except Exception:
            expected_value = date.today()
    else:
        expected_value = date.today()
    if force or expected_key not in st.session_state:
        st.session_state[expected_key] = expected_value


def _mapping_freshness_score(item: Mapping[str, object], position: int) -> float:
    """Score mapping recency based on last_modified and original position."""

    ts = None
    try:
        raw = item.get("last_modified")
        if isinstance(raw, str):
            ts = datetime.fromisoformat(raw).timestamp()
    except Exception:
        ts = None
    # Prefer valid timestamps; otherwise, prefer later positions in the list.
    if ts is None:
        return float(position)
    return ts


def _select_latest_mapping(items: list[Mapping[str, object]]) -> Mapping[str, object]:
    """Return the most recent mapping based on timestamp/position."""

    if len(items) == 1:
        return items[0]
    best_item = items[0]
    best_score = _mapping_freshness_score(best_item, 0)
    for idx, item in enumerate(items[1:], start=1):
        score = _mapping_freshness_score(item, idx)
        if score >= best_score:
            best_item, best_score = item, score
    return best_item


def _coerce_case_mapping(data: object) -> dict | None:
    """Return a dictionary representation from historical payloads."""

    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        dict_items = [item for item in data if isinstance(item, dict)]
        if dict_items:
            return _select_latest_mapping(dict_items)
    return None


class _CaseCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.data: dict[str, tuple[float, dict[str, object] | None]] = {}
        self.last_scan_ts: float = 0.0


@st.cache_resource
def _get_global_case_cache() -> _CaseCache:
    """Return a persistent thread-safe cache for case file content."""
    return _CaseCache()


@dataclass
class _RefreshThrottle:
    last_run: float = 0.0
    data: list[dict[str, object]] = field(default_factory=list)


@st.cache_resource
def _get_refresh_throttle() -> _RefreshThrottle:
    return _RefreshThrottle()


def _refresh_and_get_cases() -> list[dict[str, object]]:
    """Scan directories, incrementally update cache, and return all valid cases.

    This replaces O(N) parsing with O(N) scanning + O(K) parsing (K=changed files),
    significantly improving dashboard performance for large datasets.
    """
    throttle = _get_refresh_throttle()
    # Return cached result if called recently (throttling I/O)
    if time.time() - throttle.last_run < 2.0:
        return list(throttle.data)

    cache_obj = _get_global_case_cache()

    # Simple throttle: if scanned < 2s ago, return current snapshot
    # This prevents hammering filesystem on rapid re-renders
    now = time.time()
    if now - cache_obj.last_scan_ts < 2.0:
        with cache_obj.lock:
            # Create a snapshot for return to avoid iteration issues if modified elsewhere
            snapshot = list(cache_obj.data.values())

        # We must still perform the sorting logic for the snapshot
        def _parse_time_snapshot(t):
            if not t: return 0.0
            try:
                return datetime.fromisoformat(str(t)).timestamp()
            except ValueError:
                return 0.0

        valid_items_snapshot = [item for _, item in snapshot if item is not None]
        valid_items_snapshot.sort(key=lambda x: _parse_time_snapshot(x.get("updated")), reverse=True)
        return valid_items_snapshot

    directories = [DATABASE_DIR, TRACKED_CASES_DIR]

    # 1. Scan directories for current state
    current_files: dict[str, float] = {}
    for directory in directories:
        if not directory.exists():
            continue
        try:
            with os.scandir(str(directory)) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.lower().endswith(".json"):
                        try:
                            # entry.stat() is cached on Windows from scandir
                            current_files[str(entry.path)] = entry.stat().st_mtime
                        except OSError:
                            pass
        except OSError:
            pass

    # Populate context dictionaries using simple logic derived from legacy code
    # NOTE: manual_docs was previously loaded here but was unused.
    # For now, we populate 'context' with empty maps to ensure _derive_analysis_label runs without error.
    context = {
        "scanner_labels": {},
        "root_cause_labels": {},
    }

    # 2. Identify changes and update cache (Thread-Safe)
    # We identify which files need processing first, so we only load external resources (manual docs)
    # if we actually have work to do.
    paths_to_process = []

    with cache_obj.lock:
        cache = cache_obj.data
        cached_paths = set(cache.keys())
        current_paths = set(current_files.keys())

        # Remove deleted files
        for p in cached_paths - current_paths:
            del cache[p]

        # Check for updates or new files
        for path, mtime in current_files.items():
            cached_entry = cache.get(path)
            if cached_entry is None or cached_entry[0] != mtime:
                paths_to_process.append((path, mtime))

    # If no files need updating, we can skip the heavy setup logic entirely.
    context = {}
    if paths_to_process:
        # Populate context dictionaries using simple logic derived from legacy code
        scanner_labels = {}
        root_cause_labels = {}

        # Simple extraction logic: iterate docs and check titles/categories
        # This matches behavior from legacy code where specific docs informed these maps
        # Since exact matching logic is complex, we use a basic population if docs have "labels" or "map"
        # For now, we populate 'context' to ensure _derive_analysis_label runs without error.
        context = {
            "scanner_labels": scanner_labels,
            "root_cause_labels": root_cause_labels,
        }

    # Process files (outside lock)
    processed_updates = {}
    for path, mtime in paths_to_process:
        try:
            p_obj = Path(path)
            content = p_obj.read_text(encoding="utf-8")
            payload = json.loads(content)
            is_legacy_payload = isinstance(payload, list)
            data = _coerce_case_mapping(payload)

            if data is not None:
                # Construct the unified data object
                case_id = data.get("case_id")
                if not case_id:
                    # Fallback ID extraction for legacy files
                    case_id = p_obj.stem.replace("_Active", "")

                company = data.get("company") or data.get("company_name")
                description = _summarize_text(
                    data.get("description") or data.get("brief_description"), width=120
                )

                tags = []
                if not is_legacy_payload:
                    label = _derive_analysis_label(data, context=context)
                    if label:
                        tags.append(label)

                last_modified = data.get("last_modified")
                if not last_modified:
                    last_modified = (
                        datetime.fromtimestamp(mtime)
                        .replace(microsecond=0)
                        .isoformat()
                    )

                version = data.get("kiroshi_version")
                version_label = f"Kiroshi {version}" if version else f"Pre Kiroshi {VERSION}"
                if is_legacy_payload:
                    version_label = "Legacy JSON (this is only for display and not for case saving.)"

                # Tracking extraction logic merged from legacy workers
                tracking_info = data.get("tracking") or {}
                # Some legacy files might have fields at root
                t_type = tracking_info.get("type", "") or data.get("type", "")
                t_category = tracking_info.get("category", "") or data.get("category", "") or data.get("custom_category") or data.get("service_tag", "")
                t_status = tracking_info.get("status", "") or data.get("status", "")
                t_priority = normalize_priority(tracking_info.get("priority") or data.get("priority"))
                t_ticket = tracking_info.get("ticket_number", "") or data.get("ticket_number", "")
                t_created = tracking_info.get("creation_day", "") or data.get("creation_day", "")
                t_arrival = tracking_info.get("expected_arrival_date", "") or data.get("expected_arrival_date", "")
                t_link = tracking_info.get("case_link", "") or data.get("case_link", "")
                t_tag = tracking_info.get("service_tag", "") or data.get("service_tag", "")

                # Contact info
                end_user = (
                    data.get("contact_name")
                    or data.get("caller_name")
                    or data.get("end_user")
                    or data.get("customer")
                    or ""
                )
                phone = (
                    data.get("phone_number")
                    or data.get("office_ph")
                    or data.get("direct_ph")
                    or ""
                )

                processed = {
                    # Standard list fields
                    "case_id": case_id,
                    "company": company,
                    "description": description,
                    "tags": tags,
                    "updated": last_modified,
                    "last_modified": last_modified, # For compatibility
                    "kiroshi_version": version,
                    "version_label": version_label,
                    "is_legacy": is_legacy_payload,
                    "path": str(path),

                    # Tracking/Dashboard fields
                    "tracking": tracking_info,
                    "end_user": end_user,
                    "phone_number": phone,
                    "type": t_type,
                    "category": t_category,
                    "status": t_status,
                    "priority": t_priority,
                    "ticket_number": t_ticket,
                    "creation_day": t_created,
                    "expected_arrival_date": t_arrival,
                    "case_link": t_link,
                    "service_tag": t_tag,
                }
                processed_updates[path] = (mtime, processed)
            else:
                processed_updates[path] = (mtime, None)
        except Exception:
            processed_updates[path] = (mtime, None)

    # Update cache with processed results (Lock again)
    with cache_obj.lock:
        cache_obj.data.update(processed_updates)
        cache_obj.last_scan_ts = time.time()
        # Create a snapshot for return to avoid iteration issues if modified elsewhere
        snapshot = list(cache_obj.data.values())

    # 3. Collect valid results
    # Sort by updated time (descending) to match expected "recent" behavior
    def _parse_time(t):
        if not t: return 0.0
        try:
            return datetime.fromisoformat(str(t)).timestamp()
        except ValueError:
            return 0.0

    valid_items = [item for _, item in snapshot if item is not None]
    valid_items.sort(key=lambda x: _parse_time(x.get("updated")), reverse=True)

    # Update throttle cache
    throttle.data = valid_items
    throttle.last_run = time.time()

    return valid_items


def _filter_tracked_cases(all_cases: list) -> list:
    """Filter a list of cases to return only those that are tracked."""
    tracked = []
    seen_ids = set()

    for case in all_cases:
        case_id = case.get("case_id")
        if not case_id or case_id in seen_ids:
            continue

        is_active = False

        # Check active flag in tracking dict
        tracking_data = case.get("tracking")
        if isinstance(tracking_data, dict) and tracking_data.get("active"):
            is_active = True

        # Check location (legacy behavior: files in TRACKED_CASES_DIR are implicitly tracked)
        if not is_active:
            path = case.get("path", "")
            if str(TRACKED_CASES_DIR) in path:
                is_active = True

        if is_active:
            tracked.append(case)
            seen_ids.add(case_id)

    return tracked


@st.cache_data(ttl=None, max_entries=1)
def _load_tracked_cases_worker(signature: str) -> list:
    """Load tracked cases from the global case list, cached by signature."""
    # The signature is derived from directory state to invalidate the cache
    all_cases = _refresh_and_get_cases()
    return _filter_tracked_cases(all_cases)


def load_tracked_cases(source_data: list | None = None) -> list:
    if source_data is not None:
        return _filter_tracked_cases(source_data)

    # Compute a lightweight signature of the directory state
    # We use the mtime of the TrackedCases directory and Utilities/recent_cases.json
    # as a proxy for 'something relevant might have changed'.
    # Note: Directory mtime only changes on file add/remove/rename, not content change.
    # However, save_case_to_database updates recent_cases.json on every save,
    # so RECENT_CASES_PATH mtime is a reliable signal for content updates.
    try:
        parts = []
        if TRACKED_CASES_DIR.exists():
            parts.append(f"{TRACKED_CASES_DIR.stat().st_mtime:.6f}")
        if RECENT_CASES_PATH.exists():
            parts.append(f"{RECENT_CASES_PATH.stat().st_mtime:.6f}")

        # Mix in the last saved case timestamp from session state if available
        # to ensure immediate updates after saving within the same session
        if hasattr(st, "session_state"):
            last_save = st.session_state.get("last_save_time")
            if last_save:
                parts.append(str(last_save))

        signature = hashlib.md5("".join(parts).encode("utf-8")).hexdigest()
    except Exception:
        # Fallback to current time to force refresh if signature computation fails
        signature = str(time.time())

    return _load_tracked_cases_worker(signature)


def update_tracked_case_file(
    path: str,
    *,
    tracking_updates: Mapping[str, object] | None = None,
    **updates,
) -> str | None:
    try:
        case_path = Path(path)
        payload = json.loads(case_path.read_text(encoding="utf-8"))
        data = _coerce_case_mapping(payload)
        if data is None:
            raise ValueError("Unsupported case file structure for tracking update")
        if tracking_updates:
            if isinstance(data.get("tracking"), dict):
                tracking_data = data.get("tracking", {})
                tracking_data.update(tracking_updates)
                data["tracking"] = tracking_data
            else:
                data.update(tracking_updates)
        if updates:
            data.update(updates)
        timestamp = _utc_now_z()
        if isinstance(data, Mapping):
            data["last_modified"] = timestamp
        if isinstance(payload, list):
            mapping_positions = [
                (idx, item)
                for idx, item in enumerate(payload)
                if isinstance(item, Mapping)
            ]
            if mapping_positions:
                latest_idx, _ = max(
                    mapping_positions,
                    key=lambda pair: _mapping_freshness_score(pair[1], pair[0]),
                )
                payload[latest_idx] = data
            else:
                payload.append(data)
            to_write = payload
        else:
            to_write = data
        case_path.write_text(json.dumps(to_write, indent=2), encoding="utf-8")
        _reset_tracked_cases_cache()
        return timestamp
    except Exception as exc:
        logging.exception("Failed to update tracked case %s", path)
        st.error(f"Failed to update tracked case: {exc}")
        return None


def _apply_tracked_priority_update(
    path: str,
    new_priority: str,
    *,
    case_id: str | None = None,
    is_legacy: bool = False,
) -> tuple[str, str | None]:
    normalized_priority = normalize_priority(new_priority)
    if is_legacy:
        timestamp = update_tracked_case_file(path, priority=normalized_priority)
    else:
        timestamp = update_tracked_case_file(
            path, tracking_updates={"priority": normalized_priority}
        )
    target_case_id = case_id
    if target_case_id is None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            target_case_id = data.get("case_id")
        except Exception:
            target_case_id = None
    if target_case_id and D.case_id == target_case_id:
        D.tracking.priority = normalized_priority
        st.session_state[widget_state_key("track_priority", CURRENT_CASE_IDX)] = (
            normalized_priority
        )
        if timestamp:
            touch_case_last_modified(timestamp=timestamp)
    return normalized_priority, timestamp


def update_tracked_priority(
    path: str,
    key: str,
    *,
    case_id: str | None = None,
    is_legacy: bool = False,
) -> None:
    new_priority = normalize_priority(st.session_state.get(key))
    _apply_tracked_priority_update(
        path,
        new_priority,
        case_id=case_id,
        is_legacy=is_legacy,
    )
    st.toast("Priority updated") if hasattr(st, "toast") else None


def update_tracked_status(
    path: str,
    key: str,
    *,
    case_id: str | None = None,
    is_legacy: bool = False,
) -> None:
    new_status = st.session_state.get(key, "") or ""
    if is_legacy:
        timestamp = update_tracked_case_file(path, status=new_status)
    else:
        timestamp = update_tracked_case_file(
            path, tracking_updates={"status": new_status}
        )
    target_case_id = case_id
    if target_case_id is None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            target_case_id = data.get("case_id")
        except Exception:
            target_case_id = None
    if target_case_id and D.case_id == target_case_id:
        D.tracking.status = new_status
        status_key = widget_state_key("track_status", CURRENT_CASE_IDX)
        st.session_state[status_key] = new_status
        if timestamp:
            touch_case_last_modified(timestamp=timestamp)
    st.toast("Status updated") if hasattr(st, "toast") else None


def untrack_case(path: str, *, case_id: str | None = None, is_legacy: bool | None = None) -> None:
    """Deactivate tracking for a case and refresh the dashboard."""

    case_path = Path(path)
    legacy_source = (
        is_legacy
        if is_legacy is not None
        else case_path.parent == TRACKED_CASES_DIR or case_path.name.endswith("_Active.json")
    )
    try:
        data = json.loads(case_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.exception("Failed to read tracked case %s", path)
        st.error(f"Failed to untrack case: {exc}")
        return

    if not legacy_source and isinstance(data.get("tracking"), dict):
        tracking = data.get("tracking", {})
        tracking["active"] = False
        data["tracking"] = tracking
        target_case_id = case_id or data.get("case_id") or case_path.stem
        try:
            case_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logging.exception("Failed to persist updated case %s", path)
            st.error(f"Failed to update case: {exc}")
            return
        _reset_tracked_cases_cache()
        if target_case_id:
            update_recent_cases(target_case_id, str(case_path), case_data=payload)
        if D.case_id == target_case_id:
            D.tracking.active = False
            st.session_state.track_case = False
        st.toast("Case removed from tracking.") if hasattr(st, "toast") else st.success(
            "Case removed from tracking."
        )
        st.rerun()
        return

    try:
        case_id_value = case_id or data.get("case_id") or case_path.stem.replace("_Active", "")
        if not case_id_value:
            case_path.unlink(missing_ok=True)
            return
        safe_case_id = sanitize_case_id(case_id_value)
        dest = DATABASE_DIR / f"{safe_case_id}.json"
        payload = {k: v for k, v in data.items() if k != "path"}

        if dest.exists():
            try:
                existing = json.loads(dest.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
            if isinstance(existing, dict):
                existing.update(payload)
                dest.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            else:
                dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        else:
                dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        case_path.unlink(missing_ok=True)
        _reset_tracked_cases_cache()
        update_recent_cases(case_id_value, str(dest), case_data=payload)
        st.toast("Case removed from tracking.") if hasattr(st, "toast") else st.success(
            "Case removed from tracking."
        )
        st.rerun()
    except Exception as exc:
        logging.exception("Failed to untrack tracked case %s", path)
        st.error(f"Failed to untrack case: {exc}")


@st.cache_data(ttl=None, max_entries=1)
def _load_sprint_state_worker(mtime: float) -> SprintState:
    """Load sprint state from disk, cached until modification time changes."""
    try:
        data = json.loads(SPRINT_STATE_FILE.read_text(encoding="utf-8"))
        # Clean up corrupted entries if any
        if "completed_cases" in data:
            data["completed_cases"] = [
                entry
                for entry in data["completed_cases"]
                if isinstance(entry, dict) and "case_id" in entry
            ]
        return SprintState(**data)
    except Exception:
        return SprintState()


def load_sprint_state() -> SprintState:
    mtime = 0.0
    if SPRINT_STATE_FILE.exists():
        try:
            mtime = SPRINT_STATE_FILE.stat().st_mtime
        except OSError:
            pass
    return _load_sprint_state_worker(mtime)


def save_sprint_state(state: SprintState) -> None:
    try:
        data = asdict(state)
        SPRINT_STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logging.error("Failed to save sprint state: %s", exc)


def get_tracked_cases_for_sprint() -> list[dict[str, object]]:
    return load_tracked_cases()


@st.cache_data(ttl=None, max_entries=100)
def _load_full_case_data_worker(path: str, mtime: float) -> dict[str, object]:
    """Worker for load_full_case_data, cached by modification time."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_full_case_data(path: str) -> dict[str, object]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return {}
    return _load_full_case_data_worker(path, mtime)


def update_case_fields(path: str, fields: dict[str, object]) -> None:
    update_tracked_case_file(path, **fields)


def set_tracked_status(path: str, status: str, case_id: str | None = None) -> None:
    update_tracked_case_file(path, tracking_updates={"status": status})
    if case_id and getattr(st.session_state.get("case"), "case_id", None) == case_id:
        st.session_state.case.tracking.status = status
        status_key = widget_state_key("track_status", CURRENT_CASE_IDX)
        if status_key in st.session_state:
            st.session_state[status_key] = status
        touch_case_last_modified()


def ai_prioritize_tasks(tasks: list[SprintTask]) -> list[SprintTask]:
    if not tasks:
        return []

    task_descriptions = []
    for i, t in enumerate(tasks):
        task_descriptions.append(
            f"ID: {i}, Case: {t.case_id}, Priority: {t.priority}, Escalated: {t.is_escalated}, "
            f"Root Cause: {t.root_cause}, Solution: {t.solution}"
        )

    prompt = (
        "You are an AI Scrum Master. Prioritize the following support tasks for today's sprint. "
        "Escalated cases must come first. High priority cases next. "
        "Also, provide a brief 1-sentence suggestion and a time estimate for each task. "
        "Return a JSON object with a key 'tasks' containing a list of objects. "
        "Each object must have: 'original_id' (int), 'ai_suggestion' (str), 'ai_time_estimate' (str). "
        "Sort the list in the order they should be tackled.\n\n"
        "Tasks:\n" + "\n".join(task_descriptions)
    )

    try:
        api_key = st.session_state.openai_api_key
        model = st.session_state.openai_model
        base_url = st.session_state.ai_base_url

        # Guard against missing API key if using cloud
        if not api_key and base_url.startswith("https://api.openai.com"):
            # Fallback simple sort if AI unavailable
            return sorted(
                tasks, key=lambda x: (not x.is_escalated, x.priority != "High")
            )

        reply = invoke_gpt(
            prompt,
            [],
            api_key,
            model,
            base_url,
            source="sprint_prioritization",
        )
        data = _extract_json_object(reply)
        if not data or "tasks" not in data:
            return sorted(
                tasks, key=lambda x: (not x.is_escalated, x.priority != "High")
            )

        prioritized_tasks = []
        processed_ids = set()
        if isinstance(data["tasks"], list):
            for item in data["tasks"]:
                if not isinstance(item, dict):
                    continue
                idx = item.get("original_id")
                if idx is not None and isinstance(idx, int) and 0 <= idx < len(tasks):
                    t = tasks[idx]
                    t.ai_suggestion = str(item.get("ai_suggestion", ""))
                    t.ai_time_estimate = str(item.get("ai_time_estimate", ""))
                    prioritized_tasks.append(t)
                    processed_ids.add(idx)

        # Add any missing tasks at the end
        for i, t in enumerate(tasks):
            if i not in processed_ids:
                prioritized_tasks.append(t)

        return prioritized_tasks

    except Exception as e:
        logging.error("AI prioritization failed: %s", e)
        return sorted(tasks, key=lambda x: (not x.is_escalated, x.priority != "High"))


def generate_sprint_pdf_report(state: SprintState) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=30,
    )
    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    title_style = styles["Title"]
    heading_style = styles["Heading3"]
    body_style = styles["BodyText"]

    elements = []
    ghost_snippets = ["Sprint Execution Report", f"Date: {state.date}"]

    elements.append(Paragraph("Sprint Execution Report", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Date: {state.date}", heading_style))
    elements.append(Spacer(1, 24))

    completed = [t for t in state.tasks if t.status == "Completed"]
    pending = [t for t in state.tasks if t.status != "Completed"]

    summary_data = [
        ["Total Tasks", str(len(state.tasks))],
        ["Completed", str(len(completed))],
        ["Pending", str(len(pending))],
    ]

    t = Table(summary_data, colWidths=[150, 100])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), bold_font),
            ]
        )
    )
    elements.append(t)
    elements.append(Spacer(1, 24))

    if completed:
        elements.append(Paragraph("Completed Tasks", heading_style))
        ghost_snippets.append("Completed Tasks")
        for task in completed:
            elements.append(
                Paragraph(f"<b>{task.case_id}</b> - {task.company}", body_style)
            )
            elements.append(Paragraph(f"Root Cause: {task.root_cause}", body_style))
            elements.append(Paragraph(f"Solution: {task.solution}", body_style))
            elements.append(Spacer(1, 12))
            ghost_snippets.extend(
                [task.case_id, task.company, task.root_cause, task.solution]
            )

    if pending:
        elements.append(Paragraph("Pending Tasks", heading_style))
        ghost_snippets.append("Pending Tasks")
        for task in pending:
            elements.append(
                Paragraph(
                    f"<b>{task.case_id}</b> - {task.company} ({task.priority})",
                    body_style,
                )
            )
            if task.is_escalated:
                elements.append(
                    Paragraph("<font color='red'>ESCALATED</font>", body_style)
                )
            elements.append(Spacer(1, 12))
            ghost_snippets.extend([task.case_id, task.company, task.priority])

    _build_pdf_with_ghost_text(doc, elements, ghost_snippets)
    buffer.seek(0)
    return buffer.read()


def format_tracking_date(value) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def parse_iso_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def format_last_modified(value) -> str:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M")


def list_saved_cases(source_data: list[dict[str, object]] | None = None) -> list:
    """Retrieve all saved cases using the optimized global cache."""
    all_cases = source_data if source_data is not None else _refresh_and_get_cases()

    # We need to adapt the format to match what _list_saved_cases_worker used to return
    # The cache returns a superset, but fields like 'updated' might be strings there.
    # The legacy view expects 'updated' as datetime object.

    formatted_entries = []

    for case in all_cases:
        # Re-construct fields that might need specific types for the saved cases table
        updated_val = case.get("updated") # This is string isoformat in cache

        # Parse back to datetime for sorting/display logic in consumer
        dt_updated = parse_iso_datetime(updated_val)

        # Ensure we have fallback if parsing failed (should be handled in cache but safe to double check)
        if dt_updated is None:
            # Fallback to current time is misleading, use epoch 0
            dt_updated = datetime.fromtimestamp(0)

        # Tags construction (re-applying logic if not fully in cache or if needed)
        # Cache stores 'tags' from _derive_analysis_label.
        # Legacy worker also added "Legacy JSON", "Pre-dashboard merge".

        tags = list(case.get("tags") or [])
        is_legacy = case.get("is_legacy")
        if is_legacy:
            if "Legacy JSON" not in tags:
                tags.append("Legacy JSON")

        tracking_info = case.get("tracking")
        has_tracking = isinstance(tracking_info, dict) and bool(tracking_info)
        # Note: empty dict is still 'has_tracking' in type check, but might be empty.
        # Legacy check was: isinstance(data.get("tracking"), Mapping)

        if not has_tracking and "Pre-dashboard merge" not in tags:
            tags.append("Pre-dashboard merge")

        # Version fallback logic
        version = case.get("kiroshi_version")
        if not version:
            if not has_tracking:
                version = "1.5.2"
            elif is_legacy:
                version = "Legacy"
            else:
                version = "Unknown"

        entry = {
            "case_id": case.get("case_id"),
            "company": case.get("company"),
            "end_user": case.get("end_user"),
            "updated": dt_updated,
            "last_modified": updated_val,
            "path": case.get("path"),
            "file_name": Path(case.get("path")).name if case.get("path") else "",
            "is_legacy": is_legacy,
            "kiroshi_version": version,
            "tags": tags,
            "has_tracking": has_tracking,
            # Description is needed for search
            "description": case.get("description"),
        }
        formatted_entries.append(entry)

    return formatted_entries


def render_responsive_altair_chart(chart: alt.Chart) -> None:
    """Render an Altair chart using the best available width argument."""

    st.altair_chart(chart, **ALTAIR_CHART_KWARGS)


def render_tracked_case_insights(cases: list) -> None:
    st.subheader("Tracked Case Insights")
    if not cases:
        st.caption("No tracked cases to visualize yet.")
        return

    df = pd.DataFrame(cases)
    if "priority" in df:
        priority_counts = (
            df.assign(priority=df["priority"].fillna(DEFAULT_TRACKING_PRIORITY))
            .groupby("priority", dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        priority_chart = (
            alt.Chart(priority_counts)
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X("count:Q", title="Cases"),
                y=alt.Y("priority:N", sort="-x", title="Priority"),
                color=alt.Color("priority:N", legend=None),
                tooltip=["priority", "count"],
            )
            .properties(height=140)
        )
        render_responsive_altair_chart(priority_chart)

    if "status" in df:
        status_counts = (
            df.assign(status=df["status"].fillna("Unknown"))
            .groupby("status", dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        status_chart = (
            alt.Chart(status_counts)
            .mark_bar()
            .encode(
                x=alt.X("status:N", sort="-y", title="Status"),
                y=alt.Y("count:Q", title="Cases"),
                color=alt.Color("count:Q", legend=None),
                tooltip=["status", "count"],
            )
            .properties(height=200)
        )
        render_responsive_altair_chart(status_chart)

    if "creation_day" in df:
        created_series = pd.to_datetime(df["creation_day"], errors="coerce")
        if not created_series.isna().all():
            timeline = (
                created_series.dropna()
                .dt.floor("D")
                .value_counts()
                .rename_axis("day")
                .reset_index(name="cases")
                .sort_values("day")
            )
            timeline_chart = (
                alt.Chart(timeline)
                .mark_area(line=True, point=True, interpolate="monotone")
                .encode(
                    x=alt.X("day:T", title="Created"),
                    y=alt.Y("cases:Q", title="Tracked cases"),
                    tooltip=["day:T", "cases"],
                )
                .properties(height=160)
            )
            render_responsive_altair_chart(timeline_chart)


def render_crm_link_button(url: str) -> None:
    safe_url = (url or "").strip()
    if not safe_url:
        return
    st.markdown(
        f"<a class='crm-link' href='{escape(safe_url)}' target='_blank' rel='noopener noreferrer'>Open in CRM</a>",
        unsafe_allow_html=True,
    )


def render_tracked_cases_dashboard(
    cases: list,
    search_query: str = "",
    *,
    show_notifications: bool = True,
    key_namespace: str = "tracked",
) -> None:
    if not cases:
        st.info("No cases are currently being tracked.")
        return
    filtered_cases = cases
    query = search_query.strip().lower()
    if query:
        filtered_cases = []
        for case in cases:
            priority_value = normalize_priority(case.get("priority"))
            haystack = [
                str(case.get("company", "")),
                str(case.get("status", "")),
                str(case.get("case_id", "")),
                str(case.get("priority", "")),
                priority_value,
            ]
            if any(query in field.lower() for field in haystack if field):
                filtered_cases.append(case)
    if not filtered_cases:
        st.info("No tracked cases match your search.")
        return
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sorted_cases = sorted(
        filtered_cases,
        key=lambda item: (
            PRIORITY_RANK.get(item.get("priority"), -1),
            item.get("creation_day") or "",
        ),
        reverse=True,
    )
    for idx, case in enumerate(sorted_cases):
        path_digest = hashlib.sha1(case["path"].encode("utf-8")).hexdigest()[:8]
        unique_suffix = f"{key_namespace}_{Path(case['path']).stem}_{idx}_{path_digest}"
        priority_value = normalize_priority(case.get("priority"))
        priority_key = f"priority_{unique_suffix}"
        status_key = f"status_{unique_suffix}"
        case_id_display = case.get("case_id") or "Unknown Case"
        last_modified_str = case.get("last_modified")
        last_modified_dt = parse_iso_datetime(last_modified_str)
        idle_delta: timedelta | None = None
        if last_modified_dt:
            try:
                idle_delta = now - last_modified_dt
            except Exception:
                idle_delta = None

        reminder_due = False
        warning_text: str | None = None
        auto_escalated = False
        auto_escalation_delta: timedelta | None = None

        if idle_delta and idle_delta.total_seconds() >= 0:
            hours_since_update = idle_delta.total_seconds() / 3600
            duration_display = _format_timedelta_compact(idle_delta)
            if priority_value in {"Low", "Normal"}:
                if hours_since_update >= 24:
                    reminder_due = True
                    warning_text = (
                        f"Reminder: Case ID {case_id_display} hasn't been updated for "
                        f"{duration_display}. Low and Normal priorities should get an update "
                        "at least every 24 hours."
                    )
            elif priority_value in {"High", "Escalation"}:
                if hours_since_update >= 6:
                    reminder_due = True
                    warning_text = (
                        f"Reminder: Case ID {case_id_display} hasn't been updated for "
                        f"{duration_display}. High and Escalation priorities alert after 6 "
                        "hours without activity."
                    )
            elif priority_value == "On Time":
                if hours_since_update >= 4:
                    auto_escalated = True
                    auto_escalation_delta = idle_delta
                    updated_priority, timestamp = _apply_tracked_priority_update(
                        case["path"],
                        "High",
                        case_id=case.get("case_id"),
                        is_legacy=case.get("is_legacy", False),
                    )
                    priority_value = updated_priority
                    case["priority"] = updated_priority
                    if timestamp:
                        case["last_modified"] = timestamp
                        last_modified_dt = parse_iso_datetime(timestamp)
                        idle_delta = (
                            datetime.now(timezone.utc).replace(tzinfo=None) - last_modified_dt
                            if last_modified_dt
                            else None
                        )
                    st.session_state[priority_key] = updated_priority
                elif hours_since_update >= 1:
                    reminder_due = True
                    warning_text = (
                        f"Reminder: Case ID {case_id_display} hasn't been updated for "
                        f"{duration_display}. On Time cases ping every hour and are "
                        "automatically escalated to High after 4 hours without updates."
                    )

        if auto_escalated:
            reminder_due = True
            escalation_duration = (
                _format_timedelta_compact(auto_escalation_delta)
                if auto_escalation_delta
                else "4h"
            )
            warning_text = (
                f"Priority automatically escalated to High after {escalation_duration} "
                f"without updates. Case ID: {case_id_display}."
            )

        last_modified_display = format_last_modified(case.get("last_modified"))
        if reminder_due and warning_text and show_notifications:
            st.warning(warning_text)
        summary = " ".join(
            part
            for part in [
                PRIORITY_BADGES.get(priority_value, "🔘"),
                case.get("case_id") or "Unknown Case",
                "•",
                case.get("company") or "—",
                "•",
                case.get("status") or "—",
                "•",
                case.get("category") or "—",
                "•",
                priority_value,
            ]
            if part
        )
        expander = st.expander(summary, expanded=False)
        with expander:
            version_label = case.get("version_label")
            if version_label:
                st.caption(version_label)
            info_left, info_right = st.columns(2)
            with info_left:
                render_case_metadata("Type", case.get("type", ""))
                render_case_metadata("Case ID", case.get("case_id", ""))
                render_case_metadata("Company", case.get("company", ""))
                render_case_metadata("End User", case.get("end_user", ""))
                render_case_metadata("Phone", case.get("phone_number", ""))
                render_case_metadata("Category", case.get("category", ""))
            with info_right:
                render_case_metadata("Created", format_tracking_date(case.get("creation_day")))
                render_case_metadata("Ticket", case.get("ticket_number", ""))
                render_case_metadata("Status", case.get("status", ""))
                render_case_metadata("Priority", priority_value)
                render_case_metadata("Last Modified", last_modified_display)
                if case.get("expected_arrival_date"):
                    render_case_metadata(
                        "Expected Arrival",
                        format_tracking_date(case.get("expected_arrival_date")),
                    )
                if case.get("service_tag") and not case.get("category"):
                    render_case_metadata("Service Tag", case.get("service_tag"))
            if case.get("case_link"):
                render_crm_link_button(case.get("case_link", ""))

            controls = st.columns(2)
            if (
                priority_key not in st.session_state
                or st.session_state.get(priority_key) != priority_value
            ):
                st.session_state[priority_key] = priority_value
            if (
                status_key not in st.session_state
                or st.session_state.get(status_key) != case.get("status", "")
            ):
                st.session_state[status_key] = case.get("status", "")

            with controls[0]:
                if case.get("is_legacy"):
                    st.caption("Priority editing is unavailable for legacy JSON files.")
                else:
                    st.selectbox(
                        "Priority",
                        PRIORITY_OPTIONS,
                        key=priority_key,
                        on_change=lambda path=case["path"], key=priority_key, cid=case.get("case_id"), legacy=case.get("is_legacy", False): update_tracked_priority(
                            path,
                            key,
                            case_id=cid,
                            is_legacy=legacy,
                        ),
                    )
            with controls[1]:
                if case.get("is_legacy"):
                    st.caption("Status editing is unavailable for legacy JSON files.")
                else:
                    options = TRACKING_STATUS_OPTIONS.get(case.get("type"))
                    free_text_status = case.get("type") in {"Dell", "FedEx"}
                    if options and not free_text_status:
                        status_options = list(options)
                        current_status = case.get("status", "")
                        if current_status and current_status not in status_options:
                            status_options = [current_status] + [
                                opt for opt in status_options if opt != current_status
                            ]
                        st.selectbox(
                            "Status",
                            status_options,
                            key=status_key,
                            on_change=lambda path=case["path"], key=status_key, cid=case.get("case_id"), legacy=case.get("is_legacy", False): update_tracked_status(
                                path,
                                key,
                                case_id=cid,
                                is_legacy=legacy,
                            ),
                        )
                    else:
                        st.text_input(
                            "Status",
                            key=status_key,
                            on_change=lambda path=case["path"], key=status_key, cid=case.get("case_id"), legacy=case.get("is_legacy", False): update_tracked_status(
                                path,
                                key,
                                case_id=cid,
                                is_legacy=legacy,
                            ),
                        )

            action_cols = st.columns(2)
            with action_cols[0]:
                if st.button(
                    "Load",
                    key=f"dash_load_{unique_suffix}",
                    help="Load this case into a new tab in the workspace",
                ):
                    request_load_from_path(case["path"], prefer_new_tab=True)
            with action_cols[1]:
                button_label = "Untrack" if case.get("is_legacy") else "Stop Tracking"
                if st.button(
                    button_label,
                    key=f"dash_untrack_{unique_suffix}",
                    help="Remove this case from the dashboard tracking list (data is preserved)",
                ):
                    untrack_case(
                        case["path"],
                        case_id=case.get("case_id"),
                        is_legacy=case.get("is_legacy"),
                    )


def render_case_metadata(label: str, value: str | None) -> None:
    display_value = value if value not in (None, "") else "—"
    st.markdown(
        f"<div class='case-meta'>"
        f"<span class='case-meta__label'>{label}</span>"
        f"<span class='case-meta__value'>{display_value}</span>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_dell_fedex_dashboard(cases: list) -> None:
    dell_cases = [c for c in cases if c.get("type") == "Dell"]
    fedex_cases = [c for c in cases if c.get("type") == "FedEx"]
    st.markdown("**Dell Escalations**")
    if dell_cases:
        render_tracked_cases_dashboard(
            dell_cases,
            show_notifications=False,
            key_namespace="dell_dashboard",
        )
    else:
        st.caption("No Dell escalations in the queue.")

    st.markdown("**FedEx Replacements**")
    if fedex_cases:
        render_tracked_cases_dashboard(
            fedex_cases,
            show_notifications=False,
            key_namespace="fedex_dashboard",
        )
    else:
        st.caption("No FedEx replacements awaiting action.")


def _start_day_logic(today_date: str):
    """Populates the sprint tasks from tracked cases."""
    tracked_cases = get_tracked_cases_for_sprint()
    tasks = []

    with st.spinner("AI Scrum Master is prioritizing your day..."):
        for case in tracked_cases:
            priority = case.get("priority", "Normal")
            is_escalated = priority in ["High", "Critical", "Escalation"]
            source_path = case.get("path", "")

            # Load full data to get existing Root Cause / Solution
            full_data = {}
            if source_path:
                full_data = load_full_case_data(source_path)

            root_cause = full_data.get("root_cause", "")
            solution = full_data.get("solution", "")

            tasks.append(
                SprintTask(
                    case_id=str(case.get("case_id", "Unknown")),
                    company=str(case.get("company", "Unknown")),
                    priority=priority,
                    status="Pending",
                    is_escalated=is_escalated,
                    source_path=str(source_path),
                    root_cause=str(root_cause),
                    solution=str(solution),
                )
            )

        # AI Prioritization call
        if tasks:
            tasks = ai_prioritize_tasks(tasks)

    new_state = SprintState(date=today_date, tasks=tasks, is_active=True)
    st.session_state.sprint_state = new_state
    save_sprint_state(new_state)
    st.success(f"Day started! {len(tasks)} tasks loaded.")


def render_sprint_tab() -> None:
    st.markdown(
        "<div class='dashboard-title'>Sprint & Task Execution</div>",
        unsafe_allow_html=True,
    )

    # Check if a sprint is active
    current_state = load_sprint_state()
    today_date = _utc_now_z().split("T")[0]

    # Initialize session state if needed or if loading fresh
    if "sprint_state" not in st.session_state:
        st.session_state.sprint_state = current_state

    # 1. Start Day / End Shift
    col1, col2 = st.columns(2)
    with col1:
        if not st.session_state.sprint_state.is_active:
            if st.button("Start Day", help="Reset session counters and prepare for a new shift"):
                _start_day_logic(today_date)
                st.rerun()
        else:
            st.info(f"Sprint Active for {st.session_state.sprint_state.date}")

    with col2:
        if st.session_state.sprint_state.is_active:
            # We put End Shift logic in a separate container/modal flow usually,
            # but here a button triggering PDF download and state close is fine.
            st.write("")  # Spacer

    if not st.session_state.sprint_state.is_active:
        st.info("Start your day to see tasks and AI insights.")
        return

    # 2. Progress
    tasks = st.session_state.sprint_state.tasks
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == "Completed"])
    if total_tasks > 0:
        progress = completed_tasks / total_tasks
        st.progress(progress, text=f"Progress: {completed_tasks}/{total_tasks}")

    # 3. Task List (Sprint Board)
    st.subheader("Today's Tasks")

    # End Shift Logic (Placed here to be accessible when active)
    with col2:
        if st.download_button(
            label="📄 End Shift & Export Report",
            data=generate_sprint_pdf_report(st.session_state.sprint_state),
            file_name=f"Sprint_Report_{st.session_state.sprint_state.date}.pdf",
            mime="application/pdf",
            key="end_shift_btn",
            help="Generate a PDF report of completed tasks and close the current sprint",
        ):
            pass

        if st.button("Close Shift (Reset)", help="Archive all active cases and reset the workspace"):
            state = st.session_state.sprint_state
            state.is_active = False
            save_sprint_state(state)
            st.session_state.sprint_state = state
            st.success("Shift closed.")
            st.rerun()

    if not tasks:
        st.info("No tasks for today.")
    else:
        # Sort: Escalated first, then by priority
        # We need to ensure types are sortable (bool is int, so fine)
        sorted_tasks = sorted(tasks, key=lambda x: (not x.is_escalated, x.case_id))

        for idx, task in enumerate(sorted_tasks):
            # Dynamic expander label
            fire_emoji = "🔥 " if task.is_escalated else ""
            status_label = f"({task.status})"
            label = f"{fire_emoji}{task.case_id} - {task.company} {status_label}"
            with st.expander(label, expanded=task.status != "Completed"):
                col_info, col_action = st.columns([3, 1])
                with col_info:
                    st.write(f"**Priority:** {task.priority}")
                    if task.ai_suggestion:
                        st.info(f"🤖 **AI Suggestion:** {task.ai_suggestion}")
                    if task.ai_time_estimate:
                        st.caption(f"Estimated Time: {task.ai_time_estimate}")

                    # Editable fields with sync
                    # Use unique keys for each task to avoid conflicts
                    rc_key = f"rc_{task.case_id}_{idx}"
                    sol_key = f"sol_{task.case_id}_{idx}"

                    new_rc = st.text_input(
                        "Root Cause", value=task.root_cause, key=rc_key
                    )
                    new_sol = st.text_area(
                        "Solution", value=task.solution, key=sol_key
                    )

                    # Detect changes and sync to DB
                    if new_rc != task.root_cause or new_sol != task.solution:
                        task.root_cause = new_rc
                        task.solution = new_sol
                        save_sprint_state(st.session_state.sprint_state)

                        # Sync to Main Database
                        if task.source_path:
                            update_case_fields(
                                task.source_path,
                                {
                                    "root_cause": new_rc,
                                    "solution": new_sol,
                                },
                            )
                            # Using toast if available, or success/info
                            if hasattr(st, "toast"):
                                st.toast(
                                    f"Saved updates for {task.case_id} to database."
                                )

                with col_action:
                    if task.status != "Completed":
                        if st.button(
                            "Mark Complete",
                            key=f"btn_comp_{task.case_id}_{idx}",
                            help="Mark this task as completed and resolve the case globally",
                        ):
                            task.status = "Completed"
                            # Also mark case as Resolved globally
                            if task.source_path:
                                try:
                                    set_tracked_status(
                                        path=task.source_path,
                                        status="Resolved",
                                        case_id=task.case_id,
                                    )
                                    if hasattr(st, "toast"):
                                        st.toast(
                                            f"Case {task.case_id} marked as Resolved globally."
                                        )
                                except Exception as e:
                                    st.error(f"Failed to update global status: {e}")

                            save_sprint_state(st.session_state.sprint_state)
                            st.rerun()
                    else:
                        st.success("Completed")
                        if st.button(
                            "Reopen",
                            key=f"btn_reopen_{task.case_id}_{idx}",
                            help="Reopen this task for further work",
                        ):
                            task.status = "Pending"
                            save_sprint_state(st.session_state.sprint_state)
                            st.rerun()


def render_saved_cases_dashboard(source_data: list[dict[str, object]] | None = None) -> None:
    saved_cases = list_saved_cases(source_data=source_data)
    if not saved_cases:
        st.info("No saved cases found in your database.")
        return
    st.caption("Preview of your most recent saved cases. Use the Saved Cases tab for the full index.")
    preview = saved_cases[:5]
    weights = [1.2, 1.4, 1.1, 1.0, 0.8]
    header_cols = st.columns(weights)
    header_cols[0].markdown("**Case ID**")
    header_cols[1].markdown("**Company**")
    header_cols[2].markdown("**Version**")
    header_cols[3].markdown("**Last Modified**")
    header_cols[4].markdown("**Load**")
    for case in preview:
        row_cols = st.columns(weights)
        row_cols[0].write(case["case_id"])
        company_display = case["company"] or "—"
        badges: list[str] = []
        if case.get("is_legacy"):
            badges.append("Legacy")
        if case.get("tags"):
            badges.extend(case["tags"])
        if badges:
            company_display = f"{company_display}\n{' · '.join(dict.fromkeys(badges))}"
        row_cols[1].write(company_display)
        row_cols[2].write(case.get("kiroshi_version") or "Unknown")
        row_cols[3].write(case["updated"].strftime("%Y-%m-%d %H:%M"))
        if row_cols[4].button(
            "Load",
            key=f"saved_load_{Path(case['path']).stem}",
            help="Load this case into a new tab in the workspace",
        ):
            request_load_from_path(case["path"], prefer_new_tab=True)


def render_saved_cases_page() -> None:
    st.markdown(
        "<div class='dashboard-title'>Saved Cases</div>",
        unsafe_allow_html=True,
    )
    saved_cases = list_saved_cases()
    if not saved_cases:
        st.info("No saved cases found in your database.")
        return

    saved_df = pd.DataFrame(saved_cases)
    saved_df["updated"] = pd.to_datetime(saved_df["updated"])
    saved_df["display_last_modified"] = saved_df["updated"].dt.strftime("%Y-%m-%d %H:%M")
    saved_df["tags_text"] = saved_df["tags"].apply(
        lambda tags: ", ".join(dict.fromkeys(tags)) if tags else ""
    )
    saved_df["legacy_label"] = saved_df["is_legacy"].map({True: "Yes", False: "No"})

    version_options = sorted(
        {str(v) for v in saved_df["kiroshi_version"].dropna().unique() if str(v).strip()}
    )
    total_cases = len(saved_df)
    legacy_total = int(saved_df["is_legacy"].sum())

    metrics = st.columns(3)
    metrics[0].metric("Saved cases", total_cases)
    metrics[1].metric("Legacy records", legacy_total)
    metrics[2].metric("Known versions", len(version_options))

    search_term = st.text_input(
        "Search saved cases",
        key=global_widget_key("saved_cases_search"),
        placeholder="Search by case ID, company, end user, path, or notes",
        help="Filter your case history by ID, Company, Version, or path.",
    )

    filter_cols = st.columns((1.4, 1.2, 1.0))
    tracking_scope = filter_cols[0].selectbox(
        "Layout",
        (
            "All records",
            "Merged dashboards only",
            "Missing merged dashboards",
        ),
        key=global_widget_key("saved_cases_tracking_filter"),
        help="Filter cases based on whether they have dashboard tracking data enabled.",
    )
    selected_versions = filter_cols[1].multiselect(
        "Version",
        options=version_options,
        default=version_options,
        key=global_widget_key("saved_cases_version_filter"),
        help="Filter cases by the Kiroshi version used to create them.",
    )
    legacy_scope = filter_cols[2].selectbox(
        "Legacy",
        ("All", "Modern only", "Legacy only"),
        key=global_widget_key("saved_cases_legacy_filter"),
        help="Filter cases based on their data structure format (Modern vs Legacy).",
    )

    filtered_df = saved_df.copy()
    if selected_versions:
        filtered_df = filtered_df[filtered_df["kiroshi_version"].isin(selected_versions)]
    else:
        filtered_df = filtered_df.iloc[0:0]

    if legacy_scope == "Modern only":
        filtered_df = filtered_df[~filtered_df["is_legacy"]]
    elif legacy_scope == "Legacy only":
        filtered_df = filtered_df[filtered_df["is_legacy"]]

    if tracking_scope == "Merged dashboards only":
        filtered_df = filtered_df[filtered_df["has_tracking"]]
    elif tracking_scope == "Missing merged dashboards":
        filtered_df = filtered_df[~filtered_df["has_tracking"]]

    search_value = search_term.strip().lower()
    if search_value:
        search_columns = [
            "case_id",
            "company",
            "end_user",
            "file_name",
            "path",
            "kiroshi_version",
            "tags_text",
        ]
        filtered_df = filtered_df[
            filtered_df.apply(
                lambda row: any(
                    search_value in str(row.get(col, "")).lower()
                    for col in search_columns
                ),
                axis=1,
            )
        ]

    filtered_df = filtered_df.sort_values("updated", ascending=False)
    display_df = filtered_df[
        [
            "case_id",
            "company",
            "end_user",
            "kiroshi_version",
            "legacy_label",
            "display_last_modified",
            "tags_text",
            "path",
        ]
    ].rename(
        columns={
            "case_id": "Case ID",
            "company": "Company",
            "end_user": "End user",
            "kiroshi_version": "Version",
            "legacy_label": "Legacy",
            "display_last_modified": "Last modified",
            "tags_text": "Notes",
            "path": "File path",
        }
    )

    st.caption(
        f"Showing {len(display_df)} of {total_cases} saved cases after filters."
    )
    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
    )

    if not filtered_df.empty:
        filtered_records = filtered_df.to_dict("records")
        option_labels = [
            f"{record.get('case_id') or record.get('file_name')} · {record.get('company') or '—'} · {record.get('kiroshi_version')}"
            for record in filtered_records
        ]
        selection = st.selectbox(
            "Select a case to load or export",
            options=list(range(len(filtered_records))),
            format_func=lambda idx: option_labels[idx],
            key=global_widget_key("saved_cases_select"),
        )
        selected_case = filtered_records[selection]
        case_path = Path(selected_case["path"])

        action_cols = st.columns(4)
        if action_cols[0].button(
            "📂 Load in current tab",
            key=global_widget_key("saved_cases_load_current"),
            help="⚠️ Overwrite the currently active case tab with this data. Unsaved changes in the active tab will be lost.",
        ):
            if case_path.exists():
                request_load_from_path(str(case_path), prefer_new_tab=False)
            else:
                st.error("Case file could not be found on disk.")
        if action_cols[1].button(
            "✨ Load in new tab",
            key=global_widget_key("saved_cases_load_new"),
            type="primary",
            help="Open this case in a new workspace tab. Safe and recommended.",
        ):
            if case_path.exists():
                request_load_from_path(str(case_path), prefer_new_tab=True)
            else:
                st.error("Case file could not be found on disk.")

        export_bytes: bytes | None = None
        export_error: str | None = None
        if case_path.exists():
            try:
                export_bytes = case_path.read_bytes()
            except Exception as exc:
                export_error = str(exc)
        else:
            export_error = "Missing file"

        if export_bytes is not None:
            action_cols[2].download_button(
                "⬇️ Export JSON",
                export_bytes,
                file_name=case_path.name,
                mime="application/json",
                key=global_widget_key("saved_cases_export_json"),
                help="Download the raw JSON file for backup or sharing.",
            )
        else:
            action_cols[2].warning(
                f"Unable to export this case ({export_error or 'unknown error'})."
            )

        delete_key = global_widget_key(f"saved_delete_{selection}")
        confirm_key = f"{delete_key}_confirm"

        if st.session_state.get(confirm_key):
            if action_cols[3].button(
                "Confirm Delete",
                key=f"{delete_key}_yes",
                type="primary",
                help="Permanently delete this case file",
            ):
                try:
                    case_path.unlink(missing_ok=True)
                    st.toast(f"Deleted case: {case_path.name}")
                    st.session_state[confirm_key] = False
                    time.sleep(0.5)
                    st.rerun()
                except OSError as e:
                    st.error(f"Error deleting file: {e}")
            elif action_cols[3].button("Cancel", key=f"{delete_key}_no"):
                st.session_state[confirm_key] = False
                st.rerun()
        else:
            if action_cols[3].button(
                "Delete",
                key=delete_key,
                help="Permanently delete this case file",
            ):
                st.session_state[confirm_key] = True
                st.rerun()
    else:
        st.info(
            "No cases match the current filters. Try clearing the search bar or selecting 'All records' in the Layout filter."
        )

    export_table = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export filtered table (CSV)",
        export_table,
        file_name=f"saved_cases_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key=global_widget_key("saved_cases_export_table"),
    )

def render_dashboard() -> None:
    """Render the high-level dashboard overview tab."""

    st.markdown(
        "<div class='dashboard-title'>Dashboard</div>",
        unsafe_allow_html=True,
    )
    reminder_state = _refresh_wellness_reminder_state()
    if reminder_state and isinstance(reminder_state.get("event_dt"), datetime):
        event_dt: datetime = reminder_state["event_dt"]
        event_key = str(reminder_state.get("event_key", ""))
        meta = reminder_state.get("meta") or {}
        lead_minutes = max(
            0,
            int(
                reminder_state.get(
                    "lead_minutes", DEFAULT_WELLNESS_SETTINGS["notification_lead"]
                )
            ),
        )
        now = datetime.now()
        delta = event_dt - now
        countdown = _format_timedelta_compact(delta)
        is_soon = delta <= timedelta(minutes=lead_minutes)
        label = meta.get("label", event_key.replace("_", " ").title())
        duration = meta.get("duration_minutes")
        duration_text = (
            f" · {int(duration)} min"
            if isinstance(duration, (int, float)) and duration
            else ""
        )
        tip = str(reminder_state.get("tip") or random.choice(WELLNESS_TIPS))
        banner_class = "wellness-banner is-soon" if is_soon else "wellness-banner"
        st.markdown(
            f"""
            <div class="{banner_class}">
                <div class="wellness-banner__heading">🕒 Next pause: {label}{duration_text}</div>
                <div class="wellness-banner__meta">Starts at {event_dt.strftime('%H:%M')} · {countdown} away</div>
                <div class="wellness-banner__tip">💡 <span>{tip}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    notice_idx = st.session_state.get("dashboard_load_notice")
    if notice_idx is not None:
        st.info(f"Loaded case into Case tab {notice_idx + 1}.")
        st.session_state.dashboard_load_notice = None

    # Fetch all cases once to avoid redundant directory scanning in child components
    all_cases = _refresh_and_get_cases()

    tracked_cases = load_tracked_cases(source_data=all_cases)
    charts_col, main_col = st.columns([1.1, 2.4])
    with charts_col:
        render_tracked_case_insights(tracked_cases)
        st.markdown("---")
        st.subheader("Recent Tracked Files")
        recent = recent_tracked_files(tracked_cases)
        if recent:
            for path in recent:
                st.write(path.stem)
        else:
            st.caption("No historical tracked files yet.")
    with main_col:
        with st.container():
            st.markdown("<div class='dashboard-section'>", unsafe_allow_html=True)
            st.subheader("Tracked Cases")
            st.caption(
                "Monitor ongoing work, contact details, and adjust priority directly from this table."
            )
            search_term = st.text_input(
                "Search tracked cases",
                key=global_widget_key("tracked_cases_search"),
                placeholder="Search by company, status, case ID, or priority",
                help="Filter active cases by Company, Status, Case ID, or Priority.",
            )
            render_tracked_cases_dashboard(tracked_cases, search_term)
            st.markdown("</div>", unsafe_allow_html=True)
        with st.container():
            st.markdown("<div class='dashboard-section'>", unsafe_allow_html=True)
            st.subheader("Dell Escalations and FedEx Replacements")
            render_dell_fedex_dashboard(tracked_cases)
            st.markdown("</div>", unsafe_allow_html=True)
        with st.container():
            st.markdown("<div class='dashboard-section'>", unsafe_allow_html=True)
            st.subheader("All My Saved Cases")
            render_saved_cases_dashboard(source_data=all_cases)
            st.markdown("</div>", unsafe_allow_html=True)



def _render_settings_workspace_tab() -> None:
    st.markdown(
        "<div class='settings-section-title'><span>🎓</span>Guided onboarding</div>",
        unsafe_allow_html=True,
    )
    completion_type = st.session_state.get("tutorial_completion_type", "") or (
        "completed" if st.session_state.get("tutorial_completed") else ""
    )
    completed_at = st.session_state.get("tutorial_completed_at") or ""
    if st.session_state.get("tutorial_completed"):
        if completed_at:
            st.caption(
                f"Tutorial {completion_type} on {completed_at}. Use the button below to replay the guided tour."
            )
        else:
            st.caption(
                "Tutorial completed. Replay it any time to refresh the workflow overview."
            )
    else:
        st.warning(
            "The interactive tutorial will launch automatically for first-time users. Complete it to log your onboarding status."
        )
    if st.button(
        "Repeat interactive tutorial",
        key=global_widget_key("tutorial_repeat"),
        help="Launch the onboarding walkthrough again",
    ):
        st.session_state.show_tutorial = True
        st.session_state.tutorial_step = 0
        st.rerun()

    st.markdown(
        "<div class='settings-section-title'><span>🪪</span>Agent identity</div>",
        unsafe_allow_html=True,
    )
    identity_columns = st.columns(2)
    with identity_columns[0]:
        first_input = st.text_input(
            "First name",
            key="agent_first_name",
            placeholder="e.g. Alex",
            help="Used across reports, exports, and cloud sync metadata.",
        )
    with identity_columns[1]:
        last_input = st.text_input(
            "Last name",
            key="agent_last_name",
            placeholder="e.g. Johnson",
            help="Peers will see this when merging your Kiroshi Cloud datasets.",
        )

    first_value = _normalize_agent_name(first_input)
    last_value = _normalize_agent_name(last_input)

    if first_value != first_input:
        st.session_state.agent_first_name = first_value
    if last_value != last_input:
        st.session_state.agent_last_name = last_value

    if first_value != _persistent_settings_cache.get("agent_first_name", ""):
        _persist_setting("agent_first_name")
    if last_value != _persistent_settings_cache.get("agent_last_name", ""):
        _persist_setting("agent_last_name")

    display_name = " ".join(part for part in (first_value, last_value) if part)
    if display_name:
        st.caption(
            f"Shared datasets will be tagged as **{display_name}** so teammates recognise your contributions."
        )
    else:
        st.caption("Add your name so shared datasets are clearly attributed to you.")

    st.markdown(
        "<div class='settings-section-title'><span>🛠️</span>Workflow modes</div>",
        unsafe_allow_html=True,
    )
    prev_debug = st.session_state.debug_mode
    mode_cols = st.columns(2)
    with mode_cols[0]:
        st.toggle(
            "2nd Line mode",
            key="second_line_mode",
            on_change=_on_setting_change("second_line_mode"),
            help="Enable specialized fields for 2nd line support escalation flows.",
        )
        st.toggle(
            "Show Kiroshi Chat tab",
            key="show_kiroshi_chat",
            on_change=_on_setting_change("show_kiroshi_chat"),
            help="Display or hide the conversational workspace when you need more focus.",
        )
        st.toggle(
            "Enable Kiroshi sarcasm mode",
            key="kiroshi_sarcasm_mode",
            on_change=_on_setting_change("kiroshi_sarcasm_mode"),
            help=(
                "When enabled, Kiroshi's chat replies lean into witty sarcasm while remaining helpful."
            ),
        )
    with mode_cols[1]:
        st.toggle(
            "Show Debug tab",
            key="debug_mode",
            on_change=_on_setting_change("debug_mode"),
            help="Reveal advanced diagnostics and raw data inspection tools.",
        )
        if st.session_state.get("debug_mode"):
            st.toggle(
                "Activate Frutiger Aero easter egg",
                key="frutiger_aero_mode",
                on_change=_on_setting_change("frutiger_aero_mode"),
                help=(
                    "Adds a glassy Windows Vista-inspired sheen across the interface. "
                    "Only available while Debug mode is enabled."
                ),
            )
    if prev_debug and not st.session_state.debug_mode:
        st.session_state.debug_auth = False
        st.session_state.show_bored = False
        st.session_state.theme_preview = "auto"
        st.session_state.frutiger_aero_mode = False
        _persist_setting("frutiger_aero_mode")

    st.markdown(
        "<div class='settings-section-title'><span>💾</span>Autosave & workspace</div>",
        unsafe_allow_html=True,
    )
    st.toggle(
        "Autosave directly to database",
        key="autosave_to_database",
        on_change=_on_setting_change("autosave_to_database"),
        help=(
            "When enabled, every autosave writes the active case to the KiroshiDatabase "
            "folder using its case ID so the work is kept permanently."
        ),
    )

    st.markdown(
        "<div class='settings-section-title'><span>🎨</span>Appearance</div>",
        unsafe_allow_html=True,
    )
    st.toggle(
        "Enable dark mode",
        key="dark_mode_enabled",
        on_change=_on_setting_change("dark_mode_enabled"),
        help="Switch to a high-contrast midnight palette across the workspace.",
    )
    if st.session_state.get("dark_mode_enabled"):
        st.caption("Holiday palettes are temporarily disabled while dark mode is active.")
    st.toggle(
        "Enable holiday themes",
        key="enable_holiday_theme",
        on_change=_on_setting_change("enable_holiday_theme"),
        help="Celebrate the season with festive colors and messages.",
    )
    if st.session_state.get("debug_mode"):
        preview_options = ["auto", "default", *HOLIDAY_THEMES.keys()]

        def _format_theme_preview(option_key: str) -> str:
            if option_key == "auto":
                return "Automatic (scheduled)"
            if option_key == "default":
                return "Default (no holiday theme)"
            theme = HOLIDAY_THEMES.get(option_key)
            return theme.name if theme else option_key

        if st.session_state.theme_preview not in preview_options:
            st.session_state.theme_preview = "auto"

        st.selectbox(
            "Preview holiday theme",
            preview_options,
            key="theme_preview",
            format_func=_format_theme_preview,
            help=(
                "Force the interface to use a specific holiday palette while debugging. "
                "Choose ‘Automatic’ to return to the calendar-driven schedule."
            ),
            disabled=st.session_state.get("dark_mode_enabled", False),
        )
    st.toggle(
        "Compact case workspace",
        key="case_compact_mode",
        on_change=_on_setting_change("case_compact_mode"),
        help=(
            "Hide the documentation preview tables on the Case tab and use a tighter "
            "two-column layout for core fields."
        ),
    )

    st.markdown(
        "<div class='settings-section-title'><span>📁</span>Attachments & storage</div>",
        unsafe_allow_html=True,
    )
    attachments_help = (
        "Choose where case uploads, logs, and screenshots are stored on disk. "
        "Provide an absolute path to a folder that Streamlit can access."
    )
    st.text_input(
        "Attachments folder",
        key="attachments_directory",
        on_change=_on_setting_change("attachments_directory"),
        help=attachments_help,
    )
    requested_root = _resolve_configured_attachments_directory()
    attachments_root, attachments_error = _ensure_case_attachments_root()
    if attachments_error:
        st.warning(
            f"Could not create requested attachments directory {requested_root}. "
            "Using default Documents/kiroshi folder instead."
        )
    else:
        st.caption(f"Attachments stored in: {attachments_root}")
    if requested_root != attachments_root:
        st.info(
            "Requested directory unavailable. Using fallback attachments folder in Documents/kiroshi."
        )

    if st.button(
        "Use default attachments folder",
        key=global_widget_key("attachments_directory_reset"),
    ):
        st.session_state.attachments_directory = str(CASE_ATTACHMENTS_ROOT)
        _persist_setting("attachments_directory")
        st.rerun()

    st.markdown(
        "<div class='settings-section-title'><span>🛡️</span>Diagnostics & support</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Collect recent logs and craft a quick PDF for Support whenever something looks off."
    )
    if st.button(
        "Open incident reporter",
        key=global_widget_key("open_incident_reporter"),
    ):
        _open_incident_reporter(
            {
                "section": "Manual incident report",
                "tab": "Settings",
                "trigger": "manual",
                "case_index": st.session_state.get("last_rendered_case"),
            },
            allow_screenshot=False,
        )

    st.markdown(
        "<div class='settings-section-title'><span>🌿</span>Wellness reminders</div>",
        unsafe_allow_html=True,
    )
    wellness_settings = _normalize_wellness_settings(
        st.session_state.get("wellness_reminders", DEFAULT_WELLNESS_SETTINGS)
    )
    original_settings = deepcopy(wellness_settings)
    enabled = st.toggle(
        "Enable daily reminders",
        value=bool(wellness_settings.get("enabled")),
        key=global_widget_key("wellness_enabled"),
        help="Schedule two 15-minute breaks and a 60-minute lunch for every weekday.",
    )
    schedule = wellness_settings.get("schedule", {})
    defaults = DEFAULT_WELLNESS_SETTINGS["schedule"]
    break_cols = st.columns(3)
    break_one_time = break_cols[0].time_input(
        "Break 1",
        value=_time_str_to_time(
            str(schedule.get("break_1", defaults["break_1"])),
            fallback=_time_str_to_time(defaults["break_1"], fallback=datetime_time(hour=10, minute=30)),
        ),
        key=global_widget_key("wellness_break_one"),
        disabled=not enabled,
    )
    lunch_time = break_cols[1].time_input(
        "Lunch",
        value=_time_str_to_time(
            str(schedule.get("lunch", defaults["lunch"])),
            fallback=_time_str_to_time(defaults["lunch"], fallback=datetime_time(hour=12, minute=30)),
        ),
        key=global_widget_key("wellness_lunch"),
        disabled=not enabled,
    )
    break_two_time = break_cols[2].time_input(
        "Break 2",
        value=_time_str_to_time(
            str(schedule.get("break_2", defaults["break_2"])),
            fallback=_time_str_to_time(defaults["break_2"], fallback=datetime_time(hour=15, minute=0)),
        ),
        key=global_widget_key("wellness_break_two"),
        disabled=not enabled,
    )
    lead_default = max(0, int(wellness_settings.get("notification_lead", 10)))
    lead_default = min(45, lead_default)
    lead_minutes = st.slider(
        "Alert me this many minutes before each pause",
        min_value=0,
        max_value=45,
        value=lead_default,
        key=global_widget_key("wellness_lead"),
        disabled=not enabled,
    )
    wellness_settings["enabled"] = enabled
    wellness_settings["notification_lead"] = lead_minutes if enabled else lead_default
    wellness_settings["schedule"] = {
        "break_1": _time_to_string(break_one_time),
        "lunch": _time_to_string(lunch_time),
        "break_2": _time_to_string(break_two_time),
    }
    if wellness_settings != original_settings:
        st.session_state.wellness_reminders = wellness_settings
        _persist_setting("wellness_reminders")
        st.success("Wellness reminders updated.")
    else:
        st.session_state.wellness_reminders = wellness_settings
    if enabled:
        st.caption("Kiroshi will surface gentle reminders across the dashboard before each break.")


def _render_settings_ai_tab() -> None:
    st.markdown(
        "<div class='settings-section-title'><span>⚙️</span>AI Model Configuration</div>",
        unsafe_allow_html=True,
    )
    st.caption("Configure the AI model that powers chat, categorization, and drafting.")

    # Main mode selection
    ai_mode_options = ["Cloud", "Local API", "Local (Native)"]
    current_mode = st.session_state.ai_mode
    if current_mode not in ai_mode_options:
        current_mode = "Local (Native)"

    st.selectbox(
        "AI Mode",
        ai_mode_options,
        index=ai_mode_options.index(current_mode),
        key="ai_mode",
        on_change=_on_setting_change("ai_mode"),
        help="Select where the AI model runs. 'Cloud' uses external APIs (OpenAI), 'Local API' connects to a local server (like LM Studio), and 'Local (Native)' runs models directly within Kiroshi."
    )

    if st.session_state.ai_mode == "Cloud":
        # Force default API key if empty or if user explicitly requested reset/default behavior
        if not st.session_state.get("openai_api_key"):
            st.session_state.openai_api_key = DEFAULT_OPENAI_API_KEY

        st.text_input(
            "OpenAI API Key",
            type="password",
            key="openai_api_key",
            on_change=_on_setting_change("openai_api_key"),
            help="Your API key from OpenAI platform."
        )
        st.text_input(
            "AI Base URL",
            key="ai_base_url",
            on_change=_on_setting_change("ai_base_url"),
            help="The endpoint URL for the API (default: https://api.openai.com/v1)."
        )

        # Ensure default model is selected if current selection is invalid
        if st.session_state.get("openai_model") != "gpt-5-nano":
            st.session_state.openai_model = "gpt-5-nano"

        st.selectbox(
            "Model",
            ["gpt-5-nano"],
            key="openai_model",
            on_change=_on_setting_change("openai_model"),
        )
    elif st.session_state.ai_mode == "Local API":
        st.text_input(
            "AI Base URL",
            key="ai_base_url",
            on_change=_on_setting_change("ai_base_url"),
            help="The local server endpoint (e.g., http://localhost:1234/v1 for LM Studio)."
        )
        st.text_input(
            "API Key (optional)",
            type="password",
            key="openai_api_key",
            on_change=_on_setting_change("openai_api_key"),
        )
        st.selectbox(
            "Model",
            ["gpt-4o", "gpt-4", "gpt-3.5-turbo"],
            key="openai_model",
            on_change=_on_setting_change("openai_model"),
            help="Select the model identifier expected by your local server."
        )
    elif st.session_state.ai_mode == "Local (Native)":
        st.info("Runs entirely on your machine using internal libraries. No external apps or internet required.")
        st.radio(
            "Performance Profile",
            ["speed", "quality"],
            format_func=lambda x: "Speed (Phi-3 Mini)" if x == "speed" else "Quality (Llama 3.1 8B)",
            key="local_ai_profile",
            on_change=_on_setting_change("local_ai_profile"),
            help="Choose 'Speed' for faster responses on most laptops, or 'Quality' for better reasoning if you have a GPU."
        )

        profile = st.session_state.local_ai_profile
        model_config = MODELS[profile]
        is_downloaded = check_model_exists(profile)

        st.caption(f"Model: {model_config['name']}")
        st.caption(f"Status: {'✅ Ready' if is_downloaded else '❌ Not Downloaded'}")

        if not is_downloaded:
            if st.button(f"Download {model_config['name']}", key=global_widget_key("download_model")):
                with st.spinner(f"Downloading {model_config['name']}... This may take a while."):
                    try:
                        download_model(profile)
                        st.success("Download complete!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Download failed: {e}")
        else:
            st.success("Model ready for inference.")

    st.markdown("---")
    st.markdown(
        "<div class='settings-section-title'><span>🤖</span>AI Educate</div>",
        unsafe_allow_html=True,
    )
    prev_enabled = st.session_state.ai_educate_enabled
    st.toggle(
        "Enable AI Educate",
        key="ai_educate_enabled",
        on_change=_on_setting_change("ai_educate_enabled"),
        help="Activa el conjunto de herramientas avanzadas de AI Educate.",
    )
    ai_dataset = None
    if not st.session_state.ai_educate_enabled:
        if prev_enabled:
            st.session_state.ai_learning_matches = []
            st.session_state.ai_bug_report = None
        if st.session_state.ai_educate_report_enabled:
            st.session_state.ai_educate_report_enabled = False
            _persist_setting("ai_educate_report_enabled")
        if st.session_state.ai_educate_advanced:
            st.session_state.ai_educate_advanced = False
            _persist_setting("ai_educate_advanced")
        if st.session_state.get("ai_assist_mode") != "Standard":
            st.session_state.ai_assist_mode = "Standard"
            _persist_setting("ai_assist_mode")
        st.caption("AI Assistance enviará las solicitudes sin el contexto de Educate.")
    else:
        st.session_state.ai_assist_mode = "AI Educate"
        _persist_setting("ai_assist_mode")
        st.markdown("#### Configuración de Educate")
        refresh_requested = st.button(
            "Educate",
            help="Ejecuta nuevamente el protocolo de análisis para refrescar los aprendizajes.",
            key=global_widget_key("ai_educate_refresh"),
        )
        dataset_updated = False
        ai_dataset = ensure_ai_learning_dataset(force=refresh_requested)
        if refresh_requested:
            if ai_dataset:
                st.success("AI Educate actualizó el conocimiento con los casos guardados.")
                dataset_updated = True
                try:
                    st.session_state.ai_educate_report_cache = collect_ai_educate_report_data(
                        ai_dataset
                    )
                except Exception as exc:
                    logging.debug("Failed to build report cache after refresh: %s", exc)
            else:
                st.warning(
                    "No se encontraron casos guardados para analizar. Guarda casos primero."
                )
        elif ai_dataset is None:
            ai_dataset = ensure_ai_learning_dataset()

        st.toggle(
            "Report",
            key="ai_educate_report_enabled",
            on_change=_on_setting_change("ai_educate_report_enabled"),
            help="Habilita la pestaña Report para visualizar métricas y generar el PDF.",
        )
        advanced_enabled = st.toggle(
            "Advanced AI Assistance",
            key="ai_educate_advanced",
            on_change=_on_setting_change("ai_educate_advanced"),
            help=(
                "Cuando está activo, AI Assistance compara el caso con errores recientes, "
                "soluciones históricas y sesiones de remote desktop para sugerir acciones."
            ),
        )
        if not advanced_enabled:
            st.caption(
                "AI Assistance enviará la información básica sin contexto histórico adicional."
            )
            st.session_state.ai_learning_matches = []
        elif ai_dataset:
            st.caption(
                "AI Assistance utilizará las coincidencias encontradas por Educate para enriquecer las respuestas."
            )

        st.markdown("##### Compartir y fusionar conocimiento")
        download_payload: bytes | None = None
        if ai_dataset:
            try:
                download_payload = json.dumps(
                    ai_dataset, indent=2, ensure_ascii=False
                ).encode("utf-8")
            except TypeError as exc:
                logging.error("Failed to serialize AI learning dataset for sharing: %s", exc)
                download_payload = None
        if download_payload:
            st.download_button(
                "Descargar base de Educate",
                download_payload,
                file_name="AILearning.json",
                mime="application/json",
                help="Genera un archivo JSON para compartir la base de conocimiento con otros usuarios.",
                key=global_widget_key("ai_educate_download"),
            )
        else:
            st.caption(
                "Genera la base con Educate o importa un archivo compartido para comenzar a colaborar."
            )

        merge_cols = st.columns([3, 2])
        with merge_cols[0]:
            uploaded_dataset = st.file_uploader(
                "Importar base de Educate (.json)",
                type="json",
                help="Selecciona el archivo JSON compartido por otro usuario de Kiroshi.",
                key=global_widget_key("ai_educate_import"),
            )
        with merge_cols[1]:
            collaborator_name = st.text_input(
                "Colaborador",
                help="Nombre del usuario que compartió la base de Educate (opcional).",
                key=global_widget_key("ai_educate_collaborator"),
            )

        merge_clicked = st.button(
            "Merge knowledge",
            help="Fusiona el archivo importado con tu base de Educate para enriquecer el conocimiento.",
            key=global_widget_key("ai_educate_merge"),
            disabled=uploaded_dataset is None,
        )

        if merge_clicked and uploaded_dataset is not None:
            try:
                uploaded_bytes = uploaded_dataset.read()
                imported_payload = json.loads(uploaded_bytes.decode("utf-8"))
            except Exception as exc:
                st.error(f"No se pudo leer el archivo importado: {exc}")
                imported_payload = None
            finally:
                try:
                    uploaded_dataset.seek(0)
                except Exception:
                    pass

            if isinstance(imported_payload, Mapping):
                merged_dataset = merge_ai_learning_datasets(
                    ai_dataset,
                    imported_payload,
                    collaborator=(collaborator_name or "").strip() or None,
                    local_signature=st.session_state.get("ai_learning_signature"),
                )
                if merged_dataset:
                    save_ai_learning_dataset(merged_dataset)
                    st.session_state.ai_learning_data = merged_dataset
                    _sync_ai_learning_signature_from_dataset(merged_dataset)
                    ai_dataset = merged_dataset
                    dataset_updated = True
                    st.success(
                        "La base de Educate se fusionó con el conocimiento importado exitosamente."
                    )
                else:
                    st.warning(
                        "No se pudo fusionar el conocimiento importado. Verifica el archivo compartido."
                    )
            elif imported_payload is not None:
                st.warning("El archivo seleccionado no contiene un formato válido de Educate.")

    if ai_dataset:
        case_count = ai_dataset.get("case_count", 0)
        generated_at = ai_dataset.get("generated_at")
        status_message = (
            f"Datos de aprendizaje generados a partir de {case_count} casos guardados el {generated_at}."
        )
        if dataset_updated:
            st.success(status_message)
        else:
            st.caption(status_message)
        summary = ai_dataset.get("insight_summary", {})
        top_keywords = summary.get("top_keywords", [])
        if top_keywords:
            st.caption("Palabras clave más repetidas: " + ", ".join(top_keywords[:6]))
        root_patterns = ai_dataset.get("root_cause_patterns", [])
        if root_patterns:
            st.markdown("**Principales patrones de causa raíz:**")
            for pattern in root_patterns[:3]:
                st.markdown(f"- {pattern['root_cause']} ({pattern['count']} casos)")
    else:
        st.info(
            "Aún no hay datos históricos disponibles. Guarda casos para que Educate pueda aprender."
        )


def _render_settings_cloud_tab() -> None:
    st.markdown("##### Kiroshi Cloud")
    st.caption(
        "Sincroniza la base de Educate con la nube cifrada de Kiroshi para compartir conocimiento entre sedes remotas."
    )
    if not st.session_state.ai_educate_enabled:
        st.info("Activa AI Educate para habilitar la sincronización con Kiroshi Cloud.")
        return

    cloud_enabled = st.toggle(
        "Habilitar conexión con Kiroshi Cloud",
        key="kiroshi_cloud_enabled",
        on_change=_on_setting_change("kiroshi_cloud_enabled"),
    )
    if not cloud_enabled:
        st.session_state.kiroshi_cloud_authenticated = False
        st.session_state.kiroshi_cloud_status = None
        st.session_state.kiroshi_cloud_summary = None
        st.session_state.kiroshi_cloud_saved_at = None
        return

    overlay_info: dict[str, str] | None = None
    try:
        overlay_info = overlay_guidance()
    except KiroshiCloudError:
        overlay_info = None
    if overlay_info:
        provider_hint = overlay_info.get("provider")
        instructions_hint = overlay_info.get("instructions")
        if provider_hint:
            st.caption(
                f"Red privada recomendada para los túneles de Kiroshi Cloud: {provider_hint}."
            )
        if instructions_hint:
            with st.expander(
                "Guía para enlazar la red privada (overlay)",
                icon="🌐",
            ):
                st.markdown(instructions_hint)

    st.text_input(
        "Usuario del cloud",
        key="kiroshi_cloud_username",
        help="Credencial configurada en la consola de Kiroshi Cloud.",
        on_change=_on_setting_change("kiroshi_cloud_username"),
    )
    st.text_input(
        "Contraseña del cloud",
        type="password",
        key="kiroshi_cloud_password",
        help="Se guarda únicamente durante esta sesión.",
    )
    token_value = st.text_area(
        "Token de conexión del dispositivo",
        key="kiroshi_cloud_token",
        help=(
            "Pega el token generado para esta estación en la consola de Kiroshi Cloud."
            " El token vincula el ID del dispositivo y el secreto compartido."
        ),
        on_change=_on_setting_change("kiroshi_cloud_token"),
    )
    token_details = None
    token_value_stripped = token_value.strip()
    if token_value_stripped:
        try:
            token_details = decode_device_token(token_value_stripped)
        except KiroshiCloudError as exc:
            st.error(f"El token proporcionado no es válido: {exc}")
        else:
            issued_at = token_details.get("issued_at") or "desconocido"
            st.caption(
                f"Token válido para el dispositivo `{token_details.get('device_id')}` emitido el {issued_at}."
            )

    automation_status = st.session_state.get("_midday_cloud_sync_status")
    if isinstance(automation_status, Mapping):
        message = automation_status.get("message")
        timestamp = automation_status.get("timestamp")
        level = automation_status.get("level", "info")
        if message:
            formatted = message if not timestamp else f"{message} ({timestamp})"
            if level == "success":
                st.success(formatted)
            elif level == "warning":
                st.warning(formatted)
            elif level == "error":
                st.error(formatted)
            else:
                st.info(formatted)

    status = st.session_state.get("kiroshi_cloud_status")
    if isinstance(status, tuple) and len(status) == 2:
        level, message = status
        if level == "success":
            st.success(message)
        elif level == "warning":
            st.warning(message)
        else:
            share_status = cloud_share_status()
            if not share_status["available"]:
                message = share_status["message"]
                st.session_state.kiroshi_cloud_authenticated = False
                st.session_state.kiroshi_cloud_status = ("error", message)
                st.error(message)
            else:
                if st.session_state.kiroshi_cloud_status is None:
                    st.session_state.kiroshi_cloud_status = (
                        "warning",
                        f"Directorio de Kiroshi Cloud disponible en {share_status['path']}.",
                    )

                overlay_info: dict[str, str] | None = None
                try:
                    overlay_info = overlay_guidance()
                except KiroshiCloudError:
                    overlay_info = None
                if overlay_info:
                    provider_hint = overlay_info.get("provider")
                    instructions_hint = overlay_info.get("instructions")
                    if provider_hint:
                        st.caption(
                            f"Red privada recomendada para los túneles de Kiroshi Cloud: {provider_hint}."
                        )
                    if instructions_hint:
                        with st.expander(
                            "Guía para enlazar la red privada (overlay)",
                            icon="🌐",
                        ):
                            st.markdown(instructions_hint)

                st.text_input(
                    "Usuario del cloud",
                    key="kiroshi_cloud_username",
                    help="Credencial configurada en la consola de Kiroshi Cloud.",
                    on_change=_on_setting_change("kiroshi_cloud_username"),
                )
                st.text_input(
                    "Contraseña del cloud",
                    type="password",
                    key="kiroshi_cloud_password",
                    help="Se guarda únicamente durante esta sesión.",
                )
                token_value = st.text_area(
                    "Token de conexión del dispositivo",
                    key="kiroshi_cloud_token",
                    help=(
                        "Pega el token generado para esta estación en la consola de Kiroshi Cloud."
                        " El token vincula el ID del dispositivo y el secreto compartido."
                    ),
                    on_change=_on_setting_change("kiroshi_cloud_token"),
                )
                token_details = None
                token_value_stripped = token_value.strip()
                if token_value_stripped:
                    try:
                        token_details = decode_device_token(token_value_stripped)
                    except KiroshiCloudError as exc:
                        st.error(f"El token proporcionado no es válido: {exc}")
                    else:
                        issued_at = token_details.get("issued_at") or "desconocido"
                        st.caption(
                            f"Token válido para el dispositivo `{token_details.get('device_id')}` emitido el {issued_at}."
                        )

                status = st.session_state.get("kiroshi_cloud_status")
                if isinstance(status, tuple) and len(status) == 2:
                    level, message = status
                    if level == "success":
                        st.success(message)
                    elif level == "warning":
                        st.warning(message)
                    else:
                        st.error(message)

                def _obtain_cloud_session() -> object:
                    user = st.session_state.kiroshi_cloud_username.strip()
                    password_value = st.session_state.kiroshi_cloud_password
                    if not user or not password_value:
                        st.warning("Ingresa usuario y contraseña para conectarte al cloud.")
                        return None
                    try:
                        return open_kiroshi_cloud_session(user, password_value)
                    except CloudAuthenticationError as exc:
                        st.session_state.kiroshi_cloud_authenticated = False
                        st.session_state.kiroshi_cloud_status = ("error", str(exc))
                        st.error(str(exc))
                    except KiroshiCloudError as exc:
                        st.session_state.kiroshi_cloud_authenticated = False
                        st.session_state.kiroshi_cloud_status = ("error", str(exc))
                        st.error(f"No se pudo abrir la instancia de Kiroshi Cloud: {exc}")
                    return None

                if st.button("Validar conexión", key=global_widget_key("cloud_validate")):
                    session = _obtain_cloud_session()
                    if session:
                        selected_agents = [
                            str(agent).strip()
                            for agent in st.session_state.get("kiroshi_cloud_selected_agents", [])
                            if str(agent).strip()
                        ]
                        cloud_payload = session.load_ai_dataset(
                            agent_ids=selected_agents or None
                        )
                        saved_at = None
                        if (
                            isinstance(cloud_payload, Mapping)
                            and cloud_payload
                            and "dataset" in cloud_payload
                        ):
                            cloud_dataset = cloud_payload.get("dataset")
                            saved_at = cloud_payload.get("saved_at")
                        else:
                            cloud_dataset = cloud_payload
                        st.session_state.kiroshi_cloud_authenticated = True
                        st.session_state.kiroshi_cloud_status = (
                            "success",
                            "Conexión con Kiroshi Cloud validada correctamente.",
                        )
                        st.session_state.kiroshi_cloud_summary = summarize_cloud_dataset(cloud_dataset)
                        st.session_state.kiroshi_cloud_saved_at = saved_at
                        st.success("Conexión validada. Puedes sincronizar la base de Educate.")

                if st.session_state.kiroshi_cloud_authenticated:
                    sync_cols = st.columns(2)
                    if sync_cols[0].button(
                        "Subir Educate al cloud", key=global_widget_key("cloud_push")
                    ):
                        session = _obtain_cloud_session()
                        if session:
                            dataset_to_push = ensure_ai_learning_dataset()
                            if not dataset_to_push:
                                st.warning("Genera la base de Educate antes de sincronizar.")
                            else:
                                try:
                                    session.save_ai_dataset(dataset_to_push)
                                except KiroshiCloudError as exc:
                                    st.error(f"No se pudo subir la base al cloud: {exc}")
                                else:
                                    st.success("Base de Educate subida a Kiroshi Cloud.")
                                    st.session_state.kiroshi_cloud_summary = summarize_cloud_dataset(
                                        dataset_to_push
                                    )
                                    st.session_state.kiroshi_cloud_saved_at = (
                                        datetime.utcnow().isoformat() + "Z"
                                    )
                    if sync_cols[1].button(
                        "Descargar Educate del cloud", key=global_widget_key("cloud_pull")
                    ):
                        session = _obtain_cloud_session()
                        if session:
                            cloud_payload = session.load_ai_dataset()
                            saved_at = None
                            if (
                                isinstance(cloud_payload, Mapping)
                                and cloud_payload
                                and "dataset" in cloud_payload
                            ):
                                dataset_from_cloud = cloud_payload.get("dataset")
                                saved_at = cloud_payload.get("saved_at")
                            else:
                                dataset_from_cloud = cloud_payload
                            if not dataset_from_cloud:
                                st.info(
                                    "El cloud todavía no tiene una base de Educate disponible."
                                )
                            else:
                                save_ai_learning_dataset(dataset_from_cloud)
                                st.session_state.ai_learning_data = dataset_from_cloud
                                _sync_ai_learning_signature_from_dataset(dataset_from_cloud)
                                st.session_state.kiroshi_cloud_summary = summarize_cloud_dataset(
                                    dataset_from_cloud
                                )
                                st.session_state.kiroshi_cloud_saved_at = saved_at
                                st.success(
                                    "La base local se actualizó con la copia almacenada en el cloud."
                                )

                summary_data = st.session_state.get("kiroshi_cloud_summary")
                saved_at = st.session_state.get("kiroshi_cloud_saved_at")
                if summary_data:
                    st.caption("Resumen del cloud")
                    summary_cols = st.columns(3)
                    summary_cols[0].metric(
                        "Casos sincronizados", summary_data.get("total_cases", 0)
                    )
                    summary_cols[1].metric(
                        "Dispositivos únicos", summary_data.get("unique_devices", 0)
                    )

        summary_data = st.session_state.get("kiroshi_cloud_summary")
        saved_at = st.session_state.get("kiroshi_cloud_saved_at")
        if summary_data:
            st.caption("Resumen del cloud")
            summary_cols = st.columns(3)
            summary_cols[0].metric(
                "Casos sincronizados", summary_data.get("total_cases", 0)
            )
            summary_cols[1].metric(
                "Dispositivos únicos", summary_data.get("unique_devices", 0)
            )
            if saved_at:
                try:
                    saved_dt = datetime.fromisoformat(str(saved_at).replace("Z", "+00:00"))
                    saved_label = saved_dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    saved_label = str(saved_at)
            else:
                saved_label = "—"
            summary_cols[2].metric("Última actualización", saved_label)
            top_causes = summary_data.get("root_cause_counts") or []
            if top_causes:
                st.markdown("**Principales causas registradas en la nube:**")
                for label, count in top_causes[:3]:
                    st.markdown(f"- {label}: {count} casos")


def _render_settings_updates_tab() -> None:
    st.markdown(
        "<div class='settings-section-title'><span>⬆️</span>Updates & maintenance</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Consulta la rama principal de GitHub y descarga la versión más reciente de Kiroshi sin salir de la aplicación."
    )
    feedback = st.session_state.get("update_apply_feedback")
    if isinstance(feedback, tuple) and len(feedback) == 2:
        level, message = feedback
        if level == "success":
            st.success(message)
        elif level == "warning":
            st.warning(message)
        else:
            st.error(message)

    update_status_obj = st.session_state.get("update_status")
    update_check_clicked = st.button(
        "Check for updates", key=global_widget_key("update_check")
    )
    if update_check_clicked:
        st.session_state.update_apply_feedback = None
        with case_loading_overlay("Scanning GitHub for new builds…"):
            update_status_obj = check_for_updates()
        st.session_state.update_status = update_status_obj
        st.session_state.update_status_checked_at = datetime.now()

    update_status: UpdateCheckResult | None
    if isinstance(update_status_obj, UpdateCheckResult):
        update_status = update_status_obj
    elif isinstance(update_status_obj, Mapping):
        try:
            update_status = UpdateCheckResult(**update_status_obj)  # type: ignore[arg-type]
        except TypeError:
            update_status = None
    else:
        update_status = None

    if update_status:
        st.write(f"Current version: {update_status.current_version}")
        st.write(
            f"Repository: {update_status.repo} · Branch: {update_status.branch}"
        )
        if update_status.error:
            st.error(update_status.error)
        else:
            if update_status.latest_version:
                st.write(f"Latest version: {update_status.latest_version}")
            if update_status.latest_commit:
                commit_caption = f"Commit {update_status.latest_commit[:7]}"
                if update_status.latest_published:
                    commit_caption += f" · {update_status.latest_published}"
                st.caption(commit_caption)
            if update_status.has_update:
                st.warning(
                    "Hay una actualización disponible. Descárgala para mantener tu instalación al día."
                )
                if st.button(
                    "Download and apply update",
                    key=global_widget_key("update_apply"),
                ):
                    with case_loading_overlay("Applying the latest update package…"):
                        try:
                            apply_github_update(update_status.repo, update_status.branch)
                        except Exception as exc:
                            st.session_state.update_apply_feedback = (
                                "error",
                                f"No se pudo aplicar la actualización: {exc}",
                            )
                        else:
                            st.session_state.update_apply_feedback = (
                                "success",
                                "Actualización instalada. Reinicia Kiroshi para cargar los cambios más recientes.",
                            )
                            st.session_state.update_status = None
                            st.session_state.update_status_checked_at = datetime.now()
                    st.rerun()
            else:
                st.success("Ya estás usando la versión más reciente disponible.")
            if update_status.download_url:
                st.markdown(
                    f"[Descargar ZIP manualmente]({update_status.download_url})"
                )
                st.caption(
                    "Úsalo si prefieres aplicar la actualización manualmente o compartirla con tu equipo."
                )
        checked_at = st.session_state.get("update_status_checked_at")
        if isinstance(checked_at, datetime):
            st.caption(f"Última comprobación: {checked_at.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.caption(
            "Pulsa \"Check for updates\" para comprobar si hay cambios publicados en GitHub."
        )


def render_settings_panel() -> None:
    ensure_settings_styles()
    st.markdown(
        """
        <div class="settings-hero">
            <div class="settings-hero__glow"></div>
            <div class="settings-hero__title">Settings control centre</div>
            <div class="settings-hero__subtitle">
                Tune Kiroshi to match your workflow — switch modes, organise storage, refresh AI Educate, and keep the app up to date.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container():
        st.markdown("<div class='settings-tabs'>", unsafe_allow_html=True)
        workspace_tab, ai_tab, cloud_tab, updates_tab = st.tabs(
            [
                "Workspace",
                "AI & Knowledge",
                "Kiroshi Cloud",
                "Updates",
            ]
        )
        with workspace_tab:
            _render_settings_workspace_tab()
        with ai_tab:
            _render_settings_ai_tab()
        with cloud_tab:
            _render_settings_cloud_tab()
        with updates_tab:
            _render_settings_updates_tab()
        st.markdown("</div>", unsafe_allow_html=True)

def render_report_panel() -> None:
    st.subheader("AI Educate Report")
    if not st.session_state.ai_educate_enabled:
        st.info("Activa AI Educate desde Settings para generar reportes.")
        return
    dataset = ensure_ai_learning_dataset()
    if not dataset:
        st.info("Aún no hay suficientes casos guardados para generar estadísticas.")
        return
    cached_insights = st.session_state.get("ai_educate_report_cache")
    dataset_case_total = dataset.get("case_count") if isinstance(dataset, Mapping) else None
    if (
        isinstance(cached_insights, Mapping)
        and dataset_case_total is not None
        and cached_insights.get("case_total") == dataset_case_total
    ):
        insights = cached_insights
    else:
        insights = collect_ai_educate_report_data(dataset)
        if insights:
            st.session_state.ai_educate_report_cache = insights
    if not insights:
        st.info("Aún no hay suficientes casos guardados para generar estadísticas.")
        return

    view_order = ["30d", "all_time"]
    view_labels = {"30d": "Últimos 30 días", "all_time": "Todo el historial"}
    default_view = st.session_state.get("ai_report_view", "30d")
    if default_view not in view_order:
        default_view = "30d"
    selected_view = st.radio(
        "Rango de tiempo",
        options=view_order,
        index=view_order.index(default_view),
        format_func=lambda key: view_labels.get(key, key),
        horizontal=True,
        key=global_widget_key("ai_report_view"),
    )
    st.session_state.ai_report_view = selected_view

    view_totals = insights.get("view_totals", {})
    current_totals = view_totals.get(selected_view, {})

    cols = st.columns(4)
    cols[0].metric(
        f"Casos ({view_labels[selected_view]})",
        current_totals.get("case_total", 0),
    )
    cols[1].metric(
        "Tipos de caso únicos",
        current_totals.get("unique_labels", 0),
    )
    cols[2].metric(
        "Solucionados como bug",
        current_totals.get("bug_solution_count", 0),
    )
    cols[3].metric(
        "Menciones de 'bug'",
        current_totals.get("bug_mentions_count", 0),
    )

    if selected_view != "all_time":
        overall_totals = view_totals.get("all_time", {})
        st.caption(
            f"Historial completo: {overall_totals.get('case_total', 0)} casos · "
            f"{overall_totals.get('unique_labels', 0)} tipos únicos"
        )

    highlight_label = insights.get("highlight_label")
    if highlight_label:
        st.markdown(
            f"**Caso prioritario:** {highlight_label} "
            f"(detectado {insights.get('highlight_count', 0)} veces)."
        )
        highlight_case = insights.get("highlight_case") or {}
        solution_excerpt = highlight_case.get("solution_excerpt")
        if solution_excerpt:
            st.caption(f"Insight de solución: {solution_excerpt}")

    counts_map = insights.get("counts", {})
    selected_counts = counts_map.get(selected_view)
    if isinstance(selected_counts, pd.DataFrame) and not selected_counts.empty:
        st.markdown(
            f"### Casos más frecuentes ({view_labels[selected_view]})"
        )
        st.dataframe(
            selected_counts.rename(
                columns={"analysis_label": "Caso", "count": "Frecuencia"}
            ),
            width="stretch",
        )
        freq_chart = (
            alt.Chart(selected_counts)
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X("count:Q", title="Casos"),
                y=alt.Y("analysis_label:N", sort="-x", title="Caso"),
                tooltip=[
                    alt.Tooltip("analysis_label:N", title="Caso"),
                    alt.Tooltip("count:Q", title="Frecuencia"),
                ],
                color=alt.value("#2563eb"),
            )
            .properties(height=min(360, 40 * len(selected_counts)))
        )
        render_responsive_altair_chart(freq_chart)

    timeline_map = {
        "30d": insights.get("timeline"),
        "all_time": insights.get("timeline_all"),
    }
    selected_timeline = timeline_map.get(selected_view)
    if isinstance(selected_timeline, pd.DataFrame) and not selected_timeline.empty:
        st.markdown(f"### Tendencia de casos ({view_labels[selected_view]})")
        timeline_chart = (
            alt.Chart(selected_timeline)
            .mark_line(point=True, color="#16a34a")
            .encode(
                x=alt.X("timestamp:T", title="Fecha"),
                y=alt.Y("count:Q", title="Casos"),
                tooltip=[
                    alt.Tooltip("timestamp:T", title="Fecha"),
                    alt.Tooltip("count:Q", title="Casos"),
                ],
            )
            .properties(height=260)
        )
        render_responsive_altair_chart(timeline_chart)

    recurring_df = insights.get("recurring_issue_types")
    if isinstance(recurring_df, pd.DataFrame) and not recurring_df.empty:
        st.markdown("### Patrones recurrentes")
        st.dataframe(
            recurring_df.rename(
                columns={"analysis_label": "Caso", "count": "Recurrencias"}
            ),
            width="stretch",
        )

    root_cause_df = insights.get("common_root_causes")
    if isinstance(root_cause_df, pd.DataFrame) and not root_cause_df.empty:
        st.markdown("### Causas raíz más comunes")
        st.dataframe(
            root_cause_df.rename(columns={"root_cause": "Causa", "count": "Casos"}),
            width="stretch",
        )

    scanner_df = insights.get("common_scanner_models")
    if isinstance(scanner_df, pd.DataFrame) and not scanner_df.empty:
        st.markdown("### Modelos de escáner reportados")
        st.dataframe(
            scanner_df.rename(columns={"scanner": "Modelo", "count": "Casos"}),
            width="stretch",
        )

    bug_report = st.session_state.get("ai_bug_report")
    bug_cases = insights.get("bug_cases")
    if isinstance(bug_cases, pd.DataFrame) and not bug_cases.empty:
        st.markdown("### Casos con mención de bug")
        st.dataframe(
            bug_cases[["case_id", "title", "saved_at"]]
            .rename(
                columns={
                    "case_id": "Case ID",
                    "title": "Título",
                    "saved_at": "Guardado",
                }
            )
            .head(15),
            width="stretch",
        )

    col_pdf, col_bug = st.columns([1, 1])
    with col_pdf:
        try:
            pdf_bytes = generate_ai_educate_report_pdf(insights, bug_report)
        except Exception as exc:
            st.error(f"No se pudo generar el PDF del reporte: {exc}")
            pdf_bytes = None
        if pdf_bytes:
            st.download_button(
                "Descargar reporte PDF",
                pdf_bytes,
                file_name="ai_educate_report.pdf",
                mime="application/pdf",
                key=global_widget_key("ai_educate_report_pdf"),
            )
    with col_bug:
        if st.button(
            "Bug Detector",
            help="Analiza todos los casos guardados para encontrar patrones de bug.",
            key=global_widget_key("ai_bug_detector"),
        ):
            bug_report = run_bug_detector(dataset)
            st.session_state.ai_bug_report = bug_report
            if bug_report:
                st.success("Bug Detector completó el análisis.")
            else:
                st.info("No se detectaron bugs ni patrones recurrentes en los casos analizados.")
    bug_report = st.session_state.get("ai_bug_report")
    if bug_report:
        st.markdown("### Resultados de Bug Detector")
        st.write(bug_report.get("summary"))
        recurring = bug_report.get("recurring_patterns") or []
        if recurring:
            recurring_df = pd.DataFrame(recurring)
            if not recurring_df.empty and {"pattern", "count"}.issubset(recurring_df.columns):
                display_df = recurring_df[["pattern", "count"]]
            else:
                display_df = recurring_df
            st.table(
                display_df.rename(
                    columns={"pattern": "Patrón", "count": "Recurrencias"}
                )
            )

            eligible_patterns = [
                entry
                for entry in recurring
                if isinstance(entry, Mapping)
                and int(entry.get("count") or 0) >= 2
                and entry.get("pattern")
            ]
            if eligible_patterns:
                st.markdown("#### Generar guía para patrones recurrentes")
                options = [
                    f"{str(entry.get('pattern'))} ({int(entry.get('count', 0))})"
                    for entry in eligible_patterns
                ]
                selected_label = st.selectbox(
                    "Selecciona un patrón",
                    options,
                    key=global_widget_key("recurring_pattern_select"),
                )
                selected_entry: Mapping[str, object] | None = None
                for entry, label in zip(eligible_patterns, options):
                    if label == selected_label:
                        selected_entry = entry
                        break
                if selected_entry:
                    try:
                        pattern_pdf = generate_recurring_issue_pdf(
                            selected_entry,
                            dataset=dataset,
                        )
                    except Exception as exc:
                        st.error(f"No se pudo generar la guía del patrón: {exc}")
                    else:
                        raw_name = str(selected_entry.get("pattern", "patron"))
                        slug = re.sub(r"[^A-Za-z0-9]+", "-", raw_name.lower()).strip("-")
                        file_name = f"recurring_{slug or 'patron'}.pdf"
                        st.download_button(
                            "Descargar guía PDF",
                            pattern_pdf,
                            file_name=file_name,
                            mime="application/pdf",
                            key=global_widget_key("recurring_pattern_pdf"),
                        )


def _open_incident_reporter(
    context: Mapping[str, object] | None,
    *,
    allow_screenshot: bool,
) -> None:
    """Prepare the incident reporter modal with the provided context."""

    base_context: dict[str, object] = {}
    if isinstance(context, Mapping):
        base_context.update(context)
    if "timestamp" not in base_context:
        base_context["timestamp"] = datetime.now(timezone.utc).isoformat()
    if "tab" not in base_context:
        base_context["tab"] = st.session_state.get("last_rendered_tab")
    if "section" not in base_context:
        base_context["section"] = base_context.get("tab", "Unknown section")
    base_context.setdefault("trigger", "auto")
    base_context.setdefault("case_index", st.session_state.get("last_rendered_case"))

    st.session_state.incident_context = base_context
    st.session_state.reporter_open = True
    st.session_state.reporter_allow_screenshot = allow_screenshot
    st.session_state.reporter_source = str(base_context.get("trigger") or "auto")
    st.session_state.incident_reporter_description = ""
    st.session_state.incident_reporter_pdf = None
    st.session_state.incident_reporter_capture_error = None
    st.session_state.incident_reporter_screenshot = None
    st.session_state.incident_helpjuice_outline = None
    st.session_state.error_modal_open = False


def show_failure_modal() -> None:
    """Display a modal when a render failure has been detected."""

    if not st.session_state.get("render_failure_detected"):
        return
    if not st.session_state.get("error_modal_open"):
        return

    message = st.session_state.get("failure_modal_message")
    if not message:
        message = random.choice(ERROR_DIALOG_MESSAGES)
        st.session_state.failure_modal_message = message
    context = st.session_state.get("incident_context") or {}
    section_label = context.get("section")

    with safe_modal("Something went wrong", key=global_widget_key("render_failure_modal")):
        escaped_message = escape(str(message))
        st.markdown(
            """
            <style>
            .kiroshi-error-card {
                background: rgba(255, 244, 245, 0.95);
                border-radius: 20px;
                padding: 1.5rem;
                text-align: center;
                box-shadow: 0 18px 40px rgba(255, 0, 76, 0.18);
                border: 1px solid rgba(255, 0, 76, 0.25);
            }
            .kiroshi-error-card h3 {
                margin-bottom: 0.5rem;
            }
            .kiroshi-error-icon {
                font-size: 48px;
                line-height: 1;
                margin-bottom: 0.75rem;
            }
            </style>
            <div class="kiroshi-error-card">
                <div class="kiroshi-error-icon">⚠️</div>
                <h3>Something went wrong</h3>
                <p>{escaped_message}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write(
            "We'll freeze the workspace until you either report the crash or dismiss this alert."
        )
        if section_label:
            st.caption(f"Detected while rendering: {section_label}")
        col_report, col_ignore = st.columns(2)
        if col_report.button("Report", key=global_widget_key("render_failure_report")):
            _open_incident_reporter(context, allow_screenshot=True)
        if col_ignore.button(
            "I know what I'm doing",
            key=global_widget_key("render_failure_ignore"),
        ):
            st.session_state.error_modal_open = False
            st.session_state.render_failure_detected = False
            st.session_state.failure_modal_message = None


def show_incident_report_modal() -> None:
    """Render the incident reporter modal when requested."""

    if not st.session_state.get("reporter_open"):
        return

    context = st.session_state.get("incident_context") or {}
    allow_screenshot = bool(st.session_state.get("reporter_allow_screenshot"))

    with safe_modal("Incident reporter", key=global_widget_key("incident_report_modal")):
        st.markdown("### Incident reporter")
        st.caption(
            "We'll bundle recent logs, context, and optional screenshots into a PDF you can download."
        )
        formatted_context = _format_incident_context(context)
        if formatted_context:
            st.write(formatted_context)

        st.text_area(
            "What happened?",
            key="incident_reporter_description",
            placeholder="Share any extra detail you'd like Support to know.",
        )

        screenshot = None
        if allow_screenshot:
            st.markdown("#### Screenshot (optional)")
            shot_name = st.text_input(
                "Screenshot name",
                key=global_widget_key("incident_screenshot_name"),
                help="Used to label the image inside the PDF.",
            )
            capture_error = st.session_state.get("incident_reporter_capture_error")
            if capture_error:
                st.warning(capture_error)
            capture_cols = st.columns([1, 1, 1])
            if capture_cols[0].button(
                "Capture region",
                key=global_widget_key("incident_capture"),
            ):
                shot_label = (shot_name or "").strip()
                safe_name = shot_label or f"incident_{int(time.time())}"
                safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
                shot, error = capture_region_screenshot(
                    safe_name,
                    label=shot_label or safe_name,
                )
                _handle_incident_screenshot_result(shot, error)
            if capture_cols[1].button(
                "Use full screenshot",
                key=global_widget_key("incident_full_capture"),
            ):
                shot_label = (shot_name or "").strip()
                safe_name = shot_label or f"incident_{int(time.time())}"
                safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
                shot, error = capture_full_screenshot(
                    safe_name,
                    label=shot_label or safe_name,
                )
                _handle_incident_screenshot_result(shot, error)
            if capture_cols[2].button(
                "Clear screenshot",
                key=global_widget_key("incident_clear_capture"),
            ):
                st.session_state.incident_reporter_screenshot = None
                st.session_state.incident_reporter_capture_error = None

            screenshot = st.session_state.get("incident_reporter_screenshot")
            if screenshot:
                st.image(screenshot.data, caption=screenshot.name, use_container_width=True)
        else:
            st.info(
                "Manual reports skip screenshots. Logs and your notes will still be packaged into the PDF."
            )

        description = st.session_state.get("incident_reporter_description", "")
        case_index = context.get("case_index")
        try:
            case_idx_int = int(case_index) if case_index is not None else None
        except (TypeError, ValueError):
            case_idx_int = None
        case_data: CaseData | None = None
        sessions = st.session_state.get("case_sessions")
        if isinstance(sessions, list) and case_idx_int is not None:
            try:
                session_candidate = sessions[case_idx_int]
            except (IndexError, TypeError):
                session_candidate = None
            if session_candidate is not None:
                candidate_case = getattr(session_candidate, "case", None)
                if isinstance(candidate_case, CaseData):
                    case_data = candidate_case

        if st.button("Generate PDF", key=global_widget_key("incident_generate_pdf")):
            logs = _collect_recent_logs()
            case_snapshot = _case_metadata_snapshot(case_idx_int)
            try:
                pdf_bytes = build_incident_report_pdf(
                    context,
                    logs,
                    description,
                    case_snapshot,
                    screenshot=screenshot if allow_screenshot else None,
                )
            except Exception as exc:
                st.error(f"Unable to build PDF: {exc}")
            else:
                st.session_state.incident_reporter_pdf = pdf_bytes
                st.success("Incident PDF generated. Download below.")

        if st.button("Create Helpjuice guide", key=global_widget_key("incident_helpjuice")):
            logs = _collect_recent_logs()
            matches = st.session_state.get("ai_learning_matches") or []
            manual_docs = st.session_state.get("manual_docs") or []
            try:
                outline = build_helpjuice_outline(
                    case_data,
                    context=context,
                    logs=logs,
                    user_notes=description,
                    matches=matches,
                    manual_docs=manual_docs,
                )
            except Exception as exc:
                st.error(f"Unable to assemble Helpjuice guide: {exc}")
            else:
                st.session_state.incident_helpjuice_outline = outline
                st.success("Helpjuice outline generated. Copy or download below.")

        pdf_bytes = st.session_state.get("incident_reporter_pdf")
        if isinstance(pdf_bytes, (bytes, bytearray)):
            st.download_button(
                "Download incident PDF",
                data=pdf_bytes,
                file_name="kiroshi-incident-report.pdf",
                mime="application/pdf",
                key=global_widget_key("incident_pdf_download"),
            )

        outline_text = st.session_state.get("incident_helpjuice_outline")
        if isinstance(outline_text, str) and outline_text.strip():
            st.markdown("#### Helpjuice guide preview")
            st.text_area(
                "Outline",
                value=outline_text,
                height=320,
                key=global_widget_key("incident_helpjuice_preview"),
            )
            st.download_button(
                "Download Helpjuice guide (Markdown)",
                data=outline_text.encode("utf-8"),
                file_name="kiroshi-helpjuice-guide.md",
                mime="text/markdown",
                key=global_widget_key("incident_helpjuice_download"),
            )

        if st.button("Close", key=global_widget_key("incident_close")):
            st.session_state.reporter_open = False
            st.session_state.incident_reporter_pdf = None
            st.session_state.incident_reporter_capture_error = None
            st.session_state.incident_reporter_screenshot = None
            st.session_state.incident_helpjuice_outline = None
            if st.session_state.get("reporter_source") != "manual":
                st.session_state.render_failure_detected = False
                st.session_state.failure_modal_message = None
            st.session_state.error_modal_open = False
            st.session_state.reporter_source = "auto"


def render_with_monitor(
    section_name: str,
    render_fn: Callable[..., object],
    *args,
    tab_label: str | None = None,
    case_index: int | None = None,
    **kwargs,
) -> None:
    """Execute a rendering function and capture failures into session state."""

    placeholder = st.container()
    if tab_label:
        st.session_state.last_rendered_tab = tab_label
    st.session_state.last_rendered_case = case_index
    try:
        with placeholder:
            render_fn(*args, **kwargs)
    except WidgetKeyCollisionError as collision:
        if not st.session_state.get("debug_mode"):
            raise
        logging.warning(
            "Duplicate widget key detected while rendering %s: %s",
            section_name,
            collision.key,
        )
        context = {
            "section": section_name,
            "tab": tab_label or section_name,
            "trigger": "auto",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case_index": case_index,
            "warning": str(collision),
            "collision_key": collision.key,
            "type": "widget_key_collision",
            "level": "warning",
            "stacktrace": traceback.format_exc(),
        }
        st.session_state.incident_context = context
        st.session_state.reporter_source = "auto"
        st.session_state.debug_widget_key_collision_context = context
        placeholder.warning(
            f"Duplicate widget key detected: `{collision.key}`. Check the incident reporter for details."
        )
    except Exception as exc:  # pragma: no cover - streamlit runtime guard
        if getattr(exc, "is_rerun", False) or exc.__class__.__name__ == "RerunException":
            raise
        logging.exception("Error rendering %s: %s", section_name, exc)
        if not st.session_state.get("failure_modal_message"):
            st.session_state.failure_modal_message = random.choice(ERROR_DIALOG_MESSAGES)
        st.session_state.render_failure_detected = True
        st.session_state.error_modal_open = True
        st.session_state.incident_context = {
            "section": section_name,
            "tab": tab_label or section_name,
            "trigger": "auto",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case_index": case_index,
            "exception": repr(exc),
            "stacktrace": traceback.format_exc(),
        }
        st.session_state.reporter_source = "auto"
        placeholder.empty()
        show_failure_modal()
        if st.session_state.get("reporter_open"):
            show_incident_report_modal()
        st.stop()


def _render_case_tab(idx: int) -> None:
    """Render a single case tab inside the failure monitor."""

    load_case_state(idx)

    case_label = _case_display_name(idx)
    if idx > 0:
        col_label, col_close = st.columns([10, 1])
        with col_label:
            st.markdown(
                f"<h3 style='margin-bottom: 0.25rem'>Case: {escape(case_label)}</h3>",
                unsafe_allow_html=True,
            )
        with col_close:
            close_key = case_widget_key("close_case", idx=idx)
            if st.button("✕", key=close_key, help="Close this case tab"):
                close_case_tab(idx)
                st.rerun()
    elif idx == 0:
        st.markdown(
            f"<h3 style='margin-bottom: 0.25rem'>Case: {escape(case_label)}</h3>",
            unsafe_allow_html=True,
        )

    render_case_ui(idx)
    save_case_state(idx)


def render_case_kiroshi_chat_panel(case_idx: int) -> None:
    chat_tab_key = partial(case_widget_key, CASE_TAB_SLUGS["Kiroshi Chat"], case_idx=case_idx)
    case_label = _case_display_name(case_idx)
    sarcasm_enabled = st.session_state.get("kiroshi_sarcasm_mode", False)
    meta = _case_chat_meta(case_idx)

    if not st.session_state.get("_case_chat_styles_injected", False):
        st.markdown(
            """
            <style>
                .kiroshi-chat-wrap {
                    background: linear-gradient(140deg, rgba(15, 23, 42, 0.95), rgba(49, 46, 129, 0.92));
                    border-radius: 24px;
                    padding: 1.6rem 1.8rem;
                    border: 1px solid rgba(148, 163, 184, 0.28);
                    box-shadow: 0 26px 52px rgba(15, 23, 42, 0.45);
                    backdrop-filter: blur(12px);
                }
                .kiroshi-chat-wrap [data-testid="stChatMessage"] {
                    background: transparent;
                }
                .kiroshi-chat-wrap [data-testid="stChatMessage"] > div {
                    border-radius: 18px;
                    padding: 0.85rem 1rem;
                    background: rgba(15, 23, 42, 0.7);
                    border: 1px solid rgba(148, 163, 184, 0.32);
                    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.45);
                    color: #e2e8f0;
                }
                .kiroshi-chat-wrap [data-testid="stChatMessage"]:nth-child(even) > div {
                    background: linear-gradient(120deg, #22d3ee, #818cf8);
                    color: #0f172a;
                }
                .kiroshi-chat-wrap textarea {
                    border-radius: 18px !important;
                    background: rgba(15, 23, 42, 0.55);
                    color: #e2e8f0 !important;
                    border: 1px solid rgba(148, 163, 184, 0.35);
                }
                .kiroshi-chat-wrap textarea:focus {
                    border-color: rgba(129, 140, 248, 0.9) !important;
                    box-shadow: 0 0 0 1px rgba(129, 140, 248, 0.65) !important;
                }
                .kiroshi-chat-actions button {
                    border-radius: 999px !important;
                    font-weight: 600;
                    letter-spacing: 0.02em;
                }
                .kiroshi-chat-metric {
                    background: rgba(15, 23, 42, 0.65);
                    border: 1px solid rgba(148, 163, 184, 0.25);
                    border-radius: 16px;
                    padding: 0.9rem 1rem;
                    box-shadow: 0 18px 36px rgba(15, 23, 42, 0.4);
                }
                .kiroshi-chat-metric span.label {
                    display: block;
                    text-transform: uppercase;
                    letter-spacing: 0.08em;
                    font-size: 0.68rem;
                    color: #c7d2fe;
                }
                .kiroshi-chat-metric strong {
                    display: block;
                    margin-top: 0.35rem;
                    font-size: 1.05rem;
                    color: #f8fafc;
                }
                .kiroshi-chat-insight {
                    background: rgba(56, 189, 248, 0.12);
                    border: 1px solid rgba(56, 189, 248, 0.35);
                    border-radius: 16px;
                    padding: 0.85rem 1rem;
                    color: #e0f2fe;
                    box-shadow: inset 0 0 0 1px rgba(14, 165, 233, 0.15);
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.session_state["_case_chat_styles_injected"] = True

    if meta.get("toast"):
        st.success(str(meta.pop("toast")))

    st.image(str(KIROSHI_CHAT_LOGO_PATH), width=70)
    st.subheader(f"Kiroshi Chat — {case_label}")
    if sarcasm_enabled:
        st.caption(
            "Sarcasm Mode is enabled—Kiroshi will lean into dry wit while keeping the guidance sharp."
        )
    else:
        st.caption(
            "Kiroshi is answering in the standard helpful voice. Toggle Sarcasm Mode in Settings for extra banter."
        )

    sessions = st.session_state.get("case_sessions")
    case_obj: CaseData | None = None
    if isinstance(sessions, list) and 0 <= case_idx < len(sessions):
        candidate = getattr(sessions[case_idx], "case", None)
        if isinstance(candidate, CaseData):
            case_obj = candidate

    metrics = [
        ("Case ID", getattr(case_obj, "case_id", "") or f"Case {case_idx + 1}"),
        ("Company", getattr(case_obj, "company_name", "") or "Not provided"),
        (
            "App Version",
            getattr(case_obj, "application_version", "") or "Unknown build",
        ),
    ]
    metric_cols = st.columns(len(metrics))
    for col, (label, value) in zip(metric_cols, metrics):
        col.markdown(
            f"<div class='kiroshi-chat-metric'><span class='label'>{escape(label)}</span><strong>{escape(value)}</strong></div>",
            unsafe_allow_html=True,
        )

    if case_obj and case_obj.brief_description:
        st.markdown(
            f"<div class='kiroshi-chat-insight'>📄 <strong>Snapshot:</strong> {escape(case_obj.brief_description)}</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Personality & Memory Controls"):
        personality_mode = st.session_state.get("personality_mode", "utility")
        sarcasm_state = "On" if sarcasm_enabled else "Off"
        st.caption(
            f"Active personality: {personality_mode.replace('_', ' ').title()} · Sarcasm mode: {sarcasm_state}"
        )
        base_prompt_key = chat_tab_key("system_prompt_base")
        current_prompt = st.session_state.get("system_prompt", SYSTEM_PROMPT)
        base_registry = st.session_state.get("_system_prompt_widget_keys")
        if not isinstance(base_registry, set):
            base_registry = set()
        base_registry.add(base_prompt_key)
        st.session_state["_system_prompt_widget_keys"] = base_registry
        if st.session_state.get(base_prompt_key) != current_prompt:
            st.session_state[base_prompt_key] = current_prompt
        edited_prompt = st.text_area(
            "Base system prompt",
            height=220,
            key=base_prompt_key,
            help=(
                "Adjust the construct template that every chat request starts from. Personality and sarcasm settings "
                "layer on top of this base."
            ),
        )
        if edited_prompt != st.session_state.get("system_prompt"):
            st.session_state["system_prompt"] = edited_prompt
            for other_key in st.session_state.get("_system_prompt_widget_keys", set()):
                st.session_state[other_key] = edited_prompt

        preview_value = build_system_prompt()
        preview_key = chat_tab_key("system_prompt_preview")
        if st.session_state.get(preview_key) != preview_value:
            st.session_state[preview_key] = preview_value
        st.text_area(
            "Active construct preview",
            value=preview_value,
            height=220,
            key=preview_key,
            help="Exact system prompt currently sent with each chat request.",
            disabled=True,
        )

        control_cols = st.columns(2)
        if control_cols[0].button(
            "Clear case chat history",
            key=chat_tab_key("clear_case_history"),
        ):
            store = _case_chat_history_store()
            store[_case_chat_state_key(case_idx)] = []
            meta_store = st.session_state.get("case_chat_meta")
            if isinstance(meta_store, dict):
                meta_store.pop(_case_chat_state_key(case_idx), None)
            meta["toast"] = "Case chat reset."
            st.rerun()
        if control_cols[1].button(
            "Flush global assistant memory",
            key=chat_tab_key("flush_global_memory"),
        ):
            st.session_state.kiroshi_chat_history = []
            save_memory([])
            meta["toast"] = "Global assistant memory cleared."
            st.rerun()

    with st.expander("Manual Knowledge Base"):
        if st.session_state.manual_docs:
            st.markdown("**Stored documents:**")
            for doc in st.session_state.manual_docs:
                st.markdown(f"- {doc['title']}")
        doc_file = st.file_uploader(
            "Add document",
            type=["txt"],
            key=chat_tab_key("doc_file"),
        )
        doc_title = st.text_input("Title", key=chat_tab_key("doc_title"))
        if st.button("Save document", key=chat_tab_key("save_doc")):
            if doc_file and doc_title:
                content = doc_file.getvalue().decode("utf-8", errors="ignore")
                st.session_state.manual_docs.append({"title": doc_title, "content": content})
                save_manual_docs(st.session_state.manual_docs)
                st.success("Document saved.")
            else:
                st.error("Provide both title and document.")

        api_key = st.session_state.openai_api_key
        model = st.session_state.openai_model
        base_url = st.session_state.ai_base_url

        def _chat_ready() -> bool:
            if not api_key and base_url.startswith("https://api.openai.com"):
                st.error("Set your OpenAI API key in the Debug tab to query Kiroshi.")
                return False
            return True

        case_context_message = _build_case_context_prompt(case_idx)

        def _execute_exchange(
            prompt_payload: str,
            display_prompt: str,
            *,
            source: str,
            mode: str | None = None,
        ) -> str:
            history_for_model = [
                {"role": "system", "content": case_context_message}
            ] + _case_chat_history_for_model(case_idx)
            _append_case_chat_message(
                case_idx,
                "user",
                prompt_payload,
                display_content=display_prompt,
                mode=mode,
            )
            try:
                reply_text = invoke_gpt(
                    prompt_payload,
                    history_for_model,
                    api_key,
                    model,
                    base_url,
                    source=source,
                )
            except Exception as exc:
                logging.error("Case chat request failed: %s", exc)
                reply_text = str(exc)
            _append_case_chat_message(case_idx, "assistant", reply_text, mode=mode)
            _record_global_chat_exchange(prompt_payload, reply_text)
            return reply_text

        search_query = st.text_input("Search query", key=chat_tab_key("db_query"))
        if st.button("Search in database", key=chat_tab_key("db_search_button")):
            if not search_query:
                st.error("Enter a search query.")
            elif not _chat_ready():
                pass
            else:
                matches = search_manual_docs(search_query, st.session_state.manual_docs)
                display_prompt = f"🔍 Manual docs search: {search_query}"
                if matches:
                    context = "\n\n".join(f"{m['title']}:\n{m['content']}" for m in matches)
                    message = (
                        "Use the following documents to answer the question. "
                        "Cite document titles when drawing from them.\n\n"
                        + context
                        + f"\n\nQuestion: {search_query}"
                    )
                    reply = _execute_exchange(
                        message,
                        display_prompt,
                        source="manual_docs_search",
                        mode="manual_docs",
                    )
                    meta["last_manual_search"] = {"query": search_query, "answer": reply}
                    st.rerun()
                else:
                    notice = "No documents matched your query."
                    _append_case_chat_message(
                        case_idx,
                        "user",
                        f"[Manual docs] {search_query}",
                        display_content=display_prompt,
                        mode="manual_docs",
                    )
                    _append_case_chat_message(
                        case_idx,
                        "assistant",
                        notice,
                        mode="manual_docs",
                    )
                    _record_global_chat_exchange(f"[Manual docs] {search_query}", notice)
                    meta["last_manual_search"] = {"query": search_query, "answer": notice}
                    st.rerun()

        last_search = meta.get("last_manual_search")
        if isinstance(last_search, dict):
            query_label = last_search.get("query") or ""
            answer_text = last_search.get("answer") or ""
            if query_label and answer_text:
                st.markdown("**Latest manual-search answer**")
                st.caption(query_label)
                st.markdown(answer_text)

    st.markdown("<div class='kiroshi-chat-wrap'>", unsafe_allow_html=True)
    chat_container = st.container()
    with chat_container:
        history = _case_chat_history(case_idx)
        if history:
            for entry in history:
                role = entry.get("role")
                content = entry.get("display_content") or entry.get("content")
                if not content:
                    continue
                avatar = "🧑‍💻" if role == "user" else "🤖"
                with st.chat_message("user" if role == "user" else "assistant", avatar=avatar):
                    mode = entry.get("mode")
                    if mode == "educate" and role == "assistant":
                        st.markdown("🧠 **AI Educate Insight**\n\n" + str(content))
                    elif mode == "educate" and role == "user":
                        st.markdown("**Answer with Educate**\n\n" + str(content))
                    elif mode == "manual_docs" and role == "user":
                        st.markdown("**Manual docs search**\n\n" + str(content))
                    else:
                        st.markdown(str(content))
        else:
            st.markdown("_No chat history yet — ask Kiroshi about this case to get started._")

        prompt_key = chat_tab_key("prompt")
        user_prompt = st.text_area(
            "Message",
            key=prompt_key,
            height=120,
            placeholder="Ask Kiroshi for guidance, updates, or troubleshooting help about this case…",
            label_visibility="collapsed",
        )
        action_cols = st.columns([3, 2], gap="small")
        send_clicked = action_cols[0].button(
            "Send to Kiroshi",
            key=chat_tab_key("send_button"),
            use_container_width=True,
        )
        educate_clicked = action_cols[1].button(
            "Answer with Educate",
            key=chat_tab_key("educate_button"),
            use_container_width=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    api_key = st.session_state.openai_api_key
    model = st.session_state.openai_model
    base_url = st.session_state.ai_base_url
    case_context_message = _build_case_context_prompt(case_idx)

    def _chat_ready_global() -> bool:
        if not api_key and base_url.startswith("https://api.openai.com"):
            st.error("Set your OpenAI API key in the Debug tab to chat with Kiroshi.")
            return False
        return True

    def _execute_prompt(prompt_payload: str, display_prompt: str, *, source: str, mode: str | None = None) -> None:
        history_for_model = [
            {"role": "system", "content": case_context_message}
        ] + _case_chat_history_for_model(case_idx)
        _append_case_chat_message(
            case_idx,
            "user",
            prompt_payload,
            display_content=display_prompt,
            mode=mode,
        )
        try:
            reply_text = invoke_gpt(
                prompt_payload,
                history_for_model,
                api_key,
                model,
                base_url,
                source=source,
            )
        except Exception as exc:
            logging.error("Case chat request failed: %s", exc)
            reply_text = str(exc)
        _append_case_chat_message(case_idx, "assistant", reply_text, mode=mode)
        _record_global_chat_exchange(prompt_payload, reply_text)

    if send_clicked:
        message = (user_prompt or "").strip()
        if not message:
            st.warning("Type a message before sending.")
        elif _chat_ready_global():
            tone_directive = build_kiroshi_tone_directive()
            prompt_payload = (
                f"You are Kiroshi, the resident support expert assisting with {case_label}. {tone_directive} "
                "Use the full case JSON provided in the system context to answer the user's question accurately and concisely.\n\n"
                f"User question: {message}"
            )
            _execute_prompt(prompt_payload, message, source="case_chat")
            st.session_state[prompt_key] = ""
            st.rerun()

    if educate_clicked:
        message = (user_prompt or "").strip()
        if not message:
            st.warning("Ask a question before using Answer with Educate.")
        elif not st.session_state.get("ai_educate_enabled", False):
            st.warning("Enable AI Educate in Settings to unlock this button.")
        else:
            dataset = ensure_ai_learning_dataset()
            if not dataset:
                st.warning("No AI Educate dataset available. Generate one from the Educate panel first.")
            else:
                matches = find_relevant_learning_cases(case_obj or CaseData(), dataset, max_results=6)
                summary_payload = {
                    "insight_summary": dataset.get("insight_summary", {}),
                    "keyword_insights": dataset.get("keyword_insights", [])[:5],
                    "repeated_solutions": dataset.get("repeated_solutions", [])[:3],
                    "top_matches": matches,
                }
                knowledge_block = json.dumps(
                    summary_payload,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )
                tone_directive = build_kiroshi_tone_directive()
                prompt_payload = (
                    f"You are Kiroshi, the resident support expert assisting with {case_label}. {tone_directive} "
                    "Answer using the AI Educate knowledge base below plus the active case JSON. "
                    "Call out which historic cases, solutions, or patterns inform your advice.\n\n"
                    f"AI EDUCATE KNOWLEDGE (abridged):\n{knowledge_block}\n\n"
                    f"User question: {message}"
                )
                display_prompt = f"**Answer with Educate**\n\n{message}"
                _execute_prompt(
                    prompt_payload,
                    display_prompt,
                    source="case_chat_educate",
                    mode="educate",
                )
                st.session_state[prompt_key] = ""
                st.rerun()


def render_smart_aid_panel() -> None:
    st.subheader("Smart Aid Calibration")
    st.markdown(
        "Capture supervisor feedback once and let every AI feature remind you about it automatically."
    )

    default_areas = ["AI Assistance", "Quick Actions", "Kiroshi Chat"]
    supervisor_key = global_widget_key("smart_supervisor")
    feedback_key = global_widget_key("smart_feedback")
    areas_key = global_widget_key("smart_areas")

    supervisor_name = st.text_input(
        "Supervisor (optional)", key=supervisor_key
    )
    feedback_text = st.text_area(
        "Supervisor feedback or reminder",
        height=120,
        key=feedback_key,
    )
    selected_areas = st.multiselect(
        "Where should this reminder apply?",
        default_areas,
        default=default_areas,
        help="Smart Aid keeps a single memory shared with AI Assistance, Quick Actions, and Kiroshi Chat.",
        key=areas_key,
    )

    if st.button("Calibrate", type="primary", key=global_widget_key("smart_calibrate")):
        note_text = (feedback_text or "").strip()
        if not note_text:
            st.error("Please enter supervisor feedback before calibrating.")
        else:
            areas = [
                str(area).strip()
                for area in (selected_areas or default_areas)
                if str(area).strip()
            ] or default_areas
            note = {
                "id": uuid.uuid4().hex,
                "text": note_text,
                "supervisor": (supervisor_name or "").strip(),
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "areas": areas,
            }
            notes = get_assistant_notes()
            notes.append(note)
            set_assistant_notes(notes)
            save_memory(st.session_state.kiroshi_chat_history)
            st.success("Calibration saved to unified memory.")
            st.session_state[feedback_key] = ""
            st.session_state[supervisor_key] = ""
            st.session_state[areas_key] = default_areas
            st.rerun()

    notes = get_assistant_notes()
    if notes:
        st.markdown("#### Active supervisor reminders")
        sorted_notes = sorted(
            notes,
            key=lambda n: str(n.get("created_at", "")),
            reverse=True,
        )
        for note in sorted_notes:
            with st.container():
                st.markdown(f"**{note.get('text', '')}**")
                meta_bits: list[str] = []
                created_label = ""
                created_at = str(note.get("created_at", "")).strip()
                if created_at:
                    try:
                        created_dt = datetime.fromisoformat(created_at)
                        created_label = created_dt.strftime("Saved on %b %d, %Y %H:%M")
                    except ValueError:
                        created_label = f"Saved: {created_at}"
                if created_label:
                    meta_bits.append(created_label)
                supervisor = str(note.get("supervisor", "")).strip()
                if supervisor:
                    meta_bits.append(f"Supervisor: {supervisor}")
                areas = note.get("areas")
                if isinstance(areas, list) and areas:
                    meta_bits.append("Applies to: " + ", ".join(areas))
                if meta_bits:
                    st.caption(" • ".join(meta_bits))
                remove_key = global_widget_key(f"smart_remove_{note.get('id', '')}")
                if st.button(
                    "Remove",
                    key=remove_key,
                    help="Delete this calibration note",
                ):
                    remaining = [n for n in notes if n.get("id") != note.get("id")]
                    set_assistant_notes(remaining)
                    save_memory(st.session_state.kiroshi_chat_history)
                    st.rerun()
        memory_preview = build_assistant_memory_prompt()
        if memory_preview:
            st.markdown("#### Unified memory preview")
            st.code(memory_preview, language="markdown")
    else:
        st.info("No supervisor feedback saved yet. Add a calibration above to prime Smart Aid.")


def render_debug_panel() -> None:
    if st.session_state.debug_auth:
        st.subheader("Debug")
        st.info("AI Configuration has been moved to Settings > AI & Knowledge.")

        st.selectbox("Personality mode", ["utility", "coffee"], key="personality_mode")
        st.text_area("Allowed categories block", key="taxonomy_block", height=150)
        st.text_area("Signals config JSON", key="signals_config", height=150)
        st.json(get_session_state_snapshot())
        st.subheader("Logs")
        if log_path:
            st.caption(f"Log file location: {log_path}")
            target = log_path
        else:
            st.caption("Log file location unavailable; falling back to stdout output.")
            target = LOG_FILE
        st.text(tail_log(target))
        st.divider()
        st.subheader("Case debug tools")
        sessions = getattr(st.session_state, "case_sessions", None)
        if not isinstance(sessions, Sequence) or not sessions:
            st.info("Create or load a case to access case-specific debug utilities.")
        else:
            fallback_default = 0
            if len(sessions) > 1:
                fallback_default = min(max(CURRENT_CASE_IDX, 0), len(sessions) - 1)

            default_target = _resolve_hotkey_target_index(sessions, fallback_default)
            if not isinstance(default_target, int) or default_target < 0:
                default_target = 0
            default_target = min(default_target, len(sessions) - 1)

            def _format_case_label(idx: int) -> str:
                session = sessions[idx]
                case = getattr(session, "case", None)
                case_id = getattr(case, "case_id", "") if case else ""
                company = getattr(case, "company_name", "") if case else ""
                label = case_id or _case_display_name(idx)
                return f"{label} – {company}" if company else label

            selected_case_idx = st.selectbox(
                "Case context",
                list(range(len(sessions))),
                index=default_target,
                format_func=_format_case_label,
                key="debug_case_context",
            )

            current_target = st.session_state.get(HOTKEY_TARGET_SESSION_KEY)
            use_for_hotkeys = st.checkbox(
                "Use this case for global clipboard hotkeys",
                value=current_target == selected_case_idx,
                key="debug_hotkey_target_toggle",
                help=(
                    "When enabled, Ctrl+Alt+C and the numeric shortcuts copy tables "
                    "from this case even if another tab is open."
                ),
            )
            if use_for_hotkeys and current_target != selected_case_idx:
                st.session_state[HOTKEY_TARGET_SESSION_KEY] = selected_case_idx
                _refresh_hotkey_snapshot()
            elif not use_for_hotkeys and current_target == selected_case_idx:
                st.session_state[HOTKEY_TARGET_SESSION_KEY] = None
                _refresh_hotkey_snapshot()

            try:
                category_map = active_category_map()
            except Exception:
                logging.exception("Failed to build category map for debug panel")
                category_map = {}
            render_autohotkey_panel(category_map, selected_case_idx)
        st.divider()
        if st.button("I'm bored", key=global_widget_key("debug_bored")):
            st.session_state.show_bored = True
            st.rerun()
    else:
        st.session_state.show_bored = False
        user = st.text_input("Username", key=global_widget_key("debug_user"))
        pw = st.text_input(
            "Password", type="password", key=global_widget_key("debug_pass")
        )
        if st.button("Login", key=global_widget_key("debug_login")):
            if user == "admin" and pw == "admin":
                st.session_state.debug_auth = True
            else:
                st.error("Invalid credentials")


def recent_tracked_files(cases: list | None = None) -> list[Path]:
    if cases is None:
        cases = load_tracked_cases()
    files: list[Path] = []
    for entry in cases:
        path_value = entry.get("path") if isinstance(entry, Mapping) else None
        if not path_value:
            continue
        candidate = Path(path_value)
        if candidate.exists():
            files.append(candidate)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:20]


def _summarize_text(text: str, width: int = 200) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    try:
        return textwrap.shorten(cleaned, width=width, placeholder="…")
    except Exception:
        return cleaned[:width]


def _extract_keywords(*texts: str) -> list[str]:
    keywords: list[str] = []
    for text in texts:
        if not text:
            continue
        tokens = WORD_PATTERN.findall(text.lower())
        for token in tokens:
            if len(token) <= 3 or token in STOPWORDS or token.isdigit():
                continue
            keywords.append(token)
    return sorted(set(keywords))




def _normalize_agent_name(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _agent_identity_snapshot() -> dict[str, str]:
    try:
        first = _normalize_agent_name(st.session_state.get("agent_first_name", ""))
        last = _normalize_agent_name(st.session_state.get("agent_last_name", ""))
    except AttributeError:
        first = ""
        last = ""

    if not first:
        first = _normalize_agent_name(
            _persistent_settings_cache.get("agent_first_name", "")
        )
    if not last:
        last = _normalize_agent_name(
            _persistent_settings_cache.get("agent_last_name", "")
        )

    parts = [part for part in (first, last) if part]
    display = " ".join(parts)
    slug_parts = [
        re.sub(r"[^a-z0-9]+", "-", part.lower()).strip("-")
        for part in parts
        if part
    ]
    identifier = "-".join([part for part in slug_parts if part])

    return {
        "first_name": first,
        "last_name": last,
        "display_name": display,
        "identifier": identifier,
    }


def _create_ai_learning_dataset_from_cases(
    case_entries: Iterable[Mapping[str, object]],
    *,
    signature: Iterable[tuple[str, float]] | None = None,
    merged_sources: Iterable[str] | None = None,
    generated_at: str | None = None,
    agent_identity: Mapping[str, str] | None = None,
) -> dict[str, object] | None:
    cases: list[dict[str, object]] = []
    keyword_counter: Counter[str] = Counter()
    root_cause_counter: Counter[str] = Counter()
    solution_counter: Counter[str] = Counter()
    version_counter: Counter[str] = Counter()
    keyword_index: defaultdict[str, list[str]] = defaultdict(list)
    root_cause_cases: defaultdict[str, list[str]] = defaultdict(list)
    solution_cases: defaultdict[str, list[str]] = defaultdict(list)
    root_cause_labels: dict[str, str] = {}
    solution_labels: dict[str, str] = {}

    for entry in case_entries:
        if not isinstance(entry, Mapping):
            continue
        case_id = str(entry.get("case_id") or "").strip()
        if not case_id:
            continue
        title = str(entry.get("title") or "").strip()
        root_cause = str(entry.get("root_cause") or "").strip()
        solution = str(entry.get("solution") or "").strip()
        application_version = str(entry.get("application_version") or "").strip()
        keywords = entry.get("keywords") or []
        if not isinstance(keywords, list):
            keywords = list(keywords)
        keywords = [str(keyword) for keyword in keywords if keyword]

        for keyword in keywords:
            keyword_counter[keyword] += 1
            if case_id not in keyword_index[keyword]:
                keyword_index[keyword].append(case_id)

        if root_cause:
            norm_root = root_cause.lower()
            root_cause_counter[norm_root] += 1
            root_cause_labels.setdefault(norm_root, root_cause)
            if case_id not in root_cause_cases[norm_root]:
                root_cause_cases[norm_root].append(case_id)

        if solution:
            norm_solution = solution.lower()
            solution_counter[norm_solution] += 1
            solution_labels.setdefault(norm_solution, solution)
            if case_id not in solution_cases[norm_solution]:
                solution_cases[norm_solution].append(case_id)

        if application_version:
            version_counter[application_version] += 1

        timestamp_raw = entry.get("timestamp")
        try:
            timestamp = float(timestamp_raw)
        except (TypeError, ValueError):
            timestamp = 0.0

        saved_at = entry.get("saved_at")
        if not saved_at and timestamp:
            saved_at = datetime.fromtimestamp(timestamp).isoformat()

        case_entry = {
            "case_id": case_id,
            "title": title or _summarize_text(entry.get("description", ""), width=120),
            "application_version": application_version,
            "root_cause": root_cause,
            "solution": solution,
            "solution_excerpt": entry.get("solution_excerpt")
            or _summarize_text(solution, width=260),
            "description_excerpt": entry.get("description_excerpt")
            or _summarize_text(entry.get("description", ""), width=260),
            "keywords": keywords,
            "timestamp": timestamp,
            "saved_at": saved_at,
            "source_path": entry.get("source_path"),
        }
        if agent_identity:
            agent_identifier = _normalize_agent_name(agent_identity.get("identifier"))
            if agent_identifier:
                case_entry["agent_id"] = agent_identifier
            display_name = _normalize_agent_name(agent_identity.get("display_name"))
            if display_name:
                case_entry["agent_name"] = display_name
        cases.append(case_entry)

    if not cases:
        return None

    cases.sort(key=lambda item: item.get("timestamp", 0), reverse=True)

    keyword_insights = [
        {
            "keyword": keyword,
            "count": count,
            "related_cases": keyword_index[keyword][:5],
        }
        for keyword, count in keyword_counter.most_common(20)
    ]

    root_cause_patterns = [
        {
            "root_cause": root_cause_labels[key],
            "count": root_cause_counter[key],
            "related_cases": root_cause_cases[key][:5],
        }
        for key in sorted(root_cause_counter, key=root_cause_counter.get, reverse=True)
    ]

    repeated_solutions = [
        {
            "solution": solution_labels[key],
            "count": solution_counter[key],
            "related_cases": solution_cases[key][:5],
        }
        for key in sorted(solution_counter, key=solution_counter.get, reverse=True)
        if solution_counter[key] > 1
    ]

    dataset: dict[str, object] = {
        "generated_at": generated_at or _utc_now_z(),
        "case_count": len(cases),
        "cases": cases,
        "keyword_insights": keyword_insights,
        "root_cause_patterns": root_cause_patterns,
        "repeated_solutions": repeated_solutions,
        "version_distribution": version_counter.most_common(),
        "insight_summary": {
            "top_keywords": [kw for kw, _ in keyword_counter.most_common(10)],
            "dominant_versions": version_counter.most_common(5),
        },
    }

    if signature is not None:
        dataset["source_signature"] = [list(item) for item in signature]

    merged_labels: set[str] = set()
    if merged_sources:
        merged_labels.update(str(label) for label in merged_sources if label)
    if merged_labels:
        dataset["merged_sources"] = sorted(merged_labels)

    if agent_identity:
        identity_payload = {
            "first_name": _normalize_agent_name(agent_identity.get("first_name")),
            "last_name": _normalize_agent_name(agent_identity.get("last_name")),
            "display_name": _normalize_agent_name(agent_identity.get("display_name")),
            "identifier": _normalize_agent_name(agent_identity.get("identifier")),
        }
        dataset["agent_identity"] = identity_payload
        if identity_payload.get("display_name") and not dataset.get("shared_by"):
            dataset["shared_by"] = identity_payload["display_name"]

    return dataset


@st.cache_data(ttl=None, max_entries=1)
def _load_ai_learning_dataset_worker(mtime: float) -> dict[str, object] | None:
    """Load AI learning dataset from disk, cached until modification time changes."""
    try:
        data = json.loads(AI_LEARNING_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (OSError, json.JSONDecodeError):
        return None


def load_ai_learning_dataset() -> dict[str, object] | None:
    mtime = 0.0
    if AI_LEARNING_FILE.exists():
        try:
            mtime = AI_LEARNING_FILE.stat().st_mtime
        except OSError:
            pass
    return _load_ai_learning_dataset_worker(mtime)


def merge_ai_learning_datasets(
    base_dataset: Mapping[str, object] | None,
    imported_dataset: Mapping[str, object],
    *,
    collaborator: str | None = None,
    local_signature: Iterable[tuple[str, float]] | None = None,
) -> dict[str, object] | None:
    if not isinstance(imported_dataset, Mapping):
        logging.error("Imported dataset is not a JSON object")
        return None

    base_cases = []
    if base_dataset and isinstance(base_dataset.get("cases"), list):
        base_cases = [dict(entry) for entry in base_dataset["cases"] if isinstance(entry, Mapping)]

    imported_cases_raw = imported_dataset.get("cases")
    if not isinstance(imported_cases_raw, list):
        logging.error("Imported dataset does not contain a cases list")
        return None
    imported_cases = [dict(entry) for entry in imported_cases_raw if isinstance(entry, Mapping)]

    combined: dict[tuple[str, str], dict[str, object]] = {}

    def _case_key(entry: Mapping[str, object]) -> tuple[str, str]:
        source = str(entry.get("source_path") or "").strip().lower()
        case_id = str(entry.get("case_id") or "").strip().lower()
        return source, case_id

    for entry in base_cases + imported_cases:
        key = _case_key(entry)
        if key in combined:
            existing = combined[key]
            try:
                existing_ts = float(existing.get("timestamp") or 0)
            except (TypeError, ValueError):
                existing_ts = 0.0
            try:
                new_ts = float(entry.get("timestamp") or 0)
            except (TypeError, ValueError):
                new_ts = 0.0
            if new_ts > existing_ts:
                combined[key] = dict(entry)
        else:
            combined[key] = dict(entry)

    if not combined:
        return None

    merged_sources: set[str] = set()
    if base_dataset:
        base_sources = base_dataset.get("merged_sources")
        if isinstance(base_sources, list):
            merged_sources.update(str(label) for label in base_sources if label)
        merged_sources.add("local")

    imported_sources = imported_dataset.get("merged_sources")
    if isinstance(imported_sources, list):
        merged_sources.update(str(label) for label in imported_sources if label)

    collaborator_label = collaborator or str(imported_dataset.get("shared_by") or "external").strip()
    if collaborator_label:
        merged_sources.add(collaborator_label)

    signature: Iterable[tuple[str, float]] | None = None
    if local_signature is not None:
        signature = local_signature
    elif base_dataset:
        base_signature = base_dataset.get("source_signature")
        if isinstance(base_signature, list):
            try:
                signature = tuple(tuple(item) for item in base_signature)
            except TypeError:
                signature = None
        elif isinstance(base_signature, tuple):
            signature = base_signature

    base_identity = None
    if base_dataset:
        candidate_identity = base_dataset.get("agent_identity")
        if isinstance(candidate_identity, Mapping):
            base_identity = dict(candidate_identity)
    if base_identity is None:
        candidate_identity = imported_dataset.get("agent_identity")
        if isinstance(candidate_identity, Mapping):
            base_identity = dict(candidate_identity)

    dataset = _create_ai_learning_dataset_from_cases(
        combined.values(),
        signature=signature,
        merged_sources=merged_sources,
        agent_identity=base_identity,
    )
    return dataset


def iter_saved_case_records() -> Iterable[tuple[Path, dict[str, object]]]:
    """Yield paths and loaded data for all saved case files."""
    if not DATABASE_DIR.exists():
        return

    try:
        for entry in os.scandir(DATABASE_DIR):
            if entry.is_file() and entry.name.lower().endswith(".json"):
                if entry.name in (
                    "settings.json",
                    "sprint_state.json",
                    "case_tabs_memory.json",
                    "kiroshi_tables_hotkeys.ahk",
                ):
                    continue

                try:
                    path = Path(entry.path)
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        yield path, data
                except (OSError, json.JSONDecodeError):
                    continue
    except OSError:
        return


def build_ai_learning_dataset(
    *, signature: Iterable[tuple[str, float]] | None = None
) -> dict[str, object] | None:
    cases: list[dict[str, object]] = []

    for path, record in iter_saved_case_records():
        case_id = str(record.get("case_id") or path.stem)
        brief_description = str(record.get("brief_description") or "").strip()
        description = str(record.get("description") or "").strip()
        root_cause = str(record.get("root_cause") or "").strip()
        solution = str(record.get("solution") or "").strip()
        application_version = str(record.get("application_version") or "").strip()
        troubleshooting = extract_remote_steps_from_mapping(record)
        if not troubleshooting:
            troubleshooting = str(record.get("troubleshooting") or "").strip()
        repro_steps = str(record.get("repro_steps") or "").strip()
        additional_info = str(record.get("additional_info") or "").strip()

        keywords = _extract_keywords(
            brief_description,
            description,
            root_cause,
            solution,
            troubleshooting,
            repro_steps,
        )

        timestamp = path.stat().st_mtime
        case_entry: dict[str, object] = {
            "case_id": case_id,
            "title": brief_description or _summarize_text(description, width=120),
            "application_version": application_version,
            "root_cause": root_cause,
            "solution": solution,
            "solution_excerpt": _summarize_text(solution, width=260),
            "description_excerpt": _summarize_text(description, width=260),
            "troubleshooting": troubleshooting,
            "troubleshooting_excerpt": _summarize_text(troubleshooting, width=260),
            "repro_steps": repro_steps,
            "repro_steps_excerpt": _summarize_text(repro_steps, width=260),
            "additional_info": additional_info,
            "keywords": keywords,
            "timestamp": timestamp,
            "saved_at": datetime.fromtimestamp(timestamp).isoformat(),
            "source_path": str(path),
        }
        cases.append(case_entry)

    identity = _agent_identity_snapshot()
    return _create_ai_learning_dataset_from_cases(
        cases,
        signature=signature,
        agent_identity=identity,
    )


def save_ai_learning_dataset(dataset: Mapping[str, object]) -> None:
    try:
        with AI_LEARNING_FILE.open("w", encoding="utf-8") as fh:
            json.dump(dataset, fh, indent=2)
    except Exception as exc:
        logging.error("Failed to write AI learning dataset: %s", exc)


def _sync_ai_learning_signature_from_dataset(
    dataset: Mapping[str, object] | None,
) -> None:
    if not isinstance(dataset, Mapping):
        st.session_state.ai_learning_signature = None
        return

    signature_payload = dataset.get("source_signature")
    if isinstance(signature_payload, list):
        try:
            st.session_state.ai_learning_signature = tuple(
                tuple(item) for item in signature_payload
            )
        except TypeError:
            st.session_state.ai_learning_signature = None
    elif isinstance(signature_payload, tuple):
        st.session_state.ai_learning_signature = signature_payload
    else:
        st.session_state.ai_learning_signature = None


def _saved_case_files_signature() -> tuple[tuple[str, float], ...]:
    """Return a signature of the current state of saved case files."""
    if not DATABASE_DIR.exists():
        return ()

    files: list[tuple[str, float]] = []
    try:
        for entry in os.scandir(DATABASE_DIR):
            if entry.is_file() and entry.name.lower().endswith(".json"):
                if entry.name in (
                    "settings.json",
                    "sprint_state.json",
                    "case_tabs_memory.json",
                    "kiroshi_tables_hotkeys.ahk",
                ):
                    continue
                files.append((entry.name, entry.stat().st_mtime))
    except OSError:
        return ()

    return tuple(sorted(files))


def ensure_ai_learning_dataset(force: bool = False) -> dict[str, object] | None:
    if force:
        signature = _saved_case_files_signature()
        existing_dataset = load_ai_learning_dataset()

        dataset: dict[str, object] | None = None
        local_dataset: dict[str, object] | None = None
        if signature:
            local_dataset = build_ai_learning_dataset(signature=signature)

        if local_dataset and existing_dataset:
            merged_dataset = merge_ai_learning_datasets(
                existing_dataset,
                local_dataset,
                collaborator=None,
                local_signature=signature,
            )
            dataset = merged_dataset or local_dataset
        elif local_dataset:
            dataset = local_dataset
        else:
            dataset = existing_dataset

        if not dataset:
            st.session_state.ai_learning_data = None
            st.session_state.ai_learning_signature = None
            return None

        save_ai_learning_dataset(dataset)
        st.session_state.ai_learning_data = dataset
        _sync_ai_learning_signature_from_dataset(dataset)
        logging.info(
            "AI learning dataset generated from %s cases", dataset.get("case_count", 0)
        )
        return dataset

    cached_dataset = st.session_state.get("ai_learning_data")
    if isinstance(cached_dataset, Mapping) and cached_dataset:
        return cached_dataset

    dataset = load_ai_learning_dataset()
    if not dataset:
        return None

    st.session_state.ai_learning_data = dataset
    _sync_ai_learning_signature_from_dataset(dataset)

    return dataset


def find_relevant_learning_cases(
    case: CaseData,
    dataset: Mapping[str, object] | None,
    *,
    max_results: int = 5,
) -> list[dict[str, object]]:
    if not dataset:
        return []

    query_tokens = set(
        _extract_keywords(
            case.brief_description,
            case.description,
            case.root_cause,
            case.solution,
            case.remote_steps,
            case.additional_info,
        )
    )
    if case.application_version:
        query_version = case.application_version.lower()
    else:
        query_version = ""

    if not query_tokens and not query_version:
        return []

    results: list[dict[str, object]] = []
    for entry in dataset.get("cases", []):
        entry_keywords = set(entry.get("keywords", []))
        shared_keywords = query_tokens & entry_keywords
        score = len(shared_keywords)

        entry_version = str(entry.get("application_version") or "").lower()
        if query_version and entry_version and query_version == entry_version:
            score += 1

        entry_root = str(entry.get("root_cause") or "").lower()
        if case.root_cause and entry_root and entry_root in case.root_cause.lower():
            score += 2

        if case.root_cause and entry_root and case.root_cause.lower() in entry_root:
            score += 1

        if not score:
            continue

        results.append(
            {
                "case_id": entry.get("case_id"),
                "title": entry.get("title"),
                "root_cause": entry.get("root_cause"),
                "solution": entry.get("solution"),
                "solution_excerpt": entry.get("solution_excerpt"),
                "keywords": sorted(shared_keywords) if shared_keywords else entry.get("keywords", []),
                "score": score,
                "saved_at": entry.get("saved_at"),
                "timestamp": entry.get("timestamp", 0),
            }
        )

    results.sort(key=lambda item: (item.get("score", 0), item.get("timestamp", 0)), reverse=True)
    return results[:max_results]


def _text_contains_bug(*parts: object) -> bool:
    combined = " ".join(str(part or "") for part in parts).lower()
    return "bug" in combined


def collect_ai_educate_report_data(
    dataset: Mapping[str, object] | None,
) -> dict[str, object]:
    if not dataset:
        return {}

    cases = dataset.get("cases", [])
    if not isinstance(cases, list) or not cases:
        return {}

    df = pd.DataFrame(cases)
    if df.empty:
        return {}

    df["timestamp"] = pd.to_datetime(df.get("timestamp"), unit="s", errors="coerce")
    df["saved_at_dt"] = pd.to_datetime(df.get("saved_at"), errors="coerce")
    df["event_time"] = df["timestamp"].where(df["timestamp"].notna(), df["saved_at_dt"])

    title_series = df.get("title")
    if isinstance(title_series, pd.Series):
        title_values = title_series.fillna("").astype(str).tolist()
    else:
        title_values = ["" for _ in range(len(df))]
    cluster_assignments, cluster_label_map = _cluster_case_titles(title_values)
    df["title_cluster_id"] = cluster_assignments
    cluster_labels: list[str] = []
    for assignment, title in zip(cluster_assignments, title_values):
        label = cluster_label_map.get(assignment)
        if not label:
            label = _summarize_text(title, width=80) if title else "Caso sin título"
        cluster_labels.append(label)
    df["title_cluster_label"] = cluster_labels
    cluster_label_series = pd.Series(cluster_labels, dtype="object")
    if cluster_label_series.empty:
        df["title_cluster_recurrence"] = 1
    else:
        cluster_counts = (
            cluster_label_series[cluster_label_series != ""].value_counts()
        )
        if cluster_counts.empty:
            df["title_cluster_recurrence"] = 1
        else:
            df["title_cluster_recurrence"] = (
                df["title_cluster_label"].map(cluster_counts).fillna(1).astype(int)
            )

    root_cause_series = df.get("root_cause", pd.Series(dtype="object"))
    root_cause_norm = root_cause_series.apply(_normalize_text_field)
    root_cause_labels: dict[str, str] = {}
    if isinstance(root_cause_series, pd.Series):
        for original, normalized in zip(root_cause_series.tolist(), root_cause_norm.tolist()):
            if normalized and normalized not in root_cause_labels and isinstance(original, str):
                root_cause_labels[normalized] = original
    root_cause_counts = root_cause_norm[root_cause_norm != ""].value_counts()

    existing_recurrence = df.get("recurrence_count")
    if isinstance(existing_recurrence, pd.Series):
        df["recurrence_count"] = existing_recurrence.apply(_coerce_int)
    else:
        df["recurrence_count"] = 0
    df["recurrence_count"] = df["recurrence_count"].fillna(0).astype(int)
    df["root_cause_norm"] = root_cause_norm
    df["root_cause_recurrence"] = df["root_cause_norm"].map(root_cause_counts).fillna(1).astype(int)
    df["recurrence_count"] = (
        df[["recurrence_count", "root_cause_recurrence", "title_cluster_recurrence"]]
        .max(axis=1)
        .astype(int)
    )

    scanner_series = df.get("scanner_model")
    if scanner_series is None:
        for alt_col in ("scanner", "scanner_type", "scanner_sn"):
            if alt_col in df.columns:
                scanner_series = df.get(alt_col)
                if scanner_series is not None:
                    break
    if scanner_series is None:
        scanner_series = pd.Series(["" for _ in range(len(df))])
    scanner_norm = scanner_series.apply(_normalize_text_field)
    df["scanner_norm"] = scanner_norm
    scanner_labels: dict[str, str] = {}
    for original, normalized in zip(scanner_series.tolist(), scanner_norm.tolist()):
        if normalized and normalized not in scanner_labels and isinstance(original, str):
            scanner_labels[normalized] = original

    analysis_context = {
        "root_cause_labels": root_cause_labels,
        "scanner_labels": scanner_labels,
    }
    df["analysis_label"] = df.apply(
        _derive_analysis_label, axis=1, args=(analysis_context,)
    )

    analysis_counts = df["analysis_label"].value_counts()
    df["analysis_recurrence"] = (
        df["analysis_label"].map(analysis_counts).fillna(1).astype(int)
    )
    df["recurrence_count"] = (
        df[[
            "recurrence_count",
            "analysis_recurrence",
            "title_cluster_recurrence",
        ]]
        .max(axis=1)
        .astype(int)
    )

    now = pd.Timestamp.utcnow().tz_localize(None)
    recent_cutoff = now - pd.Timedelta(days=30)
    df["event_time"] = pd.to_datetime(df["event_time"], errors="coerce")
    recent_cases = df[df["event_time"] >= recent_cutoff]

    def _build_counts(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["analysis_label", "count"])
        counts = (
            frame.groupby("analysis_label")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        return counts

    overall_counts = _build_counts(df)
    recent_counts = _build_counts(recent_cases)

    highlight_case: dict[str, object] | None = None
    highlight_label = None
    highlight_count = 0
    if not overall_counts.empty:
        row = overall_counts.iloc[0]
        highlight_label = str(row["analysis_label"])
        highlight_count = int(row["count"])
        candidate = (
            df[df["analysis_label"] == highlight_label]
            .sort_values("event_time", ascending=False)
            .head(1)
        )
        if not candidate.empty:
            highlight_case = candidate.iloc[0].to_dict()

    bug_mask = df.apply(
        lambda row: _text_contains_bug(
            row.get("root_cause"),
            row.get("solution"),
            row.get("description_excerpt"),
            row.get("title"),
        ),
        axis=1,
    )
    bug_cases = df[bug_mask]
    bug_solution_mask = df.apply(
        lambda row: _text_contains_bug(row.get("solution"), row.get("root_cause")),
        axis=1,
    )

    recent_mask = df["event_time"] >= recent_cutoff
    bug_mentions_recent = int((bug_mask & recent_mask).sum())
    bug_solution_recent = int((bug_solution_mask & recent_mask).sum())

    def _build_timeline(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["timestamp", "count"])
        timeline = (
            frame.dropna(subset=["event_time"])
            .set_index("event_time")
            .resample("D")
            .size()
            .rename("count")
            .reset_index()
        )
        return timeline

    timeline_recent = _build_timeline(recent_cases)
    timeline_all = _build_timeline(df)

    recurring_issue_types = overall_counts[overall_counts["count"] >= 2]

    root_cause_summary = (
        df[df["root_cause_norm"] != ""]
        .groupby("root_cause_norm")
        .agg(count=("root_cause_norm", "size"))
        .reset_index()
        .sort_values("count", ascending=False)
    )
    if not root_cause_summary.empty:
        root_cause_summary["root_cause"] = root_cause_summary["root_cause_norm"].map(
            root_cause_labels
        )
        root_cause_summary = root_cause_summary[["root_cause", "count"]]

    scanner_summary = (
        df[df["scanner_norm"] != ""]
        .assign(scanner_display=lambda frame: frame["scanner_norm"].map(scanner_labels))
        .groupby(["scanner_norm", "scanner_display"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    if not scanner_summary.empty:
        scanner_summary.rename(
            columns={"scanner_display": "scanner"}, inplace=True
        )
        scanner_summary = scanner_summary[["scanner", "count"]]
    else:
        scanner_summary = pd.DataFrame(columns=["scanner", "count"])

    view_totals = {
        "all_time": {
            "case_total": int(len(df)),
            "bug_solution_count": int(bug_solution_mask.sum()),
            "bug_mentions_count": int(bug_mask.sum()),
            "unique_labels": int(overall_counts["analysis_label"].nunique()) if not overall_counts.empty else 0,
        },
        "30d": {
            "case_total": int(len(recent_cases)),
            "bug_solution_count": bug_solution_recent,
            "bug_mentions_count": bug_mentions_recent,
            "unique_labels": int(recent_counts["analysis_label"].nunique()) if not recent_counts.empty else 0,
        },
    }

    insights = {
        "recent_counts": recent_counts,
        "overall_counts": overall_counts,
        "counts": {"30d": recent_counts, "all_time": overall_counts},
        "timeline": timeline_recent,
        "timeline_all": timeline_all,
        "bug_cases": bug_cases,
        "bug_mentions_count": int(bug_mask.sum()),
        "bug_solution_count": int(bug_solution_mask.sum()),
        "bug_mentions_recent": bug_mentions_recent,
        "bug_solution_recent": bug_solution_recent,
        "highlight_case": highlight_case,
        "highlight_label": highlight_label,
        "highlight_count": highlight_count,
        "recent_total": int(len(recent_cases)),
        "case_total": int(len(df)),
        "view_totals": view_totals,
        "recurring_issue_types": recurring_issue_types,
        "common_root_causes": root_cause_summary,
        "common_scanner_models": scanner_summary,
    }

    return insights


def _build_frequency_chart(counts: pd.DataFrame, title: str) -> Drawing:
    _require_reportlab_charts()

    chart_data = counts.head(8).copy()
    if chart_data.empty:
        raise ValueError("No hay datos para el gráfico de recurrencia.")

    regular_font, bold_font = _ensure_pdf_fonts()

    labels = [
        _summarize_text(str(label), width=32)
        for label in chart_data["analysis_label"].astype(str).tolist()
    ]
    values = chart_data["count"].astype(int).tolist()
    max_value = max(values) if values else 0

    drawing_width, drawing_height = 500, 260
    chart = VerticalBarChart()
    chart.x = 60
    chart.y = 50
    chart.height = drawing_height - 110
    chart.width = drawing_width - 110
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.angle = 35
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.fontName = regular_font
    chart.categoryAxis.visibleTicks = False
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueStep = max(1, math.ceil(max_value / 4)) if max_value else 1
    chart.valueAxis.labelTextFormat = "%d"
    chart.valueAxis.labels.fontName = regular_font
    chart.barWidth = 18
    chart.bars[0].fillColor = colors.HexColor("#3478bc")
    chart.bars.strokeColor = colors.transparent

    drawing = Drawing(drawing_width, drawing_height)
    drawing.add(chart)
    drawing.add(
        String(
            drawing_width / 2,
            drawing_height - 20,
            title,
            fontName=bold_font,
            fontSize=12,
            textAnchor="middle",
            fillColor=colors.HexColor("#1f2937"),
        )
    )
    drawing.add(
        String(
            drawing_width / 2,
            15,
            "Casos",
            fontName=regular_font,
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#4b5563"),
        )
    )
    drawing.add(
        String(
            20,
            drawing_height / 2,
            "Frecuencia",
            fontName=regular_font,
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#4b5563"),
            angle=90,
        )
    )

    return drawing


def _build_timeline_chart(timeline: pd.DataFrame, title: str) -> Drawing:
    _require_reportlab_charts()

    if timeline.empty:
        raise ValueError("No hay datos para la tendencia temporal.")

    regular_font, bold_font = _ensure_pdf_fonts()

    timeline_sorted = timeline.sort_values("timestamp").reset_index(drop=True)
    if timeline_sorted.empty:
        raise ValueError("No hay datos ordenados para la tendencia temporal.")

    indices = list(range(len(timeline_sorted)))
    values = timeline_sorted["count"].astype(int).tolist()
    timestamps = [
        pd.to_datetime(ts).strftime("%b %d")
        for ts in timeline_sorted["timestamp"].tolist()
    ]
    label_map = {idx: label for idx, label in zip(indices, timestamps)}

    data_points = list(zip(indices, values))
    if not data_points:
        raise ValueError("No hay puntos para el gráfico de tendencia.")

    drawing_width, drawing_height = 500, 260
    chart = LinePlot()
    chart.x = 60
    chart.y = 50
    chart.height = drawing_height - 110
    chart.width = drawing_width - 110
    chart.data = [data_points]
    chart.lines[0].strokeColor = colors.HexColor("#2ca25f")
    chart.lines[0].strokeWidth = 2
    chart.lines[0].symbol = makeMarker("Circle")
    chart.lines[0].symbol.size = 6
    chart.lineLabelFormat = None

    if len(indices) == 1:
        min_x = indices[0] - 1
        max_x = indices[0] + 1
    else:
        min_x = indices[0]
        max_x = indices[-1]
    chart.xValueAxis.valueMin = min_x
    chart.xValueAxis.valueMax = max_x
    chart.xValueAxis.valueSteps = indices if len(indices) > 1 else indices + [indices[0] + 1]

    def _format_label(value: float, mapping: Mapping[int, str] = label_map) -> str:
        rounded = int(round(value))
        return mapping.get(rounded, "")

    chart.xValueAxis.labelTextFormat = _format_label
    chart.xValueAxis.labels.fontSize = 8
    chart.xValueAxis.labels.fontName = regular_font
    chart.yValueAxis.valueMin = 0
    max_value = max(values) if values else 0
    chart.yValueAxis.valueStep = max(1, math.ceil(max_value / 4)) if max_value else 1
    chart.yValueAxis.labelTextFormat = "%d"
    chart.yValueAxis.labels.fontName = regular_font

    drawing = Drawing(drawing_width, drawing_height)
    drawing.add(chart)
    drawing.add(
        String(
            drawing_width / 2,
            drawing_height - 20,
            title,
            fontName=bold_font,
            fontSize=12,
            textAnchor="middle",
            fillColor=colors.HexColor("#1f2937"),
        )
    )
    drawing.add(
        String(
            drawing_width / 2,
            15,
            "Fecha",
            fontName=regular_font,
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#4b5563"),
        )
    )
    drawing.add(
        String(
            20,
            drawing_height / 2,
            "Casos",
            fontName=regular_font,
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#4b5563"),
            angle=90,
        )
    )

    return drawing


def generate_ai_educate_report_pdf(
    insights: Mapping[str, object],
    bug_report: Mapping[str, object] | None = None,
) -> bytes:
    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    story: list = []
    title_style = styles["Title"]
    body_style = styles["BodyText"]
    heading_style = styles["Heading4"]
    ghost_snippets: list[str] = ["AI Educate – Informe de análisis"]

    story.append(Paragraph("AI Educate – Informe de análisis", title_style))
    story.append(Spacer(1, 16))

    view_totals = insights.get("view_totals") or {}
    totals_recent = view_totals.get("30d", {}) if isinstance(view_totals, Mapping) else {}
    totals_all = view_totals.get("all_time", {}) if isinstance(view_totals, Mapping) else {}

    summary_data = [
        ["Métrica", "30 días", "Historial"],
        [
            "Casos analizados",
            str(totals_recent.get("case_total", insights.get("recent_total", 0))),
            str(totals_all.get("case_total", insights.get("case_total", 0))),
        ],
        [
            "Tipos de caso únicos",
            str(totals_recent.get("unique_labels", 0)),
            str(totals_all.get("unique_labels", 0)),
        ],
        [
            "Soluciones marcadas como bug",
            str(totals_recent.get("bug_solution_count", insights.get("bug_solution_recent", 0))),
            str(totals_all.get("bug_solution_count", insights.get("bug_solution_count", 0))),
        ],
        [
            "Casos con mención de bug",
            str(totals_recent.get("bug_mentions_count", insights.get("bug_mentions_recent", 0))),
            str(totals_all.get("bug_mentions_count", insights.get("bug_mentions_count", 0))),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[220, 120, 120])
    for row in summary_data:
        ghost_snippets.extend(str(cell) for cell in row)
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 12))

    highlight_label = insights.get("highlight_label")
    if highlight_label:
        highlight_details = insights.get("highlight_case") or {}
        highlight_text = (
            f"Caso que requiere atención: {highlight_label}"
            f" (repetido {insights.get('highlight_count', 0)} veces)."
        )
        story.append(Paragraph(highlight_text, heading_style))
        ghost_snippets.append(highlight_text)
        if highlight_details:
            detail_lines = []
            for key in ["case_id", "title", "solution_excerpt"]:
                value = highlight_details.get(key)
                if value:
                    detail_lines.append(f"{key.replace('_', ' ').title()}: {value}")
            if detail_lines:
                story.append(Paragraph("<br/>".join(detail_lines), body_style))
                ghost_snippets.extend(detail_lines)
        story.append(Spacer(1, 12))

    counts_map_raw = insights.get("counts")
    counts_map = counts_map_raw if isinstance(counts_map_raw, Mapping) else {}
    chart_specs = [
        ("30d", "Casos más frecuentes (30 días)"),
        ("all_time", "Casos más frecuentes (historial)")
    ]
    for key, title in chart_specs:
        counts_df = counts_map.get(key) if isinstance(counts_map, Mapping) else None
        if isinstance(counts_df, pd.DataFrame) and not counts_df.empty:
            try:
                drawing = _build_frequency_chart(counts_df, title)
                story.append(drawing)
                story.append(Spacer(1, 12))
                ghost_snippets.append(title)
            except Exception:
                story.append(
                    Paragraph(
                        f"No se pudo renderizar el gráfico de frecuencia ({title}).",
                        body_style,
                    )
                )
                ghost_snippets.append(title)

    timeline_map = [
        (insights.get("timeline"), "Volumen diario (30 días)"),
        (insights.get("timeline_all"), "Volumen diario (historial)"),
    ]
    for timeline_df, title in timeline_map:
        if isinstance(timeline_df, pd.DataFrame) and not timeline_df.empty:
            try:
                drawing = _build_timeline_chart(timeline_df, title)
                story.append(drawing)
                story.append(Spacer(1, 12))
                ghost_snippets.append(title)
            except Exception:
                story.append(
                    Paragraph(
                        f"No se pudieron renderizar los gráficos de tendencia ({title}).",
                        body_style,
                    )
                )
                ghost_snippets.append(title)

    recurring_df = insights.get("recurring_issue_types")
    if isinstance(recurring_df, pd.DataFrame) and not recurring_df.empty:
        story.append(Paragraph("Patrones recurrentes", heading_style))
        ghost_snippets.append("Patrones recurrentes")
        rows = [["Caso", "Recurrencias"]]
        for _, row in recurring_df.head(10).iterrows():
            rows.append(
                [str(row.get("analysis_label", "")), str(row.get("count", 0))]
            )
        for row in rows:
            ghost_snippets.extend(str(cell) for cell in row)
        recurring_table = Table(rows, colWidths=[320, 120])
        recurring_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ]
            )
        )
        story.append(recurring_table)
        story.append(Spacer(1, 12))

    root_cause_df = insights.get("common_root_causes")
    if isinstance(root_cause_df, pd.DataFrame) and not root_cause_df.empty:
        story.append(Paragraph("Causas raíz más comunes", heading_style))
        ghost_snippets.append("Causas raíz más comunes")
        rows = [["Causa", "Casos"]]
        for _, row in root_cause_df.head(10).iterrows():
            rows.append(
                [str(row.get("root_cause", "")), str(row.get("count", 0))]
            )
        for row in rows:
            ghost_snippets.extend(str(cell) for cell in row)
        root_table = Table(rows, colWidths=[320, 120])
        root_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ]
            )
        )
        story.append(root_table)
        story.append(Spacer(1, 12))

    scanner_df = insights.get("common_scanner_models")
    if isinstance(scanner_df, pd.DataFrame) and not scanner_df.empty:
        story.append(Paragraph("Modelos de escáner reportados", heading_style))
        ghost_snippets.append("Modelos de escáner reportados")
        rows = [["Modelo", "Casos"]]
        for _, row in scanner_df.head(10).iterrows():
            rows.append([str(row.get("scanner", "")), str(row.get("count", 0))])
        for row in rows:
            ghost_snippets.extend(str(cell) for cell in row)
        scanner_table = Table(rows, colWidths=[320, 120])
        scanner_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ]
            )
        )
        story.append(scanner_table)
        story.append(Spacer(1, 12))

    bug_cases = insights.get("bug_cases")
    if isinstance(bug_cases, pd.DataFrame) and not bug_cases.empty:
        story.append(Paragraph("Casos relacionados con bugs", heading_style))
        ghost_snippets.append("Casos relacionados con bugs")
        rows = [["Case ID", "Título", "Guardado"]]
        for _, row in bug_cases.head(10).iterrows():
            saved_at = row.get("saved_at") or row.get("saved_at_dt")
            if isinstance(saved_at, pd.Timestamp):
                saved_at = saved_at.strftime("%Y-%m-%d")
            rows.append([
                str(row.get("case_id", "")),
                str(row.get("title", "")),
                str(saved_at or ""),
            ])
        for row in rows:
            ghost_snippets.extend(str(cell) for cell in row)
        bug_table = Table(rows, colWidths=[120, 260, 120])
        bug_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ]
            )
        )
        story.append(bug_table)
        story.append(Spacer(1, 12))

    if bug_report:
        story.append(Paragraph("Resultados de Bug Detector", heading_style))
        ghost_snippets.append("Resultados de Bug Detector")
        summary = bug_report.get("summary")
        if summary:
            story.append(Paragraph(summary, body_style))
            ghost_snippets.append(str(summary))
        recurring = bug_report.get("recurring_patterns") or []
        if recurring:
            rows = [["Patrón", "Recurrencias"]]
            for item in recurring[:10]:
                rows.append([str(item.get("pattern", "")), str(item.get("count", 0))])
            for row in rows:
                ghost_snippets.extend(str(cell) for cell in row)
            pattern_table = Table(rows, colWidths=[300, 120])
            pattern_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), bold_font),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ]
                )
            )
            story.append(pattern_table)
        story.append(Spacer(1, 12))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=30,
    )
    _build_pdf_with_ghost_text(doc, story, ghost_snippets)
    buffer.seek(0)
    return buffer.read()


def _collect_pattern_cases(
    pattern: str,
    dataset: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if not dataset:
        return []
    cases = dataset.get("cases", [])
    if not isinstance(cases, list):
        return []

    normalized: list[dict[str, object]] = []
    for entry in cases:
        if not isinstance(entry, Mapping):
            continue
        label = str(
            entry.get("root_cause")
            or entry.get("title")
            or entry.get("case_id")
            or ""
        ).strip()
        if not label:
            continue
        if label.lower() != pattern.lower():
            continue
        normalized.append(
            {
                "case_id": str(entry.get("case_id") or ""),
                "title": str(entry.get("title") or ""),
                "root_cause": str(entry.get("root_cause") or ""),
                "solution": str(entry.get("solution") or ""),
                "troubleshooting": (
                    extract_remote_steps_from_mapping(entry)
                    or str(entry.get("troubleshooting") or "").strip()
                ),
                "repro_steps": str(entry.get("repro_steps") or ""),
                "additional_info": str(
                    entry.get("additional_info")
                    or entry.get("description_excerpt")
                    or ""
                ),
                "saved_at": entry.get("saved_at"),
                "source_path": entry.get("source_path"),
            }
        )
    return normalized


def generate_recurring_issue_pdf(
    pattern_entry: Mapping[str, object],
    *,
    dataset: Mapping[str, object] | None = None,
) -> bytes:
    pattern = str(pattern_entry.get("pattern") or "Patrón recurrente")
    count = int(pattern_entry.get("count") or 0)
    raw_cases = pattern_entry.get("cases")

    normalized_cases: list[dict[str, object]] = []
    if isinstance(raw_cases, list):
        normalized_cases.extend(
            [
                {
                    "case_id": str(item.get("case_id") or ""),
                    "title": str(item.get("title") or ""),
                    "root_cause": str(item.get("root_cause") or ""),
                    "solution": str(item.get("solution") or ""),
                    "troubleshooting": (
                        extract_remote_steps_from_mapping(item)
                        or str(item.get("troubleshooting") or "").strip()
                    ),
                    "repro_steps": str(item.get("repro_steps") or ""),
                    "additional_info": str(
                        item.get("additional_info")
                        or item.get("description_excerpt")
                        or ""
                    ),
                    "saved_at": item.get("saved_at"),
                    "source_path": item.get("source_path"),
                }
                for item in raw_cases
                if isinstance(item, Mapping)
            ]
        )

    if not normalized_cases:
        normalized_cases = _collect_pattern_cases(pattern, dataset)

    if not normalized_cases:
        raise ValueError("No hay casos suficientes para generar la guía del patrón.")

    def _unique_text(values: Iterable[str]) -> str:
        seen: list[str] = []
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
        return "\n\n".join(seen)

    root_causes = _unique_text(case.get("root_cause", "") for case in normalized_cases)
    repro_text = _unique_text(case.get("repro_steps", "") for case in normalized_cases)
    troubleshooting_text = _unique_text(
        case.get("troubleshooting", "") for case in normalized_cases
    )
    solution_text = _unique_text(case.get("solution", "") for case in normalized_cases)
    notes_text = _unique_text(
        case.get("additional_info", "") for case in normalized_cases
    )

    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    body_style = styles["BodyText"]
    heading_style = styles["Heading3"]
    header_style = styles["Heading5"]
    ghost_snippets: list[str] = [
        pattern,
        str(count),
        root_causes,
        repro_text,
        troubleshooting_text,
        solution_text,
        notes_text,
    ]

    def _to_paragraph(text: str) -> Paragraph:
        content = text.strip()
        if not content:
            content = "—"
        else:
            content = escape(content).replace("\n", "<br/>")
        return Paragraph(content, body_style)

    guide_rows = [
        [Paragraph("Patrón", header_style), _to_paragraph(pattern)],
        [
            Paragraph("Casos detectados", header_style),
            _to_paragraph(str(count or len(normalized_cases))),
        ],
        [Paragraph("Causa raíz destacada", header_style), _to_paragraph(root_causes)],
        [Paragraph("Cómo reproducir", header_style), _to_paragraph(repro_text)],
        [
            Paragraph("Troubleshooting aplicado", header_style),
            _to_paragraph(troubleshooting_text),
        ],
        [
            Paragraph("Solución documentada", header_style),
            _to_paragraph(solution_text),
        ],
        [Paragraph("Notas adicionales", header_style), _to_paragraph(notes_text)],
    ]

    guide_table = Table(guide_rows, colWidths=[170, 330])
    guide_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ]
        )
    )

    detail_rows: list[list[Paragraph]] = [
        [
            Paragraph("Case ID", header_style),
            Paragraph("Título", header_style),
            Paragraph("Cómo reproducir", header_style),
            Paragraph("Troubleshooting", header_style),
            Paragraph("Solución", header_style),
        ]
    ]

    detail_rows.extend(
        [
            [
                _to_paragraph(case.get("case_id", "")),
                _to_paragraph(case.get("title", "")),
                _to_paragraph(case.get("repro_steps", "")),
                _to_paragraph(case.get("troubleshooting", "")),
                _to_paragraph(case.get("solution", "")),
            ]
            for case in normalized_cases
        ]
    )
    for case in normalized_cases:
        ghost_snippets.extend(
            str(case.get(key, ""))
            for key in ("case_id", "title", "repro_steps", "troubleshooting", "solution")
        )

    detail_table = Table(
        detail_rows,
        colWidths=[70, 120, 110, 110, 120],
        repeatRows=1,
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ]
        )
    )

    story: list = []
    story.append(Paragraph("Guía de patrón recurrente", heading_style))
    story.append(Spacer(1, 12))
    story.append(guide_table)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Casos analizados", heading_style))
    story.append(Spacer(1, 8))
    story.append(detail_table)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=30,
    )
    _build_pdf_with_ghost_text(doc, story, ghost_snippets)
    buffer.seek(0)
    return buffer.read()


def build_helpjuice_outline(
    case: CaseData | None,
    *,
    context: Mapping[str, object] | None = None,
    logs: str = "",
    user_notes: str = "",
    matches: Sequence[Mapping[str, object]] | None = None,
    manual_docs: Sequence[Mapping[str, object]] | None = None,
) -> str:
    """Assemble a Markdown Helpjuice guide based on incident context and history."""

    context = context or {}
    title_seed = "Helpjuice Guide"
    if case:
        for candidate in (case.brief_description, case.company_name, case.case_id):
            if candidate:
                title_seed = str(candidate)
                break
    elif context.get("section"):
        title_seed = str(context.get("section"))

    lines: list[str] = [f"# Helpjuice Guide – {title_seed}"]

    meta_bits: list[str] = []
    if case:
        if case.company_name:
            meta_bits.append(f"**Company:** {case.company_name}")
        if case.case_id:
            meta_bits.append(f"**Case ID:** {case.case_id}")
        if case.subscription_id:
            meta_bits.append(f"**Subscription:** {case.subscription_id}")
        if case.tracking and getattr(case.tracking, "priority", ""):
            meta_bits.append(f"**Priority:** {case.tracking.priority}")
    if context.get("tab"):
        meta_bits.append(f"**Detected in:** {context.get('tab')}")
    if context.get("timestamp"):
        meta_bits.append(f"**Captured:** {context.get('timestamp')}")
    if meta_bits:
        lines.append("## Case snapshot")
        lines.extend(f"- {bit}" for bit in meta_bits)

    if user_notes and user_notes.strip():
        lines.append("\n## Reporter notes")
        lines.append(user_notes.strip())

    steps: list[str] = []
    if case:
        if case.repro_steps:
            steps.append(f"Reproduce issue: {case.repro_steps.strip()}")
        remote_summary = format_remote_sessions_summary(
            case.remote_sessions, include_timestamps=False
        )
        if remote_summary:
            steps.append(f"Remote session recap: {remote_summary}")
        if case.solution:
            steps.append(f"Documented fix: {case.solution.strip()}")
        if case.root_cause:
            steps.append(f"Root cause notes: {case.root_cause.strip()}")

    top_matches: Sequence[Mapping[str, object]] = matches or []
    for match in list(top_matches)[:3]:
        if not isinstance(match, Mapping):
            continue
        case_id = str(match.get("case_id") or "Related case")
        label = str(
            match.get("root_cause")
            or match.get("title")
            or match.get("solution_excerpt")
            or case_id
        )
        solution = str(match.get("solution") or match.get("solution_excerpt") or "Review full case notes.")
        steps.append(f"Cross-reference {case_id}: {label} → {solution}")

    if steps:
        lines.append("\n## Step-by-step remediation")
        for idx, step in enumerate(steps, start=1):
            cleaned = " ".join(str(step).split())
            lines.append(f"{idx}. {cleaned}")

    keywords: set[str] = set()
    if case:
        keywords.update(
            _extract_keywords(
                case.brief_description,
                case.description,
                case.root_cause,
                case.solution,
                case.additional_info,
                case.tracking.ticket_number if case.tracking else "",
            )
        )
    keywords.update(_extract_keywords(user_notes, logs))

    doc_summaries: list[tuple[int, str, str]] = []
    for entry in manual_docs or []:
        if not isinstance(entry, Mapping):
            continue
        title = str(entry.get("title") or "")
        content = str(entry.get("content") or "")
        if not content:
            continue
        score = 0
        lowered = content.lower()
        for keyword in keywords:
            if keyword and keyword in lowered:
                score += 1
        if not score:
            continue
        snippet = _summarize_text(content, width=220)
        doc_summaries.append((score, title, snippet))

    if doc_summaries:
        lines.append("\n## Related knowledge base entries")
        for _, title, snippet in sorted(doc_summaries, reverse=True)[:3]:
            lines.append(f"- **{title}** — {snippet}")

    log_lines = [line.rstrip() for line in logs.splitlines() if line.strip()]
    if log_lines:
        lines.append("\n## Recent log highlights")
        lines.append("```text")
        lines.extend(log_lines[-10:])
        lines.append("```")

    return "\n".join(lines).strip()


def run_bug_detector(dataset: Mapping[str, object] | None) -> dict[str, object] | None:
    if not dataset:
        return None

    cases = dataset.get("cases", [])
    if not isinstance(cases, list) or not cases:
        return None

    df = pd.DataFrame(cases)
    if df.empty:
        return None

    df["analysis_label"] = df.get("root_cause").fillna("").replace("", None)
    df["analysis_label"] = df["analysis_label"].where(
        df["analysis_label"].notna(), df.get("title").fillna("")
    )
    df["analysis_label"] = df["analysis_label"].where(
        df["analysis_label"].astype(str).str.len() > 0,
        df.get("case_id").fillna("Unknown case"),
    )

    recurring_counts = (
        df.groupby("analysis_label")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    recurring_counts = recurring_counts[recurring_counts["count"] >= 2]

    pattern_details: list[dict[str, object]] = []
    for _, row in recurring_counts.iterrows():
        label = str(row.get("analysis_label") or "")
        if not label:
            continue
        group = df[df["analysis_label"] == label]
        case_records: list[dict[str, object]] = []
        case_ids: list[str] = []

        for _, case_row in group.iterrows():
            case_id = str(case_row.get("case_id") or "").strip()
            if case_id:
                case_ids.append(case_id)
            case_records.append(
                {
                    "case_id": case_id,
                    "title": str(case_row.get("title") or ""),
                    "root_cause": str(case_row.get("root_cause") or ""),
                    "solution": str(case_row.get("solution") or ""),
                    "troubleshooting": (
                        extract_remote_steps_from_mapping(case_row)
                        or str(case_row.get("troubleshooting") or "").strip()
                    ),
                    "repro_steps": str(case_row.get("repro_steps") or ""),
                    "additional_info": str(
                        case_row.get("additional_info")
                        or case_row.get("description_excerpt")
                        or ""
                    ),
                    "saved_at": case_row.get("saved_at"),
                    "source_path": case_row.get("source_path"),
                }
            )

        pattern_details.append(
            {
                "pattern": label,
                "count": int(row.get("count", 0) or 0),
                "case_ids": case_ids,
                "cases": case_records,
            }
        )

    bug_cases = df[
        df.apply(
            lambda row: _text_contains_bug(
                row.get("root_cause"),
                row.get("solution"),
                row.get("description_excerpt"),
            ),
            axis=1,
        )
    ]

    summary_parts = []
    if not recurring_counts.empty:
        top_pattern = recurring_counts.iloc[0]
        summary_parts.append(
            "Se detectaron patrones recurrentes, destacando "
            f"'{top_pattern['analysis_label']}' con {int(top_pattern['count'])} casos."
        )
    if not bug_cases.empty:
        summary_parts.append(
            f"Se identificaron {len(bug_cases)} casos con referencia directa a bugs."
        )
    if not summary_parts:
        summary_parts.append("No se detectaron comportamientos anómalos consistentes.")

    return {
        "generated_at": _utc_now_z(),
        "recurring_patterns": pattern_details,
        "bug_cases": bug_cases.to_dict("records"),
        "summary": " ".join(summary_parts),
    }


def save_case_to_database(
    case: CaseData,
    *,
    notify: bool = True,
    update_history: bool = True,
    touch_last_modified: bool = True,
) -> Path | None:
    if not case.case_id:
        if notify:
            st.error("Case ID is required to save.")
        return None
    if not isinstance(case.tracking, TrackingData):
        tracking_source = case.tracking
        tracking_payload: Mapping | None = None
        if isinstance(tracking_source, Mapping):
            tracking_payload = dict(tracking_source)
        elif hasattr(tracking_source, "__dict__"):
            tracking_payload = dict(vars(tracking_source))

        if tracking_payload:
            case.tracking = TrackingData(**tracking_payload)  # type: ignore[arg-type]
        else:
            case.tracking = TrackingData()
    case.tracking.priority = normalize_priority(case.tracking.priority)
    if not case.kiroshi_version:
        case.kiroshi_version = VERSION
    else:
        case.kiroshi_version = str(case.kiroshi_version)
    safe_case_id = sanitize_case_id(case.case_id)
    file_path = DATABASE_DIR / f"{safe_case_id}.json"
    last_modified_value = case.last_modified
    if (not last_modified_value) and file_path.exists():
        try:
            existing_payload = json.loads(file_path.read_text(encoding="utf-8"))
            existing_data = _coerce_case_mapping(existing_payload)
            if isinstance(existing_data, Mapping):
                last_modified_value = str(existing_data.get("last_modified") or "")
        except Exception:
            last_modified_value = ""
    if touch_last_modified or not last_modified_value:
        last_modified_value = _utc_now_z()
    case.last_modified = str(last_modified_value)
    case_payload = asdict(case)
    case_payload["attachments"] = persist_case_attachments(case.case_id)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(case_payload, f, indent=2)
    if update_history:
        update_recent_cases(case.case_id, str(file_path), case_data=case_payload)
    if notify:
        st.success(f"Case saved to {file_path}")
    st.session_state.ai_learning_signature = None
    st.session_state.ai_learning_data = None
    cleanup_case_autosaves(case.case_id)
    return file_path


def _apply_case_payload(
    payload: Mapping[str, object],
    attachments_data: Mapping[str, Iterable[Mapping[str, object]]] | Mapping[str, object] | None,
    *,
    source_path: str = "",
    record_recent: bool = False,
    update_tracking_from_path: bool = False,
    persist_to_database: bool = True,
) -> None:
    case_obj = CaseData(**payload)
    attachments_index = _normalise_attachments_index(attachments_data)
    uploads, log_uploads, screenshots = load_case_attachments(
        case_obj.case_id,
        attachments_index,
    )

    st.session_state.case = case_obj
    global D
    D = case_obj
    st.session_state.uploads = uploads
    st.session_state.log_uploads = log_uploads
    set_active_screenshots(screenshots)

    scratch_key = widget_state_key("scratch", CURRENT_CASE_IDX)
    scratch_default = st.session_state.get("scratch", "")
    if "case_sessions" in st.session_state and CURRENT_CASE_IDX < len(st.session_state.case_sessions):
        existing_session = st.session_state.case_sessions[CURRENT_CASE_IDX]
        scratch_value = st.session_state.get(
            scratch_key,
            getattr(existing_session, "scratch", scratch_default),
        )
    else:
        scratch_value = st.session_state.get(scratch_key, scratch_default)

    session_entry = CaseSession(
        case=case_obj,
        scratch=scratch_value,
        uploads=uploads,
        log_uploads=log_uploads,
        screenshots=screenshots,
        source_path=source_path,
        attachments_index=attachments_index,
    )

    if "case_sessions" in st.session_state and CURRENT_CASE_IDX < len(st.session_state.case_sessions):
        st.session_state.case_sessions[CURRENT_CASE_IDX] = session_entry
    else:
        st.session_state.case_sessions = [session_entry]

    _set_active_session_attachments_index(attachments_index)

    st.session_state.scratch = scratch_value
    st.session_state[scratch_key] = scratch_value

    autosave()
    if record_recent and source_path:
        update_recent_cases(
            case_obj.case_id, source_path, case_data=asdict(case_obj)
        )
    if persist_to_database:
        save_case_to_database(
            case_obj,
            notify=False,
            update_history=False,
            touch_last_modified=False,
        )
    ensure_tracking_session_defaults(CURRENT_CASE_IDX, case_obj.tracking, force=True)

    if update_tracking_from_path:
        path_obj = Path(source_path) if source_path else None
        if case_obj.tracking.active:
            st.session_state.track_case = True
        elif path_obj and (
            path_obj.parent == TRACKED_CASES_DIR or path_obj.name.endswith("_Active.json")
        ):
            st.session_state.track_case = True
        else:
            st.session_state.track_case = False
    else:
        st.session_state.track_case = bool(case_obj.tracking.active)

    _sync_case_memory_from_sessions()
    _refresh_hotkey_snapshot()


def load_case_from_path(path: str) -> None:
    try:
        with loading_indicator():
            raw_data = json.loads(Path(path).read_text(encoding="utf-8"))
            attachments_data: Mapping[str, Iterable[Mapping[str, object]]] | Mapping[str, object] | None = {}
            if isinstance(raw_data, Mapping):
                attachments_data = raw_data.get("attachments")
                filtered = {
                    k: v for k, v in raw_data.items() if k in CaseData.__annotations__
                }
            else:
                filtered = {}
            _apply_case_payload(
                filtered,
                attachments_data,
                source_path=path,
                record_recent=True,
                update_tracking_from_path=True,
            )
        st.success("Case loaded successfully.")
        trigger_hard_reload()
    except Exception as e:
        st.error(f"Failed to load case: {e}")


def load_case_from_bytes(data: bytes) -> None:
    try:
        with loading_indicator():
            payload = json.loads(data.decode("utf-8"))
            attachments_data: Mapping[str, Iterable[Mapping[str, object]]] | Mapping[str, object] | None = {}
            if isinstance(payload, Mapping):
                attachments_data = payload.get("attachments")
                filtered_payload = {
                    k: v for k, v in payload.items() if k in CaseData.__annotations__
                }
            else:
                filtered_payload = {}
            _apply_case_payload(
                filtered_payload,
                attachments_data,
                update_tracking_from_path=False,
            )
        st.success("Case loaded successfully.")
        trigger_hard_reload()
    except Exception as e:
        st.error(f"Failed to load case: {e}")


def has_unsaved_sections(case: CaseData) -> bool:
    header_fields = [
        "company_name",
        "subscription_id",
        "brief_description",
        "case_id",
        "application_version",
    ]
    phone_fields = ["phone_description"]
    remote_fields = ["remote_steps"]
    return any(getattr(case, f) for f in header_fields + phone_fields + remote_fields)


def _case_session_has_content(session: CaseSession) -> bool:
    """Return ``True`` when a case tab already contains meaningful data."""

    case = session.case
    if case.case_id and case.case_id.strip():
        return True
    if has_unsaved_sections(case):
        return True
    scratch = getattr(session, "scratch", "")
    if scratch and scratch.strip():
        return True
    if session.uploads or session.log_uploads or session.screenshots:
        return True
    if case.tracking.active:
        return True
    return False


def _allocate_case_tab_for_loading() -> int:
    """Return an available case tab index, creating one if required."""

    for idx, session in enumerate(st.session_state.case_sessions):
        if not _case_session_has_content(session):
            return idx
    st.session_state.case_sessions.append(CaseSession(case=CaseData()))
    _sync_case_memory_from_sessions()
    _refresh_hotkey_snapshot()
    return len(st.session_state.case_sessions) - 1


def _activate_case_index(idx: int) -> None:
    """Update globals so subsequent load operations target ``idx``."""

    global CURRENT_CASE_IDX
    CURRENT_CASE_IDX = idx


def request_load_from_path(path: str, *, prefer_new_tab: bool = False) -> None:
    if prefer_new_tab:
        target_idx = _allocate_case_tab_for_loading()
    else:
        target_idx = CURRENT_CASE_IDX
    session_case = st.session_state.case_sessions[target_idx].case
    if not prefer_new_tab and has_unsaved_sections(session_case):
        st.session_state.pending_load = {"path": path, "target_idx": target_idx}
    else:
        if prefer_new_tab:
            st.session_state.dashboard_load_notice = target_idx
        else:
            st.session_state.dashboard_load_notice = None
        _activate_case_index(target_idx)
        load_case_from_path(path)


def request_load_from_bytes(data: bytes, *, prefer_new_tab: bool = False) -> None:
    if prefer_new_tab:
        target_idx = _allocate_case_tab_for_loading()
    else:
        target_idx = CURRENT_CASE_IDX
    session_case = st.session_state.case_sessions[target_idx].case
    if not prefer_new_tab and has_unsaved_sections(session_case):
        st.session_state.pending_load = {"data": data, "target_idx": target_idx}
    else:
        if prefer_new_tab:
            st.session_state.dashboard_load_notice = target_idx
        else:
            st.session_state.dashboard_load_notice = None
        _activate_case_index(target_idx)
        load_case_from_bytes(data)


def request_case_dex(case_id: str) -> bytes:
    """Fetch a Case Dex package for the given case identifier.

    The download endpoint can be customized via the ``CASE_DEX_URL_TEMPLATE``
    environment variable. SSL verification is disabled to support
    corporate networks that intercept certificates.
    """

    url = CASE_DEX_URL_TEMPLATE.format(case_id=case_id)
    logging.info("Requesting Case Dex from %s", url)
    response = requests.get(url, verify=False, timeout=30)
    response.raise_for_status()
    return response.content


def touch_case_last_modified(
    *, timestamp: str | None = None, case: CaseData | None = None
) -> str:
    """Update the active (or specified) case ``last_modified`` timestamp and return it."""

    if timestamp is None:
        timestamp = _utc_now_z()

    target = case if case is not None else D

    if isinstance(target, CaseData):
        target.last_modified = timestamp

    # If no specific case was provided, ensure global state mirrors the update
    if case is None:
        case_obj = st.session_state.get("case")
        if isinstance(case_obj, CaseData) and case_obj is not target:
            case_obj.last_modified = timestamp

        st.session_state["last_modified"] = timestamp

    return timestamp


def _normalize_text_value(value: object) -> str:
    """Return a safe string representation for widget-bound text fields."""

    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("utf-8", "ignore")
    if isinstance(value, float) and math.isnan(value):  # type: ignore[arg-type]
        return ""
    return str(value)


def _seed_text_widget_state(
    field: str,
    state_key: str,
    *,
    state_labels: Mapping[bool, str] | None = None,
) -> tuple[str, bool]:
    """Ensure session state mirrors the dataclass value for a text widget."""

    marker_key = f"{state_key}__seed"
    field_value = getattr(D, field, "")
    if state_labels and isinstance(field_value, bool):
        field_value = state_labels.get(field_value, str(field_value))
    normalized_field = _normalize_text_value(field_value)

    session_has_value = state_key in st.session_state
    stored_marker = st.session_state.get(marker_key)

    if (not session_has_value) or stored_marker != normalized_field:
        st.session_state[state_key] = normalized_field
        st.session_state[marker_key] = normalized_field
        return normalized_field, True

    session_value = _normalize_text_value(st.session_state.get(state_key))
    if st.session_state.get(state_key) != session_value:
        st.session_state[state_key] = session_value
    st.session_state[marker_key] = normalized_field
    return session_value, False


def _commit_text_widget_state(field: str, state_key: str, fallback: object) -> str:
    """Persist the widget's session value back to the dataclass field."""

    marker_key = f"{state_key}__seed"
    session_value = _normalize_text_value(st.session_state.get(state_key, fallback))
    st.session_state[marker_key] = session_value

    previous_value = getattr(D, field, "")
    previous_normalized = _normalize_text_value(previous_value)
    if session_value != previous_normalized:
        setattr(D, field, session_value)
        st.session_state[field] = session_value

        sessions = st.session_state.get("case_sessions")
        if (
            isinstance(sessions, list)
            and 0 <= CURRENT_CASE_IDX < len(sessions)
            and isinstance(sessions[CURRENT_CASE_IDX], CaseSession)
        ):
            sessions[CURRENT_CASE_IDX].case = D

        st.session_state.case = D
        touch_case_last_modified()
        autosave()
    return session_value


def _text_widget_registry() -> dict[str, dict[str, int | str]]:
    """Return the persistent registry of text widget bindings."""

    registry = st.session_state.get("_text_widget_registry")
    if not isinstance(registry, dict):
        registry = {}
        st.session_state["_text_widget_registry"] = registry
    return registry


def _register_text_widget_binding(field: str, state_key: str, case_idx: int) -> None:
    """Record the relationship between a widget state key and case field."""

    registry = _text_widget_registry()
    registry[state_key] = {"field": field, "case_idx": case_idx}
    st.session_state["_text_widget_registry"] = registry


def _sync_case_text_state(case_idx: int) -> None:
    """Mirror session-state text widget values back into the case dataclass."""

    registry = st.session_state.get("_text_widget_registry")
    sessions = st.session_state.get("case_sessions")
    if not isinstance(registry, Mapping) or not isinstance(sessions, list):
        return

    if not (0 <= case_idx < len(sessions)):
        return

    session = sessions[case_idx]
    case = getattr(session, "case", None)
    if not isinstance(case, CaseData):
        return

    updated = False
    for state_key, binding in registry.items():
        if not isinstance(binding, Mapping):
            continue
        if binding.get("case_idx") != case_idx:
            continue
        field = binding.get("field")
        if not field or not hasattr(case, field):
            continue
        if state_key not in st.session_state:
            continue

        normalized = _normalize_text_value(st.session_state.get(state_key))
        if getattr(case, field, "") != normalized:
            setattr(case, field, normalized)
            marker_key = f"{state_key}__seed"
            st.session_state[marker_key] = normalized
            st.session_state[field] = normalized
            updated = True

    if not updated:
        return

    sessions[case_idx].case = case
    if case_idx == CURRENT_CASE_IDX:
        global D  # noqa: PLW0603 - keep global case reference aligned
        D = case
        st.session_state.case = case
        touch_case_last_modified()
        autosave()

def _update_field(
    field: str,
    state_key: str | None = None,
    *,
    persisted_key: str | None = None,
):
    """Update dataclass field from session state and persist.

    ``state_key`` allows callers that override the widget key to pass the
    concrete Streamlit session key associated with the widget. When omitted, the
    default widget key derived from the field name and current case index is
    used.
    """

    # ``persisted_key`` existed in a previous signature. Accept it as a keyword-only
    # argument for compatibility with any cached callbacks that may still pass it
    # positionally or by name, and normalize to ``state_key`` for the new logic.
    if state_key is None:
        state_key = persisted_key

    # Resolve target case from key if possible, falling back to global state
    target_idx = CURRENT_CASE_IDX
    if state_key is not None:
        # Standard widget keys are formatted as f"{field}_{idx}"
        prefix = f"{field}_"
        if state_key.startswith(prefix):
            try:
                suffix = state_key[len(prefix):]
                target_idx = int(suffix)
            except ValueError:
                pass

    try:
        case_obj = st.session_state.case_sessions[target_idx].case
    except (IndexError, AttributeError, TypeError):
        case_obj = D

    if state_key is None:
        state_key = widget_state_key(field, target_idx)

    new_value_raw = st.session_state.get(state_key)
    previous = getattr(case_obj, field, None)

    is_text_field = isinstance(previous, str) or isinstance(
        new_value_raw, (str, bytes, type(None))
    )

    if is_text_field:
        new_value = _normalize_text_value(new_value_raw)
        previous_normalized = _normalize_text_value(previous)

        st.session_state[f"{state_key}__seed"] = new_value

        if new_value != previous_normalized or not isinstance(previous, str):
            setattr(case_obj, field, new_value)

        if new_value != previous_normalized:
            touch_case_last_modified(case=case_obj)
            autosave(case=case_obj)
        return

    # Non-text widgets (e.g., toggles) should preserve their native value types.
    st.session_state[f"{state_key}__seed"] = new_value_raw

    if new_value_raw != previous:
        setattr(case_obj, field, new_value_raw)
        touch_case_last_modified(case=case_obj)
        autosave(case=case_obj)


def auto_text_input(
    label: str,
    field: str,
    container=st,
    *,
    state_labels: Mapping[bool, str] | None = None,
    **kwargs,
):
    """Render a text input bound to a CaseData field with autosave semantics."""

    widget_identifier = widget_key(field, CURRENT_CASE_IDX)
    text_kwargs = dict(kwargs)
    state_key = text_kwargs.get("key") or widget_identifier
    text_kwargs["key"] = state_key
    text_kwargs["on_change"] = _update_field
    text_kwargs["args"] = (field, state_key)

    _register_text_widget_binding(field, state_key, CURRENT_CASE_IDX)

    current_value, seeded = _seed_text_widget_state(
        field, state_key, state_labels=state_labels
    )
    if seeded and "value" not in text_kwargs:
        text_kwargs["value"] = current_value

    widget_value = container.text_input(label, **text_kwargs)
    return _commit_text_widget_state(field, state_key, widget_value)


def auto_tracking_text_input(label: str, field: str, container=st, **kwargs) -> str:
    """Render a tracking text input that keeps CaseData.tracking in sync."""

    widget_identifier = widget_key(f"tracking_{field}", CURRENT_CASE_IDX)
    text_kwargs = dict(kwargs)
    state_key = text_kwargs.get("key") or widget_identifier
    text_kwargs["key"] = state_key

    tracking = getattr(D, "tracking", None)
    current_value = ""
    if isinstance(tracking, TrackingData):
        current_value = _normalize_text_value(getattr(tracking, field, ""))

    if state_key not in st.session_state:
        st.session_state[state_key] = current_value

    widget_value = container.text_input(label, **text_kwargs)
    normalized_value = _normalize_text_value(widget_value)
    if normalized_value != current_value and isinstance(tracking, TrackingData):
        setattr(tracking, field, normalized_value)
        touch_case_last_modified()
        autosave()
    return normalized_value


def auto_text_area(label: str, field: str, container=st, **kwargs):
    """Render a text area bound to a CaseData field with autosave semantics."""

    widget_identifier = widget_key(field, CURRENT_CASE_IDX)
    area_kwargs = dict(kwargs)
    state_key = area_kwargs.get("key") or widget_identifier
    area_kwargs["key"] = state_key
    area_kwargs["on_change"] = _update_field
    area_kwargs["args"] = (field, state_key)

    _register_text_widget_binding(field, state_key, CURRENT_CASE_IDX)

    current_value, seeded = _seed_text_widget_state(field, state_key)
    if seeded and "value" not in area_kwargs:
        area_kwargs["value"] = current_value

    widget_value = container.text_area(label, **area_kwargs)
    return _commit_text_widget_state(field, state_key, widget_value)


def auto_number_input(label: str, field: str, container=st, **kwargs):
    key = widget_key(field, CURRENT_CASE_IDX)
    kwargs.setdefault("key", key)
    kwargs.setdefault("min_value", 0)
    kwargs.setdefault("step", 1)
    current = getattr(D, field)
    try:
        current_value = int(current)
    except (TypeError, ValueError):
        current_value = 0
    value = container.number_input(label, value=current_value, **kwargs)
    int_value = int(value)
    if int_value != current_value:
        setattr(D, field, int_value)
        st.session_state[key] = int_value
        touch_case_last_modified()
        autosave()


def auto_toggle(
    label: str,
    field: str,
    container=st,
    *,
    state_labels: Mapping[bool, str] | None = None,
    **kwargs,
):
    key = widget_key(field, CURRENT_CASE_IDX)
    kwargs.setdefault("key", key)
    default_value = bool(getattr(D, field))
    alias_key = f"{field}_on"
    stored_value = st.session_state.get(key)
    if stored_value is None:
        stored_value = st.session_state.get(alias_key, default_value)

    state_value = bool(stored_value)
    if alias_key not in st.session_state:
        st.session_state[alias_key] = state_value

    label_text = label
    if state_labels:
        on_label = state_labels.get(True)
        off_label = state_labels.get(False)
        if on_label is None or off_label is None:
            raise ValueError("state_labels must define both True and False labels")
        normalized_label = label.rstrip("?").strip()
        prefix = normalized_label or label
        label_text = f"{prefix}: {on_label if state_value else off_label}"

    try:
        value = container.toggle(label_text, value=state_value, **kwargs)
    except StreamlitAPIException as exc:
        match = re.search(
            r"st\\.session_state\\.([^.\\s]+) does not exist", str(exc)
        )
        if match:
            missing_key = match.group(1)
            if missing_key not in st.session_state:
                st.session_state[missing_key] = state_value
            value = container.toggle(label_text, value=state_value, **kwargs)
        else:
            raise

    previous_value = getattr(D, field)
    st.session_state[alias_key] = bool(value)
    if value != previous_value:
        setattr(D, field, value)
        touch_case_last_modified()
        autosave()
    else:
        setattr(D, field, value)


def _inject_case_tab_theme() -> None:
    """Lazy‑load the visual theme used by the Case tab."""

    if st.session_state.get("_case_tab_theme_injected"):
        return
    st.session_state["_case_tab_theme_injected"] = True
    st.markdown(
        """
        <style>
            .case-tab-shell {
                background: linear-gradient(
                    135deg,
                    color-mix(in srgb, var(--kiroshi-primary) 16%, #ffffff 84%),
                    color-mix(in srgb, var(--kiroshi-accent) 18%, #ffffff 82%)
                );
                border-radius: 24px;
                padding: 2.5rem clamp(1rem, 4vw, 2.75rem);
                margin-bottom: 2rem;
                box-shadow: 0 28px 58px -26px rgba(15, 23, 42, 0.35);
                position: relative;
                overflow: hidden;
                animation: kiroshiSoftDrift 20s ease-in-out infinite;
            }
            .case-tab-shell::after {
                content: "";
                position: absolute;
                inset: -42% -30% auto auto;
                width: min(360px, 62vw);
                aspect-ratio: 1;
                background: radial-gradient(circle at 35% 30%, rgba(99, 102, 241, 0.28), transparent 60%);
                transform: rotate(18deg);
                pointer-events: none;
                filter: blur(0.5px);
            }
            .case-card {
                background: rgba(255, 255, 255, 0.9);
                backdrop-filter: blur(18px) saturate(120%);
                border-radius: 20px;
                padding: 1.6rem 1.85rem;
                margin-bottom: 1.35rem;
                box-shadow: 0 22px 48px -24px rgba(15, 23, 42, 0.35);
                border: 1px solid rgba(148, 163, 184, 0.28);
                transition: transform 240ms ease, box-shadow 240ms ease, border-color 240ms ease;
            }
            .case-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 24px 56px -20px rgba(15, 23, 42, 0.34);
                border-color: color-mix(in srgb, var(--kiroshi-primary) 24%, rgba(148, 163, 184, 0.18));
            }
            .case-card h3, .case-card h4 {
                margin-top: 0;
                margin-bottom: 0.75rem;
                font-weight: 700;
                letter-spacing: -0.01em;
            }
            .case-hero {
                position: relative;
                z-index: 1;
                display: grid;
                gap: clamp(1.6rem, 3vw, 2.4rem);
                grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                align-items: center;
                margin-bottom: 1.8rem;
                padding: 1.9rem clamp(1.4rem, 3vw, 2.4rem);
                border-radius: 26px;
                background: linear-gradient(
                    120deg,
                    color-mix(in srgb, var(--kiroshi-primary) 10%, rgba(255, 255, 255, 0.95)),
                    color-mix(in srgb, var(--kiroshi-accent) 12%, rgba(255, 255, 255, 0.9))
                );
                box-shadow: 0 26px 48px -26px rgba(15, 23, 42, 0.35);
                overflow: hidden;
                animation: kiroshiFadeIn 0.8s ease-out both;
            }
            .case-hero::before {
                content: "";
                position: absolute;
                inset: -30% auto auto -25%;
                width: min(320px, 58vw);
                aspect-ratio: 1;
                background: radial-gradient(circle at center, rgba(255, 255, 255, 0.55), transparent 65%);
                pointer-events: none;
                opacity: 0.7;
                animation: kiroshiSoftDrift 18s ease-in-out infinite reverse;
            }
            .case-hero__eyebrow {
                display: inline-block;
                padding: 0.38rem 0.9rem;
                border-radius: 999px;
                font-size: 0.8rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-weight: 600;
                background: color-mix(in srgb, var(--kiroshi-primary) 18%, rgba(255, 255, 255, 0.92));
                color: var(--kiroshi-primary);
                margin-bottom: 0.75rem;
                box-shadow: 0 6px 14px rgba(79, 70, 229, 0.18);
            }
            .case-hero__title {
                font-size: clamp(1.65rem, 4vw, 2.4rem);
                margin: 0 0 0.5rem;
                font-weight: 700;
            }
            .case-hero__subtitle {
                margin: 0 0 1rem;
                color: rgba(15, 23, 42, 0.72);
                font-size: 1.05rem;
            }
            .case-hero__badges {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
            }
            .case-hero__badge {
                padding: 0.45rem 0.95rem;
                border-radius: 999px;
                background: color-mix(in srgb, var(--kiroshi-accent) 22%, rgba(255, 255, 255, 0.85));
                font-size: 0.9rem;
                font-weight: 600;
                color: color-mix(in srgb, var(--kiroshi-primary) 40%, #111827 60%);
                backdrop-filter: blur(10px);
                box-shadow: 0 10px 20px rgba(15, 23, 42, 0.12);
                transition: transform 200ms ease;
            }
            .case-hero__badge:hover {
                transform: translateY(-3px);
            }
            .case-hero__progress {
                background: rgba(255, 255, 255, 0.92);
                color: var(--kiroshi-primary);
                border-radius: 22px;
                padding: 1.6rem 1.9rem;
                box-shadow: 0 18px 40px -22px rgba(15, 23, 42, 0.3);
                border: 1px solid rgba(148, 163, 184, 0.25);
            }
            .case-hero__progress-label {
                font-size: 0.95rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.75rem;
                color: color-mix(in srgb, var(--kiroshi-primary) 55%, #1f2937 45%);
            }
            .case-hero__progress-track {
                background: rgba(15, 23, 42, 0.08);
                height: 12px;
                border-radius: 999px;
                overflow: hidden;
                margin-bottom: 0.75rem;
            }
            .case-hero__progress-fill {
                height: 100%;
                background: linear-gradient(90deg, var(--kiroshi-primary) 0%, var(--kiroshi-accent) 100%);
                animation: progressPulse 6s ease-in-out infinite;
            }
            .case-hero__progress-value {
                font-size: 2rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
                color: color-mix(in srgb, var(--kiroshi-primary) 70%, #111827 30%);
            }
            .case-hero__progress-meta {
                font-size: 0.9rem;
                color: rgba(15, 23, 42, 0.65);
            }
            .case-milestones {
                display: flex;
                flex-wrap: wrap;
                gap: 0.75rem;
                margin-top: 1rem;
            }
            .case-milestones__item {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.65rem 0.9rem;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(148, 163, 184, 0.3);
                font-weight: 600;
                color: #1f2937;
            }
            .case-milestones__item--done {
                background: rgba(34, 197, 94, 0.12);
                border-color: rgba(34, 197, 94, 0.45);
                color: #15803d;
            }
            .case-milestones__item--alert {
                background: rgba(248, 113, 113, 0.15);
                border-color: rgba(239, 68, 68, 0.45);
                color: #991b1b;
            }
            .case-milestones__icon {
                font-size: 1.25rem;
            }
            @keyframes progressPulse {
                0% { filter: drop-shadow(0 0 0 rgba(255, 255, 255, 0.0)); }
                50% { filter: drop-shadow(0 0 8px rgba(255, 255, 255, 0.55)); }
                100% { filter: drop-shadow(0 0 0 rgba(255, 255, 255, 0.0)); }
            }
            @media (max-width: 768px) {
                .case-tab-shell {
                    padding: 2rem 1rem;
                }
                .case-card {
                    padding: 1.25rem 1.35rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def case_tab_shell(container):
    _inject_case_tab_theme()
    container.markdown('<div class="case-tab-shell">', unsafe_allow_html=True)
    shell = container.container()
    try:
        yield shell
    finally:
        container.markdown("</div>", unsafe_allow_html=True)


@contextmanager
def case_tab_card(container, card_class: str, compact_mode: bool):
    if compact_mode:
        yield container
        return

    classes = f"case-card {card_class}".strip()
    container.markdown(f'<div class="{classes}">', unsafe_allow_html=True)
    card = container.container()
    try:
        yield card
    finally:
        container.markdown("</div>", unsafe_allow_html=True)

# ────────── HELPERS ──────────

def build_title(d: CaseData) -> str:
    """Construct a helper string for case titles."""
    base = (
        f"|{d.company_name}|{d.subscription_id}|{d.brief_description}|"
        f"{d.application_version}|{d.case_id}|"
    )
    if st.session_state.get("second_line_mode") and d.straumann not in ("", "N/A"):
        return f"|{d.straumann}{base}"
    return base


def compute_progress(d: CaseData, cat_map):
    """Compute completion progress for each category."""
    prog, miss = {}, {}
    for cat, flds in cat_map.items():
        if cat in OPTIONAL_PROGRESS_CATEGORIES:
            continue
        vals = [getattr(d, f) for f in flds]
        done = sum(bool(v) for v in vals)
        prog[cat] = int(done / len(flds) * 100)
        miss[cat] = [f for f, v in zip(flds, vals) if not v]
    return prog, miss


def build_email_intro(d: CaseData) -> str:
    """Standard opening for customer emails.

    Includes the contact name, company, brief description of the issue and the
    case number so every e‑mail automatically contains the required recap
    information for EC.
    """
    caller = d.caller_name or "Customer"
    company = f" from {d.company_name}" if d.company_name else ""
    brief = d.brief_description or "the reported issue"
    case_no = d.case_id or "your case"
    return (
        f"Dear {caller}{company},\n\n"
        f"I hope this email finds you well. I wanted to recap your recent call to our customer service center regarding the case you had about {brief}.\n"
        f"This was registered under the ticket {case_no}.\n"
    )


def _derive_recap_recommendation(case: CaseData) -> str:
    """Suggest a simple customer-facing recommendation for recap emails."""

    def _has_any(text: str, needles: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return any(needle in lowered for needle in needles)

    if case.internal_helpjuice.strip():
        return (
            "Review this Helpjuice guide and follow its steps: "
            f"{case.internal_helpjuice.strip()}"
        )

    combined_notes = " ".join(
        filter(
            None,
            [
                case.additional_info,
                case.description,
                case.brief_description,
                case.root_cause,
                case.solution,
            ],
        )
    )

    if _has_any(combined_notes, ("thermal", "overheat", "fan", "hot")):
        return "Place the laptop on a cooling pad and keep vents clear to avoid overheating."
    if _has_any(combined_notes, ("scanner", "scan")):
        return "Clean the scanner tip, run a quick calibration, and retry the scan."
    if _has_any(combined_notes, ("update", "patch", "windows")):
        return "Run Windows Update, install pending patches, and restart the computer."
    if _has_any(combined_notes, ("network", "wi-fi", "wifi", "internet")):
        return "Restart the router and reconnect the PC to a stable wired or Wi‑Fi network."

    return "Restart the computer daily and keep Windows updates installed for best performance."


def build_case_data_block(d: CaseData) -> str:
    """Return a newline separated list with every tracked case field."""

    rows = []
    for f in fields(CaseData):
        value = getattr(d, f.name)
        label = f.name.replace("_", " ").title()
        if isinstance(value, bool):
            display = "Yes" if value else "No"
            rows.append(f"{label}: {display}")
            continue
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                rows.append(f"{label}: N/A")
                continue
            if "\n" in cleaned:
                formatted = "\n    ".join(cleaned.splitlines())
                rows.append(f"{label}:\n    {formatted}")
            else:
                rows.append(f"{label}: {cleaned}")
            continue
        if value is None:
            rows.append(f"{label}: N/A")
        else:
            rows.append(f"{label}: {value}")
    return "\n".join(rows)


def build_third_line_escalation(d: CaseData) -> str:
    """Generate a third line escalation template using case data."""
    date_str = datetime.now().strftime("%Y %m %d")
    
    def first_non_empty(*values: str) -> str:
        for value in values:
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    return cleaned
        return ""

    def section_value(placeholder: str, *values: str) -> str:
        chosen = first_non_empty(*values)
        return chosen if chosen else placeholder

    def contact_line(label: str, placeholder_detail: str, *values: str) -> str:
        chosen = first_non_empty(*values)
        if chosen:
            return f"{label}: {chosen}"
        return f"{label}: {placeholder_detail}"

    return f"""3Q({date_str})

Hello, Advanced support team,

We need your assistance in this case:

{section_value("Add a brief description of the issue.", d.brief_description)}

HJ article or possible root cause found

{section_value("Add Helpjuice article link or suspected root cause.", d.third_line_hj_article, d.root_cause)}

How to reproduce it:

{section_value("Provide detailed reproduction steps.", d.repro_steps)}

Troubleshoot summary:

{section_value("Summarize all troubleshooting performed.", d.third_line_troubleshoot_summary, d.remote_steps)}

For more specific information, check the TV session.

Comments:

{section_value("Add any additional comments for the advanced team.", d.third_line_comments, d.additional_info)}

Contact information:
{contact_line("Reseller Name", "[Add reseller name]", d.third_line_reseller_name)}
{contact_line("Reseller Phone Number", "[Add primary reseller phone]", d.third_line_reseller_phone)}
{contact_line("Reseller Phone Number 2", "[Add alternate reseller phone]", d.third_line_reseller_phone_alt)}
{contact_line("Reseller email", "[Add reseller email address]", d.third_line_reseller_email)}
{contact_line("Clinic rep name", "[Add clinic representative name]", d.third_line_clinic_rep_name)}
{contact_line("Clinic rep phone number", "[Add clinic representative phone]", d.third_line_clinic_rep_phone)}
{contact_line("Clinic rep phone number 2", "[Add alternate clinic representative phone]", d.third_line_clinic_rep_phone_alt)}
{contact_line("TV ID", "[Add TeamViewer ID]", d.third_line_tv_id, d.teamviewer_id)}
{contact_line("TV Customer Pass", "[Add TeamViewer password]", d.third_line_tv_password, d.teamviewer_password)}
{contact_line("Unite pin", "[Add Unite PIN]", d.third_line_unite_pin, d.subscription_id)}

Find all screenshots and logs on the internal note.

Finally, you can remind the person to add on an attached notepad or over Teams the 3Shape account credentials and the computer password.
"""


def _normalize_value_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the Value column is Arrow-friendly while preserving text entries."""

    if "Value" not in df.columns:
        return df

    df = df.copy()
    original = df["Value"].copy()
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce").fillna("").astype(str)
    numeric = pd.to_numeric(original, errors="coerce")
    numeric_mask = numeric.notna()
    if numeric_mask.any():
        df.loc[numeric_mask, "Value"] = numeric.loc[numeric_mask].map(lambda v: f"{v:g}")
    empty_mask = df["Value"] == ""
    if empty_mask.any():
        df.loc[empty_mask, "Value"] = original.loc[empty_mask].fillna("").astype(str)
    return df


@st.cache_data
def category_dataframe(
    cat: str, d: CaseData, cat_map: Mapping[str, Iterable[str]] | None
) -> pd.DataFrame:
    """Return a DataFrame with human readable field names for a category."""
    rows = []
    label_overrides = dict(DELL_ESCALATION_FIELD_LABELS)
    for fld in (cat_map or {}).get(cat, []):
        value = getattr(d, fld, "N/A")
        label = fld.replace("_", " ").title()
        if cat == "DELL ESCALATION":
            label = label_overrides.get(fld, label)
        if fld == "scanner_accidental_damage":
            label = "Damage Classification"
            raw = getattr(d, fld, "")
            value = _normalize_damage_classification(raw)
            if not value:
                value = "Not specified"
        elif isinstance(value, bool):
            value = "Yes" if value else "No"
        rows.append({"Field": label, "Value": value})
    return _normalize_value_column(pd.DataFrame(rows))


def table_title(cat: str) -> str:
    """Return a formatted table title with type and current date."""
    label = "Phonecall" if cat == "PHONECALL" else "Int"
    return f"{cat} ({label}){TODAY_STR}"


def table_plain_text(cat: str, d: CaseData, cat_map) -> str:
    """Return a newline formatted view of a category table."""

    lines = [table_title(cat)]
    label_overrides = dict(DELL_ESCALATION_FIELD_LABELS)
    for fld in (cat_map or {}).get(cat, []):
        raw_value = getattr(d, fld, "")
        if isinstance(raw_value, bool):
            display = "Yes" if raw_value else "No"
        else:
            display = str(raw_value or "N/A").strip()
            if not display:
                display = "N/A"
        if "\n" in display:
            display = "\n    ".join(display.splitlines())
        label = fld.replace("_", " ").title()
        if cat == "DELL ESCALATION":
            label = label_overrides.get(fld, label)
        lines.append(f"{label}: {display}")

    # Explicitly append Application and version to DESCRIPTION table if not present
    if cat == "DESCRIPTION":
        app_ver = str(d.application_version or "N/A").strip() or "N/A"
        if "\n" in app_ver:
            app_ver = "\n    ".join(app_ver.splitlines())
        lines.append(f"Application and version: {app_ver}")

    return "\n".join(lines)


def _format_display_value(value: object) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return "N/A"
    text = str(value).strip()
    return text if text else "N/A"


def _format_multiline(value: str) -> str:
    cleaned = value.replace("\r\n", "\n").replace("\r", "\n")
    if "\n" in cleaned:
        return "\n  ".join(cleaned.splitlines())
    return cleaned


def dell_escalation_rows(d: CaseData) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for field, label in DELL_ESCALATION_FIELD_LABELS:
        raw_value = getattr(d, field, "")
        display = _format_display_value(raw_value)
        rows.append({"Field": label, "Value": display})
    return rows


def dell_escalation_dataframe(d: CaseData) -> pd.DataFrame:
    return _normalize_value_column(pd.DataFrame(dell_escalation_rows(d)))


def dell_escalation_plain_text(d: CaseData) -> str:
    lines = ["Dell Escalation"]
    for field, label in DELL_ESCALATION_FIELD_LABELS:
        raw_value = getattr(d, field, "")
        display = _format_multiline(_format_display_value(raw_value))
        lines.append(f"{label}: {display}")
    return "\n".join(lines)


def script_safe_json(value: str) -> str:
    """Return a JSON string literal safe for embedding inside <script> tags."""

    return json.dumps(value).replace("</", "<\\/")


def _slugify_hotkey(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _autohotkey_escape(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace('"', '""')
    return cleaned.replace("\n", "`n")


def build_autohotkey_script(cases: Iterable[CaseData], cat_map) -> str:
    """Generate an AutoHotkey script with hotstrings for each case table."""

    header = textwrap.dedent(
        """\
        ; AutoHotkey script generated by Kiroshi.
        ; Type the trigger (e.g., phonecall1) in any application to paste the table contents.
        #NoEnv
        #SingleInstance Force
        SendMode Input
        SetWorkingDir %A_ScriptDir%
        """
    ).strip()
    chunks: list[str] = [header]
    for idx, case in enumerate(cases, start=1):
        case_label = case.case_id or case.brief_description or f"Case {idx}"
        chunks.append(f"; Case {idx}: {case_label}")
        for cat in cat_map:
            trigger = _slugify_hotkey(cat)
            if not trigger:
                continue
            trigger_name = f"{trigger}{idx}"
            table_text = table_plain_text(cat, case, cat_map)
            escaped = _autohotkey_escape(table_text)
            chunks.append(
                textwrap.dedent(
                    f"""\
                    ::{trigger_name}::
                        Clipboard := "{escaped}"
                        ClipWait, 0.25
                        Send ^v
                    Return
                    """
                ).strip()
            )
        chunks.append("")
    script = "\n".join(chunks).rstrip()
    return script + "\n"


def sync_autohotkey_script(script: str) -> Path | None:
    """Persist the latest AutoHotkey hotstrings so AutoHotkey can include them live.

    Returns the path if the script could be written, otherwise ``None``.
    """

    if os.name != "nt":
        return None
    try:
        AUTOHOTKEY_SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            existing = AUTOHOTKEY_SCRIPT_PATH.read_text(encoding="utf-8")
        except OSError:
            existing = None
        if existing != script:
            AUTOHOTKEY_SCRIPT_PATH.write_text(script, encoding="utf-8")
        return AUTOHOTKEY_SCRIPT_PATH
    except OSError as exc:
        logging.warning("Failed to sync AutoHotkey script to %s: %s", AUTOHOTKEY_SCRIPT_PATH, exc)
        return None


def render_case_milestone_tracker(container, case_idx: int, *, compact_mode: bool) -> None:
    sessions = st.session_state.get("case_sessions")
    if not isinstance(sessions, list) or not (0 <= case_idx < len(sessions)):
        return
    session = sessions[case_idx]
    state = _ensure_case_milestone_state(session)
    now = datetime.now(timezone.utc)
    anchor_created_at = _parse_utc_timestamp(
        st.session_state.get("milestone_anchor_created_at")
    )
    created_at = anchor_created_at or _parse_utc_timestamp(state.created_at) or now
    items_html: list[str] = []
    for milestone_id in MILESTONE_ID_ORDER:
        milestone_def = MILESTONE_DEFINITION_LOOKUP.get(milestone_id, {})
        progress = state.statuses.get(milestone_id)
        if progress is None:
            progress = MilestoneProgressState()
            state.statuses[milestone_id] = progress
        completed = bool(progress.completed_at)
        due: timedelta | None = milestone_def.get("due")
        overdue = bool(
            due and not completed and (now - created_at) >= due
        )
        icon = "✅" if completed else "❌"
        css_class = "case-milestones__item"
        if completed:
            css_class += " case-milestones__item--done"
        elif overdue:
            css_class += " case-milestones__item--alert"
        description = milestone_def.get("description", "")
        label = milestone_def.get("label", milestone_id.title())
        items_html.append(
            (
                f'<div class="{css_class}" title="{escape(description)}">'
                f'<span class="case-milestones__icon">{icon}</span>'
                f"<span>{escape(label)}</span>"
                "</div>"
            )
        )

    if not items_html:
        return

    container.markdown(
        "<div class='case-milestones'>" + "".join(items_html) + "</div>",
        unsafe_allow_html=True,
    )

    resolution_progress = state.statuses.get("resolution")
    completed_resolution = bool(resolution_progress and resolution_progress.completed_at)
    action_cols = container.columns(2)
    resolve_key = case_widget_key("milestones", "resolve", case_idx=case_idx)
    replacement_key = case_widget_key("milestones", "replacement", case_idx=case_idx)
    if action_cols[0].button(
        "Resolve & Close",
        key=resolve_key,
        disabled=completed_resolution,
    ):
        _handle_resolution_action(case_idx)
    if action_cols[1].button(
        "Replacement",
        key=replacement_key,
        disabled=completed_resolution,
    ):
        _handle_resolution_action(case_idx, replacement=True)


def render_case_header_section(container, case_idx: int, compact_mode: bool) -> None:
    if not compact_mode:
        cat_map = active_category_map()
        prog, miss = compute_progress(D, cat_map)
        progress_values = list(prog.values())
        progress_pct = (
            int(sum(progress_values) / len(progress_values)) if progress_values else 0
        )
        progress_pct = max(0, min(100, progress_pct))
        outstanding = sum(len(v) for v in miss.values())
        outstanding_text = (
            "All mandatory fields complete"
            if outstanding == 0
            else f"{outstanding} field{'s' if outstanding != 1 else ''} remaining"
        )
        status_text = (D.tracking.status or "").strip()
        last_mod_raw = (D.last_modified or "").strip()
        last_mod_display = format_last_modified(last_mod_raw)
        meta_parts = [outstanding_text]
        if status_text:
            meta_parts.append(f"Status: {status_text}")
        if last_mod_display:
            meta_parts.append(f"Updated {last_mod_display}")
        elif last_mod_raw:
            meta_parts.append(f"Updated {last_mod_raw}")
        progress_meta = " • ".join(escape(part) for part in meta_parts if part)
        if not progress_meta:
            progress_meta = "Begin documenting the engagement below."

        priority_label = D.tracking.priority or DEFAULT_TRACKING_PRIORITY
        priority_emoji = {
            "High": "🔥",
            "On Time": "⏱️",
            "Escalation": "🚨",
            "Low": "🕊️",
            "Normal": "📌",
        }.get(priority_label, "📌")
        badge_texts: list[str] = [f"{priority_emoji} Priority: {priority_label}"]
        if D.tracking.active:
            badge_texts.append("📡 Tracking enabled")
        if st.session_state.get("second_line_mode"):
            badge_texts.append("🛠️ 2nd-line workspace")
        if D.customer_trios_only:
            badge_texts.append("🧪 TRIOS-only customer")
        if D.support_fee_accepted:
            badge_texts.append("💳 Support fee accepted")
        badge_html = "".join(
            f'<span class="case-hero__badge">{escape(text)}</span>'
            for text in badge_texts
        )

        case_id_label = escape(D.case_id or "Draft case")
        headline = escape(
            D.brief_description or "Describe the issue to kick things off."
        )
        subtitle = escape(
            D.company_name or "Add the customer or clinic to personalise the workspace."
        )

        container.markdown(
            f"""
            <div class="case-hero">
                <div>
                    <span class="case-hero__eyebrow">{case_id_label}</span>
                    <h2 class="case-hero__title">{headline}</h2>
                    <p class="case-hero__subtitle">{subtitle}</p>
                    <div class="case-hero__badges">{badge_html}</div>
                </div>
                <div class="case-hero__progress">
                    <div class="case-hero__progress-label">Documentation progress</div>
                    <div class="case-hero__progress-track">
                        <div class="case-hero__progress-fill" style="width: {progress_pct}%"></div>
                    </div>
                    <div class="case-hero__progress-value">{progress_pct}%</div>
                    <div class="case-hero__progress-meta">{progress_meta}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_case_milestone_tracker(container, case_idx, compact_mode=compact_mode)

    with case_tab_card(container, "case-card--header", compact_mode) as card:
        header_text = "🗂️ Case Header" if not compact_mode else "Case Header"
        card.markdown(f"### {header_text}")
        if not compact_mode:
            card.caption(
                "Start with the essentials so teammates instantly know who, what, and where."
            )

        if st.session_state.second_line_mode:
            reseller_key = widget_key("reseller_case_number", case_idx)
            default_value = st.session_state.get(
                reseller_key, D.straumann or D.patterson or ""
            )
            st.session_state[reseller_key] = default_value
            merged_value = card.text_input(
                "Reseller case # (Straumann / Patterson)",
                default_value,
                key=reseller_key,
            )
            if merged_value != D.straumann or merged_value != D.patterson:
                D.straumann = merged_value
                D.patterson = merged_value
                st.session_state[widget_state_key("straumann", case_idx)] = merged_value
                st.session_state[widget_state_key("patterson", case_idx)] = merged_value
                touch_case_last_modified()
                autosave()
        else:
            cleared = False
            reseller_key = widget_key("reseller_case_number", case_idx)
            if reseller_key in st.session_state:
                st.session_state.pop(reseller_key)
            if D.patterson != "N/A":
                D.patterson = "N/A"
                st.session_state[widget_state_key("patterson", case_idx)] = "N/A"
                cleared = True
            if D.straumann != "N/A":
                D.straumann = "N/A"
                st.session_state[widget_state_key("straumann", case_idx)] = "N/A"
                cleared = True
            if cleared:
                touch_case_last_modified()
                autosave()

        name_cols = card.columns((1.3, 1, 1))
        auto_text_input(
            "Company name",
            "company_name",
            container=name_cols[0],
            help="The full legal name of the clinic or lab.",
        )
        auto_text_input(
            "Subscription ID",
            "subscription_id",
            container=name_cols[1],
            help="The unique **Dongle ID** or **Subscription ID** identifying the customer license.",
        )
        auto_text_input(
            "Case ID",
            "case_id",
            container=name_cols[2],
            help="The CRM ticket number (e.g. CS-0012345) for this incident.",
        )

        details_cols = card.columns((2, 1))
        auto_text_input(
            "Brief description",
            "brief_description",
            container=details_cols[0],
        )
        version_col = details_cols[1]
        auto_text_input(
            "Application and version",
            "application_version",
            container=version_col,
            placeholder="e.g., Unite 1.8.10.1",
            help="Examples: Unite 1.8.10.1, TRIOS 1.18.8.8, Dental System",
        )

        version_col.markdown("#### Support Fee")
        ct_key = widget_key("customer_trios_only", case_idx)
        sf_state_key = f"support_fee_accepted_{case_idx}"
        customer_trios_only = version_col.toggle(
            "Customer is TRIOS Only?",
            value=st.session_state.get(ct_key, D.customer_trios_only),
            key=ct_key,
            on_change=_update_field,
            args=("customer_trios_only",),
        )
        if customer_trios_only:
            sf_key = widget_key("support_fee_accepted", case_idx)
            version_col.toggle(
                "Support fee price accepted?",
                value=st.session_state.get(sf_key, D.support_fee_accepted),
                key=sf_key,
                on_change=_update_field,
                args=("support_fee_accepted",),
            )
        else:
            st.session_state[sf_state_key] = False
            if D.support_fee_accepted:
                D.support_fee_accepted = False
                touch_case_last_modified()
                autosave()


def render_description_and_internal_notes(container, compact_mode: bool) -> None:
    with case_tab_card(container, "case-card--story", compact_mode) as card:
        if not compact_mode:
            card.markdown("### 📝 Case story & internal context")
            card.caption(
                "Tell the story of the incident and capture quick-access links for the squad."
            )

        desc_cols = card.columns((3, 2))
        description_col, notes_col = desc_cols

        description_label = "Description (What / When / Where)"
        notes_label = "Internal notes"
        if not compact_mode:
            description_col.subheader(f"🗒️ {description_label}")
            notes_col.subheader(f"🔖 {notes_label}")
        else:
            description_col.subheader(description_label)
            notes_col.subheader(notes_label)

        # First time happening logic
        ft_key = widget_key("first_time_happening", CURRENT_CASE_IDX)
        ft_choice = description_col.radio(
            "First time happening?",
            ["Yes", "No"],
            index=None,
            horizontal=True,
            key=ft_key,
        )
        if ft_choice == "No":
            ft_case_key = widget_key("first_time_case_ref", CURRENT_CASE_IDX)
            ft_case_ref = description_col.text_input(
                "Reference case",
                placeholder="Case number or issue reference",
                key=ft_case_key,
            )
        else:
            ft_case_ref = ""

        if description_col.button("Insert into Additional Info", key=widget_key("ft_insert", CURRENT_CASE_IDX)):
            to_append = ""
            if ft_choice == "Yes":
                to_append = "This is the first time this issue happens."
            elif ft_choice == "No":
                ref_text = ft_case_ref.strip() or "[Reference]"
                to_append = f"Customer has reported this issue before on the following case: {ref_text}"

            if to_append:
                current_info = D.additional_info or ""
                new_info = f"{current_info}\n{to_append}" if current_info else to_append
                D.additional_info = new_info
                st.session_state["additional_info"] = new_info
                st.session_state[widget_state_key("additional_info", CURRENT_CASE_IDX)] = new_info
                touch_case_last_modified()
                autosave()
                st.rerun()

        desc_height = 52 if compact_mode else 68
        auto_text_area(
            "Description",
            "description",
            height=desc_height,
            container=description_col,
        )

        auto_text_input("Helpjuice link", "internal_helpjuice", container=notes_col)
        logs_height = 52 if compact_mode else 68
        auto_text_area(
            "Logs / screenshots",
            "internal_logs",
            height=logs_height,
            container=notes_col,
        )


def render_phonecall_section(container, compact_mode: bool) -> None:
    with case_tab_card(container, "case-card--call", compact_mode) as card:
        header = "📞 Phone-call notes" if not compact_mode else "Phone-call notes"
        card.markdown(f"### {header}")
        if not compact_mode:
            card.caption(
                "Capture the live conversation details so follow-up agents can pick up the phone with confidence."
            )

        desc_height = 52 if compact_mode else 68
        layout_cols = card.columns((3, 2))
        notes_col, contact_col = layout_cols

        auto_text_input("Caller name", "caller_name", container=notes_col)
        auto_text_area(
            "Caller issue description",
            "phone_description",
            height=desc_height,
            container=notes_col,
        )

        contact_header = "Contact details"
        if not compact_mode:
            contact_col.subheader(f"📇 {contact_header}")
        else:
            contact_col.subheader(contact_header)
        first_row = contact_col.columns(2)
        auto_text_input("Dongle number", "dongle_number", container=first_row[0])
        auto_text_input("Phone number", "phone_number", container=first_row[1])
        auto_text_input("Customer email", "email", container=contact_col)
        second_row = contact_col.columns(2)
        auto_text_input("TeamViewer ID", "teamviewer_id", container=second_row[0])
        auto_text_input(
            "TeamViewer password",
            "teamviewer_password",
            container=second_row[1],
        )


def render_conclusion_and_additional(container, compact_mode: bool) -> None:
    with case_tab_card(container, "case-card--wrapup", compact_mode) as card:
        if compact_mode:
            card.subheader("Conclusion")
        else:
            card.markdown("### ✅ Resolution & wrap-up")
            card.caption(
                "Summarise the fix, celebrate the win, and log any follow-up intel for your peers."
            )

        conclusion_cols = card.columns(2)
        conclusion_left, conclusion_right = conclusion_cols
        auto_text_input("Root cause", "root_cause", container=conclusion_left)
        auto_text_input("Solution", "solution", container=conclusion_right)
        auto_text_input(
            "Customer satisfaction survey URL",
            "survey_link",
            container=conclusion_right,
        )
        auto_tracking_text_input(
            "CRM case link",
            "case_link",
            container=conclusion_right,
            placeholder="Paste the CRM case link here",
        )

        if compact_mode:
            card.subheader("Additional information")
        else:
            card.markdown("#### 🧠 Additional information")

        # Antivirus and Firewall helpers
        av_col, fw_col = card.columns(2)

        # Antivirus Logic
        av_key = widget_key("antivirus_radio", CURRENT_CASE_IDX)
        av_choice = av_col.radio(
            "Antivirus installed?",
            ["Yes", "No"],
            index=None,
            horizontal=True,
            key=av_key,
        )
        if av_choice == "Yes":
            av_name_key = widget_key("antivirus_name", CURRENT_CASE_IDX)
            av_name = av_col.text_input("Antivirus Name", key=av_name_key)
        else:
            av_name = ""

        if av_col.button("Insert", key=widget_key("av_insert", CURRENT_CASE_IDX)):
            av_text = ""
            if av_choice == "Yes":
                name_str = av_name.strip() or "[Name]"
                av_text = f"Antivirus: {name_str}"
            elif av_choice == "No":
                av_text = "No antivirus detected"

            if av_text:
                current_info = D.additional_info or ""
                new_info = f"{current_info}\n{av_text}" if current_info else av_text
                D.additional_info = new_info
                st.session_state["additional_info"] = new_info
                st.session_state[widget_state_key("additional_info", CURRENT_CASE_IDX)] = new_info
                touch_case_last_modified()
                autosave()
                st.rerun()

        # Firewall Logic
        fw_key = widget_key("firewall_radio", CURRENT_CASE_IDX)
        fw_choice = fw_col.radio(
            "Firewalls enabled?",
            ["Yes", "No"],
            index=None,
            horizontal=True,
            key=fw_key,
        )
        if fw_col.button("Insert", key=widget_key("fw_insert", CURRENT_CASE_IDX)):
            fw_text = ""
            if fw_choice == "Yes":
                fw_text = "Firewalls are ON"
            elif fw_choice == "No":
                fw_text = "Firewalls are OFF"

            if fw_text:
                current_info = D.additional_info or ""
                new_info = f"{current_info}\n{fw_text}" if current_info else fw_text
                D.additional_info = new_info
                st.session_state["additional_info"] = new_info
                st.session_state[widget_state_key("additional_info", CURRENT_CASE_IDX)] = new_info
                touch_case_last_modified()
                autosave()
                st.rerun()

        auto_text_area(
            "Additional details",
            "additional_info",
            height=220 if compact_mode else 400,
            container=card,
            help=(
                "Include details such as antivirus, firewalls enabled, update history, "
                "related case ID, possible cause, performance issues, manual additional notes, "
                "recurring issues, and recent issues."
            ),
        )


def build_kiroshi_tone_directive() -> str:
    """Return the active voice directive for Kiroshi's responses."""

    if st.session_state.get("kiroshi_sarcasm_mode", False):
        return "Reply with a dry, witty, and sarcastic tone while staying professional and helpful."
    return "Use clear, professional language that is easy to follow."


def parse_categorizer_summary(text: str) -> dict[str, str]:
    """Extract categorization fields from the quick action output."""

    summary: dict[str, str] = {}
    if not text:
        return summary
    try:
        data = json.loads(text)
    except Exception:
        data = None
    if isinstance(data, Mapping):
        product = str(data.get("product", ""))
        topic = str(data.get("topic", ""))
        subtopic = data.get("subtopic")
        if subtopic in (None, "None"):
            subtopic_str = ""
        else:
            subtopic_str = str(subtopic)
        summary.update(
            {
                "product": product,
                "topic": topic,
                "subtopic": subtopic_str,
            }
        )
        if "confidence" in data:
            summary["confidence"] = str(data.get("confidence"))
        signals = data.get("signals_used") or data.get("signals")
        if isinstance(signals, (list, tuple)):
            summary["signals"] = ", ".join(str(item) for item in signals if item)
        elif isinstance(signals, str):
            summary["signals"] = signals
        return summary

    in_block = False
    pattern = re.compile(
        r"^(?:[-*]\s*)?(product|topic|subtopic|confidence|signals?|key signals?)\s*[:：]\s*(.+)$",
        re.IGNORECASE,
    )
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not in_block and line.lower().startswith("classification summary"):
            in_block = True
            continue
        match = pattern.match(line)
        if match:
            in_block = True
            key = match.group(1).lower()
            value = match.group(2).strip()
            if key.startswith("signal"):
                summary["signals"] = value
            else:
                summary[key] = value
            continue
        if in_block and not raw_line.startswith((" ", "\t", "-", "*")):
            # Exit once the summary section ends.
            break

    subtopic_value = summary.get("subtopic")
    if isinstance(subtopic_value, str) and subtopic_value.lower() in {
        "none",
        "n/a",
        "null",
        "not applicable",
        "no subtopic",
    }:
        summary["subtopic"] = ""
    return summary


def make_pdf(d: CaseData, cat_map) -> bytes:
    """Generate a PDF summary of the case details."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30
    )
    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    body_style = styles["BodyText"]
    header_style = styles["Heading5"]
    elems = []
    ghost_snippets: list[str] = []
    for cat in cat_map:
        elems.append(Paragraph(cat, styles["Heading4"]))
        ghost_snippets.append(cat)
        df = category_dataframe(cat, d, cat_map)
        data = [[Paragraph("Field", header_style), Paragraph("Value", header_style)]]
        for field, value in df.values.tolist():
            data.append([Paragraph(field, body_style), Paragraph(str(value), body_style)])
            ghost_snippets.extend([str(field), str(value)])
        t = Table(data, colWidths=[150, 350])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )
        elems.extend([t, Spacer(1, 12)])
    _build_pdf_with_ghost_text(doc, elems, ghost_snippets)
    buf.seek(0)
    return buf.read()


def make_tables_pdf(d: CaseData) -> bytes:
    """Generate a PDF with key case information for the Tables tab."""
    summary = st.session_state.get("categorizer_summary")
    if not summary:
        summary = parse_categorizer_summary(st.session_state.get("categorizer_result", ""))
        st.session_state.categorizer_summary = summary
    product = summary.get("product", "")
    topic = summary.get("topic", "")
    subtopic = summary.get("subtopic", "") or ""
    hardware_test_value = ""
    if isinstance(d.hardware_test, str):
        hardware_test_value = d.hardware_test.strip()
    elif isinstance(d.hardware_test, bool):
        hardware_test_value = "Yes" if d.hardware_test else "No"
    elif d.hardware_test is not None:
        hardware_test_value = str(d.hardware_test)

    fields = [
        ("Reportable", "No"),
        ("Product Family", product),
        ("Product", topic),
        ("Sub-product", subtopic),
        ("Hardware test", hardware_test_value or "Not recorded"),
        ("Customer is TRIOS Only", "Yes" if d.customer_trios_only else "No"),
        (
            "Support fee price accepted",
            "Yes" if d.support_fee_accepted else "No",
        ),
        ("Direct payment", "No"),
        ("Dongle Subscription Info", d.dongle_number),
        ("Software Version", d.application_version),
        ("Category", product),
        ("Category Area", topic),
        ("Case type", subtopic),
        ("Responsible contact", d.email),
    ]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30
    )
    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    body_style = styles["BodyText"]
    header_style = styles["Heading5"]
    data = [[Paragraph("Field", header_style), Paragraph("Value", header_style)]]
    ghost_snippets: list[str] = []
    for field, value in fields:
        data.append([Paragraph(field, body_style), Paragraph(str(value), body_style)])
        ghost_snippets.extend([str(field), str(value)])
    t = Table(data, colWidths=[180, 320])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )
    elements = [t]
    _build_pdf_with_ghost_text(doc, elements, ghost_snippets)
    buf.seek(0)
    return buf.read()

def render_autohotkey_panel(cat_map: Mapping[str, object], case_idx: int) -> None:
    st.markdown("#### AutoHotkey quick paste")
    st.caption(
        "Generate a Windows AutoHotkey script so typing `phonecall1`, `remotesession1`, "
        "etc. instantly pastes the current case tables."
    )
    hotkey_script = build_autohotkey_script(
        [cs.case for cs in st.session_state.case_sessions],
        cat_map,
    )
    script_path = sync_autohotkey_script(hotkey_script)
    if script_path:
        script_path_str = str(script_path)
        encoded_hotkeys = json.dumps(hotkey_script)
        st.success(
            "Hotkeys auto-synced locally. Add a single `#Include` to your AutoHotkey "
            "launcher and the triggers will refresh whenever you update cases."
        )
        st.code(f"#Include {script_path_str}", language="autohotkey")
        components.html(
            f"""
            <script>
            function copyKiroshiHotkeys() {{
                navigator.clipboard.writeText({encoded_hotkeys}).then(() => {{
                    const note = document.createElement('div');
                    note.innerText = 'Hotkeys copied to clipboard';
                    note.style.fontSize = '0.8rem';
                    note.style.marginTop = '0.35rem';
                    const host = document.getElementById('kiroshi-hotkeys-feedback');
                    host.innerHTML = '';
                    host.appendChild(note);
                }});
            }}
            </script>
            <button onclick="copyKiroshiHotkeys();"
                    style="margin-top:0.5rem;padding:0.4rem 0.75rem;border-radius:0.4rem;"
                    title="Copy the live hotkeys to the clipboard">
                Copy hotkeys to clipboard
            </button>
            <div id='kiroshi-hotkeys-feedback'></div>
            <p style='font-size:0.8rem;margin-top:0.5rem;'>Script path: {script_path_str}</p>
            """,
            height=90,
        )
    else:
        st.info(
            "Download the script or copy it manually. Automatic syncing is only available "
            "on Windows."
        )
    st.download_button(
        "Download hotkey script",
        hotkey_script.encode("utf-8"),
        file_name=f"kiroshi_tables_hotkeys_{TODAY_STR}.ahk",
        mime="text/plain",
        key=widget_key("download_hotkeys", case_idx),
    )
    with st.expander("Preview generated hotkeys"):
        st.code(hotkey_script, language="autohotkey")


_CAPTURE_FOOTER_REGISTRY_PREFIX = "capture_footer_tab_registry"
_CAPTURE_FOOTER_RENDERED_PREFIX = f"{_CAPTURE_FOOTER_REGISTRY_PREFIX}_rendered"


def _reset_capture_footer_registry(*, case_idx: int | None = None) -> None:
    """Clear cached capture footer state so fresh widgets render cleanly."""

    if case_idx is None:
        prefix = f"{_CAPTURE_FOOTER_REGISTRY_PREFIX}_"
        keys_to_drop = [
            key
            for key in list(st.session_state.keys())
            if isinstance(key, str) and key.startswith(prefix)
        ]
        for key in keys_to_drop:
            st.session_state.pop(key, None)
        rendered_prefix = f"{_CAPTURE_FOOTER_RENDERED_PREFIX}_"
        rendered_to_drop = [
            key
            for key in list(st.session_state.keys())
            if isinstance(key, str) and key.startswith(rendered_prefix)
        ]
        for key in rendered_to_drop:
            st.session_state.pop(key, None)
    else:
        st.session_state.pop(
            widget_state_key(_CAPTURE_FOOTER_REGISTRY_PREFIX, case_idx), None
        )
        st.session_state.pop(
            widget_state_key(_CAPTURE_FOOTER_RENDERED_PREFIX, case_idx), None
        )


def render_screenshot_capture_footer(case_idx: int, *, tab_slug: str) -> None:
    """Render screenshot capture controls anchored at the bottom of a tab.

    ``tab_slug`` should be a stable identifier for the current tab (typically a
    slugified label). We still guard against empty values so the footer remains
    usable even if future tabs forget to provide a slug. Each footer instance is
    registered in session state to guarantee that its widget keys remain unique
    per case and per tab.
    """

    raw_slug = str(tab_slug or "").strip()
    clean_slug = re.sub(r"[^0-9a-z_]+", "_", raw_slug.lower()).strip("_")
    slug_key = clean_slug or "tab"
    registry_state_key = widget_state_key(
        _CAPTURE_FOOTER_REGISTRY_PREFIX, case_idx
    )
    slug_registry = st.session_state.setdefault(registry_state_key, {})

    if slug_key not in slug_registry:
        candidate = slug_key
        existing = set(slug_registry.values())
        counter = 1
        unique_candidate = candidate
        while unique_candidate in existing:
            counter += 1
            unique_candidate = f"{candidate}_{counter}"
        slug_registry[slug_key] = unique_candidate
        st.session_state[registry_state_key] = slug_registry

    footer_slug = f"capture_footer_{slug_registry[slug_key]}"
    rendered_state_key = widget_state_key(
        _CAPTURE_FOOTER_RENDERED_PREFIX, case_idx
    )
    rendered_tokens = st.session_state.setdefault(rendered_state_key, [])
    if footer_slug in rendered_tokens:
        return
    rendered_tokens.append(footer_slug)
    st.session_state[rendered_state_key] = rendered_tokens
    menu_key = partial(case_widget_key, footer_slug, case_idx=case_idx)

    label_state_key = menu_key("shot_label")
    if label_state_key not in st.session_state:
        st.session_state[label_state_key] = ""
    reset_flag_key = menu_key("shot_label_reset_pending")
    if reset_flag_key not in st.session_state:
        st.session_state[reset_flag_key] = False
    if st.session_state.get(reset_flag_key):
        st.session_state[label_state_key] = ""
        st.session_state[reset_flag_key] = False
    auto_stamp_key = menu_key("shot_auto_stamp")
    if auto_stamp_key not in st.session_state:
        st.session_state[auto_stamp_key] = True

    screenshots = get_active_screenshots()

    container = st.container()
    with container:
        st.markdown("---")
        st.subheader("Screenshot capture")
        st.caption(
            "Capture evidence without leaving the current tab. Files stay linked to the case."
        )
        st.caption(
            "These tools stay pinned to the bottom of each tab so you can grab screenshots anywhere."
        )
        st.text_input(
            "Label for next capture",
            key=label_state_key,
            placeholder="e.g. Checkout terminal error dialog",
            help="Shown alongside screenshots in exports and remote menus.",
        )
        st.checkbox(
            "Append timestamp to filenames",
            key=auto_stamp_key,
            help="Keeps filenames unique when you capture multiple shots.",
        )

        capture_cols = st.columns([1, 1, 1, 1])
        if capture_cols[0].button(
            "Capture full desktop",
            key=menu_key("shot_full"),
        ):
            _capture_screenshot_from_ui(
                "full",
                label=st.session_state.get(label_state_key, ""),
                auto_stamp=bool(st.session_state.get(auto_stamp_key, True)),
                label_state_key=label_state_key,
                reset_flag_key=reset_flag_key,
            )
            screenshots = get_active_screenshots()
        if capture_cols[1].button(
            "Capture selected area",
            key=menu_key("shot_region"),
        ):
            _capture_screenshot_from_ui(
                "region",
                label=st.session_state.get(label_state_key, ""),
                auto_stamp=bool(st.session_state.get(auto_stamp_key, True)),
                label_state_key=label_state_key,
                reset_flag_key=reset_flag_key,
            )
            screenshots = get_active_screenshots()
        if capture_cols[2].button(
            "Capture secure (HIPAA)",
            key=menu_key("shot_secure"),
            help="Captures the full screen and blurs letters while keeping numbers visible.",
        ):
            _capture_screenshot_from_ui(
                "full",
                label=st.session_state.get(label_state_key, ""),
                auto_stamp=bool(st.session_state.get(auto_stamp_key, True)),
                label_state_key=label_state_key,
                reset_flag_key=reset_flag_key,
                secure=True,
            )
            screenshots = get_active_screenshots()
        if capture_cols[3].button(
            "Reset label",
            key=menu_key("shot_label_reset"),
        ):
            st.session_state[reset_flag_key] = True

        st.caption(
            "Queued screenshots: "
            f"{len(screenshots)} capture{'s' if len(screenshots) != 1 else ''}."
        )


@contextmanager
def case_tab(tab, *, case_idx: int, slug: str):
    """Wrap a Streamlit tab and append the screenshot footer once it renders."""

    with tab:
        yield
        render_screenshot_capture_footer(case_idx, tab_slug=slug)


def render_case_attachments_panel(
    case: CaseData, *, case_idx: int, tab_slug: str
) -> None:
    """Render the redesigned evidence workflow for a case tab."""

    attachments_key = partial(case_widget_key, tab_slug, case_idx=case_idx)
    screenshots = get_active_screenshots()

    st.markdown("---")
    st.subheader("Evidence locker")

    st.markdown("##### Quick capture")
    st.caption(
        "Use the screenshot controls at the bottom of each tab to grab evidence wherever you're working."
    )
    st.caption(
        "Captured screenshots sync automatically with uploads so the export ZIP contains everything."
    )

    st.markdown("##### Upload additional evidence")
    upload_cols = st.columns(2)
    with upload_cols[0]:
        new_files = st.file_uploader(
            "Add screenshots / videos",
            accept_multiple_files=True,
            key=attachments_key("attachments_new_files"),
            help="Imported files are bundled with captured screenshots when exporting.",
        )
        if new_files:
            existing_names = {f.name for f in st.session_state.uploads}
            for nf in new_files:
                if nf.name not in existing_names:
                    st.session_state.uploads.append(nf)
                    existing_names.add(nf.name)
    with upload_cols[1]:
        log_files = st.file_uploader(
            "Upload troubleshooting logs",
            accept_multiple_files=True,
            key=attachments_key("attachments_log_files"),
            help="Logs appear beside screenshots inside the remote desktop attachments tab.",
        )
        if log_files:
            existing_log_names = {f.name for f in st.session_state.log_uploads}
            for lf in log_files:
                if lf.name not in existing_log_names:
                    st.session_state.log_uploads.append(lf)
                    existing_log_names.add(lf.name)

    st.markdown("##### Evidence queue")
    uploads = st.session_state.uploads
    log_uploads = st.session_state.log_uploads
    screenshots = get_active_screenshots()

    if not (uploads or log_uploads or screenshots):
        st.info("No evidence queued yet. Capture a screenshot or upload supporting files to begin.")
    else:
        if uploads:
            st.markdown("###### Uploaded files")
            for i, f in enumerate(list(uploads)):
                size_bytes = len(f.getvalue())
                size_mb = size_bytes / (1024 * 1024)
                is_video = f.name.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))
                is_heavy = size_mb > 30

                col_layout = [5, 2, 1]
                if is_video and is_heavy:
                    col_layout = [5, 2, 2, 1]

                cols = st.columns(col_layout)
                cols[0].markdown(f"**{f.name}**")
                cols[1].caption(f"Size: {size_mb:.1f} MB")

                if is_video and is_heavy:
                    if cols[2].button(
                        "⚡ Optimize",
                        key=attachments_key(f"attachments_opt_upload_{i}"),
                        help="Compress video to 720p 15fps to reduce size",
                    ):
                        with st.spinner("Optimizing video... this may take a minute"):
                            try:
                                optimized_buffer = optimize_video(f, f.name)
                                if optimized_buffer:
                                    new_size = len(optimized_buffer.getvalue()) / (1024 * 1024)
                                    # Update the session state list in place
                                    st.session_state.uploads[i] = optimized_buffer
                                    st.success(f"Optimized! New size: {new_size:.1f} MB")
                                    time.sleep(1.5) # Let user read success message
                                    st.rerun()
                                else:
                                    st.error("Optimization returned no data.")
                            except Exception as e:
                                st.error(f"Optimization failed: {e}")

                    remove_btn = cols[3]
                else:
                    remove_btn = cols[2]

                if remove_btn.button(
                    "Remove",
                    key=attachments_key(f"attachments_rem_upload_{i}"),
                ):
                    uploads.pop(i)
                    st.rerun()
        if log_uploads:
            st.markdown("###### Log bundles")
            for i, f in enumerate(list(log_uploads)):
                cols = st.columns([6, 2, 1])
                cols[0].markdown(f"**{f.name}**")
                cols[1].caption(f"Size: {len(f.getvalue()) // 1024} KB")
                if cols[2].button(
                    "Remove",
                    key=attachments_key(f"attachments_rem_log_{i}"),
                ):
                    log_uploads.pop(i)
                    st.rerun()
        if screenshots:
            st.markdown("###### Captured screenshots")
            for i, shot in enumerate(list(screenshots)):
                edit_cols = st.columns([3, 3, 1])
                label_edit_key = attachments_key(f"shot_label_edit_{i}")
                if label_edit_key not in st.session_state:
                    st.session_state[label_edit_key] = shot.label
                new_label = edit_cols[0].text_input(
                    "Label",
                    key=label_edit_key,
                    help="Shown in remote menus and exported summaries.",
                )
                if new_label.strip() and new_label.strip() != shot.label:
                    shot.label = new_label.strip()

                filename_edit_key = attachments_key(f"shot_filename_{i}")
                filename_pending_key = attachments_key(f"shot_filename_pending_{i}")

                pending_value = st.session_state.pop(filename_pending_key, None)
                if pending_value is not None:
                    st.session_state.pop(filename_edit_key, None)
                    default_filename = pending_value
                else:
                    default_filename = st.session_state.get(filename_edit_key, shot.name)

                new_filename = edit_cols[1].text_input(
                    "Filename",
                    value=default_filename,
                    key=filename_edit_key,
                    help="Used when evidence is written to disk or bundled into zips.",
                )
                if new_filename.strip() and new_filename.strip() != shot.name:
                    sanitized = sanitize_filename(new_filename.strip())
                    if not sanitized.lower().endswith(".png"):
                        sanitized = f"{sanitized}.png"
                    shot.name = sanitized
                    st.session_state[filename_pending_key] = sanitized
                    st.rerun()

                with edit_cols[2]:
                    if st.button(
                        "Remove",
                        key=attachments_key(f"attachments_rem_shot_{i}"),
                        help="Delete this screenshot",
                    ):
                        screenshots.pop(i)
                        set_active_screenshots(screenshots)
                        st.rerun()
                    st.download_button(
                        "Download",
                        shot.getvalue(),
                        file_name=shot.name,
                        mime=shot.content_type,
                        key=attachments_key(f"attachments_dl_shot_{i}"),
                    )

                st.caption(
                    f"Captured {shot.captured_at} · Mode: {shot.capture_mode.title()} · Stored as {shot.name}"
                )
                with st.expander("Preview", expanded=False):
                    st.image(shot.data, caption=shot.label, use_container_width=True)

    include_case_json_key = attachments_key("attachments_include_case_json")
    if include_case_json_key not in st.session_state:
        st.session_state[include_case_json_key] = True

    st.markdown("##### Package evidence")
    st.checkbox(
        "Include case.json snapshot",
        key=include_case_json_key,
        help="Adds the full case payload next to the evidence in the exported archive.",
    )
    if st.button(
        "Create evidence bundle",
        key=attachments_key("attachments_create_zip"),
        help="Writes uploads, logs, and screenshots to a single ZIP ready to attach to incidents.",
    ):
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in uploads:
                z.writestr(f"uploads/{f.name}", f.getvalue())
            for f in log_uploads:
                z.writestr(f"logs/{f.name}", f.getvalue())
            for shot in screenshots:
                z.writestr(f"screenshots/{shot.name}", shot.getvalue())
            if st.session_state.get(include_case_json_key, True):
                z.writestr("case.json", json.dumps(asdict(case), indent=2))
        zbuf.seek(0)
        archive_name = f"{case.case_id or 'case'}_evidence.zip"
        archive_bytes = zbuf.getvalue()
        download_clicked = st.download_button(
            "Download evidence.zip",
            archive_bytes,
            file_name=archive_name,
            mime="application/zip",
            key=attachments_key("attachments_download_zip"),
        )
        if download_clicked:
            saved_path = persist_evidence_bundle_zip(case.case_id or "case", archive_name, archive_bytes)
            if saved_path:
                st.info(f"Saved a copy to {saved_path}")


CASE_TAB_SLUGS = {
    # Keep this mapping in sync with the tab layout inside ``render_case_ui``.
    # Each human-friendly tab label resolves to a slug used for widget keys.
    "Case": "case",
    "Tracking": "tracking",
    "Escalations": "escalations",
    "Email": "email",
    "Hardware Issues": "hardware",
    "Remote Session": "remote",
    "Tables": "tables",
    "Corrected JSON": "corrected_json",
    "Save/Load": "save_load",
    "Kiroshi Chat": "kiroshi_chat",
    "I'm bored": "bored",
    "Debug": "debug",
}

def _case_chat_state_key(case_idx: int) -> str:
    """Return a stable session key for storing chat history per case."""

    base = f"case-{case_idx}"
    sessions = st.session_state.get("case_sessions")
    if isinstance(sessions, list) and 0 <= case_idx < len(sessions):
        case_obj = getattr(sessions[case_idx], "case", None)
        if isinstance(case_obj, CaseData):
            for candidate in (
                case_obj.case_id,
                case_obj.company_name,
                case_obj.brief_description,
            ):
                text = str(candidate or "").strip()
                if not text:
                    continue
                safe = re.sub(r"[^0-9a-zA-Z]+", "-", text).strip("-")
                if safe:
                    base = f"case-{case_idx}-{safe[:40].lower()}"
                    break
    return base


def _case_chat_history_store() -> dict[str, list[dict[str, object]]]:
    """Return the mapping that stores per-case chat transcripts."""

    store = st.session_state.get("case_chat_histories")
    if not isinstance(store, dict):
        store = {}
        st.session_state["case_chat_histories"] = store
    return store


def _case_chat_history(case_idx: int) -> list[dict[str, object]]:
    """Return the chat history list for ``case_idx``."""

    store = _case_chat_history_store()
    key = _case_chat_state_key(case_idx)
    history = store.get(key)
    if history is None:
        history = []
        store[key] = history
    return history


def _case_chat_meta(case_idx: int) -> dict[str, object]:
    """Return auxiliary metadata storage for the case chat panel."""

    meta_store = st.session_state.get("case_chat_meta")
    if not isinstance(meta_store, dict):
        meta_store = {}
        st.session_state["case_chat_meta"] = meta_store
    key = _case_chat_state_key(case_idx)
    meta = meta_store.get(key)
    if meta is None:
        meta = {}
        meta_store[key] = meta
    return meta


def _visible_case_index_list() -> list[int]:
    sessions = st.session_state.get("case_sessions")
    if not isinstance(sessions, list):
        return []
    return [idx for idx in range(len(sessions)) if idx != HIDDEN_CASE_INDEX]


def _visible_case_position(case_idx: int) -> int | None:
    indices = _visible_case_index_list()
    if case_idx in indices:
        return indices.index(case_idx) + 1
    return None


def _case_display_name(case_idx: int) -> str:
    """Return a human-friendly label for the case."""

    sessions = st.session_state.get("case_sessions")
    if isinstance(sessions, list) and 0 <= case_idx < len(sessions):
        case_obj = getattr(sessions[case_idx], "case", None)
        if isinstance(case_obj, CaseData):
            for candidate in (
                case_obj.case_id,
                case_obj.company_name,
                case_obj.brief_description,
            ):
                text = str(candidate or "").strip()
                if text:
                    return text
    position = _visible_case_position(case_idx)
    if position is not None:
        return f"Case {position}"
    return f"Case {case_idx + 1}"


def _build_case_context_prompt(case_idx: int) -> str:
    """Create a system message that enumerates the active case JSON."""

    sessions = st.session_state.get("case_sessions")
    case_obj: CaseData | None = None
    if isinstance(sessions, list) and 0 <= case_idx < len(sessions):
        candidate = getattr(sessions[case_idx], "case", None)
        if isinstance(candidate, CaseData):
            case_obj = candidate

    if not isinstance(case_obj, CaseData):
        fallback = st.session_state.get("case")
        if isinstance(fallback, CaseData):
            case_obj = fallback

    case_label = _case_display_name(case_idx)
    if isinstance(case_obj, CaseData):
        case_payload = asdict(case_obj)
    else:
        case_payload = {}
    case_json = json.dumps(case_payload, indent=2, ensure_ascii=False, default=str)
    personality_mode = st.session_state.get("personality_mode", "utility")
    sarcasm_enabled = st.session_state.get("kiroshi_sarcasm_mode", False)
    return (
        f"Active case context for {case_label}. Personality mode: {personality_mode}. "
        f"Sarcasm enabled: {'yes' if sarcasm_enabled else 'no'}. "
        "Use every field in the following JSON payload when answering questions about this case. "
        "If information is missing or uncertain, call that out directly.\n\nCASE JSON:\n"
        + case_json
    )


def _append_case_chat_message(
    case_idx: int,
    role: str,
    content: str,
    *,
    display_content: str | None = None,
    mode: str | None = None,
) -> None:
    """Store a chat message for the specified case."""

    history = _case_chat_history(case_idx)
    entry: dict[str, object] = {"role": role, "content": str(content)}
    if display_content is not None and display_content != content:
        entry["display_content"] = str(display_content)
    if mode:
        entry["mode"] = mode
    history.append(entry)


def _case_chat_history_for_model(case_idx: int) -> list[dict[str, str]]:
    """Return the case chat history in OpenAI-compatible format."""

    formatted: list[dict[str, str]] = []
    for entry in _case_chat_history(case_idx):
        role = entry.get("role")
        content = entry.get("content")
        if role not in {"user", "assistant", "system"}:
            continue
        if not isinstance(content, str):
            continue
        formatted.append({"role": role, "content": content})
    return formatted


def _record_global_chat_exchange(user_payload: str, assistant_reply: str) -> None:
    """Append a user/assistant exchange to the persistent global memory."""

    history = st.session_state.get("kiroshi_chat_history")
    if not isinstance(history, list):
        history = []
    history.append({"role": "user", "content": user_payload})
    history.append({"role": "assistant", "content": assistant_reply})
    st.session_state["kiroshi_chat_history"] = history
    save_memory(history)

def render_case_ui(case_idx: int):
    global CURRENT_CASE_IDX
    CURRENT_CASE_IDX = case_idx
    _sync_case_text_state(case_idx)
    # ──────────── TABS ───────────
    if case_idx <= 1:
        col_escal, col_hw = st.columns(2)
        with col_escal:
            st.session_state.include_escalations = st.toggle(
                "Include escalations",
                value=st.session_state.include_escalations,
                key=case_widget_key("include_escalations", case_idx=case_idx),
            )
        with col_hw:
            st.session_state.include_hardware = st.toggle(
                "Include hardware issues",
                value=st.session_state.include_hardware,
                key=case_widget_key("include_hardware", case_idx=case_idx),
            )
    cat_map = active_category_map()
    tab_labels = ["Case"]
    if st.session_state.track_case:
        tab_labels.append("Tracking")
    if st.session_state.include_escalations:
        tab_labels.append("Escalations")
    tab_labels.append("Email")
    if st.session_state.include_hardware:
        tab_labels.append("Hardware Issues")
    tab_labels += [
        "Remote Session",
        "Tables",
        "Corrected JSON",
        "Save/Load",
    ]
    show_case_chat = st.session_state.get("show_kiroshi_chat", True)
    if show_case_chat:
        tab_labels.append("Kiroshi Chat")
    if st.session_state.show_bored:
        tab_labels.append("I'm bored")

    tabs = st.tabs(tab_labels)
    tab_iter = iter(tabs)
    tab_case = next(tab_iter)
    tab_tracking = next(tab_iter) if st.session_state.track_case else None
    tab_escalations = next(tab_iter) if st.session_state.include_escalations else None
    tab_email = next(tab_iter)
    tab_hw = next(tab_iter) if st.session_state.include_hardware else None
    tab_remote = next(tab_iter)
    tab_tables = next(tab_iter)
    tab_corrected = next(tab_iter)
    tab_save_load = next(tab_iter)
    tab_chat = next(tab_iter) if show_case_chat else None
    tab_bored = next(tab_iter) if st.session_state.show_bored else None

    # ================== 2ND LINE MODE TAB =================
    # ================== CASE TAB =================
    with case_tab(tab_case, case_idx=case_idx, slug=CASE_TAB_SLUGS["Case"]):
        case_tab_key = partial(case_widget_key, CASE_TAB_SLUGS["Case"], case_idx=case_idx)
        api_key = st.session_state.openai_api_key
        model = st.session_state.openai_model
        base_url = st.session_state.ai_base_url
        toggle_key = case_tab_key("quick_actions_open")
        if toggle_key not in st.session_state:
            st.session_state[toggle_key] = False

        def render_quick_actions_menu() -> None:
            st.markdown("#### Quick actions")
            educate_enabled = st.session_state.get("ai_educate_enabled", False)
            advanced_enabled = st.session_state.get("ai_educate_advanced", False)
            ai_learning_dataset = None
            if educate_enabled and advanced_enabled:
                ai_learning_dataset = ensure_ai_learning_dataset()

            ai_assist_summary = st.session_state.get("ai_assist_result") or ""
            ai_autocorrect_summary = st.session_state.get("ai_autocorrect_result") or ""

            if st.button(
                "Save case",
                key=case_tab_key("quick_save"),
                width="stretch",
                help="Persist current case data to disk",
            ):
                save_case_to_database(D)
            if st.button(
                "Clear all",
                key=case_tab_key("clear_all_button"),
                width="stretch",
                help="Reset all fields in this case to their default state",
            ):
                logging.info("Clear all button clicked")
                with case_loading_overlay("Cycling the workspace back to zero…"):
                    time.sleep(2)
                    backup_path = None
                    if D.case_id:
                        backup_path = create_case_autosave_snapshot(D.case_id)
                    if os.path.exists(AUTOSAVE_FILE):
                        try:
                            os.remove(AUTOSAVE_FILE)
                        except OSError:
                            pass
                    clear_case_state(case_idx)
                    if backup_path is not None:
                        st.session_state["autosave_notice"] = (
                            f"Case autosaved to {backup_path.name}"
                        )
                st.rerun()
            if st.session_state.track_case:
                st.button(
                    "Tracking enabled",
                    disabled=True,
                    key=case_tab_key("tracking_enabled"),
                    width="stretch",
                )
            elif st.button(
                "Track case",
                key=case_tab_key("track_case_button"),
                width="stretch",
            ):
                st.session_state.track_case = True
                st.rerun()
            if st.button(
                "AI Assistance",
                key=case_tab_key("assist_button"),
                width="stretch",
            ):
                logging.info("AI Assistance button clicked")
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key in the Debug tab.")
                else:
                    case_dict = _build_case_ai_dict(D)
                    _, miss = compute_progress(D, cat_map)
                    missing = [f for flds in miss.values() for f in flds]
                    learning_context = ""
                    if educate_enabled and advanced_enabled:
                        matches = find_relevant_learning_cases(D, ai_learning_dataset)
                        st.session_state.ai_learning_matches = matches
                        if matches:
                            condensed_matches = [
                                {
                                    "case_id": match.get("case_id"),
                                    "title": match.get("title"),
                                    "root_cause": match.get("root_cause"),
                                    "solution": _summarize_text(
                                        str(match.get("solution") or match.get("solution_excerpt") or ""),
                                        width=240,
                                    ),
                                    "keywords": match.get("keywords"),
                                    "score": match.get("score"),
                                    "saved_at": match.get("saved_at"),
                                }
                                for match in matches
                            ]
                            learning_context = (
                                "Leverage these historical cases when reasoning about the current issue:\n\n"
                                + json.dumps(condensed_matches, indent=2)
                                + "\n\n"
                            )
                        elif ai_learning_dataset:
                            summary_payload = {
                                "top_keywords": ai_learning_dataset.get("insight_summary", {}).get(
                                    "top_keywords", []
                                )[:5],
                                "root_cause_patterns": ai_learning_dataset.get("root_cause_patterns", [])[:3],
                            }
                            learning_context = (
                                "Historical learning summary:\n\n"
                                + json.dumps(summary_payload, indent=2)
                                + "\n\n"
                            )
                    else:
                        st.session_state.ai_learning_matches = []
                    tone_directive = build_kiroshi_tone_directive()
                    disabled_tab_note = _disabled_tab_note()
                    user_message = (
                        learning_context
                        + disabled_tab_note
                        + "You are Kiroshi, an experienced support case assistant."
                        " Review the case details below and provide a concise, human-readable guidance summary."
                        f" {tone_directive}"
                        " Focus on the most relevant insights from the case data.\n\n"
                        "Your response must be plain language (no JSON) and include:\n"
                        "- A brief summary of the case context.\n"
                        "- Likely root cause or contributing factors, even if tentative.\n"
                        "- Recommended solution steps and follow-up actions.\n"
                        "- Remote or on-site verification steps when appropriate.\n"
                        "- Any helpful extra context, cautions, or reminders.\n"
                        "Keep the guidance under 220 words.\n\n"
                        "CASE DATA:\n"
                        + json.dumps(case_dict, indent=2, ensure_ascii=False)
                        + "\nMISSING OR UNCERTAIN FIELDS:\n"
                        + json.dumps(missing, ensure_ascii=False)
                    )
                    try:
                        reply = invoke_gpt(
                            user_message,
                            st.session_state.kiroshi_chat_history,
                            api_key,
                            model,
                            base_url,
                            source="ai_assist",
                        )
                    except Exception as e:
                        logging.error("AI Assist request failed: %s", e)
                        st.error(str(e))
                    else:
                        st.session_state.kiroshi_chat_history.append({"role": "user", "content": user_message})
                        st.session_state.kiroshi_chat_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.kiroshi_chat_history)
                        st.session_state.ai_assist_result = reply
            autocorrect_disabled = not bool(ai_assist_summary)
            autocorrect_help = None
            if autocorrect_disabled:
                autocorrect_help = "Run AI Assistance first to enable AI Autocorrection."
            if st.button(
                "AI Autocorrection",
                key=case_tab_key("ai_autocorrect_button"),
                width="stretch",
                disabled=autocorrect_disabled,
                help=autocorrect_help,
            ):
                logging.info("AI Autocorrection button clicked")
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key in the Debug tab.")
                else:
                    case_dict = _build_case_ai_dict(D)
                    tone_directive = build_kiroshi_tone_directive()
                    disabled_tab_note = _disabled_tab_note()
                    user_message = (
                        disabled_tab_note
                        + "You are Kiroshi, auto-correcting this case for perfect QA compliance. "
                        "Use the prior AI Assistance guidance, the QA framework for 3Shape support, and the case data to produce a corrected JSON payload. "
                        f"{tone_directive}"
                        " Return JSON only (no Markdown) using this structure:\n"
                        "{\n"
                        "  \"corrected_case\": <the CASE DATA with every key preserved; fix errors, fill missing notes, and polish language>,\n"
                        "  \"corrections_applied\": [short bullet strings describing what you changed],\n"
                        "  \"correct_steps\": [ordered steps that remain valid or should be documented],\n"
                        "  \"qa_sim_note\": \"concise QA/SIM note ready for CRM\",\n"
                        "  \"summary\": \"brief recap of the case and improvements\"\n"
                        "}\n"
                        "Keep troubleshooting facts intact, elevate clarity for QA, and leave any field untouched if uncertain rather than inventing details."
                        f"\n\nAI Assistance summary:\n{ai_assist_summary}\n\nCASE DATA:\n"
                        f"{json.dumps(case_dict, indent=2, ensure_ascii=False)}"
                    )
                    try:
                        reply = invoke_gpt(
                            user_message,
                            st.session_state.kiroshi_chat_history,
                            api_key,
                            model,
                            base_url,
                            source="ai_autocorrect",
                        )
                    except Exception as e:
                        logging.error("AI Autocorrection request failed: %s", e)
                        st.error(str(e))
                    else:
                        st.session_state.kiroshi_chat_history.append({"role": "user", "content": user_message})
                        st.session_state.kiroshi_chat_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.kiroshi_chat_history)
                        parsed_autocorrect = _extract_json_object(reply)
                        if parsed_autocorrect:
                            st.session_state.ai_autocorrect_case_json = parsed_autocorrect
                            st.session_state.ai_autocorrect_result = json.dumps(
                                parsed_autocorrect, indent=2, ensure_ascii=False
                            )
                        else:
                            st.session_state.ai_autocorrect_case_json = {}
                            st.session_state.ai_autocorrect_result = reply
            if educate_enabled and advanced_enabled:
                matches = st.session_state.get("ai_learning_matches", [])
                if matches:
                    st.markdown("**Historical cases considered for this assistance:**")
                    for match in matches:
                        case_label = match.get("case_id") or "Unknown Case"
                        title = match.get("title") or "Untitled"
                        score = match.get("score")
                        st.markdown(
                            f"- **{case_label}** – {title} (similarity score: {score})"
                        )
                        solution_excerpt = match.get("solution_excerpt") or match.get("solution")
                        if solution_excerpt:
                            st.caption(f"Solution insight: {solution_excerpt}")
                elif ai_learning_dataset and ai_learning_dataset.get("case_count"):
                    st.caption(
                        "AI Educate did not find a close historical match; general patterns were provided instead."
                    )
            if st.button(
                "Categorize",
                key=case_tab_key("categorize_button"),
                width="stretch",
                help="Analyze case text to suggest category and root cause",
            ):
                logging.info("Categorize button clicked")
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key in the Debug tab.")
                else:
                    taxonomy_block = st.session_state.taxonomy_block
                    signals_config = st.session_state.signals_config
                    if not taxonomy_block or not signals_config:
                        st.error("Please provide taxonomy and signals config in the Debug tab.")
                    else:
                        case_dict = _build_case_ai_dict(D)
                        case_input = {
                            "title": D.brief_description,
                            "description": D.description,
                            "artifacts": [f.name for f in st.session_state.uploads],
                            "meta": {
                                "product_hint": D.application_version,
                                "lang": "en",
                            },
                            "full_case": case_dict,
                        }
                        tone_directive = build_kiroshi_tone_directive()
                        user_message = (
                            "You are Kiroshi, the categorization specialist for 3Shape support. "
                            f"{tone_directive} Review the case information below and choose the best Product → Topic → (Subtopic) path from the provided taxonomy.\n\n"
                            "Guidelines:\n"
                            "- Consider the signals list as hints, but rely on the full context when selecting a category.\n"
                            "- Mention why the recommended category fits and note any uncertainties.\n"
                            "- Suggest up to two alternative categories if the match is imperfect, explaining why.\n"
                            "- Recommend evidence or follow-up checks that would confirm the choice.\n"
                            "Respond in natural language (no JSON).\n\n"
                            "Structure the answer with short sections:\n"
                            "1. Case Snapshot – summarize the situation.\n"
                            "2. Recommended Path – clearly state Product → Topic → Subtopic.\n"
                            "3. Supporting Signals – bullet the key clues that led to the decision.\n"
                            "4. Alternatives – list optional backups if relevant, otherwise state None.\n"
                            "Finish with a 'Classification Summary' block on separate lines using exactly this format:\n"
                            "Product: <product>\nTopic: <topic>\nSubtopic: <subtopic or None>\nConfidence: <confidence level>\nSignals: <comma-separated highlights>\n"
                            "Keep the entire response under 220 words. If a subtopic is not applicable, write None.\n\n"
                            "Authoritative taxonomy:\n"
                            f"{taxonomy_block}\n\n"
                            "Signals reference:\n"
                            f"{signals_config}\n\n"
                            "Case input:\n"
                            f"{json.dumps(case_input, indent=2, ensure_ascii=False)}"
                        )
                        try:
                            reply = invoke_gpt(
                                user_message,
                                st.session_state.kiroshi_chat_history,
                                api_key,
                                model,
                                base_url,
                                source="categorize",
                            )
                        except Exception as e:
                            logging.error("Categorize request failed: %s", e)
                            st.error(str(e))
                        else:
                            st.session_state.kiroshi_chat_history.append({"role": "user", "content": user_message})
                            st.session_state.kiroshi_chat_history.append({"role": "assistant", "content": reply})
                            save_memory(st.session_state.kiroshi_chat_history)
                            st.session_state.categorizer_result = reply
                            st.session_state.categorizer_summary = parse_categorizer_summary(reply)
            if st.button(
                "Ask",
                key=case_tab_key("ask_button"),
                width="stretch",
                help="Query Kiroshi about this specific case",
            ):
                logging.info("Ask button clicked")
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key in the Debug tab.")
                else:
                    case_dict = _build_case_ai_dict(D)
                    findings = st.session_state.verify_result
                    tone_directive = build_kiroshi_tone_directive()
                    findings_context = (
                        "Incorporate these verification notes when suggesting actions:\n"
                        f"{findings}\n\n"
                        if findings
                        else ""
                    )
                    user_message = (
                        f"You are Kiroshi, an experienced support engineer. {tone_directive} "
                        "Review the support case details below and craft actionable help for the frontline agent.\n"
                    )
                    user_message += findings_context
                    user_message += (
                        "Respond with clear, plain-language guidance (no JSON) that includes:\n"
                        "- A quick recap of the customer's situation.\n"
                        "- The most plausible causes or contributing factors.\n"
                        "- Concrete troubleshooting or remediation steps in logical order.\n"
                        "- Remote or on-site checks the agent should perform or request.\n"
                        "- Helpful reminders, cautions, or follow-up actions.\n"
                        "Keep the reply under 220 words.\n\n"
                        "CASE DATA:\n"
                        f"{json.dumps(case_dict, indent=2, ensure_ascii=False)}"
                    )
                    try:
                        reply = invoke_gpt(
                            user_message,
                            st.session_state.kiroshi_chat_history,
                            api_key,
                            model,
                            base_url,
                            source="ask",
                        )
                    except Exception as e:
                        logging.error("Ask request failed: %s", e)
                        st.error(str(e))
                    else:
                        st.session_state.kiroshi_chat_history.append({"role": "user", "content": user_message})
                        st.session_state.kiroshi_chat_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.kiroshi_chat_history)
                        st.session_state.ask_result = reply
            if st.button(
                "QA Verify",
                key=case_tab_key("verify_button"),
                width="stretch",
                help="Run quality assurance checks on case documentation",
            ):
                logging.info("QA Verify button clicked")
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key in the Debug tab.")
                else:
                    case_dict = _build_case_ai_dict(D)
                    tone_directive = build_kiroshi_tone_directive()
                    qa_training_content = (
                        "Comprehensive QA training (apply rigorously):\n"
                        "Criteria A – Call Control (CX 10%): greeting, ID, consent, set agenda, hold/transfer etiquette, recap.\n"
                        "Criteria B – Soft Skills (CX 40%): empathy, ownership, tone, confidence, proactive reassurance, bias-free phrasing.\n"
                        "Criteria C – Communication (CX 20%): clear/simple language, structure, avoids jargon, confirms understanding, summarizes next steps.\n"
                        "Criteria D – Closure (CX 30%): confirms resolution, lists actions/results, tickets closed or follow-up scheduled, surveys offered.\n"
                        "Criteria E – Case Procedures/Background (CP): device/OS/app versions, configurations, logs/screenshots, environment context.\n"
                        "Criteria F – Troubleshooting/Root Cause (CP): steps attempted, diagnostics, hypotheses, fixes, validation evidence, escalation notes.\n"
                        "Criteria G – Notes & CRM (CP): internal/general notes, customer-facing notes, remote steps, SIM/QA notes, CRM Description/Identification/Numbers/Categorization/conclusion/disposition filled.\n"
                        "Definitions: Yes = met, No = missing/incorrect, Super Pro = exemplary beyond standard.\n"
                        "Channel adjustments: phone requires vocal warmth, holds/transfers handled explicitly; email/chat needs brevity, formatting, and acknowledgement of wait times; convert call flows to equivalent written assurances when not on voice.\n"
                        "Customer type adjustments: consumer/external prioritize CX tone and clarity; partner/reseller/advanced users emphasize precision and CP depth while keeping CX acceptable.\n"
                        "Scoring: blend CX (A–D weights listed) with CP (E–G completeness). Track Super Pro as Yes but note excellence; mark N/A only when a criterion truly does not apply.\n"
                    )
                    qa_framework_context = (
                        "Score the case against the 3Shape Case AI Assistance QA framework: "
                        "Call Control (10%), Soft Skills (40%), Communication (20%), Closure (30%). "
                        "Also check case procedures/background, troubleshooting/root cause, notes (general/customer/remote), "
                        "and CRM documentation (Description, Identification, Numbers, Categorization, conclusion, disposition)."
                    )
                    ai_assist_context = st.session_state.get("ai_assist_result") or ""
                    ai_autocorrect_context = st.session_state.get("ai_autocorrect_result") or ""
                    disabled_tab_note = _disabled_tab_note()
                    user_message = (
                        f"You are Kiroshi, an experienced support case reviewer. {tone_directive} "
                        "Evaluate QA readiness using the framework and return a JSON object only. The JSON must include: "
                        "scores (call_control, soft_skills, communication, closure, procedures, notes, crm, qa_sim), "
                        "overall (weighted percent using the listed weights), gaps (list of missing items), "
                        "recommendations (list), and pass (true if overall >= 80). "
                        "Follow this instruction list so the model applies all KPIs: "
                        "1) Apply Criteria A–G with the channel and customer-type rules from the QA training content. "
                        "2) Balance CX-heavy items (A–D weights given) against CP completeness (E–G) when judging overall readiness. "
                        "3) Map each criterion to the structured JSON scores and short comments highlighting Yes/No/Super Pro evidence. "
                        "4) Explicitly mark any N/A criteria and explain why they do not apply. "
                        f"Use any AI Assistance or Autocorrection output when scoring.\n\n"
                        f"{disabled_tab_note}"
                        f"QA Training:\n{qa_training_content}\n"
                        f"Framework:\n{qa_framework_context}\n\n"
                        f"AI Assistance summary:\n{ai_assist_context}\n\n"
                        f"AI Autocorrection updates:\n{ai_autocorrect_context}\n\n"
                        "CASE DATA:\n"
                        f"{json.dumps(case_dict, indent=2, ensure_ascii=False)}"
                    )
                    try:
                        reply = invoke_gpt(
                            user_message,
                            st.session_state.kiroshi_chat_history,
                            api_key,
                            model,
                            base_url,
                            source="verify",
                        )
                    except Exception as e:
                        logging.error("QA Verify request failed: %s", e)
                        st.error(str(e))
                    else:
                        st.session_state.kiroshi_chat_history.append({"role": "user", "content": user_message})
                        st.session_state.kiroshi_chat_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.kiroshi_chat_history)
                        qa_result = _extract_json_object(reply)
                        st.session_state.qa_verification = qa_result or {}
                        st.session_state.qa_verification_score = None
                        if qa_result:
                            st.session_state.verify_result = json.dumps(
                                qa_result, indent=2, ensure_ascii=False
                            )
                            overall = qa_result.get("overall") if isinstance(qa_result, dict) else None
                            if isinstance(overall, (int, float)):
                                st.session_state.qa_verification_score = float(overall)
                                if overall >= 80:
                                    if st.session_state.track_case and getattr(D.tracking, "active", False):
                                        D.tracking.active = False
                                        save_case_to_database(D, notify=False)
                                        st.session_state.track_case = False
                                        st.success(
                                            "QA score meets threshold (>=80%). Case removed from tracking."
                                        )
                                    else:
                                        st.success(
                                            "QA score meets threshold (>=80%). Case is eligible to stay untracked."
                                        )
                                else:
                                    st.warning(
                                        "QA score is below 80%. Keep tracking the case until gaps are closed."
                                    )
                        else:
                            st.session_state.verify_result = reply

        popover_fn = getattr(st, "popover", None)

        st.markdown(
            f"""
            <style>
                div[data-testid="quick-actions-floating-{case_idx}"] {{
                    position: fixed;
                    bottom: 1.5rem;
                    right: 1.5rem;
                    z-index: 1000;
                }}
                div[data-testid="quick-actions-floating-{case_idx}"] > div button {{
                    border-radius: 999px !important;
                    padding: 0.75rem 1.25rem;
                    font-size: 1.25rem;
                    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
                }}
                div[data-testid="quick-actions-floating-{case_idx}"] [data-testid="stPopoverContent"] {{
                    width: 320px;
                    padding: 0.75rem 0.75rem 1rem;
                }}
                div[data-testid="quick-actions-floating-{case_idx}"] [data-testid="stPopoverContent"] h4 {{
                    margin-top: 0;
                }}
                div[data-testid="quick-actions-floating-{case_idx}"] .quick-actions-fallback-panel {{
                    margin-top: 0.75rem;
                    background-color: var(--background-color, #ffffff);
                    border-radius: 1rem;
                    padding: 0.75rem 0.75rem 1rem;
                    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
                    width: 320px;
                }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div data-testid="quick-actions-floating-{case_idx}" class="quick-actions-floating">',
            unsafe_allow_html=True,
        )

        if popover_fn is not None:
            with popover_fn(
                "⚡",
                width="content",
                help="Quick Actions menu",
            ):
                render_quick_actions_menu()
        else:
            bubble_label = "✕" if st.session_state[toggle_key] else "⚡"
            if st.button(
                bubble_label,
                key=case_tab_key("quick_actions_toggle_button"),
                width="stretch",
                help="Toggle the Quick Actions menu",
            ):
                st.session_state[toggle_key] = not st.session_state[toggle_key]
                st.rerun()
            if st.session_state[toggle_key]:
                st.markdown(
                    '<div class="quick-actions-fallback-panel">',
                    unsafe_allow_html=True,
                )
                render_quick_actions_menu()
                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        compact_mode = st.session_state.get("case_compact_mode", False)
        qa_result = st.session_state.get("qa_verification") or {}
        qa_score = st.session_state.get("qa_verification_score")
        if qa_result:
            st.markdown("#### QA Verify")
            if isinstance(qa_score, (int, float)):
                st.markdown(f"**Overall QA score:** {qa_score:.1f}%")
            scores = qa_result.get("scores") if isinstance(qa_result, dict) else None
            if isinstance(scores, dict) and scores:
                st.markdown("**Area scores**")
                for area, score in scores.items():
                    label = area.replace('_', ' ').title()
                    if isinstance(score, dict):
                        val = None
                        for key in ("score", "value", "points"):
                            if key in score:
                                val = score[key]
                                break
                        comment = score.get("comment") or score.get("note") or score.get("reason")

                        display_text = f"- **{label}:** {val}"
                        if comment:
                            display_text += f" – *{comment}*"
                        st.markdown(display_text)
                    else:
                        st.markdown(f"- **{label}:** {score}")
            gaps = qa_result.get("gaps") if isinstance(qa_result, dict) else None
            if isinstance(gaps, list) and gaps:
                st.markdown("**Gaps to fix**")
                for gap in gaps:
                    st.markdown(f"- {gap}")
            recommendations = qa_result.get("recommendations") if isinstance(qa_result, dict) else None
            if isinstance(recommendations, list) and recommendations:
                st.markdown("**Recommendations**")
                for rec in recommendations:
                    st.markdown(f"- {rec}")
        elif st.session_state.verify_result:
            st.markdown("#### Kiroshi QA Verify")
            content = st.session_state.verify_result
            if isinstance(content, str):
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            st.markdown(content)
        if st.session_state.ask_result:
            st.markdown("#### Kiroshi Suggestions")
            st.markdown(st.session_state.ask_result)
        if st.session_state.ai_assist_result:
            st.markdown("#### AI Assistance")
            st.markdown(st.session_state.ai_assist_result)
        if st.session_state.ai_autocorrect_result:
            st.markdown("#### AI Autocorrection")
            st.markdown(st.session_state.ai_autocorrect_result)
        prog, miss = compute_progress(D, cat_map)
        if compact_mode:
            right = st.container()
            left = None
        else:
            left, right = st.columns([1, 2], gap="medium")
        with right:
            if compact_mode:
                st.caption(
                    "Compact mode active — documentation tables live in the Tables tab."
                )
            st.subheader("Build title")
            st.code(build_title(D))
            st.subheader("Progress by category")
            progress_df = pd.DataFrame(
                {"Category": list(prog.keys()), "Done": list(prog.values())}
            )
            bar_chart = (
                alt.Chart(progress_df)
                .mark_bar()
                .encode(
                    x=alt.X("Category:N", sort=list(prog.keys())),
                    y=alt.Y("Done:Q", scale=alt.Scale(domain=[0, 100])),
                )
            )
            render_responsive_altair_chart(bar_chart)
            todo = [
                f"**{c}** → {', '.join(flds)}" for c, flds in miss.items() if flds
            ]
            st.markdown("### To‑do" if todo else "All mandatory info filled.")
            for t in todo:
                st.markdown(f"- {t}")
            if compact_mode:
                top_left, top_right = st.columns(2, gap="medium")
                with top_left:
                    render_case_header_section(top_left, case_idx, True)
                with top_right:
                    render_description_and_internal_notes(top_right, True)
                bottom_left, bottom_right = st.columns(2, gap="medium")
                with bottom_left:
                    render_phonecall_section(bottom_left, True)
                with bottom_right:
                    render_conclusion_and_additional(bottom_right, True)
            else:
                with case_tab_shell(st) as case_shell:
                    render_case_header_section(case_shell, case_idx, False)
                    render_description_and_internal_notes(case_shell, False)
                    render_phonecall_section(case_shell, False)
                    render_conclusion_and_additional(case_shell, False)

    # ================== EMAIL TAB =================
    if tab_email:
        with case_tab(tab_email, case_idx=case_idx, slug=CASE_TAB_SLUGS["Email"]):
            email_tab_key = partial(case_widget_key, CASE_TAB_SLUGS["Email"], case_idx=case_idx)
            st.subheader("Email Prompt Generator")
            if st.session_state.email_type == "Custom Request":
                st.session_state.email_type = "Advanced Request"

            email_widget_key = email_tab_key("email_template")
            group_widget_key = email_tab_key("email_template_group")
            template_definitions = [
                {
                    "value": "Recap (Customer)",
                    "label": "Recap (Customer)",
                    "icon": "💌",
                    "description": "Warm recap with survey invitation and key actions.",
                    "group": "Customer follow-up",
                },
                {
                    "value": "Customer Reply",
                    "label": "Customer Reply",
                    "icon": "✉️",
                    "description": "Craft a confident response to an incoming customer email.",
                    "group": "Customer follow-up",
                },
                {
                    "value": "Last Call",
                    "label": "Last Call",
                    "icon": "⏳",
                    "description": "Progressive follow-up emails (1st reminder to final notice).",
                    "group": "Customer follow-up",
                },
                {
                    "value": "Broken Scanner",
                    "label": "Broken Scanner",
                    "icon": "🛠️",
                    "description": "Guide customers through scanner recovery and documentation steps.",
                    "group": "Hardware fixes",
                },
                {
                    "value": "Broken Tip",
                    "label": "Broken Tip",
                    "icon": "🧰",
                    "description": "Troubleshoot damaged or worn scanner tips with next actions.",
                    "group": "Hardware fixes",
                },
                {
                    "value": "AX Coordinator Email",
                    "label": "AX Coordinator Email",
                    "icon": "📅",
                    "description": "Align with coordinators using a ready-to-send internal brief.",
                    "group": "Internal sync",
                },
                {
                    "value": "FedEx Tracking Email",
                    "label": "FedEx Tracking Email",
                    "icon": "📦",
                    "description": "Share parcel tracking updates and expectations with customers.",
                    "group": "Internal sync",
                    "second_line_only": True,
                },
                {
                    "value": "Replacement Dispatch Request",
                    "label": "Replacement Dispatch Request",
                    "icon": "📬",
                    "description": "Confirm replacement shipments and return expectations with customers.",
                    "group": "Hardware fixes",
                },
                {
                    "value": "Replacement Wired Scanner Setup",
                    "label": "Replacement Wired Scanner Setup",
                    "icon": "🔄",
                    "description": "Send replacement install instructions for wired scanners.",
                    "group": "Hardware fixes",
                    "second_line_only": True,
                },
                {
                    "value": "Replacement Move+ Closure",
                    "label": "Replacement Move+ Closure",
                    "icon": "✅",
                    "description": "Close the loop on Move+ replacements with shipping details.",
                    "group": "Customer follow-up",
                    "second_line_only": True,
                },
                {
                    "value": "Callback Email",
                    "label": "Callback Email",
                    "icon": "📞",
                    "description": "Confirm scheduled callbacks and set expectations clearly.",
                    "group": "Internal sync",
                    "second_line_only": True,
                },
                {
                    "value": "Dell Escalation Email",
                    "label": "Dell Escalation Email",
                    "icon": "🚀",
                    "description": "Escalate urgent cases with crisp context and next steps.",
                    "group": "Internal sync",
                    "second_line_only": True,
                },
                {
                    "value": "Advanced Request",
                    "label": "Advanced Request",
                    "icon": "🧠",
                    "description": "Provide detailed guidance for complex, multi-step scenarios.",
                    "group": "Power tools",
                },
                {
                    "value": "Custom",
                    "label": "Custom",
                    "icon": "🎨",
                    "description": "Start from a blank canvas with your own tailored prompt.",
                    "group": "Power tools",
                },
            ]
            available_templates = [
                t
                for t in template_definitions
                if not t.get("second_line_only") or st.session_state.second_line_mode
            ]
            template_lookup = {t["value"]: t for t in available_templates}
            template_groups: Dict[str, List[Dict[str, str]]] = {}
            for t in available_templates:
                template_groups.setdefault(t["group"], []).append(t)
            ordered_groups = list(template_groups.keys())

            # maintain previously selected template if still available
            current_email_type = st.session_state.email_type
            if current_email_type not in template_lookup and ordered_groups:
                current_email_type = template_groups[ordered_groups[0]][0]["value"]
                st.session_state.email_type = current_email_type
            if (
                email_widget_key not in st.session_state
                or st.session_state[email_widget_key] not in template_lookup
            ):
                st.session_state[email_widget_key] = current_email_type

            st.markdown(
                """
                <style>
                    /* Email template group chips */
                    div[aria-label="Email template family"] > div {
                        display: flex;
                        flex-wrap: wrap;
                        gap: 0.5rem;
                        margin-bottom: 0.35rem;
                    }
                    div[aria-label="Email template family"] label {
                        border-radius: 999px;
                        padding: 0.35rem 0.95rem;
                        background: rgba(99, 102, 241, 0.12);
                        border: 1px solid rgba(99, 102, 241, 0.35);
                        color: #312e81;
                        font-weight: 600;
                        transition: all 0.2s ease;
                    }
                    div[aria-label="Email template family"] label > div {
                        display: flex;
                        align-items: center;
                        gap: 0.45rem;
                    }
                    div[aria-label="Email template family"] label > div > div:first-child {
                        display: none;
                    }
                    div[aria-label="Email template family"] label > div > div:last-child {
                        display: flex;
                        align-items: center;
                        gap: 0.45rem;
                    }
                    div[aria-label="Email template family"] label:hover {
                        background: rgba(99, 102, 241, 0.18);
                        border-color: rgba(79, 70, 229, 0.45);
                        color: #1e1b4b;
                    }
                    div[aria-label="Email template family"] label input {
                        display: none;
                    }
                    div[aria-label="Email template family"] label input:checked + div {
                        background: linear-gradient(135deg, rgba(79, 70, 229, 0.18), rgba(129, 140, 248, 0.32));
                        border: 1px solid rgba(79, 70, 229, 0.55);
                        color: #1e1b4b;
                        box-shadow: 0 10px 25px rgba(67, 56, 202, 0.18);
                    }

                    /* Email template card styling */
                    div[aria-label="Email template cards"] > div {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                        gap: 1rem;
                        margin: 0.75rem 0 0.25rem;
                    }
                    div[aria-label="Email template cards"] label {
                        margin: 0;
                    }
                    div[aria-label="Email template cards"] label > div {
                        border-radius: 18px;
                        border: 1px solid rgba(148, 163, 255, 0.28);
                        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(243, 244, 255, 0.92));
                        box-shadow: 0 18px 45px rgba(79, 70, 229, 0.12);
                        padding: 1.15rem 1.15rem 1rem;
                        transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
                        height: 100%;
                        position: relative;
                        overflow: hidden;
                    }
                    div[aria-label="Email template cards"] label:hover > div {
                        transform: translateY(-3px);
                        box-shadow: 0 24px 55px rgba(67, 56, 202, 0.22);
                        border-color: rgba(79, 70, 229, 0.45);
                    }
                    div[aria-label="Email template cards"] label input {
                        display: none;
                    }
                    div[aria-label="Email template cards"] label > div > div:first-child {
                        display: none;
                    }
                    div[aria-label="Email template cards"] label > div > div:last-child {
                        display: flex;
                        flex-direction: column;
                        gap: 0.45rem;
                        color: #1f2937;
                        font-weight: 600;
                        white-space: pre-line;
                        line-height: 1.35;
                        font-size: 0.99rem;
                    }
                    div[aria-label="Email template cards"] label > div::after {
                        content: "";
                        position: absolute;
                        inset: 0;
                        border-radius: 18px;
                        background: radial-gradient(circle at top left, rgba(129, 140, 248, 0.22), transparent 55%);
                        opacity: 0;
                        transition: opacity 0.25s ease;
                        pointer-events: none;
                    }
                    div[aria-label="Email template cards"] label input:checked + div {
                        border-color: rgba(79, 70, 229, 0.8);
                        box-shadow: 0 28px 65px rgba(55, 48, 163, 0.28);
                        background: linear-gradient(140deg, rgba(99, 102, 241, 0.22), rgba(129, 140, 248, 0.15));
                    }
                    div[aria-label="Email template cards"] label input:checked + div::after {
                        opacity: 1;
                    }
                    div[aria-label="Email template cards"] label input:checked + div > div:last-child {
                        color: #111827;
                    }
                    div[aria-label="Email template cards"] label small {
                        display: block;
                        font-weight: 400;
                        font-size: 0.86rem;
                        color: rgba(17, 24, 39, 0.78);
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )

            if not ordered_groups:
                st.warning("No email templates are available. Contact an administrator to restore them.")
                email_type = st.session_state[email_widget_key]
                st.session_state.email_type = email_type
            else:
                st.markdown("#### Choose an email starting point")
                st.caption(
                    "Pick a template family first, then dive into the specific prompt that best matches your outreach."
                )

                group_for_selection = next(
                    (
                        t["group"]
                        for t in available_templates
                        if t["value"] == st.session_state[email_widget_key]
                    ),
                    ordered_groups[0],
                )
                if group_for_selection not in ordered_groups:
                    group_for_selection = ordered_groups[0]

                selected_group = st.radio(
                    "Email template family",
                    ordered_groups,
                    index=ordered_groups.index(group_for_selection),
                    key=group_widget_key,
                    horizontal=True,
                )

                group_templates = template_groups.get(selected_group, [])
                template_values = [t["value"] for t in group_templates]
                if not template_values:
                    st.info("No email templates available in this category.")
                    email_type = st.session_state[email_widget_key]
                    st.session_state.email_type = email_type
                else:
                    if st.session_state[email_widget_key] not in template_values:
                        st.session_state[email_widget_key] = template_values[0]
                    option_text = {
                        value: f"{template_lookup[value]['icon']}  {template_lookup[value]['label']}\n• {template_lookup[value]['description']}"
                        for value in template_values
                    }
                    email_type = st.radio(
                        "Email template cards",
                        template_values,
                        key=email_widget_key,
                        label_visibility="collapsed",
                        format_func=lambda value: option_text.get(value, value),
                    )
                    st.session_state.email_type = email_type
            email_type = st.session_state.email_type
            ext = st.session_state.email_extra
    
            prompt = ""
            prompt_label = "ChatGPT prompt (copy & paste)"
            show_generation_options = True
            if email_type == "Last Call":
                st.markdown("#### Last Call Stage")

                # Initialize state for Last Call variables if not present
                lc_stage_key = case_widget_key("email_last_call", "stage", case_idx)
                lc_info_key = case_widget_key("email_last_call", "requested_info", case_idx)

                if lc_stage_key not in st.session_state:
                    st.session_state[lc_stage_key] = 1
                if lc_info_key not in st.session_state:
                    st.session_state[lc_info_key] = ""

                # UI Controls
                stage = st.radio(
                    "Select Last Call Stage",
                    [1, 2, 3],
                    format_func=lambda x: f"Last Call {x}",
                    key=lc_stage_key,
                    horizontal=True
                )

                requested_info = st.text_input(
                    "Requested information",
                    key=lc_info_key,
                    placeholder="e.g. proof of purchase, scanner serial number, etc."
                )

                # Build Prompt
                intro = build_email_intro(D)
                info_text = requested_info.strip() or "[Requested Information]"

                if stage == 1:
                    instruction = (
                        f"Draft a friendly follow-up email. Mention that we tried to contact them "
                        f"or are waiting for the following information to continue assistance: {info_text}."
                    )
                elif stage == 2:
                    instruction = (
                        f"Draft a follow-up email. Warn that the case will be closed after 3 unsuccessful attempts. "
                        f"Remind them we are waiting for: {info_text}."
                    )
                else:  # stage == 3
                    instruction = (
                        f"Draft a final follow-up email. State that this is the last notice. "
                        f"Instruct them to call us back directly with the case number and the following required "
                        f"information to continue assistance: {info_text}."
                    )

                prompt = (
                    f"You are a professional support agent. {instruction}\n"
                    f"Start the email with:\n{intro}\n"
                    "Ensure the tone corresponds to the urgency of the stage (Friendly -> Warning -> Final).\n"
                    "Return only the email body."
                )

            elif email_type == "Recap (Customer)":
                intro = build_email_intro(D)
                steps_summary = "\n".join(D.remote_steps.splitlines()) or "—"
                recommendation_key = email_tab_key("recap_recommendation")
                auto_recommendation = _derive_recap_recommendation(D)
                existing_recommendation = (ext.get("recap_recommendation", "") or "").strip()
                if not existing_recommendation:
                    existing_recommendation = auto_recommendation
                    ext["recap_recommendation"] = existing_recommendation
                st.session_state.setdefault(recommendation_key, existing_recommendation)
                recommendation_value = st.text_input(
                    "Recommendation for the recap email",
                    existing_recommendation,
                    help="Required for recap emails. Suggest a simple next step or helpful resource for the customer.",
                    key=recommendation_key,
                    placeholder="e.g., Run Windows Update, restart the PC, and retry the scan.",
                )
                recommendation_value = recommendation_value.strip()
                if not recommendation_value:
                    recommendation_value = auto_recommendation
                ext["recap_recommendation"] = recommendation_value
                recap_recommendation = ext["recap_recommendation"]
                prompt = f"""You are a friendly IT‑support agent. Draft an engaging, upbeat email (≤180 words) that recaps the case and strongly
        motivates the customer to complete a brief satisfaction survey (takes <2 minutes) to help improve our service.
        Start the email exactly with the following lines (do not paraphrase or omit them):
        {intro}
        Include: Case ID, a brief summary of what happened, and the solution.
        Use a warm tone, thank the customer for their time, invite further questions, and end with a clear call‑to‑action to the survey.
        Always include this simple recommendation for the customer: {recap_recommendation}
        Apply persuasive techniques: personalize with the customer's name, show appreciation (reciprocity), mention that other customers found the survey quick and helpful (social proof), emphasise how their feedback shapes future support, and invite them to help improve our service (commitment).

        Return only the email body.

        DATA:
        Case ID: {D.case_id}
        Summary: {D.brief_description}
        Steps taken:
        {steps_summary}
        Solution: {D.solution}
        Survey link: {D.survey_link}"""
            elif email_type == "Customer Reply":
                st.markdown("#### Customer email context")
                ext["reply_original"] = st.text_area(
                    "Original customer email",
                    ext.get("reply_original", ""),
                    height=240,
                    key=email_tab_key("reply_original"),
                )
                ext["reply_focus"] = st.text_area(
                    "What should we address in the reply?",
                    ext.get("reply_focus", ""),
                    height=140,
                    key=email_tab_key("reply_focus"),
                )
                case_snapshot = {
                    "case_id": D.case_id,
                    "company": D.company_name,
                    "brief_description": D.brief_description,
                    "solution": D.solution,
                    "remote_steps": D.remote_steps,
                    "root_cause": D.root_cause,
                    "additional_info": D.additional_info,
                }
                prompt = (
                    "You are responding to a customer's email about an active support case. "
                    "Write a concise, confident reply that acknowledges their message, addresses each concern, "
                    "and clarifies next actions. Use a friendly professional tone.\n\n"
                    f"Original email:\n{ext.get('reply_original', 'No email provided.')}\n\n"
                    f"Response notes (internal guidance):\n{ext.get('reply_focus', 'Acknowledge receipt and provide an update.')}\n\n"
                    "Case context:\n"
                    f"{json.dumps(case_snapshot, indent=2, ensure_ascii=False)}\n\n"
                    "Return only the email body with a clear closing and invitation for further questions."
                )
            elif email_type == "Broken Scanner":
                st.markdown("#### Incident questionnaire (prefill if known)")
                ext["experience"] = st.text_input(
                    "Experience level (new / experienced)",
                    ext.get("experience", ""),
                    key=case_widget_key("email_broken_scanner", "experience", case_idx),
                )
                st.info(
                    "Fill in internal notes, conclusion, additional information, and support fee details "
                    "from the Case tab."
                )
                st.markdown("---")
                st.download_button(
                    "Download PDF",
                    make_pdf(D, cat_map),
                    file_name=f"{D.case_id or 'case'}.pdf",
                    mime="application/pdf",
                    key=email_tab_key("download_pdf"),
                )
            if not compact_mode and left is not None:
                with left:
                    st.subheader("Documentation Preview – Copy‑friendly Tables")
                    st.caption(
                        "Hotkeys: Ctrl+Alt+1 copies the Build Title, 2 copies Description, 3 copies Phonecall, 4 copies "
                        "Internal Notes, 5 copies Remote Session, 6 copies Additional Information, 7 copies Root Cause & "
                        "Conclusion, 8 copies the ChatGPT prompt (Email tab), and Ctrl+Alt+C still grabs every table. Flip "
                        "the “Use this case for global clipboard hotkeys” toggle in the Tables tab when you want these "
                        "shortcuts to pull from a different case. The listener keeps running even when Kiroshi is in the "
                        "background so you can paste with Ctrl+V directly into your CRM or spreadsheet."
                    )
                    for cat in cat_map:
                        title_text = table_title(cat)
                        st.markdown(f"**{title_text}**")

                        copy_suffix_raw = f"{case_idx}_{cat}".lower()
                        copy_suffix = re.sub(r"[^0-9a-z]+", "", copy_suffix_raw)
                        if not copy_suffix:
                            copy_suffix = "copy"
                        if copy_suffix[0].isdigit():
                            copy_suffix = f"a{copy_suffix}"

                        title_payload = script_safe_json(title_text)
                        table_payload = script_safe_json(table_plain_text(cat, D, cat_map))
                        components.html(
                            f"""
                            <div style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center;margin-bottom:0.35rem;">
                                <button onclick=\"copyTitle{copy_suffix}()\"
                                        style=\"padding:0.35rem 0.75rem;border-radius:0.4rem;border:1px solid #ccc;background:#f8f9fa;cursor:pointer;\">
                                    Copy title
                                </button>
                                <button onclick=\"copyTable{copy_suffix}()\"
                                        style=\"padding:0.35rem 0.75rem;border-radius:0.4rem;border:1px solid #ccc;background:#f8f9fa;cursor:pointer;\">
                                    Copy table
                                </button>
                                <span id=\"feedback-{copy_suffix}\" style=\"font-size:0.75rem;color:#4CAF50;\"></span>
                            </div>
                            <script>
                                const feedbackElem{copy_suffix} = document.getElementById('feedback-{copy_suffix}');
                                function showFeedback{copy_suffix}(message) {{
                                    if (!feedbackElem{copy_suffix}) return;
                                    feedbackElem{copy_suffix}.textContent = message;
                                    setTimeout(() => {{
                                        if (feedbackElem{copy_suffix}.textContent === message) {{
                                            feedbackElem{copy_suffix}.textContent = '';
                                        }}
                                    }}, 2000);
                                }}
                                function copyTitle{copy_suffix}() {{
                                    navigator.clipboard.writeText({title_payload}).then(() => {{
                                        showFeedback{copy_suffix}('Title copied');
                                    }});
                                }}
                                function copyTable{copy_suffix}() {{
                                    navigator.clipboard.writeText({table_payload}).then(() => {{
                                        showFeedback{copy_suffix}('Table copied');
                                    }});
                                }}
                            </script>
                            """,
                            height=80,
                        )
                        st.dataframe(
                            category_dataframe(cat, D, cat_map), width="stretch"
                        )
                    st.markdown("---")
                if st.session_state.categorizer_result:
                    st.subheader("Kiroshi Categorizer")
                    st.markdown(st.session_state.categorizer_result)
                    if not st.session_state.get("categorizer_summary"):
                        st.session_state.categorizer_summary = parse_categorizer_summary(
                            st.session_state.categorizer_result
                        )

            if email_type == "Broken Tip":
                st.markdown("#### Damaged tip questionnaire")
                ext["times_autoclaved"] = st.text_input(
                    "Times autoclaved",
                    ext.get("times_autoclaved", ""),
                    key=case_widget_key("email_broken_tip", "times_autoclaved", case_idx),
                )
                ext["bath_number"] = st.text_input(
                    "Bath number",
                    ext.get("bath_number", ""),
                    key=case_widget_key("email_broken_tip", "bath_number", case_idx),
                )
                ext["model"] = st.text_input(
                    "Autoclave model",
                    ext.get("model", ""),
                    key=case_widget_key("email_broken_tip", "model", case_idx),
                )
                ext["program"] = st.text_input(
                    "Program used",
                    ext.get("program", ""),
                    key=case_widget_key("email_broken_tip", "program", case_idx),
                )
                ext["airtight"] = st.text_input(
                    "Autoclaved in airtight pouch?",
                    ext.get("airtight", ""),
                    key=case_widget_key("email_broken_tip", "airtight", case_idx),
                )
                ext["other"] = st.text_input(
                    "Other info",
                    ext.get("other", ""),
                    key=case_widget_key("email_broken_tip", "other", case_idx),
                )

                intro = build_email_intro(D)
                prompt = f"""Draft a courteous e‑mail requesting the following information about the damaged tip.
Start the email with:
{intro}
List each question and provide any known answer beneath it, ready for the customer to correct/confirm.

1. Times autoclaved – {ext.get('times_autoclaved', '')}
2. Bath number – {ext.get('bath_number', '')}
3. Autoclave model – {ext.get('model', '')}
4. Program used – {ext.get('program', '')}
5. Autoclaved in airtight pouch? – {ext.get('airtight', '')}
6. Other info – {ext.get('other', '')}
"""

            elif email_type == "AX Coordinator Email":
                st.subheader("AX Coordinators")
                st.text_area(
                    "Request / Issue",
                    D.description,
                    disabled=True,
                    key=email_tab_key("request_issue"),
                )
                D.request_issue = D.description
                D.contact_name = D.caller_name
                st.text_input(
                    "Contact name",
                    D.contact_name,
                    disabled=True,
                    key=case_widget_key("email_ax_coordinator", "contact_name", case_idx),
                )
                D.office_ph = D.phone_number
                st.text_input(
                    "Office phone",
                    D.office_ph,
                    disabled=True,
                    key=case_widget_key("email_ax_coordinator", "office_phone", case_idx),
                )
                D.direct_ph = D.phone_number
                st.text_input(
                    "Direct phone",
                    D.direct_ph,
                    disabled=True,
                    key=case_widget_key("email_ax_coordinator", "direct_phone", case_idx),
                )
                best_cb = st.toggle(
                    "Specify best call-back time",
                    D.best_time not in ("", "ASAP"),
                    key=email_tab_key("best_cb"),
                )
                best_time_key = email_tab_key("best_time")
                if best_cb:
                    default_best_time = (
                        D.best_time if D.best_time not in ("", "ASAP") else ""
                    )
                    D.best_time = st.text_input(
                        "Best call-back time",
                        default_best_time,
                        key=best_time_key,
                    )
                else:
                    D.best_time = "ASAP"
                    if best_time_key in st.session_state:
                        st.session_state.pop(best_time_key)

                company = D.company_name or "N/A"
                case_no = D.case_id or "N/A"
                contact = D.contact_name or "N/A"
                office_phone = D.office_ph or "N/A"
                direct_phone = D.direct_ph or "N/A"
                best_time = D.best_time or "N/A"
                request_issue = D.request_issue or "N/A"
                prompt = (
                    "Draft an internal email to the AX coordinators summarizing the case.\n"
                    "Include the following details in a concise bulleted list so they can schedule support:"
                    f"\n• Case ID: {case_no}"
                    f"\n• Company: {company}"
                    f"\n• Request / Issue: {request_issue}"
                    f"\n• Contact name: {contact}"
                    f"\n• Office phone: {office_phone}"
                    f"\n• Direct phone: {direct_phone}"
                    f"\n• Best call-back time: {best_time}"
                    "\nEnd the email thanking them for their assistance."
                )

            elif email_type == "FedEx Tracking Email":
                st.markdown("#### FedEx tracking options")
                ext["agent_name"] = st.text_input(
                    "Agent name",
                    ext.get("agent_name", ""),
                    key=case_widget_key("email_fedex_tracking", "agent_name", case_idx),
                )
                ext["device_type"] = st.text_input(
                    "Device type (scanner or Move+)",
                    ext.get("device_type", ""),
                    key=case_widget_key("email_fedex_tracking", "device_type", case_idx),
                )
                ext["tracking_number"] = st.text_input(
                    "FedEx tracking number",
                    ext.get("tracking_number", ""),
                    key=case_widget_key("email_fedex_tracking", "tracking_number", case_idx),
                )
                customer = D.caller_name or "(Caller Name)"
                company = D.company_name or "(Company Name)"
                agent = ext["agent_name"] or "(Agent Name)"
                case_no = D.case_id or "(Case ID)"
                issue = D.brief_description or "(Issue Description)"
                device = ext["device_type"] or "device"
                tracking = ext["tracking_number"] or "(Tracking Number)"
                email_text = f"""Dear {customer} from {company},

I hope you are having an excellent day! This is {agent} from 3Shape support regarding your case {case_no} about {issue}.

I am more than happy to inform you that we have created a ticket to send you a refurbished unit through FedEx which you can track by using the following tracking number: {tracking}.

Remember that this process will not have a cost.

Please also remember to send us back the faulty {device} using the shipping label you will find in the box. Please be informed that if we do not receive the faulty scanner within 32 days of your receipt of the new device, your TRIOS licenses will expire.

Wishing you the best again!"""
                st.text_area(
                    "Email",
                    email_text,
                    height=300,
                    key=email_tab_key("generated_email"),
                )

            elif email_type == "Replacement Dispatch Request":
                st.markdown("#### Replacement dispatch options")
                ext["agent_name"] = st.text_input(
                    "Agent name",
                    ext.get("agent_name", ""),
                    key=case_widget_key("email_replacement_dispatch", "agent_name", case_idx),
                )
                device_options = ["TRIOS", "Pod", "Spare item"]
                prev_choice = ext.get("replacement_device_type", device_options[0])
                default_index = (
                    device_options.index(prev_choice)
                    if prev_choice in device_options
                    else 0
                )
                selected_device = st.selectbox(
                    "Replacement device type",
                    device_options,
                    index=default_index,
                    key=case_widget_key(
                        "email_replacement_dispatch", "device_type", case_idx
                    ),
                )
                ext["replacement_device_type"] = selected_device
                default_serial_map = {
                    "TRIOS": D.scanner_sn or "",
                    "Pod": D.base_sn or "",
                    "Spare item": ext.get("serial_number", ""),
                }
                if prev_choice != selected_device:
                    prev_default = default_serial_map.get(prev_choice, "")
                    current_serial = ext.get("serial_number", "")
                    if current_serial in ("", prev_default):
                        ext["serial_number"] = default_serial_map.get(
                            selected_device, ""
                        )
                spare_item_name = ext.get("spare_item_name", "")
                spare_return_required = True
                if selected_device == "Spare item":
                    spare_item_name = st.text_input(
                        "Spare item description",
                        spare_item_name,
                        key=case_widget_key(
                            "email_replacement_dispatch", "spare_item", case_idx
                        ),
                    )
                    ext["spare_item_name"] = spare_item_name
                    toggle_default = ext.get("spare_return_required")
                    if toggle_default is None:
                        toggle_default = False
                    spare_return_required = st.toggle(
                        "Return of spare item required?",
                        value=bool(toggle_default),
                        key=case_widget_key(
                            "email_replacement_dispatch", "spare_return", case_idx
                        ),
                    )
                    ext["spare_return_required"] = spare_return_required
                else:
                    ext["spare_return_required"] = True
                    ext["spare_item_name"] = spare_item_name
                serial_placeholder = ext.get("serial_number", "")
                if not serial_placeholder:
                    serial_placeholder = default_serial_map.get(selected_device, "")
                ext["serial_number"] = st.text_input(
                    "Serial number of the device being replaced",
                    serial_placeholder,
                    key=case_widget_key(
                        "email_replacement_dispatch", "serial_number", case_idx
                    ),
                )
                intro = build_email_intro(D)
                agent = ext["agent_name"] or "(Agent Name)"
                issue = D.brief_description or "the reported hardware issue"
                serial_number = ext.get("serial_number", "").strip() or "(Serial number)"
                if selected_device == "TRIOS":
                    device_label = "TRIOS scanner"
                elif selected_device == "Pod":
                    device_label = "TRIOS Pod/base unit"
                else:
                    device_label = spare_item_name.strip() or "spare item"
                return_required = (
                    spare_return_required if selected_device == "Spare item" else True
                )

                hardware_lines: list[str] = []

                def _add_hardware_line(label: str, value: object) -> None:
                    if isinstance(value, str):
                        cleaned = value.strip()
                        if cleaned:
                            hardware_lines.append(f"- {label}: {cleaned}")
                        return
                    if isinstance(value, (int, float)) and value:
                        hardware_lines.append(f"- {label}: {value}")

                _add_hardware_line("Scanner serial", D.scanner_sn)
                _add_hardware_line("Base serial", D.base_sn)
                _add_hardware_line("TRIOS module version", D.trios_module_version)
                _add_hardware_line("Dongle deployment date", D.dongle_deployment_date)
                _add_hardware_line(
                    "Previous replacements", D.scanner_previous_replacements
                )
                _add_hardware_line("Damage classification", D.scanner_accidental_damage)
                _add_hardware_line("Hardware test", D.hardware_test)
                _add_hardware_line("PC service tag", D.service_tag)
                _add_hardware_line("PC model", D.pc_model)
                _add_hardware_line("Windows version", D.windows_version)
                _add_hardware_line("BIOS version", D.bios_version)
                _add_hardware_line("Graphics card", D.graphics_card)
                _add_hardware_line("Processor", D.processor)
                _add_hardware_line("Warranty", D.warranty)

                hardware_section = ""
                if hardware_lines:
                    hardware_section = (
                        "Here are the hardware details we currently have on file:\n"
                        + "\n".join(hardware_lines)
                    )

                tracking_line = (
                    "We will send you the Tracking # for the shipment as soon as it becomes available."
                )
                if return_required:
                    return_paragraph = (
                        "Please keep the shipping box from the replacement delivery. "
                        "Once the new unit arrives, place the faulty device in that same packaging and seal it with the enclosed return label. "
                        "You will have 30 days to return the device to 3Shape using the provided label; after that period, the TRIOS licenses associated with the clinic will be suspended."
                    )
                else:
                    return_paragraph = (
                        "Because this is a spare component, a return shipment is not required. You may keep the existing part for your records, and no return label or 30-day deadline applies in this case."
                    )

                paragraphs = [
                    (
                        "We completed our hardware review and determined that replacing your "
                        f"{device_label} is necessary to resolve {issue}."
                    ),
                    f"The serial number of the unit we are exchanging is {serial_number}.",
                    tracking_line,
                    return_paragraph,
                ]
                if hardware_section:
                    paragraphs.append(hardware_section)
                body = "\n\n".join(paragraphs)
                closing = (
                    "Please let me know if anything changes or if you need further assistance."
                    f"\n\nBest regards,\n{agent}\n3Shape Support"
                )
                email_text = f"{intro}\n{body}\n\n{closing}"
                st.text_area(
                    "Email",
                    email_text,
                    height=420,
                    key=email_tab_key("generated_email"),
                )

            elif email_type == "Replacement Wired Scanner Setup":
                st.markdown("#### Replacement scanner options")
                ext["agent_name"] = st.text_input(
                    "Agent name",
                    ext.get("agent_name", ""),
                    key=case_widget_key("email_replacement_wired", "agent_name", case_idx),
                )
                ext["fedex_pickup_link"] = st.text_input(
                    "FedEx pickup link",
                    ext.get(
                        "fedex_pickup_link",
                        "https://www.fedex.com/en-us/shipping/schedule-manage-pickups.html",
                    ),
                    key=case_widget_key("email_replacement_wired", "fedex_pickup_link", case_idx),
                )
                customer = D.caller_name or "(Caller Name)"
                company = D.company_name or "(Company Name)"
                agent = ext["agent_name"] or "(Agent Name)"
                case_no = D.case_id or "(Case ID)"
                survey = D.survey_link or "(Survey URL)"
                pickup = ext["fedex_pickup_link"] or "(FedEx pickup link)"
                email_text = f"""Dear {customer} from {company},

I hope you are having an excellent day! This is {agent} from 3Shape Support regarding your case {case_no}.

I am more than happy to inform you that your issue has been resolved. According to the tracking information provided from FedEx, the refurbished scanner was already received by the office.

Regarding the installation of the scanner provided, please follow these steps:

1. Open 3Shape UNITE (please remember to log in with your user credentials).
2. In the upper section of the screen, look for the MORE icon and click on it.
3. In the menu that appears, click Settings (gear icon).
4. On the left menu, click TRIOS (scanner/wand icon).
5. In the submenu, click Scanner Management.
6. Click Add new scanner (either the large white tile in the middle or the button in the upper-right corner).
7. Select Wired scanner.
8. Connect the scanner as displayed on screen. Remember: the Pod/stand of the scanner must be connected from both sides, and the scanner itself must also be connected to the PC.
9. The scanner will then be recognized by the app and will be ready to work.

Thank you so much for letting me assist you. I would really appreciate it if you could provide feedback regarding my service today: {survey}

In case you need further assistance or have any doubts, please do not hesitate to contact our technical support team.

Please remember to send us back the faulty scanner using the shipping label included in the box. If we do not receive the faulty scanner within 32 days from when we sent the replacement device, your TRIOS licenses will expire.

You may schedule a pickup with FedEx here: {pickup}

Wishing you the best again!"""
                st.text_area(
                    "Email",
                    email_text,
                    height=400,
                    key=email_tab_key("generated_email"),
                )

            elif email_type == "Replacement Move+ Closure":
                st.markdown("#### Replacement Move+ options")
                ext["agent_name"] = st.text_input(
                    "Agent name",
                    ext.get("agent_name", ""),
                    key=case_widget_key("email_replacement_move", "agent_name", case_idx),
                )
                customer = D.caller_name or "(Caller Name)"
                company = D.company_name or "(Company Name)"
                agent = ext["agent_name"] or "(Agent Name)"
                case_no = D.case_id or "(Case ID)"
                survey = D.survey_link or "(Survey URL)"
                email_text = f"""Dear {customer} from {company},

I hope you are having an excellent day! This is {agent} from 3Shape Support regarding your case: {case_no}.

I am more than happy to inform you that your issue has been resolved. According to the tracking information provided from FedEx, the refurbished device was already received by the office.

Thank you so much for letting me assist you. I would really appreciate if you can provide me with some feedback regarding my service today in the next survey.

In case you need further assistance or have any doubts, please do not hesitate to contact our technical support team.

Please remember to send us back the faulty scanner using the shipping label you will find in the box. Please be informed that if we do not receive the faulty scanner within 32 days since we sent the device, your TRIOS licenses will expire. You may schedule a pickup with FedEx by following the next link: https://www.fedex.com/en-us/shipping/schedule-manage-pickups.html

We sincerely appreciate your patience and understanding throughout this process. Also, if you have the time, it would be helpful if you could complete our Customer Experience Survey so that we know how our assistance and services were for you.

Do remember that 10 would be the highest score to rate the following survey: {survey}

Wishing you the best again!"""
                st.text_area(
                    "Email",
                    email_text,
                    height=400,
                    key=email_tab_key("generated_email"),
                )

            elif email_type == "Callback Email":
                st.markdown("#### Callback email options")
                cb_remote_key = email_tab_key("callback_remote")
                cb_remote = st.toggle(
                    "Need remote session?",
                    st.session_state.get(cb_remote_key, False),
                    key=cb_remote_key,
                )
                cb_remote_text_key = email_tab_key("callback_remote_text")
                if cb_remote:
                    st.text_area(
                        "Remote session details",
                        st.session_state.get(cb_remote_text_key, ""),
                        key=cb_remote_text_key,
                    )
                cb_contact_key = email_tab_key("callback_contact")
                st.toggle(
                    "Need contact information?",
                    st.session_state.get(cb_contact_key, False),
                    key=cb_contact_key,
                )
                cb_clarify_key = email_tab_key("callback_clarify")
                st.toggle(
                    "Need to clarify what happened?",
                    st.session_state.get(cb_clarify_key, False),
                    key=cb_clarify_key,
                )
                cb_needed_key = email_tab_key("callback_needed")
                st.toggle(
                    "Callback needed?",
                    st.session_state.get(cb_needed_key, True),
                    key=cb_needed_key,
                )
                cb_address_key = email_tab_key("callback_address")
                cb_address = st.toggle(
                    "Request address?",
                    st.session_state.get(cb_address_key, False),
                    key=cb_address_key,
                )
                if cb_address:
                    cb_equipment_key = email_tab_key("callback_equipment")
                    st.text_input(
                        "Equipment to replace",
                        st.session_state.get(cb_equipment_key, ""),
                        key=cb_equipment_key,
                    )

                intro = build_email_intro(D)
                if cb_address:
                    equip = st.session_state.get(cb_equipment_key, "") or "(equipment)"
                    prompt = f"""Draft a polite email asking the customer to confirm their shipping address so we can send a {equip}.
Start the email with:
{intro}
List the following fields for them to fill in:
Address (include suite if any)
City
State
Zip Code/Postal Code
Full name of the recipient
Best phone number to contact the recipient
Email to contact the recipient

End with: We look forward to your reply."""
                else:
                    if st.session_state.get(cb_needed_key, True):
                        base_request = (
                            "provide us with the best time for a callback, including your time zone, "
                            "or alternatively the TeamViewer ID and password so we may connect directly to the computer."
                        )
                    else:
                        base_request = (
                            "provide us with the TeamViewer ID and password so we may connect directly to the computer."
                        )
                    prompt = (
                        f"Draft a polite email asking the customer to {base_request}\n"
                        f"Start the email with:\n{intro}\n"
                        "End with: We look forward to your reply."
                    )
                    extras = []
                    if st.session_state.get(cb_contact_key):
                        extras.append("Ask them to provide their contact information.")
                    if st.session_state.get(cb_clarify_key):
                        extras.append("Ask them to clarify what happened.")
                    if (
                        st.session_state.get(cb_remote_key)
                        and st.session_state.get(cb_remote_text_key, "").strip()
                    ):
                        extras.append(
                            "Include the following additional details:\n"
                            + st.session_state.get(cb_remote_text_key, "").strip()
                        )
                    if extras:
                        prompt += "\n\n" + "\n".join(extras)
            elif email_type == "Dell Escalation Email":
                st.markdown("#### Dell escalation data preview")
                st.info(
                    "Update the Dell escalation section in the Escalations tab to refresh this template."
                )
                st.dataframe(
                    dell_escalation_dataframe(D), width="stretch"
                )
                email_text = build_dell_escalation_email(D)
                st.text_area(
                    "Email",
                    email_text,
                    height=600,
                    key=email_tab_key("generated_email"),
                )

            elif email_type == "Advanced Request":
                st.markdown("#### Custom email options")
                ext["reason"] = st.text_input(
                    "Reason for contacting the customer",
                    ext.get("reason", ""),
                    key=case_widget_key("email_advanced_request", "reason", case_idx),
                )
                ext["goal"] = st.text_input(
                    "Goal of the email",
                    ext.get("goal", ""),
                    key=case_widget_key("email_advanced_request", "goal", case_idx),
                )
                ext["customer_need"] = st.text_input(
                    "What do we need from the customer?",
                    ext.get("customer_need", ""),
                    key=case_widget_key("email_advanced_request", "customer_need", case_idx),
                )
                intro = build_email_intro(D)
                reason = ext.get("reason", "").strip() or "(reason for the outreach)"
                goal = ext.get("goal", "").strip() or "(goal of the email)"
                customer_need = (
                    ext.get("customer_need", "").strip()
                    or "(what we need from the customer)"
                )
                prompt = (
                    "You are a friendly and professional IT-support specialist.\n"
                    "Draft a concise e-mail (≤180 words) tailored for the customer.\n"
                    "Start the e-mail exactly with the lines below (do not paraphrase):\n"
                    f"{intro}\n"
                    f"Explain you are contacting them because {reason}.\n"
                    f"State that the goal of the email is {goal}.\n"
                    f"Clearly ask the customer for {customer_need}.\n"
                    "Close by inviting them to reply if they have any questions or need further assistance."
                )
                pat_cb_key = email_tab_key("pat_cb")
                pat_cb = st.toggle(
                    "Include Patterson legacy #",
                    value=st.session_state.get(pat_cb_key, False),
                    key=pat_cb_key,
                )
                if pat_cb:
                    auto_text_input(
                        "Patterson legacy #",
                        "patterson",
                    )
                else:
                    D.patterson = "N/A"
                    touch_case_last_modified()
                    autosave()
                if st.session_state.second_line_mode:
                    st.text_input(
                        "Straumann ticket #",
                        D.straumann,
                        disabled=True,
                        key=email_tab_key("straumann_tab"),
                    )
                else:
                    D.straumann = "N/A"
                    touch_case_last_modified()
                    autosave()
            elif email_type == "Custom":
                st.markdown("#### Custom prompt builder")
                ext["custom_user_prompt"] = st.text_area(
                    "User instructions",
                    ext.get("custom_user_prompt", ""),
                    height=140,
                    key=email_tab_key("custom_user_prompt"),
                )
                case_context = build_case_data_block(D)
                st.text_area(
                    "Case data provided by Kiroshi",
                    case_context,
                    height=220,
                    key=email_tab_key("custom_case_context"),
                    disabled=True,
                )
                user_prompt = ext.get("custom_user_prompt", "").strip()
                prompt_intro = "CASE DATA (auto-collected by Kiroshi):\n"
                prompt = (
                    f"{user_prompt}\n\n{prompt_intro}{case_context}"
                    if user_prompt
                    else f"{prompt_intro}{case_context}"
                )
                prompt_label = "Custom prompt (copy & paste)"
            st.session_state.email_extra = ext
            static_templates = {
                "FedEx Tracking Email",
                "Replacement Dispatch Request",
                "Replacement Wired Scanner Setup",
                "Replacement Move+ Closure",
                "Dell Escalation Email",
            }
            generated_email_key = email_tab_key("generated_email_output")
            if generated_email_key not in st.session_state:
                st.session_state[generated_email_key] = st.session_state.get(
                    "generated_email", ""
                )

            if email_type not in static_templates:
                # Calculate hash of the generated prompt to detect changes from inputs
                prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()
                prompt_hash_key = email_tab_key("api_prompt_hash")
                prompt_widget_key = email_tab_key("api_prompt_area")

                # If the generated prompt changed (e.g. inputs changed), update the widget state
                if st.session_state.get(prompt_hash_key) != prompt_hash:
                    st.session_state[prompt_widget_key] = prompt
                    st.session_state[prompt_hash_key] = prompt_hash

                # Render the text area, which will use the updated session state value
                user_content = st.text_area(
                    prompt_label,
                    value=prompt, # Fallback, though session state takes precedence if key exists
                    height=300,
                    key=prompt_widget_key,
                )

                # Update global last_prompt with what is actually in the box (allowing user edits)
                st.session_state["last_prompt"] = user_content

                helpjuice_toggle_key = email_tab_key("api_helpjuice")
                include_helpjuice = st.toggle(
                    "Helpjuice tutorial",
                    value=st.session_state.get(helpjuice_toggle_key, False),
                    key=helpjuice_toggle_key,
                )
                restart_toggle_key = email_tab_key("api_restart")
                include_restart = st.toggle(
                    "Restart the computer",
                    value=st.session_state.get(restart_toggle_key, False),
                    key=restart_toggle_key,
                )
                scan_time_toggle_key = email_tab_key("api_scan_time")
                include_scan_time = st.toggle(
                    "Scan time warning",
                    value=st.session_state.get(scan_time_toggle_key, False),
                    key=scan_time_toggle_key,
                )
                if st.button(
                    "Use GPT-OSS",
                    key=email_tab_key("use_gpt"),
                    help="Generate an email draft using the configured AI model based on your prompt.",
                ):
                    api_key = st.session_state.openai_api_key
                    model = st.session_state.openai_model
                    base_url = st.session_state.ai_base_url
                    if not api_key and base_url.startswith("https://api.openai.com"):
                        st.error("Please set your OpenAI API key in the Debug tab.")
                    elif not user_content.strip():
                        st.error("Prompt is empty.")
                    else:
                        with case_loading_overlay("Syncing with GPT-OSS intelligence…"):
                            try:
                                augmented_prompt = user_content
                                extras = []
                                if include_helpjuice:
                                    link = D.internal_helpjuice or "https://helpjuice.com"
                                    extras.append(
                                        f"Include a sentence pointing the customer to this Help Center tutorial that may address the root cause: {link}."
                                    )
                                if include_restart:
                                    extras.append(
                                        "And recommend to the customer to restart the computer after the end of every shift."
                                    )
                                if include_scan_time:
                                    extras.append(
                                        "Educate the customer that scans over 2500 frames may cause case corruption and data loss, so they should stop scanning once notified."
                                    )
                                if extras:
                                    augmented_prompt += "\n\n" + "\n".join(extras)
                                reply = invoke_gpt(
                                    augmented_prompt,
                                    st.session_state.kiroshi_chat_history,
                                    api_key,
                                    model,
                                    base_url,
                                    source="gpt_oss_email",
                                )
                            except Exception as e:
                                logging.error("GPT-OSS email generation failed: %s", e)
                                st.error(str(e))
                            else:
                                st.session_state.kiroshi_chat_history.append({"role": "user", "content": augmented_prompt})
                                st.session_state.kiroshi_chat_history.append({"role": "assistant", "content": reply})
                                save_memory(st.session_state.kiroshi_chat_history)
                                st.session_state.generated_email = reply
                                st.session_state[generated_email_key] = reply
            st.session_state.generated_email = st.text_area(
                "Generated Email",
                height=300,
                key=generated_email_key,
            )

    # ================== TRACKING TAB =================
    if tab_tracking:
        with case_tab(tab_tracking, case_idx=case_idx, slug=CASE_TAB_SLUGS["Tracking"]):
            tracking_tab_key = partial(
                case_widget_key, CASE_TAB_SLUGS["Tracking"], case_idx=case_idx
            )
            st.subheader("Tracking")
            ensure_tracking_session_defaults(case_idx, D.tracking)
            tracking_type_key = tracking_tab_key("tracking_type")
            tracking_type = st.selectbox(
                "Tracking type",
                ["Dell", "FedEx", "Custom"],
                key=tracking_type_key,
            )

            st.text_input(
                "Case ID",
                value=D.case_id,
                disabled=True,
                key=case_widget_key("tracking", "case_id", case_idx),
            )
            st.text_input(
                "Company",
                value=D.company_name,
                disabled=True,
                key=case_widget_key("tracking", "company", case_idx),
            )
            end_user_value = D.contact_name or D.caller_name or ""
            st.text_input(
                "End User",
                value=end_user_value,
                disabled=True,
                key=case_widget_key("tracking", "end_user", case_idx),
            )
            phone_value = (
                D.phone_number or D.office_ph or D.direct_ph or ""
            )
            st.text_input(
                "Phone",
                value=phone_value,
                disabled=True,
                key=case_widget_key("tracking", "phone", case_idx),
            )
            created_display = format_tracking_date(D.tracking.creation_day)
            if not created_display:
                created_display = datetime.now().strftime("%Y-%m-%d")
            st.text_input(
                "Created",
                value=created_display,
                disabled=True,
                key=case_widget_key("tracking", "created", case_idx),
            )

            ticket_key = tracking_tab_key("track_ticket_number")
            ticket_number = st.text_input(
                "Ticket Number",
                key=ticket_key,
                help="The ticket number from the ticketing system.",
                placeholder="e.g. CS-12345",
            )

            priority_key = tracking_tab_key("track_priority")
            st.session_state[priority_key] = normalize_priority(
                st.session_state.get(priority_key)
            )
            st.selectbox("Priority", PRIORITY_OPTIONS, key=priority_key)

            category_key = tracking_tab_key("track_category")
            st.text_input(
                "Category",
                key=category_key,
                help="The category of the issue.",
                placeholder="e.g. Software / Installation",
            )

            status_key = tracking_tab_key("track_status")
            status_options = TRACKING_STATUS_OPTIONS.get(tracking_type)
            if status_options:
                status_choices = list(status_options)
                current_status = st.session_state.get(status_key, "")
                if current_status and current_status not in status_choices:
                    status_choices = [current_status] + [
                        opt for opt in status_choices if opt != current_status
                    ]
                st.selectbox("Status", status_choices, key=status_key)
            else:
                st.text_input(
                    "Status",
                    key=status_key,
                    help="Current status of the case.",
                    placeholder="e.g. In Progress",
                )

            service_tag_key = tracking_tab_key("track_service_tag")
            expected_key = tracking_tab_key("track_expected_arrival")
            if tracking_type == "Dell":
                if (
                    not D.tracking.active
                    and service_tag_key not in st.session_state
                    and D.service_tag
                ):
                    st.session_state[service_tag_key] = D.service_tag
                st.text_input("Service Tag", key=service_tag_key)
            elif tracking_type == "FedEx":
                st.date_input("Expected arrival date", key=expected_key)

            if st.button(
                "Save and track",
                key=tracking_tab_key("save_and_track"),
                help="Save changes and add this case to the Dashboard tracking list",
            ):
                if not D.case_id:
                    st.error("Case ID is required before tracking can be enabled.")
                else:
                    D.tracking.active = True
                    D.tracking.type = tracking_type
                    D.tracking.category = (st.session_state.get(category_key, "") or "").strip()
                    D.tracking.status = (st.session_state.get(status_key, "") or "").strip()
                    D.tracking.priority = normalize_priority(
                        st.session_state.get(priority_key)
                    )
                    D.tracking.ticket_number = (
                        st.session_state.get(ticket_key, "") or ""
                    ).strip()
                    D.tracking.case_link = (D.tracking.case_link or "").strip()
                    if not D.tracking.creation_day:
                        D.tracking.creation_day = datetime.now().date().isoformat()
                    if tracking_type == "Dell":
                        D.tracking.service_tag = (
                            st.session_state.get(service_tag_key, "") or ""
                        ).strip()
                        D.tracking.expected_arrival_date = ""
                    elif tracking_type == "FedEx":
                        expected_value = st.session_state.get(expected_key)
                        if isinstance(expected_value, date):
                            D.tracking.expected_arrival_date = expected_value.isoformat()
                        else:
                            D.tracking.expected_arrival_date = ""
                        D.tracking.service_tag = ""
                    else:
                        D.tracking.expected_arrival_date = ""
                        D.tracking.service_tag = ""
                    save_case_to_database(D, notify=False)
                    ensure_tracking_session_defaults(case_idx, D.tracking)
                    st.session_state.track_case = True
                    st.success("Tracking information saved.")
            if st.button(
                "Close case & stop tracking",
                key=tracking_tab_key("close_tracking"),
                help="Remove this case from the Dashboard tracking list and save changes",
            ):
                D.tracking.active = False
                save_case_to_database(D, notify=False)
                st.session_state.track_case = False
                st.rerun()



    # ================== ESCALATIONS TAB =================
    if tab_escalations:
        with case_tab(
            tab_escalations, case_idx=case_idx, slug=CASE_TAB_SLUGS["Escalations"]
        ):
            escalations_tab_key = partial(
                case_widget_key, CASE_TAB_SLUGS["Escalations"], case_idx=case_idx
            )
            if "AX COORDINATORS" in cat_map:
                st.markdown("#### AX Coordinators Table")
                st.dataframe(
                    category_dataframe("AX COORDINATORS", D, cat_map),
                    width="stretch",
                )
                st.markdown("---")

            st.subheader("Escalation 2nd line")
            D.esc_name = D.caller_name
            st.text_input(
                "Name",
                D.esc_name,
                disabled=True,
                key=escalations_tab_key("esc_name_tab"),
            )
            D.esc_ph = D.phone_number
            st.text_input(
                "Phone",
                D.esc_ph,
                disabled=True,
                key=escalations_tab_key("esc_ph_tab"),
            )
            D.esc_email = D.email
            st.text_input(
                "Email",
                D.esc_email,
                disabled=True,
                key=escalations_tab_key("esc_email_tab"),
            )
            if "ESCALATION 2ND LINE" in cat_map:
                st.markdown("#### Escalation 2nd line Table")
                st.dataframe(
                    category_dataframe("ESCALATION 2ND LINE", D, cat_map),
                    width="stretch",
                )

            st.markdown("---")
            st.subheader("Dell escalation data")
            st.caption(
                "Capture the Dell-specific diagnostics and clinic contact details required for vendor escalations."
            )
            auto_text_input("Issue start date", "dell_issue_start_date")

            st.markdown("##### PC diagnostics & setup")
            diag_col1, diag_col2 = st.columns(2)
            auto_text_input(
                "Dell Command Updates status",
                "dell_command_updates_status",
                container=diag_col1,
            )
            auto_text_input(
                "Power Options setup",
                "dell_power_options_setup",
                container=diag_col2,
            )
            auto_text_input(
                "Dell Optimizer setup",
                "dell_optimizer_setup",
                container=diag_col1,
            )
            auto_text_input(
                "Intel Processor Power Management Utility installed?",
                "dell_intel_ppm_installed",
                container=diag_col2,
            )

            st.markdown("##### Performance & drivers")
            perf_col1, perf_col2 = st.columns(2)
            auto_text_input(
                "CPU Speed / Is CPU throttling?",
                "dell_cpu_speed_or_throttling",
                container=perf_col1,
            )
            auto_text_input(
                "GPU Usage % (Integrated)",
                "dell_gpu_usage_integrated",
                container=perf_col2,
            )
            auto_text_input(
                "GPU Usage % (Dedicated)",
                "dell_gpu_usage_dedicated",
                container=perf_col1,
            )
            auto_text_input(
                "CPU Utilization %",
                "dell_cpu_utilization",
                container=perf_col2,
            )
            auto_text_area(
                "Benchmark used and results",
                "dell_benchmark_results",
                container=perf_col1,
                height=100,
            )
            auto_text_area(
                "Which GPU driver versions were tested?",
                "dell_gpu_driver_versions",
                container=perf_col2,
                height=100,
            )
            auto_text_input(
                "Can it launch simulation on Ultra Resolution? (If needed)",
                "dell_ultra_resolution_support",
            )

            st.markdown("##### Diagnostics")
            diag_notes_col1, diag_notes_col2 = st.columns(2)
            auto_text_area(
                "Reliability Monitor and Event Viewer results",
                "dell_reliability_monitor_results",
                container=diag_notes_col1,
                height=120,
            )
            auto_text_area(
                "Dell Diagnosis test results (ePSA tests included)",
                "dell_diagnostics_results",
                container=diag_notes_col2,
                height=120,
            )
            auto_text_input(
                "Has Windows been reimaged?",
                "dell_windows_reimaged",
            )

            st.markdown("##### Clinic contact information")
            clinic_col1, clinic_col2 = st.columns(2)
            auto_text_input("Clinic name", "clinic_name", container=clinic_col1)
            auto_text_input(
                "Full name of person responsible for receiving the equipment",
                "clinic_contact_name",
                container=clinic_col2,
            )
            auto_text_input(
                "Phone number",
                "clinic_contact_phone",
                container=clinic_col1,
            )
            auto_text_input(
                "Email address",
                "clinic_contact_email",
                container=clinic_col2,
            )
            auto_text_input("Address 1", "clinic_address_line_1", container=clinic_col1)
            auto_text_input("Address 2 (Suite, etc.)", "clinic_address_line_2", container=clinic_col2)
            auto_text_input("City", "clinic_city", container=clinic_col1)
            auto_text_input("State", "clinic_state", container=clinic_col2)
            auto_text_input("Zip Code", "clinic_postal_code", container=clinic_col1)

            st.markdown("##### Dell escalation table preview")
            dell_table = dell_escalation_dataframe(D)
            st.dataframe(dell_table, width="stretch")
            copy_col, download_col = st.columns([2, 3])
            with copy_col:
                copy_key = escalations_tab_key("dell_escalation_copy")
                copy_suffix = re.sub(r"[^0-9a-z]+", "", copy_key.lower())
                if not copy_suffix:
                    copy_suffix = "dellcopy"
                if copy_suffix[0].isdigit():
                    copy_suffix = f"d{copy_suffix}"
                table_payload = json.dumps(dell_escalation_plain_text(D))
                table_payload = table_payload.replace("</", "<\\/")
                components.html(
                    f"""
                    <div style=\"display:flex;gap:0.5rem;align-items:center;\">
                        <button onclick=\"copyDellTable{copy_suffix}()\"
                                style=\"padding:0.35rem 0.75rem;border-radius:0.4rem;border:1px solid #ccc;background:#f8f9fa;cursor:pointer;\">
                            Copy Dell table
                        </button>
                        <span id=\"dell-feedback-{copy_suffix}\" style=\"font-size:0.75rem;color:#4CAF50;\"></span>
                    </div>
                    <script>
                        const dellFeedback{copy_suffix} = document.getElementById('dell-feedback-{copy_suffix}');
                        function showDellFeedback{copy_suffix}(message) {{
                            if (!dellFeedback{copy_suffix}) return;
                            dellFeedback{copy_suffix}.textContent = message;
                            setTimeout(() => {{
                                if (dellFeedback{copy_suffix}.textContent === message) {{
                                    dellFeedback{copy_suffix}.textContent = '';
                                }}
                            }}, 2000);
                        }}
                        function copyDellTable{copy_suffix}() {{
                            navigator.clipboard.writeText({table_payload}).then(() => {{
                                showDellFeedback{copy_suffix}('Dell escalation copied');
                            }});
                        }}
                    </script>
                    """,
                    height=60,
                )
            with download_col:
                csv_bytes = dell_table.to_csv(index=False).encode("utf-8")
                json_bytes = json.dumps(dell_escalation_rows(D), indent=2).encode("utf-8")
                st.download_button(
                    "Download CSV",
                    csv_bytes,
                    file_name=f"{D.case_id or 'case'}_dell_escalation.csv",
                    mime="text/csv",
                    key=escalations_tab_key("download_dell_escalation_csv"),
                )
                st.download_button(
                    "Download JSON",
                    json_bytes,
                    file_name=f"{D.case_id or 'case'}_dell_escalation.json",
                    mime="application/json",
                    key=escalations_tab_key("download_dell_escalation_json"),
                )

            if st.session_state.second_line_mode:
                st.markdown("---")
                st.subheader("Escalation 3rd line")
                auto_text_area(
                    "HJ article or possible root cause found",
                    "third_line_hj_article",
                    height=100,
                    placeholder=(D.internal_helpjuice or D.root_cause or ""),
                )
                auto_text_area(
                    "How to reproduce it",
                    "repro_steps",
                    height=100,
                    placeholder="Provide detailed reproduction steps.",
                )
                auto_text_area(
                    "Troubleshoot summary",
                    "third_line_troubleshoot_summary",
                    height=120,
                    placeholder=(D.remote_steps or ""),
                )
                auto_text_area(
                    "Comments",
                    "third_line_comments",
                    height=100,
                    placeholder=(D.additional_info or ""),
                )
                st.markdown("**Reseller contact information**")
                reseller_col1, reseller_col2 = st.columns(2)
                with reseller_col1:
                    auto_text_input(
                        "Reseller name",
                        "third_line_reseller_name",
                        placeholder="Enter reseller contact name",
                    )
                    auto_text_input(
                        "Reseller phone",
                        "third_line_reseller_phone",
                        placeholder="Primary phone number",
                    )
                with reseller_col2:
                    auto_text_input(
                        "Reseller alternate phone",
                        "third_line_reseller_phone_alt",
                        placeholder="Secondary phone number",
                    )
                    auto_text_input(
                        "Reseller email",
                        "third_line_reseller_email",
                        placeholder="Email address",
                    )
                st.markdown("**Clinic representative**")
                clinic_col1, clinic_col2 = st.columns(2)
                with clinic_col1:
                    auto_text_input(
                        "Clinic representative name",
                        "third_line_clinic_rep_name",
                        placeholder="Clinic contact name",
                    )
                    auto_text_input(
                        "Clinic representative phone",
                        "third_line_clinic_rep_phone",
                        placeholder="Primary phone number",
                    )
                with clinic_col2:
                    auto_text_input(
                        "Clinic representative alternate phone",
                        "third_line_clinic_rep_phone_alt",
                        placeholder="Secondary phone number",
                    )
                st.markdown("**Remote session details**")
                tv_col1, tv_col2, tv_col3 = st.columns(3)
                with tv_col1:
                    auto_text_input(
                        "TeamViewer ID",
                        "third_line_tv_id",
                        placeholder=D.teamviewer_id or "",
                    )
                with tv_col2:
                    auto_text_input(
                        "TeamViewer password",
                        "third_line_tv_password",
                        placeholder=D.teamviewer_password or "",
                    )
                with tv_col3:
                    auto_text_input(
                        "Unite PIN",
                        "third_line_unite_pin",
                        placeholder=D.subscription_id or "",
                    )
                msg = build_third_line_escalation(D)
                escaped_msg = escape(msg)
                st.text_area(
                    "Escalation message",
                    msg,
                    height=400,
                    key=escalations_tab_key("esc_message"),
                )
                components.html(
                    f"""
                    <script>
                    function copyThirdLineEscalation{case_idx}() {{
                        const text = {json.dumps(msg)};
                        navigator.clipboard.writeText(text).then(() => {{
                            const host = document.getElementById('third-line-copy-feedback-{case_idx}');
                            if (host) {{
                                host.innerText = 'Escalation message copied to clipboard.';
                            }}
                        }}).catch(() => {{
                            const host = document.getElementById('third-line-copy-feedback-{case_idx}');
                            if (host) {{
                                host.innerText = 'Unable to copy escalation message.';
                            }}
                        }});
                    }}
                    </script>
                    <button onclick="copyThirdLineEscalation{case_idx}()"
                            style="margin-top:0.5rem;padding:0.4rem 0.75rem;border-radius:0.4rem;">
                        Copy escalation message
                    </button>
                    <div id="third-line-copy-feedback-{case_idx}" style="font-size:0.8rem;margin-top:0.35rem;"></div>
                    """,
                    height=90,
                )
                st.download_button(
                    "Download escalation message",
                    msg,
                    file_name=f"third_line_escalation_{TODAY_STR}.txt",
                    mime="text/plain",
                    key=escalations_tab_key("download_third_line_escalation"),
                )
                st.markdown("---")



    # ================== HARDWARE ISSUES TAB =================
    if tab_hw:
        with case_tab(tab_hw, case_idx=case_idx, slug=CASE_TAB_SLUGS["Hardware Issues"]):
            st.subheader("PC Hardware Issue")
            col_pc1, col_pc2 = st.columns(2)
            auto_text_input(
                "Service Tag",
                "service_tag",
                container=col_pc1,
                help="Found on the back of the PC or via 'wmic bios get serialnumber'.",
            )
            auto_text_input(
                "PC Model",
                "pc_model",
                container=col_pc2,
                help="e.g. Alienware Aurora R16, Dell Precision 3660.",
            )
            auto_text_input(
                "Windows version",
                "windows_version",
                container=col_pc1,
                help="Type 'winver' in Start menu to find this.",
                placeholder="e.g. Windows 11 Pro 23H2",
            )
            auto_text_input(
                "BIOS version",
                "bios_version",
                container=col_pc2,
                help="Found in System Information (msinfo32).",
                placeholder="e.g. 1.2.3",
            )
            auto_text_input(
                "Graphics Card",
                "graphics_card",
                container=col_pc1,
                help="Check Task Manager > Performance > GPU.",
                placeholder="e.g. NVIDIA RTX 4070",
            )
            auto_text_input(
                "Processor",
                "processor",
                container=col_pc2,
                help="Check System > About.",
                placeholder="e.g. Intel Core i9-14900K",
            )
            auto_text_input(
                "Warranty",
                "warranty",
                help="Check support.dell.com with Service Tag.",
                placeholder="e.g. ProSupport ends 2026-10-15",
            )
            st.subheader("Scanner Hardware Issue")
            col_sc1, col_sc2 = st.columns(2)
            auto_text_input(
                "Scanner serial",
                "scanner_sn",
                container=col_sc1,
                help="The serial number usually located on the scanner or its base (e.g. s12345678).",
            )
            auto_text_input("Base serial", "base_sn", container=col_sc2)
            auto_text_input(
                "TRIOS module version",
                "trios_module_version",
                container=col_sc1,
            )
            auto_text_input(
                "Dongle deployment date (YYYY-MM-DD)",
                "dongle_deployment_date",
                container=col_sc2,
            )
            auto_number_input(
                "Number of previous replacements",
                "scanner_previous_replacements",
                container=col_sc1,
            )
            auto_text_input(
                "Damage classification",
                "scanner_accidental_damage",
                container=col_sc2,
                state_labels={True: "Accidental damage", False: "Internal damage"},
            )
            auto_text_input(
                "Hardware test performed?",
                "hardware_test",
                container=col_sc1,
            )
            st.subheader("Hardware replacement history")
            hr_col1, hr_col2 = st.columns(2)
            auto_text_input(
                "Dongle Replaced",
                "hardware_dongle_replaced",
                container=hr_col1,
            )
            auto_text_input(
                "Latest Deployment Date",
                "hardware_latest_deployment_date",
                container=hr_col2,
            )
            auto_text_input(
                "Scanner replaced",
                "hardware_scanner_replaced",
                container=hr_col1,
            )
            auto_text_input(
                "Scanner S/N",
                "hardware_scanner_sn_summary",
                container=hr_col2,
            )
            auto_text_input(
                "Subscription Type",
                "hardware_subscription_type",
            )
            cat_hr = "HARDWARE REPLACEMENT HISTORY"
            title_text_hr = table_title(cat_hr)
            st.markdown(f"**{title_text_hr}**")

            copy_suffix_hr = f"hw_hist_{case_idx}"
            title_payload_hr = script_safe_json(title_text_hr)
            table_payload_hr = script_safe_json(
                table_plain_text(cat_hr, D, HW_CATEGORY_MAP)
            )

            components.html(
                f"""
                <div style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center;margin-bottom:0.35rem;">
                    <button onclick=\"copyTitle{copy_suffix_hr}()\"
                            style=\"padding:0.35rem 0.75rem;border-radius:0.4rem;border:1px solid #ccc;background:#f8f9fa;cursor:pointer;\">
                        Copy title
                    </button>
                    <button onclick=\"copyTable{copy_suffix_hr}()\"
                            style=\"padding:0.35rem 0.75rem;border-radius:0.4rem;border:1px solid #ccc;background:#f8f9fa;cursor:pointer;\">
                        Copy table
                    </button>
                    <span id=\"feedback-{copy_suffix_hr}\" style=\"font-size:0.75rem;color:#4CAF50;\"></span>
                </div>
                <script>
                    const feedbackElem{copy_suffix_hr} = document.getElementById('feedback-{copy_suffix_hr}');
                    function showFeedback{copy_suffix_hr}(message) {{
                        if (!feedbackElem{copy_suffix_hr}) return;
                        feedbackElem{copy_suffix_hr}.textContent = message;
                        setTimeout(() => {{
                            if (feedbackElem{copy_suffix_hr}.textContent === message) {{
                                feedbackElem{copy_suffix_hr}.textContent = '';
                            }}
                        }}, 2000);
                    }}
                    function copyTitle{copy_suffix_hr}() {{
                        navigator.clipboard.writeText({title_payload_hr}).then(() => {{
                            showFeedback{copy_suffix_hr}('Title copied');
                        }});
                    }}
                    function copyTable{copy_suffix_hr}() {{
                        navigator.clipboard.writeText({table_payload_hr}).then(() => {{
                            showFeedback{copy_suffix_hr}('Table copied');
                        }});
                    }}
                </script>
                """,
                height=80,
            )
            st.dataframe(
                category_dataframe(cat_hr, D, HW_CATEGORY_MAP), width="stretch"
            )
            st.dataframe(
                category_dataframe("SCANNER HARDWARE", D, HW_CATEGORY_MAP), width="stretch"
            )



    # ================== REMOTE SESSION TAB =================
    REMOTE_DESKTOP_STYLE = """
    <style>
    .remote-hub-card {
        background: linear-gradient(135deg, rgba(29,41,81,0.92), rgba(58,96,115,0.88));
        border-radius: 16px;
        padding: 1.5rem;
        color: #f7fbff;
        box-shadow: 0 18px 45px rgba(23, 37, 61, 0.25);
        margin-bottom: 1.5rem;
    }
    .remote-hub-card__header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 0.75rem;
        flex-wrap: wrap;
    }
    .remote-hub-card__title {
        font-size: 1.45rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .remote-hub-card__badge {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: rgba(255, 255, 255, 0.18);
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
    }
    .remote-hub-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 0.9rem;
        margin-top: 1.25rem;
    }
    .remote-hub-grid__item {
        background: rgba(255, 255, 255, 0.12);
        border-radius: 12px;
        padding: 0.9rem 1rem;
        backdrop-filter: blur(5px);
    }
    .remote-hub-grid__label {
        font-size: 0.75rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        opacity: 0.75;
        margin-bottom: 0.35rem;
    }
    .remote-hub-grid__value {
        font-size: 1rem;
        font-weight: 600;
        word-break: break-word;
    }
    .remote-hub-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.65rem;
        margin-top: 1.25rem;
    }
    .remote-hub-actions button {
        padding: 0.6rem 1.1rem;
        border-radius: 999px;
        border: none;
        background: rgba(255, 255, 255, 0.18);
        color: #f7fbff;
        cursor: pointer;
        font-weight: 600;
        transition: transform 0.2s ease, background 0.2s ease;
    }
    .remote-hub-actions button:hover {
        transform: translateY(-1px);
        background: rgba(255, 255, 255, 0.28);
    }
    .remote-hub-note-preview {
        font-size: 0.9rem;
        line-height: 1.5;
        color: rgba(255, 255, 255, 0.85);
        margin-top: 1rem;
        border-left: 3px solid rgba(255, 255, 255, 0.25);
        padding-left: 0.75rem;
        max-height: 180px;
        overflow-y: auto;
    }
    .remote-hub-history {
        background: rgba(18, 30, 45, 0.75);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        color: #d6e4f5;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .remote-hub-history h4 {
        margin-top: 0;
    }
    </style>
    """
    with case_tab(tab_remote, case_idx=case_idx, slug=CASE_TAB_SLUGS["Remote Session"]):
        remote_tab_key = partial(
            case_widget_key, CASE_TAB_SLUGS["Remote Session"], case_idx=case_idx
        )
        remote_style_flag = "remote_style_injected"
        if not st.session_state.get(remote_style_flag, False):
            st.markdown(REMOTE_DESKTOP_STYLE, unsafe_allow_html=True)
            st.session_state[remote_style_flag] = True

        st.subheader("Remote desktop control center")
        st.caption(
            "A single timeline for every remote engagement. Legacy multi-session "
            "notes are merged automatically to keep the JSON payload compatible."
        )

        primary_session = ensure_single_remote_session(D)

        title_key = remote_tab_key("single_session_title")
        if title_key not in st.session_state:
            st.session_state[title_key] = primary_session.title

        notes_key = remote_tab_key("single_session_notes")
        if notes_key not in st.session_state:
            st.session_state[notes_key] = primary_session.notes

        incoming_title = st.session_state.get(title_key, primary_session.title)
        incoming_notes = st.session_state.get(notes_key, primary_session.notes)

        if incoming_title != primary_session.title or incoming_notes != primary_session.notes:
            updated_entry = RemoteSessionEntry(
                session_id=primary_session.session_id,
                title=incoming_title,
                notes=incoming_notes,
                created_at=primary_session.created_at,
                updated_at=_utc_now_z(),
            )
            update_case_remote_sessions(D, [updated_entry])
            primary_session = D.remote_sessions[0]
            st.session_state[title_key] = primary_session.title
            st.session_state[notes_key] = primary_session.notes

        history_summary = (D.remote_steps or "")

        uploads_count = len(st.session_state.get("uploads", []))
        logs_count = len(st.session_state.get("log_uploads", []))
        screenshots_count = len(st.session_state.get("screenshots", []))

        grid_rows = [
            ("TeamViewer ID", (D.teamviewer_id or "").strip() or "—"),
            ("TeamViewer password", (D.teamviewer_password or "").strip() or "—"),
            ("Remote contact", (D.caller_name or "").strip() or "—"),
            ("Contact phone", (D.phone_number or "").strip() or "—"),
            ("Contact email", (D.email or "").strip() or "—"),
            ("Started", (primary_session.created_at or "").strip() or "—"),
            ("Last update", (primary_session.updated_at or "").strip() or "—"),
            (
                "Uploads queued",
                f"{uploads_count} file{'s' if uploads_count != 1 else ''}",
            ),
            (
                "Logs queued",
                f"{logs_count} file{'s' if logs_count != 1 else ''}",
            ),
            (
                "Screenshots queued",
                f"{screenshots_count} capture{'s' if screenshots_count != 1 else ''}",
            ),
        ]
        grid_html = "".join(
            f"<div class='remote-hub-grid__item'>"
            f"<div class='remote-hub-grid__label'>{escape(str(label))}</div>"
            f"<div class='remote-hub-grid__value'>{escape(str(value))}</div>"
            "</div>"
            for label, value in grid_rows
        )

        note_preview = (primary_session.notes or "").strip()
        note_preview_html = (
            "<span style='opacity:0.65;'>No notes recorded yet.</span>"
            if not note_preview
            else escape(note_preview).replace("\n", "<br>")
        )

        credential_pairs = [
            ("TeamViewer ID", (D.teamviewer_id or "").strip()),
            ("TeamViewer password", (D.teamviewer_password or "").strip()),
            ("Third-line TV ID", (D.third_line_tv_id or "").strip()),
            ("Third-line TV password", (D.third_line_tv_password or "").strip()),
            ("Unite PIN", (D.third_line_unite_pin or "").strip()),
        ]
        credential_lines = [
            f"{label}: {value}"
            for label, value in credential_pairs
            if value
        ]
        credentials_payload = script_safe_json(
            "\n".join(credential_lines)
            if credential_lines
            else "No remote credentials recorded."
        )
        notes_payload = script_safe_json(
            (primary_session.notes or "").strip() or "No remote notes captured yet."
        )
        timeline_payload = script_safe_json(
            history_summary.strip() or "No remote timeline available yet."
        )
        title_display = primary_session.display_title(1)
        badge_text = (
            primary_session.updated_at or primary_session.created_at or "Session ready"
        ).strip()

        overview_tab, notes_tab, history_tab, attachments_tab = st.tabs(
            ["Overview", "Notes & Timeline", "History", "Attachments"]
        )

        with overview_tab:
            remote_card_html = f"""
{REMOTE_DESKTOP_STYLE}
<div class='remote-hub-card'>
  <div class='remote-hub-card__header'>
    <span class='remote-hub-card__title'>{escape(title_display)}</span>
    <span class='remote-hub-card__badge'>{escape(badge_text)}</span>
  </div>
  <div class='remote-hub-grid'>
    {grid_html}
  </div>
  <div class='remote-hub-actions'>
    <button onclick=\"copyRemotePayload(credentialsPayload, 'Credentials copied')\">Copy credentials</button>
    <button onclick=\"copyRemotePayload(notesPayload, 'Notes copied')\">Copy live notes</button>
    <button onclick=\"copyRemotePayload(timelinePayload, 'Timeline copied')\">Copy timeline</button>
  </div>
  <div id='remote-action-feedback' style='font-size:0.75rem;margin-top:0.35rem;'></div>
  <div class='remote-hub-note-preview'>{note_preview_html}</div>
</div>
<script>
  const credentialsPayload = {credentials_payload};
  const notesPayload = {notes_payload};
  const timelinePayload = {timeline_payload};
  function copyRemotePayload(payload, label) {{
    navigator.clipboard.writeText(payload).then(() => {{
      const feedback = document.getElementById('remote-action-feedback');
      if (feedback) {{
        feedback.textContent = label;
        setTimeout(() => {{
          if (feedback.textContent === label) {{
            feedback.textContent = '';
          }}
        }}, 2000);
      }}
    }});
  }}
</script>
"""
            components.html(remote_card_html, height=420)

        with notes_tab:
            st.markdown("#### Update session context")
            st.text_input(
                "Session title",
                key=title_key,
                help="Saved to the case JSON and reused by exports and quick actions.",
            )

            cols = st.columns([1, 1, 1])
            if cols[0].button(
                "Insert timestamp",
                key=remote_tab_key("notes_add_timestamp"),
                help="Insert the current UTC timestamp into the notes",
            ):
                stamp = _utc_now_z()
                existing = st.session_state.get(notes_key, "")
                updated = (
                    f"{existing.rstrip()}\n[{stamp}] "
                    if existing.strip()
                    else f"[{stamp}] "
                )
                st.session_state[notes_key] = updated
                st.rerun()
            if cols[1].button(
                "Mark session complete",
                key=remote_tab_key("notes_mark_complete"),
                help="Append a completion timestamp and marker to close the session",
            ):
                completion_stamp = _utc_now_z()
                existing = st.session_state.get(notes_key, "")
                completion_text = (
                    f"{existing.rstrip()}\n\n✔ Session closed at {completion_stamp}"
                    if existing.strip()
                    else f"✔ Session closed at {completion_stamp}"
                )
                st.session_state[notes_key] = completion_text
                st.rerun()
            confirm_key = remote_tab_key("notes_clear_confirm")
            if st.session_state.get(confirm_key):
                cols[2].warning("Are you sure?")
                if cols[2].button("Yes, clear", key=remote_tab_key("notes_clear_yes")):
                    st.session_state[notes_key] = ""
                    st.session_state[confirm_key] = False
                    st.rerun()
                if cols[2].button("Cancel", key=remote_tab_key("notes_clear_no")):
                    st.session_state[confirm_key] = False
                    st.rerun()
            elif cols[2].button(
                "Clear notes",
                key=remote_tab_key("notes_clear"),
                help="Delete all text in the notes field",
            ):
                st.session_state[confirm_key] = True
                st.rerun()

            st.text_area(
                "Remote troubleshooting notes",
                key=notes_key,
                height=420,
                help="Everything written here is persisted back to the case JSON.",
            )

        with history_tab:
            st.markdown("#### Timeline preview")
            if history_summary.strip():
                history_html = escape(history_summary).replace("\n", "<br>")
                st.markdown(
                    f"<div class='remote-hub-history'>{history_html}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("Timeline will populate once remote notes are captured.")

            st.markdown("#### Raw session payload")
            st.json(asdict(primary_session))

        with attachments_tab:
            st.markdown("#### Logs & screenshots")
            render_case_attachments_panel(
                D,
                case_idx=case_idx,
                tab_slug="remote_attachments",
            )

        st.markdown("---")
        st.markdown("### How to reproduce it")
        st.caption(
            "These steps stay visible in the remote workspace and continue to appear in the 3Q escalation form."
        )
        auto_text_area(
            "How to reproduce it",
            "repro_steps",
            height=180,
            container=st,
        )

    # ================== TABLES TAB =================
    with case_tab(tab_tables, case_idx=case_idx, slug=CASE_TAB_SLUGS["Tables"]):
        tables_tab_key = partial(
            case_widget_key, CASE_TAB_SLUGS["Tables"], case_idx=case_idx
        )
        st.subheader("Copy all tables")
        target_widget_key = tables_tab_key("hotkey_target_toggle")
        desired_target_idx = st.session_state.get(HOTKEY_TARGET_SESSION_KEY)
        desired_state = desired_target_idx == case_idx
        if st.session_state.get(target_widget_key) != desired_state:
            st.session_state[target_widget_key] = desired_state
        toggle_state = st.checkbox(
            "Use this case for global clipboard hotkeys",
            value=desired_state,
            key=target_widget_key,
            help=(
                "When enabled, Ctrl+Alt+C and the numeric shortcuts copy tables "
                "from this case even if another tab is open."
            ),
        )
        if toggle_state and desired_target_idx != case_idx:
            st.session_state[HOTKEY_TARGET_SESSION_KEY] = case_idx
            _refresh_hotkey_snapshot()
        elif not toggle_state and desired_target_idx == case_idx:
            st.session_state[HOTKEY_TARGET_SESSION_KEY] = None
            _refresh_hotkey_snapshot()
        st.download_button(
            "Download Case Info PDF",
            make_tables_pdf(D),
            file_name=f"{D.case_id or 'case'}_info.pdf",
            mime="application/pdf",
            key=tables_tab_key("download_info_pdf"),
        )
        for cat in cat_map:
            title_text = table_title(cat)
            st.markdown(f"**{title_text}**")

            copy_suffix_raw = f"tables_{case_idx}_{cat}".lower()
            copy_suffix = re.sub(r"[^0-9a-z]+", "", copy_suffix_raw)
            if not copy_suffix:
                copy_suffix = "copy"
            if copy_suffix[0].isdigit():
                copy_suffix = f"a{copy_suffix}"

            title_payload = script_safe_json(title_text)
            table_payload = script_safe_json(table_plain_text(cat, D, cat_map))
            components.html(
                f"""
                <div style=\"display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center;margin-bottom:0.35rem;\">
                    <button onclick=\"copyTitle{copy_suffix}()\"
                            style=\"padding:0.35rem 0.75rem;border-radius:0.4rem;border:1px solid #ccc;background:#f8f9fa;cursor:pointer;\">
                        Copy title
                    </button>
                    <button onclick=\"copyTable{copy_suffix}()\"
                            style=\"padding:0.35rem 0.75rem;border-radius:0.4rem;border:1px solid #ccc;background:#f8f9fa;cursor:pointer;\">
                        Copy table
                    </button>
                    <span id=\"feedback-{copy_suffix}\" style=\"font-size:0.75rem;color:#4CAF50;\"></span>
                </div>
                <script>
                    const feedbackElem{copy_suffix} = document.getElementById('feedback-{copy_suffix}');
                    function showFeedback{copy_suffix}(message) {{
                        if (!feedbackElem{copy_suffix}) return;
                        feedbackElem{copy_suffix}.textContent = message;
                        setTimeout(() => {{
                            if (feedbackElem{copy_suffix}.textContent === message) {{
                                feedbackElem{copy_suffix}.textContent = '';
                            }}
                        }}, 2000);
                    }}
                    function copyTitle{copy_suffix}() {{
                        navigator.clipboard.writeText({title_payload}).then(() => {{
                            showFeedback{copy_suffix}('Title copied');
                        }});
                    }}
                    function copyTable{copy_suffix}() {{
                        navigator.clipboard.writeText({table_payload}).then(() => {{
                            showFeedback{copy_suffix}('Table copied');
                        }});
                    }}
                </script>
                """,
                height=80,
            )
            st.dataframe(
                category_dataframe(cat, D, cat_map),
                width="stretch",
                key=tables_tab_key(f"df_{copy_suffix}"),
            )

    # ================== CORRECTED JSON TAB =================
    with case_tab(
        tab_corrected, case_idx=case_idx, slug=CASE_TAB_SLUGS["Corrected JSON"]
    ):
        corrected_tab_key = partial(
            case_widget_key, CASE_TAB_SLUGS["Corrected JSON"], case_idx=case_idx
        )
        st.subheader("AI Autocorrected case JSON")
        st.caption(
            "View and export the case payload after AI Autocorrection applies QA-focused fixes."
        )
        autocorrect_payload = (
            st.session_state.get("ai_autocorrect_case_json") or {}
        )
        if autocorrect_payload:
            corrected_case = autocorrect_payload.get("corrected_case")
            if not corrected_case and isinstance(autocorrect_payload, Mapping):
                corrected_case = autocorrect_payload
            if corrected_case:
                st.markdown("**Corrected case data**")
                st.json(corrected_case)

            corrections = autocorrect_payload.get("corrections_applied")
            if isinstance(corrections, list) and corrections:
                st.markdown("**What changed**")
                for item in corrections:
                    st.markdown(f"- {item}")

            correct_steps = autocorrect_payload.get("correct_steps")
            if isinstance(correct_steps, list) and correct_steps:
                st.markdown("**Verified steps to keep**")
                for step in correct_steps:
                    st.markdown(f"- {step}")

            qa_sim_note = autocorrect_payload.get("qa_sim_note")
            if isinstance(qa_sim_note, str) and qa_sim_note.strip():
                st.markdown("**QA SIM note**")
                st.code(qa_sim_note.strip())

            download_buffer = json.dumps(
                autocorrect_payload, indent=2, ensure_ascii=False
            )
            st.download_button(
                "Download corrected JSON",
                download_buffer,
                file_name=f"{D.case_id or 'case'}_corrected.json",
                mime="application/json",
                key=corrected_tab_key("download_corrected_json"),
            )
        else:
            st.info(
                "Run AI Autocorrection from the Case tab to generate a corrected JSON view."
            )

    # ================== SAVE/LOAD TAB =================
    with case_tab(tab_save_load, case_idx=case_idx, slug=CASE_TAB_SLUGS["Save/Load"]):
        save_tab_key = partial(
            case_widget_key, CASE_TAB_SLUGS["Save/Load"], case_idx=case_idx
        )
        st.subheader("Save / Load")
        col_save, col_load = st.columns(2)
        with col_save:
            if st.button(
                "Save",
                key=save_tab_key("save_case_button"),
                help="Manually save the current case state to disk",
            ):
                save_case_to_database(D)
        with col_load:
            uploaded_case = st.file_uploader(
                "Select case JSON",
                type="json",
                key=save_tab_key("load_case_uploader"),
                help="Load the selected case file into the workspace",
            )
            if uploaded_case and st.button(
                "Load",
                key=save_tab_key("load_case_button"),
                help="Load the selected case file into the workspace",
            ):
                request_load_from_bytes(uploaded_case.getvalue())

        st.subheader("Case Dex")
        dex_case_id = st.text_input(
            "Case ID", key=save_tab_key("case_dex_id")
        )
        if st.button(
            "Fetch Case Dex",
            key=save_tab_key("fetch_case_dex"),
            help="Retrieve case data from the external Case Dex system",
        ):
            if dex_case_id:
                try:
                    dex_bytes = request_case_dex(dex_case_id)
                except Exception as e:
                    st.error(f"Failed to download Case Dex: {e}")
                else:
                    st.session_state[
                        save_tab_key("case_dex_bytes")
                    ] = dex_bytes
                    st.session_state[
                        save_tab_key("case_dex_id_store")
                    ] = dex_case_id
            else:
                st.error("Please enter a Case ID")
        dex_bytes = st.session_state.get(save_tab_key("case_dex_bytes"))
        if dex_bytes:
            st.download_button(
                "Download Case Dex",
                dex_bytes,
                file_name=f"{st.session_state.get(save_tab_key('case_dex_id_store'), 'case')}_case_dex.zip",
                mime="application/zip",
                key=save_tab_key("download_case_dex"),
            )

        st.subheader("Recent cases")
        recent_cases = load_recent_cases()
        if not recent_cases:
            st.info("No recent cases found. Your history will appear here once you load or save a case.")
        for idx, case in enumerate(recent_cases):
            info_col, btn_col = st.columns([3, 1])
            last_modified_display = format_last_modified(case.get("last_modified"))
            if last_modified_display:
                info_col.write(
                    f"{case['case_id']} ({last_modified_display})\n{case['path']}"
                )
            else:
                info_col.write(f"{case['case_id']}\n{case['path']}")
            if btn_col.button(
                "Load",
                key=save_tab_key(f"recent_load_{idx}"),
                help="Restore this case to the active workspace",
            ):
                request_load_from_path(case["path"])

        pending = st.session_state.get("pending_load")
        if pending:
            st.error("Remember to save your information before loading a new case")
            col_i, col_s = st.columns(2)
            target_idx = pending.get("target_idx", CURRENT_CASE_IDX)
            if col_i.button("Ignore and load", key=save_tab_key("ignore_and_load")):
                _activate_case_index(target_idx)
                if "path" in pending:
                    load_case_from_path(pending["path"])
                else:
                    load_case_from_bytes(pending["data"])
                st.session_state.pending_load = None
            if col_s.button("Save", key=save_tab_key("save_before_loading")):
                save_case_to_database(D)

    if show_case_chat and tab_chat is not None:
        with case_tab(tab_chat, case_idx=case_idx, slug=CASE_TAB_SLUGS["Kiroshi Chat"]):
            render_case_kiroshi_chat_panel(case_idx)

    # ================== BORED TAB =================
    if tab_bored:
        with case_tab(tab_bored, case_idx=case_idx, slug=CASE_TAB_SLUGS["I'm bored"]):
            bored_tab_key = partial(
                case_widget_key, CASE_TAB_SLUGS["I'm bored"], case_idx=case_idx
            )
            st.subheader("One Click RPG")
            game = st.session_state.bored_game
            area = [
                "Forest of the Chaos Harlequins ",
                "Forgotten Graveyard of Endal",
                "Castle of the Blackest Knight",
                "Haunted Farm of Yondor",
                "Deathtrap Dungeon of Borgon",
                " Mysterious Swampland of Kuluth",
                "Swamp of the Slimy Hobbits",
                "Darkest Dungeons",
                "Ruins of the Fallen Gods",
                "Forlorn Islands of Lost Souls",
                "Hidden Hideout of Ninedeadeyes",
                "Wildlands of Lady L Moore",
                " Woods of Ypres",
                "Heart of Darkness",
                "Doomville",
                "The Red Jester's Torture Chamber",
                "The Goblins Fortress of Snikrik,",
                " Temple of Apshai",
                " Dungeons of Doom",
                "Mountains of the Wild Berserker",
                "Stronghold of Daggerfall",
                "Walking Hills of Cthulhu",
            ]
            monster = [
                "orcs",
                "goblins",
                "dragons",
                "demons",
                "kobolds",
                "blobs",
                "hobbits",
                "zombies",
                "gnomes",
                "vampires",
                "beholders",
                "trolls",
                "hill giants",
                "ettins",
                "mimics",
                "succubuses",
                "bone devils",
                "clay golems",
                "drows",
                "gnolls",
                "swamp hags",
                " night goblins",
                "half-ogres",
                "hobgoblins",
                "bog imps",
                "owlbears",
                "ponies",
                "winter wolves",
                "harlequin",
                "abomination",
            ]
            description = [
                "stupid",
                "horny",
                "heart broken",
                "deranged",
                "morbid",
                "tiny",
                "suicidal",
                "sexy",
                "skinny",
                "racist",
                "peaceful",
                "silly",
                "drunk",
                "sadistic",
                "young",
                "shy",
                "talkative",
                "lovestruck",
                "sarcastic",
                "homophobic",
                "forelorn",
                "happy",
                "friendly",
                "psychopathic",
                "optimistic",
                "mysterious",
                "beautiful",
                "malnourish",
                "zealous",
                "hot-headed",
            ]
            if st.button(
                "Explore",
                key=bored_tab_key("bored_explore"),
                help="Venture into the unknown to fight monsters and earn rewards",
            ):
                adventure = random.choice(area)
                encounter = random.choice(monster)
                descript = random.choice(description)
                number = random.randrange(2, 5)
                reward = random.randrange(1, 10)
                exp = random.randrange(1, 20)
                game["gold"] += reward
                game["exp"] += exp
                game["lexp"] += exp
                if game["lexp"] > 123 + (game["level"] * 10):
                    game["level"] += 1
                    game["lexp"] = 0
                lvl = game["level"]
                if lvl > 2 and lvl < 4:
                    game["power_ranking"] = "The Cannon Fodder (Ready to die ? ) "
                if lvl > 4 and lvl < 6:
                    game["power_ranking"] = "The Weakling Avenger (At least you tried )"
                if lvl > 6 and lvl < 8:
                    game["power_ranking"] = "The Nice Guy (This is no compliment )"
                if lvl > 8 and lvl < 10:
                    game["power_ranking"] = "The Beta Warrior (Well.. You won't die first, I guess )"
                if lvl > 10 and lvl < 12:
                    game["power_ranking"] = "The Mighty Beta Warrior (Some nerds respect you )"
                if lvl > 12 and lvl < 14:
                    game["power_ranking"] = "The Average Chump (Nothing to see here ) "
                if lvl > 14 and lvl < 16:
                    game["power_ranking"] = "The Man with a Stick (Fear my wood )  "
                if lvl > 16 and lvl < 18:
                    game["power_ranking"] = "The Man with a Big Stick (MORE WOOD )"
                if lvl > 18 and lvl < 20:
                    game["power_ranking"] = "The Town's Guard (Obey my authority ) "
                if lvl > 20 and lvl < 24:
                    game["power_ranking"] = "The Try-Hard Hero (You win some, you lose more )"
                if lvl > 24 and lvl < 26:
                    game["power_ranking"] = "The Goblin Slayer (Your reputation grows )"
                if lvl > 26 and lvl < 28:
                    game["power_ranking"] = "The Orc Breaker (Orcs cower in your presence )"
                if lvl > 28 and lvl < 30:
                    game["power_ranking"] = " The Average Hero (Good but not great,keep fighting )"
                if lvl > 30 and lvl < 32:
                    game["power_ranking"] = " The Demon Demolisher (Guts will be proud of you )"
                if lvl > 32 and lvl < 34:
                    game["power_ranking"] = " The Master Killer (A black belt in DEATH )"
                if lvl > 34 and lvl < 40:
                    game["power_ranking"] = " The Champion of Man (The best a man can be )"
                if lvl > 40 and lvl < 70:
                    game["power_ranking"] = " Legendary Hero (Well done. You can retire now )"
                if lvl > 70 and lvl < 90:
                    game["power_ranking"] = " Old Warrior (Why are you still playing ? )"
                if lvl > 90 and lvl < 100:
                    game["power_ranking"] = "It's Over 9000 !! ( Seriously, quit it )"
                if lvl > 100:
                    game["power_ranking"] = "God (We bow down to your greatness )"
                story = (
                    f"You explore the {adventure}. You encounter {number} {descript} {encounter}. "
                    f"You slay the {encounter}. You gain {reward} gold and {exp} exp."
                )
                game["story"] = story
            st.write(game["story"])
            st.markdown(
                f"Gold:{game['gold']}    EXP:{game['exp']}    LEVEL:{game['level']}",
            )
            st.markdown(f"Power ranking: {game['power_ranking']}")

            st.subheader("Secret Arena")
            if st.button(
                "Launch arena",
                key=widget_key("launch_arena", case_idx),
                help="Launch the Kiroshi Doom clone in a new window",
            ):
                game_path = Path(__file__).parent / "doom_game.py"
                subprocess.Popen([sys.executable, str(game_path)])


    autosave()

    _maybe_trigger_midday_cloud_refresh()

    reminder_state = _refresh_wellness_reminder_state()
    render_wellness_alert(reminder_state)

    _reset_capture_footer_registry()
    _maybe_tick_case_milestones()

def main():
    resolution_notice = st.session_state.pop("_milestone_resolution_notice", None)
    if resolution_notice:
        st.success(resolution_notice)

    visible_case_indices = _visible_case_index_list()
    case_labels = [
        _case_display_name(idx) for idx in visible_case_indices
    ] + ["+ New Case"]
    tab_labels: list[str] = ["Dashboard", "Sprint", "Saved Cases", "Settings"]
    if st.session_state.debug_mode:
        tab_labels.append("Debug")
    tab_labels.append("Report")
    tab_labels += case_labels
    all_tabs = st.tabs(tab_labels)

    tab_index = 0
    with all_tabs[tab_index]:
        render_with_monitor("Dashboard", render_dashboard, tab_label="Dashboard")
    tab_index += 1
    with all_tabs[tab_index]:
        render_with_monitor("Sprint", render_sprint_tab, tab_label="Sprint")
    tab_index += 1
    with all_tabs[tab_index]:
        render_with_monitor(
            "Saved Cases", render_saved_cases_page, tab_label="Saved Cases"
        )
    tab_index += 1
    with all_tabs[tab_index]:
        render_with_monitor("Settings", render_settings_panel, tab_label="Settings")
    tab_index += 1
    if st.session_state.debug_mode:
        with all_tabs[tab_index]:
            render_with_monitor("Debug", render_debug_panel, tab_label="Debug")
        tab_index += 1
    with all_tabs[tab_index]:
        render_with_monitor("Report", render_report_panel, tab_label="Report")
    tab_index += 1

    case_tabs = all_tabs[tab_index:]
    for idx, tab in enumerate(case_tabs):
        with tab:
            if idx == len(visible_case_indices):
                if st.button("Add Case", help="Create a new case workspace"):
                    st.session_state.case_sessions.append(CaseSession(case=CaseData()))
                    _sync_case_memory_from_sessions()
                    st.rerun()
            else:
                case_label = case_labels[idx]
                actual_idx = visible_case_indices[idx]
                render_with_monitor(
                    f"Case: {case_label}",
                    _render_case_tab,
                    actual_idx,
                    tab_label=case_label,
                    case_index=actual_idx,
                )

    show_failure_modal()
    show_incident_report_modal()


if __name__ == "__main__":
    main()
