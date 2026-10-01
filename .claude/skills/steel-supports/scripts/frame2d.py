#!/usr/bin/env python3
"""2D frame analysis for tensile-structure steelwork: linear, elastic buckling (α_cr) and
second-order (P-Δ/P-δ) with a buckling-mode imperfection, plus EN 1993-1-1 member checks.

Pure-Python (banded solver, stdlib only). Euler–Bernoulli beam-column elements (3 DOF/node)
with consistent geometric stiffness; truss elements for guys/ties/struts.

Use it for arches (in-plane buckling), tapered "cigar" masts, guyed masts, portal frames,
booms, rings segments — anything planar whose stability is not a simple Euler column.

Generators
  arch     parabolic or circular arch, span L, rise f, pinned or fixed springings,
           uniform load per horizontal metre (--q, kN/m, downward +) and/or point loads
  mast     (tapered) CHS mast, pinned or fixed base, head load N (+ lateral H), optional guys
  --input  frame.json (schema in reference/steel-support-design.md)

Outputs: max N, V, M per member (first- and second-order), α_cr and mode, reactions,
and — with --check — EN 1993-1-1 member checks through member_check.py:
  * equivalent-column method: in-plane L_cr = π·√(EI/(α_cr·N_Ed)) (5.2.2(8)) + first-order M
  * second-order method: mode-shaped imperfection e0 (Table 5.1) -> section check with 2nd-order M

Examples
  python3 frame2d.py arch --L 30 --f 6 --n 24 --section CHS:323.9x10 --q 12 --supports pinned --check
  python3 frame2d.py mast --H 12 --D-base 219.1 --D-mid 323.9 --D-top 219.1 --t 8 --N 600 --check
  python3 frame2d.py --input frame.json --check
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tensile-structures", "scripts"))
import factors as CF  # noqa: E402
import member_check as MC  # noqa: E402

# Classical in-plane buckling of uniform parabolic arches under uniform load per horizontal metre:
# q_cr = γ·EI/L³ (Timoshenko & Gere, Theory of Elastic Stability, after Dinnik). Used only as a cross-check:
# frame2d itself reproduces exact ring and circular-arch solutions; against this table it differs by −0.5 … +8 %,
# so arch designs use the lower of the two α_cr values.
CLASSICAL_PARABOLIC = {"pinned": {0.1: 28.5, 0.2: 45.4, 0.3: 46.5, 0.4: 43.9, 0.5: 38.4},
                       "fixed": {0.1: 60.7, 0.2: 101.0, 0.3: 115.0, 0.4: 111.0, 0.5: 97.4}}

E0_ELASTIC = {"a0": 1 / 350, "a": 1 / 300, "b": 1 / 250, "c": 1 / 200, "d": 1 / 150}  # EN 1993-1-1 Table 5.1


# ------------------------------------------------------------ banded solver
class Banded:
    """LU (no pivoting) of a symmetric banded matrix stored as dict rows; fine for K and K+K_G below buckling."""

    def __init__(self, n, bw):
        self.n, self.bw = n, bw
        self.a = [[0.0] * (2 * bw + 1) for _ in range(n)]

    def add(self, i, j, v):
        self.a[i][j - i + self.bw] += v

    def get(self, i, j):
        k = j - i + self.bw
        return self.a[i][k] if 0 <= k <= 2 * self.bw else 0.0

    def factor(self):
        n, b, a = self.n, self.bw, self.a
        for k in range(n):
            piv = a[k][b]
            if abs(piv) < 1e-14:
                raise ZeroDivisionError("singular stiffness (mechanism or buckled)")
            for i in range(k + 1, min(n, k + b + 1)):
                lik = a[i][k - i + b] / piv
                if lik == 0.0:
                    continue
                a[i][k - i + b] = lik
                for j in range(k + 1, min(n, k + b + 1)):
                    a[i][j - i + b] -= lik * a[k][j - k + b]
        return self

    def solve(self, rhs):
        n, b, a = self.n, self.bw, self.a
        y = list(rhs)
        for i in range(n):
            s = y[i]
            for k in range(max(0, i - b), i):
                s -= a[i][k - i + b] * y[k]
            y[i] = s
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            s = y[i]
            for k in range(i + 1, min(n, i + b + 1)):
                s -= a[i][k - i + b] * x[k]
            x[i] = s / a[i][b]
        return x

    def matvec(self, x):
        n, b = self.n, self.bw
        return [sum(self.get(i, j) * x[j] for j in range(max(0, i - b), min(n, i + b + 1))) for i in range(n)]


# ------------------------------------------------------------ elements
def beam_local(E, A, I, L):
    k = [[0.0] * 6 for _ in range(6)]
    ea, ei = E * A / L, E * I
    k[0][0] = k[3][3] = ea
    k[0][3] = k[3][0] = -ea
    c1, c2, c3, c4 = 12 * ei / L ** 3, 6 * ei / L ** 2, 4 * ei / L, 2 * ei / L
    for (i, j, v) in ((1, 1, c1), (1, 2, c2), (1, 4, -c1), (1, 5, c2), (2, 2, c3), (2, 4, -c2), (2, 5, c4),
                      (4, 4, c1), (4, 5, -c2), (5, 5, c3)):
        k[i][j] = k[j][i] = v
    return k


def geo_local(N, L, truss=False):
    """consistent geometric stiffness; N > 0 tension."""
    g = [[0.0] * 6 for _ in range(6)]
    if truss:
        for (i, j, v) in ((1, 1, 1), (1, 4, -1), (4, 4, 1)):
            g[i][j] = g[j][i] = N / L * v
        return g
    f = N / (30 * L)
    for (i, j, v) in ((1, 1, 36), (1, 2, 3 * L), (1, 4, -36), (1, 5, 3 * L), (2, 2, 4 * L * L), (2, 4, -3 * L),
                      (2, 5, -L * L), (4, 4, 36), (4, 5, -3 * L), (5, 5, 4 * L * L)):
        g[i][j] = g[j][i] = f * v
    return g


def rot(c, s):
    T = [[0.0] * 6 for _ in range(6)]
    for o in (0, 3):
        T[o][o], T[o][o + 1], T[o + 1][o], T[o + 1][o + 1], T[o + 2][o + 2] = c, s, -s, c, 1.0
    return T


def mat_t_k_t(T, k):
    kt = [[sum(k[i][m] * T[m][j] for m in range(6)) for j in range(6)] for i in range(6)]
    return [[sum(T[m][i] * kt[m][j] for m in range(6)) for j in range(6)] for i in range(6)]


class Frame:
    def __init__(self):
        self.nodes = []      # [x, y]
        self.supports = {}   # node -> (rx, ry, rz) 1 = fixed
        self.elems = []      # dict(n=(a,b), E, A, I, truss, member, fy, section)
        self.members = {}    # name -> dict(section, fy, elems=[...], sec=Section)
        self.nodal = {}      # node -> [fx, fy, m]
        self.udl = []        # (elem index, qx_global, qy_global) per unit length
        self.pressure = []   # (elem index, pn) FOLLOWER load per unit length along the left normal of a->b

    def add_member(self, name, node_ids, section=None, fy=355.0, A=None, I=None, E=None, truss=False):
        E = E or CF.get("steel.E") * 1e-3  # kN/mm2 -> we use kN, m: E in kN/m2 below
        sec = None
        if section:
            sec = MC.Section(section)
            A, I = sec.A * 1e-6, sec.Iy * 1e-12
        self.members[name] = {"section": section, "fy": fy, "elems": [], "sec": sec, "truss": truss}
        for a, b in zip(node_ids[:-1], node_ids[1:]):
            self.elems.append({"n": (a, b), "E": CF.get("steel.E") * 1e3, "A": A, "I": I or 0.0, "truss": truss,
                               "member": name})
            self.members[name]["elems"].append(len(self.elems) - 1)

    # --- assembly
    def dof_map(self):
        m = {}
        k = 0
        for i in range(len(self.nodes)):
            r = self.supports.get(i, (0, 0, 0))
            for d in range(3):
                if not r[d]:
                    m[(i, d)] = k
                    k += 1
        return m, k

    def geom(self, e, U=None):
        (a, b) = e["n"]
        xa, ya = self.nodes[a]
        xb, yb = self.nodes[b]
        dx, dy = xb - xa, yb - ya
        L = math.hypot(dx, dy)
        return L, dx / L, dy / L

    def follower_terms(self, ei, pn):
        """dF_ext/dU of a follower pressure on element ei: f_a = f_b = (pn/2)·(−Δy, Δx) (lumped part)."""
        (a, b) = self.elems[ei]["n"]
        h = pn / 2
        out = []
        for row_node in (a, b):
            out += [((row_node, 0), (a, 1), h), ((row_node, 0), (b, 1), -h),
                    ((row_node, 1), (a, 0), -h), ((row_node, 1), (b, 0), h)]
        return out

    def assemble(self, dmap, n, Nax=None, geo_only=False, factor_geo=1.0, follower=0.0):
        bw = 0
        for e in self.elems:
            ids = [dmap.get((v, d)) for v in e["n"] for d in range(3)]
            ids = [i for i in ids if i is not None]
            if ids:
                bw = max(bw, max(ids) - min(ids))
        K = Banded(n, max(bw, 1))
        for ei, e in enumerate(self.elems):
            L, c, s = self.geom(e)
            kl = [[0.0] * 6 for _ in range(6)]
            if not geo_only:
                if e["truss"]:
                    ea = e["E"] * e["A"] / L
                    kl[0][0] = kl[3][3] = ea
                    kl[0][3] = kl[3][0] = -ea
                else:
                    kl = beam_local(e["E"], e["A"], e["I"], L)
            if Nax is not None:
                g = geo_local(Nax[ei], L, e["truss"])
                kl = [[kl[i][j] + factor_geo * g[i][j] for j in range(6)] for i in range(6)]
            kg = mat_t_k_t(rot(c, s), kl)
            dofs = [dmap.get((v, d)) for v in e["n"] for d in range(3)]
            for i in range(6):
                if dofs[i] is None:
                    continue
                for j in range(6):
                    if dofs[j] is not None:
                        K.add(dofs[i], dofs[j], kg[i][j])
        if follower:
            # tangent of loads that follow the deformation: K_t = K − dF_ext/dU (non-symmetric)
            for ei, pn in self.pressure:
                for r, c, v in self.follower_terms(ei, pn):
                    if r in dmap and c in dmap:
                        K.add(dmap[r], dmap[c], -follower * v)
        return K

    def load_vector(self, dmap, n, extra=None):
        F = [0.0] * n
        full = {}
        for node, f in self.nodal.items():
            for d in range(3):
                full[(node, d)] = full.get((node, d), 0.0) + f[d]
        for (ei, qx, qy) in self.udl:
            e = self.elems[ei]
            L, c, s = self.geom(e)
            # local components of a global load per unit length
            qa = qx * c + qy * s
            qt = -qx * s + qy * c
            fl = [qa * L / 2, qt * L / 2, qt * L * L / 12, qa * L / 2, qt * L / 2, -qt * L * L / 12]
            T = rot(c, s)
            fg = [sum(T[m][i] * fl[m] for m in range(6)) for i in range(6)]
            for k, (v, d) in enumerate((v, d) for v in e["n"] for d in range(3)):
                full[(v, d)] = full.get((v, d), 0.0) + fg[k]
        for (ei, pn) in self.pressure:
            e = self.elems[ei]
            L, c, s = self.geom(e)
            fl = [0.0, pn * L / 2, pn * L * L / 12, 0.0, pn * L / 2, -pn * L * L / 12]
            T = rot(c, s)
            fg = [sum(T[m][i] * fl[m] for m in range(6)) for i in range(6)]
            for k, (v, d) in enumerate((v, d) for v in e["n"] for d in range(3)):
                full[(v, d)] = full.get((v, d), 0.0) + fg[k]
        if extra:
            for key, v in extra.items():
                full[key] = full.get(key, 0.0) + v
        for key, v in full.items():
            if key in dmap:
                F[dmap[key]] += v
        return F, full

    def element_forces(self, dmap, u, Nax=None):
        """local end forces [N1, V1, M1, N2, V2, M2] (N1 +tension convention returned as N)."""
        out = []
        for ei, e in enumerate(self.elems):
            L, c, s = self.geom(e)
            ug = [u[dmap[(v, d)]] if (v, d) in dmap else 0.0 for v in e["n"] for d in range(3)]
            T = rot(c, s)
            ul = [sum(T[i][m] * ug[m] for m in range(6)) for i in range(6)]
            if e["truss"]:
                kl = [[0.0] * 6 for _ in range(6)]
                ea = e["E"] * e["A"] / L
                kl[0][0] = kl[3][3] = ea
                kl[0][3] = kl[3][0] = -ea
            else:
                kl = beam_local(e["E"], e["A"], e["I"], L)
            if Nax is not None:
                g = geo_local(Nax[ei], L, e["truss"])
                kl = [[kl[i][j] + g[i][j] for j in range(6)] for i in range(6)]
            f = [sum(kl[i][m] * ul[m] for m in range(6)) for i in range(6)]
            for (eu, qx, qy) in self.udl:
                if eu == ei:
                    qa = qx * c + qy * s
                    qt = -qx * s + qy * c
                    fe = [qa * L / 2, qt * L / 2, qt * L * L / 12, qa * L / 2, qt * L / 2, -qt * L * L / 12]
                    f = [f[i] - fe[i] for i in range(6)]
            for (eu, pn) in self.pressure:
                if eu == ei:
                    fe = [0.0, pn * L / 2, pn * L * L / 12, 0.0, pn * L / 2, -pn * L * L / 12]
                    f = [f[i] - fe[i] for i in range(6)]
            N = f[3]  # tension positive (force on end 2 along local x)
            out.append({"N": N, "V1": f[1], "M1": -f[2], "M2": f[5], "L": L})
        return out

    # --- analyses
    def linear(self):
        dmap, n = self.dof_map()
        K = self.assemble(dmap, n).factor()
        F, _ = self.load_vector(dmap, n)
        u = K.solve(F)
        return dmap, u, self.element_forces(dmap, u)

    def buckling(self, forces, iters=400, tol=1e-9):
        """smallest positive λ with det(K + λ (K_G(N) − K_P)) = 0 via inverse (power) iteration on K^-1(-K_G).

        K_P = dF/dU of follower pressures (self.pressure); dead loads (nodal, udl) keep their direction."""
        dmap, n = self.dof_map()
        Nax = [f["N"] for f in forces]
        K = self.assemble(dmap, n).factor()
        KG = self.assemble(dmap, n, Nax=Nax, geo_only=True, follower=1.0)

        def op(x):
            return K.solve([-v for v in KG.matvec(x)])

        def power(shift=0.0):
            x = [1.0 + 0.01 * ((i * 7919) % 13) for i in range(n)]
            mu = 0.0
            for _ in range(iters):
                y = op(x)
                if shift:
                    y = [yi + shift * xi for yi, xi in zip(y, x)]
                nrm = math.sqrt(sum(v * v for v in y)) or 1e-30
                mu_new = sum(a * b for a, b in zip(y, x)) / (sum(v * v for v in x) or 1e-30)
                x = [v / nrm for v in y]
                if abs(mu_new - mu) <= tol * max(1.0, abs(mu_new)):
                    mu = mu_new
                    break
                mu = mu_new
            return mu - shift, x

        mu, x = power()
        if mu <= 0:  # dominant eigenvalue negative (tension stiffening) -> shift to find largest positive
            mu, x = power(shift=abs(mu) * 1.05)
        lam = 1.0 / mu if mu > 0 else math.inf
        mode = {key: x[i] for key, i in dmap.items()}
        return lam, mode

    def second_order(self, imperfection=None, iters=50, tol=1e-6):
        """P-Δ/P-δ by iterating K_G(N); imperfection = {(node, dof): offset} added to geometry."""
        saved = [list(p) for p in self.nodes]
        if imperfection:
            for (node, d), v in imperfection.items():
                if d < 2:
                    self.nodes[node][d] += v
        try:
            dmap, u, forces = self.linear()
            for _ in range(iters):
                Nax = [f["N"] for f in forces]
                K = self.assemble(dmap, len(u), Nax=Nax, follower=1.0).factor()
                F, _ = self.load_vector(dmap, len(u))
                u2 = K.solve(F)
                f2 = self.element_forces(dmap, u2, Nax)
                if max(abs(a["N"] - b["N"]) for a, b in zip(f2, forces)) < tol * max(1.0, max(abs(b["N"]) for b in f2)):
                    u, forces = u2, f2
                    break
                u, forces = u2, f2
        finally:
            self.nodes = saved
        return dmap, u, forces

    def reactions(self, dmap, u):
        """support reactions from full stiffness (kN, kNm)."""
        R = {}
        for ei, e in enumerate(self.elems):
            pass
        # simple approach: re-assemble unrestrained K and compute K u - F at restrained dofs
        full = {}
        k = 0
        for i in range(len(self.nodes)):
            for d in range(3):
                full[(i, d)] = k
                k += 1
        saved = self.supports
        self.supports = {}
        try:
            Kf = self.assemble(full, k)
            U = [u[dmap[key]] if key in dmap else 0.0 for key in sorted(full, key=lambda t: full[t])]
            Ku = Kf.matvec(U)
            F, _ = self.load_vector(full, k)
        finally:
            self.supports = saved
        for node, r in saved.items():
            R[node] = [Ku[full[(node, d)]] - F[full[(node, d)]] for d in range(3)]
        return R


# ------------------------------------------------------------ generators
def gen_arch(L, f, n, section, fy, supports, q, shape="parabolic", P=None, p_normal=0.0):
    fr = Frame()
    if shape == "circular":
        R = (L * L / 4 + f * f) / (2 * f)
        th = math.asin(L / (2 * R))
        for i in range(n + 1):
            a = -th + 2 * th * i / n
            fr.nodes.append([L / 2 + R * math.sin(a), R * math.cos(a) - (R - f)])
    else:
        for i in range(n + 1):
            x = L * i / n
            fr.nodes.append([x, 4 * f * x * (L - x) / (L * L)])
    fix = (1, 1, 1) if supports == "fixed" else (1, 1, 0)
    fr.supports = {0: fix, n: fix}
    fr.add_member("ARCH", list(range(n + 1)), section=section, fy=fy)
    if q:
        for ei in range(n):
            (a, b) = fr.elems[ei]["n"]
            L_e = math.hypot(fr.nodes[b][0] - fr.nodes[a][0], fr.nodes[b][1] - fr.nodes[a][1])
            proj = abs(fr.nodes[b][0] - fr.nodes[a][0]) / L_e
            fr.udl.append((ei, 0.0, -q * proj))  # q per horizontal metre, downward
    if q and shape == "parabolic" and not P and not p_normal:
        fr.classical = {"L": L, "f_L": f / L, "supports": supports, "q": q}
    if p_normal:
        # nodes run left -> right over the crown, so the left normal points outward: inward pressure = −pn
        fr.pressure = [(ei, -p_normal) for ei in range(n)]
    if P:
        for (node, fx, fy_) in P:
            fr.nodal[node] = [fx, fy_, 0.0]
    return fr


def gen_mast(H, n, D_base, D_mid, D_top, t, fy, base, N, Hlat, guys):
    fr = Frame()
    for i in range(n + 1):
        fr.nodes.append([0.0, H * i / n])
    fr.supports = {0: (1, 1, 1) if base == "fixed" else (1, 1, 0)}
    # piecewise-linear taper base -> mid -> top, one member per element (varying section)
    for i in range(n):
        z = H * (i + 0.5) / n
        D = D_base + (D_mid - D_base) * (2 * z / H) if z <= H / 2 else D_mid + (D_top - D_mid) * (2 * z / H - 1)
        fr.add_member(f"M{i:02d}", [i, i + 1], section=f"CHS:{D:.1f}x{t}", fy=fy)
    fr.mast_elems = [f"M{i:02d}" for i in range(n)]
    fr.nodal[n] = [Hlat, -N, 0.0]
    for k, (dx, EA) in enumerate(guys):
        g = len(fr.nodes)
        fr.nodes.append([dx, 0.0])
        fr.supports[g] = (1, 1, 1)
        fr.members[f"GUY{k}"] = {"section": None, "fy": None, "elems": [], "sec": None, "truss": True}
        fr.elems.append({"n": (g, n), "E": 1.0, "A": EA, "I": 0.0, "truss": True, "member": f"GUY{k}"})
        fr.members[f"GUY{k}"]["elems"].append(len(fr.elems) - 1)
    if base != "fixed" and not guys:
        fr.supports[n] = (1, 0, 0)  # pinned-pinned mast (head held laterally by the membrane/cables)
    return fr


def from_json(d):
    fr = Frame()
    fr.nodes = [list(map(float, p)) for p in d["nodes"]]
    fr.supports = {int(k): tuple(v) for k, v in d["supports"].items()}
    for m in d["members"]:
        fr.add_member(m["name"], m["nodes"], section=m.get("section"), fy=m.get("fy", 355.0),
                      A=m.get("A"), I=m.get("I"), truss=m.get("truss", False))
    for k, v in d.get("loads", {}).get("nodal", {}).items():
        fr.nodal[int(k)] = v
    for u in d.get("loads", {}).get("udl", []):
        for ei in fr.members[u["member"]]["elems"]:
            e = fr.elems[ei]
            (a, b) = e["n"]
            L_e = math.hypot(fr.nodes[b][0] - fr.nodes[a][0], fr.nodes[b][1] - fr.nodes[a][1])
            proj = abs(fr.nodes[b][0] - fr.nodes[a][0]) / L_e if u.get("per_horizontal") else 1.0
            fr.udl.append((ei, u.get("qx", 0.0) * proj, u.get("qy", 0.0) * proj))
    for pr in d.get("loads", {}).get("pressure", []):
        sign = 1.0 if pr.get("side", "left") == "left" else -1.0
        fr.pressure += [(ei, sign * pr["p"]) for ei in fr.members[pr["member"]]["elems"]]
    return fr


# ------------------------------------------------------------ reporting / design
def member_summary(fr, forces):
    out = {}
    for name, m in fr.members.items():
        fs = [forces[i] for i in m["elems"]]
        out[name] = {"N_min": min(f["N"] for f in fs), "N_max": max(f["N"] for f in fs),
                     "M_max": max(max(abs(f["M1"]), abs(f["M2"])) for f in fs),
                     "V_max": max(abs(f["V1"]) for f in fs), "L": sum(f["L"] for f in fs)}
    return out


def design_aisc(fr, lin, sec_order, alpha, members=None, Lz=None, code="US", method="LRFD"):
    """AISC 360-22 / SBC 306: (a) effective-length method (L_c from α_cr, first-order M with B1);
    (b) direct analysis method (C2/C3: second-order M with 0.8EI and a 1/500 mode-shaped imperfection, K = 1 on
        the physical member length). The effective-length method needs α_cr ≥ 3 (Δ2nd/Δ1st ≤ 1.5, App. 7)."""
    import aisc_member as AM
    E = CF.get("steel.E")
    rows = []
    mast = [n for n in fr.members if n.startswith("M") and n[1:].isdigit() and not fr.members[n]["truss"]]
    Lphys = sum(lin[n]["L"] for n in mast) if len(mast) > 1 else None
    for name, m in fr.members.items():
        if m["truss"] or not m["section"] or (members and name not in members):
            continue
        s1, s2 = lin[name], sec_order[name]
        sec = m["sec"]
        Lm = s1["L"]
        NEd = max(-s1["N_min"], 0.0)
        Lcr = (math.pi * math.sqrt(E * sec.Iy / (alpha * NEd * 1e3)) / 1000) if NEd > 0 and alpha < math.inf else Lm
        kz = Lz / Lm if Lz else 1.0
        r1, _ = AM.check(sec, m["fy"], Lm, NEd, s1["M_max"], 0.0, s1["V_max"], 0.0, Kx=Lcr / Lm, Ky=kz,
                         code=code, method=method)
        # DAM (AISC C2/C3): K = 1 on the PHYSICAL member length (a mast split into M00…Mnn is one member)
        kx_dam = (Lphys / Lm) if Lphys else 1.0
        r2, _ = AM.check(sec, m["fy"], Lm, max(-s2["N_min"], 0.0), s2["M_max"], 0.0, s2["V_max"], 0.0, Kx=kx_dam,
                         Ky=kz, code=code, method=method, second_order=True)
        rows.append({"member": name, "section": m["section"], "N_Ed": NEd, "M1": s1["M_max"], "M2": s2["M_max"],
                     "Lcr_inplane": Lcr, "util_equiv_column": max(d / c for _, d, c, _ in r1),
                     "util_second_order_section": max(d / c for _, d, c, _ in r2), "class": None})
    return rows


def design(fr, lin, sec_order, alpha, members=None, Lz=None):
    rows = []
    for name, m in fr.members.items():
        if m["truss"] or not m["section"]:
            continue
        if members and name not in members:
            continue
        s1, s2 = lin[name], sec_order[name]
        NEd = max(-s1["N_min"], 0.0)
        sec = m["sec"]
        E = CF.get("steel.E")
        if NEd > 0 and alpha < math.inf:
            Ncr = alpha * NEd * 1e3
            Lcr = math.pi * math.sqrt(E * sec.Iy / Ncr) / 1000  # m
        else:
            Lcr = s1["L"]
        # (a) equivalent column: first-order M, L_cr from α_cr (in-plane = y), out-of-plane Lz
        Lm = s1["L"]
        r1, res1 = MC.check(sec, m["fy"], Lm, NEd, s1["M_max"], 0.0, 0.0, s1["V_max"], ky=Lcr / Lm,
                            kz=(Lz / Lm if Lz else 1.0))
        u1 = max(d / c for _, d, c, _ in r1)
        # (b) second-order + imperfection: cross-section check in plane, out-of-plane buckling still with Lz
        NEd2 = max(-s2["N_min"], 0.0)
        gM0 = CF.get("steel.gM0")
        W = sec.Wpl_y if res1["class"] <= 2 else sec.Wel_y
        u2 = NEd2 * 1e3 / (sec.A * m["fy"] / gM0) + s2["M_max"] * 1e6 / (W * m["fy"] / gM0)
        rows.append({"member": name, "section": m["section"], "N_Ed": NEd, "M1": s1["M_max"], "M2": s2["M_max"],
                     "Lcr_inplane": Lcr, "util_equiv_column": u1, "util_second_order_section": u2,
                     "class": res1["class"]})
    return rows


def classical_alpha(fr):
    """α_cr from the classical parabolic-arch table (interpolated in f/L), or None outside its scope."""
    c = getattr(fr, "classical", None)
    if not c:
        return None
    tab = CLASSICAL_PARABOLIC[c["supports"]]
    ks = sorted(tab)
    if not ks[0] <= c["f_L"] <= ks[-1]:
        return None
    for k0, k1 in zip(ks[:-1], ks[1:]):
        if k0 <= c["f_L"] <= k1:
            gam = tab[k0] + (tab[k1] - tab[k0]) * (c["f_L"] - k0) / (k1 - k0)
            break
    e = fr.elems[0]
    return gam * e["E"] * e["I"] / c["L"] ** 3 / c["q"]


def run(fr, check=False, imp_curve=None, Lz=None, quiet=False, code="EU", method="LRFD"):
    dmap, u, f1 = fr.linear()
    lam_fe, mode = fr.buckling(f1)
    lam_cl = classical_alpha(fr)
    lam = min(lam_fe, lam_cl) if lam_cl else lam_fe
    s1 = member_summary(fr, f1)
    # mode-shaped imperfection: amplitude e0·L of the longest compressed member (Table 5.1 elastic)
    comp = [(n, m) for n, m in s1.items() if m["N_min"] < 0 and not fr.members[n]["truss"]]
    curve = imp_curve
    if comp and not curve:
        name = max(comp, key=lambda nm: -nm[1]["N_min"])[0]
        sec = fr.members[name]["sec"]
        curve = sec.curves(fr.members[name]["fy"])[0] if sec else "c"
    Lref = sum(m["L"] for n, m in comp) if len(comp) > 1 and all(n.startswith("M") for n, _ in comp) else \
        (max(m["L"] for _, m in comp) if comp else 1.0)
    if code == "EU":
        amp = E0_ELASTIC.get(curve or "c", 1 / 200) * Lref
    else:   # AISC C2.2a system imperfection 1/500, shaped as the buckling mode
        amp = CF.get("aisc.imperfection_ratio") * Lref
        curve = "AISC C2.2a 1/500"
    mx = max((abs(v) for (node, d), v in mode.items() if d < 2), default=1.0) or 1.0
    imp = {k: v / mx * amp for k, v in mode.items() if k[1] < 2}
    if code != "EU":   # AISC C2.3 reduced stiffness for the second-order (direct analysis) run
        red = CF.get("aisc.dam_stiffness")
        saved_E = [e["E"] for e in fr.elems]
        for e in fr.elems:
            e["E"] *= red
        try:
            _, u2, f2 = fr.second_order(imp)
        finally:
            for e, E_ in zip(fr.elems, saved_E):
                e["E"] = E_
    else:
        _, u2, f2 = fr.second_order(imp)
    s2 = member_summary(fr, f2)
    R = fr.reactions(dmap, u)
    res = {"alpha_cr": lam, "alpha_cr_fe": lam_fe, "alpha_cr_classical": lam_cl, "first_order": s1, "second_order": s2, "reactions": R,
           "imperfection": {"curve": curve, "amplitude_m": amp},
           "max_disp_m": max((abs(v) for v in u), default=0.0)}
    res["code"] = code
    if check:
        res["design"] = (design(fr, s1, s2, lam, Lz=Lz) if code == "EU" else
                         design_aisc(fr, s1, s2, lam, Lz=Lz, code=code, method=method))
    if not quiet:
        report(fr, res)
    return res


def report(fr, res):
    a = res["alpha_cr"]
    if res.get("alpha_cr_classical"):
        print(f"α_cr: FE {res['alpha_cr_fe']:.2f}, classical parabolic-arch table {res['alpha_cr_classical']:.2f} "
              f"(Timoshenko & Gere) -> design uses the lower value")
    print(f"Elastic critical load factor α_cr = {a:.2f}  "
          + ("(≥ 10: first-order analysis adequate, EN 1993-1-1 5.2.1)" if a >= 10 else
             "(< 10: second-order effects must be included)"))
    imp = res["imperfection"]
    print(f"Imperfection for 2nd order: buckling-mode shape, amplitude {imp['amplitude_m'] * 1000:.1f} mm ("
          + (f"e0 curve {imp['curve']}, EN 1993-1-1 Table 5.1 elastic)" if res.get("code", "EU") == "EU"
             else f"{imp['curve']}; second-order run with 0.8EI)"))
    print(f"\n{'member':<10}{'N_min 1st':>11}{'N_min 2nd':>11}{'M 1st':>9}{'M 2nd':>9}{'V max':>9}  [kN, kNm]")
    for name in fr.members:
        a1, a2 = res["first_order"][name], res["second_order"][name]
        if len(fr.members) > 12 and name.startswith("M") and name not in ("M00", f"M{len(fr.members) - 1:02d}"):
            continue
        print(f"{name:<10}{a1['N_min']:11.1f}{a2['N_min']:11.1f}{a1['M_max']:9.2f}{a2['M_max']:9.2f}{a1['V_max']:9.2f}")
    print("\nReactions [kN, kNm]:")
    for node, r in res["reactions"].items():
        print(f"  node {node:>3}: Rx={r[0]:9.2f} Ry={r[1]:9.2f} Mz={r[2]:9.2f}")
    if "design" in res:
        if res.get("code", "EU") == "EU":
            print(f"\nEN 1993-1-1 member checks (factors {CF.tag('steel.gM0')}, {CF.tag('steel.gM1')})")
            print(f"{'member':<10}{'section':<18}{'L_cr,y [m]':>11}{'equiv. column':>15}{'2nd-order sect.':>17}")
        else:
            std = "SBC 306 (AISC based, LRFD, φc 0.85 [U])" if res["code"] == "SA" else "AISC 360-22"
            print(f"\n{std} member checks: effective-length method | direct analysis "
                  f"(0.8EI [{CF.status('aisc.dam_stiffness')}], 1/500 imperfection, K = 1 on the member)")
            print(f"{'member':<10}{'section':<18}{'L_c,x [m]':>11}{'eff. length':>15}{'direct anal.':>17}")
        worst = 0.0
        aisc_code = res.get("code", "EU") != "EU"
        for r in res["design"]:
            if aisc_code:   # both are AISC methods: ELM allowed only if α_cr ≥ 3 (App. 7); DAM always
                u = (min(r["util_equiv_column"], r["util_second_order_section"]) if res["alpha_cr"] >= 3
                     else r["util_second_order_section"])
                worst = max(worst, u)
            else:
                worst = max(worst, r["util_equiv_column"], r["util_second_order_section"])
            print(f"{r['member']:<10}{r['section']:<18}{r['Lcr_inplane']:11.2f}{r['util_equiv_column']:15.2f}"
                  f"{r['util_second_order_section']:17.2f}")
        if aisc_code:
            print("Governing = lower of the two AISC methods" + ("" if res["alpha_cr"] >= 3 else
                  " — α_cr < 3: effective-length method NOT permitted, direct analysis governs"))
        print(f"Governing utilisation {worst:.2f} -> {'OK' if worst <= 1 else 'NOT OK'}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", nargs="?", choices=["arch", "mast"])
    ap.add_argument("--input")
    ap.add_argument("--L", type=float, default=30.0)
    ap.add_argument("--f", type=float, default=6.0)
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--shape", choices=["parabolic", "circular"], default="parabolic")
    ap.add_argument("--section", default="CHS:323.9x10")
    ap.add_argument("--fy", type=float, default=355.0)
    ap.add_argument("--supports", choices=["pinned", "fixed"], default="pinned")
    ap.add_argument("--q", type=float, default=0.0, help="arch: load per horizontal metre, downward [kN/m]")
    ap.add_argument("--p-normal", type=float, default=0.0,
                    help="arch: FOLLOWER pressure normal to the arch, + toward the centre of curvature [kN/m] "
                         "(membrane/wind pressure that turns with the arch)")
    ap.add_argument("--H", type=float, default=12.0, help="mast height [m]")
    ap.add_argument("--D-base", type=float, default=219.1)
    ap.add_argument("--D-mid", type=float, default=219.1)
    ap.add_argument("--D-top", type=float, default=219.1)
    ap.add_argument("--t", type=float, default=8.0)
    ap.add_argument("--base", choices=["pinned", "fixed"], default="pinned")
    ap.add_argument("--N", type=float, default=0.0, help="mast head compression [kN]")
    ap.add_argument("--Hlat", type=float, default=0.0, help="mast head lateral load [kN]")
    ap.add_argument("--guy", action="append", default=[], help="guy 'dx:EA' (anchor offset m, EA kN)")
    ap.add_argument("--Lz", type=float, default=None, help="out-of-plane buckling length [m]")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--code", choices=CF.CODES, default=None, help="member design: EU (EN 1993-1-1) | US (AISC 360) | SA (SBC 306)")
    ap.add_argument("--method", choices=["LRFD", "ASD"], default="LRFD", help="US: LRFD or ASD (SA: LRFD only)")
    ap.add_argument("--factors", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    if a.input:
        with open(a.input) as fh:
            fr = from_json(json.load(fh))
    elif a.kind == "arch":
        fr = gen_arch(a.L, a.f, a.n, a.section, a.fy, a.supports, a.q, a.shape, p_normal=a.p_normal)
    elif a.kind == "mast":
        guys = [tuple(map(float, g.split(":"))) for g in a.guy]
        fr = gen_mast(a.H, a.n, a.D_base, a.D_mid, a.D_top, a.t, a.fy, a.base, a.N, a.Hlat, guys)
    else:
        ap.error("give arch | mast | --input")
    res = run(fr, a.check, Lz=a.Lz, code=CF.code(a.code), method=a.method)
    if a.out:
        with open(a.out + ".json", "w") as fh:
            json.dump({k: v for k, v in res.items() if k != "reactions"} | {"reactions": {str(k): v for k, v in res["reactions"].items()}},
                      fh, indent=1, default=float)
    return res


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
