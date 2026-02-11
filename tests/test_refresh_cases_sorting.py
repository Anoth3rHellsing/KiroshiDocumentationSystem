
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import time
from pathlib import Path
import datetime
import dataclasses
import copy

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Mocking dependencies ---
st_mock = MagicMock()
st_mock.session_state = MagicMock()
st_mock.session_state.get = MagicMock(return_value=None)
# Ensure dictionary-like behavior for session_state
st_mock.session_state.__getitem__ = MagicMock(return_value=None)

sys.modules["streamlit"] = st_mock
sys.modules["streamlit.errors"] = MagicMock()
class StreamlitAPIException(Exception): pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["cryptography"] = MagicMock()

# Mock st.cache_data/resource to do nothing (passthrough)
def cache_decorator_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
         return args[0]
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_decorator_mock
st_mock.cache_resource = cache_decorator_mock

# Patch json.dump to avoid writing mocks to disk during import side-effects
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        if isinstance(obj, MagicMock): return
        original_json_dump(obj, fp, **kwargs)
    except TypeError: pass
json.dump = safe_json_dump

# Patch dataclasses.asdict to handle mocks
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock): return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

# Patch deepcopy to handle mocks
original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock): return x
    return original_deepcopy(x, memo)
copy.deepcopy = safe_deepcopy

# --- Import app under test ---
# We patch pathlib.Path.mkdir/write_text to avoid actual filesystem calls during import
with patch("pathlib.Path.mkdir"), \
     patch("pathlib.Path.write_text"):
    import case_documentation_app

class TestRefreshCasesSorting(unittest.TestCase):
    def test_sorting_optimization(self):
        """
        Verify that _refresh_and_get_cases adds _updated_ts and sorts correctly.
        """

        # Define some mock case files with different times
        # Times are UTC for simplicity
        case1_time = datetime.datetime(2023, 1, 1, 12, 0, 0)
        case2_time = datetime.datetime(2023, 1, 2, 12, 0, 0) # Newer
        case3_time = datetime.datetime(2023, 1, 1, 10, 0, 0) # Older

        mock_files = {
            os.path.abspath("/data/case1.json"): {
                "case_id": "case1",
                "last_modified": case1_time.isoformat(),
                "brief_description": "Case 1"
            },
            os.path.abspath("/data/case2.json"): {
                "case_id": "case2",
                "last_modified": case2_time.isoformat(),
                "brief_description": "Case 2"
            },
            os.path.abspath("/data/case3.json"): {
                "case_id": "case3",
                "last_modified": case3_time.isoformat(),
                "brief_description": "Case 3"
            }
        }

        # Mock os.scandir entries
        mock_entries = []
        for path, data in mock_files.items():
            entry = MagicMock()
            entry.is_file.return_value = True
            entry.name = Path(path).name
            entry.path = path
            # Set mtime to timestamp of last_modified
            ts = datetime.datetime.fromisoformat(data["last_modified"]).timestamp()
            entry.stat.return_value.st_mtime = ts
            mock_entries.append(entry)

        # Mock Path.read_text
        original_read_text = Path.read_text
        def mock_read_text(self_path, encoding="utf-8", errors=None):
            s_path = str(self_path.resolve())
            if s_path in mock_files:
                return json.dumps(mock_files[s_path])
            # Fallback to verify key matching if resolving fails or differs
            for k, v in mock_files.items():
                if str(Path(k)) == str(self_path):
                     return json.dumps(v)
            return "{}"

        # Mock Cache Object
        mock_throttle = MagicMock()
        mock_throttle.last_run = 0.0 # Force refresh
        mock_throttle.data = []

        # We also need to mock _get_global_case_cache because it is used in the function
        # The function creates a new cache if not cached, but since we mocked st.cache_resource,
        # it returns a new object every time unless we patch the function itself.

        # Wait, if we mocked @st.cache_resource to be a passthrough, then _get_global_case_cache
        # just executes the function body, which returns a new GlobalCaseCache().
        # This is fine, as long as it behaves like a cache object.

        scan_context = MagicMock()
        scan_context.__enter__.return_value = mock_entries
        scan_context.__exit__.return_value = None

        with patch("case_documentation_app._get_refresh_throttle", return_value=mock_throttle), \
             patch("os.scandir", return_value=scan_context), \
             patch("pathlib.Path.read_text", side_effect=mock_read_text, autospec=True), \
             patch("pathlib.Path.exists", return_value=True):

            # Execute
            cases = case_documentation_app._refresh_and_get_cases()

            # Check sorting order: case2 (newest) -> case1 -> case3 (oldest)
            self.assertEqual(len(cases), 3)
            self.assertEqual(cases[0]["case_id"], "case2", f"Expected case2, got {cases[0]['case_id']}")
            self.assertEqual(cases[1]["case_id"], "case1", f"Expected case1, got {cases[1]['case_id']}")
            self.assertEqual(cases[2]["case_id"], "case3", f"Expected case3, got {cases[2]['case_id']}")

            # Verify optimization key
            self.assertIn("_updated_ts", cases[0], "Optimization key _updated_ts is missing")
            self.assertIsInstance(cases[0]["_updated_ts"], float)
            self.assertEqual(cases[0]["_updated_ts"], case2_time.timestamp())

if __name__ == "__main__":
    unittest.main()
