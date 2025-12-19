# Bolt's Journal

## 2025-12-16 - Streamlit File I/O Bottleneck
**Learning:** In Streamlit apps, the entire script re-runs on every interaction. Synchronous file I/O (like reading JSON configuration or history files) at the top level or in main rendering functions becomes a performance tax paid on every click.
**Action:** Use `@st.cache_data` for file readers, passing the file's `st_mtime` as an argument to automatically invalidate the cache only when the file actually changes.

## 2025-12-18 - Monolithic Streamlit Testability
**Learning:** Testing individual functions in a monolithic Streamlit script (`case_documentation_app.py`) is difficult because importing the module immediately executes the top-level UI rendering code, which requires a full Streamlit context.
**Action:** Encapsulate the main execution logic in a `main()` function and use `if __name__ == "__main__": main()` to allow the module to be imported by test suites without side effects.

## 2025-12-23 - Path.glob vs os.scandir for Directory Traversal
**Learning:** `Path.glob` combined with `stat()` calls in a loop creates a significant performance bottleneck (N*2 syscalls). For directories with thousands of files, this causes noticeable lag on every Streamlit rerun.
**Action:** Replace `Path.glob` with `os.scandir`, which yields `DirEntry` objects with cached stat information, reducing the syscall count to N. This improved traversal time by ~73% for 5000 files.
**Note:** `os.scandir` is case-sensitive on Windows unless handled carefully, unlike `glob` on Windows.
