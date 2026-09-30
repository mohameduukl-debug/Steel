#!/usr/bin/env python3
"""Run a SET of load cases / combinations on a form-found model and envelope the results.

Each case is solved separately and non-linearly (no superposition) with the DR
solver of dynamic_relaxation.py. Supports:
  * uniform normal pressure ("pressure", + = uplift) and snow on plan ("snow")
  * pressure ZONES: list of plan polygons with their own pressure
  * directional GRADIENT: linear pressure from windward to leeward edge for a wind
    direction (quick way to screen several wind directions)
  * "factor": multiplies all loads of the case (use characteristic loads + factor)
  * "ponding": true -> iterative water accumulation check for that case

Wind pressure coefficients for hypars/cones are NOT in EN 1991-1-4 / ASCE 7:
zones/gradients must come from wind-tunnel data, TensiNet App. A1, published
studies or conservative code canopy/vault values — the example file is
illustrative only.

Outputs
  <out>_envelope.json   per edge max/min force (+ governing case), per cable group
                        max/min, reactions per support per case, membrane stress per case
  <out>_summary.md      table per case + envelope table (paste into the report)

Example
  python3 run_cases.py sail.json examples/load_cases_example.json --out sail_cases

Cases file
  {"material": {"Et_u": 800, "Et_v": 600, "EA_cable": 14000},
   "cases": [
     {"name": "PS", "pressure": 0},
     {"name": "W000_up", "factor": 1.5, "gradient": {"dir_deg": 0, "p_windward": 0.9, "p_leeward": 0.3}},
     {"name": "W_zone", "factor": 1.5, "pressure": 0.4,
      "zones": [{"poly": [[0,0],[3,0],[3,10],[0,10]], "p": 1.1}]},
     {"name": "S", "factor": 1.5, "snow": 0.5, "ponding": true}]}
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynamic_relaxation as DR  # noqa: E402


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def make_pfun(case, model):
    f = case.get("factor", 1.0)
    base = case.get("pressure", 0.0)
    zones = case.get("zones")
    grad = case.get("gradient")
    if not zones and not grad:
        return None
    xs = [nd["xyz"][0] for nd in model["nodes"]]
    ys = [nd["xyz"][1] for nd in model["nodes"]]
    if grad:
        th = math.radians(grad["dir_deg"])
        ux, uy = math.cos(th), math.sin(th)
        proj = [x * ux + y * uy for x, y in zip(xs, ys)]
        smin, smax = min(proj), max(proj)

    def pfun(x, y):
        if zones:
            for z in zones:
                if point_in_poly(x, y, z["poly"]):
                    return f * z["p"]
        if grad:
            t = ((x * ux + y * uy) - smin) / ((smax - smin) or 1.0)
            return f * (grad["p_windward"] + (grad["p_leeward"] - grad["p_windward"]) * t)
        return f * base
    return pfun


def run(model_path, cases_path, out=None, verbose=False):
    with open(model_path) as fh:
        base = json.load(fh)
    with open(cases_path) as fh:
        spec = json.load(fh)
    mat = spec.get("material", {})
    Et_u, Et_v, EAc = mat.get("Et_u", 800.0), mat.get("Et_v", 600.0), mat.get("EA_cable", 14000.0)
    env_e = {}
    groups = defaultdict(lambda: {"max": -math.inf, "min": math.inf, "case_max": None, "case_min": None})
    reac = defaultdict(dict)
    rows = []
    for case in spec["cases"]:
        f = case.get("factor", 1.0)
        pfun = make_pfun(case, base)
        res = DR.analyse(base, Et_u, Et_v, EAc, pressure=(0.0 if pfun else f * case.get("pressure", 0.0)),
                         snow=f * case.get("snow", 0.0), pfun=pfun, do_ponding=case.get("ponding", False),
                         tol=case.get("tol", 1e-4), verbose=verbose)
        an = res["analysis"]
        mem = [e["stress_kN_m"] for e in res["edges"] if e["kind"] == "membrane" and "stress_kN_m" in e]
        warp = [e["stress_kN_m"] for e in res["edges"] if e["kind"] == "membrane" and "stress_kN_m" in e
                and DR.edge_direction(res, e) == "u"]
        weft = [e["stress_kN_m"] for e in res["edges"] if e["kind"] == "membrane" and "stress_kN_m" in e
                and DR.edge_direction(res, e) == "v"]
        cab = [e for e in res["edges"] if e["kind"] != "membrane"]
        for e in res["edges"]:
            r = env_e.setdefault(e["id"], {"max": -math.inf, "min": math.inf, "case_max": None, "case_min": None,
                                           "kind": e["kind"], "group": e.get("group")})
            if e["force"] > r["max"]:
                r["max"], r["case_max"] = e["force"], case["name"]
            if e["force"] < r["min"]:
                r["min"], r["case_min"] = e["force"], case["name"]
            if e.get("group"):
                gg = groups[e["group"]]
                if e["force"] > gg["max"]:
                    gg["max"], gg["case_max"] = e["force"], case["name"]
                if e["force"] < gg["min"]:
                    gg["min"], gg["case_min"] = e["force"], case["name"]
        for rc in res["reactions"]:
            reac[rc["node"]][case["name"]] = rc["pull"]
        pond = an.get("ponding")
        rows.append({"case": case["name"], "factor": f, "converged": an["converged"],
                     "max_disp_mm": round(an["max_displacement_m"] * 1000),
                     "stress_max": round(max(mem), 2) if mem else None,
                     "warp_max": round(max(warp), 2) if warp else None,
                     "weft_max": round(max(weft), 2) if weft else None,
                     "duration": case.get("duration") or ("short" if case["name"].upper().startswith("W") else "long"),
                     "stress_min": round(min(mem), 2) if mem else None,
                     "cable_max": round(max(e["force"] for e in cab), 1) if cab else None,
                     "cable_min": round(min(e["force"] for e in cab), 2) if cab else None,
                     "slack_links": an["slack_links"],
                     "ponding": pond["status"] if pond else "-",
                     "max_reaction": round(max(r["magnitude"] for r in res["reactions"]), 1)})
        if verbose:
            print(f"  done {case['name']}", file=sys.stderr)
    env = {"model": os.path.basename(model_path), "cases": [c["name"] for c in spec["cases"]],
           "material": {"Et_u": Et_u, "Et_v": Et_v, "EA_cable": EAc},
           "summary": rows, "groups": dict(groups),
           "edges": {str(k): v for k, v in env_e.items()},
           "reactions": {str(k): v for k, v in reac.items()}}
    # reaction envelope per support: max magnitude + governing case (concurrent set kept in 'reactions')
    renv = {}
    for node, per in reac.items():
        best = max(per.items(), key=lambda kv: math.sqrt(sum(c * c for c in kv[1])))
        renv[str(node)] = {"case": best[0], "pull": best[1], "magnitude": math.sqrt(sum(c * c for c in best[1])),
                           "Fz_min": min(p[2] for p in per.values()), "Fz_max": max(p[2] for p in per.values())}
    env["reaction_envelope"] = renv
    if out:
        with open(out + "_envelope.json", "w") as fh:
            json.dump(env, fh, indent=1)
        with open(out + "_summary.md", "w") as fh:
            fh.write(f"# Load-case results — {env['model']}\n\n")
            cols = list(rows[0])
            fh.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
            for r in rows:
                fh.write("| " + " | ".join(str(r[c]) for c in cols) + " |\n")
            fh.write("\n## Cable groups (envelope)\n\n| group | F_max kN | case | F_min kN | case |\n|---|---|---|---|---|\n")
            for g, v in sorted(groups.items()):
                fh.write(f"| {g} | {v['max']:.1f} | {v['case_max']} | {v['min']:.2f} | {v['case_min']} |\n")
            fh.write("\n## Supports (max resultant, governing case)\n\n| node | |F| kN | case | Fz min | Fz max |\n"
                     "|---|---|---|---|---|\n")
            for n, v in sorted(renv.items(), key=lambda kv: int(kv[0])):
                fh.write(f"| {n} | {v['magnitude']:.1f} | {v['case']} | {v['Fz_min']:.1f} | {v['Fz_max']:.1f} |\n")
            fh.write("\nNon-linear analysis per case (no superposition). Cable-net analogy: preliminary results.\n")
    return env


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("cases")
    ap.add_argument("--out", default="cases")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    env = run(a.model, a.cases, a.out, a.verbose)
    rows = env["summary"]
    print(f"{'case':<12}{'f':>5}{'disp mm':>9}{'n_max':>8}{'n_min':>8}{'cab max':>9}{'cab min':>9}{'slack':>7}"
          f"{'R max':>8}  ponding")
    for r in rows:
        print(f"{r['case']:<12}{r['factor']:>5}{r['max_disp_mm']:>9}{r['stress_max'] or 0:>8.2f}"
              f"{r['stress_min'] or 0:>8.2f}{r['cable_max'] or 0:>9.1f}{r['cable_min'] or 0:>9.2f}"
              f"{r['slack_links']:>7}{r['max_reaction']:>8.1f}  {r['ponding']}"
              + ("" if r["converged"] else "  NOT CONVERGED"))
    print("\nCable groups: " + ", ".join(f"{g} {v['max']:.1f}/{v['min']:.1f} kN" for g, v in sorted(env["groups"].items())))
    if any(r["cable_min"] is not None and r["cable_min"] <= 0 for r in rows):
        print("WARNING: slack cable segment(s) in at least one case")
    if any(r["ponding"] not in ("-", "no basin (surface drains)") for r in rows):
        print("WARNING: ponding detected — see summary")
    print(f"Wrote {a.out}_envelope.json and {a.out}_summary.md")
    return env


if __name__ == "__main__":
    main(sys.argv[1:])
