"""Streamlit interface for the Kiroshi Cloud client."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st

try:
    from kiroshi_chat import (
        KIROSHI_CHAT_LOGO_PATH,
        load_manual_docs,
        save_manual_docs,
    )
except Exception as exc:  # pragma: no cover - optional dependency guard
    raise RuntimeError(
        "The Streamlit console requires kiroshi_chat helpers. Verify dependencies are installed."
    ) from exc

DEFAULT_API_BASE = os.environ.get("KIROSHI_CLOUD_API", "http://localhost:8050")
ONLINE_THRESHOLD_SECONDS = 5 * 60


def _api_request(
    method: str,
    path: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    auth: Optional[tuple[str, str]] = None,
    base_url: str = DEFAULT_API_BASE,
    timeout: int = 15,
) -> tuple[Optional[requests.Response], Optional[Dict[str, Any]]]:
    url = base_url.rstrip("/") + path
    try:
        response = requests.request(
            method,
            url,
            json=payload,
            auth=auth,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return None, {"error": str(exc)}

    try:
        if response.headers.get("Content-Type", "").startswith("application/json"):
            data = response.json()
        else:
            data = None
    except ValueError:
        data = None
    return response, data


def _format_timestamp(value: Optional[str]) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _compute_device_metrics(devices: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(devices)
    allowed = sum(1 for d in devices if (d.get("connection_status") or "allowed") == "allowed")
    blocked = total - allowed
    now = datetime.now(timezone.utc)
    online = 0
    for device in devices:
        try:
            ts = datetime.fromisoformat(str(device.get("last_seen", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if (now - ts).total_seconds() <= ONLINE_THRESHOLD_SECONDS:
            online += 1
    return {"total": total, "allowed": allowed, "blocked": blocked, "online": online}


def _push_local_educate(auth: tuple[str, str], base_url: str) -> Dict[str, Any]:
    documents = [doc for doc in load_manual_docs() if isinstance(doc, dict)]
    _, data = _api_request(
        "POST",
        "/educate/sync",
        payload={"documents": documents},
        auth=auth,
        base_url=base_url,
        timeout=60,
    )
    return data or {}


def _pull_educate_to_desktop(documents: List[Dict[str, Any]]) -> None:
    save_manual_docs(documents)


def _check_response(
    response: Optional[requests.Response],
    data: Optional[Dict[str, Any]],
    *,
    context: str,
    clear_auth_on_unauthorized: bool = True,
) -> bool:
    if response is None:
        st.error(f"{context}: {data.get('error') if data else 'request failed'}")
        return False
    if response.status_code == 401:
        st.error("Authentication failed. Verify your username and password.")
        if clear_auth_on_unauthorized:
            st.session_state["auth"] = None
        return False
    if response.status_code >= 400:
        message = data.get("error") if isinstance(data, dict) else response.text
        st.error(f"{context}: {message}")
        return False
    return True


def _init_state() -> None:
    st.session_state.setdefault("api_base", DEFAULT_API_BASE)
    st.session_state.setdefault("auth", None)
    st.session_state.setdefault("last_error", None)


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:  # pragma: no cover - compatibility for older Streamlit builds
        st.experimental_rerun()


def main() -> None:
    st.set_page_config(
        page_title="Kiroshi Cloud Console",
        page_icon=str(KIROSHI_CHAT_LOGO_PATH),
        layout="wide",
    )
    _init_state()

    with st.sidebar:
        st.image(str(KIROSHI_CHAT_LOGO_PATH), width=160)
        st.markdown("### Connection")
        api_base_input = st.text_input("API Base URL", value=st.session_state["api_base"], key="api-base")
        current_auth = st.session_state.get("auth") or ("", "")
        username_input = st.text_input("Username", value=current_auth[0], key="api-username")
        password_input = st.text_input("Password", type="password", key="api-password")
        connect_clicked = st.button("Connect", use_container_width=True)
        if connect_clicked:
            if username_input and password_input:
                st.session_state["api_base"] = api_base_input.strip() or DEFAULT_API_BASE
                st.session_state["auth"] = (username_input.strip(), password_input)
                st.session_state["last_error"] = None
                _rerun()
            else:
                st.warning("Please provide both a username and password.")
        if st.session_state.get("auth"):
            if st.button("Disconnect", use_container_width=True):
                st.session_state["auth"] = None
                st.session_state["last_error"] = None
                _rerun()
        st.markdown("---")
        st.caption(
            "Need help bringing the cloud online? Follow the deployment notes in docs/kiroshi_cloud_arch_setup.md."
        )

    st.title("Kiroshi Cloud Control Tower")

    auth = st.session_state.get("auth")
    base_url = st.session_state.get("api_base", DEFAULT_API_BASE)
    if not auth or not all(auth):
        st.info("Enter your Kiroshi Cloud credentials in the sidebar to begin.")
        return

    devices_response, devices_data = _api_request("GET", "/devices", auth=auth, base_url=base_url)
    if not _check_response(devices_response, devices_data, context="Fetching devices"):
        return
    devices = devices_data.get("devices", []) if isinstance(devices_data, dict) else []

    creds_response, creds_data = _api_request("GET", "/settings/credentials", auth=auth, base_url=base_url)
    current_username = creds_data.get("username") if isinstance(creds_data, dict) else None

    educate_response, educate_data = _api_request("GET", "/educate", auth=auth, base_url=base_url)
    if not _check_response(educate_response, educate_data, context="Loading Educate dataset", clear_auth_on_unauthorized=False):
        educate_documents: List[Dict[str, Any]] = []
    else:
        educate_documents = educate_data.get("documents", []) if isinstance(educate_data, dict) else []

    metrics = _compute_device_metrics(devices)
    metrics_columns = st.columns(4)
    metrics_columns[0].metric("Devices", metrics["total"])
    metrics_columns[1].metric("Allowed", metrics["allowed"])
    metrics_columns[2].metric("Blocked", metrics["blocked"])
    metrics_columns[3].metric("Online", metrics["online"])

    table_rows = [
        {
            "Device ID": device.get("device_id"),
            "Name": device.get("name") or "—",
            "Model": device.get("model") or "—",
            "IP Address": device.get("ip_address") or "—",
            "Status": device.get("connection_status", "allowed").title(),
            "Last Seen": _format_timestamp(device.get("last_seen")),
        }
        for device in devices
    ]

    if table_rows:
        st.subheader("Fleet overview")
        st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")
    else:
        st.info("No devices have checked in yet. Use the CLI to register a node or wait for the first heartbeat.")

    for device in devices:
        device_id = device.get("device_id")
        header = device.get("name") or device_id or "Unknown device"
        with st.expander(f"{header} — {device_id}"):
            meta_columns = st.columns(3)
            meta_columns[0].markdown(f"**Owner:** {device.get('owner') or '—'}")
            meta_columns[1].markdown(f"**Location:** {device.get('location') or '—'}")
            meta_columns[2].markdown(f"**Firmware:** {device.get('firmware_version') or '—'}")
            st.markdown(f"**OS:** {device.get('os_version') or '—'}")
            st.markdown(f"**Notes:** {device.get('notes') or '—'}")
            if device.get("metadata"):
                st.json(device["metadata"], expanded=False)

            status_badge = device.get("connection_status", "allowed")
            st.markdown(f"**Connection policy:** `{status_badge}`")
            if device.get("connection_reason"):
                st.caption(f"Reason: {device['connection_reason']}")

            action_cols = st.columns(3)
            if action_cols[0].button("Allow", key=f"allow-{device_id}"):
                response, data = _api_request("POST", f"/connections/{device_id}/allow", auth=auth, base_url=base_url)
                if _check_response(response, data, context="Allowing device"):
                    st.success("Device allowed")
                    _rerun()
            block_reason = action_cols[1].text_input(
                "Block reason",
                value=device.get("connection_reason") or "",
                key=f"reason-{device_id}",
            )
            if action_cols[1].button("Block", key=f"block-{device_id}"):
                response, data = _api_request(
                    "POST",
                    f"/connections/{device_id}/block",
                    payload={"reason": block_reason or None},
                    auth=auth,
                    base_url=base_url,
                )
                if _check_response(response, data, context="Blocking device"):
                    st.warning("Device blocked")
                    _rerun()
            if action_cols[2].button("Remove", key=f"remove-{device_id}"):
                response, data = _api_request("DELETE", f"/connections/{device_id}", auth=auth, base_url=base_url)
                if _check_response(response, data, context="Removing device"):
                    st.success("Device removed")
                    _rerun()

    st.divider()
    st.subheader("Secure mesh (Tailscale)")
    p2p_response, p2p_data = _api_request("GET", "/p2p/status", auth=auth, base_url=base_url)
    if not _check_response(p2p_response, p2p_data, context="Checking mesh status", clear_auth_on_unauthorized=False):
        p2p_data = {"available": False}
    if not p2p_data.get("available"):
        st.info(p2p_data.get("message") or "Install the Tailscale CLI to enable peer-to-peer connectivity.")
    else:
        peers = p2p_data.get("Peer", []) or p2p_data.get("Peers")
        st.json(p2p_data, expanded=False)
        if isinstance(peers, list):
            st.caption(f"Peers connected: {len(peers)}")
        with st.form("tailscale-connect"):
            st.write("Bring the node online without exposing inbound ports.")
            auth_key = st.text_input("Auth key", type="password")
            hostname = st.text_input("Hostname override")
            submitted = st.form_submit_button("Connect via Tailscale")
            if submitted:
                response, data = _api_request(
                    "POST",
                    "/p2p/connect",
                    payload={"auth_key": auth_key or None, "hostname": hostname or None},
                    auth=auth,
                    base_url=base_url,
                    timeout=60,
                )
                if _check_response(response, data, context="Starting secure mesh"):
                    st.success("Mesh connection requested")
                    _rerun()
        if st.button("Disconnect secure mesh", key="disconnect-mesh"):
            response, data = _api_request("POST", "/p2p/disconnect", auth=auth, base_url=base_url)
            if _check_response(response, data, context="Stopping secure mesh"):
                st.success("Mesh disconnected")
                _rerun()

    st.divider()
    st.subheader("Cloud credentials")
    st.markdown(f"Current username: `{current_username or 'unknown'}`")
    with st.form("update-credentials"):
        new_username = st.text_input("New username", value=current_username or "")
        new_password = st.text_input("New password", type="password")
        confirm = st.form_submit_button("Update credentials")
        if confirm:
            if not new_username or not new_password:
                st.warning("Both username and password are required.")
            else:
                response, data = _api_request(
                    "PUT",
                    "/settings/credentials",
                    payload={"username": new_username, "password": new_password},
                    auth=auth,
                    base_url=base_url,
                )
                if _check_response(response, data, context="Updating credentials"):
                    st.success("Credentials updated. Please reconnect with the new login.")
                    st.session_state["auth"] = (new_username, new_password)
                    _rerun()

    st.divider()
    st.subheader("Educate dataset alignment")
    st.caption(
        "Synchronise the on-device Educate knowledge base with the cloud so the AI assistant works from the same corpus."
    )
    educate_cols = st.columns(3)
    educate_cols[0].metric("Documents", len(educate_documents))
    if educate_documents:
        latest_update = max(doc.get("updated_at") for doc in educate_documents if doc.get("updated_at"))
        educate_cols[1].metric("Last update", _format_timestamp(latest_update))
    if educate_cols[0].button("Push desktop knowledge base", key="push-educate"):
        with st.spinner("Uploading Educate documents..."):
            result = _push_local_educate(auth, base_url)
        if result.get("status") == "ok":
            st.success(f"Uploaded {result.get('stats', {}).get('updated', 0)} documents")
            _rerun()
        else:
            st.error(result.get("error") or "Upload failed")
    if educate_cols[1].button("Pull to desktop", key="pull-educate"):
        with st.spinner("Syncing to desktop..."):
            _pull_educate_to_desktop(educate_documents)
        st.success("Desktop Educate dataset updated")
    if educate_cols[2].button("Refresh", key="refresh-educate"):
        _rerun()


if __name__ == "__main__":
    main()


