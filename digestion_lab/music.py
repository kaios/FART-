"""Background music: a title theme and one theme per level, faded in with pygame.mixer.music.

The tracks are WAV loops in digestion_lab/music/, composed by tools/make_music.py.
"""
import sys
from pathlib import Path

import pygame

MUSIC_LEVEL = 0.45   # music sits under the sound effects
FADE_MS = 900

_state = {'enabled': True, 'volume': 0.7, 'muted': False, 'track': None, 'playing': None}


def music_dir():
    here = Path(__file__).resolve().parent / 'music'
    if here.is_dir():
        return here
    return Path(getattr(sys, '_MEIPASS', '.')) / 'digestion_lab' / 'music'


def track_names():
    return sorted(p.stem for p in music_dir().glob('*.wav'))


def _ok():
    return bool(pygame.mixer.get_init())


def _apply_volume():
    if _ok():
        pygame.mixer.music.set_volume(0 if _state['muted'] else _state['volume'] * MUSIC_LEVEL)


def _start(name):
    path = music_dir() / f'{name}.wav'
    if not _ok() or not path.is_file():
        return
    try:
        pygame.mixer.music.load(str(path))
        _apply_volume()
        pygame.mixer.music.play(loops=-1, fade_ms=FADE_MS)
        _state['playing'] = name
    except pygame.error:
        _state['playing'] = None


def play(name):
    """Switch to a track (crossfading); a no-op if it's already playing."""
    _state['track'] = name
    if not _state['enabled'] or _state['playing'] == name:
        return
    _start(name)   # loading replaces the old track; the new one fades in


def configure(enabled=None, volume=None, muted=None):
    if volume is not None:
        _state['volume'] = volume
    if muted is not None:
        _state['muted'] = muted
    if enabled is not None and enabled != _state['enabled']:
        _state['enabled'] = enabled
        if enabled and _state['track']:
            _start(_state['track'])
        elif not enabled and _ok():
            pygame.mixer.music.stop()
            _state['playing'] = None
    _apply_volume()


def pause():
    if _ok():
        pygame.mixer.music.pause()


def resume():
    if _ok():
        pygame.mixer.music.unpause()
