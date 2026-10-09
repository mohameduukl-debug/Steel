#!/usr/bin/env python3
"""Membrane material selection: filter and rank the library against project requirements.

Requirements (all optional):
  --n-design N --case wind|snow|...   design stress [kN/m] -> required strip strength via the same
                                     allowable() as membrane_check.py (method, seams included)
  --fire A2                          best EN 13501-1 class needed (A1 < A2 < B < C < D < E < F)
  --translucency 10                  minimum light transmission [%] (upper end of the family range)
  --life 25                          minimum expected service life [years] (lower end of the range)
  --foldable                         retractable / demountable / frequently folded
  --family PES/PVC                   restrict to one family
  --max-cost 3                       relative cost index (PVC = 1), indicative only

Ranking: materials that pass every requirement, ordered by (cost index, utilisation closest to
the target --u-target, default 0.8). Excluded materials are listed with the reason.

Fire, translucency, life, foldability and cost are TYPICAL family figures (materials.json
family_defaults, status 'typical'): screening only. The product's EN 13501-1 classification
report, datasheet and warranty govern. ETFE foil is checked as σ = n/t against f_y1/γ.

Examples
  python3 material_select.py --n-design 9 --case wind --fire B --life 20
  python3 material_select.py --n-design 25 --case snow --fire A2 --translucency 10
  python3 material_select.py --n-design 6 --case wind --foldable --method fm
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import membrane_check as MC  # noqa: E402

F = MC.F
FIRE_ORDER = ["A1", "A2", "B", "C", "D", "E", "F"]


def fire_rank(cls: str) -> int:
    """'B-s2,d0' -> 2 ; 'A2-s1,d0' -> 1 (euroclass letter/number only)."""
    head = cls.split("-")[0].strip().upper()
    if head not in FIRE_ORDER:
        raise ValueError(f"unknown EN 13501-1 class '{cls}'")
    return FIRE_ORDER.index(head)


def product_fire(m, d):
    """(class, source): EN 13501-1 class from the product entry when it states one, else the family default."""
    hit = re.search(r"\b(A1|A2|B|C|D|E|F)-(s[123])(?:[,\s-]*(d[012]))?", m.get("fire", ""))
    if hit:
        return f"{hit.group(1)}-{hit.group(2)}" + (f",{hit.group(3)}" if hit.group(3) else ""), "product"
    return d.get("fire_EN13501"), "family"


def utilisation(m, fam, n, case, method, seam_eff, opts=None):
    """design utilisation of one material (seams in the weaker direction, or ETFE foil).

    partial / ts19102 use the 5 % fractile (fk_w/fk_f) when the entry has one; the seam row uses the joint
    partial factor (γM 1.5 / γM2). Raises ValueError when the method has no factors for the family."""
    if n is None:
        return None
    if fam == "ETFE":
        fd, _ = MC.etfe_design_strength(case, fy=m.get("fy10_MPa"))
        return n / (fd * m["t_mm"])                      # MPa × mm = kN/m
    if method in ("partial", "ts19102") and "fk_w" in m:
        fmin = min(m["fk_w"], m["fk_f"])
    else:
        fmin = min(m["fw"], m["ff"])
    se = 1.0 if method == "japan" else seam_eff
    al, _ = MC.allowable(fmin * se, method, case, fam, opts=dict(opts or {}, joint=True))
    return n / al


def select(req, lib=None):
    """returns (passing, excluded): passing = [(key, info)], excluded = [(key, [reasons])]."""
    lib = lib or MC.load_lib()
    seam_eff = req.get("seam_eff") or F.get("membrane.seam_efficiency")
    ok, out = [], []
    for key, m in lib["materials"].items():
        fam = m["family"]
        d = lib["family_defaults"].get(fam, {})
        why = []
        if req.get("family") and fam != req["family"]:
            why.append(f"family {fam}")
        try:
            u = utilisation(m, fam, req.get("n_design"), req.get("case", "wind"), req.get("method", "factor"),
                            seam_eff, req.get("opts"))
        except ValueError:
            u = None
            why.append(f"no {req.get('method')} factors for {fam}")
        if u is not None and u > 1.0:
            why.append(f"strength (util {u:.2f})")
        fire, fsrc = product_fire(m, d)
        if req.get("fire"):
            if not fire:
                why.append("fire class unknown")
            elif fire_rank(fire) > fire_rank(req["fire"]):
                why.append(f"fire {fire} ({fsrc}) worse than {req['fire']}")
        if req.get("translucency") is not None:
            t = d.get("translucency_pct")
            if not t or t[1] < req["translucency"]:
                why.append(f"translucency ≤ {t[1] if t else '?'} %")
        if req.get("life") is not None:
            life = d.get("life_years")
            if not life or life[0] < req["life"]:
                why.append(f"life from {life[0] if life else '?'} y")
        if req.get("foldable") and not d.get("foldable"):
            why.append("not foldable")
        if req.get("max_cost") is not None and d.get("cost_index", 99) > req["max_cost"]:
            why.append(f"cost index {d.get('cost_index')}")
        info = {"family": fam, "fw": m["fw"], "ff": m["ff"], "util": u, "status": m["status"],
                "fire": fire or "?", "transl": d.get("translucency_pct"),
                "life": d.get("life_years"), "foldable": d.get("foldable"), "cost": d.get("cost_index", 99)}
        (out.append((key, why)) if why else ok.append((key, info)))
    target = req.get("u_target", 0.8)
    ok.sort(key=lambda kv: (kv[1]["cost"], abs((kv[1]["util"] if kv[1]["util"] is not None else target) - target)))
    return ok, out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-design", type=float, default=None, help="design membrane stress [kN/m]")
    ap.add_argument("--case", choices=list(MC.CASES), default="wind")
    ap.add_argument("--method", choices=MC.METHODS, default="factor")
    ap.add_argument("--area", type=float, default=None, help="french: membrane element area [m²]")
    ap.add_argument("--seam-eff", type=float, default=None)
    ap.add_argument("--fire", default=None, help="required EN 13501-1 class or better, e.g. A2, B")
    ap.add_argument("--translucency", type=float, default=None, help="minimum light transmission [%%]")
    ap.add_argument("--life", type=float, default=None, help="minimum service life [years]")
    ap.add_argument("--foldable", action="store_true")
    ap.add_argument("--family", default=None)
    ap.add_argument("--max-cost", type=float, default=None)
    ap.add_argument("--u-target", type=float, default=0.8, help="preferred utilisation for ranking")
    ap.add_argument("--factors", default=None)
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    req = {"n_design": a.n_design, "case": a.case, "method": a.method, "seam_eff": a.seam_eff, "fire": a.fire,
           "translucency": a.translucency, "life": a.life, "foldable": a.foldable, "family": a.family,
           "max_cost": a.max_cost, "u_target": a.u_target, "opts": {"area": a.area}}
    ok, out = select(req)
    print("Requirements: " + ", ".join(f"{k}={v}" for k, v in req.items()
                                       if v not in (None, False) and k != "opts"))
    print(f"\n{'rank':<5}{'material':<28}{'family':<15}{'fw/ff':>9}{'util':>6}  {'fire':<9}{'transl %':>9}"
          f"{'life y':>8}{'fold':>6}{'cost':>6}  data")
    for i, (k, v) in enumerate(ok, 1):
        tr = "-".join(map(str, v["transl"])) if v["transl"] else "?"
        lf = "-".join(map(str, v["life"])) if v["life"] else "?"
        u = f"{v['util']:.2f}" if v["util"] is not None else "-"
        print(f"{i:<5}{k:<28}{v['family']:<15}{v['fw']:>4g}/{v['ff']:<4g}{u:>6}  {v['fire']:<9}{tr:>9}{lf:>8}"
              f"{('yes' if v['foldable'] else 'no'):>6}{v['cost']:>6g}  {v['status']}")
    if not ok:
        print("  none: relax a requirement (see exclusions) or add a product to materials.json")
    print("\nExcluded:")
    for k, why in out:
        print(f"  {k:<28} {'; '.join(why)}")
    print("\nAssumptions:")
    print("  - fire/translucency/life/fold/cost are TYPICAL family figures (screening only): confirm with the product's "
          "EN 13501-1 report, datasheet and warranty")
    print(f"  - strength as membrane_check.py (method '{a.method}'): weaker direction across a seam (seam efficiency "
          f"{a.seam_eff or F.get('membrane.seam_efficiency')}, joint partial factor for partial/ts19102); library strengths "
          "are published class/datasheet values, not certified batch data")
    print("  - ETFE: σ = n/t against f_y10,23/(γM·k) of the design situation (JRC Eurocode Outlook 44)")
    return ok, out


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
