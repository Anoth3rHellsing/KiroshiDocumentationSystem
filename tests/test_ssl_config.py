import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure we can import modules from the current directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock dependencies to avoid import errors
mock_st = MagicMock()
# Make session_state behave like a dict for get/set/items
mock_st.session_state = MagicMock()
mock_st.session_state.get = MagicMock(side_effect=lambda k, d=None: d if d is not None else "mock_value")
mock_st.session_state.__getitem__ = MagicMock(return_value="mock_value")
mock_st.session_state.__setitem__ = MagicMock()
sys.modules["streamlit"] = mock_st

# Patch dataclasses.asdict to avoid TypeError when D is a Mock
import dataclasses
original_asdict = dataclasses.asdict
def mock_asdict(obj):
    if isinstance(obj, (MagicMock, str)):
        return {}
    return original_asdict(obj)
dataclasses.asdict = mock_asdict
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock requests and urllib3 as they might not be installed in the test environment
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# We need to test kiroshi_chat independently first
sys.modules["case_documentation_app"] = MagicMock()

class TestSSLVerification(unittest.TestCase):
    def setUp(self):
        # Reset environment
        if "KIROSHI_INSECURE_SKIP_VERIFY" in os.environ:
            del os.environ["KIROSHI_INSECURE_SKIP_VERIFY"]

    def _reload_module(self, module_name):
        if module_name in sys.modules:
            del sys.modules[module_name]
        return __import__(module_name)

    def test_case_app_default_secure(self):
        """Test case_documentation_app defaults to VERIFY_SSL=True."""
        mod = self._reload_module("case_documentation_app")
        self.assertTrue(getattr(mod, "VERIFY_SSL", False), "VERIFY_SSL should be True by default in case_documentation_app")

    def test_case_app_opt_out(self):
        """Test case_documentation_app respects KIROSHI_INSECURE_SKIP_VERIFY=true."""
        os.environ["KIROSHI_INSECURE_SKIP_VERIFY"] = "true"
        mod = self._reload_module("case_documentation_app")
        self.assertFalse(getattr(mod, "VERIFY_SSL", True), "VERIFY_SSL should be False when env var is true in case_documentation_app")

    def test_kiroshi_chat_default_secure(self):
        """Test kiroshi_chat defaults to VERIFY_SSL=True."""
        mod = self._reload_module("kiroshi_chat")
        self.assertTrue(getattr(mod, "VERIFY_SSL", False), "VERIFY_SSL should be True by default in kiroshi_chat")

    def test_kiroshi_chat_opt_out(self):
        """Test kiroshi_chat respects KIROSHI_INSECURE_SKIP_VERIFY=true."""
        os.environ["KIROSHI_INSECURE_SKIP_VERIFY"] = "true"
        mod = self._reload_module("kiroshi_chat")
        self.assertFalse(getattr(mod, "VERIFY_SSL", True), "VERIFY_SSL should be False when env var is true in kiroshi_chat")

if __name__ == "__main__":
    unittest.main()
