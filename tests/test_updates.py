import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import case_documentation_app


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._stream = io.BytesIO(payload)
        self.chunks_read = 0
        self.exhausted = False

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401 - mimic requests.Response
        self._stream.close()

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 8192):
        while True:
            chunk = self._stream.read(chunk_size)
            if not chunk:
                self.exhausted = True
                return
            self.chunks_read += len(chunk)
            yield chunk


def test_apply_github_update_prefers_app_directory(monkeypatch, tmp_path):
    selected_source = tmp_path / "selected"
    selected_source.mkdir()
    (selected_source / "case_documentation_app.py").write_text("updated app", encoding="utf-8")
    (selected_source / "beta_only.txt").write_text("beta", encoding="utf-8")
    nested_dir = selected_source / "nested"
    nested_dir.mkdir()
    (nested_dir / "info.txt").write_text("nested", encoding="utf-8")

    other_source = tmp_path / "other"
    other_source.mkdir()
    (other_source / "alpha_only.txt").write_text("alpha", encoding="utf-8")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for path in other_source.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(tmp_path))
        for path in selected_source.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(tmp_path))
    zip_bytes = buffer.getvalue()

    captured_response: dict[str, _FakeResponse] = {}

    def fake_get(*args, **kwargs):
        response = _FakeResponse(zip_bytes)
        captured_response["response"] = response
        return response

    app_root = tmp_path / "app"
    updates_dir = tmp_path / "updates"
    app_root.mkdir()
    updates_dir.mkdir()

    monkeypatch.setattr(case_documentation_app, "APP_ROOT", app_root)
    monkeypatch.setattr(case_documentation_app, "UPDATES_DIR", updates_dir)
    monkeypatch.setattr(case_documentation_app.requests, "get", fake_get)

    result = case_documentation_app.apply_github_update("owner/repo", "test-branch")

    assert result == app_root
    copied_app = app_root / "case_documentation_app.py"
    assert copied_app.read_text(encoding="utf-8") == "updated app"
    assert (app_root / "beta_only.txt").read_text(encoding="utf-8") == "beta"
    assert (app_root / "nested" / "info.txt").read_text(encoding="utf-8") == "nested"
    assert not (app_root / "alpha_only.txt").exists()

    stored_archives = list(updates_dir.glob("test-branch-*.zip"))
    assert len(stored_archives) == 1

    assert "response" in captured_response
    response = captured_response["response"]
    assert response.chunks_read == len(zip_bytes)
    assert response.exhausted is True
