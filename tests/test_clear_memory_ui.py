import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock dependencies before importing kiroshi_chat
sys.modules['kiroshi_local_ai'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['urllib3'] = MagicMock()

# Mock streamlit
mock_st = MagicMock()
sys.modules['streamlit'] = mock_st

# Setup session state mock
class SessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

mock_st.session_state = SessionState()

# Now import the module under test
import kiroshi_chat

class TestClearMemoryUI(unittest.TestCase):
    def setUp(self):
        # Reset mocks
        mock_st.reset_mock()
        mock_st.session_state = SessionState()
        mock_st.session_state.kiroshi_chat_history = [{"role": "user", "content": "hello"}]
        mock_st.session_state.kiroshi_sarcasm_mode = False

        # Mock st.columns to return mocks
        mock_st.columns.return_value = [MagicMock(), MagicMock()]

    def test_clear_memory_immediate_behavior(self):
        """
        This test verifies the *current* behavior where clicking "Clear memory"
        clears the history immediately.
        Once we implement the confirmation, this test should be updated or removed,
        but for TDD, we want to confirm the current state first, then the desired state.

        However, the plan says "Assert that a confirmation flag is set and history is *not* cleared".
        So I will write the test for the DESIRED behavior, and expect it to fail now.
        """

        # 1. Initial state: history exists, no confirmation flag
        self.assertTrue(mock_st.session_state.kiroshi_chat_history)
        self.assertFalse(mock_st.session_state.get("confirm_clear_memory"))

        # 2. User clicks "Clear memory"
        # We simulate st.button returning True for "Clear memory"
        def button_side_effect(label, **kwargs):
            if label == "Clear memory":
                return True
            return False

        mock_st.button.side_effect = button_side_effect

        # Run main to trigger the button click logic
        try:
            kiroshi_chat.main()
        except Exception:
            pass # ignore rerun exception

        # 3. Assert confirmation state is set, but history is NOT cleared yet
        # THIS SHOULD FAIL ON CURRENT CODEBASE because it clears immediately
        if not mock_st.session_state.get("confirm_clear_memory"):
             print("\n[Test Log] Confirmation flag not set (Expected Failure for TDD)")

        if not mock_st.session_state.kiroshi_chat_history:
             print("[Test Log] History was cleared immediately (Expected Failure for TDD)")

        self.assertTrue(mock_st.session_state.get("confirm_clear_memory"), "Confirmation flag should be set")
        self.assertTrue(mock_st.session_state.kiroshi_chat_history, "History should not be cleared yet")

    def test_confirmation_flow(self):
        """
        This test simulates the full confirmation flow:
        1. Click Clear -> Set flag
        2. Click Yes -> Clear history
        """
        # Set the flag manually to simulate "Clear memory" was clicked previously
        mock_st.session_state.confirm_clear_memory = True

        # Simulate clicking "Yes, delete it"
        col_mock1 = mock_st.columns.return_value[0]
        col_mock2 = mock_st.columns.return_value[1]

        def button_side_effect(label, **kwargs):
            if label == "Yes, delete it":
                return True
            return False

        col_mock1.button.side_effect = button_side_effect

        # Run main
        try:
            kiroshi_chat.main()
        except Exception:
            pass

        # Assert history is cleared and flag reset
        self.assertFalse(mock_st.session_state.kiroshi_chat_history, "History should be cleared after confirmation")
        self.assertFalse(mock_st.session_state.get("confirm_clear_memory"), "Confirmation flag should be reset")

if __name__ == '__main__':
    unittest.main()
