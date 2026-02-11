import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock dependencies before import
sys.modules['streamlit'] = MagicMock()
sys.modules['kiroshi_local_ai'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['urllib3'] = MagicMock()

# Mock st.session_state behavior
class SessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

sys.modules['streamlit'].session_state = SessionState()

# Import the module under test
import kiroshi_chat

class TestClearMemoryUI(unittest.TestCase):
    def setUp(self):
        # Reset session state
        kiroshi_chat.st.session_state = SessionState()
        kiroshi_chat.st.session_state.kiroshi_chat_history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"}
        ]

        # Reset mocks
        kiroshi_chat.st.button.reset_mock()
        kiroshi_chat.st.chat_input.reset_mock()
        kiroshi_chat.st.columns.reset_mock()
        kiroshi_chat.st.warning.reset_mock()

    @patch('kiroshi_chat.save_memory')
    @patch('kiroshi_chat.st.rerun')
    def test_initiation_of_clear_memory(self, mock_rerun, mock_save_memory):
        """Verify that clicking 'Clear memory' only sets the confirmation flag."""
        # Setup mocks
        kiroshi_chat.st.chat_input.return_value = None
        # st.button returns True for "Clear memory"
        kiroshi_chat.st.button.side_effect = lambda label, **kwargs: label == "Clear memory"

        # Run main
        kiroshi_chat.main()

        # Verify save_memory was NOT called
        mock_save_memory.assert_not_called()
        # Verify flag is set
        self.assertTrue(kiroshi_chat.st.session_state.confirm_clear_memory)
        # Verify rerun called
        mock_rerun.assert_called_once()

    @patch('kiroshi_chat.save_memory')
    @patch('kiroshi_chat.st.rerun')
    def test_confirmation_yes(self, mock_rerun, mock_save_memory):
        """Verify that confirming deletion clears memory."""
        # Setup state: flag is TRUE
        kiroshi_chat.st.session_state.confirm_clear_memory = True
        kiroshi_chat.st.chat_input.return_value = None

        # Mock columns and buttons inside columns
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        kiroshi_chat.st.columns.return_value = [mock_col1, mock_col2]

        # Click "Yes, delete it" on col1
        mock_col1.button.return_value = True
        mock_col2.button.return_value = False

        # Run main
        kiroshi_chat.main()

        # Verify warning shown
        kiroshi_chat.st.warning.assert_called()

        # Verify save_memory called with empty list
        mock_save_memory.assert_called_with([])
        # Verify history cleared
        self.assertEqual(kiroshi_chat.st.session_state.kiroshi_chat_history, [])
        # Verify flag reset
        self.assertFalse(kiroshi_chat.st.session_state.confirm_clear_memory)
        # Verify rerun called
        mock_rerun.assert_called_once()

    @patch('kiroshi_chat.save_memory')
    @patch('kiroshi_chat.st.rerun')
    def test_confirmation_cancel(self, mock_rerun, mock_save_memory):
        """Verify that cancelling does not clear memory."""
        # Setup state: flag is TRUE
        kiroshi_chat.st.session_state.confirm_clear_memory = True
        original_history = list(kiroshi_chat.st.session_state.kiroshi_chat_history)
        kiroshi_chat.st.chat_input.return_value = None

        # Mock columns and buttons inside columns
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        kiroshi_chat.st.columns.return_value = [mock_col1, mock_col2]

        # Click "Cancel" on col2
        mock_col1.button.return_value = False
        mock_col2.button.return_value = True

        # Run main
        kiroshi_chat.main()

        # Verify save_memory NOT called
        mock_save_memory.assert_not_called()
        # Verify history preserved
        self.assertEqual(kiroshi_chat.st.session_state.kiroshi_chat_history, original_history)
        # Verify flag reset
        self.assertFalse(kiroshi_chat.st.session_state.confirm_clear_memory)
        # Verify rerun called
        mock_rerun.assert_called_once()

if __name__ == '__main__':
    unittest.main()
