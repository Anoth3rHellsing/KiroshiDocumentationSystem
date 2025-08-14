# -*- coding: utf-8 -*-
"""
Kiroshi V0.1.4 – IT Case Documentation Helper
Run:
    streamlit run case_documentation_app.py
"""

import io
import json
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime

import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import requests
import urllib3

# Some corporate networks perform SSL interception with a self-signed
# certificate, which breaks standard certificate validation.  Disable
# warnings and certificate verification for outbound requests so the
# ChatGPT API can still be reached.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

VERSION = "0.1.4"
TODAY_STR = datetime.now().strftime("%d%m%Y")

# ─────────────────────────── CONFIG ────────────────────────────
st.set_page_config(page_title=f"Kiroshi V{VERSION}", layout="wide")

ASCII_LOGO_RAW = r"""
       /\
      /  \
     /\ \ \
    /\ \ \ \
   /\ \ \ \/\
  / /\ \ \/ /\
 / / /\  / / /\
/ / /  \/ / /  \
\  / / /\  / / /
 \/ / /  \/ / /
  \/ /\ \ \/ /
   \/\ \ \ \/
    \ \ \ \/
     \ \ \/
      \  /
       \/
"""

st.text(ASCII_LOGO_RAW)

# ────────────────────── SESSION STATE ────────────────────────
def _init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

_init_state("survey_link", "https://3shape.eu.surveymonkey.com/r/3ShapeSupportSatisfactionSurvey")
_init_state("case", {})
_init_state("uploads", [])
_init_state("scratch", "")
_init_state("email_type", "Recap (Customer)")
_init_state("email_extra", {})
_init_state("include_hw", False)
_init_state("debug_auth", False)

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
    elems = []
    for cat in cat_map:
        elems.append(Paragraph(cat, styles["Heading4"]))
        data = [["Field", "Value"]] + category_dataframe(cat, d, cat_map).values.tolist()
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
st.session_state.include_hw = st.checkbox(
    "Include hardware issue fields", st.session_state.include_hw
)
cat_map = active_category_map()

tab_labels = ["Case", "Email"]
if st.session_state.include_hw:
    tab_labels.append("Hardware Issues")
tab_labels += ["Notes", "Tables", "API", "Debug"]
tabs = st.tabs(tab_labels)
if st.session_state.include_hw:
    tab_case, tab_email, tab_hw, tab_notes, tab_tables, tab_api, tab_debug = tabs
else:
    tab_case, tab_email, tab_notes, tab_tables, tab_api, tab_debug = tabs

# ================== CASE TAB =================
with tab_case:
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
        D.company_name = st.text_input("Company name", D.company_name)
        D.subscription_id = st.text_input("Subscription ID", D.subscription_id)
        D.brief_description = st.text_input("Brief description", D.brief_description)
        D.case_id = st.text_input("Case ID", D.case_id)
        st.subheader("Description (What / When / Where)")
        D.description = st.text_area("Description", D.description, height=68)
        st.subheader("Phone-call notes")
        D.caller_name = st.text_input("Caller name", D.caller_name)
        D.phone_description = st.text_area(
            "Caller issue description", D.phone_description, height=68
        )
        c1, c2 = st.columns(2)
        D.dongle_number = c1.text_input("Dongle number", D.dongle_number)
        D.phone_number = c2.text_input("Phone number", D.phone_number)
        D.teamviewer_id = c1.text_input("TeamViewer ID", D.teamviewer_id)
        D.teamviewer_password = c2.text_input(
            "TeamViewer password", D.teamviewer_password
        )
        D.email = st.text_input("Email", D.email)
        st.subheader("Internal notes")
        D.internal_helpjuice = st.text_input("Helpjuice link", D.internal_helpjuice)
        D.internal_logs = st.text_area("Logs / screenshots", D.internal_logs, height=68)
        st.subheader("Remote session – steps")
        D.remote_steps = st.text_area("One step per line", D.remote_steps, height=68)
        st.subheader("Conclusion")
        D.root_cause = st.text_input("Root cause", D.root_cause)
        D.solution = st.text_input("Solution", D.solution)
        st.session_state.survey_link = st.text_input(
            "Customer satisfaction survey URL", st.session_state.survey_link
        )
        st.subheader("Additional information")
        av_check = st.checkbox(
            "Customer uses antivirus?", value=D.antivirus.startswith("Customer uses")
        )
        if av_check:
            av_name = st.text_input(
                "What antivirus?", D.antivirus.replace("Customer uses antivirus: ", "")
            )
            D.antivirus = f"Customer uses antivirus: {av_name}" if av_name else "Customer uses antivirus:"
        else:
            D.antivirus = "Customer does not use antivirus."
        fw_check = st.checkbox(
            "Firewalls are turned on?", value=D.firewalls_enabled.startswith("Firewalls are turned on")
        )
        D.firewalls_enabled = (
            "Firewalls are turned on." if fw_check else "Firewalls are not turned on."
        )
        upd_check = st.checkbox(
            "Any update was made?", value=not D.update_history.startswith("No updates") and bool(D.update_history)
        )
        if upd_check:
            upd_text = st.text_input(
                "From what version to what version?",
                D.update_history.replace("An update was made: ", ""),
            )
            D.update_history = (
                f"An update was made: {upd_text}" if upd_text else "An update was made:"
            )
        else:
            D.update_history = "No updates were made."
        rel_check = st.checkbox(
            "Is there any related case?", value=D.related_case_id.startswith("There is a related case")
        )
        if rel_check:
            rel_id = st.text_input(
                "Related case number", D.related_case_id.replace("There is a related case: ", "")
            )
            D.related_case_id = (
                f"There is a related case: {rel_id}" if rel_id else "There is a related case:"
            )
        else:
            D.related_case_id = "There are no related cases."
        cause_check = st.checkbox(
            "Any possible cause why it happened?",
            value=D.possible_cause.startswith("Possible cause"),
        )
        if cause_check:
            cause_text = st.text_input(
                "Why?", D.possible_cause.replace("Possible cause: ", "")
            )
            D.possible_cause = (
                f"Possible cause: {cause_text}" if cause_text else "Possible cause:"
            )
        else:
            D.possible_cause = "There is no known possible cause."
        perf_check = st.checkbox(
            "Performance related issue?",
            value=D.performance_issue.startswith("It is a performance related issue"),
        )
        if perf_check:
            perf_text = st.text_input(
                "Why?", D.performance_issue.replace("It is a performance related issue: ", "")
            )
            D.performance_issue = (
                f"It is a performance related issue: {perf_text}" if perf_text else "It is a performance related issue:"
            )
        else:
            D.performance_issue = "It is not a performance related issue."
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

# ================== EMAIL TAB =================
with tab_email:
    st.subheader("Email Prompt Generator")
    email_type = st.selectbox(
        "Select email template",
        [
            "Recap (Customer)",
            "AX Coordinators",
            "Broken Scanner",
            "Broken Tip",
            "Escalation 2nd line",
        ],
        index=[
            "Recap (Customer)",
            "AX Coordinators",
            "Broken Scanner",
            "Broken Tip",
            "Escalation 2nd line",
        ].index(st.session_state.email_type),
    )
    st.session_state.email_type = email_type
    ext = st.session_state.email_extra

    prompt = ""
    if email_type == "Recap (Customer)":
        greeting = f"Dear {(D.caller_name or 'Customer')}{(' / ' + D.company_name + ' team') if D.company_name else ' team'},"
        steps_summary = "\n".join(D.remote_steps.splitlines()) or "—"
        prompt = f"""You are a friendly IT‑support agent. Draft an engaging, upbeat email (≤180 words) that recaps the case and encourages the customer to complete a short satisfaction survey to help improve our service.
The email must start with: {greeting}

Include: Case ID, root cause, a brief 1‑3 bullet summary of the steps taken, and the final solution.
Use a warm tone, thank the customer for their time, invite further questions, and end with a clear call‑to‑action to the survey. Return only the email body.

DATA:
Case ID: {D.case_id}
Root cause: {D.root_cause}
Steps taken:
{steps_summary}
Solution: {D.solution}
Survey link: {st.session_state.survey_link}"""

    elif email_type == "AX Coordinators":
        st.markdown("#### Additional details")
        ext["request_issue"] = st.text_area(
            "Request / Issue", ext.get("request_issue", "")
        )
        ext["contact_name"] = st.text_input(
            "Contact name", ext.get("contact_name", "")
        )
        ext["office_ph"] = st.text_input(
            "Office phone", ext.get("office_ph", "")
        )
        ext["direct_ph"] = st.text_input(
            "Direct phone", ext.get("direct_ph", "")
        )
        ext["best_time"] = st.text_input(
            "Best call‑back time + timezone", ext.get("best_time", "")
        )
        ext["patterson"] = st.text_input(
            "Patterson legacy #", ext.get("patterson", "N/A")
        )
        ext["straumann"] = st.text_input(
            "Straumann ticket #", ext.get("straumann", "N/A")
        )

        prompt = f"""Compose a brief internal e‑mail for AX coordinators summarising the details below.
Use bullet points where helpful. Return only the e‑mail body.

Caller name: {D.caller_name}
Request / Issue: {ext['request_issue']}
Dongle: {D.dongle_number}
Contact: {ext['contact_name']}
Office PH: {ext['office_ph']}
Direct PH: {ext['direct_ph']}
Best call‑back: {ext['best_time']}
Case ID: {D.case_id} | SID: {D.subscription_id}
Patterson legacy#: {ext['patterson']}
Straumann ticket#: {ext['straumann']}
"""

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

    elif email_type == "Escalation 2nd line":
        st.markdown("#### Contact details for escalation")
        ext["esc_name"] = st.text_input(
            "Name", ext.get("esc_name", ""), key="esc_name_escalation"
        )
        ext["esc_ph"] = st.text_input(
            "Phone", ext.get("esc_ph", ""), key="esc_ph_escalation"
        )
        ext["esc_email"] = st.text_input(
            "Email", ext.get("esc_email", ""), key="esc_email_escalation"
        )

        prompt = (
            "Write a short note informing the customer that the case is being escalated to second‑line support to continue verification.\n"
            "Begin with that exact sentence, then list the following contact details and the Case ID.\n"
            f"Case ID: {D.case_id}\n"
            f"Name: {ext['esc_name']}\n"
            f"Phone: {ext['esc_ph']}\n"
            f"Email: {ext['esc_email']}\n"
            "Close politely. Return only the e‑mail body."
        )

    st.session_state.email_extra = ext
    st.text_area("ChatGPT prompt (copy & paste)", prompt, height=300)

# ================== HARDWARE ISSUES TAB =================
if st.session_state.include_hw:
    with tab_hw:
        st.subheader("PC Hardware Issue")
        col_pc1, col_pc2 = st.columns(2)
        D.service_tag = col_pc1.text_input("Service Tag", D.service_tag)
        D.pc_model = col_pc2.text_input("PC Model", D.pc_model)
        D.windows_version = col_pc1.text_input("Windows version", D.windows_version)
        D.bios_version = col_pc2.text_input("BIOS version", D.bios_version)
        D.graphics_card = col_pc1.text_input("Graphics Card", D.graphics_card)
        D.processor = col_pc2.text_input("Processor", D.processor)
        D.warranty = st.text_input("Warranty", D.warranty)
        st.dataframe(
            category_dataframe("PC HARDWARE", D, HW_CATEGORY_MAP), use_container_width=True
        )

        st.markdown("---")
        st.subheader("Scanner Hardware Issue")
        D.scanner_sn = st.text_input("Scanner S/N", D.scanner_sn)
        D.base_sn = st.text_input("Base S/N", D.base_sn)
        D.trios_module_version = st.text_input(
            "TRIOS MODULE Version", D.trios_module_version
        )
        st.dataframe(
            category_dataframe("SCANNER HARDWARE", D, HW_CATEGORY_MAP), use_container_width=True
        )

# ================== NOTES TAB =================
with tab_notes:
    st.subheader("Scratchpad")
    st.session_state.scratch = st.text_area(
        "Temporary notes", st.session_state.scratch, height=400
    )

# ================== TABLES TAB =================
with tab_tables:
    st.subheader("Copy all tables")
    for cat in cat_map:
        st.markdown(f"**{table_title(cat)}**")
        st.dataframe(category_dataframe(cat, D, cat_map), use_container_width=True)

# ================== FILE UPLOADS & EXPORTS =================
st.markdown("---")
st.subheader("Exports & attachments")
new_files = st.file_uploader(
    "Upload screenshots / logs / videos", accept_multiple_files=True
)
if new_files:
    st.session_state.uploads.extend(new_files)
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

# ================== API TAB =================
with tab_api:
    st.subheader("ChatGPT API Integration")
    api_key = st.text_input("OpenAI API Key", type="password", key="openai_api_key")
    model = st.selectbox("Model", ["gpt-3.5-turbo", "gpt-4"], key="openai_model")
    prompt_for_api = st.session_state.get("last_prompt", "")

    # Optionally, let user edit the prompt before sending
    prompt_for_api = st.text_area(
        "Prompt to send", prompt_for_api, height=200, key="api_prompt_area"
    )

    include_helpjuice = st.checkbox(
        "Helpjuice tutorial", key="api_helpjuice"
    )
    include_restart = st.checkbox(
        "Restart the computer", key="api_restart"
    )
    include_scan_time = st.checkbox(
        "Scan time warning", key="api_scan_time"
    )

    if st.button("Convert to Email (ChatGPT API)"):
        if not api_key:
            st.error("Please enter your OpenAI API key.")
        elif not prompt_for_api.strip():
            st.error("Prompt is empty.")
        else:
            with st.spinner("Contacting ChatGPT..."):
                try:
                    augmented_prompt = prompt_for_api
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
                                {
                                    "role": "system",
                                    "content": "You are a helpful assistant.",
                                },
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
                        st.text_area("Generated Email", email_text, height=300)
                    else:
                        st.error(
                            f"API Error: {response.status_code}\n{response.text}"
                        )
                except Exception as e:  # pragma: no cover - just in case
                    st.error(f"Request failed: {e}")

    # Save the last prompt from the Email tab for convenience
    if "prompt" in locals() and prompt:
        st.session_state["last_prompt"] = prompt

# ================== DEBUG TAB =================
with tab_debug:
    if st.session_state.debug_auth:
        st.subheader("Debug")
        st.write(tabs)
        st.write(st.session_state)
    else:
        user = st.text_input("Username", key="debug_user")
        pw = st.text_input("Password", type="password", key="debug_pass")
        if st.button("Login", key="debug_login"):
            if user == "admin" and pw == "admin":
                st.session_state.debug_auth = True
            else:
                st.error("Invalid credentials")

