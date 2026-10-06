"""Automation configuration — progressive-disclosure friendly.

Each capability has an independent enable flag plus a mode where useful.
The Automation Control Center renders these; nothing else mutates them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class BanMode(str, Enum):
    ASK = "ASK"          # never auto-ban; surface suggestion only
    AUTO = "AUTO"        # ban recommendation #1
    SKIP = "SKIP"        # do nothing on ban actions


@dataclass
class AutomationConfig:
    master_enabled: bool = True         # user-level "automation ON"
    auto_accept_ready: bool = True
    auto_pick: bool = True
    lock_in_delay_seconds: float = 0.6  # grace window for manual override
    ban_mode: BanMode = BanMode.ASK
    auto_import_team_comp: bool = False
    retry_limit: int = 2                # safe retries for transient failures
    require_confirmed_state: bool = True  # fail-closed policy (never disable blindly)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ban_mode"] = self.ban_mode.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AutomationConfig":
        known = {f for f in cls.__dataclass_fields__}  # noqa
        clean = {k: v for k, v in d.items() if k in known}
        if "ban_mode" in clean and isinstance(clean["ban_mode"], str):
            clean["ban_mode"] = BanMode(clean["ban_mode"])
        return cls(**clean)
