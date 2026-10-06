"""Per-champion user preference record used by the priority & recommendation engines."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChampionPreference:
    champion_key: str                       # stable identifier ("222" for Jinx)
    priority: Optional[int] = None          # 1..N; None = unrated
    role_override: Optional[str] = None     # optional user-declared role
    preferred: bool = False                 # "mains" flag — surfaced in reasons
    disabled: bool = False                  # temporary: skip this session, keep rank
    never_pick: bool = False                # hard exclusion until re-enabled
    recent_picks: list[float] = field(default_factory=list)  # epoch seconds

    RECENT_DAYS = 7

    def prune_recent(self, now: float) -> None:
        cutoff = now - self.RECENT_DAYS * 86400
        self.recent_picks = [t for t in self.recent_picks if t >= cutoff]

    def record_pick(self, now: float) -> None:
        self.prune_recent(now)
        self.recent_picks.append(now)

    @property
    def recently_played(self) -> bool:
        return bool(self.recent_picks)

    def to_dict(self) -> dict:
        return {
            "champion_key": self.champion_key,
            "priority": self.priority,
            "role_override": self.role_override,
            "preferred": self.preferred,
            "disabled": self.disabled,
            "never_pick": self.never_pick,
            "recent_picks": list(self.recent_picks),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ChampionPreference":
        return cls(
            champion_key=str(d["champion_key"]),
            priority=d.get("priority"),
            role_override=d.get("role_override"),
            preferred=bool(d.get("preferred", False)),
            disabled=bool(d.get("disabled", False)),
            never_pick=bool(d.get("never_pick", False)),
            recent_picks=[float(t) for t in d.get("recent_picks", [])],
        )
