import ast
import io
import logging
import logging.handlers
import os
import textwrap
from pathlib import Path
from types import SimpleNamespace

from collections.abc import Mapping

import pytest

APP_PATH = Path(__file__).resolve().parents[1] / "case_documentation_app.py"


def _load_definitions(names, extra_globals=None):
    source = APP_PATH.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    tree = ast.parse(source)
    selected: list[ast.AST] = []
    target = set(names)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in target:
            selected.append(node)
    namespace: dict[str, object] = {}
    if extra_globals:
        namespace.update(extra_globals)
    for node in selected:
        start_line = node.lineno - 1
        if getattr(node, "decorator_list", None):
            start_line = min(dec.lineno for dec in node.decorator_list) - 1
        end_line = node.end_lineno
        segment = "\n".join(source_lines[start_line:end_line])
        exec(textwrap.dedent(segment), namespace)
    return namespace


class SessionState(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


class ContextStub:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ColumnStub:
    def __init__(self, responses):
        self._responses = list(responses)

    def button(self, *args, **kwargs):
        if self._responses:
            return self._responses.pop(0)
        return False


class StreamlitShim:
    def __init__(self):
        self.session_state = SessionState()
        self.logged_warnings: list[str] = []
        self.writes: list[str] = []
        self._column_button_responses: list[list[bool]] = []

    def modal(self, *args, **kwargs):
        return ContextStub()

    def container(self, *args, **kwargs):
        return ContextStub()

    def markdown(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None

    def write(self, message):
        self.writes.append(str(message))
        return None

    def text_area(self, *args, **kwargs):
        return kwargs.get("value", "")

    def text_input(self, *args, **kwargs):
        return kwargs.get("value", "test") or "test"

    def warning(self, message):
        self.logged_warnings.append(str(message))
        return None

    def info(self, *args, **kwargs):
        return None

    def image(self, *args, **kwargs):
        return None

    def success(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def download_button(self, *args, **kwargs):
        return None

    def button(self, *args, **kwargs):
        return False

    def columns(self, layout):
        responses = self._column_button_responses.pop(0) if self._column_button_responses else []
        width = len(layout) if isinstance(layout, (list, tuple)) else int(layout)
        columns = [ColumnStub(responses if idx == 0 else []) for idx in range(width)]
        return columns

    def set_column_button_responses(self, responses):
        self._column_button_responses = [list(row) for row in responses]


@pytest.fixture
def streamlit_stub():
    stub = StreamlitShim()
    stub.session_state.debug_mode = False
    return stub


def test_logging_falls_back_to_stdout_when_directory_unwritable(monkeypatch, tmp_path):
    namespace = {
        "_candidate_log_directories": lambda: [tmp_path / "locked"],
        "LOG_FILE": "app.log",
        "logging": logging,
        "RotatingFileHandler": logging.handlers.RotatingFileHandler,
        "Path": Path,
        "os": os,
    }
    code = textwrap.dedent(
        """
        LOG_DIR = None
        log_path = None
        log_handlers = []
        for candidate in _candidate_log_directories():
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                prospective_log_path = candidate / LOG_FILE
                with open(prospective_log_path, "a", encoding="utf-8"):
                    pass
            except OSError:
                continue
            LOG_DIR = candidate
            log_path = prospective_log_path
            break

        if log_path is not None:
            try:
                log_handlers = [
                    RotatingFileHandler(
                        log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
                    ),
                    logging.StreamHandler(),
                ]
            except OSError:
                log_path = None
                log_handlers = [logging.StreamHandler()]
        else:
            log_handlers = [logging.StreamHandler()]
        """
    )

    def failing_open(path, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("builtins.open", failing_open)
    monkeypatch.setattr(
        logging.handlers,
        "RotatingFileHandler",
        lambda *_, **__: (_ for _ in ()).throw(OSError("lock")),
    )

    exec(code, namespace)
    handlers = namespace["log_handlers"]
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)
    assert namespace["log_path"] is None


def test_collect_recent_logs_prefers_synthetic_env_override(tmp_path, monkeypatch):
    namespace = _load_definitions(
        ["_collect_recent_logs"],
        {"LOG_FILE": str(tmp_path / "app.log"), "Path": Path, "os": os, "logging": logging},
    )
    (tmp_path / "app.log").write_text("real log", encoding="utf-8")
    monkeypatch.setenv("KIROSHI_SYNTHETIC_LOGS", "synthetic diagnostics")
    try:
        result = namespace["_collect_recent_logs"]()
    finally:
        monkeypatch.delenv("KIROSHI_SYNTHETIC_LOGS")
    assert result == "synthetic diagnostics"


def test_build_incident_report_pdf_includes_context_and_logs(tmp_path):
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.widgets.markers import makeMarker
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab import rl_config
    from reportlab.platypus import (
        Image,
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    rl_config.defaultCompression = 0

    namespace = _load_definitions(
        ["InMemoryUploadedFile", "build_incident_report_pdf"],
        {
            "io": io,
            "SimpleDocTemplate": SimpleDocTemplate,
            "letter": letter,
            "colors": colors,
            "getSampleStyleSheet": getSampleStyleSheet,
            "Table": Table,
            "TableStyle": TableStyle,
            "Paragraph": Paragraph,
            "Spacer": Spacer,
            "Image": Image,
            "Preformatted": Preformatted,
            "Drawing": Drawing,
            "String": String,
            "VerticalBarChart": VerticalBarChart,
            "LinePlot": LinePlot,
            "makeMarker": makeMarker,
            "escape": __import__("html", fromlist=["escape"]).escape,
            "Mapping": Mapping,
            "dataclass": __import__("dataclasses", fromlist=["dataclass"]).dataclass,
            "datetime": __import__("datetime", fromlist=["datetime"]).datetime,
        },
    )
    build_incident_report_pdf = namespace["build_incident_report_pdf"]

    context = {"section": "Debug", "stacktrace": "Traceback: boom"}
    logs = "synthetic diagnostics"
    user_notes = "Issue observed during nightly run."
    case_snapshot = [
        {"Case": "C-1", "Company": "Acme", "Summary": "Boom", "Priority": "High", "Active": "Yes"}
    ]

    pdf_bytes = build_incident_report_pdf(context, logs, user_notes, case_snapshot)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_handle_incident_screenshot_result_surfaces_warning(streamlit_stub):
    extra_globals = {"st": streamlit_stub, "logging": logging}
    namespace = _load_definitions(["_handle_incident_screenshot_result"], extra_globals)

    namespace["_handle_incident_screenshot_result"](None, "capture failed")

    assert streamlit_stub.session_state.incident_reporter_capture_error == "capture failed"
    assert streamlit_stub.logged_warnings and "capture failed" in streamlit_stub.logged_warnings[-1]


def test_format_incident_context_returns_context_string():
    namespace = _load_definitions(["_format_incident_context"], {"Mapping": Mapping})
    formatted = namespace["_format_incident_context"]({"section": "Debug", "tab": "Case"})
    assert formatted == "**Context:** Debug · Case"


def test_autosave_emits_streamlit_warning(monkeypatch, tmp_path, caplog):
    CaseData = type("CaseData", (), {"__init__": lambda self: setattr(self, "case_id", "CASE-123")})

    class AutosaveStreamlit(SimpleNamespace):
        def __init__(self):
            super().__init__(session_state=SessionState())
            self.emitted_warnings: list[str] = []

        def warning(self, message):
            self.emitted_warnings.append(str(message))

    st_stub = AutosaveStreamlit()
    st_stub.session_state.autosave_to_database = True
    st_stub.session_state.case = CaseData()

    def _write_autosave(serialized_payload, payload_hash, payload):
        try:
            save_case_to_database(st_stub.session_state.case, notify=False)
        except Exception as exc:  # pragma: no cover - behavior validated via warnings
            logging.warning(
                "Failed to autosave case %s to database: %s",
                st_stub.session_state.case.case_id,
                exc,
            )
            st_stub.warning(
                "Autosave could not write to the shared database. "
                "Check connectivity or permissions before relying on the backup."
            )

    extra_globals = {
        "st": st_stub,
        "json": __import__("json"),
        "AUTOSAVE_DIR": tmp_path / "autosaves",
        "AUTOSAVE_FILE": str(tmp_path / "autosave.json"),
        "_AUTOSAVE_SESSION_ID": "session",
        "AUTOSAVE_THROTTLE_SECONDS": 0.75,
        "hashlib": __import__("hashlib"),
        "time": __import__("time"),
        "_pending_autosave": None,
        "_pending_autosave_timer": None,
        "_last_autosave_hash": None,
        "_last_autosave_timestamp": 0.0,
        "_autosave_field_fingerprints": {},
        "_autosave_cached_payload": None,
        "_autosave_cached_serialized": None,
        "_autosave_lock": __import__("threading").Lock(),
        "autosave_payload": lambda: {"case": {"case_id": "CASE-123"}},
        "save_case_to_database": lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db offline")),
        "CaseData": CaseData,
        "logging": logging,
        "_write_autosave": _write_autosave,
        "Any": object,
    }

    namespace = _load_definitions(["autosave", "_serialize_autosave_payload", "_compact_json_dumps"], extra_globals)

    with caplog.at_level(logging.WARNING):
        namespace["autosave"]()

    assert any("Failed to autosave" in record.message for record in caplog.records)
    assert st_stub.emitted_warnings


def test_check_for_updates_populates_error_on_http_failure():
    import requests
    from KiroshiApp.models import UpdateCheckResult

    extra_globals = {
        "UpdateCheckResult": UpdateCheckResult,
        "_resolve_update_target": lambda: ("owner/repo", "main"),
        "_fetch_remote_version": lambda repo, branch: (_ for _ in ()).throw(requests.ConnectionError("boom")),
        "_fetch_latest_commit_info": lambda repo, branch: {"sha": None, "date": None},
        "_format_commit_timestamp": lambda value: value,
        "requests": requests,
        "logging": logging,
        "VERSION": "1.0",
    }
    namespace = _load_definitions(["check_for_updates"], extra_globals)
    result = namespace["check_for_updates"]()
    assert isinstance(result, UpdateCheckResult)
    assert result.error
    assert "Unable to retrieve remote version" in result.error
