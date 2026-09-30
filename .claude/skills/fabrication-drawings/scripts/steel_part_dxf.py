#!/usr/bin/env python3
"""Parametric steel PART drawings (DXF) for tensile-structure connection plates.

  lug     single lug / gusset plate for a cable fork (EN 1993-1-8 Tab 3.9 type A
          geometry): rectangular base, rounded head (radius = c + d0/2 or given),
          pin hole, optional cheek plates, dimensions, notes, title block.
  corner  corner plate from a hole list (pin holes for edge-cable forks, anchor
          hole, membrane-plate bolt holes): outline = convex hull of the holes
          offset by an edge distance, arcs approximated; dimensions from the
          anchor hole to every hole; hole table.

Units mm. Output is plotter/CAD ready R12 DXF (layers OUTLINE, HOLES, CENTER,
DIM, TEXT, TITLE).

Examples
--------
  python3 steel_part_dxf.py lug --d0 41 --t 20 --a 50 --c 35 --base 160 --height 120 \
        --grade S355J2 --mark LP-01 --qty 4 --out LP-01
  python3 steel_part_dxf.py corner --t 25 --edge 45 \
        --hole A:0:0:52 --hole EC1:180:48:33 --hole EC2:48:180:33 \
        --hole M1:95:95:18 --hole M2:130:60:18 --hole M3:60:130:18 --mark CP-01 --out CP-01
      (hole = name:x:y:diameter, relative to the anchor pin A)
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxf_writer import DXF  # noqa: E402


def setup(d: DXF):
    for ly, col in (("OUTLINE", "white"), ("HOLES", "red"), ("CENTER", "yellow"), ("DIM", "cyan"),
                    ("TEXT", "green"), ("TITLE", "grey")):
        d.layer(ly, col)


def centre_mark(d, c, r):
    e = 1.4 * r
    d.line((c[0] - e, c[1]), (c[0] + e, c[1]), "CENTER")
    d.line((c[0], c[1] - e), (c[0], c[1] + e), "CENTER")


def lug(a):
    d = DXF()
    setup(d)
    R = a.radius or (a.c + a.d0 / 2)
    W = max(a.base, 2 * R)
    # plate: base edge on y=0 (welded to the member), hole centre at (0, H)
    H = a.height
    top = H + a.a + a.d0 / 2  # plate end beyond hole along force direction
    pts = [(-W / 2, 0), (W / 2, 0), (W / 2, max(H - (W / 2 - R), 0.0) if W / 2 > R else H)]
    # tangent line from base corners to the head arc (simplified: straight flanks to arc start at hole level)
    n = 36
    arc = []
    # head: a circular cap of radius R about (0,H) from angle 0 to 180 deg, stretched to reach 'top'
    k = (top - H) / R  # vertical stretch so the end distance a is respected
    for i in range(n + 1):
        t = math.pi * i / n
        arc.append((R * math.cos(t), H + k * R * math.sin(t)))
    outline = [(-W / 2, 0), (W / 2, 0), (W / 2, H * 0.5)] + [(R, H)] + arc[1:-1] + [(-R, H), (-W / 2, H * 0.5)]
    d.polyline(outline, "OUTLINE", closed=True)
    d.circle((0, H), a.d0 / 2, "HOLES")
    centre_mark(d, (0, H), a.d0 / 2)
    th = max(W / 40, 3.5)
    d.dimension_text((-W / 2, 0), (W / 2, 0), -3 * th, th, "DIM")
    d.dimension_text((W / 2 + 0, 0), (W / 2 + 0, H), -3 * th, th, "DIM")
    d.dimension_text((0, H + a.d0 / 2), (0, top), -(R + 4 * th), th, "DIM")
    d.dimension_text((a.d0 / 2, H), (R, H), 2 * th, th, "DIM")
    d.text(f"%%c{a.d0:g} H11 (pin %%c{a.d:g})" if a.d else f"%%c{a.d0:g} H11", (a.d0 / 2 + th, H + a.d0 / 2 + th),
           th, "TEXT")
    notes = [f"{a.mark}  LUG PLATE  t = {a.t:g} mm  {a.grade}  QTY {a.qty}",
             f"a (end) = {a.a:g} mm   c (side) = {a.c:g} mm   R head = {R:g} mm",
             "Hole bored after welding/galvanising to H11 (EN 1090-2); deburr, radius arrises 2 mm.",
             f"Weld to member: {a.weld}",
             "Plate to lie in the plane of the cable (no out-of-plane eccentricity)."]
    if a.cheek:
        notes.append(f"Cheek plates 2 x t = {a.cheek:g} mm, bored together with lug in one operation.")
    y = -8 * th
    for s in notes:
        d.text(s, (-W / 2, y), th, "TEXT")
        y -= 1.8 * th
    d.frame(
                  {"PROJECT": a.project, "PART": f"LUG PLATE {a.mark}", "DWG No": a.mark, "REV": a.rev,
                   "SCALE": "1:1 (mm)", "DATE": date.today().isoformat(), "DRAWN": a.drawn, "CHECKED": "",
                   "MATERIAL": f"{a.grade}  t={a.t:g}", "EXC": a.exc}, th)
    d.save(a.out + ".dxf")
    print(f"Wrote {a.out}.dxf  (plate {W:.0f} x {top:.0f} x {a.t:g} mm, mass ≈ "
          f"{W * top * a.t * 7.85e-6 * 0.9:.1f} kg)")


def convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cr(o, a_, b):
        return (a_[0] - o[0]) * (b[1] - o[1]) - (a_[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cr(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cr(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def corner(a):
    holes = []
    for s in a.hole:
        nm, x, y, dia = s.split(":")
        holes.append((nm, float(x), float(y), float(dia)))
    # outline: hull of circles (hole radius + edge distance) sampled
    samples = []
    for _, x, y, dia in holes:
        r = dia / 2 + a.edge
        for i in range(48):
            t = 2 * math.pi * i / 48
            samples.append((round(x + r * math.cos(t), 3), round(y + r * math.sin(t), 3)))
    hull = convex_hull(samples)
    d = DXF()
    setup(d)
    d.polyline(hull, "OUTLINE", closed=True)
    xs = [p[0] for p in hull]
    ys = [p[1] for p in hull]
    th = max((max(xs) - min(xs)) / 45, 3.5)
    ax, ay = holes[0][1], holes[0][2]
    for k, (nm, x, y, dia) in enumerate(holes):
        d.circle((x, y), dia / 2, "HOLES")
        centre_mark(d, (x, y), dia / 2)
        d.text(nm, (x + dia / 2 + 0.5 * th, y + dia / 2 + 0.5 * th), th, "TEXT")
        if k:
            d.line((ax, ay), (x, y), "CENTER")
    ytab = min(ys) - 6 * th
    d.text(f"{a.mark}  CORNER PLATE  t = {a.t:g} mm  {a.grade}  QTY {a.qty}", (min(xs), ytab), 1.2 * th, "TEXT")
    ytab -= 2.2 * th
    d.text("HOLE   X      Y      DIA    dist from anchor", (min(xs), ytab), th, "TEXT")
    for nm, x, y, dia in holes:
        ytab -= 1.7 * th
        d.text(f"{nm:<6} {x - ax:7.1f} {y - ay:7.1f} {dia:6.1f}  {math.hypot(x - ax, y - ay):7.1f}",
               (min(xs), ytab), th, "TEXT")
    for s in ["Pin holes H11, bored after galvanising or clearance for zinc allowed.",
              "All lines of action to pass through anchor hole (checked with corner_plate.py).",
              f"Min. edge distance {a.edge:g} mm (check EN 1993-1-8 Tab 3.9 per hole).",
              "Radius all edges in contact with membrane; break sharp arrises."]:
        ytab -= 1.9 * th
        d.text(s, (min(xs), ytab), th, "TEXT")
    W, H = max(xs) - min(xs), max(ys) - min(ys)
    d.dimension_text((min(xs), min(ys) - 2 * th), (max(xs), min(ys) - 2 * th), -th, th, "DIM")
    d.dimension_text((max(xs) + 2 * th, min(ys)), (max(xs) + 2 * th, max(ys)), -th, th, "DIM")
    d.frame(
                  {"PROJECT": a.project, "PART": f"CORNER PLATE {a.mark}", "DWG No": a.mark, "REV": a.rev,
                   "SCALE": "1:1 (mm)", "DATE": date.today().isoformat(), "DRAWN": a.drawn, "CHECKED": "",
                   "MATERIAL": f"{a.grade}  t={a.t:g}", "EXC": a.exc}, th)
    d.save(a.out + ".dxf")
    area = 0.5 * abs(sum(hull[i][0] * hull[i - 1][1] - hull[i - 1][0] * hull[i][1] for i in range(len(hull))))
    print(f"Wrote {a.out}.dxf  (envelope {W:.0f} x {H:.0f} mm, t={a.t:g}, mass ≈ {area * a.t * 7.85e-6:.1f} kg)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("lug", "corner"):
        p = sp.add_parser(name)
        p.add_argument("--t", type=float, required=True, help="plate thickness [mm]")
        p.add_argument("--grade", default="S355J2+N")
        p.add_argument("--mark", default="P-01")
        p.add_argument("--qty", type=int, default=1)
        p.add_argument("--project", default="Tensile structure")
        p.add_argument("--rev", default="A")
        p.add_argument("--drawn", default="")
        p.add_argument("--exc", default="EXC2")
        p.add_argument("--out", default=None)
        if name == "lug":
            p.add_argument("--d0", type=float, required=True, help="hole diameter")
            p.add_argument("--d", type=float, default=None, help="pin diameter (annotation)")
            p.add_argument("--a", type=float, required=True, help="end distance beyond hole [mm]")
            p.add_argument("--c", type=float, required=True, help="side distance beside hole [mm]")
            p.add_argument("--radius", type=float, default=None)
            p.add_argument("--base", type=float, default=160.0, help="width at weld line [mm]")
            p.add_argument("--height", type=float, default=120.0, help="weld line to hole centre [mm]")
            p.add_argument("--cheek", type=float, default=None, help="cheek plate thickness [mm]")
            p.add_argument("--weld", default="double fillet a=8 all round (verify)")
        else:
            p.add_argument("--edge", type=float, required=True, help="edge distance around holes [mm]")
            p.add_argument("--hole", action="append", required=True, help="name:x:y:dia (first = anchor)")
    a = ap.parse_args(argv)
    a.out = a.out or a.mark
    (lug if a.cmd == "lug" else corner)(a)


if __name__ == "__main__":
    main(sys.argv[1:])
