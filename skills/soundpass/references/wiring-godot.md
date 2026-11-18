# Wiring a pack into Godot 4

## If the project already plays sounds

Look for `AudioStreamPlayer` nodes and any autoload that plays sounds
(`grep -rn "AudioStreamPlayer\|\.play()" --include=*.gd .`). If there is an audio
autoload, add the new streams to it and keep its bus routing.

## Otherwise: the autoload

1. Plan `out`: `audio/soundpass` (relative to the plan at the project root, so
   `res://audio/soundpass`).
2. `sp pack soundpass.json`. Godot imports the .wav files automatically when the editor
   regains focus.
3. Copy `templates/godot/sound_pass.gd` to `res://autoload/sound_pass.gd` and register it
   as an Autoload named `SoundPass` (Project > Project Settings > Globals > Autoload), or
   add it to `project.godot`:

```ini
[autoload]
SoundPass="*res://autoload/sound_pass.gd"
```

4. Exports: the manifest is a non-resource file. In the export preset, set
   Resources > "Filters to export non-resource files/folders" to `*.json`
   (or add `include_filter="*.json"` to the preset in `export_presets.cfg`).
5. Call it:

```gdscript
SoundPass.play("jump")
SoundPass.play("combo", combo - 1)
SoundPass.play("footstep", 0, -4.0)   # 4 dB quieter
```

6. If the project has an `SFX` bus, set `SoundPass.bus = &"SFX"` once (e.g. in the
   autoload's `_ready` or the settings code).

## Where calls usually go

| Event | Typical place |
|-------|---------------|
| jump, land | the player's `_physics_process` where jump velocity is set / `is_on_floor()` becomes true |
| footstep | an AnimationPlayer "Call Method" track on the walk animation, or a timer |
| coin, gem, powerup | the pickup's `body_entered` / `area_entered` handler before `queue_free()` |
| hit, hurt, death | the health component's damage / death function or signal |
| ui_click | each Button's `pressed` signal (connect once in the menu scene's `_ready`) |
| level_complete, game_over | where the game state or scene changes |

Prefer connecting to existing signals (`player.jumped.connect(func(): SoundPass.play("jump"))`)
over editing deep gameplay code, when the signals exist.
