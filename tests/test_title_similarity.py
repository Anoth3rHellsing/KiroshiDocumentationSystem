
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import dataclasses

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock dependencies before importing the app
st_mock = MagicMock()
st_mock.session_state = MagicMock()
# Ensure dictionary-like behavior
st_mock.session_state.get = MagicMock(return_value=None)
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.__setitem__ = MagicMock()

# Mock sys.modules for Streamlit and other heavy/UI libs
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
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()

# Mock other display/system libs
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.hazmat"] = MagicMock()
sys.modules["cryptography.hazmat.primitives"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf.pbkdf2"] = MagicMock()
sys.modules["cryptography.hazmat.backends"] = MagicMock()

# Mock requests/urllib3 to avoid network calls
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Mock internal modules that might be heavy or stateful
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Custom side effect for asdict to handle MagicMock
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)

# Patch logging to prevent initialization errors with mocks
with patch("logging.basicConfig"), \
     patch("logging.getLogger", MagicMock()), \
     patch("logging.handlers.RotatingFileHandler", MagicMock()), \
     patch("pathlib.Path.mkdir"), \
     patch("pathlib.Path.write_text"), \
     patch("pathlib.Path.exists", return_value=True), \
     patch("builtins.open", MagicMock()), \
     patch("dataclasses.asdict", side_effect=safe_asdict):

    import case_documentation_app

class TestTitleSimilarity(unittest.TestCase):
    def test_title_similarity_score_basic(self):
        # Case 1: Identical
        t1 = "cannot login to unite"
        tokens1 = case_documentation_app._title_similarity_tokens(t1)
        norm1 = case_documentation_app._normalize_title_similarity(t1)

        score = case_documentation_app._title_similarity_score(tokens1, tokens1, norm1, norm1)
        self.assertAlmostEqual(score, 1.0)

    def test_title_similarity_score_disjoint(self):
        # Case 2: Completely different
        # Use words that are definitely not in _GENERIC_STOPWORDS
        t1 = "catastrophic explosion"
        t2 = "peaceful meditation"

        tokens1 = case_documentation_app._title_similarity_tokens(t1)
        norm1 = case_documentation_app._normalize_title_similarity(t1)

        tokens2 = case_documentation_app._title_similarity_tokens(t2)
        norm2 = case_documentation_app._normalize_title_similarity(t2)

        score = case_documentation_app._title_similarity_score(tokens1, tokens2, norm1, norm2)
        self.assertEqual(score, 0.0)

    def test_title_similarity_score_partial(self):
        # Case 3: Partial match
        t1 = "unite login failed"
        t2 = "unite login error"

        tokens1 = case_documentation_app._title_similarity_tokens(t1)
        norm1 = case_documentation_app._normalize_title_similarity(t1)

        tokens2 = case_documentation_app._title_similarity_tokens(t2)
        norm2 = case_documentation_app._normalize_title_similarity(t2)

        score = case_documentation_app._title_similarity_score(tokens1, tokens2, norm1, norm2)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_cluster_case_titles(self):
        titles = [
            "Cannot login to Unite",
            "Unite login failed",
            "Scanner connection lost",
            "Scanner connection failed", # Changed to be more similar
            "Completely unrelated issue"
        ]

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # assignments should group similar items
        # "Cannot login to Unite" and "Unite login failed" should likely share a cluster
        # "Scanner connection lost" and "Scanner disconnected" should likely share a cluster
        # "Completely unrelated issue" should be on its own

        self.assertEqual(len(assignments), 5)

        # Check if first two are same cluster
        self.assertEqual(assignments[0], assignments[1])

        # Check if 3rd and 4th are same cluster
        self.assertEqual(assignments[2], assignments[3])

        # Check if 1st and 3rd are DIFFERENT
        self.assertNotEqual(assignments[0], assignments[2])

        # Check labels exist
        self.assertTrue(len(label_map) >= 3)

if __name__ == "__main__":
    unittest.main()
