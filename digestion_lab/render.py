"""Draws the wireframe body and the simulation onto the stage area."""
import math
import random

import pygame
import pygame.gfxdraw as gfx

from . import fonts
from .geometry import (VW, VH, BODY, BACK, ARM, CHEEK, EYE, EAR, STOM_CX, STOM_CY, STOM_W, STOM_H,
                       P_ESO, P_SI, P_COLON, P_BYPASS, BRANCH_D)
from .i18n import t
from .sim import DISSOLVE

COL = {
    'bg': (11, 15, 23), 'panel': (17, 23, 38), 'panel2': (23, 32, 54), 'line': (38, 49, 75),
    'ink': (230, 236, 247), 'muted': (127, 139, 166), 'wire': (143, 211, 255),
    'burp': (63, 180, 255), 'fart': (93, 255, 122), 'smooth': (255, 216, 74),
    'red': (255, 93, 108), 'mystery': (207, 214, 228),
}


def mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def clamp01(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def smoothstep(a, b, x):
    k = clamp01((x - a) / (b - a))
    return k * k * (3 - 2 * k)


def ease_out_back(x):
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def offset_line(pts, d):
    """Polyline shifted sideways by d: used to draw both walls of a tube."""
    out = []
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[max(0, i - 1)]
        x1, y1 = pts[min(n - 1, i + 1)]
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) or 1.0
        out.append((pts[i][0] - dy / ln * d, pts[i][1] + dx / ln * d))
    return out


class StageRenderer:
    def __init__(self):
        self.s, self.ox, self.oy = 1.0, 0.0, 0.0
        self._glow = {}
        self._burst_cache = {}
        self._walls = {}

    def P(self, x, y):
        return self.ox + x * self.s, self.oy + y * self.s

    def Pi(self, x, y):
        return int(self.ox + x * self.s), int(self.oy + y * self.s)

    # ---------- primitives ----------
    def glow_sprite(self, color, radius):
        key = (color, radius)
        g = self._glow.get(key)
        if g is None:
            size = radius * 2
            g = pygame.Surface((size, size))
            for r in range(radius, 0, -1):
                k = (1 - r / radius) ** 2 * 0.55
                pygame.draw.circle(g, tuple(int(c * k) for c in color), (radius, radius), r)
            self._glow[key] = g
        return g

    def particle(self, surf, x, y, r, color, alpha=1.0):
        X, Y = self.P(x, y)
        gr = max(4, int(r * self.s * 3.2))
        if alpha > 0.5:
            surf.blit(self.glow_sprite(color, gr), (X - gr, Y - gr), special_flags=pygame.BLEND_RGB_ADD)
        rr = max(1, int(r * self.s))
        c = (*color, int(255 * clamp01(alpha)))
        gfx.filled_circle(surf, int(X), int(Y), rr, c)
        gfx.aacircle(surf, int(X), int(Y), rr, c)

    def aalines(self, surf, color, pts, closed=False):
        if len(pts) > 1:
            pygame.draw.aalines(surf, color, closed, [self.P(*p) for p in pts])

    def dashed(self, surf, color, pts, dash, gap, offset=0.0, width=1):
        """Dashed polyline in virtual coordinates."""
        period = dash + gap
        pos = -(offset % period)
        for a, b in zip(pts, pts[1:]):
            seg = math.hypot(b[0] - a[0], b[1] - a[1])
            if seg == 0:
                continue
            d = pos
            while d < seg:
                s0, s1 = max(0.0, d), min(seg, d + dash)
                if s1 > s0:
                    p0 = (a[0] + (b[0] - a[0]) * s0 / seg, a[1] + (b[1] - a[1]) * s0 / seg)
                    p1 = (a[0] + (b[0] - a[0]) * s1 / seg, a[1] + (b[1] - a[1]) * s1 / seg)
                    if width > 1:
                        pygame.draw.line(surf, color, self.P(*p0), self.P(*p1), width)
                    else:
                        pygame.draw.aaline(surf, color, self.P(*p0), self.P(*p1))
                d += period
            pos = d - seg

    def tube(self, surf, path, color, width, fill=None):
        if fill:
            pygame.draw.lines(surf, fill, False, [self.P(*p) for p in path.pts], max(1, int(width * self.s)))
        walls = self._walls.get(id(path))
        if walls is None or walls[2:] != (width,):
            walls = (offset_line(path.pts, width / 2), offset_line(path.pts, -width / 2), width)
            self._walls[id(path)] = walls
        self.aalines(surf, color, walls[0])
        self.aalines(surf, color, walls[1])

    def flow(self, surf, path, color, now, alpha):
        c = (*color, int(255 * alpha))
        d = (now * 24) % 14
        while d < path.length:
            x, y, _ = path.at(d)
            X, Y = self.Pi(x, y)
            gfx.filled_circle(surf, X, Y, max(1, int(self.s)), c)
            d += 14

    def label(self, surf, key, x, y, tx, ty, align='left'):
        self.dashed(surf, COL['line'], [(x + (-6 if align == 'left' else 6), y - 4), (tx, ty)], 3, 3)
        f = fonts.get(12 * self.s, bold=True)
        img = f.render(t(key), True, COL['muted'])
        X, Y = self.P(x, y)
        r = img.get_rect(bottomleft=(X, Y + 3)) if align == 'left' else img.get_rect(bottomright=(X, Y + 3))
        surf.blit(img, r)

    def burst(self, surf, e, now):
        k = (now - e['t0']) / e['dur']
        scale = max(0.01, ease_out_back(k / 0.14)) if k < 0.14 else 1 + 0.03 * math.sin(now * 18)
        alpha = 1 - (k - 0.75) / 0.25 if k > 0.75 else 1.0
        size_px = max(10, int(e['size'] * self.s))
        key = (e['key'], t(e['key']), e['sub'], size_px)
        base = self._burst_cache.get(key)
        if base is None:
            base = self._make_burst(t(e['key']), e['sub'], size_px, COL[e['cat']])
            if len(self._burst_cache) > 30:
                self._burst_cache.clear()
            self._burst_cache[key] = base
        img = pygame.transform.rotozoom(base, -math.degrees(e['rot']), scale)
        img.set_alpha(int(255 * clamp01(alpha)))
        surf.blit(img, img.get_rect(center=self.P(e['x'], e['y'])))

    def _make_burst(self, text, sub, size, color):
        f = fonts.get(size, bold=True)
        txt = f.render(text, True, color)
        rx, ry = txt.get_width() / 2 + size * 0.75, size * 1.15
        W, H = int(rx * 2.6), int(ry * 2.6)
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx, cy = W / 2, H / 2
        pts = []
        for i in range(44):
            a = i / 44 * math.tau
            out = 1.12 + 0.1 * math.sin(i * 7.3) if i % 2 == 0 else 0.88
            pts.append((cx + math.cos(a) * rx * out, cy + math.sin(a) * ry * out))
        gfx.filled_polygon(s, pts, (11, 15, 23, 228))
        pygame.draw.polygon(s, color, pts, 3)
        gfx.aapolygon(s, pts, color)
        outline = f.render(text, True, COL['bg'])
        tr = txt.get_rect(center=(cx, cy))
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)):
            s.blit(outline, tr.move(dx, dy))
        s.blit(txt, tr)
        if sub:
            sf = fonts.get(size * 0.36, bold=True)
            simg = sf.render(sub, True, COL['ink'])
            s.blit(simg, simg.get_rect(center=(cx, cy + size * 0.72)))
        return s

    # ---------- frame ----------
    def draw(self, surf, rect, sim, mystery=False, shake_enabled=True):
        s = min(rect.w / VW, rect.h / VH)
        sk = sim.shake_amp * (sim.shake_t / sim.shake_dur) if shake_enabled and sim.shake_t > 0 else 0
        self.s = s
        self.ox = rect.x + (rect.w - VW * s) / 2 + (random.random() - .5) * 2 * sk * s
        self.oy = rect.y + (rect.h - VH * s) / 2 + (random.random() - .5) * 2 * sk * s
        now, run = sim.time, sim.run
        cat = run.cat if run else None
        prev_clip = surf.get_clip()
        surf.set_clip(rect)
        surf.fill(COL['bg'], rect)

        # grid
        gc = mix(COL['bg'], COL['wire'], 0.06)
        for x in range(0, VW + 1, 40):
            pygame.draw.line(surf, gc, self.P(x, 0), self.P(x, VH))
        for y in range(0, VH + 1, 40):
            pygame.draw.line(surf, gc, self.P(0, y), self.P(VW, y))

        # body wireframe
        wire_dim = mix(COL['bg'], COL['wire'], 0.78)
        self.aalines(surf, wire_dim, BODY)
        self.aalines(surf, wire_dim, BACK)
        self.dashed(surf, mix(COL['bg'], COL['wire'], 0.28), ARM, 4, 5)
        vc = mix(COL['bg'], COL['wire'], 0.6)
        for x, y in BODY + BACK:
            X, Y = self.Pi(x, y)
            surf.fill(vc, (X - 1, Y - 1, 3, 3))
        X, Y = self.Pi(*EYE)
        gfx.aacircle(surf, X, Y, max(2, int(3 * s)), wire_dim)
        ear = [(EAR[0] + 11 * math.cos(a / 10), EAR[1] + 11 * math.sin(a / 10)) for a in range(-12, 15)]
        self.aalines(surf, wire_dim, ear)

        # cheek puff: inflates over the last 0.7s before a burp, snaps back on release
        puff = 0.0
        if cat == 'burp' and run.arrived:
            puff = clamp01(1 - (run.t - run.tf) / 0.2) if run.fired else \
                smoothstep(run.tr + run.wait - 0.7, run.tr + run.wait, run.t)
        X, Y = self.Pi(CHEEK[0] + puff * 6, CHEEK[1])
        rx, ry = max(2, int((7 + puff * 13) * s)), max(2, int((6 + puff * 10) * s))
        if puff:
            gfx.filled_ellipse(surf, X, Y, rx, ry, (*COL['burp'], 46))
            gfx.aaellipse(surf, X, Y, rx, ry, COL['burp'])
        else:
            gfx.aaellipse(surf, X, Y, rx, ry, mix(COL['bg'], COL['wire'], 0.35))

        # digestive tract
        gas = sim.gas()
        lead_d = min(1.0, run.t / run.D) * run.path.length if run else 0
        self.tube(surf, P_ESO, COL['wire'], 9)
        self.tube(surf, P_SI, COL['wire'], 8)
        colon_w = 10 + gas * 6
        self.tube(surf, P_COLON, COL['fart'] if gas else COL['wire'], colon_w,
                  fill=mix(COL['bg'], COL['fart'], 0.35 * gas) if gas else None)
        if cat == 'fart' and lead_d >= BRANCH_D:
            self.dashed(surf, COL['fart'], P_BYPASS.pts, 6, 6, offset=now * 30, width=max(2, int(2 * s)))
            self.label(surf, 'express', 200, 345, 293, 355, 'right')
        self.flow(surf, P_ESO, COL['wire'], now, 0.25)
        self.flow(surf, P_SI, COL['wire'], now, 0.18)
        self.flow(surf, P_COLON, COL['fart'] if gas else COL['wire'], now, 0.18 + gas * 0.5)

        # stomach rectangle
        pr = sim.pressure()
        sc = 1 + 0.3 * pr + (math.sin(now * 30) * 0.01 if pr and not run.fired else 0)
        sw, sh = STOM_W * sc, STOM_H * sc
        x0, y0 = self.P(STOM_CX - sw / 2, STOM_CY - sh / 2)
        srect = pygame.Rect(int(x0), int(y0), int(sw * s), int(sh * s))
        surf.fill(COL['bg'], srect)
        if cat == 'burp' and run.arrived:
            gfx.box(surf, srect, (*COL['burp'], int(255 * (0.08 + 0.14 * pr))))
        if cat == 'smooth' and run.arrived:
            g = clamp01(1 - (run.t - run.tf)) if run.fired else clamp01((run.t - run.D) / 1.5)
            gfx.box(surf, srect, (*COL['smooth'], int(255 * 0.18 * g)))
        scol = COL['burp'] if cat == 'burp' and run.arrived else COL['wire']
        pygame.draw.rect(surf, scol, srect, max(1, int(1.8 * s)))
        inset = max(2, int(4 * s))
        pygame.draw.rect(surf, mix(COL['bg'], COL['wire'], 0.35), srect.inflate(-2 * inset, -2 * inset), 1)

        # bubbles, clipped to the stomach
        if sim.bubbles:
            surf.set_clip(srect.clip(rect))
            for b in sim.bubbles:
                a = clamp01(1 - (b['r'] - b['max']) / (b['max'] * 1.2)) if b['popping'] else 1.0
                X, Y = self.Pi(b['x'], b['y'])
                rr = max(1, int(b['r'] * s))
                if not b['popping']:
                    gfx.filled_circle(surf, X, Y, rr, (*COL['burp'], 38))
                gfx.aacircle(surf, X, Y, rr, (*COL['burp'], int(255 * a)))
            surf.set_clip(rect)

        self.label(surf, 'eso', 452, 232, 333, 228)
        self.label(surf, 'stomach', 452, 362, STOM_CX + sw / 2 + 2, 362)
        self.label(surf, 'small', 452, 484, 395, 482)
        self.label(surf, 'large', 452, 566, 412, 545)

        # food particles
        if run:
            col = COL['mystery'] if mystery and not run.arrived else COL[cat]
            L = run.path.length
            for i, p in enumerate(run.parts):
                lt = run.t - i * run.stagger
                if lt < 0:
                    continue
                k = lt / run.D
                if k < 1:
                    for tr in (2, 1, 0):
                        x, y, a = run.path.at(k * L - tr * 7)
                        self.particle(surf, x - math.sin(a) * p.j, y + math.cos(a) * p.j, p.r * (1 - tr * 0.22), col,
                                      0.25 if tr else 1.0)
                    continue
                since = lt - run.D
                if cat == 'burp':
                    if since < 0.25:
                        self.particle(surf, STOM_CX + p.ox * .6, STOM_CY + p.oy * .6, p.r, COL['burp'], 1 - since / .25)
                elif cat == 'smooth':
                    q = since / DISSOLVE
                    if q < 1:
                        b = smoothstep(0, 0.3, since)
                        self.particle(surf, STOM_CX + p.ox * b + math.cos(now * 2 + p.ph) * 4 * b,
                                      STOM_CY + p.oy * b + math.sin(now * 2 + p.ph) * 3 * b,
                                      p.r * (1 - q * 0.8), COL['smooth'], 1 - q)
                elif not run.fired:
                    ex, ey, _ = run.path.at(L)
                    self.particle(surf, ex + p.ox * 0.2 + math.sin(now * 9 + p.ph) * 1.5, ey + p.oy * 0.25, p.r,
                                  COL['fart'], 0.9)

            # gas building up in the rectum
            if cat == 'fart' and run.arrived and not run.fired:
                for i in range(7):
                    a = i / 7 * math.tau + now * 1.5
                    X, Y = self.Pi(286 + math.cos(a) * gas * 10, 595 + math.sin(a) * gas * 8)
                    rr = max(1, int((4 + gas * 13 + math.sin(now * 6 + i) * 2) * s))
                    gfx.filled_circle(surf, X, Y, rr, (*COL['fart'], int(255 * (0.18 + gas * 0.2))))

        # puffs: burp rings, fart clouds, smooth sparkles
        for p in sim.puffs:
            a = clamp01(p['life'] / p['max'])
            c = COL[p['cat']]
            X, Y = self.Pi(p['x'], p['y'])
            rr = max(1, int(p['r'] * s))
            if p['kind'] == 'star':
                ang = now * 4
                dx, dy = math.cos(ang) * 4 * s, math.sin(ang) * 4 * s
                cc = (*c, int(255 * a))
                pygame.draw.line(surf, cc, (X - dx, Y - dy), (X + dx, Y + dy), max(1, int(2 * s)))
                pygame.draw.line(surf, cc, (X + dy, Y - dx), (X - dy, Y + dx), max(1, int(2 * s)))
            elif p['kind'] == 'ring':
                gfx.aacircle(surf, X, Y, rr, (*c, int(255 * a)))
            else:
                gfx.filled_circle(surf, X, Y, rr, (*c, int(255 * a * 0.28)))
                gfx.aacircle(surf, X, Y, rr, (*c, int(255 * a * 0.6)))

        for e in sim.fx:
            self.burst(surf, e, now)
        surf.set_clip(prev_clip)
