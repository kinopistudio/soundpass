"""Run with: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "soundpass", "scripts")
sys.path.insert(0, SCRIPTS)

from sp import analyze, archetypes, palettes, scan, synth  # noqa: E402

SR = 22050  # half rate keeps the full matrix fast


def cli(*args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "soundpass.py")] + list(args),
                          capture_output=True, text=True)


class TestEveryArchetypeInEveryPalette(unittest.TestCase):
    def test_renders_clean(self):
        for pal in palettes.PALETTES:
            for name, meta in archetypes.REGISTRY.items():
                with self.subTest(palette=pal, archetype=name):
                    buf = synth.render(archetypes.build(name, pal, variant=1, seed=5), SR, seed=5)
                    self.assertGreater(len(buf), SR * 0.01)
                    self.assertLess(len(buf), SR * 3.0)
                    peak = max(abs(x) for x in buf)
                    self.assertLessEqual(peak, synth.db_to_lin(-0.9))
                    self.assertTrue(all(x == x for x in buf), "NaN in output")
                    self.assertLess(abs(buf[0]), 0.01, "click at start")
                    self.assertLess(abs(buf[-1]), 0.01, "click at end")
                    loud = synth.momentary_loudness_db(buf, SR)
                    self.assertLess(abs(loud - meta["loudness"]), 6.0)


class TestBehaviour(unittest.TestCase):
    def test_deterministic(self):
        r = archetypes.build("coin", "retro", variant=2, seed=9)
        self.assertEqual(synth.render(r, SR, seed=3), synth.render(r, SR, seed=3))

    def test_variants_differ(self):
        a = synth.render(archetypes.build("footstep", "cozy", variant=1, seed=1), SR, seed=1)
        b = synth.render(archetypes.build("footstep", "cozy", variant=2, seed=1), SR, seed=2)
        self.assertNotEqual(a, b)

    def test_ladder_rises(self):
        lows = []
        for v in range(4):
            r = archetypes.build("combo", "minimal", variant=v)
            lows.append(r["layers"][1]["freq"])
        self.assertEqual(lows, sorted(lows))
        self.assertEqual(len(set(lows)), 4)

    def test_jump_rises_and_hurt_falls(self):
        up = analyze.analyze(synth.render(archetypes.build("jump", "retro"), SR), SR)
        down = analyze.analyze(synth.render(archetypes.build("hurt", "retro"), SR), SR)
        self.assertEqual(up["pitch"]["motion"], "rising")
        self.assertEqual(down["pitch"]["motion"], "falling")

    def test_note_names(self):
        self.assertAlmostEqual(synth.parse_freq("A4"), 440.0)
        self.assertAlmostEqual(synth.parse_freq("C#5"), synth.parse_freq("Db5"))
        with self.assertRaises(synth.RecipeError):
            synth.parse_freq("H2")

    def test_bad_recipe(self):
        with self.assertRaises(synth.RecipeError):
            synth.render({"layers": [{"wave": "kazoo"}]}, SR)
        with self.assertRaises(synth.RecipeError):
            synth.render({"layers": []}, SR)

    def test_wav_roundtrip(self):
        buf = synth.render(archetypes.build("ui_click", "minimal"), SR)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.wav")
            synth.write_wav(p, buf, SR)
            back, sr = synth.read_wav(p)
        self.assertEqual(sr, SR)
        self.assertEqual(len(back), len(buf))
        self.assertLess(max(abs(a - b) for a, b in zip(buf, back)), 1e-3)


class TestScan(unittest.TestCase):
    def test_words(self):
        self.assertEqual(scan.words_of("OnCoinCollected"), ["on", "coin", "collected"])
        self.assertEqual(scan.words_of("take_damage"), ["take", "damage"])
        self.assertEqual(scan.words_of("HTTPRequest"), ["http", "request"])

    def test_match(self):
        self.assertIn("coin", scan.match_ident("CollectCoin"))
        self.assertIn("hurt", scan.match_ident("TakeDamage"))
        self.assertEqual(scan.match_ident("update"), [])

    def test_unity_fixture(self):
        res = scan.scan(os.path.join(ROOT, "tests", "fixtures", "unity-mini"))
        self.assertEqual(res["engine"], "unity")
        found = {c["archetype"]: c for c in res["candidates"]}
        for a in ("jump", "coin", "hurt", "death", "game_over"):
            self.assertIn(a, found)
        self.assertNotIn("shoot", found)  # PlayOneShot is an engine call, not an event
        self.assertEqual(found["hurt"]["sites_without_audio"], 0)

    def test_godot_fixture(self):
        res = scan.scan(os.path.join(ROOT, "tests", "fixtures", "godot-mini"))
        self.assertEqual(res["engine"], "godot")
        found = {c["archetype"] for c in res["candidates"]}
        self.assertTrue({"jump", "coin", "explosion"} <= found)


class TestCli(unittest.TestCase):
    def test_pack_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            plan = {"palette": "bubbly", "out": "sfx", "sample_rate": SR, "sounds": [
                {"id": "jump", "archetype": "jump", "variants": 2},
                {"id": "combo", "archetype": "combo", "variants": 3},
                {"id": "thud", "recipe": {"layers": [{"wave": "sine", "freq": 80, "freq_end": 40,
                                                      "env": {"decay": 0.2}}], "loudness": -20}},
            ]}
            pp = os.path.join(d, "soundpass.json")
            with open(pp, "w") as f:
                json.dump(plan, f)
            r = cli("pack", pp)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = os.path.join(d, "sfx")
            with open(os.path.join(out, "manifest.json")) as f:
                m = json.load(f)
            self.assertEqual([s["id"] for s in m["sounds"]], ["jump", "combo", "thud"])
            self.assertEqual(m["sounds"][1]["files"], ["combo_01.wav", "combo_02.wav", "combo_03.wav"])
            self.assertTrue(m["sounds"][1]["ladder"])
            for s in m["sounds"]:
                for fn in s["files"]:
                    self.assertTrue(os.path.exists(os.path.join(out, fn)))
            self.assertTrue(os.path.exists(os.path.join(out, "preview.html")))
            r = cli("pack", pp, "--only", "thud")
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(out, "manifest.json")) as f:
                self.assertEqual(len(json.load(f)["sounds"]), 3)

    def test_render_and_analyze(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "laser.wav")
            r = cli("render", "shoot", "--palette", "scifi", "--set", "pitch=-3", "-o", p, "--rate", str(SR))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("pitch falling", r.stdout)
            r = cli("analyze", p, "--json")
            self.assertEqual(json.loads(r.stdout)[0]["pitch"]["motion"], "falling")

    def test_bad_plan_is_a_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "p.json")
            with open(pp, "w") as f:
                json.dump({"palette": "cozy", "sounds": [{"id": "Bad Id", "archetype": "coin"}]}, f)
            r = cli("pack", pp)
            self.assertEqual(r.returncode, 2)
            self.assertIn("lowercase", r.stderr)


if __name__ == "__main__":
    unittest.main()
