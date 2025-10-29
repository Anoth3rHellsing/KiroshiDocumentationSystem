"""Dataclasses describing the core domain model for the desktop client."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import ClassVar, Iterable, Mapping, Sequence

from .utils import utc_now_iso

PRIORITY_OPTIONS = ["Low", "Normal", "High", "On Time", "Escalation"]
DEFAULT_TRACKING_PRIORITY = "Normal"
DEFAULT_APP_VERSION = "Release 1.7.2"


def _utc_now_z() -> str:
    """Return an ISO-8601 timestamp with a ``Z`` suffix."""

    return utc_now_iso().replace("+00:00", "Z")


def _normalize_hardware_test_text(value: object) -> str:
    """Return a clean text snippet describing the hardware test results."""

    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return ""
    return str(value).strip()


def _normalize_damage_classification(value: object) -> str:
    """Return a human readable scanner damage classification."""

    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        normalized = text.lower()
        if normalized in {"accidental", "accidental damage", "y", "yes", "true", "1"}:
            return "Accidental damage"
        if normalized in {"internal", "internal damage", "n", "no", "false", "0", "none"}:
            return "Internal damage"
        return text
    if isinstance(value, bool):
        return "Accidental damage" if value else "Internal damage"
    if isinstance(value, (int, float)):
        return "Accidental damage" if value else "Internal damage"
    text = str(value).strip()
    return text if text else ""


@dataclass
class RemoteSessionEntry:
    """Structured representation of a remote troubleshooting session."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    notes: str = ""
    created_at: str = field(default_factory=_utc_now_z)
    updated_at: str = field(default_factory=_utc_now_z)

    def display_title(self, index: int) -> str:
        title = (self.title or "").strip()
        return title or f"Session {index}"

    def touch(self) -> None:
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


def _coerce_remote_session_entry(payload: object, *, default_title: str) -> RemoteSessionEntry:
    if isinstance(payload, RemoteSessionEntry):
        entry = RemoteSessionEntry(
            session_id=(payload.session_id or uuid.uuid4().hex),
            title=str(payload.title or default_title),
            notes=str(payload.notes or ""),
            created_at=str(payload.created_at or _utc_now_z()),
            updated_at=str(payload.updated_at or payload.created_at or _utc_now_z()),
        )
    elif isinstance(payload, Mapping):
        created = str(payload.get("created_at") or "")
        if not created:
            created = _utc_now_z()
        updated = str(payload.get("updated_at") or "")
        if not updated:
            updated = created
        entry = RemoteSessionEntry(
            session_id=str(payload.get("session_id") or uuid.uuid4().hex),
            title=str(payload.get("title") or default_title),
            notes=str(payload.get("notes") or ""),
            created_at=created,
            updated_at=updated,
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


def _normalize_remote_session_list(raw_sessions: Iterable[object] | None) -> list[RemoteSessionEntry]:
    if not raw_sessions or isinstance(raw_sessions, (str, bytes)):
        return []
    normalized: list[RemoteSessionEntry] = []
    for payload in raw_sessions:
        default_title = f"Session {len(normalized) + 1}"
        normalized.append(_coerce_remote_session_entry(payload, default_title=default_title))
    return normalized


def format_remote_sessions_summary(
    sessions: Sequence[RemoteSessionEntry], *, include_timestamps: bool = True
) -> str:
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
    kiroshi_version: str = DEFAULT_APP_VERSION
    last_modified: str = ""

    REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = (
        "case_id",
        "company_name",
        "brief_description",
    )

    def __post_init__(self) -> None:
        self.hardware_test = _normalize_hardware_test_text(self.hardware_test)

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
            self.kiroshi_version = DEFAULT_APP_VERSION
        if self.tracking.priority not in PRIORITY_OPTIONS:
            self.tracking.priority = DEFAULT_TRACKING_PRIORITY
        if self.last_modified is None:
            self.last_modified = ""
        elif not isinstance(self.last_modified, str):
            self.last_modified = str(self.last_modified)

        self.scanner_accidental_damage = _normalize_damage_classification(
            getattr(self, "scanner_accidental_damage", "")
        )

        self._missing_required = [
            name for name in self.REQUIRED_FIELDS if not getattr(self, name)
        ]

    def validate(self) -> None:
        if self._missing_required:
            raise ValueError(
                "Missing required fields: " + ", ".join(self._missing_required)
            )

    @property
    def missing_required_fields(self) -> list[str]:
        return list(self._missing_required)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["remote_sessions"] = [asdict(entry) for entry in self.remote_sessions]
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str | Mapping[str, object]) -> "CaseData":
        if isinstance(payload, str):
            data = json.loads(payload)
        else:
            data = dict(payload)
        if not isinstance(data, Mapping):
            raise TypeError("CaseData.from_json expects a mapping or JSON string")
        field_names = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered)
