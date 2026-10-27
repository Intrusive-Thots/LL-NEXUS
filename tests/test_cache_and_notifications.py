import os
import time
from nexus.core.events.bus import EventBus
from nexus.services.cache.ttl_cache import TTLCache
from nexus.services.notifications.service import NotificationService, Notification, NotifyLevel


def test_ttl_cache_memory_and_eviction():
    cache = TTLCache(max_items=2, ttl_seconds=10.0)
    assert cache.get("url1") is None
    assert cache.stats()["misses"] == 1

    cache.put("url1", b"data1")
    assert cache.get("url1") == b"data1"
    assert cache.stats()["hits"] == 1

    cache.put("url2", b"data2")
    cache.put("url3", b"data3")  # url1 evicted due to LRU (max_items=2)

    assert cache.get("url1") is None
    assert cache.get("url2") == b"data2"
    assert cache.get("url3") == b"data3"
    assert cache.stats()["evictions"] >= 1


def test_ttl_cache_memory_expiration():
    cache = TTLCache(max_items=10, ttl_seconds=0.05)
    cache.put("exp_url", b"exp_data")
    assert cache.get("exp_url") == b"exp_data"

    time.sleep(0.06)
    assert cache.get("exp_url") is None


def test_ttl_cache_disk_mirror_and_expiration(tmp_path):
    disk_dir = tmp_path / "cache"
    cache = TTLCache(max_items=10, ttl_seconds=0.1, disk_dir=disk_dir)

    url = "https://ddragon.leagueoflegends.com/cdn/14.1.1/img/champion/Ahri.png"
    cache.put(url, b"ahri_icon")

    # Clear memory cache to force disk hit
    cache.clear()
    assert cache.get(url) == b"ahri_icon"

    # Memory cleared again, wait for disk TTL expiration
    cache.clear()
    time.sleep(0.12)
    assert cache.get(url) is None


def test_ttl_cache_get_or_load():
    cache = TTLCache(max_items=10, ttl_seconds=5.0)
    loaded_calls = []

    def loader(u):
        loaded_calls.append(u)
        return b"loaded_bytes"

    res1 = cache.get_or_load("loader_url", loader)
    assert res1 == b"loaded_bytes"
    assert len(loaded_calls) == 1

    # Second call should return cached bytes without calling loader
    res2 = cache.get_or_load("loader_url", loader)
    assert res2 == b"loaded_bytes"
    assert len(loaded_calls) == 1


def test_notification_service_levels():
    bus = EventBus()
    notifications = NotificationService(bus, enabled=True)

    events = []
    bus.subscribe("notify", lambda ev: events.append(ev))

    notifications.info("Info Title", "Info body")
    notifications.success("Success Title", "Success body")
    notifications.warning("Warning Title", "Warning body")
    notifications.critical("Critical Title", "Critical body")

    assert len(events) == 4
    assert events[0].payload["level"] == NotifyLevel.INFO.value
    assert events[1].payload["level"] == NotifyLevel.SUCCESS.value
    assert events[2].payload["level"] == NotifyLevel.WARNING.value
    assert events[3].payload["level"] == NotifyLevel.CRITICAL.value


def test_notification_service_disabled():
    bus = EventBus()
    notifications = NotificationService(bus, enabled=False)

    events = []
    bus.subscribe("notify", lambda ev: events.append(ev))

    notifications.info("Title", "Body")
    assert len(events) == 0
