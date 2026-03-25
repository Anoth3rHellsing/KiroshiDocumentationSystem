import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import case_documentation_app

def test_case_sorting_with_updated_ts():
    """Verify that case_documentation_app sorting logic properly uses _updated_ts."""

    now = datetime.now()
    t1 = now - timedelta(days=2)
    t2 = now - timedelta(days=1)
    t3 = now - timedelta(hours=12)

    mock_throttle = MagicMock()
    mock_throttle.last_run = 0.0
    mock_throttle.data = []

    mock_cache = MagicMock()
    mock_cache.last_scan_ts = 0.0

    # We need to test the sorting, but the files won't exist in the mocked dirs.
    # We can mock the time difference to trigger the snapshot branch.
    mock_cache.last_scan_ts = datetime.now().timestamp()

    mock_data = {
        "case1": (t2.timestamp(), {
            "case_id": "case1",
            "updated": t2.isoformat(),
            "_updated_ts": t2.timestamp()
        }),
        "case2": (t3.timestamp(), {
            "case_id": "case2",
            "updated": t3.isoformat(),
            "_updated_ts": t3.timestamp()
        }),
        "case3": (t1.timestamp(), {
            "case_id": "case3",
            "updated": t1.isoformat(),
            "_updated_ts": t1.timestamp()
        }),
        "case_legacy": (t1.timestamp(), {
            "case_id": "case_legacy",
            "updated": t1.isoformat()
        })
    }

    mock_cache.data = mock_data

    with patch('case_documentation_app._get_refresh_throttle', return_value=mock_throttle), \
         patch('case_documentation_app._get_global_case_cache', return_value=mock_cache):

        cases = case_documentation_app._refresh_and_get_cases()

        assert len(cases) == 4
        assert cases[0]["case_id"] == "case2"
        assert cases[1]["case_id"] == "case1"
        assert cases[2]["case_id"] in ("case3", "case_legacy")
        assert cases[3]["case_id"] in ("case3", "case_legacy")
