"""Validation tests for the membrane-fabric skill against independent references.

Every computational path of membrane_check.py, material_select.py and biaxial_fit.py is checked against a
published worked example, a code formula read from the primary text, or a closed-form / independent numerical
solution. Sources are cited per test and summarised in
.claude/skills/membrane-fabric/reference/validation.md.

Run:  python3 -m unittest tests.test_membrane_fabric -v
"""
import contextlib
import importlib.util
import io
import json
import math
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, ".claude", "skills")

JRC23 = "JRC132615 (2023) Prospect for European Guidance for the Structural Design of Tensile Membrane Structures"
JRC25 = "Mollaert & Stimpfle, CEN/TS 19102, JRC 2nd-generation Eurocodes workshop 3-5 June 2025 (D1 slides)"


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


def run(fn, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        res = fn(argv)
    return res, out.getvalue()


mc = load("membrane-fabric", "membrane_check")
ms = load("membrane-fabric", "material_select")
bx = load("membrane-fabric", "biaxial_fit")
CF = mc.F


@contextlib.contextmanager
def project_factors(data):
    """temporary project factor file (TENSILE_FACTORS) merged over the register."""
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh)
    old = os.environ.get("TENSILE_FACTORS")
    os.environ["TENSILE_FACTORS"] = path
    try:
        yield path
    finally:
        if old is None:
            os.environ.pop("TENSILE_FACTORS", None)
        else:
            os.environ["TENSILE_FACTORS"] = old
        os.remove(path)


# --------------------------------------------------------------------------------------------- stress checks
class TestTS19102WorkedExample(unittest.TestCase):
    """JRC 2025 slide 112: large hypar, Sattler 760 Atlas Type IV, 'Verification method in CEN TS 19102'.
    n23 = 172/168 kN/m, kn 1.64, Vx 0.12 -> fk,23 138.15/134.94; γM 1.5 (det. γM2); fRd1 18.27/17.85,
    fRd4 54.82/53.55, fRd5 65.79/64.26; m_d = 1.5·m; utilisation 0.246/0.210, 0.648/0.238, 0.579/0.626."""

    def test_characteristic_strength(self):
        self.assertAlmostEqual(mc.char_strength(172.0, 0.12), 138.15, places=2)
        self.assertAlmostEqual(mc.char_strength(168.0, 0.12), 134.94, places=2)

    def test_design_resistances_and_utilisation(self):
        fk = {"w": 138.15, "f": 134.94}
        j = {"joint": True}                                      # γM2 = 1.5 as used on the slide
        pub = {"prestress": (18.27, 17.85), "snow": (54.82, 53.55), "wind": (65.79, 64.26)}
        for case, (rw, rf) in pub.items():
            aw, _ = mc.allowable(fk["w"], "ts19102", case, "PES/PVC", opts=j)
            af, _ = mc.allowable(fk["f"], "ts19102", case, "PES/PVC", opts=j)
            self.assertAlmostEqual(aw, rw, delta=0.006, msg=case)
            self.assertAlmostEqual(af, rf, delta=0.006, msg=case)
        m = {"prestress": (3.0, 2.5), "snow": (23.7, 8.5), "wind": (25.4, 26.8)}
        util = {"prestress": (0.246, 0.210), "snow": (0.648, 0.238), "wind": (0.579, 0.626)}
        for case, (mw, mf) in m.items():
            aw, _ = mc.allowable(fk["w"], "ts19102", case, "PES/PVC", opts=j)
            af, _ = mc.allowable(fk["f"], "ts19102", case, "PES/PVC", opts=j)
            self.assertAlmostEqual(1.5 * mw / aw, util[case][0], delta=0.0006, msg=case)
            self.assertAlmostEqual(1.5 * mf / af, util[case][1], delta=0.0006, msg=case)

    def test_written_report_table50(self):
        # JRC144386 (2025, doi:10.2760/3056713) §13.4.1 Table 50, 'Eurocode 12 (TS 19102)': 65 %, 24 %, 58 %, 63 %
        fk = {"w": 138.15, "f": 134.94}
        m = {"snow": (23.7, 8.5), "wind": (25.4, 26.8)}
        pub = {"snow": (65, 24), "wind": (58, 63)}
        for case, (mw, mf) in m.items():
            aw, _ = mc.allowable(fk["w"], "ts19102", case, "PES/PVC", opts={"joint": True})
            af, _ = mc.allowable(fk["f"], "ts19102", case, "PES/PVC", opts={"joint": True})
            self.assertEqual((round(150 * mw / aw), round(150 * mf / af)), pub[case])

    def test_second_published_set_costa_diadema(self):
        """JRC144386 §13.3.2 Tables 48-49 = JRC 2025 slides 102-103 (Costa Diadema, Ferrari 1202 S2 Type III):
        n23 112 kN/m, kn 1.64, Vx 0.12 -> fk,23 89.96; γM 1.5, kage 1.25, kdur,P 1.60, ktemp,70 1.50:
        fRd1 (prestress) 19.99, fRd5 (wind) 47.98, fRd6 (wind at elevated temperature) 31.99 kN/m.
        Checks the situation formulas 1, 5 and 6 ('warm', not covered by slide 112) with a second factor set."""
        fk = mc.char_strength(112.0, 0.12)
        self.assertAlmostEqual(fk, 89.96, delta=0.005)
        fam = "alt_set_PES/PVC"
        for case, pub in (("prestress", 19.99), ("wind", 47.98), ("temperature", 31.99)):
            al, basis = mc.allowable(fk, "ts19102", case, fam)
            self.assertAlmostEqual(al, pub, delta=0.006, msg=case)
        # the sensitivity range of the default set covers this second published set in every situation
        lo, hi = CF.frange("membrane.ts19102")
        self.assertEqual(hi, 1.0)
        for case in ("prestress", "snow", "wind", "temperature"):
            for joint in (False, True):
                a_def, _ = mc.allowable(100.0, "ts19102", case, "PES/PVC", opts={"joint": joint})
                a_alt, _ = mc.allowable(100.0, "ts19102", case, fam, opts={"joint": joint})
                g = CF.get("membrane.ts19102")
                gd = g["PES/PVC"]["gM2" if joint else "gM0"]
                ga = g[fam]["gM2" if joint else "gM0"]
                ratio = (a_def / a_alt) * (gd / ga)        # ratio of the k-products (γM is not part of the range)
                self.assertGreaterEqual(ratio, lo - 0.005, msg=case)
                self.assertLessEqual(ratio, hi + 1e-9, msg=case)

    def test_cli_mean_to_characteristic(self):
        _, out = run(mc.main, ["--fw", "172", "--ff", "168", "--vx", "0.12", "--family", "PES/PVC",
                               "--nw", "35.55", "--nf", "12.75", "--case", "snow", "--method", "ts19102"])
        self.assertIn("138.15/134.94", out)
        self.assertIn("Assumptions:", out)

    def test_unknown_family_refused(self):
        with self.assertRaises(ValueError):
            mc.allowable(100, "ts19102", "wind", "glass/PTFE")


class TestGlobalAndFrenchWorkedExample(unittest.TestCase):
    """JRC 2025 slides 110-111, same hypar (Trm = 172/168 kN/m, m snow 23.7/8.5, wind 25.4/26.8)."""

    def test_global_safety_factor_5(self):
        # slide 111: 'fu/m = 172/23.7 = 7.26 > 5.0 ok (utilisation = 0.69)', wind 0.74, weft wind 0.80, snow 0.25
        cases = [(172, 23.7, "snow", 0.69), (172, 25.4, "wind", 0.74), (168, 8.5, "snow", 0.25),
                 (168, 26.8, "wind", 0.80)]
        for f, m, case, u in cases:
            al, _ = mc.allowable(f, "factor", case, "PES/PVC", sf_short=5.0, sf_long=5.0)
            self.assertAlmostEqual(m / al, u, delta=0.005)

    def test_french_recommendation(self):
        # slide 110: kq 1, ke 0.85 (> 250 m²), γt 4; TD 36.55 (172) / 35.7 (168); TC = 1.5·m;
        # utilisations 0.97 (snow warp), 1.04 (wind warp), 0.36 (snow weft), 1.13 (wind weft)
        o = {"ke": 0.85, "kq": 1.0, "pollution": "medium"}
        tw, _ = mc.allowable(172, "french", "wind", "PES/PVC", opts=o)
        tf, _ = mc.allowable(168, "french", "wind", "PES/PVC", opts=o)
        self.assertAlmostEqual(tw, 36.55, places=2)
        self.assertAlmostEqual(tf, 35.70, places=2)
        for tc, td, u in ((1.5 * 23.7, tw, 0.97), (1.5 * 25.4, tw, 1.04), (1.5 * 8.5, tf, 0.36), (1.5 * 26.8, tf, 1.13)):
            self.assertAlmostEqual(tc / td, u, delta=0.006)

    def test_french_scale_factor_table(self):
        # JRC132615 Code Review 21 eq. (3a/3b) vs its Table 6-1 (0.9 for 50-200 m², 0.86 for 250-500 m²)
        self.assertEqual(mc.french_ke(40.0), 1.0)
        self.assertAlmostEqual(mc.french_ke(200.0), 0.90, delta=0.015)
        self.assertAlmostEqual(mc.french_ke(500.0), 0.86, delta=0.005)

    def test_french_attachment_rule_in_corner(self):
        # Code Review 21 eq. (4): TD = kq·neff·Trm/γtloc, γtloc = 5 -> base corner allowable Trm/5
        _, out = run(mc.main, ["--fw", "100", "--ff", "90", "--method", "french", "--corner", "20", "90", "0.4",
                               "--layers", "2", "--neff-basis", "french"])
        self.assertIn("base allowable 18.00 kN/m", out)
        self.assertIn("n_eff = 1.9", out)


class TestGermanAFactors(unittest.TestCase):
    """German practice (DIN 4134 + Minte), JRC132615 Code Review 20 and JRC 2025 slide 109."""

    def test_slide_109_connection_example(self):
        # Sattler Atlas Type IV, connection, warp: n23 8600 N/5cm, fs 0.802 -> X23 6897 N/5cm; γm 1.5; A0 1.0,
        # A1 1.55, A2 1.10, A3 1.45 (A1xA3 2.25); zul n0 83.60, zul nJ 57.66, zul nt 37.20;
        # vorh n0 = 1.6·25.4 = 40.64 (0.486), nJ = 0.7·25.4 = 17.78 (0.308), nt = 1.3·23.7 = 30.81 (0.828)
        x23 = 8600 * 0.802 / 50.0
        tab = {"membrane": {"partial": {"PES/PVC": {"gM": 1.5, "A0": 1.0, "A1_long": 1.55, "A1_short": 1.0,
                                                    "A2": 1.10, "A3": 1.45}}}}
        with project_factors(tab):
            n0, _ = mc.allowable(x23, "partial", "wind", "PES/PVC")
            nJ, _ = mc.allowable(x23, "partial", "temperature", "PES/PVC")
            nt, _ = mc.allowable(x23, "partial", "snow", "PES/PVC")
        self.assertAlmostEqual(n0, 83.60, delta=0.01)
        self.assertAlmostEqual(nJ, 57.66, delta=0.01)
        self.assertAlmostEqual(nt, 37.20, delta=0.03)           # slide rounds A1·A3 = 2.2475 to 2.25
        self.assertAlmostEqual(40.64 / n0, 0.486, delta=0.001)
        self.assertAlmostEqual(17.78 / nJ, 0.308, delta=0.001)
        self.assertAlmostEqual(30.81 / nt, 0.828, delta=0.002)

    def test_register_table_inside_published_global_factors(self):
        # Code Review 20: global reduction γf·γM·A: winter storm (γf 1.6) 2.9-3.2, permanent (γf 1.5) 4.9-6.4
        k_wind = 100.0 / mc.allowable(100.0, "partial", "wind", "PES/PVC")[0]
        k_perm = 100.0 / mc.allowable(100.0, "partial", "prestress", "PES/PVC")[0]
        self.assertTrue(2.9 <= 1.6 * k_wind <= 3.2, 1.6 * k_wind)
        self.assertTrue(4.9 <= 1.5 * k_perm <= 6.4, 1.5 * k_perm)
        p = CF.get("membrane.partial")["PES/PVC"]
        for key, lo, hi in (("A0", 1.0, 1.2), ("A1_long", 1.6, 1.7), ("A2", 1.1, 1.2), ("A3", 1.1, 1.25)):
            self.assertTrue(lo <= p[key] <= hi, key)
        self.assertEqual((p["gM"], p["gM_joint"]), (1.4, 1.5))

    def test_cli_sensitivity_and_family_status(self):
        _, out = run(mc.main, ["--material", "PVC-III", "--nw", "9", "--nf", "8", "--case", "snow",
                               "--method", "partial", "--sensitivity"])
        self.assertIn("sensitivity partial", out)
        self.assertIn("[V, PES/PVC]", out)
        _, out = run(mc.main, ["--material", "Chukoh-FGT-800", "--nw", "20", "--nf", "15", "--case", "wind",
                               "--method", "partial", "--sensitivity"])
        self.assertIn("[U, glass/PTFE]", out)
        self.assertIn("sensitivity partial (glass/PTFE)", out)


class TestJapanNotification666(unittest.TestCase):
    """MLIT Notification 666, 第六 一: allowable tensile stress Fm/(80t) long, Fm/(40t) short (Fm/(50t) folded);
    narrow joints Fm/(100t), Fm/(50t); Fm in N/cm, t in mm, result N/mm²."""

    def test_divisors_from_primary_formula(self):
        Fm_Ncm, t = 1000.0, 0.8                        # Fm = 1000 N/cm = 100 kN/m
        f = Fm_Ncm / 10.0                              # kN/m
        for case, opts, denom in (("snow", {}, 80), ("wind", {}, 40), ("wind", {"folded": True}, 50),
                                  ("snow", {"folded": True}, 80), ("snow", {"japan_joint": "narrow"}, 100),
                                  ("wind", {"japan_joint": "narrow"}, 50)):
            sigma = Fm_Ncm / (denom * t)               # N/mm²
            al, _ = mc.allowable(f, "japan", case, "PES/PVC", opts=opts)
            self.assertAlmostEqual(al, sigma * t, places=9, msg=(case, opts))   # n = σ·t [N/mm = kN/m]

    def test_joint_class_replaces_seam_efficiency(self):
        rows = mc.point_utils(10, 8, 100, 90, "japan", "snow", "PES/PVC", 0.8)
        seam = [r for r in rows if r[0].startswith("seam")]
        self.assertTrue(all(abs(r[2] - (100 if "warp" in r[0] else 90) / 8) < 1e-9 for r in seam))

    def test_register_is_verified(self):
        for k in ("japan_long_divisor", "japan_short_divisor", "japan_short_divisor_folded"):
            self.assertEqual(CF.status("membrane." + k), "V")
            self.assertIn("mlit.go.jp", CF.load()["membrane"]["japan_long_divisor"]["source"])


class TestPrestressMinimum(unittest.TestCase):
    """JRC132615 §3 quoting the TensiNet guide: PES/PVC >= 1.3 % of the short-term strength; glass/PTFE >= 2.5 %
    but >= 2.0 kN/m; French recommendations (Code Review 6): >= 1.5 kN/m."""

    def test_rules(self):
        self.assertAlmostEqual(mc.prestress_minimum("PES/PVC", 200.0)[0], 2.6)       # 1.3 % governs
        self.assertAlmostEqual(mc.prestress_minimum("PES/PVC", 80.0)[0], 1.5)        # French 1.5 governs
        self.assertAlmostEqual(mc.prestress_minimum("glass/PTFE", 147.0)[0], 3.675)  # 2.5 %
        self.assertAlmostEqual(mc.prestress_minimum("glass/PTFE", 60.0)[0], 2.0)    # 2.0 kN/m floor
        self.assertAlmostEqual(mc.prestress_minimum("glass/silicone", 100.0)[0], 1.5)

    def test_cli_flags_low(self):
        _, out = run(mc.main, ["--material", "PVC-II", "--prestress", "1.0", "1.2"])
        self.assertIn("LOW", out)
        _, out = run(mc.main, ["--material", "PVC-II", "--prestress", "2.0", "2.0"])
        self.assertNotIn("LOW", out)


class TestFMandASCE(unittest.TestCase):
    def test_fm_table(self):
        # FM Global DS 1-59 (2021) Table 2.2.6.1: P+D 8.0, P+D+S 5.0
        self.assertAlmostEqual(mc.allowable(100, "fm", "prestress", "PES/PVC", fm_combo="P+D")[0], 12.5)
        self.assertAlmostEqual(mc.allowable(100, "fm", "snow", "PES/PVC", fm_combo="P+D+S")[0], 20.0)


class TestETFE(unittest.TestCase):
    """JRC132615 Eurocode Outlook 44: 'fPM,d = 21 / (1.1 · 1.05 · 1.8) = 10.1 N/mm² or an admissible
    characteristic stress of σadm = 10.1 / 1.35 = 7.5 N/mm²'."""

    def test_permanent_example(self):
        fd, basis = mc.etfe_design_strength("prestress")
        self.assertAlmostEqual(fd, 10.1, delta=0.01)
        self.assertAlmostEqual(fd / 1.35, 7.5, delta=0.02)

    def test_situations_closed_form(self):
        g = 1.1
        exp = {"snow": 21 / (g * 1.05 * 1.2 * 0.7), "live": 21 / (g * 1.05 * 1.2), "wind": 21 / (g * 1.05),
               "temperature": 21 / (g * 1.05 * 1.2)}
        for case, v in exp.items():
            self.assertAlmostEqual(mc.etfe_design_strength(case)[0], v, places=9)
        self.assertAlmostEqual(mc.etfe_design_strength("prestress", single_unregulated=True)[0],
                               21 / (g * 1.05 * 3.5), places=9)

    def test_cli_and_selection(self):
        u, out = run(mc.main, ["--material", "ETFE-250um", "--nw", "2.5", "--case", "prestress"])
        self.assertAlmostEqual(u, (2.5 / 0.25) / (21 / (1.1 * 1.05 * 1.8)), places=9)
        self.assertIn("Assumptions:", out)
        lib = mc.load_lib()
        m = lib["materials"]["ETFE-200um"]
        self.assertAlmostEqual(ms.utilisation(m, "ETFE", 1.0, "wind", "factor", 0.8), 1.0 / (21 / 1.155 * 0.2))


# --------------------------------------------------------------------------------------------- dynamics
def _spatial_added_mass(cells, h, w, r_ref):
    """independent check: Rayleigh double sum m_a = ρ ΣΣ w_i w_j h⁴/(2π r_ij) / Σ w_i² h², with the exact
    self-integral of 1/r over a square cell (h³·(4 ln(1+√2) − 4(√2−1)/3))."""
    self_term = 4 * math.log(1 + math.sqrt(2)) - 4 * (math.sqrt(2) - 1) / 3
    num = 0.0
    n = len(cells)
    for i in range(n):
        xi, yi = cells[i]
        s = w[i] * self_term / h
        for j in range(i + 1, n):
            s += 2 * w[j] / math.hypot(xi - cells[j][0], yi - cells[j][1])
        num += w[i] * s
    num *= h ** 4 / (2 * math.pi)
    return num / (sum(v * v for v in w) * h * h) / r_ref


class TestPanelFrequency(unittest.TestCase):
    def test_exact_rectangular_membrane(self):
        # rectangular membrane, tensions Nx, Ny, mass ρs, fixed edges (Graff, Wave Motion in Elastic Solids §4.4;
        # Kreyszig §12.9 for Nx = Ny): ω_mn = π·√((Nx (m/a)² + Ny (n/b)²)/ρs)
        nw, nf, a, b, rho = 3.0, 1.5, 6.0, 4.0, 1.2
        for m, n in ((1, 1), (2, 1), (1, 3), (3, 2)):
            w = math.pi * math.sqrt((nw * 1e3 * (m / a) ** 2 + nf * 1e3 * (n / b) ** 2) / rho)
            f, meff = mc.panel_frequency(nw, nf, a, b, rho, Ca=0.0, m=m, n=n)
            self.assertAlmostEqual(f, w / (2 * math.pi), places=10)
            self.assertEqual(meff, rho)

    def test_independent_route_reproduces_lamb(self):
        # Lamb (1920): clamped circular plate, w = (1 − r²)², one fluid side: added mass 0.6689·ρ·a.
        # Richardson extrapolation of two grids (error O(h)).
        def disk(N):
            h = 2.0 / N
            c = [(-1 + (i + .5) * h, -1 + (j + .5) * h) for i in range(N) for j in range(N)]
            c = [p for p in c if p[0] ** 2 + p[1] ** 2 < 1]
            return _spatial_added_mass(c, h, [(1 - (x * x + y * y)) ** 2 for x, y in c], 1.0)
        self.assertAlmostEqual(2 * disk(48) - disk(24), 0.6689, delta=0.001)

    def test_added_mass_rect_vs_independent_route(self):
        # tool: spectral Rayleigh integral; check: spatial double sum (above), square panel, mode (1,1)
        def sq(N):
            h = 1.0 / N
            c = [((i + .5) * h, (j + .5) * h) for i in range(N) for j in range(N)]
            return _spatial_added_mass(c, h, [math.sin(math.pi * x) * math.sin(math.pi * y) for x, y in c],
                                       math.sqrt(1 / math.pi))
        ref = 2 * sq(32) - sq(16)
        self.assertAlmostEqual(mc.added_mass_coeff(1.0, 1.0), ref, delta=0.004 * ref)
        self.assertAlmostEqual(mc.added_mass_coeff(5.0, 5.0), mc.added_mass_coeff(1.0, 1.0), places=9)
        self.assertGreater(mc.added_mass_coeff(1, 1), mc.added_mass_coeff(4, 1))     # aspect ratio
        self.assertGreater(mc.added_mass_coeff(1, 1), mc.added_mass_coeff(1, 1, 2, 1))  # higher mode

    def test_default_uses_computed_added_mass_and_inverse(self):
        f, meff = mc.panel_frequency(2.0, 2.0, 6.0, 4.0, 1.2)
        ca = mc.added_mass_coeff(6.0, 4.0) * CF.get("membrane.added_mass_model")
        self.assertAlmostEqual(meff, 1.2 + 2 * ca * 1.25 * math.sqrt(24 / math.pi), places=9)
        self.assertAlmostEqual(mc.prestress_for_frequency(f, 6.0, 4.0, meff), 2.0, places=9)

    def test_cli_modes(self):
        _, out = run(mc.main, ["--material", "PVC-III", "--prestress", "2", "2", "--flutter", "6", "4",
                               "--modes", "3", "--sensitivity"])
        self.assertIn("f21 =", out)
        self.assertIn("sensitivity added-mass model", out)


# --------------------------------------------------------------------------------------------- corner / tear
class TestCornerAndTear(unittest.TestCase):
    def test_published_reinforcement_factors(self):
        # JRC132615 §6.5: French 1.9 / 2.6 / 3.1, German 1.75 / 2.6, Eurocode Outlook 38: +50 % (1 layer)
        th = math.pi / 2
        for basis, layers, neff in (("french", 2, 1.9), ("french", 3, 2.6), ("french", 4, 3.1),
                                    ("german", 2, 1.75), ("german", 3, 2.6), ("ts", 2, 1.5)):
            c = mc.corner_check(30.0, 90.0, 0.35, 25.0, layers, basis=basis)
            self.assertAlmostEqual(c["n_all_reinf"], 25.0 * neff)
            self.assertAlmostEqual(c["n_r0"], 30.0 / (th * 0.35))            # radial-fan equilibrium R/(θ r)
            self.assertAlmostEqual(c["r_k"][layers], 30.0 / (th * 25.0 * neff))
        self.assertTrue(mc.corner_check(30, 90, 0.35, 25, 3, basis="ts")["beyond_table"])
        # the legacy linear ply model with η = 0.8 reproduces the French / German value for two reinforcements
        self.assertAlmostEqual(mc.corner_check(30, 90, 0.35, 25, 3, eff=0.8)["neff"], 2.6)

    def test_curvature_laplace(self):
        # membrane equilibrium (Laplace) n1/R1 + n2/R2 = p; cylinder (R2 -> inf) without prestress: n1 = p·R1
        # (e.g. Otto/Trostel, Tensile Structures; JRC132615 §3 double-curvature equilibrium)
        _, out = run(mc.main, ["--material", "PVC-III", "--curvature", "7.5", "1e9", "--p", "0.6",
                               "--prestress", "0.0001", "0.0001"])
        self.assertIn(f"{0.6 * 7.5 + 0.0001:.2f} kN/m (upper bound", out)

    def test_tear_lefm_scaling(self):
        # LEFM centre crack (Anderson, Fracture Mechanics, eq. K_I = σ√(πa)): σ_c(a2) = σ_c(a1)·√(a1/a2)
        _, out = run(mc.main, ["--material", "PVC-III", "--nw", "12", "--tear", "40", "36", "--defect", "160"])
        self.assertIn(f"{36 * math.sqrt(40 / 160):.2f} kN/m", out)
        self.assertIn("tear_factor [U]", out)


# --------------------------------------------------------------------------------------------- biaxial
class TestBiaxial(unittest.TestCase):
    """JRC132615 §2.4 eqs. 2.1-2.12 (direct vs inverse stiffness) with the published stiffness set of the
    JRC 2025 Costa Diadema example: EAX 1000, EAY 800, crimp interchange EAP 400 kN/m.
    Inverse: ν_xy = 400/1000 = 0.4, ν_yx = 400/800 = 0.5, E_x = 1000·(1 − 0.2) = 800, E_y = 640."""

    def test_transformation(self):
        inv = bx.direct_to_inverse(1000.0, 800.0, 400.0)
        self.assertAlmostEqual(inv["Ew_t"], 800.0)
        self.assertAlmostEqual(inv["Ef_t"], 640.0)
        self.assertAlmostEqual(inv["nu_fw"], 0.4)       # JRC ν_xy (multiplies n_f in ε_w)
        self.assertAlmostEqual(inv["nu_wf"], 0.5)       # JRC ν_yx
        d = bx.inverse_to_direct(800.0, 640.0, 0.5, 0.4)
        self.assertAlmostEqual(d["Ed_w"], 1000.0)
        self.assertAlmostEqual(d["Ed_wf"], d["Ed_fw"])

    def test_fit_recovers_published_set_from_direct_formulation(self):
        # strains generated with the DIRECT formulation (JRC eq. 2.1/2.2), MSAJ/M-02 ratios 1:1, 2:1, 1:2, 1:0, 0:1
        Ex, Ey, Exy = 1000.0, 800.0, 400.0
        det = Ex * Ey - Exy * Exy
        rows = ["ratio,n_w,n_f,eps_w,eps_f"]
        for rw, rf in ((1, 1), (2, 1), (1, 2), (1, 0), (0, 1)):
            for k in range(1, 6):
                nw, nf = 2.0 * k * rw, 2.0 * k * rf
                ew, ef = (Ey * nw - Exy * nf) / det, (Ex * nf - Exy * nw) / det
                rows.append(f"{rw}:{rf},{nw},{nf},{ew * 100:.12f},{ef * 100:.12f}")
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as fh:
            fh.write("\n".join(rows) + "\n")
        try:
            res, out = run(bx.main, [path, "--per-ratio", "--prestress", "2", "2", "--residual", "0", "0"])
        finally:
            os.remove(path)
        f = res["all"]
        self.assertAlmostEqual(f["Ew_t"], 800.0, places=4)
        self.assertAlmostEqual(f["Ef_t"], 640.0, places=4)
        self.assertAlmostEqual(f["nu_wf"], 0.5, places=6)
        self.assertAlmostEqual(f["nu_fw"], 0.4, places=6)
        self.assertAlmostEqual(res["direct"]["Ed_wf"], 400.0, places=3)
        # elastic compensation at 2/2 kN/m prestress = direct-form strain (Ey − Exy)·2/det, (Ex − Exy)·2/det
        cw, cf = res["compensation_%"]
        self.assertAlmostEqual(cw, 100 * (Ey - Exy) * 2 / det, places=6)
        self.assertAlmostEqual(cf, 100 * (Ex - Exy) * 2 / det, places=6)
        self.assertIn("Assumptions:", out)


class TestBiaxialPublishedTestData(unittest.TestCase):
    """Published RAW biaxial data with the authors' fitted constants.

    Uhlemann, Stranghöner, Schmidt, Saxe, "Effects on elastic constants of technical membranes applying the
    evaluation methods of MSAJ/M-02-1995", Structural Membranes 2011, CIMNE, pp. 648-659 (open access,
    https://hdl.handle.net/2117/186360). MSAJ test T2 on glass/PTFE B18089 (type G6): 10 load-strain paths,
    71 points each, extracted from the vector plot of Fig. 5 (Fig. 6 repeats the data: agreement 0.0085 % strain,
    0.036 kN/m). Table 2 gives the constants of 8 determination options, fitted by the authors' MATLAB routine
    (least squares, strain term, grid search) together with the residual sum S_ε [%²].
    Notation: paper ν_xy (n_y in ε_x) = tool ν_fw, paper ν_yx = tool ν_wf."""

    CSV = os.path.join(SK, "membrane-fabric", "reference", "data", "biaxial_uhlemann2011_T2.csv")
    # option: (ratios, 10 paths?, reciprocity) -> published (E_x t, E_y t, ν_xy, ν_yx, S_ε) for test T2
    TABLE2 = {1: ((None, False, True), (1292, 816, 0.57, 0.90, 32.72)),
              2: ((None, False, False), (1188, 864, 0.73, 0.69, 23.09)),
              3: ((None, True, True), (914, 610, 0.83, 1.24, 637.19)),
              4: ((None, True, False), (860, 634, 0.94, 1.08, 625.49)),
              5: ((["1:1", "2:1"], False, True), (1600, 924, 0.48, 0.83, 2.14)),
              6: ((["1:1", "1:2"], False, True), (1336, 824, 0.60, 0.97, 4.42))}

    @classmethod
    def setUpClass(cls):
        cls.data = bx.read(cls.CSV)

    def test_data_set(self):
        self.assertEqual(sorted(self.data), ["0:1", "1:0", "1:1", "1:2", "2:1"])
        for pts in self.data.values():
            self.assertEqual(len(pts), 71)
            lead = [max(nw, nf) for nw, nf, _, _ in pts]
            self.assertAlmostEqual(lead[0], 2.15, delta=0.05)      # MSAJ glass/PTFE paths start at 2 kN/m
            self.assertAlmostEqual(lead[-1], 30.15, delta=0.05)    # max test load 30 kN/m (paper §5)

    def test_objective_matches_published_residuals(self):
        # S_ε of the PUBLISHED constants on the extracted data = the published S_ε: same objective, same data
        for opt, ((ratios, ten, _), (Ex, Ey, nxy, nyx, S)) in self.TABLE2.items():
            got = bx.msaj_objective(self.data, Ex, Ey, nxy, nyx, ratios, include_zero=ten)
            tol = 0.025 if ten else 0.01
            self.assertAlmostEqual(got / S, 1.0, delta=tol, msg=f"option {opt}: {got:.2f} vs {S}")

    def test_reproduces_table2_options(self):
        for opt in (1, 2, 3, 4, 6):
            (ratios, ten, rec), (Ex, Ey, nxy, nyx, S) = self.TABLE2[opt]
            f = bx.fit_msaj(self.data, ratios, include_zero=ten, reciprocal=rec)
            msg = f"option {opt}: {f['Ew_t']:.0f}/{f['Ef_t']:.0f}/{f['nu_fw']:.3f}/{f['nu_wf']:.3f}/{f['S_eps']:.2f}"
            self.assertAlmostEqual(f["Ew_t"] / Ex, 1.0, delta=0.02, msg=msg)
            self.assertAlmostEqual(f["Ef_t"] / Ey, 1.0, delta=0.01, msg=msg)
            self.assertAlmostEqual(f["nu_fw"], nxy, delta=0.015, msg=msg)
            self.assertAlmostEqual(f["nu_wf"], nyx, delta=0.015, msg=msg)
            # on the same data the exact least squares is at least as good as the published (grid-search) set;
            # with reciprocity the paper accepts |E_x/E_y - ν_yx/ν_xy| < 0.005 (eq. 6), the tool enforces it exactly
            S_pub = bx.msaj_objective(self.data, Ex, Ey, nxy, nyx, ratios, include_zero=ten)
            self.assertLessEqual(f["S_eps"], S_pub * (1.005 if rec else 1.0) + 1e-9, msg=msg)
            self.assertAlmostEqual(f["S_eps"] / S, 1.0, delta=0.025, msg=msg)
            if rec:
                self.assertAlmostEqual(f["Ew_t"] / f["Ef_t"], f["nu_wf"] / f["nu_fw"], places=9)

    def test_option5_published_value_is_on_search_bound(self):
        # Table 2 option 5 has E_x t = 1600 for T2 (T1 1580, option 6 T1 1600): the upper limit of the grid.
        (ratios, ten, rec), (Ex, Ey, nxy, nyx, S) = self.TABLE2[5]
        free = bx.fit_msaj(self.data, ratios, include_zero=ten, reciprocal=rec)
        self.assertGreater(free["Ew_t"], Ex)           # the unbounded optimum lies above the bound ...
        self.assertLess(free["S_eps"], S)             # ... with a smaller residual
        f = bx.fit_msaj(self.data, ratios, include_zero=ten, reciprocal=rec, fix_Ew_t=Ex)
        self.assertAlmostEqual(f["Ef_t"] / Ey, 1.0, delta=0.005)
        self.assertAlmostEqual(f["nu_fw"], nxy, delta=0.01)
        self.assertAlmostEqual(f["nu_wf"], nyx, delta=0.01)
        self.assertAlmostEqual(f["S_eps"] / S, 1.0, delta=0.01)

    def test_cli_msaj_and_option_sensitivity(self):
        res, out = run(bx.main, [self.CSV, "--msaj"])
        self.assertIn("8 load-strain paths", out)
        self.assertIn("reciprocity applied", out)
        self.assertIn("evaluation option", out)
        # the paper's point: secant-through-origin and slope (MSAJ) evaluations differ strongly on real data
        self.assertLess(res["all"]["Ew_t"], 0.7 * res["msaj"]["Ew_t"])
        res2, out2 = run(bx.main, [self.CSV, "--msaj", "--no-reciprocity"])        # Table 2 option 2
        self.assertIn("NOT applied", out2)
        self.assertIn("not symmetric", out2)
        self.assertAlmostEqual(res2["msaj"]["Ew_t"] / 1188, 1.0, delta=0.02)
        _, out10 = run(bx.main, [self.CSV, "--msaj", "--paths", "10"])                 # option 3: ν_wf·ν_fw > 1
        self.assertIn("10 load-strain paths", out10)
        self.assertIn("Direct stiffness form not available", out10)


# --------------------------------------------------------------------------------------------- material data
UNIT = {"N/5cm": 1 / 50, "daN/5cm": 1 / 5, "N/3cm": 1 / 30, "lb/in": 0.17512684, "N/cm": 0.1}


class TestMaterialDatabase(unittest.TestCase):
    lib = mc.load_lib()

    def test_entries_consistent(self):
        allowed = {"datasheet", "excerpt", "class-table", "published-example", "typical"}
        for k, m in self.lib["materials"].items():
            with self.subTest(k):
                self.assertIn(m["family"], self.lib["family_defaults"])
                self.assertIn(m["status"], allowed)
                self.assertGreater(m["fw"], 0)
                self.assertGreater(m["ff"], 0)
                self.assertTrue(m.get("source"))
                if m["status"] in ("datasheet", "class-table", "published-example"):
                    self.assertTrue(m.get("source_url", "").startswith("http"), "URL required")
                if "fk_w" in m:
                    self.assertLessEqual(m["fk_w"], m["fw"] + 1e-9)
                    self.assertLessEqual(m["fk_f"], m["ff"] + 1e-9)
                if "tear_N" in m:
                    self.assertTrue(all(t > 0 for t in m["tear_N"]))
                if m["family"] != "ETFE":
                    self.assertTrue(0.3 <= m["ff"] / m["fw"] <= 1.3, "warp/weft ratio")
                    if isinstance(m.get("weight_gm2"), (int, float)):
                        self.assertTrue(200 <= m["weight_gm2"] <= 2000)
                        # strength-to-weight 0.04-0.2 kN/m per g/m² for coated fabrics
                        self.assertTrue(0.04 <= m["fw"] / m["weight_gm2"] <= 0.2, m["fw"] / m["weight_gm2"])

    def test_unit_conversions(self):
        for k, m in self.lib["materials"].items():
            raw = m.get("raw")
            if not raw:
                continue
            with self.subTest(k):
                hit = re.match(r"([\d.]+)/([\d.]+) (\S+)", raw)
                self.assertIsNotNone(hit, raw)
                c = UNIT[hit.group(3)]
                self.assertAlmostEqual(float(hit.group(1)) * c, m["fw"], delta=0.006 * m["fw"])
                self.assertAlmostEqual(float(hit.group(2)) * c, m["ff"], delta=0.006 * m["ff"])

    def test_class_tables(self):
        # JRC Outlook 5: strength rises with type; 5 % fractile 0.85-0.95 of the mean
        fws = [self.lib["materials"][f"PVC-{t}"]["fw"] for t in ("I", "II", "III", "IV", "V")]
        self.assertEqual(fws, sorted(fws))
        self.assertEqual(fws, [55, 80, 110, 150, 185])
        for t in ("I", "II", "III", "IV", "V"):
            m = self.lib["materials"][f"PVC-{t}"]
            self.assertTrue(0.85 <= m["fk_w"] / m["fw"] <= 0.95)

    def test_etfe_density_and_strength(self):
        for k, m in self.lib["materials"].items():
            if m["family"] != "ETFE":
                continue
            with self.subTest(k):
                self.assertAlmostEqual(m["weight_gm2"], 1.75 * m["t_mm"] * 1000, delta=0.02 * m["weight_gm2"])
                self.assertAlmostEqual(m["fw"], m["fy10_MPa"] * m["t_mm"], places=6)


class TestMaterialSelection(unittest.TestCase):
    def test_documented_case_jrc_hypar(self):
        # JRC 2025 slide 112: Sattler Atlas Type IV, design wind stress in weft 40.2 kN/m, fRd5 = 64.26 ->
        # utilisation 0.626 (CEN/TS 19102, γM 1.5). Lighter Type II classes must be excluded.
        ok, out = ms.select({"n_design": 40.2, "case": "wind", "method": "ts19102", "family": "PES/PVC",
                             "seam_eff": 1.0})
        okd = dict(ok)
        self.assertAlmostEqual(okd["Sattler-Atlas-760-IV"]["util"], 0.626, delta=0.001)
        self.assertIn("PVC-II", dict(out))
        self.assertTrue(all(v["util"] <= 1.0 for v in okd.values()))
        # other families have no TS factors in the register -> excluded with that reason
        _, out2 = ms.select({"n_design": 10.0, "case": "wind", "method": "ts19102"})
        self.assertTrue(any("no ts19102 factors" in "; ".join(w) for _, w in out2))

    def test_filters_and_product_fire_class(self):
        ok, out = ms.select({"n_design": 25.0, "case": "snow", "fire": "A2"})
        self.assertTrue(ok)
        self.assertTrue(all(v["family"] == "glass/PTFE" for _, v in ok))
        # a product sheet stating C-s2,d0 overrides the family default B-s2,d0
        _, out = ms.select({"fire": "B"})
        self.assertIn("Ferrari-Flexlight-1302S2", dict(out))
        ok, _ = ms.select({"translucency": 80})
        self.assertEqual({v["family"] for _, v in ok}, {"ETFE"})

    def test_cli_assumptions(self):
        _, out = run(ms.main, ["--n-design", "8", "--case", "wind", "--fire", "B"])
        self.assertIn("Assumptions:", out)


class TestEnvelope(unittest.TestCase):
    def test_envelope_partial_and_sensitivity(self):
        env = {"summary": [{"case": "PS", "duration": "long", "warp_max": 3.0, "weft_max": 2.5, "factor": 1.0},
                           {"case": "SNOW", "duration": "long", "warp_max": 15.0, "weft_max": 6.0, "factor": 1.5},
                           {"case": "WIND", "duration": "short", "warp_max": 20.0, "weft_max": 22.0, "factor": 1.5}]}
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(env, fh)
        try:
            _, out = run(mc.main, ["--material", "PVC-IV", "--envelope", path, "--method", "partial", "--sensitivity"])
        finally:
            os.remove(path)
        rows = mc.envelope_utils(env, 135.0, 120.0, "partial", "PES/PVC", 0.8)
        # wind row, weft governs the seam: 22 / (0.8·120 / (1.5·1.2·1.0·1.1))
        self.assertAlmostEqual(rows[2][5], 22.0 / (0.8 * 120 / (1.5 * 1.2 * 1.1)), places=9)
        self.assertIn("sensitivity partial", out)
        self.assertNotIn("WARNING", out)       # factored cases are right for the partial format


if __name__ == "__main__":
    unittest.main()
