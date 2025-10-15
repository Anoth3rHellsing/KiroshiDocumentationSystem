# -*- coding: utf-8 -*-
"""
Kiroshi RC 141025 – IT Case Documentation Helper
Run:
    streamlit run case_documentation_app.py
"""

import io
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
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import partial
from typing import Dict, List
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
from reportlab.lib.styles import getSampleStyleSheet
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
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
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
    from PIL import ImageGrab

    IMAGEGRAB_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when Pillow is unavailable
    ImageGrab = None
    IMAGEGRAB_AVAILABLE = False

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

VERSION = "RC 141025"
TODAY_STR = datetime.now().strftime("%d%m%Y")
AUTOSAVE_FILE = "autosave.json"
DEFAULT_OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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",
)
DEFAULT_AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
DEFAULT_AI_MODE = (
    "Local Model"
    if not DEFAULT_AI_BASE_URL
    else (
        "Cloud" if DEFAULT_AI_BASE_URL.startswith("https://api.openai.com") else "Local API"
    )
)
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
    "wellness_reminders": DEFAULT_WELLNESS_SETTINGS,
    "kiroshi_sarcasm_mode": False,
}


def _load_persistent_settings() -> dict[str, object]:
    if not SETTINGS_FILE.exists():
        return {}
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


_persistent_settings_cache: dict[str, object] = PERSISTENT_SETTINGS_DEFAULTS.copy()


_CASE_REFERENCE_PATTERN = re.compile(
    r"\b(?:case|caso|ticket|inc(?:ident)?|sr|cs|bug|pr|issue)[-_\s]*\d+\b",
    re.IGNORECASE,
)
_SERIAL_PATTERN = re.compile(r"\b[A-Z]{2,}\d{3,}\b")
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


def _tokenize_issue_description(text: str) -> list[str]:
    cleaned = _CASE_REFERENCE_PATTERN.sub(" ", text)
    cleaned = _SERIAL_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"[^0-9A-Za-z]+", " ", cleaned)
    tokens = [token.lower() for token in cleaned.split() if len(token) >= 3]
    return [token for token in tokens if token not in _GENERIC_STOPWORDS and not token.isdigit()]


def _normalize_text_field(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


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
    text_candidates: list[str] = []
    for key in ("category", "classification", "topic", "root_cause", "title", "description_excerpt", "solution"):
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

    recurrence_count = _coerce_int(row.get("recurrence_count"), 0)
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


def _iter_remote_app_paths(repo: str, branch: str) -> Iterable[str]:
    """Yield possible locations for the application in the update repo.

    Historically the project lived in the repository root, but some forks
    keep the Streamlit app inside a nested directory (for example the repo
    name itself).  Allow operators to further customize the lookup through
    ``KIROSHI_UPDATE_APP_PATHS`` which accepts a comma separated list of
    relative paths.
    """

    env_paths = os.environ.get("KIROSHI_UPDATE_APP_PATHS", "").strip()
    if env_paths:
        for path in env_paths.split(","):
            normalized = path.strip().lstrip("/")
            if normalized:
                yield normalized

    yield from _discover_remote_app_paths(repo, branch)

    # Built-in defaults that cover the most common layouts.
    yield from (
        "case_documentation_app.py",
        "KiroshiDocumentationSystem/case_documentation_app.py",
        "src/case_documentation_app.py",
        "app/case_documentation_app.py",
    )


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
        "visual": "layout_map",
        "description": textwrap.dedent(
            """
            Welcome to your first launch of Kiroshi! This guided tour walks through every tab,
            table, and input you will use to document cases. Follow the prompts, explore the
            visuals, and use the navigation buttons to move between steps.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Which main tab gives you an instant view of workload and priorities?",
            "options": ["Dashboard", "Settings", "Kiroshi Chat"],
            "answer": "Dashboard",
            "success": "Exactly — the Dashboard summarises tracked work at a glance.",
            "failure": "Hint: it's the first tab filled with charts and case tables.",
        },
    },
    {
        "id": "dashboard",
        "title": "Dashboard Tables",
        "visual": "dashboard_tables",
        "description": textwrap.dedent(
            """
            The Dashboard tab hosts every operational table:
            • **Tracked Cases** – live statuses, ownership, and quick actions.
            • **Dell Escalations & FedEx Replacements** – vendor-specific queues with ETAs.
            • **All My Saved Cases** – browse and reload anything stored on disk.
            Use the search bar to filter and the action buttons to load or stop tracking directly from the table rows.
            """
        ),
        "interaction": {
            "type": "checkbox_group",
            "prompt": "Check each item after you review how the Dashboard tables work.",
            "items": [
                "I know where to search and filter tracked cases.",
                "I understand the Dell/FedEx table highlights vendor priorities.",
                "I can load a saved case from the All My Saved Cases table.",
            ],
            "success": "Great! You're ready to use the Dashboard tables day to day.",
            "instruction": "Mark every checkbox once you've read the descriptions above.",
        },
    },
    {
        "id": "case_workspace",
        "title": "Case Workspace & Inputs",
        "visual": "case_sections",
        "description": textwrap.dedent(
            """
            Every case tab is a full workspace that captures customer details, troubleshooting steps,
            escalation information, optional hardware diagnostics, attachments, and AI helpers. Toggle
            hardware or escalation fields when needed and use the Tables tab to copy a spreadsheet-ready
            summary of every input.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Where do you find the Excel-style snapshot of every captured field?",
            "options": [
                "Tables tab inside the case workspace",
                "Dashboard tab",
                "Report tab",
            ],
            "answer": "Tables tab inside the case workspace",
            "success": "Correct — each case includes a Tables tab for copy/paste exports.",
            "failure": "Try again: the Tables tab lives inside each case workspace.",
        },
    },
    {
        "id": "issue_reporter",
        "title": "Instant Issue Reporter",
        "visual": "issue_reporter_flow",
        "description": textwrap.dedent(
            """
            Launch the Issue Reporter from any case to bundle call notes, logs, and screenshots into a
            single vendor-ready packet. Kiroshi maps your troubleshooting narrative into the structured
            summary that partners expect, attaches the latest evidence, and stores a timestamped copy in
            your database for follow-up.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "What does the Issue Reporter automatically include before you submit?",
            "options": [
                "Only the text from your root cause field",
                "Screenshots, selected logs, and the troubleshooting summary",
                "A blank template you must fill in manually",
            ],
            "answer": "Screenshots, selected logs, and the troubleshooting summary",
            "success": "Yes — it packages artifacts and notes so vendors see the full story.",
            "failure": "Remember, the Issue Reporter assembles evidence for you before sending.",
        },
    },
    {
        "id": "escalations",
        "title": "Escalation Control Tower",
        "visual": "escalation_matrix",
        "description": textwrap.dedent(
            """
            Use the escalations drawer to track every hand-off. Capture vendor queue IDs, urgency, and
            response targets, then pin critical follow-ups to the dashboard badge strip. Shared escalation
            history keeps teams synchronized while automated reminders flag anything approaching its SLA.
            """
        ),
        "interaction": {
            "type": "checkbox_group",
            "prompt": "Mark each checklist item once you have seen where to manage escalations.",
            "items": [
                "I can open the escalation drawer from a case tab.",
                "I know where SLA timers appear on the dashboard.",
                "I saw how vendor queue IDs are stored with the case.",
            ],
            "success": "Great — you can now coordinate escalations without losing context.",
            "instruction": "Check every box after reviewing the escalation features above.",
        },
    },
    {
        "id": "reporting",
        "title": "Reporting & Exports",
        "visual": "report_overview",
        "description": textwrap.dedent(
            """
            The Report tab turns AI Educate insights into visuals and downloadable PDFs. When AI Educate is enabled,
            refresh the dataset, inspect root-cause metrics, run the Bug Detector, and export a polished report.
            From any case you can also generate PDF summaries and ZIP bundles with attachments.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Which tab generates the AI Educate PDF analytics report?",
            "options": ["Dashboard", "Report", "Kiroshi Chat"],
            "answer": "Report",
            "success": "Exactly — open the Report tab once AI Educate is enabled to export insights.",
            "failure": "The analytics live in the Report tab right next to Settings.",
        },
    },
    {
        "id": "analytics",
        "title": "Operations Analytics",
        "visual": "analytics_suite",
        "description": textwrap.dedent(
            """
            The analytics suite blends saved case metrics, Issue Reporter outcomes, and escalation load
            into a unified view. Trendlines spotlight recurring failure types, while the resolution heat
            map highlights where teams are beating or missing their targets.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Which visual helps you spot workload bottlenecks over the week?",
            "options": [
                "Resolution heat map",
                "Issue Reporter draft list",
                "Kiroshi Chat history",
            ],
            "answer": "Resolution heat map",
            "success": "Exactly — the heat map shows when cases cluster above SLA thresholds.",
            "failure": "Hint: look for the analytic that compares days to SLA performance.",
        },
    },
    {
        "id": "settings",
        "title": "Settings & Personalisation",
        "visual": "settings_overview",
        "description": textwrap.dedent(
            """
            Settings control 2nd Line mode, debug tools, AI Educate options, and now your onboarding
            history. Use this panel to toggle advanced assistance, import or export Educate datasets, and
            relaunch this tutorial whenever you like. Completion metadata records when you finished the
            tour and the version you saw.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Where can you replay the onboarding tutorial after today?",
            "options": ["Dashboard", "Settings", "Case workspace"],
            "answer": "Settings",
            "success": "That's right — the Settings tab now includes a Repeat Tutorial button.",
            "failure": "Look in Settings for the onboarding controls and status badge.",
        },
    },
    {
        "id": "ui_refresh",
        "title": "Polished Interface & Shortcuts",
        "visual": "ui_refresh",
        "description": textwrap.dedent(
            """
            Subtle gradients, animated progress badges, and keyboard-aware navigation make the refreshed
            UI easier to scan. Tutorial step selectors, card highlights, and quick access buttons guide new
            users without getting in your way.
            """
        ),
        "interaction": {
            "type": "checkbox_group",
            "prompt": "Tick the enhancements you noticed in the new interface.",
            "items": [
                "Animated progress badges in the tutorial",
                "Improved contrast on cards and tables",
                "Step selector for jumping around the tour",
            ],
            "success": "Nicely spotted — those touches keep the workflow feeling fast.",
            "instruction": "Mark each enhancement after you've seen it in action.",
        },
    },
    {
        "id": "kiroshi_chat",
        "title": "Kiroshi Chat & Resources",
        "visual": "chat_resources",
        "description": textwrap.dedent(
            """
            Kiroshi Chat keeps a searchable manual database, including a new quick-reference summary of the README
            and Kiroshi workflow. Upload your own notes, search the knowledge base, or ask the assistant to cross-reference
            the "Kiroshi Quick Reference" entry any time you need a refresher.
            """
        ),
        "interaction": {
            "type": "text_confirm",
            "prompt": "Type READY to finish the tour and jump into Kiroshi.",
            "answer": "READY",
            "success": "Tutorial complete! You're ready to document real cases.",
            "failure": "Enter READY in all caps to confirm you're set.",
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

INSTALLER_FILENAME = "KiroshiInstaller_RC-141025.bat"


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

    request_id = f"gpt-{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}"
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
    "I drafted a to-do list and now I'm tired from the accomplishment.",
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
    primary="#433878",
    accent="#7c3aed",
    background="#f7f8ff",
    surface="#ffffff",
    text="#111827",
    muted_text="#4b5563",
    glados_messages=KIROSHI_MESSAGES,
)


HOLIDAY_THEMES: dict[str, ThemePalette] = {
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
}

HOLIDAY_NAME_TO_KEY = {
    "New Year's Day": "new_year",
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
    is_holiday_theme = theme.key != DEFAULT_THEME.key
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
    else:
        background_layers = "\n                ".join(
            [
                "radial-gradient(circle at 15% 20%, var(--kiroshi-primary-glow) 0%, transparent 55%)",
                "radial-gradient(circle at 85% 12%, var(--kiroshi-accent-glow) 0%, transparent 60%)",
                f"linear-gradient(165deg, {background_soft} 0%, {theme.background} 100%)",
            ]
        )
    st.markdown(
        f"""
        <style>
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
            font-family: 'Source Sans Pro', sans-serif;
            min-height: 100vh;
        }}
        body {{
            margin: 0;
        }}
        .stApp {{
            color: var(--kiroshi-text);
        }}
        .stApp > header {{
            background: linear-gradient(135deg, {theme.primary} 0%, {theme.accent} 100%);
            border-bottom: 1px solid color-mix(in srgb, var(--kiroshi-border) 45%, transparent);
            padding: 0.35rem 0;
        }}
        .stApp > header * {{
            color: #ffffff !important;
        }}
        .stApp [data-testid="stDecoration"] {{
            background: linear-gradient(135deg, {theme.primary} 0%, {theme.accent} 100%) !important;
        }}
        .stApp [data-testid="stDecoration"] svg {{
            display: none;
        }}
        .stApp .block-container {{
            background: linear-gradient(180deg, var(--kiroshi-surface-soft) 0%, var(--kiroshi-surface) 80%);
            border-radius: 1.6rem 1.6rem 0 0;
            box-shadow: 0 26px 60px {_rgba(card_shadow_color, 0.36)};
            padding: 2.2rem 2.4rem 2.4rem;
            color: var(--kiroshi-text);
            animation: kiroshiFadeIn 0.7s ease-out both;
            transition: background 320ms ease, box-shadow 320ms ease, transform 260ms ease;
        }}
        .stApp .block-container:hover {{
            transform: translateY(-2px);
            box-shadow: 0 30px 70px {_rgba(card_shadow_color, 0.32)};
        }}
        .stApp [data-testid="stSidebar"] > div:first-child {{
            background: linear-gradient(205deg, var(--kiroshi-surface) 0%, var(--kiroshi-surface-muted) 100%);
            border-right: 1px solid color-mix(in srgb, var(--kiroshi-border) 60%, transparent);
            box-shadow: inset -8px 0 24px rgba(15, 23, 42, 0.22);
            color: var(--kiroshi-text);
        }}
        .stApp [data-testid="stSidebar"] * {{
            color: var(--kiroshi-text);
        }}
        .stApp a {{
            color: {accent_glow};
        }}
        .stApp a:hover {{
            color: {theme.accent};
        }}
        .stApp input,
        .stApp textarea,
        .stApp select {{
            background: var(--kiroshi-input-background);
            color: var(--kiroshi-text);
            border-radius: 0.85rem;
            border: 1px solid color-mix(in srgb, var(--kiroshi-border) 55%, transparent);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
            transition: border-color 220ms ease, box-shadow 220ms ease;
        }}
        .stApp input::placeholder,
        .stApp textarea::placeholder {{
            color: color-mix(in srgb, var(--kiroshi-muted) 78%, var(--kiroshi-text) 22%);
        }}
        .stApp .stButton button {{
            border-radius: 999px;
            border: none;
            padding: 0.65rem 1.9rem;
            font-weight: 600;
            background: linear-gradient(135deg, {theme.primary} 0%, {theme.accent} 100%);
            color: #ffffff;
            box-shadow: 0 14px 34px {_rgba(button_shadow_color, 0.42)};
            transition: transform 120ms ease, filter 120ms ease;
        }}
        .stApp .stButton button:hover {{
            filter: brightness(1.05);
            transform: translateY(-1px);
        }}
        .stApp .stTabs [role="tablist"] button {{
            border-radius: 999px !important;
            color: color-mix(in srgb, var(--kiroshi-muted) 70%, var(--kiroshi-text) 30%);
        }}
        .stApp .stTabs [role="tablist"] button[aria-selected="true"] {{
            background: linear-gradient(135deg, {theme.primary} 0%, {theme.accent} 100%);
            color: #ffffff;
            box-shadow: 0 10px 24px {_rgba(button_shadow_color, 0.35)};
        }}
        .stApp .stTabs [role="tablist"] button[aria-selected="true"] p {{
            color: #ffffff !important;
        }}
        .stApp .stAlert > div {{
            background: color-mix(in srgb, var(--kiroshi-surface) 78%, rgba(255, 255, 255, 0.1));
            border: 1px solid color-mix(in srgb, var(--kiroshi-accent) 35%, transparent);
            color: var(--kiroshi-text);
        }}
        .stApp div[data-testid="stSwitch"] {{
            background: color-mix(in srgb, var(--kiroshi-surface) 82%, rgba(255, 255, 255, 0.18));
            border-radius: 1rem;
            border: 1px solid color-mix(in srgb, var(--kiroshi-border) 55%, transparent);
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
        </style>
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
            "font": "Source Sans Pro",
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

CURRENT_THEME = determine_active_theme()
apply_theme_palette(CURRENT_THEME)


def inject_base_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap');

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
            padding: 1.6rem 1.9rem;
            border-radius: 1.2rem;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.12), rgba(255, 255, 255, 0.85));
            box-shadow: 0 18px 32px rgba(15, 23, 42, 0.16);
            color: var(--kiroshi-text-on-white);
            position: relative;
            overflow: hidden;
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
    holiday_theme_active = CURRENT_THEME.key != DEFAULT_THEME.key
    companion_card_background = (
        "#ffffff"
        if holiday_theme_active
        else "linear-gradient(145deg, color-mix(in srgb, var(--kiroshi-primary) 18%, transparent), color-mix(in srgb, var(--kiroshi-accent) 12%, transparent))"
    )
    companion_card_shadow = (
        "0 14px 34px rgba(15, 23, 42, 0.18)"
        if holiday_theme_active
        else "0 10px 25px rgba(15, 23, 42, 0.12)"
    )
    companion_card_border = (
        "1px solid rgba(15, 23, 42, 0.08)" if holiday_theme_active else "1px solid transparent"
    )
    companion_title_color = "#111827" if holiday_theme_active else "var(--kiroshi-primary)"
    companion_text_color = "#111827" if holiday_theme_active else "var(--kiroshi-text)"
    header_html = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap');

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

        #kiroshi-header, #kiroshi-header * {{
            font-family: 'Source Sans Pro', 'Segoe UI', system-ui, -apple-system, sans-serif !important;
            color: var(--kiroshi-text);
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
        }}

        #kiroshi-header__companion {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 0 0.75rem;
            width: 100%;
        }}

        #kiroshi-header__companion-card {{
            background: {companion_card_background};
            border-radius: 1rem;
            padding: 1rem 1.5rem;
            box-shadow: {companion_card_shadow};
            max-width: 620px;
            width: 100%;
            margin: 0 auto;
            border: {companion_card_border};
        }}

        #kiroshi-header__companion-title {{
            font-size: 1.2rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            color: {companion_title_color};
            margin-bottom: 0.5rem;
        }}

        #kiroshi-header__companion-text {{
            font-size: 1.1rem;
            line-height: 1.6;
            color: {companion_text_color};
        }}

        #kiroshi-header__date {{
            font-weight: 600;
            text-align: right;
            min-width: 200px;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            justify-content: flex-end;
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
                padding: 0 1.5rem;
            }}

            #kiroshi-header__date {{
                order: 3;
                justify-content: center;
            }}

            #kiroshi-header__companion-card {{
                max-width: clamp(260px, 86vw, 540px);
                padding: 1.1rem 1.25rem;
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
                <div id="kiroshi-header__companion-title">Kiroshi Motivational Compannion</div>
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
    if kind == "layout_map":
        tab_cards = [
            ("Dashboard", "Charts, tracked cases, and saved case tables."),
            ("Settings", "Modes, AI Educate controls, and onboarding status."),
            ("Report", "AI Educate analytics, Bug Detector, and PDF export."),
            ("Kiroshi Chat", "Assistant conversation, manual database, and quick reference."),
        ]
        cols = st.columns(len(tab_cards))
        for col, (title, blurb) in zip(cols, tab_cards):
            with col:
                st.markdown(
                    "<div class='tutorial-visual-card'><strong>{}</strong><br><span class='tutorial-footnote'>{}</span></div>".format(
                        escape(title), escape(blurb)
                    ),
                    unsafe_allow_html=True,
                )
        st.caption(
            "Case-specific tabs appear after the global tabs — each one contains the full documentation workspace."
        )
    elif kind == "dashboard_tables":
        summary = pd.DataFrame(
            [
                {
                    "Table": "Tracked Cases",
                    "Purpose": "Monitor active work with status, owner, priority, and quick actions.",
                    "Key actions": "Update priority, load a case, or stop tracking in one click.",
                },
                {
                    "Table": "Dell Escalations & FedEx Replacements",
                    "Purpose": "Vendor-specific queues with ticket numbers, ETAs, and case IDs.",
                    "Key actions": "Scan for approaching ETAs and jump into the matching tracked file.",
                },
                {
                    "Table": "All My Saved Cases",
                    "Purpose": "Chronological list of every saved JSON file in your database.",
                    "Key actions": "Load the case into a new tab to resume documentation instantly.",
                },
            ]
        )
        st.dataframe(summary, width="stretch")
    elif kind == "case_sections":
        case_sections = pd.DataFrame(
            [
                {
                    "Section": "Case Details",
                    "Highlights": "Company, subscription ID, application version, case ID, summary.",
                },
                {
                    "Section": "Communication",
                    "Highlights": "Caller name, phone/email, phone description, remote session credentials.",
                },
                {
                    "Section": "Troubleshooting & Notes",
                    "Highlights": "Internal Helpjuice notes, logs, remote steps, root cause, repro steps, solution.",
                },
                {
                    "Section": "AI Helpers",
                    "Highlights": "Verify, Ask Kiroshi, Categorizer, AI Assist, and database search shortcuts.",
                },
                {
                    "Section": "Escalation",
                    "Highlights": "Toggle escalation fields, capture contacts, best time to call, vendor pathways.",
                },
                {
                    "Section": "Hardware Toggles",
                    "Highlights": "Enable hardware issue fields, PC specs, BIOS/GPU data, scanner serials.",
                },
                {
                    "Section": "Attachments & Tracking",
                    "Highlights": "Upload logs/screenshots, capture images, track cases with priority and ticket IDs.",
                },
                {
                    "Section": "Exports & Tables",
                    "Highlights": "Download PDFs, export ZIP bundles, copy the Tables tab for spreadsheets.",
                },
            ]
        )
        st.dataframe(case_sections, width="stretch")
    elif kind == "report_overview":
        report_summary = pd.DataFrame(
            [
                {
                    "Feature": "AI Educate Dashboard",
                    "What it shows": "Root-cause charts, top keywords, and trend analytics based on saved cases.",
                },
                {
                    "Feature": "Bug Detector",
                    "What it shows": "Recurring failure patterns detected across the Educate dataset.",
                },
                {
                    "Feature": "Report PDF",
                    "What it shows": "One-click PDF export of the Educate insights for stakeholders.",
                },
                {
                    "Feature": "Case PDF & ZIP",
                    "What it shows": "From any case tab you can export the formatted summary and attachments bundle.",
                },
            ]
        )
        st.dataframe(report_summary, width="stretch")
    elif kind == "settings_overview":
        settings_summary = pd.DataFrame(
            [
                {
                    "Control": "2nd Line mode",
                    "Description": "Switch the dashboard into tracked-case operations with Dell/FedEx tables.",
                },
                {
                    "Control": "Show Debug tab",
                    "Description": "Unlock diagnostics, API configuration, and log viewer for troubleshooting.",
                },
                {
                    "Control": "AI Educate toggles",
                    "Description": "Enable insights, activate advanced assistance, and share/import datasets.",
                },
                {
                    "Control": "Knowledge sharing",
                    "Description": "Download the learning JSON or merge collaborator contributions.",
                },
                {
                    "Control": "Onboarding status",
                    "Description": "View completion date and re-run the interactive tutorial anytime.",
                },
            ]
        )
        st.table(settings_summary)
    elif kind == "issue_reporter_flow":
        flow_steps = [
            (
                "Capture",
                "Pulls in customer summary, reproduction steps, and impact statements automatically.",
            ),
            (
                "Evidence",
                "Attaches the latest screenshots and any logs you selected from the case workspace.",
            ),
            (
                "Package",
                "Formats the narrative into a vendor-ready template with tags and queue routing.",
            ),
            (
                "Archive",
                "Saves a timestamped copy to your database for auditing and future follow-up.",
            ),
        ]
        flow_markup = "".join(
            "<div class='tutorial-flow__step'>"
            f"<div class='tutorial-flow__icon'>{idx}</div>"
            f"<div class='tutorial-flow__title'>{escape(title)}</div>"
            f"<div class='tutorial-footnote'>{escape(detail)}</div>"
            "</div>"
            for idx, (title, detail) in enumerate(flow_steps, start=1)
        )
        st.markdown(f"<div class='tutorial-flow'>{flow_markup}</div>", unsafe_allow_html=True)
        st.caption(
            "Start the Issue Reporter from any case tab — Kiroshi keeps the vendor package aligned with"
            " your troubleshooting notes."
        )
    elif kind == "escalation_matrix":
        escalation_summary = pd.DataFrame(
            [
                {
                    "Escalation": "Vendor follow-up",
                    "Tracked in": "Escalation drawer",
                    "What you see": "Queue ID, assigned engineer, promised callback, SLA timer",
                },
                {
                    "Escalation": "Internal hand-off",
                    "Tracked in": "Dashboard badge",
                    "What you see": "Owner, severity, days outstanding, linked case",
                },
                {
                    "Escalation": "Customer update",
                    "Tracked in": "Reminder banner",
                    "What you see": "Next contact window, notes, completion checklist",
                },
            ]
        )
        st.dataframe(escalation_summary, width="stretch")
        st.caption(
            "Escalations sync between the case drawer and dashboard, so the entire team sees timers and"
            " commitments in one view."
        )
    elif kind == "analytics_suite":
        heatmap_rows = [
            ("Mon", "On target", 14),
            ("Mon", "Warning", 3),
            ("Mon", "Escalated", 1),
            ("Tue", "On target", 11),
            ("Tue", "Warning", 4),
            ("Tue", "Escalated", 2),
            ("Wed", "On target", 16),
            ("Wed", "Warning", 2),
            ("Wed", "Escalated", 1),
            ("Thu", "On target", 13),
            ("Thu", "Warning", 5),
            ("Thu", "Escalated", 2),
            ("Fri", "On target", 10),
            ("Fri", "Warning", 6),
            ("Fri", "Escalated", 3),
        ]
        heatmap_data = pd.DataFrame(heatmap_rows, columns=["Day", "Status", "Cases"])
        day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        status_order = ["On target", "Warning", "Escalated"]
        chart = (
            alt.Chart(heatmap_data)
            .mark_rect()
            .encode(
                x=alt.X("Day:N", sort=day_order, title="Weekday"),
                y=alt.Y("Status:N", sort=status_order, title="Status"),
                color=alt.Color(
                    "Cases:Q",
                    scale=alt.Scale(scheme="blues", domain=[0, heatmap_data["Cases"].max()]),
                    legend=None,
                ),
                tooltip=["Day", "Status", alt.Tooltip("Cases", title="Cases")],
            )
            .properties(height=220)
        )
        st.altair_chart(chart, width="stretch", **ALTAIR_CHART_KWARGS)
        insights = [
            ("82%", "cases resolved within SLA", "+6% vs last week"),
            ("18", "active escalations", "Most due Thursday"),
            ("4.6h", "median resolution time", "Down 40 minutes"),
        ]
        insight_markup = "".join(
            "<div class='tutorial-insight-card'>"
            f"<strong>{escape(value)}</strong>"
            f"<div>{escape(caption)}</div>"
            f"<small>{escape(delta)}</small>"
            "</div>"
            for value, caption, delta in insights
        )
        st.markdown(
            f"<div class='tutorial-insight-grid'>{insight_markup}</div>", unsafe_allow_html=True
        )
    elif kind == "ui_refresh":
        col_left, col_right = st.columns([1.4, 1])
        highlights = [
            "Animated badges highlight your current tutorial step.",
            "Navigation slider jumps directly to any topic in the tour.",
            "Cards and tables ship with increased contrast for readability.",
        ]
        with col_left:
            highlight_markup = "".join(
                f"<li>{escape(item)}</li>" for item in highlights
            )
            st.markdown(
                f"<ul class='tutorial-highlight-list'>{highlight_markup}</ul>",
                unsafe_allow_html=True,
            )
        with col_right:
            st.markdown(
                "<div class='tutorial-visual-card' style='height:100%'>"
                "<strong>Palette preview</strong>"
                "<div class='tutorial-color-row'>"
                "<div class='tutorial-color-chip' data-label='Primary' style='background:linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);'></div>"
                "<div class='tutorial-color-chip' data-label='Accent' style='background:linear-gradient(135deg, #f97316 0%, #fb923c 100%);'></div>"
                "<div class='tutorial-color-chip' data-label='Surface' style='background:linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);'></div>"
                "</div>"
                "<p class='tutorial-footnote' style='margin-top:0.75rem;'>New gradients keep focus on key actions while maintaining accessibility targets.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
    elif kind == "chat_resources":
        col_chat, col_manual, col_reference = st.columns(3)
        with col_chat:
            st.markdown(
                "<div class='tutorial-visual-card'><strong>Kiroshi Chat</strong><br><span class='tutorial-footnote'>Persistent conversation history, Verify button context, and personality modes.</span></div>",
                unsafe_allow_html=True,
            )
        with col_manual:
            st.markdown(
                "<div class='tutorial-visual-card'><strong>Manual Docs Database</strong><br><span class='tutorial-footnote'>Upload TXT references, search stored notes, and feed rich context into replies.</span></div>",
                unsafe_allow_html=True,
            )
        with col_reference:
            st.markdown(
                "<div class='tutorial-visual-card'><strong>Kiroshi Quick Reference</strong><br><span class='tutorial-footnote'>A curated JSON summary of the README and workflows is preloaded for instant answers.</span></div>",
                unsafe_allow_html=True,
            )
        st.caption(
            "Ask Kiroshi to search for 'Kiroshi Quick Reference' whenever you need guidance on features or processes."
        )


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
_init_state("openai_api_key", DEFAULT_OPENAI_API_KEY)
_init_state("openai_model", "gpt-4o")
_init_state("ai_base_url", DEFAULT_AI_BASE_URL)
_init_state("ai_mode", DEFAULT_AI_MODE)
_init_state(
    "enable_holiday_theme", _get_persistent_default("enable_holiday_theme", True)
)
_init_state("theme_preview", "auto")
_init_state("api_helpjuice", False)
_init_state("api_restart", False)
_init_state("api_scan_time", False)
_init_state("generated_email", "")
_init_state("kiroshi_chat_history", load_memory())
_init_state("assistant_notes", get_assistant_notes())
_init_state("manual_docs", load_manual_docs())
_init_state("verify_result", "")
_init_state("ask_result", "")
_init_state("categorizer_result", "")
_init_state("categorizer_summary", {})
_init_state("system_prompt", SYSTEM_PROMPT)
_init_state("personality_mode", "utility")
_init_state("ai_assist_result", "")
_init_state("db_search_result", "")
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


def load_autosave():
    if st.session_state._autosave_loaded:
        return
    if os.path.exists(AUTOSAVE_FILE):
        try:
            with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            st.session_state.case = data.get("case", {})
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


def _utc_now_z() -> str:
    """Return the current UTC time in ISO-8601 format with a ``Z`` suffix."""

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


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
    hardware_test: bool = False
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
    scanner_accidental_damage: bool = False
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


@dataclass
class InMemoryUploadedFile:
    """Simple file-like container for generated screenshots."""

    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return self.data


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
) -> tuple[InMemoryUploadedFile | None, str | None]:
    """Capture a cropped screenshot using the interactive region selector."""

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

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return InMemoryUploadedFile(f"{safe_name}.png", buf.getvalue()), None


def capture_full_screenshot(
    safe_name: str,
) -> tuple[InMemoryUploadedFile | None, str | None]:
    """Capture a full screen screenshot with multiple fallbacks."""

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

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return InMemoryUploadedFile(f"{safe_name}.png", buf.getvalue()), None


def _default_attachments_index() -> dict[str, list[dict[str, str]]]:
    return {
        "uploads": [],
        "log_uploads": [],
        "screenshots": [],
    }


def _handle_incident_screenshot_result(
    screenshot: "InMemoryUploadedFile | None", error: str | None
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

    sessions = st.session_state.get("case_sessions")
    if isinstance(sessions, list) and CURRENT_CASE_IDX < len(sessions):
        session = sessions[CURRENT_CASE_IDX]
        try:
            session.attachments_index = normalised  # type: ignore[attr-defined]
            session.uploads = st.session_state.get("uploads", [])
            session.log_uploads = st.session_state.get("log_uploads", [])
            session.screenshots = st.session_state.get("screenshots", [])
        except AttributeError:
            pass
    _sync_case_memory_from_sessions()


def _normalise_attachments_index(
    data: Mapping[str, Iterable[Mapping[str, object]]] | Mapping[str, object] | None,
) -> dict[str, list[dict[str, str]]]:
    normalised = _default_attachments_index()
    if not isinstance(data, Mapping):
        return normalised
    for key in normalised:
        items = data.get(key, [])
        cleaned: list[dict[str, str]] = []
        if isinstance(items, Iterable):
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                name = item.get("name")
                path = item.get("path")
                if isinstance(name, str) and isinstance(path, str):
                    cleaned.append({"name": name, "path": path})
        normalised[key] = cleaned
    return normalised


@dataclass
class CaseSession:
    """Container for per-case session state."""

    case: CaseData
    scratch: str = ""
    uploads: list = field(default_factory=list)
    log_uploads: list = field(default_factory=list)
    screenshots: list = field(default_factory=list)
    source_path: str = ""
    attachments_index: dict[str, list[dict[str, str]]] = field(
        default_factory=_default_attachments_index
    )


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
                "Case": case.case_id or f"Case {idx + 1}",
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
    screenshot: InMemoryUploadedFile | None = None,
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
    styles = getSampleStyleSheet()
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
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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

    doc.build(elements)
    buf.seek(0)
    return buf.read()


# ──────────────── CASE TAB MEMORY ────────────────


def _load_case_tab_memory() -> list[dict[str, object]]:
    if not CASE_TAB_MEMORY_FILE.exists():
        return []
    try:
        payload = json.loads(CASE_TAB_MEMORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Failed to load case tab memory: %s", exc)
        return []
    tabs = payload.get("tabs") if isinstance(payload, Mapping) else None
    if not isinstance(tabs, list):
        return []
    return [dict(entry) for entry in tabs if isinstance(entry, Mapping)]


def _write_case_tab_memory(entries: list[dict[str, object]]) -> None:
    try:
        CASE_TAB_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CASE_TAB_MEMORY_FILE.open("w", encoding="utf-8") as fh:
            json.dump({"tabs": entries}, fh, indent=2)
    except OSError as exc:
        logging.warning("Failed to persist case tab memory: %s", exc)


def _hydrate_case_sessions_from_memory() -> list[CaseSession]:
    sessions: list[CaseSession] = []
    for entry in _load_case_tab_memory():
        source_path = str(entry.get("source_path", "")) if entry else ""
        scratch_value = str(entry.get("scratch", "")) if entry else ""
        case_payload = entry.get("case") if isinstance(entry, Mapping) else {}
        attachments_payload = entry.get("attachments_index") if isinstance(entry, Mapping) else {}
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
        screenshots: list[InMemoryUploadedFile] = []
        if case_obj.case_id:
            try:
                uploads, log_uploads, screenshots = load_case_attachments(
                    case_obj.case_id,
                    attachments_index,
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
        entries.append(
            {
                "case": case_payload,
                "source_path": source_path,
                "scratch": scratch_value,
                "attachments_index": attachments_index,
            }
        )
    _write_case_tab_memory(entries)


# convert stored dict to dataclass, ignoring unexpected fields
if isinstance(st.session_state.case, dict):
    allowed = {f.name for f in fields(CaseData)}
    filtered = {k: v for k, v in st.session_state.case.items() if k in allowed}
    st.session_state.case = CaseData(**filtered)
D: CaseData = st.session_state.case
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
        st.session_state.screenshots = primary_session.screenshots
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


def load_case_state(idx: int) -> None:
    cs = st.session_state.case_sessions[idx]
    st.session_state.case = cs.case
    st.session_state.uploads = cs.uploads
    st.session_state.log_uploads = cs.log_uploads
    st.session_state.screenshots = cs.screenshots
    st.session_state["attachments_index"] = _normalise_attachments_index(
        getattr(cs, "attachments_index", {})
    )
    scratch_value = getattr(cs, "scratch", "")
    st.session_state.scratch = scratch_value
    st.session_state[widget_key("scratch", idx)] = scratch_value
    global D
    D = st.session_state.case
    for key, value in asdict(D).items():
        st.session_state[key] = value


def save_case_state(idx: int) -> None:
    scratch_key = widget_key("scratch", idx)
    scratch_value = st.session_state.get(scratch_key, st.session_state.get("scratch", ""))
    existing_session = st.session_state.case_sessions[idx]
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
    )
    _sync_case_memory_from_sessions()


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

    suffix = f"_{idx}"
    for key in list(st.session_state.keys()):
        if key.endswith(suffix):
            st.session_state.pop(key)

    st.session_state.case_sessions[idx] = new_session

    if idx == CURRENT_CASE_IDX:
        global D
        st.session_state.case = new_case
        D = new_case
        st.session_state.uploads = []
        st.session_state.log_uploads = []
        st.session_state.screenshots = []
        st.session_state["attachments_index"] = _default_attachments_index()
        st.session_state.scratch = ""
        st.session_state[widget_key("scratch", idx)] = ""
        for key in (
            "ai_assist_result",
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


def widget_key(base: str, idx: int) -> str:
    """Return a Streamlit widget key namespaced to a case index."""
    key = f"{base}_{idx}"
    return _register_widget_key(key)


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


CURRENT_CASE_IDX = 0

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
def autosave_payload() -> dict:
    return {
        "case": asdict(D),
    }


def autosave():
    with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(autosave_payload(), f, indent=2)
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


def sanitize_case_id(case_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", case_id.strip())
    return safe_id or "case"


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename preserving extension when possible."""

    name = Path(filename).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return sanitized or "file"


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

    mapping = [
        ("uploads", st.session_state.get("uploads", []), "uploads"),
        ("log_uploads", st.session_state.get("log_uploads", []), "logs"),
        ("screenshots", st.session_state.get("screenshots", []), "screenshots"),
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
            attachments_index[key].append({"name": sanitized, "path": rel_path})

    _set_active_session_attachments_index(attachments_index)
    return attachments_index


def load_case_attachments(
    case_id: str, attachments_data: Mapping[str, Iterable[Mapping[str, object]]]
) -> tuple[list[InMemoryUploadedFile], list[InMemoryUploadedFile], list[InMemoryUploadedFile]]:
    """Load persisted attachments for a case based on stored metadata."""

    uploads: list[InMemoryUploadedFile] = []
    log_uploads: list[InMemoryUploadedFile] = []
    screenshots: list[InMemoryUploadedFile] = []

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
            target.append(InMemoryUploadedFile(display_name, data))

    return uploads, log_uploads, screenshots


def create_case_autosave_snapshot(case_id: str) -> Path | None:
    try:
        payload = autosave_payload()
        backup_path = Path(AUTOSAVE_FILE).with_name(
            f"autosave_{sanitize_case_id(case_id)}.json"
        )
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return backup_path
    except Exception as exc:
        logging.exception("Failed to create autosave snapshot for %s", case_id)
        st.warning(f"Unable to create autosave backup: {exc}")
        return None


def load_recent_cases() -> list:
    try:
        payload = json.loads(RECENT_CASES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    recent: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        recent.append(
            {
                "case_id": item.get("case_id", ""),
                "path": item.get("path", ""),
                "last_modified": item.get("last_modified", ""),
            }
        )
    return recent


def update_recent_cases(case_id: str, path: str) -> None:
    recents = [c for c in load_recent_cases() if c.get("path") != path]
    last_modified = ""
    try:
        case_path = Path(path)
        if case_path.exists():
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
    RECENT_CASES_PATH.write_text(json.dumps(recents[:10], indent=2), encoding="utf-8")


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
        key = widget_key(base_key, case_idx)
        if force or key not in st.session_state:
            st.session_state[key] = value

    assign("tracking_type", tracking.type or "Dell")
    assign("track_category", tracking.category or "")
    assign("track_status", tracking.status or "")
    assign("track_ticket_number", tracking.ticket_number or "")
    assign("track_case_link", tracking.case_link or "")
    assign("track_priority", normalize_priority(tracking.priority))
    assign("track_service_tag", tracking.service_tag or "")

    expected_key = widget_key("track_expected_arrival", case_idx)
    if tracking.expected_arrival_date:
        try:
            expected_value = datetime.fromisoformat(tracking.expected_arrival_date).date()
        except Exception:
            expected_value = date.today()
    else:
        expected_value = date.today()
    if force or expected_key not in st.session_state:
        st.session_state[expected_key] = expected_value


def _coerce_case_mapping(data: object) -> dict | None:
    """Return a dictionary representation from historical payloads."""

    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        dict_items = [item for item in data if isinstance(item, dict)]
        if len(dict_items) == 1:
            return dict_items[0]
        if dict_items:
            logging.warning("Multiple dict entries found in list payload; using first item")
            return dict_items[0]
    return None


def load_tracked_cases() -> list:
    cases = []
    # Load modern tracked cases directly from the database directory.
    for p in DATABASE_DIR.glob("*.json"):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        data = _coerce_case_mapping(payload)
        if data is None:
            continue
        tracking_info = data.get("tracking")
        if not isinstance(tracking_info, dict) or not tracking_info.get("active"):
            continue
        case_id = data.get("case_id") or p.stem
        company = data.get("company_name") or data.get("company") or ""
        end_user = (
            data.get("contact_name")
            or data.get("caller_name")
            or data.get("end_user")
            or ""
        )
        phone = (
            data.get("phone_number")
            or data.get("office_ph")
            or data.get("direct_ph")
            or ""
        )
        priority = normalize_priority(tracking_info.get("priority"))
        version = data.get("kiroshi_version")
        last_modified = data.get("last_modified")
        if not last_modified:
            last_modified = (
                datetime.fromtimestamp(p.stat().st_mtime)
                .replace(microsecond=0)
                .isoformat()
            )
        cases.append(
            {
                "path": str(p),
                "case_id": case_id,
                "company": company,
                "end_user": end_user,
                "phone_number": phone,
                "type": tracking_info.get("type", ""),
                "category": tracking_info.get("category", ""),
                "status": tracking_info.get("status", ""),
                "priority": priority,
                "ticket_number": tracking_info.get("ticket_number", ""),
                "creation_day": tracking_info.get("creation_day", ""),
                "expected_arrival_date": tracking_info.get("expected_arrival_date", ""),
                "case_link": tracking_info.get("case_link", ""),
                "service_tag": tracking_info.get("service_tag", ""),
                "version_label": f"Kiroshi {version}" if version else f"Pre Kiroshi {VERSION}",
                "kiroshi_version": version,
                "is_legacy": False,
                "last_modified": last_modified,
            }
        )
    # Include historical tracked JSON files for reference.
    for p in TRACKED_CASES_DIR.glob("*.json"):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        data = _coerce_case_mapping(payload)
        if data is None:
            continue
        case_id = data.get("case_id") or p.stem.replace("_Active", "")
        company = data.get("company") or data.get("company_name") or ""
        end_user = data.get("end_user") or data.get("customer") or ""
        phone = data.get("phone_number") or ""
        category = (
            data.get("custom_category")
            or data.get("service_tag")
            or data.get("category")
            or ""
        )
        last_modified = data.get("last_modified")
        if not last_modified:
            last_modified = (
                datetime.fromtimestamp(p.stat().st_mtime)
                .replace(microsecond=0)
                .isoformat()
            )
        cases.append(
            {
                "path": str(p),
                "case_id": case_id,
                "company": company,
                "end_user": end_user,
                "phone_number": phone,
                "type": data.get("type", ""),
                "category": category,
                "status": data.get("status", ""),
                "priority": normalize_priority(data.get("priority")),
                "ticket_number": data.get("ticket_number", ""),
                "creation_day": data.get("creation_day", ""),
                "expected_arrival_date": data.get("expected_arrival_date", ""),
                "case_link": data.get("case_link", ""),
                "service_tag": data.get("service_tag", ""),
                "version_label": "Legacy JSON (this is only for display and not for case saving.)",
                "kiroshi_version": None,
                "is_legacy": True,
                "last_modified": last_modified,
            }
        )
    return cases


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
        timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        if isinstance(data, Mapping):
            data["last_modified"] = timestamp
        if isinstance(payload, list):
            replaced = False
            for idx, item in enumerate(payload):
                if isinstance(item, Mapping):
                    payload[idx] = data
                    replaced = True
                    break
            if not replaced:
                payload.append(data)
            to_write = payload
        else:
            to_write = data
        case_path.write_text(json.dumps(to_write, indent=2), encoding="utf-8")
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
        st.session_state[widget_key("track_priority", CURRENT_CASE_IDX)] = (
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
        status_key = widget_key("track_status", CURRENT_CASE_IDX)
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
        if target_case_id:
            update_recent_cases(target_case_id, str(case_path))
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
        dest = DATABASE_DIR / f"{case_id_value}.json"
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
        update_recent_cases(case_id_value, str(dest))
        st.toast("Case removed from tracking.") if hasattr(st, "toast") else st.success(
            "Case removed from tracking."
        )
        st.rerun()
    except Exception as exc:
        logging.exception("Failed to untrack tracked case %s", path)
        st.error(f"Failed to untrack case: {exc}")


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


def list_saved_cases() -> list:
    entries: list[dict[str, object]] = []
    files = sorted(
        DATABASE_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in files:
        try:
            raw_payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        is_legacy_payload = isinstance(raw_payload, list)
        data = _coerce_case_mapping(raw_payload)
        if data is None:
            data = {}
            is_legacy_payload = True

        case_id = path.stem
        company = ""
        end_user = ""
        if isinstance(data, Mapping):
            case_id = data.get("case_id") or case_id
            company = (
                data.get("company_name")
                or data.get("company")
                or ""
            )
            end_user = (
                data.get("customer_name")
                or data.get("contact_name")
                or data.get("caller_name")
                or data.get("end_user")
                or ""
            )

        raw_last_modified = data.get("last_modified") if isinstance(data, Mapping) else None
        parsed_last_modified = parse_iso_datetime(raw_last_modified)
        if parsed_last_modified is None:
            parsed_last_modified = datetime.fromtimestamp(path.stat().st_mtime)
            raw_last_modified = parsed_last_modified.isoformat()

        has_tracking = isinstance(data, Mapping) and isinstance(data.get("tracking"), Mapping)
        kiroshi_version = ""
        if isinstance(data, Mapping):
            kiroshi_version = str(data.get("kiroshi_version") or "").strip()

        tags: list[str] = []
        if is_legacy_payload:
            tags.append("Legacy JSON")
        if not has_tracking:
            tags.append("Pre-dashboard merge")

        if not kiroshi_version:
            if not has_tracking:
                kiroshi_version = "1.5.2"
            elif is_legacy_payload:
                kiroshi_version = "Legacy"
            else:
                kiroshi_version = "Unknown"

        entries.append(
            {
                "case_id": case_id,
                "company": company,
                "end_user": end_user,
                "updated": parsed_last_modified,
                "last_modified": raw_last_modified,
                "path": str(path),
                "file_name": path.name,
                "is_legacy": is_legacy_payload,
                "kiroshi_version": kiroshi_version,
                "tags": tags,
                "has_tracking": has_tracking,
            }
        )
    return entries


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
    now = datetime.utcnow()
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
                            datetime.utcnow() - last_modified_dt
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
                if st.button("Load", key=f"dash_load_{unique_suffix}"):
                    request_load_from_path(case["path"], prefer_new_tab=True)
            with action_cols[1]:
                button_label = "Untrack" if case.get("is_legacy") else "Stop Tracking"
                if st.button(
                    button_label,
                    key=f"dash_untrack_{unique_suffix}",
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


def render_saved_cases_dashboard() -> None:
    saved_cases = list_saved_cases()
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
            "Load", key=f"saved_load_{Path(case['path']).stem}"
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
    )
    selected_versions = filter_cols[1].multiselect(
        "Version",
        options=version_options,
        default=version_options,
        key=global_widget_key("saved_cases_version_filter"),
    )
    legacy_scope = filter_cols[2].selectbox(
        "Legacy",
        ("All", "Modern only", "Legacy only"),
        key=global_widget_key("saved_cases_legacy_filter"),
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

        action_cols = st.columns(3)
        if action_cols[0].button(
            "Load in current tab",
            key=global_widget_key("saved_cases_load_current"),
        ):
            if case_path.exists():
                request_load_from_path(str(case_path), prefer_new_tab=False)
            else:
                st.error("Case file could not be found on disk.")
        if action_cols[1].button(
            "Load in new case tab",
            key=global_widget_key("saved_cases_load_new"),
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
                "Export JSON",
                export_bytes,
                file_name=case_path.name,
                mime="application/json",
                key=global_widget_key("saved_cases_export_json"),
            )
        else:
            action_cols[2].warning(
                f"Unable to export this case ({export_error or 'unknown error'})."
            )
    else:
        st.info("No cases match the current filters.")

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
    tracked_cases = load_tracked_cases()
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
            render_saved_cases_dashboard()
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
    if st.button("Repeat interactive tutorial", key=global_widget_key("tutorial_repeat")):
        st.session_state.show_tutorial = True
        st.session_state.tutorial_step = 0
        st.rerun()

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
        "Enable holiday themes",
        key="enable_holiday_theme",
        on_change=_on_setting_change("enable_holiday_theme"),
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
        workspace_tab, ai_tab, updates_tab = st.tabs(
            [
                "Workspace",
                "AI & Knowledge",
                "Updates",
            ]
        )
        with workspace_tab:
            _render_settings_workspace_tab()
        with ai_tab:
            _render_settings_ai_tab()
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
                safe_name = shot_name.strip() or f"incident_{int(time.time())}"
                safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
                shot, error = capture_region_screenshot(safe_name)
                _handle_incident_screenshot_result(shot, error)
            if capture_cols[1].button(
                "Use full screenshot",
                key=global_widget_key("incident_full_capture"),
            ):
                if not PYAUTOGUI_AVAILABLE or pyautogui is None:
                    _handle_incident_screenshot_result(
                        None,
                        "Full-screen capture is unavailable in this environment.",
                    )
                else:
                    safe_name = shot_name.strip() or f"incident_{int(time.time())}"
                    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
                    try:
                        img = pyautogui.screenshot()  # type: ignore[union-attr]
                    except Exception as exc:  # pragma: no cover - GUI dependent
                        _handle_incident_screenshot_result(
                            None, f"Unable to capture screenshot: {exc}"
                        )
                    else:
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        buf.seek(0)
                        _handle_incident_screenshot_result(
                            InMemoryUploadedFile(f"{safe_name}.png", buf.getvalue()),
                            None,
                        )
            if capture_cols[2].button(
                "Clear screenshot",
                key=global_widget_key("incident_clear_capture"),
            ):
                st.session_state.incident_reporter_screenshot = None
                st.session_state.incident_reporter_capture_error = None

            screenshot = st.session_state.get("incident_reporter_screenshot")
            if screenshot:
                st.image(screenshot.data, caption=screenshot.name, use_column_width=True)
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
    render_case_ui(idx)
    save_case_state(idx)


def render_kiroshi_chat_panel() -> None:
    st.image(str(KIROSHI_CHAT_LOGO_PATH), width=80)
    st.subheader("Kiroshi Chat")
    sarcasm_enabled = st.session_state.get("kiroshi_sarcasm_mode", False)
    if sarcasm_enabled:
        st.caption("Sarcasm Mode is enabled—Kiroshi will answer with extra dry wit.")
    else:
        st.caption(
            "Want sharper banter? Toggle Sarcasm Mode in Settings to let Kiroshi lean into the snark."
        )

    if "kiroshi_chat_history" not in st.session_state:
        migrated_history = st.session_state.pop("atom_history", None)
        if isinstance(migrated_history, list):
            st.session_state.kiroshi_chat_history = migrated_history
        else:
            st.session_state.kiroshi_chat_history = load_memory()

    with st.expander("Personality Construct"):
        personality_mode = st.session_state.get("personality_mode", "utility")
        personality_label = personality_mode.replace("_", " ").title()
        sarcasm_state = "On" if sarcasm_enabled else "Off"
        st.caption(
            f"Active personality: {personality_label} · Sarcasm mode: {sarcasm_state}"
        )

        base_prompt_key = global_widget_key("system_prompt_base")
        if base_prompt_key not in st.session_state:
            st.session_state[base_prompt_key] = st.session_state.get(
                "system_prompt", SYSTEM_PROMPT
            )
        edited_prompt = st.text_area(
            "Base system prompt",
            height=220,
            key=base_prompt_key,
            help=(
                "Adjust the underlying construct template. Personality and sarcasm settings "
                "are layered on top of this base."
            ),
        )
        if edited_prompt != st.session_state.get("system_prompt"):
            st.session_state["system_prompt"] = edited_prompt

        preview_value = build_system_prompt()
        preview_key = global_widget_key("system_prompt_preview")
        st.session_state[preview_key] = preview_value
        st.text_area(
            "Active construct preview",
            value=preview_value,
            height=220,
            key=preview_key,
            help="Exact system prompt currently sent with each chat request.",
            disabled=True,
        )

    api_key = st.session_state.openai_api_key
    model = st.session_state.openai_model
    base_url = st.session_state.ai_base_url
    if not api_key and base_url.startswith("https://api.openai.com"):
        st.info("Set your OpenAI API key in the Debug tab.")

    with st.expander("Manual Documents Database"):
        if st.session_state.manual_docs:
            st.markdown("**Stored documents:**")
            for doc in st.session_state.manual_docs:
                st.markdown(f"- {doc['title']}")
        doc_file = st.file_uploader(
            "Add document",
            type=["txt"],
            key=global_widget_key("doc_file"),
        )
        doc_title = st.text_input("Title", key=global_widget_key("doc_title"))
        if st.button("Save document", key=global_widget_key("save_doc")):
            if doc_file and doc_title:
                content = doc_file.getvalue().decode("utf-8", errors="ignore")
                st.session_state.manual_docs.append({"title": doc_title, "content": content})
                save_manual_docs(st.session_state.manual_docs)
                st.success("Document saved.")
            else:
                st.error("Provide both title and document.")

    st.subheader("Search manual database")
    search_query = st.text_input("Search query", key=global_widget_key("db_query"))
    if st.button("Search in database", key=global_widget_key("db_search_button")):
        if not api_key and base_url.startswith("https://api.openai.com"):
            st.error("Please set your OpenAI API key in the Debug tab.")
        elif not search_query:
            st.error("Enter a search query.")
        else:
            matches = search_manual_docs(search_query, st.session_state.manual_docs)
            if matches:
                context = "\n\n".join(f"{m['title']}:\n{m['content']}" for m in matches)
                message = (
                    "Use the following documents to answer the question. "
                    "Cite document titles.\n\n"
                    + context
                    + f"\n\nQuestion: {search_query}"
                )
                try:
                    reply = invoke_gpt(
                        message,
                        st.session_state.kiroshi_chat_history,
                        api_key,
                        model,
                        base_url,
                        source="manual_docs_search",
                    )
                except Exception as exc:
                    logging.error("Manual docs GPT search failed: %s", exc)
                    st.session_state.db_search_result = str(exc)
                else:
                    st.session_state.kiroshi_chat_history.append(
                        {"role": "user", "content": f"[DB Search] {search_query}"}
                    )
                    st.session_state.kiroshi_chat_history.append(
                        {"role": "assistant", "content": reply}
                    )
                    save_memory(st.session_state.kiroshi_chat_history)
                    st.session_state.db_search_result = reply
            else:
                st.session_state.db_search_result = "No documents matched your query."
    if st.session_state.db_search_result:
        st.text_area(
            "Search result",
            st.session_state.db_search_result,
            height=150,
            key=global_widget_key("db_search_result"),
        )

    for msg in st.session_state.kiroshi_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if user_msg := st.chat_input("Message", key=global_widget_key("kiroshi_chat_input")):
        if not api_key and base_url.startswith("https://api.openai.com"):
            st.error("Please set your OpenAI API key in the Debug tab.")
        else:
            history = st.session_state.kiroshi_chat_history.copy()
            try:
                reply = invoke_gpt(
                    user_msg,
                    history,
                    api_key,
                    model,
                    base_url,
                    source="kiroshi_chat",
                )
            except Exception as exc:
                logging.error("Kiroshi chat request failed: %s", exc)
                st.session_state.kiroshi_chat_history.append(
                    {"role": "user", "content": user_msg}
                )
                st.session_state.kiroshi_chat_history.append(
                    {"role": "assistant", "content": str(exc)}
                )
            else:
                st.session_state.kiroshi_chat_history.append(
                    {"role": "user", "content": user_msg}
                )
                st.session_state.kiroshi_chat_history.append(
                    {"role": "assistant", "content": reply}
                )
            save_memory(st.session_state.kiroshi_chat_history)
            st.rerun()
    if st.button("Clear memory", key=global_widget_key("kiroshi_clear")):
        st.session_state.kiroshi_chat_history = []
        save_memory([])
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
                "created_at": datetime.utcnow().isoformat(),
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
                if st.button("Remove", key=remove_key):
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
        st.selectbox("AI Mode", ["Cloud", "Local API", "Local Model"], key="ai_mode")
        if st.session_state.ai_mode == "Cloud":
            st.text_input("OpenAI API Key", type="password", key="openai_api_key")
            st.text_input("AI Base URL", key="ai_base_url")
        elif st.session_state.ai_mode == "Local API":
            st.text_input(
                "AI Base URL",
                key="ai_base_url",
                value=st.session_state.ai_base_url,
            )
            st.text_input(
                "API Key (optional)", type="password", key="openai_api_key"
            )
        else:
            st.session_state.ai_base_url = ""
            st.session_state.openai_api_key = ""
            st.info("Using local transformers model; no API key or Base URL required.")
        st.selectbox("Model", ["gpt-4o", "gpt-4", "gpt-3.5-turbo"], key="openai_model")
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


def _saved_case_files_signature() -> tuple[tuple[str, float], ...]:
    entries: list[tuple[str, float]] = []
    for path in DATABASE_DIR.glob("*.json"):
        if path.name.lower() in {"recent_cases.json", AI_LEARNING_FILE.name.lower()}:
            continue
        try:
            entries.append((path.name, path.stat().st_mtime))
        except FileNotFoundError:
            continue
    return tuple(sorted(entries))


def iter_saved_case_records() -> Iterable[tuple[Path, Mapping[str, object]]]:
    for path in DATABASE_DIR.glob("*.json"):
        if path.name.lower() in {"recent_cases.json", AI_LEARNING_FILE.name.lower()}:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception as exc:
            logging.warning("Failed to load saved case %s: %s", path, exc)
            continue
        if not isinstance(payload, Mapping):
            logging.debug("Ignoring non-mapping payload for %s", path)
            continue
        yield path, payload


def _create_ai_learning_dataset_from_cases(
    case_entries: Iterable[Mapping[str, object]],
    *,
    signature: Iterable[tuple[str, float]] | None = None,
    merged_sources: Iterable[str] | None = None,
    generated_at: str | None = None,
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
        "generated_at": generated_at or datetime.utcnow().isoformat() + "Z",
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

    return dataset


def load_ai_learning_dataset() -> dict[str, object] | None:
    if not AI_LEARNING_FILE.exists():
        return None
    try:
        with AI_LEARNING_FILE.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as exc:
        logging.error("Failed to load AI learning dataset: %s", exc)
        return None
    if not isinstance(payload, Mapping):
        logging.error("AI learning dataset is not a JSON object")
        return None
    return dict(payload)


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

    dataset = _create_ai_learning_dataset_from_cases(
        combined.values(),
        signature=signature,
        merged_sources=merged_sources,
    )
    return dataset


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

    return _create_ai_learning_dataset_from_cases(cases, signature=signature)


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
        df[["recurrence_count", "root_cause_recurrence"]].max(axis=1).astype(int)
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
        df[["recurrence_count", "analysis_recurrence"]].max(axis=1).astype(int)
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
    chart_data = counts.head(8).copy()
    if chart_data.empty:
        raise ValueError("No hay datos para el gráfico de recurrencia.")

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
    chart.categoryAxis.visibleTicks = False
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueStep = max(1, math.ceil(max_value / 4)) if max_value else 1
    chart.valueAxis.labelTextFormat = "%d"
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
            fontName="Helvetica-Bold",
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
            fontName="Helvetica",
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
            fontName="Helvetica",
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#4b5563"),
            angle=90,
        )
    )

    return drawing


def _build_timeline_chart(timeline: pd.DataFrame, title: str) -> Drawing:
    if timeline.empty:
        raise ValueError("No hay datos para la tendencia temporal.")

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
    chart.yValueAxis.valueMin = 0
    max_value = max(values) if values else 0
    chart.yValueAxis.valueStep = max(1, math.ceil(max_value / 4)) if max_value else 1
    chart.yValueAxis.labelTextFormat = "%d"

    drawing = Drawing(drawing_width, drawing_height)
    drawing.add(chart)
    drawing.add(
        String(
            drawing_width / 2,
            drawing_height - 20,
            title,
            fontName="Helvetica-Bold",
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
            fontName="Helvetica",
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
            fontName="Helvetica",
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
    styles = getSampleStyleSheet()
    story: list = []
    title_style = styles["Title"]
    body_style = styles["BodyText"]
    heading_style = styles["Heading4"]

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
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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
        if highlight_details:
            detail_lines = []
            for key in ["case_id", "title", "solution_excerpt"]:
                value = highlight_details.get(key)
                if value:
                    detail_lines.append(f"{key.replace('_', ' ').title()}: {value}")
            if detail_lines:
                story.append(Paragraph("<br/>".join(detail_lines), body_style))
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
            except Exception:
                story.append(
                    Paragraph(
                        f"No se pudo renderizar el gráfico de frecuencia ({title}).",
                        body_style,
                    )
                )

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
            except Exception:
                story.append(
                    Paragraph(
                        f"No se pudieron renderizar los gráficos de tendencia ({title}).",
                        body_style,
                    )
                )

    recurring_df = insights.get("recurring_issue_types")
    if isinstance(recurring_df, pd.DataFrame) and not recurring_df.empty:
        story.append(Paragraph("Patrones recurrentes", heading_style))
        rows = [["Caso", "Recurrencias"]]
        for _, row in recurring_df.head(10).iterrows():
            rows.append(
                [str(row.get("analysis_label", "")), str(row.get("count", 0))]
            )
        recurring_table = Table(rows, colWidths=[320, 120])
        recurring_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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
        rows = [["Causa", "Casos"]]
        for _, row in root_cause_df.head(10).iterrows():
            rows.append(
                [str(row.get("root_cause", "")), str(row.get("count", 0))]
            )
        root_table = Table(rows, colWidths=[320, 120])
        root_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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
        rows = [["Modelo", "Casos"]]
        for _, row in scanner_df.head(10).iterrows():
            rows.append([str(row.get("scanner", "")), str(row.get("count", 0))])
        scanner_table = Table(rows, colWidths=[320, 120])
        scanner_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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
        bug_table = Table(rows, colWidths=[120, 260, 120])
        bug_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ]
            )
        )
        story.append(bug_table)
        story.append(Spacer(1, 12))

    if bug_report:
        story.append(Paragraph("Resultados de Bug Detector", heading_style))
        summary = bug_report.get("summary")
        if summary:
            story.append(Paragraph(summary, body_style))
        recurring = bug_report.get("recurring_patterns") or []
        if recurring:
            rows = [["Patrón", "Recurrencias"]]
            for item in recurring[:10]:
                rows.append([str(item.get("pattern", "")), str(item.get("count", 0))])
            pattern_table = Table(rows, colWidths=[300, 120])
            pattern_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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
    doc.build(story)
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

    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    heading_style = styles["Heading3"]
    header_style = styles["Heading5"]

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
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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

    detail_table = Table(
        detail_rows,
        colWidths=[70, 120, 110, 110, 120],
        repeatRows=1,
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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
    doc.build(story)
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
        "generated_at": datetime.utcnow().isoformat() + "Z",
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
    file_path = DATABASE_DIR / f"{case.case_id}.json"
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
        last_modified_value = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    case.last_modified = str(last_modified_value)
    case_payload = asdict(case)
    case_payload["attachments"] = persist_case_attachments(case.case_id)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(case_payload, f, indent=2)
    if update_history:
        update_recent_cases(case.case_id, str(file_path))
    if notify:
        st.success(f"Case saved to {file_path}")
    st.session_state.ai_learning_signature = None
    st.session_state.ai_learning_data = None
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
    st.session_state.screenshots = screenshots

    scratch_key = widget_key("scratch", CURRENT_CASE_IDX)
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
        update_recent_cases(case_obj.case_id, source_path)
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


def touch_case_last_modified(*, timestamp: str | None = None) -> str:
    """Update the active case ``last_modified`` timestamp and return it."""

    if timestamp is None:
        timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    if isinstance(D, CaseData):
        D.last_modified = timestamp

    case_obj = st.session_state.get("case")
    if isinstance(case_obj, CaseData):
        case_obj.last_modified = timestamp

    st.session_state["last_modified"] = timestamp
    return timestamp


def _update_field(field: str):
    """Update dataclass field from session state and persist."""
    key = widget_key(field, CURRENT_CASE_IDX)
    new_value = st.session_state.get(key)
    previous = getattr(D, field)
    if new_value != previous:
        setattr(D, field, new_value)
        touch_case_last_modified()
        autosave()
    else:
        setattr(D, field, new_value)


def auto_text_input(label: str, field: str, container=st, **kwargs):
    """Text input that saves on every change."""
    key = widget_key(field, CURRENT_CASE_IDX)
    kwargs.setdefault("key", key)
    value = container.text_input(
        label, getattr(D, field), on_change=_update_field, args=(field,), **kwargs
    )
    setattr(D, field, value)


def auto_text_area(label: str, field: str, container=st, **kwargs):
    """Text area that saves on every change."""
    key = widget_key(field, CURRENT_CASE_IDX)
    kwargs.setdefault("key", key)
    value = container.text_area(
        label, getattr(D, field), on_change=_update_field, args=(field,), **kwargs
    )
    setattr(D, field, value)


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


def auto_toggle(label: str, field: str, container=st, **kwargs):
    key = widget_key(field, CURRENT_CASE_IDX)
    kwargs.setdefault("key", key)
    default_value = bool(getattr(D, field))
    alias_key = f"{field}_on"
    if key in st.session_state:
        current_value = bool(st.session_state.get(key))
    elif alias_key in st.session_state:
        current_value = bool(st.session_state.get(alias_key))
    else:
        current_value = default_value
    if alias_key not in st.session_state:
        st.session_state[alias_key] = current_value

    def _render_toggle(initial: bool) -> bool:
        return container.toggle(label, value=initial, **kwargs)

    try:
        value = _render_toggle(current_value)
    except StreamlitAPIException as exc:
        match = re.search(
            r"st\\.session_state\\.([^.\\s]+) does not exist", str(exc)
        )
        if match:
            missing_key = match.group(1)
            if missing_key not in st.session_state:
                st.session_state[missing_key] = current_value
            value = _render_toggle(current_value)
        else:
            raise

    previous_value = getattr(D, field)
    st.session_state[key] = value
    st.session_state[alias_key] = value
    if value != previous_value:
        setattr(D, field, value)
        touch_case_last_modified()
        autosave()

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
}


OPTIONAL_PROGRESS_CATEGORIES = {"DELL ESCALATION"}


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
            value = "Accidental Damage" if getattr(d, fld) else "Internal Damage"
        elif isinstance(value, bool):
            value = "Yes" if value else "No"
        rows.append({"Field": label, "Value": value})
    return pd.DataFrame(rows)


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
    return pd.DataFrame(dell_escalation_rows(d))


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
                st.session_state[widget_key("straumann", case_idx)] = merged_value
                st.session_state[widget_key("patterson", case_idx)] = merged_value
                touch_case_last_modified()
                autosave()
        else:
            cleared = False
            reseller_key = widget_key("reseller_case_number", case_idx)
            if reseller_key in st.session_state:
                st.session_state.pop(reseller_key)
            if D.patterson != "N/A":
                D.patterson = "N/A"
                st.session_state[widget_key("patterson", case_idx)] = "N/A"
                cleared = True
            if D.straumann != "N/A":
                D.straumann = "N/A"
                st.session_state[widget_key("straumann", case_idx)] = "N/A"
                cleared = True
            if cleared:
                touch_case_last_modified()
                autosave()

        name_cols = card.columns((1.3, 1, 1))
        auto_text_input("Company name", "company_name", container=name_cols[0])
        auto_text_input("Subscription ID", "subscription_id", container=name_cols[1])
        auto_text_input("Case ID", "case_id", container=name_cols[2])

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

        if compact_mode:
            card.subheader("Additional information")
        else:
            card.markdown("#### 🧠 Additional information")
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
    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    header_style = styles["Heading5"]
    elems = []
    for cat in cat_map:
        elems.append(Paragraph(cat, styles["Heading4"]))
        df = category_dataframe(cat, d, cat_map)
        data = [[Paragraph("Field", header_style), Paragraph("Value", header_style)]]
        for field, value in df.values.tolist():
            data.append([Paragraph(field, body_style), Paragraph(str(value), body_style)])
        t = Table(data, colWidths=[150, 350])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )
        elems.extend([t, Spacer(1, 12)])
    doc.build(elems)
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
    fields = [
        ("Reportable", "No"),
        ("Product Family", product),
        ("Product", topic),
        ("Sub-product", subtopic),
        ("Hardware test", "Yes" if d.hardware_test else "No"),
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
    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    header_style = styles["Heading5"]
    data = [[Paragraph("Field", header_style), Paragraph("Value", header_style)]]
    for field, value in fields:
        data.append([Paragraph(field, body_style), Paragraph(str(value), body_style)])
    t = Table(data, colWidths=[180, 320])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )
    doc.build([t])
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


def render_case_attachments_panel(
    case: CaseData, *, case_idx: int, tab_slug: str
) -> None:
    """Render the exports and attachments controls for a case tab."""

    attachments_key = partial(case_widget_key, tab_slug, case_idx=case_idx)

    st.markdown("---")
    st.subheader("Exports & attachments")

    new_files = st.file_uploader(
        "Upload screenshots / videos",
        accept_multiple_files=True,
        key=attachments_key("attachments_new_files"),
    )
    if new_files:
        existing_names = {f.name for f in st.session_state.uploads}
        for nf in new_files:
            if nf.name not in existing_names:
                st.session_state.uploads.append(nf)
                existing_names.add(nf.name)

    log_files = st.file_uploader(
        "Upload case logs",
        accept_multiple_files=True,
        key=attachments_key("attachments_log_files"),
    )
    if log_files:
        existing_log_names = {f.name for f in st.session_state.log_uploads}
        for lf in log_files:
            if lf.name not in existing_log_names:
                st.session_state.log_uploads.append(lf)
                existing_log_names.add(lf.name)

    screenshot_state_key = f"attachments_screenshot_name_{case_idx}"
    shared_screenshot_name = st.session_state.setdefault(screenshot_state_key, "")

    screenshot_widget_key = attachments_key("attachments_screenshot_name")
    if (
        screenshot_widget_key not in st.session_state
        or st.session_state[screenshot_widget_key] != shared_screenshot_name
    ):
        st.session_state[screenshot_widget_key] = shared_screenshot_name

    screenshot_name_input = st.text_input(
        "Screenshot name",
        key=screenshot_widget_key,
    )
    st.session_state[screenshot_state_key] = screenshot_name_input

    screenshot_name_value = st.session_state[screenshot_state_key]

    full_btn_col, region_btn_col = st.columns(2)
    if full_btn_col.button(
        "Take Screenshot",
        key=attachments_key("attachments_take_screenshot"),
    ):
        if screenshot_name_value:
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", screenshot_name_value)
            shot, error = capture_full_screenshot(safe_name)
            if shot:
                st.session_state.screenshots.append(shot)
                st.success(f"Captured screenshot: {safe_name}")
            else:
                st.error(error or "Screenshot capture is unavailable in this environment.")
        else:
            st.error("Please provide a screenshot name before capturing.")

    if region_btn_col.button(
        "Advanced Screenshot (select area)",
        key=attachments_key("attachments_take_region_screenshot"),
    ):
        if not screenshot_name_value:
            st.error("Please provide a screenshot name before capturing.")
        else:
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", screenshot_name_value)
            shot, error = capture_region_screenshot(safe_name)
            if shot:
                st.session_state.screenshots.append(shot)
                st.success(
                    "Captured targeted screenshot. Confirm it excludes unnecessary PHI before sharing."
                )
            else:
                message = error or "Unable to capture the selected region."
                if "cancel" in message.lower():
                    st.warning("Region capture cancelled—no image was saved.")
                elif "environment" in message.lower() or "available" in message.lower():
                    st.warning(message)
                else:
                    st.error(message)

    if (
        st.session_state.uploads
        or st.session_state.log_uploads
        or st.session_state.screenshots
    ):
        if st.session_state.uploads:
            st.markdown("Files queued:")
            for i, f in enumerate(st.session_state.uploads):
                cols = st.columns([8, 1])
                cols[0].markdown(f"• {f.name} ({len(f.getvalue())//1024} KB)")
                if cols[1].button(
                    "Remove",
                    key=attachments_key(f"attachments_rem_upload_{i}"),
                ):
                    st.session_state.uploads.pop(i)
                    st.rerun()
        if st.session_state.log_uploads:
            st.markdown("Logs queued:")
            for i, f in enumerate(st.session_state.log_uploads):
                cols = st.columns([8, 1])
                cols[0].markdown(f"• {f.name} ({len(f.getvalue())//1024} KB)")
                if cols[1].button(
                    "Remove",
                    key=attachments_key(f"attachments_rem_log_{i}"),
                ):
                    st.session_state.log_uploads.pop(i)
                    st.rerun()
        if st.session_state.screenshots:
            st.markdown("Screenshots captured:")
            for i, s in enumerate(st.session_state.screenshots):
                cols = st.columns([8, 1])
                cols[0].markdown(f"• {s.name} ({len(s.getvalue())//1024} KB)")
                if cols[1].button(
                    "Remove",
                    key=attachments_key(f"attachments_rem_shot_{i}"),
                ):
                    st.session_state.screenshots.pop(i)
                    st.rerun()
        if st.button(
            "Create ZIP",
            key=attachments_key("attachments_create_zip"),
        ):
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
                for f in st.session_state.uploads:
                    z.writestr(f"Screenshots/{f.name}", f.getvalue())
                for f in st.session_state.log_uploads:
                    z.writestr(f"logs/{f.name}", f.getvalue())
                for s in st.session_state.screenshots:
                    z.writestr(f"Screenshots/{s.name}", s.getvalue())
                if st.session_state.get("attachments_include_case_json", True):
                    z.writestr("case.json", json.dumps(asdict(case), indent=2))
            zbuf.seek(0)
            st.download_button(
                "Download attachments.zip",
                zbuf,
                file_name=f"{case.case_id or 'case'}_attachments.zip",
                mime="application/zip",
                key=attachments_key("attachments_download_zip"),
            )


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
    "Save/Load": "save_load",
    "I'm bored": "bored",
    "Debug": "debug",
}


def render_case_ui(case_idx: int):
    global CURRENT_CASE_IDX
    CURRENT_CASE_IDX = case_idx
    # ──────────── TABS ───────────
    if case_idx == 0:
        col_escal, col_hw = st.columns(2)
        with col_escal:
            st.session_state.include_escalations = st.toggle(
                "Include escalations",
                value=st.session_state.include_escalations,
            )
        with col_hw:
            st.session_state.include_hardware = st.toggle(
                "Include hardware issues",
                value=st.session_state.include_hardware,
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
        "Save/Load",
    ]
    if st.session_state.show_bored:
        tab_labels.append("I'm bored")
    if st.session_state.debug_mode:
        tab_labels.append("Debug")

    tabs = st.tabs(tab_labels)
    tab_iter = iter(tabs)
    tab_case = next(tab_iter)
    tab_tracking = next(tab_iter) if st.session_state.track_case else None
    tab_escalations = next(tab_iter) if st.session_state.include_escalations else None
    tab_email = next(tab_iter)
    tab_hw = next(tab_iter) if st.session_state.include_hardware else None
    tab_remote = next(tab_iter)
    tab_tables = next(tab_iter)
    tab_save_load = next(tab_iter)
    tab_bored = next(tab_iter) if st.session_state.show_bored else None
    tab_debug = next(tab_iter) if st.session_state.debug_mode else None

    # ================== 2ND LINE MODE TAB =================
    # ================== CASE TAB =================
    with tab_case:
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

            if st.button("Save case", key=case_tab_key("quick_save"), width="stretch"):
                save_case_to_database(D)
            if st.button(
                "Clear all",
                key=case_tab_key("clear_all_button"),
                width="stretch",
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
                    case_dict = asdict(D)
                    if not st.session_state.include_escalations:
                        for fld in [
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
                        ]:
                            case_dict.pop(fld, None)
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
                    user_message = (
                        learning_context
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
            if st.button("Categorize", key=case_tab_key("categorize_button"), width="stretch"):
                logging.info("Categorize button clicked")
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key in the Debug tab.")
                else:
                    taxonomy_block = st.session_state.taxonomy_block
                    signals_config = st.session_state.signals_config
                    if not taxonomy_block or not signals_config:
                        st.error("Please provide taxonomy and signals config in the Debug tab.")
                    else:
                        case_dict = asdict(D)
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
            if st.button("Ask", key=case_tab_key("ask_button"), width="stretch"):
                logging.info("Ask button clicked")
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key in the Debug tab.")
                else:
                    case_dict = asdict(D)
                    if not st.session_state.include_escalations:
                        for fld in [
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
                        ]:
                            case_dict.pop(fld, None)
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
            if st.button("Verify", key=case_tab_key("verify_button"), width="stretch"):
                logging.info("Verify button clicked")
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key in the Debug tab.")
                else:
                    case_dict = asdict(D)
                    if not st.session_state.include_escalations:
                        for fld in [
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
                        ]:
                            case_dict.pop(fld, None)
                    tone_directive = build_kiroshi_tone_directive()
                    user_message = (
                        f"You are Kiroshi, an experienced support case reviewer. {tone_directive} "
                        "Examine the case information below and help the agent finish the documentation.\n"
                        "Provide a plain-language response (no JSON) that includes:\n"
                        "- Specific fields that are missing, incomplete, or contradictory.\n"
                        "- Questions to ask the customer or reseller to gather the gaps.\n"
                        "- Clearer terminology or phrasing to replace confusing wording.\n"
                        "- Any reminders about mandatory fields, evidence, or follow-up actions.\n"
                        "Keep everything concise and under 200 words.\n\n"
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
                        logging.error("Verify request failed: %s", e)
                        st.error(str(e))
                    else:
                        st.session_state.kiroshi_chat_history.append({"role": "user", "content": user_message})
                        st.session_state.kiroshi_chat_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.kiroshi_chat_history)
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
            ):
                render_quick_actions_menu()
        else:
            bubble_label = "✕" if st.session_state[toggle_key] else "⚡"
            if st.button(
                bubble_label,
                key=case_tab_key("quick_actions_toggle_button"),
                width="stretch",
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
        if st.session_state.verify_result:
            st.markdown("#### Kiroshi Verification")
            st.markdown(st.session_state.verify_result)
        if st.session_state.ask_result:
            st.markdown("#### Kiroshi Suggestions")
            st.markdown(st.session_state.ask_result)
        if st.session_state.ai_assist_result:
            st.markdown("#### AI Assistance")
            st.markdown(st.session_state.ai_assist_result)
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
        with tab_email:
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
            if email_type == "Recap (Customer)":
                intro = build_email_intro(D)
                steps_summary = "\n".join(D.remote_steps.splitlines()) or "—"
                prompt = f"""You are a friendly IT‑support agent. Draft an engaging, upbeat email (≤180 words) that recaps the case and strongly
        motivates the customer to complete a brief satisfaction survey (takes <2 minutes) to help improve our service.
        Start the email exactly with the following lines (do not paraphrase or omit them):
        {intro}
        Include: Case ID, a brief summary of what happened, and the solution.
        Use a warm tone, thank the customer for their time, invite further questions, and end with a clear call‑to‑action to the survey.
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
                "Replacement Wired Scanner Setup",
                "Replacement Move+ Closure",
                "Dell Escalation Email",
            }
            if email_type not in static_templates:
                st.text_area(
                    prompt_label,
                    prompt,
                    height=300,
                    key=email_tab_key("api_prompt_area"),
                )
                st.session_state["last_prompt"] = prompt

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
                generated_email_key = email_tab_key("generated_email_output")
                if generated_email_key not in st.session_state:
                    st.session_state[generated_email_key] = st.session_state.get(
                        "generated_email", ""
                    )
                if st.button("Use GPT-OSS", key=email_tab_key("use_gpt")):
                    api_key = st.session_state.openai_api_key
                    model = st.session_state.openai_model
                    base_url = st.session_state.ai_base_url
                    if not api_key and base_url.startswith("https://api.openai.com"):
                        st.error("Please set your OpenAI API key in the Debug tab.")
                    elif not prompt.strip():
                        st.error("Prompt is empty.")
                    else:
                        with case_loading_overlay("Syncing with GPT-OSS intelligence…"):
                            try:
                                augmented_prompt = prompt
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
        with tab_tracking:
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
            ticket_number = st.text_input("Ticket Number", key=ticket_key)

            priority_key = tracking_tab_key("track_priority")
            st.session_state[priority_key] = normalize_priority(
                st.session_state.get(priority_key)
            )
            st.selectbox("Priority", PRIORITY_OPTIONS, key=priority_key)

            category_key = tracking_tab_key("track_category")
            st.text_input("Category", key=category_key)

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
                st.text_input("Status", key=status_key)

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

            case_link_key = tracking_tab_key("track_case_link")
            st.text_input("Case link (CRM)", key=case_link_key)

            if st.button("Save and track", key=tracking_tab_key("save_and_track")):
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
                    D.tracking.case_link = (
                        st.session_state.get(case_link_key, "") or ""
                    ).strip()
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
            ):
                D.tracking.active = False
                save_case_to_database(D, notify=False)
                st.session_state.track_case = False
                st.rerun()


    # ================== ESCALATIONS TAB =================
    if tab_escalations:
        with tab_escalations:
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
        with tab_hw:
            st.subheader("PC Hardware Issue")
            col_pc1, col_pc2 = st.columns(2)
            auto_text_input("Service Tag", "service_tag", container=col_pc1)
            auto_text_input("PC Model", "pc_model", container=col_pc2)
            auto_text_input("Windows version", "windows_version", container=col_pc1)
            auto_text_input("BIOS version", "bios_version", container=col_pc2)
            auto_text_input("Graphics Card", "graphics_card", container=col_pc1)
            auto_text_input("Processor", "processor", container=col_pc2)
            auto_text_input("Warranty", "warranty")
            st.subheader("Scanner Hardware Issue")
            col_sc1, col_sc2 = st.columns(2)
            auto_text_input("Scanner serial", "scanner_sn", container=col_sc1)
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
            auto_toggle(
                "Accidental damage?",
                "scanner_accidental_damage",
                container=col_sc2,
            )
            auto_toggle(
                "Hardware test completed?",
                "hardware_test",
                container=col_sc1,
            )
            st.dataframe(
                category_dataframe("SCANNER HARDWARE", D, HW_CATEGORY_MAP), width="stretch"
            )


    if tab_debug:
        with tab_debug:
            st.subheader("Case debug tools")
            render_autohotkey_panel(cat_map, case_idx)

    # ================== REMOTE SESSION TAB =================
    with tab_remote:
        remote_tab_key = partial(
            case_widget_key, CASE_TAB_SLUGS["Remote Session"], case_idx=case_idx
        )
        st.subheader("Remote sessions")
        ensure_remote_session_entries(D)
        sessions = D.remote_sessions

        action_cols = st.columns([1, 5])
        with action_cols[0]:
            if st.button(
                "Add session",
                key=remote_tab_key("remote_session_add"),
            ):
                new_session = RemoteSessionEntry(
                    title=f"Session {len(sessions) + 1}",
                    notes="",
                )
                sessions.append(new_session)
                update_case_remote_sessions(D, sessions)
                st.session_state[
                    remote_tab_key(
                        f"remote_session_title_{new_session.session_id}"
                    )
                ] = new_session.title
                st.session_state[
                    remote_tab_key(
                        f"remote_session_notes_{new_session.session_id}"
                    )
                ] = new_session.notes
                st.rerun()
        with action_cols[1]:
            st.caption(
                "Document each remote control session separately. Rename, reorder, or "
                "remove panels as needed."
            )

        for idx in range(len(sessions)):
            session = sessions[idx]
            if idx:
                st.markdown("---")
            container = st.container()
            with container:
                header_cols = st.columns([6, 1, 1, 1])
                title_key = remote_tab_key(
                    f"remote_session_title_{session.session_id}"
                )
                if title_key not in st.session_state:
                    st.session_state[title_key] = session.title
                new_title = header_cols[0].text_input(
                    "Title",
                    value=session.title,
                    key=title_key,
                )
                move_up_key = remote_tab_key(
                    f"remote_session_up_{session.session_id}"
                )
                move_down_key = remote_tab_key(
                    f"remote_session_down_{session.session_id}"
                )
                remove_key = remote_tab_key(
                    f"remote_session_remove_{session.session_id}"
                )
                with header_cols[1]:
                    if st.button(
                        "↑",
                        disabled=idx == 0,
                        key=move_up_key,
                        help="Move session up",
                    ):
                        sessions.insert(idx - 1, sessions.pop(idx))
                        update_case_remote_sessions(D, sessions)
                        st.rerun()
                with header_cols[2]:
                    if st.button(
                        "↓",
                        disabled=idx == len(sessions) - 1,
                        key=move_down_key,
                        help="Move session down",
                    ):
                        sessions.insert(idx + 1, sessions.pop(idx))
                        update_case_remote_sessions(D, sessions)
                        st.rerun()
                with header_cols[3]:
                    if st.button(
                        "Remove",
                        disabled=len(sessions) == 1,
                        key=remove_key,
                        help="Delete this session panel",
                    ):
                        sessions.pop(idx)
                        if not sessions:
                            default_session = RemoteSessionEntry(
                                title="Session 1",
                                notes="",
                            )
                            sessions.append(default_session)
                        update_case_remote_sessions(D, sessions)
                        st.rerun()

                if new_title != session.title:
                    session.title = new_title
                    session.touch()
                    update_case_remote_sessions(D, sessions)
                    sessions = D.remote_sessions
                    session = sessions[idx]
                    st.session_state[title_key] = session.title

                timestamp_parts: list[str] = []
                created_value = (session.created_at or "").strip()
                updated_value = (session.updated_at or "").strip()
                if created_value:
                    timestamp_parts.append(f"Created: {created_value}")
                if updated_value and updated_value != created_value:
                    timestamp_parts.append(f"Updated: {updated_value}")
                if timestamp_parts:
                    st.caption(" · ".join(timestamp_parts))

                notes_key = remote_tab_key(
                    f"remote_session_notes_{session.session_id}"
                )
                if notes_key not in st.session_state:
                    st.session_state[notes_key] = session.notes
                new_notes = st.text_area(
                    "Session notes",
                    session.notes,
                    height=800,
                    key=notes_key,
                )
                if new_notes != session.notes:
                    session.notes = new_notes
                    session.touch()
                    update_case_remote_sessions(D, sessions)
                    sessions = D.remote_sessions
                    session = sessions[idx]
                    st.session_state[notes_key] = session.notes



    # ================== TABLES TAB =================
    with tab_tables:
        tables_tab_key = partial(
            case_widget_key, CASE_TAB_SLUGS["Tables"], case_idx=case_idx
        )
        st.subheader("Copy all tables")
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


    # ================== SAVE/LOAD TAB =================
    with tab_save_load:
        save_tab_key = partial(
            case_widget_key, CASE_TAB_SLUGS["Save/Load"], case_idx=case_idx
        )
        st.subheader("Save / Load")
        col_save, col_load = st.columns(2)
        with col_save:
            if st.button("Save", key=save_tab_key("save_case_button")):
                save_case_to_database(D)
        with col_load:
            uploaded_case = st.file_uploader(
                "Select case JSON",
                type="json",
                key=save_tab_key("load_case_uploader"),
            )
            if uploaded_case and st.button(
                "Load", key=save_tab_key("load_case_button")
            ):
                request_load_from_bytes(uploaded_case.getvalue())

        st.subheader("Case Dex")
        dex_case_id = st.text_input(
            "Case ID", key=save_tab_key("case_dex_id")
        )
        if st.button("Fetch Case Dex", key=save_tab_key("fetch_case_dex")):
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
        for idx, case in enumerate(load_recent_cases()):
            info_col, btn_col = st.columns([3, 1])
            last_modified_display = format_last_modified(case.get("last_modified"))
            if last_modified_display:
                info_col.write(
                    f"{case['case_id']} ({last_modified_display})\n{case['path']}"
                )
            else:
                info_col.write(f"{case['case_id']}\n{case['path']}")
            if btn_col.button("Load", key=save_tab_key(f"recent_load_{idx}")):
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


    # ================== BORED TAB =================
    if tab_bored:
        with tab_bored:
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
            if st.button("Explore", key=bored_tab_key("bored_explore")):
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
            if st.button("Launch arena", key=widget_key("launch_arena", case_idx)):
                game_path = Path(__file__).parent / "doom_game.py"
                subprocess.Popen([sys.executable, str(game_path)])

    render_case_attachments_panel(
        D,
        case_idx=case_idx,
        tab_slug="attachments",
    )

    autosave()

reminder_state = _refresh_wellness_reminder_state()
render_wellness_alert(reminder_state)

case_labels = [
    cs.case.case_id or f"Case {i+1}" for i, cs in enumerate(st.session_state.case_sessions)
] + ["+ New Case"]
tab_labels: list[str] = ["Dashboard", "Saved Cases", "Settings"]
if st.session_state.debug_mode:
    tab_labels.append("Debug")
show_kiroshi_chat = st.session_state.get("show_kiroshi_chat", True)
tab_labels.append("Report")
if show_kiroshi_chat:
    tab_labels.append("Kiroshi Chat")
tab_labels += case_labels
all_tabs = st.tabs(tab_labels)

tab_index = 0
with all_tabs[tab_index]:
    render_with_monitor("Dashboard", render_dashboard, tab_label="Dashboard")
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
if show_kiroshi_chat:
    with all_tabs[tab_index]:
        render_with_monitor(
            "Kiroshi Chat", render_kiroshi_chat_panel, tab_label="Kiroshi Chat"
        )
    tab_index += 1

case_tabs = all_tabs[tab_index:]
for idx, tab in enumerate(case_tabs):
    with tab:
        if idx == len(st.session_state.case_sessions):
            if st.button("Add Case"):
                st.session_state.case_sessions.append(CaseSession(case=CaseData()))
                _sync_case_memory_from_sessions()
                st.rerun()
        else:
            case_label = case_labels[idx]
            render_with_monitor(
                f"Case: {case_label}",
                _render_case_tab,
                idx,
                tab_label=case_label,
                case_index=idx,
            )

show_failure_modal()
show_incident_report_modal()
