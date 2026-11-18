from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zlib

from . import __version__, analyze as an, archetypes, palettes, preview, scan as sc, synth

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")
DEFAULT_SAMPLER = ["ui_click", "ui_confirm", "coin", "jump", "hit", "match", "powerup", "level_complete"]


def _die(msg):
    print("error: " + msg, file=sys.stderr)
    sys.exit(2)


def _parse_sets(pairs):
    out = {}
    for p in pairs or []:
        if "=" not in p:
            _die("--set expects key=value, got %r" % p)
        k, v = p.split("=", 1)
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = v
    return out


def _seed_for(sid, base):
    return (zlib.crc32(sid.encode("utf-8")) + int(base)) & 0x7FFFFFFF


def _quick(buf, sr):
    a = an.analyze(buf, sr)
    return a


# ------------------------------------------------------------------ commands

def cmd_list(args):
    if args.json:
        print(json.dumps([{k: v for k, v in m.items() if k != "fn"} for m in archetypes.REGISTRY.values()],
                         indent=2))
        return
    for cat, names in archetypes.categories().items():
        print("[%s]" % cat)
        for n in names:
            m = archetypes.REGISTRY[n]
            print("  %-15s %s%s" % (n, m["desc"], "  (ladder)" if m["ladder"] else ""))
        print()


def cmd_palettes(args):
    if args.json:
        print(json.dumps(palettes.PALETTES, indent=2))
        return
    for name, p in palettes.PALETTES.items():
        print("%-8s %s\n         good for: %s" % (name, p["desc"], p["good_for"]))


def cmd_scan(args):
    res = sc.scan(args.path)
    if args.json:
        print(sc.dumps(res))
    else:
        print(sc.summary(res))
    if args.plan:
        out_dir = args.out or sc.DEFAULT_OUT.get(res["engine"], "sfx")
        plan = sc.draft_plan(res, args.palette, out_dir)
        if os.path.exists(args.plan) and not args.force:
            _die("%s exists (use --force to overwrite)" % args.plan)
        with open(args.plan, "w", encoding="utf-8") as f:
            f.write(sc.dumps(plan) + "\n")
        print("\nwrote draft plan with %d sounds -> %s (review it before packing)" % (len(plan["sounds"]), args.plan))


def _recipe_from(args):
    tweak = _parse_sets(args.set)
    if args.source.endswith(".json") and os.path.exists(args.source):
        with open(args.source, encoding="utf-8") as f:
            return json.load(f)
    if args.source not in archetypes.REGISTRY:
        _die("unknown archetype %r. Run `list` to see them, or pass a recipe .json file" % args.source)
    return archetypes.build(args.source, args.palette, tweak, variant=args.variant, seed=args.seed, key=args.key)


def cmd_render(args):
    recipe = _recipe_from(args)
    if args.print_recipe:
        print(json.dumps(recipe, indent=2))
        if not args.out:
            return
    out = args.out or (os.path.splitext(os.path.basename(args.source))[0] + ".wav")
    try:
        buf = synth.render(recipe, args.rate, seed=args.seed + args.variant)
    except synth.RecipeError as e:
        _die(str(e))
    synth.write_wav(out, buf, args.rate)
    a = an.analyze(buf, args.rate)
    print(an.report(out, a, spectrogram=not args.no_spectrogram))
    if args.play:
        _play(out)


def pack(plan, base_dir, out_override=None, only=None, quiet=False):
    pal = plan.get("palette")
    if not pal:
        _die("plan needs a 'palette' (%s)" % ", ".join(palettes.PALETTES))
    palettes.get(pal)
    sr = int(plan.get("sample_rate", synth.DEFAULT_SR))
    seed = int(plan.get("seed", 1))
    key = plan.get("key")
    out_dir = out_override or os.path.join(base_dir, plan.get("out", "sfx"))
    os.makedirs(out_dir, exist_ok=True)
    default_variants = int(plan.get("variants", 1))
    ids = set()
    manifest = {"generator": "soundpass/%s" % __version__, "palette": pal, "key": key,
                "sample_rate": sr, "sounds": []}
    old = {}
    mpath = os.path.join(out_dir, "manifest.json")
    if only and os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as f:
            old = {s["id"]: s for s in json.load(f).get("sounds", [])}
    rows = []
    for entry in plan.get("sounds", []):
        sid = entry.get("id") or entry.get("archetype")
        if not sid or not ID_RE.match(sid):
            _die("sound id %r must be lowercase letters, digits and underscores" % sid)
        if sid in ids:
            _die("duplicate sound id %r" % sid)
        ids.add(sid)
        if only and sid not in only:
            if sid in old:
                manifest["sounds"].append(old[sid])
            continue
        arch = entry.get("archetype")
        recipe = entry.get("recipe")
        if not arch and not recipe:
            _die("sound %r needs an 'archetype' or a 'recipe'" % sid)
        if arch and arch not in archetypes.REGISTRY:
            _die("sound %r: unknown archetype %r" % (sid, arch))
        meta = archetypes.REGISTRY.get(arch, {})
        n = int(entry.get("variants", default_variants))
        n = max(1, min(n, 16))
        files, durs = [], []
        for v in range(n):
            if recipe:
                r = recipe
            else:
                r = archetypes.build(arch, entry.get("palette", pal), entry.get("tweak"), variant=v,
                                     seed=_seed_for(sid, seed), key=entry.get("key", key))
            try:
                buf = synth.render(r, sr, seed=_seed_for(sid, seed) + v)
            except synth.RecipeError as e:
                _die("sound %r: %s" % (sid, e))
            fn = "%s.wav" % sid if n == 1 else "%s_%02d.wav" % (sid, v + 1)
            synth.write_wav(os.path.join(out_dir, fn), buf, sr)
            files.append(fn)
            durs.append(round(len(buf) / float(sr), 3))
            if v == 0:
                a = an.analyze(buf, sr)
                rows.append((sid, n, a))
        manifest["sounds"].append({
            "id": sid,
            "archetype": arch or "custom",
            "category": meta.get("category", "custom"),
            "desc": entry.get("desc") or meta.get("desc", ""),
            "ladder": bool(meta.get("ladder")),
            "files": files,
            "durations": durs,
        })
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    preview.write(os.path.join(out_dir, "preview.html"), manifest,
                  "Sound pack - %s" % pal, "%d sounds, palette '%s'. Generated by soundpass." % (
                      len(manifest["sounds"]), pal))
    if not quiet:
        print("%-16s %3s  %-7s %-7s  %s" % ("id", "var", "len", "loud", "sounds like"))
        for sid, n, a in rows:
            flag = ("  ISSUES: " + "; ".join(a["issues"])) if a["issues"] else ""
            print("%-16s %3d  %-7s %-7s  %s%s" % (sid, n, "%.2fs" % a["duration_s"],
                                                  "%.0fdB" % a["loudness_dbfs"], an.describe(a), flag))
        print("\nwrote %d sounds to %s\n  manifest: %s\n  preview:  %s" % (
            len(rows), out_dir, mpath, os.path.join(out_dir, "preview.html")))
    return manifest


def cmd_pack(args):
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    only = set(args.only.split(",")) if args.only else None
    pack(plan, os.path.dirname(os.path.abspath(args.plan)), args.out, only)


def cmd_analyze(args):
    res = []
    for p in args.files:
        buf, sr = synth.read_wav(p)
        a = an.analyze(buf, sr)
        if args.json:
            d = an.public(a)
            d["file"] = p
            d["description"] = an.describe(a)
            res.append(d)
        else:
            print(an.report(p, a, spectrogram=not args.no_spectrogram))
            print()
    if args.json:
        print(json.dumps(res, indent=2))


def cmd_sampler(args):
    events = args.events.split(",") if args.events else DEFAULT_SAMPLER
    pals = args.palettes.split(",") if args.palettes else list(palettes.PALETTES)
    os.makedirs(args.out, exist_ok=True)
    packs = []
    for pal in pals:
        plan = {"palette": pal, "out": pal, "seed": args.seed,
                "sounds": [{"id": e, "archetype": e,
                            "variants": (3 if archetypes.REGISTRY[e]["ladder"] else 1)} for e in events]}
        m = pack(plan, args.out, quiet=True)
        m["base"] = pal + "/"
        m["palette_desc"] = palettes.PALETTES[pal]["desc"] + " Good for " + palettes.PALETTES[pal]["good_for"] + "."
        packs.append(m)
        print("rendered %-8s (%d sounds)" % (pal, len(events)))
    path = os.path.join(args.out, "index.html")
    preview.write(path, {"packs": packs}, "soundpass palette sampler",
                  "The same events in every palette. Pick the one that sounds like your game.")
    print("open %s" % path)


def cmd_preview(args):
    mpath = os.path.join(args.dir, "manifest.json")
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    path = os.path.join(args.dir, "preview.html")
    preview.write(path, m, "Sound pack - %s" % m.get("palette"), "%d sounds" % len(m.get("sounds", [])))
    print(path)


def _play(path):
    for cmd in (["afplay", path], ["paplay", path], ["aplay", "-q", path], ["ffplay", "-nodisp", "-autoexit",
                                                                         "-loglevel", "quiet", path]):
        if shutil.which(cmd[0]):
            subprocess.call(cmd)
            return
    if sys.platform.startswith("win"):
        subprocess.call(["powershell", "-c", "(New-Object Media.SoundPlayer '%s').PlaySync()" % path])
        return
    print("no audio player found; open the preview.html in a browser instead", file=sys.stderr)


def cmd_play(args):
    for p in args.files:
        _play(p)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="soundpass", description="Give your whole game a sound pass.")
    ap.add_argument("--version", action="version", version="soundpass " + __version__)
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("list", help="list sound archetypes")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("palettes", help="list palettes")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_palettes)

    p = sub.add_parser("scan", help="find events in game code that deserve a sound")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")
    p.add_argument("--plan", help="also write a draft plan JSON here")
    p.add_argument("--palette", default="cozy")
    p.add_argument("--out", help="sound output dir to put in the plan (default depends on engine)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("render", help="render one archetype or recipe .json to a wav")
    p.add_argument("source", help="archetype name, or path to a recipe .json")
    p.add_argument("-o", "--out")
    p.add_argument("--palette", default="cozy")
    p.add_argument("--key")
    p.add_argument("--variant", type=int, default=0)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--rate", type=int, default=synth.DEFAULT_SR)
    p.add_argument("--set", action="append", metavar="KEY=VALUE",
                   help="tweak: pitch (semitones), length, brightness, reverb, gain_db, jitter")
    p.add_argument("--print-recipe", action="store_true", help="print the recipe JSON (edit it, render it back)")
    p.add_argument("--no-spectrogram", action="store_true")
    p.add_argument("--play", action="store_true")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("pack", help="render every sound in a plan, plus manifest.json and preview.html")
    p.add_argument("plan")
    p.add_argument("--out")
    p.add_argument("--only", help="comma-separated ids to re-render")
    p.set_defaults(fn=cmd_pack)

    p = sub.add_parser("analyze", help="describe wav files in words, numbers and a text spectrogram")
    p.add_argument("files", nargs="+")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-spectrogram", action="store_true")
    p.set_defaults(fn=cmd_analyze)

    p = sub.add_parser("sampler", help="render the same events in every palette, with an HTML page to compare")
    p.add_argument("--out", default="soundpass-sampler")
    p.add_argument("--events")
    p.add_argument("--palettes")
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(fn=cmd_sampler)

    p = sub.add_parser("preview", help="rebuild preview.html for a pack folder")
    p.add_argument("dir")
    p.set_defaults(fn=cmd_preview)

    p = sub.add_parser("play", help="play wav files through the system player")
    p.add_argument("files", nargs="+")
    p.set_defaults(fn=cmd_play)

    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 1
    args.fn(args)
    return 0
