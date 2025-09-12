# -*- coding: utf-8 -*-
"""
Kiroshi V1.5.2 Beta Build 932025 – IT Case Documentation Helper
Run:
    streamlit run case_documentation_app.py
"""

import io
import json
import os
import zipfile
from dataclasses import dataclass, asdict, fields, field
from datetime import datetime, date, timedelta
import logging
from pathlib import Path
import re
import base64
import random
import subprocess
import sys
from collections.abc import Iterable, Mapping

import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components
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
import requests
import urllib3

try:  # pyautogui may require a GUI environment
    import pyautogui  # type: ignore
    PYAUTOGUI_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when display unavailable
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False
from aatom_chat import (
    load_memory,
    save_memory,
    query_atom,
    SYSTEM_PROMPT,
    load_manual_docs,
    save_manual_docs,
    search_manual_docs,
)

# Some corporate networks perform SSL interception with a self-signed
# certificate, which breaks standard certificate validation.  Disable
# warnings and certificate verification for outbound requests so the
# ChatGPT API can still be reached.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

VERSION = "1.5.2 Beta Build 932025"
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

if os.name == "nt":
    DATABASE_DIR = Path("C:/ProgramFiles/KiroshiDatabase")
else:
    DATABASE_DIR = Path.home() / "KiroshiDatabase"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
RECENT_CASES_PATH = DATABASE_DIR / "recent_cases.json"
if not RECENT_CASES_PATH.exists():
    RECENT_CASES_PATH.write_text("[]", encoding="utf-8")

if os.name == "nt":
    TRACKED_CASES_DIR = Path("C:/ProgramFiles/KiroshiDatabase/TrackedCases")
else:
    TRACKED_CASES_DIR = DATABASE_DIR / "TrackedCases"
TRACKED_CASES_DIR.mkdir(parents=True, exist_ok=True)

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

VERSION_NOT_RELEVANT = "Version not relevant for this case"

# Configure logging to write to a user-writable directory.  Fall back to
# console-only logging if the log file cannot be created (e.g. due to
# permissions on ProgramData when running without admin rights).
LOG_DIR = Path.home() / "Kiroshi Documentation"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_handlers = [
        logging.FileHandler(LOG_DIR / LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]
except OSError:
    log_handlers = [logging.StreamHandler()]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=log_handlers,
)
logging.info("Kiroshi app started")

# Local logo assets from repository
ASSETS_DIR = Path(__file__).parent
KIROSHI_LOGO_PATH = ASSETS_DIR / "Kiroshi_Logo.png"
ATOM_LOGO_PATH = ASSETS_DIR / "atom_logo.png"

MOTD_MESSAGES = [
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
    "The only thing scarier than Monday is the printer jam.",
]


def get_message_of_the_day() -> str:
    """Return a pseudo-random MOTD that changes twice daily.

    The message rotates at 11:59 AM and 11:59 PM local time by seeding a
    deterministic RNG with the current date and half-day period.
    """
    now = datetime.now()
    minute_of_day = now.hour * 60 + now.minute
    if minute_of_day < 11 * 60 + 59:
        effective_date = now.date()
        period = "AM"
    elif minute_of_day < 23 * 60 + 59:
        effective_date = now.date()
        period = "PM"
    else:
        effective_date = (now + timedelta(days=1)).date()
        period = "AM"

    seed = f"{effective_date.isoformat()}-{period}"
    rng = random.Random(seed)
    return rng.choice(MOTD_MESSAGES)

# ─────────────────────────── CONFIG ────────────────────────────
st.set_page_config(
    page_title=f"Kiroshi V{VERSION}",
    layout="wide",
    page_icon=str(KIROSHI_LOGO_PATH),
)


def render_logo():
    motd = get_message_of_the_day()
    col_logo, col_motd = st.columns([1, 3])
    with col_logo:
        encoded_logo = base64.b64encode(KIROSHI_LOGO_PATH.read_bytes()).decode()
        html_logo = f"""
        <img src="data:image/png;base64,{encoded_logo}" width="200" id="kiroshi-logo" style="cursor:pointer;">
        <script>
        const logo = document.getElementById('kiroshi-logo');
        logo.addEventListener('click', function(){{
            Streamlit.setComponentValue('open-debug');
        }});
        </script>
        """
        action_logo = components.html(html_logo, height=200)
        if action_logo == "open-debug":
            st.session_state.debug_mode = True
    with col_motd:
        st.markdown(
            f"<span style='font-weight:bold;'>Message of the day:</span> {motd}",
            unsafe_allow_html=True,
        )

# ────────────────────── SESSION STATE ────────────────────────
def _init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

_init_state("case", {})
_init_state("uploads", [])
_init_state("log_uploads", [])
_init_state("screenshots", [])
_init_state("scratch", "")
_init_state("email_type", "Recap (Customer)")
_init_state("email_extra", {})
_init_state("include_escalations", False)
_init_state("include_hardware", False)
_init_state("debug_auth", False)
_init_state("debug_mode", False)
_init_state("_autosave_loaded", False)
_init_state("openai_api_key", DEFAULT_OPENAI_API_KEY)
_init_state("openai_model", "gpt-4o")
_init_state("ai_base_url", DEFAULT_AI_BASE_URL)
_init_state("ai_mode", DEFAULT_AI_MODE)
_init_state("api_helpjuice", False)
_init_state("api_restart", False)
_init_state("api_scan_time", False)
_init_state("atom_history", load_memory())
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
# Tracking related state
_init_state("track_case", False)
_init_state("tracking_info", {})
# 2nd line mode and callback e‑mail options
_init_state("second_line_mode", False)
_init_state("pending_load", None)
_init_state("show_bored", False)
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

render_logo()


def load_autosave():
    if st.session_state._autosave_loaded:
        return
    if os.path.exists(AUTOSAVE_FILE):
        try:
            with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            st.session_state.case = data.get("case", {})
            st.session_state.scratch = data.get("scratch", "")
            st.session_state[widget_key("scratch", 0)] = st.session_state.scratch
        except Exception:
            pass
    st.session_state._autosave_loaded = True


load_autosave()


def tail_log(path: str, lines: int = 100) -> str:
    """Return the last N lines from a log file."""
    if not os.path.exists(path):
        return "Log file not found."
    with open(path, "r", encoding="utf-8") as f:
        return "".join(f.readlines()[-lines:])

# ───────────────── DATA MODEL ──────────────────
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


@dataclass
class InMemoryUploadedFile:
    """Simple file-like container for generated screenshots."""

    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return self.data


@dataclass
class CaseSession:
    """Container for per-case session state."""

    case: CaseData
    scratch: str = ""
    uploads: list = field(default_factory=list)
    log_uploads: list = field(default_factory=list)
    screenshots: list = field(default_factory=list)


# convert stored dict to dataclass, ignoring unexpected fields
if isinstance(st.session_state.case, dict):
    allowed = {f.name for f in fields(CaseData)}
    filtered = {k: v for k, v in st.session_state.case.items() if k in allowed}
    st.session_state.case = CaseData(**filtered)
D: CaseData = st.session_state.case

if "case_sessions" not in st.session_state:
    st.session_state.case_sessions = [
        CaseSession(
            case=D,
            scratch=st.session_state.scratch,
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
    st.session_state[widget_key("scratch", idx)] = cs.scratch


def save_case_state(idx: int) -> None:
    st.session_state.case_sessions[idx] = CaseSession(
        case=st.session_state.case,
        scratch=st.session_state.get(widget_key("scratch", idx), ""),
        uploads=st.session_state.uploads,
        log_uploads=st.session_state.log_uploads,
        screenshots=st.session_state.screenshots,
    )


def widget_key(base: str, idx: int) -> str:
    """Return a Streamlit widget key namespaced to a case index."""
    return f"{base}_{idx}"


CURRENT_CASE_IDX = 0

# Ensure session state mirrors the current case data before any widgets are created
for key, value in asdict(D).items():
    st.session_state[key] = value

# Ensure the survey link widget has an initial value to prevent
# "attribute missing" errors before the first user interaction.
_init_state("survey_link", D.survey_link)

# Button to clear all case data and reset form
def autosave():
    with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "case": asdict(D),
                "scratch": st.session_state.get(
                    widget_key("scratch", CURRENT_CASE_IDX), ""
                ),
            },
            f,
            indent=2,
        )


def load_recent_cases() -> list:
    try:
        return json.loads(RECENT_CASES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def update_recent_cases(case_id: str, path: str) -> None:
    recents = [c for c in load_recent_cases() if c.get("path") != path]
    recents.insert(0, {"case_id": case_id, "path": path})
    RECENT_CASES_PATH.write_text(json.dumps(recents[:10], indent=2), encoding="utf-8")


def load_tracked_cases() -> list:
    cases = []
    for p in TRACKED_CASES_DIR.glob("*_Active.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["path"] = str(p)
            cases.append(data)
        except Exception:
            continue
    return cases


def untrack_case(path: str) -> None:
    """Move an active tracking file into the main database and refresh the page."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        case_id = data.get("case_id")
        if case_id:
            dest = DATABASE_DIR / f"{case_id}.json"
            Path(path).rename(dest)
    except Exception:
        st.error("Failed to untrack case.")


def render_tracking_table(cases: list, columns: list) -> None:
    """Render a tracking table with per-row load and untrack buttons."""
    weights = [2] * len(columns) + [1, 1]
    header_cols = st.columns(weights)
    for col, (label, _) in zip(header_cols, columns):
        col.write(f"**{label}**")
    header_cols[-2].write("**Load**")
    header_cols[-1].write("**Untrack**")
    for c in cases:
        row_cols = st.columns(weights)
        for col, (_, key) in zip(row_cols[:-2], columns):
            col.write(c.get(key, ""))
        if row_cols[-2].button("Load", key=f"load_{Path(c['path']).stem}"):
            request_load_from_path(c["path"])
        if row_cols[-1].button("Untrack", key=f"untrack_{Path(c['path']).stem}"):
            untrack_case(c["path"])
            st.rerun()


def recent_tracked_files() -> list:
    files = sorted(
        TRACKED_CASES_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[:20]


def save_case_to_database(case: CaseData) -> None:
    if not case.case_id:
        st.error("Case ID is required to save.")
        return
    file_path = DATABASE_DIR / f"{case.case_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(asdict(case), f, indent=2)
    update_recent_cases(case.case_id, str(file_path))
    st.success(f"Case saved to {file_path}")


def load_case_from_path(path: str) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = {k: v for k, v in data.items() if k in CaseData.__annotations__}
        st.session_state.case = CaseData(**data)
        global D
        D = st.session_state.case
        if "case_sessions" in st.session_state and CURRENT_CASE_IDX < len(st.session_state.case_sessions):
            st.session_state.case_sessions[CURRENT_CASE_IDX].case = D
        autosave()
        update_recent_cases(st.session_state.case.case_id, path)
        # Enable tracking tab if loaded from tracked directory or active file
        p = Path(path)
        if p.parent == TRACKED_CASES_DIR or p.name.endswith("_Active.json"):
            st.session_state.track_case = True
        else:
            st.session_state.track_case = False
        st.success("Case loaded successfully.")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to load case: {e}")


def load_case_from_bytes(data: bytes) -> None:
    try:
        payload = json.loads(data.decode("utf-8"))
        payload = {k: v for k, v in payload.items() if k in CaseData.__annotations__}
        st.session_state.case = CaseData(**payload)
        global D
        D = st.session_state.case
        if "case_sessions" in st.session_state and CURRENT_CASE_IDX < len(st.session_state.case_sessions):
            st.session_state.case_sessions[CURRENT_CASE_IDX].case = D
        autosave()
        st.success("Case loaded successfully.")
        st.rerun()
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


def request_load_from_path(path: str) -> None:
    if has_unsaved_sections(D):
        st.session_state.pending_load = {"path": path}
    else:
        load_case_from_path(path)


def request_load_from_bytes(data: bytes) -> None:
    if has_unsaved_sections(D):
        st.session_state.pending_load = {"data": data}
    else:
        load_case_from_bytes(data)


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
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        rows.append({"Field": fld.replace("_", " ").title(), "Value": value})
    return pd.DataFrame(rows)


def table_title(cat: str) -> str:
    """Return a formatted table title with type and current date."""
    label = "Phonecall" if cat == "PHONECALL" else "Int"
    return f"{cat} ({label}){TODAY_STR}"


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
            st.session_state.include_escalations = st.checkbox(
                "Include escalations", st.session_state.include_escalations
            )
        with col_hw:
            st.session_state.include_hardware = st.checkbox(
                "Include hardware issues", st.session_state.include_hardware
            )
    cat_map = active_category_map()
    tab_labels = []
    if st.session_state.second_line_mode and case_idx == 0:
        tab_labels.append("2nd Line Mode")
    tab_labels.append("Case")
    if st.session_state.track_case:
        tab_labels.append("Tracking")
    if st.session_state.include_escalations:
        tab_labels.append("Escalations")
    tab_labels.append("Email")
    if st.session_state.include_hardware:
        tab_labels.append("Hardware Issues")
    tab_labels += [
        "Remote Session",
        "Notes",
        "Tables",
        "Save/Load",
        "Settings",
        "Atom Chat",
    ]
    if st.session_state.show_bored:
        tab_labels.append("I'm bored")
    if st.session_state.debug_mode:
        tab_labels.append("Debug")

    tabs = st.tabs(tab_labels)
    tab_iter = iter(tabs)
    tab_dashboard = (
        next(tab_iter)
        if st.session_state.second_line_mode and case_idx == 0
        else None
    )
    tab_case = next(tab_iter)
    tab_tracking = next(tab_iter) if st.session_state.track_case else None
    tab_escalations = next(tab_iter) if st.session_state.include_escalations else None
    tab_email = next(tab_iter)
    tab_hw = next(tab_iter) if st.session_state.include_hardware else None
    tab_remote = next(tab_iter)
    tab_notes = next(tab_iter)
    tab_tables = next(tab_iter)
    tab_save_load = next(tab_iter)
    tab_settings = next(tab_iter)
    tab_atom = next(tab_iter)
    tab_bored = next(tab_iter) if st.session_state.show_bored else None
    tab_debug = next(tab_iter) if st.session_state.debug_mode else None

    # ================== 2ND LINE MODE TAB =================
    if tab_dashboard:
        with tab_dashboard:
            st.header("2nd Line Mode Dashboard")
            main_col, recent_col = st.columns([3, 1])
            with recent_col:
                st.subheader("Recent Tracked Cases")
                recent_box = st.container(height=400)
                for p in recent_tracked_files():
                    recent_box.write(p.stem)
            with main_col:
                st.subheader("Case Status & Tracking")
                cases = load_tracked_cases()
                dell_cases = [c for c in cases if c.get("type") == "Dell"]
                st.markdown("### Dell Case Tracking")
                if dell_cases:
                    render_tracking_table(
                        dell_cases,
                        [
                            ("Company", "company"),
                            ("End User", "end_user"),
                            ("Creation day", "creation_day"),
                            ("Ticket Number", "ticket_number"),
                            ("Service Tag", "service_tag"),
                            ("Status", "status"),
                        ],
                    )
                else:
                    st.write("No Dell cases being tracked.")
                st.markdown("### FedEx Case Tracking")
                fedex_cases = [c for c in cases if c.get("type") == "FedEx"]
                if fedex_cases:
                    render_tracking_table(
                        fedex_cases,
                        [
                            ("Company", "company"),
                            ("End User", "end_user"),
                            ("Creation day", "creation_day"),
                            ("Ticket Number", "ticket_number"),
                            ("Expected arrival date", "expected_arrival_date"),
                            ("Status", "status"),
                        ],
                    )
                else:
                    st.write("No FedEx cases being tracked.")
    # ================== CASE TAB =================
    with tab_case:
        api_key = st.session_state.openai_api_key
        model = st.session_state.openai_model
        base_url = st.session_state.ai_base_url
        verify_col, ask_col, categorize_col, assist_col, clear_col, track_col = st.columns(6)
        with verify_col:
            if st.button("Verify", key=widget_key("verify_button", case_idx)):
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
                        reply = query_atom(
                            user_message,
                            st.session_state.atom_history,
                            api_key,
                            model,
                            base_url,
                        )
                    except Exception as e:
                        st.error(str(e))
                    else:
                        st.session_state.atom_history.append({"role": "user", "content": user_message})
                        st.session_state.atom_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.atom_history)
                        st.session_state.verify_result = reply
        with ask_col:
            if st.button("Ask", key=widget_key("ask_button", case_idx)):
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
                        reply = query_atom(
                            user_message,
                            st.session_state.atom_history,
                            api_key,
                            model,
                            base_url,
                        )
                    except Exception as e:
                        st.error(str(e))
                    else:
                        st.session_state.atom_history.append({"role": "user", "content": user_message})
                        st.session_state.atom_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.atom_history)
                        st.session_state.ask_result = reply
        with categorize_col:
            if st.button("Categorize", key=widget_key("categorize_button", case_idx)):
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
                            reply = query_atom(
                                user_message,
                                st.session_state.atom_history,
                                api_key,
                                model,
                                base_url,
                            )
                        except Exception as e:
                            st.error(str(e))
                        else:
                            st.session_state.atom_history.append({"role": "user", "content": user_message})
                            st.session_state.atom_history.append({"role": "assistant", "content": reply})
                            save_memory(st.session_state.atom_history)
                            st.session_state.categorizer_result = reply
        with assist_col:
            if st.button("AI Assistance", key=widget_key("assist_button", case_idx)):
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
                    user_message = (
                        "Use the available case data to infer values for missing fields."
                        " Return a JSON object mapping field names to inferred values."
                        " Omit fields that cannot be inferred.\n\n"
                        + json.dumps(case_dict, indent=2)
                        + "\nMissing fields:\n"
                        + json.dumps(missing)
                    )
                    try:
                        reply = query_atom(
                            user_message,
                            st.session_state.atom_history,
                            api_key,
                            model,
                            base_url,
                        )
                    except Exception as e:
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
        with clear_col:
            if st.button("Clear all", key=widget_key("clear_all_button", case_idx)):
                logging.info("Clear all button clicked")
                api_key = st.session_state.get("openai_api_key", "")
                second_line_mode = st.session_state.get("second_line_mode", False)
                st.session_state.clear()
                st.session_state.openai_api_key = api_key
                st.session_state.second_line_mode = second_line_mode
                if os.path.exists(AUTOSAVE_FILE):
                    try:
                        os.remove(AUTOSAVE_FILE)
                    except OSError:
                        pass
                st.rerun()
        with track_col:
            if st.session_state.track_case:
                st.button(
                    "Tracking enabled",
                    disabled=True,
                    key=widget_key("tracking_enabled", case_idx),
                )
            elif st.button("Track case", key=widget_key("track_case_button", case_idx)):
                st.session_state.track_case = True
                st.rerun()
        if st.session_state.verify_result:
            st.text_area(
                "A.A.T.O.M. Verification",
                st.session_state.verify_result,
                height=150,
            )
        if st.session_state.ask_result:
            st.text_area(
                "A.A.T.O.M. Suggestions",
                st.session_state.ask_result,
                height=150,
            )
        if st.session_state.ai_assist_result:
            st.text_area(
                "AI Assistance",
                st.session_state.ai_assist_result,
                height=150,
                key=widget_key("ai_assist_output", case_idx),
            )
        prog, miss = compute_progress(D, cat_map)
        left, right = st.columns([1, 2], gap="medium")
        with right:
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
            st.altair_chart(bar_chart, use_container_width=True)
            todo = [
                f"**{c}** → {', '.join(flds)}" for c, flds in miss.items() if flds
            ]
            st.markdown("### To‑do" if todo else "All mandatory info filled.")
            for t in todo:
                st.markdown(f"- {t}")
            st.subheader("Case Header")
            if st.session_state.second_line_mode:
                auto_text_input("Straumann ticket #", "straumann")
            auto_text_input("Company name", "company_name")
            auto_text_input("Subscription ID", "subscription_id")
            auto_text_input("Brief description", "brief_description")
            auto_text_input("Case ID", "case_id")
            version_nr = st.checkbox(
                VERSION_NOT_RELEVANT,
                D.application_version == VERSION_NOT_RELEVANT,
                key=widget_key("application_version_not_relevant", case_idx),
            )
            if version_nr:
                st.session_state[widget_key("application_version", case_idx)] = VERSION_NOT_RELEVANT
                _update_field("application_version")
            auto_text_input(
                "Application and version",
                "application_version",
                placeholder="e.g., Unite 1.8.10.1",
                help="Examples: Unite 1.8.10.1, TRIOS 1.18.8.8, Dental System",
                disabled=version_nr,
            )
            st.subheader("Description (What / When / Where)")
            auto_text_area("Description", "description", height=68)
            st.subheader("Phone-call notes")
            auto_text_input("Caller name", "caller_name")
            auto_text_area("Caller issue description", "phone_description", height=68)
            auto_text_input("Email", "email")
            c1, c2 = st.columns(2)
            auto_text_input("Dongle number", "dongle_number", container=c1)
            auto_text_input("Phone number", "phone_number", container=c2)
            auto_text_input("TeamViewer ID", "teamviewer_id", container=c1)
            if st.session_state.second_line_mode:
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
                key="straumann_tab",
            )
        else:
            D.straumann = "N/A"
            autosave()
        if "AX COORDINATORS" in cat_map:
            st.markdown("#### AX Coordinators Table")
            st.dataframe(
                category_dataframe("AX COORDINATORS", D, cat_map),
                use_container_width=True,
            )
            st.markdown("---")
        st.subheader("Escalation 2nd line")
        D.esc_name = D.caller_name
        st.text_input("Name", D.esc_name, disabled=True, key="esc_name_tab")
        D.esc_ph = D.phone_number
        st.text_input("Phone", D.esc_ph, disabled=True, key="esc_ph_tab")
        D.esc_email = D.email
        st.text_input("Email", D.esc_email, disabled=True, key="esc_email_tab")
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
            st.text_area("Escalation message", msg, height=400)

    # ================== EMAIL TAB =================
    if tab_email:
        with tab_email:
            st.subheader("Email Prompt Generator")
            email_choices = ["Recap (Customer)", "Broken Scanner", "Broken Tip"]
            if st.session_state.second_line_mode:
                email_choices.extend(
                    [
                        "FedEx Tracking Email",
                        "Replacement Wired Scanner Setup",
                        "Replacement Move+ Closure",
                        "Callback Email",
                    ]
                )
            email_choices.append("Custom Request")
            email_type = st.selectbox(
                "Select email template",
                email_choices,
                index=
                email_choices.index(st.session_state.email_type)
                if st.session_state.email_type in email_choices
                else 0,
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
            elif email_type == "Broken Scanner":
                st.markdown("#### Incident questionnaire (prefill if known)")
                ext["experience"] = st.text_input(
                    "Experience level (new / experienced)", ext.get("experience", "")
                )
                st.subheader("Internal notes")
                auto_text_input("Helpjuice link", "internal_helpjuice")
                auto_text_area("Logs / screenshots", "internal_logs", height=68)
                st.subheader("Conclusion")
                auto_text_input("Root cause", "root_cause")
                auto_text_input("Solution", "solution")
                auto_text_input("Customer satisfaction survey URL", "survey_link")
                st.subheader("Additional information")
                auto_text_area(
                    "Additional details",
                    "additional_info",
                    height=400,
                    help=(
                        "Include details such as antivirus, firewalls enabled, update history, "
                        "related case ID, possible cause, performance issues, manual additional notes, "
                        "recurring issues, and recent issues."
                    ),
                )
                st.subheader("Support Fee")
                ct_key = widget_key("customer_trios_only", case_idx)
                sf_key = widget_key("support_fee_accepted", case_idx)
                st.checkbox(
                    "Customer is TRIOS Only?",
                    value=st.session_state.get(ct_key, False),
                    key=ct_key,
                    on_change=_update_field,
                    args=("customer_trios_only",),
                )
                if st.session_state.get(ct_key):
                    st.checkbox(
                        "Support fee price accepted?",
                        value=st.session_state.get(sf_key, False),
                        key=sf_key,
                        on_change=_update_field,
                        args=("support_fee_accepted",),
                    )
                else:
                    st.session_state[sf_key] = False
                    D.support_fee_accepted = False
                    autosave()
                st.markdown("---")
                st.download_button(
                    "Download PDF",
                    make_pdf(D, cat_map),
                    file_name=f"{D.case_id or 'case'}.pdf",
                    mime="application/pdf",
                    key=widget_key("download_pdf", case_idx),
                )
            with left:
                st.subheader("Documentation Preview – Copy‑friendly Tables")
                for cat in cat_map:
                    st.markdown(f"**{table_title(cat)}**")
                    st.dataframe(
                        category_dataframe(cat, D, cat_map), use_container_width=True
                    )
                if st.session_state.categorizer_result:
                    st.subheader("Kiroshi Categorizer")
                    st.text_area(
                        "Categorization Output",
                        st.session_state.categorizer_result,
                        height=150,
                        key=widget_key("categorizer_output", case_idx),
                    )

    # ================== TRACKING TAB =================
    if tab_tracking:
        with tab_tracking:
            st.subheader("Tracking")
            tracking_type = st.selectbox(
                "Tracking type", ["Dell", "FedEx"], key=widget_key("tracking_type", case_idx)
            )
            company = st.text_input("Company", key=widget_key("track_company", case_idx))
            end_user = st.text_input("End User", key=widget_key("track_end_user", case_idx))
            creation_day = st.date_input(
                "Creation day", value=date.today(), key=widget_key("track_creation_day", case_idx)
            )
            ticket_number = st.text_input(
                "Ticket Number", key=widget_key("track_ticket_number", case_idx)
            )
            if tracking_type == "Dell":
                service_tag = st.text_input(
                    "Service Tag", key=widget_key("track_service_tag", case_idx)
                )
                status = st.selectbox(
                    "Status",
                    [
                        "Resolved",
                        "Waiting for Technician",
                        "Waiting for clinic to send back PC for review",
                        "Pending update",
                    ],
                    key=widget_key("track_status", case_idx),
                )
            else:
                expected_arrival_date = st.date_input(
                    "Expected arrival date",
                    value=date.today(),
                    key=widget_key("track_expected_arrival", case_idx),
                )
                status = st.selectbox(
                    "Status",
                    [
                        "Scanner arrived and waiting for the return",
                        "Waiting for scanner to arrive",
                        "waiting for pickup",
                        "scanner sent",
                        "waiting to arrive to the doctor's office.",
                    ],
                    key=widget_key("track_status", case_idx),
                )
            if st.button("Save and track", key=widget_key("save_and_track", case_idx)):
                info = {
                    "type": tracking_type,
                    "case_id": D.case_id,
                    "company": company,
                    "end_user": end_user,
                    "creation_day": creation_day.isoformat(),
                    "ticket_number": ticket_number,
                    "status": status,
                }
                if tracking_type == "Dell":
                    info["service_tag"] = service_tag
                    file_path = TRACKED_CASES_DIR / f"Dell_{D.case_id}_Active.json"
                else:
                    info["expected_arrival_date"] = expected_arrival_date.isoformat()
                    file_path = TRACKED_CASES_DIR / f"FedEx_{D.case_id}_Active.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=2)
                st.success("Tracking information saved.")
            if st.button(
                "Close case & stop tracking",
                key=widget_key("close_tracking", case_idx),
            ):
                dell_file = TRACKED_CASES_DIR / f"Dell_{D.case_id}_Active.json"
                fedex_file = TRACKED_CASES_DIR / f"FedEx_{D.case_id}_Active.json"
                for f in [dell_file, fedex_file]:
                    if f.exists():
                        dest = DATABASE_DIR / f"{D.case_id}.json"
                        try:
                            f.rename(dest)
                        except Exception:
                            pass
                st.session_state.track_case = False
                st.rerun()

    # ================== ESCALATIONS TAB =================
    if tab_escalations:
        with tab_escalations:
            if email_type == "Broken Tip":
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
                best_cb = st.checkbox(
                    "Specify best call-back time",
                    D.best_time not in ("", "ASAP"),
                    key=widget_key("best_cb", case_idx),
                )

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
                cb_remote = st.checkbox(
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
                st.checkbox(
                    "Need contact information?",
                    st.session_state.get(cb_contact_key, False),
                    key=cb_contact_key,
                )
                cb_clarify_key = widget_key("callback_clarify", case_idx)
                st.checkbox(
                    "Need to clarify what happened?",
                    st.session_state.get(cb_clarify_key, False),
                    key=cb_clarify_key,
                )
                cb_needed_key = widget_key("callback_needed", case_idx)
                st.checkbox(
                    "Callback needed?",
                    st.session_state.get(cb_needed_key, True),
                    key=cb_needed_key,
                )
                cb_address_key = widget_key("callback_address", case_idx)
                cb_address = st.checkbox(
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

            elif email_type == "Custom Request":
                st.markdown("#### Custom email options")
                ext["reason"] = st.text_input(
                    "Reason for contacting the customer", ext.get("reason", "")
                )
                pat_cb = st.checkbox(
                    "Include Patterson legacy #",
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
                if "AX COORDINATORS" in cat_map:
                    st.markdown("#### AX Coordinators Table")
                    st.dataframe(
                        category_dataframe("AX COORDINATORS", D, cat_map),
                        use_container_width=True,
                    )
                    st.markdown("---")
                st.subheader("Escalation 2nd line")
                D.esc_name = D.caller_name
                st.text_input("Name", D.esc_name, disabled=True, key=widget_key("esc_name_tab", case_idx))
                D.esc_ph = D.phone_number
                st.text_input("Phone", D.esc_ph, disabled=True, key=widget_key("esc_ph_tab", case_idx))
                D.esc_email = D.email
                st.text_input("Email", D.esc_email, disabled=True, key=widget_key("esc_email_tab", case_idx))
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
            st.session_state.email_extra = ext
            static_templates = {
                "FedEx Tracking Email",
                "Replacement Wired Scanner Setup",
                "Replacement Move+ Closure",
            }
            if email_type not in static_templates:
                st.text_area(
                    prompt_label,
                    prompt,
                    height=300,
                    key=widget_key("api_prompt_area", case_idx),
                )
                st.session_state["last_prompt"] = prompt

                include_helpjuice = st.checkbox(
                    "Helpjuice tutorial", key=widget_key("api_helpjuice", case_idx)
                )
                include_restart = st.checkbox(
                    "Restart the computer", key=widget_key("api_restart", case_idx)
                )
                include_scan_time = st.checkbox(
                    "Scan time warning", key=widget_key("api_scan_time", case_idx)
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
                        with st.spinner("Contacting GPT-OSS..."):
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
                                reply = query_atom(
                                    augmented_prompt,
                                    st.session_state.atom_history,
                                    api_key,
                                    model,
                                    base_url,
                                )
                            except Exception as e:
                                st.error(str(e))
                            else:
                                st.session_state.atom_history.append({"role": "user", "content": augmented_prompt})
                                st.session_state.atom_history.append({"role": "assistant", "content": reply})
                                save_memory(st.session_state.atom_history)
                                st.session_state.generated_email = reply
                st.session_state.generated_email = st.text_area(
                    "Generated Email",
                    st.session_state.get("generated_email", ""),
                    height=300,
                    key=widget_key("generated_email_output", case_idx),
                )
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
            st.dataframe(
                category_dataframe("SCANNER HARDWARE", D, HW_CATEGORY_MAP), use_container_width=True
            )
    
    # ================== REMOTE SESSION TAB =================
    with tab_remote:
        st.subheader("Remote session – steps")
        auto_text_area("One step per line", "remote_steps", height=400)

    # ================== NOTES TAB =================
    with tab_notes:
        st.subheader("Scratchpad")
        scr_key = widget_key("scratch", case_idx)
        st.text_area(
            "Temporary notes",
            st.session_state.get(scr_key, ""),
            height=400,
            key=scr_key,
            on_change=autosave,
        )

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

        st.subheader("Recent cases")
        for idx, case in enumerate(load_recent_cases()):
            info_col, btn_col = st.columns([3, 1])
            info_col.write(f"{case['case_id']} - {case['path']}")
            if btn_col.button(
                "Load", key=widget_key(f"recent_load_{idx}", case_idx)
            ):
                request_load_from_path(case["path"])

        pending = st.session_state.get("pending_load")
        if pending:
            st.error("Remember to save your information before loading a new case")
            col_i, col_s = st.columns(2)
            if col_i.button("Ignore and load", key=widget_key("ignore_and_load", case_idx)):
                if "path" in pending:
                    load_case_from_path(pending["path"])
                else:
                    load_case_from_bytes(pending["data"])
                st.session_state.pending_load = None
            if col_s.button("Save", key=widget_key("save_before_loading", case_idx)):
                save_case_to_database(D)

    # ================== SETTINGS TAB =================
    with tab_settings:
        if case_idx == 0:
            st.subheader("Modes")
            st.checkbox("2nd Line mode", key="second_line_mode")
            prev_debug = st.session_state.debug_mode
            st.checkbox("Show Debug tab", key="debug_mode")
            if prev_debug and not st.session_state.debug_mode:
                st.session_state.debug_auth = False
                st.session_state.show_bored = False
        else:
            st.info("Settings available in first case tab.")

    # ================== ATOM CHAT TAB =================
    with tab_atom:
        st.image(str(ATOM_LOGO_PATH), width=80)
        st.subheader("A.A.T.O.M. Chat")
        with st.expander("Personality Construct"):
            st.text_area(
                "System Prompt",
                st.session_state.get("system_prompt", SYSTEM_PROMPT),
                height=300,
                key=widget_key("system_prompt_display", case_idx),
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
                "Add document", type=["txt"], key=widget_key("doc_file", case_idx)
            )
            doc_title = st.text_input("Title", key=widget_key("doc_title", case_idx))
            if st.button("Save document", key=widget_key("save_doc", case_idx)):
                if doc_file and doc_title:
                    content = doc_file.getvalue().decode("utf-8", errors="ignore")
                    st.session_state.manual_docs.append({"title": doc_title, "content": content})
                    save_manual_docs(st.session_state.manual_docs)
                    st.success("Document saved.")
                else:
                    st.error("Provide both title and document.")

        st.subheader("Search manual database")
        search_query = st.text_input("Search query", key=widget_key("db_query", case_idx))
        if st.button("Search in database", key=widget_key("db_search_button", case_idx)):
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
                        reply = query_atom(
                            message, st.session_state.atom_history, api_key, model, base_url
                        )
                    except Exception as e:
                        st.session_state.db_search_result = str(e)
                    else:
                        st.session_state.atom_history.append({"role": "user", "content": f"[DB Search] {search_query}"})
                        st.session_state.atom_history.append({"role": "assistant", "content": reply})
                        save_memory(st.session_state.atom_history)
                        st.session_state.db_search_result = reply
                else:
                    st.session_state.db_search_result = "No documents matched your query."
        if st.session_state.db_search_result:
            st.text_area(
                "Search result",
                st.session_state.db_search_result,
                height=150,
                key=widget_key("db_search_result", case_idx),
            )

        for msg in st.session_state.atom_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        if user_msg := st.chat_input(
            "Message", key=widget_key("atom_chat_input", case_idx)
        ):
            if not api_key and base_url.startswith("https://api.openai.com"):
                st.error("Please set your OpenAI API key in the Debug tab.")
            else:
                history = st.session_state.atom_history.copy()
                try:
                    reply = query_atom(user_msg, history, api_key, model, base_url)
                except Exception as e:
                    st.session_state.atom_history.append({"role": "user", "content": user_msg})
                    st.session_state.atom_history.append({"role": "assistant", "content": str(e)})
                else:
                    st.session_state.atom_history.append({"role": "user", "content": user_msg})
                    st.session_state.atom_history.append({"role": "assistant", "content": reply})
                save_memory(st.session_state.atom_history)
                st.rerun()
        if st.button("Clear memory", key=widget_key("atom_clear", case_idx)):
            st.session_state.atom_history = []
            save_memory([])
            st.rerun()

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
    if st.button("Take Screenshot", key=widget_key("take_screenshot", case_idx)):
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

    # ================== DEBUG TAB =================
    if tab_debug:
        with tab_debug:
            if case_idx != 0:
                st.info("Debug available in first case tab.")
            elif st.session_state.debug_auth:
                st.subheader("Debug")
                st.selectbox(
                    "AI Mode",
                    ["Cloud", "Local API", "Local Model"],
                    key="ai_mode",
                )
                if st.session_state.ai_mode == "Cloud":
                    st.text_input(
                        "OpenAI API Key", type="password", key="openai_api_key"
                    )
                    st.text_input("AI Base URL", key="ai_base_url")
                elif st.session_state.ai_mode == "Local API":
                    st.text_input(
                        "AI Base URL", key="ai_base_url", value=st.session_state.ai_base_url
                    )
                    st.text_input(
                        "API Key (optional)", type="password", key="openai_api_key"
                    )
                else:
                    st.session_state.ai_base_url = ""
                    st.session_state.openai_api_key = ""
                    st.info(
                        "Using local transformers model; no API key or Base URL required."
                    )
                st.selectbox(
                    "Model", ["gpt-4o", "gpt-4", "gpt-3.5-turbo"], key="openai_model"
                )
                st.selectbox(
                    "Personality mode", ["utility", "coffee"], key="personality_mode"
                )
                st.text_area("Allowed categories block", key="taxonomy_block", height=150)
                st.text_area("Signals config JSON", key="signals_config", height=150)
                st.json(st.session_state)
                st.subheader("Logs")
                st.text(tail_log(LOG_FILE))
                st.divider()
                if st.button("I'm bored", key="debug_bored"):
                    st.session_state.show_bored = True
                    st.rerun()
            else:
                st.session_state.show_bored = False
                user = st.text_input("Username", key="debug_user")
                pw = st.text_input("Password", type="password", key="debug_pass")
                if st.button("Login", key="debug_login"):
                    if user == "admin" and pw == "admin":
                        st.session_state.debug_auth = True
                    else:
                        st.error("Invalid credentials")

    autosave()

case_labels = [
    cs.case.case_id or f'Case {i+1}' for i, cs in enumerate(st.session_state.case_sessions)
] + ['+ New Case']
case_tabs = st.tabs(case_labels)
for idx, tab in enumerate(case_tabs):
    with tab:
        if idx == len(st.session_state.case_sessions):
            if st.button('Add Case'):
                st.session_state.case_sessions.append(CaseSession(case=CaseData()))
                st.rerun()
        else:
            load_case_state(idx)
            render_case_ui(idx)
            save_case_state(idx)
