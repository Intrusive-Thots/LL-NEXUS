"""Unit tests for packaging build scripts."""

from unittest.mock import patch
import pytest

from scripts.build_windows import check_pyinstaller, build


def test_check_pyinstaller_returns_bool():
    result = check_pyinstaller()
    assert isinstance(result, bool)


def test_build_raises_runtime_error_when_pyinstaller_missing():
    with patch("scripts.build_windows.check_pyinstaller", return_value=False):
        with pytest.raises(RuntimeError, match="PyInstaller module not found"):
            build()


def test_build_invokes_subprocess_when_pyinstaller_present():
    with patch("scripts.build_windows.check_pyinstaller", return_value=True), patch(
        "subprocess.call", return_value=0
    ) as mock_call:
        res = build()
        assert res == 0
        assert mock_call.called
