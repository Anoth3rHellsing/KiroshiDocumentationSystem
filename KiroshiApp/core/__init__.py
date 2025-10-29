"""Core packages for the experimental desktop client."""
from .ai_client import AIClient, AIMode

try:  # pragma: no cover - optional dependency in headless environments
    from .attachments import (
        add_attachment,
        attachments_root,
        create_zip,
        iter_attachments,
        remove_attachment,
        sanitize_filename,
    )
except Exception as exc:  # pragma: no cover - expose lazy errors when used
    def _missing(*_args, **_kwargs):
        raise RuntimeError("Attachments support unavailable") from exc

    add_attachment = attachments_root = create_zip = iter_attachments = _missing
    remove_attachment = sanitize_filename = _missing
from .model import (
    CaseData,
    RemoteSessionEntry,
    TrackingData,
    format_remote_sessions_summary,
)
from .pdf_generator import CasePdfBuilder, generate_case_pdf
from .storage import (
    autosave_path,
    create_autosave_snapshot,
    load_autosave,
    load_case,
    save_autosave,
    save_case,
)
from .tracking import (
    TrackedCaseRecord,
    list_tracked_cases,
    start_tracking,
    update_tracked_case,
)
from .utils import (
    ensure_directory,
    format_timestamp,
    get_database_root,
    load_global_config,
    save_global_config,
    setup_logging,
    utc_now,
    utc_now_iso,
)

__all__ = [
    "AIClient",
    "AIMode",
    "CaseData",
    "RemoteSessionEntry",
    "TrackingData",
    "CasePdfBuilder",
    "generate_case_pdf",
    "add_attachment",
    "attachments_root",
    "create_zip",
    "iter_attachments",
    "remove_attachment",
    "sanitize_filename",
    "autosave_path",
    "create_autosave_snapshot",
    "load_autosave",
    "load_case",
    "save_autosave",
    "save_case",
    "TrackedCaseRecord",
    "list_tracked_cases",
    "start_tracking",
    "update_tracked_case",
    "ensure_directory",
    "format_timestamp",
    "get_database_root",
    "load_global_config",
    "save_global_config",
    "setup_logging",
    "utc_now",
    "utc_now_iso",
    "format_remote_sessions_summary",
]
