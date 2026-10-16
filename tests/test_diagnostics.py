"""Tests for DiagnosticsService (§31)."""
import pytest
from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact


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
