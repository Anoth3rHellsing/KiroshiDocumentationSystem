
import time
import copy
from dataclasses import dataclass, field
from typing import List, Dict, Any
import pytest

# Mock classes to simulate the app's structure
@dataclass
class CaseData:
    case_id: str = "CASE-123"
    description: str = "A sample case description."
    # ... other fields ...

@dataclass
class CaseSession:
    case: CaseData
    uploads: List[Any] = field(default_factory=list)
    log_uploads: List[Any] = field(default_factory=list)
    screenshots: List[Any] = field(default_factory=list)
    attachments_index: Dict[str, Any] = field(default_factory=dict)
    milestones: Dict[str, Any] = field(default_factory=dict)

def baseline_copy(session):
    return copy.deepcopy(session)

def optimized_copy(session):
    # Shallow copy the container
    new_session = copy.copy(session)

    # Deep copy necessary fields
    if hasattr(session, "case"):
        new_session.case = copy.deepcopy(session.case)
    if hasattr(session, "milestones"):
        new_session.milestones = copy.deepcopy(session.milestones)
    if hasattr(session, "attachments_index"):
        new_session.attachments_index = copy.deepcopy(session.attachments_index)

    # Clear heavy assets
    new_session.uploads = []
    new_session.log_uploads = []
    new_session.screenshots = []

    return new_session

def test_hotkey_snapshot_performance():
    # Setup heavy session
    print("Setting up heavy session...")
    # Use bytearray to ensure deepcopy actually copies memory
    heavy_data = bytearray(b"x" * (10 * 1024 * 1024)) # 10 MB payload

    session = CaseSession(case=CaseData())
    # Add some heavy "files"
    # Create distinct objects to ensure they are all copied
    session.uploads = [bytearray(heavy_data) for _ in range(5)] # 50 MB
    session.screenshots = [bytearray(heavy_data) for _ in range(5)] # 50 MB

    # Measure Baseline
    start_time = time.perf_counter()
    _ = baseline_copy(session)
    baseline_duration = time.perf_counter() - start_time
    print(f"Baseline (deepcopy) time: {baseline_duration:.6f} seconds")

    # Measure Optimized
    start_time = time.perf_counter()
    optimized_session = optimized_copy(session)
    optimized_duration = time.perf_counter() - start_time
    print(f"Optimized time: {optimized_duration:.6f} seconds")

    # Verify correctness (basic check)
    assert optimized_session.case.case_id == "CASE-123"
    assert optimized_session.uploads == []

    if baseline_duration > 0.01: # Only assert speedup if baseline is measurable/slow enough
        if optimized_duration > 0:
            speedup = baseline_duration / optimized_duration
            print(f"Speedup: {speedup:.2f}x")
            assert speedup > 10, f"Optimization speedup {speedup:.2f}x is less than 10x"
        else:
            print("Optimized time was too fast to measure accurately (infinite speedup).")
    else:
        pytest.skip("Baseline too fast to measure performance improvement reliably.")

if __name__ == "__main__":
    test_hotkey_snapshot_performance()
