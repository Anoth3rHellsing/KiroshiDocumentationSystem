"""Streamlit client for managing the encrypted Kiroshi Cloud service."""

from __future__ import annotations

import ipaddress
from datetime import datetime
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from kiroshi_cloud_sync import (
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


st.set_page_config(page_title="Kiroshi Cloud", layout="wide", page_icon="☁️")


def _initialize_state() -> None:
    defaults: dict[str, Any] = {
        "cloud_session": None,
        "cloud_devices": {},
        "cloud_dataset": None,
        "cloud_dataset_meta": {},
        "cloud_summary": None,
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


def _refresh_dataset() -> None:
    session: CloudSession = st.session_state.cloud_session
    if not session:
        return
    dataset_payload = session.load_ai_dataset()
    dataset: dict[str, Any] | None
    meta: dict[str, Any]
    if dataset_payload and "dataset" in dataset_payload:
        dataset = dataset_payload.get("dataset")
        meta = {
            key: dataset_payload.get(key)
            for key in ("saved_at", "cloud_instance", "comment")
        }
    else:
        dataset = dataset_payload
        meta = {"saved_at": None}
    st.session_state.cloud_dataset = dataset
    st.session_state.cloud_dataset_meta = meta
    st.session_state.cloud_summary = summarize_dataset(dataset)


def _disconnect() -> None:
    for key in ("cloud_session", "cloud_devices", "cloud_dataset", "cloud_summary"):
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
    st.title("Kiroshi Cloud Console")
    st.caption(
        "Securely manage remote Kiroshi devices, credentials, and the shared "
        "AI Educate dataset from a central cloud interface."
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
    _refresh_dataset()
    st.success("Connected to Kiroshi Cloud. Use the tabs above to manage devices and data.")


def _render_overview() -> None:
    summary: dict[str, Any] | None = st.session_state.cloud_summary
    devices_payload: dict[str, Any] = st.session_state.cloud_devices or {"devices": []}
    devices = devices_payload.get("devices", [])

    allowed = sum(1 for item in devices if item.get("allowed"))
    blocked = sum(1 for item in devices if item.get("blocked"))
    total = len(devices)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total devices", total)
    col2.metric("Allowed", allowed)
    col3.metric("Blocked", blocked)

    if summary:
        st.subheader("AI Educate snapshot")
        saved_at = _format_timestamp(st.session_state.cloud_dataset_meta.get("saved_at"))
        st.caption(f"Last sync stored in the cloud: {saved_at}")
        metrics = st.columns(2)
        metrics[0].metric("Cases analysed", summary.get("total_cases", 0))
        metrics[1].metric("Unique devices", summary.get("unique_devices", 0))

        root_frame = dataset_counts_to_frame(summary.get("root_cause_counts", []), label="Root cause")
        device_frame = dataset_counts_to_frame(summary.get("device_counts", []), label="Device")

        chart_col1, chart_col2 = st.columns(2)
        if not root_frame.empty:
            chart_col1.altair_chart(
                alt.Chart(root_frame).mark_bar().encode(
                    x=alt.X("cases", title="Cases"),
                    y=alt.Y("Root cause", sort="-x"),
                    color=alt.Color("Root cause", legend=None),
                ),
                use_container_width=True,
            )
        else:
            chart_col1.info("No AI Educate cases uploaded yet.")

        if not device_frame.empty:
            chart_col2.altair_chart(
                alt.Chart(device_frame).mark_bar().encode(
                    x=alt.X("cases", title="Cases"),
                    y=alt.Y("Device", sort="-x"),
                    color=alt.Color("Device", legend=None),
                ),
                use_container_width=True,
            )
        else:
            chart_col2.info("No device analytics available.")

        recent = summary.get("recent_cases", [])
        if recent:
            table = pd.DataFrame(
                [
                    {
                        "Case": item.get("case_id"),
                        "Title": item.get("title"),
                        "Root cause": item.get("root_cause"),
                        "Device": item.get("device"),
                        "Timestamp": item.get("timestamp").strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for item in recent
                    if item.get("timestamp")
                ]
            )
            st.dataframe(table, use_container_width=True, hide_index=True)


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


def _render_ai_sync() -> None:
    session: CloudSession = st.session_state.cloud_session

    st.subheader("AI Educate synchronisation")
    cloud_dataset = st.session_state.cloud_dataset

    col_cloud, col_local = st.columns(2)
    if col_cloud.button("Refresh dataset from cloud", key="refresh-cloud-dataset"):
        _refresh_dataset()
        cloud_dataset = st.session_state.cloud_dataset
        st.success("Downloaded the latest dataset from Kiroshi Cloud.")

    if col_local.button("Upload local Kiroshi dataset", key="push-local-dataset"):
        dataset = load_local_ai_dataset()
        if not dataset:
            st.error("No local AI Educate dataset was found. Save at least one case from Kiroshi first.")
        else:
            try:
                session.save_ai_dataset(dataset)
            except CloudError as exc:
                st.error(f"Failed to upload dataset: {exc}")
            else:
                st.success("Uploaded the local AI Educate knowledge base to the cloud.")
                _refresh_dataset()
                cloud_dataset = st.session_state.cloud_dataset

    if st.button("Download cloud dataset into Kiroshi", key="pull-to-local"):
        _refresh_dataset()
        dataset = st.session_state.cloud_dataset
        if not dataset:
            st.info("The cloud does not yet contain an AI Educate dataset.")
        else:
            save_local_ai_dataset(dataset)
            st.success("Local Kiroshi installation updated with the cloud dataset.")

    summary = summarize_dataset(cloud_dataset)
    st.markdown("### Cloud analytics")
    st.caption("Review high level insights before exporting the knowledge base.")

    metrics = st.columns(3)
    metrics[0].metric("Cases", summary.get("total_cases", 0))
    metrics[1].metric("Unique devices", summary.get("unique_devices", 0))
    saved_at = _format_timestamp(st.session_state.cloud_dataset_meta.get("saved_at"))
    metrics[2].metric("Last cloud update", saved_at)

    root_frame = dataset_counts_to_frame(summary.get("root_cause_counts", []), label="Root cause")
    device_frame = dataset_counts_to_frame(summary.get("device_counts", []), label="Device")

    chart_row = st.columns(2)
    if not root_frame.empty:
        chart_row[0].altair_chart(
            alt.Chart(root_frame).mark_bar().encode(
                x=alt.X("cases", title="Cases"),
                y=alt.Y("Root cause", sort="-x"),
                color=alt.Color("Root cause", legend=None),
            ),
            use_container_width=True,
        )
    else:
        chart_row[0].info("Upload a dataset to calculate root cause trends.")

    if not device_frame.empty:
        chart_row[1].altair_chart(
            alt.Chart(device_frame).mark_bar().encode(
                x=alt.X("cases", title="Cases"),
                y=alt.Y("Device", sort="-x"),
                color=alt.Color("Device", legend=None),
            ),
            use_container_width=True,
        )
    else:
        chart_row[1].info("Upload a dataset to calculate device trends.")


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

    tabs = st.tabs([
        "Overview",
        "Connections",
        "AI Educate Sync",
        "Security",
        "Setup Guide",
    ])

    with tabs[0]:
        _render_overview()
    with tabs[1]:
        _render_connections()
    with tabs[2]:
        _render_ai_sync()
    with tabs[3]:
        _render_security()
    with tabs[4]:
        _render_setup()


if st.session_state.cloud_session is None:
    _render_login()
else:
    _render_authenticated()

