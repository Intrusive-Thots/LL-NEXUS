from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

from nexus.core.accounts.service import AccountService, AccountSummary
from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact
from nexus.services.cache.ttl_cache import TTLCache
from nexus.services.notifications.service import (
    Notification,
    NotificationService,
    NotifyLevel,
)


def test_diagnostics_service_and_redaction():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    diagnostics = DiagnosticsService(manager, bus)

    class CustomProvider:
        def diagnostics(self) -> dict:
            return {"status": "ok", "auth_token": "secret_12345"}

    def failing_provider():
        raise RuntimeError("Provider failed")

    diagnostics.register("custom", CustomProvider())
    diagnostics.register("failing", failing_provider)
    diagnostics.register("simple", lambda: {"password": "mypassword123"})

    snap = diagnostics.snapshot()
    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert "qt" in snap
    assert snap["custom"] == {"status": "ok", "auth_token": "[REDACTED]"}
    assert snap["failing"] == {"error": "Provider failed"}
    assert snap["simple"] == {"password": "[REDACTED]"}

    text = diagnostics.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in text
    assert "[application]" in text
    assert "[custom]" in text


def test_redact_helper_structures():
    raw_str = "auth_token: 12345 token=secret"
    redacted_str = _redact(raw_str)
    assert "token=[REDACTED]" in redacted_str

    nested_dict = {
        "user_token": "abcde",
        "nested": [{"password": "123", "normal": "value"}],
    }
    redacted_dict = _redact(nested_dict)
    assert redacted_dict["user_token"] == "[REDACTED]"
    assert redacted_dict["nested"][0]["password"] == "[REDACTED]"
    assert redacted_dict["nested"][0]["normal"] == "value"


def test_notification_service():
    bus = EventBus()
    received = []
    bus.subscribe("notify", lambda ev: received.append(ev))

    service = NotificationService(bus)
    service.info("Info Title", "Info body")
    service.success("Success Title")
    service.warning("Warning Title")
    service.critical("Critical Title")

    assert len(received) == 4
    assert received[0].payload["level"] == NotifyLevel.INFO.value
    assert received[0].payload["title"] == "Info Title"
    assert received[1].payload["level"] == NotifyLevel.SUCCESS.value
    assert received[2].payload["level"] == NotifyLevel.WARNING.value
    assert received[3].payload["level"] == NotifyLevel.CRITICAL.value

    # Disabled notification service
    service.enabled = False
    service.info("Should not publish", "body")
    assert len(received) == 4


def test_ttl_cache_mem_lru_and_disk(tmp_path: Path):
    disk_dir = tmp_path / "cache"
    cache = TTLCache(max_items=2, ttl_seconds=0.5, disk_dir=disk_dir)

    # Basic put and get
    url1 = "https://example.com/icon1.png"
    url2 = "https://example.com/icon2.png"
    url3 = "https://example.com/icon3.png"

    cache.put(url1, b"data1")
    cache.put(url2, b"data2")
    assert cache.get(url1) == b"data1"
    assert cache.get(url2) == b"data2"

    # LRU eviction when adding url3
    cache.put(url3, b"data3")
    stats = cache.stats()
    assert stats["items"] == 2
    assert stats["evictions"] >= 1

    # get_or_load loader call
    loader = MagicMock(return_value=b"loaded_data")
    data = cache.get_or_load("https://example.com/icon4.png", loader)
    assert data == b"loaded_data"
    loader.assert_called_once()

    # Disk mirror verification
    cache.clear()
    assert cache.get(url1) == b"data1"  # Loaded from disk mirror

    # TTL expiration
    time.sleep(0.6)
    assert cache.get("https://example.com/expired.png") is None


def test_account_service():
    mock_lcu = MagicMock()
    mock_lcu.get.return_value = {
        "gameName": "Faker",
        "gameTag": "KR1",
        "summonerLevel": 500,
        "summonerId": 123456,
        "puuid": "test-puuid-123",
    }

    service = AccountService(mock_lcu)
    assert service.summary is None

    done_signal = MagicMock()

    def on_done(summary):
        done_signal(summary)

    service.refresh_async(on_done=on_done)

    # Wait briefly for thread to complete
    for _ in range(50):
        if service.summary is not None:
            break
        time.sleep(0.02)

    summary = service.summary
    assert summary is not None
    assert summary.display == "Faker#KR1"
    assert summary.level == 500
    assert summary.summoner_id == 123456
    assert summary.puuid == "test-puuid-123"
    done_signal.assert_called_once()


def test_account_summary_display_fallbacks():
    s1 = AccountSummary(game_name="RiotGames", tag_line="NA1")
    assert s1.display == "RiotGames#NA1"

    s2 = AccountSummary(game_name="RiotGames")
    assert s2.display == "RiotGames"

    s3 = AccountSummary()
    assert s3.display == "Unknown summoner"
