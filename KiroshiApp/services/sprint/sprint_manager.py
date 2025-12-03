# -*- coding: utf-8 -*-
import json
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Mapping, Any
from dataclasses import dataclass, field, asdict
import streamlit as st

from KiroshiApp.constants import DATABASE_DIR, AUTOSAVE_DIR, DEFAULT_AI_BASE_URL
from KiroshiApp.services.data_manager import load_tracked_cases, list_saved_cases, update_tracked_case_file, _coerce_case_mapping
from KiroshiApp.utils import _utc_now_z
from kiroshi_chat import query_kiroshi  # Reuse existing AI function

SPRINT_STATE_FILE = DATABASE_DIR / "sprint_state.json"

@dataclass
class SprintTask:
    case_id: str
    company: str
    priority: str
    status: str  # "Pending", "Completed"
    ai_suggestion: str = ""
    ai_time_estimate: str = ""
    root_cause: str = ""
    solution: str = ""
    notes: str = ""
    is_escalated: bool = False
    source_path: str = "" # Path to the original case file

@dataclass
class SprintState:
    date: str
    tasks: list[SprintTask] = field(default_factory=list)
    daily_summary: str = ""
    is_active: bool = False

def load_sprint_state() -> SprintState:
    if not SPRINT_STATE_FILE.exists():
        return SprintState(date=_utc_now_z().split("T")[0])

    try:
        data = json.loads(SPRINT_STATE_FILE.read_text(encoding="utf-8"))
        # Check if date is today, if not, we can either clear it or return it inactive.
        # But if the user clicks "Start Day", it will overwrite.
        tasks = []
        for t in data.get("tasks", []):
            tasks.append(SprintTask(**t))
        return SprintState(
            date=data.get("date", ""),
            tasks=tasks,
            daily_summary=data.get("daily_summary", ""),
            is_active=data.get("is_active", False)
        )
    except Exception as e:
        logging.error(f"Failed to load sprint state: {e}")
        return SprintState(date=_utc_now_z().split("T")[0])

def save_sprint_state(state: SprintState) -> None:
    try:
        data = asdict(state)
        SPRINT_STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logging.error(f"Failed to save sprint state: {e}")

def get_tracked_cases_for_sprint() -> list[dict]:
    """Fetches tracked cases to populate the sprint."""
    tracked = load_tracked_cases()
    # Filter out closed cases
    return [c for c in tracked if c.get("status") not in ("Closed", "Resolved")]

def ai_prioritize_tasks(tasks: list[SprintTask]) -> list[SprintTask]:
    """Uses AI to generate suggestions and estimates for tasks."""
    if not tasks:
        return []

    # 1. Prepare data for prompt
    tasks_summary = []
    for t in tasks:
        tasks_summary.append(f"- Case: {t.case_id}, Priority: {t.priority}, Escalated: {t.is_escalated}")

    prompt = (
        "You are acting as a Scrum Master for an IT Support team. "
        "Review the following active cases and provide a JSON response with a plan for each case. "
        "The response must be a valid JSON list of objects, where each object has: "
        "'case_id', 'suggestion' (a brief next step), 'time_estimate' (e.g. '15 mins'). "
        "Prioritize escalated cases. "
        "\n\nCases:\n" + "\n".join(tasks_summary)
    )

    try:
        # Get AI settings from session state
        api_key = st.session_state.get("openai_api_key", "")
        model = st.session_state.get("openai_model", "gpt-4o")
        base_url = st.session_state.get("ai_base_url", DEFAULT_AI_BASE_URL)
        provider = st.session_state.get("ai_provider", "OpenAI")

        response_text = query_kiroshi(
            user_message=prompt,
            history=[],
            api_key=api_key,
            model=model,
            base_url=base_url,
            provider=provider
        )

        # Parse JSON from response
        # Clean markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        plan_data = json.loads(response_text)

        # Update tasks
        plan_map = {item['case_id']: item for item in plan_data if 'case_id' in item}

        for task in tasks:
            if task.case_id in plan_map:
                info = plan_map[task.case_id]
                task.ai_suggestion = info.get('suggestion', task.ai_suggestion)
                task.ai_time_estimate = info.get('time_estimate', task.ai_time_estimate)

    except Exception as e:
        logging.error(f"AI prioritization failed: {e}")
        # Fallback values are already set in view

    return tasks

def generate_sprint_pdf_report(state: SprintState) -> bytes:
    from KiroshiApp.services.pdf_generator import _load_pdf_styles, _build_pdf_with_ghost_text
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles, _, bold_font, _ = _load_pdf_styles()

    story = []
    story.append(Paragraph(f"Sprint Report - {state.date}", styles["Title"]))
    story.append(Spacer(1, 12))

    # We need to include Completed tasks, or all? User said "factura de lo hecho" (bill of what was done).
    # Typically implies completed work. But let's include all touched tasks for completeness.
    # The requirement explicitly said: "una tabla que muestre: 1. Numero de caso 2. Root Cause y solution"

    data = [["Case Number", "Root Cause", "Solution"]]
    completed_count = 0
    for task in state.tasks:
        # Only include if there is meaningful info or status is completed
        if task.status == "Completed" or task.root_cause or task.solution:
            completed_count += 1
            data.append([
                 task.case_id,
                 Paragraph(task.root_cause or "N/A", styles["BodyText"]),
                 Paragraph(task.solution or "N/A", styles["BodyText"])
             ])

    if len(data) > 1:
        table = Table(data, colWidths=[100, 200, 200])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), bold_font),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No completed tasks recorded for this shift.", styles["BodyText"]))

    doc.build(story)
    buf.seek(0)
    return buf.read()

def load_full_case_data(path_str: str) -> dict:
    """Helper to load full case dictionary from disk."""
    try:
        path = Path(path_str)
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        data = _coerce_case_mapping(payload)
        return dict(data) if data else {}
    except Exception as e:
        logging.error(f"Failed to load case data from {path_str}: {e}")
        return {}

def update_case_fields(path_str: str, updates: dict) -> None:
    """Updates specific fields in a saved case file."""
    if not path_str:
        return

    try:
        update_tracked_case_file(path_str, **updates)
    except Exception as e:
        logging.error(f"Failed to update case fields for {path_str}: {e}")
