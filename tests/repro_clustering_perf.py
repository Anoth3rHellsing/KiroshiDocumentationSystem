
import sys
import time
import random
import string
import dataclasses
from collections import defaultdict
from unittest.mock import MagicMock

# Monkeypatch asdict to handle MagicMocks and avoiding deepcopy issues
original_asdict = dataclasses.asdict
def mock_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    if not dataclasses.is_dataclass(obj):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = mock_asdict

# Mock dependencies to allow importing case_documentation_app
streamlit_mock = MagicMock()
sys.modules["streamlit"] = streamlit_mock
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()

# Setup common st functions
streamlit_mock.cache_resource = lambda func=None, **kwargs: (lambda f: f) if func is None else func
streamlit_mock.cache_data = lambda func=None, **kwargs: (lambda f: f) if func is None else func

sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()

# Mock st.session_state
mock_session_state = MagicMock()
mock_session_state.get.return_value = False
mock_session_state.__getitem__.side_effect = lambda key: False if key == "show_tutorial" else MagicMock()
streamlit_mock.session_state = mock_session_state
mock_session_state.case = MagicMock()
mock_session_state.get.side_effect = lambda k, d=None: MagicMock() if k == "case" else d

# Now import the app
import case_documentation_app as app

# Reference implementation (slow)
def _cluster_case_titles_slow(titles):
    clusters = []
    assignments = []

    for title in titles:
        normalized = app._normalize_title_similarity(title)
        tokens = app._title_similarity_tokens(title)

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
            score = app._title_similarity_score(tokens, cluster_tokens, normalized, cluster_norm)
            if score > best_score:
                best_score = score
                best_index = idx

        threshold = 0.68 if tokens else 0.8
        if best_index == -1 or best_score < threshold:
            label_source = title if isinstance(title, str) and title.strip() else normalized
            label = (
                app._summarize_text(label_source, width=80)
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
                candidate_label = app._summarize_text(title, width=80)
                if len(candidate_label) > len(str(cluster.get("label") or "")):
                    cluster["label"] = candidate_label
            assignments.append(best_index)

    label_map = {idx: str(cluster.get("label") or "Caso sin título") for idx, cluster in enumerate(clusters)}
    return assignments, label_map, len(clusters)

def generate_titles(count: int) -> list[str]:
    titles = []
    # Larger vocabulary for realistic testing
    vocab = [
        "error", "fail", "network", "connection", "printer", "login", "password", "reset", "wifi", "slow",
        "down", "crash", "screen", "blue", "update", "windows", "email", "outlook", "teams", "vpn",
        "mouse", "keyboard", "monitor", "cable", "power", "battery", "laptop", "server", "cloud", "aws",
        "azure", "database", "sql", "query", "access", "denied", "permission", "user", "account", "locked",
        "excel", "word", "powerpoint", "office", "adobe", "photoshop", "license", "key", "expire", "renew",
        "phone", "call", "voip", "headset", "audio", "video", "camera", "zoom", "meet", "chat",
        "slack", "discord", "file", "folder", "share", "drive", "onedrive", "dropbox", "upload", "download",
        "speed", "latency", "ping", "dns", "dhcp", "ip", "address", "subnet", "gateway", "router",
        "switch", "firewall", "security", "virus", "malware", "scan", "quarantine", "phishing", "spam", "block",
        "browser", "chrome", "firefox", "edge", "safari", "cache", "cookie", "history", "bookmark", "extension",
        "print", "spooler", "jam", "toner", "ink", "paper", "tray", "driver", "install", "uninstall"
    ]
    # Add random words to ensure even more diversity
    for _ in range(500):
        vocab.append(''.join(random.choices(string.ascii_lowercase, k=5)))

    for _ in range(count):
        length = random.randint(2, 5)
        title = " ".join(random.choices(vocab, k=length))
        titles.append(title)
    return titles

def inspect_clusters(titles):
    print("Inspecting tokens for first 10 titles:")
    for t in titles[:10]:
        tokens = app._title_similarity_tokens(t)
        print(f"Title: '{t}' -> Tokens: {tokens}")

def run_benchmark():
    print("Benchmarking _cluster_case_titles...")

    # Use deterministic titles for correctness check
    random.seed(42)
    titles_small = generate_titles(100)
    titles_large = generate_titles(2000)

    inspect_clusters(titles_large)

    # 1. Measure Slow Implementation (Baseline)
    print("Running slow implementation on 100 titles...")
    start_time = time.time()
    assignments_slow, _, num_clusters_slow = _cluster_case_titles_slow(titles_small)
    duration_slow = time.time() - start_time
    print(f"Slow: Clustering 100 titles took {duration_slow:.4f} seconds. Clusters: {num_clusters_slow}")

    # 1b. Measure Slow Implementation on Large Dataset
    duration_slow_large = 0
    if duration_slow < 0.5:
        print("Running slow implementation on 2000 titles...")
        start_time = time.time()
        _, _, num_clusters_slow_large = _cluster_case_titles_slow(titles_large)
        duration_slow_large = time.time() - start_time
        print(f"Slow: Clustering 2000 titles took {duration_slow_large:.4f} seconds. Clusters: {num_clusters_slow_large}")

    # 2. Measure Optimized Implementation
    print("Running optimized implementation on 100 titles...")
    start_time = time.time()
    assignments_opt, label_map = app._cluster_case_titles(titles_small)
    duration_opt = time.time() - start_time
    print(f"Opt: Clustering 100 titles took {duration_opt:.4f} seconds. Clusters: {len(label_map)}")

    # 3. Verify Correctness
    if assignments_slow == assignments_opt:
        print("✅ Correctness check PASSED (small dataset)")
    else:
        print("❌ Correctness check FAILED (small dataset)")
        print(f"Assignments differ: {assignments_slow[:10]} vs {assignments_opt[:10]}")

    # 4. Measure Large Dataset (Optimized only)
    print("Running optimized implementation on 2000 titles...")
    start_time = time.time()
    _, label_map_large = app._cluster_case_titles(titles_large)
    duration_large = time.time() - start_time
    print(f"Opt: Clustering 2000 titles took {duration_large:.4f} seconds. Clusters: {len(label_map_large)}")

    if duration_slow_large > 0:
        speedup = duration_slow_large / duration_large
        print(f"Speedup: {speedup:.2f}x")

if __name__ == "__main__":
    run_benchmark()
