
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import datetime
import threading
import copy
import dataclasses

# Mock dependencies before importing the app
st_mock = MagicMock()
st_mock.session_state = MagicMock()
# Ensure dictionary-like behavior for session_state
def session_state_getitem(self, key):
    return getattr(self, key, None)
def session_state_setitem(self, key, value):
    setattr(self, key, value)
st_mock.session_state.__getitem__ = session_state_getitem
st_mock.session_state.__setitem__ = session_state_setitem
st_mock.session_state.get = lambda k, d=None: getattr(st_mock.session_state, k, d)

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

# Robust cache mock
def cache_mock(*args, **kwargs):
    # Check if called as decorator without arguments: @st.cache_resource
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
    # Called as factory: @st.cache_resource(ttl=...)
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_mock
st_mock.cache_resource = cache_mock
st_mock.error = MagicMock()

# Patch deepcopy to handle mocks (prevent RecursionError)
original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock):
        return x
    try:
        return original_deepcopy(x, memo)
    except Exception:
        return x
copy.deepcopy = safe_deepcopy

# Patch dataclasses.asdict to handle mocks
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

import case_documentation_app

class TestRefreshCasesSorting(unittest.TestCase):
    def setUp(self):
        # Reset cache and throttle before each test
        # Note: Since we mocked cache decorators to return functions directly,
        # _get_global_case_cache returns a new instance every time we call it in the app?
        # No, the app code uses @st.cache_resource. Since we mocked it to return func,
        # calling case_documentation_app._get_global_case_cache() calls the constructor every time.
        # But wait, _refresh_and_get_cases calls _get_global_case_cache().
        # If I want it to be a singleton/shared object during my test, I should patch it.

        self.mock_cache_obj = case_documentation_app._CaseCache()
        self.mock_throttle_obj = case_documentation_app._RefreshThrottle()

        self.cache_patcher = patch("case_documentation_app._get_global_case_cache", return_value=self.mock_cache_obj)
        self.throttle_patcher = patch("case_documentation_app._get_refresh_throttle", return_value=self.mock_throttle_obj)

        self.cache_patcher.start()
        self.throttle_patcher.start()

    def tearDown(self):
        self.cache_patcher.stop()
        self.throttle_patcher.stop()

    def test_sorting_optimization_snapshot_path(self):
        """Verify that the snapshot path uses _updated_ts and sorts correctly."""

        # Populate cache with items having _updated_ts
        # Case 1: Oldest
        dt1 = datetime.datetime(2023, 1, 1, 12, 0, 0)
        item1 = {
            "case_id": "case1",
            "updated": dt1.isoformat(),
            "_updated_ts": dt1.timestamp()
        }

        # Case 2: Newest
        dt2 = datetime.datetime(2023, 1, 2, 12, 0, 0)
        item2 = {
            "case_id": "case2",
            "updated": dt2.isoformat(),
            "_updated_ts": dt2.timestamp()
        }

        self.mock_cache_obj.data = {
            "/path/case1.json": (dt1.timestamp(), item1),
            "/path/case2.json": (dt2.timestamp(), item2)
        }
        # Set last_scan_ts to now to force snapshot path (throttled)
        self.mock_cache_obj.last_scan_ts = time.time()

        # Ensure throttle.last_run is old so we bypass the first check
        self.mock_throttle_obj.last_run = 0.0

        result = case_documentation_app._refresh_and_get_cases()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["case_id"], "case2") # Newest first
        self.assertEqual(result[1]["case_id"], "case1")

    def test_processing_adds_timestamp(self):
        """Verify that processing a new file adds _updated_ts."""

        # Mock os.scandir to return one file
        mock_entry = MagicMock()
        mock_entry.is_file.return_value = True
        mock_entry.name = "case3.json"
        mock_entry.path = "/mock/KiroshiDatabase/case3.json"
        mock_entry.stat.return_value.st_mtime = 1700000000.0

        # Mock file content
        case_content = json.dumps({
            "case_id": "case3",
            "last_modified": "2023-11-14T22:13:20" # corresponds to 1700000000.0 roughly
        })

        with patch("os.scandir") as mock_scandir, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=case_content):

            mock_scandir.return_value.__enter__.return_value = [mock_entry]

            # Force refresh by making last_scan_ts old
            self.mock_cache_obj.last_scan_ts = 0.0
            self.mock_throttle_obj.last_run = 0.0

            result = case_documentation_app._refresh_and_get_cases()

            self.assertEqual(len(result), 1)
            self.assertIn("_updated_ts", result[0])
            self.assertIsInstance(result[0]["_updated_ts"], float)
            # Verify timestamp matches
            expected_ts = datetime.datetime.fromisoformat("2023-11-14T22:13:20").timestamp()
            self.assertAlmostEqual(result[0]["_updated_ts"], expected_ts, delta=0.001)

if __name__ == "__main__":
    unittest.main()
