import time
from pathlib import Path
from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService
from nexus.services.cache.ttl_cache import TTLCache
from nexus.services.notifications.service import NotificationService, NotifyLevel, Notification


# ------------------------------------------------------------------- TTLCache
def test_ttl_cache_operations(tmp_path):
    cache = TTLCache(max_items=2, ttl_seconds=0.1, disk_dir=tmp_path)

    # Put and Get
    cache.put("https://example.com/1.png", b"data1")
    assert cache.get("https://example.com/1.png") == b"data1"
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0

    # Miss
    assert cache.get("https://example.com/missing.png") is None
    assert cache.stats()["misses"] == 1

    # LRU Eviction: max capacity is 2
    cache.put("https://example.com/2.png", b"data2")
    cache.put("https://example.com/3.png", b"data3")  # 1.png evicted
    assert cache.stats()["evictions"] == 1
    cache.clear()  # Clear memory cache so 1.png won't hit memory
    assert cache.get("https://example.com/2.png") == b"data2"  # disk hit for 2.png
    assert cache.get("https://example.com/3.png") == b"data3"  # disk hit for 3.png

    # Test loader fallback
    loaded = cache.get_or_load("https://example.com/loaded.png", lambda u: b"loaded_data")
    assert loaded == b"loaded_data"
    assert cache.get("https://example.com/loaded.png") == b"loaded_data"


# -------------------------------------------------------- NotificationService
def test_notification_service():
    bus = EventBus()
    notifications = []

    def handler(evt):
        notifications.append(evt)

    bus.subscribe("notify", handler)

    svc = NotificationService(bus, enabled=True)
    svc.info("Info Title", "Info body")
    svc.success("Success Title", "Success body")
    svc.warning("Warning Title", "Warning body")
    svc.critical("Critical Title", "Critical body")

    assert len(notifications) == 4
    assert notifications[0].payload["level"] == NotifyLevel.INFO.value
    assert notifications[1].payload["level"] == NotifyLevel.SUCCESS.value
    assert notifications[2].payload["level"] == NotifyLevel.WARNING.value
    assert notifications[3].payload["level"] == NotifyLevel.CRITICAL.value

    # Disabled notification service
    disabled_svc = NotificationService(bus, enabled=False)
    disabled_svc.info("Suppressed Title")
    assert len(notifications) == 4


# -------------------------------------------------------- DiagnosticsService
def test_diagnostics_service():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    svc = DiagnosticsService(manager, bus)

    def failing_provider():
        raise RuntimeError("Provider failed")

    svc.register("failing", failing_provider)
    svc.register("secret_info", {
        "auth_token": "bearer xyz",
        "session_id": "sess_123",
        "normal_field": "ok_val",
        "nested": ["password = 12345", "token: abc"]
    })

    snap = svc.snapshot()
    assert snap["failing"] == {"error": "Provider failed"}
    assert snap["secret_info"]["auth_token"] == "[REDACTED]"
    assert snap["secret_info"]["session_id"] == "[REDACTED]"
    assert snap["secret_info"]["normal_field"] == "ok_val"
    assert "password=[REDACTED]" in snap["secret_info"]["nested"][0]
    assert "token=[REDACTED]" in snap["secret_info"]["nested"][1]

    exported = svc.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in exported
    assert "[secret_info]" in exported
