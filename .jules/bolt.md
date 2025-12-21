# Bolt's Journal

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
## 2025-05-15 - Incremental Resource Loading in Hot Loops
**Learning:** Functions like `_refresh_and_get_cases` are called frequently in Streamlit. Even with cached workers, unconditionally invoking helpers that perform file I/O (like `load_manual_docs`) adds overhead.
**Action:** Defer resource loading until *after* change detection confirms there is actual work to do. If the dataset hasn't changed (the common case), skip the setup entirely.
