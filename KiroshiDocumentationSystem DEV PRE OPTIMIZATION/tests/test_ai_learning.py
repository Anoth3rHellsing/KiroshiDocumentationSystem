import logging

import pytest

from KiroshiApp.utils import merge_ai_learning_datasets


def _case_entry(case_id, title, *, timestamp, source_path, solution, root_cause, keywords, version):
    return {
        "case_id": case_id,
        "title": title,
        "timestamp": timestamp,
        "source_path": source_path,
        "solution": solution,
        "root_cause": root_cause,
        "keywords": keywords,
        "application_version": version,
    }


def test_merge_ai_learning_datasets_prefers_newer_case():
    base_dataset = {
        "cases": [
            _case_entry(
                "100",
                "Legacy troubleshooting",
                timestamp=1000.0,
                source_path="local/100",
                solution="Old fix",
                root_cause="Caching issue",
                keywords=["legacy", "cache"],
                version="1.0",
            ),
            _case_entry(
                "200",
                "Existing base case",
                timestamp=900.0,
                source_path="local/200",
                solution="Base fix",
                root_cause="Misconfiguration",
                keywords=["base"],
                version="1.1",
            ),
        ],
        "merged_sources": ["local-internal"],
        "source_signature": (("alpha", 1.0),),
    }

    imported_dataset = {
        "cases": [
            _case_entry(
                "100",
                "Updated troubleshooting",
                timestamp=1005.0,
                source_path="local/100",
                solution="New fix",
                root_cause="Caching issue",
                keywords=["legacy", "cache", "updated"],
                version="1.2",
            ),
            _case_entry(
                "300",
                "Newly shared case",
                timestamp=1100.0,
                source_path="shared/300",
                solution="Fresh insight",
                root_cause="New cause",
                keywords=["shared"],
                version="2.0",
            ),
        ],
        "merged_sources": ["partner-handoff"],
        "shared_by": "Alice",
    }

    dataset = merge_ai_learning_datasets(
        base_dataset,
        imported_dataset,
        collaborator="Bob",
        local_signature=(("beta", 2.0),),
    )

    assert dataset is not None
    assert dataset["case_count"] == 3

    case_ids = [entry["case_id"] for entry in dataset["cases"]]
    assert case_ids == ["300", "100", "200"]

    updated_case = next(entry for entry in dataset["cases"] if entry["case_id"] == "100")
    assert updated_case["title"] == "Updated troubleshooting"
    assert updated_case["solution"] == "New fix"
    assert updated_case["application_version"] == "1.2"

    merged_sources = set(dataset["merged_sources"])
    assert merged_sources == {"Bob", "local", "local-internal", "partner-handoff"}

    assert dataset["source_signature"] == [["beta", 2.0]]


def test_merge_ai_learning_datasets_malformed_payload_logs_error(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.ERROR):
        result = merge_ai_learning_datasets(None, {"cases": "not-a-list"})

    assert result is None
    assert any("cases list" in message for message in caplog.messages)
