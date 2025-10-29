"""Entry point for the experimental desktop rebuild."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .core.ai_client import AIClient
from .core.storage import load_autosave
from .core.utils import setup_logging
from .ui import KiroshiMainWindow


def main() -> None:
    """Bootstrap the PySide6 application and show the main window."""

    setup_logging()
    app = QApplication(sys.argv)
    case = load_autosave()
    window = KiroshiMainWindow(case=case, ai_client=AIClient())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
