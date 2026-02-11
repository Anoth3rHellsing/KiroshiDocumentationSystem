
import sys
import unittest
from unittest.mock import MagicMock, patch
import os

# Mock dependencies to allow importing case_documentation_app
mock_streamlit = MagicMock()
sys.modules["streamlit"] = mock_streamlit
sys.modules["streamlit.components"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()

sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
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
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["urllib3.exceptions"] = MagicMock()

# Ensure we can import from root
sys.path.insert(0, os.getcwd())

# Patch pathlib.Path to avoid filesystem touches during import
with patch("pathlib.Path") as MockPath, patch("json.dump"), patch("dataclasses.asdict", return_value={}):
    # Setup recursive mock
    recursive_mock = MagicMock()
    recursive_mock.exists.return_value = True
    recursive_mock.stat.return_value.st_mtime = 12345.0
    recursive_mock.read_text.return_value = "{}"
    recursive_mock.read_bytes.return_value = b"fake_image_data"

    # Allow chaining to always return this useful mock
    recursive_mock.resolve.return_value = recursive_mock
    recursive_mock.parent = recursive_mock
    recursive_mock.__truediv__.return_value = recursive_mock

    MockPath.return_value = recursive_mock

    # Also handle Path.home()
    MockPath.home.return_value = recursive_mock

    import case_documentation_app

class TestTitleSimilarityOptimization(unittest.TestCase):
    def test_pruning_correctness(self):
        """
        Verify that the optimized clustering produces the same results as
        (or valid results consistent with) the expected logic.
        """
        titles = [
            "Scanner connection issue",
            "Scanner connection problem",  # Should cluster with above
            "Login failed on Unite",
            "Unite login failure",         # Should cluster with above
            "Completely unrelated issue 123",
            "Completely unrelated issue 456", # Should cluster with above
            "Unique title A",
            "Unique title B",
        ]

        # We expect fewer clusters than titles
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Check assignments validity
        self.assertEqual(len(assignments), len(titles))

        # "Scanner connection issue" and "Scanner connection problem" should likely be same cluster
        self.assertEqual(assignments[0], assignments[1], "Similar scanner titles should cluster together")

        # "Login failed on Unite" and "Unite login failure" should likely be same cluster
        self.assertEqual(assignments[2], assignments[3], "Similar login titles should cluster together")

        # "Unique title A" and "Unique title B"
        # Token overlap: "unique", "title". Jaccard is high.
        # So they should cluster together.
        self.assertEqual(assignments[6], assignments[7], "Very similar titles should cluster together")

    def test_min_score_pruning(self):
        """
        Directly test _title_similarity_score with inputs that should be pruned.
        """
        # "Scanner" vs "Login" -> Jaccard 0. Max score 0.6.
        # If min_score 0.7, should return 0.0 immediately.

        tokens_a = {"scanner"}
        tokens_b = {"login"}
        norm_a = "scanner"
        norm_b = "login"

        # Without pruning (min_score=0), returns 0.0 anyway due to isdisjoint optimization
        score = case_documentation_app._title_similarity_score(tokens_a, tokens_b, norm_a, norm_b, min_score=0.0)
        self.assertEqual(score, 0.0)

        # Case where isdisjoint is False but Jaccard is low
        # "common" is shared. "apple" vs "orange".
        tokens_a = {"common", "apple"}
        tokens_b = {"common", "orange"}
        norm_a = "common apple"
        norm_b = "common orange"

        # Jaccard: 1 / 3 = 0.333
        # Max possible: 0.6 + 0.4 * 0.333 = 0.6 + 0.133 = 0.733

        # If min_score is 0.8, should return 0.0
        score_high_threshold = case_documentation_app._title_similarity_score(
            tokens_a, tokens_b, norm_a, norm_b, min_score=0.8
        )
        self.assertEqual(score_high_threshold, 0.0)

        # If min_score is 0.5, should return actual score
        # Actual score: Base ~0.6-0.7. Score ~0.6*0.65 + 0.4*0.33 = 0.39 + 0.13 = 0.52
        score_low_threshold = case_documentation_app._title_similarity_score(
            tokens_a, tokens_b, norm_a, norm_b, min_score=0.5
        )
        self.assertGreater(score_low_threshold, 0.0)

if __name__ == "__main__":
    unittest.main()
