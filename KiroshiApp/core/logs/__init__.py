"""Log utilities for the desktop prototype."""
from .helpers import LogSnapshot, load_recent_logs, resolve_log_file_path, tail_log_file

__all__ = [
    "LogSnapshot",
    "load_recent_logs",
    "resolve_log_file_path",
    "tail_log_file",
]
