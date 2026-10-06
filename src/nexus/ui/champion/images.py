"""Champion imagery pipeline: async loading, caching, graceful placeholders.

* Never touches the GUI thread for network I/O (QThreadPool workers).
* Disk+memory cache via services.cache.TTLCache (DDragon square icons).
* Offline / no-network → deterministic initial-letter placeholder tile so the
  grid always renders (error state handled visually, not with spinners).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, QRunnable, QThreadPool, Signal, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from ...services.cache.ttl_cache import TTLCache
from ..theme import tokens as T

_image_loader = None


def _default_http_loader(url: str) -> Optional[bytes]:
    try:
        import httpx
        r = httpx.get(url, timeout=6.0)
        if r.status_code == 200:
            return r.content
    except Exception:
        return None
    return None


class ChampionImageService(QObject):
    """Shared singleton-ish service; construct once in Application."""

    _instance: Optional["ChampionImageService"] = None

    def __init__(self, cache_dir: Optional[Path] = None, offline: bool = False) -> None:
        super().__init__()
        self.cache = TTLCache(max_items=800, ttl_seconds=7 * 24 * 3600,
                              disk_dir=cache_dir)
        self.pool = QThreadPool.globalInstance()
        self.offline = offline
        ChampionImageService._instance = self

    @classmethod
    def instance(cls) -> Optional["ChampionImageService"]:
        return cls._instance

    # ----------------------------------------------------------------- api
    def pixmap_sync(self, url: str, size: int) -> Optional[QPixmap]:
        data = self.cache.get(url)
        if not data:
            return None
        img = QImage.fromData(data)
        if img.isNull():
            return None
        return QPixmap.fromImage(img).scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)

    def request(self, url: str, size: int, on_ready) -> None:
        """on_ready(QPixmap|None) is invoked on the GUI thread when loaded."""
        pm = self.pixmap_sync(url, size)
        if pm is not None:
            on_ready(pm)
            return
        if self.offline:
            on_ready(None)
            return

        class Task(QRunnable):
            def __init__(self, svc, u, s, cb):
                super().__init__()
                self.svc, self.u, self.s, self.cb = svc, u, s, cb

            def run(self):  # worker thread
                data = self.svc.cache.get_or_load(
                    self.u, _default_http_loader if not self.svc.offline else lambda _: None)
                pm = None
                if data:
                    img = QImage.fromData(data)
                    if not img.isNull():
                        pm = QPixmap.fromImage(img).scaled(
                            self.s, self.s,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
                if pm is not None:
                    QTimer.singleShot(0, lambda: self.cb(pm))
                else:
                    QTimer.singleShot(0, lambda: self.cb(None))

        self.pool.start(Task(self, url, size, on_ready))


def placeholder_pixmap(name: str, size: int, key: str = "") -> QPixmap:
    """Deterministic gradient + initials tile (used offline and while loading)."""
    hue = int(hashlib.sha256((key or name).encode()).hexdigest(), 16) % 360
    bg = QColor.fromHsl(hue, 42, 26)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(bg); p.setPen(QColor(255, 255, 255, 24))
    p.drawRoundedRect(0, 0, size, size, T.RADIUS_MD, T.RADIUS_MD)
    initials = "".join(ch for ch in name.replace("’", "'").split("'")[0][:2]).upper() or "?"
    f = QFont(); f.setPixelSize(int(size * 0.42)); f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(232, 237, 244))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, initials)
    p.end()
    return pm
