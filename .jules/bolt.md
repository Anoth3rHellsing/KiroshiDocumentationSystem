# Bolt's Journal

## 2025-12-16 - Streamlit File I/O Bottleneck
**Learning:** In Streamlit apps, the entire script re-runs on every interaction. Synchronous file I/O (like reading JSON configuration or history files) at the top level or in main rendering functions becomes a performance tax paid on every click.
**Action:** Use `@st.cache_data` for file readers, passing the file's `st_mtime` as an argument to automatically invalidate the cache only when the file actually changes.
