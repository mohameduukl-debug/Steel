"""Independent validation of the cable-tension-members tools (cable_calc.py, cable_schedule.py, cable_products.json).

Every test compares a tool result with an INDEPENDENT reference: a closed-form solution, the exact elastic catenary
(Irvine 1981), a standard's own numbers (EN 1993-1-11:2006, EN 1993-1-8, ISO 898-1) or a published worked example /
manufacturer table. The same cases are listed in .claude/skills/cable-tension-members/reference/validation.md.

Run:  python3 -m unittest tests.test_cable_tension_members -v
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


cab = load("cable-tension-members", "cable_calc")
sched = load("cable-tension-members", "cable_schedule")
CF = load("tensile-structures", "factors")
PRODUCTS = os.path.join(SK, "cable-tension-members", "reference", "cable_products.json")


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w") as fh:
        json.dump(data, fh)


def NS(**kw):
    return type("A", (), kw)


def bisect(g, lo, hi, n=200):
    """root of g on [lo, hi] (independent of the tool's own solvers)."""
    glo = g(lo)
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        gm = g(mid)
        if (gm > 0) == (glo > 0):
            lo, glo = mid, gm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def elastic_catenary_L0(span, H, W, EA):
    """unstrained length L0 of a level elastic catenary with total weight W (Irvine 1981, Cable Structures, §2:
    span = H·L0/EA + (2H/w0)·asinh(W/(2H)), w0 = W/L0)."""
    return bisect(lambda L0: H * L0 / EA + 2 * H * L0 / W * math.asinh(W / (2 * H)) - span, 0.5 * span, 2.0 * span)


def elastic_catenary_L0_w(span, H, w0, EA):
    """as elastic_catenary_L0 with the weight per UNSTRAINED length w0 given (W = w0·L0 changes with L0)."""
    return bisect(lambda L0: H * L0 / EA + 2 * H / w0 * math.asinh(w0 * L0 / (2 * H)) - span, 0.5 * span, 2.0 * span)


def elastic_catenary_H(span, L0, W, EA):
    """horizontal tension of a level elastic catenary of unstrained length L0 and total weight W (same equation)."""
    return bisect(lambda H: H * L0 / EA + 2 * H * L0 / W * math.asinh(W / (2 * H)) - span, 1e-3, 1e6)


# ------------------------------------------------------------------------------------------------ catenary / parabola
class TestCatenaryParabola(unittest.TestCase):
    def test_level_catenary_closed_form(self):
        # Closed form for level supports (Irvine 1981, Ch. 1): f = a(cosh(L/2a) − 1), S = 2a·sinh(L/2a),
        # T_max = H + w·f, a = H/w. The tool solves the general (inclined) form by bisection on H.
        L, w = 20.0, 0.05
        for f in (0.4, 0.8, 2.5, 5.0):
            a = bisect(lambda a: a * (math.cosh(L / (2 * a)) - 1) - f, 0.1, 1e5)
            H = cab.solve_H(L, 0.0, w, f, "f")
            c = cab.Catenary(L, 0.0, w, H)
            self.assertAlmostEqual(H / (w * a), 1.0, delta=1e-7)
            self.assertAlmostEqual(c.length, 2 * a * math.sinh(L / (2 * a)), delta=1e-7)
            self.assertAlmostEqual(c.T(0), w * a + w * f, delta=1e-7)

    def test_inclined_catenary_end_tension_difference(self):
        # catenary property T_B − T_A = w·(y_B − y_A) (Irvine 1981, Ch. 1)
        for h in (-3.0, 4.0, 10.0):
            c = cab.Catenary(20, h, 1.0, 50)
            self.assertAlmostEqual(c.T(20) - c.T(0), 1.0 * h, places=9)

    def test_parabola_arc_length_closed_form_and_series(self):
        # level parabola: S = (L/2)√(1+16n²) + (L/8n)·asinh(4n) (exact), series L(1 + 8n²/3 − 32n⁴/5) (Irvine 1981)
        L = 30.0
        for n in (0.02, 0.05, 0.1, 0.125, 0.2):
            exact = L / 2 * math.sqrt(1 + 16 * n * n) + L / (8 * n) * math.asinh(4 * n)
            self.assertAlmostEqual(cab.parabola_length(L, 0.0, n * L), exact, delta=1e-9 * L)
            if n <= 0.05:
                self.assertAlmostEqual(cab.parabola_length(L, 0.0, n * L), L * (1 + 8 * n * n / 3 - 32 * n ** 4 / 5),
                                       delta=1e-5 * L)
        # inclined: numerical integration of √(1 + y'²) (Simpson, 2000 strips) for h = 6 m, f = 2 m
        L, h, f = 30.0, 6.0, 2.0
        yp = lambda x: h / L - 4 * f * (L - 2 * x) / L ** 2  # noqa: E731
        g = lambda x: math.sqrt(1 + yp(x) ** 2)  # noqa: E731
        N = 2000
        simpson = (g(0) + g(L) + sum((4 if k % 2 else 2) * g(k * L / N) for k in range(1, N))) * L / N / 3
        self.assertAlmostEqual(cab.parabola_length(L, h, f), simpson, delta=1e-9)

    def test_catenary_vs_parabola_sag_ratios(self):
        # Exact catenary (w per arc) vs parabola (w per horizontal m) with the same span, sag and w.
        # Series: f_cat/f_par at equal H = 1 + x²/12 + …, x = L/(2a) ≈ 4n  ->  H ratio ≈ 1 + 4n²/3;
        # lengths at equal sag differ by O(n⁴). Values documented in reference/validation.md.
        L, w = 1.0, 1.0
        expected_H_ratio = {0.02: 1.0005, 0.05: 1.0033, 0.1: 1.0131, 0.125: 1.0202, 0.2: 1.0494}
        for n, ratio in expected_H_ratio.items():
            H = cab.solve_H(L, 0.0, w, n * L, "f")
            Hp = cab.parabola(L, 0.0, w, f=n * L)["H"]
            self.assertAlmostEqual(H / Hp, ratio, delta=2e-4)
            self.assertAlmostEqual(H / Hp, 1 + 4 * n * n / 3, delta=0.15 * 4 * n * n / 3 + 1e-4)
            c = cab.Catenary(L, 0.0, w, H)
            self.assertLess(abs(c.length / cab.parabola_length(L, 0.0, n * L) - 1), 1.4e-3)
        # at f/L = 1/8 the H (and T_max) difference is ~2 %, NOT < 1 %; lengths agree within 0.03 %
        H = cab.solve_H(L, 0.0, w, 0.125, "f")
        self.assertGreater(H / cab.parabola(L, 0.0, w, f=0.125)["H"] - 1, 0.019)

    def test_stretch_integral_closed_form(self):
        # ∫T/EA ds = (H/EA)·[x/2 + (a/4)·sinh(2(x − x0)/a)] from 0 to L (catenary, T = H cosh, ds = cosh dx)
        for L, h, w, H, EA in ((12.0, 0.0, 1.8, 60.0, 17000.0), (25.0, 5.0, 0.5, 8.0, 30000.0)):
            c = cab.Catenary(L, h, w, H)
            a, x0 = c.a, c.x0
            closed = H / EA * (L / 2 + a / 4 * (math.sinh(2 * (L - x0) / a) - math.sinh(-2 * x0 / a)))
            self.assertAlmostEqual(c.stretch(EA), closed, delta=1e-9 * L)


# ------------------------------------------------------------------------------------------------ unstressed length
class TestUnstressedLength(unittest.TestCase):
    def test_length_vs_exact_elastic_catenary(self):
        # Irvine (1981) elastic catenary: unstrained length L0 for span 12 m, H = 60 kN, EA = 17 000 kN and the same
        # total weight W = w·S as the tool's catenary. Tool: ∫ds/(1 + T/EA) over the loaded catenary (agrees to
        # 0.001 mm; the older first-order S − ∫T/EA ds was 0.15 mm short).
        L, w, H, EA = 12.0, 1.8, 60.0, 17000.0
        a = NS(L=L, h=0.0, w=w, H=H, f=None, EA=EA, alpha=12e-6, alpha_st="V", T_install=20.0, T_ref=20.0,
               fittings=0.0, creep=False)
        S0 = quiet(cab.cmd_length, a)
        S = cab.Catenary(L, 0.0, w, H).length
        L0 = elastic_catenary_L0(L, H, w * S, EA)
        self.assertAlmostEqual(S0, L0, delta=1e-5)
        # worked example quoted in reference/cable-mechanics.md §3 (installed at 30 °C, T_ref 20 °C)
        a.T_install = 30.0
        self.assertAlmostEqual(quiet(cab.cmd_length, a), L0 / (1 + 12e-6 * 10), delta=1e-5)
        self.assertAlmostEqual(quiet(cab.cmd_length, a), 12.0208, delta=1e-4)

    def test_temperature_and_straight_member(self):
        # L0(T_ref) = L0(T_inst)/(1 + αΔT) (EN 1993-1-11 3.3, α = 12e-6) and L0 = L/(1 + F/EA) for a straight
        # member (Hooke): w → 0 limit of the catenary routine.
        L, H, EA, dT = 10.0, 50.0, 20000.0, 15.0
        a = NS(L=L, h=0.0, w=1e-6, H=H, f=None, EA=EA, alpha=12e-6, alpha_st="V", T_install=20.0 + dT, T_ref=20.0,
               fittings=0.0, creep=False)
        S0 = quiet(cab.cmd_length, a)
        self.assertAlmostEqual(S0, L / (1 + H / EA) / (1 + 12e-6 * dT), delta=1e-8)
        a.creep = True                                    # EN 1993-1-11 3.2.2(3) NOTE 1: 0.15 mm/m
        self.assertAlmostEqual(quiet(cab.cmd_length, a), S0 * (1 - 0.15e-3), delta=1e-9)


# ------------------------------------------------------------------------------------------------ edge cable
class TestEdgeCable(unittest.TestCase):
    def test_edge_cable_equilibrium(self):
        # Independent geometry: half-angle φ from the sagitta, tan(φ/2) = 2s/c; equilibrium of the arc under
        # uniform normal load n: 2·T·sin φ = n·c  ->  T = n·c/(2 sin φ)  (= n·R, thin ring / Barlow).
        for c, s, n in ((10.0, 1.0, 3.0), (10.44, 1.17, 8.0), (25.0, 1.5, 4.0), (8.0, 2.0, 2.5)):
            phi = 2 * math.atan(2 * s / c)
            T = quiet(cab.cmd_edge, NS(chord=c, sag=s, n=n))
            self.assertAlmostEqual(T, n * c / (2 * math.sin(phi)), delta=1e-9 * T)
        # shallow limit: parabola H = n·c²/(8s) (Irvine 1981 Ch. 1), within (s/c)²·4/3 + margin
        T = quiet(cab.cmd_edge, NS(chord=20.0, sag=0.5, n=3.0))
        self.assertAlmostEqual(T / (3.0 * 400 / 4.0), 1.0, delta=0.01)


# ------------------------------------------------------------------------------------------------ Irvine
class TestIrvine(unittest.TestCase):
    @staticmethod
    def run_irvine(L, w0, H0, w1, EA, dT=0.0):
        return quiet(cab.cmd_irvine, NS(L=L, w0=w0, H0=H0, w1=w1, EA=EA, dT=dT, alpha=12e-6))

    def test_irvine_cubic_for_added_uniform_load(self):
        # Irvine (1981), Cable Structures, Ch. 3: added uniform load p = w*·w on a parabolic cable gives the
        # cubic  h*³ + (2 + λ²/24)h*² + (1 + λ²/12)h* − (λ²/12)·w*(1 + w*/2) = 0,  h* = ΔH/H.
        for L, w0, H0, w1, EA in ((20.0, 0.1, 50.0, 1.0, 20000.0), (40.0, 0.5, 40.0, 1.5, 30000.0),
                                  (30.0, 0.3, 20.0, 0.36, 15000.0)):
            Le = L * (1 + 8 * (w0 * L / (8 * H0)) ** 2)        # L(1 + 8n²), n = f0/L = w0·L/(8H0)
            lam2 = (w0 * L / H0) ** 2 * L / (H0 * Le / EA)
            ws = w1 / w0 - 1
            h = bisect(lambda h: h ** 3 + (2 + lam2 / 24) * h * h + (1 + lam2 / 12) * h - lam2 / 12 * ws * (1 + ws / 2),
                       -0.99, 1e3)
            self.assertAlmostEqual(self.run_irvine(L, w0, H0, w1, EA) / H0, 1 + h, delta=1e-7)

    def test_irvine_limits(self):
        # λ² → ∞ (inextensible): sag unchanged, H ∝ w (h* = w*); λ² = 0 (no sag): H = H0 − EA·α·ΔT (restrained bar)
        self.assertAlmostEqual(self.run_irvine(20.0, 0.5, 50.0, 1.5, 1e12) / 50.0, 3.0, delta=1e-5)
        self.assertAlmostEqual(self.run_irvine(20.0, 0.0, 50.0, 0.0, 20000.0, dT=-20.0), 50.0 + 20000 * 12e-6 * 20,
                               delta=1e-6)

    def test_irvine_vs_exact_elastic_catenary(self):
        # Exact elastic catenary (Irvine 1981 §2) with the same unstrained length (+ α·ΔT) and the same total loads.
        # The parabolic cable equation is within 0.3 % for f/L up to 0.1.
        for L, w0, H0, w1, EA, dT in ((20, 0.1, 50, 1.0, 20000, 0), (20, 0.1, 50, 1.0, 20000, -30),
                                      (40, 0.5, 40, 1.5, 30000, 20), (20, 1.0, 25, 2.0, 20000, 0)):
            L0 = elastic_catenary_L0(L, H0, w0 * L, EA) * (1 + 12e-6 * dT)
            H_exact = elastic_catenary_H(L, L0, w1 * L, EA)
            self.assertAlmostEqual(self.run_irvine(L, w0, H0, w1, EA, dT) / H_exact, 1.0, delta=0.004)


# ------------------------------------------------------------------------------------------------ vibration
class TestFrequencies(unittest.TestCase):
    def test_taut_string(self):
        # f_n = n/(2L)·√(T/m) (taut string; Irvine 1981 Ch. 4): L = 15 m, T = 80 kN, m = 3.4 kg/m -> f1 = 5.113 Hz
        fr = quiet(cab.cmd_freq, NS(L=15.0, T=80.0, m=3.4, modes=4))
        for n, f in enumerate(fr, 1):
            self.assertAlmostEqual(f, n / 30.0 * math.sqrt(80e3 / 3.4), places=12)
        self.assertAlmostEqual(fr[0], 5.1131, delta=1e-4)

    def test_irvine_symmetric_roots(self):
        # Irvine & Caughey (1974) / Irvine (1981): tan(ω̄/2) = ω̄/2 − (4/λ²)(ω̄/2)³.
        # λ² → ∞: roots of tan x = x, x = 4.493409457909064, 7.725251836937707 (Abramowitz & Stegun Table 4.19)
        self.assertAlmostEqual(cab.irvine_symmetric(1, 1e12), 2 * 4.493409457909064, delta=1e-6)
        self.assertAlmostEqual(cab.irvine_symmetric(2, 1e12), 2 * 7.725251836937707, delta=1e-6)
        # crossovers ω̄ = 2kπ at λ² = 4k²π² (first symmetric = first antisymmetric at λ² = 4π²)
        self.assertAlmostEqual(cab.irvine_symmetric(1, 4 * math.pi ** 2), 2 * math.pi, delta=1e-9)
        self.assertAlmostEqual(cab.irvine_symmetric(2, 16 * math.pi ** 2), 4 * math.pi, delta=1e-9)
        # small λ²: ω̄ ≈ π + 4λ²/π³ (expansion of the same equation about π/2)
        lam2 = 0.01
        self.assertAlmostEqual(cab.irvine_symmetric(1, lam2), math.pi + 4 * lam2 / math.pi ** 3, delta=1e-5)

    def test_tension_from_beam_string_frequencies(self):
        # hinged beam-string (axially loaded simply supported beam): f_n = n/(2L)·√(T/m)·√(1 + n²π²EI/(T L²))
        L, m, T, EI = 15.0, 3.4, 50e3, 3000.0
        f = lambda n: n / (2 * L) * math.sqrt(T / m) * math.sqrt(1 + n * n * math.pi ** 2 * EI / (T * L * L))  # noqa
        pairs = [(n, f(n)) for n in (1, 2, 3)]
        Tfit, EIfit, _ = cab.tension_from_freqs(L, m, pairs)
        self.assertAlmostEqual(Tfit, 50.0, delta=1e-6)
        self.assertAlmostEqual(EIfit, 3000.0, delta=1e-3)

    def test_sag_corrected_tension_from_irvine_frequencies(self):
        # frequencies of a sagging cable generated with Irvine's theory (symmetric roots, antisymmetric 2nπ) for
        # H = 30 kN, λ² ≈ 5.3: the sag correction recovers H; the string-only formula reads high
        H, L, m, EA = 30.0, 30.0, 4.0, 40000.0
        lam2 = (m * 9.81e-3 * L / H) ** 2 * L / (H * L / EA)
        c0 = math.sqrt(H * 1e3 / m)
        pairs = [(1, cab.irvine_symmetric(1, lam2) * c0 / (2 * math.pi * L)), (2, c0 / L),
                 (3, cab.irvine_symmetric(2, lam2) * c0 / (2 * math.pi * L))]
        T, _, _, lam = cab.sag_corrected_tension(L, m, pairs, EI=0.0, EA=EA)
        self.assertAlmostEqual(T, H, delta=1e-4 * H)
        self.assertGreater(cab.tension_from_freqs(L, m, pairs[:1], EI=0.0)[0], 1.1 * H)


# ------------------------------------------------------------------------------------------------ resistance
class TestResistance(unittest.TestCase):
    @staticmethod
    def frd(Fmin, ke, gammaR=1.0):
        a = NS(Fmin=Fmin, ke=ke, gammaR=gammaR, Fk=None, FEd=1.0, Fser=None, fsls=0.45, Nf=1.0, asce=2.2,
               T_asce=None, Fmin_force=None, ke_st="test")
        return quiet(cab.cmd_resist, a)

    def test_en1993_1_11_published_design_resistances(self):
        # Teufelberger-Redaelli Cable System catalogue (metric), F_Rd = (F_uk/1.5)/γR with k_e = 1 (sockets):
        # OSS 16: F_uk 240 -> 160; OSS 40: 1520 -> 1013; FLC 40: 1615 -> 1077; FLC 100: 10075 -> 6717 kN.
        for Fuk, FRd in ((240, 160), (1520, 1013), (1615, 1077), (10075, 6717)):
            self.assertAlmostEqual(self.frd(Fuk, 1.0), FRd, delta=0.5)
        # stainless OSX 40: F_uk 1385 -> F_Rd 839 = F_uk/1.65, i.e. γR = 1.1 for that product
        self.assertAlmostEqual(self.frd(1385, 1.0, gammaR=1.1), 839, delta=0.5)
        # steelwirerope.com Galfan OSS datasheet: MBL 408 kN, swaged (k_e = 0.9) -> design load 245 kN;
        # MBL 1450 kN, spelter socket (k_e = 1.0) -> 967 kN  (EN 1993-1-11 eq. 6.2/6.4, Table 6.3)
        ke_sw, ke_so = CF.get("cable.ke_swaged"), CF.get("cable.ke_socket")
        self.assertAlmostEqual(self.frd(408, ke_sw), 245, delta=0.5)
        self.assertAlmostEqual(self.frd(1450, ke_so), 967, delta=0.5)

    def test_en1993_1_11_table_values(self):
        # EN 1993-1-11:2006 Table 6.3 (k_e), Table 6.2 (γR), Table 7.1/7.2 (stress limits), 6.3.4 (k), 6.4.1 (γM,fr)
        for key, v in (("ke_socket", 1.0), ("ke_swaged", 0.9), ("ke_ferrule", 0.9), ("ke_ubolt", 0.8), ("gammaR", 1.0),
                       ("f_sls", 0.45), ("f_sls_bending_checked", 0.5), ("f_const_install", 0.6),
                       ("f_const_after", 0.55), ("saddle_k", 1.1), ("clamp_gamma", 1.65), ("saddle_min_R_over_d", 30.0),
                       ("saddle_min_R_over_d_lined", 20.0), ("saddle_min_R_over_wire", 400.0)):
            self.assertEqual(CF.get("cable." + key), v, key)
            self.assertEqual(CF.status("cable." + key), "V", key)
        # Table 9.1 / Fig. 9.1 and EN 1993-1-9 Table 8.1 detail 14
        for key, v in (("dsC_spiral_socket", 150.0), ("dsC_parallel_wire", 160.0), ("dsC_threaded_bar", 50.0),
                       ("dsC_prestressing_bar", 105.0), ("m_rope", 4.0), ("m2_rope", 6.0)):
            self.assertEqual(CF.get("fatigue_cables." + key), v, key)

    def test_sls_limit(self):
        # EN 1993-1-11 Table 7.2: F_ser ≤ 0.45·F_uk (0.50 with bending in the fatigue design)
        a = NS(Fmin=367.0, ke=0.9, gammaR=1.0, Fk=None, FEd=100.0, Fser=100.0, fsls=0.45)
        self.assertAlmostEqual(cab.resist_utils(a)[1], 100.0 / (0.45 * 367 * 0.9), places=12)


class TestRod(unittest.TestCase):
    def test_iso898_stress_areas(self):
        # ISO 898-1 nominal stress areas (optimas.com 'ISO metric thread minimum ultimate tensile loads' table)
        for d, As in ((16, 157), (20, 245), (24, 353), (30, 561), (36, 817), (39, 976)):
            P = {39: 4.0}.get(d) or cab.metric_pitch(d)
            self.assertAlmostEqual(cab.stress_area(d, P), As, delta=0.006 * As)

    def test_macalloy_460_ec3_design_resistance(self):
        # Macalloy Tension Structures data sheet UK V4.9 (03/25), Table 3 (460 carbon): min. break load and
        # 'Design Resistance to EC3 N_R,d'. With A_s = break/f_u the thread check k2·f_u·A_s/γM2 must reproduce it.
        table = {30: (28, 330, 238), 36: (34, 483, 348), 48: (44, 875, 630), 64: (59, 1596, 1149)}
        for d, (dbar, Fb, NRd) in table.items():
            a = NS(d=float(d), pitch=None, d_shank=float(dbar), fy=460.0, fu=610.0, FEd=1.0, fitting_Rd=None,
                   As=Fb * 1e3 / 610.0)
            self.assertAlmostEqual(quiet(cab.cmd_rod, a), NRd, delta=1.0)


# ------------------------------------------------------------------------------------------------ stressing
class TestStressTurns(unittest.TestCase):
    def test_straight_cable_hooke(self):
        # no sag: ΔL = ΔF·L/EA; turnbuckle with left/right threads: lead = 2·pitch
        a = NS(L=10.0, EA=14000.0, F1=5.0, F2=20.0, pitch=3.5, thread="double", k_sup=None, w=0.0)
        self.assertAlmostEqual(quiet(cab.cmd_stress_turns, a), 15 * 10 / 14000 * 1e3 / 7.0, places=12)

    def test_ernst_secant_vs_exact_elastic_catenary(self):
        # shortening needed to raise H from F1 to F2 at fixed span = L0(F1) − L0(F2) of the exact elastic catenary
        # (Irvine 1981); the Ernst secant modulus gives it within 0.3 % for these sagging cables.
        for l, w, EA, F1, F2 in ((10.0, 0.02, 14000.0, 5.0, 20.0), (30.0, 0.05, 20000.0, 10.0, 40.0),
                                 (20.0, 0.1, 20000.0, 5.0, 30.0)):
            a = NS(L=l, EA=EA, F1=F1, F2=F2, pitch=3.5, thread="double", k_sup=None, w=w)
            dL_tool = quiet(cab.cmd_stress_turns, a) * 7.0
            dL_exact = (elastic_catenary_L0_w(l, F1, w, EA) - elastic_catenary_L0_w(l, F2, w, EA)) * 1e3
            self.assertAlmostEqual(dL_tool / dL_exact, 1.0, delta=0.003)


# ------------------------------------------------------------------------------------------------ clamps / saddles
class TestClampSaddle(unittest.TestCase):
    def test_clamp_published_worked_examples(self):
        # Sun et al. (2025), Sci. Rep. 15, doi:10.1038/s41598-025-89571-3, 4 bolts × 60 kN initial preload:
        #  T/CECS 1010-2022: R = 2·ū·P_e/γ = 2 × 0.2 × 4 × 0.25 × 60 / 1.65 = 14.55 kN and (0.55) 32 kN
        #  EN 1993-1-11 eq. (6.9) with μ = 0.1 and effective preload 30.6 kN (49 % loss): 0.1 × 4 × 30.6/1.65 = 7.418 kN
        a = NS(dT=1.0, nb=4, bolt_d=16.0, grade="8.8", surfaces=2, Fp=60.0, mu=0.2, retained=0.25, Fperp=0.0)
        self.assertAlmostEqual(cab.clamp_frd(a)[0], 14.55, delta=0.01)
        a.retained = 0.55
        self.assertAlmostEqual(cab.clamp_frd(a)[0], 32.0, delta=0.01)
        b = NS(dT=1.0, nb=4, bolt_d=16.0, grade="8.8", surfaces=1, Fp=60.0, mu=0.1, retained=0.51, Fperp=0.0)
        self.assertAlmostEqual(cab.clamp_frd(b)[0], 7.418, delta=0.001)

    def test_clamp_preload_en1993_1_8(self):
        # EN 1993-1-8 eq. (3.7): F_p,C = 0.7·f_ub·A_s; M16/M20/M24 8.8 -> 87.9/137.2/197.7 kN
        for d, Fp in ((16, 87.92), (20, 137.2), (24, 197.68)):
            self.assertAlmostEqual(cab.bolt_preload(NS(Fp=None, grade="8.8", bolt_d=float(d))), Fp, delta=0.01)
        # hand calculation, EN 1993-1-11 (6.9): 2 surfaces × μ 0.1 × 2 bolts × 87.92 × 0.8 / 1.65 = 17.05 kN
        a = NS(dT=8.0, nb=2, bolt_d=16.0, grade="8.8", surfaces=2)
        self.assertAlmostEqual(cab.clamp_frd(a)[0], 2 * 0.1 * 2 * 87.92 * 0.8 / 1.65, delta=1e-9)

    def test_saddle_en1993_1_11_hand_calculation(self):
        # EN 1993-1-11 6.3: R_min = max(30d, 400δ) (20d lined); slip (6.7) (F1 − k·F_r·μ/γ)/F2 ≤ e^(μα/γ);
        # q = F_r/(d'·L2) with L2 = R·α; Reuleaux σ_b = E·δ/D (Feyrer, Wire Ropes), D = 2R.
        a = NS(T=400.0, R=2.1, d=40.0, type="FLC", delta=5.0, E=160.0, lined=False, T2=380.0, wrap=20.0, Fr=100.0,
               k_clamp=None, L2=None, dprime=None)
        r = cab.saddle_checks(a)
        self.assertAlmostEqual(r["Rmin"], 2000.0, places=9)                       # 400 × 5 > 30 × 40
        alpha = math.radians(20.0)
        self.assertAlmostEqual(r["u_slip"], (400 - 2 * 100 * 0.1 / 1.65) / (380 * math.exp(0.1 * alpha / 1.65)),
                               places=12)
        self.assertAlmostEqual(r["q"], 100e3 / (40 * 2100 * alpha), places=9)
        self.assertAlmostEqual(r["u_pressure"], r["q"] / 40.0, places=12)
        self.assertAlmostEqual(r["sigma_b"], 160e3 * 5.0 / 4200.0, places=9)
        a.lined, a.delta = True, 1.5
        self.assertAlmostEqual(cab.saddle_checks(a)["Rmin"], 800.0, places=9)  # 20 × 40 > 400 × 1.5


# ------------------------------------------------------------------------------------------------ schedule
class TestScheduleHandCalc(unittest.TestCase):
    def test_demo_cable_ec1(self):
        # Hand calculation of cable EC-1 of examples/schedule_example.json (used by examples/run_demo.sh):
        # Ronstan ACS2-GS 20.1 (CBL 367 kN incl. swage loss, A = 0.75·π·20.1²/4 = 238.0 mm², E = 160)
        with open(os.path.join(ROOT, "examples", "schedule_example.json")) as fh:
            s = json.load(fh)
        s["cables"] = [c for c in s["cables"] if c["id"] == "EC-1"]
        lib = read_json(PRODUCTS)["products"]["Ronstan-ACS2-GS-20.1"]
        self.assertEqual((lib["A"], lib["E"], lib["Fmin"]), (238.0, 160, 367))
        r = sched.compute(s)[0]
        EA = 160 * 238.0                                    # 38 080 kN
        Lpin = 10.62 - (250 + 250) / 1000                   # 10.120 m pin-to-pin, stressed
        eps = 18 / EA                                       # prestress strain 4.727e-4
        L0 = Lpin / (1 + eps) / (1 + 12e-6 * (28 - 20))     # 10.11425 m at 20 °C
        self.assertEqual(r["EA_kN"], 38080)
        self.assertAlmostEqual(r["L_pin_stressed_m"], 10.12, places=9)
        self.assertAlmostEqual(r["L0_pin_unstressed_Tref_m"], 10.1142, places=4)
        self.assertAlmostEqual(r["L0_pin_unstressed_Tref_m"], L0, delta=5e-5)
        self.assertAlmostEqual(r["L_pin_at_Fmeas_m"], 10.1190, delta=5e-5)           # L0·(1 + 18/EA)
        self.assertEqual(r["clamp_marks_unstressed_m"], [2.2487, 4.7473, 7.2459])  # (x − 0.25)/(1+ε)/(1+αΔT)
        self.assertAlmostEqual(r["F_Rd_kN"], 244.7, places=1)                       # 367/1.5
        self.assertAlmostEqual(r["util_EN"], 95 / (367 / 1.5), delta=5e-4)
        self.assertAlmostEqual(r["util_ASCE"], 2.2 * 60 / 367, delta=5e-4)
        self.assertAlmostEqual(r["util_SLS"], 60 / (0.45 * 367), delta=5e-4)
        # stressing turns for this cable from 5 to 18 kN with a left/right-hand M20 turnbuckle (pitch 2.5):
        # ΔL = 13·10.12/38 080 = 3.455 mm -> 0.69 turns
        turns = quiet(cab.cmd_stress_turns, NS(L=Lpin, EA=EA, F1=5.0, F2=18.0, pitch=2.5, thread="double",
                                               k_sup=None, w=0.0))
        self.assertAlmostEqual(turns, 13 * 10.12 / 38080 * 1e3 / 5.0, places=9)
        self.assertAlmostEqual(turns, 0.691, delta=1e-3)

    def test_product_gamma_from_eta(self):
        # stainless OSX: Redaelli publishes F_Rd = F_uk/1.65 -> the schedule must use γR = 1.1 for that product
        s = {"cables": [{"id": "S1", "product": "Redaelli-OSX-40", "L_stressed": 5.0, "F_ULS": 100.0}]}
        r = sched.compute(s)[0]
        self.assertAlmostEqual(r["F_Rd_kN"], 839, delta=0.5)

    def test_from_model_and_envelope(self):
        # length-weighted mean prestress: (10·3 + 20·7)/10 = 17 kN; ULS placeholder 3 × max = 60; envelope overrides
        m = {"nodes": [], "edges": [{"id": 0, "group": "EC-1", "length": 3.0, "force": 10.0},
                                    {"id": 1, "group": "EC-1", "length": 7.0, "force": 20.0},
                                    {"id": 2, "length": 1.0, "force": 1.0}]}
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "m.json")
            write_json(p, m)
            s = sched.from_model(p, "SWR-OSS-Galfan-16", 3.0, 2.0, 100.0)
            c = s["cables"][0]
            self.assertEqual((c["L_stressed"], c["F_prestress"], c["F_ULS"], c["F_SLS"]), (10.0, 17.0, 60.0, 40.0))
            e = os.path.join(td, "env.json")
            write_json(e, {"groups": {"EC-1": {"max": 55.04, "min": 3.333, "case_max": "W1"}}})
            s = sched.apply_envelope(s, e, "F_ULS")
            self.assertEqual((s["cables"][0]["F_ULS"], s["cables"][0]["F_min_comb"]), (55.0, 3.33))
            r = sched.compute(s)[0]
            # SWR 16 mm Galfan: MBL 266 kN, swaged k_e 0.9 -> F_Rd = 266·0.9/1.5 = 159.6 (datasheet design load 160)
            self.assertAlmostEqual(r["F_Rd_kN"], 159.6, places=1)
            self.assertAlmostEqual(r["L0_pin_unstressed_Tref_m"], (10.0 - 0.2) / (1 + 17.0 / (160 * 156.0)), delta=5e-5)


# ------------------------------------------------------------------------------------------------ product data
class TestProductLibrary(unittest.TestCase):
    """Internal consistency of every catalogue entry against EN 1993-1-11:2006 Table 2.2 (fill factors, unit
    weight 83 kN/m³ incl. corrosion protection), Table 3.1 (moduli) and the strength range of rope wire."""

    @classmethod
    def setUpClass(cls):
        cls.P = read_json(PRODUCTS)["products"]

    def test_required_fields_and_sources(self):
        self.assertGreaterEqual(len(self.P), 60)
        for k, p in self.P.items():
            for f in ("type", "d", "Fmin", "E", "A", "status", "source"):
                self.assertIn(f, p, k)
            self.assertTrue(p["source"].startswith("https://"), k)
            self.assertIn(p["status"][:2], ("V:", "U:"), k)

    def test_physical_consistency(self):
        for k, p in self.P.items():
            t = p["type"].lower()
            bar = t.startswith("bar")
            stainless = "stainless" in t or "316" in t
            flc = "locked" in t
            ke = 1.0 if p.get("ke_included") else p.get("ke", 1.0)
            fuk_over_A = p["Fmin"] * 1e3 / p["A"]                      # N/mm² on metallic area
            fill = p["A"] / (math.pi * p["d"] ** 2 / 4)
            if bar:
                self.assertTrue(500 <= p["Fmin"] * 1e3 / p["A"] <= 700, k)  # on gross bar area (f_u 610)
                self.assertTrue(195 <= p["E"] <= 210, k)
                continue
            lo, hi = (1150, 1600) if stainless else (1300, 1800)
            self.assertTrue(lo <= fuk_over_A <= hi, f"{k}: F/A = {fuk_over_A:.0f}")
            # EN Table 2.2 fill factor: spiral 0.73–0.77, FLC 0.81–0.88 (suppliers slightly above: margin)
            flo, fhi = (0.80, 0.92) if flc else (0.72, 0.80)
            self.assertTrue(flo <= fill <= fhi, f"{k}: fill {fill:.3f}")
            # EN Table 3.1: spiral 150 ± 10 (suppliers 160 ± 10), stainless 130 ± 10, FLC 160 ± 10
            # (+2 on the upper bounds: small sizes publish EA rounded to whole MN, e.g. Redaelli OSS 12: 15 MN/88 mm²)
            elo, ehi = (120, 142) if stainless else ((150, 172) if flc else (140, 172))
            self.assertTrue(elo <= p["E"] <= ehi, f"{k}: E {p['E']}")
            self.assertLessEqual(ke, 1.0)
            if "EA_MN" in p:
                self.assertAlmostEqual(p["E"] * p["A"] / 1e3 / p["EA_MN"], 1.0, delta=0.035, msg=k)
            if "mass_kg_m" in p:                                      # EN eq. (2.1): g_k = w·A_m, w = 83 kN/m³
                m_en = 83e3 * p["A"] * 1e-6 / 9.81
                self.assertAlmostEqual(p["mass_kg_m"], m_en, delta=max(0.12 * m_en, 0.06), msg=k)

    def test_published_design_values(self):
        for k, p in self.P.items():
            ke = 1.0 if p.get("ke_included") else p.get("ke", 1.0)
            g = p.get("gammaR_ETA", 1.0)
            if "FRd_pub" in p:                    # F_Rd = F_min·k_e/(1.5 γR), EN 1993-1-11 eq. (6.2)/(6.4)
                self.assertAlmostEqual(p["Fmin"] * ke / (1.5 * g), p["FRd_pub"], delta=1.0 + 0.002 * p["FRd_pub"],
                                       msg=k)
            if "Fuk_pub" in p:                    # characteristic breaking load = F_min·k_e
                self.assertAlmostEqual(p["Fmin"] * ke, p["Fuk_pub"], delta=1.0 + 0.002 * p["Fuk_pub"], msg=k)
            if "NRd_EC3_pub" in p:                # Macalloy: 0.9·F_break/1.25 (EN 1993-1-8 Table 3.4)
                self.assertAlmostEqual(0.9 * p["Fmin"] / 1.25, p["NRd_EC3_pub"], delta=1.0, msg=k)

    def test_stainless_1x19_matches_ronstan(self):
        # F_min = A_m·R_m·k_s from Carl Stahl ETA-10/0358 (A_m, k_s = 0.88, R_m = 1570) vs Ronstan's published
        # 1x19 316 breaking loads 29.7 / 52.8 / 82.6 / 119 kN (6 / 8 / 10 / 12 mm)
        for d, F in ((6, 29.7), (8, 52.8), (10, 82.6), (12, 119)):
            self.assertAlmostEqual(self.P[f"SS316-1x19-{d}"]["Fmin"] / F, 1.0, delta=0.003)

    def test_ronstan_cbl_equals_0p9_mbl(self):
        # Ronstan CBL includes the 10 % swage loss: CBL/0.9 must match an independent Galfan MBL table
        # (steelwirerope.com 20 mm: 408 kN; Ronstan 20.1 mm CBL 367 kN)
        self.assertAlmostEqual(self.P["Ronstan-ACS2-GS-20.1"]["Fmin"] / 0.9, self.P["SWR-OSS-Galfan-20"]["Fmin"],
                               delta=0.01 * 408)

    def test_demo_keys_still_present(self):
        for k in ("Ronstan-ACS2-GS-17.0", "Ronstan-ACS2-GS-20.1", "Macalloy460-M36", "OSS-Galfan-30", "FLC-40"):
            self.assertIn(k, self.P)


if __name__ == "__main__":
    unittest.main()
