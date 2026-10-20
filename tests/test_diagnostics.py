from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact


def test_diagnostics_service_snapshot_and_export():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    service = DiagnosticsService(manager, bus)

    class DummyProvider:
        def diagnostics(self):
            return {"status": "ok", "champion_key": "222", "auth_token": "secret_token_value"}

    class FaultyProvider:
        def diagnostics(self):
            raise RuntimeError("Provider failed")

    service.register("dummy", DummyProvider())
    service.register("faulty", FaultyProvider())
    service.register("raw", {"custom": "value"})

    snap = service.snapshot()
    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert snap["current_state"] == "DISCONNECTED"
    assert snap["dummy"]["status"] == "ok"
    assert snap["dummy"]["champion_key"] == "222"
    assert snap["dummy"]["auth_token"] == "[REDACTED]"
    assert snap["faulty"] == {"error": "Provider failed"}
    assert snap["raw"] == {"custom": "value"}

    text = service.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in text
    assert "[application]" in text
    assert "[dummy]" in text


def test_redact_utility():
    raw_str = "Connecting with token=super_secret_123 and password=pass456"
    redacted_str = _redact(raw_str)
    assert "super_secret_123" not in redacted_str
    assert "pass456" not in redacted_str
    assert "token=[REDACTED]" in redacted_str
    assert "password=[REDACTED]" in redacted_str

    nested_dict = {
        "user_token": "xyz789",
        "champion_key": "103",
        "details": {
            "password": "my_password",
            "safe_field": "hello"
        }
    }
    redacted_dict = _redact(nested_dict)
    assert redacted_dict["user_token"] == "[REDACTED]"
    assert redacted_dict["champion_key"] == "103"
    assert redacted_dict["details"]["password"] == "[REDACTED]"
    assert redacted_dict["details"]["safe_field"] == "hello"
