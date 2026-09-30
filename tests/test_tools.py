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
mdr = load("tensile-analysis", "membrane_dr")
sched = load("cable-tension-members", "cable_schedule")
pin = load("tensile-connections", "pin_connection")
corner = load("tensile-connections", "corner_plate")
mast = load("steel-supports", "mast_check")
mem = load("membrane-fabric", "membrane_check")
biax = load("membrane-fabric", "biaxial_fit")
memb = load("steel-supports", "member_check")
joint = load("tensile-connections", "steel_joint_checks")
frame = load("steel-supports", "frame2d")
fat = load("tensile-connections", "fatigue_check")
found = load("steel-supports", "foundation_check")
cut = load("fabrication-drawings", "cutting_pattern")
dxfw = load("fabrication-drawings", "dxf_writer")
nestm = load("fabrication-drawings", "nest_panels")


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


class TestCSTMembrane(unittest.TestCase):
    Ew, Ef, nu, G = 800.0, 600.0, 0.3, 30.0

    def flat(self, wrinkling=False):
        m = fdm.gen_sail4(2.0, 0.0, 6, 1, 1, True)
        return mdr.Membrane(m, self.Ew, self.Ef, self.nu, self.G, 1e4, prestress=(0.0, 0.0), wrinkling=wrinkling)

    def solve(self, mem, fmap):
        X = [fmap(p) if mem.fixed[i] else list(p) for i, p in enumerate(mem.X0)]
        X, _, _ = mem.relax(X, tol=1e-9, maxit=50000)
        return mem.results(X)[0]

    def test_patch_uniform_stretch(self):
        els = self.solve(self.flat(), lambda p: [p[0] * 1.01, p[1], p[2]])
        E11 = 0.01 + 0.01 ** 2 / 2
        nufw = self.nu * self.Ef / self.Ew
        den = 1 - self.nu * nufw
        for e in els:
            self.assertAlmostEqual(e["n_warp"], self.Ew / den * E11, places=6)
            self.assertAlmostEqual(e["n_weft"], nufw * self.Ew / den * E11, places=6)
            self.assertAlmostEqual(e["n_shear"], 0.0, places=6)

    def test_simple_shear(self):
        g = 0.02
        els = self.solve(self.flat(), lambda p: [p[0] + g * p[1], p[1], p[2]])
        nufw = self.nu * self.Ef / self.Ew
        den = 1 - self.nu * nufw
        self.assertAlmostEqual(els[0]["n_shear"], self.G * g, places=6)
        self.assertAlmostEqual(els[0]["n_weft"], self.Ef / den * g * g / 2, places=6)

    def test_wrinkling_no_compression(self):
        els = self.solve(self.flat(True), lambda p: [p[0] * 1.01, p[1] * 0.99, p[2]])
        self.assertTrue(all(e["wrinkled"] == 1 for e in els))
        self.assertGreaterEqual(min(e["n2"] for e in els), -1e-9)

    def test_sail_equilibrium_and_vs_net(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "s")
        quiet(fdm.main, ["sail4", "--n", "10", "--prestress", "2", "--out", p])
        with open(p + ".json") as fh:
            base = json.load(fh)
        r = mdr.analyse(base, pressure=0.8, tol=1e-5)
        X = [n["xyz"] for n in r["nodes"]]
        loads = dr.external_loads(r, X, 0.8, 0.0)
        for c in range(3):
            self.assertAlmostEqual(sum(rc["pull"][c] for rc in r["reactions"]), sum(v[c] for v in loads.values()),
                                   delta=0.02 * max(1.0, abs(sum(v[c] for v in loads.values()))))
        net = dr.analyse(base, pressure=0.8)
        ratio = r["analysis"]["max_displacement_m"] / net["analysis"]["max_displacement_m"]
        self.assertTrue(0.6 < ratio < 1.2, ratio)   # shear stiffness makes the membrane somewhat stiffer

    def test_cases_with_cst_solver(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "s")
        quiet(fdm.main, ["sail4", "--n", "8", "--prestress", "2", "--out", p])
        cf = os.path.join(tmp, "c.json")
        with open(cf, "w") as fh:
            json.dump({"solver": "cst", "material": {"Et_u": 800, "Et_v": 600, "nu": 0.3, "G": 30},
                       "cases": [{"name": "PS"}, {"name": "W_up", "pressure": 0.6}]}, fh)
        env = quiet(cases.run, p + ".json", cf, None)
        self.assertGreater(env["summary"][1]["warp_max"], env["summary"][0]["warp_max"])


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


class TestFrame2D(unittest.TestCase):
    def EI(self, spec):
        return 210e6 * memb.Section(spec).Iy * 1e-12

    def test_euler_columns(self):
        for base, k in (("pinned", 1.0), ("fixed", 2.0)):
            fr = frame.gen_mast(10, 20, 219.1, 219.1, 219.1, 8, 355, base, 1.0, 0.0, [])
            _, _, f = fr.linear()
            lam, _ = fr.buckling(f)
            self.assertAlmostEqual(lam / (math.pi ** 2 * self.EI("CHS:219.1x8") / (k * 10) ** 2), 1.0, delta=0.002)

    def test_simply_supported_beam(self):
        d = {"nodes": [[i * 0.5, 0] for i in range(21)], "supports": {"0": [1, 1, 0], "20": [0, 1, 0]},
             "members": [{"name": "B", "nodes": list(range(21)), "section": "IPE300"}],
             "loads": {"udl": [{"member": "B", "qy": -10}]}}
        fr = frame.from_json(d)
        dm, u, fo = fr.linear()
        EI = self.EI("IPE300")
        self.assertAlmostEqual(u[dm[(10, 1)]], -5 * 10 * 10 ** 4 / (384 * EI), places=9)
        self.assertAlmostEqual(max(max(abs(x["M1"]), abs(x["M2"])) for x in fo), 125.0, places=6)
        R = fr.reactions(dm, u)
        self.assertAlmostEqual(R[0][1] + R[20][1], 100.0, places=6)

    def test_parabolic_arch_vs_timoshenko(self):
        # Timoshenko & Gere, Theory of Elastic Stability, uniformly loaded parabolic arches q_cr = γ EI / L^3
        EI = self.EI("CHS:323.9x10")
        for f_L, sup, gam in ((0.1, "pinned", 28.5), (0.2, "pinned", 45.4), (0.2, "fixed", 101.0)):
            fr = frame.gen_arch(30, 30 * f_L, 40, "CHS:323.9x10", 355, sup, 1.0)
            _, _, fo = fr.linear()
            lam, _ = fr.buckling(fo)
            self.assertAlmostEqual(lam * 30 ** 3 / EI / gam, 1.0, delta=0.04)

    def test_second_order_amplification(self):
        # pinned column, midspan point load, N = 0.5 Ncr: M2/M1 = tan(u)/u, u = (π/2)√(N/Ncr)
        fr = frame.gen_mast(8, 16, 219.1, 219.1, 219.1, 8, 355, "pinned", 1.0, 0.0, [])
        _, _, f = fr.linear()
        Ncr, _ = fr.buckling(f)
        N = 0.5 * Ncr
        d = {"nodes": [[0, 0.5 * i] for i in range(17)], "supports": {"0": [1, 1, 0], "16": [1, 0, 0]},
             "members": [{"name": "C", "nodes": list(range(17)), "section": "CHS:219.1x8"}],
             "loads": {"nodal": {"16": [0, -N, 0], "8": [1.0, 0, 0]}}}
        fr2 = frame.from_json(d)
        _, _, f1 = fr2.linear()
        _, _, f2 = fr2.second_order(None)
        M1 = max(max(abs(x["M1"]), abs(x["M2"])) for x in f1)
        M2 = max(max(abs(x["M1"]), abs(x["M2"])) for x in f2)
        uu = math.pi / 2 * math.sqrt(0.5)   # exact beam-column solution for a midspan point load (Timoshenko)
        self.assertAlmostEqual(M2 / M1, math.tan(uu) / uu, delta=0.01)

    def test_arch_design_runs(self):
        res = frame.run(frame.gen_arch(30, 6, 24, "CHS:323.9x10", 355, "pinned", 12.0), check=True, quiet=True)
        self.assertGreater(res["alpha_cr"], 1.0)
        self.assertTrue(res["design"][0]["util_equiv_column"] > 0)


class TestClass4AndFoundations(unittest.TestCase):
    def test_class4_rhs_effective_area(self):
        s = memb.Section("RHS:300x300x6:cold")
        e = memb.effective_section(s, 355)
        eps = math.sqrt(235 / 355)
        lp = (300 - 18) / 6 / (28.4 * eps * 2)
        rho = (lp - 0.22) / lp ** 2
        self.assertAlmostEqual(e["A_eff"], s.A - 4 * (1 - rho) * 282 * 6, delta=1.0)

    def test_shear_reduction(self):
        s = memb.Section("IPE300")
        rows, res = memb.check(s, 355, 3, 0, 80, Vz=400)
        u = [r for r in rows if r[0].startswith("section")][0][1]
        Vpl = [r for r in rows if r[0].startswith("shear")][0][2]
        rho = (2 * 400 / Vpl - 1) ** 2
        W = s.Wpl_y - rho * (300 - 2 * 10.7) ** 2 * 7.1 / 4
        self.assertAlmostEqual(u, 80e6 / (W * 355), places=4)

    def test_block(self):
        rows, info = found.block(2, 2, 1.2, 60, 45, 0.3, 0.45, 200)
        self.assertAlmostEqual(info["W_kN"], 2 * 2 * 1.2 * 24, places=6)
        self.assertAlmostEqual(rows[0][2], 0.9 * 115.2, places=6)
        self.assertAlmostEqual(rows[1][2], (0.9 * 115.2 - 60) * 0.45 / 1.1, places=6)


class TestAnchorsFatigueClamps(unittest.TestCase):
    def test_single_anchor_cone_and_pullout(self):
        rows, info = joint.anchor_group(1, 1, 0, 0, 1000, 1000, 200, 20, 38, "8.8", 30, 50.0, cracked=True)
        self.assertAlmostEqual(info["N0_Rk_c"], 8.9 * math.sqrt(30) * 200 ** 1.5 / 1e3, places=6)
        self.assertAlmostEqual(rows[2][2], info["N0_Rk_c"] / 1.5, places=6)          # far from edges: Ac = A0
        self.assertAlmostEqual(rows[1][2], 7.5 * math.pi / 4 * (38 ** 2 - 20 ** 2) * 30 / 1e3 / 1.5, places=6)
        self.assertAlmostEqual(info["gMs"], 1.5, places=9)                              # 1.2·800/640

    def test_anchor_group_area_ratio(self):
        rows, info = joint.anchor_group(2, 2, 200, 200, 400, 400, 250, 24, 45, "8.8", 30, 150.0)
        self.assertAlmostEqual(info["NRk_c"] / info["N0_Rk_c"], 950 ** 2 / 750 ** 2, places=6)

    def test_fatigue_curve_points(self):
        # at Δσ_C/γMf and 2e6 cycles the damage is exactly 1
        D, _ = fat.check([(71 / 1.35, 2e6)], 71, 1.35)
        self.assertAlmostEqual(D, 1.0, places=9)
        D, _ = fat.check([(0.4 * 71 / 1.35, 1e9)], 71, 1.35)                            # below cut-off
        self.assertEqual(D, 0.0)
        D, _ = fat.check([(40, 1e6), (25, 5e6)], 71, 1.35)
        self.assertAlmostEqual(D, 1e6 / (2e6 * (71 / 54) ** 3) + 5e6 / (5e6 * (0.737 * 71 / 33.75) ** 5), places=6)

    def test_cable_clamp_and_saddle(self):
        a = type("A", (), dict(dT=12.0, nb=2, bolt_d=16.0, grade="8.8", surfaces=2))
        u = quiet(cab.cmd_clamp, a)
        FRd = 2 * 0.1 * 2 * 0.7 * 800 * 157 / 1e3 * 0.8 / 1.65
        self.assertAlmostEqual(u, 12.0 / FRd, places=6)
        b = type("B", (), dict(T=400.0, R=0.6, d=40.0, type="FLC", delta=6.0, E=160.0))
        self.assertAlmostEqual(quiet(cab.cmd_saddle, b), 400e3 / (600 * 40) / 40.0, places=6)


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


class TestBiaxialAndMembraneExtras(unittest.TestCase):
    def synthetic(self, Ew=900.0, Ef=600.0, nu=0.35):
        a, b = 1 / Ew, 1 / Ef
        c = nu * a
        pts = []
        for rw, rf in ((1, 1), (2, 1), (1, 2), (1, 0), (0, 1)):
            for k in range(1, 6):
                nw, nf = 2.0 * k * rw, 2.0 * k * rf
                pts.append((nw, nf, a * nw - c * nf, b * nf - c * nw))
        return pts

    def test_fit_recovers_constants(self):
        f = biax.fit(self.synthetic())
        self.assertAlmostEqual(f["Ew_t"], 900.0, places=6)
        self.assertAlmostEqual(f["Ef_t"], 600.0, places=6)
        self.assertAlmostEqual(f["nu_wf"], 0.35, places=9)
        self.assertAlmostEqual(f["nu_fw"], 0.35 * 600 / 900, places=9)   # reciprocity

    def test_fixed_nu_single_ratio(self):
        pts = [p for p in self.synthetic() if p[0] == p[1]]           # 1:1 only
        f = biax.fit_fixed_nu(pts, 0.35)
        self.assertAlmostEqual(f["Ew_t"], 900.0, places=6)
        self.assertAlmostEqual(f["Ef_t"], 600.0, places=6)

    def test_tear_and_curvature_cli(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            mem.main(["--material", "PVC-III", "--nw", "12", "--tear", "50", "45", "--defect", "200"])
        self.assertIn(f"{45 * math.sqrt(50 / 200):.2f}", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            mem.main(["--material", "PVC-III", "--curvature", "12", "18", "--p", "0.8", "--prestress", "2", "2"])
        self.assertIn("11.60", out.getvalue())
        self.assertIn("SLACK", out.getvalue())


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
        ends = [i for i, k in enumerate(kinds) if k.startswith("end")]
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


class TestFabricationExtras(unittest.TestCase):
    def patterns(self, *extra):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "mb")
        quiet(fdm.main, ["multibay", "--bays", "2", "--qc", "3", "--prestress", "2", "--out", p])
        out = os.path.join(tmp, "pat")
        rows = quiet(cut.main, [p + ".json", "--strip", "1", "--roll-width", "2670", "--out", out] + list(extra))
        with open(out + ".json") as fh:
            return rows, json.load(fh), tmp

    def test_auto_split_fits_roll_and_notches_match(self):
        rows, data, _ = self.patterns("--auto-split", "--notch", "800")
        self.assertTrue(all(r["fits_roll"] for r in rows))
        # each seam's match-mark labels (positions along the full seam) are the same set on both sides
        sides = {}
        for pnl in data["panels"]:
            for m in pnl["notches"]:
                sides.setdefault((m["seam"], pnl["panel"]), set()).add(m["k"])
        by_seam = {}
        for (sid, pid), ks in sides.items():
            by_seam.setdefault(sid, []).append(ks)
        for sid, sets in by_seam.items():
            full = max(sets, key=len)                     # the unsplit side carries every mark
            rest = [x for x in sets if x is not full]
            self.assertEqual(set().union(*rest), full, sid)  # split halves together = the other side
            for i in range(len(rest)):
                for j in range(i + 1, len(rest)):
                    self.assertFalse(rest[i] & rest[j], sid)   # halves do not duplicate marks

    def test_nesting_no_overlap_within_roll(self):
        rows, data, tmp = self.patterns("--auto-split")
        placed, length = nestm.nest(data["panels"], 2670, 25, 20)
        self.assertEqual(len(placed), len(data["panels"]))
        for q in placed:
            ys = [y for _, y in q["poly"]]
            self.assertGreaterEqual(min(ys), -1e-6)
            self.assertLessEqual(max(ys), 2670 + 1e-6)
        # no two panels overlap: sample panel interiors on a grid
        for i, a in enumerate(placed):
            for b in placed[i + 1:]:
                ax = [x for x, _ in a["poly"]]
                bx = [x for x, _ in b["poly"]]
                if max(ax) < min(bx) or max(bx) < min(ax):
                    continue
                x0, x1 = max(min(ax), min(bx)), min(max(ax), max(bx))
                for k in range(1, 20):
                    xq = x0 + (x1 - x0) * k / 20
                    for yq in range(0, 2670, 60):
                        self.assertFalse(cut.inside((xq, yq), a["poly"]) and cut.inside((xq, yq), b["poly"]))

    def test_weld_symbol_entities(self):
        d = dxfw.DXF()
        d.weld_symbol((0, 0), "a8", both_sides=True, h=5)
        txt = d.tostring()
        self.assertEqual(txt.count("\na8\n"), 2)
        self.assertIn("WELD", txt)


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
