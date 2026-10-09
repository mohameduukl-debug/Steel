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


if __name__ == "__main__":
    unittest.main()
