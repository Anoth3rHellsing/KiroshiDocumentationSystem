
import unittest
from datetime import datetime
import time

# Mocking the logic I implemented
def _parse_time(t):
    if not t: return 0.0
    try:
        return datetime.fromisoformat(str(t)).timestamp()
    except ValueError:
        return 0.0

def _sort_key(x):
    ts = x.get("_updated_ts")
    if ts is not None:
        return ts
    return _parse_time(x.get("updated"))

class TestCaseSorting(unittest.TestCase):
    def test_sorting_mixed_data(self):
        # Case 1: Item with _updated_ts
        ts1 = 1700000000.0
        item1 = {
            "case_id": "1",
            "updated": datetime.fromtimestamp(ts1).isoformat(),
            "_updated_ts": ts1
        }

        # Case 2: Item without _updated_ts (legacy cache)
        ts2 = 1600000000.0
        item2 = {
            "case_id": "2",
            "updated": datetime.fromtimestamp(ts2).isoformat()
        }

        # Case 3: Item with _updated_ts (newest)
        ts3 = 1800000000.0
        item3 = {
            "case_id": "3",
            "updated": datetime.fromtimestamp(ts3).isoformat(),
            "_updated_ts": ts3
        }

        # Case 4: Invalid updated string
        item4 = {
            "case_id": "4",
            "updated": "invalid"
        }

        items = [item1, item2, item3, item4]

        # Sort descending
        items.sort(key=_sort_key, reverse=True)

        # Expected order: 3 (newest), 1, 2, 4 (invalid=0)
        self.assertEqual(items[0]["case_id"], "3")
        self.assertEqual(items[1]["case_id"], "1")
        self.assertEqual(items[2]["case_id"], "2")
        self.assertEqual(items[3]["case_id"], "4")

    def test_sorting_performance_simulation(self):
        # Generate mixed data
        N = 1000
        items = []
        for i in range(N):
            ts = time.time() - i * 1000
            if i % 2 == 0:
                # With optimized key
                items.append({
                    "updated": datetime.fromtimestamp(ts).isoformat(),
                    "_updated_ts": ts
                })
            else:
                # Without optimized key
                items.append({
                    "updated": datetime.fromtimestamp(ts).isoformat()
                })

        start = time.perf_counter()
        items.sort(key=_sort_key, reverse=True)
        end = time.perf_counter()
        # print(f"Sorted {N} mixed items in {end - start:.4f}s")

        # Simple verification
        for i in range(N - 1):
            t_curr = _sort_key(items[i])
            t_next = _sort_key(items[i+1])
            self.assertGreaterEqual(t_curr, t_next)

if __name__ == "__main__":
    unittest.main()
