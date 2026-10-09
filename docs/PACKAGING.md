# Packaging and Distribution

LL-NEXUS provides a standalone Windows build procedure using PyInstaller.

## Build Procedure

1. Activate your virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Ensure packaging dependencies are installed:
   ```powershell
   pip install pyinstaller
   ```

3. Run the repeatable build script:
   ```powershell
   python scripts/build_windows.py
   ```

4. The built binary and package will be output to:
   ```
   dist/league-loop-nexus/league-loop-nexus.exe
   ```

## Production Safety Invariant

Per agent safety protocols, binary compiler execution (`pyinstaller`, `build.bat`, Inno Setup) is strictly controlled and only performed when explicitly directed by the repository owner.
