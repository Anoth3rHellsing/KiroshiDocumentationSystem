
import sys
import unittest
from unittest.mock import MagicMock
import dataclasses
import copy
import json

# --- Monkeypatching standard libs to handle mocks during import ---
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    try:
        return original_asdict(obj, dict_factory=dict_factory)
    except TypeError:
        return {}
dataclasses.asdict = safe_asdict

original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock):
        return x
    try:
        return original_deepcopy(x, memo)
    except Exception:
        return x
copy.deepcopy = safe_deepcopy

# --- Mocking dependencies ---
st_mock = MagicMock()
st_mock.session_state = MagicMock()
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.get = MagicMock(return_value=None)
st_mock.cache_data = lambda *args, **kwargs: lambda func: func
st_mock.cache_resource = lambda *args, **kwargs: lambda func: func
st_mock.toggle = MagicMock(return_value=False) # Ensure toggle returns boolean

sys.modules["streamlit"] = st_mock
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()

# Mock extra modules
for mod in ["pyautogui", "tkinter", "PIL", "pytesseract", "mss", "pynput", "pynput.keyboard", "kiroshi_hotkeys"]:
    sys.modules[mod] = MagicMock()

# Monkeypatching for stability
class StreamlitAPIException(Exception): pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Import app
import case_documentation_app

class TestClustering(unittest.TestCase):
    def test_basic_clustering(self):
        if not hasattr(case_documentation_app, "_cluster_case_titles"):
             self.fail("Function _cluster_case_titles not found")

        titles = [
            "Scanner connection issue",
            "Scanner connection lost",
            "Login failed",
            "Unable to login",
            "Scanner broken",
            "Hardware failure",
        ]

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        print(f"Assignments: {assignments}")
        print(f"Labels: {label_map}")

        # Verify Scanner connection (0 and 1) are same cluster
        self.assertEqual(assignments[0], assignments[1], "Similar scanner titles should cluster")

        # Verify deterministic output
        assignments2, _ = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(assignments, assignments2)

    def test_performance_logic(self):
        # Create titles that should definitely cluster
        titles = ["Test case 1", "Test case 1", "Test case 1"]
        assignments, _ = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(len(set(assignments)), 1, "Identical titles should be one cluster")

        # Create titles that are completely different
        titles = ["Apple", "Banana", "Cherry"]
        assignments, _ = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(len(set(assignments)), 3, "Different titles should be different clusters")

if __name__ == "__main__":
    unittest.main()
