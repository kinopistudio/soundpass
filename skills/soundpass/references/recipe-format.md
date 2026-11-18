# Recipe format

A recipe is one sound. Layers are rendered and mixed, then `fx` runs on the mix, then the
result is DC-blocked, loudness-normalized, soft-limited, trimmed and de-clicked.

The quickest way to write one is to start from an archetype:

```bash
sp render hit --palette arcade --print-recipe > thud.json   # edit thud.json
sp render thud.json -o thud.wav                              # check the printed analysis
```

## Top level

| field      | default | meaning |
|------------|---------|---------|
| `layers`   | -       | list of layers (at least one) |
| `fx`       | none    | effects applied to the mix, see below |
| `loudness` | -18     | target momentary loudness in dBFS (max RMS over 50 ms). UI -32..-22, pickups -21..-17, hits -17..-14 |
| `ceiling`  | -1      | peak ceiling in dBFS; overshoot is soft-limited |

Sounds are capped at 10 s.

## Layer

| field         | default  | meaning |
|---------------|----------|---------|
| `wave`        | `sine`   | `sine`, `triangle`, `square`, `saw`, `fm`, `noise`, `crunch` |
| `freq`        | 440      | Hz, or a note name: `"A4"`, `"C#5"`, `"Eb3"` |
| `freq_end`    | = freq   | slide target (exponential glide) |
| `slide_time`  | layer length | seconds the glide takes; holds `freq_end` after |
| `slide_shape` | 1        | < 1 glides fast then settles, > 1 starts slow |
| `steps`       | none     | `[[time, semitones], ...]`: jumps in pitch relative to the base. `[[0,0],[0.06,5]]` = classic coin |
| `vibrato`     | none     | `{"rate": Hz, "depth": semitones, "delay": s}` |
| `duty`        | 0.5      | `square` pulse width (0.125 / 0.25 / 0.5 for NES-style timbres) |
| `duty_end`    | = duty   | pulse-width sweep |
| `fm`          | `{ratio: 2, index: 1}` | for `wave: fm`: modulator `ratio` to the carrier, `index` (brightness) and `index_end`. Integer ratios = harmonic, 1.41 / 2.76 / 3.5 = bell or metal |
| `color`       | `white`  | for `wave: noise`: `white`, `pink` (softer), `brown` (rumble) |
| `filter`      | none     | `{"type": "lp" / "hp" / "bp", "cutoff": Hz, "cutoff_end": Hz, "q": 0.7}` - cutoff sweeps over the layer |
| `env`         | see below | amplitude envelope |
| `gain`        | 1        | layer level before mixing |
| `start`       | 0        | seconds after the sound starts |

`crunch` is lo-fi sample-and-hold noise: `freq` sets how gritty it is (80 = rumble,
2000 = hiss); it is what 8-bit explosions are made of. Plain `noise` is smooth and is
usually shaped with a `filter`.

### Envelope

```json
"env": {"attack": 0.002, "hold": 0.0, "decay": 0.2, "curve": 2.0}
```

Linear rise over `attack`, flat for `hold`, then a fall to silence over `decay` shaped by
`curve` (1 = linear, 2-3 = percussive, < 1 = swells then cuts). Layer length is
attack + hold + decay. Keep attack >= 0.001 to avoid clicks.

## fx

Applied in this order:

| field      | example | meaning |
|------------|---------|---------|
| `drive`    | `0.3`   | soft saturation, 0..1. Punch and grit |
| `bitcrush` | `{"bits": 8, "rate": 11025}` | lo-fi: fewer bits, lower sample rate |
| `highpass` | `120`   | one-pole high-pass, Hz |
| `lowpass`  | `6000`  | one-pole low-pass, Hz |
| `delay`    | `{"time": 0.09, "feedback": 0.3, "mix": 0.25}` | echo |
| `reverb`   | `{"size": 0.4, "mix": 0.2, "damp": 0.5}` | small room. size 0..1 |

## Examples

Classic 8-bit coin:

```json
{"layers": [{"wave": "square", "duty": 0.25, "freq": "B5", "steps": [[0, 0], [0.06, 5]],
             "env": {"attack": 0.001, "hold": 0.05, "decay": 0.25, "curve": 3}}],
 "fx": {"bitcrush": {"bits": 8, "rate": 22050}}, "loudness": -18}
```

Heavy door slam (three layers: body, crack, sub):

```json
{"layers": [
   {"wave": "noise", "color": "pink", "filter": {"type": "lp", "cutoff": 1800, "cutoff_end": 300},
    "env": {"attack": 0.001, "decay": 0.35, "curve": 2.5}},
   {"wave": "noise", "filter": {"type": "hp", "cutoff": 2500},
    "env": {"attack": 0.001, "decay": 0.03, "curve": 2}, "gain": 0.6},
   {"wave": "sine", "freq": 70, "freq_end": 40, "env": {"attack": 0.002, "decay": 0.3}, "gain": 0.8}],
 "fx": {"drive": 0.3, "reverb": {"size": 0.5, "mix": 0.25}}, "loudness": -15}
```

Magic sparkle (inharmonic FM bells at random-ish times):

```json
{"layers": [
   {"wave": "fm", "freq": 2093, "fm": {"ratio": 3.5, "index": 2, "index_end": 0}, "env": {"decay": 0.4}},
   {"wave": "fm", "freq": 2637, "fm": {"ratio": 3.5, "index": 2, "index_end": 0}, "env": {"decay": 0.4}, "start": 0.05, "gain": 0.7},
   {"wave": "fm", "freq": 3136, "fm": {"ratio": 3.5, "index": 2, "index_end": 0}, "env": {"decay": 0.5}, "start": 0.11, "gain": 0.5}],
 "fx": {"reverb": {"size": 0.6, "mix": 0.35}}, "loudness": -20}
```

## Sound design cheat sheet

- **Rising = good, falling = bad.** Rewards, confirms and jumps go up; damage, cancel and
  failure go down.
- **Short and dry for frequent sounds.** Anything the player hears 100 times a minute
  (footsteps, UI, shots) should be under 0.2 s with little reverb, plus variants.
- **Layer for weight.** A big sound is a transient (short noise or click) + a body
  (tone or filtered noise) + optional sub (low sine sweep).
- **Brightness reads as energy.** Darker for soft, cozy games; brighter for arcade.
- **Stay in key.** Archetypes take their notes from the palette's scale, so tonal sounds
  never clash. In custom recipes, use note names from the palette's scale (`sp palettes --json`).
