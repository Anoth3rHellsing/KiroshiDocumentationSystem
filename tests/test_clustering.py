import sys
import unittest
from unittest.mock import MagicMock
import time
import random
import re
from functools import lru_cache
from difflib import SequenceMatcher
import textwrap
import json

# --- 1. Mock dependencies BEFORE importing case_documentation_app ---

# Patch json to avoid serialization errors with Mocks during import
real_json = json
mock_json = MagicMock()
mock_json.loads = real_json.loads
mock_json.JSONDecodeError = real_json.JSONDecodeError
mock_json.dump = MagicMock()
mock_json.dumps = real_json.dumps # App might use dumps
sys.modules["json"] = mock_json

# Mock modules that might cause side effects or require GUI
mock_st = MagicMock()
class SessionState(dict):
    def __getattr__(self, item):
        return self.get(item)
    def __setattr__(self, key, value):
        self[key] = value
mock_st.session_state = SessionState()
sys.modules["streamlit"] = mock_st
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.pdfbase"] = MagicMock()
sys.modules["reportlab.rl_config"] = MagicMock()

sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Mock local modules
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Now we can import the app
# Ensure the directory is in path
sys.path.append(".")
try:
    from case_documentation_app import _cluster_case_titles, _title_similarity_tokens, _normalize_title_similarity, _title_similarity_score, _summarize_text
except ImportError as e:
    # If imports fail due to some other dependency, we need to know
    raise ImportError(f"Failed to import case_documentation_app: {e}")

# --- 2. Reference Implementation (Original) ---

def reference_cluster_case_titles(titles: list[str]) -> tuple[list[int], dict[int, str]]:
    clusters: list[dict[str, object]] = []
    assignments: list[int] = []

    for title in titles:
        normalized = _normalize_title_similarity(title)
        tokens = _title_similarity_tokens(title)

        if not normalized and not tokens:
            blank_index = next(
                (
                    idx
                    for idx, cluster in enumerate(clusters)
                    if not cluster.get("tokens") and not cluster.get("normalized")
                ),
                None,
            )
            if blank_index is None:
                clusters.append(
                    {
                        "normalized": "",
                        "tokens": set(),
                        "label": "Caso sin título",
                    }
                )
                blank_index = len(clusters) - 1
            assignments.append(blank_index)
            continue

        best_index = -1
        best_score = 0.0
        for idx, cluster in enumerate(clusters):
            cluster_tokens = cluster.get("tokens") or set()
            cluster_norm = str(cluster.get("normalized") or "")
            score = _title_similarity_score(tokens, cluster_tokens, normalized, cluster_norm)
            if score > best_score:
                best_score = score
                best_index = idx

        threshold = 0.68 if tokens else 0.8
        if best_index == -1 or best_score < threshold:
            label_source = title if isinstance(title, str) and title.strip() else normalized
            label = (
                _summarize_text(label_source, width=80)
                if label_source
                else "Caso sin título"
            )
            clusters.append(
                {
                    "normalized": normalized,
                    "tokens": set(tokens),
                    "label": label,
                }
            )
            assignments.append(len(clusters) - 1)
        else:
            cluster = clusters[best_index]
            cluster_tokens = cluster.setdefault("tokens", set())
            cluster_tokens.update(tokens)
            cluster["normalized"] = cluster.get("normalized") or normalized
            if isinstance(title, str) and title.strip():
                candidate_label = _summarize_text(title, width=80)
                if len(candidate_label) > len(str(cluster.get("label") or "")):
                    cluster["label"] = candidate_label
            assignments.append(best_index)

    label_map = {idx: str(cluster.get("label") or "Caso sin título") for idx, cluster in enumerate(clusters)}
    return assignments, label_map

# --- 3. Tests ---

class TestClustering(unittest.TestCase):

    def generate_titles(self, n=1000):
        # Larger vocabulary to simulate realistic scenarios
        words = [f"word{i}" for i in range(5000)]
        titles = []
        random.seed(42)
        for _ in range(n):
            # Create some clusters by repeating combinations
            t_words = random.sample(words, k=random.randint(2, 6))
            titles.append(" ".join(t_words))
        return titles

    def test_clustering_correctness(self):
        """Verify that the optimized implementation produces exactly the same result as the reference."""
        titles = self.generate_titles(500)

        assign_ref, map_ref = reference_cluster_case_titles(titles)
        assign_opt, map_opt = _cluster_case_titles(titles)

        self.assertEqual(len(map_ref), len(map_opt), "Cluster count mismatch")
        self.assertEqual(assign_ref, assign_opt, "Assignments mismatch")
        self.assertEqual(map_ref, map_opt, "Label map mismatch")

    def test_clustering_performance(self):
        """Verify that the optimized implementation is faster."""
        # Use enough items to make quadratic complexity hurt
        titles = self.generate_titles(2000)

        # Warmup
        reference_cluster_case_titles(titles[:10])
        _cluster_case_titles(titles[:10])

        start = time.time()
        reference_cluster_case_titles(titles)
        ref_time = time.time() - start

        start = time.time()
        _cluster_case_titles(titles)
        opt_time = time.time() - start

        print(f"\nReference time: {ref_time:.4f}s")
        print(f"Optimized time: {opt_time:.4f}s")
        print(f"Speedup: {ref_time / opt_time:.2f}x")

        self.assertLess(opt_time, ref_time, "Optimized version should be faster")
        # Assert at least 5% speedup (conservative to avoid flakiness in CI)
        self.assertLess(opt_time, ref_time * 0.95, "Optimized version should be significantly faster")

if __name__ == "__main__":
    unittest.main()
