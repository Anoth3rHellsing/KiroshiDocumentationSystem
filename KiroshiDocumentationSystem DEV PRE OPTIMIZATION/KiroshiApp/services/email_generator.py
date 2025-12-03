# -*- coding: utf-8 -*-
import json
import re
import os
from typing import Mapping, Iterable
from datetime import datetime
from KiroshiApp.models import CaseData
from KiroshiApp.constants import TODAY_STR, DELL_ESCALATION_FIELD_LABELS, AUTOHOTKEY_SCRIPT_PATH, OPTIONAL_PROGRESS_CATEGORIES
from KiroshiApp.utils import _format_display_value, _format_multiline, _summarize_text
import streamlit as st
import logging

def build_email_intro(d: CaseData) -> str:
    """Standard opening for customer emails."""
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

def dell_escalation_plain_text(d: CaseData) -> str:
    lines = ["Dell Escalation"]
    for field, label in DELL_ESCALATION_FIELD_LABELS:
        raw_value = getattr(d, field, "")
        display = _format_multiline(_format_display_value(raw_value))
        lines.append(f"{label}: {display}")
    return "\n".join(lines)

def build_dell_escalation_email(d: CaseData) -> str:
    """Generate the email body for a Dell escalation."""
    return dell_escalation_plain_text(d)

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

def _autohotkey_escape(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace('"', '""')
    return cleaned.replace("\n", "`n")

def _slugify_hotkey(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())

def build_autohotkey_script(cases: Iterable[CaseData], cat_map) -> str:
    """Generate an AutoHotkey script with hotstrings for each case table."""
    import textwrap
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

def sync_autohotkey_script(script: str) -> str | None:
    """Persist the latest AutoHotkey hotstrings so AutoHotkey can include them live.

    Returns the path if the script could be written, otherwise None.
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
        return str(AUTOHOTKEY_SCRIPT_PATH)
    except OSError as exc:
        logging.warning("Failed to sync AutoHotkey script to %s: %s", AUTOHOTKEY_SCRIPT_PATH, exc)
        return None

def build_kiroshi_tone_directive() -> str:
    """Return the active voice directive for Kiroshi's responses."""
    if st.session_state.get("kiroshi_sarcasm_mode", False):
        return "Reply with a dry, witty, and sarcastic tone while staying professional and helpful."
    return "Use clear, professional language that is easy to follow."

def build_case_data_block(d: CaseData) -> str:
    """Return a newline separated list with every tracked case field."""
    from dataclasses import fields
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
