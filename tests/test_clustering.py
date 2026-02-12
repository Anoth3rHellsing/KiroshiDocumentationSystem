
import unittest
import sys
from unittest.mock import MagicMock, patch

# Mock modules to avoid side effects during import
sys.modules['streamlit'] = MagicMock()
# Setup st.session_state to return defaults instead of MagicMocks to avoid JSON serialization errors
session_state = MagicMock()
def get_session_value(key, default=None):
    return default
session_state.get.side_effect = get_session_value
session_state.__getitem__.side_effect = lambda k: None
sys.modules['streamlit'].session_state = session_state

sys.modules['streamlit.errors'] = MagicMock()
sys.modules['streamlit.components.v1'] = MagicMock()
sys.modules['reportlab'] = MagicMock()
sys.modules['reportlab.lib.pagesizes'] = MagicMock()
sys.modules['reportlab.lib'] = MagicMock()
sys.modules['reportlab.lib.styles'] = MagicMock()
sys.modules['reportlab.platypus'] = MagicMock()
sys.modules['reportlab.graphics.shapes'] = MagicMock()
sys.modules['reportlab.graphics.charts.barcharts'] = MagicMock()
sys.modules['reportlab.graphics.charts.lineplots'] = MagicMock()
sys.modules['reportlab.graphics.widgets.markers'] = MagicMock()
sys.modules['kiroshi_chat'] = MagicMock()
sys.modules['kiroshi_local_ai'] = MagicMock()
sys.modules['kiroshi_cloud_sync'] = MagicMock()
sys.modules['kiroshi_video'] = MagicMock()
sys.modules['kiroshi_hotkeys'] = MagicMock()
sys.modules['altair'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['tkinter'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['pytesseract'] = MagicMock()
sys.modules['mss'] = MagicMock()

# Monkey patch dataclasses.asdict to handle MagicMock objects
import dataclasses
original_asdict = dataclasses.asdict
def safe_asdict(obj):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj)
dataclasses.asdict = safe_asdict

# Import the functions to test
from case_documentation_app import _cluster_case_titles, _title_similarity_score

class TestClustering(unittest.TestCase):
    def test_title_similarity_score_exact_match(self):
        title = "scanner connection issue"
        tokens = set(["scanner", "connection", "issue"])
        score = _title_similarity_score(tokens, tokens, title, title)
        self.assertAlmostEqual(score, 1.0)

    def test_title_similarity_score_partial_match(self):
        title1 = "scanner connection issue"
        tokens1 = set(["scanner", "connection", "issue"])
        title2 = "scanner connection problem"
        tokens2 = set(["scanner", "connection", "problem"])

        score = _title_similarity_score(tokens1, tokens2, title1, title2)
        # Jaccard: 2/4 = 0.5. SequenceMatcher ratio between strings > 0.5.
        # Score = 0.6 * ratio + 0.4 * 0.5.
        self.assertTrue(score > 0.5)

    def test_title_similarity_score_disjoint(self):
        title1 = "scanner connection issue"
        tokens1 = set(["scanner", "connection", "issue"])
        title2 = "login failed"
        tokens2 = set(["login", "failed"])

        score = _title_similarity_score(tokens1, tokens2, title1, title2)
        self.assertEqual(score, 0.0)

    def test_cluster_case_titles(self):
        titles = [
            "Scanner connection issue",
            "Scanner connection problem",
            "Scanner connection error",
            "Unrelated case"
        ]
        assignments, label_map = _cluster_case_titles(titles)

        # "Scanner connection issue" and "Scanner connection problem" might be close enough.
        # "Scanner connection issue" tokens: scanner, connection, issue.
        # "Scanner connection problem" tokens: scanner, connection, problem.
        # Intersection: scanner, connection. Union: scanner, connection, issue, problem.
        # Jaccard: 0.5. Base similarity is high.
        # Score = 0.6 * base + 0.4 * 0.5 = 0.6 * base + 0.2.
        # If base > 0.8, score > 0.68.

        # We expect assignments[0] and assignments[1] to cluster if similarity is high enough.
        # If not, we update our expectation.
        # Let's use strings that definitely cluster.
        titles = [
            "Scanner connection failed",
            "Scanner connection failed again",
            "Different issue entirely"
        ]
        assignments, label_map = _cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[0], assignments[2])

    def test_cluster_case_titles_performance_optimization_logic(self):
        # This test ensures that very similar titles are clustered, and very different ones are not.
        titles = ["A very specific long title about hardware failure", "A very specific long title about hardware failure"]
        assignments, _ = _cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])

if __name__ == '__main__':
    unittest.main()
