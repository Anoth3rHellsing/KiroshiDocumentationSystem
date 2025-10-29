"""UI package for the experimental desktop prototype."""
from .main_window import MainWindow
from .case_tab import CaseTab
from .email_tab import EmailTab
from .tables_tab import TablesTab
from .save_load_tab import SaveLoadTab
from .tracking_tab import TrackingTab
from .settings_tab import SettingsTab
from .debug_tab import DebugTab

__all__ = [
    "MainWindow",
    "CaseTab",
    "EmailTab",
    "TablesTab",
    "SaveLoadTab",
    "TrackingTab",
    "SettingsTab",
    "DebugTab",
]
