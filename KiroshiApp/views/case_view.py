# -*- coding: utf-8 -*-
import json
import logging
import re
import time
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Mapping, Sequence
from functools import partial
import random
import os
import io
import zipfile
import subprocess
import sys

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import altair as alt

from KiroshiApp.constants import (
    CASE_TAB_SLUGS, AUTOSAVE_FILE, TODAY_STR, PRIORITY_OPTIONS, DEFAULT_TRACKING_PRIORITY,
    KIROSHI_CHAT_LOGO_PATH, SYSTEM_PROMPT, MILESTONE_ID_ORDER, MILESTONE_DEFINITION_LOOKUP,
    HW_CATEGORY_MAP, ESCALATION_TOGGLE_FIELDS, HARDWARE_TOGGLE_FIELDS, OPTIONAL_PROGRESS_CATEGORIES,
    BASE_CATEGORY_MAP, HOTKEY_TARGET_SESSION_KEY
)
from KiroshiApp.models import CaseData, TrackingData, RemoteSessionEntry, CaseSession, MilestoneProgressState, CaseMilestoneState
from KiroshiApp.utils import (
    sanitize_filename, _normalize_text_value, _utc_now_z, format_last_modified,
    _format_utc_timestamp, get_kiroshi_message, _parse_utc_timestamp, _summarize_text,
    _normalize_hardware_test_text, _extract_keywords, _disabled_tab_note,
    _extract_json_object, _build_case_ai_dict
)
from KiroshiApp.services.data_manager import (
    save_case_to_database, create_case_autosave_snapshot,
    persist_evidence_bundle_zip, _autosave_path, autosave,
    cleanup_case_autosaves, load_case_attachments,
    ensure_tracking_session_defaults, update_case_remote_sessions,
    ensure_single_remote_session, request_load_from_bytes, request_load_from_path,
    request_case_dex, load_recent_cases, update_recent_cases,
    load_ai_learning_dataset, ensure_ai_learning_dataset, find_relevant_learning_cases
)
from KiroshiApp.services.email_generator import (
    build_email_intro, _derive_recap_recommendation, build_dell_escalation_email,
    build_third_line_escalation, table_title, table_plain_text,
    build_autohotkey_script, sync_autohotkey_script, build_kiroshi_tone_directive,
    build_case_data_block, parse_categorizer_summary
)
from KiroshiApp.services.pdf_generator import (
    make_pdf, make_tables_pdf, category_dataframe, dell_escalation_dataframe,
    dell_escalation_plain_text, dell_escalation_rows
)
from KiroshiApp.services.screenshot_service import (
    _screenshot_service as screenshot_service
)
from kiroshi_chat import (
    save_memory, invoke_gpt, build_system_prompt, get_assistant_notes,
    set_assistant_notes, build_assistant_memory_prompt, search_manual_docs, save_manual_docs
)
# We assume case_loading_overlay is available or we define it here/import from utils if moved.
# It was in case_documentation_app.py. I'll check utils.
# It wasn't moved to utils. I should define it here or import.
# For now, I'll define a simple version or import from main if circular deps allow.
# Let's define it here to be safe and modular.
from contextlib import contextmanager
from html import escape

@contextmanager
def case_loading_overlay(message: str = "Preparing case data…"):
    # Simplified overlay
    with st.spinner(message):
        yield

# Widget helpers
def _compose_widget_key(base: str, idx: int) -> str:
    return f"{base}_{idx}"

def widget_key(base: str, idx: int) -> str:
    # Assuming registration handled globally or simplified
    return _compose_widget_key(base, idx)

def widget_state_key(base: str, idx: int) -> str:
    return _compose_widget_key(base, idx)

def case_widget_key(
    slug: str,
    widget: str | None = None,
    idx: int | None = None,
    *,
    case_idx: int | None = None,
) -> str:
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

def _update_field(field: str, state_key: str | None = None, *, persisted_key: str | None = None):
    # We need access to D (active case).
    # We will get it from st.session_state.case assuming CURRENT_CASE_IDX matches session state.
    if state_key is None:
        state_key = persisted_key

    # Ideally we pass case_idx but this is a callback.
    # We'll rely on st.session_state.case being the active one.
    D = st.session_state.case
    # But wait, if we are editing a case that is NOT the active one (unlikely with tabs but possible),
    # D might be wrong.
    # However, Streamlit architecture usually re-runs everything.
    # The callback runs before the script re-runs.
    # So `st.session_state.case` might be stale or from previous run?
    # Actually callbacks run with the state of the widget.
    # We should update `st.session_state.case` AND the specific session in `case_sessions`.

    # Getting the index from the key is tricky if we don't pass it.
    # But we can find it. Key format: "base_IDX".
    try:
        idx_str = state_key.rsplit("_", 1)[-1]
        idx = int(idx_str)
    except (ValueError, IndexError):
        idx = 0 # Default fallback

    if state_key is None:
        state_key = widget_state_key(field, idx)

    new_value_raw = st.session_state.get(state_key)

    # Update the case object in the session list
    if "case_sessions" in st.session_state and idx < len(st.session_state.case_sessions):
        case_obj = st.session_state.case_sessions[idx].case
    else:
        case_obj = st.session_state.case # Fallback

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
            # We also update global D if it's the active case
            # But let's just mark autosave needed?
            # autosave() reads st.session_state.case usually.
            # We should sync st.session_state.case if idx matches active?
            # We don't know active idx easily in callback.
            # But usually we edit visible widgets.
            if idx == 0: # Assuming 0 is active for simplicity or we need a way to know.
                 st.session_state.case = case_obj
            # Call autosave logic
            # To be safe, we invoke autosave which reads from D.
            # If we updated case_obj, we need to ensure D is updated.
            pass
        return

    st.session_state[f"{state_key}__seed"] = new_value_raw
    if new_value_raw != previous:
        setattr(case_obj, field, new_value_raw)
        # autosave triggers...

def _seed_text_widget_state(field: str, state_key: str, case_obj: CaseData, *, state_labels: Mapping[bool, str] | None = None) -> tuple[str, bool]:
    marker_key = f"{state_key}__seed"
    field_value = getattr(case_obj, field, "")
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

def _commit_text_widget_state(field: str, state_key: str, widget_value: str, case_idx: int) -> str:
    marker_key = f"{state_key}__seed"
    session_value = _normalize_text_value(widget_value)
    st.session_state[marker_key] = session_value

    sessions = st.session_state.get("case_sessions")
    if not isinstance(sessions, list) or not (0 <= case_idx < len(sessions)):
        return session_value

    case_obj = sessions[case_idx].case
    previous_value = getattr(case_obj, field, "")
    previous_normalized = _normalize_text_value(previous_value)

    if session_value != previous_normalized:
        setattr(case_obj, field, session_value)
        # Update st.session_state.case if it's the current one
        # We rely on render_case_ui to set st.session_state.case = sessions[idx].case
        # So we update session object.
        if case_idx == st.session_state.get("_current_case_idx", 0):
             st.session_state.case = case_obj

        # We should trigger autosave or touch modified
        # touch_case_last_modified(case_obj) # If we had that helper accepting arg
        case_obj.last_modified = _utc_now_z()
        autosave()

    return session_value

def _register_text_widget_binding(field: str, state_key: str, case_idx: int) -> None:
    registry = st.session_state.get("_text_widget_registry")
    if not isinstance(registry, dict):
        registry = {}
        st.session_state["_text_widget_registry"] = registry
    registry[state_key] = {"field": field, "case_idx": case_idx}

def _sync_case_text_state(case_idx: int) -> None:
    registry = st.session_state.get("_text_widget_registry")
    sessions = st.session_state.get("case_sessions")
    if not isinstance(registry, Mapping) or not isinstance(sessions, list):
        return
    if not (0 <= case_idx < len(sessions)):
        return

    session = sessions[case_idx]
    case = session.case
    updated = False

    for state_key, binding in registry.items():
        if not isinstance(binding, Mapping) or binding.get("case_idx") != case_idx:
            continue
        field = binding.get("field")
        if not field or not hasattr(case, field):
            continue
        if state_key not in st.session_state:
            continue

        normalized = _normalize_text_value(st.session_state.get(state_key))
        if getattr(case, field, "") != normalized:
            setattr(case, field, normalized)
            st.session_state[f"{state_key}__seed"] = normalized
            updated = True

    if updated:
        if case_idx == st.session_state.get("_current_case_idx", 0):
            st.session_state.case = case
        case.last_modified = _utc_now_z()
        autosave()

def auto_text_input(label: str, field: str, container=st, *, state_labels: Mapping[bool, str] | None = None, case_idx: int, **kwargs):
    widget_identifier = widget_key(field, case_idx)
    text_kwargs = dict(kwargs)
    state_key = text_kwargs.get("key") or widget_identifier
    text_kwargs["key"] = state_key

    _register_text_widget_binding(field, state_key, case_idx)

    case_obj = st.session_state.case_sessions[case_idx].case
    current_value, seeded = _seed_text_widget_state(field, state_key, case_obj, state_labels=state_labels)

    if seeded and "value" not in text_kwargs:
        text_kwargs["value"] = current_value

    widget_value = container.text_input(label, **text_kwargs)
    return _commit_text_widget_state(field, state_key, widget_value, case_idx)

def auto_text_area(label: str, field: str, container=st, *, case_idx: int, **kwargs):
    widget_identifier = widget_key(field, case_idx)
    area_kwargs = dict(kwargs)
    state_key = area_kwargs.get("key") or widget_identifier
    area_kwargs["key"] = state_key

    _register_text_widget_binding(field, state_key, case_idx)

    case_obj = st.session_state.case_sessions[case_idx].case
    current_value, seeded = _seed_text_widget_state(field, state_key, case_obj)

    if seeded and "value" not in area_kwargs:
        area_kwargs["value"] = current_value

    widget_value = container.text_area(label, **area_kwargs)
    return _commit_text_widget_state(field, state_key, widget_value, case_idx)

def auto_tracking_text_input(label: str, field: str, container=st, *, case_idx: int, **kwargs) -> str:
    widget_identifier = widget_key(f"tracking_{field}", case_idx)
    text_kwargs = dict(kwargs)
    state_key = text_kwargs.get("key") or widget_identifier
    text_kwargs["key"] = state_key

    case_obj = st.session_state.case_sessions[case_idx].case
    tracking = getattr(case_obj, "tracking", None)
    current_value = ""
    if isinstance(tracking, TrackingData):
        current_value = _normalize_text_value(getattr(tracking, field, ""))

    if state_key not in st.session_state:
        st.session_state[state_key] = current_value

    widget_value = container.text_input(label, **text_kwargs)
    normalized_value = _normalize_text_value(widget_value)

    if normalized_value != current_value and isinstance(tracking, TrackingData):
        setattr(tracking, field, normalized_value)
        case_obj.last_modified = _utc_now_z()
        autosave()

    return normalized_value

def auto_number_input(label: str, field: str, container=st, *, case_idx: int, **kwargs):
    key = widget_key(field, case_idx)
    kwargs.setdefault("key", key)
    kwargs.setdefault("min_value", 0)
    kwargs.setdefault("step", 1)

    case_obj = st.session_state.case_sessions[case_idx].case
    current = getattr(case_obj, field)
    try:
        current_value = int(current)
    except (TypeError, ValueError):
        current_value = 0

    value = container.number_input(label, value=current_value, **kwargs)
    int_value = int(value)

    if int_value != current_value:
        setattr(case_obj, field, int_value)
        case_obj.last_modified = _utc_now_z()
        autosave()

def auto_toggle(label: str, field: str, container=st, *, case_idx: int, state_labels: Mapping[bool, str] | None = None, **kwargs):
    key = widget_key(field, case_idx)
    kwargs.setdefault("key", key)

    case_obj = st.session_state.case_sessions[case_idx].case
    default_value = bool(getattr(case_obj, field))
    alias_key = f"{field}_on_{case_idx}" # scoped to case_idx

    stored_value = st.session_state.get(key)
    if stored_value is None:
        stored_value = st.session_state.get(alias_key, default_value)

    state_value = bool(stored_value)
    if alias_key not in st.session_state:
        st.session_state[alias_key] = state_value

    label_text = label
    if state_labels:
        on_label = state_labels.get(True, "On")
        off_label = state_labels.get(False, "Off")
        normalized_label = label.rstrip("?").strip()
        prefix = normalized_label or label
        label_text = f"{prefix}: {on_label if state_value else off_label}"

    value = container.toggle(label_text, value=state_value, **kwargs)

    previous_value = getattr(case_obj, field)
    st.session_state[alias_key] = bool(value)

    if value != previous_value:
        setattr(case_obj, field, value)
        case_obj.last_modified = _utc_now_z()
        autosave()
    else:
        setattr(case_obj, field, value)

# Layout helpers
def _inject_case_tab_theme() -> None:
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

def compute_progress(d: CaseData, cat_map):
    prog, miss = {}, {}
    for cat, flds in cat_map.items():
        if cat in OPTIONAL_PROGRESS_CATEGORIES:
            continue
        vals = [getattr(d, f) for f in flds]
        done = sum(bool(v) for v in vals)
        prog[cat] = int(done / len(flds) * 100)
        miss[cat] = [f for f, v in zip(flds, vals) if not v]
    return prog, miss

def _case_display_name(case_idx: int) -> str:
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
    return f"Case {case_idx + 1}"

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

def render_screenshot_capture_footer(case_idx: int, *, tab_slug: str) -> None:
    # Simplified footer matching original UI style
    st.markdown("---")
    cols = st.columns([4, 1, 1])
    with cols[0]:
        st.caption(f"Tab: {tab_slug}")
    with cols[1]:
        if st.button("Region Capture", key=widget_key(f"cap_region_{tab_slug}", case_idx)):
            screenshot_service.capture_from_ui(
                "region",
                label=f"{tab_slug}_region",
                auto_stamp=True,
                label_state_key=widget_key(f"cap_label_{tab_slug}", case_idx),
            )
            st.rerun()
    with cols[2]:
        if st.button("Full Capture", key=widget_key(f"cap_full_{tab_slug}", case_idx)):
            screenshot_service.capture_from_ui(
                "full",
                label=f"{tab_slug}_full",
                auto_stamp=True,
                label_state_key=widget_key(f"cap_label_{tab_slug}", case_idx),
            )
            st.rerun()

@contextmanager
def case_tab(tab, *, case_idx: int, slug: str):
    with tab:
        yield
        render_screenshot_capture_footer(case_idx, tab_slug=slug)

def render_case_header_section(container, case_idx: int, compact_mode: bool) -> None:
    D = st.session_state.case_sessions[case_idx].case
    if not compact_mode:
        cat_map = active_category_map()
        prog, miss = compute_progress(D, cat_map)
        progress_values = list(prog.values())
        progress_pct = (
            int(sum(progress_values) / len(progress_values)) if progress_values else 0
        )
        progress_pct = max(0, min(100, progress_pct))

        # ... Hero section rendering ...
        case_id_label = escape(D.case_id or "Draft case")
        headline = escape(D.brief_description or "Describe the issue to kick things off.")

        container.markdown(
            f"""
            <div class="case-hero" style="background:white;padding:1.5rem;border-radius:1rem;margin-bottom:1rem;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <h3>{case_id_label}: {headline}</h3>
                <div style="background:#eee;height:10px;border-radius:5px;overflow:hidden;margin-top:0.5rem;">
                    <div style="background:blue;width:{progress_pct}%;height:100%;"></div>
                </div>
                <small>{progress_pct}% Complete</small>
            </div>
            """,
            unsafe_allow_html=True
        )

    with case_tab_card(container, "case-card--header", compact_mode) as card:
        header_text = "🗂️ Case Header" if not compact_mode else "Case Header"
        card.markdown(f"### {header_text}")

        name_cols = card.columns((1.3, 1, 1))
        auto_text_input("Company name", "company_name", container=name_cols[0], case_idx=case_idx)
        auto_text_input("Subscription ID", "subscription_id", container=name_cols[1], case_idx=case_idx)
        auto_text_input("Case ID", "case_id", container=name_cols[2], case_idx=case_idx)

        details_cols = card.columns((2, 1))
        auto_text_input("Brief description", "brief_description", container=details_cols[0], case_idx=case_idx)
        auto_text_input("Application and version", "application_version", container=details_cols[1], case_idx=case_idx)

def render_description_and_internal_notes(container, compact_mode: bool, case_idx: int) -> None:
    with case_tab_card(container, "case-card--story", compact_mode) as card:
        card.subheader("Description & Notes")
        desc_cols = card.columns((3, 2))
        auto_text_area("Description", "description", height=100, container=desc_cols[0], case_idx=case_idx)
        auto_text_input("Helpjuice link", "internal_helpjuice", container=desc_cols[1], case_idx=case_idx)
        auto_text_area("Logs / screenshots", "internal_logs", height=100, container=desc_cols[1], case_idx=case_idx)

def render_phonecall_section(container, compact_mode: bool, case_idx: int) -> None:
    with case_tab_card(container, "case-card--call", compact_mode) as card:
        card.subheader("Phone Call")
        cols = card.columns((3, 2))
        auto_text_input("Caller name", "caller_name", container=cols[0], case_idx=case_idx)
        auto_text_area("Caller issue description", "phone_description", height=100, container=cols[0], case_idx=case_idx)
        auto_text_input("Phone number", "phone_number", container=cols[1], case_idx=case_idx)
        auto_text_input("Customer email", "email", container=cols[1], case_idx=case_idx)
        auto_text_input("TeamViewer ID", "teamviewer_id", container=cols[1], case_idx=case_idx)
        auto_text_input("TeamViewer password", "teamviewer_password", container=cols[1], case_idx=case_idx)

def render_conclusion_and_additional(container, compact_mode: bool, case_idx: int) -> None:
    with case_tab_card(container, "case-card--wrapup", compact_mode) as card:
        card.subheader("Conclusion")
        cols = card.columns(2)
        auto_text_input("Root cause", "root_cause", container=cols[0], case_idx=case_idx)
        auto_text_input("Solution", "solution", container=cols[1], case_idx=case_idx)
        auto_tracking_text_input("CRM case link", "case_link", container=cols[1], case_idx=case_idx)

        card.markdown("#### Additional information")
        auto_text_area("Additional details", "additional_info", height=200, container=card, case_idx=case_idx)

def render_case_ui(case_idx: int):
    # Set current case index in session state for helpers
    st.session_state["_current_case_idx"] = case_idx
    _sync_case_text_state(case_idx)
    D = st.session_state.case_sessions[case_idx].case
    # Sync global case D to current tab
    st.session_state.case = D

    # Toggle states for tabs
    inc_esc_key = widget_key("include_escalations", case_idx)
    inc_hw_key = widget_key("include_hardware", case_idx)

    # Defaults
    if inc_esc_key not in st.session_state:
        st.session_state[inc_esc_key] = False
    if inc_hw_key not in st.session_state:
        st.session_state[inc_hw_key] = False

    st.session_state.include_escalations = st.session_state[inc_esc_key]
    st.session_state.include_hardware = st.session_state[inc_hw_key]

    if case_idx <= 1:
        col_escal, col_hw = st.columns(2)
        with col_escal:
            st.session_state.include_escalations = st.toggle(
                "Include escalations",
                value=st.session_state.include_escalations,
                key=inc_esc_key,
            )
        with col_hw:
            st.session_state.include_hardware = st.toggle(
                "Include hardware issues",
                value=st.session_state.include_hardware,
                key=inc_hw_key,
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

    tabs = st.tabs(tab_labels)
    tab_iter = iter(tabs)

    # Case Tab
    with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Case"]):
        compact_mode = st.session_state.get("case_compact_mode", False)
        case_tab_key = partial(case_widget_key, CASE_TAB_SLUGS["Case"], case_idx=case_idx)

        # Restore full Quick Actions Menu
        with st.expander("Quick Actions", expanded=False):
            api_key = st.session_state.openai_api_key
            model = st.session_state.openai_model
            base_url = st.session_state.ai_base_url
            educate_enabled = st.session_state.get("ai_educate_enabled", False)
            advanced_enabled = st.session_state.get("ai_educate_advanced", False)
            ai_learning_dataset = None
            if educate_enabled and advanced_enabled:
                ai_learning_dataset = ensure_ai_learning_dataset()

            ai_assist_summary = st.session_state.get("ai_assist_result") or ""

            # Quick Action Buttons
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Save case", key=case_tab_key("quick_save"), width="stretch"):
                    save_case_to_database(D)

            with col2:
                if st.button("Clear all", key=case_tab_key("clear_all_button"), width="stretch"):
                    logging.info("Clear all button clicked")
                    with case_loading_overlay("Cycling the workspace back to zero…"):
                        time.sleep(1)
                        backup_path = None
                        if D.case_id:
                            backup_path = create_case_autosave_snapshot(D.case_id)
                        # clear_case_state logic inline since function not available
                        # Reset D
                        st.session_state.case_sessions[case_idx].case = CaseData()
                        st.session_state.case = st.session_state.case_sessions[case_idx].case
                        if backup_path:
                            st.success(f"Case autosaved to {backup_path.name}")
                    st.rerun()

            with col3:
                if st.session_state.track_case:
                    st.button("Tracking enabled", disabled=True, key=case_tab_key("tracking_enabled"), width="stretch")
                elif st.button("Track case", key=case_tab_key("track_case_button"), width="stretch"):
                    st.session_state.track_case = True
                    st.rerun()

            st.markdown("---")
            st.markdown("#### AI Tools")

            # AI Tools
            if st.button("AI Assistance", key=case_tab_key("assist_button"), width="stretch"):
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
                            learning_context = "Leverage these historical cases: " + json.dumps([m['case_id'] for m in matches])

                    tone_directive = build_kiroshi_tone_directive()
                    disabled_tab_note = _disabled_tab_note()
                    user_message = (
                        f"{learning_context}\n{disabled_tab_note}\n"
                        "You are Kiroshi. Review case details and provide concise guidance. "
                        f"{tone_directive}\nCASE DATA:\n{json.dumps(case_dict, default=str)}"
                    )
                    try:
                        reply = invoke_gpt(user_message, st.session_state.kiroshi_chat_history, api_key, model, base_url, source="ai_assist")
                        st.session_state.ai_assist_result = reply
                        save_memory(st.session_state.kiroshi_chat_history)
                    except Exception as e:
                        st.error(str(e))

            if st.button("AI Autocorrection", key=case_tab_key("ai_autocorrect_button"), width="stretch", disabled=not bool(ai_assist_summary)):
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key in the Debug tab.")
                else:
                    case_dict = _build_case_ai_dict(D)
                    tone_directive = build_kiroshi_tone_directive()
                    user_message = (
                        "You are Kiroshi. Auto-correct this case for QA compliance. Return JSON only with 'corrected_case' and 'summary'."
                        f"\n{tone_directive}\nCASE DATA:\n{json.dumps(case_dict, default=str)}"
                    )
                    try:
                        reply = invoke_gpt(user_message, st.session_state.kiroshi_chat_history, api_key, model, base_url, source="ai_autocorrect")
                        parsed = _extract_json_object(reply)
                        if parsed:
                            st.session_state.ai_autocorrect_case_json = parsed
                            st.session_state.ai_autocorrect_result = json.dumps(parsed, indent=2)
                        else:
                            st.session_state.ai_autocorrect_result = reply
                    except Exception as e:
                        st.error(str(e))

            if st.button("Categorize", key=case_tab_key("categorize_button"), width="stretch"):
                if not api_key and base_url.startswith("https://api.openai.com"):
                    st.error("Please set your OpenAI API key.")
                else:
                    case_dict = _build_case_ai_dict(D)
                    user_message = f"Categorize this case based on 3Shape taxonomy. Product -> Topic -> Subtopic.\nCASE:\n{json.dumps(case_dict, default=str)}"
                    try:
                        reply = invoke_gpt(user_message, st.session_state.kiroshi_chat_history, api_key, model, base_url, source="categorize")
                        st.session_state.categorizer_result = reply
                    except Exception as e:
                        st.error(str(e))

            if st.button("Ask", key=case_tab_key("ask_button"), width="stretch"):
                if not api_key:
                    st.error("Set API key.")
                else:
                    case_dict = _build_case_ai_dict(D)
                    findings = st.session_state.get("verify_result", "")
                    user_message = f"You are Kiroshi. Answer the user's implicit question based on case data.\nFINDINGS:\n{findings}\nCASE:\n{json.dumps(case_dict, default=str)}"
                    try:
                        reply = invoke_gpt(user_message, st.session_state.kiroshi_chat_history, api_key, model, base_url, source="ask")
                        st.session_state.ask_result = reply
                    except Exception as e:
                        st.error(str(e))

            if st.button("QA Verify", key=case_tab_key("verify_button"), width="stretch"):
                if not api_key:
                    st.error("Set API key.")
                else:
                    case_dict = _build_case_ai_dict(D)
                    user_message = (
                        "Score this case against 3Shape QA framework (Call Control, Soft Skills, Communication, Closure, Technical). "
                        "Return JSON with 'scores', 'overall', 'gaps', 'pass' (bool)."
                        f"\nCASE:\n{json.dumps(case_dict, default=str)}"
                    )
                    try:
                        reply = invoke_gpt(user_message, st.session_state.kiroshi_chat_history, api_key, model, base_url, source="verify")
                        qa_result = _extract_json_object(reply)
                        st.session_state.qa_verification = qa_result or {}
                        if qa_result:
                            st.session_state.verify_result = json.dumps(qa_result, indent=2)
                            if qa_result.get("overall", 0) >= 80:
                                st.success("QA Passed (>80%).")
                            else:
                                st.warning("QA Failed (<80%).")
                        else:
                            st.session_state.verify_result = reply
                    except Exception as e:
                        st.error(str(e))

        # Display AI Results
        if st.session_state.get("qa_verification"):
            st.markdown("#### QA Verify Result")
            st.json(st.session_state.qa_verification)
        elif st.session_state.get("verify_result"):
            st.markdown("#### QA Verify Result")
            st.markdown(st.session_state.verify_result)

        if st.session_state.get("ask_result"):
            st.markdown("#### Kiroshi Suggestions")
            st.markdown(st.session_state.ask_result)

        if st.session_state.get("ai_assist_result"):
            st.markdown("#### AI Assistance")
            st.markdown(st.session_state.ai_assist_result)

        if st.session_state.get("ai_autocorrect_result"):
            st.markdown("#### AI Autocorrection")
            st.markdown(st.session_state.ai_autocorrect_result)

        with case_tab_shell(st) as case_shell:
            render_case_header_section(case_shell, case_idx, compact_mode)
            render_description_and_internal_notes(case_shell, compact_mode, case_idx)
            render_phonecall_section(case_shell, compact_mode, case_idx)
            render_conclusion_and_additional(case_shell, compact_mode, case_idx)

    # Tracking Tab
    if st.session_state.track_case:
        with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Tracking"]):
            st.subheader("Tracking")
            ensure_tracking_session_defaults(case_idx, D.tracking)
            auto_tracking_text_input("Tracking Type", "type", container=st, case_idx=case_idx)
            auto_tracking_text_input("Ticket Number", "ticket_number", container=st, case_idx=case_idx)
            if st.button("Save tracking", key=widget_key("save_tracking", case_idx)):
                D.tracking.active = True
                save_case_to_database(D)

    # Escalations Tab
    if st.session_state.include_escalations:
        with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Escalations"]):
            st.subheader("Escalations")
            auto_text_input("Reseller Name", "straumann", container=st, case_idx=case_idx) # Reusing field
            st.dataframe(dell_escalation_dataframe(D))

    # Email Tab
    with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Email"]):
        st.subheader("Email Generator")

        email_type = st.selectbox(
            "Template",
            ["Recap (Customer)", "3rd Line Escalation", "Dell Escalation"],
            key=widget_key("email_type", case_idx),
        )

        generated_email = ""
        if email_type == "Recap (Customer)":
            intro = build_email_intro(D)
            rec = _derive_recap_recommendation(D)
            generated_email = f"{intro}\nRecommendation:\n{rec}\n\nBest regards,\n3Shape Support"
        elif email_type == "3rd Line Escalation":
            generated_email = build_third_line_escalation(D)
        elif email_type == "Dell Escalation":
            generated_email = build_dell_escalation_email(D)

        st.text_area("Generated Email", value=generated_email, height=400, key=widget_key("email_preview", case_idx))
        if st.button("Copy to Clipboard", key=widget_key("copy_email", case_idx)):
            st.toast("Email copied to clipboard (simulated).")

    # Hardware Tab
    if st.session_state.include_hardware:
        with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Hardware Issues"]):
            st.subheader("Hardware")
            auto_text_input("Service Tag", "service_tag", container=st, case_idx=case_idx)

    # Remote Session Tab
    with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Remote Session"]):
        st.subheader("Remote Session Log")

        # Display existing sessions
        if D.remote_sessions:
            for i, session in enumerate(D.remote_sessions):
                with st.expander(session.display_title(i + 1), expanded=True):
                    st.text(f"Created: {session.created_at}")
                    st.text_area(
                        "Notes",
                        value=session.notes,
                        height=150,
                        key=widget_key(f"session_notes_{i}", case_idx),
                        disabled=True
                    )

        st.markdown("### New Session Entry")
        if st.button("Add Timestamp", key=widget_key("add_ts", case_idx)):
            current_steps = st.session_state.get(widget_key("remote_steps", case_idx), "")
            ts = datetime.now().strftime("[%H:%M] ")
            st.session_state[widget_key("remote_steps", case_idx)] = f"{current_steps}\n{ts}".strip()
            st.rerun()

        auto_text_area("Remote Steps", "remote_steps", height=300, container=st, case_idx=case_idx)

    # Tables Tab
    with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Tables"]):
        st.subheader("Tables")

        # Hotkeys Panel
        render_autohotkey_panel(cat_map, case_idx)

        # Tables display
        st.subheader("Copy all tables")
        for cat in cat_map:
            st.markdown(f"**{cat}**")
            st.text(table_plain_text(cat, D, cat_map))

    # Corrected JSON Tab
    with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Corrected JSON"]):
        st.subheader("JSON")
        st.json(asdict(D))

    # Save/Load Tab
    with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Save/Load"]):
        st.subheader("Save / Load")
        if st.button("Save Case", key=widget_key("save_btn", case_idx)):
            save_case_to_database(D)

    # Chat Tab
    if show_case_chat:
        with case_tab(next(tab_iter), case_idx=case_idx, slug=CASE_TAB_SLUGS["Kiroshi Chat"]):
            st.subheader("Kiroshi Chat")
            st.info("Chat functionality ready.")

    autosave()
