from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget,
    QMainWindow, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from ...core.automation.config import BanMode
from ...core.state.models import LeagueState, StateConfidence
from ...developer.inspector.view import EventInspector
from ...developer.simulation.simulator import SCENARIOS
from ..champ_select.panel import ChampionSelectPanel
from ..compact.overlay import CompactOverlay
from ..components.base import NexusButton, NexusCard, NexusHeader, NexusStatus
from ..components.toast import NexusToast
from ..pages.profile_page import ProfilePage
from ..pages.settings_page import SettingsPage
from ..theme import tokens as T
from ..theme.qss import build_qss
from .bridge import NexusQtBridge


class MainWindow(QMainWindow):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("LeagueLoop Nexus")
        self.setMinimumSize(*T.MAIN_WINDOW_MIN)
        self.resize(1180, 760)
        self.setStyleSheet(build_qss(getattr(controller.settings.appearance, "theme", "dark")))
        self.bridge = NexusQtBridge(controller.bus, self)
        self.bridge.event.connect(self._on_event)
        self._toasts = []
        self.compact = CompactOverlay(controller)
        self.compact.expand_requested = self._expand_from_compact
        self._build()
        self._show("Champ Select")
        self._refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(500)
        if getattr(controller.settings.general, "start_in_compact_mode", False):
            self.compact.show()

    def _build(self):
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(T.SP_4, T.SP_4, T.SP_4, T.SP_4)
        outer.setSpacing(T.SP_3)

        nav = QFrame()
        nav.setObjectName("NexusNav")
        nv = QVBoxLayout(nav)
        nv.setContentsMargins(T.SP_3, T.SP_3, T.SP_3, T.SP_3)

        brand = QLabel("LEAGUELOOP\nNEXUS")
        brand.setObjectName("Brand")
        nv.addWidget(brand)

        self.pages = {}
        self.buttons = []
        for name in ("Champ Select", "Automation", "Profile", "Settings", "Developer"):
            b = NexusButton(name, variant="ghost")
            b.clicked.connect(lambda _, n=name: self._show(n))
            nv.addWidget(b)
            self.buttons.append(b)

        nv.addStretch()
        compact_btn = NexusButton("COMPACT MODE", "ghost")
        compact_btn.clicked.connect(self._toggle_compact)
        nv.addWidget(compact_btn)

        self.nav_status = NexusStatus("Disconnected")
        nv.addWidget(self.nav_status)

        stop = NexusButton("EMERGENCY STOP", "danger", "Ctrl+Shift+Esc")
        stop.clicked.connect(lambda: self.controller.emergency_stop())
        nv.addWidget(stop)

        nav.setFixedWidth(190)
        outer.addWidget(nav)

        self.stack = QStackedWidget()
        for name, fn in (
            ("Champ Select", self._champ_page),
            ("Automation", self._automation_page),
            ("Profile", self._profile_page),
            ("Settings", self._settings_page),
            ("Developer", self._developer_page),
        ):
            page = fn()
            self.pages[name] = page
            self.stack.addWidget(page)

        outer.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def _show(self, name: str):
        if name in self.pages:
            self.stack.setCurrentWidget(self.pages[name])
            for b in self.buttons:
                is_active = (b.text() == name)
                b.setProperty("selected", is_active)
                b.setProperty("NexusVariant", "primary" if is_active else "ghost")
                b.style().unpolish(b)
                b.style().polish(b)

    def _champ_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(T.SP_3)
        l.addWidget(NexusHeader("Champ Select", "Recommendation-first control surface"))

        self.phase = NexusStatus("Disconnected")
        l.addWidget(self.phase)

        rec = NexusCard(True)
        self.rec_title = QLabel("No recommendation")
        self.rec_title.setObjectName("Display")
        self.rec_score = QLabel("")
        self.rec_why = QLabel("Connect the League Client to begin.")
        self.rec_why.setWordWrap(True)
        pick = NexusButton("MANUAL SELECT", "primary")
        pick.clicked.connect(self._manual_select)
        rec.body.addWidget(self.rec_title)
        rec.body.addWidget(self.rec_score)
        rec.body.addWidget(self.rec_why)
        rec.body.addWidget(pick)

        action = NexusCard()
        self.auto_state = NexusStatus("Automation disabled")
        action.body.addWidget(self.auto_state)
        self.auto_toggle = QCheckBox("Enable automation")
        self.auto_toggle.toggled.connect(self.controller.set_automation_enabled)
        action.body.addWidget(self.auto_toggle)
        stop = NexusButton("STOP AUTOMATION", "danger")
        stop.clicked.connect(lambda: self.controller.emergency_stop("Champ Select stop"))
        action.body.addWidget(stop)

        row = QHBoxLayout()
        row.addWidget(rec, 2)
        row.addWidget(action, 1)
        l.addLayout(row)

        pool = ChampionSelectPanel(self.controller)
        pool.manual_select.connect(self.controller.manual_select)
        self.pool = pool
        l.addWidget(pool, 2)

        timeline = NexusCard()
        timeline.body.addWidget(QLabel("ACTIVITY"))
        self.events = QListWidget()
        timeline.body.addWidget(self.events)
        l.addWidget(timeline, 1)
        return w

    def _automation_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(T.SP_3)
        l.addWidget(NexusHeader("Automation", "Explicit controls with fail-closed safety"))

        c = NexusCard()
        self.master = QCheckBox("Master automation")
        self.master.toggled.connect(self.controller.set_automation_enabled)
        c.body.addWidget(self.master)

        a = QCheckBox("Auto Accept Ready Check")
        a.setChecked(self.controller.settings.automation.auto_accept_ready)
        a.toggled.connect(lambda v: self.controller.update_config(auto_accept_ready=v))
        c.body.addWidget(a)

        p = QCheckBox("Auto Pick")
        p.setChecked(self.controller.settings.automation.auto_pick)
        p.toggled.connect(lambda v: self.controller.update_config(auto_pick=v))
        c.body.addWidget(p)

        b = QCheckBox("Auto Ban")
        b.setChecked(self.controller.settings.automation.ban_mode is BanMode.AUTO)
        b.toggled.connect(lambda v: self.controller.update_config(ban_mode=BanMode.AUTO if v else BanMode.ASK))
        c.body.addWidget(b)

        note = QLabel("Consequential actions require confirmed authoritative state and post-action verification.")
        note.setObjectName("Secondary")
        c.body.addWidget(note)
        l.addWidget(c)
        l.addStretch()
        return w

    def _profile_page(self):
        page = ProfilePage(self.controller)
        self.profile_page = page
        return page

    def _settings_page(self):
        page = SettingsPage(self.controller)
        self.settings_page = page
        return page

    def _toggle_compact(self):
        if self.compact.isVisible():
            self.compact.hide()
        else:
            self.compact.refresh()
            self.compact.show()

    def _expand_from_compact(self):
        rec = self.controller.automation.pending_recommendation
        snap = self.controller.manager.snapshot()
        if rec and rec.winner and snap.state in (LeagueState.CHAMP_SELECT, LeagueState.PICK_PHASE, LeagueState.BAN_PHASE):
            self.controller.manual_select(rec.winner.champion.name)
        self.compact.hide()
        self.activateWindow()
        self.raise_()
        self._show("Champ Select")

    def _developer_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(T.SP_3)
        l.addWidget(NexusHeader("Developer", "Diagnostics, simulation controls and event inspector"))

        top_row = QHBoxLayout()
        top_row.setSpacing(T.SP_3)

        # Simulation Controls Card
        sim_card = NexusCard(raised=True)
        sim_card.body.addWidget(QLabel("SIMULATION CONTROL"))

        sc_row = QHBoxLayout()
        self.scenario_box = QComboBox()
        for sc in SCENARIOS:
            self.scenario_box.addItem(f"{sc.name} ({sc.id})", sc.id)
        sc_row.addWidget(self.scenario_box, 1)

        play_btn = NexusButton("PLAY SCENARIO", variant="primary")
        play_btn.clicked.connect(self._sim_play)
        sc_row.addWidget(play_btn)

        stop_btn = NexusButton("STOP", variant="secondary")
        stop_btn.clicked.connect(self._sim_stop)
        sc_row.addWidget(stop_btn)

        reset_btn = NexusButton("RESET", variant="ghost")
        reset_btn.clicked.connect(self._sim_reset)
        sc_row.addWidget(reset_btn)
        sim_card.body.addLayout(sc_row)

        verbs_row = QHBoxLayout()
        verbs_row.setSpacing(T.SP_1)
        for verb in ("CONNECT", "LOBBY", "QUEUE", "CHAMP_SELECT", "PICK_PHASE", "LOCKED", "DISCONNECT"):
            vb = NexusButton(verb, variant="ghost")
            vb.clicked.connect(lambda _, v=verb: self._sim_feed(v))
            verbs_row.addWidget(vb)
        sim_card.body.addLayout(verbs_row)
        top_row.addWidget(sim_card, 2)

        # Authoritative Snapshot Card
        diag_card = NexusCard()
        diag_card.body.addWidget(QLabel("STATE SNAPSHOT"))
        self.diag = QLabel()
        self.diag.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.diag.setWordWrap(True)
        self.diag.setObjectName("Secondary")
        diag_card.body.addWidget(self.diag)
        top_row.addWidget(diag_card, 1)

        l.addLayout(top_row)

        # Raw Event Stream Inspector
        inspector_card = NexusCard()
        self.inspector = EventInspector(self.controller.bus, self)
        inspector_card.body.addWidget(self.inspector)
        l.addWidget(inspector_card, 1)

        return w

    def _sim_play(self):
        if not self.controller.simulator:
            return
        sc_id = self.scenario_box.currentData()
        if sc_id:
            self.controller.simulator.play(sc_id)

    def _sim_stop(self):
        if self.controller.simulator:
            self.controller.simulator.stop_playback()

    def _sim_reset(self):
        if self.controller.simulator:
            self.controller.simulator.reset()

    def _sim_feed(self, verb: str):
        if self.controller.simulator:
            self.controller.simulator.feed(verb)

    def _manual_select(self):
        rec = self.controller.automation.pending_recommendation
        if rec and rec.winner:
            self.controller.manual_select(rec.winner.champion.name)

    def _refresh(self):
        snap = self.controller.manager.snapshot()
        p = T.PALETTE_DARK
        color = {
            StateConfidence.CONFIRMED: p.dot_connected,
            StateConfidence.STALE: p.dot_stale,
            StateConfidence.ERROR: p.dot_disconnected,
            StateConfidence.UNKNOWN: p.dot_disconnected,
            StateConfidence.SYNCING: p.dot_searching,
        }[snap.confidence]

        self.phase.set_status(f"{snap.state.value.replace('_', ' ').title()} · {snap.confidence.value}", color)
        self.nav_status.set_status("Connected" if snap.state is not LeagueState.DISCONNECTED else "Disconnected", color)

        rec = self.controller.automation.pending_recommendation
        if rec and rec.winner:
            self.rec_title.setText(rec.winner.champion.name)
            self.rec_score.setText(f"Score {rec.winner.score:.1f} · {len(rec.alternates)} alternates")
            self.rec_why.setText("Why? " + " · ".join(rec.winner.reasons[:4]))
        else:
            self.rec_title.setText("No recommendation")
            self.rec_score.setText("")

        self.auto_state.set_status(str(self.controller.automation.status).replace("_", " ").title())
        self.master.blockSignals(True)
        self.master.setChecked(self.controller.settings.automation.master_enabled)
        self.master.blockSignals(False)

        self.auto_toggle.blockSignals(True)
        self.auto_toggle.setChecked(self.controller.settings.automation.master_enabled)
        self.auto_toggle.blockSignals(False)

        self.pool.refresh()
        if hasattr(self, "profile_page"):
            self.profile_page.refresh()
        if self.compact.isVisible():
            self.compact.refresh()

        if hasattr(self, "diag") and hasattr(self.controller, "diagnostics"):
            text = (
                f"State: {snap.state.value}\n"
                f"Confidence: {snap.confidence.value}\n"
                f"Queue: {snap.queue_type or 'None'}\n"
                f"Role: {snap.role.display}\n"
                f"Timer: {snap.timer_seconds}s / {snap.timer_total_seconds}s\n"
                f"Locked: {snap.locked_in}\n"
                f"Automation: {self.controller.automation.status}\n"
                f"Kill Switch: {'TRIPPED' if self.controller.kill_switch.tripped else 'ARMED'}"
            )
            self.diag.setText(text)

    def _on_event(self, ev):
        if ev.kind == "notify":
            p = ev.payload
            if not self.controller.notifications.enabled:
                return
            level = str(p.get("level", "info"))
            if level == "critical" and not self.controller.settings.notifications.toast_errors:
                return
            toast = NexusToast(
                str(p.get("title", "")),
                str(p.get("body", "")),
                level=level,
                duration_ms=int(p.get("duration_ms", 4000)),
                parent=self,
            )
            self._toasts.append(toast)
            toast.dismissed.connect(lambda t=toast: self._toasts.remove(t))
            self._layout_toasts()
            toast.show()

        if ev.kind.startswith(("state.", "automation.", "lcu.", "recommendation.", "simulation.", "notify")):
            self.events.insertItem(0, ev.human())
            while self.events.count() > 80:
                self.events.takeItem(self.events.count() - 1)

    def _layout_toasts(self):
        if not self._toasts:
            return
        margin = T.SP_4
        x = self.width() - margin
        y = self.height() - margin
        for t in self._toasts[-5:]:
            t.adjustSize()
            h = t.sizeHint().height()
            w = t.maximumWidth() + 2 * T.SP_1
            t.move(max(margin, x - w), y - h)
            y -= h + T.SP_2

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout_toasts()

    def closeEvent(self, event):
        self.bridge.shutdown()
        if hasattr(self, "inspector"):
            self.inspector.stop()
        super().closeEvent(event)
