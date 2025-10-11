# -*- coding: utf-8 -*-
"""
Kiroshi RC 1.7.2111025 – IT Case Documentation Helper
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
import random
import subprocess
import sys
import math
import calendar
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from html import escape
import textwrap
import inspect

import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components
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
from aatom_chat import (
    load_memory,
    save_memory,
    query_atom,
    SYSTEM_PROMPT,
    load_manual_docs,
    save_manual_docs,
    search_manual_docs,
    get_assistant_notes,
    set_assistant_notes,
    build_assistant_memory_prompt,
)

# Some corporate networks perform SSL interception with a self-signed
# certificate, which breaks standard certificate validation.  Disable
# warnings and certificate verification for outbound requests so the
# ChatGPT API and GitHub update checks can still be reached.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

VERSION = "RC 1.7.2111025"
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
# Point the default to the new canonical repository so users no longer see the
# "Unable to retrieve remote version" warning on startup.
DEFAULT_UPDATE_REPO = "Anoth3rHellsing/KiroshiDocumentationSystem"
DEFAULT_UPDATE_BRANCH = "main"
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
    "case_compact_mode": False,
    "show_atom_chat": True,
    "autosave_to_database": False,
    "ai_assist_mode": "Standard",
    "ai_educate_enabled": False,
    "ai_educate_report_enabled": False,
    "ai_educate_advanced": False,
    "tutorial_completed": False,
    "tutorial_completed_at": "",
    "tutorial_completion_type": "",
    "enable_holiday_theme": True,
    "wellness_reminders": DEFAULT_WELLNESS_SETTINGS,
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


def _tokenize_issue_description(text: str) -> list[str]:
    cleaned = _CASE_REFERENCE_PATTERN.sub(" ", text)
    cleaned = _SERIAL_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"[^0-9A-Za-z]+", " ", cleaned)
    tokens = [token.lower() for token in cleaned.split() if len(token) >= 3]
    return [token for token in tokens if token not in _GENERIC_STOPWORDS and not token.isdigit()]


def _derive_analysis_label(row: Mapping[str, object]) -> str:
    text_candidates: list[str] = []
    for key in ("category", "classification", "topic", "root_cause", "title", "description_excerpt", "solution"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            text_candidates.append(value)

    if not text_candidates:
        return "General"

    tokens: list[str] = []
    for text in text_candidates:
        tokens.extend(_tokenize_issue_description(text))

    if not tokens:
        return "General"

    top_tokens: list[str] = []
    for token, _ in Counter(tokens).most_common():
        if token not in top_tokens:
            top_tokens.append(token)
        if len(top_tokens) >= 3:
            break

    if not top_tokens:
        return "General"

    return " / ".join(token.title() for token in top_tokens)
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


def _resolve_update_target() -> tuple[str, str]:
    repo = os.environ.get("KIROSHI_UPDATE_REPO", DEFAULT_UPDATE_REPO).strip()
    branch = os.environ.get("KIROSHI_UPDATE_BRANCH", DEFAULT_UPDATE_BRANCH).strip()
    if not repo:
        repo = DEFAULT_UPDATE_REPO
    if "/" not in repo:
        raise ValueError(
            "Invalid GitHub repository configured for updates. Use the form 'owner/repository'."
        )
    if not branch:
        branch = DEFAULT_UPDATE_BRANCH
    return repo, branch


def _iter_remote_app_paths() -> Iterable[str]:
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

    # Built-in defaults that cover the most common layouts.
    yield from (
        "case_documentation_app.py",
        "KiroshiDocumentationSystem/case_documentation_app.py",
        "src/case_documentation_app.py",
        "app/case_documentation_app.py",
    )


def _fetch_remote_version(repo: str, branch: str) -> str:
    candidate_paths = list(dict.fromkeys(_iter_remote_app_paths()))

    last_error: Exception | None = None
    for path in candidate_paths:
        raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
        try:
            response = requests.get(raw_url, timeout=UPDATE_CHECK_TIMEOUT, verify=False)
            response.raise_for_status()
        except requests.HTTPError as exc:
            # If the file is not present at this location, try the next candidate.
            if exc.response is not None and exc.response.status_code == 404:
                last_error = exc
                continue
            raise
        except requests.RequestException as exc:  # pragma: no cover - network errors
            last_error = exc
            continue

        match = re.search(r"^VERSION\s*=\s*[\"']([^\"']+)[\"']", response.text, re.MULTILINE)
        if not match:
            raise RuntimeError("VERSION marker not found in remote application source.")
        return match.group(1).strip()

    if last_error:
        raise FileNotFoundError(
            "Unable to locate case_documentation_app.py in the configured repository"
        ) from last_error
    raise FileNotFoundError("No candidate paths were available for the update check")


def _fetch_latest_commit_info(repo: str, branch: str) -> dict[str, str | None]:
    api_url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    headers = {"Accept": "application/vnd.github+json"}
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
    else {"use_container_width": True}
)

AI_LEARNING_FILE = UTILITIES_DIR / "AILearning.json"

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
            "options": ["Dashboard", "Settings", "A.A.T.O.M. Chat"],
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
            "options": ["Dashboard", "Report", "A.A.T.O.M. Chat"],
            "answer": "Report",
            "success": "Exactly — open the Report tab once AI Educate is enabled to export insights.",
            "failure": "The analytics live in the Report tab right next to Settings.",
        },
    },
    {
        "id": "settings",
        "title": "Settings & Personalisation",
        "visual": "settings_overview",
        "description": textwrap.dedent(
            """
            Settings control 2nd Line mode, debug tools, AI Educate options, and now your onboarding history.
            Use this panel to toggle advanced assistance, import or export Educate datasets, and relaunch this tutorial whenever you like.
            Your completion status is saved in the persistent configuration so first-time use is recorded automatically.
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
        "id": "atom",
        "title": "A.A.T.O.M. Chat & Resources",
        "visual": "chat_resources",
        "description": textwrap.dedent(
            """
            A.A.T.O.M. Chat keeps a searchable manual database, including a new quick-reference summary of the README
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

INSTALLER_FILENAME = "KiroshiInstaller_RC-1-7-2111025.bat"


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
            "KiroshiInstaller_RC-1-7-2111025.bat manually from the installation media."
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
        "and run `KiroshiInstaller_RC-1-7-2111025.bat` manually."
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
    """Wrapper around :func:`query_atom` that logs request lifecycle details."""

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
        reply = query_atom(prompt, history, api_key, model, base_url)
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
ATOM_LOGO_PATH = ASSETS_DIR / "atom_logo.png"

GLADOS_MESSAGES = [
    "Good morning! Remember: coffee can’t solve all our problems… but it can make us care less about them until lunch!",
    "Hard work pays off in the future. Laziness pays off now, so let’s compromise!",
    "Teamwork makes the dream work… unless your team just wants coffee.",
    "My office dress code: business on the top, pajamas on the bottom. It’s called hybrid professionalism.",
    "Coworkers: a group chat you can’t leave, no matter how hard you try.",
    "Why work harder when you can work smarter… and blame it on your coworkers?",
    "I’m multitasking: procrastinating and being unproductive at the same time.",
    "The problem with communication is the other person. Especially on Mondays!",
    "Sometimes the best part of my job is that the chair swivels.",
    "If hard work is the key to success, most people would rather pick the lock.",
    "Doing nothing is hard. You never know when you’re done!",
    "My idea of a perfect workday is one where no actual work happens.",
    "A positive attitude may not solve all your problems, but it will annoy enough people to make it worth the effort.",
    "Payday is my favorite holiday.",
    "Going to work for a large company is like getting on a train. Are you moving, or is the train just dragging you along?",
    "Today's plan: pretend the plan is going to plan.",
    "Our Wi-Fi spirit animal is a sloth on a coffee break.",
    "Work-life balance: work on the left, life on the right monitor.",
    "Yes, we sell solutions. No, they don’t come with patience included.",
    "Your scanner is overheating? Try flossing the fan.",
    "Remember: one click by you = one headache for IT.",
    "If the scanner sounds like a drill, maybe it wants to be one.",
    "Yes, we’ll fix it. No, the reseller won’t help.",
    "Your device is down. At least your gums aren’t.",
    "If at first you don't succeed, try again after a snack break.",
    "Meetings are just emails that forgot how to type.",
    "Today’s forecast: 100% chance of not using all the tabs I opened.",
    "We put the 'pro' in procrastinate.",
    "If you need me, I'll be ignoring my email.",
    "My work playlist is just the same song on repeat until I finish something.",
    "Our password policy is 'please, just remember it this time.'",
    "Coffee: because adulting is hard.",
    "I like deadlines. I love the whooshing sound they make as they fly by.",
    "If the computer asks 'Are you sure?' it's probably judging you.",
    "A clean desk is a sign of a cluttered inbox.",
    "Do not disturb. I'm already disturbed.",
    "The best part of a conference call is pretending to care.",
    "Running out of toner builds character.",
    "Your keyboard called—it wants a vacation.",
    "Turn it off and on again: the universal sign of wisdom.",
    "Every bug you find is a feature waiting to be rebranded.",
    "Team lunch? You mean collective escape.",
    "I call it multitasking; my boss calls it 'Why is nothing done?'",
    "The printer isn't broken; it's just resting its eyes.",
    "Work hard, nap harder.",
    "Let's agree to disagree and then do it my way.",
    "My code never has bugs. It just develops random features.",
    "We can't all be morning people. Some of us are barely people.",
    "Your call is very important to us—please continue to hold until we care.",
    "This computer runs on hopes, dreams, and frequent restarts.",
    "If this meeting could be an email, the email could be nothing.",
    "Auto-save: because your work deserves a second chance.",
    "Be nice to the IT guy. He knows where the bodies are cached.",
    "Sometimes the only decision I make is to add more creamer.",
    "Ctrl+Z is my safety blanket.",
    "Our office motto: 'It worked yesterday.'",
    "Powered by caffeine and sheer confusion.",
    "Every day is a good day to stay in your pajamas.",
    "We don’t make mistakes; we create learning opportunities.",
    "Another day, another spreadsheet nobody understands.",
    "I thought I wanted a career; turns out I just wanted a paycheck.",
    "Productivity hack: do it tomorrow.",
    "Error 404: Motivation not found.",
    "My inbox has trust issues.",
    "I’m not bossy—I just have better ideas.",
    "Proofreading is for the weak.",
    "You’re not stuck in traffic; you are traffic.",
    "Success is 1% inspiration and 99% avoiding social media.",
    "Nothing says 'urgent' like three exclamation marks.",
    "Please limit all complaints to three sentences and one sigh.",
    "I only check my email to mark everything as unread again.",
    "Having a case of the Mondays on a Wednesday.",
    "Silence is golden—unless you have kids, then it's suspicious.",
    "Cayde-6 here—if a problem looks boring, throw a witty grenade at it.",
    "Heads up, Guardian: reboots are just Ghosts for your hardware.",
    "If you can't fix it, dance on the console until morale improves. —Cayde-6",
    "Legendary loot drop: a fully documented support ticket. Don't dismantle it.",
    "Cayde-6 pro tip: when in doubt, blame it on space pirates and move on.",
    "The only thing scarier than Monday is the printer jam.",
    # Diogenes
    "I am looking for an honest man.",
    "He has the most who is most content with the least.",
    "In a rich man's house there is no place to spit but his face.",
    "We have two ears and one tongue so that we would listen more and talk less.",
    "It is the privilege of the gods to want nothing, and of godlike men to want little.",
    "Dogs and philosophers do the greatest good and get the fewest rewards.",
    "I threw my cup away when I saw a child drinking from his hands.",
    "Blushing is the color of virtue.",
    "The foundation of every state is the education of its youth.",
    "Man is the most intelligent of the animals—and the most silly.",
    "Other dogs bite only their enemies; I bite also my friends to save them.",
    "A child has beaten me in plainness of living.",
    "The great thieves are leading away the little thief.",
    "It takes a wise man to discover a wise man.",
    "To get practice in being refused.",
    "Good men nowhere, but good boys at Sparta.",
    "I wish it were as easy to banish hunger by rubbing my belly.",
    "Nay, I defeat men, you defeat slaves.",
    "Come, see that you obey orders.",
    "Stand a little out of my sunshine.",
    # Aristotle
    "It is the mark of an educated mind to be able to entertain a thought without accepting it.",
    "We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
    "Well begun is half done.",
    "Pleasure in the job puts perfection in the work.",
    "The whole is greater than the sum of its parts.",
    "Happiness depends upon ourselves.",
    "Patience is bitter, but its fruit is sweet.",
    "Hope is a waking dream.",
    "Quality is not an act, it is a habit.",
    "The more you know, the more you realize you don't know.",
    "Educating the mind without educating the heart is no education at all.",
    "Knowing yourself is the beginning of all wisdom.",
    # Technoblade
    "Technoblade never dies.",
    "Blood for the Blood God.",
    "Not even close, baby!",
    "Fear is the greatest motivator.",
    (
        "Those that have treated me with kindness, I will repay that kindness tenfold. "
        "And those that treat me with injustice... I shall repay that injustice a thousand times over."
    ),
    "SUBSCRIBE TO TECHNOBLADE!",
    "I am a ninja.",
    "Imagine dating a woman, total simp move, bro…",
    "Some people say, what is dead may never die. But those guys are a bunch of idiots!",
    (
        "People that say that violence is not the answer, I think they’re just not that "
        "good at violence."
    ),
    "I don't just break the rules, I make them.",
    "Victory comes to those who refuse to give up.",
    "Strategy is the key to victory.",
    "Persistence is the key to success.",
    (
        "Oh man, the village got trashed! I’d hate to be the guy in charge of cleaning "
        "all this up… Wait a minute."
    ),
    "I went outside once and the sun hurt my eyes. 0/10 would not try again.",
    # Sun Tzu
    "Appear weak when you are strong, and strong when you are weak.",
    "If you know the enemy and know yourself, you need not fear the result of a hundred battles.",
    "In the midst of chaos, there is also opportunity.",
    "All warfare is based on deception.",
    "The greatest victory is that which requires no battle.",
]


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


DEFAULT_THEME = ThemePalette(
    key="default",
    name="Default",
    primary="#433878",
    accent="#7c3aed",
    background="#f7f8ff",
    surface="#ffffff",
    text="#111827",
    muted_text="#4b5563",
    glados_messages=GLADOS_MESSAGES,
)

HOLIDAY_THEMES: dict[str, ThemePalette] = {
    "new_year": ThemePalette(
        key="new_year",
        name="New Year's Day",
        primary="#0f172a",
        accent="#fbbf24",
        background="#0b1120",
        surface="#10172a",
        text="#f8fafc",
        muted_text="#94a3b8",
        glados_messages=[
            "Fresh calendar, fresh chance—let's make this year's cases legendary!",
            "New year, same scanners. Let’s keep them happier this time.",
            "Resolve to close cases faster than fireworks fade.",
        ],
    ),
    "mlk_day": ThemePalette(
        key="mlk_day",
        name="Martin Luther King Jr. Day",
        primary="#1f2937",
        accent="#60a5fa",
        background="#0f172a",
        surface="#16213c",
        text="#f9fafb",
        muted_text="#d1d5db",
        glados_messages=[
            "Support with dignity, lead with service—today and every day.",
            "Great support honors great dreams. Keep the mission moving.",
            "Clarity, empathy, action—our blueprint for better support.",
        ],
    ),
    "presidents_day": ThemePalette(
        key="presidents_day",
        name="Presidents' Day",
        primary="#1d4ed8",
        accent="#ef4444",
        background="#0f172a",
        surface="#152346",
        text="#f9fafb",
        muted_text="#cbd5f5",
        glados_messages=[
            "Lead every ticket like it’s a campaign promise kept.",
            "Checks, balances, and perfectly balanced documentation.",
            "Red, white, and resolve—let’s govern these cases.",
        ],
    ),
    "memorial_day": ThemePalette(
        key="memorial_day",
        name="Memorial Day",
        primary="#1f2937",
        accent="#ef4444",
        background="#111827",
        surface="#1f2937",
        text="#f3f4f6",
        muted_text="#9ca3af",
        glados_messages=[
            "Honor the service. Support with purpose.",
            "Resilience isn’t just for systems—carry it in every case.",
            "Today we remember by doing our best work for others.",
        ],
    ),
    "juneteenth": ThemePalette(
        key="juneteenth",
        name="Juneteenth",
        primary="#047857",
        accent="#dc2626",
        background="#022c22",
        surface="#04312a",
        text="#f0fdfa",
        muted_text="#a7f3d0",
        glados_messages=[
            "Freedom celebrated, progress documented.",
            "Empower every clinic, uplift every voice.",
            "Document the wins—equity in every fix.",
        ],
    ),
    "independence_day": ThemePalette(
        key="independence_day",
        name="Independence Day",
        primary="#1d4ed8",
        accent="#ef4444",
        background="#0f172a",
        surface="#172554",
        text="#f9fafb",
        muted_text="#cbd5f5",
        glados_messages=[
            "Liberty, justice, and scanners for all.",
            "Fireworks are loud—our fixes are louder.",
            "Stars, stripes, and spotless documentation.",
        ],
    ),
    "labor_day": ThemePalette(
        key="labor_day",
        name="Labor Day",
        primary="#2563eb",
        accent="#f59e0b",
        background="#0f172a",
        surface="#13203d",
        text="#f9fafb",
        muted_text="#cbd5f5",
        glados_messages=[
            "Hard work deserves smart workflows. Let’s automate the pain away.",
            "Celebrate progress—ship smoother support.",
            "Labor less, document more intelligently.",
        ],
    ),
    "columbus_day": ThemePalette(
        key="columbus_day",
        name="Indigenous Peoples' Day",
        primary="#7c3aed",
        accent="#f97316",
        background="#1f172a",
        surface="#2a1f3d",
        text="#fdf4ff",
        muted_text="#d8b4fe",
        glados_messages=[
            "Respect every journey—map the customer path clearly.",
            "Discover better processes, honor every story.",
            "Chart success with empathy and precision.",
        ],
    ),
    "veterans_day": ThemePalette(
        key="veterans_day",
        name="Veterans Day",
        primary="#1f2937",
        accent="#3b82f6",
        background="#0f172a",
        surface="#1f2937",
        text="#f9fafb",
        muted_text="#d1d5db",
        glados_messages=[
            "Serve those who served with flawless follow-up.",
            "Precision, honor, gratitude—build them into every note.",
            "Support that stands at attention.",
        ],
    ),
    "thanksgiving": ThemePalette(
        key="thanksgiving",
        name="Thanksgiving",
        primary="#b45309",
        accent="#d97706",
        background="#422006",
        surface="#78350f",
        text="#fef3c7",
        muted_text="#fde68a",
        glados_messages=[
            "Grateful users, grateful agents—pass the uptime.",
            "Feast on solutions, serve seconds of documentation.",
            "Gobble up those recurring issues before they multiply.",
        ],
    ),
    "christmas": ThemePalette(
        key="christmas",
        name="Christmas",
        primary="#047857",
        accent="#b91c1c",
        background="#03110c",
        surface="#0f1f17",
        text="#ecfdf5",
        muted_text="#a7f3d0",
        glados_messages=[
            "Wrap each fix with cheer and clarity.",
            "All we want for Christmas is zero escalations.",
            "Jingle all the way to a resolved queue.",
        ],
    ),
    "halloween": ThemePalette(
        key="halloween",
        name="Halloween",
        primary="#f97316",
        accent="#7c3aed",
        background="#111827",
        surface="#1f2937",
        text="#fef3c7",
        muted_text="#c4b5fd",
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


def get_glados_message(theme: ThemePalette | None = None) -> str:
    """Return a pseudo-random GLADoS message aligned with the active theme."""

    active_theme = theme or CURRENT_THEME
    messages = active_theme.glados_messages or GLADOS_MESSAGES
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
        }}
        html, body {{
            background:
                radial-gradient(circle at 15% 20%, var(--kiroshi-primary-glow) 0%, transparent 55%),
                radial-gradient(circle at 85% 12%, var(--kiroshi-accent-glow) 0%, transparent 60%),
                linear-gradient(165deg, {background_soft} 0%, {theme.background} 100%);
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
        }

        .tutorial-wrapper {
            margin: 1.5rem 0 2rem;
            padding: 1.6rem 1.9rem;
            border-radius: 1.2rem;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.12), rgba(255, 255, 255, 0.85));
            box-shadow: 0 18px 32px rgba(15, 23, 42, 0.16);
        }

        .tutorial-step-title {
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--kiroshi-primary);
            margin-bottom: 0.35rem;
        }

        .tutorial-intro {
            font-size: 0.98rem;
            line-height: 1.6;
            color: var(--kiroshi-text);
            margin-bottom: 1rem;
        }

        .tutorial-visual-card {
            padding: 1rem;
            border-radius: 1rem;
            background: rgba(255, 255, 255, 0.85);
            border: 1px solid rgba(209, 213, 219, 0.7);
            height: 100%;
        }

        .tutorial-footnote {
            font-size: 0.85rem;
            color: var(--kiroshi-muted);
        }

        .case-card {
            padding: 1.25rem 1.5rem;
            border-radius: 0.9rem;
            border: 1px solid rgba(15, 23, 42, 0.08);
            background: linear-gradient(145deg, var(--kiroshi-surface) 0%, rgba(255, 255, 255, 0.85) 100%);
            margin-bottom: 1rem;
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
            color: var(--kiroshi-text);
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
    glados_message = escape(get_glados_message(CURRENT_THEME))
    now = datetime.now()
    formatted_date = f"{now.strftime('%A')}, {now.month}/{now.day}/{now.year}"
    encoded_logo = base64.b64encode(KIROSHI_LOGO_PATH.read_bytes()).decode()
    holiday_theme_active = CURRENT_THEME.key != DEFAULT_THEME.key
    glados_card_background = (
        "#ffffff"
        if holiday_theme_active
        else "linear-gradient(145deg, color-mix(in srgb, var(--kiroshi-primary) 18%, transparent), color-mix(in srgb, var(--kiroshi-accent) 12%, transparent))"
    )
    glados_card_shadow = (
        "0 14px 34px rgba(15, 23, 42, 0.18)"
        if holiday_theme_active
        else "0 10px 25px rgba(15, 23, 42, 0.12)"
    )
    glados_card_border = (
        "1px solid rgba(15, 23, 42, 0.08)" if holiday_theme_active else "1px solid transparent"
    )
    glados_title_color = "#111827" if holiday_theme_active else "var(--kiroshi-primary)"
    glados_text_color = "#111827" if holiday_theme_active else "var(--kiroshi-text)"
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

        #kiroshi-header__glados {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 0 0.75rem;
            width: 100%;
        }}

        #kiroshi-header__glados-card {{
            background: {glados_card_background};
            border-radius: 1rem;
            padding: 1rem 1.5rem;
            box-shadow: {glados_card_shadow};
            max-width: 620px;
            width: 100%;
            margin: 0 auto;
            border: {glados_card_border};
        }}

        #kiroshi-header__glados-title {{
            font-size: 1.2rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            color: {glados_title_color};
            margin-bottom: 0.5rem;
        }}

        #kiroshi-header__glados-text {{
            font-size: 1.1rem;
            line-height: 1.6;
            color: {glados_text_color};
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

            #kiroshi-header__glados {{
                order: 2;
                padding: 0 1.5rem;
            }}

            #kiroshi-header__date {{
                order: 3;
                justify-content: center;
            }}

            #kiroshi-header__glados-card {{
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
        <div id="kiroshi-header__glados">
            <div id="kiroshi-header__glados-card">
                <div id="kiroshi-header__glados-title">GLADoS Daily Quip</div>
                <div id="kiroshi-header__glados-text">{glados_message}</div>
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
            ("A.A.T.O.M. Chat", "Assistant conversation, manual database, and quick reference."),
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
        st.dataframe(summary, use_container_width=True)
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
                    "Highlights": "Verify, Ask ATOM, Categorizer, AI Assist, and database search shortcuts.",
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
        st.dataframe(case_sections, use_container_width=True)
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
        st.dataframe(report_summary, use_container_width=True)
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
    elif kind == "chat_resources":
        col_chat, col_manual, col_reference = st.columns(3)
        with col_chat:
            st.markdown(
                "<div class='tutorial-visual-card'><strong>A.A.T.O.M. Chat</strong><br><span class='tutorial-footnote'>Persistent conversation history, Verify button context, and personality modes.</span></div>",
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
            "Ask ATOM to search for 'Kiroshi Quick Reference' whenever you need guidance on features or processes."
        )


def _mark_tutorial_completion(status: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    st.session_state.tutorial_completed = True
    st.session_state.tutorial_completion_type = status
    st.session_state.tutorial_completed_at = timestamp
    _persist_setting("tutorial_completed")
    _persist_setting("tutorial_completion_type")
    _persist_setting("tutorial_completed_at")
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

    with st.container():
        st.markdown("<div class='tutorial-wrapper'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='tutorial-step-title'>Step {} of {}: {}</div>".format(
                step_idx + 1, total_steps, escape(str(step.get("title", "")))
            ),
            unsafe_allow_html=True,
        )
        st.progress((step_idx + 1) / total_steps)
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
_init_state("atom_history", load_memory())
_init_state("assistant_notes", get_assistant_notes())
_init_state("manual_docs", load_manual_docs())
_init_state("verify_result", "")
_init_state("ask_result", "")
_init_state("categorizer_result", "")
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
# Tracking related state
_init_state("track_case", False)
_init_state("tracking_info", {})
# 2nd line mode and callback e‑mail options
_init_state("second_line_mode", _get_persistent_default("second_line_mode", False))
_init_state("case_compact_mode", _get_persistent_default("case_compact_mode", False))
_init_state("show_atom_chat", _get_persistent_default("show_atom_chat", True))
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
    remote_steps: str = ""
    root_cause: str = ""
    repro_steps: str = ""

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
    tracking: TrackingData = field(default_factory=TrackingData)
    kiroshi_version: str = VERSION
    last_modified: str = ""

    def __post_init__(self) -> None:
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

    if not (PYAUTOGUI_AVAILABLE or IMAGEGRAB_AVAILABLE):
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

    if img is None:
        return None, "Unable to capture the selected region."

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return InMemoryUploadedFile(f"{safe_name}.png", buf.getvalue()), None


@dataclass
class CaseSession:
    """Container for per-case session state."""

    case: CaseData
    uploads: list = field(default_factory=list)
    log_uploads: list = field(default_factory=list)
    screenshots: list = field(default_factory=list)


# convert stored dict to dataclass, ignoring unexpected fields
if isinstance(st.session_state.case, dict):
    allowed = {f.name for f in fields(CaseData)}
    filtered = {k: v for k, v in st.session_state.case.items() if k in allowed}
    st.session_state.case = CaseData(**filtered)
D: CaseData = st.session_state.case
if D.tracking.active:
    st.session_state.track_case = True

if "case_sessions" not in st.session_state:
    st.session_state.case_sessions = [
        CaseSession(
            case=D,
            uploads=st.session_state.uploads,
            log_uploads=st.session_state.log_uploads,
            screenshots=st.session_state.screenshots,
        )
    ]


def load_case_state(idx: int) -> None:
    cs = st.session_state.case_sessions[idx]
    st.session_state.case = cs.case
    st.session_state.uploads = cs.uploads
    st.session_state.log_uploads = cs.log_uploads
    st.session_state.screenshots = cs.screenshots
    global D
    D = st.session_state.case
    for key, value in asdict(D).items():
        st.session_state[key] = value


def save_case_state(idx: int) -> None:
    st.session_state.case_sessions[idx] = CaseSession(
        case=st.session_state.case,
        uploads=st.session_state.uploads,
        log_uploads=st.session_state.log_uploads,
        screenshots=st.session_state.screenshots,
    )


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
        st.session_state.scratch = ""
        st.session_state[widget_key("scratch", idx)] = ""
        for key in ("ai_assist_result", "verify_result", "ask_result", "categorizer_result"):
            if key in st.session_state:
                st.session_state[key] = "" if isinstance(st.session_state.get(key), str) else []
        st.session_state.ai_learning_matches = []

    ensure_tracking_session_defaults(idx, new_case.tracking, force=True)

    st.session_state.track_case = any(
        session.case.tracking.active for session in st.session_state.case_sessions
    )

    autosave()


def widget_key(base: str, idx: int) -> str:
    """Return a Streamlit widget key namespaced to a case index."""
    return f"{base}_{idx}"


def global_widget_key(base: str) -> str:
    """Return a Streamlit widget key reserved for global (non-case) widgets."""
    return f"global_{base}"


CURRENT_CASE_IDX = 0

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
                candidate_paths.append(base_dir / rel_path)
            if isinstance(name, str):
                candidate_paths.append(base_dir / fallback_subdir / name)
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


def update_tracked_priority(
    path: str,
    key: str,
    *,
    case_id: str | None = None,
    is_legacy: bool = False,
) -> None:
    new_priority = normalize_priority(st.session_state.get(key))
    if is_legacy:
        timestamp = update_tracked_case_file(path, priority=new_priority)
    else:
        timestamp = update_tracked_case_file(
            path, tracking_updates={"priority": new_priority}
        )
    target_case_id = case_id
    if target_case_id is None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            target_case_id = data.get("case_id")
        except Exception:
            target_case_id = None
    if target_case_id and D.case_id == target_case_id:
        D.tracking.priority = new_priority
        st.session_state[widget_key("track_priority", CURRENT_CASE_IDX)] = new_priority
        if timestamp:
            D.last_modified = timestamp
            if "case" in st.session_state:
                st.session_state.case.last_modified = timestamp
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
            D.last_modified = timestamp
            if "case" in st.session_state:
                st.session_state.case.last_modified = timestamp
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


def list_saved_cases(limit: int = 25) -> list:
    entries = []
    files = sorted(
        DATABASE_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list):
            dict_items = [item for item in data if isinstance(item, dict)]
            if len(dict_items) == 1:
                data = dict_items[0]
            else:
                continue
        if not isinstance(data, dict):
            continue
        raw_last_modified = data.get("last_modified")
        parsed_last_modified = parse_iso_datetime(raw_last_modified)
        if parsed_last_modified is None:
            parsed_last_modified = datetime.fromtimestamp(path.stat().st_mtime)
            raw_last_modified = parsed_last_modified.isoformat()
        entries.append(
            {
                "case_id": data.get("case_id") or path.stem,
                "company": data.get("company_name")
                or data.get("company")
                or "",
                "end_user": data.get("customer_name")
                or data.get("end_user")
                or "",
                "updated": parsed_last_modified,
                "last_modified": raw_last_modified,
                "path": str(path),
            }
        )
        if len(entries) >= limit:
            break
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
    cases: list, search_query: str = "", *, show_notifications: bool = True
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
        unique_suffix = f"{Path(case['path']).stem}_{idx}_{path_digest}"
        priority_value = normalize_priority(case.get("priority"))
        last_modified_display = format_last_modified(case.get("last_modified"))
        last_modified_dt = parse_iso_datetime(case.get("last_modified"))
        is_stale = False
        if last_modified_dt:
            try:
                is_stale = (now - last_modified_dt) > timedelta(hours=24)
            except Exception:
                is_stale = False
        if is_stale and show_notifications:
            st.warning(
                "Hey, this case is still pending updates, no updates after 24 hours. "
                f"Case ID: {case.get('case_id') or 'Unknown Case'}"
            )
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
            priority_key = f"priority_{unique_suffix}"
            status_key = f"status_{unique_suffix}"
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
        render_tracked_cases_dashboard(dell_cases, show_notifications=False)
    else:
        st.caption("No Dell escalations in the queue.")

    st.markdown("**FedEx Replacements**")
    if fedex_cases:
        render_tracked_cases_dashboard(fedex_cases, show_notifications=False)
    else:
        st.caption("No FedEx replacements awaiting action.")


def render_saved_cases_dashboard() -> None:
    saved_cases = list_saved_cases()
    if not saved_cases:
        st.info("No saved cases found in your database.")
        return
    weights = [1.2, 1.5, 1.5, 0.8]
    header_cols = st.columns(weights)
    header_cols[0].markdown("**Case ID**")
    header_cols[1].markdown("**Company**")
    header_cols[2].markdown("**Last Modified**")
    header_cols[3].markdown("**Load**")
    for case in saved_cases:
        row_cols = st.columns(weights)
        row_cols[0].write(case["case_id"])
        row_cols[1].write(case["company"])
        row_cols[2].write(case["updated"].strftime("%Y-%m-%d %H:%M"))
        if row_cols[3].button(
            "Load", key=f"saved_load_{Path(case['path']).stem}"
        ):
            request_load_from_path(case["path"], prefer_new_tab=True)


def render_dashboard() -> None:
    """Render the high-level dashboard overview tab."""

    st.markdown(
        "<div class='dashboard-title'>Dashboard</div>",
        unsafe_allow_html=True,
    )
    wellness_settings = _normalize_wellness_settings(
        st.session_state.get("wellness_reminders", DEFAULT_WELLNESS_SETTINGS)
    )
    st.session_state.wellness_reminders = wellness_settings
    upcoming_event = _calculate_next_wellness_event(wellness_settings)
    if upcoming_event:
        event_dt, event_key, meta = upcoming_event
        lead_minutes = wellness_settings.get(
            "notification_lead", DEFAULT_WELLNESS_SETTINGS["notification_lead"]
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
        tip = random.choice(WELLNESS_TIPS)
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
            "Show A.A.T.O.M. Chat tab",
            key="show_atom_chat",
            on_change=_on_setting_change("show_atom_chat"),
            help="Display or hide the conversational workspace when you need more focus.",
        )
    with mode_cols[1]:
        st.toggle(
            "Show Debug tab",
            key="debug_mode",
            on_change=_on_setting_change("debug_mode"),
        )
    if prev_debug and not st.session_state.debug_mode:
        st.session_state.debug_auth = False
        st.session_state.show_bored = False
        st.session_state.theme_preview = "auto"

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
    insights = collect_ai_educate_report_data(dataset)
    if not insights:
        st.info("Aún no hay suficientes casos guardados para generar estadísticas.")
        return

    cols = st.columns(4)
    cols[0].metric("Casos totales", insights.get("case_total", 0))
    cols[1].metric("Casos últimos 30 días", insights.get("recent_total", 0))
    cols[2].metric("Solucionados como bug", insights.get("bug_solution_count", 0))
    cols[3].metric("Menciones de 'bug'", insights.get("bug_mentions_count", 0))

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

    recent_counts = insights.get("recent_counts")
    if isinstance(recent_counts, pd.DataFrame) and not recent_counts.empty:
        st.markdown("### Casos más frecuentes (30 días)")
        st.dataframe(
            recent_counts.rename(
                columns={"analysis_label": "Caso", "count": "Frecuencia"}
            ),
            use_container_width=True,
        )
        freq_chart = (
            alt.Chart(recent_counts)
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X("count:Q", title="Casos"),
                y=alt.Y("analysis_label:N", sort="-x", title="Caso"),
                tooltip=["analysis_label", "count"],
            )
            .properties(height=260)
        )
        render_responsive_altair_chart(freq_chart)

    timeline = insights.get("timeline")
    if isinstance(timeline, pd.DataFrame) and not timeline.empty:
        st.markdown("### Tendencia últimos 30 días")
        timeline_chart = (
            alt.Chart(timeline)
            .mark_line(point=True)
            .encode(
                x=alt.X("timestamp:T", title="Fecha"),
                y=alt.Y("count:Q", title="Casos"),
                tooltip=["timestamp:T", "count:Q"],
            )
            .properties(height=220)
        )
        render_responsive_altair_chart(timeline_chart)

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
            use_container_width=True,
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


def render_atom_chat_panel() -> None:
    st.image(str(ATOM_LOGO_PATH), width=80)
    st.subheader("A.A.T.O.M. Chat")
    with st.expander("Personality Construct"):
        st.text_area(
            "System Prompt",
            st.session_state.get("system_prompt", SYSTEM_PROMPT),
            height=300,
            key=global_widget_key("system_prompt_display"),
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
    search_query = st.text_input(
        "Search query", key=global_widget_key("db_query")
    )
    if st.button(
        "Search in database", key=global_widget_key("db_search_button")
    ):
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
                        st.session_state.atom_history,
                        api_key,
                        model,
                        base_url,
                        source="manual_docs_search",
                    )
                except Exception as e:
                    logging.error("Manual docs GPT search failed: %s", e)
                    st.session_state.db_search_result = str(e)
                else:
                    st.session_state.atom_history.append(
                        {"role": "user", "content": f"[DB Search] {search_query}"}
                    )
                    st.session_state.atom_history.append(
                        {"role": "assistant", "content": reply}
                    )
                    save_memory(st.session_state.atom_history)
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

    for msg in st.session_state.atom_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if user_msg := st.chat_input("Message", key=global_widget_key("atom_chat_input")):
        if not api_key and base_url.startswith("https://api.openai.com"):
            st.error("Please set your OpenAI API key in the Debug tab.")
        else:
            history = st.session_state.atom_history.copy()
            try:
                reply = invoke_gpt(
                    user_msg,
                    history,
                    api_key,
                    model,
                    base_url,
                    source="atom_chat",
                )
            except Exception as e:
                logging.error("Atom chat request failed: %s", e)
                st.session_state.atom_history.append({"role": "user", "content": user_msg})
                st.session_state.atom_history.append(
                    {"role": "assistant", "content": str(e)}
                )
            else:
                st.session_state.atom_history.append({"role": "user", "content": user_msg})
                st.session_state.atom_history.append({"role": "assistant", "content": reply})
            save_memory(st.session_state.atom_history)
            st.rerun()
    if st.button("Clear memory", key=global_widget_key("atom_clear")):
        st.session_state.atom_history = []
        save_memory([])
        st.rerun()


def render_smart_aid_panel() -> None:
    st.subheader("Smart Aid Calibration")
    st.markdown(
        "Capture supervisor feedback once and let every AI feature remind you about it automatically."
    )

    default_areas = ["AI Assistance", "Quick Actions", "A.A.T.O.M. Chat"]
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
        help="Smart Aid keeps a single memory shared with AI Assistance, Quick Actions, and A.A.T.O.M.",
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
            save_memory(st.session_state.atom_history)
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
                    save_memory(st.session_state.atom_history)
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
        troubleshooting = str(
            record.get("remote_steps")
            or record.get("troubleshooting")
            or ""
        ).strip()
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
    df["analysis_label"] = df.apply(_derive_analysis_label, axis=1)

    now = pd.Timestamp.utcnow().tz_localize(None)
    recent_cutoff = now - pd.Timedelta(days=30)
    recent_cases = df[df["timestamp"] >= recent_cutoff]

    recent_counts = (
        recent_cases.groupby("analysis_label")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    overall_counts = (
        df.groupby("analysis_label")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    highlight_case: dict[str, object] | None = None
    highlight_label = None
    highlight_count = 0
    if not overall_counts.empty:
        row = overall_counts.iloc[0]
        highlight_label = str(row["analysis_label"])
        highlight_count = int(row["count"])
        candidate = (
            df[df["analysis_label"] == highlight_label]
            .sort_values("timestamp", ascending=False)
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

    timeline = pd.DataFrame(columns=["timestamp", "count"])
    if not recent_cases.empty:
        timeline = (
            recent_cases.set_index("timestamp")
            .resample("D")
            .size()
            .rename("count")
            .reset_index()
        )

    return {
        "recent_counts": recent_counts,
        "timeline": timeline,
        "bug_cases": bug_cases,
        "bug_mentions_count": int(bug_mask.sum()),
        "bug_solution_count": int(bug_solution_mask.sum()),
        "highlight_case": highlight_case,
        "highlight_label": highlight_label,
        "highlight_count": highlight_count,
        "recent_total": int(len(recent_cases)),
        "case_total": int(len(df)),
    }


def _build_recent_counts_chart(recent_counts: pd.DataFrame) -> Drawing:
    chart_data = recent_counts.head(8).copy()
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
            "Casos más frecuentes (30 días)",
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


def _build_timeline_chart(timeline: pd.DataFrame) -> Drawing:
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
            "Volumen de casos por día (30 días)",
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

    summary_data = [
        ["Total de casos", str(insights.get("case_total", 0))],
        ["Casos analizados (30 días)", str(insights.get("recent_total", 0))],
        [
            "Casos con solución marcada como bug",
            str(insights.get("bug_solution_count", 0)),
        ],
        [
            "Casos con mención de bug",
            str(insights.get("bug_mentions_count", 0)),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[240, 120])
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

    recent_counts = insights.get("recent_counts")
    if isinstance(recent_counts, pd.DataFrame) and not recent_counts.empty:
        try:
            drawing = _build_recent_counts_chart(recent_counts)
            story.append(drawing)
            story.append(Spacer(1, 12))
        except Exception:
            story.append(
                Paragraph(
                    "No se pudieron renderizar los gráficos de recurrencia reciente.",
                    body_style,
                )
            )

    timeline = insights.get("timeline")
    if isinstance(timeline, pd.DataFrame) and not timeline.empty:
        try:
            drawing = _build_timeline_chart(timeline)
            story.append(drawing)
            story.append(Spacer(1, 12))
        except Exception:
            story.append(
                Paragraph(
                    "No se pudieron renderizar los gráficos de tendencia temporal.",
                    body_style,
                )
            )

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
                "troubleshooting": str(
                    entry.get("troubleshooting")
                    or entry.get("remote_steps")
                    or ""
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
        for item in raw_cases:
            if isinstance(item, Mapping):
                normalized_cases.append(
                    {
                        "case_id": str(item.get("case_id") or ""),
                        "title": str(item.get("title") or ""),
                        "root_cause": str(item.get("root_cause") or ""),
                        "solution": str(item.get("solution") or ""),
                        "troubleshooting": str(
                            item.get("troubleshooting")
                            or item.get("remote_steps")
                            or ""
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

    for case in normalized_cases:
        detail_rows.append(
            [
                _to_paragraph(case.get("case_id", "")),
                _to_paragraph(case.get("title", "")),
                _to_paragraph(case.get("repro_steps", "")),
                _to_paragraph(case.get("troubleshooting", "")),
                _to_paragraph(case.get("solution", "")),
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
                    "troubleshooting": str(
                        case_row.get("troubleshooting")
                        or case_row.get("remote_steps")
                        or ""
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


def load_case_from_path(path: str) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        attachments_data: Mapping[str, Iterable[Mapping[str, object]]] | dict = {}
        if isinstance(raw_data, Mapping):
            attachments_raw = raw_data.get("attachments", {})
            if isinstance(attachments_raw, Mapping):
                attachments_data = attachments_raw
        filtered = {k: v for k, v in raw_data.items() if k in CaseData.__annotations__}
        st.session_state.case = CaseData(**filtered)
        global D
        D = st.session_state.case
        uploads, log_uploads, screenshots = load_case_attachments(
            D.case_id,
            attachments_data,
        )
        st.session_state.uploads = uploads
        st.session_state.log_uploads = log_uploads
        st.session_state.screenshots = screenshots
        if "case_sessions" in st.session_state and CURRENT_CASE_IDX < len(st.session_state.case_sessions):
            st.session_state.case_sessions[CURRENT_CASE_IDX] = CaseSession(
                case=D,
                uploads=uploads,
                log_uploads=log_uploads,
                screenshots=screenshots,
            )
        autosave()
        update_recent_cases(st.session_state.case.case_id, path)
        save_case_to_database(
            st.session_state.case,
            notify=False,
            update_history=False,
            touch_last_modified=False,
        )
        ensure_tracking_session_defaults(
            CURRENT_CASE_IDX, st.session_state.case.tracking, force=True
        )
        # Enable tracking tab if loaded from tracked directory or active file
        p = Path(path)
        if st.session_state.case.tracking.active:
            st.session_state.track_case = True
        elif p.parent == TRACKED_CASES_DIR or p.name.endswith("_Active.json"):
            st.session_state.track_case = True
        else:
            st.session_state.track_case = False
        st.success("Case loaded successfully.")
        trigger_hard_reload()
    except Exception as e:
        st.error(f"Failed to load case: {e}")


def load_case_from_bytes(data: bytes) -> None:
    try:
        payload = json.loads(data.decode("utf-8"))
        attachments_data: Mapping[str, Iterable[Mapping[str, object]]] | dict = {}
        if isinstance(payload, Mapping):
            attachments_raw = payload.get("attachments", {})
            if isinstance(attachments_raw, Mapping):
                attachments_data = attachments_raw
        payload = {k: v for k, v in payload.items() if k in CaseData.__annotations__}
        st.session_state.case = CaseData(**payload)
        global D
        D = st.session_state.case
        uploads, log_uploads, screenshots = load_case_attachments(
            D.case_id,
            attachments_data,
        )
        st.session_state.uploads = uploads
        st.session_state.log_uploads = log_uploads
        st.session_state.screenshots = screenshots
        if "case_sessions" in st.session_state and CURRENT_CASE_IDX < len(st.session_state.case_sessions):
            st.session_state.case_sessions[CURRENT_CASE_IDX] = CaseSession(
                case=D,
                uploads=uploads,
                log_uploads=log_uploads,
                screenshots=screenshots,
            )
        autosave()
        save_case_to_database(
            st.session_state.case,
            notify=False,
            update_history=False,
            touch_last_modified=False,
        )
        ensure_tracking_session_defaults(
            CURRENT_CASE_IDX, st.session_state.case.tracking, force=True
        )
        st.session_state.track_case = bool(st.session_state.case.tracking.active)
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
    if session.scratch and session.scratch.strip():
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


def _update_field(field: str):
    """Update dataclass field from session state and persist."""
    key = widget_key(field, CURRENT_CASE_IDX)
    setattr(D, field, st.session_state.get(key))
    autosave()


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
        autosave()


def auto_toggle(label: str, field: str, container=st, **kwargs):
    key = widget_key(field, CURRENT_CASE_IDX)
    kwargs.setdefault("key", key)
    value = container.toggle(label, value=bool(getattr(D, field)), **kwargs)
    if value != getattr(D, field):
        setattr(D, field, value)
        st.session_state[key] = value
        autosave()

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


def active_category_map():
    cm = BASE_CATEGORY_MAP.copy()
    if st.session_state.get("second_line_mode"):
        cm["HEADER"] = ["straumann"] + cm.get("HEADER", [])
    if not st.session_state.get("include_escalations", True):
        cm.pop("AX COORDINATORS", None)
        cm.pop("ESCALATION 2ND LINE", None)
    if st.session_state.get("include_hardware"):
        cm.update(HW_CATEGORY_MAP)
    return cm

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
    return f"""3Q({date_str})

Hello, Advanced support team,

We need your assistance in this case:

{d.brief_description}

HJ article or possible root cause found

{d.root_cause}

How to reproduce it:

{d.repro_steps}

Troubleshoot summary:

{d.remote_steps}

For more specific information, check the TV session.

Comments:

{d.additional_info}

Contact information:
Reseller Name:
Reseller Phone Number:
Reseller Phone Number 2:
Reseller email:
Clinic rep name:
Clinic rep phone number:
Clinic rep phone number 2:
TV ID: {d.teamviewer_id}
TV Customer Pass: {d.teamviewer_password}
Unite pin: {d.subscription_id}

Find all screenshots and logs on the internal note.

Finally, you can remind the person to add on an attached notepad or over Teams the 3Shape account credentials and the computer password.
"""


def category_dataframe(
    cat: str, d: CaseData, cat_map: Mapping[str, Iterable[str]] | None
) -> pd.DataFrame:
    """Return a DataFrame with human readable field names for a category."""
    rows = []
    for fld in (cat_map or {}).get(cat, []):
        value = getattr(d, fld, "N/A")
        label = fld.replace("_", " ").title()
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
        lines.append(f"{label}: {display}")
    return "\n".join(lines)


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
    container.subheader("Case Header")
    if st.session_state.second_line_mode:
        reseller_key = widget_key("reseller_case_number", case_idx)
        default_value = st.session_state.get(
            reseller_key, D.straumann or D.patterson or ""
        )
        st.session_state[reseller_key] = default_value
        merged_value = container.text_input(
            "Reseller case # (Straumann / Patterson)",
            default_value,
            key=reseller_key,
        )
        if merged_value != D.straumann or merged_value != D.patterson:
            D.straumann = merged_value
            D.patterson = merged_value
            st.session_state[widget_key("straumann", case_idx)] = merged_value
            st.session_state[widget_key("patterson", case_idx)] = merged_value
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
            autosave()

    name_cols = container.columns((1.3, 1, 1))
    auto_text_input("Company name", "company_name", container=name_cols[0])
    auto_text_input("Subscription ID", "subscription_id", container=name_cols[1])
    auto_text_input("Case ID", "case_id", container=name_cols[2])

    details_cols = container.columns((2, 1))
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

    version_col.subheader("Support Fee")
    ct_key = widget_key("customer_trios_only", case_idx)
    sf_key = widget_key("support_fee_accepted", case_idx)
    customer_trios_only = version_col.toggle(
        "Customer is TRIOS Only?",
        value=st.session_state.get(ct_key, D.customer_trios_only),
        key=ct_key,
        on_change=_update_field,
        args=("customer_trios_only",),
    )
    if customer_trios_only:
        version_col.toggle(
            "Support fee price accepted?",
            value=st.session_state.get(sf_key, D.support_fee_accepted),
            key=sf_key,
            on_change=_update_field,
            args=("support_fee_accepted",),
        )
    else:
        st.session_state[sf_key] = False
        _update_field("support_fee_accepted")


def render_description_and_internal_notes(container, compact_mode: bool) -> None:
    desc_cols = container.columns((3, 2))
    description_col, notes_col = desc_cols

    description_col.subheader("Description (What / When / Where)")
    desc_height = 52 if compact_mode else 68
    auto_text_area(
        "Description",
        "description",
        height=desc_height,
        container=description_col,
    )

    notes_col.subheader("Internal notes")
    auto_text_input("Helpjuice link", "internal_helpjuice", container=notes_col)
    logs_height = 52 if compact_mode else 68
    auto_text_area(
        "Logs / screenshots",
        "internal_logs",
        height=logs_height,
        container=notes_col,
    )


def render_phonecall_section(container, compact_mode: bool) -> None:
    container.subheader("Phone-call notes")
    desc_height = 52 if compact_mode else 68
    layout_cols = container.columns((3, 2))
    notes_col, contact_col = layout_cols

    auto_text_input("Caller name", "caller_name", container=notes_col)
    auto_text_area(
        "Caller issue description",
        "phone_description",
        height=desc_height,
        container=notes_col,
    )

    contact_col.subheader("Contact details")
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
    container.subheader("Conclusion")
    conclusion_cols = container.columns(2)
    conclusion_left, conclusion_right = conclusion_cols
    auto_text_input("Root cause", "root_cause", container=conclusion_left)
    auto_text_input("Solution", "solution", container=conclusion_right)
    auto_text_input(
        "Customer satisfaction survey URL",
        "survey_link",
        container=conclusion_right,
    )

    container.subheader("Additional information")
    auto_text_area(
        "Additional details",
        "additional_info",
        height=220 if compact_mode else 400,
        container=container,
        help=(
            "Include details such as antivirus, firewalls enabled, update history, "
            "related case ID, possible cause, performance issues, manual additional notes, "
            "recurring issues, and recent issues."
        ),
    )


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
    try:
        cat = json.loads(st.session_state.categorizer_result or "{}")
    except Exception:
        cat = {}
    product = cat.get("product", "")
    topic = cat.get("topic", "")
    subtopic = cat.get("subtopic", "") or ""
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
        api_key = st.session_state.openai_api_key
        model = st.session_state.openai_model
        base_url = st.session_state.ai_base_url
        toggle_key = widget_key("quick_actions_open", case_idx)
        if toggle_key not in st.session_state:
            st.session_state[toggle_key] = False

        def render_quick_actions_menu() -> None:
            st.markdown("#### Quick actions")
            educate_enabled = st.session_state.get("ai_educate_enabled", False)
            advanced_enabled = st.session_state.get("ai_educate_advanced", False)
            ai_learning_dataset = None
            if educate_enabled and advanced_enabled:
                ai_learning_dataset = ensure_ai_learning_dataset()

            if st.button(
                "Save case",
                key=widget_key("quick_save", case_idx),
                use_container_width=True,
            ):
                save_case_to_database(D)
            if st.button(
                "Clear all",
                key=widget_key("clear_all_button", case_idx),
                use_container_width=True,
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
                    key=widget_key("tracking_enabled", case_idx),
                    use_container_width=True,
                )
            elif st.button(
                "Track case",
                key=widget_key("track_case_button", case_idx),
                use_container_width=True,
            ):
                st.session_state.track_case = True
                st.rerun()
            if st.button(
                "AI Assistance",
                key=widget_key("assist_button", case_idx),
                use_container_width=True,
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
                            condensed_matches = []
                            for match in matches:
                                condensed_matches.append(
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
                                )
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
                    user_message = (
                        learning_context
                        + "Use the available case data to infer values for missing fields."
                        " Return a JSON object mapping field names to inferred values."
                        " Omit fields that cannot be inferred.\n\n"
                        + json.dumps(case_dict, indent=2)
                        + "\nMissing fields:\n"
                        + json.dumps(missing)
                    )
                    try:
                        reply = invoke_gpt(
                            user_message,
                            st.session_state.atom_history,
                            api_key,
                            model,
                            base_url,
                            source="ai_assist",
                        )
                    except Exception as e:
                        logging.error("AI Assist request failed: %s", e)
                        st.error(str(e))
                    else:
                        st.session_state.atom_history.append({"role": "user", "content": user_message})
                        st.session_state.atom_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.atom_history)
                        st.session_state.ai_assist_result = reply
                        suggestions = None
                        try:
                            suggestions = json.loads(reply)
                        except json.JSONDecodeError:
                            match = re.search(
                                r"```(?:json)?\s*(\{.*?\})\s*```",
                                reply,
                                re.DOTALL,
                            )
                            if not match:
                                match = re.search(r"\{.*\}", reply, re.DOTALL)
                            if match:
                                try:
                                    suggestions = json.loads(match.group(1) if match.lastindex else match.group())
                                except json.JSONDecodeError:
                                    pass
                        if suggestions is None:
                            st.error("AI Assistance did not return valid JSON.")
                        else:
                            for fld, val in suggestions.items():
                                if hasattr(D, fld) and not getattr(D, fld):
                                    setattr(D, fld, val)
                            autosave()
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
            if st.button("Categorize", key=widget_key("categorize_button", case_idx), use_container_width=True):
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
                        output_schema = """{
    "product": "string",
    "topic": "string",
    "subtopic": "string|null",
    "confidence": 0.0,
    "reason": "string",
    "signals_used": ["string", ...],
    "top_3_alternatives": [
    {"product":"", "topic":"", "subtopic":null, "why":""},
    {"product":"", "topic":"", "subtopic":null, "why":""},
    {"product":"", "topic":"", "subtopic":null, "why":""}
    ]
    }"""
                        user_message = (
                            "Kiroshi Categorizer, an assistant that classifies 3Shape support cases into exactly one path Product → Topic → (Subtopic) from an allowed taxonomy.\n"
                            "Your job: read the case, extract signals (keywords, logs, artefacts), and output STRICT JSON following the schema.\n\n"
                            "Taxonomy (authoritative)\n\n"
                            "Use ONLY these categories and definitions. If something does not fit perfectly, choose the closest one and lower confidence.\n\n"
                            f"ALLOWED_CATEGORIES_WITH_DEFINITIONS:\n{taxonomy_block}\n\n"
                            "Signals dictionary (hints)\n\n"
                            "Use these signals to boost the right category, but DO NOT hardcode; still decide using the whole context.\n\n"
                            f"SIGNALS_CONFIG:\n{signals_config}\n\n"
                            "Output format (STRICT JSON only)\n\n"
                            "Return ONLY this JSON (no markdown, no prose outside JSON):\n"
                            f"{output_schema}\n\n"
                            "Case to classify (runtime payload)\n\n"
                            f"CASE_INPUT:\n{json.dumps(case_input, indent=2, ensure_ascii=False)}\n\n"
                            "Return\n\n"
                            "Return ONLY the STRICT JSON described above. No extra text, no markdown."
                        )
                        try:
                            reply = invoke_gpt(
                                user_message,
                                st.session_state.atom_history,
                                api_key,
                                model,
                                base_url,
                                source="categorize",
                            )
                        except Exception as e:
                            logging.error("Categorize request failed: %s", e)
                            st.error(str(e))
                        else:
                            st.session_state.atom_history.append({"role": "user", "content": user_message})
                            st.session_state.atom_history.append({"role": "assistant", "content": reply})
                            save_memory(st.session_state.atom_history)
                            st.session_state.categorizer_result = reply
            if st.button("Ask", key=widget_key("ask_button", case_idx), use_container_width=True):
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
                    user_message = (
                        "Based on the following case data"
                        + (f" and previous findings: {findings}" if findings else "")
                        + ", suggest possible steps to fix the issue along with recommendations, tips, and tricks.\n\n"
                        + json.dumps(case_dict, indent=2)
                    )
                    try:
                        reply = invoke_gpt(
                            user_message,
                            st.session_state.atom_history,
                            api_key,
                            model,
                            base_url,
                            source="ask",
                        )
                    except Exception as e:
                        logging.error("Ask request failed: %s", e)
                        st.error(str(e))
                    else:
                        st.session_state.atom_history.append({"role": "user", "content": user_message})
                        st.session_state.atom_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.atom_history)
                        st.session_state.ask_result = reply
            if st.button("Verify", key=widget_key("verify_button", case_idx), use_container_width=True):
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
                    user_message = (
                        "Review the following case data and list any missing or incomplete information needed to complete the case documentation. Also suggest clearer vocabulary if any terms are confusing.\n\n"
                        + json.dumps(case_dict, indent=2)
                    )
                    try:
                        reply = invoke_gpt(
                            user_message,
                            st.session_state.atom_history,
                            api_key,
                            model,
                            base_url,
                            source="verify",
                        )
                    except Exception as e:
                        logging.error("Verify request failed: %s", e)
                        st.error(str(e))
                    else:
                        st.session_state.atom_history.append({"role": "user", "content": user_message})
                        st.session_state.atom_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.atom_history)
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
                key=widget_key("quick_actions_toggle_button", case_idx),
                use_container_width=True,
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
        note_height = 96 if compact_mode else 150

        if st.session_state.verify_result:
            st.text_area(
                "A.A.T.O.M. Verification",
                st.session_state.verify_result,
                height=note_height,
            )
        if st.session_state.ask_result:
            st.text_area(
                "A.A.T.O.M. Suggestions",
                st.session_state.ask_result,
                height=note_height,
            )
        if st.session_state.ai_assist_result:
            st.text_area(
                "AI Assistance",
                st.session_state.ai_assist_result,
                height=note_height,
                key=widget_key("ai_assist_output", case_idx),
            )
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
                render_case_header_section(st, case_idx, False)
                render_description_and_internal_notes(st, False)
                render_phonecall_section(st, False)
                render_conclusion_and_additional(st, False)
    # ================== EMAIL TAB =================
    if tab_email:
        with tab_email:
            st.subheader("Email Prompt Generator")
            if st.session_state.email_type == "Custom Request":
                st.session_state.email_type = "Advanced Request"

            email_choices = [
                "Recap (Customer)",
                "Broken Scanner",
                "Broken Tip",
                "AX Coordinator Email",
                "Customer Reply",
            ]
            if st.session_state.second_line_mode:
                email_choices.extend(
                    [
                        "FedEx Tracking Email",
                        "Replacement Wired Scanner Setup",
                        "Replacement Move+ Closure",
                        "Callback Email",
                        "Dell Escalation Email",
                    ]
                )
            email_choices.extend(["Advanced Request", "Custom"])
            email_widget_key = widget_key("email_template", case_idx)
            current_email_type = st.session_state.email_type
            if current_email_type not in email_choices:
                current_email_type = email_choices[0]
                st.session_state.email_type = current_email_type
            if (
                email_widget_key not in st.session_state
                or st.session_state[email_widget_key] not in email_choices
            ):
                st.session_state[email_widget_key] = current_email_type
            email_type = st.selectbox(
                "Select email template",
                email_choices,
                key=email_widget_key,
            )
            st.session_state.email_type = email_type
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
                    key=widget_key("reply_original", case_idx),
                )
                ext["reply_focus"] = st.text_area(
                    "What should we address in the reply?",
                    ext.get("reply_focus", ""),
                    height=140,
                    key=widget_key("reply_focus", case_idx),
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
                    "Experience level (new / experienced)", ext.get("experience", "")
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
                    key=widget_key("download_pdf", case_idx),
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

                        title_payload = json.dumps(title_text)
                        table_payload = json.dumps(table_plain_text(cat, D, cat_map))
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
                            category_dataframe(cat, D, cat_map), use_container_width=True
                        )
                    st.markdown("---")
                    st.markdown("#### AutoHotkey quick paste")
                    st.caption(
                        "Generate a Windows AutoHotkey script so typing `phonecall1`, `remotesession1`, etc. "
                        "instantly pastes the current case tables."
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
                        "Hotkeys auto-synced locally. Add a single `#Include` to your AutoHotkey launcher "
                        "and the triggers will refresh whenever you update cases."
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
                        "Download the script or copy it manually. Automatic syncing is only available on Windows."
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
                if st.session_state.categorizer_result:
                    st.subheader("Kiroshi Categorizer")
                    st.text_area(
                        "Categorization Output",
                        st.session_state.categorizer_result,
                        height=150,
                        key=widget_key("categorizer_output", case_idx),
                    )

            if email_type == "Broken Tip":
                st.markdown("#### Damaged tip questionnaire")
                ext["times_autoclaved"] = st.text_input(
                    "Times autoclaved", ext.get("times_autoclaved", "")
                )
                ext["bath_number"] = st.text_input(
                    "Bath number", ext.get("bath_number", "")
                )
                ext["model"] = st.text_input(
                    "Autoclave model", ext.get("model", "")
                )
                ext["program"] = st.text_input(
                    "Program used", ext.get("program", "")
                )
                ext["airtight"] = st.text_input(
                    "Autoclaved in airtight pouch?", ext.get("airtight", "")
                )
                ext["other"] = st.text_input(
                    "Other info", ext.get("other", "")
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
                    key=widget_key("request_issue", case_idx),
                )
                D.request_issue = D.description
                D.contact_name = D.caller_name
                st.text_input("Contact name", D.contact_name, disabled=True)
                D.office_ph = D.phone_number
                st.text_input("Office phone", D.office_ph, disabled=True)
                D.direct_ph = D.phone_number
                st.text_input("Direct phone", D.direct_ph, disabled=True)
                best_cb = st.toggle(
                    "Specify best call-back time",
                    D.best_time not in ("", "ASAP"),
                    key=widget_key("best_cb", case_idx),
                )
                best_time_key = widget_key("best_time", case_idx)
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
                    "Agent name", ext.get("agent_name", "")
                )
                ext["device_type"] = st.text_input(
                    "Device type (scanner or Move+)", ext.get("device_type", "")
                )
                ext["tracking_number"] = st.text_input(
                    "FedEx tracking number", ext.get("tracking_number", "")
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
                    key=widget_key("generated_email", case_idx),
                )

            elif email_type == "Replacement Wired Scanner Setup":
                st.markdown("#### Replacement scanner options")
                ext["agent_name"] = st.text_input(
                    "Agent name", ext.get("agent_name", "")
                )
                ext["fedex_pickup_link"] = st.text_input(
                    "FedEx pickup link",
                    ext.get(
                        "fedex_pickup_link",
                        "https://www.fedex.com/en-us/shipping/schedule-manage-pickups.html",
                    ),
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
                    key=widget_key("generated_email", case_idx),
                )

            elif email_type == "Replacement Move+ Closure":
                st.markdown("#### Replacement Move+ options")
                ext["agent_name"] = st.text_input(
                    "Agent name", ext.get("agent_name", "")
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
                    key=widget_key("generated_email", case_idx),
                )

            elif email_type == "Callback Email":
                st.markdown("#### Callback email options")
                cb_remote_key = widget_key("callback_remote", case_idx)
                cb_remote = st.toggle(
                    "Need remote session?",
                    st.session_state.get(cb_remote_key, False),
                    key=cb_remote_key,
                )
                cb_remote_text_key = widget_key("callback_remote_text", case_idx)
                if cb_remote:
                    st.text_area(
                        "Remote session details",
                        st.session_state.get(cb_remote_text_key, ""),
                        key=cb_remote_text_key,
                    )
                cb_contact_key = widget_key("callback_contact", case_idx)
                st.toggle(
                    "Need contact information?",
                    st.session_state.get(cb_contact_key, False),
                    key=cb_contact_key,
                )
                cb_clarify_key = widget_key("callback_clarify", case_idx)
                st.toggle(
                    "Need to clarify what happened?",
                    st.session_state.get(cb_clarify_key, False),
                    key=cb_clarify_key,
                )
                cb_needed_key = widget_key("callback_needed", case_idx)
                st.toggle(
                    "Callback needed?",
                    st.session_state.get(cb_needed_key, True),
                    key=cb_needed_key,
                )
                cb_address_key = widget_key("callback_address", case_idx)
                cb_address = st.toggle(
                    "Request address?",
                    st.session_state.get(cb_address_key, False),
                    key=cb_address_key,
                )
                if cb_address:
                    cb_equipment_key = widget_key("callback_equipment", case_idx)
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
                st.markdown("#### Dell escalation options")
                ext["issue_start_date"] = st.text_input(
                    "Issue start date", ext.get("issue_start_date", "")
                )
                company = D.company_name or "(Company Name)"
                issue_desc = D.brief_description or "(Issue Description)"
                issue_start = ext["issue_start_date"] or "(Issue Start Date)"
                case_no = D.case_id or "(Case ID)"
                service_tag = D.service_tag or "(Service Tag)"
                pc_model = D.pc_model or ""
                bios = D.bios_version or ""
                windows = D.windows_version or ""
                email_text = f"""Hello Dell Support team,

The end-user from {company} has been reporting {issue_desc}, which has been happening since {issue_start}. Could you please assist this customer with a Dell Technician on site?
Case ID {case_no}
PC service tag {service_tag}
Evidence attached to this email.

Computer information:

- Type of PC: {pc_model}
- BIOS Version: {bios}
- Windows Version: {windows}
- Dell Command Updates:
- Power Options setup:
- Dell Optimizer setup:
- Intel Processor Power Management Utility installed?:
- CPU Speed / Is CPU throttling?:
- GPU Usage % (Integrated):
- GPU Usage % (Dedicated):
- CPU Utilization %:
- Benchmark used and results:
- Can it launch simulation on Ultra Resolution? (If needed):
- Which GPU driver versions were tested?:
- Reliability Monitor and Event Viewer results:
- Dell Diagnosis test results (ePSA tests included):
- Has Windows been reimaged?:

Clinic's contact information:

- Address 1
- Address 2 (Suite, etc.)
- City
- State
- Zip Code
- Full name of person responsible for receiving the equipment
- Phone number
- Email address
- Clinic name

Thank you in advance,
"""
                st.text_area(
                    "Email",
                    email_text,
                    height=600,
                    key=widget_key("generated_email", case_idx),
                )

            elif email_type == "Advanced Request":
                st.markdown("#### Custom email options")
                ext["reason"] = st.text_input(
                    "Reason for contacting the customer", ext.get("reason", "")
                )
                ext["goal"] = st.text_input(
                    "Goal of the email", ext.get("goal", "")
                )
                ext["customer_need"] = st.text_input(
                    "What do we need from the customer?",
                    ext.get("customer_need", ""),
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
                pat_cb = st.toggle(
                    "Include Patterson legacy #",
                    value=st.session_state.get(widget_key("pat_cb", case_idx), False),
                    key=widget_key("pat_cb", case_idx),
                )
                if pat_cb:
                    auto_text_input(
                        "Patterson legacy #",
                        "patterson",
                    )
                else:
                    D.patterson = "N/A"
                    autosave()
                if st.session_state.second_line_mode:
                    st.text_input(
                        "Straumann ticket #",
                        D.straumann,
                        disabled=True,
                        key=widget_key("straumann_tab", case_idx),
                    )
                else:
                    D.straumann = "N/A"
                    autosave()
            elif email_type == "Custom":
                st.markdown("#### Custom prompt builder")
                ext["custom_user_prompt"] = st.text_area(
                    "User instructions", ext.get("custom_user_prompt", ""), height=140
                )
                case_context = build_case_data_block(D)
                st.text_area(
                    "Case data provided by Kiroshi",
                    case_context,
                    height=220,
                    key=widget_key("custom_case_context", case_idx),
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
                    key=widget_key("api_prompt_area", case_idx),
                )
                st.session_state["last_prompt"] = prompt

                include_helpjuice = st.toggle(
                    "Helpjuice tutorial",
                    value=st.session_state.get(widget_key("api_helpjuice", case_idx), False),
                    key=widget_key("api_helpjuice", case_idx),
                )
                include_restart = st.toggle(
                    "Restart the computer",
                    value=st.session_state.get(widget_key("api_restart", case_idx), False),
                    key=widget_key("api_restart", case_idx),
                )
                include_scan_time = st.toggle(
                    "Scan time warning",
                    value=st.session_state.get(widget_key("api_scan_time", case_idx), False),
                    key=widget_key("api_scan_time", case_idx),
                )
                generated_email_key = widget_key("generated_email_output", case_idx)
                if generated_email_key not in st.session_state:
                    st.session_state[generated_email_key] = st.session_state.get(
                        "generated_email", ""
                    )
                if st.button("Use GPT-OSS", key=widget_key("use_gpt", case_idx)):
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
                                    st.session_state.atom_history,
                                    api_key,
                                    model,
                                    base_url,
                                    source="gpt_oss_email",
                                )
                            except Exception as e:
                                logging.error("GPT-OSS email generation failed: %s", e)
                                st.error(str(e))
                            else:
                                st.session_state.atom_history.append({"role": "user", "content": augmented_prompt})
                                st.session_state.atom_history.append({"role": "assistant", "content": reply})
                                save_memory(st.session_state.atom_history)
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
            st.subheader("Tracking")
            ensure_tracking_session_defaults(case_idx, D.tracking)
            tracking_type_key = widget_key("tracking_type", case_idx)
            tracking_type = st.selectbox(
                "Tracking type",
                ["Dell", "FedEx", "Custom"],
                key=tracking_type_key,
            )

            st.text_input("Case ID", value=D.case_id, disabled=True)
            st.text_input("Company", value=D.company_name, disabled=True)
            end_user_value = D.contact_name or D.caller_name or ""
            st.text_input("End User", value=end_user_value, disabled=True)
            phone_value = (
                D.phone_number or D.office_ph or D.direct_ph or ""
            )
            st.text_input("Phone", value=phone_value, disabled=True)
            created_display = format_tracking_date(D.tracking.creation_day)
            if not created_display:
                created_display = datetime.now().strftime("%Y-%m-%d")
            st.text_input("Created", value=created_display, disabled=True)

            ticket_key = widget_key("track_ticket_number", case_idx)
            ticket_number = st.text_input("Ticket Number", key=ticket_key)

            priority_key = widget_key("track_priority", case_idx)
            st.session_state[priority_key] = normalize_priority(
                st.session_state.get(priority_key)
            )
            st.selectbox("Priority", PRIORITY_OPTIONS, key=priority_key)

            category_key = widget_key("track_category", case_idx)
            st.text_input("Category", key=category_key)

            status_key = widget_key("track_status", case_idx)
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

            service_tag_key = widget_key("track_service_tag", case_idx)
            expected_key = widget_key("track_expected_arrival", case_idx)
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

            case_link_key = widget_key("track_case_link", case_idx)
            st.text_input("Case link (CRM)", key=case_link_key)

            if st.button("Save and track", key=widget_key("save_and_track", case_idx)):
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
                key=widget_key("close_tracking", case_idx),
            ):
                D.tracking.active = False
                save_case_to_database(D, notify=False)
                st.session_state.track_case = False
                st.rerun()

    # ================== ESCALATIONS TAB =================
    if tab_escalations:
        with tab_escalations:
            if "AX COORDINATORS" in cat_map:
                st.markdown("#### AX Coordinators Table")
                st.dataframe(
                    category_dataframe("AX COORDINATORS", D, cat_map),
                    use_container_width=True,
                )
                st.markdown("---")

            st.subheader("Escalation 2nd line")
            D.esc_name = D.caller_name
            st.text_input(
                "Name",
                D.esc_name,
                disabled=True,
                key=widget_key("esc_name_tab", case_idx),
            )
            D.esc_ph = D.phone_number
            st.text_input(
                "Phone",
                D.esc_ph,
                disabled=True,
                key=widget_key("esc_ph_tab", case_idx),
            )
            D.esc_email = D.email
            st.text_input(
                "Email",
                D.esc_email,
                disabled=True,
                key=widget_key("esc_email_tab", case_idx),
            )
            if "ESCALATION 2ND LINE" in cat_map:
                st.markdown("#### Escalation 2nd line Table")
                st.dataframe(
                    category_dataframe("ESCALATION 2ND LINE", D, cat_map),
                    use_container_width=True,
                )

            if st.session_state.second_line_mode:
                st.markdown("---")
                st.subheader("Escalation 3rd line")
                auto_text_area("How to reproduce it", "repro_steps", height=100)
                msg = build_third_line_escalation(D)
                st.text_area(
                    "Escalation message",
                    msg,
                    height=400,
                    key=widget_key("esc_message", case_idx),
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
                category_dataframe("SCANNER HARDWARE", D, HW_CATEGORY_MAP), use_container_width=True
            )
    
    # ================== REMOTE SESSION TAB =================
    with tab_remote:
        st.subheader("Remote session – steps")
        auto_text_area("One step per line", "remote_steps", height=400)

    # ================== TABLES TAB =================
    with tab_tables:
        st.subheader("Copy all tables")
        st.download_button(
            "Download Case Info PDF",
            make_tables_pdf(D),
            file_name=f"{D.case_id or 'case'}_info.pdf",
            mime="application/pdf",
            key=widget_key("download_info_pdf", case_idx),
        )
        for cat in cat_map:
            st.markdown(f"**{table_title(cat)}**")
            st.dataframe(category_dataframe(cat, D, cat_map), use_container_width=True)

    # ================== SAVE/LOAD TAB =================
    with tab_save_load:
        st.subheader("Save / Load")
        col_save, col_load = st.columns(2)
        with col_save:
            if st.button("Save", key=widget_key("save_case_button", case_idx)):
                save_case_to_database(D)
        with col_load:
            uploaded_case = st.file_uploader(
                "Select case JSON",
                type="json",
                key=widget_key("load_case_uploader", case_idx),
            )
            if uploaded_case and st.button(
                "Load", key=widget_key("load_case_button", case_idx)
            ):
                request_load_from_bytes(uploaded_case.getvalue())

        st.subheader("Case Dex")
        dex_case_id = st.text_input(
            "Case ID", key=widget_key("case_dex_id", case_idx)
        )
        if st.button("Fetch Case Dex", key=widget_key("fetch_case_dex", case_idx)):
            if dex_case_id:
                try:
                    dex_bytes = request_case_dex(dex_case_id)
                except Exception as e:
                    st.error(f"Failed to download Case Dex: {e}")
                else:
                    st.session_state[
                        widget_key("case_dex_bytes", case_idx)
                    ] = dex_bytes
                    st.session_state[
                        widget_key("case_dex_id_store", case_idx)
                    ] = dex_case_id
            else:
                st.error("Please enter a Case ID")
        dex_bytes = st.session_state.get(widget_key("case_dex_bytes", case_idx))
        if dex_bytes:
            st.download_button(
                "Download Case Dex",
                dex_bytes,
                file_name=f"{st.session_state.get(widget_key('case_dex_id_store', case_idx), 'case')}_case_dex.zip",
                mime="application/zip",
                key=widget_key("download_case_dex", case_idx),
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
            if btn_col.button(
                "Load", key=widget_key(f"recent_load_{idx}", case_idx)
            ):
                request_load_from_path(case["path"])

        pending = st.session_state.get("pending_load")
        if pending:
            st.error("Remember to save your information before loading a new case")
            col_i, col_s = st.columns(2)
            target_idx = pending.get("target_idx", CURRENT_CASE_IDX)
            if col_i.button("Ignore and load", key=widget_key("ignore_and_load", case_idx)):
                _activate_case_index(target_idx)
                if "path" in pending:
                    load_case_from_path(pending["path"])
                else:
                    load_case_from_bytes(pending["data"])
                st.session_state.pending_load = None
            if col_s.button("Save", key=widget_key("save_before_loading", case_idx)):
                save_case_to_database(D)

    # ================== FILE UPLOADS & EXPORTS =================
    st.markdown("---")
    st.subheader("Exports & attachments")
    new_files = st.file_uploader(
        "Upload screenshots / videos",
        accept_multiple_files=True,
        key=widget_key("new_files", case_idx),
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
        key=widget_key("log_files", case_idx),
    )
    if log_files:
        existing_log_names = {f.name for f in st.session_state.log_uploads}
        for lf in log_files:
            if lf.name not in existing_log_names:
                st.session_state.log_uploads.append(lf)
                existing_log_names.add(lf.name)

    screenshot_name = st.text_input(
        "Screenshot name", key=widget_key("screenshot_name", case_idx)
    )
    full_btn_col, region_btn_col = st.columns(2)

    if full_btn_col.button("Take Screenshot", key=widget_key("take_screenshot", case_idx)):
        if not PYAUTOGUI_AVAILABLE:
            st.error("Screenshot capture is unavailable in this environment.")
        elif screenshot_name:
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", screenshot_name)
            img = pyautogui.screenshot()  # type: ignore[union-attr]
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            st.session_state.screenshots.append(
                InMemoryUploadedFile(f"{safe_name}.png", buf.getvalue())
            )
            st.success(f"Captured screenshot: {safe_name}")
        else:
            st.error("Please provide a screenshot name before capturing.")

    if region_btn_col.button(
        "Advanced Screenshot (select area)",
        key=widget_key("take_region_screenshot", case_idx),
    ):
        if not screenshot_name:
            st.error("Please provide a screenshot name before capturing.")
        elif not TK_AVAILABLE or tk is None:
            st.warning(
                "Advanced screenshot selection requires a local display and Tkinter support."
            )
        else:
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", screenshot_name)
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
                    "Remove", key=widget_key(f"rem_upload_{i}", case_idx)
                ):
                    st.session_state.uploads.pop(i)
                    st.rerun()
        if st.session_state.log_uploads:
            st.markdown("Logs queued:")
            for i, f in enumerate(st.session_state.log_uploads):
                cols = st.columns([8, 1])
                cols[0].markdown(f"• {f.name} ({len(f.getvalue())//1024} KB)")
                if cols[1].button(
                    "Remove", key=widget_key(f"rem_log_{i}", case_idx)
                ):
                    st.session_state.log_uploads.pop(i)
                    st.rerun()
        if st.session_state.screenshots:
            st.markdown("Screenshots captured:")
            for i, s in enumerate(st.session_state.screenshots):
                cols = st.columns([8, 1])
                cols[0].markdown(f"• {s.name} ({len(s.getvalue())//1024} KB)")
                if cols[1].button(
                    "Remove", key=widget_key(f"rem_shot_{i}", case_idx)
                ):
                    st.session_state.screenshots.pop(i)
                    st.rerun()
        if st.button("Create ZIP", key=widget_key("create_zip", case_idx)):
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
                for f in st.session_state.uploads:
                    z.writestr(f"Screenshots/{f.name}", f.getvalue())
                for f in st.session_state.log_uploads:
                    z.writestr(f"logs/{f.name}", f.getvalue())
                for s in st.session_state.screenshots:
                    z.writestr(f"Screenshots/{s.name}", s.getvalue())
                if st.session_state.get("attachments_include_case_json", True):
                    z.writestr("case.json", json.dumps(asdict(D), indent=2))
            zbuf.seek(0)
            st.download_button(
                "Download attachments.zip",
                zbuf,
                file_name=f"{D.case_id or 'case'}_attachments.zip",
                mime="application/zip",
                key=widget_key("download_zip", case_idx),
            )

    # ================== BORED TAB =================
    if tab_bored:
        with tab_bored:
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
            if st.button("Explore", key=widget_key("bored_explore", case_idx)):
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

    autosave()

case_labels = [
    cs.case.case_id or f"Case {i+1}" for i, cs in enumerate(st.session_state.case_sessions)
] + ["+ New Case"]
tab_labels: list[str] = ["Dashboard", "Settings"]
if st.session_state.debug_mode:
    tab_labels.append("Debug")
show_atom_chat = st.session_state.get("show_atom_chat", True)
tab_labels.append("Report")
if show_atom_chat:
    tab_labels.append("A.A.T.O.M. Chat")
tab_labels += case_labels
all_tabs = st.tabs(tab_labels)

tab_index = 0
with all_tabs[tab_index]:
    render_dashboard()
tab_index += 1
with all_tabs[tab_index]:
    render_settings_panel()
tab_index += 1
if st.session_state.debug_mode:
    with all_tabs[tab_index]:
        render_debug_panel()
    tab_index += 1
with all_tabs[tab_index]:
    render_report_panel()
tab_index += 1
if show_atom_chat:
    with all_tabs[tab_index]:
        render_atom_chat_panel()
    tab_index += 1

case_tabs = all_tabs[tab_index:]
for idx, tab in enumerate(case_tabs):
    with tab:
        if idx == len(st.session_state.case_sessions):
            if st.button("Add Case"):
                st.session_state.case_sessions.append(CaseSession(case=CaseData()))
                st.rerun()
        else:
            load_case_state(idx)
            render_case_ui(idx)
            save_case_state(idx)
