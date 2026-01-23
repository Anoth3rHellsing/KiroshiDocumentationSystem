
import time
import re
import random
import string
from difflib import SequenceMatcher
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Sequence

# --- Copied Constants and Functions ---

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
    return text[:width]

# --- Original Implementation ---

def _cluster_case_titles_original(titles: Sequence[str]) -> tuple[list[int], dict[int, str]]:
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

# --- Optimized Implementation ---

def _cluster_case_titles_optimized(titles: Sequence[str]) -> tuple[list[int], dict[int, str]]:
    clusters: list[dict[str, object]] = []
    assignments: list[int] = []

    token_index = defaultdict(set)
    empty_token_clusters = set()

    for title in titles:
        normalized = _normalize_title_similarity(title)
        tokens = _title_similarity_tokens(title)

        if not normalized and not tokens:
            blank_index = -1
            for idx in sorted(empty_token_clusters): # Sorted for deterministic behavior
                if not clusters[idx].get("normalized"):
                    blank_index = idx
                    break

            if blank_index == -1:
                clusters.append(
                    {
                        "normalized": "",
                        "tokens": set(),
                        "label": "Caso sin título",
                    }
                )
                blank_index = len(clusters) - 1
                empty_token_clusters.add(blank_index)

            assignments.append(blank_index)
            continue

        candidates = set()
        for token in tokens:
            if token in token_index:
                candidates.update(token_index[token])

        candidates.update(empty_token_clusters)

        if not tokens and not candidates:
             # Fallback if no tokens and no empty clusters (unlikely given logic above)
             pass

        # Optimization: if no tokens, we must check everything?
        # But if no tokens AND no normalized, we handled it.
        # If no tokens but has normalized (e.g. only stopwords), _title_similarity_tokens returns empty.
        # In that case, we can't use token index. We must check all clusters?
        # Or maybe clusters with normalized text?
        # For now, let's assume if tokens is empty, we check all.

        candidate_list = sorted(candidates) if tokens else range(len(clusters))

        best_index = -1
        best_score = 0.0

        for idx in candidate_list:
            cluster = clusters[idx]
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
            new_cluster_idx = len(clusters)
            clusters.append(
                {
                    "normalized": normalized,
                    "tokens": set(tokens),
                    "label": label,
                }
            )
            assignments.append(new_cluster_idx)

            if tokens:
                for t in tokens:
                    token_index[t].add(new_cluster_idx)
            else:
                empty_token_clusters.add(new_cluster_idx)

        else:
            cluster = clusters[best_index]
            cluster_tokens = cluster.setdefault("tokens", set())

            new_tokens = set(tokens) - cluster_tokens

            cluster_tokens.update(tokens)
            cluster["normalized"] = cluster.get("normalized") or normalized
            if isinstance(title, str) and title.strip():
                candidate_label = _summarize_text(title, width=80)
                if len(candidate_label) > len(str(cluster.get("label") or "")):
                    cluster["label"] = candidate_label
            assignments.append(best_index)

            for t in new_tokens:
                token_index[t].add(best_index)

            if cluster_tokens and best_index in empty_token_clusters:
                empty_token_clusters.remove(best_index)

    label_map = {idx: str(cluster.get("label") or "Caso sin título") for idx, cluster in enumerate(clusters)}
    return assignments, label_map

# --- Benchmark ---

def generate_titles(count=2000):
    # More realistic vocabulary size
    words = [f"word{i}" for i in range(5000)]
    common_words = ["error", "failure", "connection", "login", "slow", "crash"]

    titles = []
    for _ in range(count):
        if random.random() < 0.5:
            # Construct titles that are likely to cluster
            base = random.choice(common_words)
            suffix = random.choice(words)
            title = f"{base} {suffix} issue"
        else:
            # Random titles
            title = " ".join(random.choices(words, k=3))
        titles.append(title)
    return titles

def run_benchmark():
    titles = generate_titles(5000)
    print(f"Benchmarking with {len(titles)} titles...")

    start = time.time()
    res_orig, map_orig = _cluster_case_titles_original(titles)
    end = time.time()
    time_orig = end - start
    print(f"Original: {time_orig:.4f}s")

    start = time.time()
    res_opt, map_opt = _cluster_case_titles_optimized(titles)
    end = time.time()
    time_opt = end - start
    print(f"Optimized: {time_opt:.4f}s")

    if time_opt > 0:
        print(f"Speedup: {time_orig / time_opt:.2f}x")

    print(f"Clusters Original: {len(map_orig)}")
    print(f"Clusters Optimized: {len(map_opt)}")

    # Validation
    # We check if cluster assignment counts match roughly
    c_orig = Counter(res_orig)
    c_opt = Counter(res_opt)

    # We can't compare indices directly because greedy order might shift
    # but the distribution of cluster sizes should be similar
    sizes_orig = sorted(c_orig.values())
    sizes_opt = sorted(c_opt.values())

    print(f"Top 5 cluster sizes (Orig): {sizes_orig[-5:]}")
    print(f"Top 5 cluster sizes (Opt):  {sizes_opt[-5:]}")

if __name__ == "__main__":
    run_benchmark()
