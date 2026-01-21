
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

# Mock st.cache_data to do nothing (passthrough)
def cache_data_mock(*args, **kwargs):
    if args and callable(args[0]):
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

# Fix RecursionError in deepcopy of MagicMock
MagicMock.__deepcopy__ = lambda self, memo: self

import case_documentation_app

class TestLoadTrackedCasesPerformance(unittest.TestCase):
    def test_load_tracked_cases_performance(self):
        # Mock _refresh_and_get_cases to simulate many cases
        num_cases = 10000
        mock_cases = []
        for i in range(num_cases):
            mock_cases.append({
                "case_id": f"CASE-{i}",
                "path": f"/tmp/case_{i}.json",
                "tracking": {"active": i % 2 == 0}, # 50% tracked
                "last_modified": "2023-01-01T00:00:00"
            })

        with patch("case_documentation_app._refresh_and_get_cases", return_value=mock_cases):
            start_time = time.perf_counter()
            tracked = case_documentation_app.load_tracked_cases()
            end_time = time.perf_counter()

            duration = (end_time - start_time) * 1000 # ms
            print(f"load_tracked_cases took {duration:.2f}ms for {num_cases} cases")

            self.assertEqual(len(tracked), 5000)

if __name__ == "__main__":
    unittest.main()
