
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
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock st.cache_data/resource
def cache_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_mock
st_mock.cache_resource = cache_mock
st_mock.error = MagicMock()

class StreamlitAPIException(Exception):
    pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Patch json.dump to avoid writing mocks to disk during import side-effects
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
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

import case_documentation_app

class TestClustering(unittest.TestCase):
    def test_cluster_case_titles_basic(self):
        titles = [
            "Scanner connection error",
            "Scanner connection failed",
            "Unite login problem",
            "Unite login error",
            "Something completely different",
            "Scanner connection error 2",
        ]

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Verify "Scanner connection..." group together
        # (Assuming the original implementation logic groups them)
        # Note: determinism might be an issue with sets in original implementation if not careful

        # Scanner connection error -> tokens: scanner, connection, error
        # Scanner connection failed -> tokens: scanner, connection, failed
        # Similarity: (2/4)*0.4 + string_sim*0.6 -> likely > 0.68

        self.assertEqual(assignments[0], assignments[1], "Scanner titles should group")
        self.assertEqual(assignments[0], assignments[5], "Scanner titles should group")

        # Verify "Unite login..." group together
        self.assertEqual(assignments[2], assignments[3], "Unite login titles should group")

        # Verify distinct groups
        self.assertNotEqual(assignments[0], assignments[2], "Scanner and Unite should not group")
        self.assertNotEqual(assignments[0], assignments[4], "Scanner and Diff should not group")

    def test_cluster_case_titles_empty(self):
        titles = ["", "   ", "Valid title"]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Empty titles should group together (idx 0 and 1)
        self.assertEqual(assignments[0], assignments[1], "Empty titles should group")
        self.assertNotEqual(assignments[0], assignments[2], "Empty and Valid should not group")

    def test_title_similarity_score(self):
        # We will test the function directly

        tokens_a = {"scanner", "error"}
        tokens_b = {"scanner", "problem"}
        norm_a = "scanner error"
        norm_b = "scanner problem"

        score = case_documentation_app._title_similarity_score(tokens_a, tokens_b, norm_a, norm_b)
        self.assertGreater(score, 0.0)

        tokens_c = {"unite", "login"}
        norm_c = "unite login"

        # Should be low/zero
        score_diff = case_documentation_app._title_similarity_score(tokens_a, tokens_c, norm_a, norm_c)
        # Assuming current implementation returns 0 for disjoint
        self.assertEqual(score_diff, 0.0)

if __name__ == "__main__":
    unittest.main()
