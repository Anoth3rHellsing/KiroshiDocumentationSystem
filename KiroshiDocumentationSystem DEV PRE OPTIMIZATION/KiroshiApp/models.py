import uuid
import re
from dataclasses import dataclass, field, fields
from typing import Iterable, Mapping, Sequence, Dict, List
from datetime import datetime, date
from pathlib import Path

from KiroshiApp.constants import (
    VERSION,
    PRIORITY_OPTIONS,
    DEFAULT_TRACKING_PRIORITY,
    MILESTONE_ID_ORDER,
    DELL_ESCALATION_FIELDS,
    DEFAULT_THEME,
    KIROSHI_MESSAGES
)
from KiroshiApp.utils import (
    _utc_now_z,
    _normalize_hardware_test_text,
    _normalize_damage_classification,
    sanitize_filename,
    parse_iso_datetime,
)


@dataclass
class UpdateCheckResult:
    repo: str
    branch: str
    current_version: str
    latest_version: str | None = None
    latest_commit: str | None = None
    latest_published: str | None = None
    has_update: bool = False
    download_url: str | None = None
    error: str | None = None



@dataclass
class RemoteSessionEntry:
    """Structured representation of a remote troubleshooting session."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    notes: str = ""
    created_at: str = field(default_factory=_utc_now_z)
    updated_at: str = field(default_factory=_utc_now_z)

    def display_title(self, index: int) -> str:
        """Return a human-friendly title, falling back to an indexed label."""

        title = (self.title or "").strip()
        return title or f"Session {index}"

    def touch(self) -> None:
        """Refresh the ``updated_at`` timestamp to the current moment."""

        self.updated_at = _utc_now_z()


@dataclass
class TrackingData:
    """Metadata stored for active tracking in a case JSON file."""

    active: bool = False
    type: str = ""
    category: str = ""
    status: str = ""
    priority: str = DEFAULT_TRACKING_PRIORITY
    ticket_number: str = ""
    creation_day: str = ""
    case_link: str = ""
    expected_arrival_date: str = ""
    service_tag: str = ""

    def __post_init__(self) -> None:
        if self.priority not in PRIORITY_OPTIONS:
            self.priority = DEFAULT_TRACKING_PRIORITY
        # Ensure text fields never contain ``None`` when loaded from legacy JSON.
        for field_name in (
            "type",
            "category",
            "status",
            "ticket_number",
            "creation_day",
            "case_link",
            "expected_arrival_date",
            "service_tag",
        ):
            value = getattr(self, field_name)
            if value is None:
                setattr(self, field_name, "")


@dataclass
class CaseData:
    """Container for case details provided through the UI."""

    # General case
    company_name: str = ""
    subscription_id: str = ""
    brief_description: str = ""
    case_id: str = ""
    application_version: str = ""
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
    remote_sessions: list[RemoteSessionEntry] = field(default_factory=list)
    remote_steps: str = ""
    root_cause: str = ""
    repro_steps: str = ""
    third_line_hj_article: str = ""
    third_line_troubleshoot_summary: str = ""
    third_line_comments: str = ""
    third_line_reseller_name: str = ""
    third_line_reseller_phone: str = ""
    third_line_reseller_phone_alt: str = ""
    third_line_reseller_email: str = ""
    third_line_clinic_rep_name: str = ""
    third_line_clinic_rep_phone: str = ""
    third_line_clinic_rep_phone_alt: str = ""
    third_line_tv_id: str = ""
    third_line_tv_password: str = ""
    third_line_unite_pin: str = ""

    solution: str = ""
    survey_link: str = ""
    # Escalation details
    request_issue: str = ""
    contact_name: str = ""
    office_ph: str = ""
    direct_ph: str = ""
    best_time: str = ""
    patterson: str = ""
    straumann: str = ""
    esc_name: str = ""
    esc_ph: str = ""
    esc_email: str = ""
    # Additional information
    additional_info: str = ""
    customer_trios_only: bool = False
    support_fee_accepted: bool = False
    hardware_test: str = ""
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
    dongle_deployment_date: str = ""
    scanner_previous_replacements: int = 0
    scanner_accidental_damage: str = ""
    hardware_dongle_replaced: str = ""
    hardware_latest_deployment_date: str = ""
    hardware_scanner_replaced: str = ""
    hardware_scanner_sn_summary: str = ""
    hardware_subscription_type: str = ""
    # Dell escalation specifics
    dell_issue_start_date: str = ""
    dell_command_updates_status: str = ""
    dell_power_options_setup: str = ""
    dell_optimizer_setup: str = ""
    dell_intel_ppm_installed: str = ""
    dell_cpu_speed_or_throttling: str = ""
    dell_gpu_usage_integrated: str = ""
    dell_gpu_usage_dedicated: str = ""
    dell_cpu_utilization: str = ""
    dell_benchmark_results: str = ""
    dell_ultra_resolution_support: str = ""
    dell_gpu_driver_versions: str = ""
    dell_reliability_monitor_results: str = ""
    dell_diagnostics_results: str = ""
    dell_windows_reimaged: str = ""
    clinic_name: str = ""
    clinic_contact_name: str = ""
    clinic_contact_phone: str = ""
    clinic_contact_email: str = ""
    clinic_address_line_1: str = ""
    clinic_address_line_2: str = ""
    clinic_city: str = ""
    clinic_state: str = ""
    clinic_postal_code: str = ""
    tracking: TrackingData = field(default_factory=TrackingData)
    kiroshi_version: str = VERSION
    last_modified: str = ""

    def __post_init__(self) -> None:
        self.hardware_test = _normalize_hardware_test_text(self.hardware_test)

        if self.remote_steps is None:
            self.remote_steps = ""
        else:
            self.remote_steps = str(self.remote_steps)

        sessions_source: Iterable[object] | None
        if isinstance(self.remote_sessions, Iterable) and not isinstance(
            self.remote_sessions, (str, bytes)
        ):
            sessions_source = self.remote_sessions
        else:
            sessions_source = []
        normalized_sessions = _normalize_remote_session_list(sessions_source)
        if not normalized_sessions and self.remote_steps.strip():
            now = _utc_now_z()
            normalized_sessions = [
                RemoteSessionEntry(
                    title="Session 1",
                    notes=self.remote_steps,
                    created_at=now,
                    updated_at=now,
                )
            ]
        self.remote_sessions = normalized_sessions
        self.remote_steps = format_remote_sessions_summary(
            self.remote_sessions, include_timestamps=True
        )
        if not isinstance(self.tracking, TrackingData):
            if isinstance(self.tracking, Mapping):
                self.tracking = TrackingData(**self.tracking)  # type: ignore[arg-type]
            else:
                self.tracking = TrackingData()
        if not self.kiroshi_version:
            self.kiroshi_version = VERSION
        if self.tracking.priority not in PRIORITY_OPTIONS:
            self.tracking.priority = DEFAULT_TRACKING_PRIORITY
        if self.last_modified is None:
            self.last_modified = ""
        elif not isinstance(self.last_modified, str):
            self.last_modified = str(self.last_modified)

        self.scanner_accidental_damage = _normalize_damage_classification(
            getattr(self, "scanner_accidental_damage", "")
        )


@dataclass
class InMemoryUploadedFile:
    """Simple file-like container for generated screenshots."""

    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return self.data


@dataclass
class ScreenshotAsset(InMemoryUploadedFile):
    """Rich metadata container for captured screenshots."""

    label: str = ""
    capture_mode: str = "full"
    captured_at: str = field(default_factory=_utc_now_z)
    origin: str = "capture"
    content_type: str = "image/png"

    def __post_init__(self) -> None:
        safe_name = sanitize_filename(self.name)
        if not safe_name.lower().endswith(".png"):
            safe_name = f"{safe_name}.png"
        object.__setattr__(self, "name", safe_name)
        object.__setattr__(self, "label", (self.label or Path(safe_name).stem).strip())
        if not self.label:
            object.__setattr__(self, "label", Path(safe_name).stem)
        mode = (self.capture_mode or "capture").strip().lower()
        object.__setattr__(self, "capture_mode", mode or "capture")
        object.__setattr__(self, "origin", (self.origin or "capture").strip() or "capture")
        if not self.captured_at:
            object.__setattr__(self, "captured_at", _utc_now_z())

    def metadata(self, *, path: str) -> dict[str, str]:
        record = {
            "name": self.name,
            "path": path,
            "label": self.label,
            "captured_at": self.captured_at,
            "capture_mode": self.capture_mode,
            "origin": self.origin,
        }
        if self.content_type:
            record["content_type"] = self.content_type
        return record


@dataclass
class MilestoneProgressState:
    completed_at: str | None = None
    alerted_at: str | None = None
    completion_actions_done: bool = False
    overdue_actions_done: bool = False


def _default_milestone_progress() -> dict[str, MilestoneProgressState]:
    return {milestone_id: MilestoneProgressState() for milestone_id in MILESTONE_ID_ORDER}


@dataclass
class CaseMilestoneState:
    created_at: str = field(default_factory=_utc_now_z)
    statuses: dict[str, MilestoneProgressState] = field(
        default_factory=_default_milestone_progress
    )


def _default_attachments_index() -> dict[str, list[dict[str, str]]]:
    return {
        "uploads": [],
        "log_uploads": [],
        "screenshots": [],
    }


@dataclass
class CaseSession:
    """Container for per-case session state."""

    case: CaseData
    scratch: str = ""
    uploads: list = field(default_factory=list)
    log_uploads: list = field(default_factory=list)
    screenshots: list[ScreenshotAsset] = field(default_factory=list)
    source_path: str = ""
    attachments_index: dict[str, list[dict[str, str]]] = field(
        default_factory=_default_attachments_index
    )
    milestones: CaseMilestoneState = field(default_factory=CaseMilestoneState)


# Helper functions tied to models

def _coerce_remote_session_entry(
    payload: object, *, default_title: str
) -> RemoteSessionEntry:
    """Return a ``RemoteSessionEntry`` built from loose mapping data."""

    if isinstance(payload, RemoteSessionEntry):
        entry = RemoteSessionEntry(
            session_id=(payload.session_id or uuid.uuid4().hex),
            title=str(payload.title or default_title),
            notes=str(payload.notes or ""),
            created_at=str(payload.created_at or _utc_now_z()),
            updated_at=str(payload.updated_at or payload.created_at or _utc_now_z()),
        )
    elif isinstance(payload, Mapping):
        created = payload.get("created_at")
        created_str = str(created or "")
        if not created_str:
            created_str = _utc_now_z()
        updated = payload.get("updated_at")
        updated_str = str(updated or "")
        if not updated_str:
            updated_str = created_str
        entry = RemoteSessionEntry(
            session_id=str(payload.get("session_id") or uuid.uuid4().hex),
            title=str(payload.get("title") or default_title),
            notes=str(payload.get("notes") or ""),
            created_at=created_str,
            updated_at=updated_str,
        )
    elif isinstance(payload, str):
        entry = RemoteSessionEntry(title=default_title, notes=payload)
    else:
        entry = RemoteSessionEntry(title=default_title)

    if not entry.title.strip():
        entry.title = default_title

    if not entry.created_at:
        entry.created_at = _utc_now_z()
    if not entry.updated_at:
        entry.updated_at = entry.created_at

    return entry


def _normalize_remote_session_list(
    raw_sessions: Iterable[object] | None,
) -> list[RemoteSessionEntry]:
    """Convert raw session payloads into dataclass entries."""

    if not raw_sessions:
        return []
    if isinstance(raw_sessions, (str, bytes)):
        return []

    normalized: list[RemoteSessionEntry] = []
    for payload in raw_sessions:
        default_title = f"Session {len(normalized) + 1}"
        normalized.append(
            _coerce_remote_session_entry(payload, default_title=default_title)
        )
    return normalized


def format_remote_sessions_summary(
    sessions: Sequence[RemoteSessionEntry], *, include_timestamps: bool = True
) -> str:
    """Combine remote session notes into a readable multi-session summary."""

    if not sessions:
        return ""

    show_titles = len(sessions) > 1 or any(
        session.title.strip()
        and session.title.strip().lower() != f"session {index}"
        for index, session in enumerate(sessions, start=1)
    )

    blocks: list[str] = []
    for idx, session in enumerate(sessions, start=1):
        title = session.display_title(idx)
        notes = (session.notes or "").strip()
        if show_titles:
            header = title
            if include_timestamps:
                created = (session.created_at or "").strip()
                updated = (session.updated_at or "").strip()
                timestamp_bits: list[str] = []
                if created:
                    timestamp_bits.append(f"started {created}")
                if updated and updated != created:
                    timestamp_bits.append(f"updated {updated}")
                if timestamp_bits:
                    header = f"{header} ({', '.join(timestamp_bits)})"
            block = header if not notes else f"{header}\n{notes}"
        else:
            block = notes
        blocks.append(block.strip())

    return "\n\n".join(part for part in blocks if part).strip()


def _coerce_case_milestone_state(payload: object | None) -> CaseMilestoneState:
    if isinstance(payload, CaseMilestoneState):
        state = payload
    elif isinstance(payload, Mapping):
        created_at = str(payload.get("created_at") or _utc_now_z())
        statuses_payload = payload.get("statuses")
        statuses: dict[str, MilestoneProgressState] = {}
        if isinstance(statuses_payload, Mapping):
            for milestone_id, entry in statuses_payload.items():
                if not isinstance(entry, Mapping):
                    continue
                statuses[milestone_id] = MilestoneProgressState(
                    completed_at=str(entry.get("completed_at"))
                    if entry.get("completed_at")
                    else None,
                    alerted_at=str(entry.get("alerted_at"))
                    if entry.get("alerted_at")
                    else None,
                    completion_actions_done=bool(entry.get("completion_actions_done")),
                    overdue_actions_done=bool(entry.get("overdue_actions_done")),
                )
        state = CaseMilestoneState(created_at=created_at, statuses=statuses)
    else:
        state = CaseMilestoneState()

    if not isinstance(state.statuses, dict):
        state.statuses = _default_milestone_progress()

    for milestone_id in MILESTONE_ID_ORDER:
        if milestone_id not in state.statuses:
            state.statuses[milestone_id] = MilestoneProgressState()
    return state
