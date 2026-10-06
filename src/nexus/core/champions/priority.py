"""Priority list model — the user's ordered champion preferences.

Backs drag-and-drop reordering, keyboard reorder, temporary disable and the
"never pick" hard exclusion used by the recommendation engine.
"""
from __future__ import annotations

from typing import Iterable, Optional

from .preferences import ChampionPreference


class PriorityList:
    def __init__(self, prefs: Optional[Iterable[ChampionPreference]] = None) -> None:
        self._prefs: dict[str, ChampionPreference] = {}
        for p in prefs or ():
            self._prefs[p.champion_key] = p

    # ------------------------------------------------------------- access
    def get(self, key: str) -> Optional[ChampionPreference]:
        return self._prefs.get(key)

    def ensure(self, key: str) -> ChampionPreference:
        if key not in self._prefs:
            self._prefs[key] = ChampionPreference(champion_key=key)
        return self._prefs[key]

    @property
    def all(self) -> list[ChampionPreference]:
        return sorted(self._prefs.values(),
                      key=lambda p: (p.priority is None,
                                     p.priority if p.priority is not None else 0,
                                     p.champion_key))

    def ranked(self, role: Optional[str] = None) -> list[ChampionPreference]:
        items = [p for p in self.all if p.priority is not None]
        if role:
            r = role.upper()
            items = [p for p in items
                     if p.role_override is None or p.role_override.upper() == r]
        return items

    # ------------------------------------------------------------ mutation
    def set_priority(self, key: str, priority: int) -> None:
        """Assign a 1-based rank; other entries shift to keep ranks dense."""
        priority = max(1, priority)
        target = self.ensure(key)
        old_ranked = [p for p in self.ranked() if p is not target]
        others = sorted(old_ranked, key=lambda p: p.priority or 999)
        others.insert(min(priority - 1, len(others)), target)
        for i, p in enumerate(others, start=1):
            p.priority = i
        target.priority = min(priority, len(others))

    def move(self, key: str, delta: int) -> None:
        ranked = self.ranked()
        keys = [p.champion_key for p in ranked]
        if key not in keys:
            if ranked:
                self.set_priority(key, 1 if delta < 0 else len(keys) + 1)
            else:
                self.set_priority(key, 1)
            return
        idx = keys.index(key)
        new_idx = max(0, min(len(keys) - 1, idx + delta))
        if new_idx == idx:
            return
        moved = self._prefs[key]
        self.set_priority(key, new_idx + 1)
        assert moved.priority == new_idx + 1

    def swap_with_neighbour(self, key: str, towards_start: bool) -> bool:
        ranked = self.ranked()
        keys = [p.champion_key for p in ranked]
        if key not in keys:
            return False
        i = keys.index(key)
        j = i - 1 if towards_start else i + 1
        if j < 0 or j >= len(keys):
            return False
        self.set_priority(key, j + 1)
        return True

    def remove_priority(self, key: str) -> None:
        p = self._prefs.get(key)
        if not p or p.priority is None:
            return
        p.priority = None
        for i, q in enumerate(self.ranked(), start=1):
            q.priority = i

    def toggle_disabled(self, key: str) -> bool:
        p = self.ensure(key)
        p.disabled = not p.disabled
        return p.disabled

    def toggle_never_pick(self, key: str) -> bool:
        p = self.ensure(key)
        p.never_pick = not p.never_pick
        return p.never_pick

    def toggle_preferred(self, key: str) -> bool:
        p = self.ensure(key)
        p.preferred = not p.preferred
        return p.preferred

    def record_pick(self, key: str, now: float) -> None:
        self.ensure(key).record_pick(now)

    # ---------------------------------------------------------- serialise
    def to_list(self) -> list[dict]:
        return [p.to_dict() for p in sorted(self._prefs.values(),
                                            key=lambda p: p.champion_key)]

    @classmethod
    def from_list(cls, rows: Iterable[dict]) -> "PriorityList":
        return cls(ChampionPreference.from_dict(r) for r in rows)
