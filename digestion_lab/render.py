"""Draws the cartoon body and the simulation onto the stage area.

The whole body squashes, stretches and hops with the action. Every body point goes through P(),
which applies that pose, so organs, food and bubbles stay inside the body while it moves.
Effects that leave the body (fart clouds, burp rings, text bursts) are drawn with the pose off.
"""
import math
import random

import pygame
import pygame.gfxdraw as gfx

from . import fonts
from .geometry import (VW, VH, TOP, HEAD_C, HEAD_R, TORSO, LEGS, LEG_W, SHOULDER, ARM_UPPER, ARM_FORE, EYES, NOSE, EAR,
                       HAIR, CHEEK, STOMACH, STOM_CX, STOM_CY, P_ESO, P_SI, P_COLON, P_BYPASS, BRANCH_D,
                       chaikin, chaikin_closed)
from .i18n import t
from .sim import DISSOLVE

COL = {
    'bg': (11, 15, 23), 'panel': (17, 23, 38), 'panel2': (23, 32, 54), 'line': (38, 49, 75),
    'ink': (230, 236, 247), 'muted': (127, 139, 166), 'wire': (143, 211, 255),
    'burp': (63, 180, 255), 'fart': (93, 255, 122), 'smooth': (255, 216, 74),
    'red': (255, 93, 108), 'mystery': (207, 214, 228),
}

# Cartoon palette for the body and organs. 'ink' is the thick outline round everything.
TOON = {
    'ink': (24, 22, 44), 'skin': (112, 186, 236), 'skin_far': (84, 150, 206), 'shine': (200, 234, 255),
    'blush': (255, 120, 160), 'hair': (58, 46, 104), 'shoe': (255, 93, 108), 'lace': (255, 240, 245),
    'eso': (255, 150, 172), 'stomach': (255, 124, 150), 'small': (255, 186, 150), 'large': (236, 112, 142),
    'mouth': (96, 24, 52), 'tongue': (255, 120, 146), 'white': (255, 255, 255), 'sweat': (170, 225, 255),
    'cloud': (150, 255, 160), 'cloud_ink': (40, 140, 70), 'heart': (255, 96, 140),
}
ANCHOR = (340, 800)   # between the feet: squash and stretch happen around this point

HEAD = [(HEAD_C[0] + math.cos(i / 80 * math.tau) * HEAD_R, HEAD_C[1] + math.sin(i / 80 * math.tau) * HEAD_R)
        for i in range(80)]
HEAD_SHINE = [(HEAD_C[0] + math.cos(a / 20) * (HEAD_R - 13), HEAD_C[1] + math.sin(a / 20) * (HEAD_R - 13))
              for a in range(69, 86)]
BELLY_SHINE = chaikin([(432, 292), (444, 340), (452, 396)], 2)
SMILE = chaikin([(367, 140), (380, 149), (393, 146)], 2)
GRIN = chaikin_closed([(366, 140), (395, 142), (391, 152), (380, 158), (370, 151)], 2)


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


def star_points(cx, cy, r, rot, n=5, inner=0.45):
    return [(cx + math.cos(rot + i * math.pi / n) * r * (1 if i % 2 == 0 else inner),
             cy + math.sin(rot + i * math.pi / n) * r * (1 if i % 2 == 0 else inner)) for i in range(n * 2)]


def heart_points(cx, cy, r):
    return [(cx + r * 16 * math.sin(a) ** 3 / 17, cy - r * (13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a)
                                                         - math.cos(4 * a)) / 17)
            for a in (i / 24 * math.tau for i in range(24))]


class StageRenderer:
    def __init__(self):
        self.s, self.ox, self.oy = 1.0, 0.0, 0.0
        self.kx = self.ky = 1.0
        self.hop = 0.0
        self.xf = True               # apply the body pose in P()
        self.arm = [-0.4, -1.3]      # upper arm and forearm angles, eased toward a target each frame
        self._last = None
        self._bg = None
        self._burst_cache = {}

    def P(self, x, y):
        if self.xf:
            x = ANCHOR[0] + (x - ANCHOR[0]) * self.kx
            y = ANCHOR[1] + (y - ANCHOR[1]) * self.ky - self.hop
        return self.ox + x * self.s, self.oy + y * self.s

    def Pi(self, x, y):
        X, Y = self.P(x, y)
        return int(X), int(Y)

    def R(self, r):
        return max(1, int(r * self.s))

    # ---------- cartoon primitives ----------
    def stroke(self, surf, pts, color, w, closed=False, screen=False):
        """Thick polyline with round joints and caps."""
        sp = pts if screen else [self.P(*p) for p in pts]
        if len(sp) < 2:
            return
        px = max(1, int(round(w * self.s)))
        if px <= 1:
            pygame.draw.aalines(surf, color, closed, sp)
            return
        pygame.draw.lines(surf, color, closed, sp, px)
        if px >= 3:
            for p in sp:
                pygame.draw.circle(surf, color, p, px / 2)

    def shape(self, surf, pts, fill, ol=TOON['ink'], w=3.0):
        """Filled polygon with a thick cartoon outline. Returns the screen points."""
        sp = [self.P(*p) for p in pts]
        if fill is not None:
            gfx.filled_polygon(surf, sp, fill)
            gfx.aapolygon(surf, sp, fill)
        if ol is not None:
            self.stroke(surf, sp, ol, w, closed=True, screen=True)
        return sp

    def disc(self, surf, x, y, r, fill, ol=TOON['ink'], w=2.5):
        X, Y = self.Pi(x, y)
        if ol is not None:
            gfx.filled_circle(surf, X, Y, self.R(r + w), ol)
            gfx.aacircle(surf, X, Y, self.R(r + w), ol)
        gfx.filled_circle(surf, X, Y, self.R(r), fill)
        gfx.aacircle(surf, X, Y, self.R(r), fill)

    def oval(self, surf, x, y, rx, ry, fill, ol=TOON['ink'], w=2.5):
        X, Y = self.Pi(x, y)
        if ol is not None:
            gfx.filled_ellipse(surf, X, Y, self.R(rx + w), self.R(ry + w), ol)
            gfx.aaellipse(surf, X, Y, self.R(rx + w), self.R(ry + w), ol)
        gfx.filled_ellipse(surf, X, Y, self.R(rx), self.R(ry), fill)
        gfx.aaellipse(surf, X, Y, self.R(rx), self.R(ry), fill)

    def tube(self, surf, path, fill, width, w=2.5):
        sp = [self.P(*p) for p in path.pts]
        self.stroke(surf, sp, TOON['ink'], width + 2 * w, screen=True)
        self.stroke(surf, sp, fill, width, screen=True)

    def colon(self, surf, fill, base_w, bump):
        """Large intestine: a chunky tube whose walls bulge in pouches (haustra)."""
        pts, cum = P_COLON.pts, P_COLON.cum
        outer, inner = [], []
        for i, (x, y) in enumerate(pts):
            x0, y0 = pts[max(0, i - 1)]
            x1, y1 = pts[min(len(pts) - 1, i + 1)]
            ln = math.hypot(x1 - x0, y1 - y0) or 1.0
            nx, ny = -(y1 - y0) / ln, (x1 - x0) / ln
            w = base_w / 2 + bump * abs(math.sin(cum[i] / 7.5))
            outer.append((x + nx * w, y + ny * w))
            inner.append((x - nx * w, y - ny * w))
        self.shape(surf, outer + inner[::-1], fill, w=2.5)

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

    def particle(self, surf, x, y, r, color, alpha=1.0):
        """A food blob: outlined, with a shiny highlight."""
        X, Y = self.Pi(x, y)
        rr = self.R(r * 1.3)
        if alpha < 0.99:
            gfx.filled_circle(surf, X, Y, rr, (*color, int(255 * clamp01(alpha))))
            return
        gfx.filled_circle(surf, X, Y, rr + max(1, int(1.6 * self.s)), TOON['ink'])
        gfx.filled_circle(surf, X, Y, rr, color)
        gfx.aacircle(surf, X, Y, rr, color)
        gfx.filled_circle(surf, X - rr // 3, Y - rr // 3, max(1, rr // 3), (255, 255, 255, 210))

    def label(self, surf, key, x, y, tx, ty, align='left'):
        """A rounded name tag with a dotted leader to the organ."""
        self.dashed(surf, COL['muted'], [(x, y), (tx, ty)], 3, 3)
        X, Y = self.Pi(tx, ty)
        gfx.filled_circle(surf, X, Y, max(2, int(2.5 * self.s)), COL['ink'])
        f = fonts.get(11 * self.s, bold=True)
        img = f.render(t(key), True, COL['ink'])
        pad = 6 * self.s
        X, Y = self.P(x, y)
        r = img.get_rect(midleft=(X + pad, Y)) if align == 'left' else img.get_rect(midright=(X - pad, Y))
        box = r.inflate(pad * 2, pad)
        pygame.draw.rect(surf, COL['panel2'], box, border_radius=box.h // 2)
        pygame.draw.rect(surf, COL['line'], box, max(1, int(1.5 * self.s)), border_radius=box.h // 2)
        surf.blit(img, r)

    # ---------- text bursts: comic starburst with bouncing letters ----------
    def burst(self, surf, e, now):
        k = (now - e['t0']) / e['dur']
        scale = max(0.01, ease_out_back(k / 0.16)) if k < 0.16 else 1 + 0.04 * math.sin(now * 14)
        alpha = 1 - (k - 0.75) / 0.25 if k > 0.75 else 1.0
        size_px = max(10, int(e['size'] * self.s))
        text = t(e['key'])
        key = (text, e['sub'], size_px, e['cat'])
        base = self._burst_cache.get(key)
        if base is None:
            base = self._make_burst(text, e['sub'], size_px, COL[e['cat']])
            if len(self._burst_cache) > 30:
                self._burst_cache.clear()
            self._burst_cache[key] = base
        bg, letters = base
        img = bg.copy()
        for i, (g, x, y) in enumerate(letters):
            img.blit(g, (x, y + math.sin(now * 12 - i * 0.9) * size_px * 0.1))
        img = pygame.transform.rotozoom(img, -math.degrees(e['rot']) + 4 * math.sin(now * 6), scale)
        img.set_alpha(int(255 * clamp01(alpha)))
        surf.blit(img, img.get_rect(center=self.P(e['x'], e['y'])))

    def _make_burst(self, text, sub, size, color):
        f = fonts.get(size, bold=True)
        tw = f.size(text)[0]
        rx, ry = tw / 2 + size * 0.8, size * 1.2
        W, H = int(rx * 2.7), int(ry * 2.9)
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx, cy = W / 2, H / 2
        pts = []
        for i in range(36):
            a = i / 36 * math.tau
            out = 1.14 + 0.08 * math.sin(i * 5.1) if i % 2 == 0 else 0.86
            pts.append((cx + math.cos(a) * rx * out, cy + math.sin(a) * ry * out))
        sh = max(3, size // 10)
        gfx.filled_polygon(s, [(x + sh, y + sh) for x, y in pts], (*TOON['ink'], 200))
        gfx.filled_polygon(s, pts, color)
        pygame.draw.polygon(s, TOON['ink'], pts, max(3, size // 14))
        inner = [(cx + (x - cx) * 0.8, cy + (y - cy) * 0.8) for x, y in pts]
        gfx.filled_polygon(s, inner, (*mix(color, (255, 255, 255), 0.35), 255))
        # Each letter gets a thick ink outline so it can bounce on its own.
        letters, x = [], cx - tw / 2
        ol = max(2, size // 16)
        for ch in text:
            if ch.isspace():
                x += f.size(ch)[0]
                continue
            g = f.render(ch, True, TOON['white'])
            o = f.render(ch, True, TOON['ink'])
            gl = pygame.Surface((g.get_width() + ol * 2, g.get_height() + ol * 2), pygame.SRCALPHA)
            for dx in range(-ol, ol + 1, max(1, ol // 2)):
                for dy in range(-ol, ol + 1, max(1, ol // 2)):
                    if dx * dx + dy * dy <= ol * ol + 1:
                        gl.blit(o, (ol + dx, ol + dy))
            gl.blit(g, (ol, ol))
            letters.append((gl, x - ol, cy - g.get_height() / 2 - ol - (size * 0.12 if sub else 0)))
            x += g.get_width()
        if sub:
            sf = fonts.get(size * 0.34, bold=True)
            simg = sf.render(sub, True, TOON['ink'])
            s.blit(simg, simg.get_rect(center=(cx, cy + size * 0.62)))
        return s, letters

    # ---------- backdrop ----------
    def backdrop(self, rect, s):
        if self._bg and self._bg[0] == (rect.size, s):
            return self._bg[1]
        surf = pygame.Surface(rect.size)
        top, bot = (28, 34, 64), (12, 16, 28)
        for y in range(rect.h):
            pygame.draw.line(surf, mix(top, bot, y / max(1, rect.h - 1)), (0, y), (rect.w, y))
        spot = pygame.Surface(rect.size)
        cx = (rect.w - VW * s) / 2 + ANCHOR[0] * s
        cy = (rect.h - (VH + TOP) * s) / 2 + (TOP + 400) * s
        big = int(360 * s)
        for r in range(big, 0, -3):
            k = (1 - r / big) ** 1.6 * 0.2
            pygame.draw.circle(spot, (int(70 * k), int(100 * k), int(160 * k)), (cx, cy), r)
        surf.blit(spot, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        rng = random.Random(7)
        for _ in range(50):
            x, y = rng.uniform(0, rect.w), rng.uniform(0, rect.h)
            gfx.filled_circle(surf, int(x), int(y), max(1, int(rng.uniform(2, 7) * s)),
                              (*COL['wire'], rng.randint(8, 22)))
        floor_y = int((rect.h - (VH + TOP) * s) / 2 + (TOP + ANCHOR[1] + 4) * s)
        pygame.draw.rect(surf, mix(bot, COL['wire'], 0.05), (0, floor_y, rect.w, rect.h - floor_y))
        pygame.draw.line(surf, mix(bot, COL['wire'], 0.15), (0, floor_y), (rect.w, floor_y), max(1, int(2 * s)))
        self._bg = ((rect.size, s), surf)
        return surf

    # ---------- acting: pose, face and arm from the current run ----------
    def pose(self, sim):
        """Squash, stretch and hop for the whole body."""
        now, r = sim.time, sim.run
        kx = 1 - 0.006 * math.sin(now * 2.2)     # breathing
        ky = 1 + 0.012 * math.sin(now * 2.2)
        hop = 0.0
        if r:
            if r.t < 0.4:                        # gulp: a little nod as the food goes down
                g = math.sin(r.t / 0.4 * math.pi)
                ky -= 0.025 * g
                kx += 0.015 * g
            if r.cat == 'burp':
                if r.fired:                      # springy stretch as the burp comes out
                    d = r.t - r.tf
                    sp = math.exp(-d * 4.5) * math.sin(d * 16)
                    ky += 0.09 * sp
                    kx -= 0.05 * sp
                else:                            # puffing up with gas
                    pr = sim.pressure()
                    kx += 0.035 * pr
                    ky += 0.02 * pr
            elif r.cat == 'fart':
                if r.fired:                      # the fart launches the body into a hop
                    d = r.t - r.tf
                    if d < 0.5:
                        q = d / 0.5
                        hop = 170 * q * (1 - q)
                        ky += 0.06 * math.sin(q * math.pi)
                        kx -= 0.04 * math.sin(q * math.pi)
                    else:                        # squash on landing, then wobble to rest
                        e = d - 0.5
                        sp = math.exp(-e * 6) * math.cos(e * 22)
                        ky -= 0.1 * sp
                        kx += 0.07 * sp
                elif r.arrived:                  # clenching and trembling
                    g = sim.gas()
                    kx += 0.012 * g * math.sin(now * 46)
                    ky -= 0.025 * g
            elif r.fired:                        # two happy bounces
                d = r.t - r.tf
                if d < 0.8:
                    hop = 22 * abs(math.sin(d / 0.4 * math.pi))
        self.kx, self.ky, self.hop = kx, ky, hop

    def face(self, sim):
        """Expression for the current moment."""
        now, r = sim.time, sim.run
        f = {'eyes': 'open', 'mouth': 'smile', 'raise': 0.0, 'worry': 0.0, 'puff': 0.0, 'sweat': False,
             'blush': 0.35, 'look': (480, 300)}
        if r:
            L = r.path.length
            lead_d = min(1.0, r.t / r.D) * L
            if not r.arrived:
                x, y, _ = r.path.at(lead_d)
                f['look'] = (x, y + 40)
            if r.t < 0.45:
                f['mouth'] = 'open' if int(r.t * 9) % 2 == 0 else 'smile'
            if r.cat == 'burp' and r.arrived:
                f['look'] = (STOM_CX, STOM_CY)
                if not r.fired:
                    f.update(eyes='wide', mouth='o', worry=0.3)
                    f['raise'] = sim.pressure()
                    f['puff'] = smoothstep(r.tr + r.wait - 0.7, r.tr + r.wait, r.t)
                elif r.t - r.tf < 0.7:
                    f.update(eyes='squeeze', mouth='wide', blush=0.7)
                    f['puff'] = clamp01(1 - (r.t - r.tf) / 0.2)
                else:
                    f.update(eyes='happy', mouth='smile', blush=0.6)
            elif r.cat == 'fart':
                if r.fired:
                    f.update(eyes='squeeze' if r.t - r.tf < 0.8 else 'happy', mouth='grin', blush=0.9)
                elif r.arrived:
                    g = sim.gas()
                    f.update(eyes='open', mouth='wavy', worry=1.0, sweat=True, blush=0.35 + 0.5 * g,
                             look=(250, 640))
                elif lead_d >= BRANCH_D:
                    f.update(mouth='o', worry=0.7, look=(280, 420))
            elif r.cat == 'smooth' and r.arrived:
                f.update(eyes='happy', mouth='grin' if r.fired else 'smile', blush=0.6)
        if f['eyes'] == 'open' and (now % 3.7) < 0.13:
            f['eyes'] = 'blink'
        return f

    def arm_target(self, sim):
        now, r = sim.time, sim.run
        if not r:
            return -0.4, -1.3 + 0.35 * math.sin(now * 5)          # waving at the player
        if r.fired and (r.cat == 'smooth' or (r.cat == 'fart' and r.t - r.tf > 0.6)):
            return -0.5, -1.4 + 0.55 * math.sin(now * 11)          # celebrating
        if r.cat == 'fart' and r.arrived and not r.fired:
            return 1.15 + 0.06 * math.sin(now * 8), 0.3 + 0.3 * math.sin(now * 8)   # rubbing the belly
        return 1.15, 0.28                                         # hand resting on the belly

    # ---------- body parts ----------
    def draw_legs(self, surf):
        for (hip, ankle), skin in zip(LEGS, (TOON['skin_far'], TOON['skin'])):
            self.stroke(surf, [hip, ankle], TOON['ink'], LEG_W + 7)
            self.stroke(surf, [hip, ankle], skin, LEG_W)
            sx, sy = ankle[0] + 14, ankle[1] + 12
            self.oval(surf, sx, sy, 31, 16, TOON['shoe'], w=3)
            self.oval(surf, sx + 10, sy - 6, 7, 3, TOON['lace'], ol=None)

    def draw_arm(self, surf, dt, sim):
        tgt = self.arm_target(sim)
        k = 1 - math.exp(-dt * 9)
        self.arm = [a + (b - a) * k for a, b in zip(self.arm, tgt)]
        a1, a2 = self.arm
        ex, ey = SHOULDER[0] + math.cos(a1) * ARM_UPPER, SHOULDER[1] + math.sin(a1) * ARM_UPPER
        hx, hy = ex + math.cos(a2) * ARM_FORE, ey + math.sin(a2) * ARM_FORE
        pts = [SHOULDER, (ex, ey), (hx, hy)]
        self.stroke(surf, pts, TOON['ink'], 27)
        self.stroke(surf, pts, TOON['skin'], 20)
        self.disc(surf, hx, hy, 13, TOON['skin'], w=3)
        self.disc(surf, hx + math.cos(a2 - 1.6) * 11, hy + math.sin(a2 - 1.6) * 11, 5, TOON['skin'], w=2.5)

    def draw_head(self, surf):
        skin = TOON['skin']
        for x, y in HAIR:
            self.disc(surf, x, y + 8, 13, TOON['hair'], w=3)
        self.shape(surf, HEAD, skin, w=3.5)
        self.stroke(surf, HEAD_SHINE, TOON['shine'], 5)
        self.oval(surf, *EAR, 13, 17, skin, w=3)
        self.stroke(surf, chaikin([(EAR[0] + 4, EAR[1] - 8), (EAR[0] - 3, EAR[1]), (EAR[0] + 4, EAR[1] + 8)], 2),
                    TOON['skin_far'], 3)

    def draw_face(self, surf, f, now):
        ink, skin = TOON['ink'], TOON['skin']
        # eyes: near eye then the far one (three-quarter view)
        lx, ly = f['look']
        for i, (x, y, rx, ry) in enumerate(EYES):
            e = f['eyes']
            if e in ('open', 'wide'):
                m = 1.18 if e == 'wide' else 1.0
                self.oval(surf, x, y, rx * m, ry * m, TOON['white'], w=2.5)
                dx, dy = lx - x, ly - y
                d = math.hypot(dx, dy) or 1.0
                pr = rx * (0.42 if e == 'wide' else 0.56)
                px, py = x + dx / d * (rx * m - pr - 1), y + dy / d * (ry * m - pr - 2)
                self.disc(surf, px, py, pr, ink, ol=None)
                self.disc(surf, px - pr * 0.35, py - pr * 0.4, max(1.2, pr * 0.32), TOON['white'], ol=None)
            elif e == 'blink':
                self.stroke(surf, chaikin([(x - rx, y), (x, y + 4), (x + rx, y)], 2), ink, 3)
            elif e == 'squeeze':
                sgn = 1 if i == 0 else -1
                self.stroke(surf, [(x - rx * sgn, y - ry * 0.55), (x + rx * 0.6 * sgn, y), (x - rx * sgn, y + ry * 0.55)],
                            ink, 3.5)
            else:   # happy
                self.stroke(surf, chaikin([(x - rx, y + ry * 0.3), (x, y - ry * 0.55), (x + rx, y + ry * 0.3)], 2),
                            ink, 3.5)
            # eyebrows: raised with surprise, tilted when worried
            by = y - ry - 8 - f['raise'] * 6
            w = f['worry'] * 5
            self.stroke(surf, chaikin([(x - rx, by + w), (x, by - 3 - w * 0.2), (x + rx, by - w)], 2), ink, 3.5)

        self.oval(surf, *NOSE, 10, 9, skin, w=3)
        bl = TOON['blush']
        cx, cy = CHEEK
        if f['puff'] > 0:   # cheeks balloon out before a burp
            p = f['puff']
            self.disc(surf, cx + 9 * p, cy + 4, 9 + 22 * p, skin, w=3)
            bl = mix(bl, (255, 80, 120), p)
        self.oval(surf, cx + 9 * f['puff'], cy + 4, 9 + 9 * f['puff'], 5 + 6 * f['puff'],
                  (*bl, int(255 * clamp01(f['blush']))), ol=None)

        m = f['mouth']
        if m == 'smile':
            self.stroke(surf, SMILE, ink, 3.5)
        elif m == 'open':
            self.oval(surf, 384, 148, 7, 5, TOON['mouth'], w=2.5)
        elif m == 'o':
            self.oval(surf, 390, 149, 4, 5 + math.sin(now * 20), TOON['mouth'], w=2.5)
        elif m == 'wide':
            self.oval(surf, 383, 152, 12, 15, TOON['mouth'], w=3)
            self.oval(surf, 383, 160, 7, 4, TOON['tongue'], ol=None)
        elif m == 'grin':
            self.shape(surf, GRIN, TOON['mouth'], w=3)
            self.stroke(surf, [(368, 142), (393, 144)], TOON['white'], 3)
            self.oval(surf, 381, 153, 6, 3, TOON['tongue'], ol=None)
        else:   # wavy: nervous
            self.stroke(surf, [(368 + i * 3, 147 + 2.5 * math.sin(i * 1.7 + now * 9)) for i in range(9)], ink, 3)

        if f['sweat']:
            y = 34 + (now * 28) % 24
            x = 400
            drop = [(x, y - 11)] + [(x + math.cos(a) * 5.5, y + math.sin(a) * 5.5)
                                    for a in (-0.25 + i / 10 * (math.pi + 0.5) for i in range(11))]
            self.shape(surf, drop, TOON['sweat'], w=2)

    def draw_stomach(self, surf, sim, now):
        run = sim.run
        cat = run.cat if run else None
        pr = sim.pressure()
        imp = math.exp(-(run.t - run.tr) * 3.5) if run and run.arrived and cat != 'fart' else 0.0
        sc = 1 + 0.22 * pr
        jig = 0.012 + (0.05 * pr if run and not run.fired else 0) + 0.08 * imp   # jelly wobble
        pts = []
        for x, y in STOMACH:
            a = math.atan2(y - STOM_CY, x - STOM_CX)
            k = sc * (1 + jig * math.sin(3 * a + now * 9))
            pts.append((STOM_CX + (x - STOM_CX) * k, STOM_CY + (y - STOM_CY) * k))
        fill = TOON['stomach']
        if cat == 'burp' and run.arrived:
            fill = mix(fill, COL['burp'], 0.2 + 0.3 * pr)
        elif cat == 'smooth' and run.arrived:
            g = clamp01(1 - (run.t - run.tf)) if run.fired else clamp01((run.t - run.D) / 1.5)
            fill = mix(fill, COL['smooth'], 0.45 * g)
        outline = self.shape(surf, pts, fill, w=3)

        def at(x, y):
            return STOM_CX + (x - STOM_CX) * sc, STOM_CY + (y - STOM_CY) * sc
        self.oval(surf, *at(322, 340), 7, 4, (*TOON['white'], 150), ol=None)

        # the stomach's own little face
        eyes, mouth, look = 'open', 'smile', (0, 1)
        if cat == 'burp' and run.arrived:
            eyes, mouth = ('squeeze', 'o') if run.fired else ('wide', 'o')
        elif cat == 'smooth' and run.arrived:
            eyes = 'happy'
        elif cat == 'fart' and run.t / run.D * run.path.length >= BRANCH_D and not run.fired:
            eyes, mouth, look = 'wide', 'o', (-1, -0.3)   # watching the food skip past
        for i, ex in enumerate((334, 354)):
            x, y = at(ex, 360)
            if eyes == 'squeeze':
                sgn = 1 if i == 0 else -1
                self.stroke(surf, [(x - 4 * sgn, y - 3), (x + 3 * sgn, y), (x - 4 * sgn, y + 3)], TOON['ink'], 2.5)
            elif eyes == 'happy':
                self.stroke(surf, [(x - 4, y + 1), (x, y - 3), (x + 4, y + 1)], TOON['ink'], 2.5)
            else:
                r = 4.5 + (3 * pr if eyes == 'wide' and cat == 'burp' else 1 if eyes == 'wide' else 0)
                self.disc(surf, x, y, r, TOON['white'], w=1.8)
                self.disc(surf, x + look[0] * r * 0.4, y + look[1] * r * 0.4, r * 0.5, TOON['ink'], ol=None)
        x, y = at(344, 373)
        if mouth == 'o':
            self.oval(surf, x, y, 3 + 2 * pr, 4 + 2 * pr, TOON['mouth'], w=1.8)
        else:
            self.stroke(surf, chaikin([(x - 6, y - 1), (x, y + 3), (x + 6, y - 1)], 2), TOON['ink'], 2.5)

        stom_right = max(p[0] for p in pts)

        # bubbles, clipped to the stomach's real shape with a mask
        if sim.bubbles:
            xs, ys = [p[0] for p in outline], [p[1] for p in outline]
            box = pygame.Rect(int(min(xs)) - 2, int(min(ys)) - 2, int(max(xs) - min(xs)) + 5,
                              int(max(ys) - min(ys)) + 5)
            layer = pygame.Surface(box.size, pygame.SRCALPHA)
            for b in sim.bubbles:
                a = clamp01(1 - (b['r'] - b['max']) / (b['max'] * 1.2)) if b['popping'] else 1.0
                X, Y = self.Pi(b['x'], b['y'])
                X, Y = X - box.x, Y - box.y
                rr = self.R(b['r'])
                if not b['popping']:
                    gfx.filled_circle(layer, X, Y, rr, (*mix(COL['burp'], (255, 255, 255), 0.55), 170))
                gfx.aacircle(layer, X, Y, rr, (*TOON['ink'], int(200 * a)))
                if rr > 3 and not b['popping']:
                    gfx.filled_circle(layer, X - rr // 3, Y - rr // 3, max(1, rr // 4), (255, 255, 255, 220))
            mask = pygame.Surface(box.size, pygame.SRCALPHA)
            gfx.filled_polygon(mask, [(x - box.x, y - box.y) for x, y in outline], (255, 255, 255, 255))
            layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(layer, box)
        return stom_right

    def draw_puffs(self, surf, sim, now):
        s = self.s
        for p in sim.puffs:
            a = clamp01(p['life'] / p['max'])
            X, Y = self.Pi(p['x'], p['y'])
            kind = p['kind']
            if kind == 'star':
                pts = [self.P(*q) for q in star_points(p['x'], p['y'], 12 * (0.5 + 0.5 * a), now * 4 + p['vx'])]
                gfx.filled_polygon(surf, pts, (*COL['smooth'], int(255 * a)))
                gfx.aapolygon(surf, pts, (*TOON['ink'], int(255 * a)))
            elif kind == 'heart':
                pts = [self.P(*q) for q in heart_points(p['x'], p['y'], 12 * (0.6 + 0.4 * a))]
                gfx.filled_polygon(surf, pts, (*TOON['heart'], int(255 * a)))
                gfx.aapolygon(surf, pts, (*TOON['ink'], int(255 * a)))
            elif kind == 'ring':
                rr = self.R(p['r'])
                gfx.filled_circle(surf, X, Y, rr, (*mix(COL['burp'], (255, 255, 255), 0.5), int(70 * a)))
                gfx.aacircle(surf, X, Y, rr, (*COL['burp'], int(255 * a)))
                gfx.filled_circle(surf, X - rr // 3, Y - rr // 3, max(1, rr // 5), (255, 255, 255, int(230 * a)))
            else:   # puffy cartoon cloud: three overlapping lumps
                r = p['r'] * s
                for dx, dy, k in ((-0.6, 0.15, 0.7), (0.6, 0.2, 0.75), (0, -0.2, 1.0)):
                    cx, cy, rr = int(X + dx * r), int(Y + dy * r), max(1, int(r * k))
                    gfx.filled_circle(surf, cx, cy, rr, (*TOON['cloud'], int(120 * a)))
                    gfx.aacircle(surf, cx, cy, rr, (*TOON['cloud_ink'], int(230 * a)))

    # ---------- frame ----------
    def draw(self, surf, rect, sim, mystery=False, shake_enabled=True):
        s = min(rect.w / VW, rect.h / (VH + TOP))
        sk = sim.shake_amp * (sim.shake_t / sim.shake_dur) if shake_enabled and sim.shake_t > 0 else 0
        self.s = s
        base_x = rect.x + (rect.w - VW * s) / 2
        base_y = rect.y + (rect.h - (VH + TOP) * s) / 2 + TOP * s
        self.ox = base_x + (random.random() - .5) * 2 * sk * s
        self.oy = base_y + (random.random() - .5) * 2 * sk * s
        now, run = sim.time, sim.run
        dt = 0.0 if self._last is None else max(0.0, min(0.1, now - self._last))
        self._last = now
        cat = run.cat if run else None
        prev_clip = surf.get_clip()
        surf.set_clip(rect)
        surf.blit(self.backdrop(rect, s), rect)
        self.pose(sim)
        face = self.face(sim)

        # shadow on the floor: shrinks while the body is in the air
        self.xf = False
        k = 1 - min(0.6, self.hop / 120)
        X, Y = self.Pi(ANCHOR[0] + 8, ANCHOR[1] + 2)
        gfx.filled_ellipse(surf, X, Y, max(2, int(78 * k * s)), max(1, int(9 * k * s)), (0, 0, 0, 110))
        self.xf = True

        # body
        self.draw_legs(surf)
        self.shape(surf, TORSO, TOON['skin'], w=3.5)
        self.stroke(surf, BELLY_SHINE, TOON['shine'], 5)
        self.draw_head(surf)   # the face goes on last, so the esophagus shows inside the head

        # digestive tract: large intestine, small intestine, esophagus, stomach
        gas = sim.gas()
        lead_d = min(1.0, run.t / run.D) * run.path.length if run else 0
        self.colon(surf, mix(TOON['large'], TOON['cloud'], 0.8 * gas), 13 + gas * 7, 3 + gas * 1.5)
        self.tube(surf, P_SI, TOON['small'], 9)
        self.tube(surf, P_ESO, TOON['eso'], 11)
        if cat == 'fart' and lead_d >= BRANCH_D:
            self.dashed(surf, COL['fart'], P_BYPASS.pts, 6, 6, offset=now * 30, width=max(3, int(4 * s)))
            self.label(surf, 'express', 200, 345, 293, 355, 'right')
        if run and not run.arrived:   # gulp: the esophagus bulges round the food
            limit = BRANCH_D if cat == 'fart' else P_ESO.length
            for back in (4, 12):
                if 0 < lead_d - back < limit:
                    x, y, _ = run.path.at(lead_d - back)
                    self.disc(surf, x, y, 9, TOON['eso'], w=2.5)
        stom_right = self.draw_stomach(surf, sim, now)

        self.label(surf, 'eso', 226, 240, 329, 240, 'right')
        self.label(surf, 'stomach', 500, 352, stom_right + 2, 372)
        self.label(surf, 'small', 500, 470, 390, 472)
        self.label(surf, 'large', 500, 586, 410, 530)

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
                                      0.3 if tr else 1.0)
                    continue
                since = lt - run.D
                if cat == 'burp':
                    if since < 0.25:
                        self.particle(surf, STOM_CX + p.ox * .6, STOM_CY + p.oy * .6, p.r, COL['burp'],
                                      1 if since < 0.12 else 0.6)
                elif cat == 'smooth':
                    q = since / DISSOLVE
                    if q < 1:
                        b = smoothstep(0, 0.3, since)
                        self.particle(surf, STOM_CX + p.ox * b + math.cos(now * 2 + p.ph) * 4 * b,
                                      STOM_CY + p.oy * b + math.sin(now * 2 + p.ph) * 3 * b,
                                      p.r * (1 - q * 0.7), COL['smooth'], 1 if q < 0.6 else 0.5)
                elif not run.fired:
                    ex, ey, _ = run.path.at(L)
                    self.particle(surf, ex + p.ox * 0.2 + math.sin(now * 9 + p.ph) * 1.5, ey + p.oy * 0.25, p.r,
                                  COL['fart'])

            # gas lumps building up in the rectum
            if cat == 'fart' and run.arrived and not run.fired:
                for i in range(6):
                    a = i / 6 * math.tau + now * 1.5
                    r = 4 + gas * 8 + math.sin(now * 6 + i) * 1.5
                    self.disc(surf, 286 + math.cos(a) * gas * 9, 595 + math.sin(a) * gas * 7, r, TOON['cloud'],
                              ol=TOON['cloud_ink'], w=1.5)

        self.draw_arm(surf, dt, sim)
        self.draw_face(surf, face, now)

        # effects that fly free of the body
        self.xf = False
        self.draw_puffs(surf, sim, now)
        for e in sim.fx:
            self.burst(surf, e, now)
        self.xf = True
        surf.set_clip(prev_clip)
