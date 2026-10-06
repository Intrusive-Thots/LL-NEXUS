"""Nexus visual vocabulary — every reusable widget in one module family.

Rule: pages compose these; they never re-implement a button/card/toggle.
All colours/spacing come from ui.theme.tokens via QSS object names/dynamic
properties, so a theme change restyles the whole app instantly.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QPushButton, QSizePolicy, QToolButton, QVBoxLayout,
    QWidget,
)

from ..theme import tokens as T
from ..theme.qss import palette_for


# ------------------------------------------------------------------ buttons
class NexusButton(QPushButton):
    def __init__(self, text: str = "", variant: str = "default",
                 shortcut: Optional[str] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        if variant != "default":
            self.setProperty("NexusVariant", variant)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(T.CONTROL_H_MD if variant == "default" else T.CONTROL_H_LG)
        if shortcut:
            sc = QShortcut(QKeySequence(shortcut), self)
            sc.activated.connect(self.click)


class NexusIconButton(QToolButton):
    clicked_ = Signal()

    def __init__(self, glyph: str, tooltip: str = "", icon_size: int = T.ICON_MD,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("NexusIconButton")
        self.setText(glyph)
        f = QFont(); f.setPointSize(int(icon_size * 0.75)); self.setFont(f)
        if tooltip:
            self.setToolTip(tooltip)
            self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self.clicked_)


# ------------------------------------------------------------------- toggle
class NexusToggle(QAbstractButton):
    """Custom ON/OFF switch with non-color state indication (text + position)."""

    toggled_on = Signal(bool)

    def __init__(self, checked: bool = False, label: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self._label = label
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggled.connect(self._on_toggled)
        self.setMinimumWidth(64)
        self.setMinimumHeight(28)
        self.setAccessibleName(label or "toggle")

    def _on_toggled(self, on: bool) -> None:
        self._checked = on
        self.update()
        self.toggled_on.emit(on)

    def is_on(self) -> bool:
        return self._checked

    def set_on(self, on: bool) -> None:
        if on != self._checked:
            self.setChecked(on)

    def sizeHint(self):
        return super().sizeHint().expandedTo(self.minimumSize())

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        from PySide6.QtGui import QPainter, QColor, QFontMetrics
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = palette_for(_ACTIVE_THEME[0])
        w, h = self.width(), self.height()
        track_h = 22
        y = (h - track_h) // 2
        track = self.rect().adjusted(0, y, 0, -(y))
        bg = QColor(pal.accent_blue) if self._checked else QColor(pal.bg_input)
        border = QColor(pal.border_strong) if not self._checked else QColor(pal.accent_blue)
        p.setPen(border)
        p.setBrush(bg)
        p.drawRoundedRect(track, track_h / 2, track_h / 2)
        knob_d = track_h - 6
        kx = track.right() - knob_d - 3 if self._checked else track.left() + 3
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF") if self._checked else QColor(pal.text_secondary))
        p.drawEllipse(kx, track.top() + 3, knob_d, knob_d)
        # textual state for accessibility (never colour alone)
        p.setPen(QColor(pal.text_primary))
        f = p.font(); f.setPointSize(T.TYPOGRAPHY.size_caption); p.setFont(f)
        txt = "ON" if self._checked else "OFF"
        tx = track.left() + 8 if self._checked else track.right() - 26
        p.drawText(tx, track.top(), 30, track.height(),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, txt)
        p.end()


_ACTIVE_THEME = ["dark"]


def set_active_theme(theme: str) -> None:
    _ACTIVE_THEME[0] = theme


# -------------------------------------------------------------------- cards
class NexusCard(QFrame):
    def __init__(self, raised: bool = False, parent: Optional[QWidget] = None,
                 elevation: int = 1) -> None:
        super().__init__(parent)
        self.setObjectName("NexusCard")
        if raised:
            self.setProperty("raised", True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.SP_4, T.SP_4, T.SP_4, T.SP_4)
        lay.setSpacing(T.SP_3)
        self._layout = lay
        if elevation and _ACTIVE_THEME[0] == "dark":
            eff = QGraphicsDropShadowEffect(self)
            blur, dy, _rgba = getattr(T, f"ELEVATION_{elevation}", T.ELEVATION_1)
            eff.setBlurRadius(blur); eff.setOffset(0, dy)
            eff.setColor(QColor(0, 0, 0, 90))
            self.setGraphicsEffect(eff)

    @property
    def body(self) -> QVBoxLayout:
        return self._layout


class NexusSection(QWidget):
    """Collapsible titled section — progressive disclosure primitive."""

    def __init__(self, title: str, parent: Optional[QWidget] = None,
                 collapsed: bool = False) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(T.SP_2)
        self.header = NexusButton(f"{'▸' if collapsed else '▾'}  {title.upper()}",
                                  variant="ghost")
        self.header.setObjectName("SectionHeader")
        self.header.setStyleSheet("text-align:left; min-height:24px;")
        self.content = QFrame()
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(T.SP_2, 0, 0, 0)
        self.content_lay.setSpacing(T.SP_2)
        outer.addWidget(self.header)
        outer.addWidget(self.content)
        self.content.setVisible(not collapsed)
        self._collapsed = collapsed
        self._title = title
        self.header.clicked.connect(self.toggle)

    def toggle(self) -> None:
        self._collapsed = not self._collapsed
        self.content.setVisible(not self._collapsed)
        self.header.setText(f"{'▸' if self._collapsed else '▾'}  {self._title.upper()}")

    @property
    def collapsed(self) -> bool:
        return self._collapsed


class NexusHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        col = QVBoxLayout()
        col.setSpacing(T.SP_1)
        t = QLabel(title); t.setObjectName("Headline")
        lay.addLayout(col)
        col.addWidget(t)
        if subtitle:
            s = QLabel(subtitle); s.setObjectName("Secondary")
            col.addWidget(s)
        lay.addStretch(1)


# ------------------------------------------------------------- status/badge
class NexusStatus(QLabel):
    """● glyph + text; colour AND word so meaning survives grayscale."""

    def __init__(self, text: str = "", dot_color: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self._dot = dot_color
        self.setTextFormat(Qt.TextFormat.RichText)
        self.render(text)

    def set_status(self, text: str, dot_color: str = "") -> None:
        self._dot = dot_color
        self.render(text)

    def render(self, text: str) -> None:
        pal = palette_for(_ACTIVE_THEME[0])
        color = self._dot or pal.text_secondary
        dot = f'<span style="color:{color};">●</span>&nbsp;' if self._dot else ""
        self.setText(f"{dot}{text}")


class NexusBadge(QLabel):
    def __init__(self, text: str = "", level: str = "muted", parent: Optional[QWidget] = None) -> None:
        super().__init__(text.upper(), parent)
        self.setProperty("NexusBadge", level)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


# -------------------------------------------------------------------- search
class NexusSearch(QLineEdit):
    def __init__(self, placeholder: str = "Search…", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setAccessibleName(placeholder)


# ---------------------------------------------------------------- activity
class NexusActivityRow(QFrame):
    """One timeline row: time · marker · primary · secondary."""

    def __init__(self, clock: str, marker: str, primary: str,
                 secondary: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(T.SP_2, T.SP_1, T.SP_2, T.SP_1)
        lay.setSpacing(T.SP_2)
        t = QLabel(clock); t.setObjectName("Muted")
        m = QLabel(marker)
        m.setMinimumWidth(T.SP_5)
        m.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col = QVBoxLayout(); col.setSpacing(0)
        p = QLabel(primary)
        lay.addWidget(t); lay.addWidget(m); lay.addLayout(col); lay.addStretch(1)
        col.addWidget(p)
        if secondary:
            s = QLabel(secondary); s.setObjectName("Secondary"); col.addWidget(s)
