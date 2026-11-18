<p align="center"><img src=".claude-plugin/icon.png" width="96" alt=""></p>

<h1 align="center">soundpass</h1>

<p align="center"><b>Your game is silent. Give it a sound pass.</b><br>
An agent skill that finds the moments in your game that need a sound, synthesizes a matching
set of sound effects in one consistent style, and wires them into your code.</p>

<p align="center">
<a href="https://kinopistudio.github.io/soundpass/">🔊 Listen to the palettes</a> ·
<a href="#install">Install</a> ·
<a href="#how-it-works">How it works</a> ·
<a href="README.zh-TW.md">繁體中文</a>
</p>

---

Most "AI sound effect" tools make **one sound** from a prompt. A game needs **thirty that
belong together**: the jump, the coin, the button click and the victory jingle should sound
like the same game. soundpass works at that level.

What a session looks like (illustrative):

```text
You:    give my game a sound pass

Agent:  scanned 46 scripts (Unity). Found 14 events with no sound:
        Jump, CollectCoin, TakeDamage, Die, OnMatch, ComboUp, ...
        Your art is pixel art -> palette "retro".
        Rendered 14 sounds (31 files with variants) into Assets/Resources/SoundPass.
        jump   0.15s  -20dB  snappy, tonal, pitch rising 320Hz -> 600Hz (+11 st)
        hurt   0.19s  -17dB  snappy, tonal, pitch falling 590Hz -> 318Hz (-11 st)
        ...
        Wired them in with SoundPass.Play("...") at 14 call sites. Open preview.html to listen.
```

- **Whole game, one style.** Six palettes (`retro`, `arcade`, `cozy`, `bubbly`, `scifi`,
  `minimal`) fix the key, scale, instruments, brightness and room, so every sound in the pack
  is in tune and in character with the rest.
- **Reads your code.** It finds `Jump()`, `OnCoinCollected`, `take_damage`, `jumped.emit()`...
  across C#, GDScript, Dart, JS/TS, Lua and more, and notes which ones already make a sound.
- **Wires it in.** Drop-in players for **Unity, Godot 4, Flutter / Flame, web (Phaser, canvas,
  Three.js...) and Cocos Creator**, with variants (no machine-gun repeats), combo ladders
  that climb the scale, and a repeat guard.
- **The agent can "hear".** Every sound comes back as words and numbers ("snappy, tonal,
  pitch rising +11 st, -20 dB") plus a text spectrogram, so the agent checks that a jump
  rises and a hurt falls before you ever press play.
- **Offline, free, yours.** Pure Python standard library: no API keys, no downloads, no
  model. Every sound is synthesized from scratch, so you own it outright. No attribution,
  no license to track.

## Install

**Claude Code** (plugin):

```text
/plugin marketplace add KinopiStudio/soundpass
/plugin install soundpass@kinopistudio
```

**Any agent that reads skills** (Claude Code, Codex, Cursor, Gemini CLI, Copilot...):

```bash
npx skills add KinopiStudio/soundpass
```

**By hand:** copy `skills/soundpass/` into `~/.claude/skills/` (or your agent's skills folder).

Needs Python 3.8+ (already on macOS and most Linux; on Windows, `py` works too).

## Use it

Talk to your agent:

- *"Give my game a sound pass."*
- *"My match-3 feels dead. Add sounds that fit a cozy vibe."*
- *"Make an 8-bit coin sound and a jump."*
- *"The hit sound is too harsh and the combo should climb higher."*

Or drive the CLI yourself:

```bash
SP="python3 skills/soundpass/scripts/soundpass.py"

$SP scan path/to/game --plan soundpass.json --palette retro   # find events, draft a plan
$SP pack soundpass.json                                       # render the pack + manifest + preview.html
$SP render coin --palette cozy -o coin.wav --set pitch=2      # one sound
$SP analyze coin.wav                                          # describe a sound in words + spectrogram
$SP sampler --out sampler                                     # same events in every palette, to compare
```

## How it works

```text
 your game ──scan──▶ events ──▶ soundpass.json ──pack──▶ wavs + manifest.json + preview.html
                                 (palette, sounds,              │
                                  variants, tweaks)             ▼
                                        ▲              analyze: "pitch rising +11 st, -20 dB"
                                        └──── tweak ◀───────────┘
                                                                ▼
                                             templates/ ──▶ SoundPass.Play("coin") in your code
```

1. **Scan.** A heuristic pass over function, signal and event names, split into words
   (`OnCoinCollected` -> *on coin collected*) and matched against 35 sound archetypes. The
   agent then reads the actual code to confirm.
2. **Plan.** A small `soundpass.json` you keep in the repo. It is the source of truth:
   delete the wavs and `pack` gives you the same files again.
3. **Synthesize.** Each archetype is a layered design (transient, body, sub, shimmer)
   written against the palette, rendered by a small synth: PolyBLEP oscillators, FM,
   filtered and lo-fi noise, resonant filter sweeps, pitch steps and vibrato, drive,
   bit-crush, delay and reverb. Then DC-blocked, loudness-normalized to a per-category
   target, soft-limited and de-clicked.
4. **Check.** Measurements (length, loudness, attack, tail, brightness, tonality, pitch
   contour) turn into a one-line description per sound. Things like clipping or clicks are
   flagged.
5. **Wire.** If you already have an audio manager, it uses yours. If not, it adds a
   ~100-line player for your engine and calls it where the events happen.

### The 35 archetypes

| Category | Sounds |
|----------|--------|
| UI | `ui_click` `ui_hover` `ui_confirm` `ui_back` `ui_toggle` `ui_error` `ui_popup` `ui_close` `notification` `purchase` `unlock` |
| Pickups | `coin` `gem` `powerup` `heal` |
| Movement | `jump` `land` `footstep` `dash` `bounce` |
| Combat | `shoot` `hit` `hurt` `death` `explosion` `break` |
| Puzzle | `match` `combo` (ladder) `place` `swap` `star` (ladder) `countdown_tick` `countdown_go` |
| Jingles | `level_complete` `game_over` |

Anything else is a custom recipe: a JSON list of layers and effects
([format](skills/soundpass/references/recipe-format.md)). The agent starts from the closest
archetype and edits it.

### Palettes

| Palette | Sounds like | Good for |
|---------|-------------|----------|
| `retro` | pulse waves, crunchy noise, bit-crushed | pixel-art platformers, game jams |
| `arcade` | filtered saws, square bells, drive, a small room | shooters, action, roguelites |
| `cozy` | sine and FM bells, soft attacks, warm room | match-3, merge, idle, casual mobile |
| `bubbly` | bouncy triangle blips, glassy FM, short echoes | kids games, party games, pets |
| `scifi` | resonant saws, inharmonic FM, delays | space, cyberpunk, tech UI |
| `minimal` | short sine ticks, soft chimes | menus, card and board games, apps |

[Hear them side by side.](https://kinopistudio.github.io/soundpass/)

## FAQ

**Will it sound as good as a sound designer?** No. It will sound consistent, in tune and
appropriate, which is a big step up from silence or a folder of mismatched free sounds. Use
it to get a game feeling alive, then replace the hero sounds with recorded or designed ones
when you have the budget. The plan file makes it clear which sounds are generated.

**Why synthesis instead of an AI audio model?** Offline, instant, deterministic, free,
tiny, and no licensing questions. And because the parameters are known, the agent can
reason about them: "brighter", "shorter", "one step higher" map directly to numbers.

**Does it overwrite my existing sounds?** No. The skill tells the agent to fill gaps and to
leave sounds you made or bought alone unless you ask.

**Which engines?** Unity, Godot 4, Flutter / Flame, Phaser and other web engines, Cocos
Creator, with templates or snippets for each. The wav files themselves work anywhere.

## Development

```bash
python3 -m unittest discover tests     # every archetype x every palette, scan fixtures, CLI
python3 skills/soundpass/scripts/soundpass.py sampler --out docs   # rebuild the demo page
```

The Unity template is compiled against UnityEngine with Unity's own compiler and the
Flutter template passes `dart analyze` before release. Issues and pull requests welcome,
especially new archetypes, palettes and engine templates.

## License

MIT © Kinopi Studio. Sounds you generate with soundpass are yours: no attribution required.
