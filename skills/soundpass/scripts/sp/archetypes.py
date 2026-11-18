"""Archetypes: sound designs for common game events, written against a palette.

Each archetype is a function that takes a Ctx and returns a recipe (see synth.py).
The Ctx resolves the palette's instruments, key, brightness and timing, so one archetype
yields a coherent sound in every palette.
"""
from __future__ import annotations

import copy
import random

from . import palettes
from .synth import midi_to_hz, note_to_midi

REGISTRY = {}

# How much of the palette's room (reverb / delay) each kind of sound gets.
# UI and footsteps fire constantly and must stay dry and tight; jingles get the full room.
ROOM = {"ui": 0.35, "movement": 0.4, "combat": 0.7, "pickup": 0.8, "puzzle": 0.6, "jingle": 1.0}


def arch(name, category, loudness, desc, keywords, ladder=False):
    def deco(fn):
        REGISTRY[name] = {
            "name": name,
            "fn": fn,
            "category": category,
            "loudness": loudness,
            "desc": desc,
            "keywords": keywords,
            "ladder": ladder,
        }
        return fn
    return deco


def _merge(a, b):
    out = copy.deepcopy(a) if a else {}
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class Ctx:
    """Everything an archetype needs to know about the palette and the requested tweaks."""

    def __init__(self, palette_name, tweak=None, variant=0, seed=1, key=None, level=0):
        self.name = palette_name
        self.p = copy.deepcopy(palettes.get(palette_name))
        tweak = tweak or {}
        self.tweak = tweak
        self.rng = random.Random(seed * 7919 + variant * 104729)
        root = key or self.p["root"]
        if not any(ch.isdigit() for ch in root):
            root = root + "".join(ch for ch in self.p["root"] if ch.isdigit() or ch == "-")
        self.root = note_to_midi(root)
        self.scale = self.p["scale"]
        self.level = level
        self.length = float(tweak.get("length", 1.0))
        self.bright = self.p["brightness"] * float(tweak.get("brightness", 1.0))
        semis = float(tweak.get("pitch", 0.0))
        if variant and not tweak.get("no_jitter"):
            jitter = float(tweak.get("jitter", 1.0))
            semis += self.rng.uniform(-0.3, 0.3) * jitter
            self.length *= 1.0 + self.rng.uniform(-0.07, 0.07) * jitter
            self.bright *= 1.0 + self.rng.uniform(-0.08, 0.08) * jitter
        self.mult = 2.0 ** (semis / 12.0)
        self.snap = self.p["snap"]

    # ---- pitch
    def note(self, degree, octave=0):
        """Frequency of a scale degree, relative to the palette root (degree 0)."""
        n = len(self.scale)
        o, i = divmod(int(degree), n)
        return midi_to_hz(self.root + self.scale[i] + 12 * (o + octave))

    @staticmethod
    def up(freq, semitones):
        return freq * 2.0 ** (semitones / 12.0)

    # ---- time
    def S(self, s):
        """Scale a start / step time."""
        return s * self.length

    def T(self, s):
        """Scale a hold / decay time (palettes differ in how snappy they are)."""
        return s * self.length * self.snap

    def cut(self, hz):
        return max(40.0, min(hz * self.bright, 18000.0))

    # ---- layers
    def voice(self, role, freq, decay=0.2, attack=0.002, hold=0.0, curve=2.0, gain=1.0,
              start=0.0, freq_end=None, **extra):
        """A tonal layer using one of the palette's instruments: lead, bell or soft."""
        layer = copy.deepcopy(self.p[role])
        if "filter" in layer and "filter" not in extra:
            f = layer["filter"]
            f["cutoff"] = self.cut(f["cutoff"])
            if "cutoff_end" in f:
                f["cutoff_end"] = self.cut(f["cutoff_end"])
        layer["freq"] = round(freq * self.mult, 3)
        if freq_end is not None:
            layer["freq_end"] = round(freq_end * self.mult, 3)
        if "slide_time" in extra:
            extra["slide_time"] = self.T(extra["slide_time"])
        if "steps" in extra:
            extra["steps"] = [[self.S(t), s] for t, s in extra["steps"]]
        layer["env"] = {"attack": attack, "hold": self.T(hold), "decay": self.T(decay), "curve": curve}
        layer["gain"] = gain
        layer["start"] = self.S(start)
        layer.update(extra)
        return layer

    def tone(self, wave, freq, **kw):
        """A tonal layer with an explicit waveform (ignores the palette's instruments)."""
        self.p["_explicit"] = {"wave": wave}
        return self.voice("_explicit", freq, **kw)

    def noise(self, decay=0.1, attack=0.001, hold=0.0, curve=2.0, gain=1.0, start=0.0,
              filter=None, grit=800.0, grit_end=None, color=None):
        """A noise layer using the palette's noise source. `grit` only matters for 'crunch'."""
        layer = copy.deepcopy(self.p["noise"])
        if layer["wave"] == "crunch":
            layer["freq"] = grit
            if grit_end:
                layer["freq_end"] = grit_end
        if color:
            layer["color"] = color
        if filter:
            f = dict(filter)
            f["cutoff"] = self.cut(f["cutoff"])
            if "cutoff_end" in f:
                f["cutoff_end"] = self.cut(f["cutoff_end"])
            layer["filter"] = f
        layer["env"] = {"attack": attack, "hold": self.T(hold), "decay": self.T(decay), "curve": curve}
        layer["gain"] = gain
        layer["start"] = self.S(start)
        return layer

    def fx(self, extra=None, room=1.0):
        out = _merge(self.p.get("fx", {}), extra)
        room *= float(self.tweak.get("room", 1.0))
        if "reverb" in out:
            out["reverb"]["mix"] = out["reverb"].get("mix", 0.0) * room
            out["reverb"]["size"] = out["reverb"].get("size", 0.4) * (0.5 + 0.5 * min(room, 1.0))
        if "delay" in out:
            out["delay"]["mix"] = out["delay"].get("mix", 0.0) * room
            out["delay"]["feedback"] = out["delay"].get("feedback", 0.3) * min(room, 1.0) ** 0.5
        add = float(self.tweak.get("reverb", 0.0))
        if add:
            rv = out.setdefault("reverb", {"size": 0.4, "mix": 0.0, "damp": 0.5})
            rv["mix"] = max(0.0, rv.get("mix", 0.0) + add)
        return out


def build(name, palette, tweak=None, variant=0, seed=1, key=None):
    """Build the recipe for archetype `name` in `palette`."""
    if name not in REGISTRY:
        raise KeyError("unknown archetype %r" % name)
    meta = REGISTRY[name]
    tweak = dict(tweak or {})
    level = variant
    if meta["ladder"]:
        tweak["no_jitter"] = True
        level = variant + int(tweak.get("start_level", 0))
    c = Ctx(palette, tweak, variant=variant, seed=seed, key=key, level=level)
    layers, fx = meta["fn"](c)
    return {
        "layers": layers,
        "fx": c.fx(fx, ROOM.get(meta["category"], 1.0)),
        "loudness": meta["loudness"] + float(tweak.get("gain_db", 0.0)),
    }


# =================================================================== pickups

@arch("coin", "pickup", -18, "Coin or small pickup: the bright two-note 'ding-ding'.",
      ["coin", "collect", "pickup", "pick", "loot", "money", "gold", "cash", "score", "point"])
def coin(c):
    f = c.note(4, 0)
    L = [c.voice("bell", f, hold=0.05, decay=0.32, curve=3.0, steps=[[0, 0], [0.055, 5]])]
    L.append(c.voice("soft", c.up(f, 17), start=0.055, decay=0.16, curve=3.0, gain=0.22))
    return L, None


@arch("gem", "pickup", -18, "Gem, star or rare pickup: a sparkling rising arpeggio.",
      ["gem", "diamond", "crystal", "jewel", "rare", "treasure", "chest"])
def gem(c):
    L = []
    for i, deg in enumerate((0, 2, 4, 5)):
        L.append(c.voice("bell", c.note(deg, 0), start=0.05 * i, decay=0.42, curve=2.5,
                         gain=0.8 if i < 3 else 1.0))
    L.append(c.tone("fm", c.note(0, 2), start=0.15, decay=0.5, curve=2.0, gain=0.25,
                    fm={"ratio": 3.5, "index": 1.0, "index_end": 0.0}))
    return L, {"reverb": {"size": 0.35, "mix": 0.15}}


@arch("powerup", "pickup", -17, "Power-up: a fast climbing arpeggio that keeps going.",
      ["powerup", "power", "boost", "upgrade", "levelup", "buff", "mushroom", "grow"])
def powerup(c):
    f = c.note(0, -1)
    steps = [[0.045 * i, s] for i, s in enumerate((0, 4, 7, 12, 16, 19, 24))]
    L = [c.voice("lead", f, hold=0.3, decay=0.16, curve=1.5, steps=steps,
                 vibrato={"rate": 9, "depth": 0.25, "delay": 0.3})]
    L.append(c.voice("soft", c.up(f, 12), hold=0.3, decay=0.16, curve=1.5, gain=0.3, steps=steps))
    return L, None


@arch("heal", "pickup", -21, "Heal or restore: soft rising notes with a gentle shimmer.",
      ["heal", "health", "hp", "restore", "regen", "potion", "cure", "revive"])
def heal(c):
    L = []
    for i, deg in enumerate((0, 2, 4, 5)):
        L.append(c.voice("soft", c.note(deg, 0), attack=0.012, start=0.07 * i, decay=0.35,
                         curve=1.8, gain=0.7))
    L.append(c.voice("bell", c.note(0, 2), attack=0.01, start=0.21, decay=0.55, curve=2.0, gain=0.3))
    return L, {"reverb": {"size": 0.5, "mix": 0.25}}


# ================================================================= movement

@arch("jump", "movement", -20, "Jump: a quick upward pitch sweep.",
      ["jump", "hop", "leap", "jumped"])
def jump(c):
    f = c.note(0, -1)
    return [c.voice("lead", f, freq_end=f * 2.4, slide_time=0.14, slide_shape=0.6,
                    hold=0.02, decay=0.16, curve=1.6)], None


@arch("land", "movement", -21, "Landing: a soft low thump.",
      ["land", "landed", "grounded", "ground", "fall", "touchdown"])
def land(c):
    return [
        c.tone("sine", 150, freq_end=50, slide_time=0.08, decay=0.12, curve=2.5),
        c.noise(decay=0.05, curve=2.0, gain=0.5, grit=300,
                filter={"type": "lp", "cutoff": 900, "cutoff_end": 300}),
    ], None


@arch("footstep", "movement", -26, "Footstep: a short soft scuff (use variants!).",
      ["footstep", "step", "walk", "run", "stomp"])
def footstep(c):
    cf = c.rng.uniform(900, 1500)
    return [
        c.noise(decay=0.045, curve=3.0, grit=600,
                filter={"type": "bp", "cutoff": cf, "q": 1.2}),
        c.tone("sine", 110, freq_end=70, decay=0.04, curve=2.0, gain=0.5),
    ], None


@arch("dash", "movement", -21, "Dash, swipe or whoosh: a quick swell of filtered air.",
      ["dash", "whoosh", "swipe", "swing", "slash", "throw", "roll", "dodge", "fly"])
def dash(c):
    return [c.noise(attack=c.T(0.05), decay=0.18, curve=1.3, grit=400, grit_end=1600,
                    filter={"type": "bp", "cutoff": 500, "cutoff_end": 3500, "q": 1.4})], None


@arch("bounce", "movement", -20, "Bounce or spring: a wobbly 'boing'.",
      ["bounce", "spring", "boing", "trampoline", "rebound"])
def bounce(c):
    f = c.note(0, -1)
    return [c.voice("soft", f, freq_end=f * 1.8, slide_time=0.06, slide_shape=0.5,
                    decay=0.28, curve=1.6, vibrato={"rate": 16, "depth": 1.2})], None


# =================================================================== combat

@arch("shoot", "combat", -18, "Shoot or laser: a fast falling zap.",
      ["shoot", "shot", "fire", "laser", "bullet", "gun", "blast", "cast", "spell", "projectile"])
def shoot(c):
    f = c.note(0, 1) * 1.5
    return [
        c.voice("lead", f, freq_end=f / 5.0, slide_time=0.16, slide_shape=0.5, decay=0.18, curve=1.4),
        c.noise(decay=0.015, curve=2.0, gain=0.4, grit=2000, filter={"type": "hp", "cutoff": 3000}),
    ], None


@arch("hit", "combat", -16, "Hit or impact on something else: a punchy thud with grit.",
      ["hit", "impact", "punch", "strike", "attack", "smash", "bump", "kick", "collide", "collision"])
def hit(c):
    return [
        c.noise(decay=0.09, curve=2.2, grit=1200, grit_end=300,
                filter={"type": "lp", "cutoff": 4000, "cutoff_end": 500}),
        c.tone("sine", 190, freq_end=60, decay=0.1, curve=2.0, gain=0.9),
    ], {"drive": 0.35}


@arch("hurt", "combat", -17, "Player takes damage: a rough falling 'ouch'.",
      ["hurt", "damage", "takedamage", "damaged", "injure", "ouch", "lifelost", "loselife"])
def hurt(c):
    f = c.note(4, -1)
    return [
        c.voice("lead", f, freq_end=f * 0.5, decay=0.22, curve=1.2, vibrato={"rate": 22, "depth": 0.6}),
        c.noise(decay=0.06, curve=2.0, gain=0.5, grit=700, filter={"type": "lp", "cutoff": 2500}),
    ], None


@arch("death", "combat", -17, "Death or defeat of a character: a long wobbling fall.",
      ["die", "death", "dead", "died", "kill", "killed", "destroyed", "defeat", "faint"])
def death(c):
    f = c.note(4, 0)
    return [
        c.voice("lead", f, freq_end=f / 4.0, slide_time=0.8, hold=0.1, decay=0.75, curve=1.2,
                vibrato={"rate": 9, "depth": 0.4}),
        c.voice("soft", f / 2.0, freq_end=f / 8.0, slide_time=0.8, hold=0.1, decay=0.75, curve=1.2,
                gain=0.4),
    ], None


@arch("explosion", "combat", -14, "Explosion: a big noisy boom with a sub drop.",
      ["explode", "explosion", "bomb", "boom", "blow", "detonate", "blast", "nuke"])
def explosion(c):
    return [
        c.noise(attack=0.003, decay=0.9, curve=1.8, grit=900, grit_end=120,
                filter={"type": "lp", "cutoff": 4000, "cutoff_end": 200}, color="pink", gain=1.3),
        c.noise(attack=0.001, decay=0.12, curve=2.0, gain=0.7, grit=2000,
                filter={"type": "lp", "cutoff": 7000}),
        c.tone("sine", 90, freq_end=35, decay=0.45, curve=1.5, gain=0.6),
    ], {"drive": 0.4, "reverb": {"size": 0.5, "mix": 0.2}}


@arch("break", "combat", -17, "Break or shatter: a crack plus scattered glassy pings.",
      ["break", "shatter", "crack", "smash", "crate", "glass", "destroy", "broken"])
def break_(c):
    L = [
        c.noise(decay=0.18, curve=2.5, grit=2500, filter={"type": "hp", "cutoff": 2000}),
        c.noise(decay=0.08, curve=2.0, gain=0.7, grit=500, filter={"type": "lp", "cutoff": 1200}),
    ]
    for _ in range(5):
        L.append(c.tone("fm", c.rng.uniform(2000, 5000), start=c.rng.uniform(0.0, 0.08),
                        decay=0.12, curve=2.5, gain=0.22, fm={"ratio": 2.76, "index": 1.5}))
    return L, None


# ======================================================================= UI

@arch("ui_click", "ui", -26, "Button press: a tight, short tick.",
      ["click", "tap", "press", "button", "onclick", "onpressed", "ontap", "select"])
def ui_click(c):
    return [
        c.voice("bell", c.note(2, 1), decay=0.035, curve=3.0, gain=0.9),
        c.noise(decay=0.008, curve=2.0, gain=0.35, grit=3000, filter={"type": "hp", "cutoff": 4000}),
    ], None


@arch("ui_hover", "ui", -32, "Hover or focus change: the quietest tick.",
      ["hover", "focus", "highlight", "pointerenter", "mouseenter", "navigate"])
def ui_hover(c):
    return [c.voice("soft", c.note(4, 1), decay=0.025, curve=3.0)], None


@arch("ui_confirm", "ui", -22, "Confirm or OK: two notes going up.",
      ["confirm", "ok", "accept", "submit", "apply", "save", "yes", "done", "playbutton", "startbutton"])
def ui_confirm(c):
    return [
        c.voice("bell", c.note(0, 1), decay=0.12, curve=2.5),
        c.voice("bell", c.note(3, 1), start=0.07, decay=0.22, curve=2.5),
    ], None


@arch("ui_back", "ui", -24, "Back or cancel: two notes going down, a bit softer.",
      ["back", "cancel", "return", "no", "dismiss", "exit", "previous"])
def ui_back(c):
    return [
        c.voice("bell", c.note(3, 0), decay=0.1, curve=2.5, gain=0.85),
        c.voice("bell", c.note(0, 0), start=0.06, decay=0.16, curve=2.5, gain=0.85),
    ], None


@arch("ui_toggle", "ui", -26, "Toggle or switch: a small upward flick.",
      ["toggle", "switch", "checkbox", "check", "tick", "mute", "option", "setting"])
def ui_toggle(c):
    f = c.note(2, 1)
    return [
        c.voice("soft", f, freq_end=f * 1.25, slide_time=0.03, decay=0.05, curve=2.0),
        c.noise(decay=0.006, curve=2.0, gain=0.3, grit=3000, filter={"type": "hp", "cutoff": 4000}),
    ], None


@arch("ui_error", "ui", -21, "Error, denied or invalid move: a low double buzz.",
      ["error", "invalid", "denied", "deny", "wrong", "fail", "failed", "locked", "cannot", "notenough"])
def ui_error(c):
    f = c.note(0, -1) * 0.75
    filt = {"type": "lp", "cutoff": c.cut(1800), "q": 0.9}
    L = []
    for st in (0.0, 0.11):
        L.append(c.voice("lead", f, start=st, hold=0.06, decay=0.05, curve=1.0, filter=filt))
        L.append(c.voice("lead", c.up(f, -1), start=st, hold=0.06, decay=0.05, curve=1.0,
                         gain=0.6, filter=filt))
    return L, None


@arch("ui_popup", "ui", -24, "Panel, dialog or menu opens: a quick rising swoop and blip.",
      ["popup", "open", "dialog", "modal", "panel", "menu", "show", "window", "appear"])
def ui_popup(c):
    return [
        c.voice("soft", 280, freq_end=760, slide_time=0.09, slide_shape=0.5, decay=0.1, curve=2.0),
        c.voice("bell", c.note(4, 1), start=0.06, decay=0.15, curve=2.5, gain=0.5),
    ], None


@arch("ui_close", "ui", -25, "Panel or dialog closes: a quick falling swoop.",
      ["close", "hide", "collapse", "disappear"])
def ui_close(c):
    return [c.voice("soft", 700, freq_end=260, slide_time=0.09, slide_shape=1.5, decay=0.09,
                    curve=2.0, gain=0.9)], None


@arch("notification", "ui", -20, "Notification, message or alert: a friendly two-tone chime.",
      ["notify", "notification", "message", "alert", "reminder", "inbox", "mail", "ping", "badge"])
def notification(c):
    return [
        c.voice("bell", c.note(0, 1), decay=0.6, curve=2.0),
        c.voice("bell", c.note(2, 1), start=0.12, decay=0.8, curve=2.0),
    ], {"reverb": {"size": 0.4, "mix": 0.15}}


@arch("purchase", "ui", -18, "Purchase, reward claim or 'cha-ching'.",
      ["buy", "purchase", "shop", "store", "iap", "spend", "claim", "reward", "redeem", "sell"])
def purchase(c):
    L = []
    for i, (deg, octv) in enumerate(((0, 1), (2, 1), (4, 1), (0, 2))):
        L.append(c.voice("bell", c.note(deg, octv), start=0.04 * i, decay=0.3, curve=2.5,
                         gain=0.8 if i < 3 else 1.0))
    L.append(c.noise(attack=0.005, start=0.12, decay=0.25, curve=2.0, gain=0.2, grit=5000,
                     filter={"type": "hp", "cutoff": 6000}))
    return L, None


@arch("unlock", "ui", -18, "Unlock or new item: a rising sweep that blooms into a chord.",
      ["unlock", "unlocked", "new", "achievement", "discover", "open_chest", "earn"])
def unlock(c):
    L = [c.voice("soft", 300, freq_end=1200, slide_time=0.25, slide_shape=0.7, attack=0.02,
                 decay=0.25, curve=1.5, gain=0.6)]
    for deg in (0, 2, 4):
        L.append(c.voice("bell", c.note(deg, 1), start=0.2, decay=0.7, curve=2.0, gain=0.5))
    return L, {"reverb": {"size": 0.45, "mix": 0.2}}


# ================================================================== puzzle

@arch("match", "puzzle", -20, "Match, pop or tile clear: a bubbly pop with a note.",
      ["match", "clear", "pop", "merge", "combine", "line", "burst", "eliminate", "solved"])
def match(c):
    return [
        c.voice("soft", 380, freq_end=900, slide_time=0.03, decay=0.07, curve=2.0),
        c.voice("bell", c.note(2, 1), start=0.015, decay=0.18, curve=2.5, gain=0.6),
    ], None


@arch("combo", "puzzle", -19, "Combo / streak ladder: each variant is one scale step higher.",
      ["combo", "streak", "chain", "multiplier", "cascade", "consecutive"], ladder=True)
def combo(c):
    f = c.note(c.level, 0)
    return [
        c.voice("soft", f * 0.5, freq_end=f, slide_time=0.03, decay=0.07, curve=2.0, gain=0.7),
        c.voice("bell", f, start=0.012, decay=0.25, curve=2.5),
        c.voice("bell", f * 2.0, start=0.012, decay=0.15, curve=3.0, gain=0.25),
    ], None


@arch("place", "puzzle", -24, "Place, drop or snap a piece into position: a woody tock.",
      ["place", "drop", "snap", "put", "release", "dock", "slot", "build"])
def place(c):
    return [
        c.tone("sine", 900, freq_end=600, slide_time=0.02, decay=0.03, curve=3.0),
        c.noise(decay=0.02, curve=2.0, gain=0.5, grit=1500,
                filter={"type": "bp", "cutoff": 2200, "q": 1.5}),
        c.tone("sine", 140, freq_end=90, decay=0.05, curve=2.0, gain=0.5),
    ], None


@arch("swap", "puzzle", -24, "Swap two pieces: two blips crossing over.",
      ["swap", "switch_tiles", "exchange", "shuffle", "rotate", "flip", "move", "drag"])
def swap(c):
    return [
        c.voice("soft", 500, freq_end=800, slide_time=0.05, decay=0.06, curve=2.0),
        c.voice("soft", 800, freq_end=500, slide_time=0.05, start=0.05, decay=0.06, curve=2.0),
    ], None


@arch("star", "puzzle", -18, "Rating star ladder (1, 2, 3 stars): each variant rings higher.",
      ["star", "stars", "rating", "rank", "grade", "medal"], ladder=True)
def star(c):
    f = c.note(2 * c.level, 1)
    return [
        c.voice("bell", f, decay=0.5, curve=2.0),
        c.voice("soft", f * 2.0, decay=0.3, curve=2.5, gain=0.3),
        c.noise(attack=0.005, decay=0.2, curve=2.0, gain=0.15, grit=5000,
                filter={"type": "hp", "cutoff": 7000}),
    ], {"reverb": {"size": 0.35, "mix": 0.15}}


@arch("countdown_tick", "puzzle", -21, "Countdown tick (3, 2, 1...) or timer warning.",
      ["countdown", "tick", "timer", "clock", "seconds", "hurry", "warning"])
def countdown_tick(c):
    return [c.voice("bell", c.note(0, 1), decay=0.12, curve=3.0)], None


@arch("countdown_go", "puzzle", -17, "The 'GO!' after a countdown: higher and longer.",
      ["go", "begin", "start_round", "fight", "roundstart"])
def countdown_go(c):
    return [
        c.voice("bell", c.note(0, 2), hold=0.1, decay=0.5, curve=2.0),
        c.voice("lead", c.note(0, 1), hold=0.1, decay=0.5, curve=2.0, gain=0.4),
    ], None


# ================================================================== jingles

@arch("level_complete", "jingle", -16, "Level complete or victory: a short rising fanfare.",
      ["win", "victory", "complete", "levelcomplete", "cleared", "success", "finish", "goal", "won"])
def level_complete(c):
    L = []
    for i, deg in enumerate((0, 2, 4)):
        L.append(c.voice("lead", c.note(deg, 0), start=0.09 * i, decay=0.2, curve=2.0, gain=0.8))
    t = 0.27
    L.append(c.voice("lead", c.note(0, 1), start=t, hold=0.25, decay=0.5, curve=1.8,
                     vibrato={"rate": 6, "depth": 0.15, "delay": 0.15}))
    L.append(c.voice("bell", c.note(2, 1), start=t, hold=0.1, decay=0.6, curve=2.0, gain=0.45))
    L.append(c.voice("bell", c.note(4, 1), start=t, hold=0.1, decay=0.6, curve=2.0, gain=0.45))
    L.append(c.voice("soft", c.note(0, -1), start=t, hold=0.2, decay=0.5, curve=2.0, gain=0.5))
    return L, {"reverb": {"size": 0.45, "mix": 0.15}}


@arch("game_over", "jingle", -18, "Game over or lose: the sad descending 'wah wah wah wahhh'.",
      ["gameover", "lose", "lost", "fail", "failure", "over", "retry", "continue"])
def game_over(c):
    f = c.note(4, -1)
    L = []
    for i in range(4):
        last = i == 3
        L.append(c.voice("lead", c.up(f, -i), start=0.3 * i, hold=0.4 if last else 0.12,
                         decay=0.5 if last else 0.15, curve=1.5,
                         filter={"type": "lp", "cutoff": c.cut(1600), "q": 1.0},
                         vibrato={"rate": 5, "depth": 0.35, "delay": 0.1} if last else {}))
    return L, None


def categories():
    out = {}
    for meta in REGISTRY.values():
        out.setdefault(meta["category"], []).append(meta["name"])
    return out
