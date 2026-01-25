
import time
import re
import sys
import types
from functools import lru_cache
from difflib import SequenceMatcher
from collections import defaultdict
import random
import string
from unittest.mock import MagicMock

# --- Mocking Streamlit and dependencies ---
st_mock = MagicMock()

# Custom session state to handle dictionary access and attributes
class MockSessionState(dict):
    def __getattr__(self, key):
        return self.get(key, MagicMock())  # Default to MagicMock if missing, but be careful with serialization
    def __setattr__(self, key, value):
        self[key] = value

# Pre-populate with serializable values to avoid JSON errors
session_state_data = MockSessionState({
    "show_tutorial": False,
    "tutorial_completed": True,
    "tutorial_metadata": {"completed": True},
    "theme_preview": "auto",
    "dark_mode_enabled": False,
    "enable_holiday_theme": False,
    "second_line_mode": False,
    "debug_mode": False,
    "frutiger_aero_mode": False,
    "case_compact_mode": False,
    "show_kiroshi_chat": True,
    "autosave_to_database": False,
    "ai_assist_mode": "Standard",
    "ai_educate_enabled": False,
    "ai_educate_report_enabled": False,
    "ai_educate_advanced": False,
    "agent_first_name": "",
    "agent_last_name": "",
    "attachments_directory": "/tmp",
    "wellness_reminders": {},
    "kiroshi_sarcasm_mode": False,
    "ai_mode": "Cloud",
    "openai_api_key": "",
    "ai_base_url": "",
    "openai_model": "gpt-5-nano",
    "local_ai_profile": "speed",
})
st_mock.session_state = session_state_data

def cache_decorator(*args, **kwargs):
    def wrapper(func):
        return func
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return wrapper

st_mock.cache_data = cache_decorator
st_mock.cache_resource = cache_decorator
sys.modules["streamlit"] = st_mock
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()

# Ensure we can import case_documentation_app
sys.path.append(".")
import case_documentation_app

# --- Copied Baseline (Original Implementation) ---

_CASE_REFERENCE_PATTERN = re.compile(
    r"\b(?:case|caso|ticket|inc(?:ident)?|sr|cs|bug|pr|issue)[-_\s]*\d+\b",
    re.IGNORECASE,
)
_SERIAL_PATTERN = re.compile(r"\b[A-Z]{2,}\d{3,}\b")
_URL_PATTERN = re.compile(r"https?://\S+")
_NON_ALPHANUMERIC_PATTERN = re.compile(r"[^0-9A-Za-z]+")
_LOWER_ALPHANUM_PATTERN = re.compile(r"[^0-9a-z]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")

_GENERIC_STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "this", "have", "error", "issue", "case",
    "user", "when", "failed", "failure", "problem", "unable", "cannot", "customer", "reported",
    "report", "see", "observed", "during", "while", "into", "after", "before", "still", "does",
    "doesnt", "cant", "wont", "need", "needs", "should", "could", "would", "please", "help",
    "team", "agent", "support", "customer", "client", "system", "service", "application", "apps",
    "app", "server", "environment", "production", "prod", "dev", "test", "staging", "login",
    "log", "logs", "message", "messages", "details", "detail", "null", "none", "na", "unknown",
    "new", "open", "closed",
}

TITLE_SIMILARITY_STOPWORDS = {
    "issue", "issues", "problem", "problems", "error", "errors", "case", "cases",
    "support", "please", "help", "need",
}

@lru_cache(maxsize=1024)
def _tokenize_issue_description(text: str) -> tuple[str, ...]:
    cleaned = _CASE_REFERENCE_PATTERN.sub(" ", text)
    cleaned = _SERIAL_PATTERN.sub(" ", cleaned)
    cleaned = _URL_PATTERN.sub(" ", cleaned)
    cleaned = _NON_ALPHANUMERIC_PATTERN.sub(" ", cleaned)
    tokens = [token.lower() for token in cleaned.split() if len(token) >= 3]
    return tuple(token for token in tokens if token not in _GENERIC_STOPWORDS and not token.isdigit())

@lru_cache(maxsize=1024)
def _cached_normalize_title(value: str) -> str:
    lowered = value.lower()
    cleaned = _LOWER_ALPHANUM_PATTERN.sub(" ", lowered)
    return _WHITESPACE_PATTERN.sub(" ", cleaned).strip()

def _normalize_title_similarity(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return _cached_normalize_title(value)

def _title_similarity_tokens(title: object) -> set[str]:
    if not isinstance(title, str):
        return set()
    return {
        token
        for token in _tokenize_issue_description(title)
        if token not in TITLE_SIMILARITY_STOPWORDS
    }

def _title_similarity_score(
    tokens_a: set[str], tokens_b: set[str], norm_a: str, norm_b: str
) -> float:
    if tokens_a and tokens_b and tokens_a.isdisjoint(tokens_b):
        return 0.0

    base = SequenceMatcher(None, norm_a, norm_b).ratio() if (norm_a or norm_b) else 0.0
    if tokens_a and tokens_b:
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        jaccard = (intersection / union) if union else 0.0
        return 0.6 * base + 0.4 * jaccard
    return base

def _summarize_text(text: str, width: int = 200) -> str:
    if len(text) <= width:
        return text
    return text[:width] + "..."

def _cluster_case_titles_original(titles: list[str]) -> tuple[list[int], dict[int, str]]:
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

def generate_synthetic_titles(n=1000):
    # Larger vocabulary
    words = list(string.ascii_lowercase) + ["error", "fail", "broken", "slow", "down", "up", "login", "logout"]
    for i in range(500):
        words.append("".join(random.choices(string.ascii_lowercase, k=5)))

    titles = []
    for _ in range(n):
        # 3 to 6 words
        k = random.randint(3, 6)
        title = " ".join(random.choices(words, k=k))
        titles.append(title)
    return titles

if __name__ == "__main__":
    titles = generate_synthetic_titles(3000)
    print(f"Generated {len(titles)} titles.")

    print("Running original (local)...")
    start = time.time()
    res_orig = _cluster_case_titles_original(titles)
    end = time.time()
    print(f"Original took {end - start:.4f}s")

    print("Running optimized (from app)...")
    start = time.time()
    res_opt = case_documentation_app._cluster_case_titles(titles)
    end = time.time()
    print(f"Optimized took {end - start:.4f}s")

    # Verify results match
    if res_orig[0] == res_opt[0]:
        print("Assignments match exactly!")
    else:
        print("Assignments differ!")
        diffs = 0
        for i, (a, b) in enumerate(zip(res_orig[0], res_opt[0])):
            if a != b:
                diffs += 1
        print(f"Differences: {diffs}/{len(titles)}")

        # Check label map size
        print(f"Clusters orig: {len(res_orig[1])}, Clusters opt: {len(res_opt[1])}")
