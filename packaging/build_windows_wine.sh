#!/usr/bin/env bash
# Builds the Windows .exe from Linux by running Windows Python under Wine.
# First run downloads Python for Windows (from python.org) into a private Wine prefix in .build/.
# Output: dist/windows/DigestionLab-v<version>.exe
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT_DIR="$PWD"
PYVER="${WIN_PYTHON_VERSION:-3.11.9}"
export WINEPREFIX="$ROOT_DIR/.build/wine"
export WINEDEBUG=-all WINEARCH=win64
WINPY='C:\Python311\python.exe'

# Wine needs an X display even for silent installers; use a virtual one when available.
run() { if command -v xvfb-run >/dev/null; then xvfb-run -a "$@"; else "$@"; fi; }

if [ ! -f "$WINEPREFIX/drive_c/Python311/python.exe" ]; then
  mkdir -p "$ROOT_DIR/.build"
  INSTALLER="$ROOT_DIR/.build/python-$PYVER-amd64.exe"
  [ -f "$INSTALLER" ] || curl -fsSL -o "$INSTALLER" "https://www.python.org/ftp/python/$PYVER/python-$PYVER-amd64.exe"
  run wineboot -i >/dev/null 2>&1 || true
  run winecfg -v win10   # the Python installer refuses to run on the default Windows 7 setting
  run wine "$INSTALLER" /quiet InstallAllUsers=0 PrependPath=0 Include_test=0 Include_doc=0 Include_launcher=0 \
    TargetDir='C:\Python311'
  run wine "$WINPY" -m pip install --upgrade pip pygame-ce pyinstaller
fi

VERSION="$("$ROOT_DIR/.venv/bin/python" -c 'import digestion_lab; print(digestion_lab.__version__)')"
"$ROOT_DIR/.venv/bin/python" packaging/make_icons.py
"$ROOT_DIR/.venv/bin/python" packaging/make_version_file.py
rm -f "$ROOT_DIR"/dist/windows/DigestionLab*.exe
run wine "$WINPY" -m PyInstaller --noconfirm --clean --onefile --windowed --name "DigestionLab-v$VERSION" \
  --version-file "$(winepath -w "$ROOT_DIR/.build/version_info.txt")" \
  --icon "$(winepath -w "$ROOT_DIR/.build/icons/icon.ico")" --paths "$(winepath -w "$ROOT_DIR")" \
  --distpath "$(winepath -w "$ROOT_DIR/dist/windows")" --workpath "$(winepath -w "$ROOT_DIR/.build/pyi-win")" \
  --specpath "$(winepath -w "$ROOT_DIR/.build")" "$(winepath -w "$ROOT_DIR/packaging/run.py")"
echo "Built dist/windows/DigestionLab-v$VERSION.exe"
