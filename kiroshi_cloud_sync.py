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
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, Mapping

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


class AgentBlockedError(CloudError):
    """Raised when an agent attempts to upload while suspended."""


DEFAULT_USERNAME = "admin"
LEGACY_DEFAULT_PASSWORD = "admin123!"
DEFAULT_PASSWORD = LEGACY_DEFAULT_PASSWORD
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
_DEFAULT_CLOUD_SHARE = PureWindowsPath("\\\\dk-srv-fl-01\\CosCare\\Nicolas M\\KC")
_CLOUD_ROOT_OVERRIDE_ENV = "KIROSHI_CLOUD_ROOT"
_CLOUD_TIMEOUT_OVERRIDE_ENV = "KIROSHI_CLOUD_TIMEOUT"


def _initialise_cloud_root() -> tuple[Path, str]:
    override = os.environ.get(_CLOUD_ROOT_OVERRIDE_ENV)
    if override:
        return Path(override), override
    share_str = str(_DEFAULT_CLOUD_SHARE)
    if os.name == "nt":
        return Path(share_str), share_str
    return Path(share_str), share_str


def _read_timeout_setting() -> float:
    raw = os.environ.get(_CLOUD_TIMEOUT_OVERRIDE_ENV)
    if not raw:
        return 45.0
    try:
        value = float(raw)
    except (TypeError, ValueError):  # pragma: no cover - defensive parsing
        return 45.0
    return max(5.0, value)


def _default_database_directory() -> Path:
    if os.name == "nt":
        return Path("C:/ProgramFiles/KiroshiDatabase")
    return Path.home() / "KiroshiDatabase"


CLOUD_ROOT, CLOUD_ROOT_DISPLAY = _initialise_cloud_root()
CLOUD_IO_TIMEOUT_SECONDS = _read_timeout_setting()
CLOUD_CONFIG_PATH = CLOUD_ROOT / "cloud_config.json"
CLOUD_DEVICES_PATH = CLOUD_ROOT / "cloud_devices.enc"
CLOUD_EDUCATE_PATH = CLOUD_ROOT / "cloud_educate.enc"

DATASET_STORE_DEFAULT = {
    "agents": {},
    "last_modified": None,
}

DATABASE_ROOT = _default_database_directory()
DATABASE_UTILITIES = DATABASE_ROOT / "utilities"
AI_LEARNING_PATH = DATABASE_UTILITIES / "AILearning.json"

def _normalize_timeout(timeout: float | None) -> float:
    if timeout is None:
        return CLOUD_IO_TIMEOUT_SECONDS
    try:
        value = float(timeout)
    except (TypeError, ValueError):
        return CLOUD_IO_TIMEOUT_SECONDS
    return max(1.0, value)


def _cloud_share_error_message(exc: Exception | None = None) -> str:
    message = f"Could not connect to the Kiroshi Cloud share at {CLOUD_ROOT_DISPLAY}."
    if exc:
        return f"{message} {exc}"
    return message


def _wait_for_share(path: Path, timeout: float, *, create: bool) -> None:
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while True:
        try:
            if create:
                path.mkdir(parents=True, exist_ok=True)
            else:
                if path.exists():
                    path.stat()
                else:
                    parent = path.parent if path.parent != path else path
                    parent.exists()
            return
        except FileExistsError:
            return
        except FileNotFoundError:
            if not create:
                return
            last_error = None
        except PermissionError as exc:  # pragma: no cover - permission guard
            last_error = exc
        except OSError as exc:
            last_error = exc

        if time.monotonic() >= deadline:
            raise CloudError(_cloud_share_error_message(last_error)) from last_error
        time.sleep(0.5)


def ensure_cloud_share(timeout: float | None = None) -> Path:
    wait_seconds = _normalize_timeout(timeout)
    _wait_for_share(CLOUD_ROOT, wait_seconds, create=True)
    return CLOUD_ROOT


def cloud_share_status(timeout: float | None = None) -> dict[str, Any]:
    try:
        ensure_cloud_share(timeout=timeout)
    except CloudError as exc:
        return {
            "available": False,
            "path": CLOUD_ROOT_DISPLAY,
            "message": str(exc),
        }
    return {
        "available": True,
        "path": CLOUD_ROOT_DISPLAY,
        "message": f"Kiroshi Cloud share ready at {CLOUD_ROOT_DISPLAY}.",
    }


def _ensure_directories() -> None:
    ensure_cloud_share()
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


def _path_is_in_cloud(path: Path) -> bool:
    try:
        path.relative_to(CLOUD_ROOT)
    except ValueError:
        return False
    return True


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        if _path_is_in_cloud(path):
            raise CloudError(_cloud_share_error_message(exc)) from exc
        raise


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = path.read_text(encoding="utf-8")
    except OSError as exc:
        if _path_is_in_cloud(path):
            raise CloudError(_cloud_share_error_message(exc)) from exc
        raise
    return json.loads(data)


def check_is_legacy_default(config: dict[str, Any]) -> bool:
    try:
        salt_encoded = config.get("password_salt")
        password_hash = config.get("password_hash")
        if not isinstance(salt_encoded, str) or not isinstance(password_hash, str):
            return False
        salt = _decode_salt(salt_encoded)
    except Exception:  # pragma: no cover - configuration corruption guard
        return False

    expected_default = _hash_password(LEGACY_DEFAULT_PASSWORD, salt)
    return (
        config.get("username") == DEFAULT_USERNAME
        and secrets.compare_digest(password_hash, expected_default)
    )


def _synchronise_default_flag(config: dict[str, Any]) -> bool:
    # Only force flag to True if legacy credentials are detected.
    # We do not clear the flag automatically because we might be using a random default.
    if check_is_legacy_default(config) and not config.get("uses_default_credentials"):
        config["uses_default_credentials"] = True
        return True

    return False


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


def _initialize_default_config(path: Path, password: str | None = None) -> dict[str, Any]:
    salt_password = os.urandom(16)
    salt_encryption = os.urandom(16)
    instance_id = str(uuid.uuid4())
    now = _utc_timestamp()

    final_password = password or LEGACY_DEFAULT_PASSWORD

    config = {
        "version": CONFIG_VERSION,
        "username": DEFAULT_USERNAME,
        "password_salt": base64.urlsafe_b64encode(salt_password).decode("utf-8"),
        "password_hash": _hash_password(final_password, salt_password),
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


def generate_secure_password() -> str:
    return secrets.token_urlsafe(16)


def load_cloud_config(create_if_missing: bool = True) -> dict[str, Any]:
    """Load the persistent cloud configuration, creating a default one if needed."""

    _ensure_directories()
    try:
        config_exists = CLOUD_CONFIG_PATH.exists()
    except OSError as exc:
        raise CloudError(_cloud_share_error_message(exc)) from exc
    if config_exists:
        try:
            config = _read_json(CLOUD_CONFIG_PATH)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
            raise CloudError(f"Invalid cloud configuration file: {exc}") from exc
        return _upgrade_config(config, CLOUD_CONFIG_PATH)

    if not create_if_missing:
        raise CloudError("Kiroshi Cloud configuration is missing.")

    new_password = generate_secure_password()
    config = _initialize_default_config(CLOUD_CONFIG_PATH, password=new_password)
    config = _upgrade_config(config, CLOUD_CONFIG_PATH)
    # Inject the generated password transiently so the UI can display it
    config["_generated_password"] = new_password
    return config


def _decode_salt(encoded: str) -> bytes:
    return base64.urlsafe_b64decode(encoded.encode("utf-8"))


@dataclass
class CloudSession:
    """Authenticated handle used to manipulate encrypted cloud resources."""

    username: str
    config: dict[str, Any]
    config_path: Path
    _fernet: Fernet
    share_timeout: float = field(default=CLOUD_IO_TIMEOUT_SECONDS)

    @property
    def encryption_salt(self) -> bytes:
        raw = self.config.get("encryption_salt")
        if not isinstance(raw, str):
            raise CloudError("Cloud configuration is missing the encryption salt.")
        return _decode_salt(raw)

    def _decrypt_json(self, path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
        ensure_cloud_share(timeout=self.share_timeout)
        try:
            if not path.exists():
                return json.loads(json.dumps(default))
        except OSError as exc:
            raise CloudError(_cloud_share_error_message(exc)) from exc
        try:
            token = path.read_bytes()
        except FileNotFoundError:
            return json.loads(json.dumps(default))
        except OSError as exc:
            raise CloudError(_cloud_share_error_message(exc)) from exc
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
        ensure_cloud_share(timeout=self.share_timeout)
        try:
            path.write_bytes(token)
        except OSError as exc:
            raise CloudError(_cloud_share_error_message(exc)) from exc

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

    def _append_justification(self, record: dict[str, Any], action: str, note: str) -> None:
        entry = {
            "timestamp": _utc_timestamp(),
            "action": action,
            "note": note or "",
        }
        log = record.setdefault("justifications", [])
        if isinstance(log, list):
            log.append(entry)
        else:  # pragma: no cover - defensive normalisation
            record["justifications"] = [entry]

    def _empty_agent_record(self, agent_id: str) -> dict[str, Any]:
        identifier = str(agent_id or "").strip().lower()
        if not identifier:
            fallback = str(self.config.get("instance_id") or self.username or "default")
            identifier = fallback.strip().lower() or "default"
        return {
            "agent_id": identifier,
            "dataset": None,
            "saved_at": None,
            "blocked": False,
            "blocked_at": None,
            "blocked_reason": "",
            "justifications": [],
        }

    def _normalize_agent_record(
        self, agent_id: str, record: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        normalised = dict(record or {})
        changed = False
        if normalised.get("agent_id") != agent_id:
            normalised["agent_id"] = agent_id
            changed = True
        if "dataset" not in normalised:
            normalised["dataset"] = None
            changed = True
        if "saved_at" not in normalised:
            normalised["saved_at"] = None
            changed = True
        if "blocked" not in normalised:
            normalised["blocked"] = False
            changed = True
        if "blocked_at" not in normalised:
            normalised["blocked_at"] = None
            changed = True
        if "blocked_reason" not in normalised:
            normalised["blocked_reason"] = ""
            changed = True
        justifications = normalised.get("justifications")
        if not isinstance(justifications, list):
            normalised["justifications"] = []
            changed = True
        return normalised, changed

    def _normalize_agent_store(
        self, payload: dict[str, Any] | None
    ) -> tuple[dict[str, Any], bool]:
        if not isinstance(payload, dict):
            return json.loads(json.dumps(DATASET_STORE_DEFAULT)), True

        agents = payload.get("agents")
        changed = False
        if isinstance(agents, dict):
            store = {
                "agents": {},
                "last_modified": payload.get("last_modified"),
            }
            for raw_agent_id, raw_record in agents.items():
                if not isinstance(raw_agent_id, str):
                    changed = True
                    continue
                if not isinstance(raw_record, dict):
                    record = self._empty_agent_record(raw_agent_id)
                    changed = True
                else:
                    record, record_changed = self._normalize_agent_record(
                        raw_agent_id, raw_record
                    )
                    if record_changed:
                        changed = True
                store["agents"][raw_agent_id] = record
            if store.get("last_modified") is None:
                store["last_modified"] = payload.get("last_modified") or _utc_timestamp()
                changed = True
            return store, changed

        dataset = payload.get("dataset")
        if dataset is not None:
            agent_id = str(payload.get("agent_id") or "legacy")
            record = self._empty_agent_record(agent_id)
            record["dataset"] = dataset
            record["saved_at"] = payload.get("saved_at") or _utc_timestamp()
            self._append_justification(
                record,
                "migrate",
                "Migrated from legacy single-dataset store.",
            )
            store = {
                "agents": {agent_id: record},
                "last_modified": _utc_timestamp(),
            }
            return store, True

        return json.loads(json.dumps(DATASET_STORE_DEFAULT)), False

    def _persist_agent_store(self, store: dict[str, Any]) -> None:
        timestamp = _utc_timestamp()
        store["last_modified"] = timestamp
        payload = json.loads(json.dumps(store))
        self._encrypt_json(CLOUD_EDUCATE_PATH, payload)

    def _load_agent_store_raw(self) -> dict[str, Any]:
        payload = self._decrypt_json(CLOUD_EDUCATE_PATH, default=DATASET_STORE_DEFAULT)
        store, changed = self._normalize_agent_store(payload)
        if changed:
            self._persist_agent_store(store)
        return store

    def _resolve_dataset_agent_id(
        self,
        dataset: Mapping[str, Any] | None,
        *,
        default: str | None = None,
    ) -> str:
        if isinstance(dataset, Mapping):
            identity = dataset.get("agent_identity")
            if isinstance(identity, Mapping):
                candidate_identifier = identity.get("identifier")
                if isinstance(candidate_identifier, str) and candidate_identifier.strip():
                    return candidate_identifier.strip().lower()
                fallback_parts: list[str] = []
                for key in ("first_name", "last_name"):
                    raw_value = identity.get(key)
                    if isinstance(raw_value, str) and raw_value.strip():
                        fallback_parts.append(raw_value.strip().lower().replace(" ", "-"))
                if fallback_parts:
                    return "-".join(fallback_parts)
            dataset_agent = dataset.get("agent_id")
            if isinstance(dataset_agent, str) and dataset_agent.strip():
                return dataset_agent.strip().lower()
        fallback = default or self.config.get("instance_id") or self.username or "default"
        return str(fallback).strip().lower() or "default"

    def load_all_agent_datasets(self) -> dict[str, Any]:
        store = self._load_agent_store_raw()
        return json.loads(json.dumps(store))

    def get_agent_record(self, agent_id: str) -> dict[str, Any] | None:
        if not agent_id:
            raise CloudError("Agent identifier is required.")
        store = self._load_agent_store_raw()
        record = store.get("agents", {}).get(agent_id)
        if record is None:
            return None
        record, changed = self._normalize_agent_record(agent_id, record)
        if changed:
            store["agents"][agent_id] = record
            self._persist_agent_store(store)
        return json.loads(json.dumps(record))

    def load_agent_dataset(self, agent_id: str) -> dict[str, Any] | None:
        record = self.get_agent_record(agent_id)
        if not record:
            return None
        dataset = record.get("dataset")
        if dataset is None:
            return None
        return json.loads(json.dumps(dataset))

    def ensure_agent_allowed(self, agent_id: str) -> dict[str, Any] | None:
        record = self.get_agent_record(agent_id)
        if record and record.get("blocked"):
            reason = record.get("blocked_reason") or "Uploads for this agent are currently suspended."
            raise AgentBlockedError(f"Agent {agent_id} is blocked: {reason}")
        return record

    def save_agent_dataset(
        self,
        agent_id: str,
        dataset: dict[str, Any],
        *,
        justification: str | None = None,
    ) -> dict[str, Any]:
        if not agent_id:
            raise CloudError("Agent identifier is required to store a dataset.")
        if not isinstance(dataset, dict):
            raise CloudError("Agent datasets must be provided as dictionaries.")
        self.ensure_agent_allowed(agent_id)
        store = self._load_agent_store_raw()
        agents = store.setdefault("agents", {})
        record = agents.get(agent_id)
        if not isinstance(record, dict):
            record = self._empty_agent_record(agent_id)
        else:
            record, changed = self._normalize_agent_record(agent_id, record)
            if changed:
                agents[agent_id] = record
        record["dataset"] = json.loads(json.dumps(dataset))
        record["saved_at"] = _utc_timestamp()
        self._append_justification(record, "upload", justification or "Uploaded dataset.")
        agents[agent_id] = record
        self._persist_agent_store(store)
        return json.loads(json.dumps(record))

    def save_ai_dataset(
        self,
        dataset: dict[str, Any],
        *,
        agent_id: str | None = None,
        justification: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(dataset, dict):
            raise CloudError("AI datasets must be provided as dictionaries.")
        target_agent = agent_id or self._resolve_dataset_agent_id(dataset, default=self.username)
        if not target_agent:
            raise CloudError("Agent identifier is required to store the dataset.")
        return self.save_agent_dataset(target_agent, dataset, justification=justification)

    def delete_agent_dataset(self, agent_id: str, *, justification: str) -> dict[str, Any]:
        if not agent_id:
            raise CloudError("Agent identifier is required to delete a dataset.")
        if not justification.strip():
            raise CloudError("Provide a justification for deleting an agent dataset.")
        store = self._load_agent_store_raw()
        agents = store.setdefault("agents", {})
        record = agents.get(agent_id)
        if not isinstance(record, dict):
            raise CloudError(f"Agent {agent_id} does not have a dataset to delete.")
        record, _ = self._normalize_agent_record(agent_id, record)
        record["dataset"] = None
        record["saved_at"] = None
        self._append_justification(record, "delete", justification)
        agents[agent_id] = record
        self._persist_agent_store(store)
        return json.loads(json.dumps(record))

    def merge_agent_datasets(
        self,
        target_agent_id: str,
        source_agent_ids: Iterable[str],
        *,
        justification: str,
    ) -> dict[str, Any]:
        if not target_agent_id:
            raise CloudError("Target agent is required for a merge operation.")
        sources = [agent for agent in set(source_agent_ids) if agent and agent != target_agent_id]
        if not sources:
            raise CloudError("Select at least one source agent to merge.")
        if not justification.strip():
            raise CloudError("Provide a justification explaining the merge.")

        store = self._load_agent_store_raw()
        agents = store.setdefault("agents", {})

        target_record = agents.get(target_agent_id)
        if not isinstance(target_record, dict):
            target_record = self._empty_agent_record(target_agent_id)
        else:
            target_record, changed = self._normalize_agent_record(target_agent_id, target_record)
            if changed:
                agents[target_agent_id] = target_record

        merged_dataset = {}
        if isinstance(target_record.get("dataset"), dict):
            merged_dataset = json.loads(json.dumps(target_record["dataset"]))

        merged_cases: list[dict[str, Any]] = []
        seen_keys: set[tuple[str | None, str | None]] = set()

        def _extend_cases(record: dict[str, Any]) -> None:
            dataset = record.get("dataset") if isinstance(record, dict) else None
            if not isinstance(dataset, dict):
                return
            cases = dataset.get("cases")
            if not isinstance(cases, list):
                return
            for case in cases:
                if not isinstance(case, dict):
                    continue
                case_id = case.get("case_id")
                title = case.get("title")
                key = (str(case_id) if case_id is not None else None, str(title) if title is not None else None)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                merged_cases.append(json.loads(json.dumps(case)))

        _extend_cases(target_record)
        for source_id in sources:
            record = agents.get(source_id)
            if not isinstance(record, dict):
                continue
            normalised, changed = self._normalize_agent_record(source_id, record)
            if changed:
                agents[source_id] = normalised
                record = normalised
            _extend_cases(record)
            record["dataset"] = None
            record["saved_at"] = None
            self._append_justification(
                record,
                "merged", 
                f"Merged into {target_agent_id}. {justification}".strip()
            )
            agents[source_id] = record

        merged_dataset["cases"] = merged_cases
        target_record["dataset"] = merged_dataset
        target_record["saved_at"] = _utc_timestamp()
        self._append_justification(
            target_record,
            "merge",
            justification,
        )
        agents[target_agent_id] = target_record
        self._persist_agent_store(store)
        return json.loads(json.dumps(target_record))

    def set_agent_block_status(
        self,
        agent_id: str,
        *,
        blocked: bool,
        justification: str,
    ) -> dict[str, Any]:
        if not agent_id:
            raise CloudError("Agent identifier is required to update block status.")
        if blocked and not justification.strip():
            raise CloudError("Provide a justification when suspending uploads for an agent.")
        store = self._load_agent_store_raw()
        agents = store.setdefault("agents", {})
        record = agents.get(agent_id)
        if not isinstance(record, dict):
            record = self._empty_agent_record(agent_id)
        else:
            record, changed = self._normalize_agent_record(agent_id, record)
            if changed:
                agents[agent_id] = record
        record["blocked"] = bool(blocked)
        record["blocked_at"] = _utc_timestamp() if blocked else None
        record["blocked_reason"] = justification if blocked else ""
        action = "block" if blocked else "unblock"
        self._append_justification(record, action, justification)
        agents[agent_id] = record
        self._persist_agent_store(store)
        return json.loads(json.dumps(record))

    def update_credentials(self, new_username: str, new_password: str) -> None:
        devices_snapshot = self.load_devices()
        dataset_snapshot = self.load_all_agent_datasets()

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
        if dataset_snapshot:
            self._encrypt_json(CLOUD_EDUCATE_PATH, dataset_snapshot)

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
    "AgentBlockedError",
    "AuthenticationError",
    "CloudError",
    "CloudSession",
    "cloud_share_status",
    "CLOUD_DEVICES_PATH",
    "CLOUD_EDUCATE_PATH",
    "DEFAULT_USERNAME",
    "DEFAULT_PASSWORD",
    "DEFAULT_OVERLAY_INSTRUCTIONS",
    "DEFAULT_OVERLAY_PROVIDER",
    "ensure_cloud_share",
    "check_is_legacy_default",
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

