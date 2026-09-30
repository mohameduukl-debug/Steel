#!/usr/bin/env python3
"""Nest cutting patterns on the fabric roll (strip packing) -> nested DXF + roll consumption.

Reads the <out>.json written by cutting_pattern.py. Panels keep the warp along the roll
(x = roll length); only 0° or 180° rotation is allowed (fabric warp/weft must not change).
Raster "skyline" nesting: every panel is described per x-column (step --dx) by the y-interval it
occupies; panels are placed longest-first at the smallest x where their columns fit between
the roll edges and the already placed panels (with a clearance --gap). This interlocks curved
("banana") panels far better than bounding boxes.

Outputs: <out>.dxf (roll edges, nested CUT outlines, labels, roll length), <out>.csv (panel
positions) and a printed summary (roll length used, fabric area, utilisation, waste).

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


def columns(poly, dx):
    """per-column occupied y-interval [ymin, ymax] of a polygon (x from 0), sampled on column edges and centre."""
    xs = [p[0] for p in poly]
    x0, x1 = min(xs), max(xs)
    n = max(1, int(math.ceil((x1 - x0) / dx)))
    cols = []
    for k in range(n):
        lo, hi = math.inf, -math.inf
        for xq in (x0 + k * dx, x0 + (k + 0.5) * dx, min(x0 + (k + 1) * dx, x1)):
            for i in range(len(poly)):
                (a, b), (c, d) = poly[i], poly[(i + 1) % len(poly)]
                if (a - xq) * (c - xq) <= 0 and a != c:
                    y = b + (d - b) * (xq - a) / (c - a)
                    lo, hi = min(lo, y), max(hi, y)
        # vertices inside the column (sharp corners)
        for (a, b) in poly:
            if x0 + k * dx <= a <= x0 + (k + 1) * dx:
                lo, hi = min(lo, b), max(hi, b)
        cols.append((lo, hi))
    return cols, x0


def rotate180(poly, L, W):
    return [(L - x, W - y) for x, y in poly]


def fits(occ, x0, cols, yoff, W, gap):
    for k, (lo, hi) in enumerate(cols):
        a, b = lo + yoff - gap, hi + yoff + gap
        if lo + yoff < 0 or hi + yoff > W:
            return False
        for (u, v) in occ.get(x0 + k, ()):
            if a < v and u < b:
                return False
    return True


def nest(panels, W, dx, gap):
    occ = {}   # column index -> list of (ymin, ymax)
    placed = []
    order = sorted(panels, key=lambda p: -p["L"])
    for p in order:
        best = None
        for rot in (0, 180):
            poly = p["cut"] if rot == 0 else rotate180(p["cut"], p["L"], p["W"])
            cols, xmin = columns(poly, dx)
            ymin = min(lo for lo, _ in cols)
            ymax = max(hi for _, hi in cols)
            if ymax - ymin > W + 1e-6:
                continue
            # candidate vertical offsets: against the lower edge, the upper edge, and every 50 mm
            yoffs = sorted({-ymin, W - ymax} | {-ymin + s for s in range(0, int(W - (ymax - ymin)) + 1, 50)})
            x0 = 0
            while True:
                ok = None
                for yo in yoffs:
                    if fits(occ, x0, cols, yo, W, gap):
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
                       "label": (x0 * dx + p["L"] / 2, yo + (min(lo for lo, _ in cols) + max(hi for _, hi in cols)) / 2)})
    length = max(max(x for x, _ in q["poly"]) for q in placed)
    return placed, length


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
    placed, length = nest(data["panels"], W, a.dx, a.gap)
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
        wr.writerow(["panel", "rotation_deg", "x_mm", "y_mm"])
        for q in placed:
            wr.writerow([q["panel"], q["rot"], round(q["x"], 1), round(q["y"], 1)])
    net = sum(q["net_area_m2"] for q in placed)
    fabric = W * length / 1e6
    print(f"Nested {len(placed)} panels on a {W:.0f} mm roll: length used {length / 1000:.2f} m, fabric {fabric:.2f} m2")
    print(f"Net membrane area {net:.2f} m2 -> utilisation {net / fabric * 100:.0f} %, waste {100 - net / fabric * 100:.0f} %")
    avgw = sum(p["W"] for p in data["panels"]) / len(data["panels"])
    if avgw < 0.6 * W and net / fabric < 0.6:
        print(f"ADVICE: panels average {avgw:.0f} mm on a {W:.0f} mm roll -> choose wider panels (cutting_pattern "
              "--strip) or a narrower roll to cut waste")
    print(f"Wrote {a.out}.dxf and {a.out}.csv")
    return placed, length


if __name__ == "__main__":
    main(sys.argv[1:])
