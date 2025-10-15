import builtins
import logging
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import case_documentation_app as app


@pytest.fixture
def attachments_root(monkeypatch, tmp_path):
    root = tmp_path / "attachments-root"
    root.mkdir()

    def fake_ensure():
        return root, None

    monkeypatch.setattr(app, "CASE_ATTACHMENTS_ROOT", root)
    monkeypatch.setattr(app, "_ensure_case_attachments_root", fake_ensure)
    monkeypatch.setitem(
        app._persistent_settings_cache, "attachments_directory", str(root)
    )
    return root


@pytest.fixture
def session_state(monkeypatch):
    state: dict[str, object] = {}
    monkeypatch.setattr(app.st, "session_state", state, raising=False)
    return state


def test_persist_case_attachments_writes_files_and_skips_duplicates(
    attachments_root, session_state
):
    uploads = [
        app.InMemoryUploadedFile("report.txt", b"primary"),
        app.InMemoryUploadedFile("report.txt", b"duplicate"),
    ]
    log_uploads = [app.InMemoryUploadedFile("logs.log", b"log-bytes")]
    screenshots = [app.InMemoryUploadedFile("screen.png", b"png-bytes")]
    session_state.update(
        {
            "uploads": uploads,
            "log_uploads": log_uploads,
            "screenshots": screenshots,
        }
    )

    metadata = app.persist_case_attachments("Case-42")

    case_dir = attachments_root / app.sanitize_case_id("Case-42")
    assert (case_dir / "uploads" / "report.txt").read_bytes() == b"duplicate"
    assert (case_dir / "logs" / "logs.log").read_bytes() == b"log-bytes"
    assert (case_dir / "screenshots" / "screen.png").read_bytes() == b"png-bytes"

    upload_entries = metadata["uploads"]
    assert len(upload_entries) == 1
    assert upload_entries[0]["name"] == "report.txt"
    assert upload_entries[0]["path"] == "uploads/report.txt"
    assert not Path(upload_entries[0]["path"]).is_absolute()

    log_entries = metadata["log_uploads"]
    assert len(log_entries) == 1
    assert log_entries[0]["path"] == "logs/logs.log"

    screenshot_entries = metadata["screenshots"]
    assert len(screenshot_entries) == 1
    assert screenshot_entries[0]["path"] == "screenshots/screen.png"


def test_persist_case_attachments_handles_read_and_write_failures(
    attachments_root, session_state, caplog, monkeypatch
):
    good_upload = app.InMemoryUploadedFile("ok.txt", b"ok")
    unreadable = app.InMemoryUploadedFile("broken.txt", b"ignore")
    unwritable = app.InMemoryUploadedFile("nope.txt", b"deny")

    def broken_getvalue():
        raise OSError("boom")

    monkeypatch.setattr(unreadable, "getvalue", broken_getvalue)

    real_open = builtins.open

    def fake_open(path, mode="r", *args, **kwargs):
        if "nope.txt" in str(path) and "w" in mode:
            raise OSError("disk full")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)

    session_state.update(
        {
            "uploads": [good_upload, unreadable, unwritable],
            "log_uploads": [],
            "screenshots": [],
        }
    )

    with caplog.at_level(logging.WARNING):
        metadata = app.persist_case_attachments("Case-Error")

    upload_entries = metadata["uploads"]
    assert len(upload_entries) == 1
    assert upload_entries[0]["name"] == "ok.txt"

    messages = [record.message for record in caplog.records]
    assert any("Failed to read attachment" in message for message in messages)
    assert any("Failed to write attachment" in message for message in messages)


def test_load_case_attachments_reconstructs_files(attachments_root):
    case_id = "Case-55"
    case_dir = attachments_root / app.sanitize_case_id(case_id)
    (case_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (case_dir / "logs").mkdir(parents=True, exist_ok=True)
    (case_dir / "screenshots").mkdir(parents=True, exist_ok=True)

    (case_dir / "uploads" / "keep.txt").write_bytes(b"keep")
    (case_dir / "logs" / "diag.log").write_bytes(b"log")
    (case_dir / "screenshots" / "shot.png").write_bytes(b"img1")
    (case_dir / "screenshots" / "fallback.png").write_bytes(b"img2")

    metadata = {
        "uploads": [
            {"name": "keep.txt", "path": "uploads/keep.txt"},
            {"name": "ghost.txt", "path": "uploads/ghost.txt"},
        ],
        "log_uploads": [
            {"name": "diag.log", "path": "logs/diag.log"},
        ],
        "screenshots": [
            {"name": "shot.png", "path": "screenshots/shot.png"},
            {"name": "fallback.png"},
        ],
    }

    uploads, logs, screenshots = app.load_case_attachments(case_id, metadata)

    assert len(uploads) == 1
    assert isinstance(uploads[0], app.InMemoryUploadedFile)
    assert uploads[0].name == "keep.txt"
    assert uploads[0].data == b"keep"

    assert len(logs) == 1
    assert logs[0].name == "diag.log"
    assert logs[0].data == b"log"

    assert len(screenshots) == 2
    screenshot_names = {item.name for item in screenshots}
    assert screenshot_names == {"shot.png", "fallback.png"}
    screenshot_payloads = {item.name: item.data for item in screenshots}
    assert screenshot_payloads["shot.png"] == b"img1"
    assert screenshot_payloads["fallback.png"] == b"img2"

