
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import types
import dataclasses
import copy
import random
import string

# Mock dependencies before importing the app
st_mock = MagicMock()
# Mock session_state as a MagicMock to allow attribute access
st_mock.session_state = MagicMock()
# Ensure dictionary-like behavior for session_state if needed (though app uses attribute access mostly)
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.get = MagicMock(return_value=None)

# Inject mocks into sys.modules
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
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
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

# Add parent directory to path to find case_documentation_app.py
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Configure mock handler
mock_handler = MagicMock()
mock_handler.level = 0 # NOTSET

# Patch Path.mkdir to avoid filesystem errors during import
# Also mock kiroshi_chat which is imported by case_documentation_app
# Patch RotatingFileHandler to avoid logging errors with mocks
# Patch read_bytes to avoid logo rendering crash
with patch("pathlib.Path.mkdir"), \
     patch("pathlib.Path.write_text"), \
     patch("pathlib.Path.read_bytes", return_value=b"fake_logo"), \
     patch("pathlib.Path.open", new_callable=MagicMock), \
     patch("builtins.open", new_callable=MagicMock), \
     patch("logging.handlers.RotatingFileHandler", return_value=mock_handler), \
     patch("kiroshi_chat.load_memory", return_value=[]), \
     patch("kiroshi_chat.load_manual_docs", return_value=[]):
    import case_documentation_app

class TestTitleSimilarityOptimization(unittest.TestCase):
    def setUp(self):
        # Generate synthetic titles
        self.titles = []
        base_titles = [
            "Scanner connection lost",
            "Scanner disconnected",
            "TRIOS scanner not found",
            "Login failed on Unite",
            "Cannot sign in to Unite",
            "Unite authentication error",
            "Calibration failed",
            "Tip calibration error",
            "Scan quality issues",
            "Artifacts in scan",
            "Missing margin lines",
            "Dental System freezing",
            "Dental Manager crash",
            "Order form not saving",
            "Cannot send case",
            "Case upload stuck",
            "Proxy error when sending",
            "Firewall blocking connection",
            "License expired",
            "Dongle not recognized"
        ]

        # Create variations
        for base in base_titles:
            self.titles.append(base)
            # Add some noise
            for _ in range(5):
                noise = "".join(random.choices(string.ascii_lowercase, k=5))
                self.titles.append(f"{base} {noise}")
            # Add some very similar ones
            self.titles.append(f"{base} issue")
            self.titles.append(f"{base} error")

        # Add random distinct titles
        for _ in range(100):
            words = ["".join(random.choices(string.ascii_lowercase, k=random.randint(4, 8))) for _ in range(3)]
            self.titles.append(" ".join(words))

        # Shuffle
        random.shuffle(self.titles)
        # Duplicate to increase load (aiming for ~400-500 items)
        self.titles = self.titles * 2
        print(f"Benchmarking with {len(self.titles)} titles...")

    def test_clustering_performance(self):
        start_time = time.perf_counter()
        assignments, label_map = case_documentation_app._cluster_case_titles(self.titles)
        end_time = time.perf_counter()

        duration = end_time - start_time
        print(f"Clustering took {duration:.4f} seconds")

        # Verify correctness (basic sanity check)
        self.assertEqual(len(assignments), len(self.titles))
        self.assertTrue(len(label_map) > 0)

        # Verify specific behavior of _title_similarity_score if min_score is supported
        # This part will only run correctly after optimization, but currently it just benchmarks.

        # Check a known similarity pair
        t1 = "Scanner connection lost"
        t2 = "Scanner connection lost issue"
        norm1 = case_documentation_app._normalize_title_similarity(t1)
        norm2 = case_documentation_app._normalize_title_similarity(t2)
        tok1 = case_documentation_app._title_similarity_tokens(t1)
        tok2 = case_documentation_app._title_similarity_tokens(t2)

        # If the function signature has changed, we test with min_score
        import inspect
        sig = inspect.signature(case_documentation_app._title_similarity_score)
        if 'min_score' in sig.parameters:
            score = case_documentation_app._title_similarity_score(tok1, tok2, norm1, norm2, min_score=0.5)
            self.assertGreater(score, 0.5)

            # Test pruning
            # Max possible score for disjoint tokens is 0.0 (if tokens present)
            # But here they overlap. Let's find disjoint ones.
            t3 = "Completely different topic"
            tok3 = case_documentation_app._title_similarity_tokens(t3)
            norm3 = case_documentation_app._normalize_title_similarity(t3)

            # These are disjoint, should be 0.0
            score_disjoint = case_documentation_app._title_similarity_score(tok1, tok3, norm1, norm3, min_score=0.1)
            self.assertEqual(score_disjoint, 0.0)

if __name__ == "__main__":
    unittest.main()
