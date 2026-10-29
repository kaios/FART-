#!/usr/bin/env bash
# Builds a single self-contained Linux binary with PyInstaller and wraps it in a .deb.
# Output: dist/digestion-lab_<version>_amd64.deb (and dist/linux/digestion-lab)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT_DIR="$PWD"
PY="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
VERSION="$("$PY" -c 'import digestion_lab; print(digestion_lab.__version__)')"

"$PY" packaging/make_icons.py
"$PY" -m PyInstaller --noconfirm --clean --onefile --windowed --name digestion-lab \
  --paths "$ROOT_DIR" --add-data "$ROOT_DIR/digestion_lab/sounds:digestion_lab/sounds" \
  --add-data "$ROOT_DIR/digestion_lab/music:digestion_lab/music" \
  --distpath "$ROOT_DIR/dist/linux" --workpath "$ROOT_DIR/.build/pyi-linux" \
  --specpath "$ROOT_DIR/.build" "$ROOT_DIR/packaging/run.py"

PKG="$ROOT_DIR/.build/deb/digestion-lab_${VERSION}_amd64"
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/usr/bin" "$PKG/usr/share/applications" \
  "$PKG/usr/share/icons/hicolor/256x256/apps" "$PKG/usr/share/doc/digestion-lab"
install -m 755 dist/linux/digestion-lab "$PKG/usr/bin/digestion-lab"
install -m 644 packaging/digestion-lab.desktop "$PKG/usr/share/applications/digestion-lab.desktop"
install -m 644 .build/icons/icon-256.png "$PKG/usr/share/icons/hicolor/256x256/apps/digestion-lab.png"
install -m 644 LICENSE "$PKG/usr/share/doc/digestion-lab/copyright"

MAINTAINER="${MAINTAINER:-$(git config user.name) <$(git config user.email)>}"
cat > "$PKG/DEBIAN/control" <<CONTROL
Package: digestion-lab
Version: ${VERSION}
Section: games
Priority: optional
Architecture: amd64
Depends: libc6 (>= 2.36), libx11-6, libxext6
Recommends: fonts-noto-cjk
Installed-Size: $(du -sk "$PKG/usr" | cut -f1)
Maintainer: ${MAINTAINER}
Description: Digestion Lab - predict burp, fart, or smooth ride
 Feed a wireframe body and predict what happens next. Carbonated drinks
 burp, beans and broccoli fart, rice and bananas ride smooth. Three modes,
 three difficulties, a food log and achievements, in English and Japanese.
CONTROL

mkdir -p dist
dpkg-deb --build --root-owner-group "$PKG" "dist/digestion-lab_${VERSION}_amd64.deb"
echo "Built dist/digestion-lab_${VERSION}_amd64.deb"
