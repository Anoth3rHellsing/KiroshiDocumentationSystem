from datetime import datetime
from case_documentation_app import _refresh_and_get_cases, DATABASE_DIR
import json

def test_sorting():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    # create sample files
    items = [
        {"case_id": "TEST_SORT-1", "last_modified": "2023-10-25T10:00:00"},
        {"case_id": "TEST_SORT-2", "last_modified": "2023-10-25T12:00:00"},
        {"case_id": "TEST_SORT-3", "last_modified": "2023-10-25T11:00:00"},
    ]
    for i, item in enumerate(items):
        with open(DATABASE_DIR / f"test_sort_case_{i}.json", "w") as f:
            json.dump(item, f)

    # Force the cache throttle to trigger a fresh scan
    import case_documentation_app
    case_documentation_app._get_refresh_throttle().last_run = 0.0
    case_documentation_app._get_global_case_cache().last_scan_ts = 0.0

    res = _refresh_and_get_cases()
    # Filter only test cases
    res = [r for r in res if r.get("case_id", "").startswith("TEST_SORT-")]

    # Due to caching or state we only test the items we explicitly added
    assert len(res) >= 3

    # Check proper sorting
    # The output from _refresh_and_get_cases is already sorted
    assert res[0]["case_id"] == "TEST_SORT-2"
    assert res[1]["case_id"] == "TEST_SORT-3"
    assert res[2]["case_id"] == "TEST_SORT-1"
