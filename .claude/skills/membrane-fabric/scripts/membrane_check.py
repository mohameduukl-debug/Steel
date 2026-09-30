#!/usr/bin/env python3
"""Membrane stress check (warp & weft, fabric & seam) with selectable design basis.

Methods
-------
  factor   permissible-stress / global stress-factor practice (DEFAULT)
           allowable = f / SF ; SF_short (wind) = 4.0, SF_long (prestress, snow) = 5.0
           — industry practice (Birdair "usually 5"; literature range 4–8).
  fm       FM Global DS 1-59 (2021) Table 2.2.6.1 minimum safety factors on
           NEW-fabric strength: P+D 8.0 ; P+D+(L|S|R) 5.0 ; P+D+W 5.0 ; P+D+T 5.0
           (these assume ≥75 % strength retention, i.e. ASCE 55 L_t = 0.75)
  japan    MLIT Notification 666 style: 1/8 of strength long-term, 1/4 short-term
           (value reported in literature — verify before use)
  partial  limit-state format of CEN/TS 19102:2023 / German "A-factor" practice:
              n_Rd = f_k / (γ_M · k1 · k2 · k3 · k4)
           with the k (A) factors for biaxial/size, load duration, ageing,
           temperature. Default factors are INDICATIVE (German A-factor
           practice) and must be replaced by CEN/TS 19102 Annex C / National
           Annex / project values. Stress input must be the DESIGN value from the
           factored non-linear combination (γ_P ≈ 1.0, γ_Q ≈ 1.5).

Always checked: fabric warp & weft, seams (strength × seam efficiency),
no-slack (min stress > 0) and prestress level vs. strength.

Examples
--------
  python3 membrane_check.py --material PVC-III --nw 18.5 --nf 14.2 --case wind
  python3 membrane_check.py --material Chukoh-FGT-800 --nw 31 --nf 22 --case snow --method fm
  python3 membrane_check.py --fw 84 --ff 80 --nw 9 --nf 7 --case snow --method partial
  python3 membrane_check.py --material PVC-II --prestress 2.0 2.0     (prestress level advice)
  python3 membrane_check.py --list
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "reference", "materials.json")

CASES = {"prestress": "long", "dead": "long", "snow": "long", "live": "long",
         "wind": "short", "temperature": "short", "installation": "short"}

sys.path.insert(0, os.path.join(HERE, "..", "..", "tensile-structures", "scripts"))
import factors as F  # noqa: E402  central code-factor register (V/C/U tagged)


def load_lib():
    with open(LIB) as fh:
        return json.load(fh)


def allowable(f, method, case, family, sf_short=None, sf_long=None, fm_combo="P+D+W"):
    """allowable membrane stress; factors not given explicitly come from the factor register."""
    dur = CASES[case]
    if method == "factor":
        key = "membrane.stress_factor_long" if dur == "long" else "membrane.stress_factor_short"
        given = sf_long if dur == "long" else sf_short
        sf = given if given is not None else F.get(key)
        st = "user" if given is not None else F.status(key)
        return f / sf, f"SF = {sf:g} ({dur}-term) [{st}]"
    if method == "fm":
        key = "membrane.fm159_PD" if fm_combo == "P+D" else "membrane.fm159_other"
        sf = F.get(key)
        return f / sf, f"FM DS 1-59 SF = {sf:g} for {fm_combo} [{F.status(key)}]"
    if method == "japan":
        key = "membrane.japan_long_divisor" if dur == "long" else "membrane.japan_short_divisor"
        k = F.get(key)
        return f / k, f"1/{k:g} of strength ({dur}-term) [{F.status(key)}]"
    if method == "partial":
        tab = F.get("membrane.partial")
        p = tab.get(family, tab["other"])
        A1 = p["A1_long"] if dur == "long" else p["A1_short"]
        k = p["gM"] * p["A0"] * A1 * p["A2"] * p["A3"]
        st = F.status("membrane.partial")
        note = "INDICATIVE — replace with CEN/TS 19102 / NA values" if st == "U" else "project values"
        return f / k, (f"γM {p['gM']} × A0 {p['A0']} × A1 {A1} × A2 {p['A2']} × A3 {p['A3']} = {k:.2f} "
                       f"[{st}] ({note})")
    raise ValueError(method)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list library materials")
    ap.add_argument("--material", help="library key (see --list)")
    ap.add_argument("--fw", type=float, help="warp strip tensile strength [kN/m]")
    ap.add_argument("--ff", type=float, help="weft strip tensile strength [kN/m]")
    ap.add_argument("--family", default=None, help="PES/PVC | glass/PTFE | other (for --method partial)")
    ap.add_argument("--nw", type=float, help="max warp stress from analysis [kN/m]")
    ap.add_argument("--nf", type=float, help="max weft stress from analysis [kN/m]")
    ap.add_argument("--nmin", type=float, default=None, help="min principal stress (slack check) [kN/m]")
    ap.add_argument("--case", choices=list(CASES), default="wind")
    ap.add_argument("--method", choices=["factor", "fm", "japan", "partial"], default="factor")
    ap.add_argument("--sf-short", type=float, default=None, help="override short-term stress factor")
    ap.add_argument("--sf-long", type=float, default=None, help="override long-term stress factor")
    ap.add_argument("--factors", default=None, help="project code-factor file (overrides register)")
    ap.add_argument("--fm-combo", default="P+D+W", choices=["P+D", "P+D+S", "P+D+W", "P+D+T", "P+D+L", "P+D+R"])
    ap.add_argument("--seam-eff", type=float, default=None, help="seam strength / fabric strength (default register)")
    ap.add_argument("--seam-dir", choices=["warp", "weft", "both"], default="both",
                    help="which stress acts ACROSS seams (seams usually run in warp -> weft stress crosses)")
    ap.add_argument("--prestress", type=float, nargs=2, metavar=("PW", "PF"),
                    help="warp & weft prestress [kN/m] for level advice")
    ap.add_argument("--envelope", default=None, help="run_cases.py _envelope.json: check every case (warp/weft max)")
    ap.add_argument("--tear", type=float, nargs=2, metavar=("A_TEST", "N_TEST"),
                    help="slit-tear test: slit length [mm] and critical stress [kN/m] -> tear propagation check")
    ap.add_argument("--defect", type=float, default=50.0, help="design slit/defect length [mm] for --tear")
    ap.add_argument("--curvature", type=float, nargs=2, metavar=("R_RES", "R_OTH"),
                    help="radii [m] of the direction resisting the load and of the other direction (hand estimate)")
    ap.add_argument("--p", type=float, default=0.0, help="surface load for --curvature [kN/m2]")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    if a.seam_eff is None:
        a.seam_eff = F.get("membrane.seam_efficiency")

    lib = load_lib()
    if a.list:
        print(f"{'key':<28}{'family':<16}{'fw':>6}{'ff':>6}  status")
        for k, m in lib["materials"].items():
            print(f"{k:<28}{m['family']:<16}{m['fw']:>6}{m['ff']:>6}  {m['status']}")
        return
    family = a.family or "other"
    if a.material:
        m = lib["materials"].get(a.material)
        if not m:
            sys.exit(f"unknown material {a.material}; use --list")
        fw, ff, family = m["fw"], m["ff"], a.family or m["family"]
        print(f"Material {a.material}: {family}, fw/ff = {fw}/{ff} kN/m  [{m['status']}: {m['source']}]")
    else:
        if a.fw is None or a.ff is None:
            sys.exit("give --material or --fw/--ff")
        fw, ff = a.fw, a.ff
        print(f"Material: fw/ff = {fw}/{ff} kN/m ({family})")

    if a.prestress:
        pw, pf = a.prestress
        print(f"\nPrestress {pw}/{pf} kN/m = {100 * pw / fw:.1f} % / {100 * pf / ff:.1f} % of strength")
        rng = lib["family_defaults"].get(family, {}).get("prestress_kN_m", "n/a")
        print(f"  typical range for {family}: {rng} kN/m; rule of thumb ~1.5–3 % of UTS")
        if min(pw / fw, pf / ff) < 0.01:
            print("  LOW: risk of wrinkling / flutter / ponding — raise prestress or curvature")
        if max(pw / fw, pf / ff) > 0.05:
            print("  HIGH: creep, relaxation and tear risk; heavy boundary forces")
        ratio = max(pw, pf) / min(pw, pf)
        if ratio > 3:
            print(f"  warp/weft ratio {ratio:.1f} is extreme — anisotropic form-finding needs URS / checking")

    if a.curvature:
        Rr, Ro = a.curvature
        n0r, n0o = (a.prestress if a.prestress else (2.0, 2.0))
        n_res = n0r + a.p * Rr
        n_oth = n0o - a.p * Ro
        print(f"\nCurvature estimate (Laplace n1/R1 + n2/R2 = p, bounds): p = {a.p} kN/m², "
              f"R_resisting = {Rr} m, R_other = {Ro} m")
        print(f"  resisting direction  ≤ n0 + p·R = {n_res:.2f} kN/m (upper bound, other direction keeps prestress)")
        print(f"  other direction      ≥ n0 − p·R = {n_oth:.2f} kN/m (lower bound)"
              + ("  -> may go SLACK: raise prestress or curvature" if n_oth <= 0 else ""))
        print("  (hand sizing only; confirm with the non-linear analysis)")
        if a.nw is None and a.nf is None:
            a.nw = max(n_res, 0.0)

    if a.tear:
        at, nt = a.tear
        n_crit = nt * math.sqrt(at / a.defect)       # LEFM-type scaling σ_c ∝ 1/√a from the slit test
        gt = F.get("membrane.tear_factor")
        n_dem = max(v for v in (a.nw, a.nf) if v is not None) if (a.nw or a.nf) else None
        print(f"\nTear propagation: slit test {at:g} mm @ {nt:g} kN/m -> critical stress for a {a.defect:g} mm "
              f"defect ≈ {n_crit:.2f} kN/m (scaled ∝ 1/√a); allowable = /{gt:g} [{F.status('membrane.tear_factor')}]"
              f" = {n_crit / gt:.2f} kN/m")
        if n_dem is not None:
            u = n_dem / (n_crit / gt)
            print(f"  design stress {n_dem:.2f} kN/m -> util {u:.2f}" + ("  <-- FAIL" if u > 1 else "  OK"))

    if a.envelope:
        with open(a.envelope) as fh:
            env = json.load(fh)
        print(f"\nEnvelope check ({a.envelope}), method '{a.method}':")
        print(f"{'case':<14}{'dur':>6}{'warp':>8}{'weft':>8}{'u fabric':>10}{'u seam':>8}")
        worst_all = 0.0
        for r in env["summary"]:
            dur = r.get("duration", "short")
            case = "wind" if dur == "short" else "snow"
            if r["case"].upper() in ("PS", "PRESTRESS"):
                case = "prestress"
            nw_, nf_ = r.get("warp_max") or 0.0, r.get("weft_max") or 0.0
            aw, _ = allowable(fw, a.method, case, family, a.sf_short, a.sf_long,
                              "P+D" if case == "prestress" else ("P+D+W" if case == "wind" else "P+D+S"))
            af, _ = allowable(ff, a.method, case, family, a.sf_short, a.sf_long,
                              "P+D" if case == "prestress" else ("P+D+W" if case == "wind" else "P+D+S"))
            uf = max(nw_ / aw, nf_ / af)
            us = uf / a.seam_eff
            worst_all = max(worst_all, us)
            print(f"{r['case']:<14}{dur:>6}{nw_:8.2f}{nf_:8.2f}{uf:10.2f}{us:8.2f}" + ("  <-- FAIL" if us > 1 else ""))
        print(f"Governing (seams, eff {a.seam_eff:g}): {worst_all:.2f} -> {'OK' if worst_all <= 1 else 'NOT OK'}")
        if a.method != "partial" and any(abs(r.get("factor", 1.0) - 1.0) > 1e-9 for r in env["summary"]):
            print("WARNING: some cases were run with load factors ≠ 1, but global stress-factor methods "
                  "(factor/fm/japan) expect CHARACTERISTIC loads -> safety counted twice (conservative). "
                  "Run characteristic cases for these methods, or use --method partial with factored cases.")

    if family == "ETFE" and a.material and (a.nw or a.nf):
        m = lib["materials"][a.material]
        g = F.get("membrane.etfe_gamma")
        s_ = max(v for v in (a.nw, a.nf) if v) / m["t_mm"]  # kN/m / mm = MPa
        print(f"\nETFE stress check: σ = n/t = {s_:.1f} MPa vs f_y1/γ = {m['fy1_MPa']}/{g} = {m['fy1_MPa'] / g:.1f} MPa "
              f"[{F.status('membrane.etfe_gamma')}] -> util {s_ / (m['fy1_MPa'] / g):.2f} "
              "(temperature and load duration reduce f_y — see TensiNet App. A5)")
        return

    if a.nw is None and a.nf is None:
        return
    rows = []
    worst = 0.0
    for name, n, f in (("warp", a.nw, fw), ("weft", a.nf, ff)):
        if n is None:
            continue
        al, basis = allowable(f, a.method, a.case, family, a.sf_short, a.sf_long, a.fm_combo)
        rows.append((f"fabric {name}", n, al, basis))
        if a.seam_dir in (name, "both"):
            al_s, _ = allowable(f * a.seam_eff, a.method, a.case, family, a.sf_short, a.sf_long, a.fm_combo)
            rows.append((f"seam (stress {name}, eff {a.seam_eff:g})", n, al_s, basis))
    print(f"\nCheck — case '{a.case}' ({CASES[a.case]}-term), method '{a.method}'")
    print(f"{'item':<34}{'n [kN/m]':>10}{'n_all':>9}{'util':>7}  basis")
    for item, n, al, basis in rows:
        u = n / al
        worst = max(worst, u)
        print(f"{item:<34}{n:10.2f}{al:9.2f}{u:7.2f}  {basis}" + ("  <-- FAIL" if u > 1 else ""))
    if a.nmin is not None:
        print(f"{'no-slack (min principal stress)':<34}{a.nmin:10.2f}{'> 0':>9}"
              + ("   OK" if a.nmin > 0 else "   SLACK/WRINKLING -> check SLS appearance, flutter, ponding"))
    print(f"Governing utilisation {worst:.2f} -> {'OK' if worst <= 1 else 'NOT OK'}")
    print("Also check: tear propagation at critical defect, corner/clamp stress concentrations, "
          "ponding under deformed shape, strength at elevated temperature (seams).")
    return worst


if __name__ == "__main__":
    main(sys.argv[1:])
