"""Independent validation of the tensile-connections tools (stdlib unittest).

Every test reproduces a published worked example, the standard's own numbers or a closed-form hand calculation;
the source is cited in each test. The same cases are listed in
.claude/skills/tensile-connections/reference/validation.md.

Run:  python3 -m unittest tests.test_tensile_connections -v
"""
import contextlib
import importlib.util
import io
import math
import os
import sys
import types
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


J = load("tensile-connections", "steel_joint_checks")
PIN = load("tensile-connections", "pin_connection")
CP = load("tensile-connections", "corner_plate")
FAT = load("tensile-connections", "fatigue_check")
CF = load("tensile-structures", "factors")

IN, KSI, KIP = 25.4, 6.894757, 4448.222          # unit conversions for the AISC example


def rel(a, b):
    return abs(a - b) / abs(b)


class TestBoltsSBE(unittest.TestCase):
    """SBE 'Multi-storey steel buildings Part 5: Joint design' (ArcelorMittal/SCI, 2009), worked example 3.4
    Fin plate, https://www.steelconstruction.info/images/5/53/SBE_MS5.pdf pp. 5-40..5-42: IPE A 550 S275,
    fin plate 360x160x10 S275 (f_u = 430), 10 x M20 8.8, d0 = 22, e1 = 40, p1 = 70, e2 = 50, p2 = 60, z = 80."""

    def test_single_bolt_shear_and_bearing(self):
        R = J.bolt_resistances(20, "8.8", 10, 430, 40, 50, 70, 60, d0=22)          # vertical, fin plate
        self.assertAlmostEqual(R["FvRd"], 94.08, places=2)                         # SBE: F_v,Rd = 94 kN
        self.assertAlmostEqual(R["k1"], 2.12, delta=0.005)                          # SBE: k1 = 2.12
        self.assertAlmostEqual(R["ab"], 0.61, delta=0.005)                          # SBE: αb = 0.61
        self.assertLess(rel(R["FbRd"], 89.0), 0.01)                                 # SBE: 89 kN (rounded k1, αb)
        H = J.bolt_resistances(20, "8.8", 10, 430, 50, 40, 60, 70, d0=22)          # horizontal, fin plate
        self.assertLess(rel(H["FbRd"], 114.0), 0.01)                                # SBE: 114 kN
        W = J.bolt_resistances(20, "8.8", 9, 430, 0, 40, 70, 60, d0=22)            # vertical, beam web (no end)
        self.assertLess(rel(W["FbRd"], 106.0), 0.01)                                # SBE: 106 kN
        W = J.bolt_resistances(20, "8.8", 9, 430, 40, 0, 60, 70, d0=22)            # horizontal, beam web
        self.assertLess(rel(W["FbRd"], 94.0), 0.01)                                 # SBE: 94 kN

    def test_eccentric_group_shear_and_bearing(self):
        co = J.grid(5, 2, 70, 60)
        V = 350.0
        rows, R = J.bolts(co, 0, V, V * 0.080, 0, 1, 20, "8.8", 10, 430, 40, 50, 70, 60, True, 22)
        self.assertLess(rel(V * R["FvRd"] / rows[0][1], 584.0), 0.005)            # SBE: V_Rd = 584 kN (bolt shear)
        self.assertLess(rel(V / R["bearing_util"], 605.0), 0.015)                  # SBE: 605 kN (fin plate bearing)
        rows, R = J.bolts(co, 0, V, V * 0.080, 0, 1, 20, "8.8", 9, 430, 0, 40, 70, 60, True, 22)
        self.assertLess(rel(V / R["bearing_util"], 624.0), 0.005)                  # SBE: 624 kN (beam web bearing)

    def test_tension_and_wald_bearing(self):
        # SCI P398 (2013) Example C.1 sheet 5, https://steelconstruction.info/images/5/5d/SCI_P398.pdf:
        # F_t,Rd = 0.9 x 800 x 353 / 1.25 = 203 kN (M24 8.8)
        self.assertLess(rel(J.bolt_resistances(24, "8.8", 10, 430, 0, 0, 0, 0)["FtRd"], 203.0), 0.003)
        # Wald, Eurocodes workshop JRC Brussels 2014 'Bolted connection of double angle bar',
        # https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/06_Eurocodes_Steel_Workshop_WALD.pdf:
        # M20 5.6, two shear planes F_v,Rd = 2 x 0.6 x 245 x 500/1.25 = 117.6 kN; internal bolt t = 8, f_u = 360,
        # e2 = 35, p1 = 70 -> k1 = 2.5, αb = 0.811, F_b,Rd = 93.4 kN
        R = J.bolt_resistances(20, "5.6", 8, 360, 0, 35, 70, 0, d0=22)
        self.assertAlmostEqual(2 * R["FvRd"], 117.6, places=1)
        self.assertAlmostEqual(R["k1"], 2.5)
        self.assertLess(rel(R["FbRd"], 93.4), 0.002)

    def test_punching_dm_from_iso_dimensions(self):
        # EN 1993-1-8 Table 3.4: B_p,Rd = 0.6 π d_m t_p f_u/γM2, d_m = mean of across flats and across corners.
        # M24: s = 36, e = 39.55 (e used by SCI P398 sheet 5: 'dw = 39.55 mm (across the bolt head)')
        R = J.bolt_resistances(24, "8.8", 10, 430, 0, 0, 0, 0)
        self.assertAlmostEqual(R["dm"], (36 + 39.55) / 2)
        self.assertAlmostEqual(R["BpRd"], 0.6 * math.pi * 37.775 * 10 * 430 / 1.25 / 1e3, places=6)


class TestBlockTearingGusset(unittest.TestCase):
    def test_block_tearing_published(self):
        # SBE Part 5 fin plate (above) 3.2.2.3: A_nt = 770, A_nv = 2210 mm², V_Rd,b = 483 kN (Eq. 3.10)
        Ant, Anv = J.block_areas(5, 2, 70, 60, 40, 50, 22, 10, "L")
        self.assertAlmostEqual(Ant, 770.0)
        self.assertAlmostEqual(Anv, 2210.0)
        self.assertLess(rel(J.block_tearing(Ant, Anv, 275, 430, eccentric=True), 483.0), 0.002)
        # Wald JRC 2014 'Fin plate connection': 3 x M20, beam web 7.1 mm S235, V_Rd = 39.9 + 159 = 199 kN (3.10)
        Ant, Anv = J.block_areas(3, 1, 70, 0, 80, 50, 22, 7.1, "L")
        self.assertLess(rel(J.block_tearing(Ant, Anv, 235, 360, eccentric=True), 199.0), 0.003)
        # Wald JRC 2014 'Fin plate, tying resistance': f_u A_nt/γMu + f_y A_nv/(√3 γM0) = 223 + 75.1 = 298 kN
        V = J.block_tearing(7.1 * (140 - 2 * 22), 2 * 7.1 * (50 - 11), 235, 360, False, 1.0, 1.1)
        self.assertLess(rel(V, 298.0), 0.002)

    def test_whitmore_and_aisc_compression_dowswell(self):
        # Dowswell, 'Design for gusset plate buckling with variable stress trajectories', AISC Eng. J. 2019 Q3,
        # https://ej.aisc.org/index.php/engj/article/download/1153/1152, design example: t = 0.5 in, Fy = 50 ksi,
        # w = 19.3 in, l = 24 in. Thornton: K = 0.65, L = 4.71 in -> KL/r < 25 -> Whitmore yielding Pn = 1,180 kips.
        t, Fy, E = 0.5 * IN, 50 * KSI, 29000 * KSI
        be = J.whitmore_width(0, 0, 0, 0, l=24 * IN, w=19.3 * IN)
        ca = J.plate_column_aisc(be, t, Fy, 0.65 * 4.71 * IN, E=E, phi=0.9)
        self.assertLess(ca["KL_r"], 25)
        self.assertLess(rel(ca["Pn"] / KIP, 1180.0), 0.005)
        # proposed method: θ = 35.7°, b_e = 53.8 in, K = 0.40, L = 17.0 in -> Lc/r = 47.2, Fe = 128 ksi,
        # Fcr = 42.5 ksi, Pn = 1,140 kips (AISC E3)
        be = J.whitmore_width(0, 0, 0, 0, angle=35.7, l=24 * IN, w=19.3 * IN)
        self.assertLess(rel(be / IN, 53.8), 0.002)
        ca = J.plate_column_aisc(be, t, Fy, 0.40 * 17.0 * IN, E=E, phi=0.75)
        self.assertLess(rel(ca["KL_r"], 47.2), 0.003)
        self.assertLess(rel(ca["Fe"] / KSI, 128.0), 0.01)
        self.assertLess(rel(ca["Fcr"] / KSI, 42.5), 0.003)
        self.assertLess(rel(ca["Pn"] / KIP, 1140.0), 0.005)

    def test_aisc_block_shear_teh_deierlein(self):
        # Teh & Deierlein, 'Effective shear plane model for tearout and block shear failure of bolted connections',
        # AISC Eng. J. 2017 Q3, https://ej.aisc.org/index.php/engj/article/download/1117/1116, design example:
        # Fy 50, Fu 65 ksi, A_nt = 1.02 in²; n_r = 3: A_gv 8.12, A_nv 5.39 -> φRn = 207 kips; n_r = 4: A_gv 11.2,
        # A_nv 7.42 -> 267 kips (AISC J4.3, U_bs = 1, φ = 0.75)
        self.assertLess(rel(J.aisc_block_shear(8.12, 5.39, 1.02, 50, 65, 1.0, 0.75), 207.0), 0.003)
        self.assertLess(rel(J.aisc_block_shear(11.2, 7.42, 1.02, 50, 65, 1.0, 0.75), 267.0), 0.003)

    def test_en_buckling_curve_c(self):
        # SBE Part 4 worked example A.5, https://www.steelconstruction.info/images/0/01/SBE_MS4.pdf p.4-97:
        # curve c (α = 0.49), λ = 0.787 -> Φ = 0.953, χ = 0.671
        self.assertAlmostEqual(J.chi_en(0.787, 0.49), 0.671, delta=0.0015)   # 0.6703 exact; SBE rounds Φ

    def test_gusset_command_compression(self):
        a = J.gusset(-300, 3, 2, 70, 60, 40, 40, 20, 22, "8.8", 12, 355, 490, l_avg=150, aisc=True)
        rows, info = a
        self.assertAlmostEqual(info["be"], 60 + 2 * 140 * math.tan(math.radians(30)))
        col = info["col_en"]
        lam = 0.65 * 150 / (12 / math.sqrt(12)) / (math.pi * math.sqrt(210000 / 355))
        self.assertAlmostEqual(col["lam"], lam)


class TestWelds(unittest.TestCase):
    def test_simplified_method_sbe(self):
        # SBE Part 5 worked example 6.5 (column base weld): F_w,Rd = 410/√3/(0.85 x 1.25) x 0.7 x 8 = 1248 N/mm
        rows, info = J.weld(100, 0, 100, 5.6, 0, 0, "S275", fu=410)
        self.assertLess(rel(info["Fw_Rd"], 1248.0), 0.001)
        self.assertAlmostEqual(rows[2][2], info["Fw_Rd"])

    def test_directional_full_strength_ratios_sbe(self):
        # SBE Part 5 2.2.6: full-strength symmetric fillets of a plate in tension: a ≥ 0.46 t (S235), 0.48 t (S275)
        # (directional method, transverse T-joint). Plate yield force per mm = t f_y -> utilisation ≈ 1.0
        for gr, ratio in (("S235", 0.46), ("S275", 0.48)):
            t = 10.0
            rows, _ = J.weld(t * J.FYG[gr], 90, 1000, ratio * t, 0, 0, gr)
            self.assertAlmostEqual(rows[0][1] / rows[0][2], 1.0, delta=0.01)

    def test_transverse_closed_form(self):
        # Wald JRC 2014 'Fillet weld in normal shear' (closed form): σ⊥ = τ⊥ = F/(√2 a l) per weld,
        # √(σ⊥² + 3τ⊥²) = 2σ⊥ ≤ f_u/(βw γM2)
        rows, info = J.weld(250, 90, 200, 8, 0, 0, "S355")
        s = 250e3 / (2 * 200) / (8 * math.sqrt(2))
        self.assertAlmostEqual(info["sig_perp"], s)
        self.assertAlmostEqual(rows[0][1], 2 * s)

    def test_moment_on_weld_group_closed_form(self):
        # elastic line modulus: V∥ at lever arm e -> n_max = V e / (2 L²/6) on each weld line (statics)
        rows, info = J.weld(100, 0, 200, 5, 120, 0, "S355")
        n = 100e3 * 120 / (2 * 200 ** 2 / 6)
        self.assertAlmostEqual(info["sig_perp"], n / (5 * math.sqrt(2)))
        self.assertAlmostEqual(info["tau_par"], 100e3 / (2 * 200) / 5)


class TestTStubBasePlate(unittest.TestCase):
    def test_tstub_p398_column_flange(self):
        # SCI P398 Example C.1 sheets 4-5, bolt row 1, column flange: m = 33.4, e = 79.4, l_eff,cp = 210,
        # l_eff,nc = 233, t_f = 20.5, f_y = 265, ΣF_t,Rd = 406 kN, e_w = 39.55/4 -> F_T,1 = 898, F_T,2 = 398, F_T,3 = 406 kN
        le = J.leff_single_row(33.4, 79.4)
        self.assertLess(rel(le["cp"], 210.0), 0.002)
        self.assertLess(rel(le["nc"], 233.0), 0.002)
        T = J.tstub(le["leff1"], le["leff2"], 33.4, 75, 20.5, 265, 2 * 0.9 * 800 * 353 / 1.25, ew=39.55 / 4)
        self.assertLess(rel(T["F1"] / 1e3, 898.0), 0.002)
        self.assertLess(rel(T["F2"] / 1e3, 398.0), 0.002)
        self.assertLess(rel(T["F3"] / 1e3, 406.0), 0.002)

    def test_tstub_p398_end_plate_extension(self):
        # SCI P398 Example C.1 sheets 6-7, end plate extension: m_x = 30.4, e_x = 50, e = 75, w = 100, b_p = 250
        # -> l_eff,cp = 191, l_eff,nc = 125; t_p = 25: F_T,1 = 901, F_T,2 = 377 kN
        le = J.leff_extension(30.4, 50, 75, 100, 250)
        self.assertLess(rel(le["cp"], 191.0), 0.002)
        self.assertAlmostEqual(le["nc"], 125.0)
        T = J.tstub(le["leff1"], le["leff2"], 30.4, 75, 25, 265, 2 * 0.9 * 800 * 353 / 1.25, ew=39.55 / 4)
        self.assertLess(rel(T["F1"] / 1e3, 901.0), 0.002)
        self.assertLess(rel(T["F2"] / 1e3, 377.0), 0.002)

    def test_tstub_sbe_mode1_method2(self):
        # SBE Part 5 worked example 2.4 tying: Σl_eff = 430, t_p = 12, f_u = 430, γMu = 1.1, m = 59, n = 30,
        # e_w = 9.25 -> F_Rd,u,1 = 493 kN (Method 2). (Its Mode 2 '793 kN' is not reproduced: the same inputs give
        # (2 x 6.05 + 30 x 1.925)/(59 + 30) = 785 kN, an arithmetic slip in the publication.)
        T = J.tstub(430, 430, 59, 30, 12, 430, 12 * 0.9 * 800 * 245 / 1.1, ew=9.25, gM0=1.1)
        self.assertLess(rel(T["F1"] / 1e3, 493.0), 0.002)

    def _ns(self, **k):
        d = dict(col="I", D=0, tc=0, hc=200, bf=200, tfc=15, twc=9, B=340, H=340, tp=18, fy=235, fck=12, kj=2.5,
                 Nc=100.0, Nt=0.0, V=0.0, anchors=4, anchor_d=24, anchor_grade="8.8", edge=60, weld=6,
                 layout="sides", Lb=None, grout=30, washer=5)
        d.update(k)
        return types.SimpleNamespace(**d)

    def test_compression_wald_simple_base_plate(self):
        # Wald JRC 2014 'Worked example - simple base plate': HE 200 B on 340x340x18 S235, C12/15, foundation
        # 850x850 (k_j = 2.5): f_jd = 13.3 MPa, c = 43.7 mm, A_eff = 66 722 mm², N_Rd = 887 kN
        rows, info = J.baseplate(self._ns())
        self.assertLess(rel(info["fjd"], 13.33), 0.001)
        self.assertLess(rel(info["c"], 43.7), 0.003)
        self.assertLess(rel(info["Aeff"], 66722), 0.002)
        self.assertLess(rel(info["NcRd"], 887.0), 0.005)

    def test_compression_sbe_column_base(self):
        # SBE Part 5 worked example 6.5: C30/37, k_j = 1.5 -> f_jd = 20 MPa; t_p,min = c √(3 f_jd γM0/f_y) = 45 mm
        # for c = 93 mm and f_y = 255 (inverse: t_p = 45 -> c = 93 mm)
        rows, info = J.baseplate(self._ns(fck=30, kj=1.5, tp=45, fy=255, hc=320, bf=300, tfc=20.5, twc=11.5,
                                          B=600, H=600))
        self.assertAlmostEqual(info["fjd"], 20.0, delta=0.01)
        self.assertLess(rel(info["c"], 93.0), 0.003)

    def test_uplift_uses_tstub_and_prying_rule(self):
        # EN 1993-1-8 Table 6.2 / 6.2.6.12: L_b = 8d + grout + t_p + washer + h_nut/2; no prying if L_b > L_b*
        rows, info = J.baseplate(self._ns(col="CHS", D=168.3, tc=8, B=350, H=350, tp=25, fy=355, fck=30, kj=1.5,
                                          Nt=60, anchor_d=20, edge=55, layout="corners"))
        m, le = info["m"], info["leff"]
        self.assertAlmostEqual(info["Lb"], 8 * 20 + 30 + 25 + 5 + 0.4 * 20)
        self.assertAlmostEqual(info["Lb_star"], 8.8 * m ** 3 * 245 / (le["leff1"] * 25 ** 3))
        self.assertEqual(info["prying"], info["Lb"] <= info["Lb_star"])
        self.assertAlmostEqual(info["tstub"]["F12"], 2 * 0.25 * le["leff1"] * 25 ** 2 * 355 / m)


class TestAnchorsEN1992_4(unittest.TestCase):
    """Hilti PROFIS Engineering reports (EN 1992-4 design method), published on ask.hilti.com:
    H1 = https://files-ask.hilti.com/original/cf/cfip8ziqve.pdf  (cast-in headed 5.8 M16, h_ef 120, C20/25 cracked)
    H2 = https://files-ask.hilti.com/original/62/62zrajuzqr.pdf  (2 anchors near a narrow, thin member edge)
    H3 = https://files-ask.hilti.com/original/x0/x0w2kzspbz.pdf  (M20 8.8, stand-off 16 mm, plate 16 mm)
    H4 = https://files-ask.hilti.com/original/jh/jhtmzriaax.pdf  (splitting, M20, h_ef 200, C30/37)"""

    def test_cone_and_pryout_headed_H1(self):
        # H1 4.3: A_c,N = 257 050, A0 = 129 600, ψs,N = 0.950, N0 = 52.321 kN, k8 = 2, V_Rd,cp = 131.447 kN
        c = J.cone_NRk(8.9, 20, 120, 2, 2, 200, 125, None, 150, 200, 500)
        self.assertAlmostEqual(c["Ac"], 257050.0)
        self.assertAlmostEqual(c["A0"], 129600.0)
        self.assertAlmostEqual(c["psi_s"], 0.95)
        self.assertLess(rel(c["N0"], 52.321), 0.0005)
        rows, info = J.anchor_group(2, 2, 200, 125, None, 200, 120, 16, 30, "5.6", 20, 0.0, c1b=150, c2b=500,
                                    V=15.0, cv=150, cv2a=200, cv2b=500, h=175)
        pry = [r for r in rows if r[0].startswith("pry-out")][0]
        self.assertLess(rel(pry[2], 131.447), 0.0005)

    def test_edge_failure_headed_H1(self):
        # H1 4.4: c1 = 150, c2 = 200/500, s2 = 125, h = 175, d_nom = 16, l_f = 120: α = 0.089, β = 0.064,
        # V0 = 24.305 kN, A_c,V = 96 250, A0 = 101 250, ψs,V = 0.967, ψh,V = 1.134; V_Rd,c = 15.244 kN includes
        # Hilti's grout factor ψb,g = 0.903 (not EN 1992-4) -> EN value 15.244/0.903
        e = J.edge_VRk(150, 200, 500, 2, 125, 175, 16, 120, 20, cracked=True)
        self.assertAlmostEqual(e["alpha"], 0.089, places=3)
        self.assertAlmostEqual(e["beta"], 0.064, places=3)
        self.assertLess(rel(e["V0"], 24.305), 0.001)
        self.assertAlmostEqual(e["Ac"], 96250.0)
        self.assertAlmostEqual(e["A0"], 101250.0)
        self.assertAlmostEqual(e["psi_s"], 0.967, places=3)
        self.assertAlmostEqual(e["psi_h"], 1.134, places=3)
        self.assertLess(rel(e["VRk"] / 1.5, 15.244 / 0.903), 0.002)

    def test_steel_shear_headed_H1(self):
        # H1 4.1: V0_Rk,s = 52.276 kN = k6 A f_uk with k6 = 0.5 (f_uk = 520 > 500), A = 201 mm² (shank), k7 = 1
        st = J.steel_shear(math.pi * 16 ** 2 / 4, 520, 420)
        self.assertEqual(st["k6"], 0.5)
        self.assertLess(rel(st["VRk"], 52.276), 0.0005)

    def test_edge_narrow_thin_member_H2(self):
        # H2 4.3: c1 = 650 but c2,max = 600 ≤ 1.5c1 and h = 300 ≤ 1.5c1 -> c1' = max(600/1.5, 300/1.5, 100/3) = 400;
        # α = 0.041, β = 0.051, A_c,V = 390 000, A0 = 720 000, ψh,V = 1.414, V0 = 84.257 -> V_Rd,c = 43.029 kN
        e = J.edge_VRk(650, 600, 600, 2, 100, 300, 14, 68.8, 20, cracked=True)
        self.assertAlmostEqual(e["c1"], 400.0)
        self.assertAlmostEqual(e["alpha"], 0.041, places=3)
        self.assertAlmostEqual(e["beta"], 0.051, places=3)
        self.assertAlmostEqual(e["Ac"], 390000.0)
        self.assertAlmostEqual(e["A0"], 720000.0)
        self.assertAlmostEqual(e["psi_h"], 1.414, places=3)
        self.assertLess(rel(e["V0"], 84.257), 0.001)
        self.assertLess(rel(e["VRk"] / 1.5, 43.029), 0.001)

    def test_pryout_and_interaction_H2(self):
        # H2 4.2: k1 = 7.7 (ETA), N0 = 19.673, k8 = 2 -> V_Rd,cp = 38.929 kN (A_c,N 63 318 with h_ef,ETA rounding)
        c = J.cone_NRk(7.7, 20, 68.8, 1, 2, 0, 100, 650, 650, 600, 600)
        self.assertLess(rel(c["N0"], 19.673), 0.002)
        self.assertLess(rel(2 * c["NRk"] / 1.5, 38.929), 0.002)
        # H2 5: concrete βN = 9.585/12.393, βV = 13.840/38.929, exponent 1.5 -> 0.892 (report prints 90 %, rounded up);
        # steel βN = 0.142, βV = 0.174, exponent 2 -> 0.050 (prints 6 %)
        i_s, i_c = J.interaction(9.585 / 67.667, 6.920 / 39.680, 9.585 / 12.393, 13.840 / 38.929)
        self.assertAlmostEqual(i_c, 0.892, places=3)
        self.assertTrue(0.89 < i_c <= 0.90)
        self.assertTrue(0.05 < i_s <= 0.06)

    def test_lever_arm_H3(self):
        # H3 4.2: l_a = e_c + t/2 + a3 = 16 + 8 + 10 = 34 mm, αM = 2, M0_Rk,s = 0.519 kNm, V_Rk,s,M = 30.529 kN,
        # γMs = 1.25 -> V_Rd,s,M = 24.424 kN
        sl = J.steel_shear_lever(245, 800, 640, 20, 16 + 16 / 2)
        self.assertAlmostEqual(sl["la"], 34.0)
        self.assertLess(rel(sl["M0"], 0.519), 0.002)
        self.assertLess(rel(sl["VRk"], 30.529), 0.002)
        self.assertAlmostEqual(sl["gMs"], 1.25)
        self.assertLess(rel(sl["VRk"] / sl["gMs"], 24.424), 0.002)

    def test_splitting_H4(self):
        # H4 3.4: N0_Rk,sp = 111.234, c_cr,sp = 200, s_cr,sp = 400, h = 400, h_min = 244, edges c = 100/150 (x),
        # 500 (y), e_N = 2.1 mm: A_c,N = 180 000, A0 = 160 000, ψs,N = 0.850, ψec = 0.990, ψh,sp = 1.272,
        # N_Rd,sp = 89.274 kN
        sp = J.splitting_NRk(111.234, 200, 2, 1, 200, 0, 100, 150, 700, 500, 200, 400, 244, eN1=2.1)
        self.assertAlmostEqual(sp["Ac"], 180000.0)
        self.assertAlmostEqual(sp["A0"], 160000.0)
        self.assertAlmostEqual(sp["psi_s"], 0.85)
        self.assertAlmostEqual(sp["psi_ec"], 0.990, places=3)
        self.assertAlmostEqual(sp["psi_h"], 1.272, places=3)
        self.assertLess(rel(sp["NRk"] / 1.5, 89.274), 0.001)

    def test_factor_values_match_standard_extract(self):
        # EN 1992-4:2018 7.2.2.5 extract (files-ask.hilti.com/original/29/29oep37chq.pdf): k9 = 1.7 / 2.4,
        # A0_c,V = 4.5 c1², ψre,V = 1.4 with edge reinforcement
        self.assertEqual(CF.get("anchor_EN1992_4.k9_cracked"), 1.7)
        self.assertEqual(CF.get("anchor_EN1992_4.k9_uncracked"), 2.4)
        self.assertEqual(CF.get("anchor_EN1992_4.A0cV_per_c1sq"), 4.5)
        self.assertEqual(CF.get("anchor_EN1992_4.psi_re_V_edge_reinf"), 1.4)
        e = J.edge_VRk(100, None, None, 1, 0, None, 16, 100, 25, alpha_deg=90.0)
        self.assertAlmostEqual(e["psi_a"], 2.0)          # Eq. (7.48): 1/√(0 + 0.25) at α = 90°
        e = J.edge_VRk(100, None, None, 1, 0, None, 16, 100, 25, eV=150.0)
        self.assertAlmostEqual(e["psi_ec"], 0.5)          # Eq. (7.47): 1/(1 + 2·150/300)

    def test_cli_rows_order_backward_compatible(self):
        rows, info = J.anchor_group(1, 1, 0, 0, 1000, 1000, 200, 20, 38, "8.8", 30, 50.0, cracked=True)
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[0][0].startswith("steel") and rows[2][0].startswith("concrete cone"))


class TestAluminiumBearing(unittest.TestCase):
    def test_en1999_table_8_5(self):
        # EN 1999-1-1:2007+A1:2009 Table 8.5 Eq. (8.11)-(8.16): F_b,Rd = k1 αb f_u d t/γM2, αb = min(e1/3d0, f_ub/f_u, 1), k1 = min(2.8 e2/d0 - 1.7, 2.5).
        # Hand calc M10 A4-70 in 6082-T6 t = 6 (f_u = 310), d0 = 11, e1 = 30, e2 = 15:
        # αb = min(30/33, 700/310, 1) = 0.909, k1 = min(2.8x15/11 - 1.7, 2.5) = 2.118, F_b = 28.65 kN
        k1, ab = J.bearing_k1_ab(11, 700, 310, 30, 15, 0, 0)
        self.assertAlmostEqual(ab, 30 / 33)
        self.assertAlmostEqual(k1, 2.8 * 15 / 11 - 1.7)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            J.main(["clampbar", "--n", "12", "--spacing", "150", "--d", "10", "--t", "6", "--plate", "alu6082"])
        self.assertIn("28.65", out.getvalue())
        self.assertEqual(CF.status("aluminium.bearing_formula"), "V")
        self.assertEqual(CF.get("aluminium.alpha_v_stainless_bolt"), 0.5)


class TestFatigue(unittest.TestCase):
    def test_curve_constants_en1993_1_9(self):
        # EN 1993-1-9 7.1: Δσ_D = (2/5)^(1/3) Δσ_C at 5e6, Δσ_L = (5/100)^(1/5) Δσ_D at 1e8, Δτ_L = 0.457 Δτ_C
        self.assertAlmostEqual(CF.get("fatigue_EN1993_1_9.D_over_C"), (2 / 5) ** (1 / 3), places=3)
        self.assertAlmostEqual(CF.get("fatigue_EN1993_1_9.L_over_C") / CF.get("fatigue_EN1993_1_9.D_over_C"),
                               (5 / 100) ** (1 / 5), places=3)
        self.assertAlmostEqual(CF.get("fatigue_EN1993_1_9.tauL_over_C"), (2 / 100) ** (1 / 5), places=3)
        self.assertLess(rel(FAT.cycles_steel(0.737 * 100 + 1e-9, 100), 5e6), 0.001)   # knee at 5e6 (0.737 rounded)
        self.assertLess(rel(FAT.cycles_steel(0.4051 * 100, 100), 1e8), 0.01)          # cut-off at 1e8
        self.assertEqual(FAT.cycles_steel(0.40 * 100, 100), math.inf)
        self.assertLess(rel(FAT.cycles_shear(0.4571 * 80, 80), 1e8), 0.01)

    def test_miner_idea_statica_example(self):
        # IDEA StatiCa 'Fatigue analysis according to EN 1993-1-9',
        # https://www.ideastatica.com/support-center/fatigue-analysis-according-to-en-1993-1-9: Δσ_C = 90, Δτ_C = 70,
        # γMf = 1.15, γFf = 1.0; spectrum (60/60 MPa, 1.5e6), (50/40, 3e6), (20/10, 1e7):
        # N_R,σ = 4 438 235 / 10 200 230 / inf -> D_σ = 0.632; N_R,τ = 2 149 190 / 16 320 409 / inf -> D_τ = 0.882
        D, rows = FAT.check([(60, 1.5e6), (50, 3e6), (20, 1e7)], 90, 1.15)
        self.assertLess(rel(rows[0][2], 4438235), 0.002)
        self.assertLess(rel(rows[1][2], 10200230), 0.002)
        self.assertEqual(rows[2][2], math.inf)
        self.assertAlmostEqual(D, 0.632, places=3)
        Dt, rows = FAT.check_shear([(60, 1.5e6), (40, 3e6), (10, 1e7)], 70, 1.15)
        self.assertLess(rel(rows[0][2], 2149190), 0.001)
        self.assertLess(rel(rows[1][2], 16320409), 0.001)
        self.assertAlmostEqual(Dt, 0.882, places=3)
        # Eq. (8.3) with the Annex A.6 equivalent ranges reduces to D_σ + D_τ (IDEA prints 0.786 = D_σ³ + D_τ⁵, a
        # different reading of 8.3; this tool keeps the damage-sum form)
        self.assertAlmostEqual(FAT.combined(D, Dt), D + Dt)

    def test_cable_bilinear_curve_en1993_1_11(self):
        # EN 1993-1-11 Fig. 9.1 (register fatigue_cables, verified by the cable-tension-members agent): slope 4 down to
        # Δσ_C at 2e6, slope 6 beyond, no cut-off. Closed form: N(Δσ_C) = 2e6; N(0.5 Δσ_C) = 2e6·2^6; above the knee
        # N(2 Δσ_C) = 2e6/2^4; the single-slope variant (--single-slope) gives 2e6·2^4 below the knee.
        dsC = 150.0
        self.assertAlmostEqual(FAT.cycles_bilinear(dsC, dsC, 4, 6), 2e6)
        self.assertAlmostEqual(FAT.cycles_bilinear(dsC / 2, dsC, 4, 6), 2e6 * 2 ** 6)
        self.assertAlmostEqual(FAT.cycles_bilinear(2 * dsC, dsC, 4, 6), 2e6 / 2 ** 4)
        D, _ = FAT.check([(dsC / 2 / 1.35, 1e7)], dsC, 1.35, 1.0, 4, 6)
        self.assertAlmostEqual(D, 1e7 / (2e6 * 2 ** 6))
        D1, _ = FAT.check([(dsC / 2 / 1.35, 1e7)], dsC, 1.35, 1.0, 4)
        self.assertAlmostEqual(D1, 1e7 / (2e6 * 2 ** 4))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            Db = FAT.main(["--cable", "spiral_socket", "--spectrum", "40:2e6", "--spectrum", "20:1e7"])
            Ds = FAT.main(["--cable", "spiral_socket", "--spectrum", "40:2e6", "--spectrum", "20:1e7", "--single-slope"])
        self.assertLess(Db, Ds)
        self.assertIn("m2 = 6", out.getvalue())

    def test_cli_shear_and_combined(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            c = FAT.main(["--category", "90", "--spectrum", "60:1.5e6", "--spectrum", "50:3e6",
                          "--shear-category", "70", "--shear-spectrum", "60:1.5e6", "--shear-spectrum", "40:3e6",
                          "--method", "damage-tolerant", "--consequence", "high"])
        self.assertAlmostEqual(c, 0.632 + 0.882, places=2)
        self.assertIn("Assumptions", out.getvalue())


class TestCornerPlateStatics(unittest.TestCase):
    """Closed-form statics (law of cosines / sines, moment r x F, vector cross product)."""

    def test_symmetric_and_general_2d(self):
        r = CP.resolve2d([("a", 0.0, 100.0), ("b", 60.0, 100.0)])
        self.assertAlmostEqual(r["R"], 2 * 100 * math.cos(math.radians(30)))          # R = 2T cos(θ/2) = 173.2
        self.assertAlmostEqual(r["anchor_angle"], 30.0 - 180.0)
        self.assertAlmostEqual(r["deviation"], 0.0, places=9)
        # general: T1 = 48 at 15°, T2 = 52 at 105° (θ = 90°): R = √(48² + 52² + 2·48·52·cos 90°) = 70.77 kN,
        # direction 15° + atan(52/48) (law of sines with a right angle)
        r = CP.resolve2d([("EC1", 15.0, 48.0), ("EC2", 105.0, 52.0)])
        self.assertAlmostEqual(r["R"], math.sqrt(48 ** 2 + 52 ** 2))
        self.assertAlmostEqual(math.degrees(math.atan2(r["Ry"], r["Rx"])), 15 + math.degrees(math.atan2(52, 48)))
        self.assertAlmostEqual(r["opening"], 90.0)

    def test_moment_and_eccentricity(self):
        # hand calc: 10 kN along +x through the hole (0, 50) -> M = x·Fy - y·Fx = -500 kN·mm; a 10 kN pull along
        # +y through (0, 0) adds nothing; R = 14.14 kN -> e = M/R = -35.36 mm
        r = CP.resolve2d([("a", 0.0, 10.0, 0.0, 50.0), ("b", 90.0, 10.0, 0.0, 0.0)])
        self.assertAlmostEqual(r["M"], -500.0)
        self.assertAlmostEqual(r["e"], -500.0 / math.sqrt(200))
        # concurrent layout: each hole on its own line of action through the pin -> M = 0
        r = CP.resolve2d([("a", 30.0, 40.0, 100 * math.cos(math.radians(30)), 100 * math.sin(math.radians(30))),
                          ("b", 120.0, 25.0, 80 * math.cos(math.radians(120)), 80 * math.sin(math.radians(120)))])
        self.assertAlmostEqual(r["M"], 0.0, places=9)

    def test_3d_plane_and_out_of_plane(self):
        # cables along x and y (10 kN each), strap toward (1, 1, -1) with 2√3 kN: plate normal (0, 0, 1),
        # strap out-of-plane component -2 kN, resultant (12, 12, -2) -> R = √292, anchor tilt asin(2/√292)
        r = CP.resolve3d([("x", [5, 0, 0], 10.0), ("y", [0, 7, 0], 10.0), ("s", [1, 1, -1], 2 * math.sqrt(3))])
        self.assertAlmostEqual(r["n"][2], 1.0)
        self.assertAlmostEqual(r["oop"][2], -2.0)
        self.assertAlmostEqual(r["R"], math.sqrt(292))
        self.assertAlmostEqual(r["tilt_deg"], math.degrees(math.asin(2 / math.sqrt(292))))
        self.assertAlmostEqual(r["opening"], 90.0)


class TestPinWorkedExample(unittest.TestCase):
    def test_en_hand_example(self):
        # hand calculation per EN 1993-1-8 Tables 3.9/3.10 in reference/cable-steel-connections.md §1.3:
        # pin shear 483 kN, bearing 426 kN, M_Ed 1.81 kNm, M_Rd 6.03 kNm, a ≥ 44.9, c ≥ 31.3, F_b,Rd,ser 170.4, σ_h 624
        rows = {r[0]: r for r in PIN.en1993(250, 170, 40, 41, 20, 50, 35, 355, 490, 640, 800, 15, 2, True)}
        self.assertAlmostEqual(rows["Pin shear per plane [kN]"][2], 482.5, delta=0.5)
        self.assertAlmostEqual(rows["Bearing ULS, lug plate [kN]"][2], 426.0, delta=0.05)
        self.assertAlmostEqual(rows["Pin bending [kNm]"][1], 1.81, delta=0.005)
        self.assertAlmostEqual(rows["Pin bending [kNm]"][2], 6.03, delta=0.005)
        self.assertAlmostEqual(rows["Lug end distance a (beyond hole, in line of force) [mm]"][1], 44.9, delta=0.05)
        self.assertAlmostEqual(rows["Lug side distance c (beside hole) [mm]"][1], 31.3, delta=0.05)
        self.assertAlmostEqual(rows["Bearing SLS (replaceable pin), lug plate [kN]"][2], 170.4, delta=0.05)
        self.assertAlmostEqual(rows["Contact stress sigma_h,Ed (lug) [MPa]"][1], 624.0, delta=0.5)

    def test_aisc_geometry(self):
        # AISC 360 D5: b_eff = 2t + 16 mm = 56 mm (t = 20) -> a ≥ 1.33 b_eff = 74.5 mm, w ≥ 2 b_eff + d = 152 mm
        rows = {r[0]: r for r in PIN.aisc(250, 40, 41, 20, 80, 160, 355, 490)}
        self.assertAlmostEqual(rows["D5.2 a >= 1.33 beff [mm]"][1], 74.48, places=2)
        self.assertAlmostEqual(rows["D5.2 w >= 2 beff + d [mm]"][1], 152.0)

    def test_cheek_sls_share_when_cheek_equals_lug(self):
        # regression: the SLS bearing share of a cheek is F_ser/2 also when fork_t == t (was F_ser)
        rows = {r[0]: r for r in PIN.en1993(250, 170, 40, 41, 20, 50, 35, 355, 490, 640, 800, 20, 2, True)}
        self.assertAlmostEqual(rows["Bearing SLS (replaceable pin), fork cheek (each) [kN]"][1], 85.0)
        self.assertAlmostEqual(rows["Bearing SLS (replaceable pin), lug plate [kN]"][1], 170.0)


def _pin(F, d, t, a, c, fy, fyp, fup, gM0=1.0, gM2=1.0, Fser=None, d0=None, replaceable=False):
    """EN 1993-1-8 pin rows keyed by name (lug = middle plate b = t, cheeks a, gap c)."""
    rows = PIN.en1993(F, F if Fser is None else Fser, d, d + 1 if d0 is None else d0, t, 1e3, 1e3, fy, 510,
                      fyp, fup, a, c, replaceable, gM0=gM0, gM2=gM2)
    return {r[0]: r for r in rows}


class TestPinPublishedEN(unittest.TestCase):
    """EN 1993-1-8 §3.13 Table 3.10 against published calculations.
    CONDE = J. Conde, L. S. da Silva, T. Tankova, R. Simões, T. Abecasis, 'Design of pin connections between steel
    members', J. Constr. Steel Res. 201 (2023) 107752, open access https://oa.upm.es/85661/ (§3 counterexample,
    Tables 2-4). LBV = Landesamt für Bauen und Verkehr Brandenburg, Bautechnisches Prüfamt, Tipp 22/05
    'Bemessungswerte für Bolzenverbindungen nach DIN EN 1993-1-8', https://lbv.brandenburg.de/sixcms/media.php/9/bautechnik_Tipp_22-05.pdf."""

    def test_conde_counterexample(self):
        # CONDE §3: S355 (f_y 355, f_u 510), d = 16, a = 8, b = 12, c = 5: F_v,Rd = 49.2 kN per plane,
        # M_Rd = 1.5 W_el f_yp/γM0 = 214 kN·mm, F_Rd,pin = 8 M_Rd/(b + 4c + 2a) = 35.7 kN
        r = _pin(35.7, 16, 12, 8, 5, 355, 355, 510, gM2=1.25)
        self.assertLess(rel(r["Pin shear per plane [kN]"][2], 49.2), 0.002)
        self.assertLess(rel(r["Pin bending [kNm]"][2] * 1e3, 214.0), 0.002)
        self.assertLess(abs(r["Pin bending [kNm]"][3] - 1.0), 0.002)             # F = 35.7 kN exhausts M_Rd

    def _proto(self, d, fyp, fup, gM2=1.0):
        # CONDE Tables 2-3 (measured): two 10.1 mm lugs (cheeks, f_y 395.27), middle plate b = 15, gap c = 2
        # (Fig. 5); lever b + 4c + 2a = 43.2 mm; f_y for bearing = min(pin, plate)
        return lambda F: _pin(F, d, 15, 10.1, 2, 395.27, fyp, fup, gM2=gM2)

    def _published(self, pin, Fv, Fb, FM, FMV):
        r = pin(100.0)
        self.assertLess(rel(2 * r["Pin shear per plane [kN]"][2], Fv), 0.005)            # 2 shear planes
        self.assertLess(rel(2 * r["Bearing ULS, fork cheek (each) [kN]"][2], Fb), 0.005)  # 2 × 10.1 mm lugs
        self.assertLess(rel(100.0 / r["Pin bending [kNm]"][3], FM), 0.006)               # F at M_Ed = M_Rd
        F = FMV
        for _ in range(30):                                                           # F at interaction = 1
            F /= math.sqrt(pin(F)["Pin shear + bending interaction [-]"][3])
        self.assertLess(rel(F, FMV), 0.006)

    def test_conde_prototype1_table4(self):
        # P1: pin 35.8 mm (CK45, f_y 321.16, f_u 670.84), γ = 1: F_v,Rd 808.1, F_b,Rd 347.9, F(M_Rd) 399.9,
        # F(M_Rd, F_v,Rd) 358.4 kN
        self._published(self._proto(35.8, 321.16, 670.84), 808.1, 347.9, 399.9, 358.4)

    def test_conde_prototype2_table4(self):
        # P2: pin 19.8 mm (f_y 457.06, f_u 777.65), γ = 1: 286.8 / 237.4 / 96.4 / 91.4 kN; γ code (γM2 1.25):
        # F_v,Rd 229.4, F(M_Rd, F_v,Rd) 88.9 kN
        self._published(self._proto(19.8, 457.06, 777.65), 286.8, 237.4, 96.4, 91.4)
        pin = self._proto(19.8, 457.06, 777.65, gM2=1.25)
        self.assertLess(rel(2 * pin(100.0)["Pin shear per plane [kN]"][2], 229.4), 0.005)
        F = 88.9
        for _ in range(30):
            F /= math.sqrt(pin(F)["Pin shear + bending interaction [-]"][3])
        self.assertLess(rel(F, 88.9), 0.006)

    def test_brandenburg_tipp_22_05_design_values(self):
        # LBV Tipp 22/05 charts (γM2 1.25, γM0 1.0): F_v,Rd [kN] d16/f_up490 47.29, d20/490 73.89, d24/490 106.40,
        # d20/360 54.29, d24/360 78.17; F_b,Rd/t [kN/mm] d24/f_y355 12.78, d20/355 10.65, d24/235 8.46;
        # M_Rd [kNm] d24/f_yp355 0.723, d20/355 0.418, d24/235 0.478
        for d, fup, v in ((16, 490, 47.29), (20, 490, 73.89), (24, 490, 106.40), (20, 360, 54.29), (24, 360, 78.17)):
            self.assertAlmostEqual(_pin(10, d, 1, 1, 0, 355, 355, fup, gM2=1.25)["Pin shear per plane [kN]"][2], v,
                                   delta=0.006)
        for d, fy, v in ((24, 355, 12.78), (20, 355, 10.65), (24, 235, 8.46)):
            self.assertAlmostEqual(_pin(10, d, 1, 1, 0, fy, 640, 800)["Bearing ULS, lug plate [kN]"][2], v,
                                   delta=0.006)
        for d, fyp, v in ((24, 355, 0.723), (20, 355, 0.418), (24, 235, 0.478)):
            self.assertAlmostEqual(_pin(10, d, 1, 1, 0, 355, fyp, 510)["Pin bending [kNm]"][2], v, delta=0.0006)

    def test_contact_stress_is_hertz_line_contact(self):
        # Eq. (3.15) constant 0.591 = 1/sqrt(π(1 - ν²)), ν = 0.3: Hertz line contact of a cylinder in a conforming
        # hole p0 = sqrt(P'E*/(πR)) with E* = E/(2(1 - ν²)), 1/R = 2/d - 2/d0 (K. L. Johnson, Contact Mechanics,
        # CUP 1985, §4.2) and d·d0 ≈ d²
        self.assertAlmostEqual(1 / math.sqrt(math.pi * (1 - 0.3 ** 2)), 0.591, places=3)
        E, F, d, d0, t = 210000.0, 170e3, 40.0, 41.0, 20.0
        Estar, R = E / (2 * (1 - 0.3 ** 2)), 1 / (2 / d - 2 / d0)
        p0 = math.sqrt(F / t * Estar / (math.pi * R)) * math.sqrt(d0 / d)          # d·d0 -> d²
        self.assertLess(rel(PIN.contact_stress(F, d, d0, t, E), p0), 0.001)
        # F_b,Ed,ser per plate: cheeks carry F_ser/2; f_h,Rd = 2.5 min(f_y, f_yp)/γM6,ser
        r = {x[0]: x for x in PIN.en1993(250, 170, 40, 41, 20, 50, 35, 355, 490, 300, 400, 15, 2, True)}
        self.assertAlmostEqual(r["Contact stress sigma_h,Ed (fork cheek) [MPa]"][1],
                               PIN.contact_stress(85e3, 40, 41, 15, CF.get("steel.E")), places=6)
        self.assertAlmostEqual(r["Contact stress sigma_h,Ed (lug) [MPa]"][2], 2.5 * 300 / CF.get("steel.gM6ser"))


class TestPinPublishedAISC(unittest.TestCase):
    """AISC Design Examples v15.1 (Companion to the AISC Steel Construction Manual, Vol. 1),
    https://www.aisc.org/media/q5fcgxxu/v151_vol-1_design-examples.pdf, Examples D.7 and D.8 (printed values as
    reproduced in the University of Mustansiriyah lecture notes 'Pin-connected members' / 'Eye bars member',
    https://uomustansiriyah.edu.iq/media/lectures/5/5_2021_03_15!03_29_38_PM.pdf and ...03_30_02_PM.pdf)."""

    def test_D7_pin_connected_tension_member(self):
        # A36 (F_y 36, F_u 58 ksi), t = 1/2, w = 4.25, d = 1, d_h = 1 1/32, a = 2.25 in; P_u 20.8 / P_a 16.0 kips.
        # b = (4.25 - 1.03)/2 = 1.61 < 2t + 0.63 = 1.63 -> b_eff = 1.61 in; LRFD φP_n: rupture 70.0, shear 71.8,
        # bearing 24.3 (governs), yielding 68.9 kips; ASD P_n/Ω: 46.7, 47.9, 16.2, 45.8 kips
        args = (1.0 * IN, (1 + 1 / 32) * IN, 0.5 * IN, 2.25 * IN, 4.25 * IN, 36 * KSI, 58 * KSI)
        for method, Pr, pub in (("LRFD", 20.8, (70.0, 71.8, 24.3, 68.9)), ("ASD", 16.0, (46.7, 47.9, 16.2, 45.8))):
            rows = PIN.aisc(Pr * KIP / 1e3, *args, method=method)
            for r, v in zip(rows[:4], pub):
                self.assertLess(rel(r[2] * 1e3 / KIP, v), 0.004, (method, r[0]))
            gov = min(rows[:4], key=lambda r: r[2])
            self.assertTrue(gov[0].startswith("J7"))                                 # bearing governs
            self.assertLess(gov[3], 1.0)                                             # 24.3 > 20.8, 16.2 > 16.0
        rows = {r[0]: r for r in PIN.aisc(92.5, *args)}
        self.assertLess(rel(rows["D5.2 a >= 1.33 beff [mm]"][1] / IN, 1.33 * 1.61), 0.002)     # 2.14 in
        self.assertLess(rel(rows["D5.2 w >= 2 beff + d [mm]"][1] / IN, 2 * 1.61 + 1.0), 0.002)  # 4.22 in

    def test_D8_eyebar(self):
        # A36, t = 5/8, w = 3.00, b = 2.23, d = 3.00, d_h = 3 1/32, R = 8.00 in; P_u 54.0 / P_a 40.0 kips.
        # A_g = 3.00 × 0.625 = 1.875 in², P_n = 67.5 kips: φP_n = 60.8 kips, P_n/Ω = 40.4 kips (governs, 0.99)
        args = (3.0 * IN, (3 + 1 / 32) * IN, 0.625 * IN, 3.0 * IN, 2.23 * IN, 8.0 * IN, 36 * KSI)
        for method, Pr, pub in (("LRFD", 54.0, 60.75), ("ASD", 40.0, 40.42)):
            rows = PIN.aisc_eyebar(Pr * KIP / 1e3, *args, method=method)
            self.assertLess(rel(rows[0][2] * 1e3 / KIP, pub), 0.002, method)
            self.assertTrue(all(r[3] <= 1.0 for r in rows), method)                  # all D6.2 proportions met
        rows = {r[0]: r for r in PIN.aisc_eyebar(240, *args)}
        self.assertLess(rel(rows["D6.2 transition radius R >= head diameter d0 + 2b [mm]"][1] / IN, 7.49), 0.002)
        self.assertAlmostEqual(rows["D6.2 pin d >= 7/8 w [mm]"][1] / IN, 2.625)
        self.assertAlmostEqual(rows["D6.2 b >= 2/3 w [mm]"][1] / IN, 2.0, places=3)


# SCI P358 (2011) Table G.33, column bases for CHS 273 (lightest section of the range; t = 5.0 mm is fixed by the
# 4-figure value 1376 kN quoted in Example 4), S275 plates: (plate B = H, t_p, [N_Rd for C16 C20 C25 C30 C35] kN)
P358_G33_CHS273 = [
    (400, 20, [991, 1110, 1250, 1380, 1490]), (400, 25, [1170, 1360, 1550, 1700, 1840]),
    (400, 30, [1300, 1530, 1790, 2010, 2200]), (400, 35, [1380, 1660, 1960, 2230, 2480]),
    (400, 40, [1430, 1740, 2090, 2400, 2690]), (450, 25, [1230, 1380, 1550, 1700, 1840]),
    (450, 30, [1460, 1650, 1850, 2030, 2200]), (450, 35, [1610, 1880, 2140, 2350, 2550]),
    (450, 40, [1710, 2030, 2380, 2670, 2900]), (450, 45, [1760, 2120, 2520, 2870, 3170]),
    (500, 25, [1230, 1380, 1550, 1700, 1840]), (500, 30, [1470, 1650, 1850, 2030, 2200]),
    (500, 40, [1900, 2180, 2440, 2680, 2900]), (500, 50, [2100, 2500, 2930, 3270, 3540]),
    (500, 60, [2220, 2700, 3230, 3710, 4150]), (600, 30, [1470, 1650, 1850, 2030, 2200]),
    (600, 40, [1940, 2180, 2440, 2680, 2900]), (600, 50, [2390, 2660, 2980, 3270, 3540]),
    (600, 60, [2810, 3220, 3570, 3910, 4230]), (600, 70, [3020, 3560, 4110, 4490, 4830]),
    (700, 40, [1940, 2180, 2440, 2680, 2900]), (700, 50, [2390, 2660, 2980, 3270, 3540]),
    (700, 60, [2920, 3220, 3570, 3910, 4230]), (700, 70, [3420, 3750, 4130, 4490, 4830])]


class TestCHSBasePlateP358(unittest.TestCase):
    """SCI P358 'Joints in steel construction: Simple joints to Eurocode 3' (2011),
    https://www.steelconstruction.info/images/a/a9/SCI_P358.pdf: §7.5 Check 2 (CHS effective area π(d - t)(t + 2c),
    0.25π(d + 2c)² with overlap), Example 4 'Column base - CHS', Table G.33 (CHS bases), §6.8 and Example 5 'CHS
    tension splice' (ring-flange rules after the CIDECT design guide). UK NA: α_cc = 0.85, f_jd = β_j α f_cd with
    α = 1.5; S275 f_y = 275 / 265 / 255 / 245 MPa for t ≤ 16 / 40 / 63 / 80 mm (EN 10025-2)."""

    @staticmethod
    def _ns(**k):
        d = dict(col="CHS", D=273.0, tc=5.0, hc=0, bf=0, tfc=0, twc=0, B=400, H=400, tp=20, fy=265, fck=30, kj=1.5,
                 alpha_cc=0.85, Nc=1.0, Nt=0.0, V=0.0, anchors=8, anchor_d=24, anchor_grade="8.8", edge=50,
                 weld=6, layout="ring", Lb=None, grout=30, washer=5)
        d.update(k)
        return types.SimpleNamespace(**d)

    @staticmethod
    def _fy(tp):
        return 275 if tp <= 16 else 265 if tp <= 40 else 255 if tp <= 63 else 245

    def test_example4_column_base_chs(self):
        # Example 4: C30, f_jd = 1.5 × 2/3 × 0.85 × 30/1.5 = 17 N/mm²; Table G.33 (273 lightest, 400×400×20)
        # 'Resistance given in the tables is 1376 kN'
        rows, info = J.baseplate(self._ns())
        self.assertAlmostEqual(info["fjd"], 17.0, places=6)
        self.assertLess(rel(info["NcRd"], 1376.0), 0.001)
        # 273×10 detailed check: A_req = 1400e3/17 -> c = 45 mm; t_p,min = c √(3 f_jd γM0/f_y) = 20 mm (265 MPa)
        Areq = 1400e3 / 17.0
        c = (Areq / (math.pi * (273 - 10)) - 10) / 2
        self.assertAlmostEqual(c, 45.0, delta=0.2)
        rows, info = J.baseplate(self._ns(tc=10.0, tp=c * math.sqrt(3 * 17.0 / 265)))
        self.assertLess(rel(info["NcRd"], 1400.0), 1e-9)                         # inverse of the P358 steps
        self.assertEqual(math.ceil(c * math.sqrt(3 * 17.0 / 265)), 20)             # 'tp,min = 20 mm' (19.7)
        rows, info = J.baseplate(self._ns(tc=10.0, tp=20))
        self.assertGreaterEqual(info["NcRd"], 1400.0)                              # tp = 20 mm ≥ 20 mm O.K.

    def test_table_G33_chs273_all_120_values(self):
        # covers no clipping, the annulus cut by the plate edges (42 values) and the inner overlap (29 values);
        # the former radius-clip model was up to 20 % low on this set
        worst = 0.0
        for B, tp, vals in P358_G33_CHS273:
            for fck, v in zip((16, 20, 25, 30, 35), vals):
                rows, info = J.baseplate(self._ns(B=B, H=B, tp=tp, fy=self._fy(tp), fck=fck))
                worst = max(worst, rel(info["NcRd"], v))
        self.assertLess(worst, 0.005)                                              # 3 significant figures

    def test_disc_in_rect_closed_forms(self):
        self.assertAlmostEqual(J.disc_in_rect(50, 100, 100), math.pi * 2500)
        self.assertAlmostEqual(J.disc_in_rect(150, 100, 100), 4e4)
        R, h = 104.66, 100.0                                                         # four circular segments cut off
        seg = R * R * math.acos(h / R) - h * math.sqrt(R * R - h * h)
        self.assertAlmostEqual(J.disc_in_rect(R, h, h), math.pi * R * R - 4 * seg, places=6)
        self.assertAlmostEqual(J.disc_in_rect(R, h, 1e6), math.pi * R * R - 2 * seg, places=6)

    def test_example5_ring_flange_uplift(self):
        # Example 5: CHS 273×6.3, 8 × M24 8.8 on a 380 mm circle, e1 = 53.5, e2 = 50, t_p = 20 (f_y 265):
        # r2 = 190, r3 = 133.4, k1 = 0.354, f3 = 6.19; plate 1030 kN; plate + bolts 1061 kN (with F_t,Rd = 203);
        # bolts 8 × 203 = 1624 kN
        rows, info = J.baseplate(self._ns(D=273.0, tc=6.3, B=480, H=480, Nc=0.0, Nt=750.0))
        ring = info["ring"]
        self.assertAlmostEqual(ring["r2"], 190.0)
        self.assertAlmostEqual(ring["e1"], 53.5)
        self.assertAlmostEqual(ring["r1"], 240.0)
        self.assertAlmostEqual(ring["r3"], 133.35)
        self.assertAlmostEqual(ring["k1"], 0.354, delta=0.0005)
        self.assertAlmostEqual(ring["f3"], 6.19, delta=0.005)
        self.assertLess(rel(ring["N_plate"] / 1e3, 1030.0), 0.002)
        FtRd = 0.9 * 800 * 353 / 1.25
        self.assertLess(rel(ring["N_plate_bolts"] / 1e3 * 203.0 / (FtRd / 1e3), 1061.0), 0.001)   # with 203 kN
        self.assertLess(rel(ring["N_plate_bolts"] / 1e3, 1061.0), 0.003)                           # unrounded
        self.assertLess(rel(ring["N_bolts"] / 1e3, 1624.0), 0.002)
        names = [r[0] for r in rows]
        self.assertTrue(any("ring plate in bending" in n for n in names))


if __name__ == "__main__":
    unittest.main()
