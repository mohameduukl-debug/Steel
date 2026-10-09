"""Hub (tensile-structures) tests: end-to-end statics of the tool chain, factor register, report, validation matrix.

Run:  python3 -m unittest tests.test_tensile_structures -v
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, ".claude", "skills")


def load(skill, name):
    path = os.path.join(SK, skill, "scripts", name + ".py")
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


fdm = load("tensile-analysis", "form_find_fdm")
dr = load("tensile-analysis", "dynamic_relaxation")
mdr = load("tensile-analysis", "membrane_dr")
corner = load("tensile-connections", "corner_plate")
CF = load("tensile-structures", "factors")
rep = load("tensile-structures", "report")
va = load("tensile-structures", "validate_all")


def plan_area(model, key="xyz"):
    """Plan (x-y) area of the faces, independent of the tools: shoelace formula per face."""
    xyz = {n["id"]: n[key] for n in model["nodes"]}
    a = 0.0
    for f in model["faces"]:
        pts = [xyz[i] for i in f]
        a += abs(sum(pts[k][0] * pts[(k + 1) % len(pts)][1] - pts[(k + 1) % len(pts)][0] * pts[k][1]
                     for k in range(len(pts)))) / 2.0
    return a


class TestChainStatics(unittest.TestCase):
    """Independent statics: under snow s on plan area A, the supports must carry exactly s*A vertically,
    and the horizontal reactions must cancel. The plan area is computed here, not by the tools."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.path = os.path.join(cls.tmp, "sail")
        quiet(fdm.main, ["sail4", "--n", "10", "--prestress", "2.0", "--out", cls.path])

    def check(self, m, s):
        deformed = {"nodes": [{"id": n["id"], "xyz": n["xyz"]} for n in m["nodes"]], "faces": m["faces"]}
        A = plan_area(deformed)
        Rz = sum(r["pull"][2] for r in m["reactions"])
        Rx = sum(r["pull"][0] for r in m["reactions"])
        Ry = sum(r["pull"][1] for r in m["reactions"])
        self.assertAlmostEqual(-Rz, s * A, delta=0.01 * s * A)     # pull points into the structure: Σpull_z = -s·A
        self.assertAlmostEqual(Rx, 0.0, delta=0.01 * s * A)
        self.assertAlmostEqual(Ry, 0.0, delta=0.01 * s * A)
        return A

    def test_snow_cable_net(self):
        m = quiet(dr.main, [self.path + ".json", "--snow", "0.75", "--tol", "1e-5"])
        self.check(m, 0.75)

    def test_snow_cst_membrane(self):
        m = quiet(mdr.main, [self.path + ".json", "--snow", "0.75", "--out", os.path.join(self.tmp, "cst")])
        self.check(m, 0.75)

    def test_corner_reaction_passes_to_corner_plate(self):
        """The anchor force of corner_plate equals the support reaction of the analysis when it is fed the
        member forces meeting at that support (equilibrium of the corner node)."""
        m = quiet(dr.main, [self.path + ".json", "--snow", "0.75", "--tol", "1e-5"])
        r = max(m["reactions"], key=lambda r: r["magnitude"])
        xyz = {n["id"]: n["xyz"] for n in m["nodes"]}
        args = []
        for e in m["edges"]:
            if r["node"] in e["n"] and abs(e.get("force", 0)) > 1e-9:
                o = e["n"][1] if e["n"][0] == r["node"] else e["n"][0]
                d = [xyz[o][c] - xyz[r["node"]][c] for c in range(3)]
                args += ["--v", f"e{e['id']}:{d[0]}:{d[1]}:{d[2]}:{e['force']}"]
        if len(args) < 4:
            self.skipTest("corner has fewer than two members")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            corner.main(args)
        txt = out.getvalue()
        F = float(txt.split("Required anchor force")[1].split("kN")[0])
        self.assertAlmostEqual(F, r["magnitude"], delta=0.02 * r["magnitude"])


class TestFactorRegister(unittest.TestCase):
    def test_every_entry_has_status_source_and_range_when_uncertain(self):
        reg = CF.load()
        n = 0
        for path, e in CF.iter_entries(reg):
            n += 1
            self.assertIn(e.get("status"), ("V", "C", "U"), path)
            self.assertTrue(e.get("source"), path)
            if e["status"] == "U" and isinstance(e.get("value"), (int, float)):
                self.assertIn("range", e, f"{path}: U value without range")
        self.assertGreater(n, 50)

    def test_project_override_precedence(self):
        tmp = tempfile.mkdtemp()
        f = os.path.join(tmp, "p.json")
        path = "steel.gM0"
        base = CF.get(path)
        with open(f, "w") as fh:
            json.dump({"steel": {"gM0": {"value": base + 0.05, "status": "V", "source": "NA test"}}}, fh)
        self.assertAlmostEqual(CF.get(path, f), base + 0.05)
        self.assertEqual(CF.status(path, f), "V")
        self.assertAlmostEqual(CF.get(path), base)          # default untouched


class TestReportAndValidation(unittest.TestCase):
    def test_table_rows_parser(self):
        md = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\ntext\n| x |\n|:-:|\n| y |\n"
        self.assertEqual(va.table_rows(md), [["1", "2"], ["3", "4"], ["y"]])

    def test_matrix_covers_all_skills(self):
        rows = va.matrix()
        names = {r["skill"] for r in rows}
        self.assertTrue({"tensile-structures", "tensile-analysis", "connection-precedents"} <= names)
        cp = next(r for r in rows if r["skill"] == "connection-precedents")
        self.assertTrue(cp["validation_md"])
        self.assertEqual(cp["uncovered"], [])

    def test_report_with_precedents_and_validation(self):
        tmp = tempfile.mkdtemp()
        ex = [os.path.join(ROOT, "examples", f"precedents_{n}_example.json") for n in ("corner", "masthead")]
        md = quiet(rep.main, ["--precedents", *ex, "--validation", "--out", os.path.join(tmp, "r")])
        self.assertIn("Connection precedents", md)
        self.assertEqual(md.count("| PASS |"), 2)
        self.assertIn("Validation of the tools", md)
        # a failing gate shows up as a governing item
        with open(ex[0]) as fh:
            d = json.load(fh)
        d["searched"] = [q for q in d["searched"] if q.isascii()]
        bad = os.path.join(tmp, "bad.json")
        with open(bad, "w") as fh:
            json.dump(d, fh)
        md = quiet(rep.main, ["--precedents", bad, "--out", os.path.join(tmp, "r2")])
        self.assertIn("| FAIL |", md)
        self.assertIn("precedent gate corner-plate", md)


if __name__ == "__main__":
    unittest.main()
