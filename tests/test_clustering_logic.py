
import unittest
from unittest.mock import MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock modules
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
reportlab = MagicMock()
sys.modules["reportlab"] = reportlab
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["reportlab.pdfbase"] = MagicMock()
sys.modules["reportlab.pdfbase.pdfdoc"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Patch json.dump
import json
original_json_dump = json.dump
def mock_json_dump(obj, fp, **kwargs):
    try:
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = mock_json_dump

# Patch dataclasses.asdict
import dataclasses
original_asdict = dataclasses.asdict
def mock_asdict(obj, *args, **kwargs):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, *args, **kwargs)
dataclasses.asdict = mock_asdict

try:
    from case_documentation_app import _cluster_case_titles, _title_similarity_score
except ImportError:
    import traceback
    traceback.print_exc()
    sys.exit(1)

class TestClustering(unittest.TestCase):
    def test_exact_match(self):
        titles = ["Scanner Error", "Scanner Error"]
        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])
        self.assertEqual(len(labels), 1)

    def test_similar_match(self):
        titles = ["Scanner connection lost", "Scanner connection failure"]
        # These should likely cluster together
        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])
        self.assertEqual(len(labels), 1)

    def test_distinct_titles(self):
        titles = ["Scanner Error", "License Issue"]
        assignments, labels = _cluster_case_titles(titles)
        self.assertNotEqual(assignments[0], assignments[1])
        self.assertEqual(len(labels), 2)

    def test_min_score_pruning(self):
        # Verify that providing a high min_score returns 0.0 if not achievable
        tokens_a = {"scanner", "error"}
        tokens_b = {"license", "issue"}
        # Jaccard is 0. Base might be low but not 0.
        # Max score is 0.6 * 1.0 + 0.4 * 0 = 0.6
        # If min_score is 0.7, should return 0.0 immediately
        score = _title_similarity_score(tokens_a, tokens_b, "scanner error", "license issue", min_score=0.7)
        self.assertEqual(score, 0.0)

if __name__ == "__main__":
    unittest.main()
