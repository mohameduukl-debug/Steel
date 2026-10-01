#!/usr/bin/env python3
"""Fatigue check (Palmgren–Miner) for steel details and tension components.

Steel details (EN 1993-1-9): detail category Δσ_C at 2×10⁶ cycles, slope m1 = 3 to N = 5×10⁶
(Δσ_D = 0.737 Δσ_C), m2 = 5 to N = 10⁸ (Δσ_L = 0.405 Δσ_C, cut-off). Values from the factor register.
Tension components (EN 1993-1-11 type curve): single slope m (register, [U]) from Δσ_C at 2×10⁶, no
cut-off (conservative) — use the supplier's tested fatigue data when available.

Design: γFf·Δσ_i against Δσ_R(N)/γMf (γMf from EN 1993-1-9 Table 3.1: assessment method and
consequence class). Damage D = Σ n_i / N_i ≤ 1.

Examples
  python3 fatigue_check.py --category 71 --spectrum 40:1e6 --spectrum 25:5e6          # welded lug detail 71
  python3 fatigue_check.py --cable spiral_socket --spectrum 60:2e6                      # cable, category from register
  python3 fatigue_check.py --category 90 --spectrum 30:1e8 --method damage-tolerant --consequence low
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


def check(spectrum, dsC, gMf, gFf=1.0, cable_m=None):
    rows = []
    D = 0.0
    for ds, n in spectrum:
        dse = gFf * ds * gMf          # compare γFf·Δσ·γMf with the characteristic curve
        N = cycles_single(dse, dsC, cable_m) if cable_m else cycles_steel(dse, dsC)
        d = n / N if N != math.inf else 0.0
        D += d
        rows.append((ds, n, N, d))
    return D, rows


KSI = 6.894757


def aisc_fatigue(spectrum, cat):
    """AISC 360-22 Appendix 3: F_SR = (C_f / n)^(1/3) ≥ F_TH (MPa). Variable amplitude: equivalent stress range
    (Σ n_i·Δσ_i³ / Σ n_i)^(1/3) above the threshold (Miner with slope 3); returns (util, rows, F_TH)."""
    Cf_ksi, Fth_ksi = CF.get("fatigue_AISC.categories")[cat]
    Cf, Fth = Cf_ksi * KSI ** 3, Fth_ksi * KSI
    n_tot = sum(n for _, n in spectrum)
    dse = (sum(n * ds ** 3 for ds, n in spectrum) / n_tot) ** (1 / 3)
    FSR = max((Cf / n_tot) ** (1 / 3), Fth)
    rows = [(ds, n, Cf / ds ** 3 if ds > 0 else math.inf) for ds, n in spectrum]
    return dse / FSR, rows, Fth, FSR, dse


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--category", type=float, help="EN 1993-1-9 detail category Δσ_C [MPa]")
    ap.add_argument("--cable", choices=["spiral_socket", "parallel_wire", "threaded_bar"],
                    help="tension component category from the register (fatigue_cables)")
    ap.add_argument("--spectrum", action="append", required=True, help="Δσ:n (MPa:cycles), repeatable")
    ap.add_argument("--method", choices=["safe-life", "damage-tolerant"], default="safe-life")
    ap.add_argument("--consequence", choices=["high", "low"], default="high")
    ap.add_argument("--gFf", type=float, default=1.0)
    ap.add_argument("--factors", default=None)
    ap.add_argument("--code", choices=CF.CODES, default=None, help="US/SA: AISC 360 Appendix 3 (steel details)")
    ap.add_argument("--aisc-cat", choices=["A", "B", "B'", "C", "D", "E", "E'"], default=None,
                    help="AISC detail category (with --code US|SA)")
    ap.add_argument("--sensitivity", action="store_true",
                    help="--cable: damage at both ends of the ranges of the unverified Δσ_C and m")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    code = CF.code(a.code)
    if code != "EU" and not a.cable:
        if not a.aisc_cat:
            ap.error("--code US|SA needs --aisc-cat (AISC Table A-3.1 category)")
        spectrum = [tuple(map(float, s_.split(":"))) for s_ in a.spectrum]
        u, rows, Fth, FSR, dse = aisc_fatigue(spectrum, a.aisc_cat)
        std = "SBC 306 (AISC 360 App. 3 based; 2018 values [U])" if code == "SA" else "AISC 360-22 Appendix 3"
        print(f"{std}: category {a.aisc_cat}, F_TH = {Fth:.1f} MPa [{CF.status('fatigue_AISC.categories')}], "
              "service-load stress ranges (no load or resistance factors)")
        for ds, n, N in rows:
            print(f"  Δσ = {ds:.1f} MPa × {n:.3g} cycles (N at this range {N:.3g})")
        print(f"  equivalent range (cube-root mean) {dse:.1f} MPa vs F_SR = max((C_f/n)^(1/3), F_TH) = {FSR:.1f} MPa "
              f"-> util {u:.2f} {'OK' if u <= 1 else 'NOT OK'}")
        return u
    key = f"fatigue_EN1993_1_9.gMf_{'safe_life' if a.method == 'safe-life' else 'damage_tol'}_{a.consequence}"
    gMf = CF.get(key)
    spectrum = [tuple(map(float, s.split(":"))) for s in a.spectrum]
    if a.cable:
        k = {"spiral_socket": "dsC_spiral_socket", "parallel_wire": "dsC_parallel_wire",
             "threaded_bar": "dsC_threaded_bar"}[a.cable]
        dsC = CF.get(f"fatigue_cables.{k}")
        m = CF.get("fatigue_cables.m_rope") if a.cable != "threaded_bar" else None
        print(f"Tension component '{a.cable}': Δσ_C = {dsC} MPa [{CF.status('fatigue_cables.' + k)}]"
              + (f", single slope m = {m} [{CF.status('fatigue_cables.m_rope')}], no cut-off" if m else ", EN 1993-1-9 curve"))
    else:
        if a.category is None:
            ap.error("give --category or --cable")
        dsC, m = a.category, None
        print(f"EN 1993-1-9 detail category {dsC:g}: m1/m2 = 3/5 [{CF.status('fatigue_EN1993_1_9.m1')}], "
              f"Δσ_D = {0.737 * dsC:.1f}, Δσ_L = {0.405 * dsC:.1f} MPa")
    print(f"γMf = {gMf} ({a.method}, {a.consequence} consequence) [{CF.status(key)}], γFf = {a.gFf}")
    D, rows = check(spectrum, dsC, gMf, a.gFf, m)
    print(f"{'Δσ [MPa]':>10}{'n':>12}{'N_R':>14}{'n/N':>10}")
    for ds, n, N, d in rows:
        print(f"{ds:10.1f}{n:12.3g}{(f'{N:.3g}' if N != math.inf else 'inf (≤ cut-off)'):>14}{d:10.3f}")
    print(f"Damage D = {D:.3f} -> {'OK' if D <= 1 else 'NOT OK'} (Palmgren–Miner)")
    if a.sensitivity and a.cable:
        cable_sensitivity(spectrum, k, gMf, a.gFf, m)
    return D


def cable_sensitivity(spectrum, k, gMf, gFf, m):
    """D (as utilisation) over the ranges of the [U] cable fatigue factors, one at a time and combined."""
    out = []
    print("Sensitivity to uncertain factors:")
    res = CF.sensitivity(lambda v: check(spectrum, v, gMf, gFf, m)[0], f"fatigue_cables.{k}")
    print(CF.sens_line("Δσ_C (D as util)", res))
    out.append(res)
    if m:
        dsC = CF.get(f"fatigue_cables.{k}")
        res = CF.sensitivity(lambda v: check(spectrum, dsC, gMf, gFf, v)[0], "fatigue_cables.m_rope")
        print(CF.sens_line("slope m (D as util)", res))
        out.append(res)
        lo = CF.frange(f"fatigue_cables.{k}")[0]
        worst = max(check(spectrum, lo, gMf, gFf, mm)[0] for mm in CF.frange("fatigue_cables.m_rope"))
        print(f"  Δσ_C at its low end with the worse m: D = {worst:.3f} -> "
              + ("still OK" if worst <= 1 else "NOT OK: get the supplier's fatigue test data"))
    return out


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
