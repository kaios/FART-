"""Every sound is synthesized in Python at startup: no audio files.

Synthesis runs on a background thread so the window opens immediately; sounds
requested before they are ready are simply skipped.
"""
import math
import random
import threading
from array import array

import pygame

SR = 22050
_sounds = {}
_ready = False
_enabled = False
_volume = 0.7
_muted = False
_channels = 1


# ---------- tiny DSP toolkit ----------
def _env(n, peak, atk, hold, rel):
    """Attack / hold / exponential release envelope, times in seconds."""
    a, h, r = int(atk * SR), int(hold * SR), int(rel * SR)
    out = array('f', [0.0]) * n
    for i in range(n):
        if i < a:
            v = peak * i / max(1, a)
        elif i < a + h:
            v = peak
        elif i < a + h + r:
            v = peak * math.exp(-5.0 * (i - a - h) / max(1, r))
        else:
            v = 0.0
        out[i] = v
    return out


def _biquad(x, kind, f0, q):
    """RBJ cookbook biquad filter: 'lp', 'hp' or 'bp'."""
    w = 2 * math.pi * f0 / SR
    cw, sw = math.cos(w), math.sin(w)
    alpha = sw / (2 * q)
    if kind == 'lp':
        b0, b1, b2 = (1 - cw) / 2, 1 - cw, (1 - cw) / 2
    elif kind == 'hp':
        b0, b1, b2 = (1 + cw) / 2, -(1 + cw), (1 + cw) / 2
    else:
        b0, b1, b2 = alpha, 0.0, -alpha
    a0, a1, a2 = 1 + alpha, -2 * cw, 1 - alpha
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    y = array('f', [0.0]) * len(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, xi in enumerate(x):
        yi = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, xi, y1, yi
        y[i] = yi
    return y


def _osc(kind, freq_at, n):
    """Oscillator whose frequency is freq_at(t) Hz; kind: sine, saw, square, tri."""
    out = array('f', [0.0]) * n
    ph = 0.0
    for i in range(n):
        ph = (ph + freq_at(i / SR) / SR) % 1.0
        if kind == 'sine':
            v = math.sin(2 * math.pi * ph)
        elif kind == 'saw':
            v = 2 * ph - 1
        elif kind == 'square':
            v = 1.0 if ph < 0.5 else -1.0
        else:
            v = 4 * abs(ph - 0.5) - 1
        out[i] = v
    return out


def _noise(n):
    return array('f', (random.uniform(-1, 1) for _ in range(n)))


def _mix(*layers):
    n = max(len(l) for l in layers)
    out = array('f', [0.0]) * n
    for l in layers:
        for i, v in enumerate(l):
            out[i] += v
    return out


def _mul(a, b):
    return array('f', (x * y for x, y in zip(a, b)))


def _tone(kind, f0, f1, dur, vol, delay=0.0):
    n = int((dur + delay + 0.05) * SR)
    d = int(delay * SR)
    ratio = f1 / f0
    wave = _osc(kind, lambda t: f0 * ratio ** min(1.0, max(0.0, t - delay) / dur), n)
    env = array('f', [0.0]) * d + _env(n - d, vol, 0.01, dur * 0.3, dur * 0.7)
    return _mul(wave, env)


# ---------- the sounds ----------
# Burps and farts are physical models, not tones:
#   * an excitation of irregular air puffs (a pulse train with random timing and loudness),
#   * shaped by resonances (throat and mouth for burps, body cavity for farts),
#   * plus turbulent breath noise that rides on each puff.
# The irregularity is what makes them sound real; perfectly periodic pulses sound like a synth.

def _wander(dur, rate, rng, depth):
    """Smooth random drift: a list of control points read by _ctl()."""
    n = max(2, int(dur * rate) + 2)
    return [1 + depth * rng.uniform(-1, 1) for _ in range(n)], rate


def _ctl(w, t):
    pts, rate = w
    x = min(len(pts) - 1.001, t * rate)
    i = int(x)
    k = x - i
    k = k * k * (3 - 2 * k)
    return pts[i] + (pts[i + 1] - pts[i]) * k


def _contour(points, x):
    """Piecewise-linear lookup in [(x, value), ...] with x in 0..1."""
    for (x0, v0), (x1, v1) in zip(points, points[1:]):
        if x <= x1:
            return v0 + (v1 - v0) * (x - x0) / ((x1 - x0) or 1)
    return points[-1][1]


def _puffs(n, dur, f0_at, amp_at, rng, jitter, shimmer, open_q, breath, alt=0.0, gate=None, crackle=0.0):
    """Irregular puff train. Each puff is a raised-cosine bump of air plus breath noise inside it."""
    exc = array('f', [0.0]) * n
    t, k = 0.0, 0
    while True:
        i0 = int(t * SR)
        if i0 >= n:
            break
        x = t / dur
        f0 = max(18.0, f0_at(x, t))
        period = (1.0 / f0) * (1 + jitter * rng.uniform(-1, 1))
        a = amp_at(x) * (1 + shimmer * rng.uniform(-1, 1)) * (1 - alt if k % 2 else 1)
        if a > 0.002 and (gate is None or gate(x)):
            w = max(3, int(period * open_q * SR))
            for j in range(w):
                ii = i0 + j
                if ii >= n:
                    break
                bump = 0.5 - 0.5 * math.cos(2 * math.pi * j / w)
                exc[ii] += a * bump * ((1 - breath) + breath * rng.uniform(-1, 1) * 1.7)
            if crackle and rng.random() < crackle:   # wet pop: a tiny decaying noise click
                cl = int(rng.uniform(0.002, 0.006) * SR)
                ca = a * rng.uniform(0.6, 1.4)
                for j in range(cl):
                    if i0 + j < n:
                        exc[i0 + j] += ca * rng.uniform(-1, 1) * math.exp(-5 * j / cl)
        t += max(period, 1.0 / 400)
        k += 1
    return exc


def _reson(x, freq_at, bw, gain=1.0, block=64):
    """Band-pass resonator with a constant peak gain whose centre can glide over time (freq_at(x in 0..1))."""
    n = len(x)
    y = array('f', [0.0]) * n
    x1 = x2 = y1 = y2 = 0.0
    for blk in range(0, n, block):
        f = freq_at(blk / n)
        w = 2 * math.pi * f / SR
        alpha = math.sin(w) / (2 * max(0.5, f / bw))
        a0 = 1 + alpha
        b0 = alpha / a0 * gain
        a1 = -2 * math.cos(w) / a0
        a2 = (1 - alpha) / a0
        for i in range(blk, min(n, blk + block)):
            xi = x[i]
            yi = b0 * (xi - x2) - a1 * y1 - a2 * y2
            x2, x1, y2, y1 = x1, xi, y1, yi
            y[i] = yi
    return y


def _normalize(x, peak):
    m = max((abs(v) for v in x), default=0) or 1.0
    k = peak / m
    return array('f', (v * k for v in x))


def _fade(x, fin=0.005, fout=0.04):
    n = len(x)
    a, b = max(1, int(fin * SR)), max(1, int(fout * SR))
    for i in range(min(a, n)):
        x[i] *= i / a
    for i in range(min(b, n)):
        x[n - 1 - i] *= i / b
    return x


BURPS = {
    # f0: pitch contour in Hz over the burp; formants: (start Hz, end Hz, bandwidth, gain) for the throat/mouth;
    # jitter/shimmer: irregularity; alt: alternating-pulse rattle; breath: noise share; reps: separate burps
    'soda':      dict(dur=0.95, f0=[(0, 62), (.15, 78), (.6, 70), (1, 52)], jitter=.14, shimmer=.35, alt=.35,
                      breath=.18, formants=[(640, 420, 110, 1.0), (1150, 820, 160, .55), (2500, 2300, 260, .18)],
                      seed=11, reps=1, peak=.9),
    'sparkling': dict(dur=0.42, f0=[(0, 88), (.3, 104), (1, 80)], jitter=.12, shimmer=.3, alt=.25,
                      breath=.22, formants=[(720, 560, 120, 1.0), (1300, 1050, 170, .5), (2600, 2500, 280, .2)],
                      seed=12, reps=1, peak=.85),
    'ramune':    dict(dur=0.3, f0=[(0, 110), (.4, 128), (1, 96)], jitter=.12, shimmer=.3, alt=.2,
                      breath=.25, formants=[(780, 600, 130, 1.0), (1450, 1150, 180, .5), (2800, 2600, 300, .22)],
                      seed=13, reps=2, peak=.8),
    'kombucha':  dict(dur=1.4, f0=[(0, 50), (.2, 60), (.5, 46), (.8, 52), (1, 40)], jitter=.2, shimmer=.45,
                      alt=.45, breath=.15, formants=[(560, 380, 100, 1.0), (980, 720, 150, .6), (2300, 2200, 240, .15)],
                      seed=14, reps=1, peak=.95),
}

FARTS = {
    # f0: puff rate contour (Hz); res: body resonances (Hz, bandwidth, gain); breath: noise share inside puffs;
    # open_q: how long the valve stays open per puff; gate: audible spans for sputters; crackle: wet pops per puff
    'beans':       dict(dur=1.25, f0=[(0, 70), (.1, 95), (.5, 82), (.85, 105), (1, 150)], jitter=.22, shimmer=.4,
                        open_q=.45, breath=.35, res=[(170, 110, 1.0), (420, 220, .55), (1100, 500, .18)],
                        gate=None, crackle=0.0, seed=21, peak=.9, wander=.18),
    'broccoli':    dict(dur=0.8, f0=[(0, 210), (.3, 260), (.7, 230), (1, 320)], jitter=.12, shimmer=.3,
                        open_q=.35, breath=.25, res=[(320, 160, 1.0), (850, 300, .6), (1900, 600, .2)],
                        gate=None, crackle=0.0, seed=22, peak=.8, wander=.12),
    'sweetpotato': dict(dur=1.75, f0=[(0, 58), (.1, 72), (.7, 68), (.9, 80), (1, 110)], jitter=.08, shimmer=.18,
                        open_q=.55, breath=.15, res=[(140, 80, 1.0), (360, 160, .7), (900, 380, .25)],
                        gate=None, crackle=0.0, seed=23, peak=.95, wander=.08),
    'cabbage':     dict(dur=1.35, f0=[(0, 60), (.5, 75), (1, 95)], jitter=.35, shimmer=.55,
                        open_q=.6, breath=.55, res=[(150, 140, 1.0), (380, 300, .6), (1000, 600, .3)],
                        gate=[(0, .14), (.2, .3), (.37, .47), (.55, .62), (.7, .83), (.9, 1)], crackle=.35,
                        seed=24, peak=.9, wander=.25),
    'onion':       dict(dur=2.0, f0=[(0, 140), (.5, 160), (1, 190)], jitter=.6, shimmer=.7,
                        open_q=.9, breath=.95, res=[(300, 400, 1.0), (900, 900, .7), (2600, 1800, .5)],
                        gate=None, crackle=0.0, seed=25, peak=.3, wander=.3),   # silent but deadly: mostly hiss
}


def _burp(dur, f0, jitter, shimmer, alt, breath, formants, seed, reps, peak):
    rng = random.Random(seed)
    out = array('f')
    for r in range(reps):
        n = int(dur * SR)
        drift = _wander(dur, 9, rng, 0.12)
        low = 1 - 0.1 * r   # a repeat burp comes out a little lower

        def f0_at(x, t, low=low, drift=drift):
            return _contour(f0, x) * _ctl(drift, t) * low

        def amp_at(x):   # sphincter opens fast, pressure sags, then lets go
            return min(1.0, x / 0.06) * (1 - 0.35 * x) * (1 if x < 0.85 else (1 - x) / 0.15)
        exc = _puffs(n, dur, f0_at, amp_at, rng, jitter, shimmer, 0.5, breath, alt=alt)
        voiced = array('f', [0.0]) * n
        for fs, fe, bw, g in formants:   # mouth closes a little through the burp: formants glide down
            band = _reson(exc, lambda x, fs=fs, fe=fe: fs + (fe - fs) * x, bw, g)
            for i, v in enumerate(band):
                voiced[i] += v
        chest = _reson(exc, lambda x: 160, 120, 0.3)   # low chest/oesophagus body
        seg = _mix(voiced, chest)
        seg = _biquad(seg, 'hp', 45, 0.7)
        out += _fade(_normalize(seg, peak))
        if r < reps - 1:
            out += array('f', [0.0]) * int(0.09 * SR)
    return out


def _fart(dur, f0, jitter, shimmer, open_q, breath, res, gate, crackle, seed, peak, wander):
    rng = random.Random(seed)
    n = int(dur * SR)
    drift = _wander(dur, 7, rng, wander)

    def f0_at(x, t):
        return _contour(f0, x) * _ctl(drift, t)

    def amp_at(x):   # pressure builds instantly, then bleeds off; last bit tapers as the valve tightens
        return min(1.0, x / 0.03) * (0.55 + 0.45 * (1 - x)) * (1 if x < 0.88 else max(0.0, (1 - x) / 0.12))

    def gate_at(x):
        return any(a <= x < b for a, b in gate)
    exc = _puffs(n, dur, f0_at, amp_at, rng, jitter, shimmer, open_q, breath,
                 gate=gate_at if gate else None, crackle=crackle)
    body = array('f', [0.0]) * n
    for fr, bw, g in res:
        band = _reson(exc, lambda x, fr=fr: fr, bw, g)
        for i, v in enumerate(band):
            body[i] += v
    # a little of the raw puff gives the "flappy" edge; clothes and air soften the top end
    out = _mix(body, array('f', (v * 0.05 for v in exc)))
    out = _biquad(_biquad(_biquad(out, 'lp', 1600, 0.7), 'lp', 2200, 0.7), 'hp', 35, 0.7)
    return _fade(_normalize(out, peak), 0.003, 0.05)


def _fizz():
    n = int(2.0 * SR)
    hiss = _biquad(_noise(n), 'hp', 5000 if SR > 12000 else 3000, 0.7)
    trem = array('f', (0.6 + 0.4 * math.sin(2 * math.pi * 23 * i / SR) for i in range(n)))
    return _mul(_mul(hiss, _env(n, 0.12, 0.3, 1.2, 0.5)), trem)


def _rumble():
    n = int(0.7 * SR)
    low = _mul(_biquad(_noise(n), 'lp', 140, 0.7), _env(n, 0.9, 0.15, 0.2, 0.3))
    return _mix(low, _tone('sine', 55, 42, 0.5, 0.15))


def _build_all():
    return {
        'click': _tone('square', 660, 520, 0.06, 0.08),
        'gulp': _mix(_tone('sine', 320, 110, 0.22, 0.35), _tone('sine', 260, 90, 0.18, 0.25, 0.16)),
        'ok': _mix(_tone('tri', 660, 660, 0.1, 0.25), _tone('tri', 990, 990, 0.16, 0.25, 0.09)),
        'bad': _tone('saw', 220, 140, 0.25, 0.12),
        'unlock': _mix(*(_tone('square', f, f, 0.12, 0.08, i * 0.07) for i, f in enumerate((784, 988, 1175, 1568)))),
        'chime': _mix(*(_tone('tri', f, f, 0.35, 0.2, i * 0.09) for i, f in enumerate((523, 659, 784, 1047)))),
        'tick': _tone('square', 1200, 1200, 0.03, 0.05),
        'gameover': _mix(*(_tone('tri', f, f * 0.98, 0.3, 0.2, i * 0.14) for i, f in enumerate((523, 440, 349, 262)))),
        **{f'burp_{k}': _burp(**v) for k, v in BURPS.items()},
        **{f'fart_{k}': _fart(**v) for k, v in FARTS.items()},
        'fizz': _fizz(),
        'rumble': _rumble(),
    }


def _to_sound(samples):
    pcm = array('h', (int(max(-1.0, min(1.0, v)) * 32000) for v in samples))
    if _channels == 2:
        st = array('h', [0]) * (len(pcm) * 2)
        st[0::2] = pcm
        st[1::2] = pcm
        pcm = st
    return pygame.mixer.Sound(buffer=pcm.tobytes())


def _worker():
    global _ready
    try:
        built = _build_all()
        for k, v in built.items():
            _sounds[k] = _to_sound(v)
        _ready = True
    except Exception:  # audio is optional; the game runs silently without it
        pass


def init():
    """Call before pygame.init(). Starts background synthesis."""
    global _enabled, _channels
    try:
        pygame.mixer.pre_init(SR, -16, 1, 512)
        pygame.mixer.init()
        info = pygame.mixer.get_init()
        if not info:
            return
        _channels = info[2]
        if info[0] != SR:  # device forced another rate; resample is not worth it, stay silent
            pygame.mixer.quit()
            pygame.mixer.init(SR, -16, _channels, 512)
            info = pygame.mixer.get_init()
            if not info or info[0] != SR:
                return
        pygame.mixer.set_num_channels(16)
        _enabled = True
        threading.Thread(target=_worker, daemon=True).start()
    except pygame.error:
        _enabled = False


def configure(volume=None, muted=None):
    global _volume, _muted
    if volume is not None:
        _volume = volume
    if muted is not None:
        _muted = muted


def food_sound(food):
    """Name of the burp/fart sound for a food, or None for smooth foods."""
    return f'{food.cat}_{food.id}' if food.cat in ('burp', 'fart') else None


def play(name, fade_after=None):
    if not (_enabled and _ready) or _muted or _volume <= 0:
        return
    snd = _sounds.get(name)
    if not snd:
        return
    snd.set_volume(_volume)
    ch = snd.play()
    if ch and fade_after:
        ch.fadeout(int(fade_after * 1000))
