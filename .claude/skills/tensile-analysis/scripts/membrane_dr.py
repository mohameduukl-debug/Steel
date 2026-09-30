#!/usr/bin/env python3
"""Orthotropic MEMBRANE analysis (CST elements + wrinkling) by Dynamic Relaxation.

Replaces the cable-net analogy of dynamic_relaxation.py with a continuum membrane:
  * constant-strain triangles (each quad face split in two), Total-Lagrangian formulation:
    F = Σ x_k ⊗ ∇N_k (3×2), Green strain E = ½(FᵀF − I), PK2 stress S = S0 + D:E,
    internal forces f_k = A0 · F S ∇N_k  (large displacements, exact kinematics)
  * orthotropic plane-stress material per unit width, axes = warp (grid u) / weft (grid v)
    projected on each triangle: E_w·t, E_f·t, ν_wf (ν_fw by reciprocity), G·t
  * tension-field WRINKLING: if the minor principal stress becomes compressive the element
    carries only its major principal stress (uniaxial); both compressive -> slack
  * initial stress S0 from the form-finding (per quad: u/v edge stresses of the net) or uniform
    --prestress; the prestress state is first relaxed to equilibrium (no load) and reported
  * cables (edge/ridge/valley) as tension-only links with EA; supports from the model
  * loads: follower normal pressure (+ = uplift), snow on plan, optional pressure field

Examples
  python3 membrane_dr.py sail.json --Ew 800 --Ef 600 --nu 0.35 --G 30 --EA-cable 14000 --pressure 0.9 --out up
  python3 membrane_dr.py sail.json --snow 0.75 --out snow
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
        self.D = (Ew / den, Ef / den, nu_fw * Ew / den, G)     # D11, D22, D12, D33 [kN/m]
        self.wrinkling = wrinkling
        # warp/weft stress per quad from the net (u / v edges)
        edge_stress = {}
        for e in model["edges"]:
            if e["kind"] == "membrane" and "stress_kN_m" in e:
                a, b = e["n"]
                edge_stress[(min(a, b), max(a, b))] = e["stress_kN_m"]
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
                warp = unit(sub(self.X0[f[1]], self.X0[f[0]]))
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
        return {"n": t, "A0": A0, "dN": dN, "S0": (s0[0], s0[1], 0.0)}

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
            m_ = 0.5 * (S11 + S22)
            r = math.sqrt(0.25 * (S11 - S22) ** 2 + S12 ** 2)
            s1, s2 = m_ + r, m_ - r
            if s1 <= 0:
                S11 = S22 = S12 = 0.0
                wr = 2
            elif s2 < 0:
                th = 0.5 * math.atan2(2 * S12, S11 - S22)
                cth, sth = math.cos(th), math.sin(th)
                S11, S22, S12 = s1 * cth * cth, s1 * sth * sth, s1 * cth * sth
                wr = 1
        return f1, f2, (S11, S22, S12), wr

    def forces(self, X, P=None):
        n = len(X)
        R = [list(P.get(i, [0.0, 0.0, 0.0])) if P else [0.0, 0.0, 0.0] for i in range(n)]
        K = [0.0] * n
        D11, D22, D12, D33 = self.D
        Dmax = max(D11, D22) + D33
        for tri in self.tris:
            f1, f2, (S11, S22, S12), _ = self.element_state(tri, X)
            A0 = tri["A0"]
            # P1 = F S : columns p1 = S11 f1 + S12 f2, p2 = S12 f1 + S22 f2
            p1 = [S11 * f1[i] + S12 * f2[i] for i in range(3)]
            p2 = [S12 * f1[i] + S22 * f2[i] for i in range(3)]
            smax = abs(S11) + abs(S22) + abs(S12)
            for k, node in enumerate(tri["n"]):
                gx, gy = tri["dN"][k]
                for i in range(3):
                    R[node][i] -= A0 * (p1[i] * gx + p2[i] * gy)
                K[node] += A0 * (Dmax + smax) * (gx * gx + gy * gy)
        for cb in self.cables:
            a, b = cb["n"]
            d = sub(X[b], X[a])
            L = math.sqrt(dot(d, d))
            T = max(cb["EA"] * (L - cb["L0"]) / cb["L0"], 0.0)
            cb["_T"] = T
            for i in range(3):
                R[a][i] += T * d[i] / L
                R[b][i] -= T * d[i] / L
            k = cb["EA"] / cb["L0"] + T / L
            K[a] += k
            K[b] += k
        return R, K

    def relax(self, X, pressure=0.0, snow=0.0, pfun=None, tol=1e-4, maxit=100000, mass_factor=2.0, verbose=False,
              extra=None):
        n = len(X)
        V = [[0.0, 0.0, 0.0] for _ in range(n)]
        KE_prev = 0.0
        loaded = bool(pressure or snow or pfun)
        Rmax = math.inf
        it = 0
        for it in range(maxit):
            P = DRN.external_loads(self.m, X, pressure, snow, pfun) if loaded else None
            if extra:
                P = P if P is not None else defaultdict(lambda: [0.0, 0.0, 0.0])
                for i, f in extra.items():
                    for c in range(3):
                        P[i][c] += f[c]
            R, K = self.forces(X, P)
            Rmax = max((math.sqrt(dot(R[i], R[i])) for i in range(n) if not self.fixed[i]), default=0.0)
            if Rmax < tol:
                break
            KE = 0.0
            for i in range(n):
                if self.fixed[i]:
                    continue
                m = mass_factor * max(K[i], 1e-9)
                for c in range(3):
                    V[i][c] += R[i][c] / m
                KE += m * dot(V[i], V[i])
            if KE < KE_prev:
                V = [[0.0, 0.0, 0.0] for _ in range(n)]
                KE = 0.0
            KE_prev = KE
            for i in range(n):
                if not self.fixed[i]:
                    for c in range(3):
                        X[i][c] += V[i][c]
            if verbose and it % 1000 == 0:
                print(f"  it {it:6d} residual {Rmax:.3e}", file=sys.stderr)
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
        "n_elements": len(els), "ponding": pond}
    return model


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
