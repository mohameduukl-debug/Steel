#!/usr/bin/env python3
"""Nest cutting patterns on the fabric roll (strip packing) -> nested DXF + roll consumption.

Reads the <out>.json written by cutting_pattern.py. Panels keep the warp along the roll
(x = roll length); only 0° or 180° rotation is allowed (fabric warp/weft must not change).
Raster "skyline" nesting: every panel is described per x-column (step --dx) by the y-interval it
occupies; panels are placed longest-first at the smallest x where their columns fit between
the roll edges and the already placed panels (with a clearance --gap). This interlocks curved
("banana") panels far better than bounding boxes.

The clearance --gap is kept in both directions (the x-window of every column is widened by the gap), and the
finished layout is verified with exact polygon geometry (segment distances + containment).

Outputs: <out>.dxf (roll edges, nested CUT outlines, labels, roll length), <out>.csv (panel
positions, areas) and a printed summary (roll length used and its area lower bound, utilisation by cut and
net area, verified clearance / roll-edge margin / overlaps).

Example
  python3 nest_panels.py sail_patterns.json --roll-width 2500 --gap 20 --out sail_nest
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


def y_range(poly, xa, xb):
    """exact y-extent of a polygon over the x-window [xa, xb]: for a polygon the extremes occur at the window
    edges or at vertices, so sampling the boundary at xa, xb and every vertex inside is exact."""
    lo, hi = math.inf, -math.inf
    n = len(poly)
    for xq in (xa, xb):
        for i in range(n):
            (a, b), (c, d) = poly[i], poly[(i + 1) % n]
            if (a - xq) * (c - xq) <= 0 and a != c:
                y = b + (d - b) * (xq - a) / (c - a)
                lo, hi = min(lo, y), max(hi, y)
    for (a, b) in poly:
        if xa <= a <= xb:
            lo, hi = min(lo, b), max(hi, b)
    return lo, hi


def columns(poly, dx, pad=0.0):
    """per-column occupied y-interval of a polygon, columns of width dx starting at the polygon's min x.
    pad > 0: column k covers the x-window widened by pad on both sides, and extra columns are added before
    and after the polygon (used for the clearance check, so panels keep >= pad also along the roll).
    Returns (cols, x0, k0): cols[j] is the interval of column k0 + j (relative to the polygon's first column)."""
    xs = [p[0] for p in poly]
    x0, x1 = min(xs), max(xs)
    n = max(1, int(math.ceil((x1 - x0) / dx - 1e-9)))
    k0 = -int(math.ceil(pad / dx - 1e-9)) if pad > 0 else 0
    k1 = n - 1 + (-k0)
    cols = []
    for k in range(k0, k1 + 1):
        xa, xb = max(x0, x0 + k * dx - pad), min(x1, x0 + (k + 1) * dx + pad)
        cols.append(y_range(poly, xa, xb) if xa <= xb else (math.inf, -math.inf))
    return cols, x0, k0


def rotate180(poly, L, W):
    return [(L - x, W - y) for x, y in poly]


def fits(occ, x0, chk, k0, yoff, gap):
    """chk: x-widened column intervals starting at column k0 (clearance). The roll edges are respected by the
    choice of yoff (between -ymin and W - ymax), so only the other panels are checked here."""
    for j, (lo, hi) in enumerate(chk):
        if lo > hi:
            continue
        a, b = lo + yoff - gap, hi + yoff + gap
        for (u, v) in occ.get(x0 + k0 + j, ()):
            if a < v and u < b:
                return False
    return True


def nest(panels, W, dx, gap):
    """skyline raster nesting; guarantees (by construction) that two panels are never closer than gap:
    for points p in A and q in B either |px - qx| > gap or |py - qy| >= gap (checked exactly by verify())."""
    occ = {}   # column index -> list of (ymin, ymax)
    placed = []
    order = sorted(panels, key=lambda p: -p["L"])
    for p in order:
        best = None
        for rot in (0, 180):
            poly = p["cut"] if rot == 0 else rotate180(p["cut"], p["L"], p["W"])
            cols, xmin, _ = columns(poly, dx)
            chk, _, k0 = columns(poly, dx, pad=gap)
            ymin = min(lo for lo, _ in cols)
            ymax = max(hi for _, hi in cols)
            if ymax - ymin > W + 1e-6:
                continue
            # candidate vertical offsets: against the lower edge, the upper edge, and every 50 mm
            yoffs = sorted(y for y in {-ymin, W - ymax} | {-ymin + s for s in range(0, int(W - (ymax - ymin)) + 1, 50)}
                           if -ymin - 1e-9 <= y <= W - ymax + 1e-9)
            x0 = 0
            while True:
                ok = None
                for yo in yoffs:
                    if fits(occ, x0, chk, k0, yo, gap):
                        ok = yo
                        break
                if ok is not None:
                    break
                x0 += 1
            if best is None or x0 < best[0]:
                best = (x0, rot, ok, cols, poly, xmin)
        if best is None:
            raise SystemExit(f"panel {p['panel']} ({p['W']:.0f} mm) is wider than the roll ({W:.0f} mm)")
        x0, rot, yo, cols, poly, xmin = best
        for k, (lo, hi) in enumerate(cols):
            occ.setdefault(x0 + k, []).append((lo + yo, hi + yo))
        shift = (x0 * dx - xmin, yo)
        placed.append({"panel": p["panel"], "rot": rot, "x": shift[0], "y": shift[1],
                       "poly": [(x + shift[0], y + shift[1]) for x, y in poly], "net_area_m2": p["net_area_m2"],
                       "cut_area_m2": abs(poly_area(poly)) / 1e6,
                       "label": (x0 * dx + p["L"] / 2, yo + (min(lo for lo, _ in cols) + max(hi for _, hi in cols)) / 2)})
    length = max(max(x for x, _ in q["poly"]) for q in placed)
    return placed, length


def poly_area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def _seg_dist(p, q, a, b):
    """exact minimum distance between segments pq and ab (0 if they intersect)."""
    def orient(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    d1, d2_ = orient(p, q, a), orient(p, q, b)
    d3, d4 = orient(a, b, p), orient(a, b, q)
    if ((d1 > 0) != (d2_ > 0)) and ((d3 > 0) != (d4 > 0)) and d1 * d2_ < 0 and d3 * d4 < 0:
        return 0.0

    def pt_seg(c, u, v):
        dx, dy = v[0] - u[0], v[1] - u[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((c[0] - u[0]) * dx + (c[1] - u[1]) * dy) / L2))
        return math.hypot(c[0] - u[0] - t * dx, c[1] - u[1] - t * dy)
    return min(pt_seg(p, a, b), pt_seg(q, a, b), pt_seg(a, p, q), pt_seg(b, p, q))


def _inside(pt, poly):
    x, y = pt
    ins = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ins = not ins
    return ins


def poly_clearance(A, B):
    """exact minimum distance between two simple polygons (0 if they overlap or one contains the other)."""
    if _inside(A[0], B) or _inside(B[0], A):
        return 0.0
    best = math.inf
    for i in range(len(A)):
        p, q = A[i], A[(i + 1) % len(A)]
        for j in range(len(B)):
            best = min(best, _seg_dist(p, q, B[j], B[(j + 1) % len(B)]))
            if best == 0.0:
                return 0.0
    return best


def verify(placed, W, gap):
    """exact check of a nested layout: every panel inside the roll strip [0, W], pairwise clearance.
    Pairs are visited in order of bounding-box separation and the search stops when that separation exceeds
    the smallest clearance found, so the returned minimum is exact.
    Returns (min_clearance_mm (inf for one panel), min_edge_margin_mm, overlapping_pairs)."""
    margin = min(min(min(y for _, y in q["poly"]), W - max(y for _, y in q["poly"])) for q in placed)
    box = [(min(x for x, _ in q["poly"]), max(x for x, _ in q["poly"]),
            min(y for _, y in q["poly"]), max(y for _, y in q["poly"])) for q in placed]
    pairs = []
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a, b = box[i], box[j]
            far = max(b[0] - a[1], a[0] - b[1], b[2] - a[3], a[2] - b[3], 0.0)
            pairs.append((far, i, j))
    pairs.sort()
    clear, bad = math.inf, []
    for far, i, j in pairs:
        if far > clear and far > 0:
            break
        c = poly_clearance(placed[i]["poly"], placed[j]["poly"])
        clear = min(clear, c)
        if c <= 0.0:
            bad.append((placed[i]["panel"], placed[j]["panel"]))
    return clear, margin, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patterns", help="JSON from cutting_pattern.py")
    ap.add_argument("--roll-width", type=float, default=None, help="usable roll width [mm] (default from JSON)")
    ap.add_argument("--gap", type=float, default=20.0, help="clearance between panels [mm]")
    ap.add_argument("--dx", type=float, default=25.0, help="raster step along the roll [mm]")
    ap.add_argument("--out", default="nest")
    a = ap.parse_args(argv)
    with open(a.patterns) as fh:
        data = json.load(fh)
    W = a.roll_width or data["roll_width"]
    print(f"Assumptions: warp along the roll (x), rotation 0/180 deg only; usable roll width {W:.0f} mm (selvedges "
          f"already deducted); clearance {a.gap:g} mm between CUT outlines (Chebyshev sense, so >= {a.gap:g} mm "
          f"Euclidean); raster step {a.dx:g} mm along the roll; greedy longest-first skyline (not an optimiser: "
          "compare with SVGnest/Deepnest or the cutter's nesting software for large jobs).")
    placed, length = nest(data["panels"], W, a.dx, a.gap)
    clear, margin, bad = verify(placed, W, a.gap)
    d = DXF()
    for ly, col in (("ROLL", "grey"), ("CUT", "red"), ("TEXT", "green")):
        d.layer(ly, col)
    d.line((0, 0), (length, 0), "ROLL")
    d.line((0, W), (length, W), "ROLL")
    d.line((0, 0), (0, W), "ROLL")
    d.line((length, 0), (length, W), "ROLL")
    th = max(W / 40, 20)
    for q in placed:
        d.polyline(q["poly"], "CUT", closed=True)
        d.text(f"{q['panel']}{' R180' if q['rot'] else ''}", q["label"], th, "TEXT", align_center=True)
    d.text(f"ROLL WIDTH {W:.0f} mm  LENGTH USED {length:.0f} mm  (warp along the roll)", (0, -2 * th), th, "TEXT")
    d.save(a.out + ".dxf")
    with open(a.out + ".csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["panel", "rotation_deg", "x_mm", "y_mm", "cut_area_m2", "net_area_m2"])
        for q in placed:
            wr.writerow([q["panel"], q["rot"], round(q["x"], 3), round(q["y"], 3), round(q["cut_area_m2"], 4),
                         round(q["net_area_m2"], 4)])
    net = sum(q["net_area_m2"] for q in placed)
    cutA = sum(q["cut_area_m2"] for q in placed)
    fabric = W * length / 1e6
    lb = cutA / (W / 1000)   # lower bound of the roll length [m]: cut area / roll width
    print(f"Nested {len(placed)} panels on a {W:.0f} mm roll: length used {length / 1000:.2f} m, fabric {fabric:.2f} m2"
          f" (lower bound cut area / roll width = {lb:.2f} m; used length is {(length / 1000 / lb - 1) * 100:.0f} % above it)")
    print(f"Utilisation: cut area {cutA:.2f} m2 / fabric = {cutA / fabric * 100:.0f} %; net membrane area {net:.2f} m2"
          f" / fabric = {net / fabric * 100:.0f} % (waste {100 - net / fabric * 100:.0f} %)")
    print(f"Verified (exact polygon geometry): min clearance between panels "
          f"{'n/a (single panel)' if clear == math.inf else f'{clear:.1f} mm'}, min margin to roll edge {margin:.1f} mm, "
          f"overlaps {len(bad)}")
    if bad or (clear < a.gap - 1e-6) or margin < -1e-6:
        print(f"ERROR: layout check failed: overlaps {bad}, clearance {clear:.2f} < {a.gap:g} or outside the roll")
    avgw = sum(p["W"] for p in data["panels"]) / len(data["panels"])
    if avgw < 0.6 * W and net / fabric < 0.6:
        print(f"ADVICE: panels average {avgw:.0f} mm on a {W:.0f} mm roll -> choose wider panels (cutting_pattern "
              "--strip) or a narrower roll to cut waste")
    print(f"Wrote {a.out}.dxf and {a.out}.csv")
    return placed, length


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
