
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import types
import dataclasses
import copy

# Mock dependencies before importing the app
st_mock = MagicMock()
# Mock session_state as a MagicMock to allow attribute access
st_mock.session_state = MagicMock()
# Ensure dictionary-like behavior for session_state if needed
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

# Mock st.cache_data to handle both @decorator and @decorator()
def cache_data_mock(*args, **kwargs):
    # Check if called as @decorator (args[0] is function)
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
    # Check if called as @decorator(...)
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock
st_mock.error = MagicMock()

# Define StreamlitAPIException
class StreamlitAPIException(Exception):
    pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Patch json.dump to avoid writing mocks to disk during import side-effects
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        # Check if obj contains mocks (simple check)
        if isinstance(obj, MagicMock):
            return
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = safe_json_dump

# Patch dataclasses.asdict to handle mocks
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

# Patch deepcopy to handle mocks
original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock):
        return x
    return original_deepcopy(x, memo)
copy.deepcopy = safe_deepcopy

import case_documentation_app

class TestLoadRecentCasesPerformance(unittest.TestCase):
    def test_load_recent_cases_performance(self):
        # Create a temporary file for recent cases
        with patch("case_documentation_app.RECENT_CASES_PATH") as mock_path:
            # Create a large list of recent cases
            num_cases = 100
            recent_cases = []
            for i in range(num_cases):
                recent_cases.append({
                    "case_id": f"CASE-{i}",
                    "path": f"/tmp/case_{i}.json",
                    "last_modified": "2023-01-01T00:00:00"
                })

            mock_path.exists.return_value = True
            # Simulate read_text cost slightly
            mock_path.read_text.return_value = json.dumps(recent_cases)
            mock_path.stat.return_value.st_mtime = 123456789.0

            # Reset the cache in case it was used
            if hasattr(case_documentation_app, "_recent_cases_cache"):
                # Clear the cache function's cache if possible, but here we just want to ensure
                # subsequent calls use the logic.
                # Actually, the mock is passthrough, so it runs every time.
                pass

            start_time = time.perf_counter()
            # Run it multiple times to simulate re-renders
            for _ in range(100):
                data = case_documentation_app.load_recent_cases()
            end_time = time.perf_counter()

            duration = (end_time - start_time) * 1000 # ms
            print(f"100 calls to load_recent_cases took {duration:.2f}ms")

            self.assertEqual(len(data), 100)

    def test_update_recent_cases_redundant_write(self):
        # Verify that update_recent_cases does NOT write if data is unchanged
        with patch("case_documentation_app.RECENT_CASES_PATH") as mock_path, \
             patch("case_documentation_app.Path") as mock_path_cls:

            existing_cases = [
                {"case_id": "CASE-1", "path": "/tmp/case_1.json", "last_modified": "2023-01-01T12:00:00"},
                {"case_id": "CASE-2", "path": "/tmp/case_2.json", "last_modified": "2023-01-01T11:00:00"},
            ]
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = json.dumps(existing_cases)
            mock_path.stat.return_value.st_mtime = 1000.0

            # Mock Path("/tmp/case_1.json")
            mock_case_path = MagicMock()
            mock_path_cls.return_value = mock_case_path
            mock_case_path.exists.return_value = True
            # Simulate that the file content implies same last_modified
            mock_case_path.read_text.return_value = json.dumps({"last_modified": "2023-01-01T12:00:00"})

            # Action: Update the most recent case with same data (simulate redundant load)
            # Use 'case_data' to explicitly pass the timestamp to avoid file read inside update_recent_cases
            # case_documentation_app.update_recent_cases("CASE-1", "/tmp/case_1.json", case_data={"last_modified": "2023-01-01T12:00:00"})

            # Actually, let's test the path where it infers from disk or passed data
            case_documentation_app.update_recent_cases("CASE-1", "/tmp/case_1.json", case_data={"last_modified": "2023-01-01T12:00:00"})

            # Assert
            # After optimization: It should NOT write because data is identical
            mock_path.write_text.assert_not_called()
            print("Write skipped as expected (optimized behavior)")

if __name__ == "__main__":
    unittest.main()
