"""Save data as JSON in the user's data folder. Failures never stop the game."""
import json
import os
import sys
from pathlib import Path


def _data_dir():
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming')
        return base / 'DigestionLab'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'DigestionLab'
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'digestion-lab'


SAVE_PATH = _data_dir() / 'save.json'


def defaults():
    return {
        'settings': {'lang': None, 'volume': 0.7, 'muted': False, 'shake': True, 'difficulty': 'normal',
                     'fullscreen': False, 'music': True},
        'best': {'classic': 0, 'rush': 0, 'endless': 0},
        'tried': {},
        'achievements': {},
        'stats': {'games': 0, 'rounds': 0, 'correct': 0},
    }


def load(path=None):
    d = defaults()
    try:
        raw = json.loads(Path(path or SAVE_PATH).read_text(encoding='utf-8'))
        for k, v in d.items():
            if isinstance(raw.get(k), dict):
                v.update(raw[k])
    except (OSError, ValueError, AttributeError):
        pass
    return d


def persist(save, path=None):
    p = Path(path or SAVE_PATH)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(save, ensure_ascii=False, indent=1), encoding='utf-8')
        tmp.replace(p)
    except OSError:
        pass


def reset_progress(save, path=None):
    """Wipe scores, food log and achievements but keep the player's settings."""
    d = defaults()
    for k in d:
        if k != 'settings':
            save[k] = d[k]
    persist(save, path)
