
import time
import random
import string
import sys
import json
import dataclasses
from unittest.mock import MagicMock

# Mock dependencies before import
mock_st = MagicMock()
# Mock st.cache_data as a pass-through decorator that handles both @st.cache_data and @st.cache_data(...)
def cache_data_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    def decorator(func):
        return func
    return decorator
mock_st.cache_data = cache_data_mock

def cache_resource_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    def decorator(func):
        return func
    return decorator
mock_st.cache_resource = cache_resource_mock

sys.modules["streamlit"] = mock_st
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["reportlab.pdfbase"] = MagicMock()
sys.modules["reportlab.rl_config"] = MagicMock()
sys.modules["altair"] = MagicMock()
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
sys.modules["pandas"] = MagicMock()

# Patch json.dump to avoid serialization errors during import
original_json_dump = json.dump
def mock_json_dump(obj, fp, **kwargs):
    try:
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass # Ignore serialization errors of MagicMocks
json.dump = mock_json_dump

# Patch dataclasses.asdict
original_asdict = dataclasses.asdict
def mock_asdict(obj, **kwargs):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, **kwargs)
dataclasses.asdict = mock_asdict

# Now import the app
import case_documentation_app

def generate_titles(n=1000):
    # Use words that are NOT in _GENERIC_STOPWORDS
    # _GENERIC_STOPWORDS has: error, issue, failed, problem, unable, cannot, customer, report, see, observed, during, while, into, after, before, still, does, doesnt, cant, wont, need, needs, should, could, would, please, help, team, agent, support, client, system, service, application, apps, app, server, environment, production, prod, dev, test, staging, login, log, logs, message, messages, details, detail, null, none, na, unknown, new, open, closed

    words = ["printer", "scanner", "wifi", "bluetooth", "network", "firewall", "vpn", "disk", "cpu", "ram", "memory", "screen", "monitor", "keyboard", "mouse", "audio", "video", "camera", "microphone", "speaker", "headset", "driver", "bios", "firmware", "windows", "linux", "macos", "android", "ios", "chrome", "firefox", "edge", "safari", "outlook", "teams", "slack", "zoom", "excel", "word", "powerpoint", "adobe", "photoshop", "illustrator", "premiere", "blender", "unity", "unreal", "godot", "python", "java", "cpp", "javascript", "html", "css", "sql", "docker", "kubernetes", "aws", "azure", "gcp", "git", "github", "gitlab", "bitbucket", "jira", "confluence", "trello", "notion"]

    titles = []
    for _ in range(n):
        length = random.randint(2, 5)
        title = " ".join(random.choices(words, k=length))
        titles.append(title)
    return titles

def run_benchmark():
    # Use a fixed seed for reproducibility
    random.seed(42)
    # Reduce size to 2000 to be safe, if optimization works it should be fast.
    # 5000 timed out (400s+), so unoptimized 2000 would be ~64s (quadratic).
    # Optimized should be linear-ish or O(N * small_K).
    titles = generate_titles(5000)

    print(f"Benchmarking clustering with {len(titles)} titles...")
    start_time = time.time()
    assignments, label_map = case_documentation_app._cluster_case_titles(titles)
    end_time = time.time()

    duration = end_time - start_time
    print(f"Clustering took {duration:.4f} seconds")
    print(f"Number of clusters: {len(label_map)}")
    return duration

if __name__ == "__main__":
    run_benchmark()
