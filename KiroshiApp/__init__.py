"""Compatibility helpers for the experimental Qt front-end."""

from __future__ import annotations

from typing import Any

__all__ = ["ensure_single_selection_alias"]


def ensure_single_selection_alias(qtwidgets: Any) -> None:
    """Ensure ``QListWidget.SingleSelection`` exists on Qt6 builds.

    Qt 6 reorganised enum values under the ``SelectionMode`` namespace and the
    former Qt 5 style attribute ``QListWidget.SingleSelection`` is no longer
    automatically defined.  The legacy access pattern is still used in the
    experimental desktop UI which means the application crashes at startup on
    PySide6.  This helper restores the attribute so existing code keeps
    working without touching the UI layer.
    """

    if not hasattr(qtwidgets, "QListWidget") or not hasattr(qtwidgets, "QAbstractItemView"):
        return

    list_widget = qtwidgets.QListWidget
    if hasattr(list_widget, "SingleSelection"):
        return

    selection_mode = getattr(qtwidgets.QAbstractItemView, "SelectionMode", qtwidgets.QAbstractItemView)
    value = getattr(selection_mode, "SingleSelection", None)
    if value is None:
        value = getattr(qtwidgets.QAbstractItemView, "SingleSelection", None)
    if value is None:
        return

    setattr(list_widget, "SingleSelection", value)


try:  # pragma: no cover - executed only when PySide6 is installed
    from PySide6 import QtWidgets  # type: ignore
except Exception:  # pragma: no cover - PySide6 not available during tests
    QtWidgets = None  # type: ignore[assignment]
else:  # pragma: no cover - executed only in environments with PySide6
    ensure_single_selection_alias(QtWidgets)
