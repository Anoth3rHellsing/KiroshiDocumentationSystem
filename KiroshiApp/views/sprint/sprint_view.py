# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from datetime import datetime
from KiroshiApp.models import CaseData, TrackingData
from KiroshiApp.services.data_manager import load_tracked_cases, save_case_to_database
from KiroshiApp.services.sprint.sprint_manager import (
    load_sprint_state, save_sprint_state, get_tracked_cases_for_sprint,
    generate_sprint_pdf_report, SprintState, SprintTask, ai_prioritize_tasks,
    load_full_case_data, update_case_fields
)
from KiroshiApp.utils import _utc_now_z

def render_sprint_tab() -> None:
    st.title("Sprint & Task Execution")

    # Check if a sprint is active
    current_state = load_sprint_state()
    today_date = _utc_now_z().split("T")[0]

    # Initialize session state if needed or if loading fresh
    if "sprint_state" not in st.session_state:
        st.session_state.sprint_state = current_state

    # 1. Start Day / End Shift
    col1, col2 = st.columns(2)
    with col1:
        if not st.session_state.sprint_state.is_active:
            if st.button("Start Day"):
                _start_day_logic(today_date)
                st.rerun()
        else:
            st.info(f"Sprint Active for {st.session_state.sprint_state.date}")

    with col2:
        if st.session_state.sprint_state.is_active:
            # We put End Shift logic in a separate container/modal flow usually,
            # but here a button triggering PDF download and state close is fine.
            st.write("") # Spacer

    if not st.session_state.sprint_state.is_active:
        st.info("Start your day to see tasks and AI insights.")
        return

    # 2. Progress
    tasks = st.session_state.sprint_state.tasks
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == "Completed"])
    if total_tasks > 0:
        progress = completed_tasks / total_tasks
        st.progress(progress, text=f"Progress: {completed_tasks}/{total_tasks}")

    # 3. Task List (Sprint Board)
    st.subheader("Today's Tasks")

    # End Shift Logic (Placed here to be accessible when active)
    with col2:
        if st.download_button(
            label="📄 End Shift & Export Report",
            data=generate_sprint_pdf_report(st.session_state.sprint_state),
            file_name=f"Sprint_Report_{st.session_state.sprint_state.date}.pdf",
            mime="application/pdf",
            key="end_shift_btn"
        ):
             pass

        if st.button("Close Shift (Reset)"):
             state = st.session_state.sprint_state
             state.is_active = False
             save_sprint_state(state)
             st.session_state.sprint_state = state
             st.success("Shift closed.")
             st.rerun()

    if not tasks:
        st.info("No tasks for today.")
    else:
        # Sort: Escalated first, then by priority
        sorted_tasks = sorted(tasks, key=lambda x: (not x.is_escalated, x.case_id))

        for idx, task in enumerate(sorted_tasks):
            # Dynamic expanader label
            label = f"{'🔥 ' if task.is_escalated else ''}{task.case_id} - {task.company} ({task.status})"
            with st.expander(label, expanded=task.status != "Completed"):
                col_info, col_action = st.columns([3, 1])
                with col_info:
                    st.write(f"**Priority:** {task.priority}")
                    if task.ai_suggestion:
                        st.info(f"🤖 **AI Suggestion:** {task.ai_suggestion}")
                    if task.ai_time_estimate:
                        st.caption(f"Estimated Time: {task.ai_time_estimate}")

                    # Editable fields with sync
                    new_rc = st.text_input("Root Cause", value=task.root_cause, key=f"rc_{task.case_id}")
                    new_sol = st.text_area("Solution", value=task.solution, key=f"sol_{task.case_id}")

                    # Detect changes and sync to DB
                    if new_rc != task.root_cause or new_sol != task.solution:
                        task.root_cause = new_rc
                        task.solution = new_sol
                        save_sprint_state(st.session_state.sprint_state)

                        # Sync to Main Database
                        if task.source_path:
                            update_case_fields(task.source_path, {
                                "root_cause": new_rc,
                                "solution": new_sol
                            })
                            st.toast(f"Saved updates for {task.case_id} to database.")

                with col_action:
                    if task.status != "Completed":
                        if st.button("Mark Complete", key=f"btn_comp_{task.case_id}"):
                            task.status = "Completed"
                            save_sprint_state(st.session_state.sprint_state)
                            st.rerun()
                    else:
                        st.success("Completed")
                        if st.button("Reopen", key=f"btn_reopen_{task.case_id}"):
                            task.status = "Pending"
                            save_sprint_state(st.session_state.sprint_state)
                            st.rerun()

def _start_day_logic(today_date: str):
    """Populates the sprint tasks from tracked cases."""
    tracked_cases = get_tracked_cases_for_sprint()
    tasks = []

    with st.spinner("AI Scrum Master is prioritizing your day..."):
        for case in tracked_cases:
            priority = case.get('priority', 'Normal')
            is_escalated = priority in ["High", "Critical", "Escalation"]
            source_path = case.get('path', '')

            # Load full data to get existing Root Cause / Solution
            full_data = {}
            if source_path:
                full_data = load_full_case_data(source_path)

            root_cause = full_data.get('root_cause', '')
            solution = full_data.get('solution', '')

            tasks.append(SprintTask(
                case_id=case.get('case_id', 'Unknown'),
                company=case.get('company', 'Unknown'),
                priority=priority,
                status='Pending',
                is_escalated=is_escalated,
                source_path=source_path,
                root_cause=root_cause,
                solution=solution
            ))

        # AI Prioritization call
        if tasks:
            tasks = ai_prioritize_tasks(tasks)

    new_state = SprintState(
        date=today_date,
        tasks=tasks,
        is_active=True
    )
    st.session_state.sprint_state = new_state
    save_sprint_state(new_state)
    st.success(f"Day started! {len(tasks)} tasks loaded.")
