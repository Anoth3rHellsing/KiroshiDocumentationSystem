"""Regression tests covering hardware test value migration."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from tests.test_pdf_exports import _install_streamlit_stubs


def _load_app_module():
    """Import ``case_documentation_app`` with Streamlit stubs installed."""

    _install_streamlit_stubs()
    sys.modules.pop("case_documentation_app", None)
    module_path = Path(__file__).resolve().parent.parent / "case_documentation_app.py"
    spec = importlib.util.spec_from_file_location("case_documentation_app", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None  # for mypy/static checkers
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def test_migrate_hardware_test_converts_existing_booleans():
    app = _load_app_module()
    st = app.st

    # Simulate legacy session data with boolean hardware test fields.
    case = app.CaseData()
    case.hardware_test = False  # type: ignore[assignment]
    st.session_state.case = case
    st.session_state.case_sessions = [app.CaseSession(case=case)]
    st.session_state["hardware_test"] = False
    st.session_state["hardware_test_0"] = True

    app._migrate_hardware_test_state()

    assert st.session_state["hardware_test"] == "No"
    assert st.session_state["hardware_test_0"] == "Yes"
    assert st.session_state.case.hardware_test == "No"
    assert st.session_state.case_sessions[0].case.hardware_test == "No"


def test_load_case_state_normalises_per_case_widget_state():
    app = _load_app_module()
    st = app.st

    case_a = app.CaseData()
    case_b = app.CaseData()

    # Reintroduce legacy boolean payloads that may remain in session memory.
    case_a.hardware_test = "Passed"
    case_b.hardware_test = True  # type: ignore[assignment]

    st.session_state.case_sessions = [
        app.CaseSession(case=case_a),
        app.CaseSession(case=case_b),
    ]
    st.session_state.case = case_a
    st.session_state.uploads = []
    st.session_state.log_uploads = []
    st.session_state.screenshots = []
    st.session_state.attachments_index = app._default_attachments_index()

    app.load_case_state(1)

    assert st.session_state.case.hardware_test == "Yes"
    assert st.session_state.case_sessions[1].case.hardware_test == "Yes"
    state_key = app.widget_state_key("hardware_test", 1)
    assert st.session_state[state_key] == "Yes"
