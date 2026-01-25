import unittest
from unittest.mock import MagicMock
from dataclasses import dataclass, field
import sys
import threading

# Mock modules to avoid importing the entire app which might need display
sys.modules['case_documentation_app'] = MagicMock()

# Import the module under test
from kiroshi_hotkeys import update_hotkey_snapshot, _snapshot_state, HotkeySnapshot

@dataclass
class MockCaseData:
    description: str = "Test Description"
    solution: str = "Test Solution"

@dataclass
class MockCaseSession:
    case: MockCaseData
    uploads: list = field(default_factory=list)
    heavy_data: str = "Heavy" * 1000

class TestKiroshiHotkeys(unittest.TestCase):
    def setUp(self):
        # Reset snapshot state
        with threading.Lock():
            _snapshot_state.clear()

    def test_update_hotkey_snapshot_optimization(self):
        # Create a mock session with heavy data
        case_data = MockCaseData()
        session = MockCaseSession(case=case_data)
        # Add some "heavy" data to uploads (simulating files)
        session.uploads = ["Heavy File"] * 100

        sessions = [session]
        active_idx = 0
        category_map = {"TestCat": ["Field1"]}

        # Call update
        update_hotkey_snapshot(sessions, active_idx, category_map)

        # Verify snapshot
        self.assertIsNotNone(_snapshot_state.session)

        # Check that 'case' attribute exists and is correct
        self.assertTrue(hasattr(_snapshot_state.session, 'case'))
        self.assertEqual(_snapshot_state.session.case.description, "Test Description")

        # Check that it is a COPY, not the original
        self.assertIsNot(_snapshot_state.session.case, case_data)

        # Check that heavy data was NOT copied (optimization check)
        # In the original implementation, the whole session is copied, so 'uploads' would exist.
        # In the optimized implementation, only 'case' is copied.
        # So checking for absence of 'uploads' verifies the optimization.
        # Note: This assertion will FAIL before the fix, and PASS after the fix.
        self.assertFalse(hasattr(_snapshot_state.session, 'uploads'))

    def test_update_hotkey_snapshot_invalid_input(self):
        update_hotkey_snapshot(None, 0, {})
        self.assertIsNone(_snapshot_state.session)

        update_hotkey_snapshot([], 0, {})
        self.assertIsNone(_snapshot_state.session)

        update_hotkey_snapshot([MagicMock()], -1, {})
        self.assertIsNone(_snapshot_state.session)

if __name__ == '__main__':
    unittest.main()
