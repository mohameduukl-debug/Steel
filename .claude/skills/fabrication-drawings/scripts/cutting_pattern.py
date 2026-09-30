#!/usr/bin/env python3
"""Cutting patterns (patterning) from a form-found membrane mesh -> DXF + CSV.

Pure-Python. Reads the grid mesh JSON from form_find_fdm.py (any model with
"grid" + "nodes[].grid" indices), splits the surface into panels, flattens every
panel, applies compensation (+ graded decompensation), adds seam / edge
allowances and writes plotter-ready DXF and a panel schedule CSV.

Seam modes (--seams)
  grid      seams follow mesh grid lines (fast; good when the mesh lines are
            already close to geodesics)
  geodesic  each seam is relaxed ON THE SURFACE into the shortest path between
            its two boundary end points (string-shortening with closest-point
            projection onto the triangulated surface). Neighbouring panels share
            the same 3D seam curve, so mating seam lengths match. Panel interiors
            are rebuilt as a ladder of rungs projected onto the surface.

Pipeline (per panel)
  1. structured panel grid (stations along the panel × rungs across)
  2. flatten: unfold triangle-by-triangle + least-squares edge-length relaxation;
     residual strain reported (> ~0.5 % -> narrower panels)
  3. orient: warp = panel long axis (principal axis) -> DXF x
  4. compensate: warp cw %, weft cf % (biaxial tests of the batch, EN 17117-2)
  5. DECOMPENSATE (optional): at the panel ends (edge cables / clamp lines of
     fixed length) the weft compensation grades linearly from cf to
     --decomp-ends over --decomp-length; along boundary SIDES (not seams) the
     warp compensation grades to --decomp-sides the same way
  6. offset: seam allowance on seams, edge allowance on boundaries -> CUT line

DXF layers:  CUT (red) cutting line incl. allowances, NET (cyan) compensated
net/seam line, TEXT (green), WARP (yellow) warp arrow, DIM (grey) chord dims.

Examples
  python3 cutting_pattern.py sail.json --strip 2 --comp-warp 0.8 --comp-weft 1.6 --out pat
  python3 cutting_pattern.py sail.json --seams geodesic --strip 2 --comp-warp 0.8 --comp-weft 1.6 \
      --decomp-ends 0.0 --decomp-length 500 --out pat_geo
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxf_writer import DXF  # noqa: E402


def d3(a, b):
    return math.dist(a, b)


def d2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def lerp(a, b, t):
    return [a[k] + (b[k] - a[k]) * t for k in range(len(a))]


def place_third(pa, pb, la, lb, side=1.0):
    """2D point at distance la from pa and lb from pb (side selects the solution)."""
    L = d2(pa, pb)
    x = (la * la - lb * lb + L * L) / (2 * L)
    h = math.sqrt(max(la * la - x * x, 0.0))
    ux, uy = (pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L
    return [pa[0] + x * ux - side * h * uy, pa[1] + x * uy + side * h * ux]


# ------------------------------------------------------------- flattening
def flatten(quads, X, iters=400):
    """Flatten a set of quads (4-node index tuples into X). Returns 2D dict, max and RMS strain."""
    verts = sorted({v for q in quads for v in q})
    P: dict[int, list[float]] = {}
    edges = set()
    tris = []
    for q in quads:
        a, b, c, d = q
        tris += [(a, b, c), (a, c, d)]
        for u, v in ((a, b), (b, c), (c, d), (d, a), (a, c), (b, d)):
            edges.add((min(u, v), max(u, v)))
    edge_tris: dict[tuple[int, int], list[int]] = {}
    for k, t in enumerate(tris):
        for u, v in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edge_tris.setdefault((min(u, v), max(u, v)), []).append(k)
    a, b, c = tris[0]
    P[a] = [0.0, 0.0]
    P[b] = [d3(X[a], X[b]), 0.0]
    P[c] = place_third(P[a], P[b], d3(X[a], X[c]), d3(X[b], X[c]), 1.0)
    seen = {0}
    queue = [0]
    while queue:
        k = queue.pop(0)
        t = tris[k]
        for u, v in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            opp = next(x for x in t if x not in (u, v))
            for k2 in edge_tris[(min(u, v), max(u, v))]:
                if k2 in seen:
                    continue
                seen.add(k2)
                queue.append(k2)
                w = next(x for x in tris[k2] if x not in (u, v))
                if w in P:
                    continue

                def side(p):
                    return (P[v][0] - P[u][0]) * (p[1] - P[u][1]) - (P[v][1] - P[u][1]) * (p[0] - P[u][0])
                so = side(P[opp])
                cand = [place_third(P[u], P[v], d3(X[u], X[w]), d3(X[v], X[w]), sd) for sd in (1, -1)]
                P[w] = min(cand, key=lambda p: side(p) * so)
    L3 = {e: d3(X[e[0]], X[e[1]]) for e in edges}
    nbr: dict[int, list[tuple[int, float]]] = {v: [] for v in verts}
    for (u, v), L in L3.items():
        nbr[u].append((v, L))
        nbr[v].append((u, L))
    for _ in range(iters):
        for v in verts:
            sx = sy = 0.0
            for w, L in nbr[v]:
                dx, dy = P[v][0] - P[w][0], P[v][1] - P[w][1]
                cur = math.hypot(dx, dy) or 1e-12
                sx += P[w][0] + dx * L / cur
                sy += P[w][1] + dy * L / cur
            k = len(nbr[v])
            P[v] = [0.5 * P[v][0] + 0.5 * sx / k, 0.5 * P[v][1] + 0.5 * sy / k]
    strains = [(d2(P[u], P[v]) - L) / L for (u, v), L in L3.items() if L > 1e-9]
    rms = math.sqrt(sum(s * s for s in strains) / len(strains))
    return P, max(abs(s) for s in strains), rms


def principal_axis(pts):
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    return 0.5 * math.atan2(2 * sxy, sxx - syy), cx, cy


def offset_polygon(poly, dists):
    """Mitre offset of a CCW polygon; dists[i] = outward offset of edge i (poly[i]->poly[i+1])."""
    n = len(poly)
    lines = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1e-12
        nx, ny = dy / L, -dx / L
        o = dists[i]
        lines.append(((a[0] + nx * o, a[1] + ny * o), (dx, dy)))
    out = []
    for i in range(n):
        (p1, r1), (p2, r2) = lines[i - 1], lines[i]
        den = r1[0] * r2[1] - r1[1] * r2[0]
        if abs(den) < 1e-12:
            out.append(p2)
            continue
        t = ((p2[0] - p1[0]) * r2[1] - (p2[1] - p1[1]) * r2[0]) / den
        q = (p1[0] + t * r1[0], p1[1] + t * r1[1])
        corner = poly[i]
        lim = 4 * max(dists[i - 1], dists[i], 1e-9)
        dq = math.hypot(q[0] - corner[0], q[1] - corner[1])
        if dq > lim:
            q = (corner[0] + (q[0] - corner[0]) * lim / dq, corner[1] + (q[1] - corner[1]) * lim / dq)
        out.append(q)
    return out


def area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


# ------------------------------------------------------ surface projection
def closest_on_tri(p, a, b, c):
    """Ericson, Real-Time Collision Detection 5.1.5."""
    ab = [b[i] - a[i] for i in range(3)]
    ac = [c[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    dot = lambda u, v: u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
    d1, d2_ = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2_ <= 0:
        return list(a)
    bp = [p[i] - b[i] for i in range(3)]
    d3_, d4 = dot(ab, bp), dot(ac, bp)
    if d3_ >= 0 and d4 <= d3_:
        return list(b)
    vc = d1 * d4 - d3_ * d2_
    if vc <= 0 and d1 >= 0 and d3_ <= 0:
        v = d1 / (d1 - d3_)
        return [a[i] + v * ab[i] for i in range(3)]
    cp = [p[i] - c[i] for i in range(3)]
    d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return list(c)
    vb = d5 * d2_ - d1 * d6
    if vb <= 0 and d2_ >= 0 and d6 <= 0:
        w = d2_ / (d2_ - d6)
        return [a[i] + w * ac[i] for i in range(3)]
    va = d3_ * d6 - d5 * d4
    if va <= 0 and (d4 - d3_) >= 0 and (d5 - d6) >= 0:
        w = (d4 - d3_) / ((d4 - d3_) + (d5 - d6))
        return [b[i] + w * (c[i] - b[i]) for i in range(3)]
    den = 1.0 / (va + vb + vc)
    v, w = vb * den, vc * den
    return [a[i] + ab[i] * v + ac[i] * w for i in range(3)]


class Surface:
    """Triangulated surface with a uniform bin grid for closest-point queries."""

    def __init__(self, X, faces):
        self.X = X
        self.tris = []
        for f in faces:
            for k in range(1, len(f) - 1):
                self.tris.append((f[0], f[k], f[k + 1]))
        el = [d3(X[t[0]], X[t[1]]) for t in self.tris[:200]]
        self.h = 2.0 * (sum(el) / len(el))
        self.bins = defaultdict(list)
        for ti, t in enumerate(self.tris):
            lo = [min(X[v][k] for v in t) for k in range(3)]
            hi = [max(X[v][k] for v in t) for k in range(3)]
            for i in range(int(lo[0] // self.h), int(hi[0] // self.h) + 1):
                for j in range(int(lo[1] // self.h), int(hi[1] // self.h) + 1):
                    for k in range(int(lo[2] // self.h), int(hi[2] // self.h) + 1):
                        self.bins[(i, j, k)].append(ti)

    def project(self, p):
        c = [int(p[k] // self.h) for k in range(3)]
        for r in (1, 2, 4, 8):
            cand = set()
            for i in range(c[0] - r, c[0] + r + 1):
                for j in range(c[1] - r, c[1] + r + 1):
                    for k in range(c[2] - r, c[2] + r + 1):
                        cand.update(self.bins.get((i, j, k), ()))
            if cand:
                break
        else:
            cand = range(len(self.tris))
        best, bd = None, math.inf
        for ti in cand:
            t = self.tris[ti]
            q = closest_on_tri(p, self.X[t[0]], self.X[t[1]], self.X[t[2]])
            dd = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2
            if dd < bd:
                best, bd = q, dd
        return best


def resample(pts, n):
    """resample a 3D polyline to n points equally spaced by arc length."""
    s = [0.0]
    for i in range(1, len(pts)):
        s.append(s[-1] + d3(pts[i - 1], pts[i]))
    L = s[-1]
    out = []
    j = 0
    for k in range(n):
        t = L * k / (n - 1)
        while j < len(pts) - 2 and s[j + 1] < t:
            j += 1
        seg = (s[j + 1] - s[j]) or 1e-12
        out.append(lerp(pts[j], pts[j + 1], (t - s[j]) / seg))
    return out


def polylen(pts):
    return sum(d3(pts[i - 1], pts[i]) for i in range(1, len(pts)))


def geodesic(surf, pts, n, sweeps=200, tol=0.05):
    """Shorten a polyline on the surface with fixed end points (string relaxation + projection).

    Multi-level: relax on 5, 9, 17 … points, refining until n; each level converges in few sweeps
    because the coarse level already carries the long-wavelength shape. tol in model units (mm)."""
    m = 5
    P = resample(pts, m)
    while True:
        for it in range(sweeps):
            move = 0.0
            for i in range(1, m - 1):
                q = surf.project([(P[i - 1][k] + P[i + 1][k]) / 2 for k in range(3)])
                move = max(move, d3(q, P[i]))
                P[i] = q
            if move < tol:
                break
        if m >= n:
            break
        m = min(2 * m - 1, n)
        P = [surf.project(p) if 0 < i < m - 1 else p for i, p in enumerate(resample(P, m))]
    return resample(P, n)


# ------------------------------------------------------------ panel grids
def build_panels(model, X, along, strip, seams_mode, surf):
    """Return list of panels: dict(grid=[[3D]*ncross]*nstations, left_seam, right_seam)."""
    g = model["grid"]
    nu, nv, per = g["nu"], g["nv"], g.get("periodic_u", False)
    ncol = nu if per else nu + 1

    def P(i, j):
        return X[j * ncol + (i % nu if per else i)]

    if along == "v":  # panel length along v; seams are v-lines i = const
        n_across_lines = nu
        line = lambda i: [P(i, j) for j in range(nv + 1)]
        endrow = lambda a, b, end: [P(i, 0 if end == 0 else nv) for i in range(a, b + 1)]
        nlong = nv
    else:             # panel length along u; seams are u-lines j = const (periodic ignored)
        n_across_lines = nv
        line = lambda j: [P(i, j) for i in range(nu + 1)]
        endrow = lambda a, b, end: [P(0 if end == 0 else nu, j) for j in range(a, b + 1)]
        nlong = nu
        per = False
    cuts = list(range(0, n_across_lines, strip)) + ([n_across_lines] if not per else [])
    if per:
        cuts.append(n_across_lines)
    boundary_line = lambda k: (not per) and k in (0, n_across_lines)
    n_st = nlong + 1  # mesh density: finer sampling of a faceted mesh concentrates curvature at facet folds
    seam_curves = {}
    notes = []
    bnd = [] if per else [resample(line(0), 4 * n_st), resample(line(n_across_lines), 4 * n_st)]

    def min_dist_to_boundary(c):
        return min((d3(p, q) for p in c[1:-1] for b_ in bnd for q in b_), default=math.inf)

    for k in sorted(set(cuts)):
        pts = line(k)
        if seams_mode == "geodesic" and not boundary_line(k):
            geo = geodesic(surf, pts, n_st)
            grid_line = resample(pts, n_st)
            # a geodesic between end points near a concave (scalloped) edge runs into the edge:
            # reject it when it closes in on the boundary much more than the grid line does
            if bnd and min_dist_to_boundary(geo) < 0.5 * min_dist_to_boundary(grid_line):
                seam_curves[k] = grid_line
                notes.append(f"seam line {k}: geodesic rejected (runs into the curved boundary) -> grid line used")
            else:
                seam_curves[k] = geo
        elif seams_mode == "geodesic":
            seam_curves[k] = resample(pts, n_st)
        else:
            seam_curves[k] = pts
    if per:
        seam_curves[n_across_lines] = seam_curves[0]
    panels = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        A, B = seam_curves[a], seam_curves[b]
        if seams_mode == "grid":
            grid = [[(line(i)[st]) for i in range(a, b + 1)] for st in range(n_st)]
        else:
            n_x = (b - a) + 1
            ends = [resample(endrow(a, b, 0), n_x), resample(endrow(a, b, 1), n_x)]
            # deviation of each curved end row from its straight chord, blended into the rungs near that end
            dev = [[[e[t][c] - lerp(e[0], e[-1], t / (n_x - 1))[c] for c in range(3)] for t in range(n_x)] for e in ends]
            sA = [0.0]
            for st in range(1, n_st):
                sA.append(sA[-1] + d3(A[st - 1], A[st]))
            wid0, wid1 = max(d3(A[0], B[0]), 1e-9), max(d3(A[-1], B[-1]), 1e-9)
            grid = []
            for st in range(n_st):
                if st == 0 or st == n_st - 1:
                    grid.append(ends[0 if st == 0 else 1])
                    continue
                # blend each end's curvature over a distance equal to that end's own width,
                # scaled to the local panel width
                loc = d3(A[st], B[st])
                w0 = max(0.0, 1 - sA[st] / wid0) * loc / wid0
                w1 = max(0.0, 1 - (sA[-1] - sA[st]) / wid1) * loc / wid1
                row_ = [A[st]]
                for t in range(1, n_x - 1):
                    q = lerp(A[st], B[st], t / (n_x - 1))
                    q = [q[c] + w0 * dev[0][t][c] + w1 * dev[1][t][c] for c in range(3)]
                    row_.append(surf.project(q))
                grid.append(row_ + [B[st]])
        panels.append({"grid": grid, "left_seam": not boundary_line(a), "right_seam": not boundary_line(b),
                       "lines": (a, b)})
    return panels, seam_curves, notes


# ---------------------------------------------------------------- main
def process_panel(pan, cw, cf, dec_end, dec_side, dec_len):
    grid = pan["grid"]
    ns, nx = len(grid), len(grid[0])
    Xl = [p for row in grid for p in row]
    idx = lambda s, k: s * nx + k
    quads = [(idx(s, k), idx(s, k + 1), idx(s + 1, k + 1), idx(s + 1, k)) for s in range(ns - 1) for k in range(nx - 1)]
    P2, emax, erms = flatten(quads, Xl)
    th, cx, cy = principal_axis(list(P2.values()))
    c, s_ = math.cos(-th), math.sin(-th)
    R = {v: ((p[0] - cx) * c - (p[1] - cy) * s_, (p[0] - cx) * s_ + (p[1] - cy) * c) for v, p in P2.items()}
    # warp must run along the stations (panel length): if the station direction is y, rotate 90°
    first = R[idx(0, nx // 2)]
    last = R[idx(ns - 1, nx // 2)]
    if abs(last[1] - first[1]) > abs(last[0] - first[0]):
        R = {v: (p[1], -p[0]) for v, p in R.items()}
    # global compensation
    N = {v: [p[0] * (1 - cw), p[1] * (1 - cf)] for v, p in R.items()}
    # graded decompensation
    if dec_len > 0 and (dec_end is not None or dec_side is not None):
        centre = [grid[s][nx // 2] for s in range(ns)]
        sdist = [0.0]
        for s in range(1, ns):
            sdist.append(sdist[-1] + d3(centre[s - 1], centre[s]))
        Ltot = sdist[-1]
        if dec_end is not None:
            for s in range(ns):
                t = min(1.0, min(sdist[s], Ltot - sdist[s]) / dec_len)
                ceff = dec_end / 100 + (cf - dec_end / 100) * t
                f = (1 - ceff) / (1 - cf)
                m = N[idx(s, nx // 2)]
                for k in range(nx):
                    q = N[idx(s, k)]
                    N[idx(s, k)] = [m[0] + (q[0] - m[0]) * f, m[1] + (q[1] - m[1]) * f]
        if dec_side is not None and not (pan["left_seam"] and pan["right_seam"]):
            wdist = [0.0]
            mid = ns // 2
            for k in range(1, nx):
                wdist.append(wdist[-1] + d3(grid[mid][k - 1], grid[mid][k]))
            W = wdist[-1]
            for k in range(nx):
                dl = wdist[k] if not pan["left_seam"] else math.inf
                dr = (W - wdist[k]) if not pan["right_seam"] else math.inf
                t = min(1.0, min(dl, dr) / dec_len)
                ceff = dec_side / 100 + (cw - dec_side / 100) * t
                f = (1 - ceff) / (1 - cw)
                m = N[idx(ns // 2, k)]
                for s in range(ns):
                    q = N[idx(s, k)]
                    N[idx(s, k)] = [m[0] + (q[0] - m[0]) * f, m[1] + (q[1] - m[1]) * f]
    # boundary: end row 0 (k up), right side (s up), end row ns-1 (k down), left side (s down)
    ring = [idx(0, k) for k in range(nx)] + [idx(s, nx - 1) for s in range(1, ns)] + \
           [idx(ns - 1, k) for k in range(nx - 2, -1, -1)] + [idx(s, 0) for s in range(ns - 2, 0, -1)]
    kinds = ["end"] * (nx - 1) + ["right"] * (ns - 1) + ["end"] * (nx - 1) + ["left"] * (ns - 1)
    net = [tuple(N[v]) for v in ring]
    if area(net) < 0:
        net.reverse()
        kinds = kinds[::-1]
        kinds = kinds[1:] + kinds[:1]  # edge i = net[i] -> net[i+1] after reversal
    seam_len = {"left": 0.0, "right": 0.0}
    for side, k in (("left", 0), ("right", nx - 1)):
        seam_len[side] = polylen([grid[s][k] for s in range(ns)])
    return net, kinds, emax, erms, seam_len


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("--panels-along", choices=["u", "v"], default="v",
                    help="panel long direction (seam lines run this way)")
    ap.add_argument("--strip", type=int, default=2, help="mesh bays per panel width")
    ap.add_argument("--seams", choices=["grid", "geodesic"], default="grid")
    ap.add_argument("--comp-warp", type=float, default=1.0, help="warp compensation [%%]")
    ap.add_argument("--comp-weft", type=float, default=1.5, help="weft compensation [%%]")
    ap.add_argument("--decomp-ends", type=float, default=None,
                    help="weft compensation at panel ends (fixed-length boundaries) [%%], e.g. 0")
    ap.add_argument("--decomp-sides", type=float, default=None,
                    help="warp compensation along boundary sides (not seams) [%%]")
    ap.add_argument("--decomp-length", type=float, default=500.0, help="transition length [mm]")
    ap.add_argument("--seam", type=float, default=50.0, help="seam allowance (overlap width) [mm]")
    ap.add_argument("--edge", type=float, default=80.0, help="edge allowance for pocket/hem [mm]")
    ap.add_argument("--roll-width", type=float, default=2500.0, help="usable fabric roll width [mm]")
    ap.add_argument("--scale", type=float, default=1000.0, help="model length unit -> mm (m->mm = 1000)")
    ap.add_argument("--prefix", default="P")
    ap.add_argument("--out", default="patterns")
    a = ap.parse_args(argv)

    with open(a.model) as fh:
        model = json.load(fh)
    if "grid" not in model:
        sys.exit("model needs a structured grid (use form_find_fdm.py output)")
    X = [[c * a.scale for c in nd["xyz"]] for nd in model["nodes"]]
    surf = Surface(X, model["faces"]) if a.seams == "geodesic" else None
    panels, seam_curves, notes = build_panels(model, X, a.panels_along, a.strip, a.seams, surf)
    cw, cf = a.comp_warp / 100, a.comp_weft / 100

    dxf = DXF()
    for ly, col in (("CUT", "red"), ("NET", "cyan"), ("TEXT", "green"), ("WARP", "yellow"), ("DIM", "grey")):
        dxf.layer(ly, col)
    rows = []
    xoff = 0.0
    for k, pan in enumerate(panels, 1):
        pid = f"{a.prefix}{k:02d}"
        net, kinds, emax, erms, seam_len = process_panel(pan, cw, cf, a.decomp_ends, a.decomp_sides, a.decomp_length)
        dists = [a.seam if (kd == "left" and pan["left_seam"]) or (kd == "right" and pan["right_seam"]) else a.edge
                 for kd in kinds]
        cut = offset_polygon(net, dists)
        minx = min(p[0] for p in cut)
        miny = min(p[1] for p in cut)
        maxx = max(p[0] for p in cut)
        maxy = max(p[1] for p in cut)
        sh = lambda p: (p[0] - minx + xoff, p[1] - miny)
        dxf.polyline([sh(p) for p in cut], "CUT", closed=True)
        dxf.polyline([sh(p) for p in net], "NET", closed=True)
        L, W = maxx - minx, maxy - miny
        mid = sh(((minx + maxx) / 2, (miny + maxy) / 2))
        h = max(min(W / 12, 120), 20)
        dxf.text(pid, (mid[0], mid[1] + h), h, "TEXT", align_center=True)
        note = f"cw {a.comp_warp}% cf {a.comp_weft}%"
        if a.decomp_ends is not None:
            note += f" | ends {a.decomp_ends}%/{a.decomp_length:g}mm"
        if a.decomp_sides is not None:
            note += f" | sides {a.decomp_sides}%"
        dxf.text(note, (mid[0], mid[1] - 0.8 * h), 0.4 * h, "TEXT", align_center=True)
        dxf.arrow((mid[0] - L / 4, mid[1] - 2 * h), (mid[0] + L / 4, mid[1] - 2 * h), h / 2, "WARP")
        dxf.text("WARP", (mid[0], mid[1] - 2.6 * h), 0.4 * h, "WARP", align_center=True)
        net_area = abs(area(net)) / 1e6
        rows.append({"panel": pid, "length_mm": round(L), "width_mm": round(W),
                     "fits_roll": W <= a.roll_width, "net_area_m2": round(net_area, 3),
                     "cut_area_m2": round(abs(area(cut)) / 1e6, 3), "bbox_area_m2": round(L * W / 1e6, 3),
                     "flatten_strain_max_%": round(emax * 100, 3), "flatten_strain_rms_%": round(erms * 100, 3),
                     "seam_left_3d_mm": round(seam_len["left"], 1), "seam_right_3d_mm": round(seam_len["right"], 1),
                     "left": "seam" if pan["left_seam"] else "boundary",
                     "right": "seam" if pan["right_seam"] else "boundary"})
        xoff += L + 300
    dxf.save(a.out + ".dxf")
    with open(a.out + ".csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"Seams: {a.seams}")
    print(f"{'panel':<7}{'L[mm]':>8}{'W[mm]':>7}{'roll':>6}{'net m2':>8}{'cut m2':>8}{'strain max%':>12}"
          f"{'seamL 3D':>10}{'seamR 3D':>10}")
    for r in rows:
        print(f"{r['panel']:<7}{r['length_mm']:8d}{r['width_mm']:7d}{'ok' if r['fits_roll'] else 'NO':>6}"
              f"{r['net_area_m2']:8.2f}{r['cut_area_m2']:8.2f}{r['flatten_strain_max_%']:12.3f}"
              f"{r['seam_left_3d_mm']:10.0f}{r['seam_right_3d_mm']:10.0f}")
    tot_net = sum(r["net_area_m2"] for r in rows)
    tot_bb = sum(r["bbox_area_m2"] for r in rows)
    print(f"Total net {tot_net:.2f} m2, fabric consumed (bounding boxes) {tot_bb:.2f} m2, "
          f"un-nested waste ~{(1 - tot_net / tot_bb) * 100:.0f}% (nesting on the roll reduces this)")
    if a.seams == "geodesic":
        gl = [polylen(c) for k, c in seam_curves.items()]
        print(f"Geodesic seams: {len(seam_curves)} lines, lengths {min(gl):.0f}–{max(gl):.0f} mm")
        for n_ in notes:
            print("  NOTE:", n_)
    if any(not r["fits_roll"] for r in rows):
        print("WARNING: some panels exceed the roll width -> reduce --strip")
    if any(r["flatten_strain_max_%"] > 0.5 for r in rows):
        print("WARNING: flattening strain > 0.5% -> panels too wide for this curvature; reduce --strip")
    print(f"Wrote {a.out}.dxf and {a.out}.csv")
    return rows


if __name__ == "__main__":
    main(sys.argv[1:])
