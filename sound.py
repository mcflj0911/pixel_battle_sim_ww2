"""Sound for Pixel BS: every effect and the background music are synthesized with numpy when the program starts, so
there are no audio files to ship. If the machine has no audio device the game simply runs silent.

    audio = Audio()                    # None-safe: audio.ok is False when there is no sound device
    audio.listen(cam_x)                # each frame: where the camera is (sounds are panned and fade with distance)
    audio.sfx("clash", world_x)        # play an effect at a place on the battlefield
    audio.update()                     # each frame: starts the music when it has finished being composed

Drop your own .ogg/.mp3/.wav files into a folder called `music` next to this file and they are played instead of the
built-in march (in name order, looping the first).

Controls (wired in main.py): M mutes everything; [ and ] change the music volume; , and . change the effects volume."""
import json
import math
import os
import random
import threading

import numpy as np
from scipy.signal import butter, lfilter

import config as C

RATE = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(HERE, "audio_settings.json")
MUSIC_DIR = os.path.join(HERE, "music")
HEARING = 1500.0          # world pixels from the middle of the screen at which a sound can no longer be heard


# ---------------------------------------------------------------------------------------------- synthesis kit
def _t(dur):
    return np.arange(int(RATE * dur)) / RATE


def _noise(dur, rng):
    return rng.uniform(-1, 1, int(RATE * dur))


def _lp(x, fc, order=2):
    b, a = butter(order, min(fc, RATE * 0.45) / (RATE / 2), "low")
    return lfilter(b, a, x)


def _hp(x, fc, order=2):
    b, a = butter(order, max(fc, 20) / (RATE / 2), "high")
    return lfilter(b, a, x)


def _bp(x, lo, hi):
    b, a = butter(2, [lo / (RATE / 2), min(hi, RATE * 0.45) / (RATE / 2)], "band")
    return lfilter(b, a, x)


def _env(n, attack=0.004, decay=0.1):
    """A quick attack and an exponential fall."""
    t = np.arange(n) / RATE
    e = np.exp(-t / max(decay, 1e-4))
    a = int(attack * RATE)
    if a > 0:
        e[:a] *= np.linspace(0, 1, a)
    return e


def _sweep(f0, f1, dur):
    """A sine whose pitch glides from f0 to f1."""
    t = _t(dur)
    f = f0 + (f1 - f0) * (t / dur)
    return np.sin(2 * np.pi * np.cumsum(f) / RATE)


def _norm(x, peak=0.9):
    m = float(np.max(np.abs(x))) or 1.0
    return x * (peak / m)


def _fit(x, n):
    return np.pad(x, (0, max(0, n - len(x))))[:n]


def _layer(*parts):
    n = max(len(p) for p in parts)
    return sum(_fit(p, n) for p in parts)


def _echo(x, taps):
    """A cheap reverb: a few delayed, quieter copies."""
    out = np.pad(x, (0, int(max(d for d, _ in taps) * RATE)))
    for delay, gain in taps:
        k = int(delay * RATE)
        out[k:k + len(x)] += x * gain
    return out


def _stereo(x):
    return np.stack([x, x], axis=1)


# ---------------------------------------------------------------------------------------------- the effects
def make_effects(seed=5):
    """Returns {name: [variants]}, each a mono float array in -1..1. Variants differ a little so a clash is never
    the same sound twice."""
    rng = np.random.default_rng(seed)
    fx = {}

    def variants(name, n, fn):
        fx[name] = [_norm(fn(rng)) for _ in range(n)]

    def bow(r):                                             # a rifle shot: a sharp crack, a thump, a short echo
        dur = 0.38
        n = int(RATE * dur)
        crack = _hp(_noise(dur, r), 1800) * _env(n, 0.0003, 0.02)
        thump = _sweep(r.uniform(260, 340), 70, 0.12) * _env(int(RATE * 0.12), 0.0005, 0.035)
        tail = _bp(_noise(dur, r), 350, 1600) * _env(n, 0.002, 0.11)
        return _layer(crack * 1.0, np.pad(thump, (0, n - len(thump))) * 0.8, tail * 0.35)
    def fire_arrow(r):                                      # a flamethrower: a rifle-like pop and a long burning roar
        dur = 0.9
        n = int(RATE * dur)
        roar = _bp(_noise(dur, r), 200, 2600) * np.sin(np.linspace(0, np.pi, n)) ** 1.2
        crackle = (_hp(_noise(dur, r), 2200) * (r.random(n) > 0.93)) * _env(n, 0.02, 0.5)
        return _layer(bow(r) * 0.5, roar * 0.8, crackle * 1.1)
    def volley(r):                                          # a machine-gun burst
        out = np.zeros(int(RATE * 1.0))
        shots = int(r.integers(9, 14))
        at = 0.0
        for i in range(shots):
            k = int(RATE * at)
            b = bow(r) * r.uniform(0.6, 1.0)
            if k < len(out):
                out[k:k + len(b)] += b[:len(out) - k]
            at += r.uniform(0.045, 0.07)
        return _layer(out * 0.7, _bp(_noise(1.0, r), 300, 1400) * _env(len(out), 0.01, 0.5) * 0.15)
    def arrow_hit(r):                                       # a bullet strike: a dirt thud and sometimes a ricochet whine
        n = int(RATE * 0.22)
        thud = _lp(_noise(0.22, r), 700) * _env(n, 0.0008, 0.03)
        tick = _bp(_noise(0.22, r), 900, 3500) * _env(n, 0.0004, 0.012)
        ping = _sweep(r.uniform(2400, 3400), r.uniform(900, 1400), 0.18) * _env(int(RATE * 0.18), 0.0005, 0.07)
        return _layer(thud * 0.9, tick * 0.7, np.pad(ping, (0, n - len(ping)))[:n] * (0.5 if r.random() < 0.5 else 0.0))
    def rain(r):                                            # a stick of mortar bombs landing: dull pops one after another
        out = np.zeros(int(RATE * 0.8))
        for _ in range(7):
            at = int(RATE * r.uniform(0, 0.55))
            k = int(RATE * 0.16)
            pop = (_lp(_noise(0.16, r), 800) * _env(k, 0.0008, 0.05) + 0.8 * _sweep(120, 45, 0.16) * _env(k, 0.001, 0.05)) * r.uniform(0.5, 1.0)
            out[at:at + k] += pop[:len(out) - at]
        return out
    def catapult(r):                                        # a field gun: a flat, hard crack and a deep thump
        dur = 0.7
        n = int(RATE * dur)
        crack = _hp(_noise(dur, r), 1400) * _env(n, 0.0004, 0.03)
        boom = _sweep(r.uniform(150, 190), 42, 0.4) * _env(int(RATE * 0.4), 0.001, 0.14)
        tail = _lp(_noise(dur, r), 500) * _env(n, 0.004, 0.22)
        return _layer(crack * 0.9, np.pad(boom, (0, n - len(boom))) * 1.0, tail * 0.5)
    def trebuchet(r):                                       # a howitzer: a much deeper, longer blast
        dur = 1.2
        n = int(RATE * dur)
        crack = _hp(_noise(dur, r), 900) * _env(n, 0.0005, 0.045)
        boom = _sweep(105, 28, 0.8) * _env(int(RATE * 0.8), 0.001, 0.26)
        tail = _lp(_noise(dur, r), 320) * _env(n, 0.006, 0.45)
        return _layer(crack * 0.7, np.pad(boom, (0, n - len(boom))) * 1.1, tail * 0.7)
    def boulder(r):                                         # a shell bursting: a flat bang, a rolling boom, flying earth
        dur = 1.0
        n = int(RATE * dur)
        bang = _hp(_noise(dur, r), 900) * _env(n, 0.0004, 0.04)
        boom = _sweep(r.uniform(85, 110), 30, 0.9) * _env(int(RATE * 0.9), 0.001, 0.3)
        rumble = _lp(_noise(dur, r), 500) * _env(n, 0.003, 0.34)
        frag = (_hp(_noise(dur, r), 2500) * (r.random(n) > 0.985)) * _env(n, 0.04, 0.35)
        return _layer(bang * 0.9, np.pad(boom, (0, n - len(boom))) * 1.0, rumble * 0.8, frag * 1.2)
    def pitch(r):
        boom = _sweep(90, 35, 0.6) * _env(int(RATE * 0.6), 0.002, 0.2)
        n = int(RATE * 1.1)
        flutter = 0.5 + 0.5 * np.sin(2 * np.pi * r.uniform(11, 17) * _t(1.1))
        crackle = (_hp(_noise(1.1, r), 1800) * (r.random(n) > 0.9)) * _env(n, 0.01, 0.5) * flutter
        roar = _lp(_noise(1.1, r), 900) * _env(n, 0.05, 0.4)
        return _layer(boom * 0.8, roar * 0.8, crackle * 1.4)

    def clash(r):                                           # a rifle butt, a bayonet or a helmet: a thud with a short metal clink
        base = r.uniform(0.9, 1.2)
        n = int(RATE * 0.22)
        clink = sum(g * np.sin(2 * np.pi * f * base * _t(0.22)) * _env(n, 0.0004, d)
                    for f, g, d in ((2200, 0.8, 0.035), (3300, 0.5, 0.025), (4900, 0.25, 0.015)))
        thud = _lp(_noise(0.22, r), 600) * _env(n, 0.001, 0.045) + np.sin(2 * np.pi * r.uniform(110, 160) * _t(0.22)) * _env(n, 0.001, 0.04)
        return clink * 0.5 + thud * 0.9
    def hit(r):
        n = int(RATE * 0.14)
        body = _lp(_noise(0.14, r), 700) * _env(n, 0.001, 0.04)
        thud = np.sin(2 * np.pi * r.uniform(90, 140) * _t(0.14)) * _env(n, 0.001, 0.04)
        return body + thud

    def fall(r):
        n = int(RATE * 0.38)
        grunt = _sweep(r.uniform(190, 240), r.uniform(80, 110), 0.38) * _env(n, 0.01, 0.16)
        grunt = _lp(grunt + 0.4 * np.sin(2 * np.pi * 2 * np.cumsum(np.linspace(200, 90, n)) / RATE), 1200)
        drop = np.pad(_lp(_noise(0.2, r), 400) * _env(int(RATE * 0.2), 0.001, 0.06), (int(RATE * 0.2), 0))
        return _layer(grunt * 0.8, drop * 0.7)

    def crash(r):
        n = int(RATE * 1.6)
        rumble = _lp(_noise(1.6, r), 450) * _env(n, 0.005, 0.7)
        debris = _hp(_noise(1.6, r), 900) * (r.random(n) > 0.985) * _env(n, 0.05, 0.6)
        boom = _sweep(80, 25, 1.0) * _env(int(RATE * 1.0), 0.002, 0.35)
        return _layer(rumble, debris * 2.0, boom)

    def horn(r):                                            # a bugle call: three rising notes
        a = brass(392.0, 0.28, r)
        b = brass(523.2, 0.28, r)
        c = brass(659.3, 0.9, r)
        return _layer(a, np.pad(b, (int(RATE * 0.3), 0)), np.pad(c, (int(RATE * 0.6), 0)) * 0.95)
    def gate(r):                                            # a checkpoint barrier: a chain rattle and a clang of steel
        dur = 1.2
        n = int(RATE * dur)
        t = _t(dur)
        rattle = _bp(_noise(dur, r), 1200, 5200) * (r.random(n) > 0.92) * _env(n, 0.02, 0.45)
        whine = _bp(_noise(dur, r), 150, 700) * np.minimum(1, t / 0.1) * np.minimum(1, (dur - t) / 0.4) * 0.5
        clang = sum(g * np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, g, d in ((640, 1.0, 0.18), (1540, 0.6, 0.12), (2300, 0.3, 0.08)))
        clang = np.pad(clang, (int(RATE * 0.9), 0))[:n] * 0.9
        return _layer(rattle * 1.2, whine, clang)
    def thud(r):
        n = int(RATE * 0.2)
        return _lp(_noise(0.2, r), 500) * _env(n, 0.002, 0.05)

    def brass(f0, dur, r):
        t = _t(dur)
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t)
        phase = 2 * np.pi * np.cumsum(f0 * vib) / RATE
        tone = sum(np.sin(h * phase) / h ** 0.8 for h in range(1, 8))
        env = np.minimum(1, t / 0.05) * np.minimum(1, (dur - t) / 0.25)
        return _lp(tone, 2200) * env

    def rally(r):
        a = brass(261.6, 0.32, r)
        b = brass(392.0, 0.9, r)
        c = brass(523.2, 0.9, r)
        return _layer(a, np.pad(b, (int(RATE * 0.3), 0)) * 0.9, np.pad(c, (int(RATE * 0.3), 0)) * 0.6)

    def curse(r):
        dur = 1.1
        t = _t(dur)
        sweep = _bp(_noise(dur, r), 150, 1200) * np.sin(np.linspace(0, np.pi, len(t))) ** 1.5
        drone = (np.sin(2 * np.pi * 110 * t) + np.sin(2 * np.pi * 117.5 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * t))
        return _layer(sweep * 0.8, drone * 0.5 * np.minimum(1, (dur - t) / 0.5))

    def slam(r):
        boom = _sweep(130, 34, 0.55) * _env(int(RATE * 0.55), 0.002, 0.18)
        rumble = _lp(_noise(0.6, r), 600) * _env(int(RATE * 0.6), 0.002, 0.2)
        crack = _hp(_noise(0.1, r), 1500) * _env(int(RATE * 0.1), 0.0005, 0.02)
        return _layer(boom, rumble * 0.8, crack * 0.4)

    def heal(r):
        out = np.zeros(int(RATE * 1.1))
        for i, f in enumerate((1046.5, 1318.5, 1568.0, 2093.0)):
            tone = np.sin(2 * np.pi * f * _t(0.8)) * _env(int(RATE * 0.8), 0.01, 0.3)
            at = int(RATE * 0.08 * i)
            out[at:at + len(tone)] += tone[:len(out) - at]
        return out

    def charge(r):                                          # engines roaring: a rising saw-tooth growl and road noise
        dur = 1.0
        t = _t(dur)
        f = np.linspace(55, 135, len(t))
        saw = 2 * ((np.cumsum(f) / RATE) % 1) - 1
        growl = _lp(saw + 0.5 * (2 * (((np.cumsum(f * 2.01)) / RATE) % 1) - 1), 700) * (0.6 + 0.4 * np.sin(2 * np.pi * 23 * t))
        road = _bp(_noise(dur, r), 250, 1600) * np.linspace(0.1, 0.7, len(t))
        return _layer(growl * 0.9 * np.minimum(1, (dur - t) / 0.2), road * 0.5)
    def respawn(r):
        dur = 1.6
        t = _t(dur)
        bell = sum(g * np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, g, d in
                   ((523, 1.0, 0.9), (1318, 0.5, 0.6), (2093, 0.3, 0.4), (784, 0.5, 0.8)))
        return bell

    def gong(r):
        dur = 2.2
        t = _t(dur)
        body = sum(g * np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, g, d in
                   ((98, 1.0, 1.2), (147, 0.7, 0.9), (203, 0.5, 0.7), (311, 0.3, 0.5)))
        return body + _lp(_noise(dur, r), 700) * _env(len(t), 0.002, 0.25) * 0.4

    def zap(r):
        dur = 0.3
        n = int(RATE * dur)
        return _layer(_bp(_noise(dur, r), 800, 5000) * _env(n, 0.002, 0.07) * 0.8,
                      _sweep(700, 1700, dur) * _env(n, 0.002, 0.1) * 0.5)

    def holy(r):
        dur = 1.2
        t = _t(dur)
        chord = sum(np.sin(2 * np.pi * f * t) for f in (523.3, 659.3, 784.0, 1046.5)) * np.minimum(1, t / 0.06) * np.exp(-t / 0.5)
        boom = _sweep(110, 50, 0.4) * _env(int(RATE * 0.4), 0.002, 0.12)
        return _layer(chord * 0.5, np.pad(boom, (0, 0)) * 0.9)

    def whistle(r):
        dur = 0.7
        n = int(RATE * dur)
        return _sweep(2200, 500, dur) * np.linspace(0.3, 1, n) * 0.5 + _bp(_noise(dur, r), 1500, 4000) * np.linspace(0, 0.5, n) * 0.3

    variants("whistle", 2, whistle)

    def splash(r):
        dur = 0.45
        n = int(RATE * dur)
        body = _bp(_noise(dur, r), 300, 2400) * _env(n, 0.004, 0.14)
        plop = _sweep(420, 120, 0.2) * _env(int(RATE * 0.2), 0.002, 0.06)
        return _layer(body * 0.8, plop * 0.6, _hp(_noise(dur, r), 3500) * _env(n, 0.002, 0.07) * 0.25)

    def thunder(r):
        dur = 2.6
        n = int(RATE * dur)
        rumble = _lp(_noise(dur, r), 160, 2) * _env(n, 0.25, 0.9) * (1 + 0.7 * np.sin(2 * np.pi * _t(dur) * r.uniform(3, 6)))
        crackle = _bp(_noise(dur, r), 200, 900) * _env(n, 0.05, 0.5) * 0.35
        return _layer(rumble * 1.6, crackle)

    def crack(r):
        dur = 0.5
        n = int(RATE * dur)
        snap = _hp(_noise(dur, r), 1500) * _env(n, 0.0005, 0.05)
        boom = _sweep(220, 50, dur) * _env(n, 0.001, 0.18)
        return _layer(snap * 1.2, boom * 0.9)

    variants("splash", 3, splash)
    variants("thunder", 3, thunder)
    variants("crack", 2, crack)

    for name, count, fn in (("rally", 2, rally), ("curse", 2, curse), ("slam", 3, slam), ("heal", 2, heal),
                            ("charge", 2, charge), ("respawn", 1, respawn), ("gong", 1, gong), ("zap", 3, zap),
                            ("holy", 2, holy)):
        variants(name, count, fn)

    for name, count, fn in (("bow", 4, bow), ("fire_arrow", 2, fire_arrow), ("volley", 3, volley),
                            ("arrow_hit", 4, arrow_hit), ("rain", 3, rain), ("catapult", 3, catapult),
                            ("trebuchet", 3, trebuchet), ("boulder", 3, boulder), ("pitch", 2, pitch),
                            ("clash", 6, clash), ("hit", 4, hit), ("fall", 4, fall), ("crash", 2, crash),
                            ("horn", 2, horn), ("gate", 2, gate), ("thud", 3, thud)):
        variants(name, count, fn)
    return fx


# the loudness of each effect (before distance) and the quietest gap between two of the same
LEVELS = {"bow": 0.30, "fire_arrow": 0.42, "volley": 0.50, "arrow_hit": 0.30, "rain": 0.38, "catapult": 0.7,
          "trebuchet": 0.75, "boulder": 0.95, "pitch": 0.85, "clash": 0.34, "hit": 0.26, "fall": 0.38, "crash": 1.0,
          "horn": 0.75, "gate": 0.7, "thud": 0.2, "rally": 0.8, "curse": 0.7, "slam": 0.9, "heal": 0.55,
          "charge": 0.75, "respawn": 0.8, "gong": 0.8, "zap": 0.3, "holy": 0.8, "whistle": 0.35,
          "splash": 0.35, "thunder": 1.0, "crack": 0.9}
GAPS = {"bow": 0.05, "fire_arrow": 0.1, "volley": 0.2, "arrow_hit": 0.05, "rain": 0.15, "catapult": 0.15,
        "trebuchet": 0.15, "boulder": 0.1, "pitch": 0.15, "clash": 0.045, "hit": 0.05, "fall": 0.09, "crash": 0.3,
        "horn": 0.8, "gate": 0.5, "thud": 0.1, "rally": 1.0, "curse": 1.0, "slam": 0.6, "heal": 0.8,
        "charge": 1.0, "respawn": 1.0, "gong": 1.0, "zap": 0.08, "holy": 0.3, "whistle": 0.25,
        "splash": 0.07, "thunder": 0.8, "crack": 0.5}


# ---------------------------------------------------------------------------------------------- the music
def compose(seed=11):
    """A slow, modal war march in A minor: a deep drum, a drone, string pads and a plucked tune, 16 bars long
    (about 46 seconds) that loops without a seam. Returns a stereo int16 array."""
    r = random.Random(seed)
    rng = np.random.default_rng(seed)
    bpm = 84
    beat = 60.0 / bpm
    bars = 16
    n = int(RATE * beat * 4 * bars)
    left, right = np.zeros(n), np.zeros(n)

    def put(buf, x, at):
        i = int(at * RATE)
        if i < n:
            buf[i:i + len(x)] += x[:n - i]

    def midi(m):
        return 440.0 * 2 ** ((m - 69) / 12)

    # chords per bar (root, third, fifth as midi notes): Am | Am | F | G | Am | C | G | E  (twice over)
    prog = [(45, 48, 52), (45, 48, 52), (41, 45, 48), (43, 47, 50), (45, 48, 52), (48, 52, 55), (43, 47, 50), (40, 44, 47)]
    chords = prog + prog

    # --- pad: slow detuned strings, filtered
    for b, ch in enumerate(chords):
        dur = beat * 4 + 0.6
        t = _t(dur)
        pad = 0
        for note in ch:
            for det in (-0.12, 0.12):
                f = midi(note + 12) * 2 ** (det / 12)
                pad = pad + (2 * ((f * t) % 1) - 1)
        env = np.minimum(1, t / 0.9) * np.minimum(1, (dur - t) / 0.7)
        pad = _lp(pad, 900) * env * 0.05
        put(left, pad, b * beat * 4)
        put(right, pad * 0.9, b * beat * 4 + 0.01)

    # --- drone: two low notes under everything
    t = _t(n / RATE)
    drone = _lp(sum(2 * ((midi(m) * t) % 1) - 1 for m in (33, 40)), 260) * 0.08
    drone *= 0.75 + 0.25 * np.sin(2 * np.pi * t / (beat * 8))
    left += drone
    right += drone

    # --- drums: a taiko on the beat, a pickup before the bar ends, a soft rim on the off-beats
    def taiko(power):
        k = int(RATE * 0.55)
        body = _sweep(95, 42, 0.55) * _env(k, 0.002, 0.2)
        skin = _bp(_noise(0.55, rng), 200, 1200) * _env(k, 0.001, 0.05)
        return (body + 0.35 * skin) * power

    def rim():
        k = int(RATE * 0.12)
        return _bp(_noise(0.12, rng), 1800, 5200) * _env(k, 0.0005, 0.02) * 0.5

    for b in range(bars):
        bt = b * beat * 4
        for i, power in ((0, 0.9), (2, 0.75)):
            d = taiko(power) * 0.38
            put(left, d, bt + i * beat)
            put(right, d, bt + i * beat)
        if b % 2 == 1:                                  # a roll into the next bar
            for j, off in enumerate((3.0, 3.25, 3.5, 3.75)):
                d = taiko(0.35 + 0.1 * j) * 0.3
                put(left, d, bt + off * beat)
                put(right, d, bt + off * beat)
        for i in (1, 3):
            put(left, rim() * 0.35, bt + (i + 0.5) * beat)
            put(right, rim() * 0.45, bt + (i + 0.5) * beat)

    # --- the tune: plucked, on the A minor pentatonic (A C D E G), landing on a chord note at the start of each bar
    penta = [57, 60, 62, 64, 67, 69, 72, 74, 76]
    rhythms = [[1, 1, 2], [2, 1, 1], [1, 1, 1, 1], [3, 1], [2, 2], [1, 0.5, 0.5, 2], [4]]

    def pluck(m, length):
        dur = max(0.6, length)
        t = _t(dur)
        f = midi(m)
        tone = sum(np.sin(2 * np.pi * f * h * t) / h ** 1.4 for h in range(1, 7))
        return tone * np.exp(-t / 0.45) * np.minimum(1, t / 0.004) * 0.1

    phrase = []
    idx = 3
    for b in range(8):
        beats_left = 4.0
        pos = 0.0
        pattern = r.choice(rhythms)
        if b == 7:
            pattern = [2, 2]
        for k, length in enumerate(pattern):
            if k == 0:                                  # the first note of the bar is a chord tone
                root = chords[b][0] % 12
                cands = [i for i, m in enumerate(penta) if m % 12 in (root, (root + 7) % 12, (root + 3) % 12, (root + 4) % 12)]
                idx = min(cands, key=lambda i: abs(i - idx)) if cands else idx
            else:
                idx = max(0, min(len(penta) - 1, idx + r.choice((-2, -1, -1, 1, 1, 2))))
            phrase.append((b, pos, penta[idx], length))
            pos += length
        if b == 7:
            phrase[-1] = (b, 0.0 + 2, penta[2], 2)      # settle on D... the second half lifts it on repeat
    for rep in range(2):
        for b, pos, m, length in phrase:
            m2 = m + (12 if rep == 1 and b % 4 == 3 else 0)
            if rep == 0 and b < 2:
                continue                                  # the first time round the tune enters late
            note = pluck(m2, length * beat)
            at = (rep * 8 + b) * beat * 4 + pos * beat
            put(left, note * (0.8 if b % 2 else 1.0), at)
            put(right, note * (1.0 if b % 2 else 0.8), at + 0.012)

    # --- a little air: echo taps, then wrap the tail round so the loop has no seam
    for buf in (left, right):
        tail = _echo(buf, ((0.19, 0.28), (0.41, 0.17), (0.73, 0.09)))
        buf += tail[:n]
        extra = tail[n:]
        buf[:len(extra)] += extra
    out = np.stack([left, right], axis=1)
    out = np.tanh(out * 1.6) * 0.8                      # soft limiting
    fade = int(RATE * 0.03)                             # a 30 ms fade at both ends: the loop restarts without a click
    out[:fade] *= np.linspace(0, 1, fade)[:, None]
    out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return (out * 32000).astype(np.int16)


# ---------------------------------------------------------------------------------------------- the player
class Audio:
    def __init__(self, enable=True):
        self.ok = False
        self.muted = False
        self.music_vol = 0.5
        self.sfx_vol = 0.7
        self.cam_x = 0.0
        self.speed = 1
        self._last = {}
        self._clock = 0.0
        self._music_ready = None
        self._music_playing = False
        self._stream = None
        self._music_chan = None
        self._wind_chan = None
        self._rain_chan = self._surf_chan = None
        self.amb = {"rain": 0.0, "wind": 0.0, "storm": 0.0, "snow": 0.0, "surf": 0.0}
        self._amb_on = False
        self.sounds = {}
        self._load_settings()
        if not enable:
            return
        try:
            import pygame
            self.pg = pygame
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(RATE, -16, 2, 512)
                pygame.mixer.init(RATE, -16, 2, 512)
            pygame.mixer.set_num_channels(30)
            pygame.mixer.set_reserved(4)                  # channels 0-3: music, wind, rain, surf
            self._music_chan = pygame.mixer.Channel(0)
            self._wind_chan = pygame.mixer.Channel(1)
            self._rain_chan = pygame.mixer.Channel(2)
            self._surf_chan = pygame.mixer.Channel(3)
            self.ok = True
            self._built = None
            self.wind = None
            threading.Thread(target=self._build, daemon=True).start()   # composing takes a few seconds: not in the way
        except Exception as err:                            # no device, or a mixer problem: stay silent
            print(f"sound off: {err}")
            self.ok = False
            return
        self._find_music()
        self._apply()

    def _build(self):
        self._wind_raw = self._make_wind()
        self._rain_raw, self._surf_raw = self._make_rain(), self._make_surf()
        if not self._stream:
            self._music_ready = compose()
        self._built = make_effects()

    # ---------------------------------------------------------------- building
    def _sound(self, mono):
        arr = (np.clip(mono, -1, 1) * 30000).astype(np.int16)
        return self.pg.sndarray.make_sound(np.ascontiguousarray(_stereo(arr)))

    def _make_wind(self):
        rng = np.random.default_rng(3)
        dur = 12.0
        x = _noise(dur, rng)
        gust = 0.55 + 0.45 * np.sin(2 * np.pi * _t(dur) / dur * 3 + 1.0)
        wind = _bp(x, 120, 700) * gust
        fade = int(RATE * 0.5)                               # fade the ends together so it loops without a click
        wind[:fade] *= np.linspace(0, 1, fade)
        wind[-fade:] *= np.linspace(1, 0, fade)
        wind[:fade] += wind[-fade:][::-1] * 0
        return _norm(wind, 0.5)

    @staticmethod
    def _loop_fade(x):
        fade = int(RATE * 0.4)
        x = x.copy()
        x[:fade] = x[:fade] * np.linspace(0, 1, fade) + x[-fade:] * np.linspace(1, 0, fade)
        return x[:-fade]

    def _make_rain(self):
        rng = np.random.default_rng(4)
        dur = 6.0
        x = _hp(_noise(dur, rng), 900) * (0.7 + 0.3 * np.sin(2 * np.pi * _t(dur) / dur * 5))
        return _norm(self._loop_fade(x), 0.5)

    def _make_surf(self):
        rng = np.random.default_rng(6)
        dur = 10.0
        x = _bp(_noise(dur, rng), 200, 1800) * (0.5 + 0.5 * np.sin(2 * np.pi * _t(dur) / dur * 1.0 - 1.2) ** 2)
        return _norm(self._loop_fade(x), 0.5)

    def set_ambience(self, rain=0.0, wind=0.0, storm=0.0, snow=0.0, surf=None):
        """The weather's background sound: a loop of rain, more wind in a gale, the surf on the beach."""
        self.amb.update(rain=rain, wind=wind, storm=storm, snow=snow)
        if surf is not None:
            self.amb["surf"] = surf
        self._apply_ambience()

    def _apply_ambience(self):
        if not self.ok or getattr(self, "rain_loop", None) is None or not self._music_playing:
            return
        if not self._amb_on:
            self._rain_chan.play(self.rain_loop, loops=-1)
            self._surf_chan.play(self.surf_loop, loops=-1)
            self._amb_on = True
        m = 0.0 if self.muted else self.sfx_vol
        self._rain_chan.set_volume(min(1.0, 0.30 * self.amb["rain"] * m))
        self._surf_chan.set_volume(min(1.0, 0.22 * self.amb["surf"] * m * (1 + 0.8 * self.amb["storm"])))
        self._wind_chan.set_volume(min(1.0, (0.22 + 0.5 * self.amb["wind"]) * m))

    def _find_music(self):
        files = []
        if os.path.isdir(MUSIC_DIR):
            files = sorted(f for f in os.listdir(MUSIC_DIR) if f.lower().endswith((".ogg", ".mp3", ".wav")))
        if files:
            try:
                self.pg.mixer.music.load(os.path.join(MUSIC_DIR, files[0]))
                self._stream = files[0]
                return
            except Exception as err:
                print(f"music file {files[0]} not usable ({err}); using the built-in march")
        self._music_ready = None

    # ---------------------------------------------------------------- per frame
    def listen(self, cam_x):
        self.cam_x = cam_x

    def update(self):
        """Starts the music once it is ready (the built-in march is composed in the background at start-up)."""
        if not self.ok:
            return
        if self._built is not None and not self.sounds:         # the effects are ready: turn them into sounds
            for name, versions in self._built.items():
                self.sounds[name] = [self._sound(v) for v in versions]
            self.wind = self._sound(self._wind_raw)
            self.rain_loop, self.surf_loop = self._sound(self._rain_raw), self._sound(self._surf_raw)
        if self._music_playing:
            return
        if self._stream:
            self.pg.mixer.music.play(-1)
            self._music_playing = True
        elif self._music_ready is not None and self.wind is not None:
            self._music_chan.play(self.pg.sndarray.make_sound(np.ascontiguousarray(self._music_ready)), loops=-1)
            self._wind_chan.play(self.wind, loops=-1)
            self._music_playing = True
        self._apply()

    def sfx(self, name, x=None):
        """Plays an effect at world position x (None = right in front of the listener)."""
        if not self.ok or self.muted or self.sfx_vol <= 0:
            return
        now = self.pg.time.get_ticks() / 1000.0
        gap = GAPS.get(name, 0.05) * (1 + self.speed / 6.0)
        if now - self._last.get(name, -9.0) < gap:
            return
        gain, pan = 1.0, 0.0
        if x is not None:
            off = x - (self.cam_x + C.SCREEN_W / 2)
            gain = max(0.0, 1.0 - abs(off) / HEARING) ** 1.6
            pan = max(-1.0, min(1.0, off / (C.SCREEN_W * 0.75)))
        gain *= LEVELS.get(name, 0.5) * self.sfx_vol / (1 + 0.12 * math.log2(max(1, self.speed)))
        if gain < 0.01:
            return
        versions = self.sounds.get(name)
        if not versions:
            return
        chan = self.pg.mixer.find_channel()                  # None when every channel is busy: skip rather than cut one
        if chan is None:
            return
        self._last[name] = now
        chan.play(random.choice(versions))
        chan.set_volume(min(1.0, gain * (1 - 0.6 * max(0.0, pan))), min(1.0, gain * (1 + 0.0) * (1 + 0.6 * min(0.0, pan))))

    # ---------------------------------------------------------------- controls
    def _apply(self):
        if not self.ok:
            return
        vol = 0.0 if self.muted else self.music_vol
        if self._stream:
            self.pg.mixer.music.set_volume(vol)
        else:
            self._music_chan.set_volume(vol)
            self._apply_ambience()

    def toggle_mute(self):
        self.muted = not self.muted
        self._apply()
        self._save_settings()
        return "SOUND OFF" if self.muted else "SOUND ON"

    def change_music(self, delta):
        self.muted = False
        self.music_vol = round(max(0.0, min(1.0, self.music_vol + delta)), 2)
        self._apply()
        self._save_settings()
        return f"MUSIC {round(self.music_vol * 100)}%"

    def change_sfx(self, delta):
        self.muted = False
        self.sfx_vol = round(max(0.0, min(1.0, self.sfx_vol + delta)), 2)
        self._apply()
        self._save_settings()
        return f"EFFECTS {round(self.sfx_vol * 100)}%"

    def _load_settings(self):
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                d = json.load(f)
            self.muted = bool(d.get("muted", False))
            self.music_vol = float(d.get("music", self.music_vol))
            self.sfx_vol = float(d.get("sfx", self.sfx_vol))
        except (OSError, ValueError):
            pass

    def _save_settings(self):
        try:
            with open(SETTINGS, "w", encoding="utf-8") as f:
                json.dump({"muted": self.muted, "music": self.music_vol, "sfx": self.sfx_vol}, f)
        except OSError:
            pass
