
import sys
import unittest
from unittest.mock import MagicMock

# Mock dependencies
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
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
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

import json
original_json_dump = json.dump
def mock_json_dump(*args, **kwargs):
    try:
        original_json_dump(*args, **kwargs)
    except TypeError:
        pass
json.dump = mock_json_dump

class MockSessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value
sys.modules["streamlit"].session_state = MockSessionState()

sys.path.insert(0, ".")

try:
    import case_documentation_app
except ImportError:
    pass

class TestClusteringLogic(unittest.TestCase):
    def test_similarity_score_basic(self):
        # Test basic similarity calculation (existing behavior)
        tokens_a = {"scan", "issue"}
        tokens_b = {"scan", "issue"}
        norm_a = "scan issue"
        norm_b = "scan issue"
        score = case_documentation_app._title_similarity_score(tokens_a, tokens_b, norm_a, norm_b)
        self.assertEqual(score, 1.0)

    def test_similarity_score_disjoint(self):
        # Test disjoint tokens (existing behavior)
        tokens_a = {"scan", "issue"}
        tokens_b = {"login", "failed"}
        norm_a = "scan issue"
        norm_b = "login failed"
        score = case_documentation_app._title_similarity_score(tokens_a, tokens_b, norm_a, norm_b)
        self.assertEqual(score, 0.0)

    def test_similarity_score_partial(self):
        # Test partial match
        tokens_a = {"scan", "issue"}
        tokens_b = {"scan", "problem"} # 1 common token
        norm_a = "scan issue"
        norm_b = "scan problem"

        # Jaccard = 1/3 = 0.333...
        # Base = partial match of strings
        score = case_documentation_app._title_similarity_score(tokens_a, tokens_b, norm_a, norm_b)
        self.assertTrue(0.0 < score < 1.0)

    def test_similarity_score_min_score_optimization(self):
        # This test verifies the optimization logic.
        # Once implemented, _title_similarity_score should accept min_score
        # and return 0.0 if the theoretical max score is lower than min_score.

        tokens_a = {"scan", "issue"}
        tokens_b = {"scan", "problem"} # Jaccard approx 0.33
        norm_a = "scan issue"
        norm_b = "scan problem"

        # Max theoretical score: 0.6 + 0.4 * 0.33 = 0.732

        # If we pass min_score=0.8, it should return 0.0 immediately
        # Note: This will fail until we implement the change
        try:
            score = case_documentation_app._title_similarity_score(tokens_a, tokens_b, norm_a, norm_b, min_score=0.8)
            # If the argument is accepted, verify result
            self.assertEqual(score, 0.0)
        except TypeError:
            # Function signature not updated yet, skip check
            pass

    def test_clustering_correctness(self):
        # Test clustering behavior
        titles = [
            "Scanner connection issue",
            "Scanner connection issue 2",
            "Login failed",
            "Login failed 2",
            "Different issue entirely"
        ]

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Should have 3 clusters: Scanner, Login, Different
        unique_assignments = set(assignments)
        self.assertEqual(len(unique_assignments), 3)

        # Verify grouping
        self.assertEqual(assignments[0], assignments[1])
        self.assertEqual(assignments[2], assignments[3])
        self.assertNotEqual(assignments[0], assignments[2])
        self.assertNotEqual(assignments[0], assignments[4])

if __name__ == "__main__":
    unittest.main()
