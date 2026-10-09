#!/usr/bin/env python3
"""Foundations and ground anchors for masts, tie-backs and low points (preliminary, EN 1997 EQU/GEO style).

Sub-commands
  block    concrete gravity block / deadman (optionally with soil cover) under a design pull
           (uplift V, horizontal H at height h_a above the base): uplift (EQU), sliding (GEO),
           overturning about the toe (EQU) and bearing with effective width B' = B − 2e
  helical  helical (screw) anchor: ultimate tension from installation torque Q_u = K_t·T,
           allowable = Q_u / FS; compares with the design pull (proof-load test required).
           K_t by shaft (--shaft SS5|SS175|RS2875|RS3500|RS4500) from ICC-ES ESR-2794; FS ≥ 2.0 (ESR-2794 / IBC).

Loads are DESIGN values from the factored combination unless you give --unfactored (then
γ_G,dst / γ_Q,dst from the factor register are applied to the pull). Resisting self-weight is
multiplied by γ_G,stb (register, EN 1997 EQU). Geotechnical parameters (μ, bearing resistance)
are project inputs from the geotechnical report.

Examples
  python3 foundation_check.py block --B 2.0 --L 2.0 --D 1.2 --V 110 --H 85 --ha 0.3 --mu 0.45 --qRd 200
  python3 foundation_check.py helical --T 12 --pull 120        # T kNm installation torque
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as CF  # noqa: E402


def block(B, L, D, V, H, ha, mu, qRd, cover=0.0, gamma_soil=18.0, unfactored=False, var_share=1.0):
    """rows (uplift, sliding, overturning, bearing, eccentricity) and info. Pull V up, H horizontal at height D + ha
    above the base, applied on the block axis. Bearing: worst of γ_G,sup and γ_G,inf on the self-weight (DA2)."""
    gs = CF.get("geotech.gamma_G_stb")
    gd = CF.get("geotech.gamma_Q_dst") if var_share >= 0.5 else CF.get("geotech.gamma_G_dst")
    gRh = CF.get("geotech.gamma_R_h")
    gc = CF.get("geotech.gamma_conc")
    if unfactored:
        V, H = V * gd, H * gd
    W = B * L * D * gc + B * L * cover * gamma_soil          # kN
    Wd = gs * W
    rows = []
    rows.append(("uplift: V_d ≤ γ_G,stb·W  [kN]", V, Wd, "EN 1997 EQU"))
    N = Wd - V                                               # net downward force on the base
    Hr = max(N, 0.0) * mu / gRh
    rows.append((f"sliding: H_d ≤ (γ_stb W − V)·μ/γ_R,h (μ={mu})  [kN]", H, Hr, "EN 1997 GEO (DA2)"))
    # overturning about the toe (pull directed away from the toe side): M_dst = H·(D + ha) + V·B/2
    Mdst = H * (D + ha) + V * B / 2
    Mstb = Wd * B / 2
    rows.append(("overturning about toe: M_dst ≤ M_stb  [kNm]", Mdst, Mstb, "EN 1997 EQU"))
    # bearing (GEO, DA2): self-weight unfavourable (γ_G,sup) or favourable (γ_G,inf), whichever governs;
    # effective width B' = B − 2e (EN 1997-1 Annex D, Meyerhof)
    worst = None
    for g in (CF.get("geotech.gamma_G_sup"), CF.get("geotech.gamma_G_inf")):
        Nb = g * W - V
        if Nb <= 0:
            continue
        e = H * (D + ha) / Nb          # V acts on the block axis: only H gives a moment about the base centre
        Bp = B - 2 * e
        q = Nb / (Bp * L) if Bp > 0 else math.inf
        if worst is None or q > worst[0]:
            worst = (q, e, Bp, g, Nb)
    info = {"W_kN": W, "N_kN": N}
    if worst:
        q, e, Bp, g, Nb = worst
        rows.append((f"bearing: q on B'={Bp:.2f} m (e={e:.2f} m, γ_G={g})  [kPa]", q, qRd, "EN 1997 GEO (q_Rd from GI)"))
        rows.append(("eccentricity e ≤ B/3 (EN 1997-1 6.5.4, else special precautions)  [m]", e, B / 3,
                     "EN 1997-1 6.5.4"))
        info.update({"q_kPa": q, "e_m": e, "B_eff_m": Bp, "N_bearing_kN": Nb})
        if e > B / 6:
            print(f"NOTE: e = {e:.2f} m > B/6 = {B / 6:.2f} m: base partly lifts off under this combination "
                  "(acceptable for transient wind; avoid for permanent loads)")
    return rows, info


def helical(T, pull, shaft=None, FS=None):
    """T installation torque [kNm] (average of the last three readings for tension), pull design tension [kN]."""
    Kt = CF.get("geotech.helical_Kt_by_shaft")[shaft] if shaft else CF.get("geotech.helical_Kt_per_m")
    FS = CF.get("geotech.helical_FS") if FS is None else max(FS, CF.get("geotech.helical_FS"))
    Qu = Kt * T
    return ([("helical anchor: pull ≤ Q_u/FS  [kN]", pull, Qu / FS, f"Q_u = K_t·T = {Kt}·{T} = {Qu:.0f} kN, FS {FS}")],
            {"Qu": Qu, "Kt": Kt, "FS": FS, "Qall": Qu / FS})


def report(rows):
    print(f"{'check':<58}{'demand':>10}{'capacity':>10}{'util':>7}  ref")
    w = 0.0
    for n, d, c, ref in rows:
        u = d / c if c else math.inf
        w = max(w, u)
        print(f"{n:<58}{d:10.2f}{c:10.2f}{u:7.2f}  {ref}" + ("  <-- FAIL" if u > 1 else ""))
    print(f"Governing utilisation {w:.2f} -> {'OK' if w <= 1 else 'NOT OK'}")
    return w


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--factors", default=None)
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("block")
    b.add_argument("--B", type=float, required=True, help="block width in pull direction [m]")
    b.add_argument("--L", type=float, required=True, help="block length [m]")
    b.add_argument("--D", type=float, required=True, help="block depth [m]")
    b.add_argument("--cover", type=float, default=0.0, help="soil cover on top [m]")
    b.add_argument("--V", type=float, required=True, help="uplift [kN]")
    b.add_argument("--H", type=float, default=0.0, help="horizontal pull [kN]")
    b.add_argument("--ha", type=float, default=0.0, help="height of pull point above block top [m]")
    b.add_argument("--mu", type=float, default=0.45, help="base friction coefficient (tan δ) from GI")
    b.add_argument("--qRd", type=float, default=200.0, help="design bearing resistance [kPa] from GI")
    b.add_argument("--unfactored", action="store_true")
    h = sp.add_parser("helical")
    h.add_argument("--T", type=float, required=True, help="final installation torque [kNm]")
    h.add_argument("--pull", type=float, required=True, help="design tension [kN]")
    h.add_argument("--shaft", choices=["SS5", "SS175", "RS2875", "RS3500", "RS4500"], default=None,
                   help="CHANCE shaft type for K_t (ESR-2794); default square shaft 32.8 m^-1")
    h.add_argument("--FS", type=float, default=None, help="factor of safety (not below the register value 2.0)")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    if a.cmd == "block":
        print(f"Factors: {CF.tag('geotech.gamma_G_stb')}, {CF.tag('geotech.gamma_R_h')}, {CF.tag('geotech.gamma_conc')}, "
              f"{CF.tag('geotech.gamma_G_sup')}, {CF.tag('geotech.gamma_G_inf')}")
        print("Assumptions: rigid block, pull applied on the block axis at height D + ha above the base; EQU γ_G,stb on\n"
              "  the self-weight for uplift, overturning about the toe and (conservatively) sliding; sliding R = (γW − V)·μ/γ_R,h\n"
              "  (drained, μ = tan δ from GI, passive earth pressure ignored); bearing with B' = B − 2e (EN 1997-1 Annex D)\n"
              "  against q_Rd from the GI; no soil cover shear, no suction, no embedment. Concrete unit weight from register.")
        rows, info = block(a.B, a.L, a.D, a.V, a.H, a.ha, a.mu, a.qRd, a.cover, unfactored=a.unfactored)
        print(f"Block {a.B}x{a.L}x{a.D} m: self-weight {info['W_kN']:.1f} kN; net base force {info['N_kN']:.1f} kN")
    else:
        print(f"Factors: {CF.tag('geotech.helical_Kt_per_m')}, {CF.tag('geotech.helical_FS')} — proof-load test required")
        print("Assumptions: torque correlation Q_u = K_t·T (ICC-ES AC358 / ESR-2794), T = average of the last three\n"
              "  torque readings (1 ft increments) for tension; K_t is product specific (other makes: use their ESR);\n"
              "  ESR-2794 also caps Q_u per product (e.g. SS5 248.6 kN, SS175 255.3 kN in tension) — check the shaft and\n"
              "  the anchor head; Q_all = Q_u/FS is an allowable (service) load: compare with the unfactored pull.")
        rows, info = helical(a.T, a.pull, a.shaft, a.FS)
    return report(rows)


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
