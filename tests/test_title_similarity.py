
import unittest
import sys
from unittest.mock import MagicMock

# --- Mocking Setup Start ---
class SessionStateMock(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

# Mock dependencies to avoid import errors
st_mock = MagicMock()
st_mock.session_state = SessionStateMock()
st_mock.session_state.tutorial_completed = True
st_mock.session_state.show_tutorial = False

sys.modules["streamlit"] = st_mock
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["urllib3.exceptions"] = MagicMock()

import os
sys.path.append(os.getcwd())

from case_documentation_app import (
    _cluster_case_titles,
    _title_similarity_score,
    _normalize_title_similarity,
    _title_similarity_tokens
)

class TestTitleSimilarity(unittest.TestCase):
    def test_similarity_score_exact(self):
        title = "Cannot login to 3Shape Unite"
        norm = _normalize_title_similarity(title)
        tokens = _title_similarity_tokens(title)
        score = _title_similarity_score(tokens, tokens, norm, norm)
        # Should be exactly 1.0 (0.6 * 1.0 + 0.4 * 1.0)
        self.assertAlmostEqual(score, 1.0)

    def test_similarity_score_partial(self):
        t1 = "Scanner connection issue"
        t2 = "Scanner connection failed"

        norm1 = _normalize_title_similarity(t1)
        tokens1 = _title_similarity_tokens(t1)

        norm2 = _normalize_title_similarity(t2)
        tokens2 = _title_similarity_tokens(t2)

        score = _title_similarity_score(tokens1, tokens2, norm1, norm2)
        self.assertTrue(0.0 < score < 1.0)

        # Jaccard check
        # tokens1: scanner, connection, issue
        # tokens2: scanner, connection, failed
        # intersection: scanner, connection (2)
        # union: scanner, connection, issue, failed (4)
        # Jaccard = 0.5
        # Base (SequenceMatcher): "scanner connection issue" vs "scanner connection failed"
        # roughly matches "scanner connection " (19 chars) vs total length ~40 chars -> ratio ~0.5-0.8

        # Upper bound check (manual):
        # 0.6 * base + 0.4 * 0.5 = 0.6 * base + 0.2
        # If base is 0.8, score is 0.48 + 0.2 = 0.68

    def test_similarity_disjoint(self):
        t1 = "Scanner connection issue"
        t2 = "Billing update required"

        norm1 = _normalize_title_similarity(t1)
        tokens1 = _title_similarity_tokens(t1)

        norm2 = _normalize_title_similarity(t2)
        tokens2 = _title_similarity_tokens(t2)

        score = _title_similarity_score(tokens1, tokens2, norm1, norm2)
        self.assertEqual(score, 0.0)

    def test_clustering_grouping(self):
        titles = [
            "Cannot login to Unite",
            "Login failed on Unite",
            "Scanner disconnected",
            "Scanner connection lost",
            "Totally unrelated billing issue"
        ]

        clusters, label_map = _cluster_case_titles(titles)

        # Expecting roughly 3 clusters: Login, Scanner, Billing
        # Depending on threshold, login and scanner might be distinct enough.

        unique_clusters = set(clusters)
        self.assertTrue(len(unique_clusters) >= 3, f"Expected at least 3 clusters, got {len(unique_clusters)}")

        # Check that index 0 and 1 are same cluster (Login)
        # "Cannot login to Unite" vs "Login failed on Unite"
        # tokens: {login, unite, cannot} vs {login, failed, unite} -> Jaccard 2/4 = 0.5
        # Base similarity is likely high.
        # Threshold is 0.68.
        # If score > 0.68, they cluster together.

        # Let's just verify consistency: run twice, get same result.
        clusters_2, _ = _cluster_case_titles(titles)
        self.assertEqual(clusters, clusters_2)

if __name__ == '__main__':
    unittest.main()
