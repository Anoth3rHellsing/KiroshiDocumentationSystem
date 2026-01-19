
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import types
import dataclasses
import copy
import os

# Add root directory to sys.path
sys.path.insert(0, os.getcwd())

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
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()

# Mock extra dependencies
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()

# Mock local modules
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Improved cache mock
def cache_data_mock(*args, **kwargs):
    # If used as @st.cache_data (no parens), args[0] is the function
    if len(args) == 1 and callable(args[0]) and not kwargs:
        func = args[0]
        cache = {}
        def wrapper(*fargs, **fkwargs):
            key = (fargs, tuple(sorted(fkwargs.items())))
            if key not in cache:
                cache[key] = func(*fargs, **fkwargs)
            return cache[key]
        wrapper.clear = cache.clear
        return wrapper

    # If used as @st.cache_data(...), returns a decorator
    def decorator(func):
        cache = {}
        def wrapper(*fargs, **fkwargs):
            key = (fargs, tuple(sorted(fkwargs.items())))
            if key not in cache:
                cache[key] = func(*fargs, **fkwargs)
            return cache[key]
        wrapper.clear = cache.clear
        return wrapper
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
            num_cases = 50
            recent_cases = []
            for i in range(num_cases):
                recent_cases.append({
                    "case_id": f"CASE-{i}",
                    "path": f"/tmp/case_{i}.json",
                    "last_modified": "2023-01-01T00:00:00"
                })

            payload = json.dumps(recent_cases)

            mock_path.exists.return_value = True

            # Simulate read_text cost
            def side_effect_read_text(encoding="utf-8"):
                time.sleep(0.001) # 1ms penalty per read
                return payload

            mock_path.read_text.side_effect = side_effect_read_text

            # Constant mtime
            mock_path.stat.return_value.st_mtime = 123456789.0

            # Run it multiple times to simulate re-renders
            start_time = time.perf_counter()
            for _ in range(100):
                data = case_documentation_app.load_recent_cases()
            end_time = time.perf_counter()

            duration = (end_time - start_time) * 1000 # ms
            print(f"100 calls to load_recent_cases took {duration:.2f}ms")

            self.assertEqual(len(data), num_cases)

if __name__ == "__main__":
    unittest.main()
