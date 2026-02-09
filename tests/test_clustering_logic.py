
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import types
import dataclasses
import copy
import hashlib

# Mock dependencies
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

# Mock kiroshi dependencies
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock heavy libs
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()

def cache_data_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock
st_mock.error = MagicMock()

class StreamlitAPIException(Exception): pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Patches for side effects
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    if isinstance(obj, MagicMock): return
    try: original_json_dump(obj, fp, **kwargs)
    except TypeError: pass
json.dump = safe_json_dump

original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock): return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock): return x
    return original_deepcopy(x, memo)
copy.deepcopy = safe_deepcopy

# Mock Path.mkdir to avoid filesystem errors during import
with patch("pathlib.Path.mkdir"):
    import case_documentation_app

class TestClusteringLogic(unittest.TestCase):

    def test_title_similarity_score_optimization(self):
        """Verify that _title_similarity_score respects min_score."""

        # Overlapping sets but low Jaccard
        # A: {'apple', 'banana', 'cherry'}
        # B: {'apple', 'date', 'elderberry'}
        # Intersection: 1, Union: 5, Jaccard: 0.2
        # Max score: 0.6 + 0.4 * 0.2 = 0.68

        tokens_a = {'apple', 'banana', 'cherry'}
        tokens_b = {'apple', 'date', 'elderberry'}
        norm_a = "apple banana cherry"
        norm_b = "apple date elderberry"

        # If min_score is 0.7, it should be pruned
        score = case_documentation_app._title_similarity_score(
            tokens_a, tokens_b, norm_a, norm_b, min_score=0.7
        )
        self.assertEqual(score, 0.0, "Should be pruned by optimization (0.68 < 0.7)")

        # If min_score is 0.6, it should proceed (and return non-zero real score)
        score = case_documentation_app._title_similarity_score(
            tokens_a, tokens_b, norm_a, norm_b, min_score=0.6
        )
        self.assertGreater(score, 0.0, "Should not be pruned")

    def test_clustering_correctness(self):
        """Verify clustering logic still groups similar titles correctly."""
        titles = [
            "Connection error with scanner",
            "Connection error with scanner 123", # Extremely similar
            "Login failed",
            "Login failed completely",           # Extremely similar
            "Random unrelated issue"
        ]

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        cluster_ids = assignments

        # First two should match
        self.assertEqual(cluster_ids[0], cluster_ids[1],
                         f"Scanner issues should cluster. Got {cluster_ids[0]} and {cluster_ids[1]}")

        # Next two should match
        self.assertEqual(cluster_ids[2], cluster_ids[3],
                         f"Login issues should cluster. Got {cluster_ids[2]} and {cluster_ids[3]}")

        # Groups should be different
        self.assertNotEqual(cluster_ids[0], cluster_ids[2], "Groups should be distinct")
        self.assertNotEqual(cluster_ids[0], cluster_ids[4], "Random issue should be distinct")

if __name__ == "__main__":
    unittest.main()
