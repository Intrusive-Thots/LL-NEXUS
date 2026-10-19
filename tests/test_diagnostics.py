import time
from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService


class DummyProvider:
    def diagnostics(self) -> dict:
        return {
            "status": "ok",
            "auth_token": "secret_token_12345",
            "user_password": "super_secret_password",
            "session_id": "session_99999",
            "normal_key": "normal_value",
            "connection_string": "token: my_secret_token_abc"
        }


class FailingProvider:
    def diagnostics(self) -> dict:
        raise RuntimeError("Provider failed unexpectedly")


def test_diagnostics_snapshot_and_redaction():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    diag = DiagnosticsService(manager, bus)

    diag.register("dummy", DummyProvider())
    diag.register("failing", FailingProvider())
    diag.register("plain", {"api_key": "key=secret_key_777", "count": 42})

    bus.publish("test.event", source="test", foo="bar")

    snap = diag.snapshot()

    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert snap["current_state"] == "DISCONNECTED"
    assert snap["last_event"] == "test.event"

    # Redaction checks on dict keys and secret string values
    dummy_data = snap["dummy"]
    assert dummy_data["auth_token"] == "[REDACTED]"
    assert dummy_data["user_password"] == "[REDACTED]"
    assert dummy_data["session_id"] == "[REDACTED]"
    assert dummy_data["normal_key"] == "normal_value"
    assert "token=[REDACTED]" in dummy_data["connection_string"]

    # Exception caught safely
    assert snap["failing"] == {"error": "Provider failed unexpectedly"}

    # Plain dict redaction
    assert "key=[REDACTED]" in snap["plain"]["api_key"]
    assert snap["plain"]["count"] == 42


def test_diagnostics_export_text():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    diag = DiagnosticsService(manager, bus)

    text = diag.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in text
    assert "[application]" in text
    assert "[state]" in text
