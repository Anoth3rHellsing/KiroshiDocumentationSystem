
import sys
import os
import unittest
from unittest.mock import MagicMock
from datetime import date

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def mock_modules():
    modules_to_mock = [
        "streamlit",
        "streamlit.components.v1",
        "streamlit.errors",
        "pyautogui",
        "PIL",
        "PIL.Image",
        "PIL.ImageGrab",
        "PIL.ImageFilter",
        "mss",
        "pytesseract",
        "reportlab",
        "reportlab.lib",
        "reportlab.lib.pagesizes",
        "reportlab.lib.colors",
        "reportlab.lib.styles",
        "reportlab.platypus",
        "reportlab.graphics.shapes",
        "reportlab.graphics.charts.barcharts",
        "reportlab.graphics.charts.lineplots",
        "reportlab.graphics.widgets.markers",
        "reportlab.rl_config",
        "reportlab.pdfbase",
        "reportlab.pdfbase.pdfdoc",
        "tkinter",
        "pyperclip",
        "pynput",
        "requests",
        "urllib3",
        "pandas",
        "altair",
        "cryptography",
        "kiroshi_chat",
        "kiroshi_local_ai",
        "kiroshi_cloud_sync",
        "kiroshi_video",
        "kiroshi_hotkeys",
    ]
    for mod in modules_to_mock:
        sys.modules[mod] = MagicMock()

    # Special handling for streamlit
    class SessionState(dict):
        def __getattr__(self, item):
            if item in self:
                return self[item]
            raise AttributeError(f"'SessionState' object has no attribute '{item}'")
        def __setattr__(self, key, value):
            self[key] = value

    st_mock = MagicMock()
    st_mock.session_state = SessionState()

    # Mock decorators to return the function itself or handle arguments
    def mock_cache_decorator(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return lambda func: func

    st_mock.cache_data = mock_cache_decorator
    st_mock.cache_resource = mock_cache_decorator
    sys.modules["streamlit"] = st_mock

class TestHolidaysOptimization(unittest.TestCase):
    def test_caching(self):
        mock_modules()
        import case_documentation_app

        # Clear cache to start fresh
        case_documentation_app.compute_us_holidays.cache_clear()

        # First call - should calculate
        case_documentation_app.compute_us_holidays(2025)
        info1 = case_documentation_app.compute_us_holidays.cache_info()
        print(f"After 1st call: {info1}")

        # Second call - should hit cache
        case_documentation_app.compute_us_holidays(2025)
        info2 = case_documentation_app.compute_us_holidays.cache_info()
        print(f"After 2nd call: {info2}")

        self.assertTrue(info2.hits > info1.hits, "Cache hits should increase")
        self.assertEqual(info2.currsize, 1, "Cache size should be 1 for one year")

if __name__ == "__main__":
    unittest.main()
