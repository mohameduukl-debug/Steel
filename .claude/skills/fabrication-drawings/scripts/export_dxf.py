#!/usr/bin/env python3
"""Export a model / analysis JSON (form_find_fdm.py or dynamic_relaxation.py
output) to a 3D DXF for the General Arrangement, coordination with the steel
model (Tekla / Advance Steel / Revit / Rhino) and setting-out.

Layers
  MEMBRANE-MESH   membrane links (3D lines)          grey
  EDGE-CABLE      edge cables as 3D polylines        red
  CABLE           other cables / ties                magenta
  SUPPORT         fixed points (circle + id)         green
  SETOUT          text table with support coordinates yellow
  FORCES          optional: force labels on cables   cyan

Optional CSV (--csv): <out>_cables.csv (one line per cable group: kind, segments, end nodes and their
coordinates, node-to-node stressed length from the model geometry, closed loop, max force) and
<out>_setout.csv (every fixed node with X, Y, Z in mm). These are the GA-side numbers that the cable
schedule (cable_schedule.py --from-model) and the steel set-out must match.

Example:
  python3 export_dxf.py sail.json --out sail_GA --scale 1000 --forces --csv
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


def chain(edges):
    """Order the edges of one cable group into a node chain.
    Returns (nodes, closed). A closed loop (ring cable) returns its nodes once and closed=True.
    Raises ValueError if the group branches (a node with more than two segments) or is disconnected."""
    adj = defaultdict(list)
    for e in edges:
        a, b = e["n"]
        adj[a].append(b)
        adj[b].append(a)
    if any(len(n) > 2 for n in adj.values()):
        raise ValueError("cable group branches (node with > 2 segments)")
    ends = [v for v, n in adj.items() if len(n) == 1]
    start = ends[0] if ends else min(adj)
    out, prev, cur = [start], None, start
    closed = False
    while True:
        nxt = [v for v in adj[cur] if v != prev]
        if not nxt:
            break
        if nxt[0] == start:
            closed = True
            break
        prev, cur = cur, nxt[0]
        out.append(cur)
    if len(out) != len(adj):
        raise ValueError("cable group is not one connected chain")
    return out, closed


def polylength(P, closed=False):
    L = sum(math.dist(P[i - 1], P[i]) for i in range(1, len(P)))
    return L + (math.dist(P[-1], P[0]) if closed else 0.0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("--out", default="model_3d")
    ap.add_argument("--scale", type=float, default=1000.0, help="m -> mm")
    ap.add_argument("--forces", action="store_true", help="label cable groups with max force")
    ap.add_argument("--no-mesh", action="store_true", help="omit membrane mesh lines")
    ap.add_argument("--csv", action="store_true", help="also write <out>_cables.csv and <out>_setout.csv")
    ap.add_argument("--max-setout", type=int, default=60, help="max rows of the set-out table drawn in the DXF")
    a = ap.parse_args(argv)
    print(f"Assumptions: model coordinates x {a.scale:g} -> DXF units (mm when the model is in m, $INSUNITS = 4); "
          "geometry = the stressed (form-found / analysed) shape in the model axes, not an unstressed fabrication "
          "geometry; cable lengths are node-to-node along the model polyline (no fitting deductions, no temperature "
          "correction: use cable_schedule.py for fabrication lengths).")
    with open(a.model) as fh:
        m = json.load(fh)
    X = [[c * a.scale for c in nd["xyz"]] for nd in m["nodes"]]
    d = DXF()
    for ly, col in (("MEMBRANE-MESH", "grey"), ("EDGE-CABLE", "red"), ("CABLE", "magenta"),
                    ("SUPPORT", "green"), ("SETOUT", "yellow"), ("FORCES", "cyan")):
        d.layer(ly, col)
    groups = defaultdict(list)
    n_mesh = n_loose = 0
    for e in m["edges"]:
        if e["kind"] == "membrane":
            if not a.no_mesh:
                d.line(X[e["n"][0]], X[e["n"][1]], "MEMBRANE-MESH")
                n_mesh += 1
        elif e.get("group"):
            groups[e["group"]].append(e)
        else:
            d.line(X[e["n"][0]], X[e["n"][1]], "CABLE")
            n_loose += 1
    h = 0.01 * max(max(p[0] for p in X) - min(p[0] for p in X), 1.0)
    cab_rows = []
    for g, es in sorted(groups.items()):
        try:
            nodes, closed = chain(es)
        except ValueError as err:
            print(f"WARNING: group {g}: {err} -> drawn as separate lines")
            for e in es:
                d.line(X[e["n"][0]], X[e["n"][1]], "CABLE")
            continue
        layer = "EDGE-CABLE" if es[0]["kind"] == "edge_cable" else "CABLE"
        pts = [X[v] for v in nodes]
        d.polyline(pts, layer, closed=closed, three_d=True)
        fmax = max(e.get("force", 0.0) for e in es)
        if a.forces:
            mid = X[nodes[len(nodes) // 2]]
            d.text(f"{g}  Fmax={fmax:.1f} kN", mid, h, "FORCES")
        A, B = nodes[0], nodes[-1]
        cab_rows.append({"group": g, "kind": es[0]["kind"], "segments": len(es), "closed": closed,
                         "node_A": A, "node_B": B if not closed else A,
                         "XA_mm": round(X[A][0], 1), "YA_mm": round(X[A][1], 1), "ZA_mm": round(X[A][2], 1),
                         "XB_mm": round(X[B][0], 1), "YB_mm": round(X[B][1], 1), "ZB_mm": round(X[B][2], 1),
                         "L_node_stressed_mm": round(polylength(pts, closed), 1),
                         "chord_mm": round(math.dist(X[A], X[B]), 1), "F_max_kN": round(fmax, 2)})
    sup = [i for i, nd in enumerate(m["nodes"]) if nd.get("fixed")]
    corner_like = [i for i in sup if sum(1 for e in m["edges"] if i in e["n"]) <= 3] or sup
    y0 = min(p[1] for p in X) - 10 * h
    x0 = min(p[0] for p in X)
    d.text("SUPPORT SET-OUT (mm, model origin)", (x0, y0), 1.5 * h, "SETOUT")
    for r, i in enumerate(corner_like[:a.max_setout], 1):
        p = X[i]
        d.circle(p, h, "SUPPORT")
        d.text(f"S{i}", (p[0] + h, p[1] + h, p[2]), h, "SUPPORT")
        d.text(f"S{i}:  X={p[0]:.0f}  Y={p[1]:.0f}  Z={p[2]:.0f}", (x0, y0 - 2 * r * h), h, "SETOUT")
    d.save(a.out + ".dxf")
    print(f"Wrote {a.out}.dxf  ({len(m['edges'])} edges: {n_mesh} mesh lines, {len(cab_rows)} cable polylines, "
          f"{n_loose} loose cable lines; {len(sup)} supports, {min(len(corner_like), a.max_setout)} in the set-out table)")
    if len(corner_like) > a.max_setout:
        print(f"NOTE: {len(corner_like) - a.max_setout} support points not drawn in the set-out table "
              "(raise --max-setout or use --csv)")
    if a.csv:
        if cab_rows:
            with open(a.out + "_cables.csv", "w", newline="") as fh:
                wr = csv.DictWriter(fh, fieldnames=list(cab_rows[0]))
                wr.writeheader()
                wr.writerows(cab_rows)
        with open(a.out + "_setout.csv", "w", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(["support", "node", "X_mm", "Y_mm", "Z_mm"])
            for i in sup:
                wr.writerow([f"S{i}", i] + [round(c, 1) for c in X[i]])
        print(f"Wrote {a.out}_cables.csv ({len(cab_rows)} cables) and {a.out}_setout.csv ({len(sup)} supports)")
        for r in cab_rows:
            print(f"  {r['group']:<12}{r['kind']:<11}{r['segments']:4d} seg  L = {r['L_node_stressed_mm']:9.0f} mm"
                  f"{'  (closed loop)' if r['closed'] else ''}")
    return {"cables": cab_rows, "supports": sup}


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
