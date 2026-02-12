
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import types
import dataclasses
import copy

# Mock dependencies before importing the app
st_mock = MagicMock()
# Mock session_state as a MagicMock to allow attribute access
st_mock.session_state = MagicMock()
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.get = MagicMock(return_value=None)
st_mock.query_params = MagicMock(return_value={})

sys.modules["streamlit"] = st_mock
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["reportlab.pdfbase"] = MagicMock()
sys.modules["reportlab.pdfbase.pdfdoc"] = MagicMock()
sys.modules["reportlab.rl_config"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.hazmat"] = MagicMock()
sys.modules["cryptography.hazmat.primitives"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf.pbkdf2"] = MagicMock()
sys.modules["cryptography.hazmat.backends"] = MagicMock()

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

# Patch open to avoid writing files
original_open = open
def safe_open(file, mode='r', *args, **kwargs):
    if 'w' in mode or 'a' in mode:
        return MagicMock()
    try:
        return original_open(file, mode, *args, **kwargs)
    except OSError:
        return MagicMock() # Fallback for non-existent files during import

import builtins
builtins.open = safe_open

try:
    import case_documentation_app
except ImportError:
    # If import fails, we might be running from root
    sys.path.append('.')
    import case_documentation_app

class TestClustering(unittest.TestCase):
    def test_title_similarity_score_basic(self):
        # Basic similarity check
        score = case_documentation_app._title_similarity_score(
            {"test", "case"}, {"test", "case"}, "test case", "test case"
        )
        self.assertAlmostEqual(score, 1.0)

        score = case_documentation_app._title_similarity_score(
            {"test", "case"}, {"other", "thing"}, "test case", "other thing"
        )
        self.assertEqual(score, 0.0)

    def test_cluster_case_titles_grouping(self):
        titles = [
            "Connection issue with server",
            "Connection issue with server",
            "Scanner disconnected",
            "Scanner disconnected from PC",
            "Login failed",
        ]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Expecting:
        # 0 and 1 should be same cluster (identical)
        # 2 and 3 should be same cluster (similar)
        # 4 should be separate

        self.assertEqual(assignments[0], assignments[1])
        self.assertEqual(assignments[2], assignments[3])
        self.assertNotEqual(assignments[0], assignments[2])
        self.assertNotEqual(assignments[0], assignments[4])

        unique_clusters = set(assignments)
        self.assertEqual(len(unique_clusters), 3)

    def test_optimization_logic(self):
        # This test ensures that passing min_score doesn't break logic
        # Even if the current implementation ignores it (before optimization)
        # After optimization, it should still work correctly.

        # This will be tested implicitly by running the same tests after optimization.
        pass

if __name__ == "__main__":
    unittest.main()
