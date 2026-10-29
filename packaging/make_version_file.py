"""Write a PyInstaller Windows version resource (.build/version_info.txt) from digestion_lab.__version__.

This is what Windows shows under Properties > Details for the .exe.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from digestion_lab import __version__  # noqa: E402

parts = [int(p) for p in __version__.split('.')] + [0]
nums = tuple(parts[:4])
out = ROOT / '.build' / 'version_info.txt'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Digestion Lab'),
      StringStruct('FileDescription', 'Digestion Lab'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'DigestionLab'),
      StringStruct('LegalCopyright', 'GPL-3.0'),
      StringStruct('OriginalFilename', 'DigestionLab-v{__version__}.exe'),
      StringStruct('ProductName', 'Digestion Lab'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding='utf-8')
print(f'wrote {out} for v{__version__}')
