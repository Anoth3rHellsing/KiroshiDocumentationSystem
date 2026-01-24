
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Mock modules that might cause import errors or side effects
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.ImageGrab"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Setup Streamlit mock properly
import streamlit as st

class SessionState(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'SessionState' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        self[key] = value

st.session_state = SessionState()
st.text_input = MagicMock(return_value="admin")
st.button = MagicMock(return_value=False)
st.warning = MagicMock()
st.error = MagicMock()
st.rerun = MagicMock()

# Import the module under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import case_documentation_app
except ImportError as e:
    print(f"Failed to import case_documentation_app: {e}")
    sys.exit(1)
except Exception as e:
    # If other errors occur during top-level execution (which we expect might happen),
    # we might still be able to test if the function we care about is defined.
    # However, ideally we mock enough to pass import.
    print(f"Warning: Error during import: {e}")

class TestDebugAuth(unittest.TestCase):
    def setUp(self):
        # Reset session state
        st.session_state.clear()
        st.session_state['debug_auth'] = False
        st.warning.reset_mock()
        st.error.reset_mock()
        st.rerun.reset_mock()

        # Reset input mocks
        st.text_input.reset_mock()
        st.button.reset_mock()

    def test_default_credentials_warning(self):
        """Test that default admin/admin logs in but shows a warning."""
        # Setup inputs: User='admin', Pass='admin'
        st.text_input.side_effect = ["admin", "admin"]
        # Login button clicked
        st.button.return_value = True

        with patch.dict(os.environ, {}, clear=True):
            case_documentation_app.render_debug_panel()

            # Should be authenticated
            self.assertTrue(st.session_state['debug_auth'])
            # Should show warning because defaults are used
            # Wait, warning is shown AFTER auth is true, inside the IF block.
            # But in the login flow (ELSE block), we added st.rerun().
            # So warning won't be shown in THIS call for the login action,
            # but we verify auth is set and rerun is called.
            st.rerun.assert_called_once()

            # Now simulate the NEXT run where auth is True
            st.button.return_value = False # No button click this time
            st.warning.reset_mock()

            case_documentation_app.render_debug_panel()
            st.warning.assert_called()
            args, _ = st.warning.call_args
            self.assertIn("Default debug credentials are in use", args[0])

    def test_custom_credentials_success(self):
        """Test that custom credentials work and do NOT show warning."""
        st.text_input.side_effect = ["super", "secret"]
        st.button.return_value = True

        env = {
            "KIROSHI_DEBUG_USER": "super",
            "KIROSHI_DEBUG_PASSWORD": "secret"
        }

        with patch.dict(os.environ, env, clear=True):
            case_documentation_app.render_debug_panel()

            self.assertTrue(st.session_state['debug_auth'])
            st.rerun.assert_called_once()

            # Simulate next run
            st.button.return_value = False
            st.warning.reset_mock()

            case_documentation_app.render_debug_panel()
            st.warning.assert_not_called()

    def test_invalid_credentials(self):
        """Test that wrong password fails."""
        st.text_input.side_effect = ["admin", "wrong"]
        st.button.return_value = True

        with patch.dict(os.environ, {}, clear=True):
            case_documentation_app.render_debug_panel()

            self.assertFalse(st.session_state['debug_auth'])
            st.error.assert_called_with("Invalid credentials")

if __name__ == "__main__":
    unittest.main()
