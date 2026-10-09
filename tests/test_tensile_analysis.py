"""Independent validation of the tensile-analysis solvers (form_find_fdm, dynamic_relaxation, membrane_dr,
run_cases, mesh_convergence, benchmarks). Every reference value below is computed in THIS file from a closed-form
solution or a published series/table, independently of the solver code. Sources are cited per test and collected
in .claude/skills/tensile-analysis/reference/validation.md.

Run:  python3 -m unittest tests.test_tensile_analysis -v
"""
import contextlib
import importlib.util
import io
import json
import math
import os
import sys
import tempfile
import time
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
cases = load("tensile-analysis", "run_cases")
conv = load("tensile-analysis", "mesh_convergence")
bm = load("tensile-analysis", "benchmarks")


# ---------------------------------------------------------------- independent references (test-side)
# Fichter, W.B. (1997) "Some solutions for the large deflections of uniformly loaded circular membranes",
# NASA TP-3658, https://ntrs.nasa.gov/citations/19970023537 : Hencky series eqs. (12a,b), (20)-(29), (34);
# table of b0 (nu = 0.3 -> 1.7244) and table of Nr(0)/(Eh) for Hencky and uniform-pressure loading.
FICHTER_B0_NU03 = 1.7244
FICHTER_TABLE_NR0 = {("hencky", 0.001): 0.00431, ("hencky", 0.01): 0.0200,
                     ("pressure", 0.001): 0.00435, ("pressure", 0.01): 0.0207}
_B = [(1, 1, -1), (-1, 1, 2), (-2, 3, 5), (-13, 18, 8), (-17, 18, 11), (-37, 27, 14), (-1205, 567, 17),
      (-219241, 63504, 20), (-6634069, 1143072, 23), (-51523763, 5143824, 26), (-998796305, 56582064, 29)]
_A = [(1, 1, 1), (1, 2, 4), (5, 9, 7), (55, 72, 10), (7, 6, 13), (205, 108, 16), (17051, 5292, 19),
      (2864485, 508032, 22), (103863265, 10287648, 25), (27047983, 1469664, 28), (42367613873, 1244805408, 31)]


def hencky_ref(q, rho=0.0, b0=FICHTER_B0_NU03):
    W = q ** (1 / 3) * sum(n / d / b0 ** e * (1 - rho ** (2 * k + 2)) for k, (n, d, e) in enumerate(_A))
    N = 0.25 * q ** (2 / 3) * sum(n / d / b0 ** e * rho ** (2 * k) for k, (n, d, e) in enumerate(_B))
    return W, N


def navier_square(terms=301):
    """Centre deflection coefficient of n∇²w = -p on a square (Navier double sine series,
    w = 16 p a²/(π⁴ n) Σ sin(mπ/2) sin(kπ/2)/(m k (m² + k²)), m, k odd)."""
    s = sum(math.sin(m * math.pi / 2) * math.sin(k * math.pi / 2) / (m * k * (m * m + k * k))
            for m in range(1, terms, 2) for k in range(1, terms, 2))
    return 16 / math.pi ** 4 * s


def navier_square_volume(terms=301):
    """∫∫w dA · n/(p a⁴) = 64/π⁶ Σ 1/(m² k² (m² + k²)) (m, k odd)."""
    return 64 / math.pi ** 6 * sum(1.0 / (m * m * k * k * (m * m + k * k))
                                   for m in range(1, terms, 2) for k in range(1, terms, 2))


class TestReferencesThemselves(unittest.TestCase):
    """Check the test-side references against their published numbers before using them."""

    def test_fichter_series_matches_published_tables(self):
        # Fichter (1997) eq. (30): Σ (2n+1-ν) b2n = 0 at b0 = 1.7244 (ν = 0.3); table: Nr(0)/Eh = 0.00431 at q = 0.001
        resid = sum((2 * k + 1 - 0.3) * n / d / FICHTER_B0_NU03 ** e for k, (n, d, e) in enumerate(_B))
        self.assertLess(abs(resid), 2e-4)
        W, N = hencky_ref(1e-3)
        self.assertAlmostEqual(W / 0.1, 0.6534, places=3)      # w0 = 0.653 a (pa/Et)^(1/3) (Hencky, corrected)
        self.assertAlmostEqual(N, FICHTER_TABLE_NR0[("hencky", 0.001)], places=5)
        self.assertAlmostEqual(hencky_ref(0.01)[1], FICHTER_TABLE_NR0[("hencky", 0.01)], places=4)
        self.assertAlmostEqual(bm.hencky_b0(0.3), FICHTER_B0_NU03, places=3)     # tool-side copy agrees

    def test_navier_square_and_torsion_constant(self):
        # Prandtl membrane analogy: J = 4 ∫∫u dA for ∇²u = -1; square of half-side c: J ≈ 2.25 c⁴ (Roark, 7th ed.,
        # quoted at https://en.wikipedia.org/wiki/Torsion_constant) -> ∫∫u dA = 2.25/64 a⁴ for side a = 2c
        self.assertAlmostEqual(navier_square(), 0.07367, places=5)
        self.assertAlmostEqual(4 * navier_square_volume(), 2.25 / 16, places=3)


class TestHencky(unittest.TestCase):
    """Clamped circular isotropic membrane, no prestress, uniform lateral load (Hencky 1915, Fichter 1997)."""

    def test_cst_center_deflection_and_stresses(self):
        q = 1e-3
        r = bm.run_hencky(8, "snow", q=q)                 # snow = vertical load per plan area = Hencky's lateral load
        self.assertTrue(r["converged"])
        W, N0 = hencky_ref(q)
        self.assertAlmostEqual(r["w0_a"] / W, 1.0, delta=0.01)          # +0.12 % obtained
        self.assertAlmostEqual(r["N0"] / N0, 1.0, delta=0.025)          # -1.6 % (centre elements average over ρ≈0.1)
        # edge radial stress vs. series at the outer elements' centroid radius
        self.assertAlmostEqual(r["Nedge"] / r["Nedge_ref"], 1.0, delta=0.02)
        self.assertEqual(r["wrinkled"], 0)                               # Hencky: tension everywhere

    def test_follower_pressure_vs_lateral_load(self):
        # Fichter (1997) table, ν = 0.3, q = 0.01: uniform (follower) pressure 0.0207, Hencky 0.0200 -> pressure larger
        rp = bm.run_hencky(8, "pressure", q=0.01)
        rs = bm.run_hencky(8, "snow", q=0.01)
        self.assertAlmostEqual(rp["N0"] / FICHTER_TABLE_NR0[("pressure", 0.01)], 1.0, delta=0.04)   # -2.9 %
        self.assertAlmostEqual(rs["N0"] / FICHTER_TABLE_NR0[("hencky", 0.01)], 1.0, delta=0.04)     # -2.3 %
        self.assertGreater(rp["N0"] / rs["N0"], 1.01)          # published ratio 1.035; obtained 1.029


class TestPrestressedSquare(unittest.TestCase):
    """Flat square membrane, uniform isotropic prestress n, small pressure: n∇²w = -p (Navier series 0.07367)."""

    def test_net_and_cst_converge_to_poisson_solution(self):
        ref = navier_square()
        errs = {}
        for solver, meshes in (("net", (8, 16)), ("cst", (8, 12))):
            for nd in meshes:
                r = bm.run_square(nd, solver)
                self.assertTrue(r["converged"])
                errs[(solver, nd)] = r["coef"] / ref - 1
        self.assertLess(abs(errs[("net", 8)]), 0.015)       # -1.25 %
        self.assertLess(abs(errs[("net", 16)]), 0.005)      # -0.36 %
        self.assertLess(abs(errs[("cst", 12)]), 0.008)
        # O(h²): halving h cuts the error ~4x (observed 3.5x)
        self.assertGreater(errs[("net", 8)] / errs[("net", 16)], 3.0)
        # with uniform isotropic stress the CST geometric stiffness equals the 5-point Laplacian of the net
        self.assertAlmostEqual(errs[("cst", 8)], errs[("net", 8)], delta=0.001)


class TestCatenoid(unittest.TestCase):
    """Minimal surface between two coaxial rings: r = c·cosh(z/c), R = c·cosh(h/c) (Euler 1744; e.g.
    https://en.wikipedia.org/wiki/Catenoid). Isotropic uniform-stress form finding must converge to it."""

    @staticmethod
    def c_ref(R, h):
        lo, hi = h / 1.2, 10 * R            # larger (stable) root of c·cosh(h/c) = R
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            lo, hi = (lo, mid) if mid * math.cosh(h / mid) > R else (mid, hi)
        return 0.5 * (lo + hi)

    def test_uniform_stress_fdm_mesh_convergence(self):
        c = self.c_ref(1.0, 0.4)
        self.assertAlmostEqual(c * math.cosh(0.4 / c), 1.0, places=9)
        errs = []
        for nr, nc in ((4, 16), (8, 32), (16, 64)):
            r = bm.run_catenoid(nr, nc)
            self.assertAlmostEqual(r["c"], c, places=9)
            self.assertTrue(r["info"]["converged"] or r["info"]["iterations"] == 100)
            errs.append(r["err"])
        self.assertLess(errs[-1], 5e-5)                 # max |r - c cosh(z/c)| over all nodes, R = 1
        for e1, e2 in zip(errs[:-1], errs[1:]):
            self.assertGreater(e1 / e2, 3.5)            # O(h²): 4.0x per halving observed

    def test_plain_linear_fdm_is_not_a_minimal_surface(self):
        # uniform q on a fixed grid gives a mesh-dependent cosh shape (neck 0.756 instead of 0.911)
        r = bm.run_catenoid(8, 32, uniform=False)
        self.assertGreater(r["err"], 0.1)

    def test_cli_rings_and_prestress_equilibrium(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "hg")
        m = quiet(fdm.main, ["rings", "--R", "5", "--r", "5", "--H", "3", "--nr", "8", "--nc", "32",
                             "--prestress", "2", "--uniform-stress", "--out", p])
        ms = m["membrane_stress"]
        self.assertAlmostEqual(ms["min"], 2.0, delta=0.01)
        self.assertAlmostEqual(ms["max"], 2.0, delta=0.01)
        # axial force of a catenoid = σ·2π·c (constant along the axis); c from R = c cosh(h/c), h = 1.5
        c = self.c_ref(5.0, 1.5)
        self.assertAlmostEqual(m["support_groups"]["RING-T"]["magnitude"] / (2.0 * 2 * math.pi * c), 1.0, delta=0.01)
        # the form-found state is an equilibrium for DR: zero-load run converges at iteration 0
        r = quiet(dr.main, [p + ".json"])
        self.assertEqual(r["analysis"]["iterations"], 0)


class TestLinearFDMExact(unittest.TestCase):
    def test_uniform_q_rings_discrete_closed_form(self):
        # Linear FDM, uniform q, two rings radius R at z = 0 and H: node equilibrium (discrete Laplacian) gives
        # z_j linear and r_{j+1} + r_{j-1} - (4 - 2 cos Δ) r_j = 0, Δ = 2π/nc  ->  r_j = R cosh(κ(j - nr/2)) / cosh(κ nr/2)
        # with cosh κ = 2 - cos Δ (closed-form solution of the linear recurrence; derivation in validation.md)
        R, H, nr, nc = 2.0, 1.5, 10, 24
        m = fdm.gen_rings(R, R, H, nr, nc, 1.0)
        fdm.solve_fdm(m)
        kappa = math.acosh(2 - math.cos(2 * math.pi / nc))
        for nd in m["nodes"]:
            i, j = nd["grid"]
            r_ref = R * math.cosh(kappa * (j - nr / 2)) / math.cosh(kappa * nr / 2)
            self.assertAlmostEqual(math.hypot(nd["xyz"][0], nd["xyz"][1]), r_ref, places=8)
            self.assertAlmostEqual(nd["xyz"][2], H * j / nr, places=8)


class TestRunCasesStatics(unittest.TestCase):
    def test_gradient_and_zone_total_load(self):
        # flat 10 m square, rigid edges, small pressures: total vertical support pull = exact integral of the
        # pressure field over the plan (linear gradient: a²(p_w + p_l)/2; zone aligned with grid lines: Σ p_i A_i)
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "flat")
        quiet(fdm.main, ["hypar", "--size", "10", "--high", "0", "--n", "10", "--prestress", "2", "--out", p])
        cf = os.path.join(tmp, "c.json")
        with open(cf, "w") as fh:
            json.dump({"cases": [{"name": "G", "factor": 1.5, "tol": 1e-7,
                                  "gradient": {"dir_deg": 0, "p_windward": 0.02, "p_leeward": 0.01}},
                                 {"name": "Z", "pressure": 0.01, "tol": 1e-7,
                                  "zones": [{"poly": [[0, 0], [4, 0], [4, 10], [0, 10]], "p": 0.03}]}]}, fh)
        env = quiet(cases.run, p + ".json", cf, None)
        tot = {c: sum(v[c][2] for v in env["reactions"].values()) for c in ("G", "Z")}
        self.assertAlmostEqual(tot["G"] / (1.5 * 100 * (0.02 + 0.01) / 2), 1.0, delta=0.002)
        self.assertAlmostEqual(tot["Z"] / (0.03 * 40 + 0.01 * 60), 1.0, delta=0.002)


class TestCableDR(unittest.TestCase):
    """Single cables in dynamic_relaxation.relax against exact solutions (Irvine, Cable Structures, 1981)."""

    def test_point_load_exact(self):
        L, EA, T0, P = 10.0, 10000.0, 10.0, 5.0
        L0 = L / (1 + T0 / EA)
        # exact: two straight segments, T = EA(l - l0)/l0, 2 T sinθ = P, l = (L/2)/cosθ (bisection here)
        lo, hi = 0.0, math.pi / 2 - 1e-9
        for _ in range(200):
            th = 0.5 * (lo + hi)
            T = EA * (L / 2 / math.cos(th) - L0 / 2) / (L0 / 2)
            lo, hi = (lo, th) if 2 * T * math.sin(th) > P else (th, hi)
        sag_ref, T_ref = L / 2 * math.tan(th), T
        r = bm.run_cable_point(20, L, EA, T0, P)
        self.assertAlmostEqual(r["sag"] / sag_ref, 1.0, delta=1e-5)
        self.assertAlmostEqual(r["T"] / T_ref, 1.0, delta=1e-5)

    def test_uniform_load_on_plan_is_parabola(self):
        L, EA, w, S0 = 10.0, 20000.0, 1.0, 10.25
        r = bm.run_cable_udl(40, L, EA, w, S0)
        # funicular of a load per horizontal length is y = w x (L - x)/(2H) EXACTLY at the nodes
        self.assertLess(r["shape_dev"], 1e-6 * r["sag"] + 1e-9)
        self.assertAlmostEqual(r["sag"], w * L * L / (8 * r["H"]), delta=1e-6)
        # H from the elastic length condition of the continuous parabola (Simpson integral, test-side)
        def unstressed(H, n=2000):
            h = L / n
            f = [math.sqrt(1 + (w / H * (L / 2 - k * h)) ** 2) for k in range(n + 1)]
            g = [fk / (1 + H * fk / EA) for fk in f]
            return h / 3 * (g[0] + g[-1] + 4 * sum(g[1:-1:2]) + 2 * sum(g[2:-1:2]))
        lo, hi = 1.0, 100.0
        for _ in range(100):
            H = 0.5 * (lo + hi)
            lo, hi = (H, hi) if unstressed(H) > S0 else (lo, H)
        self.assertAlmostEqual(r["H"] / H, 1.0, delta=0.002)       # -0.03 % (polygon vs curve)

    def test_self_weight_elastic_catenary(self):
        L, EA, W, L0 = 10.0, 20000.0, 10.0, 10.25
        # Irvine (1981) §2: span = H L0/EA + 2 (H L0/W) asinh(W/2H); sag = W L0/(8EA) + (H L0/W)(√(1+(W/2H)²) - 1)
        lo, hi = 0.1, 1000.0
        for _ in range(200):
            H = math.sqrt(lo * hi)
            span = H * L0 / EA + 2 * H * L0 / W * math.asinh(W / (2 * H))
            lo, hi = (lo, H) if span > L else (H, hi)
        sag = W * L0 / (8 * EA) + H * L0 / W * (math.sqrt(1 + (W / (2 * H)) ** 2) - 1)
        r = bm.run_cable_catenary(40, L, EA, W, L0)
        self.assertAlmostEqual(r["H"] / H, 1.0, delta=0.002)
        self.assertAlmostEqual(r["sag"] / sag, 1.0, delta=0.002)


class TestWrinkling(unittest.TestCase):
    """Tension-field theory (Wagner 1929; Mansfield 1989; Roddeman et al. 1987, J. Appl. Mech. 54:884): a wrinkled
    membrane carries a uniaxial stress σ·n⊗n; the stress across the wrinkles is zero, never compressive."""
    Ew, Ef, nu, G = 800.0, 600.0, 0.3, 30.0

    def mem(self):
        m = fdm.gen_sail4(1.0, 0.0, 1, 1, 1, True)
        return mdr.Membrane(m, self.Ew, self.Ef, self.nu, self.G, 1e4, prestress=(0.0, 0.0))

    def strain_of(self, th, sig, beta):
        """Strain of uniaxial stress sig at angle th (orthotropic compliance, e.g. Jones, Mechanics of Composite
        Materials, 2nd ed., §2.6) plus a wrinkling contraction beta across n."""
        c, s = math.cos(th), math.sin(th)
        sx, sy, txy = sig * c * c, sig * s * s, sig * c * s
        e11 = sx / self.Ew - self.nu / self.Ew * sy - beta * s * s
        e22 = -self.nu / self.Ew * sx + sy / self.Ef - beta * c * c
        g12 = txy / self.G + 2 * beta * s * c
        return (e11, e22, g12), (sx, sy, txy)

    def linear(self, m, e):
        D11, D22, D12, D33 = m.D
        return D11 * e[0] + D12 * e[1], D12 * e[0] + D22 * e[1], D33 * e[2]

    def test_uniaxial_warp_tension_with_excess_contraction(self):
        m = self.mem()
        e, exp = self.strain_of(0.0, 8.0, 0.01)
        lin = self.linear(m, e)
        self.assertLess(lin[1], -1.0)                        # the linear law would give weft COMPRESSION
        S11, S22, S12, flag = m.wrinkle(*lin, {"th": None})
        self.assertEqual(flag, 1)
        self.assertAlmostEqual(S11, self.Ew * 0.01, places=9)   # σ = E_w·ε_w (free lateral contraction)
        self.assertAlmostEqual(S22, 0.0, places=9)
        self.assertAlmostEqual(S12, 0.0, places=9)

    def test_off_axis_orthotropic_uniaxial(self):
        m = self.mem()
        for deg, sig, beta in ((30, 5.0, 0.02), (75, 3.0, 0.005), (-40, 4.0, 0.01)):
            e, exp = self.strain_of(math.radians(deg), sig, beta)
            got = m.wrinkle(*self.linear(m, e), {"th": None})
            self.assertEqual(got[3], 1)
            for k in range(3):
                self.assertAlmostEqual(got[k], exp[k], places=7)
            # principal stresses of the result: (sig, 0) -> never compressive
            mean = 0.5 * (got[0] + got[1])
            rad = math.sqrt(0.25 * (got[0] - got[1]) ** 2 + got[2] ** 2)
            self.assertAlmostEqual(mean - rad, 0.0, places=7)

    def test_slack_when_all_strains_negative(self):
        m = self.mem()
        S = m.wrinkle(*self.linear(m, (-0.01, -0.005, 0.0)), {"th": None})
        self.assertEqual(S, (0.0, 0.0, 0.0, 2))

    def test_wagner_shear_panel(self):
        # pure shear γ of an isotropic sheet: diagonal tension σ1 = E·ε1 at 45°, shear flow τ = σ1/2 (Wagner);
        # the linear membrane would carry G·γ = E γ /(2(1+ν)) with a compressive diagonal
        r = bm.run_shear_panel(0.02, 800.0, 0.3)
        self.assertTrue(r["all_wrinkled"])
        self.assertAlmostEqual(r["S12"], 800.0 * (0.01 + 0.02 ** 2 / 8) / 2, places=6)
        self.assertLess(r["residual"], 1e-8)                # homogeneous tension field is an equilibrium
        self.assertGreater(r["S12_linear"] / r["S12"], 1.5)


class TestPerformanceAndConvergence(unittest.TestCase):
    def test_30x30_formfind_and_dr_load_case(self):
        t = time.time()
        m = fdm.gen_sail4(10, 3, 30, 1.0, 12.0, False)
        fdm.solve_fdm(m)
        fdm.compute_results(m, 2.0)
        t_ff = time.time() - t
        t = time.time()
        r = dr.analyse(m, 800, 600, 14000, pressure=0.9)
        t_dr = time.time() - t
        self.assertEqual(len(m["nodes"]), 961)
        self.assertTrue(r["analysis"]["converged"])
        self.assertLess(t_ff, 5.0)       # ~0.1 s measured
        self.assertLess(t_dr, 45.0)      # ~5.6 s measured on one CPU (was ~17 s before the flat-array rewrite)

    def test_fast_kernels_match_reference_formulation(self):
        # flat-array DR / CST kernels vs. the dictionary-based external_loads and element_state (same equations)
        m = fdm.gen_sail4(10, 3, 6, 1.0, 12.0, False)
        fdm.solve_fdm(m)
        fdm.compute_results(m, 2.0)
        X = [[p + 0.01 * math.sin(i + k) for k, p in enumerate(nd["xyz"])] for i, nd in enumerate(m["nodes"])]
        n = len(X)
        Rx, Ry, Rz = [0.0] * n, [0.0] * n, [0.0] * n
        dr.add_face_loads(dr._tri_list(m), [p[0] for p in X], [p[1] for p in X], [p[2] for p in X],
                          0.7, 0.3, None, Rx, Ry, Rz)
        P = dr.external_loads(m, X, 0.7, 0.3)
        for i in range(n):
            for c, R in enumerate((Rx, Ry, Rz)):
                self.assertAlmostEqual(R[i], P.get(i, [0, 0, 0])[c], places=12)
        mem = mdr.Membrane(m, 800, 600, 0.3, 30, 14000, wrinkling=False)
        R, _ = mem.forces(X)
        ref = [[0.0, 0.0, 0.0] for _ in range(n)]
        for tri in mem.tris:
            f1, f2, (S11, S22, S12), _ = mem.element_state(tri, X)
            for k, node in enumerate(tri["n"]):
                gx, gy = tri["dN"][k]
                for c in range(3):
                    ref[node][c] -= tri["A0"] * ((S11 * f1[c] + S12 * f2[c]) * gx + (S12 * f1[c] + S22 * f2[c]) * gy)
        for cb in mem.cables:
            a, b = cb["n"]
            d = [X[b][c] - X[a][c] for c in range(3)]
            L = math.sqrt(sum(v * v for v in d))
            T = max(cb["EA"] * (L - cb["L0"]) / cb["L0"], 0.0)
            for c in range(3):
                ref[a][c] += T * d[c] / L
                ref[b][c] -= T * d[c] / L
        for i in range(n):
            for c in range(3):
                self.assertAlmostEqual(R[i][c], ref[i][c], places=9)

    def test_mesh_convergence_helper(self):
        rows, verdict = quiet(conv.main, ["sail4", "--size", "10", "--high", "3", "--n", "4", "--qc", "12",
                                          "--prestress", "2", "--solver", "net", "--pressure", "0.9",
                                          "--levels", "1", "2"])
        self.assertEqual([r["nodes"] for r in rows], [25, 81])
        self.assertIn("disp_max_mm", verdict)
        self.assertEqual(len(verdict["disp_max_mm"]["changes_pct"]), 1)
        # qc is scaled with the mesh: cable force stays ~constant (FDM: force = q·L, L halves when n doubles)
        ff = quiet(conv.main, ["sail4", "--n", "8", "--qc", "12", "--prestress", "2", "--solver", "none",
                               "--levels", "1", "2"])[0]
        self.assertAlmostEqual(ff[1]["cable_max_kN"] / ff[0]["cable_max_kN"], 1.0, delta=0.05)
        keep = quiet(conv.main, ["sail4", "--n", "8", "--qc", "12", "--prestress", "2", "--solver", "none",
                                 "--levels", "1", "2", "--keep-qc"])[0]
        self.assertLess(keep[1]["cable_max_kN"] / keep[0]["cable_max_kN"], 0.7)

    def test_richardson_order(self):
        # f(h) = 1 + h² sampled at h = 1, 1/2, 1/4 -> order 2, extrapolated 1
        rows = [{"k": 1 + h * h} for h in (1.0, 0.5, 0.25)]
        p, fx = conv.richardson(rows, "k", [1, 2, 4])
        self.assertAlmostEqual(p, 2.0, places=9)
        self.assertAlmostEqual(fx, 1.0, places=9)

    def test_cases_cst_still_runs(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "s")
        quiet(fdm.main, ["sail4", "--n", "6", "--prestress", "2", "--out", p])
        cf = os.path.join(tmp, "c.json")
        with open(cf, "w") as fh:
            json.dump({"solver": "cst", "cases": [{"name": "PS"}, {"name": "S", "snow": 0.5}]}, fh)
        env = quiet(cases.main, [p + ".json", cf, "--out", os.path.join(tmp, "k")])
        self.assertTrue(all(r["converged"] for r in env["summary"]))
        with open(os.path.join(tmp, "k_summary.md")) as fh:
            self.assertIn("Orthotropic CST", fh.read())


if __name__ == "__main__":
    unittest.main()
