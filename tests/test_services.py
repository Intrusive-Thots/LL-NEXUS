import os
import time
from pathlib import Path
import pytest

from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact
from nexus.services.cache.ttl_cache import TTLCache
from nexus.services.notifications.service import NotificationService, Notification, NotifyLevel


# ------------------------------------------------------------------- TTLCache tests
def test_ttl_cache_put_get_memory():
    cache = TTLCache(max_items=3, ttl_seconds=10)
    cache.put("https://example.com/1.png", b"data1")
    assert cache.get("https://example.com/1.png") == b"data1"
    assert cache.get("https://example.com/missing.png") is None

    stats = cache.stats()
    assert stats["items"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_ttl_cache_lru_eviction():
    cache = TTLCache(max_items=2, ttl_seconds=10)
    cache.put("key1", b"val1")
    cache.put("key2", b"val2")
    cache.put("key3", b"val3")  # Should evict key1

    assert cache.get("key1") is None
    assert cache.get("key2") == b"val2"
    assert cache.get("key3") == b"val3"
    assert cache.stats()["evictions"] == 1


def test_ttl_cache_expiration():
    cache = TTLCache(max_items=5, ttl_seconds=0.1)
    cache.put("key1", b"val1")
    time.sleep(0.15)
    assert cache.get("key1") is None


def test_ttl_cache_disk_mirror_and_expiration(tmp_path):
    disk_dir = tmp_path / "cache"
    cache = TTLCache(max_items=2, ttl_seconds=0.2, disk_dir=disk_dir)
    url = "https://example.com/icon.png"
    cache.put(url, b"icon_bytes")

    # Clear memory cache to force reading from disk
    cache.clear()
    assert cache.stats()["items"] == 0

    # Read from disk mirror
    assert cache.get(url) == b"icon_bytes"

    # Now let disk expire and test cleanup
    cache.clear()
    time.sleep(0.25)
    assert cache.get(url) is None

    # Disk file should be unlinked
    dp = cache._disk_path(url)
    assert dp is not None and not dp.exists()


def test_ttl_cache_get_or_load():
    cache = TTLCache(max_items=5, ttl_seconds=10)
    loaded = []

    def loader(u):
        loaded.append(u)
        return b"loaded_data"

    res1 = cache.get_or_load("url1", loader)
    res2 = cache.get_or_load("url1", loader)

    assert res1 == b"loaded_data"
    assert res2 == b"loaded_data"
    assert len(loaded) == 1  # Loader called only once


# ------------------------------------------------------- DiagnosticsService tests
def test_diagnostics_snapshot_and_redaction():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    diag = DiagnosticsService(mgr, bus)

    diag.register("custom_info", lambda: {"secret_token": "my_pass_123", "normal": "hello"})
    snap = diag.snapshot()

    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert "custom_info" in snap
    assert snap["custom_info"]["secret_token"] == "[REDACTED]"
    assert snap["custom_info"]["normal"] == "hello"

    text = diag.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in text
    assert "[application]" in text


def test_redact_helper_structures():
    data = {
        "auth_token": "secret123",
        "nested": {"password": "pass", "champion_key": "103"},
        "str_secret": "token=abcd1234efgh",
    }
    redacted = _redact(data)
    assert redacted["auth_token"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["champion_key"] == "103"


# ----------------------------------------------------- NotificationService tests
def test_notification_service_publishing():
    bus = EventBus()
    svc = NotificationService(bus)

    events = []
    bus.subscribe("notify", lambda ev: events.append(ev))

    svc.info("Info Title", "Info Body")
    svc.success("Success Title")
    svc.warning("Warning Title")
    svc.critical("Critical Title")

    assert len(events) == 4
    assert events[0].payload["title"] == "Info Title"
    assert events[0].payload["level"] == "info"
    assert events[1].payload["level"] == "success"
    assert events[2].payload["level"] == "warning"
    assert events[3].payload["level"] == "critical"


def test_notification_service_disabled():
    bus = EventBus()
    svc = NotificationService(bus, enabled=False)

    events = []
    bus.subscribe("notify", lambda ev: events.append(ev))

    svc.info("Title")
    assert len(events) == 0
