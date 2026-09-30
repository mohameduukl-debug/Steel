"""Regression tests for the tensile-structure skill tools (stdlib unittest).

Run:  python3 -m unittest discover -s tests -v
"""
import contextlib
import importlib.util
import io
import json
import math
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
cab = load("cable-tension-members", "cable_calc")
sched = load("cable-tension-members", "cable_schedule")
pin = load("tensile-connections", "pin_connection")
corner = load("tensile-connections", "corner_plate")
mast = load("steel-supports", "mast_check")
mem = load("membrane-fabric", "membrane_check")
cut = load("fabrication-drawings", "cutting_pattern")
dxfw = load("fabrication-drawings", "dxf_writer")


class TestFormFinding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def run_ff(self, *args):
        out = os.path.join(self.tmp, "m")
        return quiet(fdm.main, list(args) + ["--out", out]), out + ".json"

    def test_sail_symmetry_and_equilibrium(self):
        m, _ = self.run_ff("sail4", "--n", "12", "--prestress", "2.0")
        mags = [r["magnitude"] for r in m["reactions"]]
        self.assertEqual(len(mags), 4)
        for v in mags:
            self.assertAlmostEqual(v, mags[0], places=3)
        for c in range(3):  # no external load -> support pulls sum to zero
            self.assertAlmostEqual(sum(r["pull"][c] for r in m["reactions"]), 0.0, places=3)
        self.assertAlmostEqual(m["membrane_stress"]["mean"], 2.0, places=6)
        for g in m["cable_groups"]:
            self.assertTrue(0.05 < g["sag_ratio"] < 0.2)

    def test_q_scaling_invariance(self):
        m1 = fdm.gen_sail4(10, 3, 8, 1.0, 10.0, False)
        m2 = fdm.gen_sail4(10, 3, 8, 5.0, 50.0, False)
        fdm.solve_fdm(m1)
        fdm.solve_fdm(m2)
        for a, b in zip(m1["nodes"], m2["nodes"]):
            for c in range(3):
                self.assertAlmostEqual(a["xyz"][c], b["xyz"][c], places=6)

    def test_cone_runs(self):
        m, _ = self.run_ff("cone", "--nr", "6", "--nc", "24", "--anchors", "6", "--prestress", "2.0")
        self.assertEqual(len(m["cable_groups"]), 6)
        self.assertGreater(m["surface_area_m2"], 100)


class TestDynamicRelaxation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "sail")
        quiet(fdm.main, ["sail4", "--n", "10", "--prestress", "2.0", "--out", self.path])

    def test_prestress_state_is_equilibrium(self):
        m = quiet(dr.main, [self.path + ".json"])
        self.assertEqual(m["analysis"]["iterations"], 0)

    def test_uplift_global_equilibrium(self):
        p = 0.8
        m = quiet(dr.main, [self.path + ".json", "--pressure", str(p), "--tol", "1e-5"])
        X = [n["xyz"] for n in m["nodes"]]
        loads = dr.external_loads(m, X, p, 0.0)
        for c in range(3):
            tot_load = sum(v[c] for v in loads.values())
            tot_pull = sum(r["pull"][c] for r in m["reactions"])
            self.assertAlmostEqual(tot_pull, tot_load, delta=0.01 * max(1.0, abs(tot_load)))
        self.assertGreater(m["analysis"]["max_displacement_m"], 0.05)
        self.assertLess(m["analysis"]["max_residual_kN"], 1e-4)


class TestCables(unittest.TestCase):
    def test_catenary_vs_parabola_small_sag(self):
        H = cab.solve_H(20, 0, 0.05, 0.8, "f")
        c = cab.Catenary(20, 0, 0.05, H)
        self.assertAlmostEqual(c.sag_mid, 0.8, places=6)
        p = cab.parabola(20, 0, 0.05, H=H)
        self.assertAlmostEqual(p["f"], 0.8, delta=0.01)
        self.assertAlmostEqual(c.length, p["length"], delta=0.001)

    def test_inclined_catenary_end_tensions(self):
        c = cab.Catenary(20, 4, 1.0, 50)
        self.assertAlmostEqual(c.T(20) - c.T(0), 1.0 * 4, places=6)  # T_B − T_A = w·h (catenary property)

    def test_edge_cable(self):
        a = type("A", (), {"chord": 10.0, "sag": 1.0, "n": 3.0})
        self.assertAlmostEqual(quiet(cab.cmd_edge, a), 39.0, places=6)

    def test_resistance(self):
        a = type("A", (), dict(Fmin=537.0, ke=0.9, gammaR=1.0, Fk=None, FEd=240.0, Fser=None, fsls=0.5,
                               Nf=1.0, asce=2.2, T_asce=None, Fmin_force=None))
        self.assertAlmostEqual(quiet(cab.cmd_resist, a), 537 * 0.9 / 1.5, places=6)

    def test_schedule_length(self):
        s = {"T_ref": 20, "cables": [{"id": "C1", "A": 100.0, "E": 160.0, "Fmin": 150.0, "L_stressed": 10.0,
                                      "F_prestress": 16.0, "F_ULS": 60.0, "T_install": 30.0,
                                      "deduct_A_mm": 100, "deduct_B_mm": 100}]}
        r = sched.compute(s)[0]
        EA = 16000.0
        L0 = 9.8 / (1 + 16 / EA) / (1 + 12e-6 * 10)
        self.assertAlmostEqual(r["L0_pin_unstressed_Tref_m"], round(L0, 4), places=4)
        self.assertAlmostEqual(r["F_Rd_kN"], 100.0, places=1)


class TestConnections(unittest.TestCase):
    def test_en1993_worked_example(self):
        rows = pin.en1993(250, 170, 40, 41, 20, 50, 35, 355, 490, 640, 800, 15, 2, True)
        d = {r[0]: r for r in rows}
        self.assertAlmostEqual(d["Pin shear per plane [kN]"][2], 482.55, delta=0.1)
        self.assertAlmostEqual(d["Bearing ULS, lug plate [kN]"][2], 426.0, delta=0.1)
        self.assertAlmostEqual(d["Pin bending [kNm]"][1], 1.8125, delta=0.001)
        self.assertAlmostEqual(d["Pin bending [kNm]"][2], 6.03, delta=0.01)
        self.assertAlmostEqual(d["Lug end distance a (beyond hole, in line of force) [mm]"][1], 44.94, delta=0.02)
        self.assertAlmostEqual(d["Lug side distance c (beside hole) [mm]"][1], 31.27, delta=0.02)
        self.assertAlmostEqual(d["Bearing SLS (replaceable pin), lug plate [kN]"][2], 170.4, delta=0.1)
        self.assertAlmostEqual(d["Contact stress sigma_h,Ed (lug) [MPa]"][1], 624.2, delta=0.5)

    def test_corner_symmetric(self):
        R, ang = quiet(corner.solve2d, [("EC1", 0.0, 100.0), ("EC2", 90.0, 100.0)])
        self.assertAlmostEqual(R, 100 * math.sqrt(2), places=6)
        self.assertAlmostEqual(ang, -135.0, places=6)

    def test_corner_concurrent_holes(self):
        # holes on each member's line of action -> zero moment
        ms = [("EC1", 15.0, 48.0, 180 * math.cos(math.radians(15)), 180 * math.sin(math.radians(15))),
              ("EC2", 105.0, 52.0, 150 * math.cos(math.radians(105)), 150 * math.sin(math.radians(105)))]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            corner.solve2d(ms)
        self.assertIn("concurrent", out.getvalue())


class TestSteel(unittest.TestCase):
    def test_chs_properties_and_buckling(self):
        r = mast.check(219.1, 8, 7.5, 420, 12, 355)
        self.assertAlmostEqual(r["A_mm2"], 5306, delta=5)
        self.assertAlmostEqual(r["I_mm4"], 2.96e7, delta=0.01e7)
        self.assertEqual(r["class"], 1)
        self.assertTrue(0.4 < r["chi"] < 0.5)


class TestMembrane(unittest.TestCase):
    def test_factor_method(self):
        al, _ = mem.allowable(112, "factor", "wind", "PES/PVC", 4.0, 5.0, "P+D+W")
        self.assertAlmostEqual(al, 28.0)
        al, _ = mem.allowable(100, "fm", "prestress", "PES/PVC", 4, 5, "P+D")
        self.assertAlmostEqual(al, 12.5)
        al, _ = mem.allowable(100, "japan", "snow", "PES/PVC", 4, 5, "P+D")
        self.assertAlmostEqual(al, 12.5)

    def test_library_loads(self):
        lib = mem.load_lib()
        self.assertIn("PVC-II", lib["materials"])


class TestPatterning(unittest.TestCase):
    def test_flat_panel_exact(self):
        # flat hypar (high=0) is developable: zero flattening strain, net area = 3D area when no compensation
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "flat")
        m = quiet(fdm.main, ["hypar", "--size", "6", "--high", "0", "--n", "6", "--out", p])
        rows = quiet(cut.main, [p + ".json", "--strip", "2", "--comp-warp", "0", "--comp-weft", "0",
                                "--out", os.path.join(tmp, "pat")])
        self.assertLess(max(r["flatten_strain_max_%"] for r in rows), 1e-3)
        self.assertAlmostEqual(sum(r["net_area_m2"] for r in rows), m["surface_area_m2"], delta=0.01)
        self.assertTrue(os.path.exists(os.path.join(tmp, "pat.dxf")))

    def test_curved_sail_low_strain(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "sail")
        quiet(fdm.main, ["sail4", "--n", "16", "--prestress", "2", "--out", p])
        rows = quiet(cut.main, [p + ".json", "--strip", "2", "--out", os.path.join(tmp, "pat")])
        self.assertLess(max(r["flatten_strain_max_%"] for r in rows), 0.5)


class TestFactors(unittest.TestCase):
    def test_project_override(self):
        fac = load("tensile-structures", "factors")
        self.assertEqual(fac.get("cable.gammaR"), 1.0)
        tmp = tempfile.mkdtemp()
        pf = os.path.join(tmp, "p.json")
        with open(pf, "w") as fh:
            json.dump({"cable": {"gammaR": {"value": 1.1, "status": "V", "source": "test"}}}, fh)
        self.assertEqual(fac.get("cable.gammaR", pf), 1.1)
        self.assertEqual(fac.get("cable.asce19_factor", pf), 2.2)  # untouched keys keep defaults
        os.environ["TENSILE_FACTORS"] = pf
        try:
            s = {"cables": [{"id": "C", "A": 100.0, "E": 160.0, "Fmin": 165.0, "L_stressed": 5.0, "F_ULS": 50}]}
            self.assertAlmostEqual(sched.compute(s)[0]["F_Rd_kN"], 100.0, places=1)  # 165/(1.5*1.1)
        finally:
            del os.environ["TENSILE_FACTORS"]

    def test_every_entry_tagged(self):
        fac = load("tensile-structures", "factors")
        for path, e in fac.iter_entries():
            self.assertIn(e["status"], ("V", "C", "U"), path)
            self.assertTrue(e.get("source"), path)


class TestDXF(unittest.TestCase):
    def test_structure(self):
        d = dxfw.DXF()
        d.layer("CUT", "red")
        d.polyline([(0, 0), (10, 0), (10, 5)], "CUT", closed=True)
        d.text("A", (1, 1), 2, "TEXT")
        d.frame({"PROJECT": "x", "DWG No": "1"}, 1.0)
        s = d.tostring()
        self.assertTrue(s.startswith("0\nSECTION"))
        self.assertTrue(s.rstrip().endswith("EOF"))
        self.assertIn("AC1009", s)
        self.assertIn("\nCUT\n", s)
        self.assertEqual(s.count("POLYLINE"), s.count("SEQEND"))


if __name__ == "__main__":
    unittest.main()
