#!/usr/bin/env python3
"""Welds, bolt groups, gusset plates, base plates and cast-in anchors for tensile-structure steelwork.

EN 1993-1-8:2005 (+ EN 1993-1-1 buckling, AISC 360-16 J4.4 option), EN 1992-4:2018, EN 1999-1-1 (clamp plates).

Sub-commands
------------
  weld       double fillet weld of a lug/gusset plate to a member (T-joint): cable force F at angle θ to the
             weld line, lever arm e (weld line -> pin/hole centre), offset x along the weld. Directional
             method (4.5.3.2) + simplified method (4.5.3.3).
  bolts      bolt group: in-plane Vx, Vy, torsion M about the group centroid (elastic method), tension N
             (uniform) x prying factor; per-bolt shear, bearing (components parallel / normal to the edge,
             k1 and αb from e1, e2, p1, p2), tension, punching, combined (Table 3.4). Carbon 4.6-10.9 and
             stainless A2/A4-50/70/80.
  gusset     bolted gusset / corner plate: bolt shear + bearing, block tearing (3.10.2 eq. 3.9 / 3.10),
             Whitmore width (30°) yielding, net section, compression as an equivalent column (Thornton
             K·l_avg) with EN 1993-1-1 curve c; --aisc adds AISC J4.3 block shear and J4.1/J4.4/E3.
  clampbar   membrane clamp-bar / keder-plate bolts: bolt force = n · peak · spacing (shear via keder
             bearing) or tension (plate pulled off) with prying; aluminium 6082-T6 bearing (EN 1999-1-1).
  baseplate  mast / column base plate: compression (6.2.5 equivalent T-stub, f_jd = β_j k_j α_cc f_ck/γ_c),
             uplift (T-stub Table 6.2, prying decided by L_b vs L_b*; CHS with a ring of anchors: SCI P358 6.8
             ring-flange rules), shear by friction (C_f,d·N_c) + anchor shear (α_bc). CHS or I column.
  anchor     EN 1992-4 cast-in headed anchors (rectangular group): tension (steel, pull-out, concrete cone,
             splitting), shear (steel without / with lever arm, pry-out, concrete edge with ψ factors) and
             tension-shear interaction (steel exponent 2, concrete 1.5).

Units: kN, kNm, mm, MPa.

Examples
  python3 steel_joint_checks.py weld --F 250 --angle 90 --L 200 --a 8 --e 120 --grade S355
  python3 steel_joint_checks.py bolts --n-rows 2 --n-cols 2 --p1 80 --p2 80 --Vy 120 --M 4 \
        --d 20 --grade 8.8 --t 15 --fu-plate 490 --e1 45 --e2 40
  python3 steel_joint_checks.py gusset --F 300 --n1 3 --n2 2 --p1 70 --p2 60 --e1 40 --e2 40 --d 20 --t 12
  python3 steel_joint_checks.py clampbar --n 12 --spacing 150 --d 12 --grade A4-70 --t 10
  python3 steel_joint_checks.py baseplate --col CHS --D 219.1 --tc 8 --B 400 --H 400 --tp 25 \
        --Nc 450 --Nt 120 --V 40 --anchors 4 --anchor-d 24 --anchor-grade 8.8 --edge 60 --fck 30
  python3 steel_joint_checks.py anchor --n1 2 --n2 2 --s1 200 --s2 200 --c1 400 --c2 400 --hef 250 --d 24 \
        --N 150 --V 40 --cv 300 --h 600
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as CF  # noqa: E402

INF = float("inf")
BOLT = {  # fyb, fub [MPa] (EN 1993-1-8 Table 3.1, EN ISO 3506); alpha_v for the shear plane through the thread
    "4.6": (240, 400, 0.6), "5.6": (300, 500, 0.6), "8.8": (640, 800, 0.6), "10.9": (900, 1000, 0.5),
    "A2-50": (210, 500, None), "A4-50": (210, 500, None), "A2-70": (450, 700, None), "A4-70": (450, 700, None),
    "A4-80": (600, 800, None),          # None -> aluminium.alpha_v_stainless_bolt from the register
}
AS = {10: 58, 12: 84.3, 16: 157, 20: 245, 22: 303, 24: 353, 27: 459, 30: 561, 36: 817, 42: 1120, 48: 1470}
# hexagon nut / head: width across flats s and across corners e_min (ISO 4032 / ISO 4014 product grade A) [mm]
HEX = {10: (16, 17.77), 12: (18, 20.03), 16: (24, 26.75), 20: (30, 32.95), 22: (34, 37.29), 24: (36, 39.55),
       27: (41, 45.2), 30: (46, 50.85), 36: (55, 60.79)}
FU = {"S235": 360, "S275": 430, "S355": 490, "S420": 520, "S460": 540}
FYG = {"S235": 235, "S275": 275, "S355": 355, "S420": 420, "S460": 460}


def g(k):
    return CF.get(k)


def row(name, dem, cap, ref):
    return (name, dem, cap, ref)


def report(title, rows):
    if title:
        print(title)
    print(f"{'check':<60}{'demand':>10}{'capacity':>10}{'util':>7}  ref")
    worst = 0.0
    for name, d, c, ref in rows:
        u = d / c if c else math.inf
        worst = max(worst, u)
        print(f"{name:<60}{d:10.2f}{c:10.2f}{u:7.2f}  {ref}" + ("  <-- FAIL" if u > 1 else ""))
    print(f"Governing utilisation {worst:.2f} -> {'OK' if worst <= 1 else 'NOT OK'}")
    return worst


def alpha_v(grade, threads=True):
    av = BOLT[grade][2]
    if not threads:
        return 0.6
    return g("aluminium.alpha_v_stainless_bolt") if av is None else av


# ------------------------------------------------------------------ welds
def weld(F, angle, L, a, e, x, grade, sides=2, fu=None):
    """Returns rows. F kN at angle θ (deg) to the weld line; θ=90 -> force normal to the member face.
    fu: ultimate strength of the weaker part [MPa] (default from the grade)."""
    gM2 = g("steel.gM2")
    bw = CF.get("steel.beta_w")[grade]
    fu = FU[grade] if fu is None else fu
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
        row("directional: √(σ⊥²+3(τ⊥²+τ∥²)) [MPa]", s_eq, fu / (bw * gM2), "4.5.3.2(6)"),
        row("directional: σ⊥ [MPa]", sig, 0.9 * fu / gM2, "4.5.3.2(6)"),
        row("simplified: F_w,Ed per length [N/mm]", fw, a * fvw, "4.5.3.3"),
    ], {"N_kN": N / 1e3, "V_kN": V / 1e3, "M_kNm": M / 1e6, "beta_w": bw, "fu": fu,
        "sig_perp": sig, "tau_perp": tau_p, "tau_par": tau_l, "Fw_Rd": a * fvw}


# ------------------------------------------------------------------ bolts
def hole(d):
    return d + (1 if d <= 14 else 2 if d <= 24 else 3)


def bearing_k1_ab(d0, fub, fu_p, e1, e2, p1, p2):
    """EN 1993-1-8 Table 3.4 (= EN 1999-1-1 Table 8.5). 0 / None for e1, e2, p1, p2 = not applicable.
    The smaller of the end/inner (αd) and edge/inner (k1) expressions is used (conservative for a group)."""
    ad = min(e1 / (3 * d0) if e1 else INF, (p1 / (3 * d0) - 0.25) if p1 else INF)
    ab = min(ad, fub / fu_p, 1.0)
    k1 = min(2.8 * e2 / d0 - 1.7 if e2 else INF, 1.4 * p2 / d0 - 1.7 if p2 else INF, 2.5)
    return k1, ab


def bolt_resistances(d, grade, t, fu_p, e1, e2, p1, p2, threads_in_shear=True, d0=None, edge=True):
    """Per-bolt resistances [kN]. FbRd for a load parallel to direction 1 (e1, p1 along the load)."""
    gM2 = g("steel.gM2")
    fyb, fub, _ = BOLT[grade]
    As = AS.get(int(d), 0.78 * math.pi * d * d / 4)
    A = As if threads_in_shear else math.pi * d * d / 4
    av = alpha_v(grade, threads_in_shear)
    d0 = d0 or hole(d)
    FvRd = av * fub * A / gM2
    FtRd = g("steel.k2_thread") * fub * As / gM2
    k1, ab = bearing_k1_ab(d0, fub, fu_p, e1, e2, p1, p2)
    FbRd = k1 * ab * fu_p * d * t / gM2
    s, e = HEX.get(int(d), (1.5 * d, 1.65 * d))
    dm = (s + e) / 2                       # mean of across flats and across corners (Table 3.4, B_p,Rd)
    BpRd = 0.6 * math.pi * dm * t * fu_p / gM2
    return {"FvRd": FvRd / 1e3, "FtRd": FtRd / 1e3, "FbRd": FbRd / 1e3, "BpRd": BpRd / 1e3,
            "k1": k1, "ab": ab, "d0": d0, "As": As, "av": av, "dm": dm}


def bolt_forces(coords, Vx, Vy, M):
    """elastic bolt-group forces [kN] (fx, fy) for every bolt; M [kNm] about the centroid (CCW +)."""
    n = len(coords)
    cx = sum(c[0] for c in coords) / n
    cy = sum(c[1] for c in coords) / n
    Ip = sum((c[0] - cx) ** 2 + (c[1] - cy) ** 2 for c in coords)
    out = []
    for (x, y) in coords:
        rx, ry = x - cx, y - cy
        fx = Vx / n - (M * 1e3 * ry / Ip if Ip else 0.0)   # kN (M kNm -> kN·mm)
        fy = Vy / n + (M * 1e3 * rx / Ip if Ip else 0.0)
        out.append((fx, fy))
    return out, Ip


def bolts(coords, Vx, Vy, M, N, prying, d, grade, t, fu_p, e1, e2, p1, p2, threads, d0=None):
    """Bolt group check. y = direction 1 (e1, p1 measured along y), x = direction 2 (e2, p2).
    Bearing is verified separately for the components parallel and normal to the edge (Table 3.4 note) and
    combined as √((fx/Fb,x)² + (fy/Fb,y)²) ≤ 1 at every bolt."""
    n = len(coords)
    forces, _ = bolt_forces(coords, Vx, Vy, M)
    worst = max(range(n), key=lambda i: math.hypot(*forces[i]))
    Fv = math.hypot(*forces[worst])
    Ft = N / n * prying
    R = bolt_resistances(d, grade, t, fu_p, e1, e2, p1, p2, threads, d0)
    Rx = bolt_resistances(d, grade, t, fu_p, e2, e1, p2, p1, threads, d0)     # load along x: roles swap
    ub = max(math.hypot(fx / Rx["FbRd"], fy / R["FbRd"]) for fx, fy in forces)
    rows = [row(f"bolt shear (max bolt at {coords[worst]}) [kN]", Fv, R["FvRd"], "T3.4"),
            row(f"bearing t={t:g}: y k1={R['k1']:.2f} αb={R['ab']:.2f} Fb={R['FbRd']:.0f}; "
                f"x k1={Rx['k1']:.2f} αb={Rx['ab']:.2f} Fb={Rx['FbRd']:.0f} [-]", ub, 1.0, "T3.4 note 3")]
    if N:
        rows += [row(f"bolt tension incl. prying ×{prying:g} [kN]", Ft, R["FtRd"], "T3.4"),
                 row(f"punching shear of plate (d_m={R['dm']:.1f}) [kN]", Ft, R["BpRd"], "T3.4"),
                 row("combined Fv/FvRd + Ft/(1.4 FtRd) [-]", Fv / R["FvRd"] + Ft / (1.4 * R["FtRd"]), 1.0, "T3.4")]
    R["FbRd_x"] = Rx["FbRd"]
    R["bearing_util"] = ub
    return rows, R


def grid(nr, nc, p1, p2):
    return [(j * p2, i * p1) for i in range(nr) for j in range(nc)]


# ------------------------------------------------------------- block tearing / gusset
def block_tearing(Ant, Anv, fy, fu, eccentric=False, gM0=None, gM2=None):
    """EN 1993-1-8:2005 3.10.2: V_eff,1,Rd = fu Ant/γM2 + fy Anv/(√3 γM0) (3.9, concentric);
    V_eff,2,Rd = 0.5 fu Ant/γM2 + fy Anv/(√3 γM0) (3.10, eccentric). Returns kN."""
    gM0 = g("steel.gM0") if gM0 is None else gM0
    gM2 = g("steel.gM2") if gM2 is None else gM2
    k = 0.5 if eccentric else 1.0
    return (k * fu * Ant / gM2 + fy * Anv / (math.sqrt(3) * gM0)) / 1e3


def block_areas(n1, n2, p1, p2, e1, e2, d0, t, pattern="U"):
    """Net areas for block tearing of a rectangular bolt group (n1 rows along the force, n2 columns).
    U: block between the outer columns, two shear planes, tension across the last row (gusset, concentric).
    L: one shear plane along the far column, tension from it to the free edge e2 (fin plate, eccentric)."""
    lv = e1 + (n1 - 1) * p1 - (n1 - 0.5) * d0
    if pattern == "U":
        return t * ((n2 - 1) * p2 - (n2 - 1) * d0), 2 * t * lv
    return t * ((n2 - 1) * p2 + e2 - (n2 - 0.5) * d0), t * lv


def aisc_block_shear(Agv, Anv, Ant, Fy, Fu, Ubs=1.0, phi=None):
    """AISC 360-16 J4.3: Rn = 0.60 Fu Anv + Ubs Fu Ant ≤ 0.60 Fy Agv + Ubs Fu Ant; returns φRn (force units of
    stress × area)."""
    phi = g("aisc.phi_pin") if phi is None else phi
    return phi * min(0.6 * Fu * Anv + Ubs * Fu * Ant, 0.6 * Fy * Agv + Ubs * Fu * Ant)


def whitmore_width(n1, n2, p1, p2, angle=None, l=None, w=None):
    """Whitmore effective width at the last bolt row (or end of the weld): w + 2 l tan(angle).
    Bolted: w = (n2-1) p2, l = (n1-1) p1. Welded: pass l (weld length) and w (weld spacing)."""
    angle = g("connections.whitmore_angle_deg") if angle is None else angle
    l = (n1 - 1) * p1 if l is None else l
    w = (n2 - 1) * p2 if w is None else w
    return w + 2 * l * math.tan(math.radians(angle))


def chi_en(lam, alpha):
    """EN 1993-1-1 6.3.1.2 (6.49) reduction factor."""
    if lam <= 0.2:
        return 1.0
    phi = 0.5 * (1 + alpha * (lam - 0.2) + lam ** 2)
    return min(1.0, 1 / (phi + math.sqrt(phi ** 2 - lam ** 2)))


def plate_column_en(be, t, fy, Lcr, E=None, alpha=None, gM1=None):
    """Equivalent column of width be and thickness t (buckling about the weak axis). Returns dict, N in kN."""
    E = g("steel.E") if E is None else E
    alpha = g("connections.alpha_curve_c") if alpha is None else alpha
    gM1 = g("steel.gM1") if gM1 is None else gM1
    i = t / math.sqrt(12)
    lam = Lcr / i / (math.pi * math.sqrt(E / fy))
    chi = chi_en(lam, alpha)
    return {"lam": lam, "chi": chi, "NbRd": chi * be * t * fy / gM1 / 1e3}


def plate_column_aisc(be, t, Fy, KL, E=None, phi=None):
    """AISC 360-16 J4.4: KL/r ≤ 25 -> Pn = Fy Ag; otherwise Chapter E (E3). Units consistent (N, mm, MPa)."""
    E = g("steel.E") if E is None else E
    phi = g("aisc.phi_yield") if phi is None else phi
    r = t / math.sqrt(12)
    sl = KL / r
    Ag = be * t
    if sl <= g("connections.aisc_J44_slenderness_limit"):
        Fcr, Fe = Fy, INF
    else:
        Fe = math.pi ** 2 * E / sl ** 2
        Fcr = 0.658 ** (Fy / Fe) * Fy if sl <= 4.71 * math.sqrt(E / Fy) else 0.877 * Fe
    return {"KL_r": sl, "Fe": Fe, "Fcr": Fcr, "Pn": Fcr * Ag, "phiPn": phi * Fcr * Ag}


def gusset(F, n1, n2, p1, p2, e1, e2, d, d0, grade, t, fy, fu, width=None, l_avg=None, K=None,
           pattern="U", aisc=False, threads=True):
    """Bolted gusset / corner plate with a concentric axial force F [kN] (+ tension, - compression)."""
    d0 = d0 or hole(d)
    gM0, gM2 = g("steel.gM0"), g("steel.gM2")
    n = n1 * n2
    rows, R = bolts(grid(n1, n2, p1, p2), 0.0, abs(F), 0.0, 0.0, 1.0, d, grade, t, fu, e1, e2,
                    p1 if n1 > 1 else 0, p2 if n2 > 1 else 0, threads, d0)
    Ant, Anv = block_areas(n1, n2, p1, p2, e1, e2, d0, t, pattern)
    Veff = block_tearing(Ant, Anv, fy, fu, eccentric=(pattern == "L"))
    rows.append(row(f"block tearing {pattern} (A_nt={Ant:.0f}, A_nv={Anv:.0f} mm²) [kN]", abs(F), Veff,
                    "3.10.2 " + ("(3.10)" if pattern == "L" else "(3.9)")))
    be = whitmore_width(n1, n2, p1, p2)
    be_eff = min(be, width) if width else be
    info = {"Ant": Ant, "Anv": Anv, "Veff": Veff, "be": be, "be_eff": be_eff, "R": R, "n": n}
    if F >= 0:
        rows.append(row(f"Whitmore section yield (b_e={be_eff:.0f} mm) [kN]", F, be_eff * t * fy / gM0 / 1e3,
                        "Whitmore 30° / EN 1993-1-1 6.2.3"))
        Anet = (be_eff - n2 * d0) * t
        rows.append(row("net section at the last row, 0.9 A_net f_u/γM2 [kN]", F,
                        g("steel.k_net_EN1993_1_1") * Anet * fu / gM2 / 1e3, "EN 1993-1-1 6.2.3(2)b"))
    else:
        K = g("connections.K_thornton") if K is None else K
        if not l_avg:
            raise ValueError("compression: give l_avg (average free length of the gusset, Thornton)")
        col = plate_column_en(be_eff, t, fy, K * l_avg)
        info["col_en"] = col
        rows.append(row(f"compression: K·l_avg={K * l_avg:.0f}, λ={col['lam']:.2f}, χ={col['chi']:.3f} (curve c) [kN]",
                        -F, col["NbRd"], "EN 1993-1-1 6.3.1 (equiv. column)"))
    if aisc:
        K = g("connections.K_thornton") if K is None else K
        ca = plate_column_aisc(be_eff, t, fy, K * l_avg if l_avg else 0.0)
        info["col_aisc"] = ca
        what = "yield" if F >= 0 else "compression KL/r=%.1f" % ca["KL_r"]
        dh = d0 + 1.6                                      # AISC B4.3b: + 1/16 in. for net areas
        Ant_a, Anv_a = block_areas(n1, n2, p1, p2, e1, e2, dh, t, pattern)
        Agv_a = (2 if pattern == "U" else 1) * t * (e1 + (n1 - 1) * p1)
        Ubs = 0.5 if (pattern == "L" and n2 > 1) else 1.0
        rows.append(row(f"AISC J4.3 block shear (U_bs={Ubs:g}) φRn [kN]", abs(F),
                        aisc_block_shear(Agv_a, Anv_a, Ant_a, fy, fu, Ubs) / 1e3, "AISC J4.3"))
        rows.append(row(f"AISC J4: Whitmore {what} φRn [kN]",
                        abs(F), (g('aisc.phi_yield') * fy * be_eff * t if F >= 0 else ca["phiPn"]) / 1e3,
                        "AISC J4.1(a)/J4.4"))
    return rows, info


# -------------------------------------------------------------- base plate
def tstub(leff1, leff2, m, n, tf, fy, FtRd_sum, ew=None, gM0=None):
    """EN 1993-1-8 Table 6.2 T-stub flange in tension. Forces in N (FtRd_sum in N). n is limited to 1.25 m.
    ew given -> Mode 1 by Method 2 (8n - 2ew) M / (2mn - ew(m+n)); otherwise Method 1 4M/m."""
    gM0 = g("steel.gM0") if gM0 is None else gM0
    n = min(n, 1.25 * m)
    Mpl1 = 0.25 * leff1 * tf ** 2 * fy / gM0
    Mpl2 = 0.25 * leff2 * tf ** 2 * fy / gM0
    F1 = 4 * Mpl1 / m if ew is None else (8 * n - 2 * ew) * Mpl1 / (2 * m * n - ew * (m + n))
    return {"F1": F1, "F2": (2 * Mpl2 + n * FtRd_sum) / (m + n), "F12": 2 * Mpl1 / m, "F3": FtRd_sum,
            "Mpl1": Mpl1, "Mpl2": Mpl2, "n": n}


def leff_single_row(m, e):
    """individual bolt row (Table 6.4 / column flange, end-plate inner row): circular 2πm, non-circular 4m+1.25e."""
    cp, nc = 2 * math.pi * m, 4 * m + 1.25 * e
    return {"cp": cp, "nc": nc, "leff1": min(cp, nc), "leff2": nc}


def leff_extension(mx, ex, e, w, bp):
    """bolt row outside the tension flange (end-plate extension, EN 1993-1-8 Table 6.6)."""
    cp = min(2 * math.pi * mx, math.pi * mx + w, math.pi * mx + 2 * e)
    nc = min(4 * mx + 1.25 * ex, e + 2 * mx + 0.625 * ex, 0.5 * bp, 0.5 * w + 2 * mx + 0.625 * ex)
    return {"cp": cp, "nc": nc, "leff1": min(cp, nc), "leff2": nc}


def disc_in_rect(R, hx, hy):
    """Area of a disc of radius R (centre at the origin) inside the rectangle |x| <= hx, |y| <= hy (exact)."""
    if R <= 0:
        return 0.0

    def F(x):                                            # ∫ sqrt(R² - x²) dx
        x = min(max(x, -R), R)
        return 0.5 * (x * math.sqrt(max(R * R - x * x, 0.0)) + R * R * math.asin(x / R))

    def quadrant(a, b):                                  # area of {0<=x<=a, 0<=y<=b, x²+y²<=R²}
        xe = min(a, R)
        if R <= b:
            return F(xe) - F(0.0)
        xs = math.sqrt(R * R - b * b)                    # the circle leaves the line y = b at x = xs
        if xs >= xe:
            return b * xe
        return b * xs + F(xe) - F(xs)

    return 4.0 * quadrant(hx, hy)


def bearing_area(col, c, B, H, D=0.0, tc=0.0, bf=0.0, hc=0.0, tf=0.0, tw=0.0):
    """Effective area of the T-stubs in compression (EN 1993-1-8 6.2.5, Fig. 6.4), clipped to the plate B×H.
    I: Aeff = min(B, b+2c)·min(H, h+2c) - max(min(B, b+2c) - tw - 2c, 0)·max(h - 2tf - 2c, 0)
    (Wald, JRC Eurocodes workshop 2014, simple base plate example).
    CHS: annulus of width tc + 2c around the wall, π(D - tc)(tc + 2c), a full disc π(D + 2c)²/4 when the inner
    projection overlaps (c > D/2 - tc), intersected exactly with the plate B×H (SCI P358 Check 2 and Table G.33)."""
    if col.upper() == "CHS":
        Ro, Ri = D / 2 + c, max(D / 2 - tc - c, 0.0)
        return disc_in_rect(Ro, B / 2, H / 2) - disc_in_rect(Ri, B / 2, H / 2)
    bb, hh = min(B, bf + 2 * c), min(H, hc + 2 * c)
    return bb * hh - max(bb - tw - 2 * c, 0.0) * max(hc - 2 * tf - 2 * c, 0.0)


def ring_flange(D, tc, r2, e2, tp, fy, n, FtRd, gM0=None):
    """CHS flange (base) plate in tension with n bolts equally spaced on a circle of radius r2 around the tube:
    SCI P358 (2011) §6.8 Checks 2-4 (semi-empirical rules after the CIDECT design guide). N, mm, MPa.
    Check 2 plate: N = tp² fy π f3/(2γM0); Check 3 plate + bolts (prying): n F_t,Rd/(1 - 1/f3 + 1/(f3 ln(r1/r2)));
    Check 4 bolts: n F_t,Rd. f3 = (k3 + sqrt(k3² - 4k1))/(2k1), k1 = ln(r2/r3), k3 = k1 + 2, r3 = (D - tc)/2,
    r1 = r2 + e_eff, e_eff = min(e2, 1.25 e1), e1 = r2 - D/2."""
    gM0 = g("steel.gM0") if gM0 is None else gM0
    e1 = r2 - D / 2
    r3 = (D - tc) / 2
    k1 = math.log(r2 / r3)
    k3 = k1 + 2
    f3 = (k3 + math.sqrt(k3 * k3 - 4 * k1)) / (2 * k1)
    eeff = min(e2, g("connections.cidect_ring_eeff_per_e1") * e1)
    r1 = r2 + eeff
    N2 = tp ** 2 * fy * math.pi * f3 / (2 * gM0)
    N3 = n * FtRd / (1 - 1 / f3 + 1 / (f3 * math.log(r1 / r2))) / gM0
    return {"e1": e1, "r1": r1, "r2": r2, "r3": r3, "k1": k1, "k3": k3, "f3": f3, "eeff": eeff,
            "N_plate": N2, "N_plate_bolts": N3, "N_bolts": n * FtRd}


def baseplate(a):
    gM0, gM2, gC = g("steel.gM0"), g("steel.gM2"), g("steel.gC")
    acc = getattr(a, "alpha_cc", None)
    acc = g("connections.alpha_cc") if acc is None else acc
    fjd = g("connections.beta_j") * a.kj * acc * a.fck / gC
    c = a.tp * math.sqrt(a.fy / (3 * fjd * gM0))
    rows = []
    if a.col.upper() == "CHS":
        Aeff = bearing_area("CHS", c, a.B, a.H, D=a.D, tc=a.tc)
        lever_face = a.D / 2
    else:
        Aeff = bearing_area("I", c, a.B, a.H, bf=a.bf, hc=a.hc, tf=a.tfc, tw=a.twc)
        lever_face = a.hc / 2
    NcRd = Aeff * fjd / 1e3
    info = {"fjd": fjd, "c": c, "Aeff": Aeff, "NcRd": NcRd, "alpha_cc": acc}
    if a.Nc:
        rows.append(row(f"compression: A_eff={Aeff / 1e3:.1f}e3 mm², c={c:.0f} mm, f_jd={fjd:.1f} MPa [kN]",
                        a.Nc, NcRd, "6.2.5 / 6.2.8.2"))
    if a.Nt:
        fyb, fub, _ = BOLT[a.anchor_grade]
        As = AS.get(int(a.anchor_d), 0.78 * math.pi * a.anchor_d ** 2 / 4)
        FtRd = g("steel.k2_thread") * fub * As / gM2                           # N
        if a.layout == "ring":      # anchors equally spaced on a circle around a CHS (P358 §6.8 / CIDECT)
            if a.col.upper() != "CHS":
                raise SystemExit("--layout ring needs --col CHS")
            r2 = min(a.B, a.H) / 2 - a.edge
            ring = ring_flange(a.D, a.tc, r2, a.edge, a.tp, a.fy, a.anchors, FtRd, gM0)
            info.update({"ring": ring})
            rows.append(row(f"anchor bolt tension {a.anchor_grade} M{a.anchor_d:g} [kN/bolt]", a.Nt / a.anchors,
                            FtRd / 1e3, "T3.4"))
            tag = f"r2={r2:.0f}, e1={ring['e1']:.1f}, f3={ring['f3']:.2f}"
            rows.append(row(f"ring plate in bending ({tag}) [kN]", a.Nt, ring["N_plate"] / 1e3, "P358 6.8 Check 2"))
            rows.append(row(f"ring plate + anchors with prying (r1={ring['r1']:.0f}) [kN]", a.Nt,
                            ring["N_plate_bolts"] / 1e3, "P358 6.8 Check 3"))
        elif a.layout == "corners":   # anchors at plate corners, diagonal lever arm
            bolt_r = math.hypot(a.B / 2 - a.edge, a.H / 2 - a.edge)
        else:                       # anchors on the plate sides, opposite the column faces
            bolt_r = min(a.B, a.H) / 2 - a.edge
        if a.layout != "ring":
            m = max(bolt_r - lever_face - 0.8 * a.weld * math.sqrt(2), 10.0)
            le = leff_single_row(m, a.edge)
            # one T-stub = one anchor each side of the column wall -> resistances for 2 anchors, halved per anchor
            T = tstub(le["leff1"], le["leff2"], m, a.edge, a.tp, a.fy, 2 * FtRd)
            Lb = a.Lb if a.Lb else 8 * a.anchor_d + a.grout + a.tp + a.washer + 0.5 * 0.8 * a.anchor_d
            Lb_star = g("connections.Lb_star_coeff") * m ** 3 * As * 1 / (le["leff1"] * a.tp ** 3)
            prying = Lb <= Lb_star
            per = a.Nt / a.anchors
            info.update({"m": m, "leff": le, "tstub": T, "Lb": Lb, "Lb_star": Lb_star, "prying": prying})
            rows.append(row(f"anchor bolt tension {a.anchor_grade} M{a.anchor_d:g} [kN/bolt]", per, FtRd / 1e3, "T3.4"))
            tag = f"m={m:.0f}, l_eff={le['leff1']:.0f}, L_b={Lb:.0f} {'≤' if prying else '>'} L_b*={Lb_star:.0f}"
            if prying:
                rows.append(row(f"plate mode 1 ({tag}) [kN/bolt]", per, T["F1"] / 2e3, "6.2.4 T6.2"))
                rows.append(row("plate mode 2 (bolt + plate with prying) [kN/bolt]", per, T["F2"] / 2e3, "6.2.4 T6.2"))
            else:
                rows.append(row(f"plate mode 1-2, no prying ({tag}) [kN/bolt]", per, T["F12"] / 2e3, "6.2.4 T6.2"))
            rows.append(row("T-stub mode 3 (bolt failure) [kN/bolt]", per, T["F3"] / 2e3, "6.2.4 T6.2"))
    if a.V:
        fyb, fub, av = BOLT[a.anchor_grade]
        av = alpha_v(a.anchor_grade)
        As = AS.get(int(a.anchor_d), 0.78 * math.pi * a.anchor_d ** 2 / 4)
        Ff = g("connections.Cfd_sand_cement") * max(a.Nc, 0.0) if not a.Nt else 0.0
        FvbRd = min(av * fub * As / gM2, (0.44 - 0.0003 * min(max(fyb, 235), 640)) * fub * As / gM2) / 1e3
        rows.append(row("shear: friction C_f,d·Nc + anchors α_bc (6.2.2(6)(7)) [kN]", a.V,
                        Ff + a.anchors * FvbRd, "6.2.2"))
    return rows, info


# ------------------------------------------------------------ EN 1992-4 anchors
def _c(c):
    return INF if c is None else float(c)


def proj_len(n, s, c_lo, c_hi, half):
    """length of the idealised projected area in one direction: min(c,half) + Σ min(s, 2 half) + min(c,half)."""
    return min(_c(c_lo), half) + max(n - 1, 0) * min(s, 2 * half) + min(_c(c_hi), half)


def cone_NRk(k1, fck, hef, n1, n2, s1, s2, cx_lo, cx_hi, cy_lo, cy_hi, psi_re=1.0, eN1=0.0, eN2=0.0,
             scr=None, ccr=None):
    """EN 1992-4 7.2.1.4 concrete cone (Eq. 7.1-7.6) of a rectangular group, kN. Edge distances None = no edge."""
    scr = g("anchor_EN1992_4.s_cr_N_per_hef") * hef if scr is None else scr
    ccr = g("anchor_EN1992_4.c_cr_N_per_hef") * hef if ccr is None else ccr
    N0 = k1 * math.sqrt(fck) * hef ** 1.5 / 1e3
    A0 = scr ** 2
    Ac = proj_len(n1, s1, cx_lo, cx_hi, ccr) * proj_len(n2, s2, cy_lo, cy_hi, ccr)
    cmin = min(_c(cx_lo), _c(cx_hi), _c(cy_lo), _c(cy_hi))
    psi_s = min(1.0, 0.7 + 0.3 * cmin / ccr)
    psi_ec = 1 / (1 + 2 * eN1 / scr) * 1 / (1 + 2 * eN2 / scr)
    return {"N0": N0, "A0": A0, "Ac": Ac, "psi_s": psi_s, "psi_ec": psi_ec,
            "NRk": N0 * Ac / A0 * psi_s * psi_re * psi_ec, "scr": scr, "ccr": ccr, "cmin": cmin}


def splitting_NRk(N0sp, hef, n1, n2, s1, s2, cx_lo, cx_hi, cy_lo, cy_hi, ccr_sp, h, hmin, scr_sp=None,
                  psi_re=1.0, eN1=0.0, eN2=0.0):
    """EN 1992-4 7.2.1.7 Eq. (7.23)/(7.24): N_Rk,sp = N0_Rk,sp·A_c,N/A0_c,N·ψs,N·ψre,N·ψec,N·ψh,sp with
    s_cr,sp, c_cr,sp in place of s_cr,N, c_cr,N. N0sp = min(N_Rk,p, N0_Rk,c) [kN]."""
    scr_sp = 2 * ccr_sp if scr_sp is None else scr_sp
    A0 = scr_sp ** 2
    Ac = proj_len(n1, s1, cx_lo, cx_hi, ccr_sp) * proj_len(n2, s2, cy_lo, cy_hi, ccr_sp)
    c1 = min(_c(cx_lo), _c(cx_hi), _c(cy_lo), _c(cy_hi))
    psi_s = min(1.0, 0.7 + 0.3 * c1 / ccr_sp)
    psi_ec = 1 / (1 + 2 * eN1 / scr_sp) * 1 / (1 + 2 * eN2 / scr_sp)
    cap = max(1.0, ((hef + 1.5 * min(c1, 1e9)) / hmin) ** (2 / 3))
    psi_h = min((h / hmin) ** (2 / 3), cap, g("anchor_EN1992_4.splitting_psi_h_max"))
    return {"Ac": Ac, "A0": A0, "psi_s": psi_s, "psi_ec": psi_ec, "psi_h": psi_h,
            "NRk": N0sp * Ac / A0 * psi_s * psi_re * psi_ec * psi_h}


def gamma_Ms_shear(fuk, fyk):
    if fuk <= 800 and fyk / fuk <= 0.8:
        return max(1.0 * fuk / fyk, 1.25)
    return 1.5


def steel_shear(As, fuk, fyk, ductile=True):
    """EN 1992-4 7.2.2.3.1: V_Rk,s = k7·k6·A_s·f_uk [kN], γMs (Table 4.1)."""
    k6 = g("anchor_EN1992_4.k6_fuk_le_500") if fuk <= 500 else g("anchor_EN1992_4.k6_fuk_gt_500")
    k7 = g("anchor_EN1992_4.k7_ductile") if ductile else g("anchor_EN1992_4.k7_brittle")
    V0 = k6 * As * fuk / 1e3
    return {"k6": k6, "k7": k7, "V0": V0, "VRk": k7 * V0, "gMs": gamma_Ms_shear(fuk, fyk)}


def steel_shear_lever(As, fuk, fyk, dnom, e1, NEd_over_NRds=0.0, alphaM=None, a3=None):
    """EN 1992-4 7.2.2.3.2: V_Rk,s,M = αM·M_Rk,s/l_a, M_Rk,s = 1.2·W_el·f_uk·(1 - N_Ed/N_Rd,s),
    W_el of the stressed section (diameter from A_s), l_a = a3 + e1, a3 = 0.5 d_nom. kN, kNm."""
    alphaM = g("anchor_EN1992_4.alpha_M_restrained") if alphaM is None else alphaM
    a3 = g("anchor_EN1992_4.a3_per_dnom") * dnom if a3 is None else a3
    ds = math.sqrt(4 * As / math.pi)
    Wel = math.pi * ds ** 3 / 32
    M0 = g("anchor_EN1992_4.M0_Rks_factor") * Wel * fuk / 1e6
    M = M0 * max(0.0, 1 - NEd_over_NRds)
    la = a3 + e1
    return {"M0": M0, "MRk": M, "la": la, "VRk": alphaM * M * 1e3 / la, "gMs": gamma_Ms_shear(fuk, fyk),
            "alphaM": alphaM}


def edge_VRk(c1, c2a, c2b, n2, s2, h, dnom, lf, fck, cracked=True, alpha_deg=0.0, eV=0.0, psi_re=1.0):
    """EN 1992-4 7.2.2.5 concrete edge failure of the row of n2 fasteners nearest the edge (spacing s2 parallel
    to the edge), shear towards the edge at distance c1. c2a/c2b = side edge distances (None = none),
    h = member thickness (None = thick). Eq. (7.40)-(7.48), narrow thin member c1' (7.50). kN."""
    c2a, c2b, h = _c(c2a), _c(c2b), _c(h)
    c2max = max(c2a, c2b)
    s2max = s2 if n2 > 1 else 0.0
    c1_used = c1
    if c2max <= 1.5 * c1 and h <= 1.5 * c1:
        c1_used = max(c2max / 1.5, h / 1.5, s2max / 3)
    c = c1_used
    lf = min(lf, 12 * dnom) if dnom <= 24 else min(lf, max(8 * dnom, 300.0))
    a_ = 0.1 * (lf / c) ** 0.5
    b_ = 0.1 * (dnom / c) ** 0.2
    k9 = g("anchor_EN1992_4.k9_cracked" if cracked else "anchor_EN1992_4.k9_uncracked")
    V0 = k9 * dnom ** a_ * lf ** b_ * math.sqrt(fck) * c ** 1.5 / 1e3
    A0 = g("anchor_EN1992_4.A0cV_per_c1sq") * c ** 2
    width = min(c2a, 1.5 * c) + max(n2 - 1, 0) * min(s2, 3 * c) + min(c2b, 1.5 * c)
    Ac = width * min(h, 1.5 * c)
    psi_s = min(1.0, 0.7 + 0.3 * min(c2a, c2b) / (1.5 * c))
    psi_h = max(1.0, (1.5 * c / h) ** 0.5) if h < INF else 1.0
    psi_ec = min(1.0, 1 / (1 + 2 * eV / (3 * c)))
    al = math.radians(alpha_deg)
    psi_a = max(1.0, math.sqrt(1 / (math.cos(al) ** 2 + (0.5 * math.sin(al)) ** 2)))
    VRk = V0 * Ac / A0 * psi_s * psi_h * psi_ec * psi_a * psi_re
    return {"c1": c, "alpha": a_, "beta": b_, "lf": lf, "V0": V0, "A0": A0, "Ac": Ac, "psi_s": psi_s,
            "psi_h": psi_h, "psi_ec": psi_ec, "psi_a": psi_a, "VRk": VRk, "k9": k9}


def interaction(betaN_s, betaV_s, betaN_c, betaV_c):
    """EN 1992-4 Table 7.3: steel βN² + βV² ≤ 1; concrete βN^1.5 + βV^1.5 ≤ 1 (largest β of each type)."""
    es, ec = g("anchor_EN1992_4.interaction_exp_steel"), g("anchor_EN1992_4.interaction_exp_concrete")
    return betaN_s ** es + betaV_s ** es, betaN_c ** ec + betaV_c ** ec


def anchor_group(n1, n2, s1, s2, c1, c2, hef, d, dh, grade, fck, NEd, cracked=True, psi_re=1.0,
                 c1b=None, c2b=None, k1=None, V=0.0, cv=None, cv2a=None, cv2b=None, h=None, alpha_v_deg=0.0,
                 eV=0.0, psi_re_v=1.0, standoff=None, alphaM=None, dnom=None, lf=None, ccr_sp=None, hmin=None,
                 ductile=True, A_shear=None, eN1=0.0, eN2=0.0):
    """Cast-in headed anchors, rectangular group n1 × n2 (spacings s1/s2), edge distances c1 (direction 1,
    both sides unless c1b) and c2 (direction 2, both sides unless c2b) [mm]. N_Ed tension [kN] on the group
    (uniform), V shear [kN] on the group towards the edge at cv (default c1) — the n2 fasteners of the row
    nearest that edge take it (normal hole clearance). Rows 0-2 (steel, pull-out, cone) keep their order."""
    fyb, fub, _ = BOLT[grade]
    As = AS.get(int(d), 0.78 * math.pi * d * d / 4)
    gMs = max(1.2 * fub / fyb, 1.4)                               # EN 1992-4 Table 4.1
    gMc = g("anchor_EN1992_4.gamma_Mc")
    n = n1 * n2
    NRks = As * fub / 1e3
    k2 = g("anchor_EN1992_4.k2_pullout_cracked" if cracked else "anchor_EN1992_4.k2_pullout_uncracked")
    Ah = math.pi / 4 * (dh ** 2 - d ** 2)
    NRkp = k2 * Ah * fck / 1e3
    k1 = g("anchor_EN1992_4.k_cr_N" if cracked else "anchor_EN1992_4.k_ucr_N") if k1 is None else k1
    cone = cone_NRk(k1, fck, hef, n1, n2, s1, s2, c1, c1 if c1b is None else c1b, c2, c2 if c2b is None else c2b,
                    psi_re, eN1, eN2)
    NRkc = cone["NRk"]
    rows = [
        row(f"steel failure per anchor M{d:g} {grade} (γMs={gMs:.2f}) [kN]", NEd / n, NRks / gMs, "EN 1992-4 7.2.1.3"),
        row(f"pull-out per anchor (k2={k2}, A_h={Ah:.0f} mm²) [kN]", NEd / n, NRkp / gMc, "EN 1992-4 7.2.1.5"),
        row(f"concrete cone, group (N0={cone['N0']:.1f} kN, Ac/A0={cone['Ac'] / cone['A0']:.2f}, "
            f"ψs={cone['psi_s']:.2f}) [kN]", NEd, NRkc / gMc, "EN 1992-4 7.2.1.4"),
    ]
    info = {"N0_Rk_c": cone["N0"], "NRk_c": NRkc, "gMs": gMs, "gMc": gMc, "cone": cone}
    betaN_s = (NEd / n) / (NRks / gMs) if NEd else 0.0
    betaN_c = max(((NEd / n) / (NRkp / gMc)), NEd / (NRkc / gMc)) if NEd else 0.0
    if ccr_sp and hmin:
        hh = _c(h)
        sp = splitting_NRk(min(NRkp, cone["N0"]), hef, n1, n2, s1, s2, c1, c1 if c1b is None else c1b, c2,
                           c2 if c2b is None else c2b, ccr_sp, hh, hmin, psi_re=psi_re, eN1=eN1, eN2=eN2)
        info["split"] = sp
        rows.append(row(f"splitting, group (c_cr,sp={ccr_sp:g}, ψh,sp={sp['psi_h']:.2f}) [kN]", NEd,
                        sp["NRk"] / gMc, "EN 1992-4 7.2.1.7"))
        if NEd:
            betaN_c = max(betaN_c, NEd / (sp["NRk"] / gMc))
    if V:
        dnom = d if dnom is None else dnom
        lf = hef if lf is None else lf
        Av = As if A_shear is None else A_shear
        st = steel_shear(Av, fub, fyb, ductile)
        info["steel_shear"] = st
        rows.append(row(f"shear steel, no lever arm per anchor (k6={st['k6']}, γMs={st['gMs']:.2f}) [kN]",
                        V / n, st["VRk"] / st["gMs"], "EN 1992-4 7.2.2.3.1"))
        betaV_s = (V / n) / (st["VRk"] / st["gMs"])
        if standoff is not None:
            sl = steel_shear_lever(As, fub, fyb, dnom, standoff, betaN_s, alphaM)
            info["steel_lever"] = sl
            rows.append(row(f"shear steel with lever arm l_a={sl['la']:.0f} (αM={sl['alphaM']:g}) per anchor [kN]",
                            V / n, sl["VRk"] / sl["gMs"], "EN 1992-4 7.2.2.3.2"))
            betaV_s = max(betaV_s, (V / n) / (sl["VRk"] / sl["gMs"]))
        k8 = g("anchor_EN1992_4.k8_hef_ge_60" if hef >= 60 else "anchor_EN1992_4.k8_hef_lt_60")
        rows.append(row(f"pry-out, group (k8={k8:g}) [kN]", V, k8 * NRkc / gMc, "EN 1992-4 7.2.2.4"))
        betaV_c = V / (k8 * NRkc / gMc)
        cvv = c1 if cv is None else cv
        if cvv is not None and cvv < INF:
            ed = edge_VRk(cvv, c2 if cv2a is None else cv2a, (c2 if c2b is None else c2b) if cv2b is None else cv2b,
                          n2, s2, h, dnom, lf, fck, cracked, alpha_v_deg, eV, psi_re_v)
            info["edge"] = ed
            rows.append(row(f"concrete edge, front row c1={ed['c1']:.0f} (V0={ed['V0']:.1f}, Ac/A0="
                            f"{ed['Ac'] / ed['A0']:.2f}, ψs={ed['psi_s']:.2f}, ψh={ed['psi_h']:.2f}) [kN]",
                            V, ed["VRk"] / gMc, "EN 1992-4 7.2.2.5"))
            betaV_c = max(betaV_c, V / (ed["VRk"] / gMc))
        if NEd:
            i_s, i_c = interaction(betaN_s, betaV_s, betaN_c, betaV_c)
            info["interaction"] = (i_s, i_c)
            rows.append(row(f"interaction steel βN²+βV² (βN={betaN_s:.2f}, βV={betaV_s:.2f}) [-]", i_s, 1.0,
                            "EN 1992-4 T7.3"))
            rows.append(row(f"interaction concrete βN^1.5+βV^1.5 (βN={betaN_c:.2f}, βV={betaV_c:.2f}) [-]", i_c, 1.0,
                            "EN 1992-4 T7.3"))
    return rows, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--factors", default=None, help="project code-factor file (before the sub-command)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    w = sp.add_parser("weld", help="double fillet T-joint of a lug/gusset (directional + simplified)")
    w.add_argument("--F", type=float, required=True, help="design force [kN]")
    w.add_argument("--angle", type=float, default=90.0, help="force angle to weld line [deg] (90 = normal)")
    w.add_argument("--L", type=float, required=True, help="effective weld length (each side) [mm]")
    w.add_argument("--a", type=float, required=True, help="throat thickness [mm]")
    w.add_argument("--e", type=float, default=0.0, help="lever arm weld line -> hole centre [mm]")
    w.add_argument("--x", type=float, default=0.0, help="offset of load line from weld centroid along weld [mm]")
    w.add_argument("--grade", default="S355", choices=list(FU))
    w.add_argument("--fu", type=float, default=None, help="f_u of the weaker part [MPa] (default by grade)")
    w.add_argument("--sides", type=int, default=2)

    b = sp.add_parser("bolts", help="bolt group: shear, bearing, tension, punching, combined")
    b.add_argument("--n-rows", type=int, default=1)
    b.add_argument("--n-cols", type=int, default=1)
    b.add_argument("--p1", type=float, default=0.0, help="pitch between rows (along y, direction 1) [mm]")
    b.add_argument("--p2", type=float, default=0.0, help="pitch between columns (along x) [mm]")
    b.add_argument("--coords", default=None, help="explicit 'x:y;x:y;...' [mm] (overrides grid)")
    b.add_argument("--Vx", type=float, default=0.0)
    b.add_argument("--Vy", type=float, default=0.0)
    b.add_argument("--M", type=float, default=0.0, help="in-plane moment about group centroid [kNm]")
    b.add_argument("--N", type=float, default=0.0, help="total tension [kN]")
    b.add_argument("--prying", type=float, default=1.0)
    b.add_argument("--d", type=float, required=True)
    b.add_argument("--d0", type=float, default=None, help="hole diameter [mm] (default d+1/2/3)")
    b.add_argument("--grade", default="8.8", choices=list(BOLT))
    b.add_argument("--t", type=float, required=True, help="thinnest ply in bearing [mm]")
    b.add_argument("--fu-plate", type=float, default=490.0)
    b.add_argument("--e1", type=float, default=0.0, help="end distance along y (0 = no end) [mm]")
    b.add_argument("--e2", type=float, default=0.0, help="edge distance along x (0 = no edge) [mm]")
    b.add_argument("--shank", action="store_true", help="shear plane through unthreaded shank")

    gu = sp.add_parser("gusset", help="bolted gusset/corner plate: bolts, block tearing, Whitmore, buckling")
    gu.add_argument("--F", type=float, required=True, help="axial force [kN], + tension / - compression")
    gu.add_argument("--n1", type=int, required=True, help="bolt rows along the force")
    gu.add_argument("--n2", type=int, default=1, help="bolt columns across the force")
    gu.add_argument("--p1", type=float, default=0.0)
    gu.add_argument("--p2", type=float, default=0.0)
    gu.add_argument("--e1", type=float, required=True, help="end distance of the last row to the plate end [mm]")
    gu.add_argument("--e2", type=float, required=True, help="edge distance of the outer column [mm]")
    gu.add_argument("--d", type=float, required=True)
    gu.add_argument("--d0", type=float, default=None)
    gu.add_argument("--grade", default="8.8", choices=list(BOLT))
    gu.add_argument("--t", type=float, required=True, help="gusset thickness [mm]")
    gu.add_argument("--fy", type=float, default=355.0)
    gu.add_argument("--fu", type=float, default=490.0)
    gu.add_argument("--width", type=float, default=None, help="gusset width at the Whitmore section [mm]")
    gu.add_argument("--l-avg", type=float, default=None, help="Thornton average free length (compression) [mm]")
    gu.add_argument("--K", type=float, default=None, help="effective length factor (default register 0.65)")
    gu.add_argument("--block", choices=["U", "L"], default="U",
                    help="U = two shear planes, concentric (3.9); L = one shear plane, eccentric (3.10)")
    gu.add_argument("--aisc", action="store_true", help="also AISC 360 J4.1/J4.4 Whitmore checks (φ from register)")
    gu.add_argument("--shank", action="store_true")

    c = sp.add_parser("clampbar", help="membrane clamp-bar / keder plate bolts")
    c.add_argument("--n", type=float, required=True, help="membrane stress at the clamp line [kN/m]")
    c.add_argument("--spacing", type=float, required=True, help="bolt spacing [mm]")
    c.add_argument("--d", type=float, default=12.0)
    c.add_argument("--grade", default="A4-70", choices=list(BOLT))
    c.add_argument("--t", type=float, default=10.0, help="ply in bearing [mm]")
    c.add_argument("--fu-plate", type=float, default=490.0)
    c.add_argument("--mode", choices=["shear", "tension"], default="shear")
    c.add_argument("--prying", type=float, default=1.3)
    c.add_argument("--peak", type=float, default=1.5, help="stress concentration factor at clamp line")
    c.add_argument("--plate", choices=["steel", "alu6082"], default="steel",
                   help="bearing ply material (alu6082: EN 1999-1-1 Table 8.5, f_u and γM2 from the register)")

    an = sp.add_parser("anchor", help="EN 1992-4 cast-in headed anchors: tension, shear, interaction")
    an.add_argument("--n1", type=int, default=2)
    an.add_argument("--n2", type=int, default=2)
    an.add_argument("--s1", type=float, default=200.0)
    an.add_argument("--s2", type=float, default=200.0)
    an.add_argument("--c1", type=float, default=300.0, help="edge distance in direction 1 [mm] (both sides)")
    an.add_argument("--c1b", type=float, default=None, help="edge distance on the other side in direction 1")
    an.add_argument("--c2", type=float, default=300.0, help="edge distance in direction 2 [mm] (both sides)")
    an.add_argument("--c2b", type=float, default=None, help="edge distance on the other side in direction 2")
    an.add_argument("--hef", type=float, required=True, help="effective embedment [mm]")
    an.add_argument("--d", type=float, default=24.0)
    an.add_argument("--dh", type=float, default=None, help="head / washer plate diameter [mm] (default 1.9 d)")
    an.add_argument("--grade", default="8.8", choices=list(BOLT))
    an.add_argument("--fck", type=float, default=30.0)
    an.add_argument("--N", type=float, default=0.0, help="design tension on the group [kN]")
    an.add_argument("--uncracked", action="store_true")
    an.add_argument("--psi-re", type=float, default=1.0, help="shell spalling factor (0.5 + hef/200 ≤ 1 if dense reinforcement)")
    an.add_argument("--k1", type=float, default=None, help="cone factor from the ETA (post-installed); default cast-in headed")
    an.add_argument("--ccr-sp", type=float, default=None, help="c_cr,sp from the ETA/product data [mm] (splitting)")
    an.add_argument("--hmin", type=float, default=None, help="h_min from the ETA/product data [mm] (splitting)")
    an.add_argument("--V", type=float, default=0.0, help="design shear on the group [kN]")
    an.add_argument("--cv", type=float, default=None, help="edge distance in the shear direction [mm] (default c1)")
    an.add_argument("--no-edge", action="store_true", help="no edge in the shear direction (skip edge failure)")
    an.add_argument("--cv2a", type=float, default=None, help="side edge distance of the front row (default c2)")
    an.add_argument("--cv2b", type=float, default=None, help="other side edge distance of the front row")
    an.add_argument("--h", type=float, default=None, help="member thickness [mm] (thin members, splitting)")
    an.add_argument("--alpha-v", type=float, default=0.0, help="angle of V to the edge normal [deg]")
    an.add_argument("--eV", type=float, default=0.0, help="eccentricity of V on the front row [mm]")
    an.add_argument("--edge-reinf", action="store_true", help="cracked concrete with edge reinforcement: ψre,V=1.4")
    an.add_argument("--standoff", type=float, default=None,
                    help="e1 = distance shear load -> concrete surface [mm] (stand-off/grout + t/2): lever-arm check")
    an.add_argument("--alphaM", type=float, default=None, help="2 = fixture restrained (default), 1 = free rotation")
    an.add_argument("--brittle", action="store_true", help="steel rupture elongation ≤ 8 %: k7 = 0.8")
    an.add_argument("--A-shear", type=float, default=None, help="steel area in shear [mm²] (default A_s)")

    p = sp.add_parser("baseplate", help="column/mast base plate: compression, uplift T-stub, shear")
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
    p.add_argument("--kj", type=float, default=1.5, help="concentration factor √(A_c1/A_c0) ≤ 3 (1.0 conservative)")
    p.add_argument("--alpha-cc", type=float, default=None,
                   help="α_cc of EN 1992-1-1 3.1.6 in f_cd (default register connections.alpha_cc = 1.0; UK NA 0.85)")
    p.add_argument("--Nc", type=float, default=0.0, help="compression [kN] (compression combination)")
    p.add_argument("--Nt", type=float, default=0.0,
                   help="uplift [kN] (uplift combination; if given, no friction is credited for --V)")
    p.add_argument("--V", type=float, default=0.0, help="shear [kN]")
    p.add_argument("--anchors", type=int, default=4)
    p.add_argument("--anchor-d", type=float, default=24.0)
    p.add_argument("--anchor-grade", default="8.8", choices=list(BOLT))
    p.add_argument("--edge", type=float, default=60.0, help="anchor axis to plate edge [mm]")
    p.add_argument("--weld", type=float, default=6.0, help="column-to-plate weld throat [mm]")
    p.add_argument("--layout", choices=["corners", "sides", "ring"], default="corners",
                   help="anchor position: corners / sides (T-stub per anchor) or ring = --anchors equally spaced on "
                        "a circle of radius min(B,H)/2 - edge around a CHS (SCI P358 6.8 / CIDECT ring flange)")
    p.add_argument("--Lb", type=float, default=None, help="anchor elongation length [mm] (default 8d+grout+tp+washer+0.4d)")
    p.add_argument("--grout", type=float, default=30.0, help="grout thickness for the default L_b [mm]")
    p.add_argument("--washer", type=float, default=5.0, help="washer thickness for the default L_b [mm]")

    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    print(f"Factors: {CF.tag('steel.gM0')}, {CF.tag('steel.gM2')}" + (f", {CF.tag('steel.gC')}" if a.cmd == "baseplate" else ""))
    if a.cmd == "weld":
        rows, info = weld(a.F, a.angle, a.L, a.a, a.e, a.x, a.grade, a.sides, a.fu)
        print(f"Weld: {a.sides} x fillet a={a.a:g} L={a.L:g} mm, {a.grade} (fu={info['fu']}, βw={info['beta_w']} [C]); "
              f"N⊥={info['N_kN']:.1f} kN, V∥={info['V_kN']:.1f} kN, M={info['M_kNm']:.2f} kNm")
        print("Assumptions: T-joint fillets at 45° (σ⊥ = τ⊥ = n/(a√2)); moment resisted elastically by the weld "
              "lines (W = sides·L²/6); L is the effective length (deduct 2a if end returns are missing).")
        return report("", rows)
    if a.cmd == "bolts":
        coords = ([tuple(map(float, s.split(":"))) for s in a.coords.split(";")] if a.coords
                  else grid(a.n_rows, a.n_cols, a.p1, a.p2))
        rows, R = bolts(coords, a.Vx, a.Vy, a.M, a.N, a.prying, a.d, a.grade, a.t, a.fu_plate,
                        a.e1, a.e2, a.p1, a.p2, not a.shank, a.d0)
        print(f"{len(coords)} bolts M{a.d:g} {a.grade} (d0={R['d0']:g}, As={R['As']:g} mm², αv={R['av']:g})")
        print("Assumptions: elastic bolt-group method (rigid plate); bearing per bolt with the end/inner and "
              "edge/inner minimum of αd and k1 (conservative); normal round holes; tension shared equally × prying.")
        return report("", rows)
    if a.cmd == "gusset":
        rows, info = gusset(a.F, a.n1, a.n2, a.p1, a.p2, a.e1, a.e2, a.d, a.d0, a.grade, a.t, a.fy, a.fu,
                            a.width, a.l_avg, a.K, a.block, a.aisc, not a.shank)
        print(f"Gusset t={a.t:g} f_y={a.fy:g}: {a.n1}x{a.n2} M{a.d:g} {a.grade}, Whitmore b_e={info['be']:.0f} mm "
              f"({CF.tag('connections.whitmore_angle_deg')}), {CF.tag('connections.K_thornton')}, "
              f"{CF.tag('connections.alpha_curve_c')}")
        print("Assumptions: concentric axial force shared equally by the bolts; Whitmore width at the last row; "
              "compression = equivalent column K·l_avg (Thornton) on the Whitmore width — no plate FE, no free-edge "
              "buckling check; block tearing EN 1993-1-8:2005 (2024 edition differs).")
        return report("", rows)
    if a.cmd == "clampbar":
        F = a.n * a.peak * a.spacing / 1e3  # kN per bolt
        if a.mode == "shear":
            rows, R = bolts([(0, 0)], 0, F, 0, 0, 1, a.d, a.grade, a.t, a.fu_plate, 3 * a.d, 1.5 * a.d, 0, 0, True)
            if a.plate == "alu6082":
                fu_al = g("aluminium.6082T6_fu_thin" if a.t <= 5 else "aluminium.6082T6_fu_thick")
                gM2a = g("aluminium.gM2")
                d0 = R["d0"]
                k1, ab = bearing_k1_ab(d0, BOLT[a.grade][1], fu_al, 3 * a.d, 1.5 * a.d, 0, 0)
                FbA = k1 * ab * fu_al * a.d * a.t / gM2a / 1e3
                rows = [r for r in rows if not r[0].startswith("bearing")]
                rows.append(row(f"bearing on aluminium 6082-T6 t={a.t:g} (f_u={fu_al}, γM2={gM2a}, k1={k1:.2f}, "
                                f"αb={ab:.2f}) [kN]", F, FbA, f"EN 1999-1-1 T8.5 [{CF.status('aluminium.bearing_formula')}]"))
        else:
            rows, R = bolts([(0, 0)], 0, 0, 0, F, a.prying, a.d, a.grade, a.t, a.fu_plate, 3 * a.d, 1.5 * a.d, 0, 0, True)
        print(f"Clamp line: n={a.n} kN/m × peak {a.peak} × spacing {a.spacing:g} mm = {F:.2f} kN per bolt ({a.mode})")
        print(f"Assumptions: e1 = 3d, e2 = 1.5d; αv = {R['av']:g} "
              f"({CF.tag('aluminium.alpha_v_stainless_bolt')} for stainless); single bolt per segment length.")
        if a.spacing > 200:
            print("NOTE: TensiNet guidance: clamp bolt spacing hardly more than ~200 mm [V]")
        print("Aluminium clamp plate bending and keder pull-out: check to EN 1999-1-1 / by test separately.")
        return report("", rows)
    if a.cmd == "anchor":
        dh = a.dh or 1.9 * a.d
        rows, info = anchor_group(a.n1, a.n2, a.s1, a.s2, a.c1, a.c2, a.hef, a.d, dh, a.grade, a.fck, a.N,
                                  not a.uncracked, a.psi_re, c1b=a.c1b, c2b=a.c2b, k1=a.k1, V=a.V,
                                  cv=(INF if a.no_edge else a.cv), cv2a=a.cv2a, cv2b=a.cv2b, h=a.h,
                                  alpha_v_deg=a.alpha_v, eV=a.eV,
                                  psi_re_v=(g("anchor_EN1992_4.psi_re_V_edge_reinf") if a.edge_reinf else 1.0),
                                  standoff=a.standoff, alphaM=a.alphaM, ccr_sp=a.ccr_sp, hmin=a.hmin,
                                  ductile=not a.brittle, A_shear=a.A_shear)
        print(f"{a.n1}x{a.n2} cast-in headed anchors M{a.d:g} {a.grade}, h_ef={a.hef:g} mm, C{a.fck:g} "
              f"{'uncracked' if a.uncracked else 'cracked'}; factors {CF.tag('anchor_EN1992_4.gamma_Mc')}, "
              f"{CF.tag('anchor_EN1992_4.k_cr_N')}, {CF.tag('anchor_EN1992_4.k9_cracked')}, "
              f"{CF.tag('anchor_EN1992_4.k8_hef_ge_60')}")
        print("Assumptions: rigid fixture, uniform tension and shear sharing, normal hole clearance (EN 1992-4 "
              "Table 6.1) so the row nearest the edge takes all of V for edge failure; edge distances given "
              "apply to the outermost anchors.")
        notes = ["blow-out (side-face, c < 0.5 h_ef)", "anchor/supplementary reinforcement",
                 "h'_ef reduction for ≥ 3 edges closer than c_cr,N", "fatigue / seismic", "torsion on the group"]
        if not (a.ccr_sp and a.hmin):
            notes.insert(0, "splitting (give --ccr-sp and --hmin from the ETA)")
        print("Not included: " + "; ".join(notes) + ".")
        if min(a.c1, a.c2) < 0.5 * a.hef:
            print(f"WARNING: edge distance < 0.5 h_ef = {0.5 * a.hef:.0f} mm: blow-out governs possibly — not checked.")
        return report("", rows)
    rows, info = baseplate(a)
    print(f"Base plate {a.B:g}x{a.H:g}x{a.tp:g} S{int(a.fy)} on C{a.fck:g}; column {a.col}; "
          f"{CF.tag('connections.beta_j')}, k_j={a.kj:g}, α_cc={info['alpha_cc']:g} "
          f"[{'project' if a.alpha_cc is not None else CF.status('connections.alpha_cc')}], "
          f"{CF.tag('connections.Cfd_sand_cement')}")
    print("Assumptions: f_jd = β_j k_j α_cc f_ck/γ_c; compression on the equivalent T-stub area (CHS: annulus "
          "π(D−t)(t+2c), full disc if the inner projections overlap, intersected exactly with the plate); rigid "
          "plate, no plate FE.")
    if a.Nt and a.layout == "ring":
        print("Uplift (ring): SCI P358 6.8 / CIDECT ring-flange rules for a CHS with bolts equally spaced around it "
              "(≥ 4); e2 = --edge to the nearest plate edge; prying assumed (conservative for long anchors).")
        if a.anchors < 4:
            print("WARNING: the ring-flange rules need at least 4 equally spaced anchors (P358 6.8 Check 1).")
    elif a.Nt:
        print("Uplift: per anchor as a T-stub with one anchor each side of the column wall, l_eff = min(2πm, "
              "4m+1.25e) (EN 1993-1-8 Table 6.4 pattern, not a CHS-specific yield-line solution); prying from "
              "L_b vs L_b*. For anchors on a circle around a CHS use --layout ring.")
    print("Anchor embedment / concrete breakout / pull-out: use the `anchor` sub-command (EN 1992-4).")
    return report("", rows)


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
