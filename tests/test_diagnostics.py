from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact, _is_sensitive_key


def test_is_sensitive_key():
    assert _is_sensitive_key("token")
    assert _is_sensitive_key("auth_token")
    assert _is_sensitive_key("password")
    assert _is_sensitive_key("session")
    assert _is_sensitive_key("secret")
    assert _is_sensitive_key("auth")
    assert _is_sensitive_key("api_key")
    assert _is_sensitive_key("auth_key")

    assert not _is_sensitive_key("champion_key")
    assert not _is_sensitive_key("champion_keys")
    assert not _is_sensitive_key("user_id")
    assert not _is_sensitive_key("role")


def test_redact_dictionary_and_strings():
    data = {
        "champion_key": "kaisa",
        "champion_keys": ["ahri", "jinx"],
        "auth_token": "secret123",
        "api_key": "key456",
        "user_password": "pass",
        "session_id": "sess789",
        "secret": "mysecret",
        "auth": "bearer xyz",
        "nested": {
            "token": "abc",
            "champion_key": "lux",
        },
        "log_string": "champion_key=103 token: xyz123 password=hidden",
    }

    redacted = _redact(data)

    assert redacted["champion_key"] == "kaisa"
    assert redacted["champion_keys"] == ["ahri", "jinx"]
    assert redacted["auth_token"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["user_password"] == "[REDACTED]"
    assert redacted["session_id"] == "[REDACTED]"
    assert redacted["secret"] == "[REDACTED]"
    assert redacted["auth"] == "[REDACTED]"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert redacted["nested"]["champion_key"] == "lux"
    assert "token=[REDACTED]" in redacted["log_string"]
    assert "password=[REDACTED]" in redacted["log_string"]
    assert "champion_key=103" in redacted["log_string"]


def test_diagnostics_service_snapshot_and_export():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    diag = DiagnosticsService(manager, bus)

    diag.register("custom_component", lambda: {"status": "ok", "auth_key": "secret_key_123", "champion_key": "103"})

    snap = diag.snapshot()

    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert snap["current_state"] == "DISCONNECTED"
    assert snap["custom_component"]["status"] == "ok"
    assert snap["custom_component"]["auth_key"] == "[REDACTED]"
    assert snap["custom_component"]["champion_key"] == "103"

    text = diag.export_text()
    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in text
    assert "[custom_component]" in text
    assert "[REDACTED]" in text
    assert "secret_key_123" not in text
