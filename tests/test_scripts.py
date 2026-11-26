from __future__ import annotations
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

import scripts.build_champion_catalog as bcc
import scripts.build_windows as bw


def test_build_windows_script(tmp_path):
    with patch("subprocess.check_call") as mock_call:
        bw.build()
        assert mock_call.called
        cmd = mock_call.call_args[0][0]
        assert "PyInstaller" in cmd
        assert "--name=league-loop-nexus" in cmd


def test_build_champion_catalog_offline_fallback(tmp_path):
    mock_out = tmp_path / "assets" / "champions.json"
    with patch.object(bcc, "OUT", mock_out):
        with patch("sys.argv", ["build_champion_catalog.py", "--offline"]):
            ret = bcc.main()
            assert ret == 0
            assert mock_out.exists()
            data = json.loads(mock_out.read_text(encoding="utf-8"))
            assert data["version"] == 1
            assert "seed" in data["source"]
            assert len(data["champions"]) > 0


def test_build_champion_catalog_online_success(tmp_path):
    mock_out = tmp_path / "assets" / "champions.json"
    dummy_champs = [
        {"id": 1, "key": "1", "name": "TestChamp", "alias": "TestChamp", "roles": ["TOP"], "resource": "mana"}
    ]
    with patch.object(bcc, "OUT", mock_out):
        with patch.object(bcc, "fetch_online", return_value=dummy_champs):
            with patch("sys.argv", ["build_champion_catalog.py"]):
                ret = bcc.main()
                assert ret == 0
                assert mock_out.exists()
                data = json.loads(mock_out.read_text(encoding="utf-8"))
                assert data["source"] == "ddragon"
                assert len(data["champions"]) == 1
                assert data["champions"][0]["name"] == "TestChamp"
