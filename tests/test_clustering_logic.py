
import sys
import types
from unittest.mock import MagicMock, patch
import pytest

# --- Mocking Setup ---
streamlit_mock = types.ModuleType("streamlit")
streamlit_mock.errors = types.ModuleType("streamlit.errors")
streamlit_mock.errors.StreamlitAPIException = Exception
streamlit_mock.components = types.ModuleType("streamlit.components")
streamlit_mock.components.v1 = MagicMock()

sys.modules["streamlit"] = streamlit_mock
sys.modules["streamlit.errors"] = streamlit_mock.errors
sys.modules["streamlit.components"] = streamlit_mock.components
sys.modules["streamlit.components.v1"] = streamlit_mock.components.v1

streamlit_mock.cache_resource = lambda *args, **kwargs: (lambda f: f)
streamlit_mock.cache_data = lambda *args, **kwargs: (lambda f: f)
class MockSessionState(dict):
    def __getattr__(self, key):
        return self.get(key, MagicMock())
    def __setattr__(self, key, value):
        self[key] = value

streamlit_mock.session_state = MockSessionState()
streamlit_mock.session_state.update({
    "tutorial_completed": True,
    "theme_preview": "auto",
    "dark_mode_enabled": False,
    "enable_holiday_theme": False,
})
# Satisfy inspect
streamlit_mock.altair_chart = MagicMock()
streamlit_mock.set_page_config = MagicMock()
streamlit_mock.sidebar = MagicMock()
streamlit_mock.markdown = MagicMock()
streamlit_mock.write = MagicMock()
streamlit_mock.caption = MagicMock()
streamlit_mock.code = MagicMock()
streamlit_mock.expander = MagicMock()
streamlit_mock.columns = MagicMock(return_value=[MagicMock(), MagicMock()])
streamlit_mock.tabs = MagicMock(return_value=[MagicMock()])
streamlit_mock.selectbox = MagicMock()
streamlit_mock.checkbox = MagicMock()
streamlit_mock.radio = MagicMock()
streamlit_mock.text_input = MagicMock()
streamlit_mock.text_area = MagicMock()
streamlit_mock.number_input = MagicMock()
streamlit_mock.date_input = MagicMock()
streamlit_mock.file_uploader = MagicMock()
streamlit_mock.download_button = MagicMock()
streamlit_mock.toggle = MagicMock()
streamlit_mock.metric = MagicMock()
streamlit_mock.divider = MagicMock()
streamlit_mock.image = MagicMock()
streamlit_mock.dataframe = MagicMock()
streamlit_mock.data_editor = MagicMock()
streamlit_mock.multiselect = MagicMock()
streamlit_mock.slider = MagicMock()
streamlit_mock.color_picker = MagicMock()
streamlit_mock.pyplot = MagicMock()
streamlit_mock.plotly_chart = MagicMock()
streamlit_mock.graphviz_chart = MagicMock()
streamlit_mock.map = MagicMock()
streamlit_mock.pydeck_chart = MagicMock()
streamlit_mock.vega_lite_chart = MagicMock()
streamlit_mock.bokeh_chart = MagicMock()
streamlit_mock.table = MagicMock()
streamlit_mock.json = MagicMock()
streamlit_mock.title = MagicMock()
streamlit_mock.header = MagicMock()
streamlit_mock.subheader = MagicMock()
streamlit_mock.latex = MagicMock()
streamlit_mock.empty = MagicMock()
streamlit_mock.progress = MagicMock()
streamlit_mock.spinner = MagicMock()
streamlit_mock.toast = MagicMock()
streamlit_mock.snow = MagicMock()
streamlit_mock.balloons = MagicMock()
streamlit_mock.audio = MagicMock()
streamlit_mock.video = MagicMock()
streamlit_mock.form = MagicMock()
streamlit_mock.form_submit_button = MagicMock()
streamlit_mock.echo = MagicMock()
streamlit_mock.help = MagicMock()
streamlit_mock.get_option = MagicMock()
streamlit_mock.set_option = MagicMock()
streamlit_mock.switch_page = MagicMock()
streamlit_mock.rerun = MagicMock()

sys.modules["altair"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()

sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.ImageGrab"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()

# --- Import App ---
with patch("json.dump"):
    import case_documentation_app

def test_cluster_case_titles_grouping():
    """Verify that clustering correctly groups similar titles."""
    titles = [
        "Scanner not connecting error 500",
        "Scanner not connecting error 501",
        "Unite login failed",
        "Unite login issues",
        "Completely unrelated issue",
        "Scanner not connecting please help",
    ]

    # We expect:
    # Cluster 1: Scanner not connecting ...
    # Cluster 2: Unite login ...
    # Cluster 3: Completely unrelated issue

    assignments, label_map = case_documentation_app._cluster_case_titles(titles)

    assert len(assignments) == len(titles)

    # Check that similar titles have same cluster ID
    assert assignments[0] == assignments[1] # Scanner errors
    assert assignments[0] == assignments[5] # Scanner help

    assert assignments[2] == assignments[3] # Unite login

    assert assignments[0] != assignments[2] # Scanner vs Unite
    assert assignments[0] != assignments[4] # Scanner vs Unrelated

    # Check labels
    cluster_id_scanner = assignments[0]
    label_scanner = label_map[cluster_id_scanner]
    assert "scanner" in label_scanner.lower() or "connecting" in label_scanner.lower()

def test_cluster_case_titles_empty():
    titles = ["", "   ", None, "Valid Title"]
    assignments, label_map = case_documentation_app._cluster_case_titles(titles)

    # Empty titles should be grouped together (or at least handled safely)
    assert assignments[0] == assignments[1]
    assert assignments[0] == assignments[2]

    assert assignments[3] != assignments[0]
    assert "Valid Title" in label_map[assignments[3]]

def test_cluster_case_titles_determinism():
    """Verify that clustering is deterministic."""
    titles = [f"Issue {i}" for i in range(100)] * 2
    import random
    random.seed(42)
    random.shuffle(titles)

    run1, _ = case_documentation_app._cluster_case_titles(titles)
    run2, _ = case_documentation_app._cluster_case_titles(titles)

    assert run1 == run2

def test_no_tokens_logic():
    """Verify behavior for titles with no tokens (short/stopwords)."""
    # 'a' is likely a stopword or too short, so no tokens.
    titles = ["a", "b", "a"]
    # 'a' and 'b' should be different clusters if threshold not met.
    # 'a' and 'a' should be same cluster.

    assignments, label_map = case_documentation_app._cluster_case_titles(titles)

    # 'a' -> tokens={}, normalized='a'
    # 'b' -> tokens={}, normalized='b'
    # 'a' vs 'b': score = SequenceMatcher('a', 'b').ratio() = 0.0 -> new cluster
    # 'a' vs 'a': score = 1.0 -> same cluster

    assert assignments[0] != assignments[1] # 'a' vs 'b'
    assert assignments[0] == assignments[2] # 'a' vs 'a'
