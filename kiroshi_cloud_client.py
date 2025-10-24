"""KiroshiCloud client service with secure storage and management tools.

This module exposes a dual interface:

* a CLI that administrators can use to register devices, manage
  credentials, control connections, and synchronise the "Educate"
  dataset that powers the on-premise Kiroshi assistant;
* an HTTP API that devices use to register/heartbeat and that the
  Streamlit-powered control surface consumes for real-time operations.

Major features compared to the first iteration include

* encrypted persistence for all device metadata using Fernet keys stored
  alongside the SQLite database,
* username/password authentication (PBKDF2-HMAC SHA256) enforced for all
  API calls,
* connection policy controls (allow, block, remove) exposed through both
  the CLI and HTTP endpoints,
* optional Tailnet (Tailscale) peer-to-peer orchestration helpers so the
  cloud can be reached across networks without manual port forwarding,
* bidirectional synchronisation hooks for the Kiroshi "Educate"
  knowledge base so support teams analyse the same dataset across the
  desktop and cloud experiences.

The design deliberately keeps dependencies minimal and cross-platform so
that the client runs on barebones Arch Linux workstations as well as
Windows 10/11 and Windows Server hosts.  When running
``python kiroshi_cloud_client.py serve`` a default ``admin`` account is
bootstrapped with a randomly generated password.  The credentials are
printed to the console so the operator can log into the web UI and
rotate them immediately.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import platform
import secrets
import shutil
import socket
import sqlite3
import subprocess
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple
from urllib.parse import urlparse

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "cryptography is required for KiroshiCloud. Install it with 'pip install cryptography'."
    ) from exc


def _resolve_storage_paths() -> tuple[Path, Path]:
    """Determine cross-platform default locations for the database and key."""

    env_home = os.environ.get("KIROSHI_CLOUD_HOME")
    candidates: list[Path] = []
    if env_home:
        candidates.append(Path(env_home))

    system = platform.system().lower()
    if system == "windows":
        program_data = os.environ.get("PROGRAMDATA")
        local_app_data = os.environ.get("LOCALAPPDATA")
        for base in filter(None, [program_data, local_app_data]):
            candidates.append(Path(base) / "KiroshiCloud")
        candidates.append(Path.home() / "AppData" / "Local" / "KiroshiCloud")
    elif system == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / "KiroshiCloud")
    else:
        xdg_home = os.environ.get("XDG_DATA_HOME")
        if xdg_home:
            candidates.append(Path(xdg_home) / "kiroshi_cloud")
        candidates.append(Path.home() / ".local" / "share" / "kiroshi_cloud")
        candidates.append(Path("/var/lib/kiroshi_cloud"))

    candidates.append(Path.cwd())

    for directory in candidates:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        db_path = directory / "kiroshi_cloud.sqlite3"
        key_path = directory / "kiroshi_cloud.key"
        return db_path, key_path

    # Final fallback to local files in the working directory.
    return Path("kiroshi_cloud.sqlite3"), Path("kiroshi_cloud.key")


env_database = os.environ.get("KIROSHI_CLOUD_DB")
env_key = os.environ.get("KIROSHI_CLOUD_KEY")

resolved_database, resolved_key = _resolve_storage_paths()

DEFAULT_DATABASE = Path(env_database) if env_database else resolved_database
DEFAULT_KEY_FILE = Path(env_key) if env_key else resolved_key


def utcnow() -> str:
    """Return the current time as an ISO-8601 string in UTC."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class EncryptionManager:
    """Wrapper around Fernet that stores the key next to the database."""

    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path
        try:
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self._fernet = self._load_or_create_key()

    def _load_or_create_key(self) -> Fernet:
        if not self.key_path.exists():
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
        else:
            key = self.key_path.read_bytes().strip()
        return Fernet(key)

    def encrypt(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        token = self._fernet.encrypt(value.encode("utf-8"))
        return f"enc:{token.decode('utf-8')}"

    def decrypt(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not value.startswith("enc:"):
            return value
        token = value[4:].encode("utf-8")
        try:
            return self._fernet.decrypt(token).decode("utf-8")
        except InvalidToken:
            return None


class PasswordHasher:
    """PBKDF2-HMAC SHA256 helper."""

    def __init__(self, iterations: int = 390_000) -> None:
        self.iterations = iterations

    def hash(self, password: str, *, salt: Optional[bytes] = None) -> Tuple[str, str]:
        salt_bytes = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt_bytes, self.iterations
        )
        return salt_bytes.hex(), digest.hex()

    def verify(self, password: str, salt_hex: str, stored_hash: str) -> bool:
        salt_bytes = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt_bytes, self.iterations
        )
        return hmac.compare_digest(digest.hex(), stored_hash)


@dataclass
class DeviceRecord:
    """In-memory representation of a stored device."""

    device_id: str
    name: Optional[str] = None
    model: Optional[str] = None
    owner: Optional[str] = None
    location: Optional[str] = None
    firmware_version: Optional[str] = None
    os_version: Optional[str] = None
    ip_address: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    last_seen: Optional[str] = None
    created_at: Optional[str] = None
    connection_status: str = "allowed"
    connection_reason: Optional[str] = None
    connection_updated_at: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectionRecord:
    """Administrative view of a device connection."""

    device_id: str
    status: str
    reason: Optional[str]
    updated_at: Optional[str]
    last_seen: Optional[str]
    name: Optional[str]
    ip_address: Optional[str]

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EducateDocument:
    """Representation of an Educate knowledge base entry."""

    doc_id: str
    title: str
    content: str
    tags: List[str]
    source: Optional[str]
    checksum: str
    updated_at: Optional[str]

    def to_json(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "source": self.source,
            "checksum": self.checksum,
            "updated_at": self.updated_at,
        }


class SecureMeshController:
    """Wrapper around the Tailscale CLI to orchestrate P2P tunnels."""

    def __init__(self, binary: str = "tailscale") -> None:
        self.binary = binary
        self.available = shutil.which(binary) is not None

    def status(self) -> Dict[str, Any]:
        if not self.available:
            return {
                "available": False,
                "message": f"{self.binary} binary not found on PATH. Install Tailscale to enable the secure mesh.",
            }
        result = subprocess.run(
            [self.binary, "status", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return {
                "available": True,
                "error": result.stderr.strip() or "tailscale status command failed",
                "returncode": result.returncode,
            }
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            payload = {"raw": result.stdout}
        payload.update({"available": True, "returncode": result.returncode})
        return payload

    def connect(self, *, auth_key: Optional[str] = None, hostname: Optional[str] = None) -> Dict[str, Any]:
        if not self.available:
            return {"available": False, "message": f"{self.binary} not found"}
        command = [self.binary, "up", "--accept-dns=false"]
        if auth_key:
            command.extend(["--authkey", auth_key])
        if hostname:
            command.extend(["--hostname", hostname])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return {
            "available": True,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    def disconnect(self) -> Dict[str, Any]:
        if not self.available:
            return {"available": False, "message": f"{self.binary} not found"}
        result = subprocess.run([self.binary, "down"], capture_output=True, text=True, check=False)
        return {
            "available": True,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }


class KiroshiCloudStore:
    """SQLite backed datastore with transparent encryption."""

    def __init__(self, database_path: Path, *, key_path: Optional[Path] = None) -> None:
        self.database_path = database_path
        resolved_key = key_path or database_path.with_suffix(".key")
        self._crypto = EncryptionManager(resolved_key)
        self._hasher = PasswordHasher()
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        self.bootstrap_credentials: Optional[Tuple[str, str]] = None
        self._initialise()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _initialise(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    name TEXT,
                    model TEXT,
                    owner TEXT,
                    location TEXT,
                    firmware_version TEXT,
                    os_version TEXT,
                    ip_address TEXT,
                    notes TEXT,
                    metadata TEXT,
                    last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS device_connections (
                    device_id TEXT PRIMARY KEY REFERENCES devices(device_id) ON DELETE CASCADE,
                    status TEXT NOT NULL DEFAULT 'allowed',
                    reason TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS account (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS educate_documents (
                    doc_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT,
                    source TEXT,
                    checksum TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            self._connection.commit()
            self._ensure_default_account()

    def _ensure_default_account(self) -> None:
        existing = self._connection.execute("SELECT COUNT(*) FROM account").fetchone()[0]
        if existing:
            return
        username = "admin"
        password = secrets.token_urlsafe(12)
        salt_hex, password_hash = self._hasher.hash(password)
        now = utcnow()
        self._connection.execute(
            """
            INSERT INTO account (username, password_hash, salt, is_default, created_at, updated_at)
            VALUES (:username, :password_hash, :salt, 1, :now, :now)
            """,
            {
                "username": username,
                "password_hash": password_hash,
                "salt": salt_hex,
                "now": now,
            },
        )
        self._connection.commit()
        self.bootstrap_credentials = (username, password)

    def upsert_device(self, record: DeviceRecord) -> DeviceRecord:
        now = utcnow()
        payload = {
            "device_id": record.device_id,
            "name": self._crypto.encrypt(record.name),
            "model": self._crypto.encrypt(record.model),
            "owner": self._crypto.encrypt(record.owner),
            "location": self._crypto.encrypt(record.location),
            "firmware_version": self._crypto.encrypt(record.firmware_version),
            "os_version": self._crypto.encrypt(record.os_version),
            "ip_address": self._crypto.encrypt(record.ip_address),
            "notes": self._crypto.encrypt(record.notes),
            "metadata": self._encrypt_json(record.metadata),
            "last_seen": record.last_seen or now,
            "created_at": record.created_at or now,
        }
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO devices (
                    device_id, name, model, owner, location,
                    firmware_version, os_version, ip_address, notes,
                    metadata, last_seen, created_at
                ) VALUES (
                    :device_id, :name, :model, :owner, :location,
                    :firmware_version, :os_version, :ip_address, :notes,
                    :metadata, :last_seen, COALESCE(
                        (SELECT created_at FROM devices WHERE device_id = :device_id),
                        :created_at
                    )
                )
                ON CONFLICT(device_id) DO UPDATE SET
                    name=excluded.name,
                    model=excluded.model,
                    owner=excluded.owner,
                    location=excluded.location,
                    firmware_version=excluded.firmware_version,
                    os_version=excluded.os_version,
                    ip_address=excluded.ip_address,
                    notes=excluded.notes,
                    metadata=excluded.metadata,
                    last_seen=excluded.last_seen
                """,
                payload,
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO device_connections (device_id, status, reason, updated_at)
                VALUES (:device_id, 'allowed', NULL, :now)
                """,
                {"device_id": record.device_id, "now": now},
            )
            self._connection.commit()
        device = self.fetch_device(record.device_id)
        assert device is not None
        return device

    def record_heartbeat(self, device_id: str) -> Optional[DeviceRecord]:
        now = utcnow()
        with self._lock:
            cursor = self._connection.execute(
                "UPDATE devices SET last_seen = :now WHERE device_id = :device_id",
                {"now": now, "device_id": device_id},
            )
            if cursor.rowcount == 0:
                return None
            self._connection.commit()
        return self.fetch_device(device_id)

    def fetch_device(self, device_id: str) -> Optional[DeviceRecord]:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT d.*, c.status AS connection_status, c.reason AS connection_reason,
                       c.updated_at AS connection_updated_at
                FROM devices AS d
                LEFT JOIN device_connections AS c ON d.device_id = c.device_id
                WHERE d.device_id = :device_id
                """,
                {"device_id": device_id},
            ).fetchone()
        return self._row_to_device(row)

    def iter_devices(self) -> Iterator[DeviceRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT d.*, c.status AS connection_status, c.reason AS connection_reason,
                       c.updated_at AS connection_updated_at
                FROM devices AS d
                LEFT JOIN device_connections AS c ON d.device_id = c.device_id
                ORDER BY d.last_seen DESC
                """
            ).fetchall()
        for row in rows:
            record = self._row_to_device(row)
            if record:
                yield record

    def set_connection_status(self, device_id: str, status: str, *, reason: Optional[str] = None) -> bool:
        status = status.lower()
        if status not in {"allowed", "blocked"}:
            raise ValueError("status must be 'allowed' or 'blocked'")
        now = utcnow()
        with self._lock:
            exists = self._connection.execute(
                "SELECT 1 FROM devices WHERE device_id = :device_id",
                {"device_id": device_id},
            ).fetchone()
            if exists is None:
                return False
            cursor = self._connection.execute(
                """
                INSERT INTO device_connections (device_id, status, reason, updated_at)
                VALUES (:device_id, :status, :reason, :now)
                ON CONFLICT(device_id) DO UPDATE SET
                    status=excluded.status,
                    reason=excluded.reason,
                    updated_at=excluded.updated_at
                """,
                {
                    "device_id": device_id,
                    "status": status,
                    "reason": reason,
                    "now": now,
                },
            )
            if cursor.rowcount == 0:
                return False
            self._connection.commit()
        return True

    def remove_device(self, device_id: str) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM devices WHERE device_id = :device_id", {"device_id": device_id}
            )
            removed = cursor.rowcount > 0
            if removed:
                self._connection.execute(
                    "DELETE FROM device_connections WHERE device_id = :device_id",
                    {"device_id": device_id},
                )
            self._connection.commit()
        return removed

    def list_connections(self) -> List[ConnectionRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT d.device_id, d.name, d.ip_address, d.last_seen,
                       c.status, c.reason, c.updated_at
                FROM devices AS d
                LEFT JOIN device_connections AS c ON d.device_id = c.device_id
                ORDER BY c.status DESC, d.device_id ASC
                """
            ).fetchall()
        records = []
        for row in rows:
            records.append(
                ConnectionRecord(
                    device_id=row["device_id"],
                    status=(row["status"] or "allowed"),
                    reason=row["reason"],
                    updated_at=row["updated_at"],
                    last_seen=row["last_seen"],
                    name=self._crypto.decrypt(row["name"]),
                    ip_address=self._crypto.decrypt(row["ip_address"]),
                )
            )
        return records

    def is_device_allowed(self, device_id: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT status FROM device_connections WHERE device_id = :device_id",
                {"device_id": device_id},
            ).fetchone()
        if row is None:
            return True
        return (row["status"] or "allowed").lower() == "allowed"

    def verify_credentials(self, username: str, password: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT password_hash, salt FROM account WHERE username = :username",
                {"username": username},
            ).fetchone()
        if row is None:
            return False
        return self._hasher.verify(password, row["salt"], row["password_hash"])

    def get_account_username(self) -> Optional[str]:
        with self._lock:
            row = self._connection.execute(
                "SELECT username FROM account ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        return row["username"] if row else None

    def set_credentials(self, username: str, password: str) -> None:
        salt_hex, password_hash = self._hasher.hash(password)
        now = utcnow()
        with self._lock:
            self._connection.execute("DELETE FROM account")
            self._connection.execute(
                """
                INSERT INTO account (username, password_hash, salt, is_default, created_at, updated_at)
                VALUES (:username, :password_hash, :salt, 0, :now, :now)
                """,
                {
                    "username": username,
                    "password_hash": password_hash,
                    "salt": salt_hex,
                    "now": now,
                },
            )
            self._connection.commit()

    def sync_educate_documents(self, documents: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        stats = {"updated": 0, "skipped": 0}
        with self._lock:
            for doc in documents:
                if not isinstance(doc, dict):
                    continue
                title = str(doc.get("title", "")).strip()
                content = str(doc.get("content", ""))
                tags = doc.get("tags")
                if not title and not content:
                    continue
                doc_id = doc.get("doc_id") or hashlib.sha256(
                    (title + content).encode("utf-8")
                ).hexdigest()
                checksum = hashlib.sha256(
                    json.dumps({"title": title, "content": content, "tags": tags}, sort_keys=True).encode("utf-8")
                ).hexdigest()
                existing = self._connection.execute(
                    "SELECT checksum FROM educate_documents WHERE doc_id = :doc_id",
                    {"doc_id": doc_id},
                ).fetchone()
                if existing and existing["checksum"] == checksum:
                    stats["skipped"] += 1
                    continue
                now = utcnow()
                payload = {
                    "doc_id": doc_id,
                    "title": self._crypto.encrypt(title),
                    "content": self._crypto.encrypt(content),
                    "tags": self._encrypt_json(tags if isinstance(tags, list) else []),
                    "source": self._crypto.encrypt(str(doc.get("source") or "manual")),
                    "checksum": checksum,
                    "updated_at": now,
                }
                self._connection.execute(
                    """
                    INSERT INTO educate_documents (doc_id, title, content, tags, source, checksum, updated_at)
                    VALUES (:doc_id, :title, :content, :tags, :source, :checksum, :updated_at)
                    ON CONFLICT(doc_id) DO UPDATE SET
                        title=excluded.title,
                        content=excluded.content,
                        tags=excluded.tags,
                        source=excluded.source,
                        checksum=excluded.checksum,
                        updated_at=excluded.updated_at
                    """,
                    payload,
                )
                stats["updated"] += 1
            self._connection.commit()
        return stats

    def iter_educate_documents(self) -> Iterator[EducateDocument]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM educate_documents ORDER BY title ASC"
            ).fetchall()
        for row in rows:
            title = self._crypto.decrypt(row["title"]) or ""
            content = self._crypto.decrypt(row["content"]) or ""
            tags_json = self._decrypt_json(row["tags"]) or []
            source = self._crypto.decrypt(row["source"]) if row["source"] else None
            yield EducateDocument(
                doc_id=row["doc_id"],
                title=title,
                content=content,
                tags=tags_json,
                source=source,
                checksum=row["checksum"],
                updated_at=row["updated_at"],
            )

    def _encrypt_json(self, payload: Any) -> Optional[str]:
        if payload is None:
            return None
        return self._crypto.encrypt(json.dumps(payload, sort_keys=True))

    def _decrypt_json(self, payload: Optional[str]) -> Optional[Any]:
        if payload is None:
            return None
        decoded = self._crypto.decrypt(payload)
        if decoded is None:
            return None
        try:
            return json.loads(decoded)
        except json.JSONDecodeError:
            return None

    def _row_to_device(self, row: Optional[sqlite3.Row]) -> Optional[DeviceRecord]:
        if row is None:
            return None
        metadata = self._decrypt_json(row["metadata"])
        return DeviceRecord(
            device_id=row["device_id"],
            name=self._crypto.decrypt(row["name"]),
            model=self._crypto.decrypt(row["model"]),
            owner=self._crypto.decrypt(row["owner"]),
            location=self._crypto.decrypt(row["location"]),
            firmware_version=self._crypto.decrypt(row["firmware_version"]),
            os_version=self._crypto.decrypt(row["os_version"]),
            ip_address=self._crypto.decrypt(row["ip_address"]),
            notes=self._crypto.decrypt(row["notes"]),
            metadata=metadata,
            last_seen=row["last_seen"],
            created_at=row["created_at"],
            connection_status=(row["connection_status"] or "allowed"),
            connection_reason=row["connection_reason"],
            connection_updated_at=row["connection_updated_at"],
        )


class _RequestHandler(BaseHTTPRequestHandler):
    """HTTP handler that exposes JSON endpoints with Basic auth."""

    server_version = "KiroshiCloud/2.0"

    @property
    def store(self) -> KiroshiCloudStore:
        return self.server.store  # type: ignore[attr-defined]

    @property
    def mesh(self) -> SecureMeshController:
        return self.server.mesh  # type: ignore[attr-defined]

    def _set_headers(self, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, Accept, Authorization"
        )

    def _json_response(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        self._set_headers(status)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _parse_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _extract_credentials(self) -> Optional[Tuple[str, str]]:
        header = self.headers.get("Authorization")
        if not header or not header.startswith("Basic "):
            return None
        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8")
        except Exception:
            return None
        if ":" not in decoded:
            return None
        username, password = decoded.split(":", 1)
        return username, password

    def _ensure_authenticated(self) -> bool:
        credentials = self._extract_credentials()
        if not credentials or not self.store.verify_credentials(*credentials):
            self._set_headers(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", 'Basic realm="KiroshiCloud"')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid_credentials"}).encode("utf-8"))
            return False
        return True

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._set_headers(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json_response({"status": "ok"})
            return
        if not self._ensure_authenticated():
            return
        if parsed.path == "/devices":
            devices = [device.to_json() for device in self.store.iter_devices()]
            self._json_response({"devices": devices})
            return
        if parsed.path.startswith("/devices/"):
            device_id = parsed.path.split("/", maxsplit=2)[-1]
            device = self.store.fetch_device(device_id)
            if device is None:
                self._json_response({"error": "device_not_found", "device_id": device_id}, HTTPStatus.NOT_FOUND)
                return
            self._json_response(device.to_json())
            return
        if parsed.path == "/connections":
            connections = [record.to_json() for record in self.store.list_connections()]
            self._json_response({"connections": connections})
            return
        if parsed.path == "/settings/credentials":
            username = self.store.get_account_username()
            self._json_response({"username": username})
            return
        if parsed.path == "/educate":
            documents = [doc.to_json() for doc in self.store.iter_educate_documents()]
            self._json_response({"documents": documents})
            return
        if parsed.path == "/p2p/status":
            self._json_response(self.mesh.status())
            return
        self._json_response({"error": "unknown_endpoint", "path": parsed.path}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not self._ensure_authenticated():
            return
        if parsed.path == "/devices":
            self._handle_register_device()
            return
        if parsed.path.startswith("/devices/") and parsed.path.endswith("/heartbeat"):
            device_id = parsed.path.split("/")[-2]
            if not self.store.is_device_allowed(device_id):
                self._json_response({"error": "device_blocked", "device_id": device_id}, HTTPStatus.FORBIDDEN)
                return
            device = self.store.record_heartbeat(device_id)
            if device is None:
                self._json_response({"error": "device_not_found", "device_id": device_id}, HTTPStatus.NOT_FOUND)
                return
            self._json_response(device.to_json())
            return
        if parsed.path.startswith("/devices/"):
            device_id = parsed.path.split("/", maxsplit=2)[-1]
            self._handle_register_device(device_id)
            return
        if parsed.path.startswith("/connections/") and parsed.path.endswith("/allow"):
            device_id = parsed.path.split("/")[-2]
            success = self.store.set_connection_status(device_id, "allowed")
            status = HTTPStatus.OK if success else HTTPStatus.NOT_FOUND
            self._json_response({"device_id": device_id, "status": "allowed"}, status)
            return
        if parsed.path.startswith("/connections/") and parsed.path.endswith("/block"):
            device_id = parsed.path.split("/")[-2]
            payload = self._parse_json_body()
            reason = payload.get("reason") if isinstance(payload, dict) else None
            success = self.store.set_connection_status(device_id, "blocked", reason=reason)
            status = HTTPStatus.OK if success else HTTPStatus.NOT_FOUND
            self._json_response(
                {"device_id": device_id, "status": "blocked", "reason": reason}, status
            )
            return
        if parsed.path == "/educate/sync":
            payload = self._parse_json_body()
            documents = payload.get("documents") if isinstance(payload, dict) else None
            if not isinstance(documents, list):
                self._json_response({"error": "documents_must_be_list"}, HTTPStatus.BAD_REQUEST)
                return
            stats = self.store.sync_educate_documents(documents)
            self._json_response({"status": "ok", "stats": stats})
            return
        if parsed.path == "/p2p/connect":
            payload = self._parse_json_body()
            result = self.mesh.connect(
                auth_key=(payload or {}).get("auth_key"),
                hostname=(payload or {}).get("hostname"),
            )
            self._json_response(result)
            return
        if parsed.path == "/p2p/disconnect":
            self._json_response(self.mesh.disconnect())
            return
        self._json_response({"error": "unknown_endpoint", "path": parsed.path}, HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:  # noqa: N802
        if not self._ensure_authenticated():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/settings/credentials":
            payload = self._parse_json_body()
            username = (payload or {}).get("username")
            password = (payload or {}).get("password")
            if not username or not password:
                self._json_response({"error": "username_and_password_required"}, HTTPStatus.BAD_REQUEST)
                return
            self.store.set_credentials(str(username), str(password))
            self._json_response({"status": "ok"})
            return
        self._json_response({"error": "unknown_endpoint", "path": parsed.path}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._ensure_authenticated():
            return
        parsed = urlparse(self.path)
        if parsed.path.startswith("/connections/"):
            device_id = parsed.path.split("/", maxsplit=2)[-1]
            removed = self.store.remove_device(device_id)
            status = HTTPStatus.OK if removed else HTTPStatus.NOT_FOUND
            self._json_response({"device_id": device_id, "removed": removed}, status)
            return
        self._json_response({"error": "unknown_endpoint", "path": parsed.path}, HTTPStatus.NOT_FOUND)

    def _handle_register_device(self, device_id_override: Optional[str] = None) -> None:
        payload = self._parse_json_body()
        payload.setdefault("device_id", device_id_override)
        device_id = payload.get("device_id")
        if not device_id:
            self._json_response({"error": "missing_device_id"}, HTTPStatus.BAD_REQUEST)
            return
        if not self.store.is_device_allowed(device_id):
            self._json_response({"error": "device_blocked", "device_id": device_id}, HTTPStatus.FORBIDDEN)
            return
        metadata = payload.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            self._json_response({"error": "metadata_must_be_object"}, HTTPStatus.BAD_REQUEST)
            return
        record = DeviceRecord(
            device_id=str(device_id),
            name=payload.get("name"),
            model=payload.get("model"),
            owner=payload.get("owner"),
            location=payload.get("location"),
            firmware_version=payload.get("firmware_version"),
            os_version=payload.get("os_version"),
            ip_address=payload.get("ip_address"),
            notes=payload.get("notes"),
            metadata=metadata,
            last_seen=payload.get("last_seen") or utcnow(),
        )
        device = self.store.upsert_device(record)
        self._json_response(device.to_json(), HTTPStatus.CREATED)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - BaseHTTPRequestHandler API
        message = "%s - - [%s] %s\n" % (
            self.address_string(),
            self.log_date_time_string(),
            format % args,
        )
        print(message, end="")


class KiroshiCloudServer(ThreadingHTTPServer):
    """Threading HTTP server that exposes the KiroshiCloud API."""

    def __init__(self, address: Tuple[str, int], store: KiroshiCloudStore, mesh: SecureMeshController) -> None:
        self.store = store
        self.mesh = mesh
        super().__init__(address, _RequestHandler)


def gather_local_device_profile() -> Dict[str, Any]:
    """Collect a best-effort snapshot of the current machine."""

    hostname = socket.gethostname()
    ip_address = _detect_ip_address()
    return {
        "name": hostname,
        "model": platform.machine(),
        "os_version": f"{platform.system()} {platform.release()}",
        "firmware_version": platform.version(),
        "ip_address": ip_address,
        "metadata": {
            "python_version": platform.python_version(),
            "architecture": platform.platform(),
        },
        "last_seen": utcnow(),
    }


def _detect_ip_address() -> Optional[str]:
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KiroshiCloud client utility")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help="Path to the SQLite database (default: %(default)s; override with KIROSHI_CLOUD_HOME)",
    )
    parser.add_argument(
        "--key-file",
        type=Path,
        default=DEFAULT_KEY_FILE,
        help="Path to the Fernet key file (default: %(default)s; override with KIROSHI_CLOUD_HOME)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the HTTP API service")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    serve_parser.add_argument("--port", type=int, default=8050, help="Listen port")

    register_parser = subparsers.add_parser(
        "register", help="Register or update a device record"
    )
    _add_device_arguments(register_parser)

    heartbeat_parser = subparsers.add_parser(
        "heartbeat", help="Update the last_seen timestamp for a device"
    )
    heartbeat_parser.add_argument("device_id", help="Device identifier")

    list_parser = subparsers.add_parser("list", help="List devices in the database")
    list_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for the device list",
    )

    connections_parser = subparsers.add_parser("connections", help="List connection policies")
    connections_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the connection table as JSON",
    )

    allow_parser = subparsers.add_parser("allow", help="Allow a device to connect")
    allow_parser.add_argument("device_id", help="Device identifier")

    block_parser = subparsers.add_parser("block", help="Block a device from connecting")
    block_parser.add_argument("device_id", help="Device identifier")
    block_parser.add_argument("--reason", help="Optional reason shown in the UI")

    remove_parser = subparsers.add_parser("remove", help="Remove a device from the database")
    remove_parser.add_argument("device_id", help="Device identifier")

    creds_parser = subparsers.add_parser("set-credentials", help="Update the cloud login")
    creds_parser.add_argument("--username", help="Username for the cloud account")
    creds_parser.add_argument(
        "--password",
        help="Password for the cloud account (omit to be prompted securely)",
    )

    subparsers.add_parser("show-credentials", help="Display the current username")

    educate_parser = subparsers.add_parser(
        "sync-educate", help="Push the local Kiroshi Educate dataset into the cloud"
    )
    educate_parser.add_argument(
        "--source",
        type=Path,
        help="Optional path to a JSON file. Default uses the desktop Kiroshi dataset.",
    )

    export_parser = subparsers.add_parser(
        "export-educate", help="Export the cloud Educate dataset to the desktop"
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON file destination. Default writes via the desktop app helpers.",
    )

    subparsers.add_parser("p2p-status", help="Show the secure mesh status")

    p2p_connect = subparsers.add_parser("p2p-connect", help="Bring the secure mesh online")
    p2p_connect.add_argument("--auth-key", help="Optional Tailscale auth key")
    p2p_connect.add_argument("--hostname", help="Override the node hostname")

    subparsers.add_parser("p2p-disconnect", help="Tear down the secure mesh")

    self_parser = subparsers.add_parser(
        "register-self",
        help="Collect local system details and register them as a device",
    )
    self_parser.add_argument(
        "--device-id",
        required=True,
        help="Device identifier for the current machine",
    )
    _add_device_arguments(self_parser, include_optional_defaults=False)

    return parser


def _add_device_arguments(
    parser: argparse.ArgumentParser, *, include_optional_defaults: bool = True
) -> None:
    if include_optional_defaults:
        parser.add_argument("--device-id", required=True, help="Device identifier")
    parser.add_argument("--name", help="Friendly device name")
    parser.add_argument("--model", help="Device model")
    parser.add_argument("--owner", help="Owner or department")
    parser.add_argument("--location", help="Physical location")
    parser.add_argument("--firmware-version", help="Firmware revision")
    parser.add_argument("--os-version", help="Operating system version")
    parser.add_argument("--ip-address", help="IP address of the device")
    parser.add_argument("--notes", help="Additional notes")
    parser.add_argument(
        "--metadata",
        help='Extra metadata as JSON (for example \'{"serial": "12345"}\')',
    )
    if include_optional_defaults:
        parser.add_argument(
            "--last-seen",
            help="Optional ISO timestamp; defaults to the current time",
        )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command.startswith("p2p"):
        mesh = SecureMeshController()
        if args.command == "p2p-status":
            print(json.dumps(mesh.status(), indent=2))
            return 0
        if args.command == "p2p-connect":
            result = mesh.connect(auth_key=args.auth_key, hostname=args.hostname)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "p2p-disconnect":
            print(json.dumps(mesh.disconnect(), indent=2))
            return 0

    store = KiroshiCloudStore(args.database, key_path=args.key_file)

    if args.command == "serve":
        mesh = SecureMeshController()
        server = KiroshiCloudServer((args.host, args.port), store, mesh)
        if store.bootstrap_credentials:
            username, password = store.bootstrap_credentials
            print("Default KiroshiCloud credentials created:")
            print(f"  username: {username}")
            print(f"  password: {password}")
            print("Update them from the UI or via 'set-credentials' immediately.")
        try:
            print(f"KiroshiCloud service listening on http://{args.host}:{args.port}")
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            server.server_close()
            store.close()
        return 0

    try:
        if args.command == "register":
            metadata = _load_metadata(args.metadata)
            record = DeviceRecord(
                device_id=args.device_id,
                name=args.name,
                model=args.model,
                owner=args.owner,
                location=args.location,
                firmware_version=args.firmware_version,
                os_version=args.os_version,
                ip_address=args.ip_address,
                notes=args.notes,
                metadata=metadata,
                last_seen=args.last_seen or utcnow(),
            )
            device = store.upsert_device(record)
            print(json.dumps(device.to_json(), indent=2))
            return 0

        if args.command == "heartbeat":
            if not store.is_device_allowed(args.device_id):
                print(f"Device '{args.device_id}' is blocked", flush=True)
                return 2
            device = store.record_heartbeat(args.device_id)
            if device is None:
                print(f"Device '{args.device_id}' does not exist", flush=True)
                return 1
            print(json.dumps(device.to_json(), indent=2))
            return 0

        if args.command == "list":
            devices = [device.to_json() for device in store.iter_devices()]
            if args.format == "json":
                print(json.dumps({"devices": devices}, indent=2))
            else:
                _print_table(devices)
            return 0

        if args.command == "connections":
            connections = [record.to_json() for record in store.list_connections()]
            if args.json:
                print(json.dumps({"connections": connections}, indent=2))
            else:
                display_rows = [
                    {
                        "Device ID": row.get("device_id", ""),
                        "Status": row.get("status", ""),
                        "Reason": row.get("reason", ""),
                        "Updated": row.get("updated_at", ""),
                        "Last Seen": row.get("last_seen", ""),
                        "Name": row.get("name", ""),
                        "IP": row.get("ip_address", ""),
                    }
                    for row in connections
                ]
                _print_table(
                    display_rows,
                    headers=("Device ID", "Status", "Reason", "Updated", "Last Seen", "Name", "IP"),
                )
            return 0

        if args.command == "allow":
            if store.set_connection_status(args.device_id, "allowed"):
                print(f"Device '{args.device_id}' marked as allowed")
                return 0
            print(f"Device '{args.device_id}' not found")
            return 1

        if args.command == "block":
            if store.set_connection_status(args.device_id, "blocked", reason=args.reason):
                print(f"Device '{args.device_id}' blocked")
                return 0
            print(f"Device '{args.device_id}' not found")
            return 1

        if args.command == "remove":
            if store.remove_device(args.device_id):
                print(f"Device '{args.device_id}' removed")
                return 0
            print(f"Device '{args.device_id}' not found")
            return 1

        if args.command == "set-credentials":
            username = args.username or input("New username: ")
            password = args.password or getpass.getpass("New password: ")
            store.set_credentials(username, password)
            print("Credentials updated.")
            return 0

        if args.command == "show-credentials":
            username = store.get_account_username()
            print(json.dumps({"username": username}, indent=2))
            return 0

        if args.command == "sync-educate":
            documents = _load_local_educate(args.source)
            stats = store.sync_educate_documents(documents)
            print(json.dumps({"status": "ok", "stats": stats}, indent=2))
            return 0

        if args.command == "export-educate":
            documents = [doc.to_json() for doc in store.iter_educate_documents()]
            _export_educate(documents, args.output)
            print(json.dumps({"status": "ok", "documents": len(documents)}, indent=2))
            return 0

        parser.error("Unknown command")
        return 1
    finally:
        store.close()


def _load_metadata(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse metadata JSON: {exc}") from exc
    if not isinstance(metadata, dict):
        raise SystemExit("Metadata must be a JSON object")
    return metadata


def _print_table(records: Iterable[Dict[str, Any]], headers: Optional[Tuple[str, ...]] = None) -> None:
    record_list = list(records)
    if headers is None:
        headers = tuple(record_list[0].keys()) if record_list else ()

    if not headers:
        print("(no data)")
        return

    rows = [tuple(headers)]
    for record in record_list:
        rows.append(tuple(str(record.get(key, "")) for key in headers))

    column_widths = [max(len(str(row[idx])) for row in rows) for idx in range(len(headers))]

    def format_row(row: Iterable[str]) -> str:
        return " | ".join(str(value).ljust(column_widths[idx]) for idx, value in enumerate(row))

    separator = "-+-".join("-" * width for width in column_widths)

    print(format_row(headers))
    print(separator)
    for row in rows[1:]:
        print(format_row(row))


def _load_local_educate(source: Optional[Path]) -> List[Dict[str, Any]]:
    if source:
        data = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [doc for doc in data if isinstance(doc, dict)]
        raise SystemExit("Educate source must be a JSON array")
    try:
        from kiroshi_chat import load_manual_docs  # type: ignore import-outside-toplevel
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise SystemExit(f"Unable to load desktop Educate dataset: {exc}") from exc
    return [doc for doc in load_manual_docs() if isinstance(doc, dict)]


def _export_educate(documents: List[Dict[str, Any]], destination: Optional[Path]) -> None:
    if destination:
        destination.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    try:
        from kiroshi_chat import save_manual_docs  # type: ignore import-outside-toplevel
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise SystemExit(f"Unable to persist desktop Educate dataset: {exc}") from exc
    save_manual_docs(documents)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

