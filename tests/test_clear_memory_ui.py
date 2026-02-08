import sys
import unittest
import importlib
from unittest.mock import MagicMock

# Custom session state class to mimic Streamlit's behavior
class SessionState(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self

class TestClearMemory(unittest.TestCase):
    def setUp(self):
        # Ensure clean state for mocks
        self.mock_st = MagicMock()
        self.mock_st.chat_input.return_value = None

        # Reset session state for each test
        self.session = SessionState({
            "kiroshi_chat_history": [{"role": "user", "content": "hello"}],
            "kiroshi_sarcasm_mode": False,
            "confirm_clear_memory": False
        })
        self.mock_st.session_state = self.session

        # Mock st.columns
        self.col1 = MagicMock()
        self.col2 = MagicMock()
        self.mock_st.columns.return_value = [self.col1, self.col2]

        # Patch sys.modules
        self.patcher = unittest.mock.patch.dict(sys.modules, {'streamlit': self.mock_st, 'kiroshi_local_ai': MagicMock()})
        self.patcher.start()

        # We need to ensure kiroshi_chat is imported (or reloaded) using OUR mocks
        # If kiroshi_chat is already in sys.modules (e.g. from another test), reload it.
        # If it's a MagicMock (from test_secure_blur.py), we MUST remove it first or reload won't work as expected if it was a mock object.
        if 'kiroshi_chat' in sys.modules:
             # If it is a MagicMock, reload might fail or be weird. Best to delete and re-import.
             if isinstance(sys.modules['kiroshi_chat'], MagicMock):
                 del sys.modules['kiroshi_chat']

        try:
            import kiroshi_chat
            importlib.reload(kiroshi_chat)
            self.kiroshi_chat = kiroshi_chat
        except ImportError:
            # If import fails (e.g. dependencies), we can't test
            self.kiroshi_chat = None

        # Mock save_memory/load_memory on the IMPORTED module
        if self.kiroshi_chat:
            self.kiroshi_chat.save_memory = MagicMock()
            self.kiroshi_chat.load_memory = MagicMock(return_value=[{"role": "user", "content": "hello"}])

    def tearDown(self):
        self.patcher.stop()

    def test_clear_memory_confirmation_flow(self):
        """Verify the confirmation flow for clearing memory."""
        if not self.kiroshi_chat:
            self.fail("Could not import kiroshi_chat")

        # --- Step 1: Click "Clear memory" ---
        print("\n--- Testing Step 1: Click 'Clear memory' ---")

        # Reset session state for step 1
        self.session["kiroshi_chat_history"] = [{"role": "user", "content": "keep me"}]
        self.session["confirm_clear_memory"] = False

        # Mock button clicks
        def button_step_1(label, **kwargs):
            return label == "Clear memory"

        self.mock_st.button.side_effect = button_step_1
        # The confirmation buttons (Yes/Cancel) are inside columns.
        self.col1.button.return_value = False
        self.col2.button.return_value = False

        try: self.kiroshi_chat.main()
        except Exception as e: print(f"Ignored exception: {e}")

        # Verify: Flag set, memory kept
        self.assertTrue(self.session.get("confirm_clear_memory"), "Confirmation flag should be True")
        self.assertEqual(len(self.session["kiroshi_chat_history"]), 1, "History should not be cleared yet")
        print("PASS: Confirmation flag set.")

        # --- Step 2: Click "Cancel" ---
        print("\n--- Testing Step 2: Click 'Cancel' ---")

        # Reset flag to True (as if we just clicked Clear)
        self.session["confirm_clear_memory"] = True

        # "Clear memory" button is hidden or doesn't matter
        self.mock_st.button.return_value = False

        # col2 is "Cancel" button
        self.col1.button.return_value = False
        self.col2.button.return_value = True

        try: self.kiroshi_chat.main()
        except Exception as e: print(f"Ignored exception: {e}")

        # Verify: Flag cleared, memory kept
        self.assertFalse(self.session.get("confirm_clear_memory"), "Confirmation flag should be False after Cancel")
        self.assertEqual(len(self.session["kiroshi_chat_history"]), 1, "History should not be cleared after Cancel")
        print("PASS: Cancelled correctly.")

        # --- Step 3: Click "Yes, clear it" ---
        print("\n--- Testing Step 3: Click 'Yes, clear it' ---")

        # Reset flag to True
        self.session["confirm_clear_memory"] = True

        # col1 is "Yes" button
        self.col1.button.return_value = True
        self.col2.button.return_value = False

        try: self.kiroshi_chat.main()
        except Exception as e: print(f"Ignored exception: {e}")

        # Verify: Flag cleared, memory CLEARED
        self.assertFalse(self.session.get("confirm_clear_memory"), "Confirmation flag should be False after Confirm")
        self.assertEqual(len(self.session["kiroshi_chat_history"]), 0, "History should be cleared after Confirm")
        print("PASS: Confirmed and cleared.")

if __name__ == "__main__":
    unittest.main()
