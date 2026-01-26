
import unittest
from datetime import datetime
import time

class TestCaseSorting(unittest.TestCase):
    def test_sorting_mixed_compatibility(self):
        """
        Verify that sorting works correctly when some items have _updated_ts and some don't.
        """
        # Create test data
        now = time.time()

        # Case 1: Legacy item (no _updated_ts)
        t1 = now - 1000
        iso1 = datetime.fromtimestamp(t1).isoformat()
        item1 = {"updated": iso1, "id": "legacy_1"}

        # Case 2: New item (has _updated_ts)
        t2 = now - 500 # Newer
        iso2 = datetime.fromtimestamp(t2).isoformat()
        item2 = {"updated": iso2, "_updated_ts": float(t2), "id": "new_2"}

        # Case 3: Legacy item, very old
        t3 = now - 2000
        iso3 = datetime.fromtimestamp(t3).isoformat()
        item3 = {"updated": iso3, "id": "legacy_3"}

        # Case 4: New item, newest
        t4 = now
        iso4 = datetime.fromtimestamp(t4).isoformat()
        item4 = {"updated": iso4, "_updated_ts": float(t4), "id": "new_4"}

        # Case 5: Broken item (invalid date, no ts)
        item5 = {"updated": "invalid", "id": "broken_5"}

        items = [item1, item2, item3, item4, item5]

        # Proposed sorting logic (to be used in case_documentation_app.py)
        def _get_sort_ts(item):
            # Fast path
            ts = item.get("_updated_ts")
            if isinstance(ts, (int, float)):
                return ts

            # Fallback path
            t = item.get("updated")
            if not t: return 0.0
            try:
                return datetime.fromisoformat(str(t)).timestamp()
            except ValueError:
                return 0.0

        sorted_items = sorted(items, key=_get_sort_ts, reverse=True)

        # Expected order: 4 (newest), 2, 1, 3, 5 (invalid=0)
        expected_ids = ["new_4", "new_2", "legacy_1", "legacy_3", "broken_5"]
        actual_ids = [i["id"] for i in sorted_items]

        self.assertEqual(actual_ids, expected_ids)

if __name__ == "__main__":
    unittest.main()
