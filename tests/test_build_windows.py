import os
import sys
from scripts.build_windows import get_build_command


def test_build_windows_command_args():
    cmd = get_build_command()
    assert sys.executable in cmd[0]
    assert "PyInstaller" in cmd
    assert "--name=league-loop-nexus" in cmd

    # Find the --add-data argument
    add_data_arg = next(arg for arg in cmd if arg.startswith("--add-data="))
    assert os.pathsep in add_data_arg
    assert add_data_arg.endswith(f"{os.pathsep}assets")
