"""PySide6 UI components for the experimental desktop client."""

from .main_window import KiroshiMainWindow
from .case_tab import CaseTab
from .email_tab import EmailTab
from .save_load_tab import SaveLoadTab
from .tracking_tab import TrackingTab
from .settings_tab import SettingsTab
from .debug_tab import DebugTab

__all__ = [
    "KiroshiMainWindow",
    "CaseTab",
    "EmailTab",
    "SaveLoadTab",
    "TrackingTab",
    "SettingsTab",
    "DebugTab",
]
