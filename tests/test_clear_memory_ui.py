
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock external dependencies before importing kiroshi_chat
sys.modules['streamlit'] = MagicMock()
sys.modules['kiroshi_local_ai'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['urllib3'] = MagicMock()

# Now we can import kiroshi_chat
import kiroshi_chat

class MockSessionState(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return None # Default for .get() behavior if accessed directly

    def __setattr__(self, key, value):
        self[key] = value

    def get(self, key, default=None):
        return super().get(key, default)

class TestClearMemoryUI(unittest.TestCase):
    def setUp(self):
        # Reset session state mock
        kiroshi_chat.st.session_state = MockSessionState({
            "kiroshi_chat_history": [{"role": "user", "content": "hi"}],
            "kiroshi_sarcasm_mode": False,
            "personality_mode": "utility",
            "system_prompt": "prompt",
            "confirm_clear_memory": False
        })
        # Reset mocks
        kiroshi_chat.save_memory = MagicMock()
        kiroshi_chat.st.rerun = MagicMock()
        kiroshi_chat.st.columns = MagicMock(return_value=[MagicMock(), MagicMock()])
        kiroshi_chat.st.warning = MagicMock()

    def test_clear_memory_confirmation_flow(self):
        """
        Test the full confirmation flow:
        1. Click 'Clear memory' -> Prompts confirmation
        2. Click 'Yes, delete it' -> Clears memory
        """

        # --- Step 1: Initial state, clicking "Clear memory" ---

        # Define button behavior: return True if label is "Clear memory"
        def button_side_effect(label, **kwargs):
            if label == "Clear memory":
                return True
            return False

        kiroshi_chat.st.button = MagicMock(side_effect=button_side_effect)

        with patch('kiroshi_chat.configure_page'), \
             patch('kiroshi_chat.load_memory', return_value=[]), \
             patch('kiroshi_chat.st.chat_input', return_value=None):
            kiroshi_chat.main()

        # Verify NO save/clear happened yet
        kiroshi_chat.save_memory.assert_not_called()
        # Verify confirmation state is set
        self.assertTrue(kiroshi_chat.st.session_state.confirm_clear_memory)
        # Verify rerun to show confirmation
        kiroshi_chat.st.rerun.assert_called()

        # --- Step 2: Confirmation state is active, clicking "Yes" ---

        # Reset mocks for next step
        kiroshi_chat.save_memory.reset_mock()
        kiroshi_chat.st.rerun.reset_mock()

        # Setup session state as if step 1 completed
        kiroshi_chat.st.session_state.confirm_clear_memory = True

        # Define button behavior for the columns
        # The code uses col1.button("Yes...")
        col1_mock = kiroshi_chat.st.columns.return_value[0]
        col1_mock.button.return_value = True

        # Main "Clear memory" button should NOT be clicked in this pass (or irrelevant)
        kiroshi_chat.st.button.side_effect = lambda label, **kwargs: False

        with patch('kiroshi_chat.configure_page'), \
             patch('kiroshi_chat.load_memory', return_value=[]), \
             patch('kiroshi_chat.st.chat_input', return_value=None):
            kiroshi_chat.main()

        # Verify warning is shown
        kiroshi_chat.st.warning.assert_called()

        # Verify save_memory was called with empty list
        kiroshi_chat.save_memory.assert_called_with([])

        # Verify confirmation state is reset
        self.assertFalse(kiroshi_chat.st.session_state.confirm_clear_memory)

        # Verify rerun called
        kiroshi_chat.st.rerun.assert_called()

if __name__ == '__main__':
    unittest.main()
