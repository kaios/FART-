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
# Each burp and fart food has its own voice. Parameters are tuned by ear, not by science.
BURPS = {
    # pitch start/end (Hz), length (s), pitch wobble (Hz, depth), loudness flutter (Hz, depth), filter, peak, repeats
    'soda':      dict(f0=115, f1=58, dur=0.85, wob=(31, 22), flut=(13, 0.22), cut=650, q=7, peak=0.55, reps=1),
    'sparkling': dict(f0=155, f1=100, dur=0.45, wob=(38, 16), flut=(19, 0.25), cut=950, q=6, peak=0.45, reps=1),
    'ramune':    dict(f0=200, f1=135, dur=0.28, wob=(44, 20), flut=(24, 0.3), cut=1300, q=5, peak=0.4, reps=2),
    'kombucha':  dict(f0=88, f1=46, dur=1.15, wob=(21, 12), flut=(8, 0.4), cut=430, q=8, peak=0.6, reps=1),
}

FARTS = {
    # base pitch, pitch slide over the sound, length, random pitch jitter, flutter, filter, noise mix/band, peak,
    # gate: list of (start, end) fractions that are audible (sputter); None = continuous
    'beans':       dict(base=95, slide=-38, dur=1.15, jit=30, flut=(27, 0.35), cut=420, q=4, noise=(0.5, 180, 1.2),
                        peak=0.6, gate=None),
    'broccoli':    dict(base=215, slide=-70, dur=0.7, jit=40, flut=(38, 0.4), cut=950, q=6, noise=(0.25, 600, 2),
                        peak=0.5, gate=None),
    'sweetpotato': dict(base=72, slide=12, dur=1.6, jit=8, flut=(17, 0.18), cut=520, q=9, noise=(0.15, 150, 1),
                        peak=0.65, gate=None),
    'cabbage':     dict(base=92, slide=-20, dur=1.25, jit=45, flut=(31, 0.5), cut=380, q=3, noise=(0.7, 220, 0.8),
                        peak=0.6, gate=[(0, .12), (.18, .27), (.34, .46), (.53, .6), (.68, .8), (.86, 1)]),
    'onion':       dict(base=58, slide=-6, dur=1.9, jit=6, flut=(9, 0.3), cut=200, q=1, noise=(1.0, 900, 0.8),
                        peak=0.28, gate=None),   # silent but deadly: mostly hiss
}


def _gate(n, spans, fade=0.012):
    """Amplitude mask that is 1 inside the (start, end) fractions and 0 between them."""
    out = array('f', [0.0]) * n
    f = max(1, int(fade * SR))
    for a, b in spans:
        i0, i1 = int(a * n), min(n, int(b * n))
        for i in range(i0, i1):
            out[i] = min(1.0, (i - i0) / f, (i1 - i) / f)
    return out


def _burp(f0, f1, dur, wob, flut, cut, q, peak, reps):
    gap = int(0.07 * SR)
    seg_n = int(dur * SR)
    out = array('f')
    for r in range(reps):
        drop = 1 - 0.08 * r   # second burp a touch lower

        def f(t, drop=drop):
            base = f0 + (f1 - f0) * min(1.0, t / dur) ** 0.8
            return max(30.0, (base + wob[1] * math.sin(2 * math.pi * wob[0] * t)) * drop)
        wave = _biquad(_osc('saw', f, seg_n), 'lp', cut, q)
        env = _env(seg_n, peak, 0.03, dur * 0.55, dur * 0.4)
        fl = array('f', (1 + flut[1] * math.sin(2 * math.pi * flut[0] * i / SR) for i in range(seg_n)))
        out += _mul(_mul(wave, env), fl)
        if r < reps - 1:
            out += array('f', [0.0]) * gap
    return out


def _fart(base, slide, dur, jit, flut, cut, q, noise, peak, gate):
    n = int((dur + 0.05) * SR)
    curve = [base + slide * i / 23 + (random.random() - .5) * jit for i in range(24)]

    def f(t):
        x = min(len(curve) - 1.001, t / dur * (len(curve) - 1))
        i = int(x)
        return max(25.0, curve[i] + (curve[i + 1] - curve[i]) * (x - i))
    body = _biquad(_osc('saw', f, n), 'lp', cut, q)
    env = _env(n, peak, 0.02, dur * 0.65, dur * 0.33)
    fl = array('f', (1 + flut[1] * math.sin(2 * math.pi * flut[0] * i / SR) for i in range(n)))
    amt, nf, nq = noise
    hiss = _mul(_biquad(_noise(n), 'bp', nf, nq), _env(n, peak * amt, 0.02, dur * 0.55, dur * 0.43))
    tone_part = _mul(_mul(body, env), fl)
    if amt >= 1.0:   # hiss-dominated: keep only a faint low tone under it
        tone_part = array('f', (v * 0.25 for v in tone_part))
    out = _mix(tone_part, hiss)
    return _mul(out, _gate(n, gate)) if gate else out


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
