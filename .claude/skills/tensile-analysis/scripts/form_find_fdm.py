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
  arch    arch-supported tunnel (rigid parabolic arches, ground rails, free ends)
  multibay  ridge-and-valley roof (ridge/valley cables, scalloped edges)
  rings   membrane between two coaxial rigid rings (hourglass/catenoid, cone on a ring beam)
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
  python3 form_find_fdm.py rings --R 5 --r 5 --H 3 --nr 12 --nc 48 --prestress 2 \
      --uniform-stress --out hourglass      # isotropic uniform stress (catenoid)
  python3 form_find_fdm.py sail4 --n 24 --prestress 2 --uniform-stress --cable-force 16 \
      --out sail_us                         # soap-film sail, edge cables of radius 16/2 = 8 m

Linear FDM (default) gives the equilibrium for the q RATIOS: membrane stress is only
uniform where the grid is "isotropic" (w/L equal in both directions). --uniform-stress
finds a uniform isotropic stress state (soap-film-like): --us-method cst (default for
models with cables) uses the exact isotropic stress of every triangle (cotangent force
densities) with a constant force per cable (--cable-force; edge radius R = T/sigma) and
is robust at sail corners; --us-method width iterates q = sigma*w/L on the grid links
(default without cables). Both converge to the catenoid between two rings and the cst
method gives R = T/sigma on sail edges, O(h^2) (validated, reference/validation.md).

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


def gen_arch(L: float, B: float, H: float, n_arches: int, nu: int, nv: int, qm: float, qc: float):
    """Arch-supported tunnel. x = tunnel axis (0..L), y = span (0..B).
    Rigid parabolic arches z = 4H·y(B−y)/B² at x_k = k·L/(n_arches+1); side rails y=0, y=B fixed at z=0;
    free end edges at x=0 and x=L (edge cables anchored at the ground corners)."""
    step = n_arches + 1
    if nu % step:
        nu += step - nu % step
    idx = _grid_idx(nu)
    arch_i = {k * nu // step: f"ARCH-{k}" for k in range(1, step)}
    nodes = []
    for j in range(nv + 1):
        for i in range(nu + 1):
            x, y = L * i / nu, B * j / nv
            z_arch = 4 * H * y * (B - y) / (B * B)
            tag = None
            fixed = False
            if j in (0, nv):
                fixed, tag = True, "RAIL-S" if j == 0 else "RAIL-N"
            elif i in arch_i:
                fixed, tag = True, arch_i[i]
            nd = {"id": idx(i, j), "xyz": [x, y, 0.8 * z_arch], "fixed": fixed, "grid": [i, j]}
            if i in arch_i:
                nd["xyz"][2] = z_arch
            if tag:
                nd["support_group"] = tag
            nodes.append(nd)
    edges = []

    def add(a, b, kind, q, group=None):
        if nodes[a]["fixed"] and nodes[b]["fixed"]:
            return
        e = {"id": len(edges), "n": [a, b], "q": q, "kind": kind}
        if group:
            e["group"] = group
        edges.append(e)

    for j in range(nv + 1):
        for i in range(nu):
            add(idx(i, j), idx(i + 1, j), "membrane", qm)
    for i in range(nu + 1):
        for j in range(nv):
            end = i in (0, nu)
            add(idx(i, j), idx(i, j + 1), "edge_cable" if end else "membrane", qc if end else qm,
                ("EC-W" if i == 0 else "EC-E") if end else None)
    faces = [[idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)] for j in range(nv) for i in range(nu)]
    return {"units": {"length": "m", "force": "kN"}, "type": "arch",
            "grid": {"nu": nu, "nv": nv, "periodic_u": False}, "nodes": nodes, "edges": edges, "faces": faces}


def gen_multibay(n_bays: int, bay: float, B: float, h_hi: float, h_lo: float, m: int, nv: int,
                 qm: float, qr: float, qc: float):
    """Multi-bay ridge-and-valley roof. Lines x_k = k·bay/2 (k = 0..2·n_bays) span y = 0..B:
    even k = HIGH lines (k = 0, 2n are free edge cables, interior = ridge cables),
    odd k = VALLEY cables. Line ends are fixed (masts at high ends, anchors at low ends);
    the y = 0 / y = B boundaries between line ends are scalloped edge cables."""
    nu = 2 * n_bays * m
    idx = _grid_idx(nu)
    nodes = []
    for j in range(nv + 1):
        for i in range(nu + 1):
            k, r = divmod(i, m)
            z0 = h_hi if k % 2 == 0 else h_lo
            z1 = h_lo if k % 2 == 0 else h_hi
            z = z0 + (z1 - z0) * r / m
            fixed = j in (0, nv) and r == 0
            nd = {"id": idx(i, j), "xyz": [bay / 2 * i / m, B * j / nv, z], "fixed": fixed, "grid": [i, j]}
            if fixed:
                nd["support_group"] = ("MAST" if k % 2 == 0 else "ANCHOR") + f"-{k}-{'S' if j == 0 else 'N'}"
            nodes.append(nd)
    edges = []

    def add(a, b, kind, q, group=None):
        e = {"id": len(edges), "n": [a, b], "q": q, "kind": kind}
        if group:
            e["group"] = group
        edges.append(e)

    for j in range(nv + 1):
        for i in range(nu):
            if j in (0, nv):
                add(idx(i, j), idx(i + 1, j), "edge_cable", qc, f"EC-{'S' if j == 0 else 'N'}{i // m + 1}")
            else:
                add(idx(i, j), idx(i + 1, j), "membrane", qm)
    for i in range(nu + 1):
        k, r = divmod(i, m)
        for j in range(nv):
            if r == 0 and k in (0, 2 * n_bays):
                add(idx(i, j), idx(i, j + 1), "edge_cable", qc, "EC-W" if k == 0 else "EC-E")
            elif r == 0:
                add(idx(i, j), idx(i, j + 1), "cable", qr, (f"RIDGE-{k}" if k % 2 == 0 else f"VALLEY-{k}"))
            else:
                add(idx(i, j), idx(i, j + 1), "membrane", qm)
    faces = [[idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)] for j in range(nv) for i in range(nu)]
    return {"units": {"length": "m", "force": "kN"}, "type": "multibay",
            "grid": {"nu": nu, "nv": nv, "periodic_u": False}, "nodes": nodes, "edges": edges, "faces": faces}


def gen_rings(R: float, r: float, H: float, nr: int, nc: int, qm: float):
    """Membrane between two coaxial rigid rings: bottom ring radius R at z = 0, top ring radius r at z = H
    (hourglass / catenoid when R = r; conic tent on a ring beam when r < R). Grid i = hoop (periodic, nc),
    j = meridian 0 (bottom ring) .. nr (top ring). Both rings fixed (support groups RING-B, RING-T)."""
    idx = lambda i, j: j * nc + (i % nc)
    nodes = []
    for j in range(nr + 1):
        t = j / nr
        rad = R + (r - R) * t
        for i in range(nc):
            a = 2 * math.pi * i / nc
            nd = {"id": idx(i, j), "xyz": [rad * math.cos(a), rad * math.sin(a), H * t],
                  "fixed": j in (0, nr), "grid": [i, j]}
            if j in (0, nr):
                nd["support_group"] = "RING-B" if j == 0 else "RING-T"
            nodes.append(nd)
    edges = []
    for j in range(1, nr):
        for i in range(nc):
            edges.append({"id": len(edges), "n": [idx(i, j), idx(i + 1, j)], "q": qm, "kind": "membrane"})
    for j in range(nr):
        for i in range(nc):
            edges.append({"id": len(edges), "n": [idx(i, j), idx(i, j + 1)], "q": qm, "kind": "membrane"})
    faces = [[idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)] for j in range(nr) for i in range(nc)]
    return {"units": {"length": "m", "force": "kN"}, "type": "rings",
            "grid": {"nu": nc, "nv": nr, "periodic_u": True}, "nodes": nodes, "edges": edges, "faces": faces}


# ---------------------------------------------------------------- solver
def solve_fdm(model: dict, loads: dict[int, Vec] | None = None, tol: float = 1e-10, maxit: int = 20000,
              allow_negative: bool = False):
    """Linear FDM solve (Jacobi-PCG). allow_negative: accept q < 0 on some links (used by the CST
    uniform-stress form finding, whose cotangent force densities are negative opposite obtuse angles while the
    matrix stays positive definite: it is the P1 finite-element Laplacian of the surface)."""
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
        if q < 0 and not allow_negative:
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
    if any(d <= 0 for d in diag):
        raise ValueError("a free node has no connected edges (or a non-positive force-density sum)")

    # free-free couplings once per edge (matrix-free, O(edges) per product); the three coordinate
    # systems share the matrix, so the three Jacobi-PCG solves run in lockstep over one edge loop
    pairs = [(k, m, q) for k in range(len(free)) for m, q in off[k] if m > k]
    nf = len(free)

    def matvec3(px, py, pz):
        yx = [d * v for d, v in zip(diag, px)]
        yy = [d * v for d, v in zip(diag, py)]
        yz = [d * v for d, v in zip(diag, pz)]
        for k, m, q in pairs:
            yx[k] -= q * px[m]; yx[m] -= q * px[k]
            yy[k] -= q * py[m]; yy[m] -= q * py[k]
            yz[k] -= q * pz[m]; yz[m] -= q * pz[k]
        return yx, yy, yz

    def dotp(u, v):
        return sum(a_ * b_ for a_, b_ in zip(u, v))

    B = [[r[c] for r in rhs] for c in range(3)]
    Xs = [[X[g][c] for g in free] for c in range(3)]   # warm start from the initial geometry
    A0 = matvec3(*Xs)
    R = [[bi - ai for bi, ai in zip(B[c], A0[c])] for c in range(3)]
    Z = [[ri / d for ri, d in zip(R[c], diag)] for c in range(3)]
    P = [z[:] for z in Z]
    RZ = [dotp(R[c], Z[c]) for c in range(3)]
    BN = [math.sqrt(dotp(B[c], B[c])) or 1.0 for c in range(3)]
    done = [False] * 3
    iters = 0
    for it in range(maxit):
        for c in range(3):
            if not done[c] and math.sqrt(dotp(R[c], R[c])) / BN[c] < tol:
                done[c] = True
        if all(done) or nf == 0:
            break
        AP = matvec3(*P)
        for c in range(3):
            if done[c]:
                continue
            pap = dotp(P[c], AP[c])
            if pap <= 0:
                done[c] = True
                continue
            alpha = RZ[c] / pap
            Xs[c] = [xi + alpha * pi for xi, pi in zip(Xs[c], P[c])]
            R[c] = [ri - alpha * api for ri, api in zip(R[c], AP[c])]
            Z[c] = [ri / d for ri, d in zip(R[c], diag)]
            rz_new = dotp(R[c], Z[c])
            beta = rz_new / RZ[c] if RZ[c] else 0.0
            P[c] = [zi + beta * pi for zi, pi in zip(Z[c], P[c])]
            RZ[c] = rz_new
        iters = it + 1
    for c in range(3):
        for k, g in enumerate(free):
            X[g][c] = Xs[c][k]
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


def vertex_normals(model: dict) -> list:
    """Unit vertex normals from the faces (area-weighted; quads use the diagonal cross product)."""
    X = [nd["xyz"] for nd in model["nodes"]]
    N = [[0.0, 0.0, 0.0] for _ in X]
    for f in model.get("faces", []):
        if len(f) == 4:
            nf = cross(sub(X[f[2]], X[f[0]]), sub(X[f[3]], X[f[1]]))
        else:
            nf = cross(sub(X[f[1]], X[f[0]]), sub(X[f[2]], X[f[0]]))
        for v in f:
            for c in range(3):
                N[v][c] += nf[c]
    out = []
    for v in N:
        L = norm(v)
        out.append([c / L for c in v] if L > 0 else [0.0, 0.0, 0.0])
    return out


def form_find_uniform_stress(model: dict, sigma: float = 1.0, loads=None, maxiter: int = 100, tol: float = 1e-6,
                             method: str = "auto", cable_force=None):
    """Non-linear FDM for a UNIFORM ISOTROPIC membrane stress (soap-film-like surface).

    method "width": membrane grid links q = sigma*w/L (tributary width), cables keep their q ratio (below).
    method "cst":   exact isotropic stress sigma in every triangle (cotangent force densities) and a CONSTANT
                    force in every cable; monotone (majorise-minimise) iteration, robust at sail corners.
    method "auto":  "cst" when the model has cables (edge/ridge/valley), else "width" (rings, rigid hypar).
    cable_force: kN, constant force of every cable for "cst" (default: the linear-FDM force of each cable
    group, rescaled to sigma). Returns the info dict (see the two methods)."""
    if method == "auto":
        method = "cst" if any(e["kind"] != "membrane" for e in model["edges"]) else "width"
    if method == "cst":
        return _uniform_stress_cst(model, sigma, loads, maxiter, tol, cable_force)
    if method != "width":
        raise ValueError(f"unknown uniform-stress method {method!r} (auto, cst, width)")
    info = _uniform_stress_width(model, sigma, loads, maxiter, tol)
    info["method"] = "width"
    return info


def model_triangles(model: dict) -> list:
    """Triangles of the faces, split exactly as membrane_dr.py does: quad (0,1,2,3) -> (0,1,2) + (0,2,3)."""
    out = []
    for f in model.get("faces", []):
        for k in range(1, len(f) - 1):
            out.append((f[0], f[k], f[k + 1]))
    return out


def cst_isotropic_q(X, tris, sigma: float) -> dict:
    """Force densities that reproduce an isotropic Cauchy stress sigma in every constant-strain triangle:
    node forces sigma * dA/dx_i = sum_j q_ij (x_j - x_i) with q_ij = sigma/2 (cot a_ij + cot b_ij)
    (a, b = angles opposite edge ij; Pinkall & Polthier 1993). q < 0 opposite obtuse angles."""
    q = {}
    for t in tris:
        for k in range(3):
            i, j, o = t[k], t[(k + 1) % 3], t[(k + 2) % 3]
            ux, uy, uz = X[i][0] - X[o][0], X[i][1] - X[o][1], X[i][2] - X[o][2]
            vx, vy, vz = X[j][0] - X[o][0], X[j][1] - X[o][1], X[j][2] - X[o][2]
            cr = math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2)
            if cr <= 0:
                raise ValueError(f"degenerate triangle {t}")
            key = (i, j) if i < j else (j, i)
            q[key] = q.get(key, 0.0) + 0.5 * sigma * (ux * vx + uy * vy + uz * vz) / cr
    return q


def _us_energy(X, tris, cables, sigma, T, loads):
    """Potential of the soap film + constant-force cables: sigma*Area + sum T*L - P.x (minimised)."""
    A = sum(0.5 * norm(cross(sub(X[b], X[a]), sub(X[c], X[a]))) for a, b, c in tris)
    E = sigma * A + sum(T[e["id"]] * norm(sub(X[e["n"][1]], X[e["n"][0]])) for e in cables)
    if loads:
        E -= sum(p[0] * X[i][0] + p[1] * X[i][1] + p[2] * X[i][2] for i, p in loads.items())
    return E


def _us_forces(X, n, tris, cables, sigma, T, loads):
    """Out-of-balance node forces of the exact CST soap film + cables (+ loads), and the cot q dict."""
    R = [[0.0, 0.0, 0.0] for _ in range(n)]
    q = cst_isotropic_q(X, tris, sigma)
    for (i, j), v in q.items():
        for c in range(3):
            d = v * (X[j][c] - X[i][c])
            R[i][c] += d
            R[j][c] -= d
    for e in cables:
        a, b = e["n"]
        d = sub(X[b], X[a])
        t = T[e["id"]] / norm(d)
        for c in range(3):
            R[a][c] += t * d[c]
            R[b][c] -= t * d[c]
    if loads:
        for i, p in loads.items():
            for c in range(3):
                R[i][c] += p[c]
    return R, q


def dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _shape_residual(X, R, nrm, fixed, cab):
    """Out-of-balance that changes the SHAPE: normal component at membrane nodes; at nodes on one cable line
    everything except the component along the cable (that one, like the in-plane part at interior nodes, only
    slides the mesh along the surface)."""
    out = 0.0
    for i, r in enumerate(R):
        if fixed[i]:
            continue
        nb = cab.get(i)
        if not nb:
            v = abs(dot3(nrm[i], r))
        elif len(nb) == 2:
            t = sub(X[nb[1]], X[nb[0]])
            L = norm(t)
            a = dot3(r, t) / (L * L)
            v = norm([r[c] - a * t[c] for c in range(3)])
        else:
            v = norm(r)
        out = max(out, v)
    return out


def _move_basis(X, nrm, fixed, cab):
    """Allowed move directions per node in the mesh-control phase: membrane nodes move along the surface
    normal only, nodes on one cable line also across the cable in the tangent plane (conormal); other free
    nodes (cable junctions, nodes without faces) move freely. This removes the tangential creep of a
    uniform-stress surface (the discrete minimal surface would slowly degenerate its triangles)."""
    full = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    out = []
    for i, nv in enumerate(nrm):
        nb = cab.get(i, ())
        if fixed[i]:
            out.append([])
        elif norm(nv) < 0.5 or len(nb) not in (0, 2):
            out.append(full)
        elif not nb:
            out.append([nv])
        else:                                         # orthonormal basis of the plane normal to the cable
            t = sub(X[nb[1]], X[nb[0]])
            c = cross(nv, t)
            L = norm(c)
            if L <= 0:
                out.append(full)
                continue
            c = [v / L for v in c]
            m_ = cross(t, c)
            Lm = norm(m_)
            out.append([[v / Lm for v in m_], c])
    return out


def _constrained_fdm_step(X, fixed, q, R, basis, tol=1e-9, maxit=20000):
    """Minimise the force-density quadratic (the majoriser) over the moves x_i + sum_k s_ik b_ik:
    (B^T D B) s = B^T R, R = current out-of-balance force. Matrix-free Jacobi-PCG."""
    n = len(X)
    pairs = [(i, j, v) for (i, j), v in q.items()]
    dg = [0.0] * n
    for i, j, v in pairs:
        dg[i] += v
        dg[j] += v
    idx = [(i, bv) for i in range(n) if not fixed[i] for bv in basis[i]]
    if not idx:
        return [list(p) for p in X]
    diag = [dg[i] for i, _ in idx]
    if any(d <= 0 for d in diag):
        raise ValueError("non-positive force-density sum at a free node")

    def matvec(s):
        ux, uy, uz = [0.0] * n, [0.0] * n, [0.0] * n
        for (i, bv), sv in zip(idx, s):
            ux[i] += sv * bv[0]
            uy[i] += sv * bv[1]
            uz[i] += sv * bv[2]
        yx, yy, yz = [d * u for d, u in zip(dg, ux)], [d * u for d, u in zip(dg, uy)], [d * u for d, u in zip(dg, uz)]
        for i, j, v in pairs:
            yx[i] -= v * ux[j]; yx[j] -= v * ux[i]
            yy[i] -= v * uy[j]; yy[j] -= v * uy[i]
            yz[i] -= v * uz[j]; yz[j] -= v * uz[i]
        return [bv[0] * yx[i] + bv[1] * yy[i] + bv[2] * yz[i] for i, bv in idx]

    rhs = [dot3(bv, R[i]) for i, bv in idx]
    s = [0.0] * len(idx)
    r = rhs[:]
    z = [a / d for a, d in zip(r, diag)]
    p = z[:]
    rz = sum(a * b for a, b in zip(r, z))
    bn = math.sqrt(sum(a * a for a in rhs)) or 1.0
    for _ in range(maxit):
        if math.sqrt(sum(a * a for a in r)) / bn < tol:
            break
        Ap = matvec(p)
        pap = sum(a * b for a, b in zip(p, Ap))
        if pap <= 0:
            break
        al = rz / pap
        s = [a + al * b for a, b in zip(s, p)]
        r = [a - al * b for a, b in zip(r, Ap)]
        z = [a / d for a, d in zip(r, diag)]
        rzn = sum(a * b for a, b in zip(r, z))
        p = [a + rzn / rz * b for a, b in zip(z, p)]
        rz = rzn
    Xn = [list(pt) for pt in X]
    for (i, bv), sv in zip(idx, s):
        for c in range(3):
            Xn[i][c] += sv * bv[c]
    return Xn


def _min_area(X, tris):
    return min(0.5 * norm(cross(sub(X[b], X[a]), sub(X[c], X[a]))) for a, b, c in tris)


def _uniform_stress_cst(model, sigma, loads, maxiter, tol, cable_force):
    """URS-type form finding with an isotropic Cauchy stress sigma in every CST triangle (the URS limit
    lambda = 0 of Bletzinger & Ramm 1999 for an isotropic prestress) and a prescribed constant force T in
    every cable (so each free edge becomes an arc of radius R = T / sigma, the known consistency condition
    T = sigma * R of a cable-edged soap film).

    Each step solves the LINEAR FDM with the cotangent force densities of the current mesh plus q = T/L on the
    cables. This minimises a majoriser of the potential sigma*A + sum T*L (Dirichlet energy >= area,
    Pinkall & Polthier 1993; T L^2/(2 L_k) + T L_k/2 >= T L), so the potential decreases monotonically; a
    step that increases it is halved (relaxation). No tributary widths are used, so the skewed and
    obtuse corner cells of free cable-edged sails no longer feed back on themselves (the cause of the corner
    collapse of the "width" method). The fixed point is an EXACT equilibrium of membrane_dr.py's CST
    elements with an isotropic prestress sigma on the same triangulation (quads split along 0-2).
    Convergence: max NORMAL node move < tol * model size (the mesh may still creep tangentially; that
    residual is reported as residual_kN and as stress_dev = residual / (sigma * mean edge length))."""
    nodes, edges = model["nodes"], model["edges"]
    n = len(nodes)
    tris = model_triangles(model)
    if not tris:
        raise ValueError("--uniform-stress cst needs faces (triangles or quads)")
    fixed = [bool(nd.get("fixed")) for nd in nodes]
    cables = [e for e in edges if e["kind"] != "membrane"]
    mem = [e for e in edges if e["kind"] == "membrane"]
    solve_fdm(model, loads)                       # linear FDM start (given q ratios)
    X = [list(nd["xyz"]) for nd in nodes]
    T = {}
    if cable_force is not None:
        T = {e["id"]: float(cable_force) for e in cables}
    elif cables:
        qm = sum(float(e["q"]) for e in mem) / len(mem) if mem else 1.0
        grp = defaultdict(list)
        for e in cables:
            grp[e.get("group") or ("_e", e["id"])].append(e)
        for es in grp.values():
            f = sum(float(e["q"]) * norm(sub(X[e["n"][1]], X[e["n"][0]])) for e in es) / len(es) * sigma / qm
            for e in es:
                T[e["id"]] = f
    size = max(max(p[c] for p in X) - min(p[c] for p in X) for c in range(3)) or 1.0
    hbar = sum(norm(sub(X[b], X[a])) for a, b, _ in tris) / len(tris)
    info = {"method": "cst", "iterations": 0, "normal_move": math.inf, "move": math.inf, "stress_dev": math.inf,
            "converged": False, "status": "max iterations reached", "halvings": 0}
    E = _us_energy(X, tris, cables, sigma, T, loads)
    tmp = {}
    amin0 = _min_area(X, tris)
    cab = defaultdict(list)
    for e in cables:
        cab[e["n"][0]].append(e["n"][1])
        cab[e["n"][1]].append(e["n"][0])
    phase, omega = 1, 1.5
    for k in range(1, maxiter + 1):
        R, q = _us_forces(X, n, tris, cables, sigma, T, loads)
        nrm = vertex_normals({"nodes": [{"xyz": p} for p in X], "faces": model["faces"]})
        rn = _shape_residual(X, R, nrm, fixed, cab)
        if phase == 1 and k > 1 and (info["normal_move"] < 10 * tol * size or k > 60):
            phase = 2                                 # shape nearly converged: only tangential creep is left
            info["free_iterations"] = k - 1
        for e in cables:
            a, b = e["n"]
            key = (a, b) if a < b else (b, a)
            q[key] = q.get(key, 0.0) + T[e["id"]] / norm(sub(X[b], X[a]))
        if phase == 1:
            tmp["nodes"] = [{"xyz": list(p), "fixed": f} for p, f in zip(X, fixed)]
            tmp["edges"] = [{"id": m, "n": list(kk), "q": v} for m, (kk, v) in enumerate(q.items())]
            solve_fdm(tmp, loads, allow_negative=True)
            Xn = [nd["xyz"] for nd in tmp["nodes"]]
        else:
            Xn = _constrained_fdm_step(X, fixed, q, R, _move_basis(X, nrm, fixed, cab))
        Xmm = Xn
        En = _us_energy(Xn, tris, cables, sigma, T, loads)
        if phase == 2:                                # over-relaxed step, kept only if it lowers the potential more
            Xo = [[o + omega * (a_ - o) for a_, o in zip(p, p0)] for p, p0 in zip(Xn, X)]
            Eo = _us_energy(Xo, tris, cables, sigma, T, loads) if _min_area(Xo, tris) > 0 else math.inf
            if Eo < En:
                Xn, En = Xo, Eo
                omega = min(1.25 * omega, 8.0)
            else:
                omega = max(1.25, omega / 2)
        h = 0
        while En > E + 1e-12 * abs(E) and h < 8:      # the MM step guarantees descent; guard against round-off
            Xn = [[0.5 * (a_ + b_) for a_, b_ in zip(p, o)] for p, o in zip(Xn, X)]
            En = _us_energy(Xn, tris, cables, sigma, T, loads)
            h += 1
        info["halvings"] += h
        if _min_area(Xn, tris) < 0.2 * amin0:          # triangles degenerate (shape not realisable / mesh): stop
            info["status"] = "stopped: smallest triangle < 20 % of its initial area (degenerating mesh)"
            break
        d = [sub(p, o) for p, o in zip(Xmm, X)]        # convergence on the plain (not over-relaxed) step
        info.update(iterations=k, move=max(norm(v) for v in d),
                    normal_move=max(abs(dot3(v, m_)) for v, m_ in zip(d, nrm)))
        X, E = Xn, En
        if phase == 2 and info["move"] < tol * size and rn < 1e-4 * sigma * hbar:
            info["converged"] = True
            info["status"] = "converged"
            break
    R, q = _us_forces(X, n, tris, cables, sigma, T, loads)
    res = max((norm(R[i]) for i in range(n) if not fixed[i]), default=0.0)
    resn = _shape_residual(X, R, vertex_normals(model), fixed, cab)
    info.update(residual_kN=res, normal_residual_kN=resn, stress_dev=res / (sigma * hbar), energy=E,
                cable_forces={(e.get("group") or str(e["id"])): T[e["id"]] for e in cables},
                min_q=min(q.values()))
    # write back: coordinates; cables q = T/L; grid membrane links q = sigma*w/L (stress = sigma for the
    # CST prestress S0 and the reports); reactions = exact CST + cable pulls on the supports
    for nd, p in zip(nodes, X):
        nd["xyz"] = p
    widths = tributary_widths(model) if model.get("grid") else {}
    for e in edges:
        a, b = e["n"]
        L = norm(sub(X[b], X[a]))
        if e["kind"] != "membrane":
            e["q"] = T[e["id"]] / L
        elif widths.get(e["id"]):
            e["q"] = sigma * widths[e["id"]] / L
        else:
            e["q"] = max(q.get((min(a, b), max(a, b)), 0.0), 1e-9 * sigma)
    pulls = {}
    for i in range(n):
        if fixed[i]:
            pulls[i] = [R[i][c] - (loads.get(i, [0, 0, 0])[c] if loads else 0.0) for c in range(3)]
    info["reactions"] = pulls
    return info


def _uniform_stress_width(model: dict, sigma: float = 1.0, loads=None, maxiter: int = 100, tol: float = 1e-6):
    """Tributary-width uniform-stress iteration (method "width").

    Each iteration sets every grid membrane link to q = sigma * w / L (w = tributary width, L = length,
    both from the current geometry), so the link force equals sigma times its width, and re-solves the
    linear FDM. Cable/edge links keep their force density, rescaled once so that the cable-to-membrane
    q ratio given to the generator is kept (q_cable * sigma / mean membrane q). This is the force-density
    form of the non-linear FDM "iterate q <- F_target / L" (Linkwitz & Schek); on an orthogonal grid it
    targets the same equilibrium as the Updated Reference Strategy with an isotropic Cauchy prestress
    (Bletzinger & Ramm 1999).

    Convergence is judged on the NORMAL component of the node moves: a uniform isotropic stress does not
    fix the mesh in the tangent plane, so nodes keep sliding slowly along the surface (the "swimming" that
    URS stabilises) while the shape no longer changes. Stops when max |Δx·n| < tol * model size.
    If the stress uniformity gets worse for 8 iterations in a row (mesh swimming, degenerate corner cells,
    typical of free cable-edged sails on fine meshes) the iteration stops and the most uniform equilibrium
    state found is kept (status "diverging"). Needs a structured grid (model["grid"]). Returns a dict with
    iterations, status, normal and total moves and the link-stress deviation max|F/(w·sigma) - 1|."""
    if not model.get("grid"):
        raise ValueError("--uniform-stress needs a grid model (built-in generator or 'grid' + node 'grid' indices)")
    mem = [e for e in model["edges"] if e["kind"] == "membrane"]
    qmean = sum(float(e["q"]) for e in mem) / len(mem)
    for e in model["edges"]:
        if e["kind"] != "membrane":
            e["q"] = float(e["q"]) * sigma / qmean
    X = [nd["xyz"] for nd in model["nodes"]]
    size = max(max(p[c] for p in X) - min(p[c] for p in X) for c in range(3)) or 1.0
    solve_fdm(model, loads)
    info = {"iterations": 0, "normal_move": math.inf, "move": math.inf, "stress_dev": math.inf, "converged": False,
            "status": "max iterations reached"}
    best = None          # (stress deviation, coordinates, q) of the most uniform equilibrium state seen
    worse = 0
    for k in range(1, maxiter + 1):
        widths = tributary_widths(model)
        X = [nd["xyz"] for nd in model["nodes"]]
        dev = 0.0
        newq = {}
        for e in mem:
            w = widths.get(e["id"])
            if w:
                L = norm(sub(X[e["n"][1]], X[e["n"][0]]))
                dev = max(dev, abs(float(e["q"]) * L / (w * sigma) - 1.0))
                newq[e["id"]] = sigma * w / L
        if best is None or dev < best[0]:
            best = (dev, [list(p) for p in X], [float(e["q"]) for e in model["edges"]])
            worse = 0
        else:
            worse += 1
            if worse >= 8:   # stress uniformity keeps getting worse: mesh swimming / degenerate corners
                info["status"] = "diverging (mesh swimming): most uniform state kept"
                break
        for e in mem:
            if e["id"] in newq:
                e["q"] = newq[e["id"]]
        old = [list(p) for p in X]
        nrm = vertex_normals(model)
        solve_fdm(model, loads)
        d = [sub(nd["xyz"], o) for nd, o in zip(model["nodes"], old)]
        info.update(iterations=k, stress_dev=dev, move=max(norm(v) for v in d),
                    normal_move=max(abs(v[0] * n[0] + v[1] * n[1] + v[2] * n[2]) for v, n in zip(d, nrm)))
        if info["normal_move"] < tol * size:
            info["converged"] = True
            info["status"] = "converged"
            break
    if not info["converged"] and best is not None:
        for nd, p in zip(model["nodes"], best[1]):
            nd["xyz"] = p
        for e, q in zip(model["edges"], best[2]):
            e["q"] = q
        info["stress_dev"] = best[0]
    return info


def compute_results(model: dict, prestress: float | None, reactions: dict | None = None):
    """Edge forces, membrane stress estimate, reactions, cable groups and support groups. reactions: optional
    {node: pull} computed by the caller (CST uniform-stress form finding: exact element forces), scaled like q."""
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
    if reactions is not None:
        for u, v in reactions.items():
            reac[u] = [scale * c for c in v]
    else:
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
            vmid = max(cnt, key=lambda v: norm(cross(sub(X[v], A), ch)))
            t = sum(sub(X[vmid], A)[c] * ch[c] for c in range(3)) / (L * L)
            dz = X[vmid][2] - (A[2] + t * ch[2])
            info.update({"chord": L, "sag": sag, "sag_ratio": sag / L, "mid_dz": dz,
                         "radius_approx": (L * L / (8 * sag) + sag / 2) if sag > 0 else math.inf})
        summary.append(info)
    model["cable_groups"] = summary
    # support groups (arches, rails, masts, anchors): total pull and line load
    sg = defaultdict(lambda: {"pull": [0.0, 0.0, 0.0], "nodes": []})
    by_node = {r["node"]: r["pull"] for r in model["reactions"]}
    for i, nd in enumerate(model["nodes"]):
        tag = nd.get("support_group")
        if tag and i in by_node:
            for c in range(3):
                sg[tag]["pull"][c] += by_node[i][c]
            sg[tag]["nodes"].append(i)
    out = {}
    for tag, v in sorted(sg.items()):
        pts = sorted((X[i] for i in v["nodes"]), key=lambda p: (p[0], p[1], p[2]))
        length = sum(norm(sub(pts[k], pts[k - 1])) for k in range(1, len(pts))) if len(pts) > 1 else 0.0
        out[tag] = {"pull": v["pull"], "magnitude": norm(v["pull"]), "n_nodes": len(v["nodes"]),
                    "length": length, "line_load_kN_m": norm(v["pull"]) / length if length else None}
    if out:
        model["support_groups"] = out
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


def print_assumptions(a, us=None):
    print("Assumptions: linear FDM (Schek 1974) — equilibrium shape for the force-density ratios, NOT a load "
          "analysis; links are straight bars, the membrane is represented by a grid net;")
    print("  membrane stress = link force / tributary width (grid estimate, exact only for an orthogonal grid);"
          f" forces scaled so the mean membrane stress = {a.prestress if a.prestress else 'unscaled (no --prestress)'} kN/m;")
    print("  built-in --qc is a force-density RATIO per link: edge-cable force ~ qc x segment length, so the same "
          "--qc on a finer mesh gives a smaller cable force and a larger sag (use mesh_convergence.py).")
    if us and us.get("method") == "cst":
        cf = ", ".join(f"{g} {t:.2f}" for g, t in sorted(us["cable_forces"].items())[:6])
        print(f"  --uniform-stress (cst): isotropic Cauchy stress sigma in every triangle (cotangent force "
              f"densities, Pinkall-Polthier/URS lambda = 0) + constant cable forces [kN]: {cf or 'none'};")
        print(f"  each free edge is an arc of radius T/sigma. {us['iterations']} iterations, max normal move "
              f"{us['normal_move']:.1e} m, out-of-balance {us['residual_kN']:.1e} kN "
              f"({us['stress_dev'] * 100:.3f} % of sigma x mean edge)"
              + ("" if us["converged"] else f"  ** NOT CONVERGED ({us['status']}) **"))
        print("  Link 'stress_kN_m' = sigma by construction; reactions from the exact element forces.")
        if us["stress_dev"] > 0.05:
            print("  WARNING: out-of-balance force > 5 % of sigma x edge length: increase --ff-maxiter or check "
                  "the mesh (very distorted corner cells).")
    elif us:
        print(f"  --uniform-stress: q = sigma*w/L iterated {us['iterations']} times, max normal move "
              f"{us['normal_move']:.1e} m, link-stress deviation {us['stress_dev'] * 100:.3f} %"
              + ("" if us["converged"] else f"  ** NOT CONVERGED ({us['status']}) **"))
        if us["stress_dev"] > 0.05:
            print("  WARNING: membrane stress not uniform within 5 % (typical at the corners of free cable-edged "
                  "sails with --us-method width); use --us-method cst, linear FDM or a URS/FE package.")
    print()


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shape", nargs="?", choices=["sail4", "hypar", "cone", "arch", "multibay", "rings"],
                    help="built-in generator")
    ap.add_argument("--input", help="custom model JSON")
    ap.add_argument("--size", type=float, default=10.0, help="sail/hypar plan side [m]")
    ap.add_argument("--high", type=float, default=3.0, help="height of high corners [m]")
    ap.add_argument("--n", type=int, default=16, help="mesh divisions per side")
    ap.add_argument("--R", type=float, default=8.0, help="cone outer radius / rings: bottom ring radius [m]")
    ap.add_argument("--r", type=float, default=0.6, help="cone / rings: top ring radius [m]")
    ap.add_argument("--H", type=float, default=5.0, help="cone height / rings: distance between rings [m]")
    ap.add_argument("--anchors", type=int, default=6)
    ap.add_argument("--nr", type=int, default=12)
    ap.add_argument("--nc", type=int, default=36)
    ap.add_argument("--L", type=float, default=20.0, help="arch: tunnel length [m]")
    ap.add_argument("--B", type=float, default=10.0, help="arch: span / multibay: depth in y [m]")
    ap.add_argument("--arches", type=int, default=3, help="arch: number of arches")
    ap.add_argument("--nu", type=int, default=24, help="arch: divisions along the tunnel")
    ap.add_argument("--nv", type=int, default=12, help="arch/multibay: divisions across y")
    ap.add_argument("--bays", type=int, default=3, help="multibay: number of bays")
    ap.add_argument("--bay", type=float, default=8.0, help="multibay: bay width (ridge to ridge) [m]")
    ap.add_argument("--h-hi", type=float, default=6.0, help="multibay: ridge / high point height [m]")
    ap.add_argument("--h-lo", type=float, default=3.0, help="multibay: valley / low point height [m]")
    ap.add_argument("--m", type=int, default=4, help="multibay: divisions per half bay")
    ap.add_argument("--qr", type=float, default=15.0, help="multibay: ridge/valley cable force density")
    ap.add_argument("--qm", type=float, default=1.0, help="membrane force density (relative)")
    ap.add_argument("--qc", type=float, default=10.0, help="edge-cable force density (relative)")
    ap.add_argument("--prestress", type=float, default=None,
                    help="target mean membrane prestress [kN/m]; scales all forces")
    ap.add_argument("--uniform-stress", action="store_true",
                    help="non-linear FDM: iterate membrane q = sigma*w/L until the membrane stress is uniform and "
                         "isotropic (soap-film-like; sigma = --prestress or 1). Needs a grid model")
    ap.add_argument("--ff-maxiter", type=int, default=300, help="--uniform-stress: max iterations")
    ap.add_argument("--ff-tol", type=float, default=1e-6,
                    help="--uniform-stress: stop when the max NORMAL node move < tol x model size")
    ap.add_argument("--us-method", choices=["auto", "cst", "width"], default="auto",
                    help="--uniform-stress: cst = exact isotropic stress per triangle + constant cable forces "
                         "(robust at sail corners); width = q = sigma*w/L on grid links; auto = cst if the model "
                         "has cables, else width")
    ap.add_argument("--cable-force", type=float, default=None,
                    help="--uniform-stress cst: constant force of every cable [kN] (edge radius R = T/sigma); "
                         "default = linear-FDM force of each cable group rescaled to sigma")
    ap.add_argument("--out", default="formfound")
    ap.add_argument("--obj", action="store_true", help="also write an OBJ mesh")
    return ap


def form_find(a):
    """Build the model from parsed arguments and form-find it (no file output). Returns (model, us_info)."""
    if a.input:
        with open(a.input) as fh:
            model = json.load(fh)
    elif a.shape == "sail4":
        model = gen_sail4(a.size, a.high, a.n, a.qm, a.qc, rigid=False)
    elif a.shape == "hypar":
        model = gen_sail4(a.size, a.high, a.n, a.qm, a.qc, rigid=True)
    elif a.shape == "cone":
        model = gen_cone(a.R, a.r, a.H, a.anchors, a.nr, a.nc, a.qm, a.qc)
    elif a.shape == "arch":
        model = gen_arch(a.L, a.B, a.H, a.arches, a.nu, a.nv, a.qm, a.qc)
    elif a.shape == "multibay":
        model = gen_multibay(a.bays, a.bay, a.B, a.h_hi, a.h_lo, a.m, a.nv, a.qm, a.qr, a.qc)
    elif a.shape == "rings":
        model = gen_rings(a.R, a.r, a.H, a.nr, a.nc, a.qm)
    else:
        raise SystemExit("give a shape or --input")

    loads = {int(k): v for k, v in model.get("loads", {}).items()} if model.get("loads") else None
    us = None
    reac = None
    if a.uniform_stress:
        us = form_find_uniform_stress(model, a.prestress or 1.0, loads, a.ff_maxiter, a.ff_tol,
                                      getattr(a, "us_method", "auto"), getattr(a, "cable_force", None))
        reac = us.pop("reactions", None)
        iters = None
    else:
        iters = solve_fdm(model, loads)
    scale = compute_results(model, a.prestress, reac)
    model["surface_area_m2"] = surface_area(model)
    model["solver"] = {"method": "FDM (Schek 1974), Jacobi-PCG" + (", uniform-stress iteration" if us else ""),
                       "cg_iterations": iters, "q_scale": scale}
    if us:
        model["solver"]["uniform_stress"] = us
    return model, us


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not a.input and not a.shape:
        ap.error("give a shape or --input")
    model, us = form_find(a)

    with open(a.out + ".json", "w") as fh:
        json.dump(model, fh, indent=1)
    if a.obj:
        write_obj(model, a.out + ".obj")

    print_assumptions(a, us)
    print(f"Form found: {model.get('type', 'custom')}  nodes={len(model['nodes'])} "
          f"edges={len(model['edges'])}  surface area={model['surface_area_m2']:.2f} m2")
    if "membrane_stress" in model:
        ms = model["membrane_stress"]
        print(f"Membrane prestress (grid estimate) kN/m: mean {ms['mean']:.2f}  "
              f"min {ms['min']:.2f}  max {ms['max']:.2f}")
    if model["cable_groups"]:
        print("\nCable group        Fmax[kN]  Fmin[kN]  chord[m]  sag[m]  sag/chord  R~[m]   mid dz[m]")
        for g in model["cable_groups"]:
            print(f"  {g['group']:<16}{g['force_max']:9.2f}{g['force_min']:10.2f}"
                  f"{g.get('chord', float('nan')):10.2f}{g.get('sag', float('nan')):8.3f}"
                  f"{g.get('sag_ratio', float('nan')):10.3f}{g.get('radius_approx', float('nan')):8.2f}"
                  f"{g.get('mid_dz', float('nan')):+11.3f}")
        print("  (mid dz < 0: cable sags below its chord, e.g. ridge; > 0: hogs above, e.g. valley)")
    if model.get("support_groups"):
        print("\nSupport groups (total pull of the structure; line load along the group) :")
        for tag, v in model["support_groups"].items():
            x, y, z = v["pull"]
            ll = f"{v['line_load_kN_m']:.2f} kN/m over {v['length']:.2f} m" if v["line_load_kN_m"] else "point"
            print(f"  {tag:<14} Fx={x:9.2f} Fy={y:9.2f} Fz={z:9.2f} |F|={v['magnitude']:9.2f} kN  ({ll})")
    print("\nSupport pulls (force from structure on support) [kN]:")
    for rc in model["reactions"][:24]:
        x, y, z = rc["pull"]
        print(f"  node {rc['node']:>5}:  Fx={x:9.2f} Fy={y:9.2f} Fz={z:9.2f}  |F|={rc['magnitude']:9.2f}")
    if len(model["reactions"]) > 24:
        print(f"  ... {len(model['reactions']) - 24} more in {a.out}.json")
    print(f"\nWrote {a.out}.json" + (f", {a.out}.obj" if a.obj else ""))
    return model


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
