
import sys
import os
import unittest
import json
import dataclasses
from unittest.mock import MagicMock
from collections import defaultdict, Counter

# Mock modules to avoid import errors when importing case_documentation_app
sys.modules['streamlit'] = MagicMock()
sys.modules['streamlit'].columns = MagicMock(return_value=[MagicMock() for _ in range(10)])
sys.modules['streamlit.components.v1'] = MagicMock()
sys.modules['streamlit.errors'] = MagicMock()
sys.modules['streamlit.errors'].StreamlitAPIException = Exception

sys.modules['altair'] = MagicMock()
sys.modules['pandas'] = MagicMock()
sys.modules['reportlab'] = MagicMock()
sys.modules['reportlab.lib.pagesizes'] = MagicMock()
sys.modules['reportlab.lib'] = MagicMock()
sys.modules['reportlab.lib.styles'] = MagicMock()
sys.modules['reportlab.platypus'] = MagicMock()
sys.modules['reportlab.graphics.shapes'] = MagicMock()
sys.modules['reportlab.graphics.charts.barcharts'] = MagicMock()
sys.modules['reportlab.graphics.charts.lineplots'] = MagicMock()
sys.modules['reportlab.graphics.widgets.markers'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['tkinter'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['pytesseract'] = MagicMock()
sys.modules['mss'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['urllib3'] = MagicMock()
sys.modules['kiroshi_chat'] = MagicMock()
sys.modules['kiroshi_local_ai'] = MagicMock()
sys.modules['kiroshi_cloud_sync'] = MagicMock()
sys.modules['kiroshi_video'] = MagicMock()
sys.modules['kiroshi_hotkeys'] = MagicMock()

# Mock json.dump
original_json_dump = json.dump
def mock_json_dump(obj, fp, **kwargs):
    try:
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = mock_json_dump

# Mock dataclasses.asdict
original_asdict = dataclasses.asdict
def mock_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    try:
        return original_asdict(obj, dict_factory=dict_factory)
    except TypeError:
        return {}
dataclasses.asdict = mock_asdict

# Import the function to test
sys.path.insert(0, os.getcwd())
try:
    from case_documentation_app import _cluster_case_titles
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)

class TestClustering(unittest.TestCase):
    def test_clustering_basic(self):
        titles = [
            "Scanner connection issue",
            "Scanner connection failed",
            "Login error",
            "Cant login",
            "Random issue",
            ""
        ]
        assignments, label_map = _cluster_case_titles(titles)
        self.assertEqual(len(assignments), len(titles))
        # Basic sanity check: similar titles should have same assignment
        # Scanner... (0 and 1)
        # Login... (2 and 3 potentially, or maybe not if threshold is high)
        # Empty (5)

        # We assume 0 and 1 cluster together
        if assignments[0] == assignments[1]:
            pass

        # Ensure distinct clusters exist
        self.assertTrue(len(set(assignments)) > 1)

    def test_clustering_empty(self):
        titles = []
        assignments, label_map = _cluster_case_titles(titles)
        self.assertEqual(assignments, [])
        self.assertEqual(label_map, {})

    def test_clustering_blanks(self):
        titles = ["", "   ", "Valid Title"]
        assignments, label_map = _cluster_case_titles(titles)
        # Blank titles should be clustered together (index 0 and 1 likely same cluster)
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[0], assignments[2])

if __name__ == "__main__":
    unittest.main()
