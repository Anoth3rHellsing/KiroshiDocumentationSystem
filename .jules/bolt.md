## 2025-12-16 - Streamlit File I/O Bottleneck
**Learning:** In Streamlit apps, the entire script re-runs on every interaction. Synchronous file I/O (like reading JSON configuration or history files) at the top level or in main rendering functions becomes a performance tax paid on every click.
**Action:** Use `@st.cache_data` for file readers, passing the file's `st_mtime` as an argument to automatically invalidate the cache only when the file actually changes.

## 2025-12-18 - Monolithic Streamlit Testability
**Learning:** Testing individual functions in a monolithic Streamlit script (`case_documentation_app.py`) is difficult because importing the module immediately executes the top-level UI rendering code, which requires a full Streamlit context.
**Action:** Encapsulate the main execution logic in a `main()` function and use `if __name__ == "__main__": main()` to allow the module to be imported by test suites without side effects.
## 2025-12-23 - Thread-Safe Incremental Caching in Streamlit
**Learning:** Using `@st.cache_data` for large lists of files (like a database directory) is inefficient because the cache invalidates completely if *any* single file changes, triggering a full O(N) re-parse.
**Action:** Implement a custom incremental cache using `@st.cache_resource` with a thread-safe dictionary (protected by a lock). This allows updating only the changed entries while serving the rest from memory, transforming O(N) parsing into O(K) where K is the number of changed files.
## 2025-12-19 - Optimization of Autosave Scanning
**Learning:** File system operations like `path.glob` combined with `path.stat()` in a loop can be significantly slower than `os.scandir` which yields `DirEntry` objects with cached stat information, especially on Windows or when dealing with many files.
**Action:** Replaced `path.glob` with `os.scandir` in `_iter_case_autosaves` to improve performance of autosave resolution and cleanup. Benchmarking showed ~1.25x speedup in a synthetic test with 2000 files.

## 2025-05-21 - Optimization of Recent Cases Update
**Learning:** Redundant file reads during save/load operations can be eliminated by passing available in-memory data to utility functions.
**Action:** Optimized `update_recent_cases` to accept an optional `case_data` argument, removing an O(1) file read/parse on every case save and load operation.

## 2026-01-25 - Optimization of Case Title Clustering
**Learning:** Text clustering with `SequenceMatcher` is O(N*M). For large datasets, an Inverted Index mapping tokens to candidates reduces comparisons to O(N*k) (where k << M), yielding ~15% speedup on 3000 items with deterministic results.
**Action:** Implemented `token_index` in `_cluster_case_titles` to limit similarity checks to relevant candidates.

## 2026-01-25 - Benchmarking Monolithic Streamlit Apps
**Learning:** Importing a Streamlit app script (`case_documentation_app.py`) for benchmarking triggers top-level execution logic (like tutorial rendering and settings persistence). This requires extensive mocking of `streamlit`, `sys.modules`, and `st.session_state` (populated with safe defaults) to prevent side effects or crashes during import.
**Action:** Created `tests/repro_clustering_perf.py` which mocks `streamlit` components and `session_state` before importing the app module to benchmark specific functions in isolation.
