import sys
import unittest
from unittest.mock import MagicMock
import types
import os

class TestClusteringLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create mocks for dependencies
        st_mock = MagicMock()
        st_mock.cache_data = lambda *args, **kwargs: (lambda func: func)
        st_mock.cache_resource = lambda *args, **kwargs: (lambda func: func)

        # Helper to create dummy modules
        def mock_module(name):
            if name in sys.modules:
                return sys.modules[name]
            m = types.ModuleType(name)
            sys.modules[name] = m
            return m

        # Mock ALL the things that might cause side effects on import
        st_mod = mock_module("streamlit")
        st_mod.cache_data = st_mock.cache_data
        st_mod.cache_resource = st_mock.cache_resource
        st_mod.experimental_get_query_params = MagicMock(return_value={})
        st_mod.query_params = MagicMock(return_value={})
        st_mod.altair_chart = MagicMock()
        st_mod.set_page_config = MagicMock()

        class SessionState(dict):
            def __getattr__(self, item):
                return self.get(item)
            def __setattr__(self, key, value):
                self[key] = value

        st_mod.session_state = SessionState()
        st_mod.markdown = MagicMock()
        st_mod.container = MagicMock()
        st_mod.progress = MagicMock()
        st_mod.select_slider = MagicMock()
        st_mod.caption = MagicMock()
        st_mod.rerun = MagicMock()

        for name in ["radio", "checkbox", "text_input", "button", "warning", "success", "error", "info", "stop", "expander", "form", "form_submit_button", "columns", "tabs", "write", "code", "json", "dataframe", "metric", "image", "multiselect", "selectbox", "file_uploader", "download_button", "text_area", "empty", "spinner", "balloons", "snow", "toast", "sidebar", "echo", "help", "get_option", "set_option", "subheader", "title", "toggle", "date_input", "number_input"]:
             setattr(st_mod, name, MagicMock())

        mock_module("streamlit.components")
        st_comp = mock_module("streamlit.components.v1")
        st_comp.html = MagicMock()
        st_err = mock_module("streamlit.errors")
        st_err.StreamlitAPIException = Exception

        mock_module("pandas")
        alt = mock_module("altair")
        alt.themes = MagicMock()
        mock_module("reportlab")
        mock_module("reportlab.lib")

        rl_pagesizes = mock_module("reportlab.lib.pagesizes")
        rl_pagesizes.letter = (612, 792)

        rl_colors = mock_module("reportlab.lib.colors")
        rl_colors.white = (1, 1, 1)

        rl_styles = mock_module("reportlab.lib.styles")
        rl_styles.getSampleStyleSheet = MagicMock()
        rl_styles.ParagraphStyle = MagicMock()

        rl_platypus = mock_module("reportlab.platypus")
        for cls_name in ["SimpleDocTemplate", "Table", "TableStyle", "Paragraph", "Spacer", "Image", "Preformatted"]:
            setattr(rl_platypus, cls_name, MagicMock())

        mock_module("reportlab.graphics")
        mock_module("reportlab.graphics.charts")
        rl_barcharts = mock_module("reportlab.graphics.charts.barcharts")
        rl_barcharts.VerticalBarChart = MagicMock()

        rl_lineplots = mock_module("reportlab.graphics.charts.lineplots")
        rl_lineplots.LinePlot = MagicMock()

        mock_module("reportlab.graphics.widgets")

        rl_markers = mock_module("reportlab.graphics.widgets.markers")
        rl_markers.makeMarker = MagicMock()

        rl_shapes = mock_module("reportlab.graphics.shapes")
        rl_shapes.Drawing = MagicMock()
        rl_shapes.String = MagicMock()
        mock_module("requests")
        u3 = mock_module("urllib3")
        u3.disable_warnings = MagicMock()
        u3.exceptions = MagicMock()
        u3.exceptions.InsecureRequestWarning = Warning

        mock_module("pyautogui")
        mock_module("tkinter")
        mock_module("PIL")
        mock_module("pytesseract")
        mock_module("mss")

        # Internal modules
        k_chat = mock_module("kiroshi_chat")
        k_chat.load_memory = MagicMock()
        k_chat.save_memory = MagicMock()
        k_chat.query_kiroshi = MagicMock()
        k_chat.SYSTEM_PROMPT = "prompt"
        k_chat.load_manual_docs = MagicMock()
        k_chat.save_manual_docs = MagicMock()
        k_chat.search_manual_docs = MagicMock()
        k_chat.get_assistant_notes = MagicMock()
        k_chat.set_assistant_notes = MagicMock()
        k_chat.build_assistant_memory_prompt = MagicMock()
        k_chat.build_system_prompt = MagicMock()

        k_local = mock_module("kiroshi_local_ai")
        k_local.check_model_exists = MagicMock()
        k_local.download_model = MagicMock()
        k_local.MODELS = {}

        k_cloud = mock_module("kiroshi_cloud_sync")
        k_cloud.AgentBlockedError = Exception
        k_cloud.AuthenticationError = Exception
        k_cloud.CloudError = Exception
        k_cloud.cloud_share_status = MagicMock()
        k_cloud.open_cloud_session = MagicMock()
        k_cloud.summarize_dataset = MagicMock()
        k_cloud.decode_device_token = MagicMock()
        k_cloud.overlay_guidance = MagicMock()

        k_video = mock_module("kiroshi_video")
        k_video.optimize_video = MagicMock()

        k_hotkeys = mock_module("kiroshi_hotkeys")
        k_hotkeys.ensure_hotkey_listener = MagicMock()
        k_hotkeys.update_hotkey_snapshot = MagicMock()

        # Read the file content
        with open("case_documentation_app.py", "r", encoding="utf-8") as f:
            source = f.read()

        # Register the dummy module for dataclasses to work
        test_module_name = "case_documentation_app_test_context"
        test_module = types.ModuleType(test_module_name)
        sys.modules[test_module_name] = test_module

        # Prepare globals for exec
        cls.script_globals = {
            "__file__": "case_documentation_app.py",
            "__name__": test_module_name,
            "sys": sys,
            "os": os,
            "MagicMock": MagicMock,
            "unittest": unittest,
        }

        # Execute the script in the isolated namespace
        # We need to suppress output potentially
        try:
            exec(source, cls.script_globals)
        except Exception as e:
            print(f"Error executing script: {e}")
            raise

    def test_similarity_score_exact(self):
        _title_similarity_score = self.script_globals["_title_similarity_score"]
        tokens_a = {"error", "login"}
        tokens_b = {"error", "login"}
        norm_a = "error login"
        norm_b = "error login"
        score = _title_similarity_score(tokens_a, tokens_b, norm_a, norm_b)
        self.assertAlmostEqual(score, 1.0)

    def test_similarity_score_disjoint(self):
        _title_similarity_score = self.script_globals["_title_similarity_score"]
        tokens_a = {"error"}
        tokens_b = {"login"}
        norm_a = "error"
        norm_b = "login"
        score = _title_similarity_score(tokens_a, tokens_b, norm_a, norm_b)
        self.assertEqual(score, 0.0)

    def test_similarity_score_partial(self):
        _title_similarity_score = self.script_globals["_title_similarity_score"]
        tokens_a = {"error", "login", "failed"}
        tokens_b = {"error", "login"}
        norm_a = "error login failed"
        norm_b = "error login"
        score = _title_similarity_score(tokens_a, tokens_b, norm_a, norm_b)
        self.assertTrue(0.0 < score < 1.0)

    def test_clustering_exact_duplicates(self):
        _cluster_case_titles = self.script_globals["_cluster_case_titles"]
        titles = ["Login Error", "Login Error", "Login Error"]
        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(assignments, [0, 0, 0])
        self.assertEqual(len(labels), 1)

    def test_clustering_similar(self):
        _cluster_case_titles = self.script_globals["_cluster_case_titles"]
        titles = [
            "Login Error 123",
            "Login Error 456",
            "Scanner Disconnected",
            "Scanner Disconnected issue"
        ]
        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(assignments[0], assignments[1])
        self.assertEqual(assignments[2], assignments[3])
        self.assertNotEqual(assignments[0], assignments[2])

    def test_clustering_performance_large(self):
        _cluster_case_titles = self.script_globals["_cluster_case_titles"]
        # Generate 1000 titles
        titles = []
        base_words = ["Apple", "Banana", "Cherry", "Date", "Elderberry", "Fig", "Grape", "Honeydew", "Kiwi", "Lemon"]
        for i in range(1000):
             w1 = base_words[i % 10]
             w2 = base_words[(i // 10) % 10]
             w3 = base_words[(i // 100) % 10]
             titles.append(f"Issue {w1} {w2} {w3}")

        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(len(assignments), 1000)

    def test_clustering_performance_duplicates(self):
        _cluster_case_titles = self.script_globals["_cluster_case_titles"]
        # Generate 1000 identical titles
        titles = ["Login Error" for _ in range(1000)]

        assignments, labels = _cluster_case_titles(titles)
        self.assertEqual(len(assignments), 1000)

if __name__ == '__main__':
    unittest.main()
