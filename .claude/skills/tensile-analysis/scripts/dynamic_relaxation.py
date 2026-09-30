#!/usr/bin/env python3
"""Dynamic Relaxation (DR) load analysis of a form-found cable net / membrane mesh.

Pure-Python. Takes the JSON written by form_find_fdm.py (prestress state) and
applies wind pressure and/or snow load, solving the geometrically NON-LINEAR
equilibrium with the kinetic-damping DR method (Day 1965, Barnes 1977/1999).

Model ("cable-net analogy" of the membrane):
  * every edge is an axial, TENSION-ONLY link (slack when shortened below its
    unstressed length) -> slack membrane links = wrinkling indicator;
  * membrane link stiffness EA = E·t [kN/m] × tributary width [m]
    (u-direction links use --Et-u (warp), v-direction links --Et-v (weft));
  * cable stiffness EA [kN] from --EA-cable (or per-edge "EA" in the JSON);
  * unstressed length L0 = L / (1 + F0/EA) from the form-finding prestress F0;
  * pressure is a follower load normal to the current surface;
    snow is a vertical load on plan area.

This is a PRELIMINARY analysis tool: it ignores shear stiffness and Poisson
coupling of the fabric. Final design needs an orthotropic membrane FE analysis
(Sofistik, Easy, ixForten, RFEM, GSA …) — see the tensile-analysis skill.

Examples
--------
  python3 dynamic_relaxation.py sail.json --Et-u 800 --Et-v 600 --EA-cable 14000 \
      --pressure 0.9 --out sail_wind_up
  python3 dynamic_relaxation.py sail.json --Et-u 800 --Et-v 600 --EA-cable 14000 \
      --snow 0.75 --out sail_snow

Sign convention: --pressure > 0 pushes along the surface normal oriented
upward (+z side), i.e. wind UPLIFT/suction; < 0 = downward wind pressure.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from collections import defaultdict


def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def norm(a):
    return math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def edge_direction(model, e):
    """'u' or 'v' for grid membrane edges, None otherwise."""
    a, b = e["n"]
    ga, gb = model["nodes"][a].get("grid"), model["nodes"][b].get("grid")
    if not ga or not gb:
        return None
    return "u" if ga[1] == gb[1] else "v"


def prepare(model, Et_u, Et_v, EA_cable):
    for e in model["edges"]:
        if "EA" in e:
            EA = float(e["EA"])
        elif e["kind"] == "membrane":
            w = e.get("width", 1.0)
            EA = (Et_u if edge_direction(model, e) == "u" else Et_v) * w
        else:
            EA = EA_cable
        e["EA"] = EA
        F0 = e.get("force", 0.0)
        e["L0"] = e["length"] / (1.0 + F0 / EA)


def external_loads(model, X, pressure, snow):
    P = defaultdict(lambda: [0.0, 0.0, 0.0])
    for f in model.get("faces", []):
        for k in range(1, len(f) - 1):
            tri = (f[0], f[k], f[k + 1])
            A2 = cross(sub(X[tri[1]], X[tri[0]]), sub(X[tri[2]], X[tri[0]]))  # 2*area*normal
            if A2[2] < 0:
                A2 = [-c for c in A2]  # orient normal upward
            for v in tri:
                for c in range(3):
                    P[v][c] += pressure * A2[c] / 6.0
                P[v][2] -= snow * abs(A2[2]) / 6.0  # projected (plan) area
    return P


def relax(model, pressure=0.0, snow=0.0, tol=1e-4, maxit=200000, verbose=False):
    nodes, edges = model["nodes"], model["edges"]
    X = [list(nd["xyz"]) for nd in nodes]
    fixed = [bool(nd.get("fixed")) for nd in nodes]
    n = len(nodes)
    V = [[0.0, 0.0, 0.0] for _ in range(n)]
    KE_prev = 0.0
    it = 0
    Rmax = math.inf
    for it in range(maxit):
        P = external_loads(model, X, pressure, snow) if (pressure or snow) else {}
        R = [list(P.get(i, [0.0, 0.0, 0.0])) for i in range(n)]
        S = [0.0] * n  # nodal stiffness for fictitious mass
        for e in edges:
            a, b = e["n"]
            d = sub(X[b], X[a])
            L = norm(d)
            T = e["EA"] * (L - e["L0"]) / e["L0"]
            if T < 0:
                T = 0.0  # tension-only (slack cable / wrinkled membrane)
            e["_T"], e["_L"] = T, L
            k = e["EA"] / e["L0"] + T / L
            S[a] += k
            S[b] += k
            for c in range(3):
                f = T * d[c] / L
                R[a][c] += f
                R[b][c] -= f
        Rmax = max((norm(R[i]) for i in range(n) if not fixed[i]), default=0.0)
        if Rmax < tol:
            break
        KE = 0.0
        for i in range(n):
            if fixed[i]:
                continue
            m = max(S[i], 1e-9)  # dt = 1, m = S*dt^2/2 * 2 (safety factor 2)
            for c in range(3):
                V[i][c] += R[i][c] / m
            KE += m * (V[i][0] ** 2 + V[i][1] ** 2 + V[i][2] ** 2)
        if KE < KE_prev:  # kinetic energy peak passed -> kinetic damping reset
            for i in range(n):
                V[i] = [0.0, 0.0, 0.0]
            KE = 0.0
        KE_prev = KE
        for i in range(n):
            if not fixed[i]:
                for c in range(3):
                    X[i][c] += V[i][c]
        if verbose and it % 2000 == 0:
            print(f"  it {it:6d}  max residual {Rmax:.3e} kN", file=sys.stderr)
    return X, it, Rmax


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", help="JSON from form_find_fdm.py")
    ap.add_argument("--Et-u", type=float, default=800.0, help="membrane E·t, u (warp) links [kN/m]")
    ap.add_argument("--Et-v", type=float, default=600.0, help="membrane E·t, v (weft) links [kN/m]")
    ap.add_argument("--EA-cable", type=float, default=14000.0, help="cable EA [kN]")
    ap.add_argument("--pressure", type=float, default=0.0, help="normal pressure [kN/m2], + = uplift")
    ap.add_argument("--snow", type=float, default=0.0, help="snow on plan [kN/m2]")
    ap.add_argument("--tol", type=float, default=1e-4, help="residual tolerance [kN]")
    ap.add_argument("--maxit", type=int, default=200000)
    ap.add_argument("--out", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)

    with open(a.model) as fh:
        base = json.load(fh)
    model = copy.deepcopy(base)
    prepare(model, a.Et_u, a.Et_v, a.EA_cable)
    X0 = [list(nd["xyz"]) for nd in model["nodes"]]
    X, it, Rmax = relax(model, a.pressure, a.snow, a.tol, a.maxit, a.verbose)

    disp = [norm(sub(X[i], X0[i])) for i in range(len(X))]
    imax = max(range(len(X)), key=lambda i: disp[i])
    for i, nd in enumerate(model["nodes"]):
        nd["xyz"] = X[i]
        nd["disp"] = sub(X[i], X0[i])
    slack = []
    for e in model["edges"]:
        e["force"] = e.pop("_T")
        e["length"] = e.pop("_L")
        if e["kind"] == "membrane" and e.get("width"):
            e["stress_kN_m"] = e["force"] / e["width"]
        if e["force"] <= 1e-9:
            slack.append(e["id"])
    reac = defaultdict(lambda: [0.0, 0.0, 0.0])
    for e in model["edges"]:
        a_, b_ = e["n"]
        d = sub(X[b_], X[a_])
        L = norm(d)
        for u, sgn in ((a_, 1), (b_, -1)):
            if model["nodes"][u].get("fixed"):
                for c in range(3):
                    reac[u][c] += sgn * e["force"] * d[c] / L
    # surface load falling directly on support nodes also goes into the support
    if a.pressure or a.snow:
        for u, p in external_loads(model, X, a.pressure, a.snow).items():
            if model["nodes"][u].get("fixed"):
                for c in range(3):
                    reac[u][c] += p[c]
    model["reactions"] = [{"node": k, "pull": v, "magnitude": norm(v)} for k, v in sorted(reac.items())]
    mem = [e for e in model["edges"] if e["kind"] == "membrane" and "stress_kN_m" in e]
    cab = [e for e in model["edges"] if e["kind"] != "membrane"]
    model["analysis"] = {"method": "dynamic relaxation, kinetic damping, tension-only links",
                         "pressure_kN_m2": a.pressure, "snow_kN_m2": a.snow,
                         "iterations": it, "max_residual_kN": Rmax,
                         "max_displacement_m": disp[imax], "max_disp_node": imax,
                         "slack_links": len(slack)}

    print(f"DR converged in {it} iterations (max residual {Rmax:.2e} kN)"
          + ("" if Rmax < a.tol else "  ** NOT CONVERGED – raise --maxit **"))
    print(f"Load: pressure {a.pressure:+.3f} kN/m2, snow {a.snow:.3f} kN/m2")
    print(f"Max displacement {disp[imax] * 1000:.0f} mm at node {imax}")
    if mem:
        s = [e["stress_kN_m"] for e in mem]
        print(f"Membrane stress kN/m (net estimate): max {max(s):.2f}   min {min(s):.2f}")
    if cab:
        print(f"Max cable force {max(e['force'] for e in cab):.2f} kN")
    by_group = defaultdict(float)
    for e in cab:
        if e.get("group"):
            by_group[e["group"]] = max(by_group[e["group"]], e["force"])
    for g, f in sorted(by_group.items()):
        print(f"   {g:<12} Fmax = {f:8.2f} kN")
    print(f"Slack (wrinkled) links: {len(slack)} of {len(model['edges'])}"
          + ("  -> check prestress/curvature" if slack else ""))
    print("Support pulls [kN]:")
    for rc in model["reactions"][:12]:
        x, y, z = rc["pull"]
        print(f"  node {rc['node']:>5}: Fx={x:9.2f} Fy={y:9.2f} Fz={z:9.2f} |F|={rc['magnitude']:9.2f}")
    if a.out:
        with open(a.out + ".json", "w") as fh:
            json.dump(model, fh, indent=1)
        print(f"Wrote {a.out}.json")
    return model


if __name__ == "__main__":
    main(sys.argv[1:])
