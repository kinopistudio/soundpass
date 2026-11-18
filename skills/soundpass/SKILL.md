---
name: soundpass
description: Give a whole game a coherent set of sound effects - find the moments in the code that need a sound (jump, coin, hit, button click, match, level complete...), synthesize a matching pack of .wav files offline in one consistent style, and wire them into the game. Use when a game is silent or has placeholder audio, when the user asks for sound effects, SFX, game audio, juice or feedback sounds, or wants one specific sound ("make a coin sound", "8-bit jump"). Works with Unity, Godot, Flutter/Flame, Phaser and other web games, Cocos. No API keys, no downloads, no licensing issues.
---

# soundpass

Turns a silent game into one that sounds finished, in one pass. The unit of work is the
*whole game*, not one sound: every sound comes from the same **palette** (same key, same
instruments, same room), so the coin, the button click and the victory jingle sound like
they belong together.

Everything runs through one dependency-free Python 3.8+ script. Below, `sp` means:

```bash
python3 <this skill's directory>/scripts/soundpass.py
```

You cannot hear. You have two substitutes, and you must use both:
`sp analyze` (and the table `sp pack` prints) describes each sound in words and numbers,
and the generated `preview.html` lets the user listen. Never tell the user a sound "sounds
great"; tell them what it measures like and ask them to listen.

## Which job is this?

- **One sound** ("make me a laser"): `sp list` to find the closest archetype, then
  `sp render laser-ish-archetype --palette <p> -o out.wav`, check the printed description,
  tweak with `--set`, done. Skip the rest of this file.
- **A whole game** (the main job): follow the workflow below.

## Workflow for a whole game

### 1. Look at the game

- Find the engine and how audio is played today: `sp scan <project root>` prints the engine,
  how many audio files and audio calls already exist, and a table of candidate events with
  file:line sites. `--json` gives the full detail.
- The scan is a heuristic map. Open the top sites and confirm each event is real
  (a `Jump()` method that the player triggers, not a `jump` in a math helper).
- Note what already has sound (`silent` column = sites with no audio call nearby).
  **Never replace sounds the user made or bought** unless they ask; fill the gaps.

### 2. Decide the sound list

Aim for 8-25 sounds. Prioritise what the player triggers most often and what rewards them:
core action (jump / shoot / place / match), feedback (hit, hurt, error), rewards (coin,
combo, star, level complete), then UI (click, back, popup). Leave out events that fire
every frame or in bursts too fast to hear (use one sound with variants instead).

Use **variants** for anything that repeats (footstep, hit, shoot, coin, place: 3-4 variants)
so it does not machine-gun. Use **ladders** (`combo`, `star`) for escalation: variant N is
one scale step higher, so a combo counter can call level N.

If one event has no fitting archetype, write a custom recipe (step 5).

### 3. Pick the palette

`sp palettes` lists them: `retro` (8-bit), `arcade` (punchy 16-bit), `cozy` (soft, casual
mobile), `bubbly` (cute, toy-like), `scifi`, `minimal` (clean UI, apps, card games).

Choose from the game's look and genre: pixel art -> retro; match-3 / merge / idle -> cozy;
kids / pets -> bubbly; space / cyber -> scifi; shooter / action -> arcade; menus, cards,
board games -> minimal. If it is not obvious, or the user cares, run
`sp sampler --out <tmp dir>` and have them open `index.html`: the same events in every
palette, side by side. Let them choose by ear.

### 4. Write the plan and render

The plan is a small JSON file kept in the project (suggest `soundpass.json` at the root and
committing it: it regenerates the exact same pack any time). `sp scan <root> --plan
soundpass.json --palette <p>` writes a draft; edit it down to the list from step 2.

```json
{
  "palette": "cozy",
  "out": "Assets/Resources/SoundPass",
  "seed": 1,
  "sounds": [
    {"id": "jump", "archetype": "jump", "variants": 3},
    {"id": "coin", "archetype": "coin", "variants": 3, "tweak": {"pitch": 2}},
    {"id": "combo", "archetype": "combo", "variants": 8},
    {"id": "boss_roar", "recipe": {"layers": [], "fx": {}}}
  ]
}
```

- `out` is relative to the plan file. Defaults that the template scripts expect:
  Unity `Assets/Resources/SoundPass`, Godot `audio/soundpass`, Flutter `assets/sfx`,
  web `public/sfx` (or wherever static files are served), Cocos `assets/resources/soundpass`.
- Optional per-plan: `key` (e.g. `"D"`, moves the whole pack), `sample_rate` (default 44100).
- Optional per-sound `tweak`: `pitch` (semitones), `length` (x), `brightness` (x),
  `reverb` (+ mix), `room` (x reverb/delay), `gain_db`, `jitter` (variant spread, x).

Run `sp pack soundpass.json`. It writes the wavs, `manifest.json` (what the engine
templates load) and `preview.html`, and prints one line per sound:

```
id   var  len    loud   sounds like
jump   3  0.38s  -20dB  long, snappy attack, tonal, dark, pitch rising 415Hz -> 795Hz (+11 st)
```

### 5. Check every line, then fix

Read the table like a sound designer:

- Does the motion match the meaning? Jump, powerup, confirm, unlock rise; hurt, death,
  back, game over fall. UI is short (< 0.3 s) and quiet; rewards are brighter and louder.
- Loudness hierarchy: hover < click < confirm < pickups < hits < explosion / jingles.
  `loudness` is set per archetype; shift single sounds with `gain_db`.
- `ISSUES:` lines (clipping, clicks, DC, too long) must be fixed.
- For detail, `sp analyze <file.wav>` adds a text spectrogram (time left to right, pitch
  bottom to top).

Fix with tweaks and re-render only what changed: `sp pack soundpass.json --only coin,jump`.
For a sound no archetype covers, start from the nearest one:
`sp render hit --palette cozy --print-recipe > recipes/thud.json`, edit it, and either
render it directly (`sp render recipes/thud.json -o thud.wav`) or paste it as `"recipe"`
in the plan. The format is in `references/recipe-format.md`.

### 6. Let the user listen

Open the pack's `preview.html` for them (in a browser pane if you have one, or give them
the path). Ask which sounds feel wrong and in what way ("too harsh", "too long", "not
punchy enough") and translate that into tweaks: harsh -> `brightness` 0.7; thin ->
`pitch` -3; not punchy -> `length` 0.8 and `gain_db` +2; muddy -> `room` 0.5.

### 7. Wire it into the game

- If the project already has an audio manager, call it with the new clips. Follow its
  conventions (mixer groups, volume settings, mute toggle).
- Otherwise copy the template for the engine from `templates/` and read the matching
  `references/wiring-<engine>.md`: Unity, Godot, Flutter (and Flame), web (Phaser, plain
  canvas, Three.js...), Cocos.
- Add one call at each confirmed event site, e.g. `SoundPass.Play("coin")`. Ladders take
  the level: `SoundPass.Play("combo", level: comboCount - 1)`.
- Play UI sounds from the UI layer, gameplay sounds from where the event happens (not from
  `Update` / `_process`).
- Respect existing settings: if there is a sound/SFX volume or mute option, route through it.
- Build or run the game if you can, to make sure it compiles and loads.

### 8. Report

Tell the user: the palette and why, the list of sounds and where each one is wired, what
you left silent on purpose, and how to change things later (edit `soundpass.json`, run
`sp pack`). Mention that the sounds are generated from scratch, so they own them outright:
no attribution or license needed.

## Reference

- `references/recipe-format.md` - every recipe field, with examples
- `references/wiring-unity.md`, `wiring-godot.md`, `wiring-flutter.md`, `wiring-web.md`,
  `wiring-cocos.md` - engine integration
- `sp list` - all archetypes with descriptions; `sp list --json` includes scan keywords
