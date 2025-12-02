# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import math
import os
import re
import time
import uuid
import threading
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from typing import Mapping, Iterable, Sequence, Any, Callable
from dataclasses import asdict, fields, is_dataclass

import streamlit as st
import pandas as pd
import altair as alt
import requests

from KiroshiApp.constants import (
    PRIORITY_OPTIONS, DEFAULT_TRACKING_PRIORITY,
    PRIORITY_RANK, PRIORITY_BADGES, TRACKING_STATUS_OPTIONS,
    DELL_STATUS_OPTIONS, FEDEX_STATUS_OPTIONS,
    DATABASE_DIR, TRACKED_CASES_DIR,
    TODAY_STR, VERSION, ALTAIR_CHART_KWARGS
)
from KiroshiApp.services.data_manager import (
    load_tracked_cases, recent_tracked_files, update_tracked_priority,
    update_tracked_status, untrack_case, list_saved_cases, update_recent_cases,
    save_case_to_database, request_case_dex, load_case_from_path,
    load_case_from_bytes, create_case_autosave_snapshot,
    _apply_tracked_priority_update, _reset_tracked_cases_cache, update_tracked_case_file
)
from KiroshiApp.utils import (
    format_last_modified, parse_iso_datetime, _format_timedelta_compact,
    format_tracking_date, _time_str_to_time, _time_to_string,
    _normalize_wellness_settings, _calculate_next_wellness_event,
    _calculate_lunch_midpoint, normalize_priority,
    _extract_keywords, _summarize_text
)
from KiroshiApp.models import UpdateCheckResult, CaseData

# Helper to generate widget keys, assuming it's available or we redefine it locally.
# In the original app, it was defined. We should probably move widget key helpers to utils or similar.
# For now, let's redefine locally if needed or assume we can import if we move it to utils.
# Since I didn't move it to utils yet, I will redefine basic version or check if I can import from main app (circular dep risk).
# Better to have it in utils. But let's look at `utils.py` again. It doesn't have `widget_key`.
# I will define a local helper for widget keys to avoid import mess for now.

def _register_widget_key(key: str) -> str:
    """Track widget keys during debug sessions and detect duplicates."""
    if not st.session_state.get("debug_mode"):
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
        # In a real module we might raise or log.
        # raising WidgetKeyCollisionError(key) requires the exception class.
        pass

    registry.add(key)
    return key

def global_widget_key(base: str) -> str:
    key = f"global_{base}"
    return _register_widget_key(key)

# We need ALTAIR_CHART_KWARGS. It's in case_documentation_app.py but not constants.
# It depends on streamlit version.
try:
    import inspect
    _altair_signature = inspect.signature(st.altair_chart)
    ALTAIR_CHART_KWARGS = (
        {"width": "stretch"}
        if "width" in _altair_signature.parameters
        else {}
    )
except (TypeError, ValueError, ImportError):
    ALTAIR_CHART_KWARGS = {}

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
    from html import escape
    safe_url = (url or "").strip()
    if not safe_url:
        return
    st.markdown(
        f"<a class='crm-link' href='{escape(safe_url)}' target='_blank' rel='noopener noreferrer'>Open in CRM</a>",
        unsafe_allow_html=True,
    )

def render_case_metadata(label: str, value: str | None) -> None:
    from html import escape
    display_value = value if value not in (None, "") else "—"
    st.markdown(
        f"<div class='case-meta'>"
        f"<span class='case-meta__label'>{label}</span>"
        f"<span class='case-meta__value'>{escape(str(display_value))}</span>"
        "</div>",
        unsafe_allow_html=True,
    )

# Since request_load_from_path is not in data_manager (it's in main logic because it affects UI state),
# we need a way to callback to main app or handle it.
# BUT, `request_load_from_path` basically calls `load_case_from_path` (which we moved to data_manager)
# AND updates session state `pending_load` or `dashboard_load_notice`.
# So we can reimplement `request_load_from_path` logic here using `data_manager` functions
# OR we pass a callback.
# For simplicity in this view, I'll assume we can manipulate session state directly which acts as the "Controller".

def _request_load_from_path_ui(path: str, prefer_new_tab: bool = False):
    # Logic similar to case_documentation_app.py
    # We need access to check if current case has unsaved sections.
    # That requires access to current case object in session state.
    # Let's import has_unsaved_sections from main? No circular.
    # I'll re-implement a simple check or just assume safe loading for now to decouple.
    # Actually `load_case_from_path` in data_manager loads it into session_state.
    # But the UI logic about "unsaved changes" is view logic.

    # We will trigger the load directly for now.
    # If we need the "unsaved check", we should ideally duplicate that small logic or move it to utils.
    from KiroshiApp.services.data_manager import load_case_from_path

    # We need to know CURRENT_CASE_IDX to know where to load.
    # In dashboard view, we usually load into a new tab or overwrite current.
    # Let's assume we want to load into a new tab if requested.

    # This part is tricky because it involves "allocating a tab".
    # I'll emit a signal via session_state that the main app loop picks up?
    # Or just manipulate `case_sessions`.

    # Let's simplify: Dashboard "Load" usually loads into the *active* context or new tab.
    # We will define a helper that mimics the main app behavior but operates on state.

    if "case_sessions" not in st.session_state:
        st.session_state.case_sessions = []

    # We can't easily allocate a tab here without logic duplication.
    # I will set a flag in session state that the main app's loop will respect?
    # No, that's complex.
    # I will operate on `st.session_state.case` and `case_sessions`.

    # For now, let's just call load_case_from_path which updates `st.session_state.case`.
    # And we update `case_sessions[CURRENT_CASE_IDX]` if we knew it.
    # But we don't know `CURRENT_CASE_IDX` here easily unless we pass it or read it.
    # `CURRENT_CASE_IDX` is a global in main app.

    # Strategy: Render functions shouldn't handle complex loading logic that affects global layout.
    # They should probably set a state `st.session_state._action_load_case = path` and let main loop handle it?
    # Or we replicate the logic.

    # Replicating logic seems best for "modularity" if we accept `st.session_state` as the bus.

    pass

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

    # Import update functions from data manager to use in callbacks
    from KiroshiApp.services.data_manager import update_tracked_priority, update_tracked_status, untrack_case, load_case_from_path

    # Helper to load
    def _trigger_load(path):
        # We'll use a hack to request load in main app if possible, or just load to current state
        # For this refactor, let's assume we can load into session state directly.
        # But `load_case_from_path` in data_manager handles session state update!
        # The only missing piece is updating `case_sessions` list index.
        # We can implement a simplified version here.
        # load_case_from_path(path) is available.
        # But we need to handle "New Tab" vs "Current Tab".
        # Let's set a flag `pending_open_path`?
        st.session_state["_pending_load_path"] = path
        st.session_state["_pending_load_new_tab"] = True

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

        # ... (Same logic for auto-escalation check as in main app) ...
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
                    # This update function is in data_manager now, imported as _apply_tracked_priority_update
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

        # Priority badges need PRIORITY_BADGES from constants
        badge = PRIORITY_BADGES.get(priority_value, "🔘")

        summary = " ".join(
            part
            for part in [
                badge,
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

            # We need to pass case_id and is_legacy to update functions
            cid = case.get("case_id")
            legacy = case.get("is_legacy", False)
            path = case["path"]

            # Wrappers for callbacks to match data_manager signature
            # We use st.session_state[key] to get value in data_manager functions usually,
            # but `update_tracked_priority` in data_manager reads from session state.
            # So we just pass the key.

            with controls[0]:
                if case.get("is_legacy"):
                    st.caption("Priority editing is unavailable for legacy JSON files.")
                else:
                    st.selectbox(
                        "Priority",
                        PRIORITY_OPTIONS,
                        key=priority_key,
                        on_change=update_tracked_priority,
                        kwargs={"path": path, "key": priority_key, "case_id": cid, "is_legacy": legacy}
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
                            on_change=update_tracked_status,
                            kwargs={"path": path, "key": status_key, "case_id": cid, "is_legacy": legacy}
                        )
                    else:
                        st.text_input(
                            "Status",
                            key=status_key,
                            on_change=update_tracked_status,
                            kwargs={"path": path, "key": status_key, "case_id": cid, "is_legacy": legacy}
                        )

            action_cols = st.columns(2)
            with action_cols[0]:
                if st.button("Load", key=f"dash_load_{unique_suffix}"):
                    _trigger_load(case["path"])
                    st.rerun()
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
                    st.rerun()

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
            st.session_state["_pending_load_path"] = case["path"]
            st.session_state["_pending_load_new_tab"] = True
            st.rerun()

def render_saved_cases_page() -> None:
    """Render the full Saved Cases management page."""
    st.markdown("<div class='dashboard-title'>Saved Cases Index</div>", unsafe_allow_html=True)
    saved_cases = list_saved_cases()
    if not saved_cases:
        st.info("No saved cases found.")
        return

    st.caption("Complete history of locally stored cases.")

    # Simple table layout
    weights = [1.2, 1.5, 1.0, 1.2, 0.8, 0.8]
    header_cols = st.columns(weights)
    header_cols[0].markdown("**Case ID**")
    header_cols[1].markdown("**Company**")
    header_cols[2].markdown("**Version**")
    header_cols[3].markdown("**Last Modified**")
    header_cols[4].markdown("**Action**")

    for case in saved_cases:
        row_cols = st.columns(weights)
        row_cols[0].write(case["case_id"])

        company_display = case["company"] or "—"
        if case.get("tags"):
            company_display += f" ({', '.join(case['tags'])})"
        row_cols[1].write(company_display)

        row_cols[2].write(case.get("kiroshi_version") or "Unknown")
        row_cols[3].write(case["updated"].strftime("%Y-%m-%d %H:%M"))

        if row_cols[4].button("Load", key=f"page_load_{Path(case['path']).stem}"):
            st.session_state["_pending_load_path"] = case["path"]
            st.session_state["_pending_load_new_tab"] = True
            st.rerun()

def render_dashboard() -> None:
    """Render the high-level dashboard overview tab."""
    from KiroshiApp.constants import DEFAULT_WELLNESS_SETTINGS, WELLNESS_TIPS, WELLNESS_EVENT_METADATA

    st.markdown(
        "<div class='dashboard-title'>Dashboard</div>",
        unsafe_allow_html=True,
    )

    # Wellness reminder logic
    # We need _refresh_wellness_reminder_state which is in main app or we move it.
    # It updates session state. I will import it from a new location if moved, or replicate if simple.
    # It seems tied to `st.session_state` heavily.
    # For now, let's assume `_refresh_wellness_reminder_state` is available via `KiroshiApp.utils`?
    # I didn't move it to utils. It was in main.
    # I should have moved wellness logic to utils or services.
    # I'll check `KiroshiApp/utils.py`. `_calculate_next_wellness_event` and `_normalize_wellness_settings` are there.
    # But `_refresh_wellness_reminder_state` is in main.
    # I will move `_refresh_wellness_reminder_state` to `KiroshiApp/services/wellness_service.py` later or implement here.

    # ... Wellness implementation skipped for brevity in this specific file update,
    # but I should implement `_refresh_wellness_reminder_state` here using utils.

    # Actually, let's just do it here.
    import random

    # Re-implementing _refresh_wellness_reminder_state logic using utils
    def _refresh_wellness_reminder_state_local(*, now: datetime | None = None) -> dict[str, object] | None:
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

    reminder_state = _refresh_wellness_reminder_state_local()
    if reminder_state and isinstance(reminder_state.get("event_dt"), datetime):
        from html import escape
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
                <div class="wellness-banner__tip">💡 <span>{escape(tip)}</span></div>
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
