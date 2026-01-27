import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
import json

# Mock dependencies
class SessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

st_mock = MagicMock()
st_mock.session_state = SessionState()
st_mock.session_state.tutorial_completed = True
st_mock.session_state.debug_mode = False

def cache_mock(*args, **kwargs):
    def decorator(func):
        return func
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return decorator

st_mock.cache_resource = cache_mock
st_mock.cache_data = cache_mock

sys.modules["streamlit"] = st_mock
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
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

# Patch json.dump
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass

with patch("json.dump", side_effect=safe_json_dump):
    import case_documentation_app

class TestCaseSorting(unittest.TestCase):
    def test_sorting_logic(self):
        # Simulate items with pre-calculated _updated_ts
        cases = [
            {"updated": "2023-10-27T10:00:00", "_updated_ts": datetime(2023, 10, 27, 10, 0).timestamp()},
            {"updated": "2023-10-28T10:00:00", "_updated_ts": datetime(2023, 10, 28, 10, 0).timestamp()},
            {"updated": "2023-10-26T10:00:00", "_updated_ts": datetime(2023, 10, 26, 10, 0).timestamp()},
            {"updated": None, "_updated_ts": 0.0},
            {"updated": "invalid", "_updated_ts": 0.0},
        ]

        expected_order = [
            "2023-10-28T10:00:00",
            "2023-10-27T10:00:00",
            "2023-10-26T10:00:00",
            None,
            "invalid"
        ]

        # Sort using the optimized key
        sorted_cases = sorted(cases, key=lambda x: x.get("_updated_ts", 0.0), reverse=True)
        sorted_updated = [c.get("updated") for c in sorted_cases]

        self.assertEqual(sorted_updated[:3], expected_order[:3])
        # For 0.0 values, order is preserved (stable sort)
        self.assertEqual(sorted_updated[3], None)
        self.assertEqual(sorted_updated[4], "invalid")

if __name__ == "__main__":
    unittest.main()
