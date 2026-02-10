import sys
import os
import unittest
import importlib
from unittest.mock import MagicMock, patch

# Add parent directory to path so we can import kiroshi_chat
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestClearMemoryUI(unittest.TestCase):
    def setUp(self):
        # 1. Setup mocks
        self.mock_st = MagicMock()

        # Configure st.cache_data to be a transparent decorator
        def mock_cache_data(*args, **kwargs):
            def decorator(func):
                return func
            return decorator

        self.mock_st.cache_data = mock_cache_data
        self.mock_st.cache_resource = mock_cache_data

        # Mock Session State
        class SessionState(dict):
            def __getattr__(self, key):
                if key in self:
                    return self[key]
                raise AttributeError(f"SessionState has no attribute '{key}'")
            def __setattr__(self, key, value):
                self[key] = value

        self.mock_st.session_state = SessionState()
        self.mock_st.session_state.kiroshi_chat_history = ["some history"]

        # Mock columns to return 2 columns by default
        col1 = MagicMock()
        col2 = MagicMock()
        self.mock_st.columns.return_value = (col1, col2)

        # 2. Patch sys.modules to inject mocks and ensure fresh import of kiroshi_chat
        self.modules_patcher = patch.dict(sys.modules, {
            "streamlit": self.mock_st,
            "requests": MagicMock(),
            "urllib3": MagicMock(),
            "kiroshi_local_ai": MagicMock()
        })
        self.modules_patcher.start()

        # Remove kiroshi_chat from sys.modules if it exists (e.g. from other tests)
        if "kiroshi_chat" in sys.modules:
            del sys.modules["kiroshi_chat"]

        import kiroshi_chat
        self.kiroshi_chat = kiroshi_chat

    def tearDown(self):
        self.modules_patcher.stop()
        # Clean up kiroshi_chat to avoid polluting other tests
        if "kiroshi_chat" in sys.modules:
            del sys.modules["kiroshi_chat"]

    def test_clear_memory_button_shows_confirmation(self):
        # Simulate clicking "Clear memory"
        self.mock_st.button.side_effect = lambda label, **kwargs: label == "Clear memory"

        self.kiroshi_chat.render_clear_memory_button()

        # Check that confirmation flag is set
        self.assertTrue(self.mock_st.session_state.get("confirm_clear_memory"))
        # Check that rerun was called
        self.mock_st.rerun.assert_called()

    def test_confirmation_yes_clears_memory(self):
        # Setup state: confirmation is active
        self.mock_st.session_state.confirm_clear_memory = True

        def button_side_effect(label, **kwargs):
            if label == "Yes, delete it":
                return True
            return False

        self.mock_st.button.side_effect = button_side_effect

        # Mock save_memory to verify it's called
        with patch.object(self.kiroshi_chat, 'save_memory') as mock_save:
            self.kiroshi_chat.render_clear_memory_button()

            # Verify memory cleared
            self.assertEqual(self.mock_st.session_state.kiroshi_chat_history, [])
            mock_save.assert_called_with([])

            # Verify confirmation flag reset
            self.assertFalse(self.mock_st.session_state.confirm_clear_memory)

            # Verify rerun called
            self.mock_st.rerun.assert_called()

    def test_confirmation_cancel_resets_state(self):
        # Setup state: confirmation is active
        self.mock_st.session_state.confirm_clear_memory = True

        def button_side_effect(label, **kwargs):
            if label == "Cancel":
                return True
            return False

        self.mock_st.button.side_effect = button_side_effect

        # Mock save_memory to ensure it is NOT called
        with patch.object(self.kiroshi_chat, 'save_memory') as mock_save:
            self.kiroshi_chat.render_clear_memory_button()

            # Verify memory NOT cleared
            self.assertEqual(self.mock_st.session_state.kiroshi_chat_history, ["some history"])
            mock_save.assert_not_called()

            # Verify confirmation flag reset
            self.assertFalse(self.mock_st.session_state.confirm_clear_memory)

            # Verify rerun called
            self.mock_st.rerun.assert_called()

if __name__ == "__main__":
    unittest.main()
