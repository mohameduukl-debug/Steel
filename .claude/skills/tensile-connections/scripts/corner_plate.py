#!/usr/bin/env python3
"""Corner-plate force resolution for membrane corners (edge cable + edge cable +
membrane strap/belt -> tie-back rod / mast head / anchor).

A corner plate must be in equilibrium with all lines of action meeting at ONE
point (the anchor pin), otherwise the plate rotates/twists and the membrane
corner wrinkles. The tool:

  * sums the member pulls and gives the required anchor force & direction,
  * reports the bisector of the two edge cables (membrane corner strap line),
  * checks concurrency: moment of the member forces about the anchor pin from
    the hole positions -> eccentricity; the plate should be re-shaped until ~0,
  * in 3D mode, finds the plate plane from the two edge cables and reports any
    out-of-plane force component (should be ~0: the plate must lie in that plane).

2D input  (angles in the plate plane, measured CCW from the plate x-axis,
           pointing FROM the plate TOWARD the member; x,y = hole position in mm
           relative to the anchor pin):
  python3 corner_plate.py --m EC1:15:48:180:40 --m EC2:105:52:40:180 \
                          --m strap:60:6:120:120

3D input  (direction = vector from corner to the member's far end; force kN):
  python3 corner_plate.py --v EC1:9.8:1.2:-2.1:48 --v EC2:1.0:10.1:-1.9:52 \
                          --v strap:5:5:-1.5:6

The first two members are taken as the edge cables.
"""
from __future__ import annotations

import argparse
import math
import sys


def unit(v):
    L = math.sqrt(sum(c * c for c in v))
    return [c / L for c in v]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def resolve2d(members):
    """Pure statics, no printing. members: (name, angle_deg, F[, x, y]). Returns a dict:
    Rx, Ry, R (resultant of the member pulls), anchor_angle (direction the anchor must pull), M (kN·mm about
    the anchor pin, from the hole positions; None without positions), e = M/R (mm), bisector and opening of
    the first two members (edge cables), deviation of the anchor line from the bisector."""
    Rx = sum(F * math.cos(math.radians(t)) for _, t, F, *_ in members)
    Ry = sum(F * math.sin(math.radians(t)) for _, t, F, *_ in members)
    R = math.hypot(Rx, Ry)
    ang = math.degrees(math.atan2(-Ry, -Rx))  # anchor must pull opposite to resultant
    M = None
    if all(len(m) >= 5 for m in members):
        M = 0.0
        for _, t, F, x, y in members:
            fx, fy = F * math.cos(math.radians(t)), F * math.sin(math.radians(t))
            M += x * fy - y * fx  # kN·mm about the anchor pin
    t1, t2 = members[0][1], members[1][1]
    bis = math.degrees(math.atan2(math.sin(math.radians(t1)) + math.sin(math.radians(t2)),
                                  math.cos(math.radians(t1)) + math.cos(math.radians(t2))))
    opening = abs((t2 - t1 + 180) % 360 - 180)
    dev = abs(((ang + 180) - bis + 180) % 360 - 180)
    return {"Rx": Rx, "Ry": Ry, "R": R, "anchor_angle": ang, "M": M, "e": (M / R if (M is not None and R) else None),
            "bisector": bis, "opening": opening, "deviation": dev}


def solve2d(members):
    r = resolve2d(members)
    R, ang = r["R"], r["anchor_angle"]
    print("Corner plate — 2D resolution")
    print("Assumptions: rigid plate, pin-ended members, forces of ONE load combination concurrent at the node; "
          "angles CCW from the plate x-axis toward the member; hole positions relative to the anchor pin.")
    print(f"{'member':<10}{'angle[deg]':>11}{'F[kN]':>9}")
    for m in members:
        print(f"{m[0]:<10}{m[1]:11.1f}{m[2]:9.2f}")
    print(f"\nResultant of members : {R:.2f} kN toward {math.degrees(math.atan2(r['Ry'], r['Rx'])):.1f} deg")
    print(f"Required anchor force: {R:.2f} kN acting at {ang:.1f} deg (tie-back / mast direction)")
    print(f"Edge-cable opening angle {r['opening']:.1f} deg, bisector at {r['bisector']:.1f} deg "
          f"(membrane corner strap should align with it)")
    print(f"Anchor line deviates {r['deviation']:.1f} deg from the bisector"
          + ("  (unequal edge-cable forces — expected)" if r["deviation"] > 2 else ""))
    if r["M"] is not None:
        e = r["e"] or 0.0
        print(f"\nMoment about anchor pin from hole layout: {r['M'] / 1000:.3f} kNm  -> eccentricity {e:.1f} mm")
        print("  OK: lines of action concurrent" if abs(e) < 5 else
              "  Re-shape plate: move holes so each member's line of action passes through the anchor pin")
    return R, ang


def resolve3d(members):
    """members: (name, [dx, dy, dz], F). Plate plane from the first two members (edge cables).
    Returns n (unit normal), Rv, R, anchor (unit), out-of-plane components F_i·(d_i·n), anchor tilt (deg),
    bisector and opening."""
    d = [unit(m[1]) for m in members]
    F = [m[2] for m in members]
    n = unit(cross(d[0], d[1]))
    Rv = [sum(F[i] * d[i][c] for i in range(len(d))) for c in range(3)]
    R = math.sqrt(dot(Rv, Rv))
    anchor = [-c / R for c in Rv]
    oop = dot(anchor, n)
    b = unit([d[0][c] + d[1][c] for c in range(3)])
    return {"n": n, "Rv": Rv, "R": R, "anchor": anchor, "oop": [F[i] * dot(d[i], n) for i in range(len(d))],
            "tilt_deg": math.degrees(math.asin(max(-1, min(1, oop)))), "bisector": b,
            "opening": math.degrees(math.acos(max(-1, min(1, dot(d[0], d[1])))))}


def solve3d(members):
    r = resolve3d(members)
    n, R, anchor = r["n"], r["R"], r["anchor"]
    print("Corner plate — 3D resolution (plate plane from the two edge cables)")
    print("Assumptions: member directions from the corner to the far end; plate plane = plane of the first "
          "two members; one load combination.")
    print(f"Plate normal n = ({n[0]:.3f}, {n[1]:.3f}, {n[2]:.3f})")
    print(f"{'member':<10}{'F[kN]':>9}{'out-of-plane[kN]':>18}")
    for i, m in enumerate(members):
        print(f"{m[0]:<10}{m[2]:9.2f}{r['oop'][i]:18.3f}")
    print(f"\nRequired anchor force {R:.2f} kN along ({anchor[0]:.3f}, {anchor[1]:.3f}, {anchor[2]:.3f})")
    print(f"Anchor direction out of plate plane: {r['tilt_deg']:.2f} deg"
          + ("  -> plate would twist; rotate plate or re-align tie-back" if abs(r['tilt_deg']) > 2.0 else "  OK"))
    b = r["bisector"]
    print(f"Edge-cable bisector ({b[0]:.3f}, {b[1]:.3f}, {b[2]:.3f}); opening {r['opening']:.1f} deg")
    return R, anchor


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--m", action="append", default=[], help="2D member name:angle:F[:x:y]")
    ap.add_argument("--v", action="append", default=[], help="3D member name:dx:dy:dz:F")
    a = ap.parse_args(argv)
    if a.m:
        ms = []
        for s in a.m:
            p = s.split(":")
            ms.append((p[0], *map(float, p[1:])))
        if len(ms) < 2:
            sys.exit("need at least the two edge cables")
        return solve2d(ms)
    if a.v:
        ms = []
        for s in a.v:
            p = s.split(":")
            ms.append((p[0], list(map(float, p[1:4])), float(p[4])))
        return solve3d(ms)
    ap.print_help()


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
