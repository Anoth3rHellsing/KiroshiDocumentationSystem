
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import types
import dataclasses
import copy
from datetime import datetime

# Mock dependencies before importing the app
st_mock = MagicMock()
st_mock.session_state = MagicMock()
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
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Mock st.cache_data/resource to do nothing (passthrough)
def cache_mock(func_or_options=None, *args, **kwargs):
    if callable(func_or_options):
        return func_or_options
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_mock
st_mock.cache_resource = cache_mock
st_mock.error = MagicMock()

# Patch json.dump
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        if isinstance(obj, MagicMock):
            return
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = safe_json_dump

# Patch dataclasses.asdict
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

# Patch deepcopy
original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock):
        return x
    return original_deepcopy(x, memo)
copy.deepcopy = safe_deepcopy

sys.path.append(".")
import case_documentation_app

class TestSortingOptimization(unittest.TestCase):
    def test_sorting_optimization(self):
        # Mock Path.exists to return True
        with patch("pathlib.Path.exists", return_value=True), \
             patch("case_documentation_app.DATABASE_DIR", Path("/mock/db")), \
             patch("case_documentation_app.TRACKED_CASES_DIR", Path("/mock/tracked")):

            # Create mock entries for os.scandir
            entry1 = MagicMock()
            entry1.is_file.return_value = True
            entry1.name = "case1.json"
            entry1.path = "/mock/db/case1.json"
            entry1.stat.return_value.st_mtime = 1000.0

            entry2 = MagicMock()
            entry2.is_file.return_value = True
            entry2.name = "case2.json"
            entry2.path = "/mock/db/case2.json"
            entry2.stat.return_value.st_mtime = 2000.0

            # Mock os.scandir context manager
            scandir_mock = MagicMock()
            scandir_mock.__enter__.return_value = [entry1, entry2]
            scandir_mock.__exit__.return_value = None

            # Mock Path.read_text
            def read_text_side_effect(encoding="utf-8"):
                # We can't easily know which path called us in the side effect without more complex mocking,
                # but we can rely on order or mock Path constructor.
                # simpler: patch Path constructor or assume usage pattern.
                return "{}"

            # Better approach: Patch Path to return specific mocks for specific paths
            with patch("case_documentation_app.os.scandir", return_value=scandir_mock), \
                 patch("pathlib.Path.read_text") as mock_read:

                # Setup return values for read_text based on calls is tricky.
                # Instead, we can mock _coerce_case_mapping to return data directly.

                # Case 1: Older
                data1 = {
                    "case_id": "C1",
                    "brief_description": "Old Case",
                    "last_modified": "2023-01-01T10:00:00" # ts roughly 1672567200
                }
                # Case 2: Newer
                data2 = {
                    "case_id": "C2",
                    "brief_description": "New Case",
                    "last_modified": "2023-01-02T10:00:00" # ts roughly 1672653600
                }

                def read_side_effect():
                    # This won't work easily as read_text is called on instances.
                    pass

                # We will patch _coerce_case_mapping which processes the JSON payload.
                # But we need read_text to return valid JSON.
                mock_read.return_value = "{}"

                with patch("case_documentation_app._coerce_case_mapping", side_effect=[data1, data2]):
                    # Reset cache
                    cache = case_documentation_app._get_global_case_cache()
                    cache.data.clear()
                    cache.last_scan_ts = 0.0

                    # Force throttle expiry
                    throttle = case_documentation_app._get_refresh_throttle()
                    throttle.last_run = 0.0

                    # Run
                    cases = case_documentation_app._refresh_and_get_cases()

                    print(f"Loaded {len(cases)} cases.")

                    # Verify
                    self.assertEqual(len(cases), 2)
                    self.assertEqual(cases[0]["case_id"], "C2") # Newer first
                    self.assertEqual(cases[1]["case_id"], "C1")

                    # Check for _updated_ts
                    # NOTE: This assertion will FAIL until we implement the optimization
                    if "_updated_ts" in cases[0]:
                        print("Optimization present: _updated_ts found.")
                        self.assertIsInstance(cases[0]["_updated_ts"], float)
                        self.assertTrue(cases[0]["_updated_ts"] > cases[1]["_updated_ts"])
                    else:
                        print("Optimization MISSING: _updated_ts not found.")
                        self.fail("_updated_ts missing")

if __name__ == "__main__":
    unittest.main()
