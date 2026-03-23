from difflib import SequenceMatcher

def _title_similarity_score(tokens_a: set[str], tokens_b: set[str], norm_a: str, norm_b: str, matcher: SequenceMatcher | None = None) -> float:
    if tokens_a and tokens_b and tokens_a.isdisjoint(tokens_b):
        return 0.0

    if norm_a or norm_b:
        if matcher is not None:
            matcher.set_seq1(norm_a)
            base = matcher.ratio()
        else:
            base = SequenceMatcher(None, norm_a, norm_b).ratio()
    else:
        base = 0.0

    if tokens_a and tokens_b:
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        jaccard = (intersection / union) if union else 0.0
        return 0.6 * base + 0.4 * jaccard
    return base

import time
import random
import string
import sys
import json
from unittest.mock import MagicMock

# Mock required modules to load case_documentation_app
sys.modules['pandas'] = MagicMock()
sys.modules['altair'] = MagicMock()
sys.modules['streamlit'] = MagicMock()
sys.modules['streamlit.components'] = MagicMock()
sys.modules['streamlit.components.v1'] = MagicMock()
sys.modules['streamlit.errors'] = MagicMock()
sys.modules['reportlab'] = MagicMock()
sys.modules['reportlab.lib.pagesizes'] = MagicMock()
sys.modules['reportlab.lib'] = MagicMock()
sys.modules['reportlab.lib.styles'] = MagicMock()
sys.modules['reportlab.platypus'] = MagicMock()
sys.modules['reportlab.graphics'] = MagicMock()
sys.modules['reportlab.graphics.shapes'] = MagicMock()
sys.modules['reportlab.graphics.widgets'] = MagicMock()
sys.modules['reportlab.graphics.widgets.markers'] = MagicMock()
sys.modules['reportlab.graphics.charts'] = MagicMock()
sys.modules['reportlab.graphics.charts.barcharts'] = MagicMock()
sys.modules['reportlab.graphics.charts.lineplots'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['tkinter'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['pytesseract'] = MagicMock()
sys.modules['mss'] = MagicMock()
sys.modules['kiroshi_chat'] = MagicMock()
sys.modules['kiroshi_local_ai'] = MagicMock()
sys.modules['kiroshi_cloud_sync'] = MagicMock()
sys.modules['kiroshi_video'] = MagicMock()
sys.modules['kiroshi_hotkeys'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['urllib3'] = MagicMock()
sys.modules['urllib3.exceptions'] = MagicMock()

import dataclasses
orig_asdict = dataclasses.asdict
def patched_asdict(obj, *args, **kwargs):
    if isinstance(obj, MagicMock):
        return {}
    return orig_asdict(obj, *args, **kwargs)
dataclasses.asdict = patched_asdict

json.dump = MagicMock()

import case_documentation_app

def _cluster_case_titles_optimized(titles):
    clusters = []
    assignments = []

    for title in titles:
        normalized = case_documentation_app._normalize_title_similarity(title)
        tokens = case_documentation_app._title_similarity_tokens(title)

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
        matcher = SequenceMatcher()
        matcher.set_seq2(normalized)

        for idx, cluster in enumerate(clusters):
            cluster_tokens = cluster.get("tokens") or set()
            cluster_norm = str(cluster.get("normalized") or "")
            score = _title_similarity_score(cluster_tokens, tokens, cluster_norm, normalized, matcher)

            if score > best_score:
                best_score = score
                best_index = idx
                if best_score > 0.99:
                    break

        threshold = 0.68 if tokens else 0.8
        if best_index == -1 or best_score < threshold:
            label_source = title if isinstance(title, str) and title.strip() else normalized
            label = (
                case_documentation_app._summarize_text(label_source, width=80)
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
                candidate_label = case_documentation_app._summarize_text(title, width=80)
                if len(candidate_label) > len(str(cluster.get("label") or "")):
                    cluster["label"] = candidate_label
            assignments.append(best_index)

    label_map = {idx: str(cluster.get("label") or "Caso sin título") for idx, cluster in enumerate(clusters)}
    return assignments, label_map

def generate_random_string(length=20):
    words = ['error', 'connection', 'timeout', 'scanner', 'failed', 'login', 'issue', 'reported']
    return ' '.join(random.choice(words) for _ in range(5)) + ' ' + ''.join(random.choice(string.ascii_lowercase) for _ in range(5))

random.seed(42)
titles = [generate_random_string() for _ in range(1000)]

start = time.perf_counter()
_cluster_case_titles_optimized(titles)
print(f"Time taken (Optimized): {time.perf_counter() - start:.4f} seconds")
