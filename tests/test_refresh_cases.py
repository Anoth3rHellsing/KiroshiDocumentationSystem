
import sys
import unittest
import time
import json
import datetime
from unittest.mock import MagicMock, patch
from pathlib import Path
import copy
import dataclasses

# Mock dependencies similar to existing tests
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

def cache_data_mock(*args, **kwargs):
    # Check if called as a decorator (with function as first arg)
    if args and callable(args[0]):
        func = args[0]
        # Memoize to replicate singleton behavior for st.cache_resource
        if not hasattr(func, "_cached_val"):
            func._cached_val = None

        def wrapper(*w_args, **w_kwargs):
            # Simple memoization for parameterless functions like _get_refresh_throttle
            if func._cached_val is None:
                func._cached_val = func(*w_args, **w_kwargs)
            return func._cached_val
        return wrapper

    # Called as a factory (with arguments)
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock
st_mock.error = MagicMock()

class StreamlitAPIException(Exception): pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Patches for side effects
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

# To avoid recursion error in deepcopy when importing case_documentation_app
# we will patch deepcopy only after import if needed, or rely on this safe version
original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock): return x
    # If x is likely a Streamlit session state proxy (Mock), return as is
    try:
        return original_deepcopy(x, memo)
    except RecursionError:
        return x
copy.deepcopy = safe_deepcopy

# Important: Patch _snapshot_case_state to avoid deepcopying the session state during import side effects if any
with patch("copy.deepcopy", side_effect=safe_deepcopy):
    import case_documentation_app

class TestRefreshCases(unittest.TestCase):

    def setUp(self):
        # Reset the global cache before each test
        # We need to reset the cached singleton too if we mocked it with memoization
        # But for now, let's just ensure the underlying data structures are fresh
        pass

    def test_refresh_and_get_cases_sorting(self):
        """Test that _refresh_and_get_cases correctly sorts items and populates _updated_ts."""

        # Reset the throttle and cache explicitly
        if hasattr(case_documentation_app, "_get_refresh_throttle"):
             # Access the wrapped function if it was decorated
             pass

        # We can also mock the return value of _get_global_case_cache directly
        # But since we imported the module, it's better to use its internals if possible
        # However, due to my cache_data_mock, _get_refresh_throttle is a wrapper.
        # Let's force a fresh state by mocking the cache retrieval functions inside the test

        mock_throttle = MagicMock()
        mock_throttle.last_run = 0.0
        mock_throttle.data = []

        mock_cache = MagicMock()
        mock_cache.last_scan_ts = 0.0
        mock_cache.data = {}
        # Mock Lock context manager
        mock_cache.lock.__enter__.return_value = None
        mock_cache.lock.__exit__.return_value = None

        with patch("case_documentation_app._get_refresh_throttle", return_value=mock_throttle), \
             patch("case_documentation_app._get_global_case_cache", return_value=mock_cache):

            # Mock os.scandir to return a few files
            mock_entry1 = MagicMock()
            mock_entry1.is_file.return_value = True
            mock_entry1.name = "case1.json"
            mock_entry1.path = "/mock/case1.json"
            mock_entry1.stat.return_value.st_mtime = 1000.0

            mock_entry2 = MagicMock()
            mock_entry2.is_file.return_value = True
            mock_entry2.name = "case2.json"
            mock_entry2.path = "/mock/case2.json"
            mock_entry2.stat.return_value.st_mtime = 2000.0

            # Mock reading file content
            now = datetime.datetime.now()
            dt1 = now - datetime.timedelta(hours=2)
            dt2 = now - datetime.timedelta(hours=1)

            content1 = json.dumps({
                "case_id": "C1",
                "last_modified": dt1.isoformat()
            })
            content2 = json.dumps({
                "case_id": "C2",
                "last_modified": dt2.isoformat()
            })

            with patch("os.scandir") as mock_scandir, \
                patch("pathlib.Path.read_text") as mock_read_text, \
                patch("pathlib.Path.exists") as mock_exists:

                mock_exists.return_value = True

                # Context manager for scandir
                mock_scandir.return_value.__enter__.return_value = [mock_entry1, mock_entry2]

                # Easier approach: patch Path entirely
                with patch("case_documentation_app.Path") as MockPath:
                    # Setup mock path instances
                    p1 = MagicMock()
                    p1.read_text.return_value = content1
                    p1.exists.return_value = True
                    p1.stem = "case1"

                    p2 = MagicMock()
                    p2.read_text.return_value = content2
                    p2.exists.return_value = True
                    p2.stem = "case2"

                    def path_side_effect(path):
                        if str(path).endswith("case1.json"):
                            return p1
                        if str(path).endswith("case2.json"):
                            return p2
                        return MagicMock() # For other paths like directories

                    MockPath.side_effect = path_side_effect
                    MockPath.return_value = MagicMock() # Default

                    cases = case_documentation_app._refresh_and_get_cases()

                    # Check results
                    self.assertEqual(len(cases), 2)

                    # C2 is newer (1 hour ago) than C1 (2 hours ago), so C2 should be first
                    self.assertEqual(cases[0]["case_id"], "C2")
                    self.assertEqual(cases[1]["case_id"], "C1")

                    # Verify _updated_ts presence and correctness
                    self.assertIn("_updated_ts", cases[0])
                    self.assertAlmostEqual(cases[0]["_updated_ts"], dt2.timestamp(), places=3)

                    self.assertIn("_updated_ts", cases[1])
                    self.assertAlmostEqual(cases[1]["_updated_ts"], dt1.timestamp(), places=3)

if __name__ == "__main__":
    unittest.main()
