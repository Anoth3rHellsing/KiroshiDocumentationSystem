"""Lightweight shim of the :mod:`responses` API for the test suite."""

from __future__ import annotations

import json
from contextlib import ContextDecorator
from functools import wraps
from dataclasses import dataclass
from typing import Any

import requests

GET = "GET"
_active_stack: list["Mocker"] = []


@dataclass
class _MockResponse:
    method: str
    url: str
    status: int
    body: bytes

    @classmethod
    def from_kwargs(
        cls,
        method: str,
        url: str,
        *,
        json_data: Any | None,
        body: Any,
        status: int,
    ) -> "_MockResponse":
        if json_data is not None:
            payload = json.dumps(json_data).encode("utf-8")
        elif body is None:
            payload = b""
        elif isinstance(body, bytes):
            payload = body
        else:
            payload = str(body).encode("utf-8")
        return cls(method.upper(), url, status, payload)

    def build_response(self, method: str, url: str) -> requests.Response:
        response = requests.Response()
        response.status_code = self.status
        response.url = url
        response._content = self.body  # type: ignore[attr-defined]
        response.request = requests.Request(method=method, url=url).prepare()
        if self.body and self.body.lstrip().startswith((b"{", b"[")):
            response.headers["Content-Type"] = "application/json"
        return response


class Mocker(ContextDecorator):
    def __enter__(self) -> "Mocker":
        self._registry: list[_MockResponse] = []
        self._original_request = requests.sessions.Session.request

        def _mock_request(session, method, url, **kwargs):  # type: ignore[override]
            for entry in self._registry:
                if entry.method == method.upper() and entry.url == url:
                    return entry.build_response(method, url)
            raise AssertionError(f"No mock registered for {method} {url}")

        requests.sessions.Session.request = _mock_request  # type: ignore[assignment]
        _active_stack.append(self)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        requests.sessions.Session.request = self._original_request  # type: ignore[assignment]
        _active_stack.pop()
        self._registry.clear()

    def add(self, method: str, url: str, *, json=None, body=None, status=200) -> None:  # noqa: A002 - align with upstream signature
        self._registry.append(
            _MockResponse.from_kwargs(method, url, json_data=json, body=body, status=status)
        )


def activate(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with Mocker():
            return func(*args, **kwargs)

    return wrapper


def add(method: str, url: str, *, json=None, body=None, status: int = 200) -> None:  # noqa: A002
    if not _active_stack:
        raise RuntimeError("responses.add() must be called within an activated mocker")
    _active_stack[-1].add(method, url, json=json, body=body, status=status)


__all__ = ["GET", "Mocker", "activate", "add"]
