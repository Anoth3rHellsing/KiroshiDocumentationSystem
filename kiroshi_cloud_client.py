"""Streamlit client for managing the encrypted Kiroshi Cloud service."""

from __future__ import annotations

import ipaddress
from datetime import datetime
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from kiroshi_cloud_sync import (
    AgentBlockedError,
    AuthenticationError,
    CloudError,
    CloudSession,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    overlay_guidance,
    add_device,
    dataset_counts_to_frame,
    generate_device_token,
    load_cloud_config,
    load_local_ai_dataset,
    open_cloud_session,
    save_local_ai_dataset,
    summarize_dataset,
    update_device_status,
    record_device_seen,
    remove_device,
)


st.set_page_config(page_title="Kiroshi Control Tower", layout="wide", page_icon="🛰️")


def _initialize_state() -> None:
    defaults: dict[str, Any] = {
        "cloud_session": None,
        "cloud_devices": {},
        "cloud_agent_store": None,
        "cloud_agent_summaries": {},
        "cloud_overall_summary": None,
        "cloud_username": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_initialize_state()


def _refresh_devices() -> None:
    session: CloudSession = st.session_state.cloud_session
    if not session:
        return
    st.session_state.cloud_devices = session.load_devices()


def _refresh_agent_store() -> None:
    session: CloudSession = st.session_state.cloud_session
    if not session:
        return
    store = session.load_all_agent_datasets()
    st.session_state.cloud_agent_store = store
    agents = store.get("agents", {}) if isinstance(store, dict) else {}
    agent_summaries: dict[str, dict[str, Any]] = {}
    combined_cases: list[dict[str, Any]] = []

    for agent_id, record in agents.items():
        dataset = record.get("dataset") if isinstance(record, dict) else None
        if isinstance(dataset, dict):
            agent_summaries[agent_id] = summarize_dataset(dataset)
            cases = dataset.get("cases")
            if isinstance(cases, list):
                combined_cases.extend([case for case in cases if isinstance(case, dict)])
        else:
            agent_summaries[agent_id] = summarize_dataset(None)

    combined_dataset = {"cases": combined_cases} if combined_cases else None
    st.session_state.cloud_agent_summaries = agent_summaries
    st.session_state.cloud_overall_summary = summarize_dataset(combined_dataset)


def _disconnect() -> None:
    for key in (
        "cloud_session",
        "cloud_devices",
        "cloud_agent_store",
        "cloud_agent_summaries",
        "cloud_overall_summary",
    ):
        st.session_state[key] = None


def _format_timestamp(raw: str | None) -> str:
    if not raw:
        return "—"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(raw)


def _validate_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    return True


def _render_login() -> None:
    st.title("Kiroshi Control Tower")
    st.caption(
        "Coordinate encrypted datasets, device access, and quality analytics for every field agent "
        "from a single command interface."
    )

    config = load_cloud_config()
    if config.get("uses_default_credentials"):
        st.warning(
            "The cloud instance is still using the default credentials. Update them in the "
            "Security tab after logging in."
        )

    with st.form("cloud-login"):
        username = st.text_input("Cloud username", value=config.get("username", DEFAULT_USERNAME))
        password = st.text_input("Cloud password", type="password")
        submitted = st.form_submit_button("Connect to Kiroshi Cloud", type="primary")

    if not submitted:
        st.info(
            "Default credentials: **%s / %s**.\n\nChange them immediately after the first login."
            % (DEFAULT_USERNAME, DEFAULT_PASSWORD)
        )
        return

    try:
        session = open_cloud_session(username, password)
    except AuthenticationError as exc:
        st.error(str(exc))
        return
    except CloudError as exc:
        st.error(f"Failed to open Kiroshi Cloud: {exc}")
        return

    st.session_state.cloud_session = session
    st.session_state.cloud_username = username
    _refresh_devices()
    _refresh_agent_store()
    st.success("Connected to Kiroshi Cloud. Use the tabs above to manage devices and data.")


def _render_overview() -> None:
    agent_store: dict[str, Any] = st.session_state.cloud_agent_store or {"agents": {}}
    overall_summary: dict[str, Any] = st.session_state.cloud_overall_summary or summarize_dataset(None)
    agent_summaries: dict[str, dict[str, Any]] = st.session_state.cloud_agent_summaries or {}
    devices_payload: dict[str, Any] = st.session_state.cloud_devices or {"devices": []}
    devices = devices_payload.get("devices", [])

    total_devices = len(devices)
    allowed_devices = sum(1 for item in devices if item.get("allowed"))
    blocked_devices = sum(1 for item in devices if item.get("blocked"))

    agents = agent_store.get("agents", {}) if isinstance(agent_store, dict) else {}
    total_agents = len(agents)
    blocked_agents = sum(1 for record in agents.values() if isinstance(record, dict) and record.get("blocked"))
    active_agents = total_agents - blocked_agents

    st.subheader("Operational snapshot")
    metric_row = st.columns(4)
    metric_row[0].metric("Agents reporting", total_agents)
    metric_row[1].metric("Active agents", max(active_agents, 0))
    metric_row[2].metric("Blocked agents", blocked_agents)
    metric_row[3].metric("Managed devices", total_devices)

    second_row = st.columns(3)
    second_row[0].metric("Allowed devices", allowed_devices)
    second_row[1].metric("Blocked devices", blocked_devices)
    last_saved = None
    if isinstance(agents, dict) and agents:
        timestamps = [record.get("saved_at") for record in agents.values() if isinstance(record, dict) and record.get("saved_at")]
        if timestamps:
            timestamps.sort(reverse=True)
            last_saved = timestamps[0]
    second_row[2].metric("Latest dataset", _format_timestamp(last_saved))

    st.caption(
        "High-level metrics based on encrypted agent datasets. Use the Agent Databases tab for granular control."
    )

    cases_total = overall_summary.get("total_cases", 0)
    unique_devices = overall_summary.get("unique_devices", 0)
    summary_row = st.columns(2)
    summary_row[0].metric("Cases analysed", cases_total)
    summary_row[1].metric("Unique devices", unique_devices)

    agent_rows: list[dict[str, Any]] = []
    for agent_id, record in agents.items():
        summary = agent_summaries.get(agent_id, summarize_dataset(record.get("dataset")))
        agent_rows.append(
            {
                "Agent": agent_id,
                "Cases": summary.get("total_cases", 0),
                "Unique devices": summary.get("unique_devices", 0),
                "Blocked": "Yes" if record.get("blocked") else "No",
                "Last upload": _format_timestamp(record.get("saved_at")),
            }
        )

    if agent_rows:
        agent_df = pd.DataFrame(agent_rows)
        st.dataframe(agent_df, use_container_width=True, hide_index=True)

        chart_cols = st.columns(2)
        chart_cols[0].altair_chart(
            alt.Chart(agent_df).mark_bar().encode(
                x=alt.X("Cases", title="Cases"),
                y=alt.Y("Agent", sort="-x"),
                color=alt.Color("Blocked", legend=None),
            ),
            use_container_width=True,
        )
        root_frame = dataset_counts_to_frame(overall_summary.get("root_cause_counts", []), label="Root cause")
        if not root_frame.empty:
            chart_cols[1].altair_chart(
                alt.Chart(root_frame).mark_bar().encode(
                    x=alt.X("cases", title="Cases"),
                    y=alt.Y("Root cause", sort="-x"),
                    color=alt.Color("Root cause", legend=None),
                ),
                use_container_width=True,
            )
        else:
            chart_cols[1].info("Upload datasets to view root cause trends.")
    else:
        st.info("No agent datasets have been uploaded yet. Use the Agent Databases tab to ingest data.")


def _render_connections() -> None:
    session: CloudSession = st.session_state.cloud_session
    payload: dict[str, Any] = st.session_state.cloud_devices or {"devices": []}
    devices = payload.get("devices", [])

    st.subheader("Register a new device")
    with st.form("add-device"):
        name = st.text_input("Device name", help="Use an easily recognisable label, e.g. \'HQ Front Desk\'.")
        ip = st.text_input("Device IP address", help="The private or overlay IP used to reach the host.")
        notes = st.text_area("Notes", help="Optional context such as location or operating system.")
        submitted = st.form_submit_button("Add device", type="primary")

    if submitted:
        if not ip or not _validate_ip(ip):
            st.error("Enter a valid IPv4/IPv6 address before adding the device.")
        else:
            try:
                record = add_device(session, name=name, ip=ip, notes=notes)
            except CloudError as exc:
                st.error(f"Failed to add device: {exc}")
            else:
                st.success(f"Registered {record['name']} ({record['device_id']}).")
                _refresh_devices()
                devices = st.session_state.cloud_devices.get("devices", [])

    st.divider()
    st.subheader("Managed devices")
    if not devices:
        st.info("No devices are registered yet. Add one above to begin managing connections.")
        return

    for record in devices:
        device_id = record.get("device_id")
        header = f"{record.get('name')} — {record.get('ip')}"
        with st.expander(header, expanded=False):
            st.markdown(
                f"**Device ID:** `{device_id}`  \
**Status:** {record.get('status','unknown').title()}  \
**Last seen:** {_format_timestamp(record.get('last_seen'))}"
            )
            if record.get("notes"):
                st.caption(record.get("notes"))

            action_cols = st.columns([1, 1, 1, 1])
            if action_cols[0].button("Allow", key=f"allow-{device_id}"):
                try:
                    update_device_status(session, device_id, allowed=True, blocked=False)
                    st.success("Device allowed.")
                except CloudError as exc:
                    st.error(str(exc))
                _refresh_devices()
            if action_cols[1].button("Block", key=f"block-{device_id}"):
                try:
                    update_device_status(session, device_id, allowed=False, blocked=True)
                    st.warning("Device blocked.")
                except CloudError as exc:
                    st.error(str(exc))
                _refresh_devices()
            if action_cols[2].button("Mark online", key=f"seen-{device_id}"):
                try:
                    record_device_seen(session, device_id)
                    st.success("Connection heartbeat stored.")
                except CloudError as exc:
                    st.error(str(exc))
                _refresh_devices()
            if action_cols[3].button("Remove", key=f"remove-{device_id}"):
                try:
                    remove_device(session, device_id)
                    st.info("Device removed from the roster.")
                except CloudError as exc:
                    st.error(str(exc))
                _refresh_devices()

            token_col, paste_col = st.columns([2, 1])
            if token_col.button("Generate connection token", key=f"token-{device_id}"):
                token = generate_device_token(session, device_id)
                st.session_state[f"token_{device_id}"] = token
            token = st.session_state.get(f"token_{device_id}")
            if token:
                st.code(token, language="text")
                paste_col.download_button(
                    "Download token",
                    token.encode("utf-8"),
                    file_name=f"kiroshi_cloud_token_{device_id}.txt",
                )


def _render_agent_databases() -> None:
    session: CloudSession = st.session_state.cloud_session
    agent_store: dict[str, Any] = st.session_state.cloud_agent_store or {"agents": {}}
    agents = agent_store.get("agents", {}) if isinstance(agent_store, dict) else {}

    st.subheader("Agent data vault")
    st.caption("Review and orchestrate encrypted datasets per agent. Actions requiring justification are logged for audit trails.")

    refresh_col, _ = st.columns([1, 3])
    if refresh_col.button("Refresh from cloud", key="refresh-agent-store"):
        _refresh_agent_store()
        agents = (st.session_state.cloud_agent_store or {}).get("agents", {})
        st.success("Reloaded datasets for all agents.")

    agent_ids = sorted(agents.keys())
    if len(agent_ids) >= 2:
        st.markdown("### Merge datasets")
        with st.form("merge-agents"):
            target_agent = st.selectbox("Target agent", agent_ids, key="merge-target")
            source_options = [agent for agent in agent_ids if agent != target_agent]
            selected_sources = st.multiselect(
                "Source agents", source_options, key="merge-sources", help="Selected sources will be cleared after merging into the target namespace."
            )
            merge_note = st.text_area(
                "Justification", key="merge-justification", help="Explain why the datasets are being combined."
            )
            submitted = st.form_submit_button("Merge datasets", type="primary")
            if submitted:
                if not selected_sources:
                    st.error("Select at least one source agent to merge.")
                elif not merge_note.strip():
                    st.error("Provide a justification for the merge.")
                else:
                    try:
                        session.merge_agent_datasets(
                            target_agent_id=target_agent,
                            source_agent_ids=selected_sources,
                            justification=merge_note.strip(),
                        )
                    except CloudError as exc:
                        st.error(f"Unable to merge datasets: {exc}")
                    else:
                        st.success(
                            f"Merged {len(selected_sources)} dataset(s) into `{target_agent}`. Source namespaces were cleared."
                        )
                        _refresh_agent_store()
                        agents = (st.session_state.cloud_agent_store or {}).get("agents", {})

    if not agents:
        st.info("No agents found yet. Upload a dataset from a desktop client to create the first namespace.")
        return

    st.markdown("### Agent namespaces")
    for agent_id in agent_ids:
        record = agents.get(agent_id) or {}
        summary = st.session_state.cloud_agent_summaries.get(agent_id, summarize_dataset(record.get("dataset")))
        blocked = bool(record.get("blocked"))
        saved_at = _format_timestamp(record.get("saved_at"))
        header_status = "🚫 Blocked" if blocked else "✅ Active"
        expander = st.expander(f"{agent_id} — {summary.get('total_cases', 0)} cases ({header_status})", expanded=False)
        with expander:
            metrics = st.columns(4)
            metrics[0].metric("Cases", summary.get("total_cases", 0))
            metrics[1].metric("Unique devices", summary.get("unique_devices", 0))
            metrics[2].metric("Root causes tracked", len(summary.get("root_cause_counts", [])))
            metrics[3].metric("Last upload", saved_at)

            if blocked:
                reason = record.get("blocked_reason") or "Uploads are suspended by an administrator."
                st.warning(f"Uploads blocked: {reason}")

            upload_note = st.text_input(
                "Upload justification (optional)",
                key=f"upload-note-{agent_id}",
                help="Document why a manual upload is being performed from the Control Tower.",
            )
            admin_note = st.text_area(
                "Administrative justification for block/delete",
                key=f"admin-note-{agent_id}",
                help="Required when deleting data or suspending uploads.",
                height=90,
            )

            action_cols = st.columns(4)
            if action_cols[0].button("Upload local dataset", key=f"upload-{agent_id}"):
                dataset = load_local_ai_dataset()
                if not dataset:
                    st.error("No local AI Educate dataset found. Export data from a desktop client first.")
                else:
                    try:
                        session.save_agent_dataset(
                            agent_id,
                            dataset,
                            justification=(upload_note.strip() or "Uploaded from Control Tower"),
                        )
                    except AgentBlockedError as exc:
                        st.error(str(exc))
                    except CloudError as exc:
                        st.error(f"Failed to upload dataset: {exc}")
                    else:
                        st.success("Dataset uploaded to the agent namespace.")
                        _refresh_agent_store()

            if action_cols[1].button("Download dataset", key=f"download-{agent_id}"):
                dataset = session.load_agent_dataset(agent_id)
                if not dataset:
                    st.info("This agent does not have a dataset stored yet.")
                else:
                    save_local_ai_dataset(dataset)
                    st.success("Saved the agent dataset to the local Kiroshi installation.")

            if blocked:
                if action_cols[2].button("Allow uploads", key=f"unblock-{agent_id}"):
                    try:
                        session.set_agent_block_status(agent_id, blocked=False, justification="Uploads re-enabled via Control Tower.")
                    except CloudError as exc:
                        st.error(f"Unable to allow uploads: {exc}")
                    else:
                        st.success("Agent uploads have been restored.")
                        _refresh_agent_store()
            else:
                if action_cols[2].button("Block uploads", key=f"block-{agent_id}"):
                    if not admin_note.strip():
                        st.error("Provide a justification before suspending uploads.")
                    else:
                        try:
                            session.set_agent_block_status(
                                agent_id,
                                blocked=True,
                                justification=admin_note.strip(),
                            )
                        except CloudError as exc:
                            st.error(f"Unable to block uploads: {exc}")
                        else:
                            st.warning("Agent uploads have been suspended.")
                            _refresh_agent_store()

            if action_cols[3].button("Delete dataset", key=f"delete-{agent_id}"):
                if not admin_note.strip():
                    st.error("Provide a justification before deleting the dataset.")
                else:
                    try:
                        session.delete_agent_dataset(agent_id, justification=admin_note.strip())
                    except CloudError as exc:
                        st.error(f"Unable to delete dataset: {exc}")
                    else:
                        st.info("Dataset removed from the agent namespace. Future uploads will recreate it.")
                        _refresh_agent_store()

            justifications = record.get("justifications") if isinstance(record, dict) else []
            if justifications:
                log_rows = [
                    {
                        "Timestamp": _format_timestamp(entry.get("timestamp")),
                        "Action": entry.get("action"),
                        "Justification": entry.get("note"),
                    }
                    for entry in justifications
                    if isinstance(entry, dict)
                ]
                log_df = pd.DataFrame(log_rows)
                st.markdown("**Justification log**")
                st.dataframe(log_df, use_container_width=True, hide_index=True)
            else:
                st.caption("No justification records have been captured for this agent yet.")


def _render_analytics() -> None:
    agent_store: dict[str, Any] = st.session_state.cloud_agent_store or {"agents": {}}
    agent_summaries: dict[str, dict[str, Any]] = st.session_state.cloud_agent_summaries or {}
    agents = agent_store.get("agents", {}) if isinstance(agent_store, dict) else {}

    st.subheader("Quality assurance analytics")
    st.caption("Compare trends across field agents to identify recurring issues and training opportunities.")

    if not agents:
        st.info("No datasets available. Upload agent data before generating analytics.")
        return

    overview_rows: list[dict[str, Any]] = []
    recurrence_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    timeline_rows: list[dict[str, Any]] = []

    for agent_id, record in agents.items():
        summary = agent_summaries.get(agent_id, summarize_dataset(record.get("dataset")))
        total_cases = summary.get("total_cases", 0)
        top_root, top_root_count = ("—", 0)
        root_counts = summary.get("root_cause_counts", []) or []
        if root_counts:
            top_root, top_root_count = root_counts[0]

        recurrence_rate = float(top_root_count) / float(total_cases) if total_cases else 0.0
        overview_rows.append(
            {
                "Agent": agent_id,
                "Cases": total_cases,
                "Unique devices": summary.get("unique_devices", 0),
                "Top root cause": top_root,
                "Blocked": "Yes" if record.get("blocked") else "No",
            }
        )
        recurrence_rows.append(
            {
                "Agent": agent_id,
                "Top root cause": top_root,
                "Recurrence rate": recurrence_rate,
            }
        )

        for root_cause, count in root_counts:
            root_rows.append({"Agent": agent_id, "Root cause": root_cause, "Cases": count})

        dataset = record.get("dataset") if isinstance(record, dict) else None
        cases = dataset.get("cases") if isinstance(dataset, dict) else []
        if isinstance(cases, list):
            for case in cases:
                if not isinstance(case, dict):
                    continue
                timestamp = case.get("timestamp") or case.get("saved_at")
                if not timestamp:
                    continue
                try:
                    if isinstance(timestamp, (int, float)):
                        dt = datetime.fromtimestamp(float(timestamp))
                    else:
                        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                except Exception:
                    continue
                month_dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                timeline_rows.append({"Agent": agent_id, "Month": month_dt})

    overview_df = pd.DataFrame(overview_rows)
    st.dataframe(overview_df, use_container_width=True, hide_index=True)

    charts = st.columns(2)
    charts[0].altair_chart(
        alt.Chart(overview_df).mark_bar().encode(
            x=alt.X("Cases", title="Cases"),
            y=alt.Y("Agent", sort="-x"),
            color=alt.Color("Blocked", legend=None),
        ),
        use_container_width=True,
    )

    recurrence_df = pd.DataFrame(recurrence_rows)
    recurrence_df["Recurrence %"] = recurrence_df["Recurrence rate"] * 100
    charts[1].altair_chart(
        alt.Chart(recurrence_df).mark_line(point=True).encode(
            x=alt.X("Agent", sort=None),
            y=alt.Y("Recurrence %", title="Top root recurrence (%)"),
            color=alt.value("#FF7B00"),
        ),
        use_container_width=True,
    )

    st.markdown("### Root cause distribution")
    root_df = pd.DataFrame(root_rows)
    if not root_df.empty:
        stacked = (
            alt.Chart(root_df)
            .mark_bar()
            .encode(
                x=alt.X("Cases", aggregate="sum", stack="normalize", title="Case share"),
                y=alt.Y("Agent", sort="-x"),
                color=alt.Color("Root cause"),
                tooltip=["Agent", "Root cause", "Cases"],
            )
        )
        st.altair_chart(stacked, use_container_width=True)
    else:
        st.info("Root cause information is not available in the uploaded datasets.")

    st.markdown("### Case velocity")
    timeline_df = pd.DataFrame(timeline_rows)
    if not timeline_df.empty:
        timeline_counts = (
            timeline_df.groupby(["Month", "Agent"]).size().reset_index(name="Cases")
        )
        timeline_chart = (
            alt.Chart(timeline_counts)
            .mark_line(point=True)
            .encode(
                x=alt.X("Month:T", title="Month"),
                y=alt.Y("Cases", title="Cases per month"),
                color=alt.Color("Agent"),
            )
        )
        st.altair_chart(timeline_chart, use_container_width=True)
    else:
        st.caption("Case timestamps not found. Future uploads will populate velocity analytics.")


def _render_security() -> None:
    session: CloudSession = st.session_state.cloud_session
    config = load_cloud_config()

    st.subheader("Credentials")
    st.caption("Rotate the username and password used by Kiroshi clients to connect to this cloud instance.")

    with st.form("update-credentials"):
        username = st.text_input("New username", value=session.username)
        password = st.text_input(
            "New password",
            type="password",
            help="Use a strong password – the encryption key is derived from it.",
        )
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Update credentials", type="primary")

    if submitted:
        if not username.strip() or not password:
            st.error("Both username and password are required.")
        elif password != confirm:
            st.error("Passwords do not match.")
        else:
            try:
                session.update_credentials(username.strip(), password)
            except CloudError as exc:
                st.error(f"Unable to update credentials: {exc}")
            else:
                st.session_state.cloud_username = username.strip()
                st.success("Credentials updated. Remember to update each Kiroshi workstation.")
                config = load_cloud_config()

    st.divider()
    st.subheader("Security posture")
    creds_warning = config.get("uses_default_credentials")
    if creds_warning:
        st.error(
            "Default credentials detected. Until you change them, the cloud database is protected by a known password."
        )
    else:
        st.success("Custom credentials active.")

    st.caption(
        "All device metadata and AI Educate snapshots are encrypted at rest using a symmetric key derived from your password."
        " Kiroshi Cloud never stores plaintext case information."
    )


def _render_setup() -> None:
    session: CloudSession = st.session_state.cloud_session
    guidance = overlay_guidance(session.config if session else None)

    st.subheader("Overlay network checklist")
    st.caption(
        "Recommended mesh overlay: "
        f"{guidance['provider']}"
    )

    with st.form("overlay-guidance"):
        provider_value = st.text_input(
            "Recommended overlay provider(s)",
            value=guidance["provider"],
            help="Displayed to technicians so they know which tunnel service to deploy.",
        )
        instructions_value = st.text_area(
            "Overlay instructions (Markdown supported)",
            value=guidance["instructions"],
            height=260,
            help="Explain how to join the overlay network, verify connectivity, and distribute tokens.",
        )
        submitted = st.form_submit_button("Save overlay guidance", type="primary")

    if submitted and session:
        try:
            guidance = session.update_overlay_settings(provider_value, instructions_value)
        except CloudError as exc:
            st.error(f"Unable to update overlay guidance: {exc}")
        else:
            st.success("Overlay guidance updated for all cloud-connected desktops.")

    st.markdown(guidance["instructions"])

    st.subheader("Troubleshooting")
    st.markdown(
        """
* **Tunnel won’t connect** – ensure the overlay service is allowed through Windows Defender Firewall and
  any third-party security suites. Double-check that the device shows as *connected* in the overlay’s admin
  console.
* **Token rejected** – verify that the workstation is using the latest credentials and token generated from
  this console. Revoke and recreate the token if you suspect it leaked.
* **Dataset mismatch** – use *Refresh dataset from cloud* followed by *Download cloud dataset into Kiroshi*
  to guarantee both sides share the same AI Educate snapshot.
        """
    )


def _render_authenticated() -> None:
    st.sidebar.markdown(
        f"**Connected as:** `{st.session_state.cloud_username or st.session_state.cloud_session.username}`"
    )
    if st.sidebar.button("Disconnect", use_container_width=True):
        _disconnect()
        st.rerun()

    tabs = st.tabs(
        [
            "Overview",
            "Agent Databases",
            "Analytics",
            "Connections",
            "Security",
            "Setup Guide",
        ]
    )

    with tabs[0]:
        _render_overview()
    with tabs[1]:
        _render_agent_databases()
    with tabs[2]:
        _render_analytics()
    with tabs[3]:
        _render_connections()
    with tabs[4]:
        _render_security()
    with tabs[5]:
        _render_setup()


if st.session_state.cloud_session is None:
    _render_login()
else:
    _render_authenticated()

