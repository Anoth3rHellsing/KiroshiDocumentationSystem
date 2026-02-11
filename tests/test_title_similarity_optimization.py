
import unittest
from unittest.mock import patch, MagicMock
import sys
import dataclasses
import copy
import json

# Mock dependencies to import the module
st_mock = MagicMock()
st_mock.session_state = MagicMock()
# Ensure dictionary-like behavior for session_state
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.get = MagicMock(return_value=None)
st_mock.cache_data = lambda *args, **kwargs: lambda func: func
st_mock.cache_resource = lambda *args, **kwargs: lambda func: func

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
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["urllib3.exceptions"] = MagicMock()

# Patch dataclasses.asdict to handle mocks or module-level execution issues
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    try:
        return original_asdict(obj, dict_factory=dict_factory)
    except TypeError:
        return {}
dataclasses.asdict = safe_asdict

# Patch filesystem operations to avoid side effects during import
with patch("pathlib.Path.mkdir"), \
     patch("pathlib.Path.write_text"), \
     patch("pathlib.Path.exists", return_value=True), \
     patch("builtins.open", MagicMock()), \
     patch("json.dump", MagicMock()), \
     patch("json.load", return_value={}):

    import case_documentation_app
    from case_documentation_app import (
        _title_similarity_score,
        _cluster_case_titles,
        _title_similarity_tokens,
        _normalize_title_similarity
    )

class TestTitleSimilarityOptimization(unittest.TestCase):
    def test_similarity_pruning(self):
        """Verify that SequenceMatcher is skipped when theoretical max score is too low."""

        tokens_a = {"scanner", "connecting"}
        tokens_b = {"license", "expired"}
        norm_a = "scanner not connecting"
        norm_b = "license expired"

        # Patch the name imported in the module
        with patch("case_documentation_app.SequenceMatcher") as mock_matcher:
            score = _title_similarity_score(tokens_a, tokens_b, norm_a, norm_b, min_score=0.7)
            self.assertEqual(score, 0.0)
            mock_matcher.assert_not_called()

    def test_similarity_no_pruning(self):
        """Verify SequenceMatcher IS called when score could be high enough."""

        tokens_a = {"scanner", "connecting"}
        tokens_b = {"scanner", "connection"}
        norm_a = "scanner connecting"
        norm_b = "scanner connection"

        with patch("case_documentation_app.SequenceMatcher") as mock_matcher:
            mock_instance = mock_matcher.return_value
            mock_instance.ratio.return_value = 0.9 # Fake high string similarity

            score = _title_similarity_score(tokens_a, tokens_b, norm_a, norm_b, min_score=0.7)

            mock_matcher.assert_called()
            # Score = 0.6 * 0.9 + 0.4 * (1/3) = 0.54 + 0.133 = 0.673
            self.assertAlmostEqual(score, 0.6 * 0.9 + 0.4 * (1/3), places=2)

    def test_clustering_correctness(self):
        """Ensure clustering still groups obvious duplicates."""
        titles = [
            "Scanner connection error", # Tokens: {scanner, connection}
            "Scanner connection problem", # Tokens: {scanner, connection} -> Jaccard 1.0, should cluster
            "License expired",
            "License expired error", # Tokens: {license, expired} -> Jaccard 1.0, should cluster
            "Totally unrelated issue"
        ]

        # This uses the real SequenceMatcher (unless patched globally, which we shouldn't)
        assignments, labels = _cluster_case_titles(titles)

        # Expect 3 clusters
        # 0: Scanner...
        # 1: Scanner... -> maps to 0
        # 2: License...
        # 3: License... -> maps to 2
        # 4: Unrelated

        self.assertEqual(len(labels), 3, f"Expected 3 clusters, got {len(labels)}: {labels}")

        # Verify grouping
        self.assertEqual(assignments[0], assignments[1], "Scanner issues should group together")
        self.assertEqual(assignments[2], assignments[3], "License issues should group together")
        self.assertNotEqual(assignments[0], assignments[2])
        self.assertNotEqual(assignments[0], assignments[4])

if __name__ == "__main__":
    unittest.main()
