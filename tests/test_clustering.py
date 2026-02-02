
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add root to path
sys.path.append(os.getcwd())

# Mock streamlit and other dependencies
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Mock st attributes that are accessed
import streamlit as st
st.cache_resource = lambda func=None, **kwargs: (lambda f: f) if func is None else func
st.cache_data = lambda func=None, **kwargs: (lambda f: f) if func is None else func

class MockSessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

st.session_state = MockSessionState()

# Now import
from case_documentation_app import _cluster_case_titles, _title_similarity_score, _title_similarity_tokens

class TestClustering(unittest.TestCase):
    def test_title_similarity_score(self):
        # High similarity
        t1 = {"error", "scanner", "connection"}
        t2 = {"error", "scanner", "connection"}
        score = _title_similarity_score(t1, t2, "error scanner connection", "error scanner connection")
        self.assertEqual(score, 1.0)

        # Partial similarity
        t3 = {"error", "scanner"}
        score = _title_similarity_score(t3, t1, "error scanner", "error scanner connection")
        # Jaccard: 2/3. Base: ~0.7. Score: 0.6*0.7 + 0.4*0.66 ~ 0.42 + 0.26 = 0.68
        self.assertGreater(score, 0.6)

        # Disjoint
        t4 = {"printer", "jam"}
        score = _title_similarity_score(t4, t1, "printer jam", "error scanner connection")
        self.assertEqual(score, 0.0)

        # Threshold optimization check
        # With threshold 0.9, the partial match should fail early and return 0.0
        # (Assuming max possible is checked correctly)
        # For t3 vs t1: Jaccard 0.66. Max score 0.6 + 0.4*0.66 = 0.866.
        # If threshold is 0.9, it should return 0.0.
        score_thresh = _title_similarity_score(t3, t1, "error scanner", "error scanner connection", threshold=0.9)
        self.assertEqual(score_thresh, 0.0)

    def test_clustering_exact(self):
        titles = ["Scanner Error", "Scanner Error"]
        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(assignments, [0, 0])
        self.assertEqual(len(labels), 1)

    def test_clustering_similar(self):
        titles = ["Scanner Error Connection", "Scanner Connection Error"]
        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(assignments, [0, 0])

    def test_clustering_distinct(self):
        titles = ["Scanner Error", "Printer Jam"]
        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(assignments, [0, 1])
        self.assertEqual(len(labels), 2)

    def test_clustering_tokenless(self):
        # Assuming stopwords are removed. "the" is likely a stopword.
        titles = ["the", "the"]
        assignments, labels = _cluster_case_titles(titles)
        # Should be assigned to blank cluster or similar if they match by string
        self.assertEqual(assignments[0], assignments[1])

if __name__ == "__main__":
    unittest.main()
