"""Independent validation of the fabrication-drawings skill tools (stdlib unittest).

Every test compares a tool result with an INDEPENDENT reference (closed-form geometry, hand calculation or the
Autodesk DXF specification); the source is cited in each test and summarised in
.claude/skills/fabrication-drawings/reference/validation.md.

Run:  python3 -m unittest tests.test_fabrication_drawings -v
"""
import contextlib
import csv
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


def captured(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = fn(*a, **k)
    return res, buf.getvalue()


cut = load("fabrication-drawings", "cutting_pattern")
dxfw = load("fabrication-drawings", "dxf_writer")
rdr = load("fabrication-drawings", "dxf_reader")
nestm = load("fabrication-drawings", "nest_panels")
ga = load("fabrication-drawings", "export_dxf")
spd = load("fabrication-drawings", "steel_part_dxf")
fdm = load("tensile-analysis", "form_find_fdm")
sched = load("cable-tension-members", "cable_schedule")


# ------------------------------------------------------------------ geometry helpers (test side, independent)
def grid_model(fn, nu, nv, periodic=False):
    """structured model in the shared schema; fn(i, j) -> (x, y, z) in metres."""
    ncol = nu if periodic else nu + 1
    nodes = [{"id": j * ncol + i, "xyz": list(fn(i, j)), "fixed": False, "grid": [i, j]}
             for j in range(nv + 1) for i in range(ncol)]
    faces = []
    for j in range(nv):
        for i in range(nu):
            i2 = (i + 1) % ncol if periodic else i + 1
            faces.append([j * ncol + i, j * ncol + i2, (j + 1) * ncol + i2, (j + 1) * ncol + i])
    return {"units": {"length": "m", "force": "kN"}, "type": "custom",
            "grid": {"nu": nu, "nv": nv, "periodic_u": periodic}, "nodes": nodes, "edges": [], "faces": faces}


def revolve(rz, nu, dtheta=None, periodic=True):
    dth = dtheta or 2 * math.pi / nu
    return grid_model(lambda i, j: (rz[j][0] * math.cos(i * dth), rz[j][0] * math.sin(i * dth), rz[j][1]),
                      nu, len(rz) - 1, periodic)


def mm(model):
    return [[c * 1000 for c in nd["xyz"]] for nd in model["nodes"]]


def flatten_grid(grid):
    """flatten a panel grid with the tool's flatten(); return 2D positions P[(s, k)] plus strain stats."""
    ns, nx = len(grid), len(grid[0])
    Xl = [p for row in grid for p in row]
    idx = lambda s, k: s * nx + k
    quads = [(idx(s, k), idx(s, k + 1), idx(s + 1, k + 1), idx(s + 1, k)) for s in range(ns - 1) for k in range(nx - 1)]
    P, emax, erms, strains = cut.flatten(quads, Xl, return_strains=True)
    return {(s, k): P[idx(s, k)] for s in range(ns) for k in range(nx)}, emax, erms, strains, quads


def side_points(net, kinds, kind):
    n = len(net)
    return [net[i] for i in range(n) if kinds[i] == kind] + \
           [net[(i + 1) % n] for i in range(n) if kinds[i] == kind]


def farthest_pair(pts):
    best = (0, None, None)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = math.dist(pts[i], pts[j])
            if d > best[0]:
                best = (d, pts[i], pts[j])
    return best[1], best[2]


def line_intersection(p1, p2, q1, q2):
    r = (p2[0] - p1[0], p2[1] - p1[1])
    s = (q2[0] - q1[0], q2[1] - q1[1])
    den = r[0] * s[1] - r[1] * s[0]
    t = ((q1[0] - p1[0]) * s[1] - (q1[1] - p1[1]) * s[0]) / den
    return (p1[0] + t * r[0], p1[1] + t * r[1])


def shoelace(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def seg_pt(c, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / L2))
    return math.hypot(c[0] - a[0] - t * dx, c[1] - a[1] - t * dy)


def segs_cross(p, q, a, b):
    def o(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    return o(p, q, a) * o(p, q, b) < 0 and o(a, b, p) * o(a, b, q) < 0


def pip(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def boundary_distance(A, B):
    """exact min distance between the boundaries of two polygons (test-side implementation)."""
    best = math.inf
    for i in range(len(A)):
        p, q = A[i], A[(i + 1) % len(A)]
        for j in range(len(B)):
            a, b = B[j], B[(j + 1) % len(B)]
            if segs_cross(p, q, a, b):
                return 0.0
            best = min(best, seg_pt(p, a, b), seg_pt(q, a, b), seg_pt(a, p, q), seg_pt(b, p, q))
    return best


# ============================================================ 1. patterning vs exact developable geometry
class TestDevelopableExact(unittest.TestCase):
    """Cones and cylinders are developable: their development is known in closed form
    (e.g. Kreyszig, Differential Geometry, ruled/developable surfaces; any descriptive-geometry text:
    the lateral surface of a right circular cone frustum develops into an annular sector with radii equal to the
    slant distances s = r / sin(alpha) and sector angle theta * sin(alpha); a cylinder into a rectangle
    of width R * theta). For a polyhedral mesh with nodes on the surface the facets are planar and the
    exact development is: rays from the apex at angle beta = 2 asin(sin(alpha) sin(dtheta/2)) per bay."""

    def cone_panel(self, nu=48, nv=10, strip=4, r1=6.0, r2=2.0, H=4.0):
        m = revolve([(r1 + (r2 - r1) * j / nv, H * j / nv) for j in range(nv + 1)], nu)
        pans, _, _ = cut.build_panels(m, mm(m), "v", strip, "grid", None)
        return pans[0], dict(nu=nu, nv=nv, strip=strip, r1=r1 * 1000, r2=r2 * 1000, H=H * 1000)

    def test_cone_frustum_develops_into_exact_annular_sector(self):
        pan, g = self.cone_panel()
        net, kinds, emax, erms, seam_len, seam2d, stats = cut.process_panel(pan, 0.0, 0.0, None, None, 0.0)
        slant = math.hypot(g["r1"] - g["r2"], g["H"])
        sina = (g["r1"] - g["r2"]) / slant
        dth = 2 * math.pi / g["nu"]
        theta = g["strip"] * dth
        s_out, s_in = g["r1"] / sina, g["r2"] / sina
        beta_poly = g["strip"] * 2 * math.asin(sina * math.sin(dth / 2))      # exact for the faceted mesh
        beta_smooth = theta * sina                                              # smooth cone
        # sides (meridians) are straight lines through the apex
        Lp, Lq = farthest_pair(side_points(net, kinds, "left"))
        Rp, Rq = farthest_pair(side_points(net, kinds, "right"))
        for pts, (a, b) in ((side_points(net, kinds, "left"), (Lp, Lq)), (side_points(net, kinds, "right"), (Rp, Rq))):
            for p in pts:   # collinear within 1e-6 mm
                self.assertLess(seg_pt(p, a, b), 1e-6)
        apex = line_intersection(Lp, Lq, Rp, Rq)
        radii = sorted(math.dist(apex, p) for p in (Lp, Lq, Rp, Rq))
        self.assertAlmostEqual(radii[0], s_in, delta=1e-6 * s_in)
        self.assertAlmostEqual(radii[1], s_in, delta=1e-6 * s_in)
        self.assertAlmostEqual(radii[2], s_out, delta=1e-6 * s_out)
        self.assertAlmostEqual(radii[3], s_out, delta=1e-6 * s_out)
        u = [(p[0] - apex[0], p[1] - apex[1]) for p in (max((Lp, Lq), key=lambda p: math.dist(apex, p)),
                                                        max((Rp, Rq), key=lambda p: math.dist(apex, p)))]
        ang = math.acos((u[0][0] * u[1][0] + u[0][1] * u[1][1]) / (math.hypot(*u[0]) * math.hypot(*u[1])))
        self.assertAlmostEqual(ang, beta_poly, delta=1e-9)                       # exact faceted development
        self.assertLess(abs(ang - beta_smooth) / beta_smooth, 5e-4)              # chord discretisation only
        # arc lengths: chord sums exact; smooth arc r*theta within the chord error 1 - sin(x)/x
        ends = sorted(sum(math.dist(net[i], net[(i + 1) % len(net)]) for i in range(len(net)) if kinds[i] == kd)
                      for kd in ("end0", "end1"))
        for got, r in zip(ends, (g["r2"], g["r1"])):
            self.assertAlmostEqual(got, g["strip"] * 2 * r * math.sin(dth / 2), delta=1e-6 * got)
            self.assertLess(abs(got - r * theta) / (r * theta), 1 - math.sin(dth / 2) / (dth / 2) + 1e-9)
        # area: exact faceted development (polar polygon) and smooth annular sector
        a_poly = 0.5 * (s_out ** 2 - s_in ** 2) * g["strip"] * math.sin(beta_poly / g["strip"])
        self.assertAlmostEqual(abs(cut.area(net)), a_poly, delta=1e-9 * a_poly)
        a_smooth = 0.5 * beta_smooth * (s_out ** 2 - s_in ** 2)
        bk = beta_poly / g["strip"]                  # inscribed facets: sin(b)/b per bay + chord-angle difference
        bound = (1 - math.sin(bk) / bk) + abs(beta_poly - beta_smooth) / beta_smooth
        self.assertLess(abs(abs(cut.area(net)) - a_smooth) / a_smooth, bound + 1e-9)
        self.assertLess(emax, 1e-9)                                             # developable: no strain
        self.assertLess(abs(stats["area2d"] - stats["area3d"]) / stats["area3d"], 1e-9)

    def test_cone_all_boundary_distances_match_exact_development(self):
        pan, g = self.cone_panel(nu=36, nv=8, strip=3)
        P, emax, *_ = flatten_grid(pan["grid"])
        slant = math.hypot(g["r1"] - g["r2"], g["H"])
        sina = (g["r1"] - g["r2"]) / slant
        beta = 2 * math.asin(sina * math.sin(math.pi / g["nu"]))
        ex = {(s, k): ((g["r1"] + (g["r2"] - g["r1"]) * s / g["nv"]) / sina * math.cos(k * beta),
                       (g["r1"] + (g["r2"] - g["r1"]) * s / g["nv"]) / sina * math.sin(k * beta)) for (s, k) in P}
        keys = list(P)
        err = max(abs(math.dist(P[a], P[b]) - math.dist(ex[a], ex[b])) for i, a in enumerate(keys) for b in keys[i + 1:])
        self.assertLess(err, 1e-6)   # mm, every pair of nodes (global shape, not only mesh edges)

    def test_cylinder_strip_develops_into_exact_rectangle(self):
        R, Lc, nu, strip = 3000.0, 8000.0, 36, 3
        dth = 2 * math.pi / nu
        m = grid_model(lambda i, j: (3 * math.cos(i * dth), 3 * math.sin(i * dth), 8 * j / 8), nu, 8, True)
        pans, _, _ = cut.build_panels(m, mm(m), "v", strip, "grid", None)
        net, kinds, emax, *_ = cut.process_panel(pans[0], 0.0, 0.0, None, None, 0.0)
        xs, ys = [p[0] for p in net], [p[1] for p in net]
        W_poly = strip * 2 * R * math.sin(dth / 2)
        self.assertAlmostEqual(max(xs) - min(xs), Lc, delta=1e-6)
        self.assertAlmostEqual(max(ys) - min(ys), W_poly, delta=1e-6)
        self.assertAlmostEqual(abs(cut.area(net)), Lc * W_poly, delta=1e-3)   # mm2 on 12.4e6 mm2
        self.assertLess(abs(W_poly - R * strip * dth) / (R * strip * dth), 1 - math.sin(dth / 2) / (dth / 2) + 1e-12)
        # every net vertex lies on the rectangle boundary (corners exactly square)
        for p in net:
            self.assertLess(min(abs(p[0] - min(xs)), abs(p[0] - max(xs)), abs(p[1] - min(ys)), abs(p[1] - max(ys))),
                            1e-6)
        # compensation hand calculation on the same panel: warp 1.5 % along the generator, weft 0.8 % across
        net_c, *_ = cut.process_panel(pans[0], 0.015, 0.008, None, None, 0.0)
        xs, ys = [p[0] for p in net_c], [p[1] for p in net_c]
        self.assertAlmostEqual(max(xs) - min(xs), Lc * 0.985, delta=1e-6)      # 7880.000 mm
        self.assertAlmostEqual(max(ys) - min(ys), W_poly * 0.992, delta=1e-6)


class TestDoublyCurvedGore(unittest.TestCase):
    """Sphere zone gores vs the classical gore construction (sinusoidal / Sanson-Flamsteed projection of one
    gore: x = R*lambda*cos(phi), y = R*phi; Snyder, Map Projections - A Working Manual, USGS PP 1395 (1987), p. 243):
    parallels and central meridian true length, gore area = R^2 * dlambda * (sin phi2 - sin phi1) (Archimedes).
    A sphere is not developable (Gauss, K = 1/R^2 != 0), so some flattening strain must remain; for a narrow
    strip of width w it scales with K*w^2 (halving the gore width divides it by about 4)."""

    R, PHI2, NV = 10000.0, math.pi / 3, 24

    def gore(self, strip, bay_deg=5.0):
        dth = math.radians(bay_deg)
        rz = [(self.R / 1000 * math.cos(self.PHI2 * j / self.NV), self.R / 1000 * math.sin(self.PHI2 * j / self.NV))
              for j in range(self.NV + 1)]
        m = revolve(rz, strip, dtheta=dth, periodic=False)           # ONE gore of strip bays
        pans, _, _ = cut.build_panels(m, mm(m), "v", strip, "grid", None)
        P, emax, erms, strains, quads = flatten_grid(pans[0]["grid"])
        return m, pans[0], P, emax, erms, strains, strip * dth

    def check_gore(self, strip):
        m, pan, P, emax, erms, strains, dl = self.gore(strip)
        ns, nx = self.NV + 1, strip + 1
        R = self.R
        # gore widths along the parallels
        for s in range(ns):
            phi = self.PHI2 * s / (ns - 1)
            w = sum(math.dist(P[(s, k - 1)], P[(s, k)]) for k in range(1, nx))
            w_cf = R * math.cos(phi) * dl
            self.assertLess(abs(w - w_cf) / w_cf, emax + 5e-4, f"station {s}")
        # central meridian length
        c = sum(math.dist(P[(s - 1, nx // 2)], P[(s, nx // 2)]) for s in range(1, ns))
        self.assertLess(abs(c - R * self.PHI2) / (R * self.PHI2), emax + 5e-4)
        # gore area (equal-area sinusoidal gore)
        ring = [P[(0, k)] for k in range(nx)] + [P[(s, nx - 1)] for s in range(1, ns)] + \
               [P[(ns - 1, k)] for k in range(nx - 2, -1, -1)] + [P[(s, 0)] for s in range(ns - 2, 0, -1)]
        A_cf = R * R * dl * (math.sin(self.PHI2) - 0.0)
        self.assertLess(abs(abs(shoelace(ring)) - A_cf) / A_cf, 2 * emax)
        # the least-squares pattern is at least as good (RMS edge strain) as the textbook sinusoidal gore
        grid = pan["grid"]
        sin_pos = {(s, k): (R * (k - (nx - 1) / 2) * dl / strip * math.cos(self.PHI2 * s / (ns - 1)),
                            R * self.PHI2 * s / (ns - 1)) for s in range(ns) for k in range(nx)}
        sstr = []
        for s in range(ns - 1):
            for k in range(nx - 1):
                q = [(s, k), (s, k + 1), (s + 1, k + 1), (s + 1, k)]
                for a, b in ((0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)):
                    L3 = math.dist(grid[q[a][0]][q[a][1]], grid[q[b][0]][q[b][1]])
                    sstr.append((math.dist(sin_pos[q[a]], sin_pos[q[b]]) - L3) / L3)
        rms_sin = math.sqrt(sum(x * x for x in sstr) / len(sstr))
        self.assertLessEqual(erms, rms_sin)
        self.assertGreater(emax, 1e-4)        # non-developable: strain cannot vanish (theorema egregium)
        return emax, erms, rms_sin

    def test_gore_widths_length_area_and_strain_scaling(self):
        e30, r30, s30 = self.check_gore(6)    # 30 deg gore
        e15, r15, s15 = self.check_gore(3)    # 15 deg gore
        self.assertGreater(e30 / e15, 3.0)    # K w^2 scaling -> 4
        self.assertLess(e30 / e15, 5.5)
        self.assertGreater(r30 / r15, 3.0)
        self.assertLess(r30 / r15, 5.5)

    def test_strain_warning_threshold(self):
        tmp = tempfile.mkdtemp()
        out = {}
        for strip in (6, 3):
            dth = math.radians(5.0)
            rz = [(self.R / 1000 * math.cos(self.PHI2 * j / self.NV), self.R / 1000 * math.sin(self.PHI2 * j / self.NV))
                  for j in range(self.NV + 1)]
            m = revolve(rz, strip, dtheta=dth, periodic=False)
            p = os.path.join(tmp, f"g{strip}.json")
            with open(p, "w") as fh:
                json.dump(m, fh)
            rows, txt = captured(cut.main, [p, "--strip", str(strip), "--comp-warp", "0", "--comp-weft", "0",
                                            "--roll-width", "5000", "--out", os.path.join(tmp, f"g{strip}")])
            out[strip] = (rows, txt)
            self.assertIn("Assumptions:", txt)
            self.assertIn("Flattening strain distribution", txt)
        warn = CFm.get("fabrication.flatten_strain_warn_pct")
        self.assertGreater(out[6][0][0]["flatten_strain_max_%"], warn)
        self.assertIn("WARNING: flattening strain", out[6][1])
        self.assertLess(max(r["flatten_strain_max_%"] for r in out[3][0]), warn)
        self.assertNotIn("WARNING: flattening strain", out[3][1])
        # area error column = flat vs 3D area before compensation; bounded by twice the max strain
        for r in out[6][0] + out[3][0]:
            self.assertLessEqual(abs(r["flatten_area_err_%"]), 2 * r["flatten_strain_max_%"])
            self.assertLessEqual(r["flatten_strain_p95_%"], r["flatten_strain_max_%"] + 1e-9)


CFm = load("tensile-structures", "factors")


# ============================================================ 2. compensation, decompensation, allowances
def flat_panel(L=6.0, W=2.0, nu=4, nv=12):
    m = grid_model(lambda i, j: (W * i / nu, L * j / nv, 0.0), nu, nv)
    pans, _, _ = cut.build_panels(m, mm(m), "v", nu, "grid", None)
    return m, pans[0]


def columns_by_x(net, tol=1e-6):
    """group net points by x -> {x: (ymin, ymax)} (stations of a rectangle panel)."""
    out = {}
    for x, y in net:
        key = next((k for k in out if abs(k - x) < tol), x)
        lo, hi = out.get(key, (math.inf, -math.inf))
        out[key] = (min(lo, y), max(hi, y))
    return dict(sorted(out.items()))


class TestCompensation(unittest.TestCase):
    """Hand calculations (compensation = shrink factor (1 - c), see reference/patterning.md section 4)."""

    def test_uniform_compensation_hand_calc(self):
        # 6000 x 2000 mm flat panel, warp 1.5 %, weft 0.8 %:
        # L = 6000 * 0.985 = 5910.000 mm, W = 2000 * 0.992 = 1984.000 mm, A = 11.725440 m2
        _, pan = flat_panel()
        net, kinds, emax, *_ = cut.process_panel(pan, 0.015, 0.008, None, None, 0.0)
        xs, ys = [p[0] for p in net], [p[1] for p in net]
        self.assertAlmostEqual(max(xs) - min(xs), 5910.0, delta=1e-6)
        self.assertAlmostEqual(max(ys) - min(ys), 1984.0, delta=1e-6)
        self.assertAlmostEqual(abs(cut.area(net)) / 1e6, 11.725440, delta=1e-9)

    def test_end_decompensation_hand_calc(self):
        # weft decompensated to 0 % at both ends over 1500 mm: c(d) = 0.8 % * min(1, d / 1500)
        # stations every 500 mm: d = 0, 500, 1000, 1500.. -> widths 2000.000, 1994.667, 1989.333, 1984.000
        _, pan = flat_panel()
        net, *_ = cut.process_panel(pan, 0.015, 0.008, 0.0, None, 1500.0)
        cols = columns_by_x(net)
        self.assertEqual(len(cols), 13)
        xs = list(cols)
        for s, x in enumerate(xs):
            self.assertAlmostEqual(x - xs[0], 500.0 * s * 0.985, delta=1e-6)    # warp unchanged by weft decomp
            d = min(500.0 * s, 6000.0 - 500.0 * s)
            w_hand = 2000.0 * (1 - 0.008 * min(1.0, d / 1500.0))
            self.assertAlmostEqual(cols[x][1] - cols[x][0], w_hand, delta=1e-6, msg=f"station {s}")

    def test_side_decompensation_hand_calc(self):
        # warp decompensated to 0 % on both boundary sides over 1000 mm; columns at w = 0, 500, .., 2000 mm:
        # c(w) = 1.5 % * min(1, min(w, 2000 - w) / 1000) -> lengths 6000, 5955, 5910, 5955, 6000 mm
        _, pan = flat_panel()
        self.assertFalse(pan["left_seam"] or pan["right_seam"])
        net, kinds, *_ = cut.process_panel(pan, 0.015, 0.008, None, 0.0, 1000.0)
        # end-row vertices carry one point per column at each end; pair them by y
        e0 = [net[i] for i in range(len(net)) if kinds[i] == "end0"] + \
             [net[(i + 1) % len(net)] for i in range(len(net)) if kinds[i] == "end0"]
        e1 = [net[i] for i in range(len(net)) if kinds[i] == "end1"] + \
             [net[(i + 1) % len(net)] for i in range(len(net)) if kinds[i] == "end1"]
        e0 = sorted(set(e0), key=lambda p: p[1])
        e1 = sorted(set(e1), key=lambda p: p[1])
        self.assertEqual(len(e0), 5)
        lengths = [abs(b[0] - a[0]) for a, b in zip(e0, e1)]
        for got, hand in zip(lengths, (6000.0, 5955.0, 5910.0, 5955.0, 6000.0)):
            self.assertAlmostEqual(got, hand, delta=1e-6)


class TestAllowanceOffset(unittest.TestCase):
    """Exact offset geometry: parallel lines at the allowance; mitre corners = line intersections; a triangle
    offset uniformly by d is the similar triangle scaled about the incentre by (r + d) / r (r = inradius).
    Bevel at a convex corner of angle theta beyond the mitre limit m*d: the removed tip is a triangle of area
    (d / sin(theta/2) - m d)^2 * tan(theta/2)."""

    def test_rectangle_mixed_allowances(self):
        L, W = 5910.0, 1984.0
        net = [(0, 0), (L, 0), (L, W), (0, W)]                  # CCW; edges: bottom, right, top, left
        cutp = cut.offset_polygon(net, [80.0, 50.0, 80.0, 50.0])
        exact = [(-50.0, -80.0), (L + 50.0, -80.0), (L + 50.0, W + 80.0), (-50.0, W + 80.0)]
        for p, q in zip(cutp, exact):
            self.assertLess(math.dist(p, q), 1e-9)
        self.assertAlmostEqual(shoelace(cutp), (L + 100) * (W + 160), delta=1e-6)

    def test_triangle_uniform_offset_is_scaled_about_incentre(self):
        for tri in ([(0, 0), (3000, 0), (0, 4000)], [(0, 0), (2000, 0), (1000, 1000 * math.sqrt(3))]):
            a = math.dist(tri[1], tri[2])
            b = math.dist(tri[0], tri[2])
            c = math.dist(tri[0], tri[1])
            per = a + b + c
            inc = ((a * tri[0][0] + b * tri[1][0] + c * tri[2][0]) / per, (a * tri[0][1] + b * tri[1][1] + c * tri[2][1]) / per)
            r = 2 * abs(shoelace(tri)) / per
            d = 60.0
            out = cut.offset_polygon(tri, [d] * 3)
            self.assertEqual(len(out), 3)                       # no bevel (all angles >= 30 deg)
            k = (r + d) / r
            for p, v in zip(out, tri):
                ex = (inc[0] + k * (v[0] - inc[0]), inc[1] + k * (v[1] - inc[1]))
                self.assertLess(math.dist(p, ex), 1e-6)
            for i in range(3):                                   # cut vertex i lies at d from the lines of edges i-1, i
                for e0, e1 in ((tri[i - 1], tri[i]), (tri[i], tri[(i + 1) % 3])):
                    dist = abs((e1[0] - e0[0]) * (out[i][1] - e0[1]) - (e1[1] - e0[1]) * (out[i][0] - e0[0])) \
                        / math.dist(e0, e1)
                    self.assertAlmostEqual(dist, d, delta=1e-6)

    def test_sharp_corner_bevel_keeps_full_allowance(self):
        theta = math.radians(20.0)                               # mitre = d / sin(10 deg) = 5.76 d > 4 d -> bevel
        tri = [(0, 0), (3000, -3000 * math.tan(theta / 2)), (3000, 3000 * math.tan(theta / 2))]
        d = 50.0
        out = cut.offset_polygon(tri, [d] * 3)
        self.assertEqual(len(out), 4)                            # bevelled apex = two vertices
        self.assertGreaterEqual(boundary_distance(out, tri), d - 1e-6)   # never inside the allowance
        for p in tri:
            self.assertTrue(pip(p, out))
        # area = mitred offset - removed tip
        mit = cut.offset_polygon(tri, [d] * 3, miter_limit=1e9)
        tip = (d / math.sin(theta / 2) - 4 * d) ** 2 * math.tan(theta / 2)
        self.assertAlmostEqual(abs(shoelace(mit)) - abs(shoelace(out)), tip, delta=1e-6)
        # bevel vertices lie 4 d from the corner, measured along the bisector
        for p in out[:2]:
            self.assertAlmostEqual(p[0] - 0.0, -4 * d, delta=1e-6)

    def test_reflex_corner_is_exact_intersection(self):
        L = [(0, 0), (2000, 0), (2000, 1000), (1000, 1000), (1000, 2000), (0, 2000)]   # L-shape, reflex at (1000,1000)
        out = cut.offset_polygon(L, [50.0] * 6)
        self.assertEqual(len(out), 6)
        self.assertLess(math.dist(out[3], (1050.0, 1050.0)), 1e-9)
        self.assertGreaterEqual(boundary_distance(out, L), 50.0 - 1e-9)

    def test_main_cut_outline_and_dxf_round_trip(self):
        # flat 4 m x 6 m model, two panels (strip 2): panel = 6000 x 2000 net before compensation;
        # cut = net + 80 mm edge allowance on boundary sides and ends, 50 mm on the seam side
        tmp = tempfile.mkdtemp()
        m = grid_model(lambda i, j: (4.0 * i / 4, 6.0 * j / 12, 0.0), 4, 12)
        p = os.path.join(tmp, "flat.json")
        with open(p, "w") as fh:
            json.dump(m, fh)
        out = os.path.join(tmp, "pat")
        rows = quiet(cut.main, [p, "--strip", "2", "--comp-warp", "1.5", "--comp-weft", "0.8", "--seam", "50",
                                "--edge", "80", "--out", out, "--sheets", "--project", "TEST-PRJ"])
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertEqual(r["length_mm"], round(5910 + 160))
            self.assertEqual(r["width_mm"], round(1984 + 80 + 50))
            self.assertAlmostEqual(r["net_area_m2"], 11.725, delta=0.001)
            self.assertAlmostEqual(r["cut_area_m2"], (5910 + 160) * (1984 + 130) / 1e6, delta=0.001)
        with open(out + ".json") as fh:
            data = json.load(fh)
        doc = rdr.read(out + ".dxf", units_mm=True)
        self.assertEqual(doc.header_value("$ACADVER"), "AC1009")
        cuts, nets = doc.polylines("CUT"), doc.polylines("NET")
        self.assertEqual(len(cuts), len(data["panels"]))
        self.assertEqual(len(nets), len(data["panels"]))
        for pl, pn, pc in zip(data["panels"], cuts, nets):
            self.assertTrue(pn["closed"] and pc["closed"])
            for src, ent in ((pl["cut"], pn), (pl["net"], pc)):
                self.assertEqual(len(src), len(ent["pts"]))
                err = max(math.dist((x + pl["x_offset_in_dxf"], y), q[:2]) for (x, y), q in zip(src, ent["pts"]))
                self.assertLess(err, 1e-5)
            self.assertIn(pl["panel"], doc.texts("TEXT"))
        sheet = rdr.read(out + "_P01.dxf", units_mm=True)
        t = sheet.texts("TITLE")
        for key in ("PROJECT:", "PANEL:", "MATERIAL:", "DWG No:", "REV:", "SCALE:", "COMP:", "NET AREA:"):
            self.assertIn(key, t)
        self.assertIn("TEST-PRJ", t)
        self.assertIn("w 1.5% / f 0.8%", t)


# ============================================================ 3. DXF reader / validator and round trips
class TestDXFReader(unittest.TestCase):
    """The reader enforces the Autodesk DXF Reference (Group Code Value Types; HEADER $ACADVER group 1,
    $INSUNITS group 70 with 4 = Millimeters; LAYER table entries; POLYLINE/VERTEX/SEQEND)."""

    def base(self):
        d = dxfw.DXF()
        d.layer("CUT", "red")
        d.polyline([(0, 0), (10, 0), (10, 5)], "CUT", closed=True)
        d.text("A", (1, 1), 2, "CUT", align_center=True)
        return d.tostring()

    def test_valid_file_parses(self):
        doc = rdr.parse(self.base())
        self.assertEqual(doc.header_value("$INSUNITS"), 4)
        self.assertEqual(doc.sections, ["HEADER", "TABLES", "ENTITIES"])
        pl = doc.polylines("CUT")[0]
        self.assertTrue(pl["closed"])
        self.assertEqual([p[:2] for p in pl["pts"]], [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)])
        self.assertEqual(doc.texts(), ["A"])

    def test_rejects_malformed(self):
        good = self.base()
        bad = {
            "no EOF": good.replace("0\nEOF\n", ""),
            "odd lines": good + "0\n",
            "bad float": good.replace("10\n10\n", "10\nten\n", 1),
            "undefined layer": good.replace("8\nCUT\n", "8\nNOPE\n", 1),
            "vertex outside polyline": good.replace("0\nPOLYLINE", "0\nVERTEX\n8\nCUT\n10\n0\n20\n0\n0\nPOLYLINE", 1),
            "no ENDSEC": good.replace("0\nENDSEC\n0\nEOF", "0\nEOF"),
            "no ACADVER": good.replace("9\n$ACADVER\n1\nAC1009\n", ""),
            "polyline without 66": good.replace("66\n1\n", "", 1),
            "unknown section": good.replace("2\nENTITIES", "2\nENTITYS"),
            "int expected": good.replace("70\n1\n", "70\n1.5\n", 1),
        }
        for name, txt in bad.items():
            with self.assertRaises(rdr.DXFError, msg=name):
                rdr.parse(txt)

    def test_cli_validates_and_prints_assumptions(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "a.dxf")
        with open(p, "w", newline="\r\n") as fh:
            fh.write(self.base())
        _, txt = captured(rdr.main, [p, "--units-mm"])
        self.assertIn("Assumptions:", txt)
        self.assertIn("OK", txt)

    def test_optional_ezdxf_cross_check(self):
        try:
            import ezdxf  # noqa: F401  (optional independent parser; never a dependency of the tools)
        except ImportError:
            self.skipTest("ezdxf not installed")
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "a.dxf")
        d = dxfw.DXF()
        d.layer("CUT", "red")
        d.polyline([(0, 0), (10, 0), (10, 5)], "CUT", closed=True)
        d.circle((3, 3), 2, "CUT")
        d.save(p)
        doc = ezdxf.readfile(p)
        self.assertEqual(len(doc.audit().errors), 0)
        self.assertEqual(doc.header.get("$INSUNITS"), 4)
        mine = rdr.read(p)
        pl = [e for e in doc.modelspace() if e.dxftype() == "POLYLINE"][0]
        self.assertEqual([tuple(v.dxf.location) for v in pl.vertices], mine.polylines("CUT")[0]["pts"])
        self.assertEqual(pl.is_closed, mine.polylines("CUT")[0]["closed"])


class TestGARoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = os.path.join(self.tmp, "sail")
        quiet(fdm.main, ["sail4", "--n", "10", "--prestress", "2", "--out", self.p])
        with open(self.p + ".json") as fh:
            self.m = json.load(fh)
        self.X = mm(self.m)

    def test_ga_dxf_coordinates_and_cable_schedule_vs_model(self):
        out = os.path.join(self.tmp, "ga")
        res, txt = captured(ga.main, [self.p + ".json", "--forces", "--csv", "--out", out])
        self.assertIn("Assumptions:", txt)
        doc = rdr.read(out + ".dxf", units_mm=True)
        mem = [e for e in self.m["edges"] if e["kind"] == "membrane"]
        lines = doc.of("LINE", "MEMBRANE-MESH")
        self.assertEqual(len(lines), len(mem))
        for e, ln in zip(mem, lines):
            self.assertLess(math.dist(ln["p"], self.X[e["n"][0]]), 1e-5)
            self.assertLess(math.dist(ln["q"], self.X[e["n"][1]]), 1e-5)
        # cable groups: polyline length = sum of the model segment lengths (computed here from xyz)
        groups = {}
        for e in self.m["edges"]:
            if e.get("group"):
                groups.setdefault(e["group"], []).append(e)
        polys = doc.polylines("EDGE-CABLE")
        self.assertEqual(len(polys), len(groups))
        L_model = {g: sum(math.dist(self.X[e["n"][0]], self.X[e["n"][1]]) for e in es) for g, es in groups.items()}
        L_dxf = sorted(sum(math.dist(p["pts"][i - 1], p["pts"][i]) for i in range(1, len(p["pts"]))) for p in polys)
        for a, b in zip(L_dxf, sorted(L_model.values())):
            self.assertAlmostEqual(a, b, delta=1e-4)
        for p in polys:
            self.assertTrue(p["three_d"])
        # supports: circles at the fixed nodes
        fixed = [self.X[i] for i, nd in enumerate(self.m["nodes"]) if nd.get("fixed")]
        circ = doc.of("CIRCLE", "SUPPORT")
        self.assertEqual(len(circ), len(fixed))
        for c in circ:
            self.assertLess(min(math.dist(c["p"], f) for f in fixed), 1e-5)
        # cable CSV vs model, and vs cable_schedule.py --from-model (quantities and lengths)
        with open(out + "_cables.csv") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual({r["group"] for r in rows}, set(groups))
        for r in rows:
            self.assertAlmostEqual(float(r["L_node_stressed_mm"]), L_model[r["group"]], delta=0.06)
            self.assertEqual(int(r["segments"]), len(groups[r["group"]]))
        s = sched.from_model(self.p + ".json", "Ronstan-ACS2-GS-20.1", 3.0, 1.5, 0)
        self.assertEqual(len(s["cables"]), len(groups))
        for c in s["cables"]:
            self.assertAlmostEqual(c["L_stressed"] * 1000, L_model[c["id"]], delta=0.1)
        with open(out + "_setout.csv") as fh:
            so = list(csv.DictReader(fh))
        self.assertEqual(len(so), len(fixed))

    def test_closed_ring_and_branch(self):
        ring = [{"n": [i, (i + 1) % 6]} for i in range(6)]
        nodes, closed = ga.chain(ring)
        self.assertTrue(closed)
        self.assertEqual(sorted(nodes), list(range(6)))
        with self.assertRaises(ValueError):
            ga.chain([{"n": [0, 1]}, {"n": [1, 2]}, {"n": [1, 3]}])


class TestPanelSchedule(unittest.TestCase):
    def test_panel_quantities_and_lengths_vs_model(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "sail")
        quiet(fdm.main, ["sail4", "--n", "12", "--prestress", "2", "--out", p])
        with open(p + ".json") as fh:
            m = json.load(fh)
        X = mm(m)
        out = os.path.join(tmp, "pat")
        rows = quiet(cut.main, [p + ".json", "--strip", "3", "--comp-warp", "0", "--comp-weft", "0", "--out", out])
        g = m["grid"]
        self.assertEqual(len(rows), g["nu"] // 3)                          # quantity
        with open(out + ".csv") as fh:
            csv_rows = list(csv.DictReader(fh))
        self.assertEqual([r["panel"] for r in csv_rows], [r["panel"] for r in rows])
        ncol = g["nu"] + 1
        line_len = lambda i: sum(math.dist(X[(j - 1) * ncol + i], X[j * ncol + i]) for j in range(1, g["nv"] + 1))
        for k, r in enumerate(rows):                                        # seam lengths = model grid lines
            self.assertAlmostEqual(r["seam_left_3d_mm"], line_len(3 * k), delta=0.1)
            self.assertAlmostEqual(r["seam_right_3d_mm"], line_len(3 * k + 3), delta=0.1)
        # independent 3D area of the model faces (two triangles per quad, as split in the tool)
        def tri(a, b, c):
            u = [X[b][i] - X[a][i] for i in range(3)]
            v = [X[c][i] - X[a][i] for i in range(3)]
            return 0.5 * math.hypot(u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        A = sum(tri(f[0], f[1], f[2]) + tri(f[0], f[2], f[3]) for f in m["faces"]) / 1e6
        self.assertAlmostEqual(sum(r["area_3d_m2"] for r in rows), A, delta=1e-3)
        smax = max(r["flatten_strain_max_%"] for r in rows) / 100
        self.assertLess(abs(sum(r["net_area_m2"] for r in rows) - A) / A, 2 * smax + 1e-4)
        # mating seams: compensated (here uncompensated) seam lengths on both panels agree
        for a_, b_ in zip(rows[:-1], rows[1:]):
            self.assertAlmostEqual(a_["seam_right_net_mm"], b_["seam_left_net_mm"],
                                   delta=a_["seam_right_net_mm"] * (2 * smax + 1e-6))


# ============================================================ 4. nesting
class TestNesting(unittest.TestCase):
    def rect(self, name, L, W):
        return {"panel": name, "cut": [(0, 0), (L, 0), (L, W), (0, W)], "L": L, "W": W, "net_area_m2": L * W / 1e6}

    def independent_check(self, placed, W, gap):
        for q in placed:
            ys = [y for _, y in q["poly"]]
            self.assertGreaterEqual(min(ys), -1e-9)
            self.assertLessEqual(max(ys), W + 1e-9)
        for i, a in enumerate(placed):
            for b in placed[i + 1:]:
                self.assertFalse(pip(a["poly"][0], b["poly"]) or pip(b["poly"][0], a["poly"]))
                self.assertGreaterEqual(boundary_distance(a["poly"], b["poly"]), gap - 1e-6,
                                        (a["panel"], b["panel"]))

    def test_known_optimum_rectangles(self):
        # 4 panels 3000 x 1240 mm, roll 2500 mm, gap 20: exactly two fit across (1240 + 20 + 1240 = 2500),
        # so the optimum roll length is 3000 + 20 + 3000 = 6020 mm (raster rounds the second start to 3025)
        panels = [self.rect(f"R{k}", 3000.0, 1240.0) for k in range(4)]
        placed, length = nestm.nest(panels, 2500.0, 25.0, 20.0)
        self.independent_check(placed, 2500.0, 20.0)
        self.assertGreaterEqual(length, 6020.0)
        self.assertLessEqual(length, 6020.0 + 25.0)
        util = sum(abs(shoelace(q["poly"])) for q in placed) / (2500.0 * length)
        self.assertGreater(util, 4 * 3000 * 1240 / (2500 * 6045) - 1e-9)    # >= 98.4 %

    def test_clearance_along_the_roll(self):
        # only one 2400-wide panel fits across a 2500 roll: panels follow each other along the roll and must
        # keep the gap in x too (length 1000 is an exact raster multiple, the worst case)
        panels = [self.rect("A", 1000.0, 2400.0), self.rect("B", 1000.0, 2400.0)]
        placed, length = nestm.nest(panels, 2500.0, 25.0, 20.0)
        self.independent_check(placed, 2500.0, 20.0)
        self.assertGreaterEqual(length, 2020.0)
        clear, margin, bad = nestm.verify(placed, 2500.0, 20.0)
        self.assertGreaterEqual(clear, 20.0)
        self.assertEqual(bad, [])

    def test_real_patterns_and_verify_detects_overlap(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "mb")
        quiet(fdm.main, ["multibay", "--bays", "2", "--qc", "3", "--prestress", "2", "--out", p])
        out = os.path.join(tmp, "pat")
        quiet(cut.main, [p + ".json", "--strip", "1", "--roll-width", "2670", "--auto-split", "--out", out])
        res, txt = captured(nestm.main, [out + ".json", "--gap", "20", "--out", os.path.join(tmp, "nest")])
        placed, length = res
        self.assertIn("Assumptions:", txt)
        self.assertIn("overlaps 0", txt)
        self.independent_check(placed, 2670.0, 20.0)
        # DXF round trip: nested CUT outlines = placed polygons, roll edges at y = 0 and y = W
        doc = rdr.read(os.path.join(tmp, "nest.dxf"), units_mm=True)
        polys = doc.polylines("CUT")
        self.assertEqual(len(polys), len(placed))
        for q, pl in zip(placed, polys):
            self.assertLess(max(math.dist(a, b[:2]) for a, b in zip(q["poly"], pl["pts"])), 1e-5)
        ys = sorted({round(e["p"][1], 6) for e in doc.of("LINE", "ROLL")} | {round(e["q"][1], 6) for e in doc.of("LINE", "ROLL")})
        self.assertEqual(ys, [0.0, 2670.0])
        # utilisation printed = cut area / (roll width x length)
        cutA = sum(abs(shoelace(q["poly"])) for q in placed) / 1e6
        self.assertIn(f"Utilisation: cut area {cutA:.2f} m2", txt)
        # verify() must flag an overlapping layout
        a, b = placed[0], dict(placed[0], panel="COPY", poly=[(x + 5, y) for x, y in placed[0]["poly"]])
        clear, margin, bad = nestm.verify([a, b], 2670.0, 20.0)
        self.assertEqual(clear, 0.0)
        self.assertEqual(bad, [(a["panel"], "COPY")])


# ============================================================ 5. steel part drawings
class TestSteelParts(unittest.TestCase):
    def run_part(self, args):
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "part")
        res, txt = captured(spd.main, args + ["--out", out, "--project", "PRJ-X", "--drawn", "AB", "--checked", "CD"])
        return res, txt, rdr.read(out + ".dxf", units_mm=True)

    def outline_and_holes(self, doc):
        out = doc.polylines("OUTLINE")
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["closed"])
        return [p[:2] for p in out[0]["pts"]], doc.of("CIRCLE", "HOLES")

    def test_lug_outline_hole_and_edge_distances(self):
        # EN 1993-1-8 Table 3.9 type A geometry: end distance a beyond the hole, side distance c beside it
        d0, a_, c_, H, base, t = 41.0, 50.0, 35.0, 120.0, 160.0, 20.0
        res, txt, doc = self.run_part(["lug", "--d0", "41", "--d", "40", "--t", "20", "--a", "50", "--c", "35",
                                       "--base", "160", "--height", "120", "--mark", "LP-01", "--qty", "4"])
        self.assertIn("Assumptions:", txt)
        outline, holes = self.outline_and_holes(doc)
        self.assertEqual(len(holes), 1)
        self.assertLess(math.dist(holes[0]["p"][:2], (0.0, H)), 1e-9)
        self.assertAlmostEqual(holes[0]["r"], d0 / 2, places=9)
        R = c_ + d0 / 2
        ys = [p[1] for p in outline]
        xs = [p[0] for p in outline]
        self.assertAlmostEqual(max(ys) - (H + d0 / 2), a_, delta=1e-6)            # end distance in the DXF
        self.assertAlmostEqual(min(ys), 0.0, delta=1e-9)
        self.assertAlmostEqual(max(xs) - min(xs), base, delta=1e-6)
        clear = min(seg_pt((0.0, H), outline[i - 1], outline[i]) for i in range(len(outline))) - d0 / 2
        self.assertGreaterEqual(clear, min(a_, c_) - 1e-6)                       # never less than specified
        self.assertLess(clear, min(a_, c_) + 0.05)                               # and tight (circumscribed chords)
        # mass: exact semi-ellipse head + trapezoid flanks (closed form) - hole, t, 7850 kg/m3
        k = (a_ + d0 / 2) / R
        A = base * H * 0.5 + 0.5 * (base + 2 * R) * (H * 0.5) + 0.5 * math.pi * R * (k * R) - math.pi * d0 ** 2 / 4
        self.assertAlmostEqual(res["mass_kg"], A * t * 7850e-9, delta=0.005 * res["mass_kg"])
        tb = doc.texts("TITLE")
        for key, val in (("PROJECT:", "PRJ-X"), ("PART:", "LUG PLATE LP-01"), ("DWG No:", "LP-01"), ("QTY:", "4"),
                         ("DRAWN:", "AB"), ("CHECKED:", "CD"), ("MATERIAL:", "S355J2+N  t=20"), ("UNITS:", "mm")):
            self.assertIn(key, tb)
            self.assertIn(val, tb)
        self.assertIn(f"{res['mass_kg']:.2f} kg each", tb)
        self.assertEqual(sum(1 for s in doc.texts("WELD") if s == "a8"), 2)     # ISO 2553 both-side fillet

    def test_corner_plate_holes_and_edge_distances(self):
        hl = [("A", 0, 0, 52), ("EC1", 180, 48, 33), ("EC2", 48, 180, 33), ("M1", 95, 95, 18)]
        edge = 45.0
        res, txt, doc = self.run_part(["corner", "--t", "25", "--edge", "45", "--mark", "CP-01"] +
                                      sum((["--hole", f"{n}:{x}:{y}:{d}"] for n, x, y, d in hl), []))
        outline, holes = self.outline_and_holes(doc)
        self.assertEqual(len(holes), len(hl))
        for (n, x, y, dia), c in zip(hl, holes):
            self.assertLess(math.dist(c["p"][:2], (x, y)), 1e-9)
            self.assertAlmostEqual(c["r"], dia / 2, places=9)
            e = min(seg_pt((x, y), outline[i - 1], outline[i]) for i in range(len(outline))) - dia / 2
            self.assertGreaterEqual(e, edge - 1e-6, n)                            # >= specified edge distance
            if n != "M1":                                                         # hull-defining holes: tight
                self.assertLess(e, edge + 0.05, n)
            self.assertTrue(pip((x, y), outline))
        # convexity (outline = convex hull)
        n = len(outline)
        sgn = [((outline[(i + 1) % n][0] - outline[i][0]) * (outline[(i + 2) % n][1] - outline[(i + 1) % n][1]) -
                (outline[(i + 1) % n][1] - outline[i][1]) * (outline[(i + 2) % n][0] - outline[(i + 1) % n][0]))
               for i in range(n)]
        self.assertTrue(all(s >= -1e-9 for s in sgn) or all(s <= 1e-9 for s in sgn))
        # hole table rows: distance from the anchor
        txts = doc.texts("TEXT")
        self.assertTrue(any(t.startswith("EC1") and f"{math.hypot(180, 48):7.1f}".strip() in t for t in txts))
        tb = doc.texts("TITLE")
        self.assertIn("CORNER PLATE CP-01", tb)
        self.assertIn("EXC2", tb)


if __name__ == "__main__":
    unittest.main()
