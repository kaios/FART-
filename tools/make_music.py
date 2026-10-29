"""Compose the background music loops into digestion_lab/music/*.wav.

Run with any Python that has numpy (development only; the game itself doesn't need numpy):
    python3 tools/make_music.py
Each track is an 8-bar loop that repeats seamlessly. Tracks get faster and busier per level.
"""
import wave
from pathlib import Path

import numpy as np

SR = 22050
OUT = Path(__file__).resolve().parent.parent / 'digestion_lab' / 'music'

SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],
    'dorian': [0, 2, 3, 5, 7, 9, 10],
}

TRACKS = {
    # bpm, tonic (MIDI), scale, chord degree per bar, bass steps, kick/snare/hat steps (per 16-step bar), feel
    'title':  dict(bpm=96, root=65, scale='major', prog=[0, 5, 3, 4, 0, 5, 3, 4], bass=[0, 8, 12],
                   kick=[0, 8], snare=[4, 12], hat=[0, 4, 8, 12], arp=0, lead=0.45, seed=1, bass_wave='tri'),
    'level1': dict(bpm=104, root=60, scale='major', prog=[0, 4, 5, 3, 0, 4, 3, 4], bass=[0, 6, 8, 14],
                   kick=[0, 8], snare=[4, 12], hat=[0, 2, 4, 6, 8, 10, 12, 14], arp=8, lead=0.55, seed=2,
                   bass_wave='tri'),
    'level2': dict(bpm=114, root=67, scale='major', prog=[0, 3, 1, 4, 0, 3, 1, 4], bass=[0, 2, 4, 6, 8, 10, 12, 14],
                   kick=[0, 6, 8], snare=[4, 12], hat=[0, 2, 4, 6, 8, 10, 12, 14], arp=8, lead=0.6, seed=3,
                   bass_wave='square'),
    'level3': dict(bpm=124, root=62, scale='dorian', prog=[0, 3, 0, 3, 0, 3, 6, 4], bass=[0, 3, 6, 8, 11, 14],
                   kick=[0, 7, 8], snare=[4, 12], hat=list(range(16)), arp=16, lead=0.6, seed=4, bass_wave='square'),
    'level4': dict(bpm=136, root=57, scale='minor', prog=[0, 5, 2, 6, 0, 5, 2, 6], bass=[0, 2, 4, 6, 8, 10, 12, 14],
                   kick=[0, 4, 8, 12], snare=[4, 12], hat=list(range(16)), arp=16, lead=0.65, seed=5,
                   bass_wave='square'),
    'level5': dict(bpm=150, root=64, scale='minor', prog=[0, 3, 5, 4, 0, 3, 5, 4], bass=list(range(16)),
                   kick=[0, 3, 6, 8, 11, 14], snare=[4, 12], hat=list(range(16)), arp=16, lead=0.75, seed=6,
                   bass_wave='square'),
}


def freq(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def osc(kind, f, n, duty=0.5, vib=0.0):
    t = np.arange(n) / SR
    ph = np.cumsum(np.full(n, f) * (1 + vib * np.sin(2 * np.pi * 5.5 * t))) / SR % 1.0
    if kind == 'square':
        return np.where(ph < duty, 1.0, -1.0)
    if kind == 'tri':
        return 4 * np.abs(ph - 0.5) - 1
    return np.sin(2 * np.pi * ph)


def adsr(n, a=0.005, d=0.06, s=0.6, r=0.04):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    env = np.full(n, s)
    env[:a] = np.linspace(0, 1, a) if a else env[:a]
    env[a:a + d] = np.linspace(1, s, len(env[a:a + d]))
    if r and n > r:
        env[-r:] *= np.linspace(1, 0, r)
    return env


def lowpass(x, k):
    """One-pole low-pass, k in 0..1 (smaller = darker)."""
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += k * (v - acc)
        y[i] = acc
    return y


def chord(scale, degree):
    return [scale[(degree + k) % 7] + 12 * ((degree + k) // 7) for k in (0, 2, 4)]


def render(spec):
    rng = np.random.default_rng(spec['seed'])
    scale = SCALES[spec['scale']]
    step = 60 / spec['bpm'] / 4
    steps = 16 * len(spec['prog'])
    total = int(steps * step * SR)
    tail = int(2.0 * SR)
    mix = {k: np.zeros(total + tail) for k in ('bass', 'arp', 'lead', 'drums')}

    def put(track, start_step, sig, gain):
        i = int(start_step * step * SR)
        mix[track][i:i + len(sig)] += sig[:len(mix[track]) - i] * gain

    noise = rng.uniform(-1, 1, int(0.3 * SR))
    kick_n = int(0.16 * SR)
    kt = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-kt * 30)) / SR) * np.exp(-kt * 18)
    sn = int(0.15 * SR)
    snare = (np.diff(noise[:sn + 1]) * 0.7 + 0.4 * np.sin(2 * np.pi * 185 * np.arange(sn) / SR)) * \
        np.exp(-np.arange(sn) / SR * 28)
    hn = int(0.035 * SR)
    hat = np.diff(np.diff(noise[:hn + 2])) * np.exp(-np.arange(hn) / SR * 90)

    # melody: phrase A (bars 1-2), A' (3-4), B (5-6), A ending on the tonic (7-8)
    def rhythm(density):
        return [s for s in range(32) if (s % 4 == 0 and rng.random() < 0.9) or rng.random() < density * 0.35]
    ra, rb = rhythm(spec['lead']), rhythm(spec['lead'])
    phrases = [ra, ra, rb, ra]
    prev = spec['root'] + 12 + scale[2]
    for p, rhy in enumerate(phrases):
        for idx, s in enumerate(rhy):
            bar = p * 2 + s // 16
            tones = [spec['root'] + 12 + t for t in chord(scale, spec['prog'][bar])]
            if p == 3 and idx == len(rhy) - 1:
                target = spec['root'] + 12        # resolve home at the end of the loop
            elif s % 4 == 0:
                target = min((t + 12 * o for t in tones for o in (-1, 0, 1)), key=lambda m: abs(m - prev))
            else:
                deg = [spec['root'] + 12 + x + 12 * o for x in scale for o in (-1, 0, 1)]
                near = sorted(deg, key=lambda m: abs(m - prev))[1:4]
                target = near[rng.integers(len(near))]
            nxt = rhy[idx + 1] if idx + 1 < len(rhy) else 32
            dur = max(1, min(nxt - s, 4)) * step * 0.9
            n = int(dur * SR)
            sig = osc('square', freq(target), n, duty=0.5, vib=0.006) * adsr(n, d=0.08, s=0.55, r=0.05)
            put('lead', p * 32 + s, sig, 0.2)
            prev = target

    for bar, deg in enumerate(spec['prog']):
        tones = chord(scale, deg)
        root = spec['root'] - 24 + tones[0]
        for k, s in enumerate(spec['bass']):
            m = root + (12 if (len(spec['bass']) >= 8 and k % 2) else 0)
            n = int(step * 1.6 * SR)
            sig = osc(spec['bass_wave'], freq(m), n, duty=0.35) * adsr(n, d=0.1, s=0.5, r=0.03)
            put('bass', bar * 16 + s, sig, 0.3)
        if spec['arp']:
            every = 16 // spec['arp']
            for k, s in enumerate(range(0, 16, every)):
                m = spec['root'] + 12 + tones[k % 3]
                n = int(step * every * 0.8 * SR)
                put('arp', bar * 16 + s, osc('square', freq(m), n, duty=0.25) * adsr(n, d=0.04, s=0.3), 0.07)
        for s in spec['kick']:
            put('drums', bar * 16 + s, kick, 0.55)
        for s in spec['snare']:
            put('drums', bar * 16 + s, snare, 0.32)
        for s in spec['hat']:
            put('drums', bar * 16 + s, hat, 0.12 if s % 4 else 0.18)

    lead = lowpass(mix['lead'], 0.35)
    echo = int(3 * step * SR)
    lead[echo:] += lead[:-echo] * 0.28
    out = lowpass(mix['bass'], 0.25) + lowpass(mix['arp'], 0.3) + lead + mix['drums']
    out[:tail] += out[total:total + tail]   # fold the tail onto the start: seamless loop
    out = out[:total]
    out = np.tanh(out / np.abs(out).max() * 1.4) * 0.8
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in TRACKS.items():
        x = render(spec)
        pcm = (x * 32767).astype(np.int16)
        with wave.open(str(OUT / f'{name}.wav'), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        print(f'{name:7s} {spec["bpm"]} bpm  {len(x) / SR:5.1f}s loop')


if __name__ == '__main__':
    main()
