"""Palettes: the shared sonic identity of a whole sound pack.

Every sound in a pack is built from the same palette, so a coin, a button click and the
level-complete jingle sound like they belong to the same game: same key and scale,
same instrument family, same brightness, same room.
"""
from __future__ import annotations

MAJOR_PENTA = [0, 2, 4, 7, 9]
MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR_PENTA = [0, 3, 5, 7, 10]
LYDIAN = [0, 2, 4, 6, 7, 9, 11]

PALETTES = {
    "retro": {
        "desc": "8-bit chiptune: pulse-wave leads, crunchy noise, bit-crushed.",
        "good_for": "pixel-art platformers, NES/Game Boy homages, game jams",
        "root": "C5",
        "scale": MAJOR_PENTA,
        "lead": {"wave": "square", "duty": 0.5},
        "bell": {"wave": "square", "duty": 0.25},
        "soft": {"wave": "triangle"},
        "noise": {"wave": "crunch"},
        "brightness": 1.0,
        "snap": 0.85,
        "fx": {"bitcrush": {"bits": 8, "rate": 22050}},
    },
    "arcade": {
        "desc": "Punchy 16-bit arcade: filtered saws, chunky square bells, a little drive and room.",
        "good_for": "shoot 'em ups, action, beat 'em ups, roguelites",
        "root": "D5",
        "scale": MAJOR_PENTA,
        "lead": {"wave": "saw", "filter": {"type": "lp", "cutoff": 5000, "q": 1.2}},
        "bell": {"wave": "square", "duty": 0.5, "filter": {"type": "lp", "cutoff": 6000, "q": 0.8}},
        "soft": {"wave": "triangle"},
        "noise": {"wave": "noise", "color": "white"},
        "brightness": 1.0,
        "snap": 1.0,
        "fx": {"drive": 0.25, "reverb": {"size": 0.2, "mix": 0.12, "damp": 0.5}},
    },
    "cozy": {
        "desc": "Soft and warm: sine and FM bells, gentle attacks, rounded highs, a soft room.",
        "good_for": "puzzle, match-3, merge, idle, farming, casual mobile",
        "root": "F5",
        "scale": MAJOR_PENTA,
        "lead": {"wave": "sine"},
        "bell": {"wave": "fm", "fm": {"ratio": 3.0, "index": 1.4, "index_end": 0.2}},
        "soft": {"wave": "sine"},
        "noise": {"wave": "noise", "color": "pink"},
        "brightness": 0.7,
        "snap": 1.15,
        "fx": {"lowpass": 9000, "reverb": {"size": 0.45, "mix": 0.22, "damp": 0.55}},
    },
    "bubbly": {
        "desc": "Cute and toy-like: bouncy triangle blips, glassy FM bells, springy pitch bends.",
        "good_for": "kids games, party games, cute characters, pets",
        "root": "G5",
        "scale": MAJOR_PENTA,
        "lead": {"wave": "triangle"},
        "bell": {"wave": "fm", "fm": {"ratio": 2.0, "index": 2.4, "index_end": 0.4}},
        "soft": {"wave": "sine"},
        "noise": {"wave": "noise", "color": "white"},
        "brightness": 1.1,
        "snap": 0.9,
        "fx": {"delay": {"time": 0.07, "feedback": 0.2, "mix": 0.18}},
    },
    "scifi": {
        "desc": "Synthetic and spacey: resonant filtered saws, inharmonic FM, echoing delays.",
        "good_for": "space shooters, cyberpunk, robots, tech UIs",
        "root": "E5",
        "scale": LYDIAN,
        "lead": {"wave": "saw", "filter": {"type": "lp", "cutoff": 3500, "q": 3.0}},
        "bell": {"wave": "fm", "fm": {"ratio": 1.41, "index": 2.0, "index_end": 0.3}},
        "soft": {"wave": "sine"},
        "noise": {"wave": "noise", "color": "white"},
        "brightness": 1.0,
        "snap": 1.0,
        "fx": {"delay": {"time": 0.11, "feedback": 0.35, "mix": 0.22},
               "reverb": {"size": 0.3, "mix": 0.1, "damp": 0.3}},
    },
    "minimal": {
        "desc": "Clean and quiet: short sine ticks and soft FM chimes, nothing gets in the way.",
        "good_for": "menus, card and board games, word games, apps, utilities",
        "root": "A5",
        "scale": MAJOR_PENTA,
        "lead": {"wave": "sine"},
        "bell": {"wave": "fm", "fm": {"ratio": 2.0, "index": 0.8, "index_end": 0.1}},
        "soft": {"wave": "sine"},
        "noise": {"wave": "noise", "color": "white"},
        "brightness": 0.85,
        "snap": 0.8,
        "fx": {"reverb": {"size": 0.15, "mix": 0.08, "damp": 0.6}},
    },
}


def get(name: str) -> dict:
    if name not in PALETTES:
        raise KeyError("unknown palette %r (choose from %s)" % (name, ", ".join(PALETTES)))
    return PALETTES[name]
