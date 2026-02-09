
import sys
import unittest
from unittest.mock import MagicMock, patch, mock_open
import datetime
import time
import json
import os

# Mock streamlit before importing case_documentation_app
mock_st = MagicMock()
sys.modules["streamlit"] = mock_st
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()

# Setup session state mock
class MockSessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

mock_st.session_state = MockSessionState()

# Mock cache decorators to just execute the function
def mock_cache(func=None, **kwargs):
    if func and callable(func):
        return func
    def wrapper(f):
        return f
    return wrapper

mock_st.cache_resource = mock_cache
mock_st.cache_data = mock_cache

sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()

# Mock other dependencies
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Need to patch Path.mkdir to avoid actual filesystem access during import
with patch("pathlib.Path.mkdir"):
    import case_documentation_app

class TestSortingOptimization(unittest.TestCase):
    def setUp(self):
        # Reset cache - but since we mocked the decorator to pass through,
        # _get_global_case_cache returns a new instance every time?
        # No, the function creates a new instance.
        # But case_documentation_app relies on the decorator to cache it.
        # Since we removed caching, every call creates a new instance.
        # This is fine for testing as we want a fresh state.
        pass

    @patch("case_documentation_app.DATABASE_DIR")
    @patch("case_documentation_app.TRACKED_CASES_DIR")
    @patch("os.scandir")
    @patch("pathlib.Path.read_text")
    def test_sorting_uses_updated_ts(self, mock_read_text, mock_scandir, mock_tracked_dir, mock_db_dir):
        # Setup mocks
        mock_db_dir.exists.return_value = True
        mock_tracked_dir.exists.return_value = False

        # Create mock file entries
        entry1 = MagicMock()
        entry1.is_file.return_value = True
        entry1.name = "case1.json"
        entry1.path = "/db/case1.json"
        entry1.stat.return_value.st_mtime = 1000.0

        entry2 = MagicMock()
        entry2.is_file.return_value = True
        entry2.name = "case2.json"
        entry2.path = "/db/case2.json"
        entry2.stat.return_value.st_mtime = 2000.0

        mock_scandir.return_value.__enter__.return_value = [entry1, entry2]

        # Mock file content
        # Case 1: Older mtime (1000), but last_modified is newer (Jan 2)
        case1_content = json.dumps({
            "case_id": "case1",
            "last_modified": "2023-01-02T12:00:00"
        })

        # Case 2: Newer mtime (2000), but last_modified is older (Jan 1)
        case2_content = json.dumps({
            "case_id": "case2",
            "last_modified": "2023-01-01T12:00:00"
        })

        mock_read_text.side_effect = [case1_content, case2_content]

        # Run function
        cases = case_documentation_app._refresh_and_get_cases()

        # Check if _updated_ts is present
        self.assertIn("_updated_ts", cases[0])
        self.assertIn("_updated_ts", cases[1])

        # Verify timestamps
        ts1 = datetime.datetime.fromisoformat("2023-01-02T12:00:00").timestamp()
        ts2 = datetime.datetime.fromisoformat("2023-01-01T12:00:00").timestamp()

        self.assertEqual(cases[0]["_updated_ts"], ts1)
        self.assertEqual(cases[1]["_updated_ts"], ts2)

        # Check sorting order
        # Case 1 (Jan 2) should be before Case 2 (Jan 1) because ts1 > ts2
        self.assertEqual(cases[0]["case_id"], "case1")
        self.assertEqual(cases[1]["case_id"], "case2")

        print("\nVerification successful: _updated_ts calculated and sorting correct.")

if __name__ == "__main__":
    unittest.main()
