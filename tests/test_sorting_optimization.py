
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
import datetime
from pathlib import Path
import dataclasses

# Mock dependencies before importing
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
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock st.cache_data/resource
def cache_data_mock(*args, **kwargs):
    if args and callable(args[0]):
        return args[0]
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock
st_mock.error = MagicMock()

# Patch json.dump to avoid side-effects
json.dump = MagicMock()

# Patch dataclasses.asdict to handle mocks
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

# Ensure we can import the app from root
sys.path.append(str(Path(__file__).parent.parent))

try:
    import case_documentation_app
except ImportError:
    # If running from inside tests directory, root might not be in path
    sys.path.append("..")
    import case_documentation_app

class TestSortingOptimization(unittest.TestCase):
    def setUp(self):
        pass

    def test_sorting_performance(self):
        # Create persistent cache objects
        global_cache = case_documentation_app._CaseCache()
        refresh_throttle = case_documentation_app._RefreshThrottle()

        # Mock file system with many files
        num_files = 1000
        mock_entries = []
        mock_file_content = {}

        base_time = time.time()

        for i in range(num_files):
            mtime = base_time - (i * 100) # different times
            path = f"/tmp/case_{i}.json"

            entry = MagicMock()
            entry.is_file.return_value = True
            entry.name = f"case_{i}.json"
            entry.path = path
            entry.stat.return_value.st_mtime = mtime
            mock_entries.append(entry)

            # Create content with last_modified matching mtime
            dt = datetime.datetime.fromtimestamp(mtime).replace(microsecond=0)
            iso = dt.isoformat()

            content = {
                "case_id": f"CASE-{i}",
                "last_modified": iso
            }
            mock_file_content[path] = json.dumps(content)

        # Context manager for scandir
        def mock_scandir(path):
            class MockScandirIterator:
                def __enter__(self):
                    return mock_entries
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
            return MockScandirIterator()

        # Mock Path.read_text
        def mock_read_text(self, encoding=None, errors=None):
            return mock_file_content.get(str(self), "{}")

        # Patch the accessor functions to return these singletons
        with patch("case_documentation_app._get_global_case_cache", return_value=global_cache), \
             patch("case_documentation_app._get_refresh_throttle", return_value=refresh_throttle), \
             patch("os.scandir", side_effect=mock_scandir), \
             patch("pathlib.Path.read_text", side_effect=mock_read_text, autospec=True), \
             patch("pathlib.Path.exists", return_value=True):

            # First run (populate cache)
            t0 = time.perf_counter()
            result1 = case_documentation_app._refresh_and_get_cases()
            t1 = time.perf_counter()
            print(f"First run (scan): {t1-t0:.4f}s")

            # Verify result length
            self.assertEqual(len(result1), num_files)

            # Verify sort order (newest first)
            self.assertEqual(result1[0]["case_id"], "CASE-0")
            self.assertEqual(result1[-1]["case_id"], f"CASE-{num_files-1}")

            # Second run (cache hit)
            # Force bypass first throttle check to exercise sorting logic on cached data
            refresh_throttle.last_run = 0.0

            t2 = time.perf_counter()
            result2 = case_documentation_app._refresh_and_get_cases()
            t3 = time.perf_counter()
            print(f"Second run (cache hit + sorting): {t3-t2:.4f}s")

            self.assertEqual(len(result2), num_files)
            self.assertEqual(result1, result2)

if __name__ == "__main__":
    unittest.main()
