
import unittest
import sys
import os
import dataclasses
from unittest.mock import MagicMock

# Monkeypatch dataclasses.asdict
original_asdict = dataclasses.asdict
def mock_asdict(obj, *, dict_factory=dict):
    return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}
dataclasses.asdict = mock_asdict

# Setup Mocks
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()

reportlab_mock = MagicMock()
sys.modules["reportlab"] = reportlab_mock
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()

sys.modules["tkinter"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()

class MockSessionState(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'MockSessionState' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        self[key] = value

mock_session_state = MockSessionState()
mock_session_state._autosave_loaded = False
sys.modules["streamlit"].session_state = mock_session_state

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from case_documentation_app import _cluster_case_titles
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

class TestClusteringLogic(unittest.TestCase):
    def test_exact_matches(self):
        titles = ["Error de red", "Error de red", "Other issue"]
        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[0], assignments[2])

    def test_similar_titles(self):
        # "Printer Connection" and "Printer Connection Lost"
        # Shared tokens: printer, connection. (Assuming neither are stopwords)
        # Should cluster together.
        titles = ["Printer Connection", "Printer Connection Lost"]
        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])

    def test_distinct_titles(self):
        titles = ["Printer not working", "Network down"]
        assignments, labels = _cluster_case_titles(titles)
        self.assertNotEqual(assignments[0], assignments[1])

    def test_empty_titles(self):
        titles = ["", "   ", "Valid title"]
        assignments, labels = _cluster_case_titles(titles)
        # Empty titles should be clustered together (or to a generic empty cluster)
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[0], assignments[2])

    def test_empty_tokens_but_different_normalized(self):
        # Titles that normalize to something but have no tokens (e.g. only stopwords if all words are stopwords)
        # Assuming stopwords are removed.
        # "The The" might result in empty tokens if "the" is a stopword.
        # But `_cluster_case_titles` checks `if not normalized and not tokens`.
        # If normalized is not empty, it goes to similarity check.
        # If tokens are empty, it scans ALL clusters.
        pass

if __name__ == "__main__":
    unittest.main()
