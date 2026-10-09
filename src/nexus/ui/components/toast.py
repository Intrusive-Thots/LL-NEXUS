"""NexusToast — transient in-app notification card (spec §24/§30).

The shell keeps a vertical stack of toasts anchored bottom-right; each toast
auto-dismisses after `duration_ms` and can be dismissed early with Enter/Esc
or the ✕ button. Level drives border colour via the QSS
`QFrame#NexusToast[level="…"]` rules, and the level word is also shown as text
so meaning never relies on colour alone.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ..theme import tokens as T
from ..components.base import NexusButton


class NexusToast(QFrame):
    dismissed = Signal()
    action_triggered = Signal()

    def __init__(self, title: str, body: str = "", level: str = "info",
                 duration_ms: int = 4000, action_label: Optional[str] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("NexusToast")
        self.setProperty("level", level)
        self.setAccessibleName(f"{level} notification")
        self._action_label = action_label
        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.SP_3, T.SP_2, T.SP_2, T.SP_2)
        lay.setSpacing(T.SP_1)
        head = QHBoxLayout(); head.setSpacing(T.SP_2)
        t = QLabel(title.upper()); t.setObjectName("Headline")
        t.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        head.addWidget(t, 1)
        close = NexusButton("✕", variant="ghost")
        close.setFixedWidth(28); close.setMinimumHeight(20)
        close.clicked.connect(self.close_toast)
        head.addWidget(close)
        lay.addLayout(head)
        if body:
            b = QLabel(body); b.setObjectName("Secondary")
            b.setWordWrap(True)
            b.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            lay.addWidget(b)
        if action_label:
            a = NexusButton(action_label, variant="primary")
            a.clicked.connect(lambda: (self.action_triggered.emit(), self.close_toast()))
            lay.addWidget(a)
        self.setMaximumWidth(int(T.TILE_MIN * 2.6))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        timer_ms = max(1500, int(duration_ms))
        if timer_ms > 0:
            QTimer.singleShot(timer_ms, self.close_toast)

    def close_toast(self) -> None:
        self.dismissed.emit()
        self.deleteLater()

    def keyPressEvent(self, e) -> None:  # Esc dismisses
        if e.key() == Qt.Key.Key_Escape:
            self.close_toast()
        else:
            super().keyPressEvent(e)
