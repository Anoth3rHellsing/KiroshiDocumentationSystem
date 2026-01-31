
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock dependencies before import
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.pdfgen"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.lib.units"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.pdfbase"] = MagicMock()
sys.modules["reportlab.pdfbase.ttfonts"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.fernet"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()

# Setup Streamlit mock
import streamlit as st

class SessionStateMock(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'SessionStateMock' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        self[key] = value

st.session_state = SessionStateMock()

# Mock Path to spy on mkdir and exists
from pathlib import Path

# We need to mock Path globally because the module uses it at top level
with patch("pathlib.Path") as MockPath:
    # Setup mock behavior
    mock_path_instance = MockPath.return_value

    # Configure chained calls to return the same mock instance
    mock_path_instance.resolve.return_value = mock_path_instance
    mock_path_instance.parent = mock_path_instance
    mock_path_instance.__truediv__.return_value = mock_path_instance

    mock_path_instance.exists.return_value = True
    mock_path_instance.read_bytes.return_value = b"fake_bytes"
    mock_path_instance.read_text.return_value = "{}" # For JSON reads

    # Import the module
    import case_documentation_app

class TestCheckInstallationStatus(unittest.TestCase):
    def setUp(self):
        # Reset mocks
        case_documentation_app.DATABASE_DIR.mkdir.reset_mock()
        case_documentation_app.UTILITIES_DIR.mkdir.reset_mock()
        case_documentation_app.UPDATES_DIR.mkdir.reset_mock()
        case_documentation_app.TRACKED_CASES_DIR.mkdir.reset_mock()
        case_documentation_app.RECENT_CASES_PATH.exists.reset_mock()

        # Reset session state
        st.session_state.clear()

    def test_redundant_fs_calls(self):
        # First call
        case_documentation_app._check_installation_status()

        # Check that mkdir was called (indicating FS access)
        # We expect _initialize_storage_paths to be called
        # which calls mkdir on several directories
        self.assertTrue(case_documentation_app.DATABASE_DIR.mkdir.called)

        # Reset mocks
        case_documentation_app.DATABASE_DIR.mkdir.reset_mock()

        # Second call - should NO LONGER trigger FS calls
        case_documentation_app._check_installation_status()
        self.assertFalse(case_documentation_app.DATABASE_DIR.mkdir.called,
                        "mkdir should NOT be called again due to optimization")

if __name__ == "__main__":
    unittest.main()
