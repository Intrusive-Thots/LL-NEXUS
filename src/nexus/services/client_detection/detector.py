"""League Client process detection (Windows-first, cross-platform fallback).

Strategy:
1. Windows: scan running processes for the League Client (`LeagueClientUx` or `LeagueClient`),
   read its command line and extract `--app-port=` / `--port=` and `--remoting-auth-token=`.
2. Any OS: fall back to Riot's official Lockfile at `<install>/lockfile` — formatted
   as `ProcessName:PID:Port:Password:Protocol`.
3. Degrades gracefully: no psutil → skip process scan; no install found → return None.
"""
from __future__ import annotations

import json
import os
import re
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


_PORT_RE = re.compile(r"--(?:app-)?port=(\d+)")
_TOKEN_RE = re.compile(r"--remoting-auth-token=([A-Za-z0-9_\-]+)")
_INSTALL_RE = re.compile(r"--install-directory=([^\s\"]+)")


def _detect_windows_process() -> Optional[ClientInfo]:
    try:
        import psutil  # type: ignore
    except Exception:
        return None

    # First attempt: find LeagueClientUx.exe or LeagueClient.exe and read command line
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if "leagueclientux" not in name and name != "leagueclient.exe":
                continue
            cmdline = " ".join(proc.cmdline())
            m_port = _PORT_RE.search(cmdline)
            m_tok = _TOKEN_RE.search(cmdline)
            m_dir = _INSTALL_RE.search(cmdline)
            install_dir = m_dir.group(1) if m_dir else None

            if m_port and m_tok:
                return ClientInfo(
                    port=int(m_port.group(1)),
                    pid=int(proc.info["pid"]),
                    auth_token=m_tok.group(1),
                    source="process",
                    install_path=install_dir,
                )
        except Exception:
            continue

    # Second attempt: check process exe directory for lockfile
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if "leagueclient" in name:
                exe = proc.exe()
                if exe:
                    p = Path(exe).parent / "lockfile"
                    info = _parse_lockfile_path(p)
                    if info:
                        return info
        except Exception:
            continue

    return None


def _parse_lockfile_path(path: Path) -> Optional[ClientInfo]:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        # Standard Riot colon-separated format: process:pid:port:token:protocol
        parts = raw.split(":")
        if len(parts) >= 5:
            return ClientInfo(
                port=int(parts[2]),
                pid=int(parts[1]),
                auth_token=parts[3],
                source="lockfile",
                install_path=str(path.parent),
            )
        # JSON fallback format if used by wrappers
        data = json.loads(raw)
        if isinstance(data, list) and len(data) >= 4:
            pid = int(data[2])
            port = int(data[3])
            token = str(data[4]) if len(data) > 4 else None
            return ClientInfo(
                port=port,
                pid=pid,
                auth_token=token,
                source="lockfile",
                install_path=str(path.parent),
            )
    except Exception:
        pass
    return None


def _lockfile_candidates() -> list[Path]:
    candidates: list[Path] = []
    env = os.environ.get("NEXUS_LEAGUE_INSTALL")
    if env:
        candidates.append(Path(env) / "lockfile")
        candidates.append(Path(env) / "Lockfile")
        candidates.append(Path(env) / "Lockfile.json")

    default_roots = [
        r"C:\Riot Games\League of Legends",
        r"D:\Riot Games\League of Legends",
        r"C:\Riot Games",
        r"C:\Program Files\Riot Games\League of Legends",
        os.path.expandvars(r"%LOCALAPPDATA%\Riot Games\League of Legends"),
    ]
    for root in default_roots:
        p = Path(root)
        if p.exists():
            candidates.append(p / "lockfile")
            candidates.append(p / "Lockfile")
            candidates.extend(sorted(p.glob("**/lockfile")))

    candidates.append(Path("/Applications/League of Legends.app/Contents/LoL/lockfile"))
    return candidates


def _read_lockfile() -> Optional[ClientInfo]:
    for path in _lockfile_candidates():
        info = _parse_lockfile_path(path)
        if info:
            return info
    return None


def detect_client() -> Optional[ClientInfo]:
    """Best-effort discovery of a running League Client. Returns None if absent."""
    port = os.environ.get("NEXUS_LCU_PORT")
    token = os.environ.get("NEXUS_LCU_TOKEN")
    if port:
        return ClientInfo(port=int(port), pid=-1, auth_token=token, source="env")

    # 1. Process scanning (cmdline flags)
    info = _detect_windows_process() if os.name == "nt" else None
    if info and info.auth_token:
        return info

    # 2. Lockfile detection
    lock = _read_lockfile()
    if lock:
        return lock

    return info


def client_still_running(info: ClientInfo) -> bool:
    if info.source == "env":
        return True
    try:
        import psutil  # type: ignore
        return psutil.pid_exists(info.pid)
    except Exception:
        return False
