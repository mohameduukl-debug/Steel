#!/usr/bin/env python3
"""Welds, bolt groups and base plates for tensile-structure steelwork (EN 1993-1-8).

Sub-commands
------------
  weld       double fillet weld of a lug/gusset plate to a member (T-joint):
             cable force F at angle θ to the weld line, lever arm e (weld line ->
             pin/hole centre), offset x along the weld. Directional method
             (4.5.3.2) + simplified method (4.5.3.3).
  bolts      bolt group: shear (in-plane Vx, Vy, torsion M about the group centroid,
             elastic method), tension N (uniform) + prying factor; per-bolt shear,
             tension, bearing, punching, combined (Table 3.4). Carbon 4.6–10.9 and
             stainless A2/A4-50/70/80.
  clampbar   membrane clamp-bar / keder-plate bolts: bolt force = n · spacing
             (shear via keder bearing) or tension (plate pulled off) with prying.
  baseplate  mast / column base plate: compression (6.2.5 equivalent T-stub,
             f_jd = β_j k_j f_ck / γ_c), uplift (T-stub modes 1–3 with anchor bolts),
             shear by friction (0.2·N_c) + anchor shear. CHS or I column.

Units: kN, kNm, mm, MPa.

Examples
  python3 steel_joint_checks.py weld --F 250 --angle 90 --L 200 --a 8 --e 120 --grade S355
  python3 steel_joint_checks.py bolts --n-rows 2 --n-cols 2 --p1 80 --p2 80 --Vy 120 --M 4 \
        --d 20 --grade 8.8 --t 15 --fu-plate 490 --e1 45 --e2 40
  python3 steel_joint_checks.py clampbar --n 12 --spacing 150 --d 12 --grade A4-70 --t 10
  python3 steel_joint_checks.py baseplate --col CHS --D 219.1 --tc 8 --B 400 --H 400 --tp 25 \
        --Nc 450 --Nt 120 --V 40 --anchors 4 --anchor-d 24 --anchor-grade 8.8 --edge 60 --fck 30
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as CF  # noqa: E402

BOLT = {  # fyb, fub [MPa]; alpha_v for shear plane through thread
    "4.6": (240, 400, 0.6), "5.6": (300, 500, 0.6), "8.8": (640, 800, 0.6), "10.9": (900, 1000, 0.5),
    "A2-50": (210, 500, 0.6), "A4-50": (210, 500, 0.6), "A2-70": (450, 700, 0.6), "A4-70": (450, 700, 0.6),
    "A4-80": (600, 800, 0.6),
}
AS = {10: 58, 12: 84.3, 16: 157, 20: 245, 22: 303, 24: 353, 27: 459, 30: 561, 36: 817, 42: 1120, 48: 1470}
FU = {"S235": 360, "S275": 430, "S355": 490, "S420": 520, "S460": 540}


def g(k):
    return CF.get(k)


def row(name, dem, cap, ref):
    return (name, dem, cap, ref)


def report(title, rows):
    print(title)
    print(f"{'check':<56}{'demand':>10}{'capacity':>10}{'util':>7}  ref")
    worst = 0.0
    for name, d, c, ref in rows:
        u = d / c if c else math.inf
        worst = max(worst, u)
        print(f"{name:<56}{d:10.2f}{c:10.2f}{u:7.2f}  {ref}" + ("  <-- FAIL" if u > 1 else ""))
    print(f"Governing utilisation {worst:.2f} -> {'OK' if worst <= 1 else 'NOT OK'}")
    return worst


# ------------------------------------------------------------------ welds
def weld(F, angle, L, a, e, x, grade, sides=2):
    """Returns rows. F kN at angle θ (deg) to the weld line; θ=90 -> force normal to the member face."""
    gM2 = g("steel.gM2")
    bw = CF.get("steel.beta_w")[grade]
    fu = FU[grade]
    N = F * 1e3 * math.sin(math.radians(angle))   # normal to weld line (pulls plate off member)
    V = F * 1e3 * math.cos(math.radians(angle))   # along the weld line
    M = V * e + N * x                              # in-plane moment about weld-group centroid
    Wl = sides * L ** 2 / 6                        # line modulus (per unit throat)
    n_max = N / (sides * L) + M / Wl               # N/mm per weld line (normal to weld axis)
    v = V / (sides * L)
    # T-joint fillet loaded transversely: σ⊥ = τ⊥ = n/(a√2); longitudinal τ∥ = v/a
    sig = tau_p = abs(n_max) / (a * math.sqrt(2))
    tau_l = abs(v) / a
    s_eq = math.sqrt(sig ** 2 + 3 * (tau_p ** 2 + tau_l ** 2))
    fvw = fu / (math.sqrt(3) * bw * gM2)
    fw = math.hypot(n_max, v)                      # simplified: resultant per unit length
    return [
        row(f"directional: √(σ⊥²+3(τ⊥²+τ∥²)) [MPa]", s_eq, fu / (bw * gM2), "4.5.3.2(6)"),
        row("directional: σ⊥ [MPa]", sig, 0.9 * fu / gM2, "4.5.3.2(6)"),
        row("simplified: F_w,Ed per length [N/mm]", fw, a * fvw, "4.5.3.3"),
    ], {"N_kN": N / 1e3, "V_kN": V / 1e3, "M_kNm": M / 1e6, "beta_w": bw, "fu": fu}


# ------------------------------------------------------------------ bolts
def bolt_resistances(d, grade, t, fu_p, e1, e2, p1, p2, threads_in_shear=True, d0=None, edge=True):
    gM2 = g("steel.gM2")
    fyb, fub, av_thr = BOLT[grade]
    As = AS.get(int(d), 0.78 * math.pi * d * d / 4)
    A = As if threads_in_shear else math.pi * d * d / 4
    av = av_thr if threads_in_shear else 0.6
    d0 = d0 or (d + (1 if d <= 14 else 2 if d <= 24 else 3))
    FvRd = av * fub * A / gM2
    FtRd = 0.9 * fub * As / gM2
    ad = min(e1 / (3 * d0) if e1 else 9e9, (p1 / (3 * d0) - 0.25) if p1 else 9e9)
    ab = min(ad, fub / fu_p, 1.0)
    k1 = min(2.8 * e2 / d0 - 1.7 if e2 else 9e9, 1.4 * p2 / d0 - 1.7 if p2 else 9e9, 2.5)
    FbRd = k1 * ab * fu_p * d * t / gM2
    dm = 1.7 * d  # mean of across-flats and across-corners of nut/head (approx.)
    BpRd = 0.6 * math.pi * dm * t * fu_p / gM2
    return {"FvRd": FvRd / 1e3, "FtRd": FtRd / 1e3, "FbRd": FbRd / 1e3, "BpRd": BpRd / 1e3,
            "k1": k1, "ab": ab, "d0": d0, "As": As}


def bolts(coords, Vx, Vy, M, N, prying, d, grade, t, fu_p, e1, e2, p1, p2, threads):
    n = len(coords)
    cx = sum(c[0] for c in coords) / n
    cy = sum(c[1] for c in coords) / n
    Ip = sum((c[0] - cx) ** 2 + (c[1] - cy) ** 2 for c in coords)
    worst = (0.0, None)
    for (x, y) in coords:
        rx, ry = x - cx, y - cy
        fx = Vx / n - (M * 1e3 * ry / Ip if Ip else 0.0)   # kN (M kNm -> kN·mm)
        fy = Vy / n + (M * 1e3 * rx / Ip if Ip else 0.0)
        fv = math.hypot(fx, fy)
        if fv > worst[0]:
            worst = (fv, (x, y))
    Fv = worst[0]
    Ft = N / n * prying
    R = bolt_resistances(d, grade, t, fu_p, e1, e2, p1, p2, threads)
    rows = [row(f"bolt shear (max bolt at {worst[1]}) [kN]", Fv, R["FvRd"], "T3.4"),
            row(f"bearing on plate t={t:g} (k1={R['k1']:.2f}, αb={R['ab']:.2f}) [kN]", Fv, R["FbRd"], "T3.4")]
    if N:
        rows += [row(f"bolt tension incl. prying ×{prying:g} [kN]", Ft, R["FtRd"], "T3.4"),
                 row("punching shear of plate [kN]", Ft, R["BpRd"], "T3.4"),
                 row("combined Fv/FvRd + Ft/(1.4 FtRd) [-]", Fv / R["FvRd"] + Ft / (1.4 * R["FtRd"]), 1.0, "T3.4")]
    return rows, R


def grid(nr, nc, p1, p2):
    return [(j * p2, i * p1) for i in range(nr) for j in range(nc)]


# -------------------------------------------------------------- base plate
def baseplate(a):
    gM0, gM2, gC = g("steel.gM0"), g("steel.gM2"), g("steel.gC")
    fjd = (2 / 3) * a.kj * a.fck / gC           # β_j = 2/3
    c = a.tp * math.sqrt(a.fy / (3 * fjd * gM0))
    rows = []
    if a.col.upper() == "CHS":
        Ro, Ri = a.D / 2 + c, max(a.D / 2 - a.tc - c, 0.0)
        Ro_lim = min(Ro, a.B / 2, a.H / 2)
        Aeff = math.pi * (Ro_lim ** 2 - Ri ** 2)
        lever_face = a.D / 2
    else:  # I column: 3 T-stubs (EN 1993-1-8 Fig 6.4) approximated as H-shape of width 2c + t
        bf, h, tf, tw = a.bf, a.hc, a.tfc, a.twc
        Af = 2 * min(bf + 2 * c, a.B) * min(tf + 2 * c, (a.H - h) / 2 + tf + c)
        Aw = max(h - 2 * tf - 2 * c, 0) * (tw + 2 * c)
        Aeff = Af + Aw
        lever_face = h / 2
    NcRd = Aeff * fjd / 1e3
    if a.Nc:
        rows.append(row(f"compression: A_eff={Aeff / 1e3:.1f}e3 mm², c={c:.0f} mm, f_jd={fjd:.1f} MPa [kN]",
                        a.Nc, NcRd, "6.2.5 / 6.2.8.2"))
    if a.Nt:
        fyb, fub, _ = BOLT[a.anchor_grade]
        As = AS.get(int(a.anchor_d), 0.78 * math.pi * a.anchor_d ** 2 / 4)
        FtRd = 0.9 * fub * As / gM2 / 1e3
        # bolt axis at 'edge' from plate edge; lever arm m from bolt to column face (0.8 weld deducted)
        if a.layout == "corners":   # anchors at plate corners, diagonal lever arm
            bolt_r = math.hypot(a.B / 2 - a.edge, a.H / 2 - a.edge)
        else:                       # anchors on the plate sides, opposite the column faces
            bolt_r = min(a.B, a.H) / 2 - a.edge
        m = max(bolt_r - lever_face - 0.8 * a.weld * math.sqrt(2), 10.0)
        e = a.edge
        n_ = min(e, 1.25 * m)
        leff = min(2 * math.pi * m, 4 * m + 1.25 * e)          # per bolt (circular / non-circular)
        # equivalent T-stub of length l_eff with one anchor each side of the column wall:
        # T-stub resistances are for 2 bolts -> divide by 2 for the force per anchor
        Mpl = 0.25 * leff * a.tp ** 2 * a.fy / gM0            # N·mm
        F1 = 4 * Mpl / m / 2 / 1e3
        F2 = (2 * Mpl + n_ * 2 * FtRd * 1e3) / (m + n_) / 2 / 1e3
        F12 = 2 * Mpl / m / 2 / 1e3                          # no prying (long anchor bolts), Table 6.2
        F3 = FtRd
        per = a.Nt / a.anchors
        rows.append(row(f"anchor bolt tension {a.anchor_grade} M{a.anchor_d:g} [kN/bolt]", per, FtRd, "T3.4"))
        rows.append(row(f"plate mode 1 (m={m:.0f}, l_eff={leff:.0f}) [kN/bolt]", per, F1, "6.2.4 T6.2"))
        rows.append(row("plate mode 2 (bolt + plate with prying) [kN/bolt]", per, F2, "6.2.4 T6.2"))
        rows.append(row("plate mode 1-2 without prying (anchor bolts) [kN/bolt]", per, F12, "6.2.4 T6.2"))
        rows.append(row("T-stub mode 3 (bolt failure) [kN/bolt]", per, F3, "6.2.4"))
    if a.V:
        fyb, fub, av = BOLT[a.anchor_grade]
        As = AS.get(int(a.anchor_d), 0.78 * math.pi * a.anchor_d ** 2 / 4)
        Ff = 0.2 * max(a.Nc, 0.0) if not a.Nt else 0.0        # friction only when in compression
        FvbRd = min(av * fub * As / gM2, (0.44 - 0.0003 * fyb) * fub * As / gM2) / 1e3
        rows.append(row("shear: friction 0.2·Nc + anchors α_bc (6.2.2(7)) [kN]", a.V, Ff + a.anchors * FvbRd, "6.2.2"))
    return rows, {"fjd": fjd, "c": c}


# ------------------------------------------------------------ EN 1992-4 anchors
def anchor_group(n1, n2, s1, s2, c1, c2, hef, d, dh, grade, fck, NEd, cracked=True, psi_re=1.0):
    """cast-in headed anchors, rectangular group n1 × n2, spacings s1/s2, min edge distances c1/c2 (mm),
    uniform tension N_Ed [kN] (concentric). Steel, pull-out (per anchor) and concrete cone (group)."""
    fyb, fub, _ = BOLT[grade]
    As = AS.get(int(d), 0.78 * math.pi * d * d / 4)
    gMs = max(1.2 * fub / fyb, 1.4)                               # EN 1992-4 Table 4.1
    gMc = g("anchor_EN1992_4.gamma_Mc")
    n = n1 * n2
    NRks = As * fub / 1e3
    k2 = g("anchor_EN1992_4.k2_pullout_cracked" if cracked else "anchor_EN1992_4.k2_pullout_uncracked")
    Ah = math.pi / 4 * (dh ** 2 - d ** 2)
    NRkp = k2 * Ah * fck / 1e3
    k1 = g("anchor_EN1992_4.k_cr_N" if cracked else "anchor_EN1992_4.k_ucr_N")
    scr = g("anchor_EN1992_4.s_cr_N_per_hef") * hef
    ccr = g("anchor_EN1992_4.c_cr_N_per_hef") * hef
    N0 = k1 * math.sqrt(fck) * hef ** 1.5 / 1e3                  # kN
    A0 = scr ** 2
    wx = min(c1, ccr) + s1 * (n1 - 1) + min(c1, ccr) if n1 > 0 else scr
    wy = min(c2, ccr) + s2 * (n2 - 1) + min(c2, ccr)
    Ac = min(wx * wy, n * A0)
    cmin = min(c1, c2)
    psi_s = min(1.0, 0.7 + 0.3 * cmin / ccr)
    NRkc = N0 * (Ac / A0) * psi_s * psi_re
    rows = [
        row(f"steel failure per anchor M{d:g} {grade} (γMs={gMs:.2f}) [kN]", NEd / n, NRks / gMs, "EN 1992-4 7.2.1.3"),
        row(f"pull-out per anchor (k2={k2}, A_h={Ah:.0f} mm²) [kN]", NEd / n, NRkp / gMc, "EN 1992-4 7.2.1.5"),
        row(f"concrete cone, group (N0={N0:.1f} kN, Ac/A0={Ac / A0:.2f}, ψs={psi_s:.2f}) [kN]", NEd, NRkc / gMc,
            "EN 1992-4 7.2.1.4"),
    ]
    return rows, {"N0_Rk_c": N0, "NRk_c": NRkc, "gMs": gMs, "gMc": gMc}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--factors", default=None, help="project code-factor file (before the sub-command)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    w = sp.add_parser("weld")
    w.add_argument("--F", type=float, required=True)
    w.add_argument("--angle", type=float, default=90.0, help="force angle to weld line [deg]")
    w.add_argument("--L", type=float, required=True, help="weld length (each side) [mm]")
    w.add_argument("--a", type=float, required=True, help="throat thickness [mm]")
    w.add_argument("--e", type=float, default=0.0, help="lever arm weld line -> hole centre [mm]")
    w.add_argument("--x", type=float, default=0.0, help="offset of load line from weld centroid along weld [mm]")
    w.add_argument("--grade", default="S355", choices=list(FU))
    w.add_argument("--sides", type=int, default=2)

    b = sp.add_parser("bolts")
    b.add_argument("--n-rows", type=int, default=1)
    b.add_argument("--n-cols", type=int, default=1)
    b.add_argument("--p1", type=float, default=0.0, help="pitch between rows (in force dir) [mm]")
    b.add_argument("--p2", type=float, default=0.0, help="pitch between columns [mm]")
    b.add_argument("--coords", default=None, help="explicit 'x:y;x:y;...' [mm] (overrides grid)")
    b.add_argument("--Vx", type=float, default=0.0)
    b.add_argument("--Vy", type=float, default=0.0)
    b.add_argument("--M", type=float, default=0.0, help="in-plane moment about group centroid [kNm]")
    b.add_argument("--N", type=float, default=0.0, help="total tension [kN]")
    b.add_argument("--prying", type=float, default=1.0)
    b.add_argument("--d", type=float, required=True)
    b.add_argument("--grade", default="8.8", choices=list(BOLT))
    b.add_argument("--t", type=float, required=True, help="thinnest ply in bearing [mm]")
    b.add_argument("--fu-plate", type=float, default=490.0)
    b.add_argument("--e1", type=float, default=0.0)
    b.add_argument("--e2", type=float, default=0.0)
    b.add_argument("--shank", action="store_true", help="shear plane through unthreaded shank")

    c = sp.add_parser("clampbar")
    c.add_argument("--n", type=float, required=True, help="membrane stress at the clamp line [kN/m]")
    c.add_argument("--spacing", type=float, required=True, help="bolt spacing [mm]")
    c.add_argument("--d", type=float, default=12.0)
    c.add_argument("--grade", default="A4-70", choices=list(BOLT))
    c.add_argument("--t", type=float, default=10.0, help="steel ply in bearing [mm]")
    c.add_argument("--fu-plate", type=float, default=490.0)
    c.add_argument("--mode", choices=["shear", "tension"], default="shear")
    c.add_argument("--prying", type=float, default=1.3)
    c.add_argument("--peak", type=float, default=1.5, help="stress concentration factor at clamp line")
    c.add_argument("--sensitivity", action="store_true", help="aluminium bearing over its [U] range")
    c.add_argument("--plate", choices=["steel", "alu6082"], default="steel",
                   help="bearing ply material (alu6082: EN 1999-1-1, f_u and γM2 from the register)")

    an = sp.add_parser("anchor")
    an.add_argument("--n1", type=int, default=2)
    an.add_argument("--n2", type=int, default=2)
    an.add_argument("--s1", type=float, default=200.0)
    an.add_argument("--s2", type=float, default=200.0)
    an.add_argument("--c1", type=float, default=300.0, help="edge distance in direction 1 [mm]")
    an.add_argument("--c2", type=float, default=300.0)
    an.add_argument("--hef", type=float, required=True, help="effective embedment [mm]")
    an.add_argument("--d", type=float, default=24.0)
    an.add_argument("--dh", type=float, default=None, help="head / washer plate diameter [mm] (default 1.9 d)")
    an.add_argument("--grade", default="8.8", choices=list(BOLT))
    an.add_argument("--fck", type=float, default=30.0)
    an.add_argument("--N", type=float, required=True, help="design tension on the group [kN]")
    an.add_argument("--uncracked", action="store_true")
    an.add_argument("--psi-re", type=float, default=1.0, help="shell spalling factor (0.5 + hef/200 ≤ 1 if dense reinforcement)")

    p = sp.add_parser("baseplate")
    p.add_argument("--col", choices=["CHS", "I"], default="CHS")
    p.add_argument("--D", type=float, default=219.1)
    p.add_argument("--tc", type=float, default=8.0)
    p.add_argument("--hc", type=float, default=300.0)
    p.add_argument("--bf", type=float, default=300.0)
    p.add_argument("--tfc", type=float, default=19.0)
    p.add_argument("--twc", type=float, default=11.0)
    p.add_argument("--B", type=float, required=True)
    p.add_argument("--H", type=float, required=True)
    p.add_argument("--tp", type=float, required=True)
    p.add_argument("--fy", type=float, default=355.0)
    p.add_argument("--fck", type=float, default=30.0)
    p.add_argument("--kj", type=float, default=1.5, help="concentration factor (≤ ~3; 1.0 conservative)")
    p.add_argument("--Nc", type=float, default=0.0, help="compression [kN] (compression combination)")
    p.add_argument("--Nt", type=float, default=0.0,
                   help="uplift [kN] (uplift combination; if given, no friction is credited for --V)")
    p.add_argument("--V", type=float, default=0.0, help="shear [kN]")
    p.add_argument("--anchors", type=int, default=4)
    p.add_argument("--anchor-d", type=float, default=24.0)
    p.add_argument("--anchor-grade", default="8.8", choices=list(BOLT))
    p.add_argument("--edge", type=float, default=60.0, help="anchor axis to plate edge [mm]")
    p.add_argument("--weld", type=float, default=6.0, help="column-to-plate weld throat [mm]")
    p.add_argument("--layout", choices=["corners", "sides"], default="corners", help="anchor position on the plate")

    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    print(f"Factors: {CF.tag('steel.gM0')}, {CF.tag('steel.gM2')}" + (f", {CF.tag('steel.gC')}" if a.cmd == "baseplate" else ""))
    if a.cmd == "weld":
        rows, info = weld(a.F, a.angle, a.L, a.a, a.e, a.x, a.grade, a.sides)
        print(f"Weld: {a.sides} x fillet a={a.a:g} L={a.L:g} mm, {a.grade} (fu={info['fu']}, βw={info['beta_w']} [C]); "
              f"N⊥={info['N_kN']:.1f} kN, V∥={info['V_kN']:.1f} kN, M={info['M_kNm']:.2f} kNm")
        return report("", rows)
    if a.cmd == "bolts":
        coords = ([tuple(map(float, s.split(":"))) for s in a.coords.split(";")] if a.coords
                  else grid(a.n_rows, a.n_cols, a.p1, a.p2))
        rows, R = bolts(coords, a.Vx, a.Vy, a.M, a.N, a.prying, a.d, a.grade, a.t, a.fu_plate,
                        a.e1, a.e2, a.p1, a.p2, not a.shank)
        print(f"{len(coords)} bolts M{a.d:g} {a.grade} (d0={R['d0']:g}, As={R['As']:g} mm²)")
        return report("", rows)
    if a.cmd == "clampbar":
        F = a.n * a.peak * a.spacing / 1e3  # kN per bolt
        if a.mode == "shear":
            rows, R = bolts([(0, 0)], 0, F, 0, 0, 1, a.d, a.grade, a.t, a.fu_plate, 3 * a.d, 1.5 * a.d, 0, 0, True)
            if a.plate == "alu6082":
                fu_al = g("aluminium.6082T6_fu_thin" if a.t <= 5 else "aluminium.6082T6_fu_thick")
                gM2a = g("aluminium.gM2")
                d0 = R["d0"]
                ab = min(3 * a.d / (3 * d0), BOLT[a.grade][1] / fu_al, 1.0)
                k1 = min(2.8 * 1.5 * a.d / d0 - 1.7, 2.5)
                FbA = k1 * ab * fu_al * a.d * a.t / gM2a / 1e3
                rows = [r for r in rows if not r[0].startswith("bearing")]
                rows.append(row(f"bearing on aluminium 6082-T6 t={a.t:g} (f_u={fu_al}, γM2={gM2a}) [kN]", F, FbA,
                                f"EN 1999-1-1 T8.5 [{CF.status('aluminium.bearing_formula')}]"))
                if a.sensitivity:
                    res = CF.sensitivity(lambda s_: F / (FbA * s_), "aluminium.bearing_formula")
                    sens = CF.sens_line("aluminium bearing (scale on F_b,Rd)", res)
        else:
            rows, R = bolts([(0, 0)], 0, 0, 0, F, a.prying, a.d, a.grade, a.t, a.fu_plate, 3 * a.d, 1.5 * a.d, 0, 0, True)
        print(f"Clamp line: n={a.n} kN/m × peak {a.peak} × spacing {a.spacing:g} mm = {F:.2f} kN per bolt ({a.mode})")
        if a.spacing > 200:
            print("NOTE: TensiNet guidance: clamp bolt spacing hardly more than ~200 mm [V]")
        print("Aluminium clamp plate/keder bearing and bending: check to EN 1999-1-1 separately.")
        w = report("", rows)
        if a.sensitivity:
            print(locals().get("sens") or "  sensitivity: no uncertain factor in this check (steel plate)")
        return w
    if a.cmd == "anchor":
        dh = a.dh or 1.9 * a.d
        rows, info = anchor_group(a.n1, a.n2, a.s1, a.s2, a.c1, a.c2, a.hef, a.d, dh, a.grade, a.fck, a.N,
                                  not a.uncracked, a.psi_re)
        print(f"{a.n1}x{a.n2} cast-in headed anchors M{a.d:g} {a.grade}, h_ef={a.hef:g} mm, C{a.fck:g} "
              f"{'uncracked' if a.uncracked else 'cracked'}; factors {CF.tag('anchor_EN1992_4.gamma_Mc')}, "
              f"{CF.tag('anchor_EN1992_4.k_cr_N')}")
        print("Not included: splitting, blow-out (edge), anchor reinforcement, shear/combined (EN 1992-4 7.2.2–7.2.3).")
        return report("", rows)
    rows, info = baseplate(a)
    print(f"Base plate {a.B:g}x{a.H:g}x{a.tp:g} S{int(a.fy)} on C{a.fck:g}; column {a.col}")
    print("Anchor embedment / concrete breakout / pull-out: EN 1992-4 (not included).")
    return report("", rows)


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
