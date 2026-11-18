<p align="center"><img src=".claude-plugin/icon.png" width="96" alt=""></p>

<h1 align="center">soundpass</h1>

<p align="center"><b>你的遊戲沒有聲音？幫它做一次完整的音效配置。</b><br>
一個 agent skill：找出遊戲裡需要音效的時刻，用同一種風格合成整套音效，再接進你的程式碼。</p>

<p align="center">
<a href="https://kinopistudio.github.io/soundpass/">🔊 試聽各種風格</a> ·
<a href="README.md">English</a>
</p>

---

大部分「AI 音效」工具一次只做**一個**聲音。但一款遊戲需要的是**三十個彼此搭配的聲音**：跳躍、撿金幣、按鈕、過關音樂，聽起來應該像同一款遊戲。soundpass 就是以整款遊戲為單位來處理。

- **整款遊戲同一種風格**：6 套風格（`retro`、`arcade`、`cozy`、`bubbly`、`scifi`、`minimal`）統一調性、音階、樂器、亮度與空間感，整套音效的音高彼此和諧、風格一致。
- **看得懂你的程式碼**：從 C#、GDScript、Dart、JS/TS、Lua 等程式碼裡找出 `Jump()`、`OnCoinCollected`、`take_damage` 這類事件，也會標出哪些地方已經有音效。
- **直接接好**：附 Unity、Godot 4、Flutter／Flame、網頁（Phaser、canvas、Three.js…）和 Cocos Creator 的播放器。同一個音效有多個變體，連續播放不會像機關槍；combo 會沿著音階一路往上爬；同一瞬間重複觸發也有防護。
- **Agent「聽得到」**：每個音效都會轉成文字和數據（例如「短促、有音高、音高上升 +11 半音、-20 dB」）再加上文字頻譜圖。所以在你按下播放之前，agent 就能先確認跳躍是往上、受傷是往下。
- **離線、免費、版權歸你**：只用 Python 標準函式庫，不需要 API key、不用下載、也不用模型。每個聲音都是從零合成，完全屬於你，不用標註來源，也沒有授權問題。

## 安裝

**Claude Code（plugin）**：

```text
/plugin marketplace add KinopiStudio/soundpass
/plugin install soundpass@kinopistudio
```

**其他支援 skills 的 agent**（Codex、Cursor、Gemini CLI、Copilot…）：

```bash
npx skills add KinopiStudio/soundpass
```

**手動安裝**：把 `skills/soundpass/` 複製到 `~/.claude/skills/`（或你所用 agent 的 skills 資料夾）。

需要 Python 3.8 以上（macOS 和多數 Linux 已內建）。

## 使用

直接跟 agent 說：

- 「幫我的遊戲配上音效。」
- 「我的三消遊戲感覺很死板，加上溫暖療癒風格的音效。」
- 「做一個 8-bit 的金幣音效和跳躍音效。」
- 「打擊聲太刺耳了，combo 要再往上爬高一點。」

也可以自己下指令：

```bash
SP="python3 skills/soundpass/scripts/soundpass.py"

$SP scan 遊戲資料夾 --plan soundpass.json --palette retro   # 找事件、產生計畫草稿
$SP pack soundpass.json                                     # 產生整套音效 + manifest + 試聽頁
$SP render coin --palette cozy -o coin.wav --set pitch=2    # 只做一個音效
$SP analyze coin.wav                                        # 用文字和頻譜圖描述一個音效
$SP sampler --out sampler                                   # 同一組事件在各種風格的對照
```

## 常見問題

**會跟專業音效師做的一樣好嗎？** 不會。但它會一致、合調、恰如其分，比起完全沒有聲音，或是一堆風格不搭的免費素材，已經是很大的進步。先用它讓遊戲活起來，等有預算時再把最重要的幾個聲音換成錄製或專門設計的版本。

**會覆蓋我原本的音效嗎？** 不會。skill 會要求 agent 只補缺少的部分，你自己做的或買的音效，除非你要求，否則不會動。

## 授權

MIT © Kinopi Studio。用 soundpass 產生的音效歸你所有，不需要標註來源。
