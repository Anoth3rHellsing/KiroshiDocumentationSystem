## 2024-05-15 - Streamlit I/O Bottlenecks
**Learning:** Synchronous file I/O (like `json.load`) in the main render loop kills responsiveness.
**Action:** Move all I/O to functions decorated with `@st.cache_data`.

## 2024-05-16 - Monolithic Streamlit Testability
**Learning:** Importing `case_documentation_app.py` runs the entire app script, making unit testing individual functions impossible without heavy mocking of `streamlit`.
**Action:** Extract logic to pure Python modules or wrap top-level code in `if __name__ == "__main__":` blocks where possible.

## 2024-05-18 - Incremental Caching Strategy
**Learning:** `st.cache_data` is powerful but invalidating complex objects is hard.
**Action:** Use `_worker(mtime)` pattern where the cache key is just a timestamp or signature, forcing a refresh only when necessary.

## 2024-05-19 - Autosave Scanning Optimization
**Learning:** Autosave logic scanning all session files (O(N)) on every keystroke causes typing lag.
**Action:** Use a dictionary of hashes to track changes in memory before touching disk.

## 2024-05-20 - Recent Cases Update Optimization
**Learning:** Updating the "Recent Cases" list on every interaction is unnecessary and slow.
**Action:** Cache the recent cases list and only invalidate it when a file save operation occurs.

## 2025-05-21 - Streamlit Disk I/O Debouncing
**Learning:** Functions scanning directories (like `_saved_case_files_signature`) run on the main thread during every rerender. For large directories, this causes UI lag.
**Action:** Always decorate directory scanners with `@st.cache_data(ttl=...)` (e.g., 2s) to debounce these operations.
