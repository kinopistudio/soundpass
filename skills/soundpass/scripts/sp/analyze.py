"""Let an agent 'hear' a sound: measurements, a plain-words description and a text spectrogram."""
from __future__ import annotations

import math

from .synth import lin_to_db, momentary_loudness_db

N_BANDS = 36
F_LO, F_HI = 60.0, 14000.0
FRAME = 1024
HOP_S = 0.02
SHADES = " .:-=+*#%@"


def _band_freqs():
    r = (F_HI / F_LO) ** (1.0 / (N_BANDS - 1))
    return [F_LO * r ** i for i in range(N_BANDS)]


def _spectrogram(buf, sr):
    freqs = _band_freqs()
    hop = max(int(HOP_S * sr), 1)
    win = [0.5 - 0.5 * math.cos(2 * math.pi * i / (FRAME - 1)) for i in range(FRAME)]
    coefs = [2.0 * math.cos(2.0 * math.pi * f / sr) for f in freqs]
    frames = []
    pos = 0
    n = len(buf)
    while pos < n:
        seg = buf[pos:pos + FRAME]
        if len(seg) < FRAME:
            seg = seg + [0.0] * (FRAME - len(seg))
        x = [seg[i] * win[i] for i in range(FRAME)]
        row = []
        for c in coefs:
            s1 = s2 = 0.0
            for v in x:
                s0 = v + c * s1 - s2
                s2 = s1
                s1 = s0
            p = s1 * s1 + s2 * s2 - c * s1 * s2
            row.append(max(p, 0.0))
        frames.append(row)
        pos += hop
    return freqs, frames


def _dominant(freqs, row):
    i = max(range(len(row)), key=lambda k: row[k])
    if 0 < i < len(row) - 1:
        a, b, c = (math.log(row[i - 1] + 1e-20), math.log(row[i] + 1e-20), math.log(row[i + 1] + 1e-20))
        den = a - 2 * b + c
        off = 0.5 * (a - c) / den if den else 0.0
        off = max(-0.5, min(0.5, off))
        r = freqs[1] / freqs[0]
        return freqs[i] * r ** off
    return freqs[i]


def _fmt_hz(f):
    return "%.1fkHz" % (f / 1000.0) if f >= 1000 else "%dHz" % round(f)


def analyze(buf, sr):
    n = len(buf)
    dur = n / float(sr)
    peak = max((abs(x) for x in buf), default=0.0)
    rms = math.sqrt(sum(x * x for x in buf) / max(n, 1))
    dc = sum(buf) / max(n, 1)

    # envelope in 5 ms blocks
    blk = max(int(0.005 * sr), 1)
    env = [max((abs(x) for x in buf[i:i + blk]), default=0.0) for i in range(0, n, blk)]
    epk = max(env) if env else 0.0
    attack_ms = next((i * 5.0 for i, v in enumerate(env) if v >= 0.9 * epk), 0.0)
    ipk = env.index(epk) if env else 0
    tail_ms = 0.0
    for i in range(len(env) - 1, ipk, -1):
        if env[i] >= epk * 0.01:  # -40 dB
            tail_ms = (i - ipk) * 5.0
            break

    freqs, frames = _spectrogram(buf, sr)
    energies = [sum(r) for r in frames]
    emax = max(energies) if energies else 0.0
    loud = [i for i, e in enumerate(energies) if e > emax * 0.01]
    total = [0.0] * N_BANDS
    for r in frames:
        for k, v in enumerate(r):
            total[k] += v
    tsum = sum(total) or 1.0
    centroid = math.exp(sum(math.log(f) * v for f, v in zip(freqs, total)) / tsum)
    third = N_BANDS // 3
    low = sum(total[:third]) / tsum
    mid = sum(total[third:2 * third]) / tsum
    high = sum(total[2 * third:]) / tsum
    # tonality: how peaky the spectrum is (1 = pure tone, ~0 = flat noise)
    peaky = []
    for i in loud:
        r = frames[i]
        m = sum(r) / len(r)
        if m > 0:
            peaky.append(max(r) / (m * len(r)))
    tonality = sum(peaky) / len(peaky) if peaky else 0.0

    contour = [_dominant(freqs, frames[i]) for i in loud]
    if len(contour) >= 2:
        f_start, f_end = contour[0], contour[-1]
        f_max, f_min = max(contour), min(contour)
        semis = 12.0 * math.log(f_end / f_start, 2)
        if abs(semis) < 2 and 12.0 * math.log(f_max / f_min, 2) < 3:
            motion = "steady"
        elif semis >= 2:
            motion = "rising"
        elif semis <= -2:
            motion = "falling"
        else:
            motion = "wobbling"
    else:
        f_start = f_end = contour[0] if contour else 0.0
        semis = 0.0
        motion = "steady"

    issues = []
    if peak >= 0.999:
        issues.append("clipping: peak at 0 dBFS")
    if n and abs(buf[0]) > 0.02:
        issues.append("click risk: starts at %.2f" % buf[0])
    if n and abs(buf[-1]) > 0.02:
        issues.append("click risk: ends at %.2f" % buf[-1])
    if abs(dc) > 0.01:
        issues.append("DC offset %.3f" % dc)
    if dur > 3.0:
        issues.append("long for an SFX (%.1fs)" % dur)

    return {
        "duration_s": round(dur, 3),
        "peak_dbfs": round(lin_to_db(peak), 1),
        "rms_dbfs": round(lin_to_db(rms), 1),
        "loudness_dbfs": round(momentary_loudness_db(buf, sr), 1),
        "attack_ms": round(attack_ms, 1),
        "tail_ms": round(tail_ms, 1),
        "brightness_hz": round(centroid),
        "balance": {"low": round(low, 2), "mid": round(mid, 2), "high": round(high, 2)},
        "tonality": round(min(tonality, 1.0), 2),
        "pitch": {"start_hz": round(f_start), "end_hz": round(f_end), "semitones": round(semis, 1),
                  "motion": motion},
        "issues": issues,
        "_freqs": freqs,
        "_frames": frames,
    }


def describe(a):
    words = []
    d = a["duration_s"]
    words.append("very short" if d < 0.08 else "short" if d < 0.3 else "medium" if d < 0.8 else "long")
    words.append("snappy attack" if a["attack_ms"] <= 10 else "soft attack" if a["attack_ms"] > 40 else "quick attack")
    t = a["tonality"]
    words.append("tonal" if t > 0.35 else "noisy" if t < 0.15 else "part tone, part noise")
    c = a["brightness_hz"]
    words.append("dark" if c < 500 else "warm" if c < 1200 else "bright" if c < 3500 else "very bright / harsh")
    p = a["pitch"]
    if t > 0.15:
        if p["motion"] in ("rising", "falling"):
            words.append("pitch %s %s -> %s (%+.0f st)" % (p["motion"], _fmt_hz(p["start_hz"]),
                                                          _fmt_hz(p["end_hz"]), p["semitones"]))
        else:
            words.append("pitch %s around %s" % (p["motion"], _fmt_hz(p["start_hz"])))
    return ", ".join(words)


def ascii_spectrogram(a, width=56, rows=12):
    freqs, frames = a["_freqs"], a["_frames"]
    if not frames:
        return ""
    per_row = len(freqs) // rows
    cols = min(width, len(frames))
    grid = []
    vmax = 1e-20
    for c in range(cols):
        f0 = int(c * len(frames) / cols)
        f1 = max(int((c + 1) * len(frames) / cols), f0 + 1)
        col = []
        for r in range(rows):
            b0, b1 = r * per_row, (r + 1) * per_row
            v = max(max(fr[b0:b1]) for fr in frames[f0:f1])
            col.append(v)
            vmax = max(vmax, v)
        grid.append(col)
    lines = []
    for r in range(rows - 1, -1, -1):
        label = _fmt_hz(freqs[r * per_row]).rjust(7)
        chars = []
        for c in range(cols):
            db = 10.0 * math.log10(grid[c][r] / vmax + 1e-12)
            lvl = int((db + 60.0) / 60.0 * (len(SHADES) - 1))
            chars.append(SHADES[max(0, min(len(SHADES) - 1, lvl))])
        lines.append("%s |%s" % (label, "".join(chars)))
    lines.append(" " * 8 + "+" + "-" * cols + "> %.2fs" % a["duration_s"])
    return "\n".join(lines)


def report(name, a, spectrogram=True):
    out = ["%s" % name,
           "  %s" % describe(a),
           "  duration %.3fs | loudness %.1f dBFS | peak %.1f dBFS | attack %.0fms | tail %.0fms" % (
               a["duration_s"], a["loudness_dbfs"], a["peak_dbfs"], a["attack_ms"], a["tail_ms"]),
           "  brightness %s | low/mid/high %.2f/%.2f/%.2f | tonality %.2f" % (
               _fmt_hz(a["brightness_hz"]), a["balance"]["low"], a["balance"]["mid"],
               a["balance"]["high"], a["tonality"])]
    if a["issues"]:
        out.append("  ISSUES: " + "; ".join(a["issues"]))
    if spectrogram:
        out.append(ascii_spectrogram(a))
    return "\n".join(out)


def public(a):
    return {k: v for k, v in a.items() if not k.startswith("_")}
