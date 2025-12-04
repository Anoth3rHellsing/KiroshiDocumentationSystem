# -*- coding: utf-8 -*-
import io
import time
import random
import re
import traceback
import streamlit as st
from datetime import datetime, timezone
from typing import Mapping
from html import escape

from KiroshiApp.utils import safe_modal, global_widget_key
from KiroshiApp.services.pdf_generator import build_incident_report_pdf
from KiroshiApp.services.data_manager import (
    load_tracked_cases, _case_metadata_snapshot as get_case_snapshot
)
# We need _collect_recent_logs. It was in legacy main app.
# We should implement it in utils or logging service.
# Let's check if it exists in utils. It probably doesn't yet.
# I'll implement it here or in utils.
# For now, let's put it in utils as well or import if I add it there.
# I'll add it to utils in the next step to keep this file clean.
from KiroshiApp.utils import _collect_recent_logs
from KiroshiApp.services.data_manager import build_helpjuice_outline

ERROR_DIALOG_MESSAGES = [
    "Even cybernetic scribes trip sometimes. Give me a second to regroup.",
    "That panel face-planted. Let's grab the logs before it pretends nothing happened.",
    "Something went sideways. Want to tag in Support with a quick report?",
    "Kiroshi hit a weird edge case. Capture it now so the engineers can slay it later.",
]

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
            f"""
            <style>
            .kiroshi-error-card {{
                background: rgba(255, 244, 245, 0.95);
                border-radius: 20px;
                padding: 1.5rem;
                text-align: center;
                box-shadow: 0 18px 40px rgba(255, 0, 76, 0.18);
                border: 1px solid rgba(255, 0, 76, 0.25);
            }}
            .kiroshi-error-card h3 {{
                margin-bottom: 0.5rem;
            }}
            .kiroshi-error-icon {{
                font-size: 48px;
                line-height: 1;
                margin-bottom: 0.75rem;
            }}
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

        section = context.get("section")
        tab_label = context.get("tab")
        bits = [str(bit).strip() for bit in (section, tab_label) if str(bit).strip()]
        if bits:
            st.write("**Context:** " + " · ".join(bits))

        st.text_area(
            "What happened?",
            key="incident_reporter_description",
            placeholder="Share any extra detail you'd like Support to know.",
        )

        screenshot = None
        if allow_screenshot:
            # Screenshot logic requires ScreenshotService which we have in services.
            # But the UI buttons need to be here.
            # For brevity in this refactor, we will enable basic screenshot handling
            # if the service is fully wired.
            # Assuming simplified capture for now or placeholder as per plan.
            st.info("Screenshot capture requires full UI context. (Simplified for this view)")

            # Legacy code had capture buttons. We can re-add them if we import capture functions.
            from KiroshiApp.services.screenshot_service import _screenshot_service

            # Simple capture buttons
            col_cap = st.columns(2)
            if col_cap[0].button("Capture Region", key=global_widget_key("inc_cap_region")):
                 shot, err = _screenshot_service.capture_region("incident_region")
                 if shot: st.session_state.incident_reporter_screenshot = shot
            if col_cap[1].button("Capture Full", key=global_widget_key("inc_cap_full")):
                 shot, err = _screenshot_service.capture_full("incident_full")
                 if shot: st.session_state.incident_reporter_screenshot = shot

            screenshot = st.session_state.get("incident_reporter_screenshot")
            if screenshot:
                st.image(screenshot.data, caption="Evidence", use_container_width=True)

        description = st.session_state.get("incident_reporter_description", "")
        case_index = context.get("case_index")

        # We need a way to get case data. Global D might not be the right one if we crashed elsewhere.
        # But we can try to access st.session_state.case_sessions[case_index]
        # For PDF generation we need snapshot and logs.

        if st.button("Generate PDF", key=global_widget_key("incident_generate_pdf")):
            logs = _collect_recent_logs()
            # case_snapshot helper needed.
            # Let's import get_case_snapshot from data_manager if we put it there?
            # I put it there as _case_metadata_snapshot alias.
            case_snapshot = get_case_snapshot(case_index)

            try:
                pdf_bytes = build_incident_report_pdf(
                    context,
                    logs,
                    description,
                    case_snapshot,
                    screenshot=screenshot if allow_screenshot else None,
                )
                st.session_state.incident_reporter_pdf = pdf_bytes
                st.success("Incident PDF generated.")
            except Exception as exc:
                st.error(f"Unable to build PDF: {exc}")

        pdf_bytes = st.session_state.get("incident_reporter_pdf")
        if isinstance(pdf_bytes, (bytes, bytearray)):
            st.download_button(
                "Download incident PDF",
                data=pdf_bytes,
                file_name="kiroshi-incident-report.pdf",
                mime="application/pdf",
                key=global_widget_key("incident_pdf_download"),
            )

        if st.button("Close", key=global_widget_key("incident_close")):
            st.session_state.reporter_open = False
            st.session_state.incident_reporter_pdf = None
            st.session_state.incident_reporter_screenshot = None
            if st.session_state.get("reporter_source") != "manual":
                st.session_state.render_failure_detected = False
                st.session_state.failure_modal_message = None
            st.session_state.error_modal_open = False
            st.session_state.reporter_source = "auto"
            st.rerun()

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

    # We might not have last_rendered_tab if we crashed early
    if "tab" not in base_context:
        base_context["tab"] = st.session_state.get("last_rendered_tab", "Unknown")
    if "section" not in base_context:
        base_context["section"] = base_context.get("tab", "Unknown section")

    base_context.setdefault("trigger", "auto")
    base_context.setdefault("case_index", st.session_state.get("last_rendered_case"))

    st.session_state.incident_context = base_context
    st.session_state.reporter_open = True
    st.session_state.reporter_allow_screenshot = allow_screenshot
    st.session_state.reporter_source = str(base_context.get("trigger") or "auto")

    # Reset ephemeral reporter state
    st.session_state.incident_reporter_description = ""
    st.session_state.incident_reporter_pdf = None
    st.session_state.incident_reporter_screenshot = None

    st.session_state.error_modal_open = False
