
import sys
import unittest
from unittest.mock import MagicMock, patch
import json
from pathlib import Path

# Mock dependencies before importing the app
sys.path.append(".")
sys.modules["streamlit"] = MagicMock()
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
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["urllib3.exceptions"] = MagicMock()

# Mock optional deps
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.hazmat"] = MagicMock()
sys.modules["cryptography.hazmat.primitives"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf.pbkdf2"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.ciphers"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.ciphers.algorithms"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.ciphers.modes"] = MagicMock()
sys.modules["cryptography.hazmat.backends"] = MagicMock()

# Mock internal modules
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock st.session_state
class SessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

sys.modules["streamlit"].session_state = SessionState()
sys.modules["streamlit"].secrets = {}

# Now import the app
import case_documentation_app as app

class TestAutosavePerformance(unittest.TestCase):
    def setUp(self):
        # Reset session state
        app.st.session_state.clear()

        # Create a dummy CaseData
        self.case_data = app.CaseData(
            case_id="TEST-123",
            brief_description="Test case"
        )
        # Ensure D is defined if missing (though we pass case explicitly)
        if not hasattr(app, 'D'):
            app.D = self.case_data

    @patch("os.replace")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.mkdir")
    # Patch open to avoid actually opening files
    @patch("builtins.open", new_callable=MagicMock)
    @patch("case_documentation_app.Path.open")
    def test_autosave_avoids_redundant_writes(self, mock_path_open, mock_open, mock_mkdir, mock_write_text, mock_replace):
        # Setup the mock for file opening to return a context manager
        mock_file = MagicMock()
        mock_path_open.return_value.__enter__.return_value = mock_file

        # First save: should write
        app.autosave(self.case_data)

        # Depending on implementation, it might use path.write_text or open().write
        # The code uses: with temp_path.open("w", ...) as f: f.write(...)

        # Verify first write happened
        self.assertEqual(mock_file.write.call_count, 1, "Should write on first save")

        # Force a "new" run by resetting the module level global if simulating Streamlit reload
        # In this test environment, we just call autosave again.
        # But wait, in the REAL app, _last_autosave_hash is reset because the script reruns.
        # In this unit test, the module is NOT reloaded, so _last_autosave_hash persists!

        # To verify the BUG, we must manually reset _last_autosave_hash to None,
        # simulating what happens when Streamlit reruns the script.
        app._last_autosave_hash = None

        # Second save (no changes)
        app.autosave(self.case_data)

        # With the fix (using session_state), it should NOT write again.
        self.assertEqual(mock_file.write.call_count, 1, "Should NOT write again even if global hash is lost (session state should prevent it)")

if __name__ == "__main__":
    unittest.main()
