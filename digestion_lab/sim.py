"""Digestion simulation: particles, bubbles, gas and text bursts.

Runs on its own clock (advanced by update), so pausing simply stops calling update.
update() returns events for the controller: arrive, fire, finish, rumble.
"""
import math
import random
from dataclasses import dataclass, field

from .geometry import P_TO_STOM, P_BEANS, STOM_CX, STOM_CY, STOM_W, STOM_H, MOUTH, ANUS

N_PART = 14
STAGGER = 0.07
TRAVEL = {'burp': 2.2, 'fart': 2.8, 'smooth': 2.2}   # lead particle travel time at speed 1
TIMEOUT = {'burp': 2.0, 'fart': 4.0}                  # arrival -> explosion at speed <= 1
AFTER = {'burp': 1.6, 'fart': 2.2, 'smooth': 1.8}     # explosion -> round over
DISSOLVE = 0.9


@dataclass
class Particle:
    j: float
    r: float
    ox: float
    oy: float
    ph: float
    arrived: bool = False


@dataclass
class Run:
    food: object
    cat: str
    speed: float
    D: float
    stagger: float
    wait: float
    path: object
    parts: list
    t: float = 0.0
    arrived: bool = False
    tr: float = 0.0
    fired: bool = False
    tf: float = 0.0
    rumble_at: float = 0.0
    predicted: object = None
    outcome: str = '+0'


@dataclass
class Sim:
    time: float = 0.0
    run: Run = None
    bubbles: list = field(default_factory=list)
    puffs: list = field(default_factory=list)
    fx: list = field(default_factory=list)
    shake_t: float = 0.0
    shake_dur: float = 1.0
    shake_amp: float = 0.0

    def reset(self):
        self.run = None
        self.bubbles, self.puffs, self.fx = [], [], []
        self.shake_t = 0.0

    def start_run(self, food, speed=1.0):
        cat = food.cat
        self.run = Run(
            food=food, cat=cat, speed=speed,
            D=TRAVEL[cat] / speed,
            stagger=STAGGER / speed,
            # Timeouts never get longer than the spec's 2s / 4s, only shorter as the game speeds up.
            wait=TIMEOUT.get(cat, 0.0) / max(1.0, speed),
            path=P_BEANS if cat == 'fart' else P_TO_STOM,
            parts=[Particle(j=(random.random() - .5) * 5, r=3 + random.random() * 2,
                            ox=(random.random() - .5) * 44, oy=(random.random() - .5) * 26,
                            ph=random.random() * 6.28) for _ in range(N_PART)],
        )
        return self.run

    # --- helpers shared with the renderer ---
    def pressure(self):
        """Burp swelling 0..1, drives stomach size and cheek puff."""
        r = self.run
        if not r or r.cat != 'burp' or not r.arrived:
            return 0.0
        if r.fired:
            return max(0.0, 1 - (r.t - r.tf) / 0.25)
        return min(1.0, (r.t - r.tr) / r.wait)

    def gas(self):
        r = self.run
        if not r or r.cat != 'fart' or not r.arrived:
            return 0.0
        if r.fired:
            return max(0.0, 1 - (r.t - r.tf) / 0.6)
        return min(1.0, (r.t - r.tr) / r.wait)

    def _burst(self, key, x, y, cat, size, rot, dur):
        self.fx.append({'key': key, 'x': x, 'y': y, 'cat': cat, 'size': size, 'rot': rot, 't0': self.time,
                        'dur': dur, 'sub': self.run.outcome if self.run else ''})

    def _shake(self, amp, dur):
        self.shake_amp, self.shake_dur, self.shake_t = amp, dur, dur

    def _fire(self):
        r = self.run
        r.fired, r.tf = True, r.t
        if r.cat == 'burp':
            self._burst('burpFx', 480, 120, 'burp', 60, 0.08, 1.6)
            for _ in range(14):
                a = (random.random() - .5) * 1.2
                self.puffs.append({'x': MOUTH[0] + 4, 'y': MOUTH[1], 'vx': math.cos(a) * (90 + random.random() * 90),
                                   'vy': math.sin(a) * 90, 'r': 3, 'gr': 20 + random.random() * 20, 'life': 1.0,
                                   'max': 1.0, 'cat': 'burp', 'kind': 'ring'})
            for b in self.bubbles:
                b['popping'] = True
            self._shake(4, 0.3)
        elif r.cat == 'fart':
            self._burst('fartFx', 165, 640, 'fart', 72, -0.1, 2.0)
            for _ in range(46):
                a = math.pi * (0.6 + random.random() * 0.75)
                sp = 60 + random.random() * 190
                self.puffs.append({'x': ANUS[0], 'y': ANUS[1], 'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp * 0.8,
                                   'r': 4 + random.random() * 6, 'gr': 18 + random.random() * 30, 'life': 1.6,
                                   'max': 1.6, 'cat': 'fart', 'kind': 'cloud'})
            self._shake(14, 0.9)
        else:
            self._burst('smoothFx', 300, 270, 'smooth', 46, -0.04, 1.8)
            for _ in range(18):
                a = random.random() * math.tau
                sp = 40 + random.random() * 80
                self.puffs.append({'x': STOM_CX, 'y': STOM_CY, 'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp,
                                   'r': 2, 'gr': 0, 'life': 1.0, 'max': 1.0, 'cat': 'smooth', 'kind': 'star'})

    def update(self, dt):
        ev = []
        self.time += dt
        r = self.run
        if r:
            r.t += dt
            t = r.t
            if not r.arrived and t >= r.D:
                r.arrived, r.tr = True, t
                ev.append(('arrive', r))
            for i, p in enumerate(r.parts):
                if not p.arrived and t - i * r.stagger >= r.D:
                    p.arrived = True
                    if r.cat == 'burp':
                        self.bubbles.append({'x': STOM_CX + p.ox * .6, 'y': STOM_CY + p.oy * .6, 'r': p.r,
                                             'max': 8 + random.random() * 10, 'gr': 70, 'popping': False})
            if r.arrived and not r.fired:
                if r.cat == 'burp':
                    s = 1 + 0.3 * self.pressure()
                    w, h = STOM_W * s, STOM_H * s
                    if len(self.bubbles) < 70 and random.random() < dt * 40:
                        self.bubbles.append({'x': STOM_CX + (random.random() - .5) * (w - 12),
                                             'y': STOM_CY + h / 2 - 6 - random.random() * h * 0.3, 'r': 1,
                                             'max': 5 + random.random() * 12, 'gr': 40 + random.random() * 50,
                                             'popping': False})
                    if t >= r.tr + r.wait:
                        self._fire()
                        ev.append(('fire', r))
                elif r.cat == 'fart':
                    if t >= r.rumble_at:
                        r.rumble_at = t + 1.1
                        self._shake(1.5, 0.4)
                        ev.append(('rumble', r))
                    if t >= r.tr + r.wait:
                        self._fire()
                        ev.append(('fire', r))
                elif t >= r.D + (N_PART - 1) * r.stagger + DISSOLVE:
                    self._fire()
                    ev.append(('fire', r))
            elif r.fired and t >= r.tf + AFTER[r.cat]:
                self.run = None
                ev.append(('finish', r))

        for b in self.bubbles:
            if b['popping']:
                b['r'] += 120 * dt
                b['dead'] = b['r'] > b['max'] * 2.2
                continue
            b['r'] += b['gr'] * dt
            b['y'] -= 14 * dt
            if b['r'] >= b['max']:
                b['popping'], b['max'] = True, b['r']
        self.bubbles = [b for b in self.bubbles if not b.get('dead')]

        damp = 1 - 1.6 * dt
        for p in self.puffs:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vx'] *= damp
            p['vy'] = p['vy'] * damp - 10 * dt
            p['r'] += p['gr'] * dt
            p['life'] -= dt
        self.puffs = [p for p in self.puffs if p['life'] > 0]
        self.fx = [e for e in self.fx if self.time - e['t0'] < e['dur']]
        self.shake_t = max(0.0, self.shake_t - dt)
        return ev
