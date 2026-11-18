# Wiring a pack into a web game

Render the pack into the folder the game serves statically (Vite / Next: `public/sfx`,
plain HTML: next to `index.html`, Phaser templates: `public/assets/sfx` or `assets/sfx`).

## Phaser 3

Use Phaser's own loader and sound manager, reading ids from the manifest:

```js
// preload()
this.load.json('sfx-manifest', 'sfx/manifest.json');
this.load.once('filecomplete-json-sfx-manifest', (key, type, m) => {
  for (const s of m.sounds) s.files.forEach((f, i) => this.load.audio(`${s.id}#${i}`, `sfx/${f}`));
});

// anywhere after create()
function sfx(scene, id, level = 0) {
  const m = scene.cache.json.get('sfx-manifest');
  const s = m.sounds.find((x) => x.id === id);
  if (!s) return;
  const i = s.ladder ? Math.min(level, s.files.length - 1) : Math.floor(Math.random() * s.files.length);
  scene.sound.play(`${id}#${i}`, { detune: s.ladder ? 0 : (Math.random() - 0.5) * 60 });
}
```

## Everything else (plain canvas, PixiJS, Three.js, Kaplay, React games)

Copy `templates/web/soundpass.js` into the source tree:

```js
import { SoundPass } from './soundpass.js';
export const sfx = new SoundPass('sfx/');
await sfx.load();

sfx.play('jump');
sfx.play('combo', { level: combo - 1 });
```

Browsers block audio until the first user gesture. `play()` resumes the AudioContext, so
make sure the first sound is triggered from a click / key / touch handler (a "Start"
button is the usual place).

For Howler.js projects, keep Howler and build `new Howl({ src: ['sfx/coin.wav'] })` per file.

## Where calls usually go

| Event | Typical place |
|-------|---------------|
| jump, shoot, dash | the input handler that starts the action |
| coin, hit, hurt | the collision / overlap callback |
| ui_click | the DOM button `click` handlers or the in-canvas button callbacks |
| level_complete, game_over | the scene / state transition |
