# Wiring a pack into Unity

## If the project already has an audio manager

Look for it first: `grep -rn "PlayOneShot\|AudioSource\|AudioManager\|SoundManager" Assets --include=*.cs`.
If one exists, keep using it. Render the pack wherever its clips live (set `out` in the
plan), then hook the new clips into it the way existing clips are hooked up (serialized
fields, a ScriptableObject list, Addressables keys...). Route through its mixer group and
volume setting.

## Otherwise: the drop-in player

1. Plan `out`: `Assets/Resources/SoundPass` (the template loads from any `Resources/SoundPass`).
2. `sp pack soundpass.json`
3. Copy `templates/unity/SoundPass.cs` into `Assets/Scripts/` (or the project's script folder).
4. Call it at each event:

```csharp
SoundPass.Play("jump");
SoundPass.Play("combo", level: comboCount - 1);
SoundPass.Play("footstep", volume: 0.7f);
```

5. Optional: `SoundPass.Preload()` during a loading screen; `SoundPass.Output = sfxGroup`
   to route into an AudioMixer group; `SoundPass.Volume` / `SoundPass.Muted` from settings.

## Where calls usually go

| Event | Typical place |
|-------|---------------|
| jump, land | the character controller where velocity is applied / ground is detected (`isGrounded` flips true) |
| footstep | an Animation Event on the walk clip's contact frames, or a timer while moving and grounded |
| coin, gem, powerup, heal | `OnTriggerEnter(2D)` of the pickup, right before `Destroy` |
| hit, hurt, death | the health component's `TakeDamage` / `Die` |
| shoot | where the projectile is instantiated |
| ui_click, ui_back | `Button.onClick` listeners, or a small component on button prefabs |
| match, combo, place, swap | the board / grid logic after the move is validated |
| level_complete, game_over | the game state manager when the state changes |

UnityEvents in the Inspector can't call static methods directly. If the project wires
buttons in the Inspector, add a tiny component:

```csharp
public class PlaySound : MonoBehaviour { public string id = "ui_click"; public void Play() => SoundPass.Play(id); }
```

## Import settings

The defaults are fine for short SFX. For a mobile game with many sounds, select the
`SoundPass` folder and set Load Type = Decompress On Load, Compression = ADPCM (or
Vorbis quality 70) for files over ~0.5 s.

## Check

Enter Play mode and trigger each event; the Console warns about any id that isn't in the
manifest (`SoundPass: no sound 'xyz'`).
