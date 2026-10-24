import time
import tempfile
from pathlib import Path
from nexus.services.cache.ttl_cache import TTLCache


def test_ttl_cache_basic_get_put():
    cache = TTLCache(max_items=10, ttl_seconds=60)
    assert cache.get("key1") is None

    cache.put("key1", b"val1")
    assert cache.get("key1") == b"val1"

    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["items"] == 1


def test_ttl_cache_lru_eviction():
    cache = TTLCache(max_items=2, ttl_seconds=60)
    cache.put("a", b"1")
    cache.put("b", b"2")
    cache.put("c", b"3")  # Evicts 'a'

    assert cache.get("a") is None
    assert cache.get("b") == b"2"
    assert cache.get("c") == b"3"
    assert cache.stats()["evictions"] == 1


def test_ttl_cache_ttl_expiration():
    cache = TTLCache(max_items=10, ttl_seconds=0.05)
    cache.put("a", b"1")
    assert cache.get("a") == b"1"

    time.sleep(0.06)
    assert cache.get("a") is None


def test_ttl_cache_disk_mirror():
    with tempfile.TemporaryDirectory() as tmpdir:
        disk_path = Path(tmpdir)
        cache = TTLCache(max_items=10, ttl_seconds=60, disk_dir=disk_path)
        cache.put("http://example.com/icon.png", b"png_data")

        # Clear memory
        cache.clear()
        assert cache.stats()["items"] == 0

        # Read back should load from disk mirror
        loaded = cache.get("http://example.com/icon.png")
        assert loaded == b"png_data"
        assert cache.stats()["items"] == 1


def test_ttl_cache_get_or_load():
    cache = TTLCache(max_items=10, ttl_seconds=60)
    loader_calls = 0

    def loader(url):
        nonlocal loader_calls
        loader_calls += 1
        return b"loaded_data"

    data1 = cache.get_or_load("url1", loader)
    assert data1 == b"loaded_data"
    assert loader_calls == 1

    data2 = cache.get_or_load("url1", loader)
    assert data2 == b"loaded_data"
    assert loader_calls == 1  # From cache, loader not called
