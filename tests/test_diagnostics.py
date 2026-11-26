"""Tests for DiagnosticsService (§31)."""
from __future__ import annotations

from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact, _is_sensitive_key


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


def test_diagnostics_service_snapshot_and_redaction():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    diag = DiagnosticsService(manager, bus)

    diag.register("custom_component", lambda: {"status": "ok", "token": "secret123"})

    snap = diag.snapshot()

    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert "qt" in snap
    assert snap["current_state"] == "DISCONNECTED"
    assert snap["custom_component"]["token"] == "[REDACTED]"

    export_text = diag.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in export_text
    assert "[custom_component]" in export_text
    assert "[REDACTED]" in export_text


def test_redact_helper():
    sample = {
        "password": "my_secret_password",
        "nested": {"session_key": "abcxyz", "safe": "public_val"},
        "list": ["token=12345", "normal_str"],
    }
    redacted = _redact(sample)
    assert redacted["password"] == "[REDACTED]"
    assert redacted["nested"]["session_key"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "public_val"
    assert "token=[REDACTED]" in redacted["list"][0]
    assert redacted["list"][1] == "normal_str"


def test_diagnostics_snapshot_and_redaction():
    bus = EventBus()
    manager = LeagueStateManager(bus=bus)
    diag = DiagnosticsService(manager, bus)

    # Register custom provider returning sensitive data
    diag.register(
        "provider_data",
        lambda: {
            "token": "secret_token_123",
            "password": "super_secret_password",
            "session": "sess_abc123",
            "safe_info": "public_data",
            "nested": ["password: 12345", {"auth_token": "secret"}],
        },
    )

    snap = diag.snapshot()

    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert snap["current_state"] == "DISCONNECTED"

    auth_data = snap["provider_data"]
    assert auth_data["token"] == "[REDACTED]"
    assert auth_data["password"] == "[REDACTED]"
    assert auth_data["session"] == "[REDACTED]"
    assert auth_data["safe_info"] == "public_data"
    assert auth_data["nested"][0] == "password=[REDACTED]"
    assert auth_data["nested"][1]["auth_token"] == "[REDACTED]"


def test_diagnostics_provider_exception_handling():
    bus = EventBus()
    manager = LeagueStateManager(bus=bus)
    diag = DiagnosticsService(manager, bus)

    def failing_provider():
        raise RuntimeError("Provider failed")

    diag.register("failing_component", failing_provider)
    snap = diag.snapshot()

    assert snap["failing_component"] == {"error": "Provider failed"}


def test_diagnostics_export_text():
    bus = EventBus()
    manager = LeagueStateManager(bus=bus)
    diag = DiagnosticsService(manager, bus)

    diag.register("custom", {"setting_a": "value_a", "setting_b": 123})
    exported = diag.export_text()

    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in exported
    assert "[application]" in exported
    assert "[custom]" in exported
    assert "setting_a: value_a" in exported

