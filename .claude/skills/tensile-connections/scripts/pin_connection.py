#!/usr/bin/env python3
"""Pin / lug (clevis-to-gusset) connection check — the standard cable-to-steel joint.

Checks a cable fork (clevis) or eye pinned through a steel lug (gusset) plate.

  EN 1993-1-8:2005  §3.13, Table 3.9 (lug geometry) + Table 3.10 (pin checks)
  AISC 360-22       §D5 (pin-connected members) + §J7 (bearing)

Pin moment follows EN 1993-1-8 Fig. 3.11:
      M_Ed = F_Ed (b + 4c + 2a) / 8
  b = lug (middle plate) thickness, a = fork cheek thickness, c = gap each side.

Units: N, mm, MPa (N/mm2).  Forces entered in kN.

Example (fork of a 26 mm spiral strand, 400 kN ULS, 280 kN SLS):
  python3 pin_connection.py --F 400 --Fser 280 --d 45 --d0 47 --t 30 \
      --a-lug 70 --c-lug 55 --fy 355 --fu 490 --pin-fy 460 --pin-fu 610 \
      --fork-t 22 --gap 2 --replaceable
"""
from __future__ import annotations

import argparse
import math
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as CF  # noqa: E402  central code-factor register (V/C/U tagged)


def en1993(F, Fser, d, d0, t, a_lug, c_lug, fy, fu, fyp, fup, fork_t, gap,
           replaceable, gM0=None, gM2=None, gM6ser=None, E=None, n_planes=2):
    gM0 = CF.get("steel.gM0") if gM0 is None else gM0
    gM2 = CF.get("steel.gM2") if gM2 is None else gM2
    gM6ser = CF.get("steel.gM6ser") if gM6ser is None else gM6ser
    E = CF.get("steel.E") if E is None else E
    """Return list of (check, demand, capacity, utilisation, clause)."""
    F *= 1e3
    Fser *= 1e3
    out = []
    # --- Table 3.9 geometry, type A (given thickness)
    a_req = F * gM0 / (2 * t * fy) + 2 * d0 / 3
    c_req = F * gM0 / (2 * t * fy) + d0 / 3
    out.append(("Lug end distance a (beyond hole, in line of force) [mm]", a_req, a_lug, a_req / a_lug, "T3.9 A"))
    out.append(("Lug side distance c (beside hole) [mm]", c_req, c_lug, c_req / c_lug, "T3.9 A"))
    # type B (given geometry) – informative
    t_B = 0.7 * math.sqrt(F * gM0 / fy)  # conservative: F_Ed (some editions quote F_Ed,ser)
    out.append(("Lug thickness for type B geometry [mm]", t_B, t, t_B / t, "T3.9 B (info)"))
    out.append(("Hole d0 <= 2.5 t (type B) [mm]", d0, 2.5 * t, d0 / (2.5 * t), "T3.9 B (info)"))
    # --- Table 3.10
    A = math.pi * d * d / 4
    Fv = F / n_planes
    FvRd = 0.6 * A * fup / gM2
    out.append(("Pin shear per plane [kN]", Fv / 1e3, FvRd / 1e3, Fv / FvRd, "T3.10"))
    # bearing: lug plate, fork cheeks (each takes F/2), and pin; weakest fy governs
    for name, tt, Fb in (("lug plate", t, F), ("fork cheek (each)", fork_t, F / 2)):
        fy_min = min(fy, fyp)
        FbRd = 1.5 * tt * d * fy_min / gM0
        out.append((f"Bearing ULS, {name} [kN]", Fb / 1e3, FbRd / 1e3, Fb / FbRd, "T3.10"))
        if replaceable:
            FbRdser = 0.6 * tt * d * fy_min / gM6ser
            Fbs = Fser if tt == t else Fser / 2
            out.append((f"Bearing SLS (replaceable pin), {name} [kN]", Fbs / 1e3, FbRdser / 1e3, Fbs / FbRdser, "T3.10"))
    # bending
    Wel = math.pi * d ** 3 / 32
    MEd = F * (t + 4 * gap + 2 * fork_t) / 8
    MRd = 1.5 * Wel * fyp / gM0
    out.append(("Pin bending [kNm]", MEd / 1e6, MRd / 1e6, MEd / MRd, "T3.10"))
    if replaceable:
        MEds = Fser * (t + 4 * gap + 2 * fork_t) / 8
        MRds = 0.8 * Wel * fyp / gM6ser
        out.append(("Pin bending SLS (replaceable) [kNm]", MEds / 1e6, MRds / 1e6, MEds / MRds, "T3.10"))
        # contact (Hertz) bearing stress, lug plate
        if d0 > d:
            sig = 0.591 * math.sqrt(E * Fser * (d0 - d) / (d * d * t))
            fhRd = 2.5 * fy / gM6ser
            out.append(("Contact stress sigma_h,Ed (lug) [MPa]", sig, fhRd, sig / fhRd, "3.13.2"))
    inter = (MEd / MRd) ** 2 + (Fv / FvRd) ** 2
    out.append(("Pin shear + bending interaction [-]", inter, 1.0, inter, "T3.10"))
    # net section of lug (tension across the hole) — plain EN 1993-1-1 check
    b_net = 2 * c_lug  # material both sides of hole
    NuRd = 0.9 * b_net * t * fu / gM2
    out.append(("Lug net section across hole [kN]", F / 1e3, NuRd / 1e3, F / NuRd, "EN1993-1-1 6.2.3"))
    return out


def aisc(F_kN, d, d0, t, a_lug, w_lug, fy, fu, method="LRFD"):
    """AISC 360 D5 + J7 for the lug plate. w_lug = total plate width at the hole."""
    F = F_kN * 1e3
    lrfd = method.upper() == "LRFD"
    out = []
    beff = min(2 * t + CF.get("aisc.beff_add_mm"), (w_lug - d0) / 2)
    # D5.1(a) tensile rupture on net effective area
    Pn = fu * 2 * t * beff
    out.append(("D5.1a tensile rupture net effective area [kN]", Pn, 0.75 if lrfd else 1 / 2.00))
    # D5.1(b) shear rupture on effective area
    Asf = 2 * t * (a_lug + d / 2)
    Pn = 0.6 * fu * Asf
    out.append(("D5.1b shear rupture [kN]", Pn, 0.75 if lrfd else 1 / 2.00))
    # J7 bearing on projected area
    Pn = 1.8 * fy * d * t
    out.append(("J7 bearing on projected area [kN]", Pn, 0.75 if lrfd else 1 / 2.00))
    # D2 yielding on gross section
    Pn = fy * w_lug * t
    out.append(("D2 gross section yielding [kN]", Pn, 0.90 if lrfd else 1 / 1.67))
    res = [(n, F / 1e3, p * phi / 1e3, F / (p * phi), "AISC") for n, p, phi in out]
    # D5.2 dimensional requirements
    res.append(("D5.2 a >= 1.33 beff [mm]", 1.33 * beff, a_lug, 1.33 * beff / a_lug, "AISC D5.2"))
    res.append(("D5.2 w >= 2 beff + d [mm]", 2 * beff + d, w_lug, (2 * beff + d) / w_lug, "AISC D5.2"))
    res.append(("D5.2 hole d0 <= d + 1 mm [mm]", d0, d + 1.0, d0 / (d + 1.0), "AISC D5.2"))
    return res


def report(rows, title):
    print(f"\n{title}")
    print(f"{'check':<58}{'demand':>10}{'capacity':>11}{'util':>7}  ref")
    worst = 0.0
    for name, dem, cap, u, ref in rows:
        flag = "  <-- FAIL" if u > 1.0 and "info" not in ref else ""
        if "info" not in ref:
            worst = max(worst, u)
        print(f"{name:<58}{dem:10.2f}{cap:11.2f}{u:7.2f}  {ref}{flag}")
    print(f"{'governing utilisation':<58}{'':>21}{worst:7.2f}  {'OK' if worst <= 1 else 'NOT OK'}")
    return worst


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--F", type=float, required=True, help="ULS design force [kN]")
    ap.add_argument("--Fser", type=float, default=None, help="SLS force [kN] (default F/1.4)")
    ap.add_argument("--d", type=float, required=True, help="pin diameter [mm]")
    ap.add_argument("--d0", type=float, required=True, help="hole diameter [mm]")
    ap.add_argument("--t", type=float, required=True, help="lug (gusset) plate thickness [mm]")
    ap.add_argument("--a-lug", type=float, required=True, help="edge distance hole edge->plate end, in force direction [mm]")
    ap.add_argument("--c-lug", type=float, required=True, help="edge distance hole edge->plate side [mm]")
    ap.add_argument("--fy", type=float, default=355.0, help="plate fy [MPa]")
    ap.add_argument("--fu", type=float, default=490.0, help="plate fu [MPa]")
    ap.add_argument("--pin-fy", type=float, default=460.0, help="pin fyp [MPa] (e.g. 42CrMo4 QT ~ 650-900)")
    ap.add_argument("--pin-fu", type=float, default=610.0, help="pin fup [MPa]")
    ap.add_argument("--fork-t", type=float, default=None, help="fork cheek thickness each side [mm] (default 0.6 t)")
    ap.add_argument("--gap", type=float, default=2.0, help="gap between lug and cheek [mm]")
    ap.add_argument("--replaceable", action="store_true", help="pin designed to be replaceable (SLS checks)")
    ap.add_argument("--aisc", action="store_true", help="also run AISC 360 D5/J7 lug checks")
    ap.add_argument("--method", default="LRFD", choices=["LRFD", "ASD"])
    ap.add_argument("--factors", default=None, help="project code-factor file")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    Fser = a.Fser if a.Fser is not None else a.F / 1.4
    fork_t = a.fork_t if a.fork_t is not None else 0.6 * a.t
    if a.d0 < a.d:
        sys.exit("hole must be larger than pin")
    rows = en1993(a.F, Fser, a.d, a.d0, a.t, a.a_lug, a.c_lug, a.fy, a.fu, a.pin_fy, a.pin_fu,
                  fork_t, a.gap, a.replaceable)
    print(f"Partial factors: {CF.tag('steel.gM0')}, {CF.tag('steel.gM2')}, {CF.tag('steel.gM6ser')}")
    w = report(rows, f"EN 1993-1-8 pin connection  F_Ed={a.F} kN  F_Ed,ser={Fser:.1f} kN  "
                     f"pin d={a.d} hole d0={a.d0} lug t={a.t} fork cheeks {fork_t:.1f} mm")
    if a.aisc:
        width = a.d0 + 2 * a.c_lug
        report(aisc(a.F, a.d, a.d0, a.t, a.a_lug, width, a.fy, a.fu, a.method),
               f"AISC 360 {a.method} lug checks (plate width at hole = {width:.0f} mm)")
    print("\nNotes: fork (clevis) itself is a proprietary fitting — take its capacity from the "
          "manufacturer (matched to cable MBL). Check welds of the lug to the supporting member, "
          "out-of-plane eccentricity (lug must lie in the cable plane) and plate buckling of long "
          "unstiffened lugs separately.")
    return w


if __name__ == "__main__":
    main(sys.argv[1:])
