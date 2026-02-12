
import sys
import unittest
from unittest.mock import MagicMock, patch
import json
import dataclasses
import copy
from pathlib import Path

# --- Mocking Setup Start ---
st_mock = MagicMock()
st_mock.session_state = MagicMock()
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.get = MagicMock(return_value=None)
st_mock.session_state.__setitem__ = MagicMock()

# Mock essential modules
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
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock st.cache_data/resource decorators
def cache_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_mock
st_mock.cache_resource = cache_mock

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

# Import the module to test
# We need to catch potential import errors if some other dependency is missing
try:
    import case_documentation_app
except Exception as e:
    print(f"Error importing case_documentation_app: {e}")
    raise

# --- Mocking Setup End ---

class TestClustering(unittest.TestCase):
    def test_clustering_exact_match(self):
        titles = [
            "Scanner connection lost",
            "Scanner connection lost",
            "Different issue"
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Expect 2 clusters: one for scanner connection, one for different issue
        self.assertEqual(len(set(assignments)), 2)
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[0], assignments[2])

    def test_clustering_near_match(self):
        titles = [
            "Scanner connection failed",
            "Scanner connection fail", # Slightly different
            "Totally unrelated"
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Should cluster "failed" and "fail" together if threshold allows
        # Threshold is 0.68 if tokens exist.
        # "Scanner connection failed" tokens: scanner, connection, failed
        # "Scanner connection fail" tokens: scanner, connection, fail
        # Overlap is high.
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[0], assignments[2])

    def test_clustering_distinct(self):
        titles = [
            "First unique issue",
            "Second unique issue",
            "Third unique issue"
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # All distinct
        self.assertEqual(len(set(assignments)), 3)

    def test_clustering_empty(self):
        titles = ["", "   ", "Valid title"]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Empty titles should group together into a "blank" cluster
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[0], assignments[2])

        # Check label for empty cluster
        empty_cluster_idx = assignments[0]
        self.assertEqual(label_map[empty_cluster_idx], "Caso sin título")

    def test_clustering_performance_logic(self):
        # This test ensures that the optimized logic returns the same results as expected
        # for a tricky case where early break might be triggered.
        titles = [
            "Complex issue with many words Alpha",
            "Complex issue with many words Alpha", # Exact match, should break early and assign same cluster
            "Complex issue with many words Beta"   # Distinct suffix
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        self.assertEqual(assignments[0], assignments[1])
        # Depending on threshold, these might still cluster together if the shared prefix is long enough.
        # But let's check if they do or don't.
        # If they cluster together, that's fine for the logic, we just want to ensure consistency.
        # Let's change expectation or inputs to ensure separation if that's what we want to test.
        # If we use very distinct words:
        titles = [
            "Scanner connection failure type one",
            "Scanner connection failure type one",
            "Scanner connection failure type two"
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])
        # These are still very similar.

        # Let's use something that definitely separates
        titles = [
             "Scanner error 101",
             "Scanner error 101",
             "Printer error 202"
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[0], assignments[2])

if __name__ == "__main__":
    unittest.main()
