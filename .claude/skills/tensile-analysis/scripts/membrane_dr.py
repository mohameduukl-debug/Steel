#!/usr/bin/env python3
"""Orthotropic MEMBRANE analysis (CST elements + wrinkling) by Dynamic Relaxation or Newton-Raphson.

Replaces the cable-net analogy of dynamic_relaxation.py with a continuum membrane:
  * constant-strain triangles (each quad face split in two), Total-Lagrangian formulation:
    F = Σ x_k ⊗ ∇N_k (3×2), Green strain E = ½(FᵀF − I), PK2 stress S = S0 + D:E,
    internal forces f_k = A0 · F S ∇N_k  (large displacements, exact kinematics)
  * orthotropic plane-stress material per unit width, axes = warp (grid u) / weft (grid v)
    projected on each triangle: E_w·t, E_f·t, ν_wf (ν_fw by reciprocity), G·t
  * tension-field WRINKLING (Roddeman et al. 1987, mixed criterion): taut if the minor principal stress
    >= 0; slack if the major principal elastic strain <= 0; otherwise wrinkled: uniaxial stress sigma n(x)n
    with n and sigma = eps_nn / C_nn(n) solved so that the rest of the strain is pure wrinkling contraction
    (exact for linear orthotropy; isotropic: n = major principal strain direction, sigma = E t eps_1)
  * initial stress S0 from the form-finding (per quad: u/v edge stresses of the net) or uniform
    --prestress; the prestress state is first relaxed to equilibrium (no load) and reported
  * cables (edge/ridge/valley) as tension-only links with EA; supports from the model
  * loads: follower normal pressure (+ = uplift), snow on plan, optional pressure field

Examples
  python3 membrane_dr.py sail.json --Ew 800 --Ef 600 --nu 0.35 --G 30 --EA-cable 14000 --pressure 0.9 --out up
  python3 membrane_dr.py sail.json --snow 0.75 --out snow
Triangle faces take the warp direction from the model's optional "warp_dir" (default global x) projected on
each element; quads take it from their grid u direction.
Solvers: --solver dr (default, explicit kinetic-damping dynamic relaxation) or --solver newton (implicit
Newton-Raphson: consistent tangent K = K_material + K_geometric + K_cable (+ symmetric follower-pressure part),
tension-field tangent by central differences, adaptive load steps, energy line search, skyline Cholesky in
RCM/natural order, Levenberg-Marquardt shift if K is not positive definite, DR fallback). Both solve the same
residual, so they agree to the tolerance; Newton is 5-50x faster on medium/large meshes.
Validation (reference/validation.md): Hencky/Fichter clamped circular membrane, prestressed square under
pressure (Poisson equation), tension-field uniaxial/off-axis/shear-panel cases, Newton = DR on all of them.
Outputs per element: warp/weft/shear stress, principal n1, n2, wrinkled flag; cable forces; reactions.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynamic_relaxation as DRN  # noqa: E402  (loads, cable prep helpers)


def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def unit(a):
    n = math.sqrt(dot(a, a)) or 1e-30
    return [a[0] / n, a[1] / n, a[2] / n]


# ------------------------------------------------------------------ sparse direct solver (stdlib)
def rcm_order(nodes, adj):
    """Reverse Cuthill-McKee ordering of `nodes` (adjacency dict) to keep the skyline profile small;
    each connected component starts from a pseudo-peripheral node (repeated BFS)."""
    deg = {i: len(adj[i]) for i in nodes}
    seen = set()
    order = []

    def bfs(s):
        lev, front, seen_l = {s: 0}, [s], {s}
        while front:
            nxt = []
            for u in front:
                for v in adj[u]:
                    if v not in seen_l:
                        seen_l.add(v)
                        lev[v] = lev[u] + 1
                        nxt.append(v)
            front = nxt
        return lev

    for s0 in sorted(nodes, key=lambda i: deg[i]):
        if s0 in seen:
            continue
        s, ecc = s0, -1
        for _ in range(4):                     # pseudo-peripheral start node
            lev = bfs(s)
            e = max(lev.values())
            if e <= ecc:
                break
            ecc = e
            far = [v for v, l in lev.items() if l == e]
            s = min(far, key=lambda v: deg[v])
        comp = [s]
        seen.add(s)
        k = 0
        while k < len(comp):
            u = comp[k]
            k += 1
            for v in sorted((v for v in adj[u] if v not in seen), key=lambda v: deg[v]):
                seen.add(v)
                comp.append(v)
        order.extend(reversed(comp))
    return order


def skyline_cholesky(sky, fc):
    """In-place Cholesky L L^T of a symmetric matrix in skyline (variable band) storage: row i holds columns
    fc[i]..i. Returns False (matrix not positive definite) at the first non-positive pivot."""
    from operator import mul
    sqrt = math.sqrt
    for i in range(len(sky)):
        ri, fi = sky[i], fc[i]
        for j in range(fi, i):
            rj, fj = sky[j], fc[j]
            k0 = fi if fi > fj else fj
            ri[j - fi] = (ri[j - fi] - sum(map(mul, ri[k0 - fi:j - fi], rj[k0 - fj:j - fj]))) / rj[j - fj]
        seg = ri[:i - fi]
        d = ri[i - fi] - sum(map(mul, seg, seg))
        if not d > 0:
            return False
        ri[i - fi] = sqrt(d)
    return True


def skyline_solve(L, fc, b):
    """Solve L L^T x = b with the factor from skyline_cholesky."""
    from operator import mul
    N = len(L)
    y = list(b)
    for i in range(N):                                   # forward: L y = b
        ri, fi = L[i], fc[i]
        y[i] = (y[i] - sum(map(mul, ri[:i - fi], y[fi:i]))) / ri[i - fi]
    for i in range(N - 1, -1, -1):                       # backward: L^T x = y (column sweep)
        ri, fi = L[i], fc[i]
        xi = y[i] / ri[i - fi]
        y[i] = xi
        if i > fi:
            y[fi:i] = [a - xi * c for a, c in zip(y[fi:i], ri[:i - fi])]
    return y


class Membrane:
    def __init__(self, model, Ew, Ef, nu_wf, G, EA_cable, prestress=None, wrinkling=True):
        self.m = model
        nodes = model["nodes"]
        self.X0 = [list(nd["xyz"]) for nd in nodes]          # reference = form-found geometry
        # per-component supports: "fixed": true = all three; optional "fix": [bool, bool, bool] (x, y, z), e.g.
        # symmetry planes or a roller (CST solver only). self.fixed = fully fixed; self.fix = per component.
        self.fix = [(True, True, True) if nd.get("fixed") else tuple(bool(v) for v in nd.get("fix", (0, 0, 0)))
                    for nd in nodes]
        self.fixed = [all(f) for f in self.fix]
        self.partial = any(any(f) and not all(f) for f in self.fix)
        nu_fw = nu_wf * Ef / Ew
        den = 1 - nu_wf * nu_fw
        if den <= 0 or Ew <= 0 or Ef <= 0 or G <= 0:
            raise ValueError("material not positive definite: need E_w·t, E_f·t, G·t > 0 and ν_wf·ν_fw < 1")
        self.D = (Ew / den, Ef / den, nu_fw * Ew / den, G)     # D11, D22, D12, D33 [kN/m]
        # compliance (per unit width): e11 = C11 S11 + C12 S22, e22 = C12 S11 + C22 S22, gamma12 = C66 S12
        self.C = (1.0 / Ew, 1.0 / Ef, -nu_wf / Ew, 1.0 / G)
        # isotropic in the plane -> wrinkle direction = principal strain direction (no search needed)
        self.iso = (abs(Ew - Ef) <= 1e-9 * Ew and abs(G - Ew / (2 * (1 + nu_wf))) <= 1e-6 * G)
        self.wrinkling = wrinkling
        # warp/weft stress per quad from the net (u / v edges)
        edge_stress = {}
        for e in model["edges"]:
            if e["kind"] == "membrane" and "stress_kN_m" in e:
                a, b = e["n"]
                edge_stress[(min(a, b), max(a, b))] = e["stress_kN_m"]
        warp_global = model.get("warp_dir", [1.0, 0.0, 0.0])
        self.tris = []
        for f in model["faces"]:
            quad = f if len(f) == 4 else None
            if quad:
                i0, i1, i2, i3 = quad
                warp = unit([self.X0[i1][c] - self.X0[i0][c] + self.X0[i2][c] - self.X0[i3][c] for c in range(3)])
                su = [edge_stress.get((min(i0, i1), max(i0, i1))), edge_stress.get((min(i3, i2), max(i3, i2)))]
                sv = [edge_stress.get((min(i0, i3), max(i0, i3))), edge_stress.get((min(i1, i2), max(i1, i2)))]
                su = [v for v in su if v is not None]
                sv = [v for v in sv if v is not None]
                s0 = (prestress[0] if prestress else (sum(su) / len(su) if su else 2.0),
                      prestress[1] if prestress else (sum(sv) / len(sv) if sv else 2.0))
                tri_list = [(i0, i1, i2), (i0, i2, i3)]
            else:
                # triangle faces: warp = model "warp_dir" (default global x) projected on the element
                nrm = unit(cross(sub(self.X0[f[1]], self.X0[f[0]]), sub(self.X0[f[2]], self.X0[f[0]])))
                if abs(dot(unit(warp_global), nrm)) < 0.95:
                    warp = list(warp_global)
                else:
                    warp = sub(self.X0[f[1]], self.X0[f[0]])
                s0 = prestress or (2.0, 2.0)
                tri_list = [tuple(f)]
            for t in tri_list:
                self.tris.append(self._make_tri(t, warp, s0))
        # cables
        self.cables = []
        for e in model["edges"]:
            if e["kind"] != "membrane":
                EA = float(e.get("EA", EA_cable))
                F0 = e.get("force", 0.0)
                L = math.dist(self.X0[e["n"][0]], self.X0[e["n"][1]])
                self.cables.append({"n": tuple(e["n"]), "EA": EA, "L0": L / (1 + F0 / EA), "id": e["id"],
                                    "group": e.get("group"), "kind": e["kind"]})

    def _make_tri(self, t, warp, s0):
        P = [self.X0[i] for i in t]
        e12, e13 = sub(P[1], P[0]), sub(P[2], P[0])
        nrm = unit(cross(e12, e13))
        g1 = unit(sub(warp, [dot(warp, nrm) * c for c in nrm]))   # warp projected on the plane
        g2 = cross(nrm, g1)
        xy = [(dot(sub(p, P[0]), g1), dot(sub(p, P[0]), g2)) for p in P]
        (x1, y1), (x2, y2), (x3, y3) = xy
        A2 = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
        A0 = abs(A2) / 2
        # ∇N_k = (dN/dX, dN/dY)
        dN = [((y2 - y3) / A2, (x3 - x2) / A2), ((y3 - y1) / A2, (x1 - x3) / A2), ((y1 - y2) / A2, (x2 - x1) / A2)]
        return {"n": t, "A0": A0, "dN": dN, "S0": (s0[0], s0[1], 0.0), "th": None}

    # ------------------------------------------------------------ wrinkling
    def _uniaxial_dir(self, e11, e22, e12, th0):
        """Tension-field state for an orthotropic sheet (Roddeman et al. 1987): find the direction n(θ)
        such that a uniaxial stress σ·n⊗n plus a wrinkling strain β·m⊗m (m ⟂ n, β ≥ 0) reproduces the
        elastic strain (e11, e22, tensor e12). Conditions: σ = ε_nn / C_nn(θ) and ε_nm = σ·C_nm(θ).
        Returns (θ, σ) or None."""
        C11, C22, C12, C66 = self.C
        em, ed = 0.5 * (e11 + e22), 0.5 * (e11 - e22)

        def fun(th):
            c, s = math.cos(th), math.sin(th)
            c2, s2, cs = c * c, s * s, c * s
            cnn = C11 * c2 * c2 + (2 * C12 + C66) * c2 * s2 + C22 * s2 * s2
            cnm = ((C12 - C11) * c2 + (C22 - C12) * s2) * cs + 0.5 * C66 * cs * (c2 - s2)
            cmm = (C11 + C22 - C66) * c2 * s2 + C12 * (c2 * c2 + s2 * s2)
            enn = em + ed * (c2 - s2) + 2 * e12 * cs
            enm = -2 * ed * cs + e12 * (c2 - s2)
            emm = em - ed * (c2 - s2) - 2 * e12 * cs
            sig = enn / cnn
            return enm - sig * cnm, sig, sig * cmm - emm      # residual, σ, wrinkling strain β

        def ok(th):
            r, sig, beta = fun(th)
            return sig > 0 and beta >= -1e-12

        th = th0
        for _ in range(30):                        # Newton (numerical slope) from the cached direction
            r, sig, _b = fun(th)
            if abs(r) < 1e-13 * max(abs(e11), abs(e22), abs(e12), 1e-15):
                break
            h = 1e-7
            dr = (fun(th + h)[0] - fun(th - h)[0]) / (2 * h)
            if dr == 0:
                break
            step = -r / dr
            if abs(step) > 0.3:
                step = math.copysign(0.3, step)
            th += step
            if abs(step) < 1e-12:
                break
        scale = max(abs(e11), abs(e22), abs(e12), 1e-15)
        if abs(fun(th)[0]) < 1e-9 * scale and ok(th):
            return th, fun(th)[1]
        # robust fallback: scan [0, π) for sign changes, bisect, keep the valid root with the largest σ
        best = None
        N = 72
        ths = [k * math.pi / N for k in range(N + 1)]
        vals = [fun(t)[0] for t in ths]
        for k in range(N):
            if vals[k] == 0 or vals[k] * vals[k + 1] < 0:
                lo, hi, flo = ths[k], ths[k + 1], vals[k]
                for _ in range(60):
                    mid = 0.5 * (lo + hi)
                    fm = fun(mid)[0]
                    if flo * fm <= 0:
                        hi = mid
                    else:
                        lo, flo = mid, fm
                t = 0.5 * (lo + hi)
                if ok(t) and (best is None or fun(t)[1] > best[1]):
                    best = (t, fun(t)[1])
        return best

    def wrinkle(self, S11, S22, S12, tri=None):
        """Apply the tension-field model to the linear stress (PK2, material axes).
        Mixed criterion: taut if the minor principal stress ≥ 0; slack if the major principal ELASTIC strain
        ≤ 0; otherwise wrinkled -> uniaxial stress σ·n⊗n with σ = ε_nn/C_nn (exact for linear orthotropy).
        Returns (S11, S22, S12, flag) with flag 0 taut, 1 wrinkled, 2 slack."""
        m_ = 0.5 * (S11 + S22)
        r = math.sqrt(0.25 * (S11 - S22) ** 2 + S12 * S12)
        if m_ - r >= 0:
            return S11, S22, S12, 0
        C11, C22, C12, C66 = self.C
        e11 = C11 * S11 + C12 * S22                 # elastic strain (incl. the prestress pre-strain)
        e22 = C12 * S11 + C22 * S22
        e12 = 0.5 * C66 * S12                       # tensor shear strain
        e1 = 0.5 * (e11 + e22) + math.sqrt(0.25 * (e11 - e22) ** 2 + e12 * e12)
        if e1 <= 0:
            return 0.0, 0.0, 0.0, 2
        th_e = 0.5 * math.atan2(2 * e12, e11 - e22)  # major principal strain direction
        if self.iso:
            th, sig = th_e, e1 / C11
        else:
            th0 = tri["th"] if (tri is not None and tri.get("th") is not None) else th_e
            res = self._uniaxial_dir(e11, e22, e12, th0)
            if res is None:                         # no admissible uniaxial state: keep the stress projection
                if m_ + r <= 0:
                    return 0.0, 0.0, 0.0, 2
                th = 0.5 * math.atan2(2 * S12, S11 - S22)
                sig = m_ + r
            else:
                th, sig = res
            if tri is not None:
                tri["th"] = th
        c, s = math.cos(th), math.sin(th)
        return sig * c * c, sig * s * s, sig * c * s, 1

    # ---------------------------------------------------------------- core
    def element_state(self, tri, X):
        (a, b, c) = tri["n"]
        dN = tri["dN"]
        xa, xb, xc = X[a], X[b], X[c]
        # F columns: f1 = ∂x/∂X, f2 = ∂x/∂Y
        f1 = [xa[i] * dN[0][0] + xb[i] * dN[1][0] + xc[i] * dN[2][0] for i in range(3)]
        f2 = [xa[i] * dN[0][1] + xb[i] * dN[1][1] + xc[i] * dN[2][1] for i in range(3)]
        E11 = 0.5 * (dot(f1, f1) - 1.0)
        E22 = 0.5 * (dot(f2, f2) - 1.0)
        G12 = dot(f1, f2)                                   # engineering shear 2E12
        D11, D22, D12, D33 = self.D
        S11 = tri["S0"][0] + D11 * E11 + D12 * E22
        S22 = tri["S0"][1] + D12 * E11 + D22 * E22
        S12 = tri["S0"][2] + D33 * G12
        wr = 0
        if self.wrinkling:
            S11, S22, S12, wr = self.wrinkle(S11, S22, S12, tri)
        return f1, f2, (S11, S22, S12), wr

    def _pack(self):
        """Flat per-element tuples for the inner loop (built once)."""
        if getattr(self, "_tdata", None) is None:
            self._tdata = []
            for tri in self.tris:
                (a, b, c), dN, A0 = tri["n"], tri["dN"], tri["A0"]
                kk = tuple(A0 * (g[0] * g[0] + g[1] * g[1]) for g in dN)
                self._tdata.append((a, b, c, dN[0][0], dN[0][1], dN[1][0], dN[1][1], dN[2][0], dN[2][1], A0,
                                    tri["S0"][0], tri["S0"][1], tri["S0"][2], kk[0], kk[1], kk[2], tri))
            self._cdata = [(cb["n"][0], cb["n"][1], cb["EA"], cb["L0"], cb["EA"] / cb["L0"], cb)
                           for cb in self.cables]
        return self._tdata, self._cdata

    def _internal(self, x, y, z, Rx, Ry, Rz, K):
        """Add element and cable forces to R and the DR stiffness estimate to K (flat arrays)."""
        D11, D22, D12, D33 = self.D
        Dmax = max(D11, D22) + D33
        wrink = self.wrinkling
        sqrt = math.sqrt
        tdata, cdata = self._pack()
        for (a, b, c, gax, gay, gbx, gby, gcx, gcy, A0, s0x, s0y, s0xy, ka, kb, kc, tri) in tdata:
            xa, xb, xc, ya, yb, yc, za, zb, zc = x[a], x[b], x[c], y[a], y[b], y[c], z[a], z[b], z[c]
            f1x = xa * gax + xb * gbx + xc * gcx
            f1y = ya * gax + yb * gbx + yc * gcx
            f1z = za * gax + zb * gbx + zc * gcx
            f2x = xa * gay + xb * gby + xc * gcy
            f2y = ya * gay + yb * gby + yc * gcy
            f2z = za * gay + zb * gby + zc * gcy
            E11 = 0.5 * (f1x * f1x + f1y * f1y + f1z * f1z - 1.0)
            E22 = 0.5 * (f2x * f2x + f2y * f2y + f2z * f2z - 1.0)
            S11 = s0x + D11 * E11 + D12 * E22
            S22 = s0y + D12 * E11 + D22 * E22
            S12 = s0xy + D33 * (f1x * f2x + f1y * f2y + f1z * f2z)
            if wrink:
                h = S11 - S22
                if 0.5 * (S11 + S22) < sqrt(0.25 * h * h + S12 * S12):   # minor principal stress < 0
                    S11, S22, S12, _ = self.wrinkle(S11, S22, S12, tri)
            p1x, p1y, p1z = S11 * f1x + S12 * f2x, S11 * f1y + S12 * f2y, S11 * f1z + S12 * f2z
            p2x, p2y, p2z = S12 * f1x + S22 * f2x, S12 * f1y + S22 * f2y, S12 * f1z + S22 * f2z
            Rx[a] -= A0 * (p1x * gax + p2x * gay)
            Ry[a] -= A0 * (p1y * gax + p2y * gay)
            Rz[a] -= A0 * (p1z * gax + p2z * gay)
            Rx[b] -= A0 * (p1x * gbx + p2x * gby)
            Ry[b] -= A0 * (p1y * gbx + p2y * gby)
            Rz[b] -= A0 * (p1z * gbx + p2z * gby)
            Rx[c] -= A0 * (p1x * gcx + p2x * gcy)
            Ry[c] -= A0 * (p1y * gcx + p2y * gcy)
            Rz[c] -= A0 * (p1z * gcx + p2z * gcy)
            kf = Dmax + abs(S11) + abs(S22) + abs(S12)
            K[a] += kf * ka
            K[b] += kf * kb
            K[c] += kf * kc
        for a, b, ea, l0, k0, cb in cdata:
            dx, dy, dz = x[b] - x[a], y[b] - y[a], z[b] - z[a]
            L = sqrt(dx * dx + dy * dy + dz * dz)
            T = ea * (L - l0) / l0
            if T < 0.0:
                T = 0.0
            cb["_T"] = T
            t = T / L
            Rx[a] += t * dx; Ry[a] += t * dy; Rz[a] += t * dz
            Rx[b] -= t * dx; Ry[b] -= t * dy; Rz[b] -= t * dz
            K[a] += k0 + t
            K[b] += k0 + t

    def forces(self, X, P=None):
        n = len(X)
        x, y, z = [p[0] for p in X], [p[1] for p in X], [p[2] for p in X]
        Rx, Ry, Rz = [0.0] * n, [0.0] * n, [0.0] * n
        if P:
            for i, f in P.items():
                Rx[i] += f[0]
                Ry[i] += f[1]
                Rz[i] += f[2]
        K = [0.0] * n
        self._internal(x, y, z, Rx, Ry, Rz, K)
        return [[Rx[i], Ry[i], Rz[i]] for i in range(n)], K

    def relax(self, X, pressure=0.0, snow=0.0, pfun=None, tol=1e-4, maxit=100000, mass_factor=2.0, verbose=False,
              extra=None):
        """Kinetic-damping DR (dt = 1, M_i = mass_factor·K_i). X is updated in place and returned."""
        n = len(X)
        x, y, z = [p[0] for p in X], [p[1] for p in X], [p[2] for p in X]
        free = [i for i in range(n) if not self.fixed[i]]
        tris = DRN._tri_list(self.m)
        loaded = bool(pressure or snow or pfun)
        P0x, P0y, P0z = [0.0] * n, [0.0] * n, [0.0] * n
        if extra:
            for i, f in extra.items():
                P0x[i] += f[0]
                P0y[i] += f[1]
                P0z[i] += f[2]
        vx, vy, vz = [0.0] * n, [0.0] * n, [0.0] * n
        KE_prev = 0.0
        Rmax = math.inf
        it = 0
        tol2 = tol * tol
        for it in range(maxit):
            Rx, Ry, Rz = P0x[:], P0y[:], P0z[:]
            if loaded:
                DRN.add_face_loads(tris, x, y, z, pressure, snow, pfun, Rx, Ry, Rz)
            K = [0.0] * n
            self._internal(x, y, z, Rx, Ry, Rz, K)
            if self.partial:
                for i in free:
                    fx_, fy_, fz_ = self.fix[i]
                    if fx_:
                        Rx[i] = 0.0
                    if fy_:
                        Ry[i] = 0.0
                    if fz_:
                        Rz[i] = 0.0
            r2 = 0.0
            for i in free:
                q = Rx[i] * Rx[i] + Ry[i] * Ry[i] + Rz[i] * Rz[i]
                if q > r2:
                    r2 = q
            Rmax = math.sqrt(r2)
            if r2 < tol2:
                break
            KE = 0.0
            for i in free:
                m = mass_factor * K[i]
                if m < 1e-9:
                    m = 1e-9
                a_, b_, c_ = vx[i] + Rx[i] / m, vy[i] + Ry[i] / m, vz[i] + Rz[i] / m
                vx[i], vy[i], vz[i] = a_, b_, c_
                KE += m * (a_ * a_ + b_ * b_ + c_ * c_)
            if KE < KE_prev:
                for i in free:
                    vx[i] = vy[i] = vz[i] = 0.0
                KE = 0.0
            KE_prev = KE
            for i in free:
                x[i] += vx[i]
                y[i] += vy[i]
                z[i] += vz[i]
            if verbose and it % 1000 == 0:
                print(f"  it {it:6d} residual {Rmax:.3e}", file=sys.stderr)
        for i in range(n):
            X[i][0], X[i][1], X[i][2] = x[i], y[i], z[i]
        return X, it, Rmax

    # ------------------------------------------------------- implicit (Newton-Raphson) solver
    def _stress_tangent(self, tri, E11, E22, G12):
        """Stress (tension-field law) and its tangent dS/dE (3x3, Voigt, engineering shear) of one element.
        Taut: the elastic D. Wrinkled: central differences of the exact tension-field stress S(E) (6 calls of
        wrinkle()), symmetrised (the relaxed energy is a potential), plus EPS_WR*D. Slack: EPS_SL*D.
        The small multiples of D only regularise the tangent; the residual (and so the solution) is exact."""
        D11, D22, D12, D33 = self.D
        s0 = tri["S0"]

        def stress(e1, e2, g):
            S11 = s0[0] + D11 * e1 + D12 * e2
            S22 = s0[1] + D12 * e1 + D22 * e2
            S12 = s0[2] + D33 * g
            if self.wrinkling:
                h = S11 - S22
                if 0.5 * (S11 + S22) < math.sqrt(0.25 * h * h + S12 * S12):
                    return self.wrinkle(S11, S22, S12, tri)
            return S11, S22, S12, 0

        S = stress(E11, E22, G12)
        Dm = ((D11, D12, 0.0), (D12, D22, 0.0), (0.0, 0.0, D33))
        if S[3] == 0:
            return S, Dm
        if S[3] == 2:
            e = self.EPS_SL
            return S, tuple(tuple(e * v for v in r) for r in Dm)
        h = 1e-8
        cols = []
        for k in range(3):
            dp = [E11, E22, G12]
            dm = [E11, E22, G12]
            dp[k] += h
            dm[k] -= h
            sp, sm = stress(*dp), stress(*dm)
            cols.append([(sp[r] - sm[r]) / (2 * h) for r in range(3)])
        e = self.EPS_WR
        Dt = tuple(tuple(0.5 * (cols[c][r] + cols[r][c]) + e * Dm[r][c] for c in range(3)) for r in range(3))
        return S, Dt

    EPS_WR = 1e-4     # tangent regularisation of wrinkled elements (fraction of D)
    EPS_SL = 1e-3     # tangent of slack elements / slack cables (fraction of D or EA/L0)

    def _setup_dofs(self):
        """Free-node equation numbers (reverse Cuthill-McKee order) and the skyline profile."""
        if getattr(self, "_dofs", None) is not None:
            return self._dofs
        n = len(self.X0)
        adj = defaultdict(set)
        for tri in self.tris:
            a, b, c = tri["n"]
            adj[a] |= {b, c}
            adj[b] |= {a, c}
            adj[c] |= {a, b}
        for cb in self.cables:
            a, b = cb["n"]
            adj[a].add(b)
            adj[b].add(a)
        free = [i for i in range(n) if not self.fixed[i]]
        best = None
        for order in (rcm_order(free, {i: [j for j in adj[i] if not self.fixed[j]] for i in free}), free):
            dof = [[-1, -1, -1] for _ in range(n)]  # keep the smaller profile of RCM and the input numbering
            N = 0
            for i in order:
                for c in range(3):
                    if not self.fix[i][c]:
                        dof[i][c] = N
                        N += 1
            first = [min([d for d in dof[i] if d >= 0], default=-1) for i in range(n)]
            fc = list(range(N))
            for i in free:
                lo = min([first[i]] + [first[j] for j in adj[i] if first[j] >= 0])
                for d in dof[i]:
                    if d >= 0:
                        fc[d] = lo
            prof = sum(i - fc[i] + 1 for i in range(N))
            if best is None or prof < best[0]:
                best = (prof, order, dof, N, fc)
        _, order, dof, N, fc = best
        # element / cable dof lists and lower-triangle scatter maps
        def scatter(dofs):
            out = []
            for p, dp in enumerate(dofs):
                if dp < 0:
                    continue
                for q, dq in enumerate(dofs):
                    if 0 <= dq <= dp:
                        out.append((p, q, dp, dq - fc[dp]))
            return out
        tsc = []
        for tri in self.tris:
            tsc.append(scatter([dof[v][c] for v in tri["n"] for c in range(3)]))
        csc = []
        for cb in self.cables:
            csc.append(scatter([dof[v][c] for v in cb["n"] for c in range(3)]))
        dl = [(i, c, dof[i][c]) for i in order for c in range(3) if dof[i][c] >= 0]
        self._dofs = {"dof": dof, "order": order, "dl": dl, "N": N, "fc": fc, "tsc": tsc, "csc": csc,
                      "profile": sum(i - fc[i] + 1 for i in range(N))}
        return self._dofs

    def _tangent(self, X, lam_p, pfun, follower, ltris):
        """Assemble the consistent tangent K = K_material + K_geometric (+ K_cable, + symmetric part of the
        follower-pressure load stiffness) in skyline form (lower triangle, rows in RCM order)."""
        dd = self._setup_dofs()
        fc, N = dd["fc"], dd["N"]
        sky = [[0.0] * (i - fc[i] + 1) for i in range(N)]
        for tri, sc in zip(self.tris, dd["tsc"]):
            if not sc:
                continue
            (a, b, c), g = tri["n"], tri["dN"]
            A0 = tri["A0"]
            xa, xb, xc = X[a], X[b], X[c]
            f1 = [xa[i] * g[0][0] + xb[i] * g[1][0] + xc[i] * g[2][0] for i in range(3)]
            f2 = [xa[i] * g[0][1] + xb[i] * g[1][1] + xc[i] * g[2][1] for i in range(3)]
            E11 = 0.5 * (dot(f1, f1) - 1.0)
            E22 = 0.5 * (dot(f2, f2) - 1.0)
            G12 = dot(f1, f2)
            (S11, S22, S12, _), Dt = self._stress_tangent(tri, E11, E22, G12)
            # B (3 x 9): dE/dx for node k, component i
            B0, B1, B2 = [], [], []
            for k in range(3):
                gx, gy = g[k]
                for i in range(3):
                    B0.append(f1[i] * gx)
                    B1.append(f2[i] * gy)
                    B2.append(f1[i] * gy + f2[i] * gx)
            DB = [[Dt[r][0] * B0[p] + Dt[r][1] * B1[p] + Dt[r][2] * B2[p] for p in range(9)] for r in range(3)]
            gsg = [[A0 * (g[k][0] * (S11 * g[l][0] + S12 * g[l][1]) + g[k][1] * (S12 * g[l][0] + S22 * g[l][1]))
                    for l in range(3)] for k in range(3)]
            D0, D1, D2 = DB
            for p, q, r, cpos in sc:
                v = A0 * (B0[p] * D0[q] + B1[p] * D1[q] + B2[p] * D2[q])
                if p % 3 == q % 3:
                    v += gsg[p // 3][q // 3]
                sky[r][cpos] += v
        for cb, sc in zip(self.cables, dd["csc"]):
            if not sc:
                continue
            a, b = cb["n"]
            d = sub(X[b], X[a])
            L = math.sqrt(dot(d, d))
            e = [v / L for v in d]
            T = cb["EA"] * (L - cb["L0"]) / cb["L0"]
            kE = cb["EA"] / cb["L0"]
            if T <= 0:
                kE, t = self.EPS_SL * kE, 0.0
            else:
                t = T / L
            k3 = [[(kE - t) * e[i] * e[j] + (t if i == j else 0.0) for j in range(3)] for i in range(3)]
            for p, q, r, cpos in sc:
                v = k3[p % 3][q % 3]
                sky[r][cpos] += v if (p < 3) == (q < 3) else -v
        if follower and (lam_p or pfun):
            dof = dd["dof"]
            for (a, b, c) in ltris:
                xa, xb, xc = X[a], X[b], X[c]
                nz = (xb[0] - xa[0]) * (xc[1] - xa[1]) - (xb[1] - xa[1]) * (xc[0] - xa[0])
                p = lam_p if pfun is None else pfun((xa[0] + xb[0] + xc[0]) / 3, (xa[1] + xb[1] + xc[1]) / 3)
                coef = -(p if nz >= 0 else -p) / 12.0     # K_T -= sym(dP/dx): block (v,w) = coef [e_w - e_v]x
                es = (sub(xc, xb), sub(xa, xc), sub(xb, xa))
                vs = (a, b, c)
                for iv in range(3):
                    if self.fixed[vs[iv]]:
                        continue
                    for iw in range(3):
                        if iw == iv or self.fixed[vs[iw]]:
                            continue
                        w = sub(es[iw], es[iv])
                        # skew matrix [w]x = [[0,-w2,w1],[w2,0,-w0],[-w1,w0,0]]
                        sk = ((0.0, -w[2], w[1]), (w[2], 0.0, -w[0]), (-w[1], w[0], 0.0))
                        for i in range(3):
                            r = dof[vs[iv]][i]
                            if r < 0:
                                continue
                            for j in range(3):
                                cdof = dof[vs[iw]][j]
                                if 0 <= cdof <= r and sk[i][j]:
                                    sky[r][cdof - fc[r]] += coef * sk[i][j]
        return sky

    def _residual(self, X, pressure, snow, pfun, extra, ltris):
        """Out-of-balance nodal forces (external + internal), flat arrays, and the max nodal norm."""
        n = len(X)
        x, y, z = [p[0] for p in X], [p[1] for p in X], [p[2] for p in X]
        Rx, Ry, Rz = [0.0] * n, [0.0] * n, [0.0] * n
        if extra:
            for i, f in extra.items():
                Rx[i] += f[0]
                Ry[i] += f[1]
                Rz[i] += f[2]
        if pressure or snow or pfun:
            DRN.add_face_loads(ltris, x, y, z, pressure, snow, pfun, Rx, Ry, Rz)
        self._internal(x, y, z, Rx, Ry, Rz, [0.0] * n)
        return Rx, Ry, Rz

    def newton(self, X, pressure=0.0, snow=0.0, pfun=None, tol=1e-4, maxit=400, verbose=False, extra=None,
               follower=True, fallback=True):
        """Implicit solution: Newton-Raphson with the consistent tangent (material + geometric stiffness of the
        Total-Lagrangian CST, tension-field tangent by central differences, cable stiffness, symmetric part of
        the follower-pressure stiffness; snow on plan treated as dead load in the tangent), adaptive load
        stepping (lambda from 0 to 1), step limit and backtracking line search on the residual norm, skyline
        Cholesky in reverse Cuthill-McKee order. A tangent that is not positive definite (no wrinkling model
        with compression, slack regions) is shifted (K + mu*diag K); if a load step cannot be completed the
        remaining load is solved by dynamic relaxation (fallback). The residual is the same as relax(), so
        the converged state is the same equilibrium to within the tolerance.
        X is updated in place. Returns (X, iterations, max residual) and stores self.newton_info."""
        dd = self._setup_dofs()
        order, dl, N = dd["order"], dd["dl"], dd["N"]
        ltris = DRN._tri_list(self.m)
        n = len(X)
        Xs = [list(p) for p in X]
        size = max(max(p[c] for p in X) - min(p[c] for p in X) for c in range(3)) or 1.0
        dmax = 0.2 * size
        info = {"newton_iterations": 0, "factorizations": 0, "modified_steps": 0, "load_steps": 0, "step_cuts": 0,
                "shifts": 0,
                "line_search_cuts": 0, "fallback_dr": False, "dr_iterations": 0, "profile": dd["profile"],
                "equations": N}
        loaded = bool(pressure or snow or pfun or extra)

        def loads(lam):
            pf = (lambda xx, yy: lam * pfun(xx, yy)) if pfun else None
            ex = {i: [lam * v for v in f] for i, f in extra.items()} if extra else None
            return lam * pressure, lam * snow, pf, ex

        def rnorm(R):                                  # max nodal norm and 2-norm over the free components
            if self.partial:
                for i in order:
                    for c in range(3):
                        if self.fix[i][c]:
                            R[c][i] = 0.0
            Rx, Ry, Rz = R
            m2 = s2 = 0.0
            for i in order:
                q = Rx[i] * Rx[i] + Ry[i] * Ry[i] + Rz[i] * Rz[i]
                s2 += q
                if q > m2:
                    m2 = q
            return math.sqrt(m2), math.sqrt(s2)

        def stage(lam, tol_s, max_s):
            p_, s_, pf_, ex_ = loads(lam)
            R = self._residual(Xs, p_, s_, pf_, ex_, ltris)
            rmax, r2 = rnorm(R)
            sky, reuse = None, False
            for it in range(max_s):
                if rmax < tol_s:
                    return True, rmax
                if reuse:                                  # modified Newton: keep the factor of the last tangent
                    info["modified_steps"] += 1
                else:
                    sky0 = self._tangent(Xs, p_, pf_, follower, ltris)
                    dbar = sum(abs(row[-1]) for row in sky0) / max(1, len(sky0))
                    mu, ok = 0.0, False
                    for _ in range(8):                     # Levenberg-Marquardt shift K + mu*mean(diag)*I if needed
                        sky = [row[:-1] + [row[-1] + mu * dbar] for row in sky0]
                        info["factorizations"] += 1
                        if skyline_cholesky(sky, dd["fc"]):
                            ok = True
                            break
                        info["shifts"] += 1
                        mu = 1e-8 if mu == 0.0 else mu * 10
                    if not ok:
                        return False, rmax
                b = [0.0] * N
                for i, c, d in dl:
                    b[d] = R[c][i]
                du = skyline_solve(sky, dd["fc"], b)
                big = max(abs(v) for v in du) if du else 0.0
                scale = min(1.0, dmax / big) if big > 0 else 1.0
                X0 = [Xs[i][c] for i, c, d in dl]

                def slope(Rv):                             # du . R: derivative of the potential along du
                    return sum(du[d] * Rv[c][i] for i, c, d in dl)
                s0 = slope(R)
                lo, hi = (0.0, s0), None
                alpha = scale
                for ls in range(6):                        # energy line search (regula falsi on du . R = 0)
                    for (i, c, d), x0 in zip(dl, X0):
                        Xs[i][c] = x0 + alpha * du[d]
                    Rn = self._residual(Xs, p_, s_, pf_, ex_, ltris)
                    sa = slope(Rn)
                    if abs(sa) <= 0.5 * abs(s0) or (sa > 0 and hi is None):
                        break
                    if sa < 0:
                        hi = (alpha, sa)
                    else:
                        lo = (alpha, sa)
                    a_new = lo[0] - lo[1] * (hi[0] - lo[0]) / (hi[1] - lo[1])
                    alpha = min(max(a_new, lo[0] + 0.05 * (hi[0] - lo[0])), hi[0] - 0.05 * (hi[0] - lo[0]))
                    info["line_search_cuts"] += 1
                rmax_n, r2_n = rnorm(Rn)
                info["newton_iterations"] += 1
                if verbose:
                    print(f"  newton lam {lam:.3f} it {it:3d} residual {rmax_n:.3e} alpha {alpha:.3f}"
                          f"{' shift %.0e' % mu if mu else ''}", file=sys.stderr)
                if not rmax_n < 1e6 * (rmax + tol):         # diverging (or NaN): cut the load increment
                    return False, rmax
                # quadratic phase (residual down > 10x; > 4x for a reused factor): reuse the factorisation
                reuse = rmax_n < (0.25 if reuse else 0.1) * rmax
                R, rmax, r2 = Rn, rmax_n, r2_n
            return rmax < tol_s, rmax

        lam, dlam = 0.0, 1.0
        rmax = math.inf
        if not loaded:
            ok, rmax = stage(0.0, tol, maxit)
            lam = 1.0 if ok else 0.0
        while loaded and lam < 1.0 and info["newton_iterations"] < maxit:
            target = min(1.0, lam + dlam)
            saved = [list(p) for p in Xs]
            before = info["newton_iterations"]
            ok, rmax = stage(target, tol if target >= 1.0 else 100 * tol, 30)
            if ok:
                lam = target
                info["load_steps"] += 1
                if info["newton_iterations"] - before <= 6:
                    dlam = min(1.0, 2 * dlam)
            else:
                Xs = saved
                dlam *= 0.5
                info["step_cuts"] += 1
                if dlam < 1.0 / 64:
                    break
        if lam < 1.0 or rmax >= tol:
            if fallback:
                info["fallback_dr"] = True
                Xs, itd, rmax = self.relax(Xs, pressure, snow, pfun, tol, 200000, verbose=verbose, extra=extra)
                info["dr_iterations"] = itd
        info["lambda"] = lam if not info["fallback_dr"] else 1.0
        self.newton_info = info
        R = self._residual(Xs, pressure, snow, pfun, extra, ltris)   # also refreshes cable forces (_T)
        rmax = rnorm(R)[0]
        for i in range(n):
            X[i][0], X[i][1], X[i][2] = Xs[i]
        return X, info["newton_iterations"], rmax

    def results(self, X, pressure=0.0, snow=0.0, pfun=None):
        els = []
        for tri in self.tris:
            f1, f2, (S11, S22, S12), wr = self.element_state(tri, X)
            m_ = 0.5 * (S11 + S22)
            r = math.sqrt(0.25 * (S11 - S22) ** 2 + S12 ** 2)
            els.append({"nodes": list(tri["n"]), "n_warp": S11, "n_weft": S22, "n_shear": S12,
                        "n1": m_ + r, "n2": m_ - r, "wrinkled": wr})
        R, _ = self.forces(X, None)
        reac = {}
        P = DRN.external_loads(self.m, X, pressure, snow, pfun) if (pressure or snow or pfun) else {}
        for i in range(len(X)):
            if any(self.fix[i]):                       # pull of structure + direct load (free components ~ 0)
                reac[i] = [R[i][c] + P.get(i, [0, 0, 0])[c] for c in range(3)]
        return els, reac


def analyse(base, Ew=800.0, Ef=600.0, nu=0.3, G=30.0, EA_cable=14000.0, pressure=0.0, snow=0.0, pfun=None,
            prestress=None, tol=1e-4, maxit=100000, verbose=False, wrinkling=True, do_ponding=False,
            depth_limit=1.0, solver="dr", follower_stiffness=True):
    """solver: "dr" (kinetic-damping dynamic relaxation, default) or "newton" (implicit Newton-Raphson with
    the consistent tangent, load stepping, line search, skyline Cholesky, DR fallback). Same equilibrium
    equations and outputs; maxit caps the DR iterations (Newton: at most 400 iterations per solve)."""
    if solver not in ("dr", "newton"):
        raise ValueError("solver must be 'dr' or 'newton'")
    model = copy.deepcopy(base)
    mem = Membrane(model, Ew, Ef, nu, G, EA_cable, prestress, wrinkling)
    nstats = []

    def solve(X, p=0.0, s=0.0, pf=None, extra=None, verbose=False):
        if solver == "dr":
            return mem.relax(X, p, s, pf, tol, maxit, verbose=verbose, extra=extra)
        out = mem.newton(X, p, s, pf, tol, min(maxit, 400), verbose=verbose, extra=extra,
                         follower=follower_stiffness)
        nstats.append(mem.newton_info)
        return out

    X = [list(p) for p in mem.X0]
    X, it0, r0 = solve(X, verbose=verbose)                                      # prestress equilibrium
    drift = max(math.dist(X[i], mem.X0[i]) for i in range(len(X)))
    Xp = [list(p) for p in X]
    els_p, _ = mem.results(Xp)
    X, it1, r1 = solve(X, pressure, snow, pfun, verbose=verbose)
    pond, extra = None, {}
    if do_ponding:  # same fill-to-spill iteration as dynamic_relaxation.ponding, with the membrane model
        outs = DRN.outlets(model)
        hist = []
        status = "no basin (surface drains)"
        for k in range(40):
            d = DRN.water_depths(model, X, outs)
            A = DRN.plan_areas(model, X)
            vol = sum(d[i] * A[i] for i in d)
            dmax = max(d.values()) if d else 0.0
            hist.append((vol, dmax))
            if vol < 1e-6:
                status = "no basin (surface drains)" if k == 0 else "stable"
                break
            if dmax > depth_limit:
                status = f"PONDING INSTABILITY (depth > {depth_limit} m)"
                break
            if k > 0 and abs(vol - hist[-2][0]) <= 0.01 * vol:
                status = "stable (water volume converged)"
                break
            extra = {i: [0.0, 0.0, -DRN.GAMMA_W * d[i] * A[i]] for i in d if d[i] > 0 and not mem.fixed[i]}
            X, _, r1 = solve(X, pressure, snow, pfun, extra=extra)
        else:
            status = "PONDING INSTABILITY (water volume did not converge)"
        pond = {"status": status, "water_volume_m3": hist[-1][0], "max_depth_m": hist[-1][1], "iterations": len(hist)}
    els, reac = mem.results(X, pressure, snow, pfun)
    if extra:
        for i, f in extra.items():
            if i in reac:
                for c in range(3):
                    reac[i][c] += f[c]
    disp = [math.dist(X[i], Xp[i]) for i in range(len(X))]
    imax = max(range(len(X)), key=lambda i: disp[i])
    for i, nd in enumerate(model["nodes"]):
        nd["xyz"] = X[i]
    for cb in mem.cables:
        e = model["edges"][cb["id"]]
        e["force"] = cb["_T"]
    model["elements"] = els
    model["reactions"] = [{"node": k, "pull": v, "magnitude": math.sqrt(dot(v, v))} for k, v in sorted(reac.items())]
    wr = [e["wrinkled"] for e in els]
    model["analysis"] = {
        "method": "CST orthotropic membrane (TL) + tension-field wrinkling, "
                  + ("dynamic relaxation" if solver == "dr" else "Newton-Raphson (consistent tangent)"),
        "solver": solver,
        "material": {"Ew_t": Ew, "Ef_t": Ef, "nu_wf": nu, "G_t": G, "EA_cable": EA_cable},
        "pressure_kN_m2": pressure, "snow_kN_m2": snow, "pressure_field": pfun is not None,
        "prestress_equilibrium": {"iterations": it0, "residual": r0, "max_drift_m": drift,
                                  "warp_range": (min(e["n_warp"] for e in els_p), max(e["n_warp"] for e in els_p)),
                                  "weft_range": (min(e["n_weft"] for e in els_p), max(e["n_weft"] for e in els_p))},
        "iterations": it1, "max_residual_kN": r1, "converged": r1 < tol,
        "max_displacement_m": disp[imax], "max_disp_node": imax,
        "wrinkled_elements": sum(1 for w in wr if w == 1), "slack_elements": sum(1 for w in wr if w == 2),
        "n_elements": len(els), "ponding": pond, "tol": tol}
    if nstats:
        tot = {k: sum(st[k] for st in nstats) for k in ("newton_iterations", "factorizations", "modified_steps",
                                                         "load_steps",
                                                         "step_cuts", "shifts", "line_search_cuts", "dr_iterations")}
        tot["fallback_dr"] = any(st["fallback_dr"] for st in nstats)
        tot["equations"] = nstats[0]["equations"]
        tot["skyline_profile"] = nstats[0]["profile"]
        model["analysis"]["newton"] = tot
    return model


def print_assumptions(an, wrinkling=True):
    print("Assumptions: membrane = constant-strain triangles (each quad split in two), Total-Lagrangian (Green strain, "
          "PK2 stress per unit reference width), linear-orthotropic plane stress in warp (grid u) / weft (grid v) axes;")
    print("  " + ("tension-field wrinkling (mixed criterion; uniaxial stress σ·n⊗n with σ = ε_nn/C_nn, exact for linear "
                  "orthotropy)" if wrinkling else "NO wrinkling model: compressive stresses are kept (--no-wrinkling)")
          + "; cables = tension-only links; follower pressure (+ = uplift), snow per plan area;")
    sol = ("Newton-Raphson (consistent tangent; wrinkled tangent by central differences; follower-pressure "
           "stiffness symmetrised, snow as dead load in the tangent; load stepping, energy line search; DR fallback)"
           if an.get("solver") == "newton" else "kinetic-damping DR")
    print("  initial stress from the form finding (per quad) or --prestress, relaxed to equilibrium first; "
          f"{sol} to max residual < {an.get('tol', 1e-4):.0e} kN. Not modelled: non-linear/hysteretic fabric,")
    print("  creep, crimp interchange beyond the constant ν, bending, dynamic wind. Screening/verification aid, not a "
          "replacement for a validated membrane FE package.")
    print()


def summary(model):
    an = model["analysis"]
    pe = an["prestress_equilibrium"]
    els = model["elements"]
    print(f"Membrane model: {an['n_elements']} CST elements; material E_w·t={an['material']['Ew_t']}, "
          f"E_f·t={an['material']['Ef_t']} kN/m, ν_wf={an['material']['nu_wf']}, G·t={an['material']['G_t']} kN/m")
    print(f"Prestress equilibrium: {pe['iterations']} it, drift {pe['max_drift_m'] * 1000:.1f} mm; warp "
          f"{pe['warp_range'][0]:.2f}–{pe['warp_range'][1]:.2f}, weft {pe['weft_range'][0]:.2f}–{pe['weft_range'][1]:.2f} kN/m")
    print(f"Load: pressure {an['pressure_kN_m2']:+.3f} kN/m2, snow {an['snow_kN_m2']:.3f} kN/m2 -> "
          f"{an['iterations']} it, residual {an['max_residual_kN']:.1e}" + ("" if an["converged"] else "  NOT CONVERGED"))
    if an.get("newton"):
        nw = an["newton"]
        print(f"Newton: {nw['newton_iterations']} iterations ({nw['factorizations']} factorisations, "
              f"{nw['modified_steps']} modified steps), {nw['load_steps']} load steps, {nw['step_cuts']} step cuts, "
              f"{nw['shifts']} tangent shifts; {nw['equations']} equations, skyline {nw['skyline_profile']} terms"
              + (f"; DR FALLBACK used ({nw['dr_iterations']} DR iterations)" if nw["fallback_dr"] else ""))
    print(f"Max displacement {an['max_displacement_m'] * 1000:.0f} mm")
    print(f"Stresses [kN/m]: warp max {max(e['n_warp'] for e in els):.2f}, weft max {max(e['n_weft'] for e in els):.2f}, "
          f"principal n1 max {max(e['n1'] for e in els):.2f}, n2 min {min(e['n2'] for e in els):.2f}")
    print(f"Wrinkled elements {an['wrinkled_elements']}, slack {an['slack_elements']} of {an['n_elements']}"
          + ("  -> check prestress/curvature (SLS appearance, flutter)" if an["wrinkled_elements"] + an["slack_elements"] else ""))
    if an.get("ponding"):
        p = an["ponding"]
        print(f"Ponding: {p['status']}; water {p['water_volume_m3']:.3f} m3, max depth {p['max_depth_m'] * 1000:.0f} mm"
              + ("  FAIL: ponding must be avoided" if p["water_volume_m3"] > 1e-6 else ""))
    groups = defaultdict(float)
    for e in model["edges"]:
        if e["kind"] != "membrane" and e.get("group"):
            groups[e["group"]] = max(groups[e["group"]], e.get("force", 0.0))
    for g, f in sorted(groups.items()):
        print(f"   {g:<12} Fmax = {f:8.2f} kN")
    print("Support pulls [kN]:")
    for rc in model["reactions"][:8]:
        x, y, z = rc["pull"]
        print(f"  node {rc['node']:>5}: Fx={x:9.2f} Fy={y:9.2f} Fz={z:9.2f} |F|={rc['magnitude']:9.2f}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("--Ew", type=float, default=800.0, help="warp E·t [kN/m]")
    ap.add_argument("--Ef", type=float, default=600.0, help="weft E·t [kN/m]")
    ap.add_argument("--nu", type=float, default=0.3, help="ν_wf (ν_fw by reciprocity)")
    ap.add_argument("--G", type=float, default=30.0, help="shear stiffness G·t [kN/m]")
    ap.add_argument("--EA-cable", type=float, default=14000.0)
    ap.add_argument("--pressure", type=float, default=0.0)
    ap.add_argument("--snow", type=float, default=0.0)
    ap.add_argument("--prestress", type=float, nargs=2, default=None, help="uniform S0 warp weft [kN/m]")
    ap.add_argument("--no-wrinkling", action="store_true")
    ap.add_argument("--ponding", action="store_true")
    ap.add_argument("--solver", choices=["dr", "newton"], default="dr",
                    help="dr = kinetic-damping dynamic relaxation (default); newton = implicit Newton-Raphson with the "
                         "consistent tangent, load stepping, line search, skyline Cholesky, DR fallback (faster on "
                         "large meshes, same equilibrium)")
    ap.add_argument("--no-follower-stiffness", action="store_true",
                    help="newton: leave the (symmetrised) follower-pressure load stiffness out of the tangent")
    ap.add_argument("--tol", type=float, default=1e-4)
    ap.add_argument("--maxit", type=int, default=100000, help="max DR iterations (newton: max 400 iterations)")
    ap.add_argument("--out", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    with open(a.model) as fh:
        base = json.load(fh)
    m = analyse(base, a.Ew, a.Ef, a.nu, a.G, a.EA_cable, a.pressure, a.snow, None, a.prestress, a.tol, a.maxit,
                a.verbose, not a.no_wrinkling, a.ponding, solver=a.solver,
                follower_stiffness=not a.no_follower_stiffness)
    print_assumptions(m["analysis"], not a.no_wrinkling)
    summary(m)
    if a.out:
        with open(a.out + ".json", "w") as fh:
            json.dump(m, fh, indent=1)
        print(f"Wrote {a.out}.json")
    return m


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
