import logging
from types import SimpleNamespace

import sys
import types

import pytest


class _DummyHotKeys:
    def __init__(self, mapping):
        self.mapping = mapping

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def join(self):
        return None


keyboard_stub = types.SimpleNamespace(GlobalHotKeys=lambda mapping: _DummyHotKeys(mapping))
sys.modules.setdefault("pynput", types.SimpleNamespace(keyboard=keyboard_stub))
sys.modules["pynput.keyboard"] = keyboard_stub

import kiroshi_hotkeys


@pytest.fixture(autouse=True)
def reset_hotkey_snapshot():
    kiroshi_hotkeys.update_hotkey_snapshot([], 0, {})
    yield
    kiroshi_hotkeys.update_hotkey_snapshot([], 0, {})


def test_copy_active_case_tables_logs_when_snapshot_empty(caplog):
    with caplog.at_level(logging.INFO):
        kiroshi_hotkeys.copy_active_case_tables()
    assert any(
        "hotkey snapshot is empty" in message for message in caplog.messages
    ), caplog.messages


def test_copy_active_case_tables_uses_snapshot(monkeypatch, caplog):
    captured_payloads: list[str] = []

    def fake_iter(case_obj, cat_map, categories=None):
        header = ", ".join(cat_map["HEADER"])
        return [f"{case_obj.value} | {header}"]

    monkeypatch.setattr(kiroshi_hotkeys, "_iter_category_tables", fake_iter)
    monkeypatch.setattr(kiroshi_hotkeys.pyperclip, "copy", captured_payloads.append)

    session = SimpleNamespace(case=SimpleNamespace(value="original"))
    category_map = {"HEADER": ["case_id"]}

    monotonic_values = iter(
        [
            0.0,
            kiroshi_hotkeys.STALE_SNAPSHOT_WARNING_SECONDS + 5.0,
        ]
    )
    monkeypatch.setattr(kiroshi_hotkeys.time, "monotonic", lambda: next(monotonic_values))

    kiroshi_hotkeys.update_hotkey_snapshot([session], 0, category_map)

    session.case.value = "mutated"
    category_map["HEADER"].append("extra")

    caplog.set_level(logging.INFO)
    kiroshi_hotkeys.copy_active_case_tables()

    assert captured_payloads == ["original | case_id"]
    assert any(
        "Hotkey snapshot data may be stale" in record.message for record in caplog.records
    )
    assert any(
        "Copied case tables to clipboard" in record.message for record in caplog.records
    )
