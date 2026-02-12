
import unittest
from unittest.mock import MagicMock
import sys
import types

# Helper to create a mock module
def create_mock_module(name):
    m = MagicMock()
    sys.modules[name] = m
    return m

# Better SessionState mock
class SessionState(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'SessionState' object has no attribute '{key}'")
    def __setattr__(self, key, value):
        self[key] = value

# Mock streamlit and its submodules
st_mock = create_mock_module("streamlit")
st_mock.session_state = SessionState()
st_mock.secrets = {}
st_mock.cache_resource = lambda func=None, **kwargs: (lambda f: f) if func is None else func
st_mock.cache_data = lambda func=None, **kwargs: (lambda f: f) if func is None else func

st_errors = create_mock_module("streamlit.errors")
st_errors.StreamlitAPIException = Exception

st_components = create_mock_module("streamlit.components.v1")

# Mock reportlab
create_mock_module("reportlab")
create_mock_module("reportlab.lib")
create_mock_module("reportlab.lib.pagesizes")
create_mock_module("reportlab.lib.colors")
create_mock_module("reportlab.lib.styles")
create_mock_module("reportlab.platypus")
create_mock_module("reportlab.graphics.shapes")
create_mock_module("reportlab.graphics.widgets.markers")

# Mock kiroshi modules
kiroshi_chat = create_mock_module("kiroshi_chat")
kiroshi_chat.load_memory.return_value = []
kiroshi_chat.KIROSHI_MESSAGES = []

create_mock_module("kiroshi_local_ai")
create_mock_module("kiroshi_cloud_sync")
create_mock_module("kiroshi_video")
create_mock_module("kiroshi_hotkeys")

# Mock pynput and others that might cause issues
create_mock_module("pynput")
create_mock_module("pyautogui")
create_mock_module("pyperclip")

# Import the module under test
import case_documentation_app

class TestClustering(unittest.TestCase):
    def test_clustering_logic(self):
        titles = [
            "Scanner connection lost",
            "Scanner disconnected",
            "Login failed",
            "Cannot login",
            "Completely different issue",
            "Scanner connection lost",
        ]

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        self.assertEqual(len(assignments), len(titles))
        self.assertEqual(assignments[0], assignments[5], "Exact match should cluster together")

        print(f"Assignments: {assignments}")
        print(f"Labels: {label_map}")

    def test_title_similarity_score(self):
        # Test exact match
        tokens_a = {"scanner", "connection", "lost"}
        norm_a = "scanner connection lost"
        score = case_documentation_app._title_similarity_score(tokens_a, tokens_a, norm_a, norm_a)
        self.assertAlmostEqual(score, 1.0)

        # Test no match
        tokens_b = {"login", "failed"}
        norm_b = "login failed"
        score = case_documentation_app._title_similarity_score(tokens_a, tokens_b, norm_a, norm_b)
        self.assertEqual(score, 0.0)

if __name__ == "__main__":
    unittest.main()
