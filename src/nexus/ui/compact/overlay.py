"""Compact overlay (spec §26) — always-on-top mini panel.

Shows live phase, countdown ring/bar, and the current recommendation with a
single primary action button. Frameless + WindowStaysOnTopHint; draggable by
pressing anywhere on the surface. Sized by settings.appearance.compact_size.
The shell owns show/hide; this widget only renders state fed to it.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

from ...core.state.models import LeagueState, StateConfidence
from ..components.base import NexusButton, NexusStatus
from ..theme import tokens as T

_SIZES = {  # width x height per compact_size token
    "small": (280, 150),
    "medium": (320, 170),
    "large": (360, 190),
}


class CompactOverlay(QFrame):
    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setObjectName("CompactOverlay")
        self.controller = controller
        self._drag_offset: Optional[QPoint] = None

        w, h = _SIZES.get(
            getattr(controller.settings.appearance, "compact_size", "medium"),
            _SIZES["medium"])
        self.setFixedSize(w, h)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAccessibleName("Compact nexus overlay")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.SP_3, T.SP_2, T.SP_3, T.SP_2)
        lay.setSpacing(T.SP_1)

        head = QHBoxLayout(); head.setSpacing(T.SP_2)
        self.status = NexusStatus("Disconnected")
        head.addWidget(self.status, 1)
        close = NexusButton("✕", variant="ghost")
        close.setFixedWidth(26); close.setMinimumHeight(18)
        close.clicked.connect(self.hide)
        head.addWidget(close)
        lay.addLayout(head)

        self.champ = QLabel("No recommendation")
        cf = QFont(); cf.setPointSize(cf.pointSize() + 6); cf.setBold(True)
        self.champ.setFont(cf)
        self.champ.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction)
        lay.addWidget(self.champ)

        self.detail = QLabel("")
        self.detail.setObjectName("Secondary")
        lay.addWidget(self.detail)

        self.timer_bar = QProgressBar()
        self.timer_bar.setRange(0, 100)
        self.timer_bar.setValue(0)
        self.timer_bar.setTextVisible(False)
        self.timer_bar.setFixedHeight(6)
        self.timer_bar.setAccessibleName("Phase timer")
        lay.addWidget(self.timer_bar)

        self.action = NexusButton("OPEN NEXUS", variant="primary")
        self.action.clicked.connect(self._expand)
        lay.addWidget(self.action)

    expand_requested = None  # set by shell: callable() -> None

    def _expand(self) -> None:
        if callable(self.expand_requested):
            self.expand_requested()

    # ---------------------------------------------------------------- refresh
    def refresh(self) -> None:
        c = self.controller
        snap = c.manager.snapshot()
        p = T.PALETTE_DARK
        color = {StateConfidence.CONFIRMED: p.dot_connected,
                 StateConfidence.STALE: p.dot_stale,
                 StateConfidence.ERROR: p.dot_disconnected,
                 StateConfidence.UNKNOWN: p.dot_disconnected,
                 StateConfidence.SYNCING: p.dot_searching}[snap.confidence]
        self.status.set_status(snap.state.value.replace("_", " ").title(), color)
        rec = c.automation.pending_recommendation
        if rec and rec.winner:
            self.champ.setText(rec.winner.champion.name)
            self.detail.setText(f"Score {rec.winner.score:.1f}")
            in_cs = snap.state in (LeagueState.CHAMP_SELECT,
                                   LeagueState.PICK_PHASE,
                                   LeagueState.BAN_PHASE)
            self.action.setText("PICK ✓" if in_cs else "OPEN NEXUS")
        else:
            self.champ.setText("No recommendation")
            self.detail.setText("")
        remaining = snap.timer_seconds
        total = snap.timer_total_seconds
        if isinstance(remaining, (int, float)) and isinstance(total, (int, float)) and total > 0:
            self.timer_bar.setValue(int(max(0.0, remaining) * 100 / total))
        else:
            self.timer_bar.setValue(0)

    # ------------------------------------------------------------- drag logic
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._drag_offset is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(e)
