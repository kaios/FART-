"""Render the code-drawn app icon to PNG sizes and a Windows .ico in .build/icons/."""
import os
import sys
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402
from digestion_lab.icon import make_icon, write_ico  # noqa: E402

out = Path(__file__).resolve().parent.parent / '.build' / 'icons'
out.mkdir(parents=True, exist_ok=True)
pygame.init()
pngs = []
for size in (16, 32, 48, 64, 128, 256):
    p = out / f'icon-{size}.png'
    pygame.image.save(make_icon(size), str(p))
    pngs.append(p)
write_ico(out / 'icon.ico', pngs)
print(f'icons written to {out}')
