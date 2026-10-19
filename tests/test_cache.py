import time
from nexus.services.cache.ttl_cache import TTLCache


def test_ttl_cache_mem_put_get():
    cache = TTLCache(max_items=10, ttl_seconds=60)
    cache.put("https://example.com/img1.png", b"data1")
    assert cache.get("https://example.com/img1.png") == b"data1"
    assert cache.get("https://example.com/nonexistent") is None

    st = cache.stats()
    assert st["hits"] == 1
    assert st["misses"] == 1
    assert st["items"] == 1


def test_ttl_cache_expiration(monkeypatch):
    cache = TTLCache(max_items=10, ttl_seconds=2)
    cache.put("https://example.com/img1.png", b"data1")

    assert cache.get("https://example.com/img1.png") == b"data1"

    # Fast forward time past TTL
    future_time = time.time() + 10
    monkeypatch.setattr(time, "time", lambda: future_time)

    assert cache.get("https://example.com/img1.png") is None


def test_ttl_cache_lru_eviction():
    cache = TTLCache(max_items=2, ttl_seconds=60)
    cache.put("k1", b"v1")
    cache.put("k2", b"v2")
    cache.put("k3", b"v3")  # Evicts k1

    assert cache.get("k1") is None
    assert cache.get("k2") == b"v2"
    assert cache.get("k3") == b"v3"

    st = cache.stats()
    assert st["evictions"] == 1


def test_ttl_cache_disk_mirror(tmp_path):
    cache = TTLCache(max_items=10, ttl_seconds=60, disk_dir=tmp_path)
    url = "https://example.com/icon.png"
    cache.put(url, b"icon_bytes")

    # Clear memory cache to force disk hit
    cache.clear()
    assert cache.stats()["items"] == 0

    retrieved = cache.get(url)
    assert retrieved == b"icon_bytes"


def test_ttl_cache_get_or_load():
    cache = TTLCache(max_items=10, ttl_seconds=60)
    url = "https://example.com/load.png"

    loaded = cache.get_or_load(url, lambda u: b"loaded_data")
    assert loaded == b"loaded_data"

    # Second call uses cached version without invoking loader
    calls = []
    def spy_loader(u):
        calls.append(u)
        return b"new_data"

    cached = cache.get_or_load(url, spy_loader)
    assert cached == b"loaded_data"
    assert len(calls) == 0
