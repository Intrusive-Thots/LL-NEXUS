import os
from nexus.services.client_detection.detector import detect_client, client_still_running, ClientInfo


def test_client_detector_env_override(monkeypatch):
    monkeypatch.setenv("NEXUS_LCU_PORT", "29999")
    monkeypatch.setenv("NEXUS_LCU_TOKEN", "test_env_token")

    info = detect_client()
    assert info is not None
    assert info.port == 29999
    assert info.auth_token == "test_env_token"
    assert info.source == "env"
    assert info.base_url == "https://127.0.0.1:29999"
    assert client_still_running(info) is True


def test_client_detector_absent_env(monkeypatch):
    monkeypatch.delenv("NEXUS_LCU_PORT", raising=False)
    monkeypatch.delenv("NEXUS_LCU_TOKEN", raising=False)
    monkeypatch.delenv("NEXUS_LEAGUE_INSTALL", raising=False)

    # In test sandbox without real League Client running, detect_client returns None or lockfile if exists
    info = detect_client()
    # Should not crash
    if info:
        assert isinstance(info, ClientInfo)
