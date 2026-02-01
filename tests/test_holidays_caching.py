
import sys
import unittest
from unittest.mock import MagicMock, patch
from datetime import date

# Mock heavy dependencies BEFORE importing the app
mock_st = MagicMock()

# Custom dictionary that allows attribute access
class AttributeDict(dict):
    def __getattr__(self, attr):
        return self.get(attr)
    def __setattr__(self, attr, value):
        self[attr] = value

mock_st.session_state = AttributeDict()
# Need to populate some default values if code expects them, or let them return None
# But the code might do st.session_state.something.append() which fails on None.
# If I use MagicMock for missing keys, it might fail JSON serialization again.

# Let's try to make it so that missing keys return MagicMocks but only if needed,
# or just ensure critical paths are mocked.
# The error was: st.session_state.kiroshi_chat_history = load_memory()
# This is an assignment, so AttributeDict handles it.

sys.modules["streamlit"] = mock_st

sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
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

# Now import the app
import case_documentation_app

class TestHolidayCaching(unittest.TestCase):
    def test_caching_and_return_type(self):
        # Access the function
        func = case_documentation_app.compute_us_holidays

        # Check if it is decorated with lru_cache
        self.assertTrue(hasattr(func, "cache_info"), "Function should be decorated with @lru_cache")

        # Clear cache to ensure clean state
        func.cache_clear()

        # First call
        result1 = func(2025)
        self.assertIsInstance(result1, tuple, "Return value must be a tuple for immutability")

        # Check cache info - should have 0 hits, 1 miss, size 1
        info1 = func.cache_info()
        self.assertEqual(info1.misses, 1)
        self.assertEqual(info1.hits, 0)
        self.assertEqual(info1.currsize, 1)

        # Second call with same arg
        result2 = func(2025)
        self.assertIs(result1, result2, "Should return the exact same object from cache")

        # Check cache info - should have 1 hit
        info2 = func.cache_info()
        self.assertEqual(info2.misses, 1)
        self.assertEqual(info2.hits, 1)

        # Third call with different arg
        result3 = func(2026)
        self.assertNotEqual(result1, result3)

        # Check cache info - should have 2 misses (total), 1 hit (total), size 2
        info3 = func.cache_info()
        self.assertEqual(info3.misses, 2)
        self.assertEqual(info3.currsize, 2)

if __name__ == "__main__":
    unittest.main()
