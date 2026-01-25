import sys
import unittest
from unittest.mock import MagicMock
from copy import deepcopy

# Mock dependencies before importing kiroshi_hotkeys
sys.modules["case_documentation_app"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()

# Ensure we get the real module, not a mock from previous tests (e.g., test_secure_blur.py)
if "kiroshi_hotkeys" in sys.modules:
    del sys.modules["kiroshi_hotkeys"]

import kiroshi_hotkeys

class SimpleCase:
    def __init__(self):
        self.title = "Test Case"
        self.description = "Test Description"

class SimpleSession:
    def __init__(self):
        self.case = SimpleCase()
        self.screenshots = []
        self.uploads = []
        self.log_uploads = []
        self.scratch = "scratchpad"

class TestKiroshiHotkeys(unittest.TestCase):
    def setUp(self):
        # Reset snapshot state
        kiroshi_hotkeys._snapshot_state.clear()

    def test_update_hotkey_snapshot_optimization(self):
        # Setup
        session = SimpleSession()
        session.screenshots = ["heavy_image_data_1", "heavy_image_data_2"]
        session.uploads = ["heavy_file_1"]
        session.case.title = "Original Title"

        sessions = [session]

        # Action
        kiroshi_hotkeys.update_hotkey_snapshot(sessions, 0, {})

        # Verification
        snapshot = kiroshi_hotkeys._snapshot_state.session
        self.assertIsNotNone(snapshot)

        # 1. Verify it is a different object
        self.assertIsNot(snapshot, session)

        # 2. Verify Case Data is preserved and copied
        self.assertEqual(snapshot.case.title, "Original Title")
        self.assertIsNot(snapshot.case, session.case)

        # 3. Verify Heavy Assets are CLEARED in the snapshot
        self.assertEqual(snapshot.screenshots, [])
        self.assertEqual(snapshot.uploads, [])

        # 4. Verify Original is untouched (CRITICAL)
        self.assertEqual(session.screenshots, ["heavy_image_data_1", "heavy_image_data_2"])
        self.assertEqual(session.uploads, ["heavy_file_1"])

if __name__ == "__main__":
    unittest.main()
