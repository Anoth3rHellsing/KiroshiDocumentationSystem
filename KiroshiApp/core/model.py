"""Data model helpers for the experimental desktop prototype."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence
import uuid


__all__ = [
    "RemoteSessionEntry",
    "TrackingData",
    "CaseData",
]


def _utc_now_z() -> str:
    """Return the current UTC time in ISO-8601 format with a ``Z`` suffix."""

    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.isoformat().replace("+00:00", "Z")


def _normalize_hardware_test_text(value: object) -> str:
    """Return a text representation for stored hardware test values."""

    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return ""
    return str(value).strip()


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

    def to_dict(self) -> dict[str, str]:
        """Return a serialisable mapping for the entry."""

        return {
            "session_id": self.session_id,
            "title": self.title,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _coerce_remote_session_entry(payload: object, *, default_title: str) -> RemoteSessionEntry:
    """Return a ``RemoteSessionEntry`` built from loose mapping data."""

    if isinstance(payload, RemoteSessionEntry):
        return RemoteSessionEntry(
            session_id=payload.session_id or uuid.uuid4().hex,
            title=str(payload.title or default_title),
            notes=str(payload.notes or ""),
            created_at=str(payload.created_at or _utc_now_z()),
            updated_at=str(payload.updated_at or payload.created_at or _utc_now_z()),
        )
    if isinstance(payload, Mapping):
        created = str(payload.get("created_at") or "")
        if not created:
            created = _utc_now_z()
        updated = str(payload.get("updated_at") or "") or created
        return RemoteSessionEntry(
            session_id=str(payload.get("session_id") or uuid.uuid4().hex),
            title=str(payload.get("title") or default_title),
            notes=str(payload.get("notes") or ""),
            created_at=created,
            updated_at=updated,
        )
    if isinstance(payload, str):
        return RemoteSessionEntry(title=default_title, notes=payload)
    return RemoteSessionEntry(title=default_title)


def _normalize_remote_session_list(raw_sessions: Iterable[object] | None) -> list[RemoteSessionEntry]:
    """Convert raw session payloads into dataclass entries."""

    if not raw_sessions or isinstance(raw_sessions, (str, bytes)):
        return []

    normalized: list[RemoteSessionEntry] = []
    for payload in raw_sessions:
        default_title = f"Session {len(normalized) + 1}"
        normalized.append(
            _coerce_remote_session_entry(payload, default_title=default_title)
        )
    return normalized


PRIORITY_OPTIONS = ["Low", "Normal", "High", "On Time", "Escalation"]
DEFAULT_TRACKING_PRIORITY = "Normal"


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
            if getattr(self, field_name) is None:
                setattr(self, field_name, "")

    def to_dict(self) -> dict[str, object]:
        """Return a serialisable mapping for the tracking data."""

        return asdict(self)


@dataclass
class CaseData:
    """Container for case details provided through the UI."""

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
    email_selected_template: str = ""
    email_tone: str = "neutral"
    email_audience: str = "customer"
    email_custom_prompt: str = ""
    email_last_body: str = ""
    email_second_line_mode: bool = False
    email_draft: str = ""
    additional_info: str = ""
    customer_trios_only: bool = False
    support_fee_accepted: bool = False
    hardware_test: str = ""
    service_tag: str = ""
    pc_model: str = ""
    windows_version: str = ""
    bios_version: str = ""
    graphics_card: str = ""
    processor: str = ""
    warranty: str = ""
    scanner_sn: str = ""
    base_sn: str = ""
    trios_module_version: str = ""
    dongle_deployment_date: str = ""
    scanner_previous_replacements: int = 0
    scanner_accidental_damage: str = ""
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
    kiroshi_version: str = ""
    last_modified: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.tracking, TrackingData):
            pass
        elif isinstance(self.tracking, Mapping):
            self.tracking = TrackingData(**dict(self.tracking))
        else:
            self.tracking = TrackingData()
        self.hardware_test = _normalize_hardware_test_text(self.hardware_test)
        self.remote_sessions = _normalize_remote_session_list(self.remote_sessions)
        if self.remote_steps and not self.remote_sessions:
            self.remote_sessions = _normalize_remote_session_list([self.remote_steps])

    def validate(self) -> None:
        """Validate the case payload. Raises ``ValueError`` on invalid data."""

        if not isinstance(self.case_id, str):
            raise ValueError("case_id must be a string")
        if not isinstance(self.company_name, str):
            raise ValueError("company_name must be a string")
        for entry in self.remote_sessions:
            if not isinstance(entry, RemoteSessionEntry):
                raise ValueError("remote_sessions must contain RemoteSessionEntry instances")

    def to_dict(self) -> dict[str, object]:
        """Return a serialisable mapping representing the case."""

        payload = asdict(self)
        payload["remote_sessions"] = [entry.to_dict() for entry in self.remote_sessions]
        payload["tracking"] = self.tracking.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "CaseData":
        """Instantiate a case from a plain mapping."""

        data = dict(payload)
        tracking_payload = data.get("tracking")
        if isinstance(tracking_payload, Mapping):
            data["tracking"] = TrackingData(**tracking_payload)
        remote_payload = data.get("remote_sessions")
        if isinstance(remote_payload, Sequence) and not isinstance(remote_payload, (str, bytes)):
            data["remote_sessions"] = _normalize_remote_session_list(remote_payload)
        return cls(**data)
