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

Example:
  python3 export_dxf.py sail.json --out sail_GA --scale 1000 --forces
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxf_writer import DXF  # noqa: E402


def chain(edges):
    """Order the edges of one cable group into a node chain."""
    adj = defaultdict(list)
    for e in edges:
        a, b = e["n"]
        adj[a].append(b)
        adj[b].append(a)
    ends = [v for v, n in adj.items() if len(n) == 1]
    start = ends[0] if ends else next(iter(adj))
    out, prev, cur = [start], None, start
    while True:
        nxt = [v for v in adj[cur] if v != prev]
        if not nxt or nxt[0] == start:
            break
        prev, cur = cur, nxt[0]
        out.append(cur)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("--out", default="model_3d")
    ap.add_argument("--scale", type=float, default=1000.0, help="m -> mm")
    ap.add_argument("--forces", action="store_true", help="label cable groups with max force")
    ap.add_argument("--no-mesh", action="store_true", help="omit membrane mesh lines")
    a = ap.parse_args(argv)
    with open(a.model) as fh:
        m = json.load(fh)
    X = [[c * a.scale for c in nd["xyz"]] for nd in m["nodes"]]
    d = DXF()
    for ly, col in (("MEMBRANE-MESH", "grey"), ("EDGE-CABLE", "red"), ("CABLE", "magenta"),
                    ("SUPPORT", "green"), ("SETOUT", "yellow"), ("FORCES", "cyan")):
        d.layer(ly, col)
    groups = defaultdict(list)
    for e in m["edges"]:
        if e["kind"] == "membrane":
            if not a.no_mesh:
                d.line(X[e["n"][0]], X[e["n"][1]], "MEMBRANE-MESH")
        elif e.get("group"):
            groups[e["group"]].append(e)
        else:
            d.line(X[e["n"][0]], X[e["n"][1]], "CABLE")
    h = 0.01 * max(max(p[0] for p in X) - min(p[0] for p in X), 1.0)
    for g, es in sorted(groups.items()):
        nodes = chain(es)
        layer = "EDGE-CABLE" if es[0]["kind"] == "edge_cable" else "CABLE"
        d.polyline([X[v] for v in nodes], layer, three_d=True)
        if a.forces:
            mid = X[nodes[len(nodes) // 2]]
            fmax = max(e.get("force", 0.0) for e in es)
            d.text(f"{g}  Fmax={fmax:.1f} kN", mid, h, "FORCES")
    sup = [i for i, nd in enumerate(m["nodes"]) if nd.get("fixed")]
    corner_like = [i for i in sup if sum(1 for e in m["edges"] if i in e["n"]) <= 3] or sup
    y0 = min(p[1] for p in X) - 10 * h
    x0 = min(p[0] for p in X)
    d.text("SUPPORT SET-OUT (mm, model origin)", (x0, y0), 1.5 * h, "SETOUT")
    for r, i in enumerate(corner_like[:60], 1):
        p = X[i]
        d.circle(p, h, "SUPPORT")
        d.text(f"S{i}", (p[0] + h, p[1] + h, p[2]), h, "SUPPORT")
        d.text(f"S{i}:  X={p[0]:.0f}  Y={p[1]:.0f}  Z={p[2]:.0f}", (x0, y0 - 2 * r * h), h, "SETOUT")
    d.save(a.out + ".dxf")
    print(f"Wrote {a.out}.dxf  ({len(m['edges'])} edges, {len(groups)} cable groups, {len(sup)} supports)")


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
