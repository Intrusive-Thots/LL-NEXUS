from __future__ import annotations
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QCheckBox,QFrame,QHBoxLayout,QLabel,QListWidget,QMainWindow,QStackedWidget,QVBoxLayout,QWidget
from ...core.automation.config import BanMode
from ...core.state.models import LeagueState,StateConfidence
from ..components.base import NexusButton,NexusCard,NexusHeader,NexusStatus
from ..theme import tokens as T
from ..theme.qss import build_qss
from ..champ_select.panel import ChampionSelectPanel
from .bridge import NexusQtBridge
class MainWindow(QMainWindow):
    def __init__(self,controller,parent=None):
        super().__init__(parent); self.controller=controller; self.setWindowTitle("LeagueLoop Nexus")
        self.setMinimumSize(*T.MAIN_WINDOW_MIN); self.resize(1180,760); self.setStyleSheet(build_qss("dark"))
        self.bridge=NexusQtBridge(controller.bus,self); self.bridge.event.connect(self._on_event); self._build(); self._refresh()
        self.timer=QTimer(self); self.timer.timeout.connect(self._refresh); self.timer.start(500)
    def _build(self):
        root=QWidget(); outer=QHBoxLayout(root); outer.setContentsMargins(T.SP_4,T.SP_4,T.SP_4,T.SP_4); outer.setSpacing(T.SP_3)
        nav=QFrame(); nav.setObjectName("NexusNav"); nv=QVBoxLayout(nav); nv.setContentsMargins(T.SP_3,T.SP_3,T.SP_3,T.SP_3)
        brand=QLabel("LEAGUELOOP\nNEXUS"); brand.setObjectName("Brand"); nv.addWidget(brand)
        self.pages={}; self.buttons=[]
        for name in ("Champ Select","Automation","Profile","Settings","Developer"):
            b=NexusButton(name,variant="ghost"); b.clicked.connect(lambda _,n=name:self._show(n)); nv.addWidget(b); self.buttons.append(b)
        nv.addStretch(); self.nav_status=NexusStatus("Disconnected"); nv.addWidget(self.nav_status)
        stop=NexusButton("EMERGENCY STOP","danger","Ctrl+Shift+Esc"); stop.clicked.connect(lambda:self.controller.emergency_stop()); nv.addWidget(stop)
        nav.setFixedWidth(190); outer.addWidget(nav)
        self.stack=QStackedWidget()
        for name,fn in (("Champ Select",self._champ_page),("Automation",self._automation_page),("Profile",self._profile_page),("Settings",self._settings_page),("Developer",self._developer_page)):
            page=fn(); self.pages[name]=page; self.stack.addWidget(page)
        outer.addWidget(self.stack,1); self.setCentralWidget(root)
    def _show(self,name): self.stack.setCurrentWidget(self.pages[name])
    def _champ_page(self):
        w=QWidget(); l=QVBoxLayout(w); l.addWidget(NexusHeader("Champ Select","Recommendation-first control surface"))
        self.phase=NexusStatus("Disconnected"); l.addWidget(self.phase)
        rec=NexusCard(True); self.rec_title=QLabel("No recommendation"); self.rec_title.setObjectName("Display")
        self.rec_score=QLabel(""); self.rec_why=QLabel("Connect the League Client to begin."); self.rec_why.setWordWrap(True)
        pick=NexusButton("MANUAL SELECT","primary"); pick.clicked.connect(self._manual_select)
        rec.body.addWidget(self.rec_title); rec.body.addWidget(self.rec_score); rec.body.addWidget(self.rec_why); rec.body.addWidget(pick)
        action=NexusCard(); self.auto_state=NexusStatus("Automation disabled"); action.body.addWidget(self.auto_state)
        self.auto_toggle=QCheckBox("Enable automation"); self.auto_toggle.toggled.connect(self.controller.set_automation_enabled); action.body.addWidget(self.auto_toggle)
        stop=NexusButton("STOP AUTOMATION","danger"); stop.clicked.connect(lambda:self.controller.emergency_stop("Champ Select stop")); action.body.addWidget(stop)
        row=QHBoxLayout(); row.addWidget(rec,2); row.addWidget(action,1); l.addLayout(row)
        pool=ChampionSelectPanel(self.controller); pool.manual_select.connect(self.controller.manual_select); self.pool=pool; l.addWidget(pool,2)
        timeline=NexusCard(); timeline.body.addWidget(QLabel("ACTIVITY")); self.events=QListWidget(); timeline.body.addWidget(self.events); l.addWidget(timeline,1)
        return w
    def _automation_page(self):
        w=QWidget(); l=QVBoxLayout(w); l.addWidget(NexusHeader("Automation","Explicit controls with fail-closed safety"))
        c=NexusCard(); self.master=QCheckBox("Master automation"); self.master.toggled.connect(self.controller.set_automation_enabled); c.body.addWidget(self.master)
        a=QCheckBox("Auto Accept Ready Check"); a.setChecked(self.controller.settings.automation.auto_accept_ready); a.toggled.connect(lambda v:self.controller.update_config(auto_accept_ready=v)); c.body.addWidget(a)
        p=QCheckBox("Auto Pick"); p.setChecked(self.controller.settings.automation.auto_pick); p.toggled.connect(lambda v:self.controller.update_config(auto_pick=v)); c.body.addWidget(p)
        b=QCheckBox("Auto Ban"); b.setChecked(self.controller.settings.automation.ban_mode is BanMode.AUTO); b.toggled.connect(lambda v:self.controller.update_config(ban_mode=BanMode.AUTO if v else BanMode.ASK)); c.body.addWidget(b)
        c.body.addWidget(QLabel("Consequential actions require confirmed authoritative state and post-action verification."))
        l.addWidget(c); l.addStretch(); return w
    def _profile_page(self):
        w=QWidget(); l=QVBoxLayout(w); l.addWidget(NexusHeader("Profile","Champion priorities and session context")); c=NexusCard()
        c.body.addWidget(QLabel(f"{len(self.controller.catalog.all)} champions in catalog")); c.body.addWidget(QLabel(f"{len(self.controller.priorities.to_list())} configured priorities")); l.addWidget(c); l.addStretch(); return w
    def _settings_page(self):
        w=QWidget(); l=QVBoxLayout(w); l.addWidget(NexusHeader("Settings","General · Appearance · Automation · Champion Selection · Notifications · Hotkeys · Accounts · Advanced"))
        for name in ("General","Appearance","Automation","Champion Selection","Notifications","Hotkeys","Accounts","Advanced"):
            b=NexusButton(name,variant="ghost"); b.setEnabled(name=="Automation"); l.addWidget(b)
        l.addStretch(); return w
    def _developer_page(self):
        w=QWidget(); l=QVBoxLayout(w); l.addWidget(NexusHeader("Developer","Diagnostics and authoritative state")); self.diag=QLabel(); self.diag.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); l.addWidget(self.diag); l.addStretch(); return w
    def _manual_select(self):
        rec=self.controller.automation.pending_recommendation
        if rec and rec.winner:self.controller.manual_select(rec.winner.champion.name)
    def _refresh(self):
        snap=self.controller.manager.snapshot(); p=T.PALETTE_DARK
        color={StateConfidence.CONFIRMED:p.dot_connected,StateConfidence.STALE:p.dot_stale,StateConfidence.ERROR:p.dot_disconnected,StateConfidence.UNKNOWN:p.dot_disconnected,StateConfidence.SYNCING:p.dot_searching}[snap.confidence]
        self.phase.set_status(f"{snap.state.value.replace('_',' ').title()} · {snap.confidence.value}",color); self.nav_status.set_status("Connected" if snap.state is not LeagueState.DISCONNECTED else "Disconnected",color)
        rec=self.controller.automation.pending_recommendation
        if rec and rec.winner:self.rec_title.setText(rec.winner.champion.name); self.rec_score.setText(f"Score {rec.winner.score:.1f} · {len(rec.alternates)} alternates"); self.rec_why.setText("Why? "+" · ".join(rec.winner.reasons[:4]))
        else:self.rec_title.setText("No recommendation"); self.rec_score.setText("")
        self.auto_state.set_status(str(self.controller.automation.status).replace("_"," ").title())
        self.master.blockSignals(True); self.master.setChecked(self.controller.settings.automation.master_enabled); self.master.blockSignals(False)
        self.auto_toggle.blockSignals(True); self.auto_toggle.setChecked(self.controller.settings.automation.master_enabled); self.auto_toggle.blockSignals(False)
        self.pool.refresh()
        if hasattr(self.controller.diagnostics,"snapshot"):self.diag.setText(str(self.controller.diagnostics.snapshot()))
    def _on_event(self,ev):
        if ev.kind.startswith(("state.","automation.","lcu.")):
            self.events.insertItem(0,ev.human())
            while self.events.count()>80:self.events.takeItem(self.events.count()-1)
    def closeEvent(self,event):self.bridge.shutdown(); super().closeEvent(event)
