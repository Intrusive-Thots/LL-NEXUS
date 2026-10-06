"""League Client process detection (Windows-first, cross-platform fallback).

Strategy (mirrors what the real client exposes, learned from LeagueLoop):
1. Windows: scan running processes for the League Client UWP (`LeagueClientUx`),
   read its command line and extract `--port=` and `--remoting-auth-token=`.
2. Any OS: fall back to Riot's official Lockfile at
   `<install>/Lockfile.json` — it contains port + PID but NOT the token; the
   token can only come from the process command line (Windows) or a user
   supplied override.

Everything degrades gracefully: no psutil → skip process scan; no install found
→ return None with an explanation. Detection never blocks the UI thread — the
LCU service calls this from its worker loop.

Documented limitation: on non-Windows platforms the auth token cannot be
extracted automatically (the client itself is Windows-only), so live LCU mode
is effectively Windows; Nexus remains fully usable elsewhere via Simulation
Mode.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ClientInfo:
    port: int
    pid: int
    auth_token: Optional[str]
    source: str                     # "process" | "lockfile" | "env"
    install_path: Optional[str] = None

    @property
    def base_url(self) -> str:
        return f"https://127.0.0.1:{self.port}"


_PORT_RE = re.compile(r"--port=(\d+)")
_TOKEN_RE = re.compile(r"--remoting-auth-token=([A-Za-z0-9_\-]+)")
_PID_RE = re.compile(r"--app-path=.*?[\\/](?:Riot Games|League of Legends)", re.I)


def _detect_windows_process() -> Optional[ClientInfo]:
    try:
        import psutil  # type: ignore
    except Exception:
        return None
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if "leagueclientux" not in name:
                continue
            cmdline = " ".join(proc.cmdline())
            m_port = _PORT_RE.search(cmdline)
            m_tok = _TOKEN_RE.search(cmdline)
            if m_port:
                return ClientInfo(port=int(m_port.group(1)), pid=int(proc.info["pid"]),
                                  auth_token=m_tok.group(1) if m_tok else None,
                                  source="process")
        except Exception:
            continue      # access denied / exited mid-scan — keep going
    return None


def _lockfile_candidates() -> list[Path]:
    candidates: list[Path] = []
    env = os.environ.get("NEXUS_LEAGUE_INSTALL")
    if env:
        candidates.append(Path(env) / "Lockfile.json")
    default_roots = [
        r"C:\Riot Games",
        r"C:\Program Files\Riot Games",
        os.path.expandvars(r"%LOCALAPPDATA%\Riot Games"),
    ]
    for root in default_roots:
        p = Path(root)
        if p.exists():
            candidates.extend(sorted(p.glob("**/Lockfile.json")))
    candidates.append(Path("/Applications/League of Legends.app/Contents/LoL/Lockfile.json"))
    return candidates


def _read_lockfile() -> Optional[ClientInfo]:
    for path in _lockfile_candidates():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # format: ["Custom League Client", "", pid, port, token]
            if isinstance(data, list) and len(data) >= 4:
                pid = int(data[2]); port = int(data[3])
                token = str(data[4]) if len(data) > 4 else None
                return ClientInfo(port=port, pid=pid, auth_token=token,
                                  source="lockfile", install_path=str(path.parent))
        except Exception:
            continue
    return None


def detect_client() -> Optional[ClientInfo]:
    """Best-effort discovery of a running League Client. Returns None if absent."""
    # explicit env override wins (useful for testing against a stub server)
    port = os.environ.get("NEXUS_LCU_PORT")
    token = os.environ.get("NEXUS_LCU_TOKEN")
    if port:
        return ClientInfo(port=int(port), pid=-1, auth_token=token, source="env")

    info = _detect_windows_process() if os.name == "nt" else None
    if info and info.auth_token:
        return info
    lock = _read_lockfile()
    if lock:
        if info and not lock.auth_token:
            return ClientInfo(port=lock.port, pid=info.pid, auth_token=None,
                              source="process+lockfile", install_path=lock.install_path)
        return lock
    return info


def client_still_running(info: ClientInfo) -> bool:
    if info.source == "env":
        return True
    try:
        import psutil  # type: ignore
        return psutil.pid_exists(info.pid)
    except Exception:
        # Without psutil we cannot verify the PID; report unknown as False so
        # the LCU service falls back to HTTP probing rather than trusting us.
        return False
