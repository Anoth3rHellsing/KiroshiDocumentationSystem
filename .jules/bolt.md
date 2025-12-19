# Bolt's Journal

## 2025-12-16 - Streamlit File I/O Bottleneck
**Learning:** In Streamlit apps, the entire script re-runs on every interaction. Synchronous file I/O (like reading JSON configuration or history files) at the top level or in main rendering functions becomes a performance tax paid on every click.
**Action:** Use `@st.cache_data` for file readers, passing the file's `st_mtime` as an argument to automatically invalidate the cache only when the file actually changes.

## 2025-12-18 - Monolithic Streamlit Testability
**Learning:** Testing individual functions in a monolithic Streamlit script (`case_documentation_app.py`) is difficult because importing the module immediately executes the top-level UI rendering code, which requires a full Streamlit context.
**Action:** Encapsulate the main execution logic in a `main()` function and use `if __name__ == "__main__": main()` to allow the module to be imported by test suites without side effects.

## 2025-12-19 - Efficient Directory Scanning on Windows
**Learning:** Using `Path.glob` combined with `path.stat().st_mtime` in a loop creates significant overhead due to repeated system calls and object instantiation, especially on Windows. `os.scandir` provides a much faster alternative by retrieving directory entries and their attributes in a single pass.
**Action:** Replace `Path.glob` iterations with `os.scandir` when filtering files and accessing their metadata (like modification time) for caching purposes.
