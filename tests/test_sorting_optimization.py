
import unittest
import tempfile
import shutil
import os
import time
import json
import dataclasses
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

# Mock dependencies
st_mock = MagicMock()
def cache_mock(*args, **kwargs):
    def decorator(func):
        return func
    if len(args) == 1 and callable(args[0]):
         return args[0]
    return decorator

st_mock.cache_resource = cache_mock
st_mock.cache_data = cache_mock
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
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["openai"] = MagicMock()

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

# Patch json.dump/load etc if needed, but for this test we might be fine importing
# provided we patch DATABASE_DIR and TRACKED_CASES_DIR

sys.path.append(os.getcwd())
import case_documentation_app

class TestRefreshCasesLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_dir = Path(self.test_dir) / "db"
        self.tracked_dir = Path(self.test_dir) / "tracked"
        self.db_dir.mkdir()
        self.tracked_dir.mkdir()

        # Patch globals
        self.orig_db_dir = case_documentation_app.DATABASE_DIR
        self.orig_tracked_dir = case_documentation_app.TRACKED_CASES_DIR
        case_documentation_app.DATABASE_DIR = self.db_dir
        case_documentation_app.TRACKED_CASES_DIR = self.tracked_dir

        # Clear cache
        cache = case_documentation_app._get_global_case_cache()
        cache.data.clear()
        cache.last_scan_ts = 0.0

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        case_documentation_app.DATABASE_DIR = self.orig_db_dir
        case_documentation_app.TRACKED_CASES_DIR = self.orig_tracked_dir

    def test_refresh_sorting(self):
        # Create 3 cases with different times
        case1 = {"case_id": "c1", "last_modified": "2023-01-01T10:00:00"}
        case2 = {"case_id": "c2", "last_modified": "2023-01-02T10:00:00"}
        case3 = {"case_id": "c3", "last_modified": "2023-01-01T12:00:00"}

        (self.db_dir / "c1.json").write_text(json.dumps(case1))
        (self.db_dir / "c2.json").write_text(json.dumps(case2))
        (self.db_dir / "c3.json").write_text(json.dumps(case3))

        # Force cache refresh
        throttle = case_documentation_app._get_refresh_throttle()
        throttle.last_run = 0.0

        cases = case_documentation_app._refresh_and_get_cases()

        # Expect order: c2 (Jan 2), c3 (Jan 1 12:00), c1 (Jan 1 10:00)
        self.assertEqual(len(cases), 3)
        self.assertEqual(cases[0]["case_id"], "c2")
        self.assertEqual(cases[1]["case_id"], "c3")
        self.assertEqual(cases[2]["case_id"], "c1")

        # Verify _updated_ts is present (if optimized) or just verify sorting works
        # If I haven't applied the optimization yet, this test should still pass.
        # After optimization, it should also pass.

        # Also verify cache works
        throttle.last_run = time.time()
        cases_cached = case_documentation_app._refresh_and_get_cases()
        self.assertEqual(cases, cases_cached)

if __name__ == "__main__":
    unittest.main()
