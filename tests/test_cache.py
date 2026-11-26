from __future__ import annotations

import os
import time
from pathlib import Path

from nexus.services.cache.ttl_cache import TTLCache


def test_ttl_cache_mem_put_get():
    cache = TTLCache(max_items=10, ttl_seconds=60)
    assert cache.get("http://example.com/a.png") is None
    assert cache.misses == 1

    cache.put("http://example.com/a.png", b"image_data_a")
    res = cache.get("http://example.com/a.png")
    assert res == b"image_data_a"
    assert cache.hits == 1


def test_ttl_cache_lru_eviction():
    cache = TTLCache(max_items=2, ttl_seconds=60)
    cache.put("url1", b"data1")
    cache.put("url2", b"data2")
    cache.put("url3", b"data3")  # url1 should be evicted

    assert cache.evictions == 1
    assert cache.get("url1") is None
    assert cache.get("url2") == b"data2"
    assert cache.get("url3") == b"data3"


def test_ttl_cache_mem_expiration():
    cache = TTLCache(max_items=10, ttl_seconds=0.1)
    cache.put("url1", b"data1")
    assert cache.get("url1") == b"data1"

    time.sleep(0.15)
    assert cache.get("url1") is None


def test_ttl_cache_disk_mirror_hit_and_expiration(tmp_path: Path):
    disk_dir = tmp_path / "cache"
    cache = TTLCache(max_items=10, ttl_seconds=0.2, disk_dir=disk_dir)

    cache.put("url1", b"data1")
    # Clear memory cache to force disk read
    cache.clear()

    # Should load from disk
    assert cache.get("url1") == b"data1"

    # Clear memory again and age disk file
    cache.clear()
    dp = cache._disk_path("url1")
    assert dp is not None and dp.exists()

    # Set mtime to past
    past_mtime = time.time() - 100
    os.utime(dp, (past_mtime, past_mtime))

    # Should expire disk cache, delete file, and return None
    assert cache.get("url1") is None
    assert not dp.exists()


def test_ttl_cache_get_or_load():
    cache = TTLCache(max_items=10, ttl_seconds=60)
    calls = []

    def loader(url: str) -> bytes | None:
        calls.append(url)
        return b"loaded_data"

    data1 = cache.get_or_load("url1", loader)
    assert data1 == b"loaded_data"
    assert len(calls) == 1

    # Second call uses cache
    data2 = cache.get_or_load("url1", loader)
    assert data2 == b"loaded_data"
    assert len(calls) == 1


def test_ttl_cache_stats_and_clear():
    cache = TTLCache(max_items=10, ttl_seconds=60)
    cache.put("url1", b"data1")
    cache.get("url1")  # Hit
    cache.get("url2")  # Miss

    stats = cache.stats()
    assert stats["items"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5

    cache.clear()
    stats = cache.stats()
    assert stats["items"] == 0
