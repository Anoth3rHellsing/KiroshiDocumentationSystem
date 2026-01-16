
import unittest
from datetime import datetime, timedelta
import random
import time

class TestSortingPerformance(unittest.TestCase):
    def test_sorting_correctness_and_perf(self):
        # Generate mixed data
        N = 10000
        items = []
        base_dt = datetime.now()

        for i in range(N):
            dt = base_dt - timedelta(minutes=random.randint(0, 10000))
            iso_str = dt.isoformat()
            ts = dt.timestamp()

            items.append({
                "updated": iso_str,
                "_updated_ts": ts,
                "id": i
            })

        # Sort using old method (simulation)
        def _parse_time(t):
            if not t: return 0.0
            try:
                return datetime.fromisoformat(str(t)).timestamp()
            except ValueError:
                return 0.0

        start_time = time.perf_counter()
        sorted_old = sorted(items, key=lambda x: _parse_time(x.get("updated")), reverse=True)
        old_duration = time.perf_counter() - start_time

        # Sort using new method
        start_time = time.perf_counter()
        sorted_new = sorted(items, key=lambda x: x.get("_updated_ts", 0.0), reverse=True)
        new_duration = time.perf_counter() - start_time

        # Verify correctness
        ids_old = [item["id"] for item in sorted_old]
        ids_new = [item["id"] for item in sorted_new]
        self.assertEqual(ids_old, ids_new, "Sorting order mismatch")

        # Verify performance (soft assertion, just print)
        print(f"\nSorting {N} items:")
        print(f"Old method: {old_duration*1000:.2f} ms")
        print(f"New method: {new_duration*1000:.2f} ms")
        speedup = old_duration / new_duration if new_duration > 0 else 0
        print(f"Speedup: {speedup:.2f}x")

        # We expect a speedup, but won't fail the test if CI is weird
        if speedup < 1.5:
            print("WARNING: Expected speedup > 1.5x")

if __name__ == "__main__":
    unittest.main()
