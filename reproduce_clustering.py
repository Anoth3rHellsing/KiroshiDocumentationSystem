
import time
import random
import string
import sys
from pathlib import Path
import unittest.mock
import json
from collections import defaultdict, Counter
from typing import Sequence, Any

# Add repo root to path so we can import case_documentation_app
repo_root = Path(__file__).resolve().parent
sys.path.insert(0, str(repo_root))

# Mock streamlit and its submodules
class MockSessionState(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        return unittest.mock.MagicMock()

    def __setattr__(self, key, value):
        self[key] = value

    def get(self, key, default=None):
        return self[key] if key in self else default

st_mock = unittest.mock.MagicMock()
st_mock.session_state = MockSessionState()
st_mock.session_state["show_tutorial"] = False
st_mock.session_state["tutorial_metadata"] = {}
st_mock.session_state["debug_mode"] = False
st_mock.session_state["enable_holiday_theme"] = False
st_mock.session_state["dark_mode_enabled"] = False
st_mock.session_state["attachments_directory"] = "/tmp"

sys.modules["streamlit"] = st_mock
sys.modules["streamlit.components.v1"] = unittest.mock.MagicMock()
sys.modules["streamlit.errors"] = unittest.mock.MagicMock()
sys.modules["altair"] = unittest.mock.MagicMock()

# Mock other display-dependent modules
sys.modules["pyautogui"] = unittest.mock.MagicMock()
sys.modules["PIL"] = unittest.mock.MagicMock()
sys.modules["mss"] = unittest.mock.MagicMock()
sys.modules["pytesseract"] = unittest.mock.MagicMock()
sys.modules["reportlab"] = unittest.mock.MagicMock()
sys.modules["reportlab.lib"] = unittest.mock.MagicMock()
sys.modules["reportlab.lib.pagesizes"] = unittest.mock.MagicMock()
sys.modules["reportlab.lib.styles"] = unittest.mock.MagicMock()
sys.modules["reportlab.platypus"] = unittest.mock.MagicMock()
sys.modules["reportlab.graphics.shapes"] = unittest.mock.MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = unittest.mock.MagicMock()
sys.modules["tkinter"] = unittest.mock.MagicMock()
sys.modules["pyperclip"] = unittest.mock.MagicMock()
sys.modules["pynput"] = unittest.mock.MagicMock()
sys.modules["cryptography"] = unittest.mock.MagicMock()
sys.modules["cryptography.fernet"] = unittest.mock.MagicMock()
sys.modules["cryptography.hazmat"] = unittest.mock.MagicMock()
sys.modules["cryptography.hazmat.primitives"] = unittest.mock.MagicMock()
sys.modules["cryptography.hazmat.primitives.hashes"] = unittest.mock.MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf"] = unittest.mock.MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf.pbkdf2"] = unittest.mock.MagicMock()
sys.modules["requests"] = unittest.mock.MagicMock()
sys.modules["urllib3"] = unittest.mock.MagicMock()

# Import the module
import case_documentation_app

# Helper imports from app
_normalize_title_similarity = case_documentation_app._normalize_title_similarity
_title_similarity_tokens = case_documentation_app._title_similarity_tokens
_title_similarity_score = case_documentation_app._title_similarity_score
_summarize_text = case_documentation_app._summarize_text

# Original implementation (copied)
def original_cluster_case_titles(titles: Sequence[str]) -> tuple[list[int], dict[int, str]]:
    clusters: list[dict[str, Any]] = []
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

def generate_synthetic_titles(n=1000, vocab_size=500):
    vocab = [
        "".join(random.choices(string.ascii_lowercase, k=random.randint(4, 10)))
        for _ in range(vocab_size)
    ]
    titles = []
    for _ in range(n):
        length = random.randint(3, 8)
        title_tokens = random.choices(vocab, k=length)
        titles.append(" ".join(title_tokens))
    return titles

def benchmark():
    random.seed(42)
    # 5000 titles, 10000 vocab (low collision)
    titles = generate_synthetic_titles(n=5000, vocab_size=10000)
    print(f"Generated {len(titles)} titles.")

    print("Running ORIGINAL clustering...")
    start_time = time.time()
    orig_clusters, _ = original_cluster_case_titles(titles)
    end_time = time.time()
    orig_time = end_time - start_time
    print(f"Original took {orig_time:.4f} seconds.")

    print("Running OPTIMIZED clustering...")
    start_time = time.time()
    opt_clusters, _ = case_documentation_app._cluster_case_titles(titles)
    end_time = time.time()
    opt_time = end_time - start_time
    print(f"Optimized took {opt_time:.4f} seconds.")

    speedup = orig_time / opt_time if opt_time > 0 else 1.0
    print(f"Speedup: {speedup:.2f}x")

if __name__ == "__main__":
    benchmark()
