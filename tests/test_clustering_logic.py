
import sys
import unittest
from unittest.mock import MagicMock

# Mock all dependencies
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()

# Internal modules
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Patch builtins to avoid issues with MagicMocks
import json
import dataclasses
import copy

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

# Now import the module under test
try:
    import case_documentation_app
except ImportError:
    # If imports fail despite mocks, we might need to adjust PYTHONPATH
    sys.path.append(".")
    import case_documentation_app

class TestClusteringLogic(unittest.TestCase):
    def setUp(self):
        self._title_similarity_score = case_documentation_app._title_similarity_score
        self._cluster_case_titles = case_documentation_app._cluster_case_titles
        self._normalize = case_documentation_app._normalize_title_similarity
        self._tokenize = case_documentation_app._title_similarity_tokens

    def test_similarity_score_identical(self):
        title = "UniqueTerm XYZ"
        norm = self._normalize(title)
        tokens = self._tokenize(title)
        score = self._title_similarity_score(tokens, tokens, norm, norm)
        self.assertAlmostEqual(score, 1.0)

    def test_similarity_score_disjoint(self):
        t1 = "UniqueTerm Alpha"
        t2 = "UniqueTerm Beta"
        # "UniqueTerm" will be shared.
        # I want completely disjoint.
        t1 = "Alpha Gamma"
        t2 = "Beta Delta"
        tokens1 = self._tokenize(t1)
        tokens2 = self._tokenize(t2)
        norm1 = self._normalize(t1)
        norm2 = self._normalize(t2)
        score = self._title_similarity_score(tokens1, tokens2, norm1, norm2)
        # Assuming "alpha", "beta", "gamma", "delta" are not stopwords
        self.assertEqual(score, 0.0)

    def test_similarity_score_partial(self):
        t1 = "Alpha Gamma Delta"
        t2 = "Alpha Gamma Epsilon"
        tokens1 = self._tokenize(t1)
        tokens2 = self._tokenize(t2)
        norm1 = self._normalize(t1)
        norm2 = self._normalize(t2)
        score = self._title_similarity_score(tokens1, tokens2, norm1, norm2)
        # Jaccard: {alpha, gamma} / {alpha, gamma, delta, epsilon} = 2/4 = 0.5
        # Base: high similarity
        # Score > 0.5
        self.assertGreater(score, 0.5)
        self.assertLess(score, 1.0)

    def test_cluster_case_titles_grouping(self):
        titles = [
            "Alpha Gamma",
            "Alpha Gamma Delta",
            "Beta Delta",
            "Beta Delta Epsilon",
            "Zeta Theta"
        ]
        assignments, labels = self._cluster_case_titles(titles)
        # Expecting 3 clusters: Alpha..., Beta..., Zeta...
        # Indices: 0, 0, 1, 1, 2
        self.assertEqual(assignments[0], assignments[1])
        self.assertEqual(assignments[2], assignments[3])
        self.assertNotEqual(assignments[0], assignments[2])
        self.assertNotEqual(assignments[0], assignments[4])

    def test_min_score_parameter(self):
        # This test verifies the optimization logic if implemented

        # Check if function supports min_score
        import inspect
        sig = inspect.signature(self._title_similarity_score)
        if "min_score" in sig.parameters:
            t1 = "Alpha Gamma"
            t2 = "Alpha Delta"
            tokens1 = self._tokenize(t1)
            tokens2 = self._tokenize(t2)
            norm1 = self._normalize(t1)
            norm2 = self._normalize(t2)

            # Normal score
            # Jaccard: 1/3 = 0.33
            # Max possible = 0.6 + 0.4*0.33 = 0.73

            # If min_score is 0.8, it should return 0.0
            score_opt = self._title_similarity_score(tokens1, tokens2, norm1, norm2, min_score=0.8)
            self.assertEqual(score_opt, 0.0)

if __name__ == "__main__":
    unittest.main()
