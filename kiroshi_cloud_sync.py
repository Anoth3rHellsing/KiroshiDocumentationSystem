"""Utility helpers for the Kiroshi Cloud client and desktop app.

This module centralises the shared logic required by the new Kiroshi Cloud
experience.  Both the dedicated Streamlit client (`kiroshi_cloud_client.py`)
and the original Kiroshi case documentation app import these helpers to:

* discover the storage layout used for encrypted cloud metadata;
* validate credentials and derive the symmetric keys that protect the cloud
  device database and AI Educate snapshots;
* manipulate the encrypted device roster (allow, block, remove peers);
* exchange the AI Educate dataset between the classic Kiroshi desktop app and
  the new cloud service; and
* generate human readable analytics for quality assurance reviews.

The implementation deliberately avoids any Streamlit dependencies so that it
can be safely imported from traditional Python contexts (unit tests, CLI
scripts, etc.).
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CloudError(RuntimeError):
    """Base exception raised when the cloud helpers encounter an error."""


class AuthenticationError(CloudError):
    """Raised when username/password validation fails."""


class EncryptionError(CloudError):
    """Raised when encrypted payloads cannot be decrypted with the session key."""


DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123!"
DEFAULT_OVERLAY_PROVIDER = "Tailscale, ZeroTier, or WireGuard"
DEFAULT_OVERLAY_INSTRUCTIONS = """
1. **Install the overlay agent** – deploy a mesh VPN such as
   [Tailscale](https://tailscale.com), [ZeroTier](https://www.zerotier.com/),
   or a WireGuard hub. These tools create encrypted tunnels between the cloud
   host and every workstation without opening inbound firewall ports.
2. **Authenticate each device** – sign in with the same organisation account
   or network ID across the cloud host and every Kiroshi desktop deployment.
3. **Record the overlay IP** – once connected, copy the assigned overlay
   address (for example 100.x.y.z on Tailscale) into the *Device IP* field when
   registering the workstation in the Connections tab.
4. **Test the tunnel** – from the cloud host run `ping <overlay-ip>` or your
   overlay provider's status command to verify the workstation is reachable.
5. **Distribute the token** – generate a connection token per workstation and
   paste it into the Kiroshi desktop client's Cloud settings. Only peers with
   a valid token and shared secret can synchronise the Educate dataset.
"""
CONFIG_VERSION = 2
KDF_ITERATIONS = 390_000


def _default_cloud_directory() -> Path:
    if os.name == "nt":
        return Path("C:/ProgramFiles/KiroshiCloud")
    return Path.home() / "KiroshiCloud"


def _default_database_directory() -> Path:
    if os.name == "nt":
        return Path("C:/ProgramFiles/KiroshiDatabase")
    return Path.home() / "KiroshiDatabase"


CLOUD_ROOT = _default_cloud_directory()
CLOUD_CONFIG_PATH = CLOUD_ROOT / "cloud_config.json"
CLOUD_DEVICES_PATH = CLOUD_ROOT / "cloud_devices.enc"
CLOUD_EDUCATE_PATH = CLOUD_ROOT / "cloud_educate.enc"

DATABASE_ROOT = _default_database_directory()
DATABASE_UTILITIES = DATABASE_ROOT / "utilities"
AI_LEARNING_PATH = DATABASE_UTILITIES / "AILearning.json"


def _ensure_directories() -> None:
    CLOUD_ROOT.mkdir(parents=True, exist_ok=True)
    DATABASE_ROOT.mkdir(parents=True, exist_ok=True)
    DATABASE_UTILITIES.mkdir(parents=True, exist_ok=True)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pbkdf2(password: str, salt: bytes, length: int = 32) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def _hash_password(password: str, salt: bytes) -> str:
    digest = _pbkdf2(password, salt)
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def _build_fernet(password: str, salt: bytes) -> Fernet:
    key = base64.urlsafe_b64encode(_pbkdf2(password, salt))
    return Fernet(key)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _synchronise_default_flag(config: dict[str, Any]) -> bool:
    try:
        salt_encoded = config.get("password_salt")
        password_hash = config.get("password_hash")
        if not isinstance(salt_encoded, str) or not isinstance(password_hash, str):
            return False
        salt = _decode_salt(salt_encoded)
    except Exception:  # pragma: no cover - configuration corruption guard
        return False

    expected_default = _hash_password(DEFAULT_PASSWORD, salt)
    using_defaults = (
        config.get("username") == DEFAULT_USERNAME
        and secrets.compare_digest(password_hash, expected_default)
    )

    if config.get("uses_default_credentials") == using_defaults:
        return False

    config["uses_default_credentials"] = using_defaults
    return True


def _ensure_optional_fields(config: dict[str, Any]) -> bool:
    updated = False

    if not config.get("instance_id"):
        config["instance_id"] = str(uuid.uuid4())
        updated = True

    if "uses_default_credentials" not in config:
        config["uses_default_credentials"] = True
        updated = True

    if "overlay_provider" not in config:
        config["overlay_provider"] = DEFAULT_OVERLAY_PROVIDER
        updated = True

    if "overlay_instructions" not in config:
        config["overlay_instructions"] = DEFAULT_OVERLAY_INSTRUCTIONS.strip()
        updated = True

    return updated or _synchronise_default_flag(config)


def _upgrade_config(config: dict[str, Any], path: Path) -> dict[str, Any]:
    updated = False

    version = config.get("version")
    if not isinstance(version, int) or version < CONFIG_VERSION:
        config["version"] = CONFIG_VERSION
        updated = True

    if "created_at" not in config:
        config["created_at"] = _utc_timestamp()
        updated = True

    if "updated_at" not in config:
        config["updated_at"] = config.get("created_at")
        updated = True

    if _ensure_optional_fields(config):
        updated = True

    if updated:
        config["updated_at"] = _utc_timestamp()
        _write_json(path, config)

    return config


def _initialize_default_config(path: Path) -> dict[str, Any]:
    salt_password = os.urandom(16)
    salt_encryption = os.urandom(16)
    instance_id = str(uuid.uuid4())
    now = _utc_timestamp()
    config = {
        "version": CONFIG_VERSION,
        "username": DEFAULT_USERNAME,
        "password_salt": base64.urlsafe_b64encode(salt_password).decode("utf-8"),
        "password_hash": _hash_password(DEFAULT_PASSWORD, salt_password),
        "encryption_salt": base64.urlsafe_b64encode(salt_encryption).decode("utf-8"),
        "instance_id": instance_id,
        "created_at": now,
        "updated_at": now,
        "uses_default_credentials": True,
        "overlay_provider": DEFAULT_OVERLAY_PROVIDER,
        "overlay_instructions": DEFAULT_OVERLAY_INSTRUCTIONS.strip(),
    }
    _write_json(path, config)
    return config


def load_cloud_config(create_if_missing: bool = True) -> dict[str, Any]:
    """Load the persistent cloud configuration, creating a default one if needed."""

    _ensure_directories()
    if CLOUD_CONFIG_PATH.exists():
        try:
            config = _read_json(CLOUD_CONFIG_PATH)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
            raise CloudError(f"Invalid cloud configuration file: {exc}") from exc
        return _upgrade_config(config, CLOUD_CONFIG_PATH)
    if not create_if_missing:
        raise CloudError("Kiroshi Cloud configuration is missing.")
    config = _initialize_default_config(CLOUD_CONFIG_PATH)
    return _upgrade_config(config, CLOUD_CONFIG_PATH)


def _decode_salt(encoded: str) -> bytes:
    return base64.urlsafe_b64decode(encoded.encode("utf-8"))


@dataclass
class CloudSession:
    """Authenticated handle used to manipulate encrypted cloud resources."""

    username: str
    config: dict[str, Any]
    config_path: Path
    _fernet: Fernet

    @property
    def encryption_salt(self) -> bytes:
        raw = self.config.get("encryption_salt")
        if not isinstance(raw, str):
            raise CloudError("Cloud configuration is missing the encryption salt.")
        return _decode_salt(raw)

    def _decrypt_json(self, path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return json.loads(json.dumps(default))
        token = path.read_bytes()
        if not token:
            return json.loads(json.dumps(default))
        try:
            payload = self._fernet.decrypt(token)
        except InvalidToken as exc:
            raise EncryptionError(f"Unable to decrypt {path.name}; verify the password.") from exc
        return json.loads(payload.decode("utf-8"))

    def _encrypt_json(self, path: Path, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        token = self._fernet.encrypt(data)
        path.write_bytes(token)

    def load_devices(self) -> dict[str, Any]:
        return self._decrypt_json(
            CLOUD_DEVICES_PATH,
            default={"devices": [], "last_synced": None},
        )

    def save_devices(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload.setdefault("devices", [])
        payload["last_synced"] = _utc_timestamp()
        self._encrypt_json(CLOUD_DEVICES_PATH, payload)

    def load_ai_dataset(
        self, *, agent_ids: Iterable[str] | None = None
    ) -> dict[str, Any] | None:
        payload = self._decrypt_json(CLOUD_EDUCATE_PATH, default={})
        if not payload:
            return None

        agent_filter = {
            str(agent).strip().lower()
            for agent in agent_ids or []
            if str(agent).strip()
        }

        if not agent_filter:
            return payload or None

        def _apply_filter(dataset: dict[str, Any] | None) -> dict[str, Any] | None:
            if not isinstance(dataset, dict):
                return dataset

            filtered = dict(dataset)
            cases = dataset.get("cases")
            if isinstance(cases, list):
                filtered_cases = [
                    entry
                    for entry in cases
                    if isinstance(entry, dict)
                    and str(entry.get("agent_id") or "").strip().lower() in agent_filter
                ]
                filtered["cases"] = filtered_cases
                filtered["case_count"] = len(filtered_cases)
            filtered["filtered_agents"] = sorted(agent_filter)
            return filtered

        if isinstance(payload, dict) and "dataset" in payload:
            dataset_obj = _apply_filter(payload.get("dataset"))
            wrapped = dict(payload)
            wrapped["dataset"] = dataset_obj
            wrapped["requested_agents"] = sorted(agent_filter)
            return wrapped or None

        if isinstance(payload, dict):
            filtered_dataset = _apply_filter(payload)
            if isinstance(filtered_dataset, dict):
                filtered_dataset.setdefault("requested_agents", sorted(agent_filter))
            return filtered_dataset or None

        return payload

    def save_ai_dataset(self, dataset: dict[str, Any]) -> None:
        payload = {
            "dataset": dataset,
            "saved_at": _utc_timestamp(),
        }
        self._encrypt_json(CLOUD_EDUCATE_PATH, payload)

    def read_ai_dataset_wrapper(self) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        data = self.load_ai_dataset()
        if not data:
            return None, {}
        if isinstance(data, dict) and "dataset" in data and "saved_at" in data:
            return data.get("dataset"), data
        return data, {"saved_at": None}

    def update_credentials(self, new_username: str, new_password: str) -> None:
        devices_snapshot = self.load_devices()
        dataset_snapshot, metadata = self.read_ai_dataset_wrapper()

        password_salt = os.urandom(16)
        self.config["username"] = new_username
        self.config["password_salt"] = base64.urlsafe_b64encode(password_salt).decode("utf-8")
        self.config["password_hash"] = _hash_password(new_password, password_salt)
        self.config["updated_at"] = _utc_timestamp()
        self.config["uses_default_credentials"] = False

        _write_json(self.config_path, self.config)

        self.username = new_username
        self._fernet = _build_fernet(new_password, self.encryption_salt)

        self.save_devices(devices_snapshot)
        if dataset_snapshot is not None:
            if metadata:
                payload = dict(metadata)
                payload["dataset"] = dataset_snapshot
            else:
                payload = {"dataset": dataset_snapshot}
            self._encrypt_json(CLOUD_EDUCATE_PATH, payload)

    def update_overlay_settings(self, provider: str, instructions: str) -> dict[str, str]:
        provider_value = provider.strip() or DEFAULT_OVERLAY_PROVIDER
        instructions_value = instructions.strip() or DEFAULT_OVERLAY_INSTRUCTIONS.strip()

        changed = False
        if self.config.get("overlay_provider") != provider_value:
            self.config["overlay_provider"] = provider_value
            changed = True
        if self.config.get("overlay_instructions") != instructions_value:
            self.config["overlay_instructions"] = instructions_value
            changed = True

        if changed:
            self.config["updated_at"] = _utc_timestamp()
            _write_json(self.config_path, self.config)

        return {
            "provider": self.config.get("overlay_provider", DEFAULT_OVERLAY_PROVIDER),
            "instructions": self.config.get(
                "overlay_instructions", DEFAULT_OVERLAY_INSTRUCTIONS.strip()
            ),
        }


def open_cloud_session(username: str, password: str) -> CloudSession:
    """Authenticate against the encrypted Kiroshi Cloud store."""

    config = load_cloud_config(create_if_missing=True)
    stored_username = config.get("username")
    if stored_username != username:
        raise AuthenticationError("The provided username does not match the cloud configuration.")

    salt_encoded = config.get("password_salt")
    password_hash = config.get("password_hash")
    if not isinstance(salt_encoded, str) or not isinstance(password_hash, str):
        raise CloudError("Cloud configuration is missing password metadata.")

    salt = _decode_salt(salt_encoded)
    expected = _hash_password(password, salt)
    if not secrets.compare_digest(expected, password_hash):
        raise AuthenticationError("Invalid username or password for Kiroshi Cloud.")

    encryption_salt_encoded = config.get("encryption_salt")
    if not isinstance(encryption_salt_encoded, str):
        raise CloudError("Cloud configuration is missing the encryption salt.")

    encryption_salt = _decode_salt(encryption_salt_encoded)
    session = CloudSession(
        username=username,
        config=config,
        config_path=CLOUD_CONFIG_PATH,
        _fernet=_build_fernet(password, encryption_salt),
    )
    return session


def _normalize_ip(ip: str) -> str:
    return ip.strip()


def _current_timestamp() -> str:
    return _utc_timestamp()


def add_device(session: CloudSession, *, name: str, ip: str, notes: str = "") -> dict[str, Any]:
    devices_payload = session.load_devices()
    devices = devices_payload.get("devices", [])
    device_id = str(uuid.uuid4())
    record = {
        "device_id": device_id,
        "name": name.strip() or f"Device {device_id[:8]}",
        "ip": _normalize_ip(ip),
        "notes": notes.strip(),
        "allowed": True,
        "blocked": False,
        "shared_secret": secrets.token_urlsafe(32),
        "created_at": _current_timestamp(),
        "last_seen": None,
        "status": "allowed",
    }
    devices.append(record)
    devices_payload["devices"] = devices
    session.save_devices(devices_payload)
    return record


def update_device_status(
    session: CloudSession,
    device_id: str,
    *,
    allowed: bool | None = None,
    blocked: bool | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    payload = session.load_devices()
    devices = payload.get("devices", [])
    for record in devices:
        if record.get("device_id") == device_id:
            if allowed is not None:
                record["allowed"] = bool(allowed)
            if blocked is not None:
                record["blocked"] = bool(blocked)
            if notes is not None:
                record["notes"] = notes
            record["status"] = (
                "blocked" if record.get("blocked") else ("allowed" if record.get("allowed") else "pending")
            )
            payload["devices"] = devices
            session.save_devices(payload)
            return record
    raise CloudError(f"Device with ID {device_id} was not found in the cloud roster.")


def record_device_seen(session: CloudSession, device_id: str, *, ip: str | None = None) -> dict[str, Any]:
    payload = session.load_devices()
    devices = payload.get("devices", [])
    for record in devices:
        if record.get("device_id") == device_id:
            record["last_seen"] = _current_timestamp()
            if ip:
                record["ip"] = _normalize_ip(ip)
            payload["devices"] = devices
            session.save_devices(payload)
            return record
    raise CloudError(f"Device with ID {device_id} was not found in the cloud roster.")


def remove_device(session: CloudSession, device_id: str) -> None:
    payload = session.load_devices()
    devices = payload.get("devices", [])
    updated = [record for record in devices if record.get("device_id") != device_id]
    if len(updated) == len(devices):
        raise CloudError(f"Device with ID {device_id} was not found in the cloud roster.")
    payload["devices"] = updated
    session.save_devices(payload)


def generate_device_token(session: CloudSession, device_id: str) -> str:
    payload = session.load_devices()
    for record in payload.get("devices", []):
        if record.get("device_id") == device_id:
            token_payload = {
                "device_id": record.get("device_id"),
                "shared_secret": record.get("shared_secret"),
                "cloud_instance": session.config.get("instance_id"),
                "issued_at": _current_timestamp(),
            }
            encoded = json.dumps(token_payload).encode("utf-8")
            return base64.urlsafe_b64encode(encoded).decode("utf-8")
    raise CloudError(f"Device with ID {device_id} was not found in the cloud roster.")


def decode_device_token(token: str) -> dict[str, Any]:
    try:
        payload = base64.urlsafe_b64decode(token.encode("utf-8"))
        data = json.loads(payload.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive parsing guard
        raise CloudError("The provided device token is invalid or corrupted.") from exc
    return data


def load_local_ai_dataset() -> dict[str, Any] | None:
    if not AI_LEARNING_PATH.exists():
        return None
    try:
        return _read_json(AI_LEARNING_PATH)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise CloudError(f"Local AI Educate dataset is corrupted: {exc}") from exc


def save_local_ai_dataset(dataset: dict[str, Any]) -> None:
    _ensure_directories()
    _write_json(AI_LEARNING_PATH, dataset)


def overlay_guidance(config: dict[str, Any] | None = None) -> dict[str, str]:
    if config is None:
        try:
            config = load_cloud_config()
        except CloudError:
            config = {}

    provider = config.get("overlay_provider") or DEFAULT_OVERLAY_PROVIDER
    instructions = config.get("overlay_instructions") or DEFAULT_OVERLAY_INSTRUCTIONS.strip()
    return {"provider": provider, "instructions": instructions}


def _pick_field(record: dict[str, Any], keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def summarize_dataset(dataset: dict[str, Any] | None) -> dict[str, Any]:
    if not dataset:
        return {
            "total_cases": 0,
            "unique_devices": 0,
            "root_cause_counts": [],
            "device_counts": [],
            "recent_cases": [],
        }

    cases = dataset.get("cases", [])
    if not isinstance(cases, list):
        return {
            "total_cases": 0,
            "unique_devices": 0,
            "root_cause_counts": [],
            "device_counts": [],
            "recent_cases": [],
        }

    root_counter: Counter[str] = Counter()
    device_counter: Counter[str] = Counter()
    recent_entries: list[dict[str, Any]] = []

    for entry in cases:
        if not isinstance(entry, dict):
            continue
        root_cause = _pick_field(entry, ["root_cause", "analysis_label"], default="Unspecified")
        root_counter[root_cause or "Unspecified"] += 1

        device_label = _pick_field(
            entry,
            [
                "scanner_model",
                "scanner",
                "device",
                "workstation",
                "host",
            ],
            default="Unknown",
        )
        device_counter[device_label or "Unknown"] += 1

        timestamp = entry.get("timestamp") or entry.get("saved_at")
        if timestamp:
            try:
                if isinstance(timestamp, (int, float)):
                    dt = datetime.utcfromtimestamp(float(timestamp))
                else:
                    dt = datetime.fromisoformat(str(timestamp))
            except Exception:
                dt = None
        else:
            dt = None
        recent_entries.append(
            {
                "case_id": entry.get("case_id"),
                "title": entry.get("title"),
                "root_cause": root_cause,
                "device": device_label,
                "timestamp": dt,
            }
        )

    recent_entries = [item for item in recent_entries if item.get("timestamp")]
    recent_entries.sort(key=lambda row: row["timestamp"], reverse=True)

    return {
        "total_cases": len(cases),
        "unique_devices": len(device_counter),
        "root_cause_counts": root_counter.most_common(10),
        "device_counts": device_counter.most_common(10),
        "recent_cases": recent_entries[:10],
    }


def dataset_counts_to_frame(counts: list[tuple[str, int]], *, label: str) -> pd.DataFrame:
    if not counts:
        return pd.DataFrame(columns=[label, "cases"])
    labels = [item[0] for item in counts]
    values = [item[1] for item in counts]
    return pd.DataFrame({label: labels, "cases": values})


__all__ = [
    "AI_LEARNING_PATH",
    "AuthenticationError",
    "CloudError",
    "CloudSession",
    "CLOUD_DEVICES_PATH",
    "CLOUD_EDUCATE_PATH",
    "DEFAULT_USERNAME",
    "DEFAULT_PASSWORD",
    "DEFAULT_OVERLAY_INSTRUCTIONS",
    "DEFAULT_OVERLAY_PROVIDER",
    "add_device",
    "dataset_counts_to_frame",
    "decode_device_token",
    "generate_device_token",
    "load_cloud_config",
    "overlay_guidance",
    "load_local_ai_dataset",
    "open_cloud_session",
    "record_device_seen",
    "remove_device",
    "save_local_ai_dataset",
    "summarize_dataset",
    "update_device_status",
]

