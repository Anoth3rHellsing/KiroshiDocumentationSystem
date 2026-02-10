import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add current directory to path
sys.path.append(os.getcwd())

class SessionState(dict):
    """Mock session state that supports both dict and attribute access."""
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'SessionState' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        self[key] = value

session_state = SessionState()

mock_st = MagicMock()
mock_st.session_state = session_state

sys.modules["streamlit"] = mock_st
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

import kiroshi_chat

class TestClearMemoryUI(unittest.TestCase):
    def setUp(self):
        session_state.clear()
        session_state.update({
            "kiroshi_chat_history": [{"role": "user", "content": "test"}],
            "confirm_clear_memory": False
        })
        mock_st.reset_mock()
        mock_st.chat_input.return_value = None
        mock_st.session_state = session_state

        mock_st.button.side_effect = None
        mock_st.button.return_value = False

        # Mock st.columns to return mock columns
        self.mock_col1 = MagicMock()
        self.mock_col2 = MagicMock()
        mock_st.columns.return_value = [self.mock_col1, self.mock_col2]

    @patch("kiroshi_chat.save_memory")
    @patch("kiroshi_chat.st.rerun")
    def test_confirmation_flow(self, mock_rerun, mock_save):
        """Verify confirmation flow: ask for confirmation before deleting."""

        # Scenario 1: User clicks "Clear memory"
        # Setup: "Clear memory" returns True
        def button_side_effect(label, **kwargs):
            if label == "Clear memory":
                return True
            return False

        mock_st.button.side_effect = button_side_effect

        kiroshi_chat.main()

        # Expect: confirm_clear_memory set to True, rerun called, save_memory NOT called
        self.assertTrue(session_state.get("confirm_clear_memory"), "Should set confirmation flag")
        mock_rerun.assert_called()
        mock_save.assert_not_called()

        # Scenario 2: Confirmation state is active, user clicks "Yes"
        # Reset mocks
        mock_rerun.reset_mock()
        mock_save.reset_mock()
        mock_st.button.reset_mock()

        # Setup: confirm_clear_memory is True
        session_state["confirm_clear_memory"] = True

        # Setup: "Yes, delete it" button returns True
        def col1_button_side_effect(label, **kwargs):
            if "Yes" in label:
                return True
            return False

        self.mock_col1.button.side_effect = col1_button_side_effect
        self.mock_col2.button.return_value = False

        # Note: In the confirmation state, "Clear memory" button should NOT be rendered (or at least not clicked)
        # We need to simulate the rendering logic.
        # If we just run main(), it will check session_state["confirm_clear_memory"].

        kiroshi_chat.main()

        # Expect: memory cleared, flag reset, rerun called
        mock_save.assert_called_with([])
        self.assertEqual(session_state["kiroshi_chat_history"], [])
        self.assertFalse(session_state["confirm_clear_memory"], "Should reset confirmation flag")
        mock_rerun.assert_called()

if __name__ == "__main__":
    unittest.main()
