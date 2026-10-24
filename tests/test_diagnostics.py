from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact


def test_diagnostics_snapshot_and_export():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    diag = DiagnosticsService(mgr, bus)

    class CustomComponent:
        def diagnostics(self):
            return {"status": "ok", "count": 42}

    diag.register("custom", CustomComponent())
    diag.register("simple_func", lambda: "func_value")

    snap = diag.snapshot()
    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert "current_state" in snap
    assert snap["custom"] == {"status": "ok", "count": 42}
    assert snap["simple_func"] == "func_value"

    text = diag.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in text
    assert "[application]" in text
    assert "[custom]" in text


def test_diagnostics_redaction():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    diag = DiagnosticsService(mgr, bus)

    sensitive_provider = lambda: {
        "api_key": "secret_key_123",
        "auth_token": "bearer_abc",
        "user_password": "my_password",
        "session_id": "sess_999",
        "secret_data": "shh",
        "champion_key": "103",
        "raw_string": "token: 9999 password=secret",
        "champion_str": "champion_key: 103",
    }

    diag.register("sensitive", sensitive_provider)
    snap = diag.snapshot()
    sec = snap["sensitive"]

    assert sec["api_key"] == "[REDACTED]"
    assert sec["auth_token"] == "[REDACTED]"
    assert sec["user_password"] == "[REDACTED]"
    assert sec["session_id"] == "[REDACTED]"
    assert sec["secret_data"] == "[REDACTED]"
    assert sec["champion_key"] == "103"
    assert "token=[REDACTED]" in sec["raw_string"] or "token:[REDACTED]" in sec["raw_string"] or "[REDACTED]" in sec["raw_string"]
    assert sec["champion_str"] == "champion_key: 103"


def test_diagnostics_handles_provider_exception():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    diag = DiagnosticsService(mgr, bus)

    def faulty_provider():
        raise RuntimeError("Provider crashed!")

    diag.register("broken", faulty_provider)
    snap = diag.snapshot()
    assert snap["broken"] == {"error": "Provider crashed!"}
