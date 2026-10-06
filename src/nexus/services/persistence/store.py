"""SQLite persistence for session history (append-heavy tabular data).

Settings/priorities live in JSON (see core.preferences.SettingsStore); sessions
use SQLite because they are queried, appended and exported. All writes go
through a single lock; callers run this from worker threads only.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from ...core.sessions.models import Session

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
    number INTEGER PRIMARY KEY,
    started_ts REAL,
    ended_ts REAL,
    queue_type TEXT,
    role TEXT,
    recommendation TEXT,
    action_taken TEXT,
    result TEXT,
    events_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_ts DESC);
"""


class PersistenceService:
    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "nexus.db"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        self._ok = True
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------ api
    @property
    def path(self) -> Path:
        return self._path

    def diagnostics(self) -> dict:
        return {"backend": "sqlite", "path": str(self._path),
                "healthy": self._ok, "last_error": self._last_error}

    def save_session(self, session: Session) -> bool:
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?,?,?,?)",
                    (session.number, session.started_ts, session.ended_ts,
                     session.queue_type, session.role, session.recommendation,
                     session.action_taken, session.result,
                     json.dumps([e.to_dict() for e in session.events])),
                )
                self._conn.commit()
            self._ok = True
            return True
        except Exception as exc:
            self._ok = False
            self._last_error = str(exc)
            return False

    def load_recent(self, limit: int = 50) -> list[Session]:
        out: list[Session] = []
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT * FROM sessions ORDER BY started_ts DESC LIMIT ?",
                    (limit,)).fetchall()
            for r in rows:
                d = {
                    "number": r[0], "started_ts": r[1], "ended_ts": r[2],
                    "queue_type": r[3], "role": r[4], "recommendation": r[5],
                    "action_taken": r[6], "result": r[7],
                    "events": json.loads(r[8] or "[]"),
                }
                out.append(Session.from_dict(d))
        except Exception as exc:
            self._ok = False
            self._last_error = str(exc)
        return out

    def export_all(self) -> list[dict]:
        return [s.to_dict() for s in self.load_recent(limit=10_000)]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
