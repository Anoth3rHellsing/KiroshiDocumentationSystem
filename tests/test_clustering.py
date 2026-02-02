
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock dependencies before importing the app
st_mock = MagicMock()
st_mock.session_state = MagicMock()
class SessionStateMock(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value
st_mock.session_state = SessionStateMock()

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
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["cryptography"] = MagicMock()

def cache_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator
st_mock.cache_data = cache_mock
st_mock.cache_resource = cache_mock
st_mock.error = MagicMock()

import dataclasses
import copy
import json

original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        if isinstance(obj, MagicMock):
            return
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = safe_json_dump

original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

import case_documentation_app

class TestClustering(unittest.TestCase):
    def test_clustering_basics(self):
        titles = [
            "Printer error",
            "printer error",
            "Scanner issue",
            "scanner problem",
            "Completely different"
        ]

        # Expected:
        # "Printer error" and "printer error" should be same cluster (0)
        # "Scanner issue" and "scanner problem" should be same cluster (1) (assuming similarity threshold is met)
        # "Completely different" should be new cluster (2)

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        self.assertEqual(len(assignments), 5)
        self.assertEqual(assignments[0], assignments[1], "Identical titles should cluster together")

        # Check if scanner issue/problem clustered together.
        # "Scanner issue" -> tokens: {scanner, issue} (issue is stopword?)
        # Let's check stop words
        # TITLE_SIMILARITY_STOPWORDS contains "issue", "problem"
        # So "Scanner issue" -> tokens: {scanner}
        # "scanner problem" -> tokens: {scanner}
        # They share "scanner", score should be high.
        self.assertEqual(assignments[2], assignments[3], "Similar titles should cluster together")

        self.assertNotEqual(assignments[0], assignments[2], "Different topics should be separate")
        self.assertNotEqual(assignments[0], assignments[4], "Different topics should be separate")
        self.assertNotEqual(assignments[2], assignments[4], "Different topics should be separate")

    def test_clustering_no_tokens(self):
        # Titles that might result in no tokens (e.g. only stopwords or short words)
        # "The issue" -> tokens: {} (the is generic stopword, issue is title stopword)
        # "Another problem" -> tokens: {}

        titles = ["The issue", "The issue", "Another problem"]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        self.assertEqual(assignments[0], assignments[1], "Identical no-token titles should cluster together")
        # "Another problem" vs "The issue" -> SequenceMatcher might distinguish them
        self.assertNotEqual(assignments[0], assignments[2], "Distinct no-token titles should generally separate")

    def test_clustering_incremental(self):
        titles = ["Alpha case", "Beta case", "Alpha case error"]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)
        # "Alpha case" tokens: alpha
        # "Beta case" tokens: beta
        # "Alpha case error" tokens: alpha. Shares 'alpha'.

        self.assertEqual(assignments[0], assignments[2], "Should cluster with earlier similar title")
        self.assertNotEqual(assignments[0], assignments[1])

if __name__ == "__main__":
    unittest.main()
