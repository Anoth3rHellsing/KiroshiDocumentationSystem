
import sys
import unittest
from unittest.mock import MagicMock

# Mock dependencies properly
st_mock = MagicMock()
st_mock.cache_resource = lambda *args, **kwargs: lambda func: func
st_mock.cache_data = lambda *args, **kwargs: lambda func: func
st_mock.set_page_config = MagicMock()

# Mock session state
class SessionStateMock(dict):
    def __getattr__(self, key):
        return self.get(key, MagicMock())
    def __setattr__(self, key, value):
        self[key] = value

st_mock.session_state = SessionStateMock()
sys.modules["streamlit"] = st_mock
sys.modules["streamlit.components"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()

sys.modules["json"] = MagicMock() # To prevent issues with json.dump if called

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

sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Import the app
try:
    import case_documentation_app as app
except ImportError:
    sys.path.append(".")
    import case_documentation_app as app

class TestClusteringLogic(unittest.TestCase):
    def test_similarity_score_exact_match(self):
        t1 = "Scanner connection apple"
        norm1 = app._normalize_title_similarity(t1)
        tok1 = app._title_similarity_tokens(t1)

        # Self match should be 1.0
        score = app._title_similarity_score(tok1, tok1, norm1, norm1)
        self.assertAlmostEqual(score, 1.0)

    def test_similarity_score_disjoint(self):
        t1 = "Scanner apple"
        t2 = "Login banana"
        norm1 = app._normalize_title_similarity(t1)
        tok1 = app._title_similarity_tokens(t1)
        norm2 = app._normalize_title_similarity(t2)
        tok2 = app._title_similarity_tokens(t2)

        # These should result in tokens "scanner", "apple" and "login", "banana" (assuming login is not stopword in token set?)
        # Wait _GENERIC_STOPWORDS has "login".
        # So "Login banana" -> "banana".

        score = app._title_similarity_score(tok1, tok2, norm1, norm2)
        # If disjoint, it should return 0.0.
        # Check if tokens are actually present
        if tok1 and tok2:
            self.assertEqual(score, 0.0)
        else:
            # If one set is empty, it falls back to SequenceMatcher, which will be > 0.0
            print(f"Skipping disjoint assertion because tokens empty: {tok1} {tok2}")

    def test_similarity_score_partial(self):
        t1 = "Scanner connection apple"
        t2 = "Scanner connection banana"
        norm1 = app._normalize_title_similarity(t1)
        tok1 = app._title_similarity_tokens(t1)
        norm2 = app._normalize_title_similarity(t2)
        tok2 = app._title_similarity_tokens(t2)

        # {scanner, connection, apple} vs {scanner, connection, banana}
        # Jaccard = 2/4 = 0.5.

        score = app._title_similarity_score(tok1, tok2, norm1, norm2)
        self.assertGreater(score, 0.5)
        self.assertLess(score, 1.0)

    def test_similarity_score_min_score_optimization(self):
        t1 = "Scanner connection apple"
        t2 = "Scanner connection banana"
        norm1 = app._normalize_title_similarity(t1)
        tok1 = app._title_similarity_tokens(t1)
        norm2 = app._normalize_title_similarity(t2)
        tok2 = app._title_similarity_tokens(t2)

        # Verify tokens
        # print(tok1, tok2)

        # Calculate actual score
        actual_score = app._title_similarity_score(tok1, tok2, norm1, norm2)

        # Max possible score logic
        # tokens: {scanner, connection, apple} (3)
        # tokens: {scanner, connection, banana} (3)
        # intersection: 2. union: 4. jaccard: 0.5.
        # max possible = 0.6 + 0.4 * 0.5 = 0.8.

        # If I pass min_score = 0.81. It should return 0.0.
        score_opt = app._title_similarity_score(tok1, tok2, norm1, norm2, min_score=0.81)
        self.assertEqual(score_opt, 0.0)

        # If I pass min_score = 0.79. It should return actual score.
        score_normal = app._title_similarity_score(tok1, tok2, norm1, norm2, min_score=0.79)
        self.assertAlmostEqual(score_normal, actual_score)

    def test_clustering_grouping(self):
        titles = [
            "Scanner issue - 123",
            "Scanner issue - 456",
            "Login failed",
            "Login failed again"
        ]
        # Should result in 2 clusters
        clusters, label_map = app._cluster_case_titles(titles)
        self.assertEqual(len(label_map), 2)
        self.assertEqual(clusters[0], clusters[1]) # Scanner issues grouped
        self.assertEqual(clusters[2], clusters[3]) # Login issues grouped
        self.assertNotEqual(clusters[0], clusters[2])

if __name__ == "__main__":
    unittest.main()
