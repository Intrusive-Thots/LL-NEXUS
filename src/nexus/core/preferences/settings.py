"""Settings store — user preferences, automation config, champion priorities.

Persistence backend: JSON files under the data directory (simple, inspectable,
no DB migration burden for a settings document). Session history uses SQLite in
`nexus.services.persistence.store` because it is append-heavy tabular data.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..automation.config import AutomationConfig
from ..champions.priority import PriorityList


@dataclass
class GeneralSettings:
    launch_on_startup: bool = False
    start_in_compact_mode: bool = False
    reduced_motion: bool = False
    language: str = "en"


@dataclass
class AppearanceSettings:
    theme: str = "dark"                 # dark | light
    accent: str = "hextech-gold"        # token name from the theme system
    ui_scale: float = 1.0               # extra scaling on top of DPI
    compact_size: str = "medium"        # small | medium | large


@dataclass
class NotificationSettings:
    toast_recommendation: bool = True
    toast_errors: bool = True
    sound_kill_switch: bool = True


@dataclass
class HotkeySettings:
    emergency_stop: str = "Ctrl+Alt+S"
    toggle_compact: str = "Ctrl+Alt+C"
    accept_queue: str = "Ctrl+Alt+A"
    focus_search: str = "/"


@dataclass
class DeveloperSettings:
    developer_mode: bool = False
    simulation_mode: bool = False       # forced by --simulate / env NEXUS_SIMULATE
    log_raw_events: bool = True


@dataclass
class Settings:
    general: GeneralSettings = field(default_factory=GeneralSettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    automation: AutomationConfig = field(default_factory=AutomationConfig)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)
    developer: DeveloperSettings = field(default_factory=DeveloperSettings)

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Settings":
        s = cls()
        for section_name, section in d.items():
            if not isinstance(section, dict):
                continue
            if section_name == "automation":
                s.automation = AutomationConfig.from_dict(section)
                continue
            attr = getattr(s, section_name, None)
            if attr is None:
                continue
            for k, v in section.items():
                if hasattr(attr, k):
                    setattr(attr, k, v)
        return s


class SettingsStore:
    """Thread-safe load/save of the settings document + priority list."""

    FILENAME = "settings.json"
    PRIORITY_FILENAME = "priorities.json"

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._lock = threading.RLock()
        self.settings = Settings()
        self.priorities = PriorityList()
        self.load()

    # ---------------------------------------------------------------- paths
    @property
    def path(self) -> Path:
        return self._dir / self.FILENAME

    @property
    def priority_path(self) -> Path:
        return self._dir / self.PRIORITY_FILENAME

    # ------------------------------------------------------------------- io
    def load(self) -> None:
        with self._lock:
            if self.path.exists():
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                    self.settings = Settings.from_dict(raw)
                except Exception:
                    self.settings = Settings()   # corrupt file → safe defaults
            if self.priority_path.exists():
                try:
                    rows = json.loads(self.priority_path.read_text(encoding="utf-8"))
                    self.priorities = PriorityList.from_list(rows)
                except Exception:
                    self.priorities = PriorityList()

    def save(self) -> None:
        with self._lock:
            self._dir.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.settings.to_dict(), indent=2), encoding="utf-8")
            tmp.replace(self.path)

    def save_priorities(self) -> None:
        with self._lock:
            self._dir.mkdir(parents=True, exist_ok=True)
            tmp = self.priority_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.priorities.to_list(), indent=1), encoding="utf-8")
            tmp.replace(self.priority_path)

    def update(self, mutate) -> None:
        """Mutate settings then persist atomically."""
        with self._lock:
            mutate(self.settings)
            self.save()
