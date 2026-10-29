@echo off
rem Builds dist\windows\DigestionLab-v<version>.exe on a Windows machine with Python 3.10+ installed.
cd /d "%~dp0\.."
python -m venv .venv-win || exit /b 1
.venv-win\Scripts\python -m pip install --upgrade pip pygame-ce pyinstaller || exit /b 1
for /f %%v in ('.venv-win\Scripts\python -c "import digestion_lab; print(digestion_lab.__version__)"') do set VERSION=%%v
.venv-win\Scripts\python packaging\make_icons.py || exit /b 1
.venv-win\Scripts\python packaging\make_version_file.py || exit /b 1
.venv-win\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --name DigestionLab-v%VERSION% ^
  --version-file .build\version_info.txt --add-data "digestion_lab\sounds;digestion_lab\sounds" --icon .build\icons\icon.ico --paths . --distpath dist\windows --workpath .build\pyi-win --specpath .build ^
  packaging\run.py || exit /b 1
echo Built dist\windows\DigestionLab-v%VERSION%.exe
