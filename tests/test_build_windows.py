import os
import sys
from unittest.mock import patch
import pytest

from scripts.build_windows import build, ROOT


def test_build_windows_command_args():
    with patch("subprocess.check_call") as mock_check_call:
        build()
        assert mock_check_call.called
        cmd = mock_check_call.call_args[0][0]
        cwd = mock_check_call.call_args[1].get("cwd")

        assert str(cwd) == str(ROOT)
        assert cmd[0] == sys.executable
        assert cmd[1] == "-m"
        assert cmd[2] == "PyInstaller"
        assert f"--add-data={ROOT / 'assets'}{os.pathsep}assets" in cmd
        assert f"--paths={ROOT / 'src'}" in cmd
