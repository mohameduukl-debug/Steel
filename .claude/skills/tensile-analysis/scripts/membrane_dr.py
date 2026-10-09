#!/usr/bin/env python3
"""Orthotropic MEMBRANE analysis (CST elements + wrinkling) by Dynamic Relaxation.

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
Validation (reference/validation.md): Hencky/Fichter clamped circular membrane, prestressed square under
pressure (Poisson equation), tension-field uniaxial/off-axis/shear-panel cases.
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


class Membrane:
    def __init__(self, model, Ew, Ef, nu_wf, G, EA_cable, prestress=None, wrinkling=True):
        self.m = model
        nodes = model["nodes"]
        self.X0 = [list(nd["xyz"]) for nd in nodes]          # reference = form-found geometry
        self.fixed = [bool(nd.get("fixed")) for nd in nodes]
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
            if self.fixed[i]:
                reac[i] = [R[i][c] + P.get(i, [0, 0, 0])[c] for c in range(3)]  # pull of structure + direct load
        return els, reac


def analyse(base, Ew=800.0, Ef=600.0, nu=0.3, G=30.0, EA_cable=14000.0, pressure=0.0, snow=0.0, pfun=None,
            prestress=None, tol=1e-4, maxit=100000, verbose=False, wrinkling=True, do_ponding=False,
            depth_limit=1.0):
    model = copy.deepcopy(base)
    mem = Membrane(model, Ew, Ef, nu, G, EA_cable, prestress, wrinkling)
    X = [list(p) for p in mem.X0]
    X, it0, r0 = mem.relax(X, tol=tol, maxit=maxit, verbose=verbose)           # prestress equilibrium
    drift = max(math.dist(X[i], mem.X0[i]) for i in range(len(X)))
    Xp = [list(p) for p in X]
    els_p, _ = mem.results(Xp)
    X, it1, r1 = mem.relax(X, pressure, snow, pfun, tol, maxit, verbose=verbose)
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
            X, _, r1 = mem.relax(X, pressure, snow, pfun, tol, maxit, extra=extra)
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
        "method": "CST orthotropic membrane (TL) + tension-field wrinkling, dynamic relaxation",
        "material": {"Ew_t": Ew, "Ef_t": Ef, "nu_wf": nu, "G_t": G, "EA_cable": EA_cable},
        "pressure_kN_m2": pressure, "snow_kN_m2": snow, "pressure_field": pfun is not None,
        "prestress_equilibrium": {"iterations": it0, "residual": r0, "max_drift_m": drift,
                                  "warp_range": (min(e["n_warp"] for e in els_p), max(e["n_warp"] for e in els_p)),
                                  "weft_range": (min(e["n_weft"] for e in els_p), max(e["n_weft"] for e in els_p))},
        "iterations": it1, "max_residual_kN": r1, "converged": r1 < tol,
        "max_displacement_m": disp[imax], "max_disp_node": imax,
        "wrinkled_elements": sum(1 for w in wr if w == 1), "slack_elements": sum(1 for w in wr if w == 2),
        "n_elements": len(els), "ponding": pond, "tol": tol}
    return model


def print_assumptions(an, wrinkling=True):
    print("Assumptions: membrane = constant-strain triangles (each quad split in two), Total-Lagrangian (Green strain, "
          "PK2 stress per unit reference width), linear-orthotropic plane stress in warp (grid u) / weft (grid v) axes;")
    print("  " + ("tension-field wrinkling (mixed criterion; uniaxial stress σ·n⊗n with σ = ε_nn/C_nn, exact for linear "
                  "orthotropy)" if wrinkling else "NO wrinkling model: compressive stresses are kept (--no-wrinkling)")
          + "; cables = tension-only links; follower pressure (+ = uplift), snow per plan area;")
    print("  initial stress from the form finding (per quad) or --prestress, relaxed to equilibrium first; "
          f"kinetic-damping DR to max residual < {an.get('tol', 1e-4):.0e} kN. Not modelled: non-linear/hysteretic fabric,")
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
    ap.add_argument("--tol", type=float, default=1e-4)
    ap.add_argument("--maxit", type=int, default=100000)
    ap.add_argument("--out", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    with open(a.model) as fh:
        base = json.load(fh)
    m = analyse(base, a.Ew, a.Ef, a.nu, a.G, a.EA_cable, a.pressure, a.snow, None, a.prestress, a.tol, a.maxit,
                a.verbose, not a.no_wrinkling, a.ponding)
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
