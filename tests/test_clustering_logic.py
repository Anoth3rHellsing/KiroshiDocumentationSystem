
import sys
import unittest
from unittest.mock import MagicMock
import json
import dataclasses
import copy
import re
from pathlib import Path

# --- Mocking Setup (copied from tests/repro_load_tracked_cases.py) ---
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
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["cryptography"] = MagicMock()

# Mock local modules
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock st.cache_data to do nothing (passthrough)
def cache_data_mock(*args, **kwargs):
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

# --- Import App ---
sys.path.append(str(Path(__file__).parent.parent))
import case_documentation_app

class TestClusteringLogic(unittest.TestCase):
    def test_cluster_case_titles_behavior(self):
        titles = [
            "Scanner connection failed",
            "Scanner connection failed - 2",
            "Scanner connection failed - 3",
            "License expired error 202",
            "License expired error 202 - A",
            "Dongle not found",
            "Dongle not detected",
            "Completely different issue",
        ]

        # Run clustering
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Verify assignments
        # First 3 should be in same cluster
        self.assertEqual(assignments[0], assignments[1])
        self.assertEqual(assignments[0], assignments[2])

        # 4 and 5 should be in same cluster
        self.assertEqual(assignments[3], assignments[4])

        # 0 and 3 should be DIFFERENT
        self.assertNotEqual(assignments[0], assignments[3])

        # "Dongle not found" and "Dongle not detected" end up in different clusters with current logic
        self.assertNotEqual(assignments[5], assignments[6])

        # Last one is unique
        count = assignments.count(assignments[7])
        self.assertEqual(count, 1)

if __name__ == "__main__":
    unittest.main()
