
import sys
import os
from unittest.mock import MagicMock

# Add root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import dataclasses

# Patch json.dump to avoid TypeError with MagicMock
def mock_json_dump(obj, fp, **kwargs):
    fp.write("{}")
json.dump = mock_json_dump

# Patch dataclasses.asdict to avoid TypeError with MagicMock
original_asdict = dataclasses.asdict
def mock_asdict(obj):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj)
dataclasses.asdict = mock_asdict

# Mock dependencies before import
streamlit_mock = MagicMock()
streamlit_mock.__path__ = []  # Mark as a package
sys.modules["streamlit"] = streamlit_mock
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Now import the app
import case_documentation_app

def test_title_similarity_score_basic():
    # Identical titles should have score 1.0 (base=1.0, jaccard=1.0 -> 0.6+0.4=1.0)
    tokens = {"hello", "world"}
    norm = "hello world"
    score = case_documentation_app._title_similarity_score(tokens, tokens, norm, norm)
    assert score == 1.0

def test_title_similarity_score_disjoint():
    tokens_a = {"hello"}
    tokens_b = {"world"}
    norm_a = "hello"
    norm_b = "world"
    score = case_documentation_app._title_similarity_score(tokens_a, tokens_b, norm_a, norm_b)
    assert score == 0.0

def test_clustering_basic():
    titles = [
        "Scanner connection issue",
        "Scanner connection problem",
        "Completely unrelated title",
        "Scanner connection failure"
    ]
    assignments, label_map = case_documentation_app._cluster_case_titles(titles)

    # Expect 1st, 2nd, 4th to be in same cluster (index 0)
    # 3rd in separate cluster (index 1)

    # Note: clustering order depends on implementation details, but let's check basic structure
    print(f"Assignments: {assignments}")
    print(f"Label Map: {label_map}")
    assert assignments[0] == assignments[1]
    assert assignments[0] == assignments[3]
    assert assignments[2] != assignments[0]

    assert len(set(assignments)) == 2

if __name__ == "__main__":
    test_title_similarity_score_basic()
    test_title_similarity_score_disjoint()
    test_clustering_basic()
    print("All tests passed!")
