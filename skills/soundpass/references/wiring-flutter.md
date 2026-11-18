# Wiring a pack into Flutter (and Flame)

## If the project already plays sounds

Check `pubspec.yaml` for `audioplayers`, `just_audio`, `soundpool`, `flame_audio` and
search for existing calls (`grep -rn "AudioPlayer\|FlameAudio\|playSound" lib`). Reuse
whatever is there and its settings (mute toggle, volume).

## Flame games with flame_audio

Plan `out`: `assets/audio/sfx`. Then use the files directly:

```dart
await FlameAudio.audioCache.loadAll(['sfx/jump_01.wav', 'sfx/coin.wav']);  // optional preload
FlameAudio.play('sfx/coin.wav', volume: 0.8);
```

For variants and ladders, the drop-in player below is easier (it reads the manifest).

## Otherwise: the drop-in player (audioplayers)

1. `flutter pub add audioplayers`
2. Plan `out`: `assets/sfx`. Add the folder to `pubspec.yaml`:

```yaml
flutter:
  assets:
    - assets/sfx/
```

3. `sp pack soundpass.json`
4. Copy `templates/flutter/sound_pass.dart` to `lib/audio/sound_pass.dart`.
5. Initialise once:

```dart
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SoundPass.init();
  runApp(const MyApp());
}
```

6. Call it:

```dart
SoundPass.play('ui_click');
SoundPass.play('combo', level: combo - 1);
```

## Where calls usually go

| Event | Typical place |
|-------|---------------|
| ui_click | `onPressed` / `onTap` of buttons; for app-wide coverage wrap the app's button widget |
| ui_popup, ui_close | where dialogs and bottom sheets are shown / popped |
| match, combo, place, swap | the game state notifier / bloc / controller after a valid move |
| level_complete, game_over | where the result screen is pushed |
| notification, purchase | after the purchase / reward is confirmed (not on button press) |

Respect the platform: keep UI sounds short and quiet, and wire them to the app's existing
"sound" setting if it has one (`if (settings.soundOn) SoundPass.play(...)`, or set
`SoundPass.muted`).

## Check

`flutter run`, trigger each event. A missing id prints `SoundPass: no sound "xyz"`.
Hot restart (not hot reload) after adding new asset files.
