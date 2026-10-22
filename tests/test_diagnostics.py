from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact, _is_sensitive_key


def test_diagnostics_service_snapshot():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    diag_svc = DiagnosticsService(mgr, bus)

    snap = diag_svc.snapshot()
    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert "version" in snap["application"]
    assert "current_state" in snap
    assert "state_confidence" in snap


def test_diagnostics_service_register_component():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    diag_svc = DiagnosticsService(mgr, bus)

    class DummyComponent:
        def diagnostics(self):
            return {"status": "OK", "count": 42, "champion_key": "103"}

    diag_svc.register("dummy", DummyComponent())
    snap = diag_svc.snapshot()
    assert "dummy" in snap
    assert snap["dummy"]["status"] == "OK"
    assert snap["dummy"]["count"] == 42
    assert snap["dummy"]["champion_key"] == "103"


def test_diagnostics_service_export_text():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    diag_svc = DiagnosticsService(mgr, bus)

    text = diag_svc.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in text
    assert "[application]" in text


def test_is_sensitive_key_matching():
    assert _is_sensitive_key("auth_token") is True
    assert _is_sensitive_key("api_key") is True
    assert _is_sensitive_key("user_password") is True
    assert _is_sensitive_key("session_id") is True
    assert _is_sensitive_key("secret") is True
    assert _is_sensitive_key("champion_key") is False
    assert _is_sensitive_key("champion_id") is False


def test_redact_sensitive_dictionary_keys():
    raw = {
        "auth_token": "secret123",
        "api_key": "secret456",
        "password": "my_password",
        "session": "session_val",
        "secret": "confidential",
        "champion_key": "103",
        "champion_id": 103,
        "normal_field": "hello",
    }
    redacted = _redact(raw)
    assert redacted["auth_token"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["session"] == "[REDACTED]"
    assert redacted["secret"] == "[REDACTED]"
    assert redacted["champion_key"] == "103"
    assert redacted["champion_id"] == 103
    assert redacted["normal_field"] == "hello"


def test_redact_string_credential_patterns():
    text = "Connecting with auth_token: super_secret_123 and password = pass_xyz. Target champion_key: 103."
    redacted = _redact(text)
    assert "auth_token=[REDACTED]" in redacted
    assert "password=[REDACTED]" in redacted
    assert "champion_key: 103" in redacted
