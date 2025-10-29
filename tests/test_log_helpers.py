import logging

from KiroshiApp.core.logs import load_recent_logs, resolve_log_file_path, tail_log_file


def test_resolve_log_file_prefers_env(monkeypatch, tmp_path):
    env_path = tmp_path / "env.log"
    monkeypatch.setenv("KIROSHI_LOG_FILE", str(env_path))
    assert resolve_log_file_path().resolve() == env_path.resolve()


def test_resolve_log_file_detects_handlers(tmp_path):
    log_path = tmp_path / "handler.log"
    handler = logging.FileHandler(log_path)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        assert resolve_log_file_path().resolve() == log_path.resolve()
    finally:
        root_logger.removeHandler(handler)
        handler.close()


def test_tail_log_file_reads_tail(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("\n".join(str(i) for i in range(100)), encoding="utf-8")
    snapshot = tail_log_file(log_path, max_bytes=64)
    assert snapshot.ok
    # Only the tail of the file should be returned.
    assert "99" in snapshot.content
    assert "0" not in snapshot.content.splitlines()[0]


def test_tail_log_file_handles_missing(tmp_path):
    missing = tmp_path / "missing.log"
    snapshot = tail_log_file(missing)
    assert not snapshot.ok
    assert "no existe" in snapshot.error.lower()


def test_load_recent_logs_uses_default(tmp_path, monkeypatch):
    default_log = tmp_path / "default.log"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KIROSHI_LOG_FILE", str(default_log))
    default_log.write_text("hola", encoding="utf-8")
    snapshot = load_recent_logs()
    assert snapshot.ok
    assert snapshot.content == "hola"
