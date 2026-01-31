
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
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.fernet"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()

# Improved mock for cache decorators
def cache_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_mock
st_mock.cache_resource = cache_mock
st_mock.error = MagicMock()

# Define StreamlitAPIException
class StreamlitAPIException(Exception):
    pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Patch json.dump
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    if isinstance(obj, MagicMock):
        return
    try:
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
    try:
        return original_deepcopy(x, memo)
    except (TypeError, ValueError, RecursionError):
        return x
copy.deepcopy = safe_deepcopy

import case_documentation_app

class TestRefreshCasesOptimization(unittest.TestCase):
    def test_sorting_with_updated_ts(self):
        # Mock _get_global_case_cache to return populated data
        mock_cache = MagicMock()
        mock_cache.last_scan_ts = 0.0 # Force re-scan logic? No, let's test the throttle path first if easier, or scan path.

        # We want to test the sorting logic.
        # The logic is in _refresh_and_get_cases.

        # Let's mock the filesystem scan to return some files
        with patch("case_documentation_app.DATABASE_DIR") as mock_db_dir, \
             patch("case_documentation_app.TRACKED_CASES_DIR") as mock_track_dir, \
             patch("os.scandir") as mock_scandir, \
             patch("pathlib.Path.read_text") as mock_read_text, \
             patch("case_documentation_app._get_refresh_throttle") as mock_get_throttle, \
             patch("case_documentation_app._get_global_case_cache") as mock_get_cache:

            # Mock throttle to always allow run
            mock_throttle = MagicMock()
            mock_throttle.last_run = 0.0
            mock_throttle.data = []
            mock_get_throttle.return_value = mock_throttle

            # Mock cache object
            global_cache = MagicMock()
            global_cache.data = {}
            global_cache.last_scan_ts = 0.0
            global_cache.lock = MagicMock() # Context manager
            global_cache.lock.__enter__.return_value = None
            global_cache.lock.__exit__.return_value = None
            mock_get_cache.return_value = global_cache

            # Mock scandir
            entry1 = MagicMock()
            entry1.is_file.return_value = True
            entry1.name = "case1.json"
            entry1.path = "/tmp/case1.json"
            entry1.stat.return_value.st_mtime = 1000.0

            entry2 = MagicMock()
            entry2.is_file.return_value = True
            entry2.name = "case2.json"
            entry2.path = "/tmp/case2.json"
            entry2.stat.return_value.st_mtime = 2000.0 # Newer

            mock_scandir.return_value.__enter__.return_value = [entry1, entry2]
            mock_scandir.return_value.__exit__.return_value = None

            mock_db_dir.exists.return_value = True
            mock_track_dir.exists.return_value = False

            # Mock file content
            # We need to make sure _updated_ts is calculated correctly
            def side_effect_read_text(*args, **kwargs):
                # The mock object for Path("/tmp/case1.json") needs to be handled
                # But mock_read_text is patching Path.read_text directly
                # We can check the instance? No, side_effect receives nothing useful about instance usually unless it's an autospec
                # Actually, simple trick: read_text is called on Path objects created from entry.path
                return "{}"

            # Instead of mocking Path.read_text which is hard to map to specific files,
            # let's mock json.loads?
            # Or assume read_text returns a standard JSON and we rely on mtime for ordering?
            # The code uses:
            # last_modified = data.get("last_modified") or datetime.fromtimestamp(mtime)...

            mock_read_text.return_value = "{}" # Empty dict

            # Execute
            results = case_documentation_app._refresh_and_get_cases()

            # Verify results
            self.assertEqual(len(results), 2)
            # Case 2 has mtime 2000, Case 1 has mtime 1000.
            # Should be sorted descending by updated time.
            self.assertEqual(results[0]["path"], "/tmp/case2.json")
            self.assertEqual(results[1]["path"], "/tmp/case1.json")

            # Verify _updated_ts is present
            self.assertIn("_updated_ts", results[0])
            self.assertIn("_updated_ts", results[1])
            self.assertEqual(results[0]["_updated_ts"], 2000.0)
            self.assertEqual(results[1]["_updated_ts"], 1000.0)

            print("Verification successful: Results are sorted and contain _updated_ts")

if __name__ == "__main__":
    unittest.main()
