import tempfile
from pathlib import Path
from nexus.services.cache.ttl_cache import TTLCache
from nexus.services.notifications.service import NotificationService, Notification, NotifyLevel
from nexus.core.events.bus import EventBus


def test_ttl_cache_memory_and_expiration(monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr("time.time", lambda: current_time)

    cache = TTLCache(max_items=2, ttl_seconds=10.0, disk_dir=None)

    # Initial stats
    stats = cache.stats()
    assert stats["items"] == 0
    assert stats["hits"] == 0
    assert stats["misses"] == 0

    # Put and Get
    cache.put("url1", b"data1")
    assert cache.get("url1") == b"data1"
    stats = cache.stats()
    assert stats["hits"] == 1

    # Test LRU Eviction
    cache.put("url2", b"data2")
    cache.put("url3", b"data3")  # url1 evicted from memory
    assert cache.get("url1") is None  # miss
    assert cache.stats()["misses"] == 1

    # Test Expiration without disk mirror
    current_time += 15.0  # past 10s TTL
    assert cache.get("url2") is None  # expired miss

    # Test get_or_load
    loaded = cache.get_or_load("url4", lambda u: b"data4")
    assert loaded == b"data4"
    assert cache.get("url4") == b"data4"

    # Clear
    cache.clear()
    assert cache.stats()["items"] == 0


def test_ttl_cache_disk_mirror():
    with tempfile.TemporaryDirectory() as td:
        disk_dir = Path(td)
        cache = TTLCache(max_items=5, ttl_seconds=3600.0, disk_dir=disk_dir)

        cache.put("url1", b"disk_data")
        p1 = cache._disk_path("url1")
        assert p1 is not None and p1.exists()
        assert p1.read_bytes() == b"disk_data"

        # Clear memory cache to test reload from disk mirror
        with cache._lock:
            cache._mem.clear()

        assert cache.get("url1") == b"disk_data"


def test_notification_service():
    bus = EventBus()
    received = []

    def handler(evt):
        received.append(evt)

    bus.subscribe("notify", handler)

    svc = NotificationService(bus, enabled=True)
    svc.info("Info Title", "Info body")
    svc.success("Success Title", "Success body")
    svc.warning("Warning Title", "Warning body")
    svc.critical("Critical Title", "Critical body")

    assert len(received) == 4
    assert received[0].payload["title"] == "Info Title"
    assert received[0].payload["level"] == "info"
    assert received[1].payload["title"] == "Success Title"
    assert received[1].payload["level"] == "success"
    assert received[2].payload["title"] == "Warning Title"
    assert received[2].payload["level"] == "warning"
    assert received[3].payload["title"] == "Critical Title"
    assert received[3].payload["level"] == "critical"

    # Disabled service
    svc_disabled = NotificationService(bus, enabled=False)
    svc_disabled.info("Should not publish", "Body")
    assert len(received) == 4
