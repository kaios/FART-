"""Immediate-mode UI: every frame draws the widgets and records clickable areas.

Drawing never changes game state. Clicks are resolved later through Widgets.find(),
which returns the (action, arg) the controller acts on.
"""
import math

import pygame
import pygame.gfxdraw as gfx

from . import __version__, fonts
from .achievements import ACHIEVEMENTS
from .foods import FOODS
from .i18n import t, L, get_lang
from .render import COL, mix
from .rules import MODE_RULES

HEADER_H = 58


# ---------- text helpers ----------
def text(surf, s, size, color, pos, anchor='topleft', bold=False, lang=None):
    img = fonts.get(size, bold, lang).render(str(s), True, color)
    r = img.get_rect(**{anchor: pos})
    surf.blit(img, r)
    return r


def wrap(s, font, width):
    """Word wrap for English, character wrap for Japanese."""
    lines, cur = [], ''
    tokens = list(s) if get_lang() == 'ja' else [w + ' ' for w in s.split(' ')]
    for tok in tokens:
        if font.size((cur + tok).rstrip())[0] <= width or not cur:
            cur += tok
        else:
            lines.append(cur.rstrip())
            cur = tok.lstrip() if get_lang() != 'ja' else tok
    if cur.strip():
        lines.append(cur.rstrip())
    return lines


def text_block(surf, s, size, color, x, y, width, bold=False, line_gap=1.45, align='left', max_lines=None):
    f = fonts.get(size, bold)
    lh = int(f.get_linesize() * line_gap / 1.2)
    lines = wrap(s, f, width)
    if max_lines:
        lines = lines[:max_lines]
    for i, ln in enumerate(lines):
        img = f.render(ln, True, color)
        if align == 'center':
            surf.blit(img, img.get_rect(midtop=(x + width // 2, y + i * lh)))
        else:
            surf.blit(img, (x, y + i * lh))
    return len(lines) * lh


def block_height(s, size, width, bold=False, line_gap=1.45):
    f = fonts.get(size, bold)
    return len(wrap(s, f, width)) * int(f.get_linesize() * line_gap / 1.2)


def spaced(s):
    return ' '.join(s)


# ---------- shapes ----------
def rrect(surf, color, rect, radius, width=0):
    pygame.draw.rect(surf, color, rect, width, border_radius=min(radius, rect.h // 2, rect.w // 2))


def heart(surf, cx, cy, size, color, filled=True):
    pts = []
    for i in range(40):
        a = i / 40 * math.tau
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x * size / 34, cy + y * size / 34))
    if filled:
        gfx.filled_polygon(surf, pts, color)
    gfx.aapolygon(surf, pts, color)


def draw_icon(surf, food, rect, color, width=2):
    k = rect.w / 24

    def P(p):
        return rect.x + p[0] * k, rect.y + p[1] * k
    for shape in food.icon:
        if shape[0] == 'lines':
            pts = [P(p) for p in shape[1]]
            pygame.draw.lines(surf, color, shape[2], pts, width)
            pygame.draw.aalines(surf, color, shape[2], pts)
        else:
            _, cx, cy, r = shape
            X, Y = P((cx, cy))
            rr = max(1, int(r * k))
            if rr <= 2:
                gfx.filled_circle(surf, int(X), int(Y), rr, color)
            else:
                pygame.draw.circle(surf, color, (X, Y), rr, width)
            gfx.aacircle(surf, int(X), int(Y), rr, color)


# ---------- widgets ----------
class Widgets:
    def __init__(self):
        self.hits = []
        self.mouse = (-1, -1)
        self.modal = False   # True while drawing what sits under an overlay: no hover there

    def reset(self):
        self.hits = []

    def block(self, rect):
        self.hits.append((pygame.Rect(rect), None, None))

    def hit(self, rect, action, arg=None):
        self.hits.append((pygame.Rect(rect), action, arg))

    def find(self, pos):
        for r, a, g in reversed(self.hits):
            if r.collidepoint(pos):
                return (a, g) if a else None
        return None

    def hovering(self, rect):
        return not self.modal and rect.collidepoint(self.mouse)

    def button(self, surf, rect, label, action, arg=None, *, style='chip', enabled=True, selected=False,
               color=None, size=14, bold=True, radius=None, lang=None):
        rect = pygame.Rect(rect)
        hover = enabled and self.hovering(rect)
        accent = color or COL['wire']
        radius = rect.h // 2 if radius is None else radius
        if style == 'primary':
            fill = mix(COL['fart'], (255, 255, 255), 0.12) if hover else COL['fart']
            rrect(surf, fill, rect, radius)
            fg = (6, 33, 15)
        else:
            fill = {'chip': COL['panel'], 'card': COL['panel2'], 'ghost': COL['panel'],
                    'seg': (34, 48, 77) if selected else COL['panel2']}.get(style, COL['panel'])
            if style == 'pred' and selected:
                fill = (34, 48, 77)
            elif style == 'pred':
                fill = COL['panel2']
            rrect(surf, fill, rect, radius)
            border = accent if (hover or selected) and style != 'seg' else COL['line']
            if style == 'danger':
                border = COL['red']
            rrect(surf, border, rect, radius, 1)
            fg = color or COL['ink']
            if style == 'danger':
                fg = COL['red']
            if style == 'seg':
                fg = COL['ink'] if selected else COL['muted']
                if selected:
                    pygame.draw.line(surf, COL['fart'], (rect.x + 2, rect.bottom - 2), (rect.right - 3, rect.bottom - 2), 2)
        if not enabled and not selected:
            fg = mix(COL['bg'], fg, 0.35)
        if label is not None:
            text(surf, label, size, fg, rect.center, 'center', bold, lang)
        if enabled and action:
            self.hit(rect, action, arg)
        return rect


# ---------- header ----------
def draw_header(app, surf, W):
    ui = app.ui
    surf.fill(COL['bg'], (0, 0, W, HEADER_H))
    pygame.draw.line(surf, COL['line'], (0, HEADER_H - 1), (W, HEADER_H - 1))
    text(surf, t('title'), 16, COL['ink'], (18, HEADER_H // 2), 'midleft', True)

    # right-hand controls, laid out from the right edge
    x = W - 16
    f_en, f_ja = fonts.get(12, True, 'en'), fonts.get(12, True, 'ja')
    ja_on = get_lang() == 'ja'
    w_ja, w_en = f_ja.size('日本語')[0], f_en.size('EN')[0]
    sw = pygame.Rect(0, 0, w_en + w_ja + 40 + 20, 30)
    sw.midright = (x, HEADER_H // 2)
    text(surf, 'EN', 12, COL['muted'] if ja_on else COL['ink'], (sw.x, sw.centery), 'midleft', True, 'en')
    track = pygame.Rect(sw.x + w_en + 8, 0, 40, 22)
    track.centery = sw.centery
    rrect(surf, COL['panel2'], track, 11)
    rrect(surf, COL['wire'] if ui.hovering(sw) else COL['line'], track, 11, 1)
    kx = track.x + 11 + (18 if ja_on else 0)
    gfx.filled_circle(surf, kx, track.centery, 8, COL['red'] if ja_on else COL['wire'])
    gfx.aacircle(surf, kx, track.centery, 8, COL['red'] if ja_on else COL['wire'])
    text(surf, '日本語', 12, COL['ink'] if ja_on else COL['muted'], (track.right + 8, sw.centery), 'midleft', True, 'ja')
    ui.hit(sw, 'lang')
    x = sw.x - 12

    def chip(label, action):
        nonlocal x
        w = fonts.get(12, True).size(label)[0] + 26
        r = pygame.Rect(x - w, HEADER_H // 2 - 15, w, 30)
        ui.button(surf, r, label, action, size=12)
        x = r.x - 10

    chip(t('soundOff' if app.save['settings']['muted'] else 'soundOn'), 'sound')
    if app.mode == 'play':
        chip(t('resume' if app.paused else 'pause'), 'pause')

    # stats, right-aligned columns
    x -= 10
    s = app.session
    stats = [('best', str(app.best_for_header()))]
    stats.append(('streak', str(s.streak if s else 0)))
    if not s or s.mode == 'classic':
        stats.append(('round', f"{min(s.round, 8) if s else 0}/{MODE_RULES['classic']['rounds']}"))
    elif s.mode == 'rush':
        stats.append(('time', str(math.ceil(s.time_left))))
    else:
        stats.append(('lives', None))
    stats.append(('level', str(app.level if s else 1)))
    stats.append(('score', str(s.score if s else 0)))
    for key, val in stats:
        lab = fonts.get(10, True).render(t(key), True, COL['muted'])
        if val is None:
            vw = 3 * 20
        else:
            warn = key == 'time' and s.time_left <= 10
            vimg = fonts.get(19, True).render(val, True, COL['red'] if warn else COL['ink'])
            vw = vimg.get_width()
        colw = max(lab.get_width(), vw)
        surf.blit(lab, lab.get_rect(topright=(x, 8)))
        if val is None:
            for i in range(MODE_RULES['endless']['lives']):
                hx = x - colw + 10 + i * 20
                heart(surf, hx, 36, 16, COL['red'], filled=i < s.lives)
        else:
            surf.blit(vimg, vimg.get_rect(topright=(x, 22)))
        x -= colw + 22


# ---------- menu card ----------
def draw_menu(app, surf, rect):
    ui = app.ui
    surf.fill(COL['panel'], rect)
    pygame.draw.line(surf, COL['line'], rect.topleft, rect.bottomleft)
    x, y, w = rect.x + 18, rect.y + 20, rect.w - 36
    text(surf, spaced(t('menu')) if get_lang() == 'en' else t('menu'), 22, COL['ink'], (x, y), bold=True)
    y += 36
    y += text_block(surf, t('menuSub'), 13, COL['muted'], x, y, w) + 12
    for dx in range(0, w, 6):
        pygame.draw.line(surf, COL['line'], (x + dx, y), (x + min(w, dx + 3), y))
    y += 14
    enabled = app.can_pick_food()
    for i, food in enumerate(app.menu_foods):
        r = pygame.Rect(x, y, w, 52)
        hover = enabled and ui.hovering(r)
        rrect(surf, COL['panel2'], r, 10)
        rrect(surf, COL['wire'] if hover else COL['line'], r, 10, 1)
        fresh = app.menu_flash and app.menu_flash[0] == i and app.clock_time - app.menu_flash[1] < 2.5
        if fresh and app.mode == 'play':   # a new food was just dealt into this slot
            k = 1 - (app.clock_time - app.menu_flash[1]) / 2.5
            rrect(surf, mix(COL['panel2'], COL['fart'], k), r, 10, 2)
            tag = fonts.get(9, True, 'en').render(t('new'), True, COL['bg'])
            tr = pygame.Rect(0, 0, tag.get_width() + 8, 14)
            tr.topright = (r.right - 40, r.y + 5)
            rrect(surf, mix(COL['panel2'], COL['fart'], k), tr, 4)
            surf.blit(tag, tag.get_rect(center=tr.center))
        fg = COL['ink'] if enabled else mix(COL['bg'], COL['ink'], 0.4)
        ic = COL['wire'] if enabled else mix(COL['bg'], COL['wire'], 0.4)
        draw_icon(surf, food, pygame.Rect(r.x + 12, r.centery - 14, 28, 28), ic)
        name_w = w - 100
        name = L(food.name)
        f = fonts.get(15, True)
        while f.size(name)[0] > name_w and len(name) > 3:
            name = name[:-2] + '…'
        text(surf, name, 15, fg, (r.x + 52, r.centery), 'midleft', True)
        k = pygame.Rect(0, 0, 20, 20)
        k.midright = (r.right - 12, r.centery)
        rrect(surf, COL['line'], k, 4, 1)
        text(surf, str(i + 1), 11, COL['muted'], k.center, 'center', lang='en')
        if enabled:
            ui.hit(r, 'food', i)
        y += 60
    fh = block_height(t('keys'), 11, w)
    if y + fh + 10 < rect.bottom:
        text_block(surf, t('keys'), 11, COL['muted'], x, rect.bottom - fh - 16, w)


# ---------- stage overlays: status + prediction panel ----------
def draw_status(app, surf, stage):
    msg = app.status_text()
    if msg:
        text(surf, msg, 12, COL['muted'], (stage.x + 16, stage.y + 12), bold=True)


def draw_predict(app, surf, stage):
    p = app.pred
    if not p['visible']:
        return
    ui = app.ui
    w = min(540, stage.w - 32)
    r = pygame.Rect(0, 0, w, 132)
    r.midbottom = (stage.centerx, stage.bottom - 16)
    panel = pygame.Surface(r.size, pygame.SRCALPHA)
    rrect(panel, (17, 23, 38, 236), panel.get_rect(), 14)
    surf.blit(panel, r)
    rrect(surf, COL['line'], r, 14, 1)
    text(surf, t('predict'), 12, COL['smooth'], (r.centerx, r.y + 12), 'midtop', True)
    bar = pygame.Rect(r.x + 14, r.y + 34, r.w - 28, 4)
    rrect(surf, COL['panel2'], bar, 2)
    if p['progress'] > 0:
        rrect(surf, COL['smooth'], pygame.Rect(bar.x, bar.y, int(bar.w * p['progress']), 4), 2)
    bw = (r.w - 28 - 16) // 3
    for i, choice in enumerate(('burp', 'fart', 'smooth')):
        br = pygame.Rect(r.x + 14 + i * (bw + 8), r.y + 48, bw, 42)
        picked = p['picked'] == choice
        enabled = not p['locked']
        col = COL[choice] if (enabled or picked) else mix(COL['bg'], COL[choice], 0.35)
        ui.button(surf, br, t(choice), 'predict', choice, style='pred', enabled=enabled, selected=picked,
                  color=col, size=15, radius=10)
    res = p['result']
    if res:
        if res.ok:
            msg = t('correctCombo', n=res.points, s=res.streak) if res.bonus else t('correct', n=res.points)
        else:
            msg = t('late' if res.late else 'wrong')
        if res.life_lost:
            msg += t('lifeLost')
        text(surf, msg, 16, COL['fart'] if res.ok else COL['red'], (r.centerx, r.y + 112), 'center', True)


# ---------- overlay screens ----------
def _card(surf, W, H, cw, ch, top=HEADER_H):
    cw, ch = min(cw, W - 32), min(ch, H - top - 24)
    r = pygame.Rect(0, 0, cw, ch)
    r.center = (W // 2, top + (H - top) // 2)
    rrect(surf, COL['panel'], r, 18)
    rrect(surf, COL['line'], r, 18, 1)
    return r


def draw_overlay(app, surf, W, H):
    name = app.screen
    if not name:
        return
    ui = app.ui
    dim = pygame.Surface((W, H - HEADER_H), pygame.SRCALPHA)
    dim.fill((11, 15, 23, 214))
    surf.blit(dim, (0, HEADER_H))
    ui.block(pygame.Rect(0, HEADER_H, W, H - HEADER_H))
    globals()['_screen_' + name](app, surf, W, H)


def _screen_title(app, surf, W, H):
    ui, save = app.ui, app.save
    r = _card(surf, W, H, 660, 478)
    x, w = r.x + 26, r.w - 52
    y = r.y + 24
    text(surf, t('logo1'), 40, COL['ink'], (r.centerx, y), 'midtop', True)
    y += 50
    text(surf, spaced(t('logo2')), 22, COL['fart'], (r.centerx, y), 'midtop', True)
    y += 36
    for i, c in enumerate(('burp', 'fart', 'smooth')):
        gfx.filled_circle(surf, r.centerx - 20 + i * 20, y, 5, COL[c])
        gfx.aacircle(surf, r.centerx - 20 + i * 20, y, 5, COL[c])
    y += 14
    text(surf, t('tagline'), 15, COL['muted'], (r.centerx, y), 'midtop')
    y += 34
    text(surf, t('modes'), 11, COL['muted'], (x, y), bold=True)
    y += 20
    mw = (w - 16) // 3
    for i, m in enumerate(('classic', 'rush', 'endless')):
        mr = pygame.Rect(x + i * (mw + 8), y, mw, 122)
        hover = ui.hovering(mr)
        rrect(surf, COL['panel2'], mr, 12)
        rrect(surf, COL['fart'] if hover else COL['line'], mr, 12, 1)
        text(surf, t(m), 17, COL['fart'], (mr.x + 12, mr.y + 12), bold=True)
        text_block(surf, t(m + 'Desc'), 12, COL['muted'], mr.x + 12, mr.y + 38, mr.w - 24, max_lines=3)
        text(surf, f"{t('best')} {save['best'][m]}", 11, COL['smooth'], (mr.x + 12, mr.bottom - 10), 'bottomleft', True)
        ui.hit(mr, 'start', m)
    y += 140
    text(surf, t('difficulty'), 11, COL['muted'], (x, y), bold=True)
    y += 20
    diff = save['settings']['difficulty']
    sw = w // 3
    seg = pygame.Rect(x, y, w, 40)
    rrect(surf, COL['panel2'], seg, 10)
    for i, d in enumerate(('easy', 'normal', 'hard')):
        br = pygame.Rect(x + i * sw, y, sw if i < 2 else w - 2 * sw, 40)
        ui.button(surf, br, t(d), 'difficulty', d, style='seg', selected=d == diff, size=13, radius=10)
    rrect(surf, COL['line'], seg, 10, 1)
    y += 48
    text_block(surf, t(diff + 'Desc'), 12, COL['muted'], x, y, w, max_lines=2)
    y = r.bottom - 52
    chips = [(f"{t('foodLog')}  {len(save['tried'])}/{len(FOODS)}", 'go', 'foodlog'),
             (f"{t('achievements')}  {len(save['achievements'])}/{len(ACHIEVEMENTS)}", 'go', 'achievements'),
             (t('settings'), 'go', 'settings'),
             (t('exit'), 'exit', None)]
    widths = [fonts.get(12, True).size(c[0])[0] + 28 for c in chips]
    cx = r.centerx - (sum(widths) + 8 * (len(chips) - 1)) // 2
    for (label, action, arg), cw in zip(chips, widths):
        ui.button(surf, (cx, y, cw, 32), label, action, arg, size=12)
        cx += cw + 8
    text(surf, f'v{__version__}', 11, COL['muted'], (r.right - 14, r.bottom - 8), 'bottomright', lang='en')


def _scroll_list(app, surf, r, items, item_h_fn, draw_fn, footer=0):
    """Two-column scrolling grid inside card r. Returns nothing; updates app.scroll bounds."""
    ui = app.ui
    view = pygame.Rect(r.x + 22, r.y + 62, r.w - 44, r.h - 62 - 70 - footer)
    colw = (view.w - 10) // 2
    rows = [items[i:i + 2] for i in range(0, len(items), 2)]
    heights = [max(item_h_fn(it, colw) for it in row) for row in rows]
    total = sum(heights) + 8 * (len(rows) - 1)
    app.scroll_max = max(0, total - view.h)
    app.scroll = max(0, min(app.scroll, app.scroll_max))
    prev = surf.get_clip()
    surf.set_clip(view)
    y = view.y - app.scroll
    for row, h in zip(rows, heights):
        for j, it in enumerate(row):
            ir = pygame.Rect(view.x + j * (colw + 10), y, colw, h)
            if ir.colliderect(view):
                draw_fn(it, ir)
        y += h + 8
    surf.set_clip(prev)
    if app.scroll_max:
        track = pygame.Rect(view.right + 8, view.y, 4, view.h)
        rrect(surf, COL['panel2'], track, 2)
        th = max(30, int(view.h * view.h / (total or 1)))
        ty = view.y + int((view.h - th) * app.scroll / app.scroll_max)
        rrect(surf, COL['muted'], pygame.Rect(track.x, ty, 4, th), 2)
    return view


def _screen_foodlog(app, surf, W, H):
    ui, save = app.ui, app.save
    r = _card(surf, W, H, 780, 700)
    text(surf, t('foodLog'), 22, COL['ink'], (r.centerx, r.y + 22), 'midtop', True)
    note_h = block_height(t('logNote'), 12, r.w - 44)

    def item_h(f, colw):
        body = L(f.fact) if f.id in save['tried'] else t('untried')
        return 34 + block_height(body, 12, colw - 60) + 10

    def draw(f, ir):
        tried = f.id in save['tried']
        rrect(surf, COL['panel2'], ir, 10)
        rrect(surf, COL['line'], ir, 10, 1)
        if tried:
            draw_icon(surf, f, pygame.Rect(ir.x + 10, ir.y + 10, 28, 28), COL['wire'])
            nr = text(surf, L(f.name), 14, COL['ink'], (ir.x + 48, ir.y + 10), bold=True)
            lab = t('cat' + f.cat)
            bw = fonts.get(10, True).size(lab)[0] + 10
            br = pygame.Rect(nr.right + 8, nr.y + 2, bw, 16)
            if br.right > ir.right - 6:
                br.topright = (ir.right - 8, ir.y + 10)
            rrect(surf, COL[f.cat], br, 4, 1)
            text(surf, lab, 10, COL[f.cat], br.center, 'center', True)
            text_block(surf, L(f.fact), 12, COL['muted'], ir.x + 48, ir.y + 32, ir.w - 60)
        else:
            gfx.aacircle(surf, ir.x + 24, ir.y + 24, 9, COL['muted'])
            text(surf, '???', 14, COL['muted'], (ir.x + 48, ir.y + 10), bold=True)
            text_block(surf, t('untried'), 12, mix(COL['bg'], COL['muted'], 0.7), ir.x + 48, ir.y + 32, ir.w - 60)

    view = _scroll_list(app, surf, r, FOODS, item_h, draw, footer=note_h + 8)
    text_block(surf, t('logNote'), 12, COL['muted'], r.x + 22, view.bottom + 10, r.w - 44)
    ui.button(surf, (r.x + 22, r.bottom - 58, r.w - 44, 42), t('back'), 'go', 'title', style='ghost', size=15, radius=12)


def _screen_achievements(app, surf, W, H):
    ui, save = app.ui, app.save
    r = _card(surf, W, H, 720, 560)
    text(surf, t('achievements'), 22, COL['ink'], (r.centerx, r.y + 22), 'midtop', True)

    def item_h(a, colw):
        return 34 + block_height(L(a.desc), 12, colw - 54) + 10

    def draw(a, ir):
        on = a.id in save['achievements']
        rrect(surf, COL['panel2'], ir, 10)
        rrect(surf, mix(COL['bg'], COL['smooth'], 0.5) if on else COL['line'], ir, 10, 1)
        cx, cy = ir.x + 22, ir.y + 22
        if on:
            for rad in range(11, 0, -1):
                gfx.filled_circle(surf, cx, cy, rad, mix(COL['smooth'], (255, 246, 196), (11 - rad) / 14))
            gfx.aacircle(surf, cx, cy, 11, COL['smooth'])
        else:
            for k in range(0, 360, 30):
                a0 = math.radians(k)
                pygame.draw.arc(surf, COL['muted'], (cx - 11, cy - 11, 22, 22), a0, a0 + math.radians(15), 2)
        fg = COL['ink'] if on else mix(COL['bg'], COL['ink'], 0.55)
        text(surf, L(a.name), 14, fg, (ir.x + 44, ir.y + 10), bold=True)
        text_block(surf, L(a.desc), 12, COL['muted'] if on else mix(COL['bg'], COL['muted'], 0.6),
                   ir.x + 44, ir.y + 32, ir.w - 54)

    _scroll_list(app, surf, r, ACHIEVEMENTS, item_h, draw)
    ui.button(surf, (r.x + 22, r.bottom - 58, r.w - 44, 42), t('back'), 'go', 'title', style='ghost', size=15, radius=12)


def _screen_settings(app, surf, W, H):
    ui, st = app.ui, app.save['settings']
    r = _card(surf, W, H, 500, 468)
    text(surf, t('settings'), 22, COL['ink'], (r.centerx, r.y + 22), 'midtop', True)
    x, w, y = r.x + 24, r.w - 48, r.y + 70

    def row(label):
        nonlocal y
        rr = pygame.Rect(x, y, w, 48)
        rrect(surf, COL['panel2'], rr, 10)
        rrect(surf, COL['line'], rr, 10, 1)
        text(surf, label, 14, COL['ink'], (rr.x + 14, rr.centery), 'midleft', True)
        y += 56
        return rr

    rr = row(t('language'))
    ui.button(surf, pygame.Rect(rr.right - 118, rr.centery - 15, 106, 30),
              '日本語' if get_lang() == 'ja' else 'English', 'lang', size=13)
    rr = row(t('volume'))
    slider = pygame.Rect(rr.right - 200, rr.centery - 3, 186, 6)
    rrect(surf, COL['line'], slider, 3)
    vol = 0 if st['muted'] else st['volume']
    rrect(surf, COL['fart'], pygame.Rect(slider.x, slider.y, int(slider.w * vol), 6), 3)
    kx = slider.x + int(slider.w * vol)
    gfx.filled_circle(surf, kx, slider.centery, 9, COL['ink'])
    gfx.aacircle(surf, kx, slider.centery, 9, COL['ink'])
    app.slider_rect = slider
    ui.hit(slider.inflate(20, 30), 'volume_drag')
    rr = row(t('music'))
    on = st.get('music', True)
    ui.button(surf, pygame.Rect(rr.right - 86, rr.centery - 15, 74, 30), t('on' if on else 'off'), 'music',
              size=13, color=COL['fart'] if on else COL['muted'])
    rr = row(t('shakeOpt'))
    ui.button(surf, pygame.Rect(rr.right - 86, rr.centery - 15, 74, 30), t('on' if st['shake'] else 'off'), 'shake',
              size=13, color=COL['fart'] if st['shake'] else COL['muted'])
    rr = row(t('fullscreen'))
    ui.button(surf, pygame.Rect(rr.right - 86, rr.centery - 15, 74, 30), t('on' if st['fullscreen'] else 'off'),
              'fullscreen', size=13, color=COL['fart'] if st['fullscreen'] else COL['muted'])
    lab = t('reset')
    bw = fonts.get(12, True).size(lab)[0] + 30
    ui.button(surf, pygame.Rect(r.centerx - bw // 2, y + 4, bw, 32), lab, 'reset', style='danger', size=12)
    ui.button(surf, (x, r.bottom - 58, w, 42), t('back'), 'go', 'title', style='ghost', size=15, radius=12)
    text(surf, f'Digestion Lab v{__version__}', 11, COL['muted'], (r.right - 14, r.y + 14), 'topright', lang='en')


def _screen_confirm(app, surf, W, H):
    ui = app.ui
    r = _card(surf, W, H, 460, 230)
    text_block(surf, t('resetConfirm'), 16, COL['ink'], r.x + 30, r.y + 34, r.w - 60, bold=True, align='center')
    bw = (r.w - 60 - 12) // 2
    ui.button(surf, (r.x + 30, r.bottom - 70, bw, 44), t('no'), 'go', 'settings', style='ghost', size=14, radius=12)
    ui.button(surf, (r.x + 42 + bw, r.bottom - 70, bw, 44), t('yes'), 'reset_yes', style='danger', size=14, radius=12)


def _screen_pause(app, surf, W, H):
    ui = app.ui
    r = _card(surf, W, H, 400, 250)
    text(surf, t('paused'), 24, COL['ink'], (r.centerx, r.y + 28), 'midtop', True)
    ui.button(surf, (r.x + 30, r.y + 90, r.w - 60, 46), t('resume'), 'resume', style='primary', size=16, radius=12)
    ui.button(surf, (r.x + 30, r.y + 148, r.w - 60, 46), t('quit'), 'quit', style='ghost', size=15, radius=12)


def _screen_results(app, surf, W, H):
    ui, s = app.ui, app.session
    r = _card(surf, W, H, 460, 440)
    y = r.y + 26
    text(surf, f"{t('results')} · {t(s.mode)}", 20, COL['ink'], (r.centerx, y), 'midtop', True)
    y += 44
    if app.new_best:
        lab = t('newBest')
        bw = fonts.get(14, True).size(lab)[0] + 22
        br = pygame.Rect(r.centerx - bw // 2, y, bw, 26)
        rrect(surf, COL['smooth'], br, 6)
        text(surf, lab, 14, COL['bg'], br.center, 'center', True)
    y += 34
    text(surf, str(s.score), 66, COL['smooth'], (r.centerx, y), 'midtop', True)
    y += 84
    text(surf, t('ranks')[app.rank], 18, COL['ink'], (r.centerx, y), 'midtop', True)
    y += 40
    for i, (lab, val) in enumerate(((t('statCorrect'), f'{s.correct}/{s.round}'), (t('statStreak'), str(s.best_streak)))):
        cx = r.centerx + (-70 if i == 0 else 70)
        text(surf, lab, 11, COL['muted'], (cx, y), 'midtop', True)
        text(surf, val, 22, COL['ink'], (cx, y + 18), 'midtop', True)
    ui.button(surf, (r.x + 30, r.bottom - 118, r.w - 60, 46), t('again'), 'again', style='primary', size=16, radius=12)
    ui.button(surf, (r.x + 30, r.bottom - 62, r.w - 60, 44), t('toTitle'), 'quit', style='ghost', size=15, radius=12)


# ---------- toasts ----------
def draw_toasts(app, surf, W):
    y = HEADER_H + 12
    now = app.clock_time
    for title, body, t0 in app.toasts:
        age = now - t0
        alpha = 1.0 if age < 2.6 else max(0.0, 1 - (age - 2.6) / 0.5)
        slide = 0 if age > 0.3 else (0.3 - age) / 0.3 * -12
        f1, f2 = fonts.get(10, True), fonts.get(15, True)
        w = max(f1.size(title)[0], f2.size(body)[0]) + 36
        r = pygame.Rect(0, 0, w, 48)
        r.midtop = (W // 2, int(y + slide))
        box = pygame.Surface(r.size, pygame.SRCALPHA)
        rrect(box, (*COL['panel'], 245), box.get_rect(), 12)
        rrect(box, COL['smooth'], box.get_rect(), 12, 1)
        text(box, title, 10, COL['smooth'], (w // 2, 8), 'midtop', True)
        text(box, body, 15, COL['ink'], (w // 2, 22), 'midtop', True)
        box.set_alpha(int(255 * alpha))
        surf.blit(box, r)
        y += 56
