#!/usr/bin/env python3
"""Mesh-convergence study: rerun a form-finding (+ optional load case) at 2-4 mesh densities and report
how the governing results change.

Built-in shapes are regenerated at each density with form_find_fdm.py; every mesh count of the shape
(sail4/hypar --n, cone/rings --nr --nc, arch --nu --nv, multibay --m --nv) is multiplied by the level
factor. Cable force densities (--qc, --qr) are multiplied by the same factor so that the CABLE FORCE /
MEMBRANE STRESS ratio, and therefore the design, stays the same: a link force is q x segment length, the
segments get shorter when the mesh is refined, so a fixed --qc would otherwise give a weaker cable and a
bigger sag on finer meshes (use --keep-qc to see that effect). Custom geometry: build the same design at
2-3 densities yourself and pass them with --models.

Examples
  python3 mesh_convergence.py sail4 --size 10 --high 3 --n 8 --qc 12 --prestress 2 \\
          --solver net --pressure 0.9 --levels 1 2 3
  python3 mesh_convergence.py --models coarse.json medium.json fine.json --solver cst --snow 0.6

Reported per level: nodes, max displacement, max/min membrane stress, max cable force, max support
reaction, slack/wrinkled count, run time; then the change between consecutive levels [%]. When the levels
form a geometric sequence (e.g. 1 2 4) and the last two changes are monotonic, the observed order of
convergence p and a Richardson-extrapolated value are printed. A result is called "converged" when its last
change is below --target % (default 5 %).
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynamic_relaxation as DR  # noqa: E402
import form_find_fdm as FDM  # noqa: E402
import membrane_dr as MDR  # noqa: E402

MESH_PARAMS = {"sail4": ["n"], "hypar": ["n"], "cone": ["nr", "nc"], "rings": ["nr", "nc"],
               "arch": ["nu", "nv"], "multibay": ["m", "nv"]}


def refine_args(a, factor, keep_qc=False):
    """Copy of the form-finding namespace with the mesh counts (and cable q) scaled by `factor`."""
    b = copy.deepcopy(a)
    for p in MESH_PARAMS[a.shape]:
        setattr(b, p, max(1, int(round(getattr(a, p) * factor))))
    if a.shape == "cone" and b.nc % b.anchors:
        b.nc += b.anchors - b.nc % b.anchors          # nc must be a multiple of --anchors
    if not keep_qc:
        # actual refinement ratio of the cable-carrying direction(s)
        base = MESH_PARAMS[a.shape][0]
        r = getattr(b, base) / getattr(a, base)
        b.qc = a.qc * r
        b.qr = a.qr * r
    return b


def metrics(model, solver):
    """Governing results of a form-found (solver 'none') or analysed model."""
    out = {"nodes": len(model["nodes"])}
    cab = [e for e in model["edges"] if e["kind"] != "membrane"]
    out["cable_max_kN"] = max((e["force"] for e in cab), default=float("nan"))
    out["reaction_max_kN"] = max((r["magnitude"] for r in model.get("reactions", [])), default=float("nan"))
    if solver == "none":
        ms = model.get("membrane_stress", {})
        out["stress_max"] = ms.get("max", float("nan"))
        out["stress_min"] = ms.get("min", float("nan"))
        sag = [g["sag_ratio"] for g in model.get("cable_groups", []) if "sag_ratio" in g]
        out["cable_sag_ratio_max"] = max(sag) if sag else float("nan")
        return out
    an = model["analysis"]
    out["disp_max_mm"] = an["max_displacement_m"] * 1000.0
    if solver in ("cst", "cst-newton"):
        els = model["elements"]
        out["stress_max"] = max(e["n1"] for e in els)
        out["stress_min"] = min(e["n2"] for e in els)
        out["wrinkled"] = an["wrinkled_elements"] + an["slack_elements"]
    else:
        s = [e["stress_kN_m"] for e in model["edges"] if e["kind"] == "membrane" and "stress_kN_m" in e]
        out["stress_max"] = max(s) if s else float("nan")
        out["stress_min"] = min(s) if s else float("nan")
        out["wrinkled"] = an["slack_links"]
    out["converged"] = an["converged"]
    return out


def run_level(model, o):
    if o.solver == "none":
        return model
    if o.solver == "net":
        return DR.analyse(model, o.Et_u, o.Et_v, o.EA_cable, o.pressure, o.snow, None, False, o.tol)
    return MDR.analyse(model, o.Et_u, o.Et_v, o.nu_wf, o.G, o.EA_cable, o.pressure, o.snow, None, None, o.tol,
                       solver="newton" if o.solver == "cst-newton" else "dr")


def study(models, o, labels):
    rows = []
    for lab, m in zip(labels, models):
        t = time.time()
        res = run_level(m, o)
        r = metrics(res, o.solver)
        r["level"] = lab
        r["time_s"] = time.time() - t
        rows.append(r)
    return rows


def changes(rows, key):
    out = [None]
    for a, b in zip(rows[:-1], rows[1:]):
        fa, fb = a.get(key), b.get(key)
        if fa is None or fb is None or not math.isfinite(fa) or not math.isfinite(fb):
            out.append(None)
        elif max(abs(fa), abs(fb)) < 1e-9:      # both zero (e.g. min stress of a wrinkled membrane)
            out.append(0.0)
        elif fb == 0:
            out.append(None)
        else:
            out.append(100.0 * (fb - fa) / abs(fb))
    return out


def richardson(rows, key, ratios):
    """Observed order and extrapolated value from the last three levels (geometric refinement only)."""
    if len(rows) < 3:
        return None
    r1, r2 = ratios[-2] / ratios[-3], ratios[-1] / ratios[-2]
    if abs(r1 - r2) > 0.02 * r1 or r1 <= 1.0:
        return None
    f1, f2, f3 = (rows[k].get(key) for k in (-3, -2, -1))
    if any(v is None or not math.isfinite(v) for v in (f1, f2, f3)):
        return None
    d1, d2 = f2 - f1, f3 - f2
    if d1 == 0 or d2 == 0 or d1 * d2 < 0 or abs(d2) >= abs(d1):
        return None
    p = math.log(abs(d1 / d2)) / math.log(r1)
    if not 0.3 < p < 5.0:
        return None
    return p, f3 + d2 / (r1 ** p - 1.0)


KEYS = ["disp_max_mm", "stress_max", "stress_min", "cable_max_kN", "reaction_max_kN", "cable_sag_ratio_max"]


def report(rows, ratios, target):
    keys = [k for k in KEYS if any(k in r for r in rows)]
    print(f"{'level':>8}{'nodes':>7}" + "".join(f"{k:>18}" for k in keys) + f"{'wrinkled':>10}{'time s':>8}")
    for r in rows:
        print(f"{str(r['level']):>8}{r['nodes']:>7}" + "".join(f"{r.get(k, float('nan')):>18.4g}" for k in keys)
              + f"{r.get('wrinkled', '-'):>10}{r['time_s']:>8.1f}" + ("" if r.get("converged", True) else "  NOT CONVERGED"))
    print("\nChange from the previous level [%]:")
    verdict = {}
    for k in keys:
        ch = changes(rows, k)
        txt = "  ".join("-" if c is None else f"{c:+.2f}" for c in ch[1:])
        last = ch[-1]
        ok = last is not None and abs(last) < target
        verdict[k] = {"changes_pct": ch[1:], "converged": ok}
        line = f"  {k:<20} {txt}   -> " + ("converged" if ok else f"NOT converged (> {target} %)")
        rich = richardson(rows, k, ratios)
        if rich:
            p, fx = rich
            verdict[k].update(order=p, extrapolated=fx)
            line += f"; observed order p = {p:.2f}, extrapolated {fx:.4g}"
        print(line)
    return verdict


def print_assumptions(o):
    print("Assumptions: each level is form-found and analysed from scratch (no superposition);")
    if o.models:
        print("  user models: the caller is responsible for them describing the same design at different densities;")
    elif o.keep_qc:
        print("  --keep-qc: cable force densities NOT scaled -> the cable force changes with the mesh (shows the effect);")
    else:
        print("  cable force densities --qc/--qr scaled with the mesh factor so cable force / membrane stress is constant;")
    if o.solver == "net":
        print("  solver: dynamic_relaxation.py (cable-net analogy: no fabric shear, no Poisson coupling);")
    elif o.solver in ("cst", "cst-newton"):
        print("  solver: membrane_dr.py (linear-orthotropic CST, tension-field wrinkling; "
              + ("Newton-Raphson" if o.solver == "cst-newton" else "dynamic relaxation") + ");")
    print(f"  loads: pressure {o.pressure:+.3f} kN/m2 (follower), snow {o.snow:.3f} kN/m2 (plan); "
          f"material E_w·t {o.Et_u}, E_f·t {o.Et_v} kN/m, ν {o.nu_wf}, G·t {o.G} kN/m, EA cable {o.EA_cable} kN;")
    print(f"  converged = last change < {o.target} % (engineering judgement, not a code value); max values can move"
          " to a different node between levels, and local peaks at supports/corners converge slowest.\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="All other arguments are passed to form_find_fdm.py (shape and options).",
                                 allow_abbrev=False)
    ap.add_argument("--levels", type=float, nargs="+", default=[1.0, 2.0, 3.0],
                    help="mesh multipliers of the base mesh (2-4 values, increasing)")
    ap.add_argument("--models", nargs="+", help="pre-built form-found models (coarse -> fine) instead of a shape")
    ap.add_argument("--solver", choices=["none", "net", "cst", "cst-newton"], default="net",
                    help="none = compare form-finding only; net = dynamic_relaxation; cst = membrane_dr (DR); "
                         "cst-newton = membrane_dr --solver newton (same results, faster on fine meshes)")
    ap.add_argument("--pressure", type=float, default=0.0, help="normal pressure [kN/m2], + = uplift")
    ap.add_argument("--snow", type=float, default=0.0, help="snow on plan [kN/m2]")
    ap.add_argument("--Et-u", type=float, default=800.0, help="warp E·t [kN/m]")
    ap.add_argument("--Et-v", type=float, default=600.0, help="weft E·t [kN/m]")
    ap.add_argument("--nu-wf", type=float, default=0.3, help="ν_wf (cst only)")
    ap.add_argument("--G", type=float, default=30.0, help="shear stiffness G·t [kN/m] (cst only)")
    ap.add_argument("--EA-cable", type=float, default=14000.0, help="cable EA [kN]")
    ap.add_argument("--tol", type=float, default=1e-4, help="DR residual tolerance [kN]")
    ap.add_argument("--keep-qc", action="store_true", help="do not scale --qc/--qr with the mesh")
    ap.add_argument("--target", type=float, default=5.0, help="convergence threshold on the last change [%%]")
    ap.add_argument("--json", help="write the table and verdict to this JSON file")
    o, rest = ap.parse_known_args(argv)
    if o.models:
        models = []
        for p in o.models:
            with open(p) as fh:
                models.append(json.load(fh))
        labels = [os.path.basename(p) for p in o.models]
        ratios = [1.0] * len(models)
    else:
        fa = FDM.build_parser().parse_args(rest)
        if not fa.shape or fa.input:
            ap.error("give a built-in shape (sail4, hypar, cone, rings, arch, multibay) or use --models")
        lv = sorted(o.levels)
        models, labels, ratios = [], [], []
        for f in lv:
            b = refine_args(fa, f, o.keep_qc)
            with contextlib.redirect_stdout(io.StringIO()):
                m, _ = FDM.form_find(b)
            models.append(m)
            base = MESH_PARAMS[fa.shape][0]
            ratios.append(getattr(b, base) / getattr(fa, base))
            labels.append(f"x{ratios[-1]:.3g}")
    print_assumptions(o)
    rows = study(models, o, labels)
    verdict = report(rows, ratios, o.target)
    if o.json:
        with open(o.json, "w") as fh:
            json.dump({"rows": rows, "verdict": verdict}, fh, indent=1)
        print(f"Wrote {o.json}")
    return rows, verdict


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main(sys.argv[1:])
