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
     residual strain reported (max, RMS, p95, distribution) and flat-vs-3D area error;
     warning above the register threshold fabrication.flatten_strain_warn_pct (0.5 % [U])
     -> narrower panels. Exact for developable panels (cone, cylinder; see reference/validation.md)
  3. orient: warp = panel long axis (principal axis) -> DXF x
  4. compensate: warp cw %, weft cf % (biaxial tests of the batch, EN 17117-2)
  5. DECOMPENSATE (optional): at the panel ends (edge cables / clamp lines of
     fixed length) the weft compensation grades linearly from cf to
     --decomp-ends over --decomp-length; along boundary SIDES (not seams) the
     warp compensation grades to --decomp-sides the same way
  6. offset: seam allowance on seams, edge allowance on boundaries -> CUT line (exact parallel
     offsets; convex corners beyond --miter-limit x allowance are bevelled)
  7. checks: roll fit, mating-seam compensated lengths (fabrication.mating_seam_tol_mm_per_m)

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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as CF  # noqa: E402  central register (practice thresholds tagged V/C/U)


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
def flatten(quads, X, iters=6000, tol=1e-4, return_strains=False):
    """Flatten a set of quads (4-node index tuples into X). Returns 2D dict, max and RMS strain
    (+ the list of signed edge strains (L2D - L3D)/L3D of all quad edges and diagonals if return_strains)."""
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
    # start the unfolding in the middle of the panel so the unfolding error is split both ways
    t0 = 2 * (len(quads) // 2)
    a, b, c = tris[t0]
    P[a] = [0.0, 0.0]
    P[b] = [d3(X[a], X[b]), 0.0]
    P[c] = place_third(P[a], P[b], d3(X[a], X[c]), d3(X[b], X[c]), 1.0)
    seen = {t0}
    queue = [t0]
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
    for _ in range(iters):  # Gauss–Seidel least-squares relaxation, until converged
        move = 0.0
        for v in verts:
            sx = sy = 0.0
            for w, L in nbr[v]:
                dx, dy = P[v][0] - P[w][0], P[v][1] - P[w][1]
                cur = math.hypot(dx, dy) or 1e-12
                sx += P[w][0] + dx * L / cur
                sy += P[w][1] + dy * L / cur
            k = len(nbr[v])
            new_ = [0.5 * P[v][0] + 0.5 * sx / k, 0.5 * P[v][1] + 0.5 * sy / k]
            move = max(move, abs(new_[0] - P[v][0]) + abs(new_[1] - P[v][1]))
            P[v] = new_
        if move < tol:
            break
    strains = [(d2(P[u], P[v]) - L) / L for (u, v), L in L3.items() if L > 1e-9]
    rms = math.sqrt(sum(s * s for s in strains) / len(strains))
    if return_strains:
        return P, max(abs(s) for s in strains), rms, strains
    return P, max(abs(s) for s in strains), rms


def principal_axis(pts):
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    return 0.5 * math.atan2(2 * sxy, sxx - syy), cx, cy


def offset_polygon(poly, dists, miter_limit=4.0):
    """Offset of a CCW polygon; dists[i] = outward offset of edge i (poly[i]->poly[i+1]).

    Every offset edge is the exact parallel line at dists[i]. Corners: the two neighbouring
    offset lines are intersected (mitre). At a CONVEX corner whose mitre point lies further than
    miter_limit * max(d) from the net corner, the corner is BEVELLED: the mitre is cut by a line
    perpendicular to the bisector at that distance, giving two vertices. This keeps the cut line at
    least the allowance away from the net line everywhere (a mitre point merely pulled back towards
    the corner would eat into the allowance). Reflex corners keep the exact line intersection."""
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
        if abs(den) < 1e-12 * (math.hypot(*r1) * math.hypot(*r2) + 1e-30):
            out.append(p2)
            continue
        t = ((p2[0] - p1[0]) * r2[1] - (p2[1] - p1[1]) * r2[0]) / den
        q = (p1[0] + t * r1[0], p1[1] + t * r1[1])
        corner = poly[i]
        lim = miter_limit * max(dists[i - 1], dists[i], 1e-9)
        dq = math.hypot(q[0] - corner[0], q[1] - corner[1])
        if dq > lim and den > 0:            # convex corner (left turn of a CCW polygon): bevel
            u = ((q[0] - corner[0]) / dq, (q[1] - corner[1]) / dq)
            for (pp, rr) in ((p1, r1), (p2, r2)):
                ru = rr[0] * u[0] + rr[1] * u[1]
                tt = (lim - ((pp[0] - corner[0]) * u[0] + (pp[1] - corner[1]) * u[1])) / (ru or 1e-12)
                out.append((pp[0] + tt * rr[0], pp[1] + tt * rr[1]))
            continue
        out.append(q)
    return out


def poly_dist(p, poly):
    """shortest distance from point p to the boundary of a closed polygon."""
    best = math.inf
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        best = min(best, math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy))
    return best


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
    relaxed = set()   # seam lines actually replaced by a geodesic
    notes = []
    bnd = [] if per else [resample(line(0), 4 * n_st), resample(line(n_across_lines), 4 * n_st)]

    def min_dist_to_boundary(c):
        return min((d3(p, q) for p in c[1:-1] for b_ in bnd for q in b_), default=math.inf)

    # lines that carry a support (arch, rail) or a cable (ridge/valley) must keep their position
    node_of = {}
    for vid, nd in enumerate(model["nodes"]):
        gi, gj = nd["grid"]
        node_of[(gi, gj)] = vid
    cable_nodes = set()
    for e in model["edges"]:
        if e["kind"] != "membrane":
            cable_nodes.update(e["n"])

    def constrained(k):
        ids = ([node_of.get((k % nu if per else k, j)) for j in range(1, nv)] if along == "v"
               else [node_of.get((i, k)) for i in range(1, nu)])
        return any(v is not None and (model["nodes"][v].get("fixed") or v in cable_nodes) for v in ids)

    for k in sorted(set(cuts)):
        pts = line(k)
        if seams_mode == "geodesic" and not boundary_line(k) and constrained(k):
            seam_curves[k] = resample(pts, n_st)
            notes.append(f"seam line {k}: on a support/cable line (arch, ridge, valley) -> kept on that line")
        elif seams_mode == "geodesic" and not boundary_line(k):
            geo = geodesic(surf, pts, n_st)
            grid_line = resample(pts, n_st)
            # a geodesic between end points near a concave (scalloped) edge runs into the edge:
            # reject it when it closes in on the boundary much more than the grid line does
            # the seam may not wander more than half a panel width from its grid position,
            # otherwise it crowds the neighbouring seam (saddles, scalloped edges)
            nb = [resample(line(kk), n_st) for kk in (k - strip, k + strip)
                  if per or 0 <= kk <= n_across_lines]
            spacing = min(d3(grid_line[st], c[st]) for c in nb for st in range(n_st)) if nb else math.inf
            dev = max(d3(geo[st], grid_line[st]) for st in range(n_st))
            if bnd and min_dist_to_boundary(geo) < 0.5 * min_dist_to_boundary(grid_line):
                seam_curves[k] = grid_line
                notes.append(f"seam line {k}: geodesic rejected (runs into the curved boundary) -> grid line used")
            elif dev > 0.5 * spacing:
                seam_curves[k] = grid_line
                notes.append(f"seam line {k}: geodesic rejected (wanders {dev:.0f} mm, > half the panel spacing "
                             f"{spacing:.0f} mm) -> grid line used")
            else:
                seam_curves[k] = geo
                relaxed.add(k)
        elif seams_mode == "geodesic":
            seam_curves[k] = resample(pts, n_st)
        else:
            seam_curves[k] = pts
    if per:
        seam_curves[n_across_lines] = seam_curves[0]
    panels = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        A, B = seam_curves[a], seam_curves[b]
        if seams_mode == "grid" or (a % n_across_lines not in relaxed and b % n_across_lines not in relaxed
                                    and a not in relaxed and b not in relaxed):
            # both seams on mesh lines -> exact mesh nodes, no projection
            lines_ = [line(i) for i in range(a, b + 1)]
            if seams_mode == "grid":
                grid = [[ln[st] for ln in lines_] for st in range(n_st)]
            else:
                grid = [[resample(ln, n_st)[st] for ln in lines_] for st in range(n_st)]
        else:
            # project only onto the fabric of this panel (+ margin on sides whose seam is a geodesic),
            # so points near a crease (arch, ridge) cannot jump to the neighbouring bay
            lo = a - (strip if a in relaxed else 0)
            hi = b + (strip if b in relaxed else 0)
            pfaces = []
            for f in model["faces"]:
                gi, gj = model["nodes"][f[0]]["grid"]
                c_ = gi if along == "v" else gj
                if per:
                    c_ = lo + (c_ - lo) % nu
                if lo <= c_ < hi:
                    pfaces.append(f)
            surf = Surface(X, pfaces)
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


# ---------------------------------------------------------------- drawing
def draw_panel(dxf, pid, cut, net, marks, note, off, L, W, table=False):
    sh = lambda p: (p[0] + off[0], p[1] + off[1])
    dxf.polyline([sh(p) for p in cut], "CUT", closed=True)
    dxf.polyline([sh(p) for p in net], "NET", closed=True)
    # label inside the fabric: vertical section of the net outline at mid-length
    xm = L / 2
    ys = []
    for i in range(len(net)):
        (x1, y1), (x2, y2) = net[i], net[(i + 1) % len(net)]
        if (x1 - xm) * (x2 - xm) <= 0 and x1 != x2:
            ys.append(y1 + (y2 - y1) * (xm - x1) / (x2 - x1))
    lo, hi = (min(ys), max(ys)) if len(ys) >= 2 else (0.0, W)
    local = hi - lo
    h = max(min(local / 6, 120), 10)
    mid = sh((xm, (lo + hi) / 2))
    dxf.text(pid, (mid[0], mid[1] + 0.6 * h), h, "TEXT", align_center=True)
    dxf.text(note, (mid[0], mid[1] - 0.3 * h), 0.35 * h, "TEXT", align_center=True)
    dxf.arrow((mid[0] - L / 6, mid[1] - 1.1 * h), (mid[0] + L / 6, mid[1] - 1.1 * h), h / 2, "WARP")
    dxf.text("WARP", (mid[0], mid[1] - 1.7 * h), 0.35 * h, "WARP", align_center=True)
    for m in marks:
        dxf.line(sh(m["p"]), sh(m["q"]), "NOTCH")
        dxf.text(f"{m['seam']}.{m['k']}", sh(m["q"]), 0.25 * h, "NOTCH")
    if table:
        dxf.dimension_text(sh((0, 0)), sh((L, 0)), -2 * h, 0.4 * h, "DIM")
        dxf.dimension_text(sh((L, 0)), sh((L, W)), -2 * h, 0.4 * h, "DIM")
        th = 0.3 * h
        y = -4 * h
        dxf.text("NET LINE COORDINATES (mm, panel origin at lower-left of cut outline)", sh((0, y)), th, "TEXT")
        step = max(1, len(net) // 60)
        for i, p in enumerate(net[::step]):
            col, row = divmod(i, 20)
            dxf.text(f"{i * step:3d}: {p[0]:8.1f} {p[1]:8.1f}", sh((col * 14 * th * 2, y - (row + 1) * 1.6 * th)), th, "TEXT")


# ---------------------------------------------------------------- main
def process_panel(pan, cw, cf, dec_end, dec_side, dec_len):
    grid = pan["grid"]
    ns, nx = len(grid), len(grid[0])
    Xl = [p for row in grid for p in row]
    idx = lambda s, k: s * nx + k
    quads = [(idx(s, k), idx(s, k + 1), idx(s + 1, k + 1), idx(s + 1, k)) for s in range(ns - 1) for k in range(nx - 1)]
    P2, emax, erms, strains = flatten(quads, Xl, return_strains=True)
    # area check: 3D area of the triangulated panel vs flat area (before compensation)
    def tri3(a, b, c):
        u = [Xl[b][i] - Xl[a][i] for i in range(3)]
        v = [Xl[c][i] - Xl[a][i] for i in range(3)]
        return 0.5 * math.hypot(u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])

    def tri2(a, b, c):
        return 0.5 * ((P2[b][0] - P2[a][0]) * (P2[c][1] - P2[a][1]) - (P2[b][1] - P2[a][1]) * (P2[c][0] - P2[a][0]))
    a3 = sum(tri3(q[0], q[1], q[2]) + tri3(q[0], q[2], q[3]) for q in quads)
    a2 = abs(sum(tri2(q[0], q[1], q[2]) + tri2(q[0], q[2], q[3]) for q in quads))
    stats = {"area3d": a3, "area2d": a2, "strains": strains}
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
    kinds = ["end0"] * (nx - 1) + ["right"] * (ns - 1) + ["end1"] * (nx - 1) + ["left"] * (ns - 1)
    net = [tuple(N[v]) for v in ring]
    if area(net) < 0:
        net.reverse()
        kinds = kinds[::-1]
        kinds = kinds[1:] + kinds[:1]  # edge i = net[i] -> net[i+1] after reversal
    seam_len = {"left": 0.0, "right": 0.0}
    for side, k in (("left", 0), ("right", nx - 1)):
        seam_len[side] = polylen([grid[s][k] for s in range(ns)])
    seam2d = {"left": [tuple(N[idx(s, 0)]) for s in range(ns)],
              "right": [tuple(N[idx(s, nx - 1)]) for s in range(ns)]}
    strip_w = max(math.hypot(N[idx(s, 0)][0] - N[idx(s, nx - 1)][0], N[idx(s, 0)][1] - N[idx(s, nx - 1)][1])
                  for s in range(ns))
    seam2d["strip_width"] = strip_w
    return net, kinds, emax, erms, seam_len, seam2d, stats


_SPLIT_COUNTER = [0]


def split_panel(pan, surf_fn, across=False):
    """split an over-wide panel: along its length (extra long seam) or across it (cross seam, for curved
    'banana' panels whose bounding width comes from curvature rather than strip width)."""
    grid = pan["grid"]
    ns, nx = len(grid), len(grid[0])
    _SPLIT_COUNTER[0] += 1
    new_id = f"N{_SPLIT_COUNTER[0]}"
    lid, rid = pan["ids"]
    base = {k: v for k, v in pan.items() if k not in ("grid",)}
    info = pan["seam_info"]
    if across and ns >= 3:
        m = ns // 2
        dl = polylen([row[0] for row in grid[:m + 1]])
        dr = polylen([row[-1] for row in grid[:m + 1]])
        p1 = dict(base, grid=grid[:m + 1], end1_seam=True, end_ids=(pan.get("end_ids", ("", ""))[0], new_id))
        p2 = dict(base, grid=grid[m:], end0_seam=True, end_ids=(new_id, pan.get("end_ids", ("", ""))[1]),
                  seam_info={"left": (info["left"][0] + dl, info["left"][1]),
                             "right": (info["right"][0] + dr, info["right"][1])})
        return [p1, p2]
    if nx >= 3:
        m = nx // 2
        g1 = [row[:m + 1] for row in grid]
        g2 = [row[m:] for row in grid]
    else:
        surf = surf_fn()
        mids = [surf.project(lerp(row[0], row[1], 0.5)) for row in grid]
        g1 = [[row[0], mp] for row, mp in zip(grid, mids)]
        g2 = [[mp, row[1]] for row, mp in zip(grid, mids)]
    Lnew = polylen([row[-1] for row in g1])
    p1 = dict(base, grid=g1, right_seam=True, ids=(lid, new_id), seam_info={"left": info["left"], "right": (0.0, Lnew)})
    p2 = dict(base, grid=g2, left_seam=True, ids=(new_id, rid), seam_info={"left": (0.0, Lnew), "right": info["right"]})
    return [p1, p2]


def inside(pt, poly):
    x, y = pt
    ins = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ins = not ins
    return ins


def notch_marks(poly2d, net, fractions, length):
    """match marks at given arc-length fractions (with their labels) along a seam polyline,
    pointing out of the net outline. fractions = [(f, label), ...] with 0 < f < 1."""
    s = [0.0]
    for i in range(1, len(poly2d)):
        s.append(s[-1] + d2(poly2d[i - 1], poly2d[i]))
    L = s[-1]
    marks = []
    j = 0
    for fr, k in fractions:
        t = L * fr
        while j < len(poly2d) - 2 and s[j + 1] < t:
            j += 1
        seg = (s[j + 1] - s[j]) or 1e-12
        f = (t - s[j]) / seg
        p = (poly2d[j][0] + f * (poly2d[j + 1][0] - poly2d[j][0]), poly2d[j][1] + f * (poly2d[j + 1][1] - poly2d[j][1]))
        tx, ty = poly2d[j + 1][0] - poly2d[j][0], poly2d[j + 1][1] - poly2d[j][1]
        tl = math.hypot(tx, ty) or 1e-12
        nx_, ny_ = -ty / tl, tx / tl
        if inside((p[0] + nx_ * 1.0, p[1] + ny_ * 1.0), net):
            nx_, ny_ = -nx_, -ny_
        marks.append((p, (p[0] + nx_ * length, p[1] + ny_ * length), k))
    return marks


STRAIN_BINS = (0.1, 0.3, 0.5, 1.0)   # % bins of the printed flattening-strain distribution (reporting only)


def strain_histogram(strains):
    """share of edges (in %) with |strain| in [0, 0.1), [0.1, 0.3), [0.3, 0.5), [0.5, 1.0), >= 1.0 %."""
    edges = (0.0,) + STRAIN_BINS + (math.inf,)
    n = max(len(strains), 1)
    return [100.0 * sum(1 for s in strains if edges[k] <= abs(s) * 100 < edges[k + 1]) / n
            for k in range(len(edges) - 1)]


def percentile(vals, q):
    v = sorted(vals)
    if not v:
        return 0.0
    k = (len(v) - 1) * q
    lo = int(math.floor(k))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


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
    ap.add_argument("--miter-limit", type=float, default=4.0,
                    help="convex allowance corners whose mitre exceeds this x allowance are bevelled")
    ap.add_argument("--roll-width", type=float, default=2500.0, help="usable fabric roll width [mm]")
    ap.add_argument("--scale", type=float, default=1000.0, help="model length unit -> mm (m->mm = 1000)")
    ap.add_argument("--prefix", default="P")
    ap.add_argument("--auto-split", action="store_true", help="split panels wider than the roll (extra seam)")
    ap.add_argument("--notch", type=float, default=1000.0, help="match-mark spacing along seams [mm]")
    ap.add_argument("--sheets", action="store_true", help="also write one shop sheet (DXF with title block) per panel")
    ap.add_argument("--strain-warn", type=float, default=None,
                    help="flattening-strain warning threshold [%%] (default: register fabrication.flatten_strain_warn_pct)")
    ap.add_argument("--seam-tol", type=float, default=None,
                    help="mating-seam length tolerance [mm/m] (default: register fabrication.mating_seam_tol_mm_per_m)")
    ap.add_argument("--project", default="Tensile structure")
    ap.add_argument("--material", default="(membrane material)")
    ap.add_argument("--out", default="patterns")
    a = ap.parse_args(argv)

    strain_warn = a.strain_warn if a.strain_warn is not None else CF.get("fabrication.flatten_strain_warn_pct")
    strain_tag = "user" if a.strain_warn is not None else CF.status("fabrication.flatten_strain_warn_pct")
    seam_tol = a.seam_tol if a.seam_tol is not None else CF.get("fabrication.mating_seam_tol_mm_per_m")
    seam_tag = "user" if a.seam_tol is not None else CF.status("fabrication.mating_seam_tol_mm_per_m")
    print("Assumptions: model lengths x --scale -> mm; panels flattened by unfolding + least-squares edge-length "
          "relaxation (a geometric method, no material stiffness; not an energy/FE patterning as in MPanel, Easy or "
          "RFEM); compensation = shrink factor (1 - c) along the panel principal axes (warp = panel length); "
          "decompensation graded linearly over --decomp-length; allowances = exact parallel offsets, convex corners "
          f"bevelled beyond {a.miter_limit:g} x allowance; strain warning {strain_warn:g} % [{strain_tag}], mating-seam "
          f"tolerance {seam_tol:g} mm/m [{seam_tag}] (practice values, confirm with the fabricator).")

    with open(a.model) as fh:
        model = json.load(fh)
    if "grid" not in model:
        sys.exit("model needs a structured grid (use form_find_fdm.py output)")
    X = [[c * a.scale for c in nd["xyz"]] for nd in model["nodes"]]
    surf = Surface(X, model["faces"]) if a.seams == "geodesic" else None
    panels, seam_curves, notes = build_panels(model, X, a.panels_along, a.strip, a.seams, surf)
    cw, cf = a.comp_warp / 100, a.comp_weft / 100
    g = model["grid"]
    per_nu = g["nu"] if (g.get("periodic_u") and a.panels_along == "v") else None

    def line_id(k):
        return f"L{k % per_nu if per_nu else k}"

    dxf = DXF()
    layers = (("CUT", "red"), ("NET", "cyan"), ("TEXT", "green"), ("WARP", "yellow"), ("DIM", "grey"),
              ("NOTCH", "magenta"))
    for ly, col in layers:
        dxf.layer(ly, col)
    rows, pjson = [], []
    xoff = 0.0
    surf_cache = {}
    all_strains = []
    seam_net = defaultdict(lambda: [0.0, 0.0])   # seam id -> [net length on its left panel(s), on its right panel(s)]

    def surf_fn():
        if "s" not in surf_cache:
            surf_cache["s"] = surf or Surface(X, model["faces"])
        return surf_cache["s"]

    _SPLIT_COUNTER[0] = 0
    queue = [dict(p, ids=(line_id(p['lines'][0]), line_id(p['lines'][1])), depth=0,
                  seam_info={"left": (0.0, polylen([r[0] for r in p["grid"]])),
                             "right": (0.0, polylen([r[-1] for r in p["grid"]]))}) for p in panels]
    k = 0
    while queue:
        pan = queue.pop(0)
        net, kinds, emax, erms, seam_len, seam2d, stats = process_panel(pan, cw, cf, a.decomp_ends, a.decomp_sides,
                                                                        a.decomp_length)

        def is_seam(kd):
            return ((kd == "left" and pan["left_seam"]) or (kd == "right" and pan["right_seam"])
                    or (kd == "end0" and pan.get("end0_seam")) or (kd == "end1" and pan.get("end1_seam")))
        dists = [a.seam if is_seam(kd) else a.edge for kd in kinds]
        cut = offset_polygon(net, dists, a.miter_limit)
        W = max(p[1] for p in cut) - min(p[1] for p in cut)
        if a.auto_split and W > a.roll_width and pan["depth"] < 6:
            across = seam2d["strip_width"] + 2 * a.seam < 0.9 * a.roll_width   # width comes from curvature
            parts = split_panel(pan, surf_fn, across)
            for q in parts[::-1]:
                queue.insert(0, dict(q, depth=pan["depth"] + 1))
            notes.append(f"panel between {pan['ids'][0]} and {pan['ids'][1]}: {W:.0f} mm > roll {a.roll_width:.0f} mm "
                         f"-> split {'ACROSS (cross seam, curved panel)' if across else 'along its length (extra seam)'}")
            continue
        k += 1
        pid = f"{a.prefix}{k:02d}"
        all_strains += stats["strains"]
        minx = min(p[0] for p in cut)
        miny = min(p[1] for p in cut)
        maxx = max(p[0] for p in cut)
        maxy = max(p[1] for p in cut)
        L, W = maxx - minx, maxy - miny
        loc = lambda p: (p[0] - minx, p[1] - miny)
        cut_l, net_l = [loc(p) for p in cut], [loc(p) for p in net]
        marks = []
        net_seam = {}
        for side, sid in (("left", pan["ids"][0]), ("right", pan["ids"][1])):
            net_seam[side] = sum(d2(seam2d[side][i - 1], seam2d[side][i]) for i in range(1, len(seam2d[side])))
            if (side == "left" and pan["left_seam"]) or (side == "right" and pan["right_seam"]):
                seam_net[sid][0 if side == "right" else 1] += net_seam[side]
                s0, Lfull = pan["seam_info"][side]
                n_full = max(2, round(Lfull / a.notch))
                sp = Lfull / n_full
                fr = [((kk * sp - s0) / seam_len[side], kk) for kk in range(1, n_full)
                      if s0 + 1e-6 < kk * sp < s0 + seam_len[side] - 1e-6]
                for (p0, p1, kk) in notch_marks([loc(p) for p in seam2d[side]], net_l, fr, a.seam):
                    marks.append({"seam": sid, "k": kk, "p": p0, "q": p1})
        note = f"cw {a.comp_warp}% cf {a.comp_weft}%"
        if a.decomp_ends is not None:
            note += f" | ends {a.decomp_ends}%/{a.decomp_length:g}mm"
        if a.decomp_sides is not None:
            note += f" | sides {a.decomp_sides}%"
        draw_panel(dxf, pid, cut_l, net_l, marks, note, (xoff, 0.0), L, W)
        net_area = abs(area(net)) / 1e6
        rows.append({"panel": pid, "length_mm": round(L), "width_mm": round(W),
                     "fits_roll": W <= a.roll_width, "net_area_m2": round(net_area, 3),
                     "cut_area_m2": round(abs(area(cut)) / 1e6, 3), "bbox_area_m2": round(L * W / 1e6, 3),
                     "flatten_strain_max_%": round(emax * 100, 3), "flatten_strain_rms_%": round(erms * 100, 3),
                     "seam_left_3d_mm": round(seam_len["left"], 1), "seam_right_3d_mm": round(seam_len["right"], 1),
                     "left": pan["ids"][0] if pan["left_seam"] else "boundary",
                     "right": pan["ids"][1] if pan["right_seam"] else "boundary",
                     "cross_seams": ",".join(x for x in pan.get("end_ids", ("", "")) if x),
                     "area_3d_m2": round(stats["area3d"] / 1e6, 4),
                     "flatten_area_err_%": round((stats["area2d"] - stats["area3d"]) / stats["area3d"] * 100, 4),
                     "flatten_strain_p95_%": round(percentile([abs(s) for s in stats["strains"]], 0.95) * 100, 3),
                     "seam_left_net_mm": round(net_seam["left"], 1), "seam_right_net_mm": round(net_seam["right"], 1)})
        pjson.append({"panel": pid, "cut": cut_l, "net": net_l, "notches": marks, "L": L, "W": W,
                      "net_area_m2": net_area, "note": note, "x_offset_in_dxf": xoff})
        if a.sheets:
            sheet = DXF()
            for ly, col in layers + (("TITLE", "grey"),):
                sheet.layer(ly, col)
            draw_panel(sheet, pid, cut_l, net_l, marks, note, (0.0, 0.0), L, W, table=True)
            sheet.frame({"PROJECT": a.project, "PANEL": pid, "MATERIAL": a.material, "DWG No": f"{a.out}-{pid}",
                         "REV": "A", "SCALE": "1:1 (mm)", "COMP": f"w {a.comp_warp}% / f {a.comp_weft}%",
                         "SEAMS": f"{rows[-1]['left']} / {rows[-1]['right']}", "NET AREA": f"{net_area:.2f} m2"},
                        max(min(W / 25, 60), 12))
            sheet.save(f"{a.out}_{pid}.dxf")
        xoff += L + 300
    dxf.save(a.out + ".dxf")
    with open(a.out + ".json", "w") as fh:
        json.dump({"roll_width": a.roll_width, "panels": pjson}, fh, indent=1)
    with open(a.out + ".csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"Seams: {a.seams}")
    print(f"{'panel':<7}{'L[mm]':>8}{'W[mm]':>7}{'roll':>6}{'net m2':>8}{'cut m2':>8}{'strain max%':>12}"
          f"{'p95%':>7}{'area err%':>10}{'seamL 3D':>10}{'seamR 3D':>10}")
    for r in rows:
        print(f"{r['panel']:<7}{r['length_mm']:8d}{r['width_mm']:7d}{'ok' if r['fits_roll'] else 'NO':>6}"
              f"{r['net_area_m2']:8.2f}{r['cut_area_m2']:8.2f}{r['flatten_strain_max_%']:12.3f}"
              f"{r['flatten_strain_p95_%']:7.3f}{r['flatten_area_err_%']:10.3f}"
              f"{r['seam_left_3d_mm']:10.0f}{r['seam_right_3d_mm']:10.0f}")
    tot_net = sum(r["net_area_m2"] for r in rows)
    tot_bb = sum(r["bbox_area_m2"] for r in rows)
    tot_3d = sum(r["area_3d_m2"] for r in rows)
    print(f"Total net {tot_net:.2f} m2, 3D panel area {tot_3d:.2f} m2"
          + (f" (model surface_area_m2 {model['surface_area_m2']:.2f})" if "surface_area_m2" in model else "")
          + f", fabric consumed (bounding boxes) {tot_bb:.2f} m2, "
          f"un-nested waste ~{(1 - tot_net / tot_bb) * 100:.0f}% (nesting on the roll reduces this)")
    h = strain_histogram(all_strains)
    lab = ["<0.1", "0.1-0.3", "0.3-0.5", "0.5-1.0", ">=1.0"]
    print("Flattening strain distribution (all edges and diagonals, |strain| %): "
          + ", ".join(f"{l_} {v:.1f}%" for l_, v in zip(lab, h)))
    if a.seams == "geodesic":
        gl = [polylen(c) for kk, c in seam_curves.items()]
        print(f"Geodesic seams: {len(seam_curves)} lines, lengths {min(gl):.0f}–{max(gl):.0f} mm")
    for sid, (lft, rgt) in sorted(seam_net.items()):
        if lft > 0 and rgt > 0:
            dev = abs(lft - rgt) / max(lft, rgt) * 1000
            if dev > seam_tol:
                notes.append(f"seam {sid}: compensated lengths {lft:.0f} / {rgt:.0f} mm differ by {dev:.1f} mm/m "
                             f"> {seam_tol:g} mm/m (decompensation or flattening) -> check before cutting")
    for n_ in notes:
        print("  NOTE:", n_)
    if any(not r["fits_roll"] for r in rows):
        print("WARNING: some panels exceed the roll width -> reduce --strip or use --auto-split")
    if any(r["flatten_strain_max_%"] > strain_warn for r in rows):
        print(f"WARNING: flattening strain > {strain_warn:g}% -> panels too wide for this curvature; reduce --strip")
    if any(r["flatten_strain_max_%"] > 0.5 * min(a.comp_warp, a.comp_weft) for r in rows) and min(cw, cf) > 0:
        print("NOTE: flattening strain exceeds half the smaller compensation value; the pattern error is of the "
              "same order as the compensation itself")
    print(f"Wrote {a.out}.dxf, {a.out}.csv, {a.out}.json" + (f" and {len(rows)} panel sheets" if a.sheets else ""))
    return rows


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
