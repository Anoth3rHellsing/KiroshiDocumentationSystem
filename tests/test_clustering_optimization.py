import sys
import unittest
from unittest.mock import MagicMock, patch
import json
import dataclasses
import copy

# Mock dependencies before importing the app
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
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.fernet"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock st.cache_data to do nothing (passthrough)
def cache_data_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock
st_mock.error = MagicMock()

# Define StreamlitAPIException
class StreamlitAPIException(Exception):
    pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Patch json.dump to avoid writing mocks to disk during import side-effects
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        # Check if obj contains mocks (simple check)
        if isinstance(obj, MagicMock):
            return
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = safe_json_dump

# Patch dataclasses.asdict to handle mocks
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

# Patch deepcopy to handle mocks
original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock):
        return x
    return original_deepcopy(x, memo)
copy.deepcopy = safe_deepcopy

# Import the module under test
import case_documentation_app

class TestClusteringOptimization(unittest.TestCase):
    def test_title_similarity_score_early_exit(self):
        """Test that _title_similarity_score returns 0.0 if max possible score < min_score."""
        tokens_a = {"login", "failed"}
        tokens_b = {"system", "crash"}
        norm_a = "login failed"
        norm_b = "system crash"

        # Jaccard is 0.0. Max possible score = 0.6 + 0.4*0 = 0.6.
        # If min_score is 0.7, it should return 0.0 without needing SequenceMatcher.

        score = case_documentation_app._title_similarity_score(
            tokens_a, tokens_b, norm_a, norm_b, min_score=0.7
        )
        self.assertEqual(score, 0.0)

    def test_title_similarity_score_calculation(self):
        """Test that _title_similarity_score returns correct value when possible >= min_score."""
        tokens_a = {"login", "failed"}
        tokens_b = {"login", "error"}
        norm_a = "login failed"
        norm_b = "login error"

        # Jaccard = 1/3 = 0.333...
        # Max possible = 0.6 + 0.4 * 0.333 = 0.733...

        score = case_documentation_app._title_similarity_score(
            tokens_a, tokens_b, norm_a, norm_b, min_score=0.0
        )
        self.assertGreater(score, 0.0)

        # Calculate expected manually
        from difflib import SequenceMatcher
        base = SequenceMatcher(None, norm_a, norm_b).ratio()
        jaccard = 1/3
        expected = 0.6 * base + 0.4 * jaccard
        self.assertAlmostEqual(score, expected)

    def test_title_similarity_exact_match(self):
        tokens = {"login"}
        norm = "login"
        score = case_documentation_app._title_similarity_score(
            tokens, tokens, norm, norm, min_score=0.9
        )
        self.assertEqual(score, 1.0)

    def test_sequence_matcher_skipped(self):
        # Patch SequenceMatcher in case_documentation_app module to verify it's skipped
        with patch("case_documentation_app.SequenceMatcher") as mock_sm:
            tokens_a = {"login", "failed"}
            tokens_b = {"system", "crash"}
            norm_a = "login failed"
            norm_b = "system crash"

            # Max possible score = 0.6. Min score = 0.7. Should skip.
            score = case_documentation_app._title_similarity_score(
                tokens_a, tokens_b, norm_a, norm_b, min_score=0.7
            )
            self.assertEqual(score, 0.0)
            mock_sm.assert_not_called()

    def test_cluster_case_titles_behavior(self):
        """Test that clustering produces expected results."""
        titles = [
            "Login failed",
            "Login failed again",
            "System crash",
            "Login failure", # Should cluster with "Login failed"
            "Network error"
        ]

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        num_clusters = len(label_map)
        self.assertTrue(1 < num_clusters <= 4)
        self.assertEqual(len(assignments), len(titles))

    def test_early_break_optimization(self):
        """Verify that identical items get clustered efficiently and correctly."""
        titles = ["Same Title"] * 10
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(len(label_map), 1)
        self.assertEqual(set(assignments), {0})

if __name__ == "__main__":
    unittest.main()
