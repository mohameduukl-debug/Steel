#!/usr/bin/env python3
"""Load combinations and wind velocity pressure for EU / US / Saudi codes (tensile structures).

Sub-commands
  combos      list the combinations of a code system (--code EU|US|SA) for a set:
                uls   EN 1990 6.10 / ASCE 7-22 2.3.1 (LRFD) / SBC 301-18 2.3.2
                asd   ASCE 7-22 2.4.1 (US; SA uses the same forms — SBC 306 itself is LRFD only)
                sls   characteristic combinations (EU) — deflection, ponding, appearance
                membrane  the membrane-check set: EU/stress-factor = characteristic; US/SA = ASCE 55
                      (P + D, P + D + S, P + D + W at ASD level: 0.7S, 0.6W) with the β of each
  make-cases  turn characteristic load cases into factored cases for run_cases.py (one case per
              combination and per wind case); keeps prestress P at γP = 1.0 (it is the form-found state)
  wind        peak / velocity pressure: EN 1991-1-4 (q_p(z) from v_b and terrain category),
              ASCE 7-22 or 7-16 (q_z = 0.613·K_z·K_zt·K_e·V²; K_d applied in the pressure equation),
              SBC 301-18 (ASCE 7-10 form q = 0.613·K_z·K_zt·K_d·V², V ultimate 3-s gust)

Load symbols: D dead (membrane + fittings, small), S snow, W wind (each wind case separately:
W_up, W_down, W000 …), Lr roof live / maintenance, T temperature. Prestress P is in the model.

Characteristic loads file for make-cases (values per run_cases.py keys):
  {"solver": "net", "material": {...},
   "loads": {"D": {"snow": 0.02},
             "S": {"snow": 0.6, "ponding": true},
             "W_up": {"pressure": 0.55},                       # + = uplift (run_cases convention)
             "W_down": {"pressure": -0.35},
             "W090": {"gradient": {"dir_deg": 90, "p_windward": 0.7, "p_leeward": 0.3}},
             "Lr": {"snow": 0.6}}}
  Any key starting with W is a wind case. Combinations that contain W are repeated for every wind case.

Examples
  python3 loads.py combos --code US --set uls
  python3 loads.py combos --code SA --set membrane
  python3 loads.py make-cases loads.json --code EU --set uls --out sail_uls_cases.json
  python3 loads.py wind --code EU --vb 26 --terrain II --z 6
  python3 loads.py wind --code US --V 50 --exposure C --z 6
  python3 loads.py wind --code SA --V 50 --exposure C --z 6

Wind pressure COEFFICIENTS for hypars, cones and saddles are in none of these codes: use wind-tunnel
data, CFD or conservative canopy values (see tensile-analysis). This tool gives the reference pressure.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factors as F  # noqa: E402


# ------------------------------------------------------------ combinations
def combos(code: str, kind: str = "uls"):
    """list of dicts {name, D, S, W, Lr, T, (beta), (dur)} — factors on characteristic actions."""
    if kind == "membrane":
        if code == "EU":
            return [{"name": "P+G", "D": 1.0, "case": "prestress"},
                    {"name": "P+G+S", "D": 1.0, "S": 1.0, "case": "snow"},
                    {"name": "P+G+W", "D": 1.0, "W": 1.0, "case": "wind"},
                    {"name": "P+G+S+0.6W", "D": 1.0, "S": 1.0, "W": F.get("en1990.psi0_wind"), "case": "snow"},
                    {"name": "P+G+W+0.5S", "D": 1.0, "W": 1.0, "S": F.get("en1990.psi0_snow"), "case": "wind"}]
        beta = F.get("asce55.beta")
        out = [{"name": "P+D", "D": 1.0, "beta": beta["P+D"], "combo_type": "P+D"}]
        if code == "US":
            out.append({"name": "P+D+0.7S", "D": 1.0, "S": 0.7, "beta": beta["P+D+S"], "combo_type": "P+D+S"})
        out += [{"name": "P+D+Lr", "D": 1.0, "Lr": 1.0, "beta": beta["P+D+S"], "combo_type": "P+D+S"},
                {"name": "P+D+0.6W", "D": 1.0, "W": 0.6, "beta": beta["P+D+W"], "combo_type": "P+D+W"}]
        return out
    if code == "EU":
        gs, gi, gq = F.get("en1990.gamma_G_sup"), F.get("en1990.gamma_G_inf"), F.get("en1990.gamma_Q")
        p0s, p0w = F.get("en1990.psi0_snow"), F.get("en1990.psi0_wind")
        if kind == "sls":
            return [{"name": "G", "D": 1.0}, {"name": "G+S", "D": 1.0, "S": 1.0}, {"name": "G+W", "D": 1.0, "W": 1.0},
                    {"name": f"G+S+{p0w}W", "D": 1.0, "S": 1.0, "W": p0w},
                    {"name": f"G+W+{p0s}S", "D": 1.0, "W": 1.0, "S": p0s}]
        if kind != "uls":
            raise SystemExit("EU sets: uls, sls, membrane")
        return [{"name": f"{gs}G", "D": gs},
                {"name": f"{gs}G+{gq}S+{gq * p0w:g}W", "D": gs, "S": gq, "W": gq * p0w},
                {"name": f"{gs}G+{gq}S", "D": gs, "S": gq},
                {"name": f"{gs}G+{gq}W+{gq * p0s:g}S", "D": gs, "W": gq, "S": gq * p0s},
                {"name": f"{gi}G+{gq}W", "D": gi, "W": gq},
                {"name": f"{gs}G+{gq}Lr", "D": gs, "Lr": gq}]
    if code == "US":
        key = {"uls": "asce7.combos_lrfd_22", "asd": "asce7.combos_asd_22"}.get(kind)
    else:
        key = {"uls": "sbc.combos_301", "asd": "asce7.combos_asd_22"}.get(kind)
    if not key:
        raise SystemExit(f"{code} sets: uls, asd, membrane")
    lst = [dict(c) for c in F.get(key)["list"]]
    if code == "SA":
        for c in lst:
            if "S" in c:  # SBC 301-18: snow chapter deleted
                c.pop("S")
                c["name"] = c["name"].replace("+0.7S", "").replace("+0.75(0.7S)", "")
    return lst


def combo_source(code, kind):
    if kind == "membrane":
        return ("characteristic (stress-factor / CEN/TS 19102 practice)" if code == "EU"
                else f"ASCE 55 β method at ASD-level loads [{F.status('asce55.beta')}]")
    return {("EU", "uls"): "EN 1990 eq. 6.10 [C]", ("EU", "sls"): "EN 1990 characteristic [C]",
            ("US", "uls"): f"ASCE 7-22 §2.3.1 [{F.status('asce7.combos_lrfd_22')}]",
            ("US", "asd"): f"ASCE 7-22 §2.4.1 [{F.status('asce7.combos_asd_22')}]",
            ("SA", "uls"): f"SBC 301-18 §2.3.2 [{F.status('sbc.combos_301')}] (no snow)",
            ("SA", "asd"): "ASCE 7 ASD forms (SBC 306 is LRFD only) [U]"}[(code, kind)]


# ------------------------------------------------------------ factored cases for run_cases
FIELDS = ("pressure", "snow")


def scale_load(ld, f):
    out = {}
    for k in FIELDS:
        if k in ld:
            out[k] = f * ld[k]
    if "gradient" in ld:
        g = dict(ld["gradient"])
        g["p_windward"] *= f
        g["p_leeward"] *= f
        out["gradient"] = g
    if "zones" in ld:
        out["zones"] = [{"poly": z["poly"], "p": f * z["p"]} for z in ld["zones"]]
    if ld.get("ponding"):
        out["ponding"] = True
    return out


def add_loads(a, b):
    out = dict(a)
    for k in FIELDS:
        if k in b:
            out[k] = out.get(k, 0.0) + b[k]
    for k in ("gradient", "zones"):
        if k in b:
            if k in out:
                raise SystemExit("two load cases with a pressure field (gradient/zones) in one combination")
            out[k] = b[k]
    if b.get("ponding"):
        out["ponding"] = True
    return out


def make_cases(spec, code, kind):
    loads = spec["loads"]
    winds = sorted(k for k in loads if k.upper().startswith("W"))
    cases = [{"name": "PS", "pressure": 0.0, "duration": "long", "combo_type": "P+D"}]
    for c in combos(code, kind):
        variants = winds if c.get("W") else [None]
        if c.get("W") and not winds:
            continue
        for w in variants:
            case = {}
            for sym, f in c.items():
                if sym in ("name", "beta", "combo_type", "case") or not isinstance(f, (int, float)):
                    continue
                key = w if sym == "W" else sym
                if key in loads:
                    case = add_loads(case, scale_load(loads[key], f))
            if not case:
                continue
            nm = c["name"] + (f"[{w}]" if w else "")
            case.update({"name": nm, "factor": 1.0, "duration": "short" if w else "long",
                         "combo": c["name"], "basis": combo_source(code, kind)})
            if "combo_type" in c:
                case["combo_type"] = c["combo_type"]
            elif kind == "membrane" and code == "EU":
                case["combo_type"] = {"prestress": "P+D", "snow": "P+D+S", "wind": "P+D+W"}[c["case"]]
            cases.append(case)
    out = {k: v for k, v in spec.items() if k != "loads"}
    out["cases"] = cases
    out["code"] = code
    out["set"] = kind
    return out


# ------------------------------------------------------------ wind
def qp_en(vb, z, terrain="II", co=1.0):
    """EN 1991-1-4 peak velocity pressure [kN/m²] and its parts."""
    z0, zmin = F.get("en1991_1_4.terrain")[terrain]
    kr = F.get("en1991_1_4.kr_coeff") * (z0 / F.get("en1991_1_4.z0_II")) ** 0.07
    ze = max(z, zmin)
    cr = kr * math.log(ze / z0)
    vm = cr * co * vb
    Iv = F.get("en1991_1_4.kI") / (co * math.log(ze / z0))
    rho = F.get("en1991_1_4.rho_air")
    qp = (1 + F.get("en1991_1_4.peak_factor") * Iv) * 0.5 * rho * vm ** 2 / 1e3
    qb = 0.5 * rho * vb ** 2 / 1e3
    return {"qp": qp, "ce": qp / qb, "cr": cr, "Iv": Iv, "vm": vm, "kr": kr, "qb": qb}


def kz_asce(z, exposure="C", edition="22"):
    key = "asce7.kz_22" if edition == "22" else "asce7.kz_10_16"
    t = F.get(key)
    alpha, zg = t[exposure]
    zz = max(z, F.get("asce7.kz_zmin"))
    return t["coef"] * (zz / zg) ** (2 / alpha)


def q_asce(V, z, exposure="C", edition="22", Kzt=1.0, Ke=1.0, Kd=None):
    """velocity pressure [kN/m²]: 7-22 without K_d (it goes in the pressure equation); 7-16 / 7-10 / SBC with K_d."""
    Kz = kz_asce(z, exposure, edition)
    c = F.get("asce7.q_coef_SI")
    if edition == "22":
        q = c * Kz * Kzt * Ke * V ** 2 / 1e3
        Kd_used = None
    else:
        Kd_used = F.get("asce7.Kd_building") if Kd is None else Kd
        q = c * Kz * Kzt * Kd_used * (Ke if edition == "16" else 1.0) * V ** 2 / 1e3
    return {"q": q, "Kz": Kz, "Kd": Kd_used}


# ------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--factors", default=None)
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("combos")
    c.add_argument("--code", default=None, choices=F.CODES)
    c.add_argument("--set", default="uls", choices=["uls", "asd", "sls", "membrane"])
    m = sp.add_parser("make-cases")
    m.add_argument("loads")
    m.add_argument("--code", default=None, choices=F.CODES)
    m.add_argument("--set", default="uls", choices=["uls", "asd", "sls", "membrane"])
    m.add_argument("--out", required=True)
    w = sp.add_parser("wind")
    w.add_argument("--code", default=None, choices=F.CODES)
    w.add_argument("--z", type=float, required=True, help="reference height [m] (roof height for canopies)")
    w.add_argument("--vb", type=float, help="EU: basic wind velocity v_b = c_dir·c_season·v_b,0 [m/s] (NA map)")
    w.add_argument("--terrain", default="II", choices=["0", "I", "II", "III", "IV"])
    w.add_argument("--co", type=float, default=1.0, help="EU orography factor")
    w.add_argument("--V", type=float, help="US/SA: basic (ultimate) wind speed, 3-s gust at 10 m [m/s]")
    w.add_argument("--exposure", default="C", choices=["B", "C", "D"])
    w.add_argument("--edition", default="22", choices=["22", "16"], help="US: ASCE 7 edition")
    w.add_argument("--Kzt", type=float, default=1.0)
    w.add_argument("--Ke", type=float, default=1.0)
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    code = F.code(getattr(a, "code", None))
    if a.cmd == "combos":
        lst = combos(code, a.set)
        print(f"{F.code_label(code)} — set '{a.set}': {combo_source(code, a.set)}")
        for c_ in lst:
            extra = f"   β = {c_['beta']}" if "beta" in c_ else ""
            print(f"  {c_['name']:<34}" + "  ".join(f"{k}×{v:g}" for k, v in c_.items()
                                                    if k in ("D", "S", "W", "Lr", "T")) + extra)
        if code == "SA":
            print("  SBC 301-18: snow (Ch. 7) and ice (Ch. 10) deleted; wind V is ultimate (factor 1.0 LRFD, 0.6 ASD level). "
                  "2018 values — confirm against SBC 2024 [U].")
        if code != "EU" and a.set == "membrane":
            print("  ASCE 55-10 β calibrated with service-level wind: 0.6W (ASD) used with strength-level wind maps [U inference].")
        return lst
    if a.cmd == "make-cases":
        with open(a.loads) as fh:
            spec = json.load(fh)
        out = make_cases(spec, code, a.set)
        with open(a.out, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"{len(out['cases'])} cases ({F.code_label(code)}, set '{a.set}') -> {a.out}")
        for cs in out["cases"]:
            print(f"  {cs['name']:<40} " + ", ".join(f"{k}={cs[k]:.3g}" for k in FIELDS if k in cs)
                  + (" +gradient" if "gradient" in cs else "") + (" +zones" if "zones" in cs else ""))
        print("Run: python3 ../../tensile-analysis/scripts/run_cases.py model.json " + a.out)
        return out
    # wind
    if code == "EU":
        if a.vb is None:
            ap.error("EU wind needs --vb")
        r = qp_en(a.vb, a.z, a.terrain, a.co)
        print(f"EN 1991-1-4: v_b = {a.vb} m/s, terrain {a.terrain}, z = {a.z} m [C]")
        print(f"  k_r = {r['kr']:.4f}, c_r = {r['cr']:.3f}, v_m = {r['vm']:.2f} m/s, I_v = {r['Iv']:.3f}")
        print(f"  q_b = {r['qb']:.3f} kN/m², c_e = {r['ce']:.3f}  ->  q_p(z) = {r['qp']:.3f} kN/m²")
        print("  w = q_p·c_pe (and c_f / c_p,net for canopies); NA values (c_dir, c_season, z0) may differ.")
        return r
    if a.V is None:
        ap.error("US/SA wind needs --V")
    if code == "US":
        r = q_asce(a.V, a.z, a.exposure, a.edition, a.Kzt, a.Ke)
        print(f"ASCE 7-{a.edition}: V = {a.V} m/s (ultimate, risk-category map), exposure {a.exposure}, z = {a.z} m "
              f"[{F.status('asce7.kz_22' if a.edition == '22' else 'asce7.kz_10_16')}]")
        if a.edition == "22":
            print(f"  K_z = {r['Kz']:.3f}, K_zt = {a.Kzt}, K_e = {a.Ke}  ->  q_z = {r['q']:.3f} kN/m² "
                  f"(K_d = {F.get('asce7.Kd_building')} goes in p = q·K_d·G·C_N for open buildings)")
        else:
            print(f"  K_z = {r['Kz']:.3f}, K_d = {r['Kd']}  ->  q_z = {r['q']:.3f} kN/m²")
    else:
        r = q_asce(a.V, a.z, a.exposure, "10", a.Kzt)
        print(f"SBC 301-18 (ASCE 7-10 form): V = {a.V} m/s ultimate 3-s gust, exposure {a.exposure}, z = {a.z} m "
              f"[{F.status('sbc.wind_basis')}]")
        print(f"  K_z = {r['Kz']:.3f}, K_zt = {a.Kzt}, K_d = {r['Kd']}  ->  q_z = {r['q']:.3f} kN/m²")
        print("  KSA RC II speeds ≈ 46–52 m/s (Riyadh ≈ 50, Jeddah ≈ 46–48; read from SBC maps — use the official "
              "figure). 2018 values: confirm against SBC 2024 [U].")
    print("  Strength-level q: LRFD factor 1.0 on W, ASD 0.6W.")
    return r


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
