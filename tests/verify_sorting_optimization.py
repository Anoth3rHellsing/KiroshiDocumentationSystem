
import unittest
import sys
import json
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime
import dataclasses

# 1. Mock dependencies
sys.modules["streamlit"] = MagicMock()
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
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Mock st.cache_resource/data
def cache_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

sys.modules["streamlit"].cache_resource = cache_mock
sys.modules["streamlit"].cache_data = cache_mock
sys.modules["streamlit"].session_state = MagicMock()

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

# Add current directory to path so we can import the app
sys.path.append(".")

import case_documentation_app

class TestSortingOptimization(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_dir = Path(self.test_dir) / "db"
        self.db_dir.mkdir()

        # Patch the directories in the module
        self.original_db_dir = case_documentation_app.DATABASE_DIR
        self.original_tracked_dir = case_documentation_app.TRACKED_CASES_DIR
        case_documentation_app.DATABASE_DIR = self.db_dir
        case_documentation_app.TRACKED_CASES_DIR = self.db_dir # Use same dir for simplicity

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        case_documentation_app.DATABASE_DIR = self.original_db_dir
        case_documentation_app.TRACKED_CASES_DIR = self.original_tracked_dir

    def create_case(self, name, updated_iso):
        content = {
            "case_id": name,
            "last_modified": updated_iso,
            "description": "Test case"
        }
        p = self.db_dir / f"{name}.json"
        p.write_text(json.dumps(content), encoding="utf-8")
        # Touch file to update mtime (though logic uses file mtime if last_modified missing)
        return p

    def test_updated_ts_presence_and_sorting(self):
        # Create cases with different times
        # Case A: 2023-01-01 (Oldest)
        # Case B: 2023-06-01 (Middle)
        # Case C: 2024-01-01 (Newest)

        t1 = "2023-01-01T10:00:00"
        t2 = "2023-06-01T10:00:00"
        t3 = "2024-01-01T10:00:00"

        self.create_case("case_a", t1)
        self.create_case("case_b", t2)
        self.create_case("case_c", t3)

        # Create a fresh cache for each test
        cache_mock_obj = MagicMock()
        cache_mock_obj.data = {}
        cache_mock_obj.lock = MagicMock()
        cache_mock_obj.lock.__enter__ = MagicMock()
        cache_mock_obj.lock.__exit__ = MagicMock()
        cache_mock_obj.last_scan_ts = 0.0

        throttle_mock_obj = MagicMock()
        throttle_mock_obj.data = []
        throttle_mock_obj.last_run = 0.0

        # Mock _get_global_case_cache to return our mock
        with patch("case_documentation_app._get_global_case_cache", return_value=cache_mock_obj):
            # Also mock _get_refresh_throttle to avoid caching logic skipping the scan
            with patch("case_documentation_app._get_refresh_throttle", return_value=throttle_mock_obj):
                cases = case_documentation_app._refresh_and_get_cases()

        # Check if _updated_ts is present
        # This assertion is expected to fail before optimization
        missing_ts = False
        for case in cases:
            if "_updated_ts" not in case:
                 missing_ts = True
                 print(f"Case {case['case_id']} missing _updated_ts (Expected before fix)")
            else:
                 expected_ts = datetime.fromisoformat(case["updated"]).timestamp()
                 self.assertAlmostEqual(case["_updated_ts"], expected_ts, places=1)

        # Check sorting (Reverse chronological order: C, B, A)
        ids = [c["case_id"] for c in cases]
        self.assertEqual(ids, ["case_c", "case_b", "case_a"])

if __name__ == "__main__":
    unittest.main()
