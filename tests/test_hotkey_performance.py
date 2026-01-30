
import sys
import time
import unittest
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from typing import Any, List

# Mock dependencies to avoid import errors
sys.modules["case_documentation_app"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock() # Just in case

# Now import the module under test
import kiroshi_hotkeys

@dataclass
class CaseData:
    case_id: str = "CASE-TEST"
    description: str = "Test Description"

@dataclass
class MockUpload:
    name: str
    data: bytearray

@dataclass
class CaseSession:
    case: CaseData = field(default_factory=CaseData)
    uploads: List[Any] = field(default_factory=list)
    log_uploads: List[Any] = field(default_factory=list)
    screenshots: List[Any] = field(default_factory=list)
    milestones: List[Any] = field(default_factory=list)
    attachments_index: dict = field(default_factory=dict)

class TestHotkeyPerformance(unittest.TestCase):
    def test_snapshot_performance_and_correctness(self):
        # Setup a heavy session
        session = CaseSession()

        # Simulate heavy data (e.g., 50MB of binary data total)
        # Using bytearray to ensure deepcopy would be slow
        heavy_data_size = 10 * 1024 * 1024 # 10MB per file
        for i in range(5):
            data = bytearray(b"0" * heavy_data_size)
            session.uploads.append(MockUpload(name=f"file{i}.bin", data=data))

        case_sessions = [session]

        # Measure time
        start_time = time.perf_counter()
        kiroshi_hotkeys.update_hotkey_snapshot(case_sessions, 0, {}, "")
        end_time = time.perf_counter()
        duration = end_time - start_time

        print(f"Snapshot update took {duration:.4f} seconds")

        # Assert performance
        # Without optimization, this takes ~0.4s. With optimization, it should be < 0.01s
        self.assertLess(duration, 0.1, "Snapshot update was too slow! Optimization might be missing.")

        # Verify snapshot state
        snapshot = kiroshi_hotkeys._snapshot_state
        self.assertIsNotNone(snapshot.session, "Snapshot session should not be None")

        # Verify that the case data is present and correct
        self.assertEqual(snapshot.session.case.case_id, "CASE-TEST")

        # Verify that uploads are empty in the snapshot (the optimization)
        self.assertEqual(len(snapshot.session.uploads), 0, "Uploads should be empty in snapshot to save memory/time")

        # Verify original session is untouched
        self.assertEqual(len(session.uploads), 5, "Original session uploads should not be modified")

if __name__ == "__main__":
    unittest.main()
