# Wiring a pack into Cocos Creator 3.x

Plan `out`: `assets/resources/soundpass` (anything under `assets/resources` can be loaded
at runtime with `resources.load`).

Add a small component to a persistent node (or make it a singleton):

```ts
import { _decorator, Component, AudioSource, AudioClip, JsonAsset, resources, director } from 'cc';
const { ccclass } = _decorator;

@ccclass('SoundPass')
export class SoundPass extends Component {
  static instance: SoundPass;
  private clips = new Map<string, AudioClip[]>();
  private ladder = new Map<string, boolean>();
  private source!: AudioSource;
  volume = 1;

  onLoad() {
    SoundPass.instance = this;
    director.addPersistRootNode(this.node);
    this.source = this.node.addComponent(AudioSource);
    resources.load('soundpass/manifest', JsonAsset, (err, asset) => {
      if (err) { console.warn('SoundPass: manifest missing', err); return; }
      for (const s of (asset.json as any).sounds) {
        const paths = s.files.map((f: string) => 'soundpass/' + f.replace(/\.wav$/, ''));
        resources.load(paths, AudioClip, (e, clips) => { if (!e) this.clips.set(s.id, clips as AudioClip[]); });
        this.ladder.set(s.id, !!s.ladder);
      }
    });
  }

  static play(id: string, level = 0, volume = 1) {
    const self = SoundPass.instance;
    const arr = self?.clips.get(id);
    if (!arr || !arr.length) return;
    const i = self.ladder.get(id) ? Math.min(level, arr.length - 1) : Math.floor(Math.random() * arr.length);
    self.source.playOneShot(arr[i], volume * self.volume);
  }
}
```

Then `SoundPass.play('coin')` from gameplay code. Button clicks can be wired with a
`Button` click event that calls a method which calls `SoundPass.play('ui_click')`.
