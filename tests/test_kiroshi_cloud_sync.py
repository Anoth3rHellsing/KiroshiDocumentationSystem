import base64
import json
import os
import uuid

import pytest

import kiroshi_cloud_sync as cloud


def _configure_paths(tmp_path, monkeypatch):
    cloud_root = tmp_path / "cloud"
    database_root = tmp_path / "db"

    monkeypatch.setattr(cloud, "CLOUD_ROOT", cloud_root, raising=False)
    monkeypatch.setattr(cloud, "CLOUD_ROOT_DISPLAY", str(cloud_root), raising=False)
    monkeypatch.setattr(cloud, "CLOUD_CONFIG_PATH", cloud_root / "cloud_config.json", raising=False)
    monkeypatch.setattr(cloud, "CLOUD_DEVICES_PATH", cloud_root / "cloud_devices.enc", raising=False)
    monkeypatch.setattr(cloud, "CLOUD_EDUCATE_PATH", cloud_root / "cloud_educate.enc", raising=False)
    monkeypatch.setattr(cloud, "DATABASE_ROOT", database_root, raising=False)
    monkeypatch.setattr(cloud, "DATABASE_UTILITIES", database_root / "utilities", raising=False)
    monkeypatch.setattr(
        cloud,
        "AI_LEARNING_PATH",
        database_root / "utilities" / "AILearning.json",
        raising=False,
    )


def test_load_cloud_config_initialises_overlay_defaults(tmp_path, monkeypatch):
    _configure_paths(tmp_path, monkeypatch)

    config = cloud.load_cloud_config()

    assert config["overlay_provider"] == cloud.DEFAULT_OVERLAY_PROVIDER
    assert config["overlay_instructions"] == cloud.DEFAULT_OVERLAY_INSTRUCTIONS.strip()
    assert config["version"] == cloud.CONFIG_VERSION


def test_load_cloud_config_upgrades_missing_overlay_fields(tmp_path, monkeypatch):
    _configure_paths(tmp_path, monkeypatch)

    salt_password = os.urandom(16)
    salt_encryption = os.urandom(16)
    config = {
        "version": 1,
        "username": cloud.DEFAULT_USERNAME,
        "password_salt": base64.urlsafe_b64encode(salt_password).decode("utf-8"),
        "password_hash": cloud._hash_password(cloud.DEFAULT_PASSWORD, salt_password),
        "encryption_salt": base64.urlsafe_b64encode(salt_encryption).decode("utf-8"),
        "instance_id": str(uuid.uuid4()),
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "uses_default_credentials": True,
    }
    cloud.CLOUD_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cloud.CLOUD_CONFIG_PATH.write_text(json.dumps(config), encoding="utf-8")

    upgraded = cloud.load_cloud_config()

    assert upgraded["version"] == cloud.CONFIG_VERSION
    assert upgraded["overlay_provider"] == cloud.DEFAULT_OVERLAY_PROVIDER
    assert upgraded["overlay_instructions"] == cloud.DEFAULT_OVERLAY_INSTRUCTIONS.strip()
    assert upgraded["uses_default_credentials"] is True


def test_update_overlay_settings_persists(tmp_path, monkeypatch):
    _configure_paths(tmp_path, monkeypatch)

    cloud.load_cloud_config()
    session = cloud.open_cloud_session(cloud.DEFAULT_USERNAME, cloud.DEFAULT_PASSWORD)

    updated = session.update_overlay_settings(
        "ZeroTier corporate network",
        """1. Join the ZeroTier network ID `abcdef1234567890`.
2. Wait until the controller authorises the node.
3. Use the assigned overlay IP inside the Kiroshi Cloud Connections tab.""",
    )

    assert updated["provider"] == "ZeroTier corporate network"
    assert "ZeroTier" in updated["instructions"]

    refreshed = cloud.load_cloud_config()
    assert refreshed["overlay_provider"] == "ZeroTier corporate network"
    assert "network ID" in refreshed["overlay_instructions"]


def test_cloud_share_status_reports_availability(tmp_path, monkeypatch):
    _configure_paths(tmp_path, monkeypatch)

    status = cloud.cloud_share_status(timeout=0.1)

    assert status["available"] is True
    assert status["path"] == str(tmp_path / "cloud")
    assert (tmp_path / "cloud").exists()


def test_cloud_session_reports_share_errors(tmp_path, monkeypatch):
    _configure_paths(tmp_path, monkeypatch)

    cloud.load_cloud_config()
    session = cloud.open_cloud_session(cloud.DEFAULT_USERNAME, cloud.DEFAULT_PASSWORD)

    def _fail_share(timeout=None):
        raise cloud.CloudError("Could not connect to the Kiroshi Cloud share at TEST.")

    monkeypatch.setattr(cloud, "ensure_cloud_share", _fail_share, raising=False)

    with pytest.raises(cloud.CloudError) as excinfo:
        session.load_devices()
    assert "Could not connect" in str(excinfo.value)

    with pytest.raises(cloud.CloudError):
        session.save_ai_dataset({"cases": []})
