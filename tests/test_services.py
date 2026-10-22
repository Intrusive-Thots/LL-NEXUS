import tempfile
import time
from pathlib import Path
from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService
from nexus.services.cache.ttl_cache import TTLCache


def test_ttl_cache_mem_put_get_and_stats():
    cache = TTLCache(max_items=3, ttl_seconds=10.0)
    assert cache.get("http://example.com/a") is None
    assert cache.stats()["misses"] == 1

    cache.put("http://example.com/a", b"data_a")
    assert cache.get("http://example.com/a") == b"data_a"

    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["items"] == 1


def test_ttl_cache_expiration():
    cache = TTLCache(max_items=10, ttl_seconds=0.05)
    cache.put("key1", b"val1")
    assert cache.get("key1") == b"val1"

    time.sleep(0.06)
    assert cache.get("key1") is None


def test_ttl_cache_lru_eviction():
    cache = TTLCache(max_items=2, ttl_seconds=60.0)
    cache.put("key1", b"val1")
    cache.put("key2", b"val2")
    cache.put("key3", b"val3")  # Evicts key1

    assert cache.get("key1") is None
    assert cache.get("key2") == b"val2"
    assert cache.get("key3") == b"val3"
    assert cache.stats()["evictions"] == 1


def test_ttl_cache_disk_mirror_and_get_or_load():
    with tempfile.TemporaryDirectory() as td:
        disk_path = Path(td)
        cache1 = TTLCache(max_items=5, ttl_seconds=60.0, disk_dir=disk_path)
        cache1.put("http://example.com/img", b"binary_image_data")

        # Create a second cache instance using same disk directory
        cache2 = TTLCache(max_items=5, ttl_seconds=60.0, disk_dir=disk_path)
        # Reading from cache2 triggers disk read on memory miss
        assert cache2.get("http://example.com/img") == b"binary_image_data"

        # Test get_or_load
        loaded = cache2.get_or_load("http://example.com/new", lambda url: b"loaded_data")
        assert loaded == b"loaded_data"
        assert cache2.get("http://example.com/new") == b"loaded_data"

        cache2.clear()
        assert cache2.stats()["items"] == 0


def test_diagnostics_service_snapshot_redaction_and_export():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    diag = DiagnosticsService(mgr, bus)

    class DummyComponent:
        def diagnostics(self):
            return {
                "auth_token": "secret123",
                "password": "my_password",
                "champion_key": "Ahri",
            }

    diag.register("dummy", DummyComponent())
    diag.register("custom_func", lambda: {"session": "abc_session_xyz"})

    snap = diag.snapshot()
    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert snap["dummy"]["auth_token"] == "[REDACTED]"
    assert snap["dummy"]["password"] == "[REDACTED]"
    assert snap["dummy"]["champion_key"] == "Ahri"
    assert snap["custom_func"]["session"] == "[REDACTED]"

    export_str = diag.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in export_str
    assert "[application]" in export_str
    assert "[dummy]" in export_str
