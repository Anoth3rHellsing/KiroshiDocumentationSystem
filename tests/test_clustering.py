
import unittest
import sys
from unittest.mock import MagicMock

# Mock dependencies before import
mock_st = MagicMock()
# Mock st.cache_data as a pass-through decorator that handles both @st.cache_data and @st.cache_data(...)
def cache_data_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    def decorator(func):
        return func
    return decorator
mock_st.cache_data = cache_data_mock

def cache_resource_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    def decorator(func):
        return func
    return decorator
mock_st.cache_resource = cache_resource_mock

sys.modules["streamlit"] = mock_st
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["reportlab.pdfbase"] = MagicMock()
sys.modules["reportlab.rl_config"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pandas"] = MagicMock()

import json
import dataclasses
# Patch json.dump and dataclasses.asdict
original_json_dump = json.dump
def mock_json_dump(obj, fp, **kwargs):
    try:
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = mock_json_dump

original_asdict = dataclasses.asdict
def mock_asdict(obj, **kwargs):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, **kwargs)
dataclasses.asdict = mock_asdict

import case_documentation_app

class TestClustering(unittest.TestCase):
    def test_basic_clustering(self):
        titles = [
            "Network connection timeout",
            "Network connection failed",
            "Unrelated issue"
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Network issues should be clustered
        self.assertEqual(assignments[0], assignments[1], f"Network issues should be in same cluster. Got {assignments}")

        # Unrelated should be different
        self.assertNotEqual(assignments[0], assignments[2])

    def test_identical_titles(self):
        titles = ["Same Title", "Same Title"]
        assignments, _ = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])

    def test_no_tokens(self):
        # Titles with only stopwords or numbers
        titles = ["The the", "123 456"]
        assignments, _ = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(len(assignments), 2)

if __name__ == '__main__':
    unittest.main()
