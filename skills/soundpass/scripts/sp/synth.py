"""A small, dependency-free synthesizer for game sound effects.

A sound is described by a *recipe* (a plain dict / JSON object):

    {
      "layers": [ {layer}, {layer}, ... ],   # mixed together
      "fx": { ... },                          # applied to the mix
      "loudness": -18                         # target momentary loudness, dBFS RMS
    }

See references/recipe-format.md for the full field reference.
Only the Python standard library is used, so it runs anywhere Python 3.8+ does.
"""
from __future__ import annotations

import math
import random
import re
import struct
import sys
import wave
from array import array

TWO_PI = 2.0 * math.pi
DEFAULT_SR = 44100

WAVES = ("sine", "triangle", "square", "saw", "noise", "crunch", "fm")
FILTER_TYPES = ("lp", "hp", "bp")

_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


class RecipeError(ValueError):
    pass


def midi_to_hz(m: float) -> float:
    return 440.0 * 2.0 ** ((m - 69.0) / 12.0)


def note_to_midi(name: str) -> int:
    m = _NOTE_RE.match(name.strip())
    if not m:
        raise RecipeError("bad note name %r (use e.g. 'A4', 'C#5', 'Eb3')" % name)
    pc = _PC[m.group(1).upper()]
    if m.group(2) == "#":
        pc += 1
    elif m.group(2) == "b":
        pc -= 1
    return pc + 12 * (int(m.group(3)) + 1)


def parse_freq(v) -> float:
    """Accept Hz as a number, or a note name such as 'A4'."""
    if isinstance(v, (int, float)):
        f = float(v)
    else:
        s = str(v).strip()
        try:
            f = float(s)
        except ValueError:
            f = midi_to_hz(note_to_midi(s))
    if not (1.0 <= f <= 20000.0):
        raise RecipeError("frequency %r out of range (1..20000 Hz)" % v)
    return f


def db_to_lin(db: float) -> float:
    return 10.0 ** (db / 20.0)


def lin_to_db(x: float) -> float:
    return 20.0 * math.log10(x) if x > 1e-12 else -240.0


# ---------------------------------------------------------------- layers

def layer_duration(layer: dict) -> float:
    env = layer.get("env", {})
    return (max(float(env.get("attack", 0.002)), 0.0005)
            + max(float(env.get("hold", 0.0)), 0.0)
            + max(float(env.get("decay", 0.2)), 0.001))


def render_layer(L: dict, sr: int, rng: random.Random) -> list:
    wave_type = L.get("wave", "sine")
    if wave_type not in WAVES:
        raise RecipeError("unknown wave %r (choose from %s)" % (wave_type, ", ".join(WAVES)))

    env = L.get("env", {})
    a = max(float(env.get("attack", 0.002)), 0.0005)
    h = max(float(env.get("hold", 0.0)), 0.0)
    d = max(float(env.get("decay", 0.2)), 0.001)
    curve = max(float(env.get("curve", 2.0)), 0.1)
    dur = a + h + d
    n = max(int(dur * sr), 1)

    f0 = parse_freq(L.get("freq", 440.0))
    f1 = parse_freq(L["freq_end"]) if "freq_end" in L else f0
    slide_time = max(float(L.get("slide_time", dur)), 1e-4)
    slide_shape = max(float(L.get("slide_shape", 1.0)), 0.05)
    log_ratio = math.log(f1 / f0)

    steps = sorted((float(s[0]), float(s[1])) for s in L.get("steps", []))
    vib = L.get("vibrato") or {}
    vib_rate = float(vib.get("rate", 0.0))
    vib_depth = float(vib.get("depth", 0.0))  # semitones
    vib_delay = float(vib.get("delay", 0.0))

    duty0 = min(max(float(L.get("duty", 0.5)), 0.02), 0.98)
    duty1 = min(max(float(L.get("duty_end", duty0)), 0.02), 0.98)

    fm = L.get("fm") or {}
    fm_ratio = float(fm.get("ratio", 2.0))
    fm_i0 = float(fm.get("index", 1.0))
    fm_i1 = float(fm.get("index_end", fm_i0))

    color = L.get("color", "white")
    gain = float(L.get("gain", 1.0))

    filt = L.get("filter")
    if filt:
        ftype = filt.get("type", "lp")
        if ftype not in FILTER_TYPES:
            raise RecipeError("unknown filter type %r (choose lp, hp, bp)" % ftype)
        fc0 = parse_freq(filt.get("cutoff", 2000))
        fc1 = parse_freq(filt.get("cutoff_end", fc0))
        fq = max(float(filt.get("q", 0.707)), 0.3)
        fk = 1.0 / fq
        f_log = math.log(fc1 / fc0)
    nyq_safe = sr * 0.45

    out = [0.0] * n
    inv_sr = 1.0 / sr
    rnd = rng.random
    sin = math.sin
    exp = math.exp

    phase = rng.random() if wave_type in ("sine", "fm", "triangle") and L.get("random_phase") else 0.0
    mphase = 0.0
    sh_val = 0.0
    sh_phase = 1.0
    # pink noise (Paul Kellet, economy) / brown noise state
    p0 = p1 = p2 = 0.0
    brown = 0.0
    if wave_type == "noise" and color in ("pink", "brown"):
        # warm the filters up so the noise is at full level from the first sample
        for _ in range(3000):
            w = rnd() * 2.0 - 1.0
            p0 = 0.99765 * p0 + w * 0.0990460
            p1 = 0.96300 * p1 + w * 0.2965164
            p2 = 0.57000 * p2 + w * 1.0526913
            brown = (brown + 0.02 * w) * 0.998
    # state-variable filter state
    ic1 = ic2 = 0.0
    a1 = a2 = a3 = 0.0
    step_i = 0
    step_mul = 1.0
    nsteps = len(steps)
    ah = a + h

    for i in range(n):
        t = i * inv_sr

        # ---- pitch
        if log_ratio:
            p = t / slide_time if t < slide_time else 1.0
            if slide_shape != 1.0:
                p = p ** slide_shape
            f = f0 * exp(log_ratio * p)
        else:
            f = f0
        while step_i < nsteps and t >= steps[step_i][0]:
            step_mul = 2.0 ** (steps[step_i][1] / 12.0)
            step_i += 1
        f *= step_mul
        if vib_depth and t >= vib_delay:
            f *= 2.0 ** (vib_depth * sin(TWO_PI * vib_rate * (t - vib_delay)) / 12.0)
        if f > nyq_safe:
            f = nyq_safe
        dt = f * inv_sr

        # ---- oscillator
        if wave_type == "sine":
            s = sin(TWO_PI * phase)
        elif wave_type == "triangle":
            s = 4.0 * abs(phase - 0.5) - 1.0
        elif wave_type == "square":
            duty = duty0 + (duty1 - duty0) * (t / dur) if duty1 != duty0 else duty0
            s = 1.0 if phase < duty else -1.0
            # PolyBLEP at the rising edge (phase 0) and falling edge (phase == duty)
            if phase < dt:
                x = phase / dt
                s += x + x - x * x - 1.0
            elif phase > 1.0 - dt:
                x = (phase - 1.0) / dt
                s += x * x + x + x + 1.0
            q = phase - duty
            if q < 0.0:
                q += 1.0
            if q < dt:
                x = q / dt
                s -= x + x - x * x - 1.0
            elif q > 1.0 - dt:
                x = (q - 1.0) / dt
                s -= x * x + x + x + 1.0
        elif wave_type == "saw":
            s = 2.0 * phase - 1.0
            if phase < dt:
                x = phase / dt
                s -= x + x - x * x - 1.0
            elif phase > 1.0 - dt:
                x = (phase - 1.0) / dt
                s -= x * x + x + x + 1.0
        elif wave_type == "fm":
            idx = fm_i0 + (fm_i1 - fm_i0) * (t / dur)
            s = sin(TWO_PI * phase + idx * sin(TWO_PI * mphase))
            mphase += dt * fm_ratio
            if mphase >= 1.0:
                mphase -= math.floor(mphase)
        elif wave_type == "crunch":
            # lo-fi sample-and-hold noise: freq sets how gritty / pitched it sounds
            sh_phase += dt * 16.0
            if sh_phase >= 1.0:
                sh_phase -= math.floor(sh_phase)
                sh_val = rnd() * 2.0 - 1.0
            s = sh_val
        else:  # noise
            w = rnd() * 2.0 - 1.0
            if color == "pink":
                p0 = 0.99765 * p0 + w * 0.0990460
                p1 = 0.96300 * p1 + w * 0.2965164
                p2 = 0.57000 * p2 + w * 1.0526913
                s = (p0 + p1 + p2 + w * 0.1848) * 0.25
            elif color == "brown":
                brown = (brown + 0.02 * w) * 0.998
                s = brown * 3.5
            else:
                s = w

        phase += dt
        if phase >= 1.0:
            phase -= math.floor(phase)

        # ---- filter (topology-preserving state-variable filter)
        if filt:
            if (i & 15) == 0:
                fc = fc0 * exp(f_log * (t / dur)) if f_log else fc0
                if fc > nyq_safe:
                    fc = nyq_safe
                g = math.tan(math.pi * fc * inv_sr)
                a1 = 1.0 / (1.0 + g * (g + fk))
                a2 = g * a1
                a3 = g * a2
            v3 = s - ic2
            v1 = a1 * ic1 + a2 * v3
            v2 = ic2 + a2 * ic1 + a3 * v3
            ic1 = 2.0 * v1 - ic1
            ic2 = 2.0 * v2 - ic2
            if ftype == "lp":
                s = v2
            elif ftype == "bp":
                s = v1 * fk  # unity gain at the centre
            else:
                s = s - fk * v1 - v2

        # ---- amplitude envelope
        if t < a:
            e = t / a
        elif t < ah:
            e = 1.0
        else:
            x = (t - ah) / d
            e = (1.0 - x) ** curve if x < 1.0 else 0.0
        out[i] = s * e * gain
    return out


# ---------------------------------------------------------------- effects

def _onepole_lp(buf, fc, sr):
    if fc >= sr * 0.49:
        return buf
    c = math.exp(-TWO_PI * fc / sr)
    y = 0.0
    out = [0.0] * len(buf)
    for i, x in enumerate(buf):
        y = (1.0 - c) * x + c * y
        out[i] = y
    return out


def _onepole_hp(buf, fc, sr):
    c = math.exp(-TWO_PI * fc / sr)
    y = 0.0
    xp = 0.0
    out = [0.0] * len(buf)
    for i, x in enumerate(buf):
        y = c * (y + x - xp)
        xp = x
        out[i] = y
    return out


def _drive(buf, amount):
    if amount <= 0:
        return buf
    k = 1.0 + amount * 9.0
    norm = 1.0 / math.tanh(k)
    th = math.tanh
    return [th(x * k) * norm for x in buf]


def _bitcrush(buf, bits, rate, sr):
    levels = 2 ** (max(int(bits), 2) - 1)
    step = max(sr / float(rate), 1.0) if rate else 1.0
    out = [0.0] * len(buf)
    acc = step
    held = 0.0
    for i, x in enumerate(buf):
        acc += 1.0
        if acc >= step:
            acc -= step
            held = round(x * levels) / levels
        out[i] = held
    return out


def _delay(buf, time_s, feedback, mix, sr):
    dn = max(int(time_s * sr), 1)
    feedback = min(max(feedback, 0.0), 0.9)
    tail = int(dn * math.log(0.001) / math.log(max(feedback, 0.05)))
    tail = min(tail, sr * 2)
    buf = buf + [0.0] * tail
    line = [0.0] * dn
    out = [0.0] * len(buf)
    j = 0
    for i, x in enumerate(buf):
        dly = line[j]
        line[j] = x + dly * feedback
        j += 1
        if j == dn:
            j = 0
        out[i] = x + dly * mix
    return out


def _reverb(buf, size, mix, damp, sr):
    """Small Schroeder reverb: 4 damped combs into 2 allpasses."""
    size = min(max(size, 0.0), 1.0)
    scale = sr / 44100.0
    comb_ms = (29.7, 37.1, 41.1, 43.7)
    comb_len = [max(int(ms * (0.6 + size) * 44.1 * scale), 1) for ms in comb_ms]
    fb = 0.5 + 0.38 * size
    longest = max(comb_len) / float(sr)
    rt60 = 3.0 * longest / -math.log10(fb)
    tail = int(sr * (rt60 + 0.05))
    src = buf + [0.0] * tail
    n = len(src)
    wet = [0.0] * n
    for L in comb_len:
        line = [0.0] * L
        j = 0
        lp = 0.0
        for i in range(n):
            y = line[j]
            lp = y * (1.0 - damp) + lp * damp
            line[j] = src[i] + lp * fb
            j += 1
            if j == L:
                j = 0
            wet[i] += y
    for ms, g in ((5.0, 0.7), (1.7, 0.7)):
        L = max(int(ms * 44.1 * scale), 1)
        line = [0.0] * L
        j = 0
        for i in range(n):
            bo = line[j]
            x = wet[i]
            y = -g * x + bo
            line[j] = x + g * y
            j += 1
            if j == L:
                j = 0
            wet[i] = y
    k = 0.25 * mix
    return [src[i] + wet[i] * k for i in range(n)]


def apply_fx(buf, fx, sr):
    if not fx:
        return buf
    if fx.get("drive"):
        buf = _drive(buf, float(fx["drive"]))
    bc = fx.get("bitcrush")
    if bc:
        buf = _bitcrush(buf, bc.get("bits", 8), bc.get("rate", 0), sr)
    if fx.get("highpass"):
        buf = _onepole_hp(buf, float(fx["highpass"]), sr)
    if fx.get("lowpass"):
        buf = _onepole_lp(buf, float(fx["lowpass"]), sr)
    dl = fx.get("delay")
    if dl and dl.get("mix", 0) > 0:
        buf = _delay(buf, float(dl.get("time", 0.12)), float(dl.get("feedback", 0.3)),
                     float(dl.get("mix", 0.25)), sr)
    rv = fx.get("reverb")
    if rv and rv.get("mix", 0) > 0:
        buf = _reverb(buf, float(rv.get("size", 0.4)), float(rv.get("mix", 0.2)),
                      float(rv.get("damp", 0.4)), sr)
    return buf


# ---------------------------------------------------------------- mastering

def momentary_loudness_db(buf, sr, window_s=0.05):
    """Max RMS over a sliding window, in dBFS. A cheap stand-in for momentary loudness."""
    w = max(int(window_s * sr), 1)
    if len(buf) <= w:
        ms = sum(x * x for x in buf) / max(len(buf), 1)
        return lin_to_db(math.sqrt(ms))
    acc = sum(x * x for x in buf[:w])
    best = acc
    for i in range(w, len(buf)):
        acc += buf[i] * buf[i] - buf[i - w] * buf[i - w]
        if acc > best:
            best = acc
    return lin_to_db(math.sqrt(max(best, 0.0) / w))


def _soft_limit(buf, ceiling):
    knee = 0.7 * ceiling
    span = ceiling - knee
    th = math.tanh
    out = [0.0] * len(buf)
    for i, x in enumerate(buf):
        ax = abs(x)
        if ax > knee:
            y = knee + span * th((ax - knee) / span)
            out[i] = y if x > 0 else -y
        else:
            out[i] = x
    return out


def finalize(buf, sr, loudness_db=-18.0, ceiling_db=-1.0):
    if not buf:
        return buf
    buf = _onepole_hp(buf, 20.0, sr)  # remove DC
    cur = momentary_loudness_db(buf, sr)
    if cur > -200:
        g = db_to_lin(loudness_db - cur)
        buf = [x * g for x in buf]
    ceiling = db_to_lin(ceiling_db)
    peak = max(abs(x) for x in buf)
    if peak > ceiling * db_to_lin(4.0):
        # too much overshoot to limit transparently: pull back first
        g = ceiling * db_to_lin(4.0) / peak
        buf = [x * g for x in buf]
        peak *= g
    if peak > 0.7 * ceiling:
        buf = _soft_limit(buf, ceiling)

    # trim the silent tail (below -50 dB of peak), keep 15 ms of air
    peak = max(abs(x) for x in buf) or 1.0
    thr = peak * 0.00316
    end = len(buf)
    while end > 1 and abs(buf[end - 1]) < thr:
        end -= 1
    end = min(len(buf), end + int(0.015 * sr))
    buf = buf[:end]

    # de-click: 1.5 ms fade in, 6 ms fade out
    fi = min(int(0.0015 * sr), len(buf))
    for i in range(fi):
        buf[i] *= i / fi
    fo = min(int(0.006 * sr), len(buf))
    for i in range(fo):
        buf[len(buf) - 1 - i] *= i / fo
    return buf


# ---------------------------------------------------------------- top level

def render(recipe: dict, sr: int = DEFAULT_SR, seed: int = 1) -> list:
    """Render a recipe to a list of floats in [-1, 1]."""
    layers = recipe.get("layers")
    if not layers:
        raise RecipeError("recipe needs at least one layer")
    rng = random.Random(seed)
    total = 0.0
    for L in layers:
        total = max(total, float(L.get("start", 0.0)) + layer_duration(L))
    if total > 10.0:
        raise RecipeError("recipe is %.1fs long; sound effects are capped at 10s" % total)
    mix = [0.0] * (int(total * sr) + 1)
    for L in layers:
        buf = render_layer(L, sr, rng)
        off = int(float(L.get("start", 0.0)) * sr)
        for i, x in enumerate(buf):
            j = off + i
            if j < len(mix):
                mix[j] += x
    mix = apply_fx(mix, recipe.get("fx"), sr)
    return finalize(mix, sr, float(recipe.get("loudness", -18.0)),
                    float(recipe.get("ceiling", -1.0)))


def write_wav(path: str, buf: list, sr: int = DEFAULT_SR) -> None:
    data = array("h", (int(max(-1.0, min(1.0, x)) * 32767.0) for x in buf))
    if sys.byteorder == "big":
        data.byteswap()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


def read_wav(path: str):
    """Read a mono or stereo 8/16/24-bit PCM wav as (floats, sample_rate). Stereo is averaged."""
    with wave.open(path, "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        a = array("h")
        a.frombytes(raw)
        if sys.byteorder == "big":
            a.byteswap()
        vals = [x / 32768.0 for x in a]
    elif sw == 1:
        vals = [(b - 128) / 128.0 for b in raw]
    elif sw == 3:
        vals = []
        for i in range(0, len(raw), 3):
            v = struct.unpack("<i", raw[i:i + 3] + (b"\xff" if raw[i + 2] & 0x80 else b"\x00"))[0]
            vals.append(v / 8388608.0)
    else:
        raise ValueError("unsupported sample width %d" % sw)
    if ch > 1:
        vals = [sum(vals[i:i + ch]) / ch for i in range(0, len(vals), ch)]
    return vals, sr
