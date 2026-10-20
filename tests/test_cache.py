import time
import pytest
from nexus.services.cache.ttl_cache import TTLCache


def test_ttl_cache_put_and_get():
    cache = TTLCache(max_items=10, ttl_seconds=60)
    url = "https://example.com/icon.png"
    data = b"image_data_123"

    assert cache.get(url) is None
    cache.put(url, data)
    assert cache.get(url) == data

    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["items"] == 1
    assert stats["hit_rate"] == 0.5


def test_ttl_cache_lru_eviction():
    cache = TTLCache(max_items=2, ttl_seconds=60)
    cache.put("url1", b"data1")
    cache.put("url2", b"data2")
    cache.put("url3", b"data3")

    # url1 should have been evicted
    assert cache.get("url1") is None
    assert cache.get("url2") == b"data2"
    assert cache.get("url3") == b"data3"

    stats = cache.stats()
    assert stats["evictions"] == 1
    assert stats["items"] == 2


def test_ttl_cache_expiry(monkeypatch):
    cache = TTLCache(max_items=10, ttl_seconds=10)
    url = "https://example.com/icon.png"
    cache.put(url, b"fresh")

    start_time = time.time()
    monkeypatch.setattr(time, "time", lambda: start_time + 5)
    assert cache.get(url) == b"fresh"

    monkeypatch.setattr(time, "time", lambda: start_time + 15)
    assert cache.get(url) is None


def test_ttl_cache_disk_mirror(tmp_path):
    disk_dir = tmp_path / "cache_disk"
    cache = TTLCache(max_items=2, ttl_seconds=60, disk_dir=disk_dir)

    url = "https://example.com/disk_icon.png"
    data = b"disk_bytes"

    cache.put(url, data)

    # Clear memory cache to force fallback to disk
    cache.clear()
    assert cache.stats()["items"] == 0

    fetched = cache.get(url)
    assert fetched == data
    # Loaded back into memory
    assert cache.stats()["items"] == 1


def test_ttl_cache_get_or_load():
    cache = TTLCache(max_items=10, ttl_seconds=60)
    url = "https://example.com/load.png"
    calls = []

    def loader(u):
        calls.append(u)
        return b"loaded_data"

    res1 = cache.get_or_load(url, loader)
    assert res1 == b"loaded_data"
    assert len(calls) == 1

    # Second call should return cached without loader execution
    res2 = cache.get_or_load(url, loader)
    assert res2 == b"loaded_data"
    assert len(calls) == 1
