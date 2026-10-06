"""Thread-safe TTL image/HTTP cache used by champion tiles.

* memory dict keyed by URL with per-entry expiry;
* bounded size (LRU eviction) so long sessions don't grow without limit;
* optional disk mirror under the data dir for champion icons (fast relaunch);
* `get_or_load(url, loader)` runs the loader off the GUI thread (caller's job —
  UI supplies a callable executed on a worker pool).
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional


class TTLCache:
    def __init__(self, max_items: int = 512, ttl_seconds: float = 6 * 3600,
                 disk_dir: Optional[Path] = None) -> None:
        self._max = max_items
        self._ttl = ttl_seconds
        self._disk = Path(disk_dir) if disk_dir else None
        if self._disk:
            self._disk.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._mem: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    # ------------------------------------------------------------- internals
    def _disk_path(self, url: str) -> Optional[Path]:
        if not self._disk:
            return None
        h = hashlib.sha256(url.encode()).hexdigest()[:24]
        return self._disk / h

    # ------------------------------------------------------------------- api
    def get(self, url: str) -> Optional[bytes]:
        now = time.time()
        with self._lock:
            entry = self._mem.get(url)
            if entry and now - entry[0] <= self._ttl:
                self._mem.move_to_end(url)
                self.hits += 1
                return entry[1]
            if entry:
                del self._mem[url]
        dp = self._disk_path(url)
        if dp and dp.exists():
            data = dp.read_bytes()
            self.put(url, data)
            with self._lock:
                self.hits += 1
            return data
        with self._lock:
            self.misses += 1
        return None

    def put(self, url: str, data: bytes) -> None:
        with self._lock:
            self._mem[url] = (time.time(), data)
            self._mem.move_to_end(url)
            while len(self._mem) > self._max:
                self._mem.popitem(last=False)
                self.evictions += 1
        dp = self._disk_path(url)
        if dp:
            try:
                dp.write_bytes(data)
            except OSError:
                pass    # disk mirror is best-effort

    def get_or_load(self, url: str, loader: Callable[[str], Optional[bytes]]) -> Optional[bytes]:
        cached = self.get(url)
        if cached is not None:
            return cached
        data = loader(url)
        if data is not None:
            self.put(url, data)
        return data

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {"items": len(self._mem), "max": self._max,
                    "hits": self.hits, "misses": self.misses,
                    "hit_rate": round(self.hits / total, 3) if total else 0.0,
                    "evictions": self.evictions,
                    "disk": str(self._disk) if self._disk else None}

    def clear(self) -> None:
        with self._lock:
            self._mem.clear()
