"""Tests for Qt compatibility helpers."""

from types import SimpleNamespace

import KiroshiApp


def build_fake_qt(single_selection_missing: bool = True):
    value = object()

    class FakeSelectionMode:
        SingleSelection = value

    attributes = {
        "SelectionMode": FakeSelectionMode,
        "SingleSelection": value,
    }

    qabstract_item_view = SimpleNamespace(**attributes)
    qlist_widget_dict = {} if single_selection_missing else {"SingleSelection": value}
    qlist_widget = SimpleNamespace(**qlist_widget_dict)

    return SimpleNamespace(QAbstractItemView=qabstract_item_view, QListWidget=qlist_widget), value


def test_ensure_single_selection_alias_adds_attribute_when_missing():
    qtwidgets, expected = build_fake_qt(single_selection_missing=True)

    KiroshiApp.ensure_single_selection_alias(qtwidgets)

    assert getattr(qtwidgets.QListWidget, "SingleSelection") is expected


def test_ensure_single_selection_alias_noop_when_attribute_present():
    qtwidgets, expected = build_fake_qt(single_selection_missing=False)

    KiroshiApp.ensure_single_selection_alias(qtwidgets)

    assert getattr(qtwidgets.QListWidget, "SingleSelection") is expected
