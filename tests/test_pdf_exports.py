"""PDF export integration tests."""
from __future__ import annotations

import base64
import io
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util

import pandas as pd
import pytest

try:  # pragma: no cover - optional dependency during CI runs
    from pdfminer.high_level import extract_text as _pdfminer_extract_text
except ModuleNotFoundError:  # pragma: no cover - fallback when pdfminer is unavailable
    _pdfminer_extract_text = None


class _MagicStub:
    """Very small callable/attribute stub used to fake Streamlit APIs."""

    def __call__(self, *args, **kwargs):
        for key in ("value", "default"):
            if key in kwargs:
                return kwargs[key]
        if args:
            return args[0] if not isinstance(args[0], (list, tuple, dict)) else self
        return self

    def __getattr__(self, _name):  # pragma: no cover - convenience access
        return self

    def __enter__(self):  # pragma: no cover - context support
        return self

    def __exit__(self, *exc):  # pragma: no cover - context support
        return False

    def __iter__(self):  # pragma: no cover - allow unpacking loops
        return iter(())

    def __len__(self):  # pragma: no cover - treat stub as empty container
        return 0

    def __bool__(self):  # pragma: no cover - default falsy semantics
        return False


class _SessionState(dict):
    """Lightweight mapping mimicking ``st.session_state`` semantics."""

    def __getattr__(self, name):  # pragma: no cover - fallback attribute access
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover - mimic AttributeError contract
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):  # pragma: no cover - attribute assignment
        self[name] = value


def _install_streamlit_stubs() -> None:
    """Register minimal Streamlit shims for module import."""

    if "streamlit" in sys.modules:
        return

    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.session_state = _SessionState()
    streamlit_stub.session_state.update(
        {
            "show_tutorial": False,
            "tutorial_step": 0,
            "tutorial_metadata": {"visited": [], "total_steps": 0, "last_step": 0},
            "reporter_open": False,
            "incident_context": {},
            "reporter_allow_screenshot": False,
        }
    )
    streamlit_stub.sidebar = _MagicStub()
    streamlit_stub.runtime = _MagicStub()
    streamlit_stub.dialog = lambda *a, **k: _MagicStub()
    streamlit_stub.set_page_config = lambda *a, **k: None
    streamlit_stub.experimental_get_query_params = lambda: {}
    streamlit_stub.experimental_set_query_params = lambda **_k: None
    streamlit_stub.experimental_rerun = lambda: None
    streamlit_stub.experimental_memo = lambda *a, **k: (lambda func: func)
    streamlit_stub.experimental_singleton = lambda *a, **k: (lambda func: func)
    streamlit_stub.cache_data = lambda *a, **k: (lambda func: func)
    streamlit_stub.cache_resource = lambda *a, **k: (lambda func: func)
    streamlit_stub.markdown = lambda *a, **k: None
    streamlit_stub.title = lambda *a, **k: None
    streamlit_stub.header = lambda *a, **k: None
    streamlit_stub.subheader = lambda *a, **k: None
    streamlit_stub.text = lambda *a, **k: None
    streamlit_stub.caption = lambda *a, **k: None
    streamlit_stub.write = lambda *a, **k: None
    streamlit_stub.info = lambda *a, **k: None
    streamlit_stub.warning = lambda *a, **k: None
    streamlit_stub.error = lambda *a, **k: None
    streamlit_stub.success = lambda *a, **k: None
    streamlit_stub.toast = lambda *a, **k: None
    streamlit_stub.stop = lambda: None
    streamlit_stub.rerun = lambda: None
    streamlit_stub.spinner = lambda *a, **k: _MagicStub()
    streamlit_stub.status = lambda *a, **k: _MagicStub()
    streamlit_stub.container = lambda *a, **k: _MagicStub()
    streamlit_stub.expander = lambda *a, **k: _MagicStub()
    streamlit_stub.modal = lambda *a, **k: _MagicStub()
    streamlit_stub.tabs = lambda labels: [_MagicStub() for _ in labels]
    streamlit_stub.columns = lambda spec: [_MagicStub() for _ in range(len(spec) if isinstance(spec, (list, tuple)) else int(spec))]
    streamlit_stub.form = lambda *a, **k: _MagicStub()
    streamlit_stub.form_submit_button = lambda *a, **k: False
    streamlit_stub.button = lambda *a, **k: False
    streamlit_stub.radio = (
        lambda label, options, **kwargs: (options or kwargs.get("options") or [None])[0]
        if options or kwargs.get("options")
        else None
    )
    streamlit_stub.checkbox = lambda *a, **k: k.get("value", False)
    streamlit_stub.toggle = lambda *a, **k: k.get("value", False)
    streamlit_stub.text_input = lambda *a, **k: k.get("value", "")
    streamlit_stub.text_area = lambda *a, **k: k.get("value", "")
    streamlit_stub.selectbox = lambda *a, **k: (k.get("options", [None]) or [None])[0]
    streamlit_stub.select_slider = lambda *a, **k: (k.get("options", [0]) or [0])[0]
    streamlit_stub.multiselect = lambda *a, **k: k.get("default", [])
    streamlit_stub.slider = lambda *a, **k: k.get("value", 0)
    streamlit_stub.number_input = lambda *a, **k: k.get("value", 0)
    streamlit_stub.file_uploader = lambda *a, **k: []
    streamlit_stub.download_button = lambda *a, **k: None
    streamlit_stub.experimental_data_editor = lambda *a, **k: None
    streamlit_stub.dataframe = lambda *a, **k: None
    streamlit_stub.table = lambda *a, **k: None
    streamlit_stub.altair_chart = lambda *a, **k: None
    streamlit_stub.progress = lambda *a, **k: _MagicStub()
    streamlit_stub.image = lambda *a, **k: None

    components_stub = types.ModuleType("streamlit.components")
    components_v1_stub = types.ModuleType("streamlit.components.v1")
    components_v1_stub.html = lambda *a, **k: None
    components_stub.v1 = components_v1_stub

    errors_stub = types.ModuleType("streamlit.errors")

    class StreamlitAPIException(Exception):
        pass

    errors_stub.StreamlitAPIException = StreamlitAPIException

    sys.modules["streamlit"] = streamlit_stub
    sys.modules["streamlit.components"] = components_stub
    sys.modules["streamlit.components.v1"] = components_v1_stub
    sys.modules["streamlit.errors"] = errors_stub


def _install_altair_stub() -> None:
    """Provide the minimal surface used during import when Altair is absent."""

    if "altair" in sys.modules:
        return

    altair_stub = types.ModuleType("altair")

    class _ThemeRegistry:
        def names(self):  # pragma: no cover - simple registry API
            return []

        def register(self, *args, **kwargs):  # pragma: no cover - test helper
            return None

        def enable(self, *args, **kwargs):  # pragma: no cover - test helper
            return None

    altair_stub.themes = _ThemeRegistry()
    altair_stub.Chart = _MagicStub
    altair_stub.LayerChart = _MagicStub
    altair_stub.data_transformers = types.SimpleNamespace(disable_max_rows=lambda: None)
    for attr in ("X", "Y", "Color", "Tooltip", "Scale", "Axis", "encoding"):
        setattr(altair_stub, attr, lambda *a, **k: _MagicStub())

    sys.modules["altair"] = altair_stub


def _install_kiroshi_stub() -> None:
    """Register a lightweight replacement for the chat helper module."""

    if "kiroshi_chat" in sys.modules:
        return

    kiroshi_stub = types.ModuleType("kiroshi_chat")
    kiroshi_stub.SYSTEM_PROMPT = "Kiroshi stub prompt"
    kiroshi_stub.load_memory = lambda *a, **k: {}
    kiroshi_stub.save_memory = lambda *a, **k: None
    kiroshi_stub.query_kiroshi = lambda *a, **k: ""
    kiroshi_stub.load_manual_docs = lambda *a, **k: []
    kiroshi_stub.save_manual_docs = lambda *a, **k: None
    kiroshi_stub.search_manual_docs = lambda *a, **k: []
    kiroshi_stub.get_assistant_notes = lambda *a, **k: ""
    kiroshi_stub.set_assistant_notes = lambda *a, **k: None
    kiroshi_stub.build_assistant_memory_prompt = lambda *a, **k: ""
    kiroshi_stub.build_system_prompt = lambda *a, **k: ""

    sys.modules["kiroshi_chat"] = kiroshi_stub


@pytest.fixture(scope="module")
def app_module():
    _install_streamlit_stubs()
    _install_altair_stub()
    _install_kiroshi_stub()
    spec = importlib.util.spec_from_file_location(
        "case_documentation_app",
        Path(__file__).resolve().parent.parent / "case_documentation_app.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def dense_case(app_module):
    long_text = "🚀" * 200 + " — Multilingual résumé: 日本語, العربية, עברית."
    attachment_blob = "attachment" * 100
    remote_entry = app_module.RemoteSessionEntry(
        title="Γρήγορη συνεδρία",
        notes="Σημειώσεις: múltiples idiomas y detalles técnicos detallados.",
    )
    tracking = app_module.TrackingData(
        active=True,
        type="Escalation",
        category="Critical",
        status="Investigating",
        ticket_number="BUG-123456789",
        creation_day="2024-12-24",
        case_link="https://intranet.example.com/cases/BUG-123456789",
        expected_arrival_date="2024-12-31",
        service_tag="SVC-TAG-Ω≈ç√∫˜µ≤≥÷",
    )
    case = app_module.CaseData(
        company_name="株式会社テスト",
        subscription_id="SUB-∞",
        brief_description="Extremely detailed hardware diagnostics.",
        case_id="CASE-987654",
        application_version="v2024.11.0",
        description=long_text,
        caller_name="Zoë Ångström",
        phone_description=long_text,
        dongle_number="Δ1234567890",
        phone_number="+1 (555) 010-1234",
        teamviewer_id="TV-⊕-ID",
        teamviewer_password="密码-安全",
        email="support@example.com",
        internal_helpjuice=long_text,
        internal_logs=attachment_blob,
        remote_sessions=[remote_entry],
        remote_steps="Reproduced multiple issues across locales.",
        root_cause="GPU driver buffer overflow",
        solution="Applied patched firmware with checksum validation.",
        request_issue="Device intermittently overheats",
        contact_name="Людмила",
        office_ph="+45 12 34 56",
        direct_ph="+45 98 76 54",
        best_time="16:00",
        patterson="Yes",
        straumann="No",
        esc_name="Ing. Peñaranda",
        esc_ph="+34 600 123 456",
        esc_email="ing.p@example.com",
        additional_info=long_text,
        customer_trios_only=True,
        support_fee_accepted=True,
        hardware_test=True,
        service_tag="SRV-112233",
        pc_model="Alienware Aurora",
        windows_version="Windows 11 Pro",
        bios_version="1.2.3",
        graphics_card="RTX 5090",
        processor="ThreadRipper 9990X",
        warranty="2026-12-31",
        scanner_sn="SCAN-0001",
        base_sn="BASE-0001",
        trios_module_version="5.6.7",
        dongle_deployment_date="2023-08-15",
        scanner_previous_replacements=3,
        scanner_accidental_damage=False,
        tracking=tracking,
    )
    return case


def _extract_text_fallback(pdf_bytes: bytes) -> str:
    import re
    import zlib

    snippets: list[str] = []
    pattern = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
    for match in pattern.finditer(pdf_bytes):
        chunk = match.group(1)
        for prefix in (b"\r\n", b"\n", b"\r"):
            if chunk.startswith(prefix):
                chunk = chunk[len(prefix) :]
        try:
            chunk = zlib.decompress(chunk)
        except zlib.error:
            pass
        for text_bytes in re.findall(rb"\(([^()]*)\)", chunk):
            try:
                snippets.append(text_bytes.decode("utf-8"))
            except UnicodeDecodeError:
                snippets.append(text_bytes.decode("latin-1", errors="ignore"))
    return " ".join(snippets)


def _pdf_text(pdf_bytes: bytes) -> str:
    assert pdf_bytes, "Generated PDF was empty"
    if _pdfminer_extract_text:
        return _pdfminer_extract_text(io.BytesIO(pdf_bytes))
    return _extract_text_fallback(pdf_bytes)


def test_make_pdf_contains_expected_sections(app_module, dense_case):
    cat_map = app_module.BASE_CATEGORY_MAP | app_module.HW_CATEGORY_MAP
    pdf_bytes = app_module.make_pdf(dense_case, cat_map)
    text = _pdf_text(pdf_bytes)
    for heading in ("HEADER", "PHONECALL", "PC HARDWARE", "SCANNER HARDWARE"):
        assert heading in text
    assert "Zoë Ångström" in text
    assert "GPU driver buffer overflow" in text


def test_make_tables_pdf_uses_session_summary(app_module, dense_case):
    app_module.st.session_state["categorizer_summary"] = {
        "product": "Scanner",
        "topic": "Calibration",
        "subtopic": "Optics",
    }
    pdf_bytes = app_module.make_tables_pdf(dense_case)
    text = _pdf_text(pdf_bytes)
    assert "Product" in text
    assert "Calibration" in text
    assert "Responsible contact" in text


def test_incident_report_pdf_includes_metadata(app_module):
    context = {
        "section": "Case tab",
        "tab": "Tables",
        "trigger": "export",
        "timestamp": "2024-04-05T16:30:00Z",
        "case_index": 1,
        "exception": "ValueError('bad state')",
        "stacktrace": "Traceback (most recent call last):\nValueError: bad state",
    }
    logs = "INFO Ready\nERROR Failure captured"
    user_notes = "Operator observed spikes during QA."
    case_snapshot = [
        {
            "Case": "CASE-42",
            "Company": "Acme Labs",
            "Summary": "Cooling issue",
            "Priority": "High",
            "Active": "Yes",
        }
    ]
    screenshot_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
    )
    screenshot = app_module.InMemoryUploadedFile(name="screen.png", data=screenshot_png)

    pdf_bytes = app_module.build_incident_report_pdf(
        context,
        logs,
        user_notes,
        case_snapshot,
        screenshot=screenshot,
    )
    text = _pdf_text(pdf_bytes)
    assert "Kiroshi Incident Report" in text
    assert "Case index" in text
    assert "Operator observed spikes" in text
    assert "CASE-42" in text


def test_ai_educate_pdf_handles_rich_and_sparse_inputs(app_module):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    timeline = pd.DataFrame(
        {
            "timestamp": [now - timedelta(days=i) for i in range(3)],
            "count": [5, 3, 8],
        }
    )
    counts_recent = pd.DataFrame(
        {
            "analysis_label": ["Login failure", "Scanner overheating"],
            "count": [7, 4],
        }
    )
    counts_all = pd.DataFrame(
        {
            "analysis_label": ["Login failure", "Scanner overheating", "Calibration drift"],
            "count": [15, 9, 3],
        }
    )
    recurring = counts_all[counts_all["count"] >= 3].rename(
        columns={"analysis_label": "case"}
    )
    scanners = pd.DataFrame({"scanner": ["Trios 5"], "count": [6]})
    bug_cases = pd.DataFrame(
        {
            "case_id": ["CASE-99"],
            "title": ["Scanner misalignment"],
            "saved_at": [now],
        }
    )
    insights_rich = {
        "view_totals": {
            "30d": {"case_total": 10, "unique_labels": 2, "bug_solution_count": 1, "bug_mentions_count": 1},
            "all_time": {"case_total": 25, "unique_labels": 3, "bug_solution_count": 4, "bug_mentions_count": 5},
        },
        "counts": {"30d": counts_recent, "all_time": counts_all},
        "timeline": timeline,
        "timeline_all": timeline,
        "recurring_issue_types": recurring,
        "common_scanner_models": scanners,
        "bug_cases": bug_cases,
        "highlight_label": "Login failure",
        "highlight_count": 7,
        "highlight_case": {
            "case_id": "CASE-1",
            "title": "Login failure",
            "solution_excerpt": "Reset cache",
        },
    }
    bug_report = {
        "summary": "Detector flagged several recurring login issues.",
        "recurring_patterns": [
            {"pattern": "Login failure", "count": 5},
            {"pattern": "Scanner overheating", "count": 2},
        ],
    }

    rich_pdf = app_module.generate_ai_educate_report_pdf(insights_rich, bug_report)
    rich_text = _pdf_text(rich_pdf)
    assert "AI Educate" in rich_text
    assert "Patrones recurrentes" in rich_text or "Patrón" in rich_text
    assert "Detector" in rich_text

    sparse_insights = {"view_totals": {}, "counts": {}, "timeline": pd.DataFrame(), "timeline_all": pd.DataFrame()}
    sparse_pdf = app_module.generate_ai_educate_report_pdf(sparse_insights, None)
    sparse_text = _pdf_text(sparse_pdf)
    assert "AI Educate" in sparse_text
