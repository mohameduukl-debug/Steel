#!/usr/bin/env python3
"""Cable schedule generator: fabrication (unstressed) lengths + design checks.

Input: a schedule JSON (see example below) OR a form-finding result
(--from-model sail.json) from which every cable group becomes a schedule line.

For every cable:
  EA              = E · A
  L0 (T_install)  = L_stressed / (1 + F_prestress / EA)            [no load]
  L0 (T_ref)      = L0 / (1 + α (T_install − T_ref))               [what the factory makes]
  L_meas          = L0_ref · (1 + F_meas / EA)   if a measuring load is specified
  clamp marks     = scaled the same way (unstressed position from end A)
  F_Rd (EN)       = F_min · k_e / (1.5 γR)        util = F_ULS / F_Rd
  ASCE 19         = 2.2 · T / (F_min · N_f)
  SLS             = F_SLS / (f_sls · F_uk)
  slack           = F_min_comb > 0

Outputs <out>.csv and <out>.md (paste into the drawing / report).

Schedule JSON example
---------------------
{
 "project": "Demo canopy", "T_ref": 20, "gammaR": 1.0,
 "cables": [
  {"id": "EC-1", "product": "Ronstan-ACS2-GS-20.1", "L_stressed": 10.62,
   "F_prestress": 18, "F_ULS": 95, "F_SLS": 60, "F_min_comb": 9,
   "end_A": "swaged fork", "end_B": "swaged adjustable fork +/-75", "qty": 1,
   "deduct_A_mm": 250, "deduct_B_mm": 250, "clamp_marks": [2.5, 5.0, 7.5]}
 ]
}
L_stressed = node-to-node (theoretical) stressed length along the cable [m];
deduct_*_mm = distance from theoretical node to pin centre (corner-plate
geometry) — the schedule length is PIN-TO-PIN.

Examples
--------
  python3 cable_schedule.py schedule.json --out cable_schedule
  python3 cable_schedule.py --from-model sail.json --product Ronstan-ACS2-GS-20.1 \
      --uls-factor 3.0 --deduct 250 --out sail_cables
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tensile-structures", "scripts"))
import factors as F  # noqa: E402
LIB = os.path.join(HERE, "..", "reference", "cable_products.json")


def products():
    with open(LIB) as fh:
        return json.load(fh)["products"]


def from_model(path, product, uls_factor, sls_factor, deduct):
    with open(path) as fh:
        m = json.load(fh)
    groups = defaultdict(list)
    for e in m["edges"]:
        if e.get("group"):
            groups[e["group"]].append(e)
    cables = []
    for g, es in sorted(groups.items()):
        L = sum(e["length"] for e in es)
        F = sum(e["force"] * e["length"] for e in es) / L  # length-weighted mean prestress force
        Fmax = max(e["force"] for e in es)
        cables.append({"id": g, "product": product, "L_stressed": round(L, 4), "F_prestress": round(F, 2),
                       "F_ULS": round(Fmax * uls_factor, 1), "F_SLS": round(Fmax * sls_factor, 1),
                       "F_min_comb": None, "end_A": "fork (TBC)", "end_B": "adjustable fork (TBC)",
                       "qty": 1, "deduct_A_mm": deduct, "deduct_B_mm": deduct,
                       "note": f"from {os.path.basename(path)}; ULS/SLS = {uls_factor}/{sls_factor} x prestress "
                               "(PLACEHOLDER — replace with enveloped non-linear results)"})
    return {"project": os.path.basename(path), "T_ref": 20.0, "cables": cables}


def compute(s):
    lib = products()
    T_ref = s.get("T_ref", 20.0)
    gR = s.get("gammaR", F.get("cable.gammaR"))
    asce = F.get("cable.asce19_factor")
    fsls = s.get("f_sls", F.get("cable.f_sls"))
    out = []
    for c in s["cables"]:
        p = dict(lib.get(c.get("product", ""), {}))
        p.update({k: v for k, v in c.items() if v is not None})
        for req in ("A", "E", "Fmin", "L_stressed"):
            if req not in p:
                raise SystemExit(f"cable {c.get('id')}: missing '{req}' (give product or explicit value)")
        EA = p["E"] * p["A"]  # kN (E in kN/mm2 * mm2)
        alpha = p.get("alpha", F.get("cable.alpha_carbon"))
        T_inst = p.get("T_install", T_ref)
        Lpin = p["L_stressed"] - (p.get("deduct_A_mm", 0) + p.get("deduct_B_mm", 0)) / 1000
        Fp = p.get("F_prestress", 0.0)
        strain = Fp / EA
        L0 = Lpin / (1 + strain)
        L0ref = L0 / (1 + alpha * (T_inst - T_ref))
        Fmeas = p.get("F_meas")
        Lmeas = L0ref * (1 + Fmeas / EA) if Fmeas else None
        ke = 1.0 if p.get("ke_included") else p.get("ke", 1.0)
        Fuk = p["Fmin"] * ke
        FRd = Fuk / (1.5 * gR)
        if p.get("Fk"):
            FRd = min(FRd, p["Fk"] / gR)
        uls = p.get("F_ULS")
        sls = p.get("F_SLS")
        marks = [round((x - p.get("deduct_A_mm", 0) / 1000) / (1 + strain) / (1 + alpha * (T_inst - T_ref)), 4)
                 for x in p.get("clamp_marks", [])]
        r = {"id": p["id"], "qty": p.get("qty", 1), "type": p.get("type", p.get("product", "")),
             "d_mm": p.get("d"), "A_mm2": p["A"], "EA_kN": round(EA), "Fmin_kN": p["Fmin"], "ke": ke,
             "F_Rd_kN": round(FRd, 1), "F_prestress_kN": Fp, "F_ULS_kN": uls, "F_SLS_kN": sls,
             "util_EN": round(uls / FRd, 3) if uls else None,
             "util_ASCE": round(asce * (sls if sls else uls / 1.4) / (p["Fmin"] * p.get("Nf", 1.0)), 3) if uls else None,
             "util_SLS": round(sls / (fsls * Fuk), 3) if sls else None,
             "slack_ok": (p.get("F_min_comb") is None) or p["F_min_comb"] > 0,
             "L_node_stressed_m": p["L_stressed"], "L_pin_stressed_m": round(Lpin, 4),
             "L0_pin_unstressed_Tref_m": round(L0ref, 4),
             "L_pin_at_Fmeas_m": round(Lmeas, 4) if Lmeas else None,
             "T_ref_C": T_ref, "clamp_marks_unstressed_m": marks,
             "end_A": p.get("end_A", ""), "end_B": p.get("end_B", ""),
             "coating": p.get("coating", ""), "status": p.get("status", ""), "note": p.get("note", "")}
        out.append(r)
    return out


def write(rows, s, out):
    keys = list(rows[0])
    with open(out + ".csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (";".join(map(str, v)) if isinstance(v, list) else v) for k, v in r.items()})
    cols = [("id", "ID"), ("qty", "Qty"), ("type", "Type"), ("d_mm", "Ø mm"), ("Fmin_kN", "F_min kN"),
            ("F_Rd_kN", "F_Rd kN"), ("F_ULS_kN", "F_ULS kN"), ("util_EN", "util EN"),
            ("util_ASCE", "util ASCE"), ("F_prestress_kN", "Prestress kN"),
            ("L_pin_stressed_m", "L pin stressed m"), ("L0_pin_unstressed_Tref_m", "L0 pin unstressed m"),
            ("end_A", "End A"), ("end_B", "End B")]
    with open(out + ".md", "w") as fh:
        fh.write(f"# Cable schedule — {s.get('project', '')}\n\n")
        fh.write("| " + " | ".join(h for _, h in cols) + " |\n")
        fh.write("|" + "---|" * len(cols) + "\n")
        for r in rows:
            fh.write("| " + " | ".join("" if r[k] is None else str(r[k]) for k, _ in cols) + " |\n")
        fh.write(f"\nCode factors: {F.tag('cable.gammaR')}, {F.tag('cable.f_sls')}, "
                 f"{F.tag('cable.asce19_factor')} (V verified-search, C code, U unverified)\n")
        fh.write(f"\nNotes\n\n1. Lengths are PIN-TO-PIN. L0 = unstressed length of the prestretched cable at "
                 f"reference temperature {s.get('T_ref', 20)} °C (EA from supplier E × metallic area).\n"
                 "2. F_Rd = F_min·k_e/(1.5·γR) to EN 1993-1-11 (γR per National Annex); ASCE 19: "
                 "S_d ≥ 2.2·T.\n3. Supplier to confirm E, metallic area, F_min, fittings and length tolerance; "
                 "cables prestretched and clamp positions marked under the stated measuring load.\n"
                 "4. Adjustment range at the adjustable end to cover fabrication + erection tolerance and "
                 "membrane creep re-tensioning.\n")
        for r in rows:
            if r["clamp_marks_unstressed_m"]:
                fh.write(f"\nClamp marks {r['id']} (unstressed, from pin A): {r['clamp_marks_unstressed_m']}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("schedule", nargs="?")
    ap.add_argument("--from-model")
    ap.add_argument("--product", default="Ronstan-ACS2-GS-20.1")
    ap.add_argument("--uls-factor", type=float, default=3.0,
                    help="placeholder ULS force = factor × max prestress force (replace with analysis!)")
    ap.add_argument("--sls-factor", type=float, default=2.0)
    ap.add_argument("--deduct", type=float, default=0.0, help="node-to-pin deduction each end [mm]")
    ap.add_argument("--out", default="cable_schedule")
    ap.add_argument("--list", action="store_true", help="list library products")
    ap.add_argument("--factors", default=None, help="project code-factor file")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    if a.list:
        for k, v in products().items():
            print(f"{k:<24} {v['type']:<34} d={v['d']:<5} Fmin={v['Fmin']:<7} {v['status']}")
        return
    if a.from_model:
        s = from_model(a.from_model, a.product, a.uls_factor, a.sls_factor, a.deduct)
    elif a.schedule:
        with open(a.schedule) as fh:
            s = json.load(fh)
    else:
        ap.error("give a schedule JSON or --from-model")
    rows = compute(s)
    write(rows, s, a.out)
    print(f"{'ID':<8}{'type':<22}{'F_Rd':>8}{'F_ULS':>8}{'utilEN':>8}{'Lpin':>10}{'L0 ref':>10}")
    for r in rows:
        print(f"{r['id']:<8}{str(r['type'])[:21]:<22}{r['F_Rd_kN']:8.1f}{(r['F_ULS_kN'] or 0):8.1f}"
              f"{(r['util_EN'] or 0):8.2f}{r['L_pin_stressed_m']:10.4f}{r['L0_pin_unstressed_Tref_m']:10.4f}"
              + ("" if r["slack_ok"] else "  SLACK!") + ("  FAIL" if (r["util_EN"] or 0) > 1 else ""))
    print(f"Wrote {a.out}.csv and {a.out}.md")
    return rows


if __name__ == "__main__":
    main(sys.argv[1:])
