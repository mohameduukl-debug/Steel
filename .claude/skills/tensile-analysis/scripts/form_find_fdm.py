#!/usr/bin/env python3
"""Force Density Method (FDM) form finding for cable nets and membrane meshes.

Pure-Python (standard library only). Implements the linear FDM of Schek (1974):

    D_ff · x_f = p_f − D_fs · x_s      (solved separately for x, y, z)

where D = Cᵀ Q C is the "force density matrix", f = free nodes, s = supports.
The geometry depends only on the *ratios* of force densities q = F/L, so after
solving the whole q-field is scaled so that the average membrane stress equals
the requested prestress (kN/m). Edge cables get a higher q (ratio --qc) to
control their sag.

Built-in generators
-------------------
  sail4   4-point hypar sail with free (cable) edges, 2 high + 2 low corners
  hypar   hypar with rigid (fully fixed) boundary, e.g. a frame-supported panel
  cone    conic tent: top ring (mast head) + outer anchors with edge cables
  --input model.json  your own nodes/edges (see reference/model-schema.md in
                      the tensile-structures skill)

Outputs
-------
  <out>.json   model + results (coordinates, edge forces, reactions, cable sags)
  <out>.obj    mesh for Rhino / Blender / any viewer (optional --obj)

Examples
--------
  python3 form_find_fdm.py sail4 --size 10 --high 3 --n 16 --qc 12 \
      --prestress 2.0 --out sail
  python3 form_find_fdm.py cone --R 8 --r 0.6 --H 5 --anchors 6 --nr 12 --nc 36 \
      --prestress 2.5 --out cone --obj
  python3 form_find_fdm.py --input mymodel.json --prestress 1.5 --out result

Limitations: FDM is a *form-finding* tool (equilibrium shape for a prestress
state). It is not a load analysis. Use the geometry as the starting point for
a geometrically non-linear analysis (wind/snow) in a dedicated FE package,
or with dynamic relaxation (see dynamic_relaxation.py).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict

Vec = list[float]


# ---------------------------------------------------------------- vectors
def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def norm(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


# ------------------------------------------------------------- generators
def _grid_idx(nu):
    return lambda i, j: j * (nu + 1) + i


def gen_sail4(size: float, high: float, n: int, qm: float, qc: float, rigid: bool):
    """Square plan, corners A(0,0,0) B(a,0,h) C(a,a,0) D(0,a,h)."""
    nu = nv = n
    idx = _grid_idx(nu)
    corners = [(0.0, 0.0, 0.0), (size, 0.0, high), (size, size, 0.0), (0.0, size, high)]
    nodes = []
    for j in range(nv + 1):
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            p = [0.0, 0.0, 0.0]
            w = [(1 - u) * (1 - v), u * (1 - v), u * v, (1 - u) * v]
            for k in range(3):
                p[k] = sum(w[c] * corners[c][k] for c in range(4))
            on_b = i in (0, nu) or j in (0, nv)
            is_corner = i in (0, nu) and j in (0, nv)
            nodes.append({"id": idx(i, j), "xyz": p,
                          "fixed": bool(is_corner or (rigid and on_b)),
                          "grid": [i, j]})
    edges = []

    def add(a, b, kind, q, group=None):
        e = {"id": len(edges), "n": [a, b], "q": q, "kind": kind}
        if group:
            e["group"] = group
        edges.append(e)

    for j in range(nv + 1):
        for i in range(nu):
            b = j in (0, nv)
            if b and rigid:
                continue  # edge between two fixed nodes carries nothing useful
            add(idx(i, j), idx(i + 1, j), "edge_cable" if b else "membrane",
                qc if b else qm, ("EC-S" if j == 0 else "EC-N") if b else None)
    for i in range(nu + 1):
        for j in range(nv):
            b = i in (0, nu)
            if b and rigid:
                continue
            add(idx(i, j), idx(i, j + 1), "edge_cable" if b else "membrane",
                qc if b else qm, ("EC-W" if i == 0 else "EC-E") if b else None)
    faces = [[idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)]
             for j in range(nv) for i in range(nu)]
    return {"units": {"length": "m", "force": "kN"},
            "type": "hypar" if rigid else "sail4",
            "grid": {"nu": nu, "nv": nv, "periodic_u": False},
            "nodes": nodes, "edges": edges, "faces": faces}


def gen_cone(R: float, r: float, H: float, anchors: int, nr: int, nc: int, qm: float, qc: float):
    """Conic tent. Grid i = hoop index (periodic, nc), j = ring index 0 (outer) .. nr (top ring)."""
    if nc % anchors:
        raise SystemExit("--nc must be a multiple of --anchors")
    step = nc // anchors
    idx = lambda i, j: j * nc + (i % nc)
    nodes = []
    for j in range(nr + 1):
        t = j / nr
        rad = R + (r - R) * t
        z = H * t
        for i in range(nc):
            a = 2 * math.pi * i / nc
            fixed = (j == nr) or (j == 0 and i % step == 0)
            nodes.append({"id": idx(i, j), "xyz": [rad * math.cos(a), rad * math.sin(a), z],
                          "fixed": fixed, "grid": [i, j]})
    edges = []
    for j in range(nr + 1):
        for i in range(nc):
            if j == nr:
                continue  # top ring: rigid steel ring, both nodes fixed
            outer = j == 0
            e = {"id": len(edges), "n": [idx(i, j), idx(i + 1, j)],
                 "q": qc if outer else qm, "kind": "edge_cable" if outer else "membrane"}
            if outer:
                e["group"] = f"EC-{i // step + 1}"
            edges.append(e)
    for j in range(nr):
        for i in range(nc):
            edges.append({"id": len(edges), "n": [idx(i, j), idx(i, j + 1)], "q": qm, "kind": "membrane"})
    faces = [[idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)]
             for j in range(nr) for i in range(nc)]
    return {"units": {"length": "m", "force": "kN"}, "type": "cone",
            "grid": {"nu": nc, "nv": nr, "periodic_u": True},
            "nodes": nodes, "edges": edges, "faces": faces}


# ---------------------------------------------------------------- solver
def solve_fdm(model: dict, loads: dict[int, Vec] | None = None, tol: float = 1e-10, maxit: int = 20000):
    nodes, edges = model["nodes"], model["edges"]
    n = len(nodes)
    fixed = [bool(nd.get("fixed")) for nd in nodes]
    X = [list(map(float, nd["xyz"])) for nd in nodes]
    free = [i for i in range(n) if not fixed[i]]
    pos = {g: k for k, g in enumerate(free)}
    diag = [0.0] * len(free)
    off: list[list[tuple[int, float]]] = [[] for _ in free]
    rhs = [[0.0, 0.0, 0.0] for _ in free]
    for e in edges:
        a, b = e["n"]
        q = float(e["q"])
        if q < 0:
            raise ValueError(f"edge {e['id']} has negative force density (compression)")
        for u, v in ((a, b), (b, a)):
            if fixed[u]:
                continue
            k = pos[u]
            diag[k] += q
            if fixed[v]:
                for c in range(3):
                    rhs[k][c] += q * X[v][c]
            else:
                off[k].append((pos[v], q))
    if loads:
        for g, p in loads.items():
            if not fixed[g]:
                for c in range(3):
                    rhs[pos[g]][c] += p[c]
    if any(d == 0 for d in diag):
        raise ValueError("a free node has no connected edges")

    def matvec(x):
        return [diag[k] * x[k] - sum(q * x[m] for m, q in off[k]) for k in range(len(x))]

    iters = 0
    for c in range(3):
        b = [r[c] for r in rhs]
        x = [X[g][c] for g in free]  # warm start from initial geometry
        r = [bi - ai for bi, ai in zip(b, matvec(x))]
        z = [ri / d for ri, d in zip(r, diag)]
        p = z[:]
        rz = sum(ri * zi for ri, zi in zip(r, z))
        bn = math.sqrt(sum(bi * bi for bi in b)) or 1.0
        for it in range(maxit):
            if math.sqrt(sum(ri * ri for ri in r)) / bn < tol:
                break
            Ap = matvec(p)
            alpha = rz / sum(pi * api for pi, api in zip(p, Ap))
            x = [xi + alpha * pi for xi, pi in zip(x, p)]
            r = [ri - alpha * api for ri, api in zip(r, Ap)]
            z = [ri / d for ri, d in zip(r, diag)]
            rz_new = sum(ri * zi for ri, zi in zip(r, z))
            p = [zi + (rz_new / rz) * pi for zi, pi in zip(z, p)]
            rz = rz_new
        iters = max(iters, it)
        for k, g in enumerate(free):
            X[g][c] = x[k]
    for g in range(n):
        nodes[g]["xyz"] = X[g]
    return iters


# --------------------------------------------------------------- results
def tributary_widths(model: dict) -> dict[int, float]:
    """Approximate width of membrane carried by each grid edge (for stress = F / w)."""
    g = model.get("grid")
    if not g:
        return {}
    nu, nv, per = g["nu"], g["nv"], g.get("periodic_u", False)
    ncol = nu if per else nu + 1
    X = [nd["xyz"] for nd in model["nodes"]]

    def P(i, j):
        if per:
            i %= nu
        return X[j * ncol + i]

    def valid(i, j):
        return 0 <= j <= nv and (per or 0 <= i <= nu)

    def half_span(i, j, di, dj):
        """half the distance to neighbours across direction (di,dj)."""
        pts = [(i + di, j + dj), (i - di, j - dj)]
        ds = [norm(sub(P(*q), P(i, j))) for q in pts if valid(*q)]
        return sum(ds) / 2 if len(ds) == 2 else (ds[0] / 2 if ds else 0.0)

    w = {}
    for e in model["edges"]:
        if e["kind"] != "membrane":
            continue
        a, b = e["n"]
        ia, ja = model["nodes"][a]["grid"]
        ib, jb = model["nodes"][b]["grid"]
        if ja == jb:  # u-direction edge -> width measured across v
            w[e["id"]] = 0.5 * (half_span(ia, ja, 0, 1) + half_span(ib, jb, 0, 1))
        else:
            w[e["id"]] = 0.5 * (half_span(ia, ja, 1, 0) + half_span(ib, jb, 1, 0))
    return w


def compute_results(model: dict, prestress: float | None):
    X = [nd["xyz"] for nd in model["nodes"]]
    for e in model["edges"]:
        a, b = e["n"]
        e["length"] = norm(sub(X[b], X[a]))
        e["force"] = e["q"] * e["length"]
    widths = tributary_widths(model)
    scale = 1.0
    if prestress and widths:
        stresses = [model["edges"][k]["force"] / w for k, w in widths.items() if w > 0]
        mean = sum(stresses) / len(stresses)
        scale = prestress / mean
    for e in model["edges"]:
        e["q"] *= scale
        e["force"] *= scale
        if e["id"] in widths and widths[e["id"]] > 0:
            e["width"] = widths[e["id"]]
            e["stress_kN_m"] = e["force"] / widths[e["id"]]
    # reactions = force applied BY the structure ON each support (pull), kN
    reac = defaultdict(lambda: [0.0, 0.0, 0.0])
    for e in model["edges"]:
        a, b = e["n"]
        for u, v in ((a, b), (b, a)):
            if model["nodes"][u].get("fixed"):
                d = sub(X[v], X[u])
                for c in range(3):
                    reac[u][c] += e["q"] * d[c]
    model["reactions"] = [{"node": k, "pull": [round(c, 4) for c in v], "magnitude": round(norm(v), 4)}
                          for k, v in sorted(reac.items())]
    # cable groups: max force + sag relative to the chord between group ends
    groups = defaultdict(list)
    for e in model["edges"]:
        if e.get("group"):
            groups[e["group"]].append(e)
    summary = []
    for gname, es in sorted(groups.items()):
        cnt = defaultdict(int)
        for e in es:
            for v in e["n"]:
                cnt[v] += 1
        ends = [v for v, c in cnt.items() if c == 1]
        info = {"group": gname, "segments": len(es),
                "force_max": max(e["force"] for e in es), "force_min": min(e["force"] for e in es),
                "length": sum(e["length"] for e in es)}
        if len(ends) == 2:
            A, B = X[ends[0]], X[ends[1]]
            ch = sub(B, A)
            L = norm(ch)
            sag = max(norm(cross(sub(X[v], A), ch)) / L for v in cnt)
            info.update({"chord": L, "sag": sag, "sag_ratio": sag / L,
                         "radius_approx": (L * L / (8 * sag) + sag / 2) if sag > 0 else math.inf})
        summary.append(info)
    model["cable_groups"] = summary
    mem = [e for e in model["edges"] if e["kind"] == "membrane" and "stress_kN_m" in e]
    if mem:
        s = [e["stress_kN_m"] for e in mem]
        model["membrane_stress"] = {"min": min(s), "max": max(s), "mean": sum(s) / len(s),
                                    "note": "stress = edge force / tributary width (grid estimate)"}
    return scale


def surface_area(model: dict) -> float:
    X = [nd["xyz"] for nd in model["nodes"]]
    A = 0.0
    for f in model.get("faces", []):
        for k in range(1, len(f) - 1):
            A += 0.5 * norm(cross(sub(X[f[k]], X[f[0]]), sub(X[f[k + 1]], X[f[0]])))
    return A


def write_obj(model: dict, path: str) -> None:
    with open(path, "w") as fh:
        fh.write(f"# FDM form-found mesh ({model.get('type', 'custom')})\n")
        for nd in model["nodes"]:
            fh.write("v {:.6f} {:.6f} {:.6f}\n".format(*nd["xyz"]))
        for f in model.get("faces", []):
            fh.write("f " + " ".join(str(i + 1) for i in f) + "\n")
        for e in model["edges"]:
            if e["kind"] != "membrane":
                fh.write(f"l {e['n'][0] + 1} {e['n'][1] + 1}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shape", nargs="?", choices=["sail4", "hypar", "cone"], help="built-in generator")
    ap.add_argument("--input", help="custom model JSON")
    ap.add_argument("--size", type=float, default=10.0, help="sail/hypar plan side [m]")
    ap.add_argument("--high", type=float, default=3.0, help="height of high corners [m]")
    ap.add_argument("--n", type=int, default=16, help="mesh divisions per side")
    ap.add_argument("--R", type=float, default=8.0, help="cone outer radius [m]")
    ap.add_argument("--r", type=float, default=0.6, help="cone top ring radius [m]")
    ap.add_argument("--H", type=float, default=5.0, help="cone height [m]")
    ap.add_argument("--anchors", type=int, default=6)
    ap.add_argument("--nr", type=int, default=12)
    ap.add_argument("--nc", type=int, default=36)
    ap.add_argument("--qm", type=float, default=1.0, help="membrane force density (relative)")
    ap.add_argument("--qc", type=float, default=10.0, help="edge-cable force density (relative)")
    ap.add_argument("--prestress", type=float, default=None,
                    help="target mean membrane prestress [kN/m]; scales all forces")
    ap.add_argument("--out", default="formfound")
    ap.add_argument("--obj", action="store_true", help="also write an OBJ mesh")
    a = ap.parse_args(argv)

    if a.input:
        with open(a.input) as fh:
            model = json.load(fh)
    elif a.shape == "sail4":
        model = gen_sail4(a.size, a.high, a.n, a.qm, a.qc, rigid=False)
    elif a.shape == "hypar":
        model = gen_sail4(a.size, a.high, a.n, a.qm, a.qc, rigid=True)
    elif a.shape == "cone":
        model = gen_cone(a.R, a.r, a.H, a.anchors, a.nr, a.nc, a.qm, a.qc)
    else:
        ap.error("give a shape or --input")

    loads = {int(k): v for k, v in model.get("loads", {}).items()} if model.get("loads") else None
    iters = solve_fdm(model, loads)
    scale = compute_results(model, a.prestress)
    model["surface_area_m2"] = surface_area(model)
    model["solver"] = {"method": "FDM (Schek 1974), Jacobi-PCG", "cg_iterations": iters, "q_scale": scale}

    with open(a.out + ".json", "w") as fh:
        json.dump(model, fh, indent=1)
    if a.obj:
        write_obj(model, a.out + ".obj")

    print(f"Form found: {model.get('type', 'custom')}  nodes={len(model['nodes'])} "
          f"edges={len(model['edges'])}  surface area={model['surface_area_m2']:.2f} m2")
    if "membrane_stress" in model:
        ms = model["membrane_stress"]
        print(f"Membrane prestress (grid estimate) kN/m: mean {ms['mean']:.2f}  "
              f"min {ms['min']:.2f}  max {ms['max']:.2f}")
    if model["cable_groups"]:
        print("\nCable group        Fmax[kN]  Fmin[kN]  chord[m]  sag[m]  sag/chord  R~[m]")
        for g in model["cable_groups"]:
            print(f"  {g['group']:<16}{g['force_max']:9.2f}{g['force_min']:10.2f}"
                  f"{g.get('chord', float('nan')):10.2f}{g.get('sag', float('nan')):8.3f}"
                  f"{g.get('sag_ratio', float('nan')):10.3f}{g.get('radius_approx', float('nan')):8.2f}")
    print("\nSupport pulls (force from structure on support) [kN]:")
    for rc in model["reactions"][:24]:
        x, y, z = rc["pull"]
        print(f"  node {rc['node']:>5}:  Fx={x:9.2f} Fy={y:9.2f} Fz={z:9.2f}  |F|={rc['magnitude']:9.2f}")
    if len(model["reactions"]) > 24:
        print(f"  ... {len(model['reactions']) - 24} more in {a.out}.json")
    print(f"\nWrote {a.out}.json" + (f", {a.out}.obj" if a.obj else ""))
    return model


if __name__ == "__main__":
    main(sys.argv[1:])
