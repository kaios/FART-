"""System fonts only: nothing is bundled.

Japanese text is rendered in runs: CJK characters use an installed Japanese font and
everything else (digits, Latin, symbols) uses the Latin font. That way mixed strings such
as "正解！ +100" render correctly even when the Japanese font has no Latin glyphs.
"""
import pygame

from .i18n import get_lang

_LATIN = ['segoeui', 'dejavusans', 'liberationsans', 'notosans', 'arial', 'helvetica', 'freesans']
_JAPANESE = ['yugothicui', 'yugothic', 'meiryo', 'msgothic', 'notosanscjkjp', 'notosansjp', 'notosanscjk',
             'sourcehansansjp', 'ipagothic', 'ipaexgothic', 'takaogothic', 'vlgothic', 'droidsansfallback',
             'droidsansfallbackfull', 'hiraginosans', 'hiraginokakugothicpron']

_paths = {}
_cache = {}


def _is_cjk(ch):
    return ord(ch) >= 0x2E80


def _path(lang, bold):
    key = (lang, bold)
    if key not in _paths:
        names = _JAPANESE if lang == 'ja' else _LATIN
        regular = pygame.font.match_font(names)
        path = pygame.font.match_font(names, bold=True) if bold else regular
        # match_font falls back to the regular face when no bold one exists; synthesize bold then.
        _paths[key] = (path, bold and (path is None or path == regular))
    return _paths[key]


def _load(lang, size, bold):
    path, fake_bold = _path(lang, bold)
    try:
        f = pygame.font.Font(path, size)
    except (OSError, pygame.error):
        f = pygame.font.Font(None, int(size * 1.3))
        fake_bold = bold
    if fake_bold:
        f.bold = True
    return f


class MixedFont:
    """Font-like object that picks the Japanese or Latin face per character run."""

    def __init__(self, ja, latin):
        self.ja, self.latin = ja, latin
        self._asc = max(ja.get_ascent(), latin.get_ascent())
        self._h = max(self._asc - f.get_ascent() + f.get_height() for f in (ja, latin))

    def _runs(self, s):
        runs, cur, cur_cjk = [], '', None
        for ch in s:
            c = _is_cjk(ch) if not ch.isspace() else cur_cjk
            if cur and c != cur_cjk:
                runs.append((cur, self.ja if cur_cjk else self.latin))
                cur = ''
            cur += ch
            cur_cjk = c
        if cur:
            runs.append((cur, self.ja if cur_cjk else self.latin))
        return runs

    def size(self, s):
        return sum(f.size(r)[0] for r, f in self._runs(s)), self._h

    def render(self, s, aa, color):
        parts = [(f.render(r, aa, color), f) for r, f in self._runs(s)]
        out = pygame.Surface((max(1, sum(p.get_width() for p, _ in parts)), self._h), pygame.SRCALPHA)
        x = 0
        for img, f in parts:
            out.blit(img, (x, self._asc - f.get_ascent()))
            x += img.get_width()
        return out

    def get_linesize(self):
        return max(self.ja.get_linesize(), self.latin.get_linesize())

    def get_height(self):
        return self._h

    def get_ascent(self):
        return self._asc


def get(size, bold=False, lang=None):
    lang = lang or get_lang()
    size = max(8, int(size))
    key = (lang, size, bold)
    f = _cache.get(key)
    if f is None:
        latin = _cache.get(('en', size, bold)) or _load('en', size, bold)
        _cache[('en', size, bold)] = latin
        f = MixedFont(_load('ja', size, bold), latin) if lang == 'ja' else latin
        _cache[key] = f
    return f


def has_japanese():
    return _path('ja', False)[0] is not None
