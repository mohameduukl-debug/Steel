#!/usr/bin/env python3
"""Fatigue check (Palmgren–Miner) for steel details and tension components.

Steel details (EN 1993-1-9): detail category Δσ_C at 2×10⁶ cycles, slope m1 = 3 to N = 5×10⁶
(Δσ_D = 0.737 Δσ_C), m2 = 5 to N = 10⁸ (Δσ_L = 0.549 Δσ_D = 0.405 Δσ_C, cut-off). Shear: m = 5 to 10⁸,
Δτ_L = 0.457 Δτ_C. Combined normal + shear: Eq. (8.3) with Annex A.6 equivalents = D_σ + D_τ ≤ 1.
Values from the factor register.
Tension components (EN 1993-1-11 Fig. 9.1): slope m1 = 4 down to Δσ_C at the knee N = 2×10⁶, then m2 = 6, no
cut-off (register fatigue_cables); --single-slope keeps m1 beyond the knee (conservative, the former behaviour).
Use the supplier's tested fatigue data when available.

Design: γFf·Δσ_i against Δσ_R(N)/γMf (γMf from EN 1993-1-9 Table 3.1: assessment method and
consequence class). Damage D = Σ n_i / N_i ≤ 1.

Examples
  python3 fatigue_check.py --category 71 --spectrum 40:1e6 --spectrum 25:5e6          # welded lug detail 71
  python3 fatigue_check.py --cable spiral_socket --spectrum 60:2e6                      # cable, category from register
  python3 fatigue_check.py --category 90 --spectrum 30:1e8 --method damage-tolerant --consequence low
  python3 fatigue_check.py --category 90 --spectrum 60:1.5e6 --shear-category 70 --shear-spectrum 60:1.5e6 \
        --method damage-tolerant --consequence high        # normal + shear, combined Eq. (8.3)
Stress ranges in MPa (on the metallic area for cables); cycles as numbers (1e6 etc.).
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as CF  # noqa: E402


def cycles_steel(ds, dsC):
    """endurance N for stress range ds (already including γ factors) on the EN 1993-1-9 curve."""
    m1, m2 = CF.get("fatigue_EN1993_1_9.m1"), CF.get("fatigue_EN1993_1_9.m2")
    dsD = CF.get("fatigue_EN1993_1_9.D_over_C") * dsC
    dsL = CF.get("fatigue_EN1993_1_9.L_over_C") * dsC
    if ds <= dsL:
        return math.inf
    if ds >= dsD:
        return 2e6 * (dsC / ds) ** m1
    return 5e6 * (dsD / ds) ** m2


def cycles_single(ds, dsC, m):
    return 2e6 * (dsC / ds) ** m if ds > 0 else math.inf


def cycles_shear(dt, dtC):
    """EN 1993-1-9 7.1(2) shear curve: Δτ^5 N = Δτ_C^5 2e6 down to the cut-off Δτ_L = 0.457 Δτ_C at 1e8."""
    m = CF.get("fatigue_EN1993_1_9.m_shear")
    if dt <= CF.get("fatigue_EN1993_1_9.tauL_over_C") * dtC:
        return math.inf
    return 2e6 * (dtC / dt) ** m


def check_shear(spectrum, dtC, gMf, gFf=1.0):
    """Palmgren–Miner damage for shear stress ranges (EN 1993-1-9 Annex A.5, Eq. A.1)."""
    rows, D = [], 0.0
    for dt, n in spectrum:
        N = cycles_shear(gFf * dt * gMf, dtC)
        d = n / N if N != math.inf else 0.0
        D += d
        rows.append((dt, n, N, d))
    return D, rows


def combined(D_sigma, D_tau):
    """EN 1993-1-9 8(3) Eq. (8.3) with the damage-equivalent ranges of Annex A.6 (Eq. A.3): the terms
    (γFf Δσ_E,2/(Δσ_C/γMf))^3 and (γFf Δτ_E,2/(Δτ_C/γMf))^5 equal D_σ and D_τ, so (8.3) reads D_σ + D_τ ≤ 1.
    (Exact for spectra on the m = 3 branch; on the m = 5 branch Δσ_E,2 from D^(1/3) is conservative.)"""
    return D_sigma + D_tau


def cycles_bilinear(ds, dsC, m1, m2, N_knee=2e6):
    """EN 1993-1-11 Fig. 9.1 type curve: Δσ^m1 N = Δσ_C^m1 2e6 above the knee (N ≤ N_knee), slope m2 below,
    continuous at the knee, no cut-off."""
    if ds <= 0:
        return math.inf
    ds_k = dsC * (2e6 / N_knee) ** (1 / m1)
    if ds >= ds_k:
        return 2e6 * (dsC / ds) ** m1
    return N_knee * (ds_k / ds) ** m2


def check(spectrum, dsC, gMf, gFf=1.0, cable_m=None, cable_m2=None, N_knee=2e6):
    rows = []
    D = 0.0
    for ds, n in spectrum:
        dse = gFf * ds * gMf          # compare γFf·Δσ·γMf with the characteristic curve
        if cable_m and cable_m2:
            N = cycles_bilinear(dse, dsC, cable_m, cable_m2, N_knee)
        elif cable_m:
            N = cycles_single(dse, dsC, cable_m)
        else:
            N = cycles_steel(dse, dsC)
        d = n / N if N != math.inf else 0.0
        D += d
        rows.append((ds, n, N, d))
    return D, rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--category", type=float, help="EN 1993-1-9 detail category Δσ_C [MPa]")
    ap.add_argument("--cable", choices=["spiral_socket", "parallel_wire", "threaded_bar"],
                    help="tension component category from the register (fatigue_cables)")
    ap.add_argument("--spectrum", action="append", default=[], help="Δσ:n (MPa:cycles), repeatable")
    ap.add_argument("--shear-category", type=float, default=None, help="EN 1993-1-9 shear detail category Δτ_C [MPa]")
    ap.add_argument("--shear-spectrum", action="append", default=[], help="Δτ:n (MPa:cycles), repeatable")
    ap.add_argument("--method", choices=["safe-life", "damage-tolerant"], default="safe-life")
    ap.add_argument("--consequence", choices=["high", "low"], default="high")
    ap.add_argument("--gFf", type=float, default=1.0)
    ap.add_argument("--factors", default=None)
    ap.add_argument("--sensitivity", action="store_true",
                    help="--cable: damage at both ends of the ranges of Δσ_C and m")
    ap.add_argument("--single-slope", action="store_true",
                    help="--cable: keep slope m1 beyond the knee (no m2 = 6 branch; conservative)")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    key = f"fatigue_EN1993_1_9.gMf_{'safe_life' if a.method == 'safe-life' else 'damage_tol'}_{a.consequence}"
    gMf = CF.get(key)
    spectrum = [tuple(map(float, s.split(":"))) for s in a.spectrum]
    if not spectrum and not a.shear_spectrum:
        ap.error("give --spectrum and/or --shear-spectrum")
    print("Assumptions: nominal stress ranges at the detail (no SCF unless included), linear Palmgren–Miner "
          "summation (EN 1993-1-9 Annex A), stress ranges multiplied by γFf and by γMf instead of dividing Δσ_C.")
    if a.shear_spectrum and not spectrum:
        return shear_part(a, gMf, 0.0)
    if a.cable:
        k = {"spiral_socket": "dsC_spiral_socket", "parallel_wire": "dsC_parallel_wire",
             "threaded_bar": "dsC_threaded_bar"}[a.cable]
        dsC = CF.get(f"fatigue_cables.{k}")
        m = CF.get("fatigue_cables.m_rope") if a.cable != "threaded_bar" else None
        m2 = None if (a.single_slope or not m) else CF.get("fatigue_cables.m2_rope")
        Nk = CF.get("fatigue_cables.N_knee_rope") if m2 else 2e6
        if not m:
            txt = ", EN 1993-1-9 curve"
        elif m2:
            txt = (f", m1 = {m} [{CF.status('fatigue_cables.m_rope')}] to the knee at {Nk:.0e}, m2 = {m2} "
                   f"[{CF.status('fatigue_cables.m2_rope')}] beyond (EN 1993-1-11 Fig. 9.1), no cut-off")
        else:
            txt = f", single slope m = {m} [{CF.status('fatigue_cables.m_rope')}] (--single-slope), no cut-off"
        print(f"Tension component '{a.cable}': Δσ_C = {dsC} MPa [{CF.status('fatigue_cables.' + k)}]" + txt)
    else:
        if a.category is None:
            ap.error("give --category or --cable")
        dsC, m, m2, Nk = a.category, None, None, 2e6
        print(f"EN 1993-1-9 detail category {dsC:g}: m1/m2 = 3/5 [{CF.status('fatigue_EN1993_1_9.m1')}], "
              f"Δσ_D = {0.737 * dsC:.1f}, Δσ_L = {0.405 * dsC:.1f} MPa")
    print(f"γMf = {gMf} ({a.method}, {a.consequence} consequence) [{CF.status(key)}], γFf = {a.gFf}")
    D, rows = check(spectrum, dsC, gMf, a.gFf, m, m2, Nk)
    print(f"{'Δσ [MPa]':>10}{'n':>12}{'N_R':>14}{'n/N':>10}")
    for ds, n, N, d in rows:
        print(f"{ds:10.1f}{n:12.3g}{(f'{N:.3g}' if N != math.inf else 'inf (≤ cut-off)'):>14}{d:10.3f}")
    print(f"Damage D = {D:.3f} -> {'OK' if D <= 1 else 'NOT OK'} (Palmgren–Miner)")
    if a.sensitivity and a.cable:
        cable_sensitivity(spectrum, k, gMf, a.gFf, m, m2, Nk)
    if a.shear_spectrum:
        return shear_part(a, gMf, D)
    return D


def shear_part(a, gMf, D_sigma):
    if a.shear_category is None:
        raise SystemExit("--shear-spectrum needs --shear-category (Δτ_C)")
    spec = [tuple(map(float, s.split(":"))) for s in a.shear_spectrum]
    Dt, rows = check_shear(spec, a.shear_category, gMf, a.gFf)
    print(f"Shear detail category Δτ_C = {a.shear_category:g}: m = 5 [{CF.status('fatigue_EN1993_1_9.m_shear')}], "
          f"cut-off Δτ_L = {CF.get('fatigue_EN1993_1_9.tauL_over_C') * a.shear_category:.1f} MPa at 1e8")
    print(f"{'Δτ [MPa]':>10}{'n':>12}{'N_R':>14}{'n/N':>10}")
    for dt, n, N, d in rows:
        print(f"{dt:10.1f}{n:12.3g}{(f'{N:.3g}' if N != math.inf else 'inf (≤ cut-off)'):>14}{d:10.3f}")
    print(f"Damage D_τ = {Dt:.3f} -> {'OK' if Dt <= 1 else 'NOT OK'}")
    if D_sigma:
        c = combined(D_sigma, Dt)
        print(f"Combined Eq. (8.3) with Annex A.6 equivalent ranges: D_σ + D_τ = {c:.3f} -> "
              f"{'OK' if c <= 1 else 'NOT OK'}")
        return c
    return Dt


def cable_sensitivity(spectrum, k, gMf, gFf, m, m2=None, N_knee=2e6):
    """D (as utilisation) over the ranges of the cable fatigue factors, one at a time and combined.
    m2 = None: single-slope curve (former behaviour); otherwise bilinear with the knee at N_knee."""
    out = []
    print("Sensitivity to uncertain factors:")
    res = CF.sensitivity(lambda v: check(spectrum, v, gMf, gFf, m, m2, N_knee)[0], f"fatigue_cables.{k}")
    print(CF.sens_line("Δσ_C (D as util)", res))
    out.append(res)
    if m:
        dsC = CF.get(f"fatigue_cables.{k}")
        res = CF.sensitivity(lambda v: check(spectrum, dsC, gMf, gFf, v, m2, N_knee)[0], "fatigue_cables.m_rope")
        print(CF.sens_line("slope m (D as util)", res))
        out.append(res)
        lo = CF.frange(f"fatigue_cables.{k}")[0]
        worst = max(check(spectrum, lo, gMf, gFf, mm, m2, N_knee)[0] for mm in CF.frange("fatigue_cables.m_rope"))
        print(f"  Δσ_C at its low end with the worse m: D = {worst:.3f} -> "
              + ("still OK" if worst <= 1 else "NOT OK: get the supplier's fatigue test data"))
    return out


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
