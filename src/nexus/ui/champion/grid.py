"""Champion tile + responsive grid (spec §26).

NexusChampionTile — one champion: image, name, rank badge, flags.
NexusChampionGrid — FlowLayout-based responsive grid:
  * column count derived from viewport width and DPI-scaled tile size
    (never a hard-coded three columns);
  * lazy loading with prefetch of the visible page;
  * keyboard navigation (arrows/Home/End/Enter) with visible focus;
  * preserves selection & scroll across re-population (state preservation).
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Optional

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ...core.champions.models import Champion
from ..components.base import NexusBadge
from ..theme import tokens as T
from .images import ChampionImageService, placeholder_pixmap


class NexusChampionTile(QFrame):
    clicked_ = Signal(object)          # Champion
    context_menu = Signal(object, QPoint := __import__("PySide6.QtCore", fromlist=["QPoint"]).QPoint)

    def __init__(self, champion: Champion, tile_w: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.champion = champion
        self.setProperty("NexusTile", "champion")
        self.setFixedSize(tile_w, int(tile_w * 1.34))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        img_h = tile_w - T.SP_2
        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.SP_1, T.SP_1, T.SP_1, T.SP_1)
        lay.setSpacing(2)
        self.image = QLabel()
        self.image.setFixedSize(img_h, img_h)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setPixmap(placeholder_pixmap(champion.name, img_h, champion.key))
        name = QLabel(champion.name)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = name.font(); f.setPixelSize(max(10, int(tile_w * 0.11))); f.setBold(True)
        name.setFont(f)
        name.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        row = QHBoxLayout(); row.setSpacing(2)
        self.rank_badge = NexusBadge("", "info")
        self.flags = QLabel("")
        self.flags.setObjectName("Accent")
        row.addWidget(self.rank_badge)
        row.addStretch(1)
        row.addWidget(self.flags)
        lay.addWidget(self.image)
        lay.addWidget(name)
        lay.addLayout(row)
        self.setToolTip(champion.name)
        self.setAccessibleName(f"{champion.name}, {', '.join(champion.roles)}")
        self._loaded = False

    # ------------------------------------------------------------------ api
    def set_rank(self, rank: Optional[int]) -> None:
        self.rank_badge.setText(f"#{rank}" if rank else "")
        self.rank_badge.setVisible(bool(rank))

    def set_flags(self, text: str) -> None:
        self.flags.setText(text)

    def set_dimmed(self, dim: bool) -> None:
        self.setProperty("dimmed", dim)
        self.style().unpolish(self); self.style().polish(self)

    def set_selected(self, sel: bool) -> None:
        self.setProperty("selected", sel)
        self.style().unpolish(self); self.style().polish(self)

    def load_image(self, svc: Optional[ChampionImageService]) -> None:
        if self._loaded or svc is None:
            return
        self._loaded = True
        size = self.image.width()

        def ready(pm):
            if pm is not None:
                self.image.setPixmap(pm)

        svc.request(self.champion.square_icon_url, size, ready)

    # ------------------------------------------------------------- interaction
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked_.emit(self.champion)
        super().mousePressEvent(e)

    def contextMenuEvent(self, e) -> None:
        self.context_menu.emit(self.champion, e.globalPos())

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.clicked_.emit(self.champion)
        else:
            super().keyPressEvent(e)

    def focusInEvent(self, e) -> None:
        self.set_selected(True)
        super().focusInEvent(e)

    def focusOutEvent(self, e) -> None:
        if not self.property("selected"):
            pass
        super().focusOutEvent(e)


# ---------------------------------------------------------------- flow layout
class _FlowLayout(QWidget):
    """Minimal flow layout used by the grid (wraps tiles to available width)."""

    def __init__(self, host: "NexusChampionGrid") -> None:
        super().__init__(host)
        self.host = host
        self.items: list[QWidget] = []
        self.setContentsMargins(0, 0, 0, 0)

    def add_widget(self, w: QWidget) -> None:
        self.items.append(w)

    def clear(self) -> None:
        for w in self.items:
            w.setParent(None); w.deleteLater()
        self.items.clear()

    def count(self) -> int:
        return len(self.items)

    def widget_at(self, i: int) -> QWidget:
        return self.items[i]

    def itemAt(self, i: int):  # noqa: N802 — Qt API
        return None

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        cols = max(1, width // (self.host.tile_w + self.host.gap))
        rows = math.ceil(len(self.items) / cols) if self.items else 0
        return rows * (self.host.tile_h + self.host.gap)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        w = self.host.width()
        h = self.heightForWidth(w) if w else 0
        return QSize(w, h)

    def doLayout(self, rect: QRect) -> None:  # noqa: N802
        cols = max(1, rect.width() // (self.host.tile_w + self.host.gap))
        self.host.columns = cols
        x = y = 0
        for it in self.items:
            it.setGeometry(rect.x() + x, rect.y() + y,
                           self.host.tile_w, self.host.tile_h)
            x += self.host.tile_w + self.host.gap
            if x + self.host.tile_w > rect.width():
                x = 0
                y += self.host.tile_h + self.host.gap

    def resizeEvent(self, e) -> None:
        self.doLayout(QRect(0, 0, self.width(), self.height()))
        self.host._on_layout_changed()


class NexusChampionGrid(QScrollArea):
    tile_ready = Signal(object)
    tile_clicked = Signal(object)
    tile_context = Signal(object, object)

    def __init__(self, parent: Optional[QWidget] = None, base_tile: int = T.TILE_MIN) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.base_tile = base_tile
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        self.tile_w = int(base_tile * max(1.0, math.sqrt(dpr)))
        self.tile_h = int(self.tile_w * 1.34)
        self.gap = T.SP_2
        self.columns = 1
        self._champions: list[Champion] = []
        self._tiles: dict[str, NexusChampionTile] = {}
        self._selected_key: Optional[str] = None
        self._svc = ChampionImageService.instance()
        container = QWidget()
        self.flow = _FlowLayout(container)
        container.setLayout(self.flow)
        self.setWidget(container)
        self.setAccessibleName("Champion grid")

    # ------------------------------------------------------------------- api
    def populate(self, champions: Iterable[Champion], ranks: Optional[dict[str, int]] = None,
                 flags: Optional[dict[str, str]] = None, keep_selection: bool = True) -> None:
        ranks = ranks or {}
        flags = flags or {}
        self._champions = list(champions)
        self.flow.clear()
        self._tiles.clear()
        for c in self._champions:
            tile = NexusChampionTile(c, self.tile_w)
            tile.set_rank(ranks.get(c.key))
            tile.set_flags(flags.get(c.key, ""))
            tile.clicked_.connect(self.tile_clicked.emit)
            tile.context_menu.connect(self.tile_context.emit)
            self.flow.add_widget(tile)
            self._tiles[c.key] = tile
            if keep_selection and c.key == self._selected_key:
                tile.set_selected(True)
        self.flow.doLayout(QRect(0, 0, max(self.viewport().width(), self.tile_w),
                                 self.flow.heightForWidth(self.viewport().width())))
        self.flow.resize(self.viewport().size())
        self._prefetch_visible()

    def set_selection(self, key: Optional[str]) -> None:
        self._selected_key = key
        for k, t in self._tiles.items():
            t.set_selected(k == key)

    def selected_key(self) -> Optional[str]:
        return self._selected_key

    def scroll_to_key(self, key: str) -> None:
        t = self._tiles.get(key)
        if t:
            self.ensureWidgetVisible(t, 0, self.tile_h)

    def focus_first(self) -> None:
        if self.flow.count():
            self.flow.widget_at(0).setFocus()

    def _on_layout_changed(self) -> None:
        self._prefetch_visible()

    def _visible_indices(self) -> tuple[int, int]:
        top = self.verticalScrollBar().value()
        bottom = top + self.viewport().height()
        per_row = max(1, self.columns)
        first_row = max(0, top // (self.tile_h + self.gap))
        last_row = min((bottom + self.tile_h) // (self.tile_h + self.gap), 
                       math.ceil(self.flow.count() / per_row))
        return first_row * per_row, last_row * per_row

    def _prefetch_visible(self) -> None:
        lo, hi = self._visible_indices()
        for i in range(lo, min(hi, self.flow.count())):
            w = self.flow.widget_at(i)
            if isinstance(w, NexusChampionTile):
                w.load_image(self._svc)

    # ------------------------------------------------------------ keyboard
    def keyPressEvent(self, e) -> None:
        n = self.flow.count()
        if n == 0:
            return super().keyPressEvent(e)
        cur = -1
        for i in range(n):
            if self.flow.widget_at(i).hasFocus():
                cur = i
                break
        cols = max(1, self.columns)
        nxt = None
        if e.key() == Qt.Key.Key_Right and cur >= 0:
            nxt = min(cur + 1, n - 1)
        elif e.key() == Qt.Key.Key_Left and cur >= 0:
            nxt = max(cur - 1, 0)
        elif e.key() == Qt.Key.Key_Down and cur >= 0:
            nxt = min(cur + cols, n - 1)
        elif e.key() == Qt.Key.Key_Up and cur >= 0:
            nxt = max(cur - cols, 0)
        elif e.key() == Qt.Key.Key_Home:
            nxt = 0
        elif e.key() == Qt.Key.Key_End:
            nxt = n - 1
        if nxt is not None:
            w = self.flow.widget_at(nxt)
            w.setFocus()
            self.ensureWidgetVisible(w, 0, self.tile_h)
            return
        super().keyPressEvent(e)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        w = self.viewport().width()
        self.flow.doLayout(QRect(0, 0, w, self.flow.heightForWidth(w)))
        self.flow.resize(self.viewport().size())
        self._prefetch_visible()
