import tempfile
import time
from pathlib import Path
from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.core.accounts.service import AccountService, AccountSummary
from nexus.developer.diagnostics.service import DiagnosticsService
from nexus.services.cache.ttl_cache import TTLCache
from nexus.services.notifications.service import NotificationService, NotifyLevel


def test_ttl_cache_operations_and_eviction():
    cache = TTLCache(max_items=2, ttl_seconds=1.0)
    assert cache.get("https://example.com/1.png") is None

    cache.put("https://example.com/1.png", b"data1")
    cache.put("https://example.com/2.png", b"data2")
    assert cache.get("https://example.com/1.png") == b"data1"

    # Adding 3rd item triggers eviction of LRU (which is 2.png because 1.png was just accessed)
    cache.put("https://example.com/3.png", b"data3")
    assert cache.get("https://example.com/2.png") is None
    assert cache.get("https://example.com/1.png") == b"data1"
    assert cache.get("https://example.com/3.png") == b"data3"

    stats = cache.stats()
    assert stats["items"] == 2
    assert stats["max"] == 2
    assert stats["hits"] > 0

    cache.clear()
    assert cache.get("https://example.com/1.png") is None


def test_ttl_cache_disk_mirror():
    with tempfile.TemporaryDirectory() as td:
        disk_path = Path(td)
        cache = TTLCache(max_items=5, ttl_seconds=3600, disk_dir=disk_path)
        cache.put("https://example.com/item.png", b"disk_bytes")

        # Clear memory cache to force disk hit
        cache._mem.clear()
        retrieved = cache.get("https://example.com/item.png")
        assert retrieved == b"disk_bytes"

        # Loader fallback
        loader_called = [False]

        def mock_loader(url: str):
            loader_called[0] = True
            return b"loaded_data"

        res = cache.get_or_load("https://example.com/new.png", mock_loader)
        assert res == b"loaded_data"
        assert loader_called[0] is True


def test_diagnostics_service_snapshot_redaction_and_export():
    bus = EventBus()
    state_mgr = LeagueStateManager(bus)
    diag = DiagnosticsService(state_mgr, bus)

    def healthy_provider():
        return {"status": "ok", "api_key": "secret_key_123", "password": "my_password"}

    def faulty_provider():
        raise RuntimeError("Provider failed")

    diag.register("healthy", healthy_provider)
    diag.register("faulty", faulty_provider)

    snap = diag.snapshot()
    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert snap["healthy"]["status"] == "ok"
    assert snap["healthy"]["password"] == "[REDACTED]"
    assert snap["faulty"]["error"] == "Provider failed"

    export_str = diag.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in export_str
    assert "[application]" in export_str


def test_notification_service():
    bus = EventBus()
    notifications = []
    bus.subscribe("notify", lambda evt: notifications.append(evt))

    svc = NotificationService(bus, enabled=True)
    svc.info("Info Title", "Info Body")
    svc.success("Success Title")
    svc.warning("Warning Title")
    svc.critical("Critical Title")

    assert len(notifications) == 4
    assert notifications[0].payload["title"] == "Info Title"
    assert notifications[0].payload["level"] == NotifyLevel.INFO.value
    assert notifications[1].payload["level"] == NotifyLevel.SUCCESS.value
    assert notifications[2].payload["level"] == NotifyLevel.WARNING.value
    assert notifications[3].payload["level"] == NotifyLevel.CRITICAL.value

    # Test disabled service
    svc.enabled = False
    svc.info("Suppressed", "Body")
    assert len(notifications) == 4


def test_account_service():
    class MockLCUClient:
        def __init__(self, response=None, should_raise=False):
            self.response = response
            self.should_raise = should_raise

        def get(self, path: str):
            if self.should_raise:
                raise RuntimeError("LCU connection error")
            return self.response

    # Test display formatting
    s1 = AccountSummary(game_name="SummonerOne", tag_line="NA1")
    assert s1.display == "SummonerOne#NA1"
    s2 = AccountSummary(game_name="SoloPlayer")
    assert s2.display == "SoloPlayer"
    s3 = AccountSummary()
    assert s3.display == "Unknown summoner"

    # Test successful refresh
    mock_client = MockLCUClient({
        "gameName": "Faker",
        "gameTag": "KR1",
        "summonerLevel": 500,
        "summonerId": 12345,
        "puuid": "abc-123-puuid"
    })
    acct_svc = AccountService(mock_client)

    done_event = []

    def on_done(summary):
        done_event.append(summary)

    acct_svc.refresh_async(on_done=on_done)
    time.sleep(0.1)

    summary = acct_svc.summary
    assert summary is not None
    assert summary.display == "Faker#KR1"
    assert summary.level == 500
    assert summary.puuid == "abc-123-puuid"
    assert len(done_event) == 1

    # Test exception handling
    error_client = MockLCUClient(should_raise=True)
    error_svc = AccountService(error_client)

    error_done = []
    error_svc.refresh_async(on_done=lambda s: error_done.append(s))
    time.sleep(0.1)

    assert error_svc.summary is None
    assert len(error_done) == 1
    assert error_done[0] is None
