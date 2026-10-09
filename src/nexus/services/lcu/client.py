"""Minimal, dependency-light LCU HTTP client.

The League Client exposes a local HTTPS API with a self-signed certificate;
credentials are the Riot username + remoting auth token discovered by
client_detection. We use `httpx` (sync) from dedicated worker threads only —
never on the Qt GUI thread.

Endpoints used (documented LCU surface):
* GET  /                                → client version
* GET  /lol-login/v1/session            → account/session
* GET  /lol-champ-select/v1/session     → champ select session (phases/timer)
* GET  /lol-gameflow/v1/gameflow-phase  → high-level flow phase
* GET  /patching/v1/installed-products?product=league-of-legends → live champs
* POST /lol-ready-check/v1/accept       → accept ready check
* POST /lol-champ-select/v1/session/actions/<id> {"selectedChampionId":N}
* POST /lol-champ-select/v1/session/actions/<id>/complete  → lock in
* GET  /live-client/v1/grid/drag/...    (not used)
Event stream: SSE at /sse — consumed by `events.py`.
"""
from __future__ import annotations

import base64
import ssl
import threading
from typing import Any, Optional

import httpx


class LCUNotConnected(RuntimeError):
    pass


class LCUClient:
    def __init__(self, port: int, auth_token: Optional[str], timeout: float = 3.0) -> None:
        self._port = port
        self._token = auth_token
        self._timeout = timeout
        self._lock = threading.Lock()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE          # documented: client cert is self-signed
        self._ssl_ctx = ctx
        auth = ("riot", auth_token) if auth_token else None
        self._http = httpx.Client(verify=ctx, auth=auth, timeout=timeout)
        self._base = f"https://127.0.0.1:{port}"

    @property
    def port(self) -> int:
        return self._port

    # Exposed for the SSE listener (needs the same auth + TLS policy).
    @property
    def base_url(self) -> str:
        return self._base

    @property
    def auth(self) -> Optional[tuple[str, str]]:
        return ("riot", self._token) if self._token else None

    @property
    def ssl_context(self) -> ssl.SSLContext:
        return self._ssl_ctx

    # ------------------------------------------------------------------ core
    def _request(self, method: str, path: str, json_body: Any = None) -> Any:
        url = self._base + path
        with self._lock:
            resp = self._http.request(method, url, json=json_body)
        if resp.status_code >= 400:
            raise LCUNotConnected(f"{method} {path} → HTTP {resp.status_code}")
        if not resp.content:
            return None
        try:
            return resp.json()
        except Exception:
            return resp.text

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, body: Any = None) -> Any:
        return self._request("POST", path, body)

    def put(self, path: str, body: Any = None) -> Any:
        return self._request("PUT", path, body)

    # ------------------------------------------------------------- liveness
    def ping(self) -> bool:
        try:
            with self._lock:
                resp = self._http.get(f"{self._base}/lol-gameflow/v1/gameflow-phase")
            return resp.status_code < 500
        except Exception:
            try:
                with self._lock:
                    resp = self._http.get(self._base + "/")
                return resp.status_code < 500
            except Exception:
                return False

    def close(self) -> None:
        with self._lock:
            self._http.close()
