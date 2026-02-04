
import sys
import unittest
from unittest.mock import MagicMock, patch, call
import dataclasses
import copy
import json
import os
from pathlib import Path

# --- Mocking Setup Start ---
st_mock = MagicMock()
# Mock session_state as a MagicMock to allow attribute access
st_mock.session_state = MagicMock()
# Ensure dictionary-like behavior for session_state
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.get = MagicMock(return_value=None)

sys.modules["streamlit"] = st_mock
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock caching decorators
def cache_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_mock
st_mock.cache_resource = cache_mock
st_mock.error = MagicMock()
st_mock.sidebar = MagicMock()
st_mock.columns = MagicMock(return_value=[MagicMock(), MagicMock()])

# Define StreamlitAPIException
class StreamlitAPIException(Exception):
    pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Patch json.dump
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    if isinstance(obj, MagicMock): return
    try:
        original_json_dump(obj, fp, **kwargs)
    except TypeError: pass
json.dump = safe_json_dump

# Patch dataclasses.asdict
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock): return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

# Patch copy.deepcopy
original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock): return x
    return original_deepcopy(x, memo)
copy.deepcopy = safe_deepcopy

# --- Import App ---
# We need to set KIROSHI_DB_DIR env var to avoid touching real files during import if possible
# or just patch things.
os.environ["KIROSHI_DB_DIR"] = "/tmp/kiroshi_test_ux"
import case_documentation_app
from case_documentation_app import render_dashboard

class TestDashboardUX(unittest.TestCase):
    def setUp(self):
        st_mock.reset_mock()
        st_mock.columns.return_value = [MagicMock(), MagicMock()]

    @patch("case_documentation_app.load_tracked_cases")
    @patch("case_documentation_app.recent_tracked_files")
    @patch("case_documentation_app._refresh_wellness_reminder_state")
    @patch("case_documentation_app.render_tracked_cases_dashboard") # mock this to avoid complex internal logic
    def test_recent_files_render_buttons(self, mock_render_tracked, mock_wellness, mock_recent, mock_load_tracked):
        # Setup data
        mock_load_tracked.return_value = []
        mock_wellness.return_value = {}

        # Recent files returns Paths
        case1 = Path("/path/to/Case1.json")
        case2 = Path("/path/to/Case2.json")
        mock_recent.return_value = [case1, case2]

        # Capture columns
        col_name = MagicMock()
        col_action = MagicMock()
        st_mock.columns.side_effect = lambda spec, **kwargs: [col_name, col_action] if spec == [4, 1] else [MagicMock(), MagicMock()]

        # Run function
        render_dashboard()

        # Verification
        # 1. Verify buttons created
        self.assertEqual(col_action.button.call_count, 2)

        # 2. Check logic
        calls = col_action.button.call_args_list

        # Button 1
        args, kwargs = calls[0]
        self.assertEqual(args[0], "📂")
        self.assertIn("key", kwargs)
        self.assertIn("dashboard_load_recent_Case1", kwargs["key"])
        self.assertEqual(kwargs["help"], "Load this case")

        # Button 2
        args, kwargs = calls[1]
        self.assertEqual(args[0], "📂")
        self.assertIn("key", kwargs)
        self.assertIn("dashboard_load_recent_Case2", kwargs["key"])

        # 3. Verify caption
        self.assertEqual(col_name.caption.call_count, 2)
        col_name.caption.assert_any_call("Case1", help=str(case1))

if __name__ == "__main__":
    unittest.main()
