from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact


class FailingProvider:
    def diagnostics(self):
        raise RuntimeError("Provider failed intentionally")


class ComponentProvider:
    def diagnostics(self):
        return {"status": "ok", "champion_key": "145", "auth_token": "secret123"}


def test_diagnostics_snapshot_and_registration():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    svc = DiagnosticsService(manager, bus)

    svc.register("component", ComponentProvider())
    svc.register("func_component", lambda: {"status": "active"})
    svc.register("plain_component", "plain_value")

    snap = svc.snapshot()
    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert snap["current_state"] == "DISCONNECTED"
    assert "component" in snap
    assert snap["component"]["champion_key"] == "145"
    assert snap["component"]["auth_token"] == "[REDACTED]"
    assert snap["func_component"]["status"] == "active"
    assert snap["plain_component"] == "plain_value"


def test_diagnostics_provider_exception_resilience():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    svc = DiagnosticsService(manager, bus)

    svc.register("failing", FailingProvider())
    snap = svc.snapshot()

    assert "failing" in snap
    assert "error" in snap["failing"]
    assert "Provider failed intentionally" in snap["failing"]["error"]


def test_diagnostics_credential_redaction():
    data = {
        "auth_token": "abc123secret",
        "password": "my_password",
        "session_id": "sess_999",
        "api_key": "key_xyz",
        "secret_val": "topsecret",
        "champion_key": "145",
        "nested": {
            "user_token": "token123",
            "info": "token: 998877",
        },
    }
    redacted = _redact(data)

    assert redacted["auth_token"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["session_id"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["secret_val"] == "[REDACTED]"
    assert redacted["champion_key"] == "145"
    assert redacted["nested"]["user_token"] == "[REDACTED]"
    assert "token=[REDACTED]" in redacted["nested"]["info"]


def test_diagnostics_export_text():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    svc = DiagnosticsService(manager, bus)

    svc.register("test_sec", {"status": "ok"})
    text = svc.export_text()

    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in text
    assert "[application]" in text
    assert "[test_sec]" in text
    assert "status: ok" in text
