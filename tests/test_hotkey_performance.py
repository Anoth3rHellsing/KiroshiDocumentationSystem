
import sys
from unittest.mock import MagicMock

# Mock dependencies before import
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()

import time
import io
import unittest
from copy import deepcopy
from dataclasses import dataclass, field
from types import SimpleNamespace
import kiroshi_hotkeys

# Mock dependencies
class InMemoryUploadedFile:
    def __init__(self, data):
        self.data = io.BytesIO(data)
        self.name = "test.txt"
        self.type = "text/plain"
        self.size = len(data)

    def __deepcopy__(self, memo):
        # Simulate deepcopy of a file object (which often involves copying the buffer)
        new_obj = InMemoryUploadedFile(self.data.getvalue())
        return new_obj

@dataclass
class CaseData:
    case_id: str = "12345"
    description: str = "Test case"
    remote_sessions: list = field(default_factory=list)

@dataclass
class CaseSession:
    case: CaseData
    uploads: list = field(default_factory=list)
    log_uploads: list = field(default_factory=list)
    screenshots: list = field(default_factory=list)

class TestHotkeyPerformance(unittest.TestCase):
    def test_update_hotkey_snapshot_performance(self):
        # Setup heavy session
        heavy_data = b"0" * 1024 * 1024 * 5 # 5MB
        case_data = CaseData()
        session = CaseSession(case=case_data)
        for _ in range(5):
            session.uploads.append(InMemoryUploadedFile(heavy_data))

        sessions = [session]

        # Test original function wrapper
        def wrapper(sessions, idx, cmap):
            kiroshi_hotkeys.update_hotkey_snapshot(sessions, idx, cmap)

        start = time.perf_counter()
        wrapper(sessions, 0, {})
        end = time.perf_counter()

        duration = end - start
        print(f"Update duration: {duration:.6f}s")

        # Assert that session was copied correctly (case data preserved)
        snapshot = kiroshi_hotkeys._snapshot_state
        self.assertIsNotNone(snapshot.session)

        # Check that it's a SimpleNamespace
        self.assertIsInstance(snapshot.session, SimpleNamespace)

        # Check that it contains the case data
        self.assertEqual(snapshot.session.case.case_id, "12345")

        # Check that it does NOT contain the heavy uploads
        self.assertFalse(hasattr(snapshot.session, "uploads"))

if __name__ == "__main__":
    unittest.main()
