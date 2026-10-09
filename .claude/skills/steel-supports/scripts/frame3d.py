#!/usr/bin/env python3
"""3D frame analysis for tensile-structure steelwork: masts + tie-backs + edge/stay cables, booms, frames.

Linear (first-order), elastic critical load factor α_cr and second-order (P-Δ/P-δ by geometric stiffness
iteration) analysis of space frames, with tension-only prestressed cables, pinned member ends and
EN 1993-1-1 imperfections; optional member checks through member_check.py. Pure Python (stdlib only).

Elements
  beam    12-DOF Euler–Bernoulli beam-column (N, Vy, Vz, T, My, Mz), consistent geometric stiffness
          (incl. torsional term N·Ip/(A·L)); members are subdivided (default div = 4) so that the
          member's own bow buckling is captured; end releases "pinned" (both bending rotations free),
          "pinned_y" / "pinned_z" (one bending rotation free) — torsion stays connected.
  truss   axial bar (tension and compression), string stiffness N/L.
  cable   tension-only bar with prestress T0 (or unstressed length L0); slack cables drop out.

Analyses (all run by default)
  1. first order: K_E (+ string stiffness N/L of cables, needed for cable-only nodes) with cable status iteration
  2. α_cr: smallest positive α with det(K_E + α·K_G(N)) = 0, by Sturm-sequence bisection (LDLᵀ inertia)
     + shifted inverse iteration; EN 1993-1-1 5.2.1(3): first-order analysis adequate if α_cr ≥ 10
  3. second order: (K_E + K_G(N)) u = F iterated to convergence of N and cable status, on a geometry with an
     imperfection: --imp unique (EN 1993-1-1 5.3.2(11), default), sway (φ0·h, 5.3.2(3) with αh = αm = 1),
     mm:<amplitude> (buckling-mode shape scaled to the amplitude) or none.

Membrane reactions
  The shared model JSON (model-schema.md) writes reactions[].pull = force FROM the membrane ON the support.
  `--reactions model.json --map 0:5,12:9` applies pull of membrane node 0 to frame node 5 ...; without --map,
  each reaction is attached to the frame node within --match-tol of the membrane node's xyz.
  --reaction-factor scales them (e.g. 1.0 if the membrane run already used factored loads).

Input JSON (see reference/steel-support-design.md §13), z vertical, kN and m:
  {"nodes": [[x,y,z], ...], "supports": {"0": "pinned" | "fixed" | [ux,uy,uz,rx,ry,rz]},
   "members": [{"name": "MAST", "nodes": [0, 1], "section": "CHS:219.1x8", "fy": 355, "div": 6,
                "release_start": "pinned", "ref": [1, 0, 0], "Lcr_y": 8.0, "Lcr_z": 8.0},
               {"name": "TIE1", "nodes": [1, 2], "type": "cable", "EA": 30000, "prestress": 15}],
   "loads": {"nodal": {"1": [Fx, Fy, Fz, Mx, My, Mz]}, "udl": [{"member": "B", "q": [qx, qy, qz]}]},
   "reactions": {"file": "sail.json", "map": {"0": 1}, "factor": 1.0}}

Examples
  python3 frame3d.py mast --H 8 --section CHS:219.1x8 --base pinned --tie=-5,0,0:25000:10 \\
        --tie 2.5,4.33,0:25000:10 --tie 2.5,-4.33,0:25000:10 --load 12,4,-3 --check
  python3 frame3d.py mast --H 6 --section CHS:168.3x8 --tie=-5,0,0:20000:5 --tie 3,4,0:20000:5 \\
        --tie 3,-4,0:20000:5 --reactions sail.json --node 0 --check
  python3 frame3d.py --input frame3d.json --check --out results
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

RELEASES = {"fixed": (), "pinned": (4, 5), "pinned_y": (4,), "pinned_z": (5,)}  # local dof index at an end


# ------------------------------------------------------------ small vector helpers
def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    return [a[0] / n, a[1] / n, a[2] / n]


# ------------------------------------------------------------ banded symmetric LDLᵀ
class Band:
    """symmetric banded matrix, upper band stored: a[i][k] = A[i][i+k], k = 0..bw."""

    def __init__(self, n, bw):
        self.n, self.bw = n, bw
        self.a = [[0.0] * (bw + 1) for _ in range(n)]

    def add(self, i, j, v):
        if j < i:
            i, j = j, i
        self.a[i][j - i] += v

    def copy_scaled_sum(self, other, s):
        """new Band = self + s·other."""
        out = Band(self.n, self.bw)
        out.a = [[x + s * y for x, y in zip(r1, r2)] for r1, r2 in zip(self.a, other.a)]
        return out

    def matvec(self, x):
        n, bw, a = self.n, self.bw, self.a
        y = [0.0] * n
        for i in range(n):
            row = a[i]
            s = row[0] * x[i]
            xi = x[i]
            for k in range(1, min(bw, n - 1 - i) + 1):
                v = row[k]
                if v:
                    s += v * x[i + k]
                    y[i + k] += v * xi
            y[i] += s
        return y

    def ldl(self):
        """in-place LDLᵀ (no pivoting); returns number of negative pivots (Sturm count)."""
        n, bw, a = self.n, self.bw, self.a
        neg = 0
        self.weak = []
        for i in range(n):
            ri = a[i]
            d = ri[0]
            if 0 < d < 1e3 * getattr(self, "spring", 0.0):
                self.weak.append(i)
            if d == 0.0:
                d = ri[0] = 1e-300
            if d < 0:
                neg += 1
            top = min(bw, n - 1 - i)
            for k in range(1, top + 1):
                v = ri[k]
                if v == 0.0:
                    continue
                lk = v / d
                rj = a[i + k]
                # row j = i+k, columns j..i+top  ->  rj[m - k] for m = k..top
                for m in range(k, top + 1):
                    w = ri[m]
                    if w:
                        rj[m - k] -= lk * w
                ri[k] = lk
        self.neg = neg
        return neg

    def solve(self, b):
        n, bw, a = self.n, self.bw, self.a
        y = list(b)
        for i in range(n):
            yi = y[i]
            if yi:
                row = a[i]
                for k in range(1, min(bw, n - 1 - i) + 1):
                    if row[k]:
                        y[i + k] -= row[k] * yi
        for i in range(n):
            y[i] /= a[i][0]
        for i in range(n - 1, -1, -1):
            row = a[i]
            s = y[i]
            for k in range(1, min(bw, n - 1 - i) + 1):
                if row[k]:
                    s -= row[k] * y[i + k]
            y[i] = s
        return y


# ------------------------------------------------------------ element matrices (local)
def beam_ke(E, G, A, Iy, Iz, J, L):
    k = [[0.0] * 12 for _ in range(12)]

    def s(i, j, v):
        k[i][j] = k[j][i] = v
    ea, gj = E * A / L, G * J / L
    s(0, 0, ea); s(6, 6, ea); s(0, 6, -ea)
    s(3, 3, gj); s(9, 9, gj); s(3, 9, -gj)
    # bending in x-y plane (v, θz) with Iz
    a, b, c, d = 12 * E * Iz / L ** 3, 6 * E * Iz / L ** 2, 4 * E * Iz / L, 2 * E * Iz / L
    s(1, 1, a); s(1, 5, b); s(1, 7, -a); s(1, 11, b)
    s(5, 5, c); s(5, 7, -b); s(5, 11, d)
    s(7, 7, a); s(7, 11, -b); s(11, 11, c)
    # bending in x-z plane (w, θy) with Iy  (θy = −dw/dx)
    a, b, c, d = 12 * E * Iy / L ** 3, 6 * E * Iy / L ** 2, 4 * E * Iy / L, 2 * E * Iy / L
    s(2, 2, a); s(2, 4, -b); s(2, 8, -a); s(2, 10, -b)
    s(4, 4, c); s(4, 8, b); s(4, 10, d)
    s(8, 8, a); s(8, 10, b); s(10, 10, c)
    return k


def beam_kg(N, L, Ip_over_A=None):
    """consistent geometric stiffness, N > 0 tension. The torsional term N·Ip/(A·L) is only added when
    Ip_over_A is given (off by default: free member torsion would show up as a spurious zero-load mode)."""
    k = [[0.0] * 12 for _ in range(12)]

    def s(i, j, v):
        k[i][j] = k[j][i] = v
    f = N / (30 * L)
    s(1, 1, 36 * f); s(1, 5, 3 * L * f); s(1, 7, -36 * f); s(1, 11, 3 * L * f)
    s(5, 5, 4 * L * L * f); s(5, 7, -3 * L * f); s(5, 11, -L * L * f)
    s(7, 7, 36 * f); s(7, 11, -3 * L * f); s(11, 11, 4 * L * L * f)
    s(2, 2, 36 * f); s(2, 4, -3 * L * f); s(2, 8, -36 * f); s(2, 10, -3 * L * f)
    s(4, 4, 4 * L * L * f); s(4, 8, 3 * L * f); s(4, 10, -L * L * f)
    s(8, 8, 36 * f); s(8, 10, 3 * L * f); s(10, 10, 4 * L * L * f)
    if Ip_over_A:
        t = N * Ip_over_A / L
        s(3, 3, t); s(9, 9, t); s(3, 9, -t)
    return k


def bar_k(EA, N, L):
    """axial bar in local coordinates (12x12, translations only): EA/L axial + N/L string stiffness."""
    k = [[0.0] * 12 for _ in range(12)]
    ea = EA / L
    for (i, j) in ((0, 0), (6, 6)):
        k[i][j] += ea
    k[0][6] -= ea
    k[6][0] -= ea
    g = N / L
    for d in (1, 2):
        k[d][d] += g
        k[d + 6][d + 6] += g
        k[d][d + 6] -= g
        k[d + 6][d] -= g
    return k


# ------------------------------------------------------------ model
class Model:
    def __init__(self):
        self.nodes = []          # [x, y, z]
        self.supports = {}       # node -> 6 flags
        self.members = {}        # name -> dict
        self.elems = []          # dicts
        self.nodal = {}          # node -> 6 loads
        self.udl = []            # (elem index, [qx, qy, qz]) global per unit length
        self.notes = []
        self.cable_string_first = True   # include N/L of cables in the first-order run (needed for cable-only nodes)

    # --- building
    def add_node(self, xyz):
        self.nodes.append([float(v) for v in xyz])
        return len(self.nodes) - 1

    def add_member(self, name, node_ids, kind="beam", section=None, fy=355.0, div=None, ref=None,
                   release_start="fixed", release_end="fixed", A=None, Iy=None, Iz=None, J=None, E=None, G=None,
                   EA=None, prestress=0.0, L0=None, Lcr_y=None, Lcr_z=None, Lb=None, cold=False):
        E = E if E is not None else CF.get("steel.E") * 1e3          # kN/m2
        G = G if G is not None else CF.get("steel.G") * 1e3
        sec = None
        if kind == "beam":
            if section:
                sec = MC.Section(section, cold)
                A, Iy, Iz, J = sec.A * 1e-6, sec.Iy * 1e-12, sec.Iz * 1e-12, sec.It * 1e-12
            if None in (A, Iy, Iz, J):
                raise SystemExit(f"member {name}: give a section or A, Iy, Iz, J")
            div = 4 if div is None else int(div)
        else:
            if EA is None:
                if section:
                    sec = MC.Section(section, cold)
                    A = sec.A * 1e-6
                if A is None:
                    raise SystemExit(f"member {name}: give EA [kN] or A [m2]")
                EA = E * A
            div = 1 if div is None else int(div)
        m = {"name": name, "kind": kind, "section": section, "sec": sec, "fy": fy, "elems": [], "nodes": list(node_ids),
             "Lcr_y": Lcr_y, "Lcr_z": Lcr_z, "Lb": Lb}
        self.members[name] = m
        chain = [node_ids[0]]
        for a, b in zip(node_ids[:-1], node_ids[1:]):
            pa, pb = self.nodes[a], self.nodes[b]
            for k in range(1, div):
                t = k / div
                chain.append(self.add_node([pa[i] + t * (pb[i] - pa[i]) for i in range(3)]))
            chain.append(b)
        L_total = sum(norm(sub(self.nodes[b], self.nodes[a])) for a, b in zip(chain[:-1], chain[1:]))
        for idx, (a, b) in enumerate(zip(chain[:-1], chain[1:])):
            e = {"n": (a, b), "kind": kind, "member": name, "E": E, "G": G, "A": A, "Iy": Iy, "Iz": Iz, "J": J,
                 "EA": EA, "ref": ref, "rel": (tuple(RELEASES[release_start]) if idx == 0 else (),
                                               tuple(RELEASES[release_end]) if idx == len(chain) - 2 else ())}
            if kind == "cable":
                L = norm(sub(self.nodes[b], self.nodes[a]))
                if L0 is not None:   # unstressed length given for the whole member: same strain in each segment
                    T0 = EA * (L_total - L0) / L0
                else:
                    T0 = prestress
                e["T0"] = T0
            else:
                e["T0"] = prestress if kind == "truss" else 0.0
            self.elems.append(e)
            m["elems"].append(len(self.elems) - 1)
        m["L"] = L_total
        return m

    # --- geometry
    def frame_of(self, e, nodes=None):
        nodes = nodes or self.nodes
        a, b = e["n"]
        d = sub(nodes[b], nodes[a])
        L = norm(d)
        x = [v / L for v in d]
        ref = e["ref"] or ([0.0, 0.0, 1.0] if abs(x[2]) < 0.999 else [1.0, 0.0, 0.0])
        z = sub(ref, [dot(ref, x) * v for v in x])
        if norm(z) < 1e-9:
            raise SystemExit(f"member {e['member']}: reference vector parallel to the member")
        z = unit(z)
        y = cross(z, x)
        return L, [x, y, z]

    # --- DOF numbering with reverse Cuthill–McKee node order
    def numbering(self):
        nn = len(self.nodes)
        adj = [set() for _ in range(nn)]
        rot = [False] * nn
        for e in self.elems:
            a, b = e["n"]
            adj[a].add(b)
            adj[b].add(a)
            if e["kind"] == "beam":
                for end, node in ((0, a), (1, b)):
                    rot[node] = True     # torsion (at least) is always connected
        order, seen = [], [False] * nn
        for start in sorted(range(nn), key=lambda i: len(adj[i])):
            if seen[start]:
                continue
            seen[start] = True
            q = [start]
            while q:
                v = q.pop(0)
                order.append(v)
                for w in sorted(adj[v], key=lambda i: len(adj[i])):
                    if not seen[w]:
                        seen[w] = True
                        q.append(w)
        order.reverse()
        hinge_at = {}
        for ei, e in enumerate(self.elems):
            for end in (0, 1):
                for d in e["rel"][end]:
                    hinge_at.setdefault(e["n"][end], []).append((ei, end, d))
        dof, n = {}, 0
        hinge = {}
        for v in order:
            sup = self.supports.get(v, (0,) * 6)
            for d in range(6):
                if d >= 3 and not rot[v]:
                    continue                      # node without rotational connection: rotations removed
                if not sup[d]:
                    dof[(v, d)] = n
                    n += 1
            for (ei, end, d) in hinge_at.get(v, []):
                hinge[(ei, end, d)] = n
                n += 1
        self.dof, self.hinge, self.ndof, self.rot = dof, hinge, n, rot
        return n

    def elem_map(self, ei, T):
        """rows: local dof -> {global index: coeff}; T = [x, y, z] local axes."""
        e = self.elems[ei]
        rows = []
        for end, node in enumerate(e["n"]):
            for blk in (0, 1):
                for li in range(3):
                    ld = blk * 3 + li
                    if blk == 1 and ld in e["rel"][end]:
                        rows.append({self.hinge[(ei, end, ld)]: 1.0})
                        continue
                    r = {}
                    for g in range(3):
                        gi = self.dof.get((node, blk * 3 + g))
                        if gi is not None and T[li][g]:
                            r[gi] = T[li][g]
                    rows.append(r)
        return rows

    # --- assembly
    def element_matrix(self, e, L, Nax, with_geo=True, geo_scale=1.0, geo_only=False):
        if e["kind"] == "beam":
            k = [[0.0] * 12 for _ in range(12)] if geo_only else beam_ke(e["E"], e["G"], e["A"], e["Iy"], e["Iz"], e["J"], L)
            if with_geo and Nax:
                g = beam_kg(Nax, L)
                k = [[k[i][j] + geo_scale * g[i][j] for j in range(12)] for i in range(12)]
            return k
        EA = 0.0 if geo_only else e["EA"]
        return bar_k(EA, (geo_scale * Nax) if with_geo else 0.0, L)

    def assemble(self, Nax, active, beam_geo=True, cable_geo=True, geo_only=False, nodes=None):
        nodes = nodes or self.nodes
        maps = []
        bw = 1
        for ei, e in enumerate(self.elems):
            L, T = self.frame_of(e, nodes)
            rows = self.elem_map(ei, T)
            idx = [g for r in rows for g in r]
            if idx:
                bw = max(bw, max(idx) - min(idx))
            maps.append((L, rows))
        K = Band(self.ndof, bw)
        for ei, e in enumerate(self.elems):
            if not active[ei]:
                continue
            L, rows = maps[ei]
            geo = beam_geo if e["kind"] == "beam" else cable_geo
            k = self.element_matrix(e, L, Nax[ei], with_geo=geo, geo_only=geo_only)
            nz = [(i, r) for i, r in enumerate(rows) if r]
            for i, ri in nz:
                ki = k[i]
                for j, rj in nz:
                    kij = ki[j]
                    if kij == 0.0:
                        continue
                    for gi, ci in ri.items():
                        for gj, cj in rj.items():
                            if gj >= gi:
                                K.add(gi, gj, ci * kij * cj)
        if not geo_only:   # tiny rotational spring on free nodal rotations (removes torsion-only singularities)
            kmax = max((K.a[i][0] for i in range(self.ndof)), default=1.0)
            K.spring = 1e-12 * kmax
            for (v, d), gi in self.dof.items():
                if d >= 3:
                    K.a[gi][0] += K.spring
        self._maps = maps
        return K

    def load_vector(self, Nax_init, active, nodes=None):
        """external nodal loads + equivalent loads of UDLs + initial forces of prestressed cables/bars."""
        nodes = nodes or self.nodes
        F = [0.0] * self.ndof
        for node, f in self.nodal.items():
            for d in range(6):
                gi = self.dof.get((node, d))
                if gi is not None:
                    F[gi] += f[d]
        for ei, e in enumerate(self.elems):
            L, T = self.frame_of(e, nodes)
            rows = self.elem_map(ei, T)
            fl = self.fixed_end(ei, L, T)
            if e["kind"] != "beam" and active[ei] and e["T0"]:
                # a tensioned bar pulls its end nodes towards each other
                fl = [0.0] * 12
                fl[0], fl[6] = e["T0"], -e["T0"]
            for i, r in enumerate(rows):
                if fl[i]:
                    for gi, c in r.items():
                        F[gi] += c * fl[i]
        return F

    def fixed_end(self, ei, L, T):
        fl = [0.0] * 12
        for (eu, q) in self.udl:
            if eu != ei:
                continue
            qx, qy, qz = (dot(T[i], q) for i in range(3))
            fl[0] += qx * L / 2
            fl[6] += qx * L / 2
            fl[1] += qy * L / 2
            fl[7] += qy * L / 2
            fl[5] += qy * L * L / 12
            fl[11] -= qy * L * L / 12
            fl[2] += qz * L / 2
            fl[8] += qz * L / 2
            fl[4] -= qz * L * L / 12
            fl[10] += qz * L * L / 12
        return fl

    def end_forces(self, u, Nax, active, beam_geo, nodes=None, loads=True, bar_geo=True):
        """local end forces on each element (12 values) and axial force N (tension +).
        loads=False: response to u only (no member loads, no prestress) — used for buckling-mode moments."""
        nodes = nodes or self.nodes
        out = []
        for ei, e in enumerate(self.elems):
            L, T = self.frame_of(e, nodes)
            if not active[ei]:
                out.append({"f": [0.0] * 12, "N": 0.0, "L": L})
                continue
            rows = self.elem_map(ei, T)
            ul = [sum(c * u[gi] for gi, c in r.items()) for r in rows]
            if e["kind"] == "beam":
                k = self.element_matrix(e, L, Nax[ei], with_geo=beam_geo)
                fe = self.fixed_end(ei, L, T) if loads else [0.0] * 12
                f = [sum(k[i][j] * ul[j] for j in range(12)) - fe[i] for i in range(12)]
                N = f[6]
            else:
                N = (e["T0"] if loads else 0.0) + e["EA"] / L * (ul[6] - ul[0])
                f = [0.0] * 12
                f[0], f[6] = -N, N
                # string forces of the transverse displacement (equilibrium of the deflected bar)
                for d in (1, 2) if bar_geo else ():
                    f[d] = N / L * (ul[d] - ul[d + 6])
                    f[d + 6] = -f[d]
            out.append({"f": f, "N": N, "L": L, "ul": ul})
        return out

    # --- analyses
    def solve_state(self, second_order, nodes=None, maxit=60, tol=1e-7):
        """iterate cable status (and N for second order). Returns u, forces, active, converged."""
        nodes = nodes or self.nodes
        active = [True] * len(self.elems)
        Nax = [e["T0"] if e["kind"] != "beam" else 0.0 for e in self.elems]
        u, forces, ok = None, None, False
        for it in range(maxit):
            K = self.assemble(Nax, active, beam_geo=second_order,
                              cable_geo=second_order or self.cable_string_first, nodes=nodes)
            K.ldl()
            if K.weak and it == 0:
                inv = {gi: key for key, gi in self.dof.items()}
                names = ("ux", "uy", "uz", "rx", "ry", "rz")
                where = ", ".join(f"node {inv[g][0]} {names[inv[g][1]]}" if g in inv else f"hinge dof {g}"
                                  for g in K.weak[:6])
                msg = (f"near-mechanism: stiffness only from the tiny stabilising spring at {where}"
                       " (free member torsion or an unrestrained rotation?) — add a restraint")
                if msg not in self.notes:
                    self.notes.append(msg)
            F = self.load_vector(Nax, active, nodes)
            u = K.solve(F)
            forces = self.end_forces(u, Nax, active, second_order, nodes,
                                     bar_geo=second_order or self.cable_string_first)
            new_active = []
            for ei, e in enumerate(self.elems):
                if e["kind"] != "cable":
                    new_active.append(True)
                    continue
                if active[ei]:
                    new_active.append(forces[ei]["N"] > 0.0)
                else:   # trial: would it be in tension at the current displacements?
                    L, T = self.frame_of(e, nodes)
                    rows = self.elem_map(ei, T)
                    ul = [sum(c * u[gi] for gi, c in r.items()) for r in rows]
                    new_active.append(e["T0"] + e["EA"] / L * (ul[6] - ul[0]) > 0.0)
            newN = [f["N"] for f in forces]
            dN = max((abs(a - b) for a, b in zip(newN, Nax)), default=0.0)
            scale = max((abs(x) for x in newN), default=1.0) or 1.0
            changed = new_active != active
            active = new_active
            Nax = [n if a else 0.0 for n, a in zip(newN, active)]
            if not changed and dN <= tol * scale:
                ok = True
                break
        if not ok:
            self.notes.append("state iteration did not fully converge (cable status / N); check results")
        for ei, a in enumerate(active):
            if not a:
                forces[ei]["N"] = 0.0
        return u, forces, active, ok

    def buckling(self, forces, active, nodes=None, lam_max=1e6):
        """smallest positive α with K_E + α K_G(N) singular: Sturm bisection + shifted inverse iteration."""
        nodes = nodes or self.nodes
        Nax = [f["N"] for f in forces]
        KE = self.assemble(Nax, active, beam_geo=False, cable_geo=False, nodes=nodes)
        KG = self.assemble(Nax, active, beam_geo=True, cable_geo=True, geo_only=True, nodes=nodes)

        def count(lam):
            M = KE.copy_scaled_sum(KG, lam)
            return M.ldl()

        lo, hi = 0.0, 1.0
        while count(hi) == 0:
            lo, hi = hi, hi * 2.0
            if hi > lam_max:
                return math.inf, None
        while hi - lo > 1e-4 * hi:
            mid = 0.5 * (lo + hi)
            if count(mid) == 0:
                lo = mid
            else:
                hi = mid
        sigma = lo if lo > 0 else 0.5 * hi
        M = KE.copy_scaled_sum(KG, sigma)
        M.ldl()
        x = [1.0 + 0.1 * math.sin(1.7 * i) for i in range(self.ndof)]
        lam = hi
        for _ in range(200):
            y = M.solve([-v for v in KG.matvec(x)])
            ny = math.sqrt(sum(v * v for v in y)) or 1e-300
            x = [v / ny for v in y]
            kx, gx = KE.matvec(x), KG.matvec(x)
            den = -sum(a * b for a, b in zip(x, gx))
            lam_new = sum(a * b for a, b in zip(x, kx)) / den if den else lam
            if abs(lam_new - lam) <= 1e-10 * abs(lam_new):
                lam = lam_new
                break
            lam = lam_new
        if not (lo * 0.999 <= lam <= hi * 1.001):    # inverse iteration drifted: keep the bisection value
            lam = 0.5 * (lo + hi)
        return lam, x

    def mode_translations(self, x):
        t = {}
        for (v, d), gi in self.dof.items():
            if d < 3:
                t.setdefault(v, [0.0, 0.0, 0.0])[d] = x[gi]
        return t

    def reactions(self, forces, active, nodes=None):
        nodes = nodes or self.nodes
        R = {v: [0.0] * 6 for v in self.supports}
        for ei, e in enumerate(self.elems):
            if not active[ei]:
                continue
            L, T = self.frame_of(e, nodes)
            f = forces[ei]["f"]
            for end, node in enumerate(e["n"]):
                if node not in R:
                    continue
                for blk in (0, 1):
                    loc = f[end * 6 + blk * 3: end * 6 + blk * 3 + 3]
                    for g in range(3):
                        R[node][blk * 3 + g] += sum(T[li][g] * loc[li] for li in range(3))
        for v in R:
            for d in range(6):
                R[v][d] -= self.nodal.get(v, [0.0] * 6)[d]
                if not self.supports[v][d]:
                    R[v][d] = 0.0
        return R


# ------------------------------------------------------------ results per member
def member_summary(model, forces, active):
    out = {}
    for name, m in model.members.items():
        fs = [forces[i] for i in m["elems"]]
        if m["kind"] == "beam":
            f = [x["f"] for x in fs]
            out[name] = {"kind": "beam", "N_min": min(x["N"] for x in fs), "N_max": max(x["N"] for x in fs),
                         "Vy": max(max(abs(v[1]), abs(v[7])) for v in f), "Vz": max(max(abs(v[2]), abs(v[8])) for v in f),
                         "T": max(abs(v[9]) for v in f),
                         "My": max(max(abs(v[4]), abs(v[10])) for v in f), "Mz": max(max(abs(v[5]), abs(v[11])) for v in f),
                         "L": m["L"]}
        else:
            out[name] = {"kind": m["kind"], "N_min": min(x["N"] for x in fs), "N_max": max(x["N"] for x in fs),
                         "slack": not all(active[i] for i in m["elems"]), "L": m["L"]}
    return out


def unique_imperfection(model, forces, active, lam, x):
    """EN 1993-1-1 5.3.2(11): η_init = e0·N_cr/(EI·η''_cr,max)·η_cr, e0 from eq. (5.10). Returns (offsets, info)."""
    gM1 = CF.get("steel.gM1")
    crit, best = None, -1.0
    for ei, e in enumerate(model.elems):
        m = model.members[e["member"]]
        if e["kind"] != "beam" or m["sec"] is None or forces[ei]["N"] >= 0:
            continue
        r = -forces[ei]["N"] * 1e3 / (m["sec"].A * m["fy"])
        if r > best * (1 + 1e-9):
            best, crit = r, [ei]
        elif abs(r - best) <= 1e-9 * best:
            crit.append(ei)
    if crit is None or x is None or not math.isfinite(lam):
        return None, None
    # bending moment of the mode at the critical section: EI·η'' = k_E·u_mode (local end moments)
    mode_f = model.end_forces(x, [0.0] * len(model.elems), active, False, loads=False)
    best_m, ce, axis = -1.0, crit[0], "y"
    for ei in crit:
        f = mode_f[ei]["f"]
        for my, mz in ((f[4], f[5]), (f[10], f[11])):
            mm = math.hypot(my, mz)
            if mm > best_m:
                best_m, ce, axis = mm, ei, ("y" if abs(my) >= abs(mz) else "z")
    m = model.members[model.elems[ce]["member"]]
    sec, fy = m["sec"], m["fy"]
    NEd = -forces[ce]["N"]
    NRk = sec.A * fy * 1e-3                                  # kN
    cls, _ = MC.section_class(sec, fy, NEd)
    if cls <= 2:
        W = sec.Wpl_y if axis == "y" else sec.Wpl_z
    else:
        W = sec.Wel_y if axis == "y" else sec.Wel_z
    MRk = W * fy * 1e-6                                      # kNm
    curve = sec.curves(fy)[0 if axis == "y" else 1]
    al = MC.alpha_of(curve)
    a_ult = NRk / NEd
    lam_bar = math.sqrt(a_ult / lam)
    chi = MC.chi(lam_bar, al)
    if lam_bar <= 0.2:
        e0 = 0.0
    else:
        e0 = al * (lam_bar - 0.2) * MRk / NRk * (1 - chi * lam_bar ** 2 / gM1) / (1 - chi * lam_bar ** 2)
    Ncr = lam * NEd
    s = e0 * Ncr / best_m if best_m > 0 else 0.0
    t = model.mode_translations(x)
    offs = {v: [s * c for c in d] for v, d in t.items()}
    amp = max((norm(d) for d in offs.values()), default=0.0)
    return offs, {"method": "unique (EN 1993-1-1 5.3.2(11))", "critical_member": m["name"], "curve": curve,
                  "lambda_bar_global": lam_bar, "chi": chi, "e0_m": e0, "amplitude_m": amp}


def scaled_mode(model, x, amp):
    t = model.mode_translations(x)
    mx = max((norm(d) for d in t.values()), default=0.0) or 1.0
    return {v: [amp * c / mx for c in d] for v, d in t.items()}


def design(model, s1, s2, lam, imp_info):
    rows = []
    E = CF.get("steel.E")
    gM0 = CF.get("steel.gM0")
    for name, m in model.members.items():
        if m["kind"] != "beam" or m["sec"] is None:
            continue
        sec, fy, L = m["sec"], m["fy"], m["L"]
        a, b = s1[name], s2[name]
        NEd1, NEd2 = max(-a["N_min"], 0.0), max(-b["N_min"], 0.0)
        # (a) equivalent column: first-order forces, L_cr from α_cr (conservative for both axes) or user values
        if NEd1 > 0 and math.isfinite(lam):
            Ncr = lam * NEd1 * 1e3
            Lcy = m["Lcr_y"] or math.pi * math.sqrt(E * sec.Iy / Ncr) / 1000
            Lcz = m["Lcr_z"] or math.pi * math.sqrt(E * sec.Iz / Ncr) / 1000
        else:
            Lcy, Lcz = m["Lcr_y"] or L, m["Lcr_z"] or L
        kLT = (m["Lb"] / L) if m["Lb"] else 1.0
        r1, res1 = MC.check(sec, fy, L, NEd1, a["My"], a["Mz"], a["Vy"], a["Vz"], ky=Lcy / L, kz=Lcz / L, kLT=kLT)
        u1 = max(d / c for _, d, c, _ in r1)
        # (b) second-order + imperfection: cross-section check (6.2.9) with second-order forces
        r2, res2 = MC.check(sec, fy, L, NEd2 if NEd2 > 0 else b["N_max"] * -1.0 if b["N_max"] > 0 else 0.0,
                            b["My"], b["Mz"], b["Vy"], b["Vz"], ky=1.0, kz=1.0, kLT=kLT)
        u2 = max(d / c for nm, d, c, _ in r2 if nm.startswith("section") or nm.startswith("shear")
                 or nm.startswith("tension"))
        rows.append({"member": name, "section": m["section"], "class": res1["class"], "N_Ed": NEd1,
                     "My1": a["My"], "Mz1": a["Mz"], "My2": b["My"], "Mz2": b["Mz"], "T": b["T"],
                     "Lcr_y": Lcy, "Lcr_z": Lcz, "util_equiv_column": u1, "util_second_order_section": u2})
    return rows


ASSUMPTIONS = """Assumptions / model limits (frame3d):
  - Linear elastic, small displacements; second order = geometric stiffness (P-Δ/P-δ) iterated on the
    imperfect geometry (no large-rotation update, no cable sag: straight cables, no Ernst modulus).
  - Euler–Bernoulli beams (no shear deformation), St Venant torsion only (no warping torsion). Geometric
    stiffness acts on bending only: torsional and lateral-torsional buckling are NOT in α_cr — LTB is checked
    per member by member_check.py (k = 1 between member end nodes unless Lb is given).
  - Cables: tension-only straight bars, prestress T0 in the given geometry (or from L0), string stiffness N/L
    always included (also in the 'first-order' run). Slack cables carry nothing.
  - α_cr: total load including prestress scaled by α (as in common FE software); members subdivided (div).
  - Releases free the two bending rotations at a member end; torsion stays connected. Supports are rigid.
  - Loads are design values of ONE combination (non-linear: run each combination; never superpose)."""


def run(model, imp="unique", check=False, quiet=False):
    model.numbering()
    u1, f1, act1, ok1 = model.solve_state(False)
    lam, x = model.buckling(f1, act1)
    s1 = member_summary(model, f1, act1)
    offs, info = None, {"method": "none"}
    if imp and imp != "none" and x is not None:
        if imp == "unique":
            offs, info = unique_imperfection(model, f1, act1, lam, x)
            if offs is None:
                info = {"method": "none (no compressed member with a section)"}
        elif imp == "sway":
            zs = [p[2] for p in model.nodes]
            h = max(zs) - min(zs)
            amp = CF.get("steel.phi0") * h
            offs = scaled_mode(model, x, amp)
            info = {"method": "sway φ0·h along the buckling mode (EN 1993-1-1 5.3.2(3), αh = αm = 1)",
                    "amplitude_m": amp}
        elif imp.startswith("mm:"):
            amp = float(imp[3:]) / 1000
            offs = scaled_mode(model, x, amp)
            info = {"method": "buckling-mode shape, user amplitude", "amplitude_m": amp}
    nodes2 = [list(p) for p in model.nodes]
    if offs:
        for v, d in offs.items():
            for i in range(3):
                nodes2[v][i] += d[i]
    u2, f2, act2, ok2 = model.solve_state(True, nodes=nodes2)
    s2 = member_summary(model, f2, act2)
    R1 = model.reactions(f1, act1)
    R2 = model.reactions(f2, act2, nodes2)
    disp = {}
    for (v, d), gi in model.dof.items():
        if d < 3:
            disp.setdefault(v, [0.0] * 3)[d] = u2[gi]
    disp1 = {}
    for (v, d), gi in model.dof.items():
        if d < 3:
            disp1.setdefault(v, [0.0] * 3)[d] = u1[gi]
    res = {"alpha_cr": lam, "first_order": s1, "second_order": s2, "reactions_first": R1, "reactions_second": R2,
           "imperfection": info, "disp_first": disp1, "disp_second": disp,
           "max_disp_first_m": max((norm(d) for d in disp1.values()), default=0.0),
           "max_disp_second_m": max((norm(d) for d in disp.values()), default=0.0),
           "converged": ok1 and ok2, "notes": list(model.notes), "u_first": u1, "u_second": u2}
    if check:
        res["design"] = design(model, s1, s2, lam, info)
    if not quiet:
        report(model, res)
    return res


def report(model, res):
    print(ASSUMPTIONS)
    a = res["alpha_cr"]
    lim = CF.get("steel.alpha_cr_min_elastic")
    print(f"\nElastic critical load factor α_cr = {a:.3f}  " +
          (f"(≥ {lim:g}: first-order analysis adequate, EN 1993-1-1 5.2.1(3))" if a >= lim else
           f"(< {lim:g}: second-order effects must be included, 5.2.1(3))") + f"  [{CF.tag('steel.alpha_cr_min_elastic')}]")
    imp = res["imperfection"]
    print("Imperfection: " + imp["method"] + (f", amplitude {imp['amplitude_m'] * 1000:.1f} mm" if "amplitude_m" in imp else "")
          + (f" (critical member {imp['critical_member']}, curve {imp['curve']}, λ̄={imp['lambda_bar_global']:.2f}, "
             f"e0={imp['e0_m'] * 1000:.1f} mm)" if "critical_member" in imp else ""))
    print(f"Max displacement: first order {res['max_disp_first_m'] * 1000:.1f} mm, second order "
          f"{res['max_disp_second_m'] * 1000:.1f} mm")
    print(f"\n{'member':<10}{'kind':<6}{'N_min':>9}{'N_max':>9}{'My 1st':>9}{'My 2nd':>9}{'Mz 1st':>9}{'Mz 2nd':>9}"
          f"{'T':>7}  [kN, kNm]")
    for name, a1 in res["first_order"].items():
        a2 = res["second_order"][name]
        if a1["kind"] == "beam":
            print(f"{name:<10}{'beam':<6}{a2['N_min']:9.1f}{a2['N_max']:9.1f}{a1['My']:9.2f}{a2['My']:9.2f}"
                  f"{a1['Mz']:9.2f}{a2['Mz']:9.2f}{a2['T']:7.2f}")
        else:
            print(f"{name:<10}{a1['kind']:<6}{a2['N_min']:9.1f}{a2['N_max']:9.1f}" +
                  ("   SLACK (tension-only, dropped out)" if a2.get("slack") else ""))
    print("\nReactions, second order [kN, kNm] (force from support on structure):")
    for node, r in res["reactions_second"].items():
        print(f"  node {node:>3}: " + " ".join(f"{k}={v:9.2f}" for k, v in zip(("Rx", "Ry", "Rz", "Mx", "My", "Mz"), r)))
    for n in res["notes"]:
        print("NOTE:", n)
    if "design" in res:
        print(f"\nEN 1993-1-1 member checks ({CF.tag('steel.gM0')}, {CF.tag('steel.gM1')})")
        print(f"{'member':<10}{'section':<18}{'cl':>3}{'L_cr,y':>8}{'L_cr,z':>8}{'equiv.col':>11}{'2nd-ord sect':>14}")
        worst = 0.0
        for r in res["design"]:
            worst = max(worst, r["util_equiv_column"], r["util_second_order_section"])
            print(f"{r['member']:<10}{r['section']:<18}{r['class']:>3}{r['Lcr_y']:8.2f}{r['Lcr_z']:8.2f}"
                  f"{r['util_equiv_column']:11.2f}{r['util_second_order_section']:14.2f}")
        print(f"Governing utilisation {worst:.2f} -> {'OK' if worst <= 1 else 'NOT OK'}")
        print("  equiv. column: first-order N, M with L_cr = π√(EI/(α_cr·N_Ed)) about both axes (conservative) + LTB;")
        print("  2nd-order section: 6.2.9 check with second-order forces on the imperfect geometry (torsion not checked).")


# ------------------------------------------------------------ input
SUPPORT_WORDS = {"pinned": [1, 1, 1, 0, 0, 0], "fixed": [1, 1, 1, 1, 1, 1], "roller_z": [0, 0, 1, 0, 0, 0]}


def support_flags(v):
    if isinstance(v, str):
        return tuple(SUPPORT_WORDS[v])
    v = list(v) + [0] * (6 - len(v))
    return tuple(int(bool(x)) for x in v[:6])


def apply_membrane_reactions(model, src, mapping=None, factor=1.0, tol=0.05):
    """add reactions[].pull from a shared-schema model JSON as nodal loads. Returns list of (membrane node, frame node, pull)."""
    with open(src) as fh:
        mem = json.load(fh)
    xyz = {}
    for n in mem.get("nodes", []):
        if isinstance(n, dict):
            xyz[n["id"]] = n["xyz"]
    applied = []
    for r in mem.get("reactions", []):
        mid = r["node"]
        if mapping is not None:
            if str(mid) not in mapping:
                continue
            fn = int(mapping[str(mid)])
        else:
            if mid not in xyz:
                continue
            p = xyz[mid]
            fn, dmin = None, tol
            for i, q in enumerate(model.nodes):
                d = norm(sub(p, q))
                if d <= dmin:
                    fn, dmin = i, d
            if fn is None:
                continue
        pull = [factor * v for v in r["pull"]]
        cur = model.nodal.setdefault(fn, [0.0] * 6)
        for i in range(3):
            cur[i] += pull[i]
        applied.append((mid, fn, pull))
    return applied


def from_json(d, base_dir="."):
    md = Model()
    for p in d["nodes"]:
        md.add_node(p["xyz"] if isinstance(p, dict) else p)
    md.supports = {int(k): support_flags(v) for k, v in d.get("supports", {}).items()}
    for m in d["members"]:
        md.add_member(m["name"], m["nodes"], kind=m.get("type", "beam"), section=m.get("section"),
                      fy=m.get("fy", 355.0), div=m.get("div"), ref=m.get("ref"),
                      release_start=m.get("release_start", "fixed"), release_end=m.get("release_end", "fixed"),
                      A=m.get("A"), Iy=m.get("Iy"), Iz=m.get("Iz"), J=m.get("J"), E=m.get("E"), G=m.get("G"),
                      EA=m.get("EA"), prestress=m.get("prestress", 0.0), L0=m.get("L0"),
                      Lcr_y=m.get("Lcr_y"), Lcr_z=m.get("Lcr_z"), Lb=m.get("Lb"), cold=m.get("cold", False))
    loads = d.get("loads", {})
    for k, v in loads.get("nodal", {}).items():
        cur = md.nodal.setdefault(int(k), [0.0] * 6)
        for i, x in enumerate(list(v) + [0.0] * (6 - len(v))):
            cur[i] += x
    for u in loads.get("udl", []):
        for ei in md.members[u["member"]]["elems"]:
            md.udl.append((ei, list(u["q"])))
    rx = d.get("reactions")
    if rx:
        path = rx["file"] if os.path.isabs(rx["file"]) else os.path.join(base_dir, rx["file"])
        md.applied = apply_membrane_reactions(md, path, rx.get("map"), rx.get("factor", 1.0), rx.get("tol", 0.05))
    return md


def gen_mast(H, section, base="pinned", ties=(), loads=(), fy=355.0, div=8, cold=False):
    """vertical mast (0,0,0)-(0,0,H) with tie-back cables 'x,y,z:EA:T0' from the head to anchors."""
    md = Model()
    b = md.add_node([0, 0, 0])
    h = md.add_node([0, 0, H])
    md.supports[b] = support_flags("fixed" if base == "fixed" else "pinned")
    if base != "fixed":
        md.supports[b] = (1, 1, 1, 0, 0, 1)   # pinned base: torsion held (spigot/fork), bending free
    md.add_member("MAST", [b, h], section=section, fy=fy, div=div, cold=cold)
    for k, t in enumerate(ties):
        p, EA, T0 = t
        a = md.add_node(p)
        md.supports[a] = support_flags("pinned")
        md.add_member(f"TIE{k + 1}", [h, a], kind="cable", EA=EA, prestress=T0)
    for f in loads:
        cur = md.nodal.setdefault(h, [0.0] * 6)
        for i in range(3):
            cur[i] += f[i]
    md.head = h
    return md


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", nargs="?", choices=["mast"])
    ap.add_argument("--input")
    ap.add_argument("--H", type=float, default=8.0, help="mast: height [m]")
    ap.add_argument("--section", default="CHS:219.1x8", help="mast: section (member_check syntax)")
    ap.add_argument("--fy", type=float, default=355.0)
    ap.add_argument("--cold", action="store_true")
    ap.add_argument("--base", choices=["pinned", "fixed"], default="pinned")
    ap.add_argument("--div", type=int, default=8, help="mast: elements along the mast")
    ap.add_argument("--tie", action="append", default=[],
                    help="mast: tie-back cable 'x,y,z:EA:T0' (anchor point m, EA kN, prestress kN); "
                         "use --tie=-5,0,0:... for negative x")
    ap.add_argument("--load", action="append", default=[], help="mast: head load 'Fx,Fy,Fz' [kN] (design value)")
    ap.add_argument("--reactions", help="shared-schema model JSON with reactions[].pull (membrane -> steel)")
    ap.add_argument("--node", type=int, action="append", default=[],
                    help="mast: membrane node id(s) whose pull acts on the mast head")
    ap.add_argument("--map", default=None, help="--input: 'membraneNode:frameNode,...' (else match by xyz)")
    ap.add_argument("--match-tol", type=float, default=0.05, help="xyz match tolerance [m]")
    ap.add_argument("--reaction-factor", type=float, default=1.0)
    ap.add_argument("--imp", default="unique", help="unique | sway | none | mm:<amplitude>")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--factors", default=None)
    ap.add_argument("--out", default=None, help="write <out>.json with results")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    if a.input:
        with open(a.input) as fh:
            md = from_json(json.load(fh), os.path.dirname(os.path.abspath(a.input)))
        if a.reactions:
            mp = dict(p.split(":") for p in a.map.split(",")) if a.map else None
            md.applied = apply_membrane_reactions(md, a.reactions, mp, a.reaction_factor, a.match_tol)
    elif a.kind == "mast":
        ties = []
        for t in a.tie:
            p, EA, T0 = t.split(":")
            ties.append(([float(v) for v in p.split(",")], float(EA), float(T0)))
        loads = [[float(v) for v in s.split(",")] for s in a.load]
        md = gen_mast(a.H, a.section, a.base, ties, loads, a.fy, a.div, a.cold)
        if a.reactions:
            mp = {str(n): md.head for n in a.node} if a.node else None
            if mp is None:
                ap.error("mast --reactions needs --node <membrane node id> (reaction applied at the head)")
            md.applied = apply_membrane_reactions(md, a.reactions, mp, a.reaction_factor, a.match_tol)
    else:
        ap.error("give 'mast' or --input")
    print(f"Factors: {CF.tag('steel.E')}, {CF.tag('steel.G')}, {CF.tag('steel.phi0')}, "
          f"e0/imperfection α [{CF.status('steel.imp_alpha')}]")
    for (mid, fn, pull) in getattr(md, "applied", []):
        print(f"Membrane reaction: membrane node {mid} -> frame node {fn}: pull = "
              f"({pull[0]:.2f}, {pull[1]:.2f}, {pull[2]:.2f}) kN (factor {a.reaction_factor:g})")
    if a.reactions and not getattr(md, "applied", []):
        print("WARNING: no membrane reaction matched a frame node (check --map / --node / --match-tol)")
    res = run(md, imp=a.imp, check=a.check)
    if a.out:
        keep = {k: v for k, v in res.items() if k not in ("u_first", "u_second")}
        for k in ("reactions_first", "reactions_second", "disp_first", "disp_second"):
            keep[k] = {str(n): v for n, v in res[k].items()}
        with open(a.out + ".json", "w") as fh:
            json.dump(keep, fh, indent=1, default=float)
    return res


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
