
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock everything required to import case_documentation_app
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
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
sys.modules["reportlab.rl_config"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["PIL.ImageFilter"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["urllib3.exceptions"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock json to avoid serialization errors during import
real_json = __import__("json")
json_mock = MagicMock(wraps=real_json)
json_mock.dump = MagicMock()
sys.modules["json"] = json_mock

# Mock dataclasses.asdict to handle MagicMock objects
real_dataclasses = __import__("dataclasses")
dataclasses_mock = MagicMock(wraps=real_dataclasses)
def safe_asdict(obj, *args, **kwargs):
    if isinstance(obj, MagicMock):
        return {}
    try:
        return real_dataclasses.asdict(obj, *args, **kwargs)
    except TypeError:
        return {}
dataclasses_mock.asdict = safe_asdict
sys.modules["dataclasses"] = dataclasses_mock

import case_documentation_app

class TestTitleSimilarity(unittest.TestCase):
    def test_title_similarity_score_basic(self):
        # Test basic similarity
        t1 = {"scanner", "connection", "issue"}
        t2 = {"scanner", "connection", "issue"}
        n1 = "scanner connection issue"
        n2 = "scanner connection issue"
        score = case_documentation_app._title_similarity_score(t1, t2, n1, n2)
        self.assertAlmostEqual(score, 1.0)

    def test_title_similarity_score_partial(self):
        t1 = {"scanner", "issue"}
        t2 = {"scanner", "connection"}
        n1 = "scanner issue"
        n2 = "scanner connection"
        # Jaccard: 1/3 = 0.333
        # SequenceMatcher: "scanner issue" vs "scanner connection" -> match "scanner " (8 chars). Total 13+18=31. Ratio 2*8/31 = 0.516
        # Score = 0.6 * 0.516 + 0.4 * 0.333 = 0.309 + 0.133 = 0.442
        score = case_documentation_app._title_similarity_score(t1, t2, n1, n2)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_title_similarity_score_disjoint(self):
        t1 = {"apple"}
        t2 = {"banana"}
        n1 = "apple"
        n2 = "banana"
        score = case_documentation_app._title_similarity_score(t1, t2, n1, n2)
        self.assertEqual(score, 0.0)

    def test_clustering_exact_duplicates(self):
        titles = [
            "Scanner Issue",
            "Scanner Issue",
            "Different Issue"
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)
        # Should be 2 clusters
        self.assertEqual(len(label_map), 2)
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[0], assignments[2])

    def test_clustering_similar_items(self):
        titles = [
            "Scanner Connection Issue 1",
            "Scanner Connection Issue 2", # Very similar to 1
            "Totally Different Thing"
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(len(label_map), 2)
        self.assertEqual(assignments[0], assignments[1])

if __name__ == "__main__":
    unittest.main()
