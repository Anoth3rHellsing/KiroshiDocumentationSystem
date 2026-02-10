
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import types
import dataclasses
import copy
from datetime import datetime

# Mock dependencies before importing the app
st_mock = MagicMock()
# Mock session_state as a MagicMock to allow attribute access
st_mock.session_state = MagicMock()
# Ensure dictionary-like behavior for session_state if needed (though app uses attribute access mostly)
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
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock st.cache_data to do nothing (passthrough)
def cache_data_mock(*args, **kwargs):
    # Check if called as @st.cache_data (no parens) or @st.cache_data(...) (parens)
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
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

class TestSortingOptimization(unittest.TestCase):
    def test_sorting_performance(self):
        num_cases = 1000
        mock_files = {}
        mock_entries = []

        # Generate fake case files
        for i in range(num_cases):
            case_id = f"CASE-{i:04d}"
            path = f"/fake/path/{case_id}.json"
            ts = 1700000000.0 + i  # distinct timestamps
            iso_time = datetime.fromtimestamp(ts).isoformat()

            content = json.dumps({
                "case_id": case_id,
                "company": f"Company {i}",
                "description": f"Description {i}",
                "last_modified": iso_time
            })

            mock_files[path] = content

            entry = MagicMock()
            entry.is_file.return_value = True
            entry.name = f"{case_id}.json"
            entry.path = path
            entry.stat.return_value.st_mtime = ts
            mock_entries.append(entry)

        # Mock os.scandir to return our fake entries
        # We need context manager support for scandir result
        scandir_mock = MagicMock()
        scandir_mock.__enter__.return_value = mock_entries
        scandir_mock.__exit__.return_value = None

        # Mock Path.read_text to return content from our dict
        def read_text_side_effect(*args, **kwargs):
            # self matches the Path object, but we need the path string.
            # Since Path is mocked or real, let's see.
            # case_documentation_app uses pathlib.Path, so we should mock Path or its read_text method.
            # But constructing Path objects from string in app...
            pass

        # Create persistent cache objects
        persistent_cache = case_documentation_app._CaseCache()
        persistent_throttle = case_documentation_app._RefreshThrottle()

        # Easier way: mock Path object creation in the app or patch Path.read_text
        with patch("case_documentation_app.os.scandir", return_value=scandir_mock), \
             patch("case_documentation_app.Path") as MockPath, \
             patch("case_documentation_app.datetime") as mock_datetime, \
             patch("case_documentation_app._get_global_case_cache", return_value=persistent_cache), \
             patch("case_documentation_app._get_refresh_throttle", return_value=persistent_throttle), \
             patch("case_documentation_app.time.time") as mock_time:

            start_ts = 1000.0
            mock_time.return_value = start_ts

            # Configure MockPath to return content
            def get_mock_path(path_str):
                p = MagicMock()
                p.read_text.return_value = mock_files.get(str(path_str), "{}")
                p.exists.return_value = True
                p.stem = str(path_str).split("/")[-1].replace(".json", "")
                return p

            MockPath.side_effect = get_mock_path

            # We want to count calls to fromisoformat.
            # We need to wrap the real datetime.fromisoformat to keep functionality but count calls.
            real_datetime = datetime

            # Create a spy for fromisoformat
            mock_datetime.fromisoformat.side_effect = real_datetime.fromisoformat
            mock_datetime.now.side_effect = real_datetime.now
            mock_datetime.fromtimestamp.side_effect = real_datetime.fromtimestamp

            # Run the function
            # First run: populates cache.
            # We need to make sure cache is empty or cleared.

            # Reset cache (just in case)
            persistent_cache.data.clear()
            persistent_cache.last_scan_ts = 0.0
            persistent_throttle.last_run = 0.0
            persistent_throttle.data = []

            # Measure time
            start_time = time.perf_counter()
            cases = case_documentation_app._refresh_and_get_cases()
            end_time = time.perf_counter()

            duration = (end_time - start_time) * 1000
            print(f"First run (populate cache) took {duration:.2f}ms")

            # Verify we got cases
            self.assertEqual(len(cases), num_cases)

            # Count calls to fromisoformat
            # Each case loading calls it once for "last_modified" parsing if not present,
            # but here "last_modified" IS present in JSON.
            # Wait, the sorting logic calls it:
            # valid_items.sort(key=lambda x: _parse_time(x.get("updated")), reverse=True)
            # So we expect roughly N calls during sort.

            call_count = mock_datetime.fromisoformat.call_count
            print(f"datetime.fromisoformat call count: {call_count}")

            # If optimization is working, this should be 0 (or very low) for the sort key part.
            # However, logic might use it elsewhere.
            # In unoptimized code:
            # 1. Inside `processed` creation? No, only if last_modified is missing.
            # 2. Inside sort key? Yes, definitely.

            # So unoptimized: call_count >= N (1000)

            # With optimization:
            # 1 call per case during processing to calculate last_modified and _updated_ts (N calls)
            # 0 calls during sort (uses _updated_ts)
            # Total ~N calls.
            # Without optimization:
            # 1 call per case during processing (N calls)
            # 1 call per case during sort (N calls)
            # Total ~2N calls.

            # Since we implemented the optimization, we expect N calls.
            self.assertLess(call_count, num_cases * 1.5, f"Should call fromisoformat ~N times (processing only), got {call_count}")

            # Reset spy
            mock_datetime.fromisoformat.reset_mock()

            # Second run: Throttle check (if we simulate immediate recall)
            # But the throttle logic uses time.time(), so we might need to patch time.time
            # However, time is imported as "import time", so we patch "case_documentation_app.time"
            with patch("case_documentation_app.time.time", return_value=end_time + 1.0): # 1s later, < 2.0s throttle
                 # This should hit the "simple throttle" path which ALSO sorts
                 start_time_2 = time.perf_counter()
                 cases_2 = case_documentation_app._refresh_and_get_cases()
                 end_time_2 = time.perf_counter()

                 duration_2 = (end_time_2 - start_time_2) * 1000
                 print(f"Second run (throttle sort) took {duration_2:.2f}ms")

                 call_count_2 = mock_datetime.fromisoformat.call_count
                 print(f"datetime.fromisoformat call count (throttle): {call_count_2}")

                 # This path also sorts. With optimization, it should use _updated_ts.
                 # So call count should be 0 (since items are already processed).
                 self.assertEqual(call_count_2, 0, f"Should NOT call fromisoformat in throttle path sort, got {call_count_2}")

if __name__ == "__main__":
    unittest.main()
