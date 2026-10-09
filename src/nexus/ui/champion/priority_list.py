"""NexusPriorityList — drag-and-drop + keyboard-reorderable priority list.

Backed by core.champions.priority.PriorityList; emits change signals so the
recommendation engine and persistence stay in sync. Right-click context menu
supports disable / never-pick / preferred / remove-rank (spec §10).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QListWidget, QMenu, QVBoxLayout, QWidget

from ...core.champions.models import Champion, ChampionCatalog
from ...core.champions.priority import PriorityList
from ..components.base import NexusSearch
from ..theme import tokens as T


class NexusPriorityList(QListWidget):
    changed = Signal()

    def __init__(self, priorities: PriorityList, catalog: ChampionCatalog,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PriorityList")
        self.priorities = priorities
        self.catalog = catalog
        from PySide6.QtWidgets import QAbstractItemView
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAccessibleName("Champion priority list")
        self.setToolTip("Drag to reorder • Alt+↑/↓ keyboard reorder • right-click for options")
        self.model().rowsMoved.connect(lambda *a: self._commit_reorder())
        self.reload()

    # ------------------------------------------------------------------ view
    def reload(self) -> None:
        self.clear()
        for pref in self.priorities.ranked():
            champ = self.catalog.by_key(pref.champion_key)
            name = champ.name if champ else pref.champion_key
            flags = []
            if pref.disabled:
                flags.append("⏸ disabled")
            if pref.never_pick:
                flags.append("🚫 never")
            if pref.preferred:
                flags.append("★ preferred")
            label = f"#{pref.priority:<2} {name}"
            if flags:
                label += "   " + "  ".join(flags)
            from PySide6.QtWidgets import QListWidgetItem
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, pref.champion_key)
            it.setToolTip(label)
            if pref.disabled or pref.never_pick:
                f = it.font(); f.setItalic(True); it.setFont(f)
            self.addItem(it)
        self.changed.emit()

    def _current_key(self) -> Optional[str]:
        it = self.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    # ------------------------------------------------------------- mutations
    def _commit_reorder(self) -> None:
        """Translate a model row-move into PriorityList rank changes."""
        keys = [self.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.count())]
        for idx, key in enumerate(keys, start=1):
            self.priorities.set_priority(key, idx)
        self.reload()

    def move_current(self, delta: int) -> None:
        key = self._current_key()
        if not key:
            return
        self.priorities.move(key, delta)
        self.reload()
        # restore selection on the moved row
        for i in range(self.count()):
            if self.item(i).data(Qt.ItemDataRole.UserRole) == key:
                self.setCurrentRow(i)
                break

    def keyPressEvent(self, e) -> None:
        if e.modifiers() & Qt.AltModifier and e.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.move_current(-1 if e.key() == Qt.Key.Key_Up else 1)
            return
        super().keyPressEvent(e)

    # ------------------------------------------------------------ context menu
    def _menu(self, event) -> None:
        self._show_menu(event.globalPos())

    def contextMenuEvent(self, e) -> None:  # noqa: N802
        self._show_menu(e.globalPos())

    def _show_menu(self, global_pos) -> None:
        key = self._current_key()
        if not key:
            return
        menu = QMenu(self)
        pref = self.priorities.ensure(key)
        champ = self.catalog.by_key(key)
        title = champ.name if champ else key
        menu.setTitle(title)
        act_disable = QAction("Temporarily disable" if not pref.disabled else "Re-enable", menu)
        act_never = QAction("Never pick" if not pref.never_pick else "Allow picking", menu)
        act_pref = QAction("Mark preferred ★" if not pref.preferred else "Unmark preferred", menu)
        act_up = QAction("Move up (Alt+↑)", menu)
        act_down = QAction("Move down (Alt+↓)", menu)
        act_remove = QAction("Remove from priority list", menu)
        menu.addAction(act_up); menu.addAction(act_down); menu.addSeparator()
        menu.addAction(act_disable); menu.addAction(act_never); menu.addAction(act_pref)
        menu.addSeparator(); menu.addAction(act_remove)
        chosen = menu.exec(global_pos)
        if chosen is act_disable:
            self.priorities.toggle_disabled(key)
        elif chosen is act_never:
            self.priorities.toggle_never_pick(key)
        elif chosen is act_pref:
            self.priorities.toggle_preferred(key)
        elif chosen is act_up:
            self.priorities.move(key, -1)
        elif chosen is act_down:
            self.priorities.move(key, 1)
        elif chosen is act_remove:
            self.priorities.remove_priority(key)
        else:
            return
        self.reload()
