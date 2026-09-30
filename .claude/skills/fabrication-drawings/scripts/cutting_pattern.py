#!/usr/bin/env python3
"""Cutting patterns (patterning) from a form-found membrane mesh -> DXF + CSV.

Pure-Python. Reads the grid mesh JSON from form_find_fdm.py (or any model with
"grid" + "nodes[].grid" indices), splits the surface into strips (panels)
along grid lines, flattens every panel, applies compensation, adds seam /
edge allowances and writes plotter-ready DXF and a panel schedule CSV.

Pipeline (per panel)
  1. extract strip of quads between grid lines  (seams follow grid lines —
     for good results make the mesh lines approximate geodesics, i.e. form-find
     a mesh whose "v" lines run along the intended seam direction)
  2. triangulate, unfold triangle-by-triangle (exact edge lengths along the
     unfolding path) and then minimise edge-length error in 2D by iterative
     least-squares relaxation (all edges + diagonals). The residual strain is
     reported: > ~0.5 % means the strip is too wide / too doubly curved.
  3. orient: warp axis = panel long axis (principal axis) -> x of the DXF
  4. compensate: shrink warp by cw %, weft by cf % (from biaxial tests);
     boundary (cable pocket / clamp) lines may be decompensated separately
  5. offset: seam allowance on seam sides, edge allowance (pocket/hem) on the
     free boundary sides -> CUT line; the net (weld/seam) line is kept.

DXF layers:  CUT (red) cutting line incl. allowances, NET (cyan) compensated
net/seam line, TEXT (green), WARP (yellow) warp arrow, DIM (grey) chord dims.

Example:
  python3 cutting_pattern.py sail.json --panels-along u --strip 3 \
      --comp-warp 0.8 --comp-weft 1.4 --seam 50 --edge 80 --roll-width 2500 \
      --out sail_patterns
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxf_writer import DXF  # noqa: E402


def d3(a, b):
    return math.dist(a, b)


def d2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def place_third(pa, pb, la, lb, side=1.0):
    """2D point at distance la from pa and lb from pb (side selects the solution)."""
    L = d2(pa, pb)
    x = (la * la - lb * lb + L * L) / (2 * L)
    h = math.sqrt(max(la * la - x * x, 0.0))
    ux, uy = (pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L
    return [pa[0] + x * ux - side * h * uy, pa[1] + x * uy + side * h * ux]


def flatten(quads, X, iters=400):
    """Flatten a strip of quads (list of 4-node tuples, ordered along the strip)."""
    verts = sorted({v for q in quads for v in q})
    P: dict[int, list[float]] = {}
    edges = set()
    tris = []
    for q in quads:
        a, b, c, d = q
        tris += [(a, b, c), (a, c, d)]
        for u, v in ((a, b), (b, c), (c, d), (d, a), (a, c), (b, d)):
            edges.add((min(u, v), max(u, v)))
    # --- unfold: first triangle, then breadth-first across shared triangle edges;
    #     each new vertex goes on the opposite side of the shared edge
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
    # --- least-squares edge-length relaxation (Gauss–Seidel style)
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
    strains = [(d2(P[u], P[v]) - L) / L for (u, v), L in L3.items()]
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
        nx, ny = dy / L, -dx / L  # outward normal for CCW polygon
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
        # limit mitre spikes on very sharp corners
        corner = poly[i]
        lim = 4 * max(dists[i - 1], dists[i], 1e-9)
        if math.hypot(q[0] - corner[0], q[1] - corner[1]) > lim:
            q = (corner[0] + (q[0] - corner[0]) * lim / math.hypot(q[0] - corner[0], q[1] - corner[1]),
                 corner[1] + (q[1] - corner[1]) * lim / math.hypot(q[0] - corner[0], q[1] - corner[1]))
        out.append(q)
    return out


def area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def build_panels(model, along, strip):
    g = model["grid"]
    nu, nv, per = g["nu"], g["nv"], g.get("periodic_u", False)
    ncol = nu if per else nu + 1
    idx = lambda i, j: j * ncol + (i % nu if per else i)
    panels = []
    if along == "v":  # panels run in v, seams are v-lines, strips cut across u
        starts = list(range(0, nu, strip))
        for s in starts:
            e = min(s + strip, nu)
            quads = [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1))
                     for j in range(nv) for i in range(s, e)]
            left = [idx(s, j) for j in range(nv + 1)]
            right = [idx(e, j) for j in range(nv + 1)]
            bottom = [idx(i, 0) for i in range(s, e + 1)]
            top = [idx(i, nv) for i in range(s, e + 1)]
            seam_l = per or s > 0
            seam_r = per or e < nu
            panels.append((quads, bottom, right, top, left, (False, seam_r, False, seam_l)))
    else:  # panels run in u, seams are u-lines
        for s in range(0, nv, strip):
            e = min(s + strip, nv)
            quads = [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1))
                     for i in range(nu) for j in range(s, e)]
            bottom = [idx(i, s) for i in range(nu + 1)]
            top = [idx(i, e) for i in range(nu + 1)]
            left = [idx(0, j) for j in range(s, e + 1)]
            right = [idx(nu, j) for j in range(s, e + 1)]
            panels.append((quads, bottom, right, top, left, (s > 0, False, e < nv, False)))
    return panels


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("--panels-along", choices=["u", "v"], default="v",
                    help="panel long direction (seam lines run this way)")
    ap.add_argument("--strip", type=int, default=2, help="mesh bays per panel width")
    ap.add_argument("--comp-warp", type=float, default=1.0, help="warp compensation [%%]")
    ap.add_argument("--comp-weft", type=float, default=1.5, help="weft compensation [%%]")
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
    panels = build_panels(model, a.panels_along, a.strip)
    cw, cf = a.comp_warp / 100, a.comp_weft / 100

    dxf = DXF()
    for ly, col in (("CUT", "red"), ("NET", "cyan"), ("TEXT", "green"), ("WARP", "yellow"), ("DIM", "grey")):
        dxf.layer(ly, col)
    rows = []
    xoff = 0.0
    for k, (quads, bottom, right, top, left, seams) in enumerate(panels, 1):
        pid = f"{a.prefix}{k:02d}"
        P, emax, erms = flatten(quads, X)
        boundary = bottom + right[1:] + top[::-1][1:] + left[::-1][1:-1]
        poly = [P[v] for v in boundary]
        if area(poly) < 0:
            poly.reverse()
            sides = [bottom, right, top, left][::-1]
            seams = seams[::-1]
            boundary.reverse()
        else:
            sides = [bottom, right, top, left]
        th, cx, cy = principal_axis(poly)
        c, s = math.cos(-th), math.sin(-th)
        rot = [((p[0] - cx) * c - (p[1] - cy) * s, (p[0] - cx) * s + (p[1] - cy) * c) for p in poly]
        net = [(x * (1 - cw), y * (1 - cf)) for x, y in rot]  # warp along x
        # per-edge offsets: seam allowance on seam sides, edge allowance on free sides
        side_of = []
        for si, side in enumerate(sides):
            side_of += [si] * (len(side) - 1)
        dists = [a.seam if seams[side_of[i]] else a.edge for i in range(len(net))]
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
        dxf.text(f"cw {a.comp_warp}% cf {a.comp_weft}%", (mid[0], mid[1] - 0.8 * h), 0.4 * h, "TEXT",
                 align_center=True)
        dxf.arrow((mid[0] - L / 4, mid[1] - 2 * h), (mid[0] + L / 4, mid[1] - 2 * h), h / 2, "WARP")
        dxf.text("WARP", (mid[0], mid[1] - 2.6 * h), 0.4 * h, "WARP", align_center=True)
        dxf.dimension_text(sh(net[0]), sh(net[len(bottom) - 1]), -1.5 * h, 0.4 * h)
        net_area = abs(area(net)) / 1e6
        cut_area = abs(area(cut)) / 1e6
        rows.append({"panel": pid, "length_mm": round(L), "width_mm": round(W),
                     "fits_roll": W <= a.roll_width, "net_area_m2": round(net_area, 3),
                     "cut_area_m2": round(cut_area, 3), "bbox_area_m2": round(L * W / 1e6, 3),
                     "flatten_strain_max_%": round(emax * 100, 3), "flatten_strain_rms_%": round(erms * 100, 3)})
        xoff += L + 300
    dxf.save(a.out + ".dxf")
    with open(a.out + ".csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"{'panel':<7}{'L[mm]':>8}{'W[mm]':>7}{'roll':>6}{'net m2':>8}{'cut m2':>8}{'strain max%':>12}")
    for r in rows:
        print(f"{r['panel']:<7}{r['length_mm']:8d}{r['width_mm']:7d}{'ok' if r['fits_roll'] else 'NO':>6}"
              f"{r['net_area_m2']:8.2f}{r['cut_area_m2']:8.2f}{r['flatten_strain_max_%']:12.3f}")
    tot_net = sum(r["net_area_m2"] for r in rows)
    tot_bb = sum(r["bbox_area_m2"] for r in rows)
    print(f"Total net {tot_net:.2f} m2, fabric consumed (bounding boxes) {tot_bb:.2f} m2, "
          f"un-nested waste ~{(1 - tot_net / tot_bb) * 100:.0f}% (nesting on the roll reduces this)")
    if any(not r["fits_roll"] for r in rows):
        print("WARNING: some panels exceed the roll width -> reduce --strip")
    if any(r["flatten_strain_max_%"] > 0.5 for r in rows):
        print("WARNING: flattening strain > 0.5% -> panels too wide for this curvature; reduce --strip")
    print(f"Wrote {a.out}.dxf and {a.out}.csv")
    return rows


if __name__ == "__main__":
    main(sys.argv[1:])
