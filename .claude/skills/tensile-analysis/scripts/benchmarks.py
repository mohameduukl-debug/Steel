#!/usr/bin/env python3
"""Validation benchmarks of the tensile-analysis solvers against independent reference solutions.

Runs every case of reference/validation.md and prints the table (case | reference | expected | obtained |
error | tolerance) plus the run time, so the validation can be repeated on any machine:

    python3 benchmarks.py            # all cases (about 1-2 min on one CPU)
    python3 benchmarks.py --quick    # coarse meshes only
    python3 benchmarks.py --case hencky catenoid

Cases (references are closed-form or published series, computed here independently of the solvers):
  hencky     clamped circular membrane, no prestress, uniform lateral load (Hencky 1915, corrected
             series of Fichter 1997, NASA TP-3658) -> membrane_dr.py (CST), snow-type load
  fichter    same with follower pressure normal to the deformed surface (Fichter 1997 table) -> CST
  square     prestressed flat square membrane, small pressure: n·∇²w = -p, w_max = 0.07367 p a²/n
             (Navier double sine series) -> dynamic_relaxation.py (net) and membrane_dr.py (CST)
  catenoid   minimal surface between two coaxial rings, r = c·cosh(z/c) -> form_find_fdm.py
             --uniform-stress (and the plain linear FDM for contrast)
  cable_point  pretensioned elastic cable, point load at mid-span: exact 2-segment equilibrium
             (Irvine 1981, ch. 1) -> dynamic_relaxation.py
  cable_udl  elastic cable under uniform load per horizontal length: parabola y = w x (L-x)/(2H),
             H from the elastic length condition (Irvine 1981, ch. 2) -> dynamic_relaxation.py
  wrinkling  tension-field theory (Mansfield 1989; Roddeman et al. 1987): uniaxial / off-axis
             orthotropic tension with excess contraction, and Wagner's diagonal-tension shear panel
             -> membrane_dr.py wrinkling model
  speed      30 x 30 sail: form finding + one DR load case (net) timing
"""
from __future__ import annotations

import argparse
import copy
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynamic_relaxation as DR  # noqa: E402
import form_find_fdm as FDM  # noqa: E402
import membrane_dr as MDR  # noqa: E402


# ------------------------------------------------------------------ references
# Fichter (1997) NASA TP-3658, eqs. (20)-(29) and (34): Hencky's series N(ρ) = ¼ q^(2/3) Σ b2n ρ^2n,
# W(ρ) = q^(1/3) Σ a2n (1 - ρ^(2n+2)); b2n and a2n as (numerator, denominator, power of b0).
# b8 (eq. 23, illegible in the scan) re-derived from recurrence (17): b8 = -17 / (18 b0^11).
HENCKY_B = [(1, 1, -1), (-1, 1, 2), (-2, 3, 5), (-13, 18, 8), (-17, 18, 11), (-37, 27, 14), (-1205, 567, 17),
            (-219241, 63504, 20), (-6634069, 1143072, 23), (-51523763, 5143824, 26), (-998796305, 56582064, 29)]
HENCKY_A = [(1, 1, 1), (1, 2, 4), (5, 9, 7), (55, 72, 10), (7, 6, 13), (205, 108, 16), (17051, 5292, 19),
            (2864485, 508032, 22), (103863265, 10287648, 25), (27047983, 1469664, 28),
            (42367613873, 1244805408, 31)]


def hencky_b0(nu):
    """Lead coefficient from the edge condition u(a) = 0, Fichter eq. (30)-(31)."""
    def bc(b0):
        return sum((2 * n + 1 - nu) * num / den / b0 ** e for n, (num, den, e) in enumerate(HENCKY_B))
    lo, hi = 1.2, 3.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if bc(lo) * bc(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def hencky(nu, q, rho=0.0):
    """(w/a at ρ, Nr/(E t) at ρ) for q = p a / (E t)."""
    b0 = hencky_b0(nu)
    W = q ** (1 / 3) * sum(n / d / b0 ** e * (1 - rho ** (2 * k + 2)) for k, (n, d, e) in enumerate(HENCKY_A))
    N = 0.25 * q ** (2 / 3) * sum(n / d / b0 ** e * rho ** (2 * k) for k, (n, d, e) in enumerate(HENCKY_B))
    return W, N


def square_poisson_center(terms=401):
    """w_max·n/(p a²) for n ∇²w = -p on a square of side a, w = 0 on the edges (Navier double series)."""
    s = 0.0
    for m in range(1, terms, 2):
        for k in range(1, terms, 2):
            s += math.sin(m * math.pi / 2) * math.sin(k * math.pi / 2) / (m * k * (m * m + k * k))
    return 16.0 / math.pi ** 4 * s


def catenoid_c(R, h):
    """Larger (stable) root c of R = c·cosh(h/c) (rings of radius R at z = ±h)."""
    lo, hi = h / 1.1997, 50.0 * R           # c·cosh(h/c) is minimal at h/c = 1.1997
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mid * math.cosh(h / mid) > R:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def cable_point_exact(L, L0, EA, P):
    """Symmetric 2-segment cable, supports at the same level, point load P at mid-span.
    Returns (sag, tension). Exact statics + Hooke: T = EA(l - l0)/l0, 2 T sinθ = P, l = (L/2)/cosθ."""
    a, l0 = L / 2, L0 / 2
    th_lo = math.acos(min(1.0, a / l0)) if l0 > a else 0.0
    th_hi = math.pi / 2 - 1e-9

    def f(th):
        T = EA * (a / math.cos(th) - l0) / l0
        return 2 * T * math.sin(th) - P
    lo, hi = th_lo, th_hi
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
    th = 0.5 * (lo + hi)
    return a * math.tan(th), EA * (a / math.cos(th) - l0) / l0


def cable_udl_exact(L, S0, EA, w, nint=4000):
    """Elastic cable under w per horizontal length: y = w x (L - x)/(2H). H from
    S0 = ∫ sqrt(1+y'^2) / (1 + H sqrt(1+y'^2)/EA) dx (unstressed length). Returns (H, sag)."""
    def unstressed(H):
        hstep = L / nint
        tot = 0.0
        for k in range(nint + 1):
            x = k * hstep
            sl = w / H * (L / 2 - x)
            ds = math.sqrt(1 + sl * sl)
            f = ds / (1 + H * ds / EA)
            wgt = 1 if k in (0, nint) else (4 if k % 2 else 2)
            tot += wgt * f
        return tot * hstep / 3
    lo, hi = 1e-6 * w * L, 1e6 * w * L
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if unstressed(mid) > S0:      # too long unstressed -> H too small
            lo = mid
        else:
            hi = mid
    H = math.sqrt(lo * hi)
    return H, w * L * L / (8 * H)


# ------------------------------------------------------------------ models
def disk_model(a, nrings):
    """Triangulated disc of radius a: centre node + rings k = 1..nrings with 6k nodes; outer ring fixed."""
    nodes = [{"id": 0, "xyz": [0.0, 0.0, 0.0], "fixed": False}]
    rings = [[0]]
    for k in range(1, nrings + 1):
        ids = []
        for j in range(6 * k):
            t = 2 * math.pi * j / (6 * k)
            nodes.append({"id": len(nodes), "xyz": [a * k / nrings * math.cos(t), a * k / nrings * math.sin(t), 0.0],
                          "fixed": k == nrings})
            ids.append(len(nodes) - 1)
        rings.append(ids)
    faces = []
    for k in range(1, nrings + 1):
        inner, outer = rings[k - 1], rings[k]
        if k == 1:
            for j in range(6):
                faces.append([0, outer[j], outer[(j + 1) % 6]])
            continue
        ni, no = len(inner), len(outer)
        i = o = 0
        while i < ni or o < no:      # merge both rings by angle
            ai = (i + 1) / ni
            ao = (o + 1) / no
            if o < no and (i >= ni or ao <= ai):
                faces.append([inner[i % ni], outer[o % no], outer[(o + 1) % no]])
                o += 1
            else:
                faces.append([inner[i % ni], outer[o % no], inner[(i + 1) % ni]])
                i += 1
    return {"units": {"length": "m", "force": "kN"}, "type": "disk", "nodes": nodes, "edges": [], "faces": faces}


def cable_model(L, nseg, EA, L0):
    nodes = [{"id": i, "xyz": [L * i / nseg, 0.0, 0.0], "fixed": i in (0, nseg)} for i in range(nseg + 1)]
    edges = [{"id": i, "n": [i, i + 1], "kind": "cable", "EA": EA, "L0": L0 / nseg, "length": L / nseg}
             for i in range(nseg)]
    return {"nodes": nodes, "edges": edges, "faces": []}


# ------------------------------------------------------------------ cases
def run_hencky(nrings, load="snow", a=1.0, Et=1000.0, nu=0.3, q=1e-3, tol=None):
    """CST on the Hencky problem. Returns dict with w0/a, Nr(0)/Et, Nr(edge)/Et (+ refs at element radius)."""
    m = disk_model(a, nrings)
    p = q * Et / a
    tol = tol or 1e-7 * p * a * a
    G = Et / (2 * (1 + nu))
    kw = {"snow": p} if load == "snow" else {"pressure": p}
    r = MDR.analyse(m, Et, Et, nu, G, 0.0, prestress=(0.0, 0.0), tol=tol, maxit=400000, **kw)
    X = [nd["xyz"] for nd in r["nodes"]]
    w0 = abs(X[0][2]) / a
    els = r["elements"]
    cen = [e for e in els if 0 in e["nodes"]]
    n0 = sum(0.5 * (e["n1"] + e["n2"]) for e in cen) / len(cen) / Et
    # radial stress of the outer-ring elements vs. series at the element centroid radius
    errs = []
    for e in els:
        c = [sum(m["nodes"][v]["xyz"][k] for v in e["nodes"]) / 3 for k in range(2)]
        rho = math.hypot(*c) / a
        if rho < 1 - 1.0 / nrings:
            continue
        ph = math.atan2(c[1], c[0])
        nrr = e["n_warp"] * math.cos(ph) ** 2 + e["n_weft"] * math.sin(ph) ** 2 + 2 * e["n_shear"] * math.sin(ph) * math.cos(ph)
        errs.append((nrr / Et, hencky(nu, q, rho)[1]))
    nr_edge = sum(x for x, _ in errs) / len(errs)
    nr_edge_ref = sum(y for _, y in errs) / len(errs)
    return {"w0_a": w0, "N0": n0, "Nedge": nr_edge, "Nedge_ref": nr_edge_ref, "converged": r["analysis"]["converged"],
            "nodes": len(m["nodes"]), "wrinkled": r["analysis"]["wrinkled_elements"]}


def square_model(a, ndiv, n0):
    m = FDM.gen_sail4(a, 0.0, ndiv, 1.0, 1.0, True)
    FDM.solve_fdm(m)
    FDM.compute_results(m, n0)
    return m


def run_square(ndiv, solver, a=10.0, n0=2.0, p=0.002, Et=800.0):
    m = square_model(a, ndiv, n0)
    tol = 1e-6 * p * a * a / ndiv ** 2
    if solver == "net":
        r = DR.analyse(m, Et, Et, 1e5, pressure=p, tol=tol, maxit=500000)
    else:
        r = MDR.analyse(m, Et, Et, 0.3, Et / 2.6, 1e5, pressure=p, prestress=(n0, n0), tol=tol, maxit=500000)
    w = max(abs(nd["xyz"][2]) for nd in r["nodes"])
    return {"coef": w * n0 / (p * a * a), "converged": r["analysis"]["converged"], "nodes": len(m["nodes"])}


def run_catenoid(nr, nc, R=1.0, h=0.4, uniform=True):
    m = FDM.gen_rings(R, R, 2 * h, nr, nc, 1.0)
    for nd in m["nodes"]:
        nd["xyz"][2] -= h
    info = FDM.form_find_uniform_stress(m, 1.0) if uniform else (FDM.solve_fdm(m) and None)
    c = catenoid_c(R, h)
    err = max(abs(math.hypot(nd["xyz"][0], nd["xyz"][1]) - c * math.cosh(nd["xyz"][2] / c)) for nd in m["nodes"])
    neck = min(math.hypot(nd["xyz"][0], nd["xyz"][1]) for nd in m["nodes"])
    return {"err": err, "neck": neck, "c": c, "info": info}


def run_cable_point(nseg=20, L=10.0, EA=10000.0, T0=10.0, P=5.0):
    L0 = L / (1 + T0 / EA)
    m = cable_model(L, nseg, EA, L0)
    X, it, R = DR.relax(m, extra={nseg // 2: [0.0, 0.0, -P]}, tol=1e-10, maxit=500000)
    sag = -X[nseg // 2][2]
    T = max(e["_T"] for e in m["edges"])
    return {"sag": sag, "T": T, "ref": cable_point_exact(L, L0, EA, P)}


def run_cable_udl(nseg=40, L=10.0, EA=20000.0, w=1.0, S0=10.25):
    """Load per HORIZONTAL length: nodal loads w x (horizontal tributary length), updated from the current
    geometry until they stop changing (the cable nodes move horizontally when it stretches)."""
    m = cable_model(L, nseg, EA, S0)
    for nd in m["nodes"]:          # start from a sagging shape (a straight slack cable has no stiffness)
        x = nd["xyz"][0]
        nd["xyz"][2] = -4 * 0.8 * x * (L - x) / (L * L)
    X = [nd["xyz"] for nd in m["nodes"]]
    for _ in range(50):
        loads = {i: [0.0, 0.0, -w * (X[i + 1][0] - X[i - 1][0]) / 2] for i in range(1, nseg)}
        X, it, R = DR.relax(m, extra=loads, tol=1e-9, maxit=500000)
        for nd, p in zip(m["nodes"], X):
            nd["xyz"] = p
        new = [w * (X[i + 1][0] - X[i - 1][0]) / 2 for i in range(1, nseg)]
        if max(abs(n_ + loads[i + 1][2]) for i, n_ in enumerate(new)) < 1e-10:
            break
    H = abs(m["edges"][0]["_T"] * (X[1][0] - X[0][0]) / m["edges"][0]["_L"])
    sag = -X[nseg // 2][2]
    dev = max(abs(-X[i][2] - w * X[i][0] * (L - X[i][0]) / (2 * H)) for i in range(nseg + 1))
    return {"H": H, "sag": sag, "shape_dev": dev, "ref": cable_udl_exact(L, S0, EA, w)}


def cable_catenary_exact(L, L0, EA, W):
    """Elastic catenary, supports at the same level, total weight W on unstressed length L0 (Irvine 1981):
    span L = H L0/EA + 2 (H L0/W) asinh(W/(2H)); mid sag = W L0/(8 EA) + (H L0/W)(sqrt(1+(W/2H)^2) - 1)."""
    def span(H):
        return H * L0 / EA + 2 * H * L0 / W * math.asinh(W / (2 * H))
    lo, hi = 1e-9 * W, 1e9 * W
    for _ in range(300):
        mid = math.sqrt(lo * hi)
        if span(mid) > L:
            hi = mid
        else:
            lo = mid
    H = math.sqrt(lo * hi)
    return H, W * L0 / (8 * EA) + H * L0 / W * (math.sqrt(1 + (W / (2 * H)) ** 2) - 1)


def run_cable_catenary(nseg=40, L=10.0, EA=20000.0, W=10.0, L0=10.25):
    """Equal nodal loads on equal UNSTRESSED segments = self-weight -> elastic catenary."""
    m = cable_model(L, nseg, EA, L0)
    for nd in m["nodes"]:
        x = nd["xyz"][0]
        nd["xyz"][2] = -4 * 0.8 * x * (L - x) / (L * L)
    loads = {i: [0.0, 0.0, -W / nseg] for i in range(1, nseg)}
    X, it, R = DR.relax(m, extra=loads, tol=1e-9, maxit=500000)
    H = abs(m["edges"][0]["_T"] * (X[1][0] - X[0][0]) / m["edges"][0]["_L"])
    # the end half-loads W/(2 nseg) sit on the supports: they do not change H or the sag
    return {"H": H, "sag": -X[nseg // 2][2], "ref": cable_catenary_exact(L, L0, EA, W)}


def wrinkle_cases(Ew=800.0, Ef=600.0, nu=0.3, G=30.0):
    """Element-level tension-field checks. Returns list of (name, expected (S11,S22,S12), obtained, linear)."""
    m = FDM.gen_sail4(1.0, 0.0, 1, 1, 1, True)
    mem = MDR.Membrane(m, Ew, Ef, nu, G, 1e4, prestress=(0.0, 0.0))
    C11, C22, C12, C66 = mem.C
    D11, D22, D12, D33 = mem.D
    out = []
    for name, th_deg, sig0, beta in (("uniaxial warp, excess contraction", 0.0, 8.0, 0.01),
                                     ("off-axis 30 deg uniaxial + wrinkle strain", 30.0, 5.0, 0.02)):
        th = math.radians(th_deg)
        c, s = math.cos(th), math.sin(th)
        sx, sy, txy = sig0 * c * c, sig0 * s * s, sig0 * c * s
        e11 = C11 * sx + C12 * sy - beta * s * s
        e22 = C12 * sx + C22 * sy - beta * c * c
        g12 = C66 * txy + 2 * beta * s * c
        lin = (D11 * e11 + D12 * e22, D12 * e11 + D22 * e22, D33 * g12)
        got = mem.wrinkle(*lin, {"th": None})[:3]
        out.append((name, (sx, sy, txy), got, lin))
    return out


def run_shear_panel(gamma=0.02, Et=800.0, nu=0.3, n=6):
    """Wagner diagonal-tension field: square sheet, pure shear by boundary displacement, isotropic."""
    m = FDM.gen_sail4(2.0, 0.0, n, 1, 1, True)
    mem = MDR.Membrane(m, Et, Et, nu, Et / (2 * (1 + nu)), 1e4, prestress=(0.0, 0.0), wrinkling=True)
    X = [[p[0] + 0.5 * gamma * p[1], p[1] + 0.5 * gamma * p[0], p[2]] for p in mem.X0]
    X, it, R = mem.relax(X, tol=1e-9, maxit=50000)
    els, _ = mem.results(X)
    e1 = gamma / 2 + gamma * gamma / 8                   # major principal Green strain (45 deg)
    return {"S12": sum(e["n_shear"] for e in els) / len(els), "S12_ref": Et * e1 / 2,
            "S12_linear": Et / (2 * (1 + nu)) * gamma, "all_wrinkled": all(e["wrinkled"] == 1 for e in els),
            "residual": R}


def run_speed(n=30):
    t = time.time()
    m = FDM.gen_sail4(10, 3, n, 1.0, 12.0, False)
    FDM.solve_fdm(m)
    FDM.compute_results(m, 2.0)
    t_ff = time.time() - t
    t = time.time()
    r = DR.analyse(m, 800, 600, 14000, pressure=0.9)
    t_dr = time.time() - t
    return {"nodes": len(m["nodes"]), "t_ff": t_ff, "t_dr": t_dr, "it": r["analysis"]["iterations"],
            "converged": r["analysis"]["converged"]}


# ------------------------------------------------------------------ table
def row(case, ref, exp, got, tol_pct, contrast=False):
    err = 100.0 * (got - exp) / abs(exp) if exp else float("nan")
    ok = abs(err) <= tol_pct
    res = "(contrast, not a check)" if contrast else ("PASS" if ok else "FAIL")
    print(f"| {case} | {ref} | {exp:.5g} | {got:.5g} | {err:+.2f} % | {'-' if contrast else f'{tol_pct} %'} | {res} |")
    return ok or contrast


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", nargs="+", default=["hencky", "fichter", "square", "catenoid", "cable_point",
                                                   "cable_udl", "cable_catenary", "wrinkling", "speed"])
    ap.add_argument("--quick", action="store_true", help="coarse meshes only")
    a = ap.parse_args(argv)
    print("Assumptions: references are closed-form / published series evaluated in this script, independently of "
          "the solvers; errors include discretisation (mesh) error, DR tolerance and, for the Hencky problem, the "
          "PK2-vs-Cauchy and load-direction differences of order of the strain (< 1 %).\n")
    print("| case | reference | expected | obtained | error | tolerance | result |\n|---|---|---|---|---|---|---|")
    allok = True
    t0 = time.time()
    if "hencky" in a.case:
        W, N = hencky(0.3, 1e-3)
        for nr in ([6] if a.quick else [4, 8, 12]):
            r = run_hencky(nr, "snow")
            allok &= row(f"Hencky w0/a, CST {r['nodes']} nodes", "Fichter 1997 series", W, r["w0_a"], 1.0)
            tl = 8.0 if nr < 8 else 2.0          # centre-element stress: coarse mesh averages over rho ~ 0.2
            allok &= row(f"Hencky Nr(0)/Et, CST {r['nodes']} nodes", "Fichter 1997 series", N, r["N0"], tl)
            allok &= row(f"Hencky Nr(edge)/Et, CST {r['nodes']} nodes", "Fichter 1997 series", r["Nedge_ref"],
                         r["Nedge"], 3.0)
    if "fichter" in a.case:
        r = run_hencky(6 if a.quick else 12, "pressure", q=0.01)
        allok &= row(f"Uniform pressure q=0.01 Nr(0)/Et, CST {r['nodes']} nodes", "Fichter 1997 table: 0.0207",
                     0.0207, r["N0"], 5.0)
        r2 = run_hencky(6 if a.quick else 12, "snow", q=0.01)
        allok &= row(f"Hencky q=0.01 Nr(0)/Et, CST {r2['nodes']} nodes", "Fichter 1997 table: 0.0200",
                     0.0200, r2["N0"], 5.0)
    if "square" in a.case:
        ref = square_poisson_center()
        for nd in ([8] if a.quick else [8, 16, 24]):
            for sv in ("net", "cst"):
                r = run_square(nd, sv)
                allok &= row(f"Square n∇²w=-p, w·n/(pa²), {sv} {nd}x{nd}", "Navier series 0.07367", ref, r["coef"],
                             3.0 if nd == 8 else 1.0)
    if "catenoid" in a.case:
        for nr, nc in ([(4, 16), (8, 32)] if a.quick else [(4, 16), (8, 32), (16, 64)]):
            r = run_catenoid(nr, nc)
            allok &= row(f"Catenoid neck r, FDM uniform-stress {nr}x{nc}", "c from R = c cosh(h/c)", r["c"],
                         r["neck"], 0.1)
        r = run_catenoid(8, 32, uniform=False)
        row("Catenoid neck r, plain linear FDM 8x32 (uniform q)", "c from R = c cosh(h/c)", r["c"], r["neck"], 0.1,
            contrast=True)
    if "cable_point" in a.case:
        r = run_cable_point()
        sag, T = r["ref"]
        allok &= row("Cable point load: mid sag", "exact statics (Irvine 1981)", sag, r["sag"], 0.1)
        allok &= row("Cable point load: tension", "exact statics (Irvine 1981)", T, r["T"], 0.1)
    if "cable_udl" in a.case:
        r = run_cable_udl()
        H, sag = r["ref"]
        allok &= row("Cable UDL: horizontal force H", "elastic parabola (Irvine 1981)", H, r["H"], 0.5)
        allok &= row("Cable UDL: mid sag", "elastic parabola (Irvine 1981)", sag, r["sag"], 0.5)
        allok &= row("Cable UDL: shape vs w x(L-x)/2H (max dev / sag)", "parabola", 1.0, 1.0 + r["shape_dev"] / sag, 0.5)
    if "cable_catenary" in a.case:
        r = run_cable_catenary()
        H, sag = r["ref"]
        allok &= row("Cable self-weight: horizontal force H", "elastic catenary (Irvine 1981)", H, r["H"], 0.5)
        allok &= row("Cable self-weight: mid sag", "elastic catenary (Irvine 1981)", sag, r["sag"], 0.5)
    if "wrinkling" in a.case:
        for name, exp, got, lin in wrinkle_cases():
            for k, comp in enumerate(("S11", "S22", "S12")):
                if abs(exp[k]) > 1e-12:
                    allok &= row(f"Tension field {name}: {comp}", "uniaxial σ n⊗n (Roddeman 1987)", exp[k], got[k],
                                 0.01)
                else:
                    ok = abs(got[k]) < 1e-9
                    allok &= ok
                    print(f"| Tension field {name}: {comp} (linear model gives {lin[k]:.3g}) | 0 (no compression) "
                          f"| 0 | {got[k]:.2g} | abs | 1e-9 | {'PASS' if ok else 'FAIL'} |")
        r = run_shear_panel()
        allok &= row("Wagner shear panel: shear flow S12", "tension field σ1 = Eε1, τ = σ1/2", r["S12_ref"], r["S12"], 0.5)
    if "speed" in a.case:
        r = run_speed(20 if a.quick else 30)
        print(f"\nTiming: {r['nodes']}-node sail: form finding {r['t_ff']:.2f} s, DR net pressure case "
              f"{r['t_dr']:.2f} s ({r['it']} iterations, converged {r['converged']})")
    print(f"\nAll checks {'PASS' if allok else 'FAIL'}; total {time.time() - t0:.1f} s")
    return allok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1:]) else 1)
