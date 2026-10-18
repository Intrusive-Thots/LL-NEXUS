"""Tests for developer diagnostics service and secret redaction."""

from __future__ import annotations

from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact


def test_diagnostics_snapshot_and_redaction():
    bus = EventBus()
    manager = LeagueStateManager(bus=bus)
    diag = DiagnosticsService(manager, bus)

    # Register custom provider returning sensitive data
    diag.register(
        "auth_provider",
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

    auth_data = snap["auth_provider"]
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
