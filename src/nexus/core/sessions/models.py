"""First-class session model (spec §16).

A session spans one League flow: queue → champ select → game → post-game.
It records state transitions, recommendations, automation actions, manual
overrides, failures and outcomes — everything needed to answer "what happened
afterward?" without raw logs.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SessionEvent:
    ts: float
    kind: str          # "state" | "recommendation" | "action" | "override" | "failure" | "outcome"
    text: str
    detail: dict[str, Any] = field(default_factory=dict)

    def clock(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.ts))

    def to_dict(self) -> dict:
        return {"ts": self.ts, "kind": self.kind, "text": self.text, "detail": self.detail}

    @classmethod
    def from_dict(cls, d: dict) -> "SessionEvent":
        return cls(ts=float(d["ts"]), kind=str(d["kind"]), text=str(d["text"]),
                   detail=dict(d.get("detail", {})))


@dataclass
class Session:
    number: int
    started_ts: float = field(default_factory=time.time)
    ended_ts: Optional[float] = None
    queue_type: Optional[str] = None
    role: Optional[str] = None
    recommendation: Optional[str] = None
    recommendation_reasons: list[str] = field(default_factory=list)
    action_taken: Optional[str] = None      # "Auto-selected" | "Manual override" | ...
    result: str = "IN PROGRESS"             # SUCCESS | FAILED | ABANDONED | IN PROGRESS
    events: list[SessionEvent] = field(default_factory=list)

    # ------------------------------------------------------------- recording
    def add(self, kind: str, text: str, **detail: Any) -> SessionEvent:
        ev = SessionEvent(ts=time.time(), kind=kind, text=text, detail=detail)
        self.events.append(ev)
        return ev

    def set_context(self, *, queue_type: Optional[str] = None,
                    role: Optional[str] = None) -> None:
        if queue_type and not self.queue_type:
            self.queue_type = queue_type
        if role and role != "NONE":
            self.role = role

    def finish(self, result: str) -> None:
        self.result = result
        self.ended_ts = time.time()

    # ------------------------------------------------------------ rendering
    def summary(self) -> str:
        lines = [f"SESSION #{self.number}",
                 f"Queue: {self.queue_type or '—'}",
                 f"Role: {self.role or '—'}",
                 f"Start: {time.strftime('%H:%M:%S', time.localtime(self.started_ts))}",
                 ""]
        if self.recommendation:
            lines.append(f"Recommendation:\n{self.recommendation}")
        if self.action_taken:
            lines.append(f"\nAction:\n{self.action_taken}")
        lines.append(f"\nResult:\n{self.result}")
        return "\n".join(lines)

    def timeline(self) -> list[str]:
        """Human-readable event timeline rows (spec §17)."""
        rows: list[str] = []
        for ev in self.events:
            marker = {"state": "●", "recommendation": "★", "action": "→",
                      "override": "✋", "failure": "⚠", "outcome": "✓"}.get(ev.kind, "·")
            rows.append(f"{ev.clock()}  {marker} {ev.text}")
        return rows

    def to_dict(self) -> dict:
        return {
            "number": self.number, "started_ts": self.started_ts,
            "ended_ts": self.ended_ts, "queue_type": self.queue_type,
            "role": self.role, "recommendation": self.recommendation,
            "recommendation_reasons": list(self.recommendation_reasons),
            "action_taken": self.action_taken, "result": self.result,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        return cls(
            number=int(d["number"]), started_ts=float(d.get("started_ts", time.time())),
            ended_ts=d.get("ended_ts"), queue_type=d.get("queue_type"),
            role=d.get("role"), recommendation=d.get("recommendation"),
            recommendation_reasons=list(d.get("recommendation_reasons", [])),
            action_taken=d.get("action_taken"), result=str(d.get("result", "IN PROGRESS")),
            events=[SessionEvent.from_dict(e) for e in d.get("events", [])],
        )
