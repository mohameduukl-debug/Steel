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
cases = load("tensile-analysis", "run_cases")
sched = load("cable-tension-members", "cable_schedule")
pin = load("tensile-connections", "pin_connection")
corner = load("tensile-connections", "corner_plate")
mast = load("steel-supports", "mast_check")
mem = load("membrane-fabric", "membrane_check")
memb = load("steel-supports", "member_check")
joint = load("tensile-connections", "steel_joint_checks")
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


class TestPondingAndCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def ff(self, *args):
        p = os.path.join(self.tmp, "m")
        quiet(fdm.main, list(args) + ["--out", p])
        with open(p + ".json") as fh:
            return json.load(fh), p + ".json"

    def test_flat_hypar_ponds(self):
        m, _ = self.ff("hypar", "--size", "10", "--high", "0.3", "--n", "12", "--prestress", "0.6")
        r = dr.analyse(m, snow=0.5, do_ponding=True)
        self.assertGreater(r["analysis"]["ponding"]["water_volume_m3"], 1.0)
        self.assertIn("INSTABILITY", r["analysis"]["ponding"]["status"])

    def test_sail_drains(self):
        m, _ = self.ff("sail4", "--n", "10", "--prestress", "2")
        r = dr.analyse(m, snow=0.75, do_ponding=True)
        self.assertLess(r["analysis"]["ponding"]["water_volume_m3"], 1e-6)

    def test_priority_flood_bowl(self):
        # 3x3 bowl: centre 1 m below a flat rim of outlets -> depth 1 m at centre only
        X = [[i, j, 0.0 if (i, j) != (1, 1) else -1.0] for j in range(3) for i in range(3)]
        model = {"nodes": [{"fixed": (i, j) != (1, 1)} for j in range(3) for i in range(3)],
                 "edges": [{"n": [4, k], "kind": "membrane"} for k in (1, 3, 5, 7)], "faces": []}
        d = dr.water_depths(model, X, dr.outlets(model))
        self.assertAlmostEqual(d[4], 1.0)
        self.assertAlmostEqual(sum(d.values()), 1.0)

    def test_cases_envelope(self):
        m, path = self.ff("sail4", "--n", "8", "--prestress", "2")
        cf = os.path.join(self.tmp, "c.json")
        with open(cf, "w") as fh:
            json.dump({"cases": [{"name": "PS"}, {"name": "UP", "factor": 1.5, "pressure": 0.6},
                                 {"name": "G", "gradient": {"dir_deg": 0, "p_windward": 1.0, "p_leeward": 0.0}},
                                 {"name": "Z", "pressure": 0.1, "zones": [{"poly": [[0, 0], [5, 0], [5, 10], [0, 10]],
                                                                          "p": 1.0}]}]}, fh)
        env = quiet(cases.run, path, cf, None)
        self.assertEqual(len(env["summary"]), 4)
        for g, v in env["groups"].items():
            self.assertGreaterEqual(v["max"], v["min"])
            self.assertEqual(v["case_min"], "PS")
        self.assertTrue(cases.point_in_poly(1, 1, [[0, 0], [2, 0], [2, 2], [0, 2]]))
        self.assertFalse(cases.point_in_poly(3, 1, [[0, 0], [2, 0], [2, 2], [0, 2]]))


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


class TestMemberCheck(unittest.TestCase):
    # EN 10365 / EN 10210 / EN 10219 table values (A cm2, Iy cm4, Iz cm4, Wpl,y cm3, It cm4)
    TABLE = {"IPE200": (28.5, 1943, 142.4, 220.6, 6.98), "HEB200": (78.1, 5696, 2003, 642.5, 59.3),
             "IPE300": (53.8, 8356, 603.8, 628.4, 20.1), "RHS:200x100x8": (44.8, 2234, 739, 282, 1804),
             "SHS:100x5": (18.7, 279, 279, 66.4, 441), "SHS:100x5:cold": (18.4, 271, 271, 64.9, 441)}

    def test_section_properties_vs_tables(self):
        for spec, (A, Iy, Iz, Wpl, It) in self.TABLE.items():
            s = memb.Section(spec)
            for got, ref in ((s.A / 100, A), (s.Iy / 1e4, Iy), (s.Iz / 1e4, Iz), (s.Wpl_y / 1e3, Wpl),
                             (s.It / 1e4, It)):
                self.assertAlmostEqual(got / ref, 1.0, delta=0.02, msg=f"{spec}: {got} vs {ref}")

    def test_chs_matches_mast_check(self):
        rows, res = memb.check(memb.Section("CHS:219.1x8"), 355, 7.5, 420, 12)
        u = max(d / c for _, d, c, _ in rows)
        r = mast.check(219.1, 8, 7.5, 420, 12, 355)
        self.assertAlmostEqual(u, r["u_member_NM"], delta=0.01)

    def test_ltb_mcr_ipe300(self):
        rows, _ = memb.check(memb.Section("IPE300"), 355, 6.0, 0.0, 80, psi_LT=0.0)
        ltb = [r for r in rows if r[0].startswith("LTB")][0]
        self.assertIn("Mcr=169", ltb[0])


class TestJoints(unittest.TestCase):
    def test_weld_pure_tension(self):
        rows, _ = joint.weld(250, 90, 200, 8, 0, 0, "S355")
        self.assertAlmostEqual(rows[0][1], 2 * 625 / (8 * math.sqrt(2)), places=3)   # σ⊥=τ⊥ -> 2σ⊥
        self.assertAlmostEqual(rows[0][2], 490 / (0.9 * 1.25), places=3)
        self.assertAlmostEqual(rows[2][2], 8 * 490 / (math.sqrt(3) * 0.9 * 1.25), places=2)

    def test_bolt_group_torsion(self):
        rows, R = joint.bolts(joint.grid(2, 2, 80, 80), 0, 120, 4, 0, 1, 20, "8.8", 15, 490, 45, 40, 80, 80, True)
        self.assertAlmostEqual(R["FvRd"], 94.08, places=2)
        self.assertAlmostEqual(rows[0][1], math.hypot(12.5, 42.5), places=3)


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


class TestGeodesicAndDecomp(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "sail")
        quiet(fdm.main, ["sail4", "--n", "12", "--prestress", "2", "--out", p])
        with open(p + ".json") as fh:
            self.m = json.load(fh)
        self.X = [[c * 1000 for c in nd["xyz"]] for nd in self.m["nodes"]]

    def test_geodesic_not_longer_than_grid_and_mating_seams(self):
        surf = cut.Surface(self.X, self.m["faces"])
        pans, seams, notes = cut.build_panels(self.m, self.X, "v", 2, "geodesic", surf)
        g = self.m["grid"]
        for k, curve in seams.items():
            grid_line = [self.X[j * (g["nu"] + 1) + k] for j in range(g["nv"] + 1)]
            self.assertLessEqual(cut.polylen(curve), cut.polylen(grid_line) + 1.0)
        for a, b in zip(pans[:-1], pans[1:]):   # right seam of a == left seam of b (shared curve)
            ra = [row[-1] for row in a["grid"]]
            lb = [row[0] for row in b["grid"]]
            self.assertAlmostEqual(cut.polylen(ra), cut.polylen(lb), places=6)

    def test_geodesic_on_plane_is_straight(self):
        # flat square: geodesic between two points = straight chord
        m = fdm.gen_sail4(10, 0, 6, 1, 1, True)
        X = [[c * 1000 for c in nd["xyz"]] for nd in m["nodes"]]
        surf = cut.Surface(X, m["faces"])
        pts = [X[0], [3000, 5000, 0], X[-1]]  # bent start polyline
        geo = cut.geodesic(surf, pts, 9)
        self.assertAlmostEqual(cut.polylen(geo), math.dist(X[0], X[-1]), delta=1.0)

    def test_decompensation_at_ends(self):
        m = fdm.gen_sail4(6, 0, 6, 1, 1, True)   # flat, developable
        X = [[c * 1000 for c in nd["xyz"]] for nd in m["nodes"]]
        pans, _, _ = cut.build_panels(m, X, "v", 2, "grid", None)
        pan = pans[1]
        end3d = cut.polylen(pan["grid"][0])
        mid3d = cut.polylen(pan["grid"][len(pan["grid"]) // 2])
        net, kinds, *_ = cut.process_panel(pan, 0.01, 0.02, 0.0, None, 1000.0)
        # net ring starts with end row 0 (or reversed); measure end-row and mid-rung widths in 2D
        ends = [i for i, k in enumerate(kinds) if k == "end"]
        L_end = sum(math.dist(net[i], net[(i + 1) % len(net)]) for i in ends) / 2
        self.assertAlmostEqual(L_end / end3d, 1.0, delta=0.002)       # decompensated to 0 %
        net2, *_ = cut.process_panel(pan, 0.01, 0.02, None, None, 1000.0)
        ys = [p[1] for p in net2]
        self.assertAlmostEqual((max(ys) - min(ys)) / mid3d, 0.98, delta=0.002)  # full weft compensation


class TestNewShapes(unittest.TestCase):
    def test_multibay_ridge_valley_physics(self):
        m = fdm.gen_multibay(2, 8, 10, 6, 3, 4, 10, 1.0, 15.0, 3.0)
        fdm.solve_fdm(m)
        fdm.compute_results(m, 2.0)
        g = {c["group"]: c for c in m["cable_groups"]}
        self.assertLess(g["RIDGE-2"]["mid_dz"], -0.1)      # ridge cable sags below its chord
        self.assertGreater(g["VALLEY-1"]["mid_dz"], 0.1)   # valley cable hogs above its chord
        sg = m["support_groups"]
        self.assertLess(sg["MAST-2-S"]["pull"][2], 0)      # masts pulled down (compression)
        self.assertGreater(sg["ANCHOR-1-S"]["pull"][2], 0)  # anchors pulled up (uplift)
        for c in range(3):
            self.assertAlmostEqual(sum(v["pull"][c] for v in sg.values()), 0.0, places=3)

    def test_arch_loads_and_symmetry(self):
        m = fdm.gen_arch(20, 10, 4, 3, 24, 12, 1.0, 10.0)
        fdm.solve_fdm(m)
        fdm.compute_results(m, 2.0)
        sg = m["support_groups"]
        for k in (1, 2, 3):
            self.assertLess(sg[f"ARCH-{k}"]["pull"][2], 0)  # membrane pulls the arches down
        self.assertAlmostEqual(sg["ARCH-1"]["magnitude"], sg["ARCH-3"]["magnitude"], places=3)
        self.assertGreater(sg["RAIL-S"]["pull"][2], 0)      # rails pulled up

    def test_flatten_symmetric_panels(self):
        m = fdm.gen_arch(20, 10, 4, 3, 24, 12, 1.0, 10.0)
        fdm.solve_fdm(m)
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "arch.json")
        fdm.compute_results(m, 2.0)
        with open(p, "w") as fh:
            json.dump(m, fh)
        rows = quiet(cut.main, [p, "--strip", "2", "--out", os.path.join(tmp, "pat")])
        s = [r["flatten_strain_max_%"] for r in rows]
        for a, b in zip(s, reversed(s)):
            self.assertAlmostEqual(a, b, delta=0.02)        # mirror-symmetric roof -> mirror-symmetric strains
        self.assertLess(max(s), 2.0)


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
