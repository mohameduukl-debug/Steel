"""Independent validation of the steel-supports tools (member_check, mast_check, frame2d, frame3d, foundation_check).

Every test compares a tool against an INDEPENDENT reference: closed-form solutions, published worked examples or
the standard's own tables. Sources are cited per test and summarised in
.claude/skills/steel-supports/reference/validation.md.

Run:  python3 -m unittest tests.test_steel_supports -v
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


MC = load("steel-supports", "member_check")
MAST = load("steel-supports", "mast_check")
F2 = load("steel-supports", "frame2d")
F3 = load("steel-supports", "frame3d")
FND = load("steel-supports", "foundation_check")
CF = load("tensile-structures", "factors")

E_KN_M2 = 210e6     # E = 210 000 N/mm2 (EN 1993-1-1 3.2.6) in kN/m2
G_KN_M2 = 81e6


def util(rows):
    return max(d / c for _, d, c, _ in rows)


# ======================================================================= member_check
class TestBucklingCurves(unittest.TestCase):
    # ESDEP lecture notes (ECCS buckling curves), §5.2 "Table 1 Reduction factors", values of χ for curves a, b, c, d
    # (copy: https://hobbielektronika.hu/forum/getfile.php?id=6912). Independent tabulation, 4 decimals.
    ESDEP = {0.3: (0.9775, 0.9641, 0.9491, 0.9235), 0.5: (0.9243, 0.8842, 0.8430, 0.7793),
             0.8: (0.7957, 0.7245, 0.6622, 0.5797), 1.0: (0.6656, 0.5970, 0.5399, 0.4671),
             1.5: (0.3724, 0.3422, 0.3145, 0.2766), 2.0: (0.2229, 0.2095, 0.1962, 0.1766),
             3.0: (0.1036, 0.0994, 0.0951, 0.0882)}

    def test_chi_vs_eccs_table(self):
        for lam, vals in self.ESDEP.items():
            for curve, ref in zip(("a", "b", "c", "d"), vals):
                self.assertAlmostEqual(MC.chi(lam, MC.alpha_of(curve)), ref, delta=6e-5, msg=f"{curve} λ̄={lam}")

    def test_chi_curve_a0_closed_form(self):
        # curve a0 is not in the ESDEP table: closed form EN 1993-1-1 eq. (6.49) evaluated here by hand, α = 0.13
        # (EN 1993-1-1 Table 6.1); also checks the register values against Table 6.1.
        self.assertEqual([MC.alpha_of(c) for c in ("a0", "a", "b", "c", "d")], [0.13, 0.21, 0.34, 0.49, 0.76])
        for lam, ref in ((0.3, 0.985935), (0.5, 0.951321), (1.0, 0.725344), (2.0, 0.232299)):
            self.assertAlmostEqual(MC.chi(lam, 0.13), ref, delta=2e-6, msg=f"a0 λ̄={lam}")
        self.assertEqual(MC.chi(0.15, 0.49), 1.0)   # plateau λ̄ ≤ 0.2


class TestLTB(unittest.TestCase):
    def test_mcr_closed_form_ipe300(self):
        # M_cr = C1 π²EIz/L² √(Iw/Iz + L²GIt/(π²EIz)) (SN003b eq. (3), Timoshenko & Gere) with IPE 300 table values
        # Iz = 603.8 cm4, It = 20.12 cm4, Iw = 125.9e3 cm6 (ArcelorMittal / EN 10365 tables), uniform moment C1 = 1.
        Iz, It, Iw, L, E, G = 603.8e4, 20.12e4, 125.9e9, 6000.0, 210000.0, 81000.0
        ref = math.pi ** 2 * E * Iz / L ** 2 * math.sqrt(Iw / Iz + L ** 2 * G * It / (math.pi ** 2 * E * Iz)) / 1e6
        _, res = MC.check(MC.Section("IPE300"), 355, 6.0, 0.0, 50.0, psi_LT=1.0)
        self.assertAlmostEqual(res["C1"], 1.0)
        self.assertAlmostEqual(res["Mcr_kNm"] / ref, 1.0, delta=0.01)

    def test_C1_table_sn003b(self):
        # NCCI SN003b-EN-EU Table 3.1 (C1 for end moments, k = 1)
        for psi, c1 in ((1.0, 1.00), (0.5, 1.31), (0.0, 1.77), (-0.5, 2.33), (-1.0, 2.55)):
            self.assertAlmostEqual(MC.C1_end_moments(psi), c1, places=6)
        self.assertAlmostEqual(MC.C1_end_moments(0.125), (1.52 + 1.77) / 2, places=6)

    def test_gardner_ex_6_8_mcr(self):
        # Gardner & Nethercot, Designers' Guide to EN 1993-1-1 (2005) Example 6.8 (reproduced in Autodesk Robot
        # "Verification Manual Eurocodes", Verification Example 4): UB 762x267x173 S275, segment L = 5.10 m,
        # C1 = 1.879 used by the handbook: Mcr = 4311 kNm, χLT = 0.82 (curve b, general case).
        s = MC.Section("I:762.2:266.7:14.3:21.6:16.5")
        _, res = MC.check(s, 275, 5.1, 0.0, 1276.7, C1=1.879)
        self.assertAlmostEqual(res["Mcr_kNm"] / 4311.0, 1.0, delta=0.005)
        self.assertAlmostEqual(res["chi_LT"], 0.82, delta=0.006)


class TestCHSClass(unittest.TestCase):
    def test_chs_class_limits_table_5_2(self):
        # EN 1993-1-1 Table 5.2 (sheet 3): d/t ≤ 50ε² class 1, ≤ 70ε² class 2, ≤ 90ε² class 3 (ε² = 235/fy)
        for fy in (235, 355, 460):
            e2 = 235.0 / fy
            for D, t in ((219.1, 4.0), (219.1, 5.0), (219.1, 6.3), (323.9, 5.0), (323.9, 8.0), (508.0, 6.3),
                         (168.3, 10.0), (406.4, 6.3)):
                r = D / t
                exp = 1 if r <= 50 * e2 else 2 if r <= 70 * e2 else 3 if r <= 90 * e2 else 4
                cls, _ = MC.section_class(MC.Section(f"CHS:{D}x{t}"), fy, 100.0)
                self.assertEqual(cls, exp, f"CHS {D}x{t} S{fy} d/t={r:.1f}")
                self.assertEqual(MAST.check(D, t, 5.0, 100.0, 0.0, fy)["class"], exp)


class TestWorkedExamples(unittest.TestCase):
    """Gardner & Nethercot, Designers' Guide to EN 1993-1-1 (Thomas Telford 2005); handbook values as reproduced in the
    Autodesk Robot 'Verification Manual Eurocodes' (help.autodesk.com/sfdcarticles/attachments/Verification_Manual_Eurocodes.pdf)."""

    def test_ex_6_7_chs_column(self):
        # CHS 244.5x10 S275, pinned, L = 4 m: Nc,Rd = 2026.8 kN, λ̄ = 0.56 (handbook); Nb,Rd = 1836.5 kN (Robot)
        rows, res = MC.check(MC.Section("CHS:244.5x10"), 275, 4.0, 1630.0)
        fb = [r for r in rows if r[0].startswith("flexural buckling y")][0]
        self.assertAlmostEqual(MC.Section("CHS:244.5x10").A * 275 / 1e3 / 2026.8, 1.0, delta=0.002)
        self.assertAlmostEqual(res["lambda_y"], 0.56, delta=0.006)
        self.assertAlmostEqual(fb[2] / 1836.5, 1.0, delta=0.003)
        r = MAST.check(244.5, 10, 4.0, 1630.0, 0.0, 275)
        self.assertAlmostEqual(r["NbRd_kN"] / 1836.5, 1.0, delta=0.003)

    def test_ex_6_6_reduced_plastic_moment(self):
        # UB 457x191x98 S235, N = 1400 kN: Mpl,y,Rd = 524.5 kNm, MN,y,Rd = 342.2 kNm (6.2.9.1, handbook)
        s = MC.Section("I:467.2:192.8:11.4:19.6:10.2")
        _, res = MC.check(s, 235, 0.01, 1400.0, 300.0)
        self.assertAlmostEqual(s.Wpl_y * 235 / 1e6 / 524.5, 1.0, delta=0.003)
        self.assertAlmostEqual(res["MN_y_Rd"] / 342.2, 1.0, delta=0.005)

    def test_ex_6_10_biaxial_beam_column(self):
        # UC 305x305x240 S275, L = 4.2 m, Lcr,y = 0.7L, N = 3440, My = 420, Mz = 110 kNm. Handbook: section (6.41)
        # 0.33, interaction (6.61) 0.66 and (6.62) 0.97, kzy = 0.79, kzz = 0.78 (Annex B). The moment diagrams are only
        # given graphically: ψy = ψLT ≤ −0.5 (Cmy = CmLT = 0.4) and ψz = 0 (Cmz = 0.6) reproduce the published k factors.
        s = MC.Section("I:352.5:317.9:23.0:37.7:15.2")
        _, res = MC.check(s, 275, 4.2, 3440.0, 420.0, 110.0, ky=0.7, kz=1.0, psi_y=-0.5, psi_z=0.0, psi_LT=-0.5)
        self.assertAlmostEqual(res["biax_LHS"], 0.33, delta=0.015)
        self.assertAlmostEqual(res["eq661"], 0.66, delta=0.01)
        self.assertAlmostEqual(res["eq662"], 0.97, delta=0.01)
        self.assertAlmostEqual(res["kzy"], 0.79, delta=0.01)
        self.assertAlmostEqual(res["kzz"], 0.78, delta=0.01)

    def test_chs_plastic_interaction_vs_strip_integration(self):
        # first-principles plastic N-M interaction of a real annulus: plastic neutral axis at z0, compression below,
        # tension above; closed-form circular-cap area ρ²(θ − sinθcosθ) and first moment (2/3)(ρ² − z0²)^1.5
        def cap(rho, z0):
            if z0 >= rho:
                return 0.0, 0.0
            th = math.acos(max(-1.0, z0 / rho))
            return rho ** 2 * (th - math.sin(th) * math.cos(th)), 2 / 3 * max(rho ** 2 - z0 ** 2, 0.0) ** 1.5

        def exact(D, t, n):
            R, r = D / 2, D / 2 - t
            A = math.pi * (R * R - r * r)
            lo, hi = -R, R
            for _ in range(200):
                z0 = (lo + hi) / 2
                Ao = cap(R, z0)[0] - cap(r, z0)[0]                  # area in tension (above z0)
                if (A - 2 * Ao) / A > n:
                    hi = z0
                else:
                    lo = z0
            S = cap(R, z0)[1] - cap(r, z0)[1]
            return 2 * S / (2 / 3 * (R ** 3 - r ** 3) * 2)
        for D, t in ((219.1, 8.0), (168.3, 12.5)):
            s = MC.Section(f"CHS:{D}x{t}")
            for n in (0.2, 0.5, 0.8, 0.9):
                MNy, _, _, _ = MC.plastic_NM(s, 355, n * s.A * 355, s.Wpl_y * 355, s.Wpl_z * 355, 1.0)
                ref = exact(D, t, n)
                ratio = MNy / (s.Wpl_y * 355) / ref
                self.assertLessEqual(ratio, 1.003)          # cos(πn/2) never notably above the exact annulus
                self.assertGreaterEqual(ratio, 0.96)        # and at most 4 % conservative (thick tube, n = 0.9)

    def test_rhs_plastic_interaction_eq_6_39(self):
        # EN 1993-1-1 eq. (6.39): M_N,y = M_pl,y(1 − n)/(1 − 0.5 a_w), a_w = (A − 2bt)/A ≤ 0.5, evaluated with the
        # EN 10210-2 table values of RHS 200x100x8 (A = 44.8 cm², W_pl,y = 282 cm³), S355, N = 500 kN
        A, Wpl, b, t, fy, N = 4480.0, 282e3, 100.0, 8.0, 355.0, 500e3
        n = N / (A * fy)
        aw = min((A - 2 * b * t) / A, 0.5)
        ref = Wpl * fy * (1 - n) / (1 - 0.5 * aw) / 1e6
        _, res = MC.check(MC.Section("RHS:200x100x8"), fy, 0.01, 500.0, 10.0)
        self.assertAlmostEqual(res["MN_y_Rd"] / ref, 1.0, delta=0.02)

    def test_tension_and_class3_paths(self):
        # tension: N_t,Rd = A f_y/γM0 (6.6); class 3 CHS: linear N/N_Rd + M/(W_el f_y) (6.2.9.2 / 6.2.1(7))
        s = MC.Section("CHS:219.1x8")
        rows, _ = MC.check(s, 355, 5.0, -300.0)
        self.assertAlmostEqual(rows[0][2], math.pi / 4 * (219.1 ** 2 - 203.1 ** 2) * 355 / 1e3, places=6)
        s3 = MC.Section("CHS:323.9x6.3")                    # d/t = 51.4: class 3 for S355 (46.3 < d/t ≤ 59.6)
        rows, res = MC.check(s3, 355, 0.01, 200.0, 30.0)
        self.assertEqual(res["class"], 3)
        D, d = 323.9, 323.9 - 12.6
        A = math.pi / 4 * (D ** 2 - d ** 2)
        Wel = math.pi / 32 * (D ** 4 - d ** 4) / D
        ref = 200e3 / (A * 355) + 30e6 / (Wel * 355)
        self.assertAlmostEqual([r for r in rows if r[0].startswith("section")][0][1], ref, places=9)

    def test_sway_cm(self):
        # EN 1993-1-1 Annex B Table B.3 note: sway buckling mode -> Cmy = 0.9 (cantilever mast k = 2)
        r = MAST.check(273, 10, 6, 300, 40, 355, k=2.0)
        self.assertEqual(r["Cm"], 0.9)
        _, res = MC.check(MC.Section("CHS:273x10"), 355, 6, 300, 40, ky=2.0, kz=2.0)
        self.assertEqual(res["Cmy"], 0.9)


# ======================================================================= mast_check vs closed form / frames
class TestMastCheck(unittest.TestCase):
    def test_euler_and_chi_closed_form(self):
        # N_cr = π²EI/(kL)² (Euler) and χ from eq. (6.49), curve a (α = 0.21), evaluated by hand
        D, t, L = 219.1, 8.0, 7.5
        I = math.pi / 64 * (D ** 4 - (D - 2 * t) ** 4)
        A = math.pi / 4 * (D ** 2 - (D - 2 * t) ** 2)
        for k in (1.0, 2.0):
            r = MAST.check(D, t, L, 100.0, 0.0, 355, k=k)
            Ncr = math.pi ** 2 * 210000 * I / (k * L * 1000) ** 2
            self.assertAlmostEqual(r["Ncr_kN"], Ncr / 1e3, places=6)
            lam = math.sqrt(A * 355 / Ncr)
            ph = 0.5 * (1 + 0.21 * (lam - 0.2) + lam ** 2)
            self.assertAlmostEqual(r["chi"], 1 / (ph + math.sqrt(ph ** 2 - lam ** 2)), places=9)

    def test_ncr_matches_frame2d_and_frame3d(self):
        D, t, L = 219.1, 8.0, 10.0
        for base, k in (("pinned", 1.0), ("fixed", 2.0)):
            Ncr = MAST.check(D, t, L, 1.0, 0.0, 355, k=k)["Ncr_kN"]
            fr = F2.gen_mast(L, 20, D, D, D, t, 355, base, 1.0, 0.0, [])
            _, _, f = fr.linear()
            lam2, _ = fr.buckling(f)
            md = F3.gen_mast(L, f"CHS:{D}x{t}", base, ties=(), loads=[[0, 0, -1.0]], div=16)
            if base == "pinned":
                md.supports[md.head] = (1, 1, 0, 0, 0, 0)
            lam3 = F3.run(md, imp="none", quiet=True)["alpha_cr"]
            self.assertAlmostEqual(lam2 / Ncr, 1.0, delta=0.002)
            self.assertAlmostEqual(lam3 / Ncr, 1.0, delta=0.002)


# ======================================================================= frame3d
def cantilever_model(div=4):
    return F3.from_json({"nodes": [[0, 0, 0], [4, 0, 0]], "supports": {"0": "fixed"},
                         "members": [{"name": "C", "nodes": [0, 1], "A": 5e-3, "Iy": 8e-5, "Iz": 2e-5, "J": 3e-5,
                                      "div": div}],
                         "loads": {"nodal": {"1": [0, 10.0, -20.0, 5.0, 0, 0]}}})


class TestFrame3D(unittest.TestCase):
    def test_cantilever_deflection_and_torsion(self):
        # closed forms: δ = PL³/(3EI) about both axes, twist φ = TL/(GJ)
        md = cantilever_model()
        r = F3.run(md, imp="none", quiet=True)
        u = r["disp_first"][1]
        self.assertAlmostEqual(u[1] / (10 * 4 ** 3 / (3 * E_KN_M2 * 2e-5)), 1.0, delta=1e-4)
        self.assertAlmostEqual(u[2] / (-20 * 4 ** 3 / (3 * E_KN_M2 * 8e-5)), 1.0, delta=1e-4)
        self.assertAlmostEqual(r["u_first"][md.dof[(1, 3)]] / (5 * 4 / (G_KN_M2 * 3e-5)), 1.0, delta=1e-4)
        R = r["reactions_first"][0]
        self.assertAlmostEqual(R[1], -10.0, places=6)
        self.assertAlmostEqual(R[5] / -40.0, 1.0, delta=1e-6)      # Mz = −P·L about global z
        self.assertAlmostEqual(R[3], -5.0, places=6)

    def test_euler_pinned_and_cantilever(self):
        # α_cr vs π²EI/L² (pinned) and π²EI/(4L²) (cantilever), N = 1 kN
        EI = E_KN_M2 * MC.Section("CHS:219.1x8").Iy * 1e-12
        for sup0, sup1, k in (([1, 1, 1, 0, 0, 1], [1, 1, 0, 0, 0, 0], 1.0), ("fixed", [0] * 6, 2.0)):
            md = F3.from_json({"nodes": [[0, 0, 0], [0, 0, 10]], "supports": {"0": sup0, "1": sup1},
                               "members": [{"name": "M", "nodes": [0, 1], "section": "CHS:219.1x8", "div": 8}],
                               "loads": {"nodal": {"1": [0, 0, -1.0]}}})
            lam = F3.run(md, imp="none", quiet=True)["alpha_cr"]
            self.assertAlmostEqual(lam / (math.pi ** 2 * EI / (k * 10) ** 2), 1.0, delta=5e-4)

    def test_member_end_releases_simply_supported_beam(self):
        # fully fixed supports + pinned member ends = simply supported beam: w = 5qL⁴/384EI, M = qL²/8
        md = F3.from_json({"nodes": [[0, 0, 0], [6, 0, 0]], "supports": {"0": "fixed", "1": "fixed"},
                           "members": [{"name": "B", "nodes": [0, 1], "section": "IPE300", "div": 6,
                                        "release_start": "pinned", "release_end": "pinned"}],
                           "loads": {"udl": [{"member": "B", "q": [0, 0, -10.0]}]}})
        r = F3.run(md, imp="none", quiet=True)
        mid = [v for v, p in enumerate(md.nodes) if abs(p[0] - 3) < 1e-9][0]
        EI = E_KN_M2 * MC.Section("IPE300").Iy * 1e-12
        self.assertAlmostEqual(r["disp_first"][mid][2] / (-5 * 10 * 6 ** 4 / (384 * EI)), 1.0, delta=1e-4)
        self.assertAlmostEqual(r["first_order"]["B"]["My"], 45.0, delta=0.01)
        self.assertAlmostEqual(r["reactions_first"][0][4], 0.0, delta=1e-6)   # no fixed-end moment

    def guyed(self, P, string=False):
        H, a = 8.0, 6.0
        md = F3.from_json({"nodes": [[0, 0, 0], [0, 0, H], [-a, 0, 0], [a, 0, 0]],
                           "supports": {"0": [1, 1, 1, 1, 0, 1], "1": [0, 1, 0, 0, 0, 0], "2": "pinned", "3": "pinned"},
                           "members": [{"name": "M", "nodes": [0, 1], "A": 1e6 / E_KN_M2, "Iy": 1e-4, "Iz": 1e-4,
                                        "J": 1e-4, "div": 2, "release_end": "pinned"},
                                       {"name": "W", "nodes": [1, 2], "type": "cable", "EA": 20000.0, "prestress": 10.0},
                                       {"name": "L", "nodes": [1, 3], "type": "cable", "EA": 20000.0, "prestress": 10.0}],
                           "loads": {"nodal": {"1": [P, 0, 0]}}})
        md.cable_string_first = string
        return F3.run(md, imp="none", quiet=True)

    @staticmethod
    def guyed_hand(P, both):
        # hand solution (2 DOF): K = Σ EA/Lc e eᵀ + EA_m/H e_z e_zᵀ, F = P e_x − Σ T0 e (prestress pulls the head)
        H, a, EAc, T0, EAm = 8.0, 6.0, 20000.0, 10.0, 1e6
        Lc = math.hypot(a, H)
        cabs = [-a, a] if both else [-a]
        K = [[0.0, 0.0], [0.0, EAm / H]]
        F = [P, 0.0]
        for x in cabs:
            e = (-x / Lc, H / Lc)
            for i in range(2):
                for j in range(2):
                    K[i][j] += EAc / Lc * e[i] * e[j]
                F[i] -= T0 * e[i]
        det = K[0][0] * K[1][1] - K[0][1] * K[1][0]
        dx = (F[0] * K[1][1] - K[0][1] * F[1]) / det
        dz = (K[0][0] * F[1] - K[1][0] * F[0]) / det
        T = [T0 + EAc / Lc * ((-x / Lc) * dx + (H / Lc) * dz) for x in cabs]
        return dx, dz, T, EAm / H * dz

    def test_guyed_mast_hand_solution_both_regimes(self):
        # regime 1 (both prestressed guys active) and regime 2 (leeward guy slack, tension-only)
        for P, both in ((5.0, True), (40.0, False)):
            r = self.guyed(P)
            dx, dz, T, Nm = self.guyed_hand(P, both)
            self.assertAlmostEqual(r["disp_first"][1][0] / dx, 1.0, delta=1e-5)
            self.assertAlmostEqual(r["disp_first"][1][2] / dz, 1.0, delta=1e-5)
            self.assertAlmostEqual(r["first_order"]["W"]["N_max"] / T[0], 1.0, delta=1e-5)
            self.assertAlmostEqual(r["first_order"]["M"]["N_min"] / Nm, 1.0, delta=1e-5)
            if both:
                self.assertAlmostEqual(r["first_order"]["L"]["N_max"] / T[1], 1.0, delta=1e-5)
            else:
                self.assertTrue(r["first_order"]["L"]["slack"])
                self.assertEqual(r["first_order"]["L"]["N_max"], 0.0)
        # statics of the slack regime (rigid mast limit): T = P/cosθ, N_mast = P·tanθ
        self.assertAlmostEqual(self.guyed(40.0)["first_order"]["W"]["N_max"] / (40 / 0.6), 1.0, delta=0.01)

    def test_two_bar_truss(self):
        # symmetric two-bar truss (bars at θ to the horizontal, span 2a, rise h), vertical load P at the apex:
        # N = −P/(2 sinθ) (statics), apex deflection δ = P·L/(2EA sin²θ) (virtual work)
        a, h, P, EA = 4.0, 3.0, 100.0, 2.0e5
        md = F3.from_json({"nodes": [[-a, 0, 0], [0, 0, h], [a, 0, 0]],
                           "supports": {"0": "pinned", "2": "pinned", "1": [0, 1, 0, 0, 0, 0]},
                           "members": [{"name": "B1", "nodes": [0, 1], "type": "truss", "EA": EA},
                                       {"name": "B2", "nodes": [2, 1], "type": "truss", "EA": EA}],
                           "loads": {"nodal": {"1": [0, 0, -P]}}})
        md.cable_string_first = False
        r = F3.run(md, imp="none", quiet=True)
        L, sin = 5.0, 0.6
        self.assertAlmostEqual(r["first_order"]["B1"]["N_max"], -P / (2 * sin), places=6)
        self.assertAlmostEqual(r["disp_first"][1][2] / (-P * L / (2 * EA * sin ** 2)), 1.0, delta=1e-9)

    def test_sway_imperfection_amplitude(self):
        # --imp sway: amplitude φ0·h with φ0 = 1/200 (EN 1993-1-1 5.3.2(3)), αh = αm = 1
        md = F3.gen_mast(8.0, "CHS:219.1x8", "fixed", ties=(), loads=[[1.0, 0, -100.0]], div=8)
        r = F3.run(md, imp="sway", quiet=True)
        self.assertAlmostEqual(r["imperfection"]["amplitude_m"], 8.0 / 200, places=12)
        self.assertGreater(r["second_order"]["MAST"]["My"] + r["second_order"]["MAST"]["Mz"],
                           r["first_order"]["MAST"]["My"] + r["first_order"]["MAST"]["Mz"])

    def test_agrees_with_frame2d_planar_arch(self):
        # same planar arch in both tools (out-of-plane DOFs held in frame3d): α_cr, N, M, reactions and the
        # second-order moment with the same imperfection amplitude
        for sup in ("pinned", "fixed"):
            fr = F2.gen_arch(30, 6, 24, "CHS:323.9x10", 355, sup, 12.0)
            r2 = F2.run(fr, quiet=True)
            n = len(fr.nodes)
            sp = [1, 1, 1, 1, 0, 1] if sup == "pinned" else [1, 1, 1, 1, 1, 1]
            supports = {str(i): [0, 1, 0, 1, 0, 1] for i in range(n)}
            supports["0"] = supports[str(n - 1)] = sp
            md = F3.from_json({"nodes": [[x, 0, y] for x, y in fr.nodes], "supports": supports,
                               "members": [{"name": "ARCH", "nodes": list(range(n)), "section": "CHS:323.9x10",
                                            "div": 1}]})
            for ei, (eu, qx, qy) in enumerate(fr.udl):
                md.udl.append((eu, [qx, 0.0, qy]))
            r3 = F3.run(md, imp="none", quiet=True)
            self.assertAlmostEqual(r3["alpha_cr"] / r2["alpha_cr"], 1.0, delta=1e-4)
            self.assertAlmostEqual(r3["first_order"]["ARCH"]["My"] / r2["first_order"]["ARCH"]["M_max"], 1.0, delta=1e-4)
            self.assertAlmostEqual(r3["first_order"]["ARCH"]["N_min"] / r2["first_order"]["ARCH"]["N_min"], 1.0, delta=1e-5)
            self.assertAlmostEqual(r3["reactions_first"][0][0] / r2["reactions"][0][0], 1.0, delta=1e-5)
        # second order, asymmetric load (half-span point loads), no imperfection: same P-Δ answer
        fr = F2.gen_arch(30, 6, 24, "CHS:323.9x10", 355, "pinned", 12.0, P=[(6, 0.0, -80.0)])
        _, u2, f2 = fr.second_order(None)
        M2 = max(max(abs(f["M1"]), abs(f["M2"])) for f in f2)
        n = len(fr.nodes)
        supports = {str(i): [0, 1, 0, 1, 0, 1] for i in range(n)}
        supports["0"] = supports[str(n - 1)] = [1, 1, 1, 1, 0, 1]
        md = F3.from_json({"nodes": [[x, 0, y] for x, y in fr.nodes], "supports": supports,
                           "members": [{"name": "ARCH", "nodes": list(range(n)), "section": "CHS:323.9x10", "div": 1}],
                           "loads": {"nodal": {"6": [0, 0, -80.0]}}})
        for (eu, qx, qy) in fr.udl:
            md.udl.append((eu, [qx, 0.0, qy]))
        r3 = F3.run(md, imp="none", quiet=True)
        self.assertAlmostEqual(r3["second_order"]["ARCH"]["My"] / M2, 1.0, delta=1e-3)
        self.assertGreater(M2, 1.05 * r3["first_order"]["ARCH"]["My"])     # second-order effect is significant

    def test_second_order_amplification_tan_u_over_u(self):
        # pinned column, N = 0.5 Ncr, lateral midspan load Q: M2/M1 = tan(u)/u, u = (π/2)√(N/Ncr) (Timoshenko & Gere)
        EI = E_KN_M2 * MC.Section("CHS:219.1x8").Iy * 1e-12
        Ncr = math.pi ** 2 * EI / 8.0 ** 2
        md = F3.from_json({"nodes": [[0, 0, 0], [0, 0, 4], [0, 0, 8]],
                           "supports": {"0": [1, 1, 1, 0, 0, 1], "2": [1, 1, 0, 0, 0, 0]},
                           "members": [{"name": "C", "nodes": [0, 1, 2], "section": "CHS:219.1x8", "div": 8}],
                           "loads": {"nodal": {"2": [0, 0, -0.5 * Ncr], "1": [1.0, 0, 0]}}})
        r = F3.run(md, imp="none", quiet=True)
        M1 = math.hypot(r["first_order"]["C"]["My"], r["first_order"]["C"]["Mz"])
        M2 = math.hypot(r["second_order"]["C"]["My"], r["second_order"]["C"]["Mz"])
        u = math.pi / 2 * math.sqrt(0.5)
        self.assertAlmostEqual(M1 / 2.0, 1.0, delta=1e-6)          # QL/4
        self.assertAlmostEqual(M2 / M1 / (math.tan(u) / u), 1.0, delta=0.005)

    def test_unique_imperfection_reproduces_buckling_curve(self):
        # EN 1993-1-1 5.3.2(11): with η_init and e0 from eq. (5.10), a second-order cross-section check
        # N/N_Rk + M/M_Rk of a pinned column loaded with N = χ·N_Rk (χ from eq. 6.49) must give 1.0.
        for spec, L, fy, rotfree in (("CHS:219.1x8", 7.5, 355, False), ("CHS:219.1x8", 15.0, 275, False),
                                     ("IPE300", 5.0, 355, True)):
            sec = MC.Section(spec)
            _, res = MC.check(sec, fy, L, 100.0)
            chi = min(res["chi_y"], res["chi_z"])
            NRk = sec.A * fy / 1e3
            md = F3.from_json({"nodes": [[0, 0, 0], [0, 0, L]],
                               "supports": {"0": [1, 1, 1, 0, 0, 1], "1": [1, 1, 0, 0, 0, 0]},
                               "members": [{"name": "C", "nodes": [0, 1], "section": spec, "fy": fy, "div": 16,
                                            "ref": [1, 0, 0]}],
                               "loads": {"nodal": {"1": [0, 0, -chi * NRk]}}})
            r = F3.run(md, imp="unique", quiet=True)
            s = r["second_order"]["C"]
            W = sec.Wpl_z if rotfree else sec.Wpl_y
            u = chi + math.hypot(s["My"], s["Mz"]) * 1e6 / (W * fy)
            self.assertAlmostEqual(u, 1.0, delta=0.008, msg=spec)

    def test_membrane_reactions_import(self):
        # pull vectors from the shared model JSON (model-schema.md) act on the mast head; global equilibrium
        pull = [6.0, -2.0, -3.0]
        with tempfile.TemporaryDirectory() as td:
            mpath = os.path.join(td, "sail.json")
            with open(mpath, "w") as fh:
                json.dump({"nodes": [{"id": 7, "xyz": [0.0, 0.0, 8.0], "fixed": True}],
                           "reactions": [{"node": 7, "pull": pull, "magnitude": math.sqrt(49)}]}, fh)
            ties = ["--tie=-5,0,0:25000:10", "--tie", "2.5,4.33,0:25000:10", "--tie", "2.5,-4.33,0:25000:10"]
            res = quiet(F3.main, ["mast", "--H", "8", "--section", "CHS:219.1x8", "--reactions", mpath,
                                  "--node", "7", "--check"] + ties)
            Rsum = [sum(r[i] for r in res["reactions_first"].values()) for i in range(3)]
            for i in range(3):
                self.assertAlmostEqual(Rsum[i], -pull[i], places=6)
            self.assertIn("design", res)
            # coordinate matching through --input JSON (no map)
            fpath = os.path.join(td, "frame.json")
            with open(fpath, "w") as fh:
                json.dump({"nodes": [[0, 0, 0], [0, 0, 8], [-5, 0, 0], [3, 4, 0], [3, -4, 0]],
                           "supports": {"0": [1, 1, 1, 0, 0, 1], "2": "pinned", "3": "pinned", "4": "pinned"},
                           "members": [{"name": "MAST", "nodes": [0, 1], "section": "CHS:219.1x8", "div": 6},
                                       {"name": "T1", "nodes": [1, 2], "type": "cable", "EA": 25000, "prestress": 10},
                                       {"name": "T2", "nodes": [1, 3], "type": "cable", "EA": 25000, "prestress": 10},
                                       {"name": "T3", "nodes": [1, 4], "type": "cable", "EA": 25000, "prestress": 10}],
                           "reactions": {"file": "sail.json", "factor": 1.5}}, fh)
            res2 = quiet(F3.main, ["--input", fpath])
            Rsum = [sum(r[i] for r in res2["reactions_second"].values()) for i in range(3)]
            for i in range(3):
                self.assertAlmostEqual(Rsum[i], -1.5 * pull[i], places=5)

    def test_mechanism_warning(self):
        md = F3.from_json({"nodes": [[0, 0, 0], [0, 0, 5]], "supports": {"0": "pinned", "1": [1, 1, 0, 0, 0, 0]},
                           "members": [{"name": "C", "nodes": [0, 1], "section": "CHS:219.1x8", "div": 4}],
                           "loads": {"nodal": {"1": [0, 0, -100.0]}}})
        r = F3.run(md, imp="none", quiet=True)
        self.assertTrue(any("near-mechanism" in n for n in r["notes"]))


# ======================================================================= foundation_check
class TestFoundations(unittest.TestCase):
    def test_block_hand_calculation(self):
        # EN 1997-1 2.4.7.2 eq. (2.4) EQU (overturning about the toe, uplift), 6.5.3 eq. (6.3a) sliding
        # R = V'·tan δ / γ_R,h, Annex D effective width B' = B − 2e (Meyerhof). Hand calculation:
        B, L, D, V, H, ha, mu = 2.5, 2.5, 1.5, 60.0, 45.0, 0.3, 0.45
        W = B * L * D * 24.0                                        # 225 kN
        rows, info = FND.block(B, L, D, V, H, ha, mu, 200.0)
        self.assertAlmostEqual(info["W_kN"], 225.0, places=9)
        self.assertAlmostEqual(rows[0][2], 0.9 * 225.0, places=9)                      # uplift
        self.assertAlmostEqual(rows[1][2], (0.9 * 225.0 - 60.0) * 0.45 / 1.1, places=9)   # 58.30 kN sliding
        self.assertAlmostEqual(rows[2][1], 45.0 * 1.8 + 60.0 * 1.25, places=9)         # M_dst = 156 kNm
        self.assertAlmostEqual(rows[2][2], 0.9 * 225.0 * 1.25, places=9)               # M_stb = 253.1 kNm
        Nb = 1.35 * W - V                                           # 243.75 kN (γ_G,sup governs)
        e = H * (D + ha) / Nb                                       # 0.3323 m
        self.assertAlmostEqual(info["q_kPa"], Nb / ((B - 2 * e) * L), places=6)       # 53.12 kPa
        self.assertAlmostEqual(info["q_kPa"], 53.12, delta=0.01)

    def test_block_unfactored_pull(self):
        # --unfactored: the pull is multiplied by γ_Q,dst = 1.5 (EN 1997-1 Table A.1, EQU, variable action)
        rows, _ = quiet(FND.block, 2.0, 2.0, 1.2, 40.0, 30.0, 0.3, 0.45, 200.0, unfactored=True)
        self.assertAlmostEqual(rows[0][1], 60.0, places=9)
        self.assertAlmostEqual(rows[1][1], 45.0, places=9)

    def test_helical_torque_correlation(self):
        # ICC-ES ESR-2794 4.1.5: Q_ult = Kt·T, Kt = 10 ft-1 (32.8 m-1) square shaft, Q_all = 0.5 Q_ult.
        # Supportworks HA150 (1.5 in square bar): max torque 6,500 ft-lb -> Qu = 65.0 kips with Kt = 10 ft-1.
        T = 6500 * 4.4482216 * 0.3048 / 1000                       # kNm
        rows, info = FND.helical(T, 50.0, shaft="SS5")
        self.assertAlmostEqual(info["Qu"] / (65.0 * 4.4482216), 1.0, delta=0.002)
        self.assertAlmostEqual(info["Qall"], info["Qu"] / 2.0, places=9)
        self.assertAlmostEqual(FND.helical(10.0, 50.0, shaft="RS3500")[1]["Qu"], 230.0, places=9)
        self.assertEqual(FND.helical(10.0, 50.0, FS=1.5)[1]["FS"], 2.0)       # FS never below 2.0

    def test_register_geotech_verified(self):
        self.assertEqual(CF.status("geotech.helical_Kt_per_m"), "V")
        self.assertEqual(CF.status("geotech.helical_FS"), "V")
        self.assertAlmostEqual(CF.get("geotech.helical_Kt_per_m"), 10 / 0.3048, delta=0.05)


class TestCLIs(unittest.TestCase):
    def test_all_clis_print_assumptions(self):
        cases = [(MC.main, ["--section", "IPE300", "--L", "6", "--N", "50", "--My", "80", "--psi-LT", "0"]),
                 (MAST.main, ["--D", "219.1", "--t", "8", "--L", "7.5", "--N", "420", "--M", "12"]),
                 (F2.main, ["mast", "--H", "6", "--N", "200", "--check"]),
                 (F3.main, ["mast", "--H", "6", "--section", "CHS:168.3x8", "--tie=-5,0,0:20000:5",
                            "--tie", "3,4,0:20000:5", "--tie", "3,-4,0:20000:5", "--load", "8,2,-4", "--check"]),
                 (FND.main, ["block", "--B", "2", "--L", "2", "--D", "1.2", "--V", "60", "--H", "45"]),
                 (FND.main, ["helical", "--T", "8", "--pull", "110"])]
        for fn, argv in cases:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                fn(argv)
            self.assertIn("Assumptions", out.getvalue(), fn.__module__)


if __name__ == "__main__":
    unittest.main()
