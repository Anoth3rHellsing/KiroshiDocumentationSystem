"""Kiroshi desktop client package.

This namespace exposes the PySide6 entry point and the main window used by
our desktop parity effort so callers can launch the UI with
``python -m KiroshiApp.main`` or by importing :class:`~KiroshiApp.ui.main_window.KiroshiMainWindow`.
"""

from .main import main  # re-export for convenience
from .ui.main_window import KiroshiMainWindow, MainWindow

__all__ = ["main", "KiroshiMainWindow", "MainWindow"]
