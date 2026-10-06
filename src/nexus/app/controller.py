"""ApplicationController — the single wiring point between core and UI (§6 app/).

Owns construction order, exposes typed handles to pages, and provides the
few cross-cutting commands the shell needs (emergency stop, reconnect,
compact toggle). Pages never reach into services directly; they ask here.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..core.automation.config import AutomationConfig
from ..core.automation.controller import AutomationController
from ..core.automation.kill_switch import GlobalKillSwitch
from ..core.champions.models import ChampionCatalog, default_catalog
from ..core.champions.priority import PriorityList
from ..core.events.bus import EventBus
from ..core.preferences.settings import Settings, SettingsStore
from ..core.recommendations.engine import RecommendationEngine
from ..core.sessions.recorder import SessionRecorder
from ..core.state.manager import LeagueStateManager
from ..developer.diagnostics.service import DiagnosticsService
from ..developer.simulation.port import SimActionPort
from ..developer.simulation.simulator import Simulator
from ..services.lcu.service import LCUService
from ..services.notifications.service import NotificationService
from ..services.persistence.store import PersistenceService


class AppController:
    def __init__(self, data_dir: Optional[Path] = None,
                 simulate: bool = False) -> None:
        self.simulate = simulate or os.environ.get("NEXUS_SIMULATE") == "1"
        root = Path(__file__).resolve().parents[3]      # repo root in a checkout
        self.data_dir = data_dir or (root / "nexus_data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------- core (no Qt deps)
        self.bus = EventBus()
        self.manager = LeagueStateManager(self.bus)
        self.settings_store = SettingsStore(self.data_dir)
        self.settings_store.load()
        self.settings: Settings = self.settings_store.settings

        catalog_path = root / "assets" / "champions.json"
        self.catalog: ChampionCatalog = (ChampionCatalog.load(catalog_path)
                                         if catalog_path.exists() else None)
        self.priorities = PriorityList.from_list(self.settings_store.priorities) \
            if hasattr(self.settings_store, "priorities") else PriorityList()

        self.engine = RecommendationEngine(self.catalog, self.priorities) \
            if self.catalog else None

        self.persistence = PersistenceService(self.data_dir)
        self.recorder = SessionRecorder(
            self.bus,
            on_session_closed=lambda s: self.persistence.save_session(s))

        self.notifications = NotificationService(self.bus, enabled=True)

        # ------------------------------------------------------- automation
        self.kill_switch = GlobalKillSwitch()
        self.lcu_service: Optional[LCUService] = None
        self.simulator: Optional[Simulator] = None
        self.sim_port: Optional[SimActionPort] = None

        if self.simulate:
            assert self.catalog is not None
            self.sim_port = SimActionPort(self.manager, self.catalog)
            self._port = self.sim_port
            self.simulator = Simulator(self.manager, self.bus, self.catalog)
            self.simulator.on_availability = self._sim_availability_hook
        else:
            self.lcu_service = LCUService(self.manager, self.bus)
            self._port = self.lcu_service.action_port

        self.automation = AutomationController(
            self.manager, self.bus, self._port, self.engine, self.recorder,
            config=self.settings.automation, kill_switch=self.kill_switch)

        self.diagnostics = DiagnosticsService(self.manager, self.bus)
        self.diagnostics.register("automation", self.automation)
        self.diagnostics.register("persistence", self.persistence)
        self.diagnostics.register("state_manager", self.manager)
        if self.simulator:
            self.diagnostics.register("simulation", self.simulator)

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self.manager.start_watchdog()
        self.automation.start()
        if self.lcu_service and not self.simulate:
            self.lcu_service.start()

    def shutdown(self) -> None:
        if self.simulator:
            self.simulator.stop_playback()
        self.automation.shutdown()
        self.recorder.close_active("ABANDONED")
        if self.lcu_service:
            self.lcu_service.stop()
        self.manager.stop_watchdog()
        self._save_preferences()
        self.persistence.close()

    # ------------------------------------------------------------- commands
    def emergency_stop(self, reason: str = "user hotkey") -> None:
        self.automation.emergency_stop(reason)

    def resume_automation(self) -> None:
        self.automation.resume()

    def reconnect(self) -> None:
        if self.lcu_service:
            self.lcu_service.reconnect_now()
        elif self.simulator:
            self.simulator.feed("RECONNECT")

    def manual_select(self, champion_name: str) -> None:
        """Manual override path used by the Champ Select page's big button."""
        if self.catalog is None:
            return
        champ = self.catalog.by_name(champion_name)
        if champ:
            self.automation.manual_override(champ.name, champ.id)

    def set_automation_enabled(self, enabled: bool) -> None:
        self.automation.set_enabled(enabled)
        self.settings_store.update(lambda s: setattr(
            s.automation, "master_enabled", enabled))

    def update_config(self, **fields) -> None:
        cfg = self.settings.automation
        for k, v in fields.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        self.automation.config = cfg
        self.settings_store.update(lambda s: [setattr(s.automation, k, v)
                                              for k, v in fields.items()])

    # ------------------------------------------------------ simulation hook
    def _sim_availability_hook(self, key: str, picked: bool) -> None:
        assert self.catalog and self.sim_port
        champ = self.catalog.by_key(key)
        if champ is None:
            return
        ids = set(self.sim_port.available_champion_ids() or
                  {c.id for c in self.catalog.all})
        (ids.add if not picked else ids.discard)(champ.id)
        self.sim_port.available_champion_ids = lambda: ids  # type: ignore[method-assign]

    # ---------------------------------------------------------- persistence
    def save_priorities(self) -> None:
        self.settings_store.save_priorities_rows(self.priorities.to_list()) \
            if hasattr(self.settings_store, "save_priorities_rows") else None

    def _save_preferences(self) -> None:
        try:
            rows = self.priorities.to_list()
            if hasattr(self.settings_store, "priorities"):
                self.settings_store.priorities = rows
            self.settings_store.save_priorities()
        except Exception:
            pass
