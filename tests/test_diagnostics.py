from __future__ import annotations

import pytest

from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.diagnostics.service import DiagnosticsService, _redact


def test_diagnostics_service_snapshot_and_components():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    diag = DiagnosticsService(manager, bus)

    def sample_provider():
        return {"status": "ok", "value": 42}

    class ErrorProvider:
        def diagnostics(self):
            raise RuntimeError("Provider failed")

    diag.register("sample", sample_provider)
    diag.register("failing", ErrorProvider())

    snap = diag.snapshot()

    assert snap["application"]["name"] == "LeagueLoop Nexus"
    assert snap["application"]["version"] == "0.1.0"
    assert "PySide6" in snap["qt"]
    assert snap["current_state"] == "DISCONNECTED"
    assert snap["sample"] == {"status": "ok", "value": 42}
    assert snap["failing"] == {"error": "Provider failed"}


def test_diagnostics_redaction():
    data = {
        "auth_token": "secret_token_123",
        "user_password": "super_secret_password",
        "session_id": "session_999",
        "safe_field": "public_data",
        "champion_key": "Ahri",
        "connection_string": "token: my_token_abc password=pass123",
        "nested_list": [
            {"token": "nested_token"},
            "password: hidden_password"
        ]
    }

    redacted = _redact(data)

    assert redacted["auth_token"] == "[REDACTED]"
    assert redacted["user_password"] == "[REDACTED]"
    assert redacted["session_id"] == "[REDACTED]"
    assert redacted["safe_field"] == "public_data"
    assert redacted["champion_key"] == "Ahri"
    assert "token=[REDACTED]" in redacted["connection_string"]
    assert "password=[REDACTED]" in redacted["connection_string"]
    assert redacted["nested_list"][0]["token"] == "[REDACTED]"
    assert "password=[REDACTED]" in redacted["nested_list"][1]


def test_diagnostics_export_text():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    diag = DiagnosticsService(manager, bus)
    diag.register("custom", {"key": "value"})

    text = diag.export_text()

    assert "LEAGUELOOP NEXUS — DIAGNOSTICS" in text
    assert "[application]" in text
    assert "[custom]" in text
    assert "key: value" in text
