# -*- coding: utf-8 -*-
"""
Kiroshi V1.0.0 – IT Case Documentation Helper
Run:
    streamlit run case_documentation_app.py
"""

import io
import json
import os
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime, date
import logging
from pathlib import Path

import pandas as pd
import streamlit as st
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

VERSION = "1.0.0"
TODAY_STR = datetime.now().strftime("%d%m%Y")
AUTOSAVE_FILE = "autosave.json"
DEFAULT_OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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",
)
LOG_FILE = "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logging.info("Kiroshi app started")

# Local logo assets from repository
ASSETS_DIR = Path(__file__).parent
KIROSHI_LOGO_PATH = ASSETS_DIR / "Kiroshi_Logo.png"
ATOM_LOGO_PATH = ASSETS_DIR / "atom_logo.png"

# ─────────────────────────── CONFIG ────────────────────────────
st.set_page_config(
    page_title=f"Kiroshi V{VERSION}",
    layout="wide",
    page_icon=str(KIROSHI_LOGO_PATH),
)
st.image(str(KIROSHI_LOGO_PATH))

# ────────────────────── SESSION STATE ────────────────────────
def _init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

_init_state("case", {})
_init_state("uploads", [])
_init_state("scratch", "")
_init_state("email_type", "Recap (Customer)")
_init_state("email_extra", {})
_init_state("include_hw", False)
_init_state("include_escalations", False)
_init_state("debug_auth", False)
_init_state("_autosave_loaded", False)
_init_state("openai_api_key", DEFAULT_OPENAI_API_KEY)
_init_state("openai_model", "gpt-4o")
_init_state("api_helpjuice", False)
_init_state("api_restart", False)
_init_state("api_scan_time", False)
_init_state("atom_history", load_memory())
_init_state("manual_docs", load_manual_docs())
_init_state("verify_result", "")
_init_state("ask_result", "")
_init_state("system_prompt", SYSTEM_PROMPT)
_init_state("personality_mode", "utility")
_init_state("ai_assist_result", "")
_init_state("db_search_result", "")


def load_autosave():
    if st.session_state._autosave_loaded:
        return
    if os.path.exists(AUTOSAVE_FILE):
        try:
            with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            st.session_state.case = data.get("case", {})
            st.session_state.scratch = data.get("scratch", "")
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
    antivirus: str = ""
    firewalls_enabled: str = ""
    update_history: str = ""
    related_case_id: str = ""
    possible_cause: str = ""
    performance_issue: str = ""
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


# convert stored dict to dataclass
if isinstance(st.session_state.case, dict):
    st.session_state.case = CaseData(**st.session_state.case)
D: CaseData = st.session_state.case

# Ensure the survey link widget has an initial value to prevent
# "attribute missing" errors before the first user interaction.
_init_state("survey_link", D.survey_link)

# Button to clear all case data and reset form
def autosave():
    with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
        json.dump({"case": asdict(D), "scratch": st.session_state.scratch}, f, indent=2)


def _update_field(field: str):
    """Update dataclass field from session state and persist."""
    setattr(D, field, st.session_state[field])
    autosave()


def auto_text_input(label: str, field: str, container=st, **kwargs):
    """Text input that saves on every change."""
    kwargs.setdefault("key", field)
    value = container.text_input(
        label, getattr(D, field), on_change=_update_field, args=(field,), **kwargs
    )
    setattr(D, field, value)


def auto_text_area(label: str, field: str, container=st, **kwargs):
    """Text area that saves on every change."""
    kwargs.setdefault("key", field)
    value = container.text_area(
        label, getattr(D, field), on_change=_update_field, args=(field,), **kwargs
    )
    setattr(D, field, value)

BASE_CATEGORY_MAP = {
    "HEADER": ["company_name", "subscription_id", "brief_description", "case_id"],
    "DESCRIPTION": ["description"],
    "PHONECALL": [
        "caller_name",
        "phone_description",
        "dongle_number",
        "phone_number",
        "teamviewer_id",
        "teamviewer_password",
        "email",
    ],
    "INTERNAL NOTES": ["internal_helpjuice", "internal_logs"],
    "REMOTE SESSION": ["remote_steps"],
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
    "ADDITIONAL INFORMATION": [
        "antivirus",
        "firewalls_enabled",
        "update_history",
        "related_case_id",
        "possible_cause",
        "performance_issue",
    ],
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
    "SCANNER HARDWARE": ["scanner_sn", "base_sn", "trios_module_version"],
}


def active_category_map():
    cm = BASE_CATEGORY_MAP.copy()
    if not st.session_state.get("include_escalations", True):
        cm.pop("AX COORDINATORS", None)
        cm.pop("ESCALATION 2ND LINE", None)
    if st.session_state.get("include_hw"):
        cm.update(HW_CATEGORY_MAP)
    return cm

# ────────── HELPERS ──────────

def build_title(d: CaseData) -> str:
    """Construct a helper string for case titles."""
    return f"|{d.company_name}|{d.subscription_id}|{d.brief_description}|{d.case_id}|"


def compute_progress(d: CaseData, cat_map):
    """Compute completion progress for each category."""
    prog, miss = {}, {}
    for cat, flds in cat_map.items():
        vals = [getattr(d, f) for f in flds]
        done = sum(bool(v) for v in vals)
        prog[cat] = int(done / len(flds) * 100)
        miss[cat] = [f for f, v in zip(flds, vals) if not v]
    return prog, miss


def category_dataframe(cat: str, d: CaseData, cat_map) -> pd.DataFrame:
    """Return a DataFrame with human readable field names for a category."""
    rows = []
    for fld in cat_map[cat]:
        rows.append({"Field": fld.replace("_", " ").title(), "Value": getattr(d, fld)})
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

# ──────────── TABS ───────────
st.session_state.include_escalations = st.checkbox(
    "Include escalations", st.session_state.include_escalations
)
st.session_state.include_hw = st.checkbox(
    "Include hardware issue fields", st.session_state.include_hw
)
cat_map = active_category_map()

tab_labels = ["Case"]
if st.session_state.include_escalations:
    tab_labels.append("Escalations")
tab_labels.append("Email")
if st.session_state.include_hw:
    tab_labels.append("Hardware Issues")
tab_labels += ["Notes", "Tables", "Atom Chat", "Debug"]

tabs = st.tabs(tab_labels)
tab_iter = iter(tabs)
tab_case = next(tab_iter)
tab_escalations = next(tab_iter) if st.session_state.include_escalations else None
tab_email = next(tab_iter)
tab_hw = next(tab_iter) if st.session_state.include_hw else None
tab_notes = next(tab_iter)
tab_tables = next(tab_iter)
tab_atom = next(tab_iter)
tab_debug = next(tab_iter)

# ================== CASE TAB =================
with tab_case:
    api_key = st.session_state.openai_api_key
    model = st.session_state.openai_model
    verify_col, ask_col, assist_col, clear_col = st.columns(4)
    with verify_col:
        if st.button("Verify", key="verify_button"):
            logging.info("Verify button clicked")
            if not api_key:
                st.error("Please set your OpenAI API key in the Debug tab.")
            else:
                case_dict = asdict(D)
                if not st.session_state.include_hw:
                    for fld in [
                        "service_tag",
                        "pc_model",
                        "windows_version",
                        "bios_version",
                        "graphics_card",
                        "processor",
                        "warranty",
                        "scanner_sn",
                        "base_sn",
                        "trios_module_version",
                    ]:
                        case_dict.pop(fld, None)
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
                    )
                except Exception as e:
                    st.error(str(e))
                else:
                    st.session_state.atom_history.append({"role": "user", "content": user_message})
                    st.session_state.atom_history.append({"role": "assistant", "content": reply})
                    save_memory(st.session_state.atom_history)
                    st.session_state.verify_result = reply
    with ask_col:
        if st.button("Ask", key="ask_button"):
            logging.info("Ask button clicked")
            if not api_key:
                st.error("Please set your OpenAI API key in the Debug tab.")
            else:
                case_dict = asdict(D)
                if not st.session_state.include_hw:
                    for fld in [
                        "service_tag",
                        "pc_model",
                        "windows_version",
                        "bios_version",
                        "graphics_card",
                        "processor",
                        "warranty",
                        "scanner_sn",
                        "base_sn",
                        "trios_module_version",
                    ]:
                        case_dict.pop(fld, None)
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
                    )
                except Exception as e:
                    st.error(str(e))
                else:
                    st.session_state.atom_history.append({"role": "user", "content": user_message})
                    st.session_state.atom_history.append({"role": "assistant", "content": reply})
                    save_memory(st.session_state.atom_history)
                    st.session_state.ask_result = reply
    with assist_col:
        if st.button("AI Assistance", key="assist_button"):
            logging.info("AI Assistance button clicked")
            if not api_key:
                st.error("Please set your OpenAI API key in the Debug tab.")
            else:
                case_dict = asdict(D)
                if not st.session_state.include_hw:
                    for fld in [
                        "service_tag",
                        "pc_model",
                        "windows_version",
                        "bios_version",
                        "graphics_card",
                        "processor",
                        "warranty",
                        "scanner_sn",
                        "base_sn",
                        "trios_module_version",
                    ]:
                        case_dict.pop(fld, None)
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
                    )
                except Exception as e:
                    st.error(str(e))
                else:
                    st.session_state.atom_history.append({"role": "user", "content": user_message})
                    st.session_state.atom_history.append({"role": "assistant", "content": reply})
                    save_memory(st.session_state.atom_history)
                    st.session_state.ai_assist_result = reply
                    try:
                        suggestions = json.loads(reply)
                    except json.JSONDecodeError:
                        st.error("AI Assistance did not return valid JSON.")
                    else:
                        for fld, val in suggestions.items():
                            if hasattr(D, fld) and not getattr(D, fld):
                                setattr(D, fld, val)
                        autosave()
    with clear_col:
        if st.button("Clear all", key="clear_all_button"):
            logging.info("Clear all button clicked")
            api_key = st.session_state.get("openai_api_key", "")
            st.session_state.clear()
            st.session_state.openai_api_key = api_key
            if os.path.exists(AUTOSAVE_FILE):
                try:
                    os.remove(AUTOSAVE_FILE)
                except OSError:
                    pass
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
        )
    prog, miss = compute_progress(D, cat_map)
    left, right = st.columns([1, 2], gap="medium")
    with right:
        st.subheader("Build title")
        st.code(build_title(D))
        st.subheader("Progress by category")
        st.bar_chart(
            pd.DataFrame({"Category": prog.keys(), "Done": prog.values()}).set_index(
                "Category"
            )
        )
        todo = [
            f"**{c}** → {', '.join(flds)}" for c, flds in miss.items() if flds
        ]
        st.markdown("### To‑do" if todo else "All mandatory info filled.")
        for t in todo:
            st.markdown(f"- {t}")
        st.subheader("Case Header")
        auto_text_input("Company name", "company_name")
        auto_text_input("Subscription ID", "subscription_id")
        auto_text_input("Brief description", "brief_description")
        auto_text_input("Case ID", "case_id")
        st.subheader("Description (What / When / Where)")
        auto_text_area("Description", "description", height=68)
        st.subheader("Phone-call notes")
        auto_text_input("Caller name", "caller_name")
        auto_text_area("Caller issue description", "phone_description", height=68)
        c1, c2 = st.columns(2)
        auto_text_input("Dongle number", "dongle_number", container=c1)
        auto_text_input("Phone number", "phone_number", container=c2)
        auto_text_input("TeamViewer ID", "teamviewer_id", container=c1)
        auto_text_input(
            "TeamViewer password",
            "teamviewer_password",
            container=c2,
        )
        auto_text_input("Email", "email")
        st.subheader("Internal notes")
        auto_text_input("Helpjuice link", "internal_helpjuice")
        auto_text_area("Logs / screenshots", "internal_logs", height=68)
        st.subheader("Remote session – steps")
        auto_text_area("One step per line", "remote_steps", height=68)
        st.subheader("Conclusion")
        auto_text_input("Root cause", "root_cause")
        auto_text_input("Solution", "solution")
        auto_text_input("Customer satisfaction survey URL", "survey_link")
        st.subheader("Additional information")
        av_check = st.checkbox(
            "Customer uses antivirus?", value=D.antivirus.startswith("Customer uses")
        )
        if av_check:
            av_name = st.text_input(
                "What antivirus?",
                D.antivirus.replace("Customer uses antivirus: ", ""),
                key="antivirus_name",
                on_change=autosave,
            )
            D.antivirus = (
                f"Customer uses antivirus: {av_name}"
                if av_name
                else "Customer uses antivirus:"
            )
        else:
            D.antivirus = "Customer does not use antivirus."
        autosave()
        fw_check = st.checkbox(
            "Firewalls are turned on?", value=D.firewalls_enabled.startswith("Firewalls are turned on")
        )
        D.firewalls_enabled = (
            "Firewalls are turned on." if fw_check else "Firewalls are not turned on."
        )
        autosave()
        upd_check = st.checkbox(
            "Any update was made?", value=not D.update_history.startswith("No updates") and bool(D.update_history)
        )
        if upd_check:
            upd_text = st.text_input(
                "From what version to what version?",
                D.update_history.replace("An update was made: ", ""),
                key="update_history",
                on_change=autosave,
            )
            D.update_history = (
                f"An update was made: {upd_text}"
                if upd_text
                else "An update was made:"
            )
        else:
            D.update_history = "No updates were made."
        autosave()
        rel_check = st.checkbox(
            "Is there any related case?", value=D.related_case_id.startswith("There is a related case")
        )
        if rel_check:
            rel_id = st.text_input(
                "Related case number",
                D.related_case_id.replace("There is a related case: ", ""),
                key="related_case_id",
                on_change=autosave,
            )
            D.related_case_id = (
                f"There is a related case: {rel_id}"
                if rel_id
                else "There is a related case:"
            )
        else:
            D.related_case_id = "There are no related cases."
        autosave()
        cause_check = st.checkbox(
            "Any possible cause why it happened?",
            value=D.possible_cause.startswith("Possible cause"),
        )
        if cause_check:
            cause_text = st.text_input(
                "Why?",
                D.possible_cause.replace("Possible cause: ", ""),
                key="possible_cause",
                on_change=autosave,
            )
            D.possible_cause = (
                f"Possible cause: {cause_text}" if cause_text else "Possible cause:"
            )
        else:
            D.possible_cause = "There is no known possible cause."
        autosave()
        perf_check = st.checkbox(
            "Performance related issue?",
            value=D.performance_issue.startswith("It is a performance related issue"),
        )
        if perf_check:
            perf_text = st.text_input(
                "Why?",
                D.performance_issue.replace(
                    "It is a performance related issue: ", ""
                ),
                key="performance_issue",
                on_change=autosave,
            )
            D.performance_issue = (
                f"It is a performance related issue: {perf_text}"
                if perf_text
                else "It is a performance related issue:"
            )
        else:
            D.performance_issue = "It is not a performance related issue."
        autosave()
        st.markdown("---")
        st.download_button(
            "Download PDF",
            make_pdf(D, cat_map),
            file_name=f"{D.case_id or 'case'}.pdf",
            mime="application/pdf",
        )
    with left:
        st.subheader("Documentation Preview – Copy‑friendly Tables")
        for cat in cat_map:
            st.markdown(f"**{table_title(cat)}**")
            st.dataframe(
                category_dataframe(cat, D, cat_map), use_container_width=True
            )

# ================== ESCALATIONS TAB =================
if tab_escalations:
    with tab_escalations:
        st.subheader("AX Coordinators")
        st.text_area("Request / Issue", D.description, disabled=True)
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
        )
        if best_cb:
            auto_text_input(
                "Best call-back time + timezone",
                "best_time",
            )
        else:
            D.best_time = "ASAP"
            autosave()
        pat_cb = st.checkbox(
            "Patterson legacy #",
            D.patterson not in ("", "N/A"),
        )
        if pat_cb:
            auto_text_input(
                "Patterson legacy #",
                "patterson",
            )
        else:
            D.patterson = "N/A"
            autosave()
        str_cb = st.checkbox(
            "Straumann ticket #",
            D.straumann not in ("", "N/A"),
        )
        if str_cb:
            auto_text_input(
                "Straumann ticket #",
                "straumann",
            )
        else:
            D.straumann = "N/A"
            autosave()
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
        st.markdown("#### Escalation 2nd line Table")
        st.dataframe(
            category_dataframe("ESCALATION 2ND LINE", D, cat_map),
            use_container_width=True,
        )

# ================== EMAIL TAB =================
with tab_email:
    st.subheader("Email Prompt Generator")
    email_choices = ["Recap (Customer)", "Broken Scanner", "Broken Tip"]
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
    if email_type == "Recap (Customer)":
        greeting = f"Dear {(D.caller_name or 'Customer')}{(' / ' + D.company_name + ' team') if D.company_name else ' team'},"
        steps_summary = "\n".join(D.remote_steps.splitlines()) or "—"
        prompt = f"""You are a friendly IT‑support agent. Draft an engaging, upbeat email (≤180 words) that recaps the case and strongly
motivates the customer to complete a brief satisfaction survey (takes <2 minutes) to help improve our service.
The email must start with: {greeting}

Include: Case ID, root cause, a brief 1‑3 bullet summary of the steps taken, and the final solution.
Use a warm tone, thank the customer for their time, invite further questions, and end with a clear call‑to‑action to the survey.
Apply persuasive techniques: personalize with the customer's name, show appreciation (reciprocity), mention that other customers found the survey quick and helpful (social proof), emphasise how their feedback shapes future support, and invite them to help improve our service (commitment).

Return only the email body.

DATA:
Case ID: {D.case_id}
Root cause: {D.root_cause}
Steps taken:
{steps_summary}
Solution: {D.solution}
Survey link: {D.survey_link}"""
    elif email_type == "Broken Scanner":
        st.markdown("#### Incident questionnaire (prefill if known)")
        ext["experience"] = st.text_input(
            "Experience level (new / experienced)", ext.get("experience", "")
        )
        ext["drop_details"] = st.text_area(
            "Describe how / when scanner was dropped", ext.get("drop_details", "")
        )
        ext["cause"] = st.text_area(
            "What do you think caused the incident?", ext.get("cause", "")
        )
        ext["prevention"] = st.text_area(
            "Ideas to prevent", ext.get("prevention", "")
        )
        ext["satisfaction"] = st.text_input(
            "Are you satisfied with service?", ext.get("satisfaction", "")
        )

        prompt = f"""Draft a friendly e‑mail asking the customer to confirm / provide the following details about the broken scanner.
Number the questions 1‑5 and leave blank space after each for their answers.

Questions:
1. Experience with intra‑oral scanners – {ext['experience']}
2. How and when was the scanner dropped? – {ext['drop_details']}
3. What do you think caused the incident? – {ext['cause']}
4. Ideas on preventing similar incidents – {ext['prevention']}
5. Satisfaction with our proposed solution – {ext['satisfaction']}

Prefill any answers we already know (shown above) right under each question.
"""

    elif email_type == "Broken Tip":
        st.markdown("#### Cleaning questionnaire (prefill if known)")
        ext["times_autoclaved"] = st.text_input(
            "Times autoclaved", ext.get("times_autoclaved", "")
        )
        ext["bath_number"] = st.text_input(
            "Tip bath number", ext.get("bath_number", "")
        )
        ext["model"] = st.text_input("Autoclave model", ext.get("model", ""))
        ext["program"] = st.text_input(
            "Program used", ext.get("program", "")
        )
        ext["airtight"] = st.text_input(
            "Autoclaved in airtight pouch?", ext.get("airtight", "")
        )
        ext["other"] = st.text_area(
            "Other relevant info", ext.get("other", "")
        )

        prompt = f"""Draft a courteous e‑mail requesting the following information about the damaged tip.
List each question and provide any known answer beneath it, ready for the customer to correct/confirm.

1. Times autoclaved – {ext['times_autoclaved']}
2. Bath number – {ext['bath_number']}
3. Autoclave model – {ext['model']}
4. Program used – {ext['program']}
5. Autoclaved in airtight pouch? – {ext['airtight']}
6. Other info – {ext['other']}
"""

    st.session_state.email_extra = ext
    st.text_area("ChatGPT prompt (copy & paste)", prompt, height=300, key="api_prompt_area")
    st.session_state["last_prompt"] = prompt

    include_helpjuice = st.checkbox("Helpjuice tutorial", key="api_helpjuice")
    include_restart = st.checkbox("Restart the computer", key="api_restart")
    include_scan_time = st.checkbox("Scan time warning", key="api_scan_time")

    if st.button("Generate Email (ChatGPT API)"):
        api_key = st.session_state.openai_api_key
        model = st.session_state.openai_model
        if not api_key:
            st.error("Please set your OpenAI API key in the Debug tab.")
        elif not prompt.strip():
            st.error("Prompt is empty.")
        else:
            with st.spinner("Contacting ChatGPT..."):
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
                    response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": "You are a helpful assistant."},
                                {"role": "user", "content": augmented_prompt},
                            ],
                            "max_tokens": 600,
                            "temperature": 0.7,
                        },
                        timeout=30,
                        verify=False,
                    )
                    if response.status_code == 200:
                        result = response.json()
                        email_text = result["choices"][0]["message"]["content"]
                        st.success("Email generated!")
                        st.text_area("Generated Email", email_text, height=300, key="generated_email")
                    else:
                        st.error(
                            f"API Error: {response.status_code}\n{response.text}"
                        )
                except Exception as e:  # pragma: no cover - just in case
                    st.error(f"Request failed: {e}")

# ================== HARDWARE ISSUES TAB =================
if st.session_state.include_hw:
    with tab_hw:
        st.subheader("PC Hardware Issue")
        col_pc1, col_pc2 = st.columns(2)
        auto_text_input("Service Tag", "service_tag", container=col_pc1)
        auto_text_input("PC Model", "pc_model", container=col_pc2)
        auto_text_input(
            "Windows version", "windows_version", container=col_pc1
        )
        auto_text_input("BIOS version", "bios_version", container=col_pc2)
        auto_text_input("Graphics Card", "graphics_card", container=col_pc1)
        auto_text_input("Processor", "processor", container=col_pc2)
        auto_text_input("Warranty", "warranty")
        st.dataframe(
            category_dataframe("PC HARDWARE", D, HW_CATEGORY_MAP), use_container_width=True
        )

        st.markdown("---")
        st.subheader("Scanner Hardware Issue")
        auto_text_input("Scanner S/N", "scanner_sn")
        auto_text_input("Base S/N", "base_sn")
        auto_text_input("TRIOS MODULE Version", "trios_module_version")
        st.dataframe(
            category_dataframe("SCANNER HARDWARE", D, HW_CATEGORY_MAP), use_container_width=True
        )

# ================== NOTES TAB =================
with tab_notes:
    st.subheader("Scratchpad")
    st.text_area(
        "Temporary notes",
        st.session_state.scratch,
        height=400,
        key="scratch",
        on_change=autosave,
    )

# ================== TABLES TAB =================
with tab_tables:
    st.subheader("Copy all tables")
    for cat in cat_map:
        st.markdown(f"**{table_title(cat)}**")
        st.dataframe(category_dataframe(cat, D, cat_map), use_container_width=True)

# ================== ATOM CHAT TAB =================
with tab_atom:
    st.image(str(ATOM_LOGO_PATH), width=80)
    st.subheader("A.A.T.O.M. Chat")
    with st.expander("Personality Construct"):
        st.text_area(
            "System Prompt",
            st.session_state.get("system_prompt", SYSTEM_PROMPT),
            height=300,
        )
    api_key = st.session_state.openai_api_key
    model = st.session_state.openai_model
    if not api_key:
        st.info("Set your OpenAI API key in the Debug tab.")

    with st.expander("Manual Documents Database"):
        if st.session_state.manual_docs:
            st.markdown("**Stored documents:**")
            for doc in st.session_state.manual_docs:
                st.markdown(f"- {doc['title']}")
        doc_file = st.file_uploader("Add document", type=["txt"], key="doc_file")
        doc_title = st.text_input("Title", key="doc_title")
        if st.button("Save document", key="save_doc"):
            if doc_file and doc_title:
                content = doc_file.getvalue().decode("utf-8", errors="ignore")
                st.session_state.manual_docs.append({"title": doc_title, "content": content})
                save_manual_docs(st.session_state.manual_docs)
                st.success("Document saved.")
            else:
                st.error("Provide both title and document.")

    st.subheader("Search manual database")
    search_query = st.text_input("Search query", key="db_query")
    if st.button("Search in database", key="db_search_button"):
        if not api_key:
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
                    reply = query_atom(message, st.session_state.atom_history, api_key, model)
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
        st.text_area("Search result", st.session_state.db_search_result, height=150)

    for msg in st.session_state.atom_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if user_msg := st.chat_input("Message", key="atom_chat_input"):
        if not api_key:
            st.error("Please set your OpenAI API key in the Debug tab.")
        else:
            history = st.session_state.atom_history.copy()
            try:
                reply = query_atom(user_msg, history, api_key, model)
            except Exception as e:
                st.session_state.atom_history.append({"role": "user", "content": user_msg})
                st.session_state.atom_history.append({"role": "assistant", "content": str(e)})
            else:
                st.session_state.atom_history.append({"role": "user", "content": user_msg})
                st.session_state.atom_history.append({"role": "assistant", "content": reply})
            save_memory(st.session_state.atom_history)
            st.rerun()
    if st.button("Clear memory", key="atom_clear"):
        st.session_state.atom_history = []
        save_memory([])
        st.rerun()

# ================== FILE UPLOADS & EXPORTS =================
st.markdown("---")
st.subheader("Exports & attachments")
new_files = st.file_uploader(
    "Upload screenshots / logs / videos", accept_multiple_files=True
)
if new_files:
    existing_names = {f.name for f in st.session_state.uploads}
    for nf in new_files:
        if nf.name not in existing_names:
            st.session_state.uploads.append(nf)
            existing_names.add(nf.name)
if st.session_state.uploads:
    st.markdown("Files queued:")
    for f in st.session_state.uploads:
        st.markdown(f"• {f.name} ({len(f.getvalue())//1024} KB)")
    if st.button("Create ZIP"):
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in st.session_state.uploads:
                z.writestr(f.name, f.getvalue())
            z.writestr("case.json", json.dumps(asdict(D), indent=2))
        zbuf.seek(0)
        st.download_button(
            "Download attachments.zip",
            zbuf,
            file_name=f"{D.case_id or 'case'}_attachments.zip",
            mime="application/zip",
        )

# ================== DEBUG TAB =================
with tab_debug:
    if st.session_state.debug_auth:
        st.subheader("Debug")
        st.text_input("OpenAI API Key", type="password", key="openai_api_key")
        st.selectbox("Model", ["gpt-4o", "gpt-4", "gpt-3.5-turbo"], key="openai_model")
        st.selectbox("Personality mode", ["utility", "coffee"], key="personality_mode")
        st.json(st.session_state)
        st.subheader("Logs")
        st.text(tail_log(LOG_FILE))
    else:
        user = st.text_input("Username", key="debug_user")
        pw = st.text_input("Password", type="password", key="debug_pass")
        if st.button("Login", key="debug_login"):
            if user == "admin" and pw == "admin":
                st.session_state.debug_auth = True
            else:
                st.error("Invalid credentials")

autosave()
