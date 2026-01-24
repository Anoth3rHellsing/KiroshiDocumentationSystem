import sys
import time
import random
from types import ModuleType
from unittest.mock import MagicMock

# Mock dependencies to avoid import errors and side effects
mocks = [
    "streamlit", "streamlit.components.v1", "streamlit.errors",
    "pandas", "altair", "reportlab", "reportlab.lib", "reportlab.lib.pagesizes",
    "reportlab.lib.styles", "reportlab.lib.colors", "reportlab.platypus",
    "reportlab.graphics", "reportlab.graphics.shapes", "reportlab.graphics.widgets",
    "reportlab.graphics.widgets.markers",
    "reportlab.graphics.charts", "reportlab.graphics.charts.barcharts", "reportlab.graphics.charts.lineplots",
    "reportlab.pdfbase", "reportlab.pdfbase.pdfdoc",
    "requests", "urllib3",
    "pyautogui", "PIL", "mss", "pytesseract", "tkinter",
    "kiroshi_chat", "kiroshi_local_ai", "kiroshi_cloud_sync",
    "kiroshi_video", "kiroshi_hotkeys", "cryptography",
    "cryptography.hazmat", "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.hashes",
    "cryptography.hazmat.primitives.kdf",
    "cryptography.hazmat.primitives.kdf.pbkdf2"
]

for mock_name in mocks:
    sys.modules[mock_name] = MagicMock()

# Specifically mock st.cache_resource/data to return the function itself (identity decorator)
st_mock = sys.modules["streamlit"]

def cache_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return lambda func: func

st_mock.cache_resource = cache_mock
st_mock.cache_data = cache_mock

# Mock st.session_state as a dict that supports attribute access
class SessionState(dict):
    def __getattr__(self, item):
        if item in self:
            return self[item]
        # Return a MagicMock for unknown attributes to prevent AttributeErrors during top-level execution
        return MagicMock()
    def __setattr__(self, key, value):
        self[key] = value

st_mock.session_state = SessionState()

# Mock pandas series/dataframe behavior lightly if needed, but we probably just need imports to pass.
# The clustering function uses generic Sequence[str] input, but inside the file there are type hints using pandas.
# Since we only use the logic functions, it should be fine.

# Prepare execution context
module_name = "repro_clustering_perf_context"
app_globals = {
    "__file__": "case_documentation_app.py",
    "__name__": module_name # Avoid __main__ to prevent main() execution
}
# We need to ensure the module exists in sys.modules for dataclasses to work
sys.modules[module_name] = ModuleType(module_name)
app_globals.update(sys.modules) # Inject mocks

# Read and execute the file
with open("case_documentation_app.py", "r", encoding="utf-8") as f:
    source = f.read()

# We need to bypass the "if __name__ == '__main__': main()" block, but exec runs top level.
# The top level code sets up some constants.
# We'll just run it. The mocks should prevent UI rendering.
import traceback
try:
    exec(source, app_globals, app_globals)
except Exception as e:
    print(f"Warning during app execution (expected due to mocks): {e}")
    traceback.print_exc()

# Extract functions
_cluster_case_titles = app_globals.get("_cluster_case_titles")

if not _cluster_case_titles:
    print("Error: Could not find _cluster_case_titles in loaded globals")
    sys.exit(1)

# Generate synthetic data
print("Generating synthetic titles...")
# Larger vocabulary to simulate real world distribution better
words = []
for i in range(10000):
    words.append(f"word{i}")

titles = []
for _ in range(5000):
    # Pick 3-5 random words
    sample = random.sample(words, k=random.randint(3, 5))
    t = " ".join(sample)
    titles.append(t)

# Add some duplicates or near duplicates
titles.extend(titles[:100])
random.shuffle(titles)

print(f"Running clustering on {len(titles)} titles...")
start_time = time.time()
assignments, label_map = _cluster_case_titles(titles)
end_time = time.time()

duration = end_time - start_time
cluster_count = len(label_map)

print(f"Time taken: {duration:.4f} seconds")
print(f"Clusters created: {cluster_count}")

# Basic verification
if cluster_count == 0:
    print("Error: No clusters created!")
    sys.exit(1)

print("Baseline run complete.")
