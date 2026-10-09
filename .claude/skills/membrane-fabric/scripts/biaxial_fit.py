#!/usr/bin/env python3
"""Biaxial test evaluation: orthotropic membrane stiffness + compensation (EN 17117-1/-2 style).

Fits the plane-stress orthotropic law (per unit width, stresses in kN/m, strains in %)

    ε_w = n_w/(E_w t) − ν_fw · n_f/(E_f t)
    ε_f = n_f/(E_f t) − ν_wf · n_w/(E_w t)       with reciprocity  ν_wf/(E_w t) = ν_fw/(E_f t)

to measured points by least squares (unknowns a = 1/E_w t, b = 1/E_f t, c = ν_wf/E_w t),
either for all load ratios together or per ratio (--per-ratio, stiffness that matches the
governing stress state, e.g. 1:1 prestress, 2:1 / 1:2 snow/wind). Use points from the
STABILISED cycles (after the shake-down cycles of the test protocol), as stress/strain
increments relative to the start of the evaluated cycle.

Compensation (EN 17117-2 concept): strain the panel must be shrunk by so that it reaches the
design prestress on site = residual strain after the test's prestress cycles + elastic strain
at the prestress:   comp_w = ε_res,w + (a·n_w0 − c·n_f0),  comp_f = ε_res,f + (b·n_f0 − c·n_w0)

Direct stiffness formulation (used by many membrane programs, JRC132615 eqs. 2.1-2.12):
    n_w = Ed_w·ε_w + Ed_wf·ε_f ,  n_f = Ed_f·ε_f + Ed_fw·ε_w
    Ed_w = E_w t/(1 − ν_wf ν_fw),  Ed_f = E_f t/(1 − ν_wf ν_fw),  Ed_wf = ν_fw·Ed_w = Ed_fw = ν_wf·Ed_f
  (here ν_fw multiplies n_f in the warp strain = JRC ν_xy; ν_wf = JRC ν_yx). The fit prints both forms.

MSAJ/M-02-1995 commentary evaluation (--msaj): each load-strain path (ratio x direction) is first
replaced by its regression line n = m·ε + b (least squares, load on strain); the constants are then
chosen so that the fictitious lines ε = (n − b_j)·k_j(constants), with the intercept b_j of the
path's regression line, minimise the sum of squared STRAIN errors S_ε over all points (the "least
squares method, strain term" of the commentary, as implemented by Uhlemann et al. 2011). By default
the two zero-load paths (weft at 1:0, warp at 0:1) are omitted (8 paths, commentary); --paths 10
includes them (Bridgens & Gosling 2010). --no-reciprocity fits four constants; --ratios selects
load ratios (e.g. 1:1,2:1 for a synclastic roof). The default fit (without --msaj) is a secant fit
through the origin of the increments; the MSAJ fit uses the slopes of the paths, so the two differ
on non-linear data (validated in reference/validation.md).

Input CSV (header required, lines starting with # are comments):
  ratio,n_w,n_f,eps_w,eps_f     (kN/m, kN/m, %, %); ratio as "warp:weft", e.g. 2:1

Examples
  python3 biaxial_fit.py test.csv
  python3 biaxial_fit.py test.csv --per-ratio
  python3 biaxial_fit.py test.csv --prestress 2.0 2.0 --residual 0.45 1.10     # compensation
  python3 biaxial_fit.py ../reference/data/biaxial_uhlemann2011_T2.csv --msaj              # 8 paths
  python3 biaxial_fit.py ../reference/data/biaxial_uhlemann2011_T2.csv --msaj --paths 10 --no-reciprocity
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict


def inverse_to_direct(Ew_t, Ef_t, nu_wf, nu_fw):
    """inverse (E·t, ν) -> direct stiffness (Ed_w, Ed_f, Ed_wf, Ed_fw) [kN/m] (JRC132615 eqs. 2.5-2.8)."""
    d = 1.0 - nu_wf * nu_fw
    if d <= 0:
        raise ValueError("ν_wf·ν_fw >= 1: no positive-definite direct stiffness")
    Edw, Edf = Ew_t / d, Ef_t / d
    return {"Ed_w": Edw, "Ed_f": Edf, "Ed_wf": nu_fw * Edw, "Ed_fw": nu_wf * Edf}


def direct_to_inverse(Ed_w, Ed_f, Ed_wf, Ed_fw=None):
    """direct stiffness (crimp-interchange Ed_wf, symmetric if Ed_fw None) -> E_w t, E_f t, ν_wf, ν_fw
    (JRC132615 eqs. 2.9-2.12)."""
    Ed_fw = Ed_wf if Ed_fw is None else Ed_fw
    nu_fw, nu_wf = Ed_wf / Ed_w, Ed_fw / Ed_f
    d = 1.0 - nu_wf * nu_fw
    return {"Ew_t": Ed_w * d, "Ef_t": Ed_f * d, "nu_wf": nu_wf, "nu_fw": nu_fw}


def solve3(M, v):
    """Gaussian elimination with partial pivoting for a 3x3 system."""
    A = [row[:] + [v[i]] for i, row in enumerate(M)]
    for k in range(3):
        p = max(range(k, 3), key=lambda r: abs(A[r][k]))
        A[k], A[p] = A[p], A[k]
        if abs(A[k][k]) < 1e-18:
            raise ValueError("singular normal equations (need points with both n_w and n_f varying)")
        for r in range(k + 1, 3):
            f = A[r][k] / A[k][k]
            for c in range(k, 4):
                A[r][c] -= f * A[k][c]
    x = [0.0] * 3
    for k in range(2, -1, -1):
        x[k] = (A[k][3] - sum(A[k][c] * x[c] for c in range(k + 1, 3))) / A[k][k]
    return x


def fit(points):
    """points: list of (n_w, n_f, eps_w, eps_f) with eps as strain (not %). Returns dict."""
    # residuals: r1 = a nw − c nf − ew ; r2 = b nf − c nw − ef ; unknowns x = (a, b, c)
    rows = []
    for nw, nf, ew, ef in points:
        rows.append(((nw, 0.0, -nf), ew))
        rows.append(((0.0, nf, -nw), ef))
    M = [[sum(r[0][i] * r[0][j] for r in rows) for j in range(3)] for i in range(3)]
    v = [sum(r[0][i] * r[1] for r in rows) for i in range(3)]
    a, b, c = solve3(M, v)
    res = [sum(r[0][i] * x for i, x in enumerate((a, b, c))) - r[1] for r in rows]
    rms = math.sqrt(sum(e * e for e in res) / len(res))
    return {"Ew_t": 1 / a, "Ef_t": 1 / b, "nu_wf": c / a, "nu_fw": c / b, "a": a, "b": b, "c": c,
            "rms_strain": rms, "n_points": len(points)}


def fit_fixed_nu(points, nu_wf):
    """per-ratio stiffness with ν_wf fixed (one load ratio cannot identify three constants)."""
    # r1 = a (nw − ν nf) − ew ;  r2 = b nf − a ν nw − ef   (c = ν a)
    rows = []
    for nw, nf, ew, ef in points:
        rows.append(((nw - nu_wf * nf, 0.0), ew))
        rows.append(((-nu_wf * nw, nf), ef))
    m11 = sum(r[0][0] ** 2 for r in rows)
    m12 = sum(r[0][0] * r[0][1] for r in rows)
    m22 = sum(r[0][1] ** 2 for r in rows)
    v1 = sum(r[0][0] * r[1] for r in rows)
    v2 = sum(r[0][1] * r[1] for r in rows)
    det = m11 * m22 - m12 * m12
    if abs(det) < 1e-18 or m11 < 1e-12 or m22 < 1e-12:
        raise ValueError("ratio does not load both directions enough")
    a = (v1 * m22 - v2 * m12) / det
    b = (m11 * v2 - m12 * v1) / det
    c = nu_wf * a
    res = [r[0][0] * a + r[0][1] * b - r[1] for r in rows]
    return {"Ew_t": 1 / a, "Ef_t": 1 / b, "nu_wf": nu_wf, "nu_fw": c / b, "a": a, "b": b, "c": c,
            "rms_strain": math.sqrt(sum(e * e for e in res) / len(res)), "n_points": len(points)}


def solve(M, v):
    """Gaussian elimination with partial pivoting for a k x k system."""
    k = len(v)
    A = [row[:] + [v[i]] for i, row in enumerate(M)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c]))
        A[c], A[p] = A[p], A[c]
        if abs(A[c][c]) < 1e-18:
            raise ValueError("singular normal equations (the selected paths do not identify all constants)")
        for r in range(c + 1, k):
            f = A[r][c] / A[c][c]
            for z in range(c, k + 1):
                A[r][z] -= f * A[c][z]
    x = [0.0] * k
    for c in range(k - 1, -1, -1):
        x[c] = (A[c][k] - sum(A[c][z] * x[z] for z in range(c + 1, k))) / A[c][c]
    return x


def parse_ratio(label):
    """'2:1' -> (1.0, 0.5): load per unit leading load in warp and weft."""
    try:
        rw, rf = (float(s) for s in label.split(":"))
    except ValueError:
        raise ValueError(f"ratio label '{label}' is not of the form warp:weft (e.g. 2:1)")
    m = max(rw, rf)
    if m <= 0:
        raise ValueError(f"ratio label '{label}' has no load")
    return rw / m, rf / m


def regression_line(pts):
    """least-squares line n = m·ε + b through (n, ε) points (load on strain). Returns (m, b)."""
    n = len(pts)
    mn, me = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    see = sum((p[1] - me) ** 2 for p in pts)
    if see < 1e-30:
        raise ValueError("path without strain variation")
    m = sum((p[1] - me) * (p[0] - mn) for p in pts) / see
    return m, mn - m * me


def msaj_paths(data, ratios=None, include_zero=False):
    """split the CSV data into load-strain paths {(ratio, 'w'|'f'): [(N_lead, ε), ...]} (ε as strain)."""
    paths = {}
    for label, pts in data.items():
        if ratios and label not in ratios:
            continue
        rw, rf = parse_ratio(label)
        for d, r in (("w", rw), ("f", rf)):
            if r == 0 and not include_zero:
                continue
            paths[(label, d)] = [((nw / rw) if rw >= rf else (nf / rf), ew if d == "w" else ef)
                                 for nw, nf, ew, ef in pts]
    return paths


def fit_msaj(data, ratios=None, include_zero=False, reciprocal=True, fix_Ew_t=None):
    """MSAJ/M-02-1995 commentary least squares (strain term) with regression-line intercepts.

    data: {ratio label: [(n_w, n_f, eps_w, eps_f), ...]} (eps as strain), as returned by read().
    Model per path j (direction d, leading load N): ε = k_j·(N − b_j), k_j linear in the compliances
    a = 1/E_w t, b = 1/E_f t, c1 = ν_fw/E_f t (n_f in ε_w), c2 = ν_wf/E_w t (n_w in ε_f); c1 = c2 with
    reciprocity. fix_Ew_t holds E_w t (e.g. to reproduce a bounded grid search).
    Returns the constants, S_ε in %² (as Uhlemann et al. 2011, Table 2) and the paths used."""
    paths = msaj_paths(data, ratios, include_zero)
    if not paths:
        raise ValueError("no load-strain paths selected")
    rows = []
    for (label, d), pts in paths.items():
        rw, rf = parse_ratio(label)
        _, b0 = regression_line(pts)
        # unknowns (a, b, c1, c2): ε_w = a·n_w − c1·n_f ; ε_f = b·n_f − c2·n_w   (n = r·(N − b0))
        coef = (rw, 0.0, -rf, 0.0) if d == "w" else (0.0, rf, 0.0, -rw)
        for N, e in pts:
            rows.append(([q * (N - b0) for q in coef], e))
    if reciprocal:      # c1 = c2 = c
        rows = [((r[0][0], r[0][1], r[0][2] + r[0][3]), r[1]) for r in rows]
    free = list(range(len(rows[0][0])))
    fixed = {}
    if fix_Ew_t:
        fixed[0] = 1.0 / fix_Ew_t
        free.remove(0)
    sub = [([r[0][i] for i in free], r[1] - sum(r[0][i] * v for i, v in fixed.items())) for r in rows]
    k = len(free)
    M = [[sum(r[0][i] * r[0][j] for r in sub) for j in range(k)] for i in range(k)]
    v = [sum(r[0][i] * r[1] for r in sub) for i in range(k)]
    sol = solve(M, v)
    x = [0.0] * len(rows[0][0])
    for i, val in fixed.items():
        x[i] = val
    for i, val in zip(free, sol):
        x[i] = val
    S = sum((sum(c * xi for c, xi in zip(r[0], x)) - r[1]) ** 2 for r in rows)
    a, b = x[0], x[1]
    c1, c2 = (x[2], x[2]) if reciprocal else (x[2], x[3])
    return {"Ew_t": 1 / a, "Ef_t": 1 / b, "nu_fw": c1 / b, "nu_wf": c2 / a, "a": a, "b": b, "c": c1, "c1": c1,
            "c2": c2, "S_eps": S * 1e4, "rms_strain": math.sqrt(S / len(rows)), "n_points": len(rows),
            "paths": sorted(paths), "reciprocal": reciprocal}


def msaj_objective(data, Ew_t, Ef_t, nu_fw, nu_wf, ratios=None, include_zero=False):
    """S_ε [%²] of given constants with the MSAJ regression-line intercepts (to check published sets)."""
    S = 0.0
    for (label, d), pts in msaj_paths(data, ratios, include_zero).items():
        rw, rf = parse_ratio(label)
        _, b0 = regression_line(pts)
        k = (rw / Ew_t - nu_fw * rf / Ef_t) if d == "w" else (rf / Ef_t - nu_wf * rw / Ew_t)
        S += sum((e - k * (N - b0)) ** 2 for N, e in pts)
    return S * 1e4


def read(path):
    data = defaultdict(list)
    with open(path) as fh:
        lines = [ln for ln in fh if ln.strip() and not ln.lstrip().startswith("#")]
        for r in csv.DictReader(lines):
            data[r["ratio"].strip()].append((float(r["n_w"]), float(r["n_f"]),
                                             float(r["eps_w"]) / 100, float(r["eps_f"]) / 100))
    return data


def show(tag, f):
    flag = []
    if f["nu_wf"] > 1 or f["nu_fw"] > 1:
        flag.append("ν > 1 (crimp interchange; valid for fabrics but check the evaluation range)")
    if f["Ew_t"] <= 0 or f["Ef_t"] <= 0:
        flag.append("NEGATIVE stiffness — data inconsistent")
    print(f"{tag:<10}{f['Ew_t']:9.0f}{f['Ef_t']:9.0f}{f['nu_wf']:8.3f}{f['nu_fw']:8.3f}"
          f"{f['rms_strain'] * 100:10.4f}{f['n_points']:6d}  " + "; ".join(flag))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--per-ratio", action="store_true", help="separate constants per load ratio")
    ap.add_argument("--prestress", type=float, nargs=2, metavar=("NW0", "NF0"), help="design prestress [kN/m]")
    ap.add_argument("--residual", type=float, nargs=2, metavar=("EW", "EF"), default=(0.0, 0.0),
                    help="residual strain after the prestress cycles of the test [%%]")
    ap.add_argument("--msaj", action="store_true",
                    help="MSAJ/M-02-1995 commentary least squares (strain term, regression-line intercepts)")
    ap.add_argument("--paths", type=int, choices=(8, 10), default=8,
                    help="--msaj: 8 = omit the zero-load paths (commentary), 10 = include them (Bridgens & Gosling)")
    ap.add_argument("--no-reciprocity", action="store_true", help="--msaj: fit ν_wf and ν_fw independently")
    ap.add_argument("--ratios", help="--msaj: comma-separated load ratios to use, e.g. 1:1,2:1 (default all)")
    a = ap.parse_args(argv)
    data = read(a.csv)
    allp = [p for v in data.values() for p in v]
    print(f"{'set':<10}{'Ew·t':>9}{'Ef·t':>9}{'ν_wf':>8}{'ν_fw':>8}{'rms ε %':>10}{'pts':>6}   [kN/m]")
    f_all = fit(allp)
    show("all", f_all)
    out = {"all": f_all}
    if a.msaj:
        ratios = [s.strip() for s in a.ratios.split(",")] if a.ratios else None
        fm = fit_msaj(data, ratios, include_zero=(a.paths == 10), reciprocal=not a.no_reciprocity)
        show("MSAJ", fm)
        npaths = len(fm["paths"])
        print(f"  MSAJ commentary least squares (strain term): {npaths} load-strain paths "
              f"({', '.join(r + d for r, d in fm['paths'])}), reciprocity {'applied' if fm['reciprocal'] else 'NOT applied'},"
              f" S_ε = {fm['S_eps']:.2f} %²\n  (the 'all' row is the secant fit through the origin of the increments;"
              " the MSAJ row uses the path slopes — on non-linear data they differ, use the one your analysis assumes)")
        out["msaj"] = fm
    if a.per_ratio:
        for ratio, pts in sorted(data.items()):
            try:
                f = fit_fixed_nu(pts, f_all["nu_wf"])
                out[ratio] = f
                show(ratio + "*", f)
            except ValueError as e:
                print(f"{ratio:<10} skipped ({e})")
    if a.per_ratio:
        print("  * per-ratio stiffness with ν_wf fixed from the full fit (a single ratio cannot identify 3 constants);"
              "\n    uniaxial ratios (1:0, 0:1) only determine the loaded direction reliably")
    if a.prestress:
        nw0, nf0 = a.prestress
        src = "msaj" if "msaj" in out else ("1:1" if "1:1" in out else "all")
        f = out[src]
        cw = a.residual[0] / 100 + f["a"] * nw0 - f.get("c1", f["c"]) * nf0
        cf = a.residual[1] / 100 + f["b"] * nf0 - f.get("c2", f["c"]) * nw0
        print(f"\nCompensation at prestress {nw0}/{nf0} kN/m (constants '{src}'):")
        print(f"  warp {cw * 100:.2f} %   weft {cf * 100:.2f} %   (residual {a.residual[0]}/{a.residual[1]} % + elastic)")
        print("  -> use as --comp-warp / --comp-weft in cutting_pattern.py; decompensate fixed-length edges")
        out["compensation_%"] = (cw * 100, cf * 100)
    try:
        fd = out.get("msaj", f_all)
        dd = inverse_to_direct(fd["Ew_t"], fd["Ef_t"], fd["nu_wf"], fd["nu_fw"])
        tag = "MSAJ fit" if "msaj" in out else "all ratios"
        cross = (f"Ed_wf = Ed_fw {dd['Ed_wf']:.0f}" if abs(dd["Ed_wf"] - dd["Ed_fw"]) < 0.5
                 else f"Ed_wf {dd['Ed_wf']:.0f}, Ed_fw {dd['Ed_fw']:.0f} (not symmetric: reciprocity not applied)")
        print(f"\nDirect stiffness form ({tag}): Ed_w {dd['Ed_w']:.0f}, Ed_f {dd['Ed_f']:.0f}, "
              f"crimp interchange {cross} kN/m (for programs using the direct formulation)")
        out["direct"] = dd
    except ValueError as e:
        print(f"\nDirect stiffness form not available: {e}")
    print("\nUse E·t in dynamic_relaxation.py / run_cases.py (--Et-u warp, --Et-v weft). A net model cannot use ν;"
          " use the CST membrane solver (membrane_dr.py) to include ν and shear.")
    print("\nAssumptions:\n  - linear orthotropic plane stress with reciprocity (one ν_wf/E_w t = ν_fw/E_f t), fitted to the "
          "stabilised-cycle increments given in the CSV; real fabrics are non-linear, load-history dependent and "
          "show crimp interchange, so constants depend on the ratios and stress range included (JRC132615 §2.2.2.5)"
          "\n  - the constants depend strongly on the evaluation option (paths, ratios, reciprocity, secant vs "
          "slope): Uhlemann et al. 2011 obtain E_w t 500-1600 kN/m from one glass/PTFE test; state the option used"
          "\n  - shear stiffness is not identified by biaxial tests on warp/weft axes (needs a bias / shear test)"
          "\n  - compensation = residual + elastic strain at the prestress (EN 17117-2 concept); confirm on the "
          "delivered batch")
    return out


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
