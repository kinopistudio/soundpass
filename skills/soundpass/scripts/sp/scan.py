"""Find the moments in a game's code that deserve a sound.

Heuristic and engine-agnostic: it looks at function names, event / signal names and
calls, splits them into words (OnCoinCollected -> on coin collected) and matches them
against each archetype's keywords. The agent reviews the result; it is a map, not a verdict.
"""
from __future__ import annotations

import json
import os
import re

from .archetypes import REGISTRY

CODE_EXTS = {".cs", ".gd", ".dart", ".js", ".mjs", ".ts", ".jsx", ".tsx", ".lua", ".py", ".swift",
             ".kt", ".java", ".cpp", ".cc", ".h", ".hpp", ".c", ".hx", ".rs", ".go", ".luau"}
SKIP_DIRS = {".git", ".svn", "node_modules", "Library", "Temp", "Logs", "obj", "bin", "build",
             "Build", "Builds", ".dart_tool", "Pods", ".gradle", ".godot", ".import", "dist", "out",
             "Packages", "PackageCache", "vendor", ".idea", ".vs", ".vscode", "__pycache__", "venv",
             ".venv", "Plugins", "ThirdParty", "third_party", "addons", "UserSettings", "coverage",
             ".next", ".nuxt", "android", "ios", "macos", "windows", "linux", "test", "tests"}
DEFAULT_OUT = {"unity": "Assets/Resources/SoundPass", "godot": "audio/soundpass",
               "flutter": "assets/sfx", "flutter-flame": "assets/audio/sfx",
               "cocos": "assets/resources/soundpass"}
AUDIO_EXTS = {".wav", ".ogg", ".mp3", ".m4a", ".aiff", ".aif", ".flac"}
MAX_FILE_BYTES = 600_000

IDENT_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
DECL = re.compile(r"\b(?:signal|event|def|func|function|fun|fn|void|async|override|"
                  r"public|private|protected|static|export)\s+(?:[A-Za-z_<>\[\],.?]+\s+)*?"
                  r"([A-Za-z_][A-Za-z0-9_]*)")
STRING_EVENT = re.compile(r"(?:emit_signal|emit|dispatch|trigger|Invoke|send|fire|publish|on)\s*\(\s*"
                          r"[\"']([A-Za-z_][A-Za-z0-9_\-.:]*)[\"']")
AUDIO_HINT = re.compile(r"PlayOneShot|AudioSource|AudioClip|AudioStreamPlayer|play_sfx|playSfx|PlaySfx|"
                        r"PlaySound|play_sound|playSound|FlameAudio|AudioPlayer|AudioPool|SoundPass|"
                        r"\bsfx\b|\bSfx\b|Howl|sound\.play|this\.sound\.|audio\.play|\.playEffect|"
                        r"SoundManager|AudioManager", re.I)
DECL_WORDS = {"signal", "event", "def", "func", "function", "fun", "fn", "void"}
NOISE_WORDS = {"if", "for", "while", "switch", "return", "new", "catch", "print", "log", "debug",
               "assert", "typeof", "sizeof", "super", "this", "self", "get", "set", "update",
               "start", "awake", "init", "ready", "process", "main", "build", "dispose", "render"}

# Engine / framework API calls whose names happen to contain event words.
API_CALLS = {"getbuttondown", "getbuttonup", "getbutton", "getkeydown", "getkeyup", "getkey",
             "getmousebuttondown", "destroy", "destroyimmediate", "instantiate", "queue_free",
             "is_action_just_pressed", "is_action_pressed", "is_action_just_released",
             "comparetag", "getcomponent", "addcomponent", "setactive", "invoke", "startcoroutine",
             "addeventlistener", "removeeventlistener", "setstate", "connect", "disconnect",
             "emit", "emit_signal", "dispatch", "settimeout", "setinterval", "requestanimationframe",
             "navigator", "pushnamed", "pushreplacement", "showdialog"}

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def words_of(ident):
    out = []
    for part in re.split(r"[_\-.:]+", ident):
        out.extend(w.lower() for w in _CAMEL.findall(part))
    return out


def _keyword_index():
    idx = []
    for name, meta in REGISTRY.items():
        for kw in meta["keywords"]:
            idx.append((tuple(words_of(kw)) if "_" in kw else (kw.lower(),), name))
    return idx


KW = _keyword_index()


def match_ident(ident):
    """Return the archetypes whose keywords appear in this identifier."""
    ws = words_of(ident)
    if not ws or ident.lower() in NOISE_WORDS:
        return []
    joined_spans = set()
    for i in range(len(ws)):
        acc = ""
        for j in range(i, min(i + 3, len(ws))):
            acc += ws[j]
            joined_spans.add(acc)
    hits = []
    for kw, name in KW:
        if len(kw) == 1:
            ok = kw[0] in ws or (len(kw[0]) >= 6 and kw[0] in joined_spans)
        else:
            ok = any(tuple(ws[i:i + len(kw)]) == kw for i in range(len(ws)))
        if ok and name not in hits:
            hits.append(name)
    return hits


def detect_engine(root):
    def has(*p):
        return os.path.exists(os.path.join(root, *p))
    if has("ProjectSettings", "ProjectVersion.txt"):
        return "unity"
    if has("project.godot"):
        return "godot"
    if has("pubspec.yaml"):
        try:
            with open(os.path.join(root, "pubspec.yaml"), encoding="utf-8", errors="ignore") as f:
                txt = f.read()
            return "flutter-flame" if "flame" in txt else "flutter"
        except OSError:
            return "flutter"
    if has("package.json"):
        try:
            with open(os.path.join(root, "package.json"), encoding="utf-8", errors="ignore") as f:
                txt = f.read().lower()
        except OSError:
            txt = ""
        if "cocos" in txt or has("settings", "project.json"):
            return "cocos"
        for lib in ("phaser", "pixi", "three", "kaboom", "kaplay", "excalibur", "babylon", "playcanvas"):
            if '"%s' % lib in txt:
                return "web-" + lib
        return "web"
    if has("main.lua") or has("conf.lua"):
        return "love2d"
    if any(f.endswith(".uproject") for f in os.listdir(root)):
        return "unreal"
    return "unknown"


def scan(root, max_sites=8):
    root = os.path.abspath(root)
    engine = detect_engine(root)
    found = {}
    audio_files = 0
    files_scanned = 0
    audio_code_sites = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in AUDIO_EXTS:
                audio_files += 1
                continue
            if ext not in CODE_EXTS:
                continue
            path = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    continue
                with open(path, encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
            except OSError:
                continue
            files_scanned += 1
            rel = os.path.relpath(path, root)
            for ln, line in enumerate(lines, 1):
                s = line.strip()
                if not s or s.startswith(("//", "#", "*", "/*", "--", "import ", "using ", "from ")):
                    continue
                if AUDIO_HINT.search(s):
                    audio_code_sites += 1
                idents = []
                for m in DECL.finditer(s):
                    idents.append((m.group(1), True))
                for m in IDENT_CALL.finditer(s):
                    idents.append((m.group(1), False))
                for m in STRING_EVENT.finditer(s):
                    idents.append((m.group(1), True))
                seen = set()
                for ident, is_decl in idents:
                    if ident in seen or len(ident) < 3:
                        continue
                    if ident.lower() in API_CALLS or AUDIO_HINT.search(ident):
                        continue
                    seen.add(ident)
                    for arch in match_ident(ident):
                        lo, hi = max(0, ln - 4), min(len(lines), ln + 3)
                        has_audio = any(AUDIO_HINT.search(x) for x in lines[lo:hi])
                        site = {"file": rel, "line": ln, "symbol": ident, "kind": "decl" if is_decl else "call",
                                "has_audio": bool(has_audio), "code": s[:140]}
                        found.setdefault(arch, []).append(site)

    candidates = []
    for arch, sites in found.items():
        decls = [x for x in sites if x["kind"] == "decl"]
        symbols = sorted({x["symbol"] for x in sites})
        score = len(decls) * 2 + len(sites)
        silent = [x for x in sites if not x["has_audio"]]
        sites_sorted = sorted(sites, key=lambda x: (x["kind"] != "decl", x["has_audio"], x["file"], x["line"]))
        candidates.append({
            "archetype": arch,
            "category": REGISTRY[arch]["category"],
            "score": score,
            "symbols": symbols[:12],
            "sites_total": len(sites),
            "sites_without_audio": len(silent),
            "sites": sites_sorted[:max_sites],
        })
    candidates.sort(key=lambda c: -c["score"])
    return {
        "root": root,
        "engine": engine,
        "files_scanned": files_scanned,
        "existing_audio_files": audio_files,
        "existing_audio_code_lines": audio_code_sites,
        "candidates": candidates,
    }


def summary(result, limit=30):
    out = ["engine: %s | code files scanned: %d | existing audio files: %d | lines that already touch audio: %d"
           % (result["engine"], result["files_scanned"], result["existing_audio_files"],
              result["existing_audio_code_lines"]),
           "",
           "%-15s %-9s %5s %7s  %s" % ("archetype", "category", "sites", "silent", "example symbols / first site")]
    for c in result["candidates"][:limit]:
        first = c["sites"][0]
        out.append("%-15s %-9s %5d %7d  %s  (%s:%d)" % (
            c["archetype"], c["category"], c["sites_total"], c["sites_without_audio"],
            ", ".join(c["symbols"][:4]), first["file"], first["line"]))
    if not result["candidates"]:
        out.append("(no candidate events found - read the code and pick events by hand)")
    return "\n".join(out)


def draft_plan(result, palette, out_dir, min_score=2):
    sounds = []
    for c in result["candidates"]:
        if c["score"] < min_score:
            continue
        arch = c["archetype"]
        meta = REGISTRY[arch]
        variants = 3 if arch in ("footstep", "hit", "shoot", "coin", "jump", "match", "place") else 1
        if meta["ladder"]:
            variants = 8 if arch == "combo" else 3
        sounds.append({"id": arch, "archetype": arch, "variants": variants,
                       "_why": "%s (%s:%d)" % (", ".join(c["symbols"][:3]), c["sites"][0]["file"],
                                               c["sites"][0]["line"])})
    return {"palette": palette, "out": out_dir, "seed": 1, "sounds": sounds}


def dumps(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)
