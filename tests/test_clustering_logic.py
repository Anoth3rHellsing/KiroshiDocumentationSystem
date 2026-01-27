
import pytest
from case_documentation_app import _cluster_case_titles, _normalize_title_similarity, _title_similarity_tokens, _title_similarity_score

def test_clustering_basics():
    titles = [
        "System Error 500",
        "System Error 502",  # Should cluster (high similarity)
        "Network Down",
        "Printer Jam",
    ]
    assignments, label_map = _cluster_case_titles(titles)
    print(f"\nAssignments: {assignments}")

    # "System Error 500" (0) and "System Error 502" (1) should be same cluster
    assert assignments[0] == assignments[1]

    # "Network Down" (2) should be different
    assert assignments[2] != assignments[0]

    # "Printer Jam" (3) should be different
    assert assignments[3] != assignments[0]
    assert assignments[3] != assignments[2]

def test_clustering_no_tokens():
    # "ab" and "cd" have no tokens (too short).
    titles = ["ab", "cd", "xy", "xy"]
    assignments, label_map = _cluster_case_titles(titles)
    print(f"\nNo Tokens Assignments: {assignments}")

    # "ab" != "cd"
    assert assignments[0] != assignments[1]
    # "xy" == "xy"
    assert assignments[2] == assignments[3]

def test_clustering_disjoint():
    titles = ["Alpha Bravo", "Charlie Delta"]
    assignments, _ = _cluster_case_titles(titles)
    assert assignments[0] != assignments[1]

def test_clustering_update_empty_cluster():
    # Title 1: "1234567890" (no tokens, normalized "1234567890")
    # Title 2: "1234567890 ABC" (tokens "abc", normalized "1234567890 abc")
    # They should match by string similarity even though Title 1 has no tokens.
    titles_close = ["1234567890", "1234567890 ABC"]
    assignments_close, _ = _cluster_case_titles(titles_close)
    print(f"\nEmpty Cluster Assignments: {assignments_close}")
    assert assignments_close[0] == assignments_close[1]

def test_clustering_common_token():
    # "System Error" and "System Failure" might not cluster due to high threshold.
    # Use something closer.
    titles = ["System Connection Error", "System Connection Failure"]
    assignments, _ = _cluster_case_titles(titles)
    print(f"\nCommon Token Assignments: {assignments}")
    assert assignments[0] == assignments[1]

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", "-s", __file__]))
