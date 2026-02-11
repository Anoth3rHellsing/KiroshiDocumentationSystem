
import sys
import unittest
from unittest.mock import MagicMock
import dataclasses

# --- MOCKING SETUP START ---
st_mock = MagicMock()
st_mock.session_state = MagicMock()
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.get = MagicMock(return_value=None)
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
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
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

def cache_data_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock

# Patch Path
from pathlib import Path
original_mkdir = Path.mkdir
original_write_text = Path.write_text
original_exists = Path.exists
Path.mkdir = MagicMock()
Path.write_text = MagicMock()
Path.exists = MagicMock(return_value=True)

# Patch dataclasses
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

try:
    from case_documentation_app import _cluster_case_titles, _title_similarity_score
except ImportError:
    pass
finally:
    Path.mkdir = original_mkdir
    Path.write_text = original_write_text
    Path.exists = original_exists
    dataclasses.asdict = original_asdict
# --- MOCKING SETUP END ---

class TestTitleSimilarityOptimization(unittest.TestCase):
    def test_title_similarity_score_pruning(self):
        # Case 1: Disjoint tokens -> should be 0.0
        tokens_a = {"apple", "banana"}
        tokens_b = {"cherry", "date"}
        score = _title_similarity_score(tokens_a, tokens_b, "apple banana", "cherry date", min_score=0.1)
        self.assertEqual(score, 0.0)

        # Case 2: Low Jaccard, high min_score -> pruned
        # Intersection = 1 (apple), Union = 3 (apple, banana, cherry). Jaccard = 0.33.
        # Max score = 0.6 + 0.4 * 0.33 = 0.733.
        # If min_score = 0.8, it should return 0.0
        tokens_a = {"apple", "banana"}
        tokens_b = {"apple", "cherry"}
        score = _title_similarity_score(tokens_a, tokens_b, "apple banana", "apple cherry", min_score=0.8)
        self.assertEqual(score, 0.0)

        # Case 3: Low Jaccard, low min_score -> not pruned (returns actual score)
        # SequenceMatcher ratio for "apple banana" vs "apple cherry": "apple " matches.
        # "banana" vs "cherry" no match. Ratio approx 0.5.
        # Score approx 0.6*0.5 + 0.4*0.33 = 0.3 + 0.132 = 0.432.
        score = _title_similarity_score(tokens_a, tokens_b, "apple banana", "apple cherry", min_score=0.1)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 0.75) # Should be less than max possible

    def test_clustering_basic(self):
        titles = [
            "Cannot login to Unite",
            "Unite login failure",
            "Scanner connection lost",
            "Scanner disconnected"
        ]
        # Current algorithm produces 3 clusters because "Scanner connection lost" and "Scanner disconnected"
        # have low similarity score (only sharing "Scanner" token and low string similarity).
        assignments, labels = _cluster_case_titles(titles)

        # Verify that "Cannot login to Unite" and "Unite login failure" are clustered together
        self.assertEqual(assignments[0], assignments[1])

        # Verify that we have at least 2 clusters (login vs scanner)
        self.assertGreaterEqual(len(labels), 2)

if __name__ == "__main__":
    unittest.main()
