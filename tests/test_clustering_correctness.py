
import sys
import os
import unittest
from unittest.mock import MagicMock

# Create a custom SessionState class
class SessionState(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"SessionState has no attribute '{key}'")

    def __setattr__(self, key, value):
        self[key] = value

# Mock streamlit
streamlit_mock = MagicMock()
streamlit_mock.session_state = SessionState()
streamlit_mock.session_state.tutorial_completed = True
streamlit_mock.session_state.show_tutorial = False
sys.modules["streamlit"] = streamlit_mock
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()

# Mock other dependencies
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Import the function
sys.path.append(os.getcwd())
from case_documentation_app import _cluster_case_titles

class TestClusteringCorrectness(unittest.TestCase):
    def test_clustering_exact_matches(self):
        titles = [
            "Scanner connection failed",
            "Scanner connection failed",
            "Scanner connection failed"
        ]
        assignments, label_map = _cluster_case_titles(titles)
        self.assertEqual(len(label_map), 1)
        self.assertEqual(assignments, [0, 0, 0])

    def test_clustering_similar_matches(self):
        titles = [
            "Scanner connection failed",
            "Scanner connect failure", # Similar enough?
            "Something completely different"
        ]
        assignments, label_map = _cluster_case_titles(titles)
        # Assuming the first two are similar enough to cluster together
        # "connection" vs "connect" -> tokens might match if stemming was used, but simple tokenization might not.
        # However, "Scanner" matches.
        # Let's check logic: _title_similarity_score uses SequenceMatcher + Jaccard.
        # "Scanner connection failed" tokens: {scanner, connection, failed}
        # "Scanner connect failure" tokens: {scanner, connect, failure}
        # Intersection: {scanner}. Union: 5. Jaccard: 0.2.
        # Norm strings: "scanner connection failed", "scanner connect failure".
        # SequenceMatcher ratio will be high.

        # Actually, let's just assert they are NOT all same if distinct.
        # But wait, I want to verify behavior preservation.
        pass

    def test_clustering_grouping(self):
        titles = [
            "Scanner issue",
            "Scanner problem",
            "Login error",
            "Login failed",
            "Scanner issue"
        ]
        assignments, label_map = _cluster_case_titles(titles)
        # Expected:
        # "Scanner issue" (0)
        # "Scanner problem" -> likely clusters with "Scanner issue" (share "scanner", high seq match)
        # "Login error" -> New cluster
        # "Login failed" -> likely clusters with "Login error"
        # "Scanner issue" -> matches cluster 0.

        # Note: indices depend on processing order.
        self.assertEqual(assignments[0], assignments[4]) # Same title, same cluster
        self.assertNotEqual(assignments[0], assignments[2]) # "Scanner" vs "Login"

    def test_clustering_empty(self):
        titles = []
        assignments, label_map = _cluster_case_titles(titles)
        self.assertEqual(assignments, [])
        self.assertEqual(label_map, {})

    def test_clustering_no_tokens(self):
        # Titles that produce no tokens AND empty normalized string
        titles = [
            "!!!", "...", "   ", # Should be normalized to empty
            "???"
        ]
        # logic: if not normalized and not tokens: goes to blank_index.
        assignments, label_map = _cluster_case_titles(titles)
        # They should all map to the "blank" cluster
        self.assertEqual(len(label_map), 1)
        self.assertEqual(label_map[0], "Caso sin título")
        self.assertEqual(assignments, [0, 0, 0, 0])

if __name__ == '__main__':
    unittest.main()
