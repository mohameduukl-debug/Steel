#!/usr/bin/env python3
"""AISC 360-22 member checks (US) and SBC 306 (Saudi, AISC-based, LRFD only) for CHS, RHS/SHS and
doubly-symmetric I sections. Called by member_check.py --code US|SA; usable on its own.

Covered
  * compression: E3 flexural buckling about both axes, E4 torsional buckling (I sections),
    E7 slender elements (round HSS A_e formula; effective widths for RHS walls and I flanges/webs)
  * tension: D2 yielding (rupture on the net section: check separately)
  * flexure: F2 (I, compact web: yielding + LTB), F3 (noncompact/slender flanges), F6 (I minor axis),
    F7 (RHS: flange and web local buckling, LTB), F8 (round HSS)
  * shear: G2.1 (I web), G4 (RHS), G5 (round HSS), G6 (I minor axis)
  * interaction: H1-1 with B1 = C_m/(1 − α·P_r/P_e1) (Appendix 8, effective-length method) unless the
    moments are already second-order (--second-order)

φ / Ω from the register (aisc.*). SBC 306-18: φc = 0.85, φv = 0.90 [U, AR text] and LRFD only.
Units: kN, kNm, m; section dimensions mm; Fy MPa.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as CF  # noqa: E402

G_STEEL = 77200.0  # MPa (AISC G = 11 200 ksi)


def factors(code="US", method="LRFD", phi_c=None, phi_v=None):
    """resistance factors (LRFD φ) or 1/Ω (ASD), so capacity = factor × nominal in both cases."""
    if code == "SA" and method != "LRFD":
        raise SystemExit("SBC 306 is LRFD only (no ASD / Ω)")
    if method == "ASD":
        return {"c": 1 / CF.get("aisc.Omega_c"), "b": 1 / CF.get("aisc.Omega_b"), "t": 1 / CF.get("aisc.Omega_t"),
                "v": 1 / CF.get("aisc.Omega_v"), "v_rolled": 1 / 1.50, "label": "ASD: R_n/Ω"}
    f = {"c": CF.get("aisc.phi_c"), "b": CF.get("aisc.phi_b"), "t": CF.get("aisc.phi_yield"),
         "v": CF.get("aisc.phi_v"), "v_rolled": 1.0, "label": "LRFD: φR_n"}
    if code == "SA":
        f["c"] = CF.get("sbc.phi_c_306") if phi_c is None else phi_c
        f["v"] = f["v_rolled"] = CF.get("sbc.phi_v_306") if phi_v is None else phi_v
        f["label"] = "LRFD (SBC 306): φR_n"
    return f


# ------------------------------------------------------------ element slenderness / E7
def _be(b, t, lam_r, c1, c2, Fy, Fn):
    lam = b / t
    if lam <= lam_r * math.sqrt(Fy / Fn):
        return b
    Fel = (c2 * lam_r / lam) ** 2 * Fy
    return b * (1 - c1 * math.sqrt(Fel / Fn)) * math.sqrt(Fel / Fn)


def effective_area(sec, Fy, Fn, E):
    """A_e for E7 (mm²) and a note."""
    if sec.kind == "CHS":
        Dt = sec.D / sec.t
        if Dt <= 0.11 * E / Fy:
            return sec.A, "round HSS nonslender (D/t ≤ 0.11E/Fy)"
        if Dt >= 0.45 * E / Fy:
            raise SystemExit("round HSS with D/t ≥ 0.45E/Fy: outside AISC 360 (E7.2)")
        return (0.038 * E / (Fy * Dt) + 2 / 3) * sec.A, "round HSS slender: A_e = [0.038E/(Fy·D/t) + 2/3]·A_g"
    rt = math.sqrt(E / Fy)
    if sec.kind == "RHS":
        Ae = sec.A
        for w in (sec.h, sec.b):
            b = w - 3 * sec.t
            be = _be(b, sec.t, 1.40 * rt, 0.20, 1.38, Fy, Fn)
            Ae -= 2 * (b - be) * sec.t
        return Ae, "RHS walls b = B − 3t, E7.1 c1 = 0.20, c2 = 1.38"
    bf = sec.b / 2
    bfe = _be(bf, sec.tf, 0.56 * rt, 0.22, 1.49, Fy, Fn)
    hw = sec.h - 2 * (sec.tf + sec.r)
    hwe = _be(hw, sec.tw, 1.49 * rt, 0.18, 1.31, Fy, Fn)
    return sec.A - 4 * (bf - bfe) * sec.tf - (hw - hwe) * sec.tw, "I: flanges c1 0.22/c2 1.49, web 0.18/1.31"


def compression(sec, Fy, Lcx, Lcy, Lcz, E):
    """nominal P_n [kN] and the governing mode."""
    modes = []
    for name, Lc, r in (("flexural x (strong)", Lcx, sec.iy), ("flexural y (weak)", Lcy, sec.iz)):
        modes.append((name, math.pi ** 2 * E / (Lc * 1000 / r) ** 2 if Lc > 0 else math.inf))
    if sec.kind == "I" and Lcz > 0:
        Fe_t = (math.pi ** 2 * E * sec.Iw / (Lcz * 1000) ** 2 + G_STEEL * sec.It) / (sec.Iy + sec.Iz)
        modes.append(("torsional (E4)", Fe_t))
    name, Fe = min(modes, key=lambda m: m[1])
    Fn = 0.658 ** (Fy / Fe) * Fy if Fy / Fe <= 2.25 else 0.877 * Fe
    Ae, note = effective_area(sec, Fy, Fn, E)
    return Fn * Ae / 1e3, {"mode": name, "Fe": Fe, "Fn": Fn, "Ae": Ae, "note": note}


# ------------------------------------------------------------ flexure
def flexure_major(sec, Fy, Lb, Cb, E):
    rt = math.sqrt(E / Fy)
    Mp = Fy * sec.Wpl_y / 1e6
    S = sec.Wel_y
    if sec.kind == "CHS":
        Dt = sec.D / sec.t
        if Dt <= 0.07 * E / Fy:
            return Mp, "F8 compact: M_p"
        if Dt <= 0.31 * E / Fy:
            return (0.021 * E / Dt + Fy) * S / 1e6, "F8 noncompact"
        return 0.33 * E / Dt * S / 1e6, "F8 slender: F_cr = 0.33E/(D/t)"
    if sec.kind == "RHS":
        return _rhs_flexure(sec.h, sec.b, sec.t, Mp, S, sec.Iy, sec.iz, sec.It, sec.A, Fy, Lb, Cb, E, rt, ltb=True)
    # I section, F2 / F3 (compact web assumed; checked)
    hw = sec.h - 2 * (sec.tf + sec.r)
    if hw / sec.tw > 3.76 * rt:
        note_w = " (web noncompact: F4/F5 not implemented — conservative only if Mn below is reduced)"
    else:
        note_w = ""
    ry = sec.iz
    Lp = 1.76 * ry * rt / 1000
    h0 = sec.h - sec.tf
    rts = math.sqrt(math.sqrt(sec.Iz * sec.Iw) / S)
    Jc = sec.It / (S * h0)
    Lr = 1.95 * rts * E / (0.7 * Fy) * math.sqrt(Jc + math.sqrt(Jc ** 2 + 6.76 * (0.7 * Fy / E) ** 2)) / 1000
    if Lb <= Lp:
        M_ltb, mode = Mp, "yielding"
    elif Lb <= Lr:
        M_ltb = min(Cb * (Mp - (Mp - 0.7 * Fy * S / 1e6) * (Lb - Lp) / (Lr - Lp)), Mp)
        mode = "inelastic LTB"
    else:
        x = Lb * 1000 / rts
        Fcr = Cb * math.pi ** 2 * E / x ** 2 * math.sqrt(1 + 0.078 * Jc * x ** 2)
        M_ltb, mode = min(Fcr * S / 1e6, Mp), "elastic LTB"
    lam = sec.b / (2 * sec.tf)
    lp, lr = 0.38 * rt, 1.0 * rt
    if lam <= lp:
        M_flb = Mp
    elif lam <= lr:
        M_flb = Mp - (Mp - 0.7 * Fy * S / 1e6) * (lam - lp) / (lr - lp)
    else:
        kc = min(max(4 / math.sqrt(hw / sec.tw), 0.35), 0.76)
        M_flb = 0.9 * E * kc * S / lam ** 2 / 1e6
    Mn = min(M_ltb, M_flb)
    return Mn, (f"F2 {mode} (L_p = {Lp:.2f} m, L_r = {Lr:.2f} m, C_b = {Cb:.2f})"
                + ("" if M_flb >= M_ltb else f"; F3 flange local buckling λ = {lam:.1f}") + note_w)


def _rhs_flexure(H, B, t, Mp, S, I, ry, J, A, Fy, Lb, Cb, E, rt, ltb):
    """F7 for bending with flanges of width B and webs of depth H."""
    notes = []
    Mn = Mp
    b = B - 3 * t
    lam = b / t
    if lam > 1.12 * rt:
        if lam <= 1.40 * rt:
            Mn = min(Mn, Mp - (Mp - Fy * S / 1e6) * (3.57 * lam / rt - 4.0))
            notes.append("flange noncompact")
        else:
            be = min(1.92 * t * rt * (1 - 0.38 / lam * rt), b)
            Arem, yrem = (b - be) * t, (H - t) / 2
            d = Arem * yrem / (A - Arem)
            Ie = I - Arem * yrem ** 2 - (A - Arem) * d ** 2
            Se = Ie / (H / 2 + d)
            Mn = min(Mn, Fy * Se / 1e6)
            notes.append("flange slender (S_e)")
    h = H - 3 * t
    lw = h / t
    if lw > 2.42 * rt:
        Mn = min(Mn, Mp - (Mp - Fy * S / 1e6) * (0.305 * lw / rt - 0.738))
        notes.append("web noncompact" + (" (slender web: F7.3 not implemented)" if lw > 5.70 * rt else ""))
    if ltb and Lb > 0:
        Lp = 0.13 * E * ry * math.sqrt(J * A) / (Mp * 1e6) / 1000
        Lr = 2 * E * ry * math.sqrt(J * A) / (0.7 * Fy * S) / 1000
        if Lp < Lb <= Lr:
            Mn = min(Mn, Cb * (Mp - (Mp - 0.7 * Fy * S / 1e6) * (Lb - Lp) / (Lr - Lp)))
            notes.append(f"LTB inelastic (L_p {Lp:.1f} m)")
        elif Lb > Lr:
            Mn = min(Mn, 2 * E * Cb * math.sqrt(J * A) / (Lb * 1000 / ry) / 1e6)
            notes.append("LTB elastic")
    return Mn, "F7 " + (", ".join(notes) if notes else "compact")


def flexure_minor(sec, Fy, E):
    rt = math.sqrt(E / Fy)
    if sec.kind == "CHS":
        return flexure_major(sec, Fy, 0.0, 1.0, E)
    Mp = Fy * sec.Wpl_z / 1e6
    S = sec.Wel_z
    if sec.kind == "RHS":
        return _rhs_flexure(sec.b, sec.h, sec.t, Mp, S, sec.Iz, sec.iy, sec.It, sec.A, Fy, 0.0, 1.0, E, rt, ltb=False)
    Mp = min(Mp, 1.6 * Fy * S / 1e6)
    lam = sec.b / (2 * sec.tf)
    lp, lr = 0.38 * rt, 1.0 * rt
    if lam <= lp:
        return Mp, "F6 yielding"
    if lam <= lr:
        return Mp - (Mp - 0.7 * Fy * S / 1e6) * (lam - lp) / (lr - lp), "F6 flange noncompact"
    return 0.69 * E / lam ** 2 * S / 1e6, "F6 flange slender"


# ------------------------------------------------------------ shear
def shear(sec, Fy, E, f, axis="major", Lv=None):
    """design (or allowable) shear strength [kN] and note."""
    rt = math.sqrt(E / Fy)
    if sec.kind == "CHS":
        Dt = sec.D / sec.t
        Lv = Lv or 1.0
        Fcr = min(max(1.60 * E / (math.sqrt(Lv * 1000 / sec.D) * Dt ** 1.25), 0.78 * E / Dt ** 1.5), 0.6 * Fy)
        return f["v"] * Fcr * sec.A / 2 / 1e3, "G5 round HSS"
    if sec.kind == "RHS":
        H = sec.h if axis == "major" else sec.b
        h = H - 3 * sec.t
        kv = 5.0
        lim = 1.10 * math.sqrt(kv * E / Fy)
        lam = h / sec.t
        Cv2 = 1.0 if lam <= lim else (lim / lam if lam <= 1.37 * math.sqrt(kv * E / Fy)
                                      else 1.51 * kv * E / (lam ** 2 * Fy))
        return f["v"] * 0.6 * Fy * 2 * h * sec.t * Cv2 / 1e3, "G4 RHS (A_w = 2ht, h = H − 3t)"
    if axis == "minor":
        return f["v"] * 0.6 * Fy * 2 * sec.b * sec.tf / 1e3, "G6 I minor axis"
    hw = sec.h - 2 * (sec.tf + sec.r)
    Aw = sec.h * sec.tw
    if hw / sec.tw <= 2.24 * rt:
        return f["v_rolled"] * 0.6 * Fy * Aw / 1e3, "G2.1(a) rolled I web, C_v1 = 1"
    lim = 1.10 * math.sqrt(5.34 * E / Fy)
    Cv1 = 1.0 if hw / sec.tw <= lim else lim / (hw / sec.tw)
    return f["v"] * 0.6 * Fy * Aw * Cv1 / 1e3, "G2.1(b)"


def cb_linear(psi):
    """C_b (F1-1) for a linear moment diagram with end ratio ψ (M_small/M_large, −1 … 1)."""
    MA, MB, MC = (abs(psi + q * (1 - psi)) for q in (0.25, 0.5, 0.75))
    return min(12.5 / (2.5 + 3 * MA + 4 * MB + 3 * MC), 3.0)


# ------------------------------------------------------------ member check
def check(sec, Fy, L, N, Mx=0.0, My=0.0, Vx=0.0, Vy=0.0, Kx=1.0, Ky=1.0, Kz=None, Lb=None, Cb=None,
          psi_x=0.0, psi_y=0.0, psi_LT=0.0, code="US", method="LRFD", second_order=False, phi_c=None, phi_v=None):
    """AISC 360-22 / SBC 306 member check. N > 0 compression (kN), M about strong x / weak y (kNm).

    Returns (rows, info): rows = [(check, demand, capacity, note)]."""
    E = CF.get("aisc.E")
    f = factors(code, method, phi_c, phi_v)
    Kz = Ky if Kz is None else Kz
    Lb = Ky * L if Lb is None else Lb
    Cb = cb_linear(psi_LT) if Cb is None else Cb
    rows = []
    info = {"factors": f}
    if N >= 0:
        Pn, ci = compression(sec, Fy, Kx * L, Ky * L, Kz * L, E)
        Pc = f["c"] * Pn
        rows.append((f"compression ({ci['mode']}, F_n = {ci['Fn']:.0f} MPa) [kN]", N, Pc,
                     f"E3/E4/E7: {ci['note']}"))
        info["comp"] = ci
    else:
        Pc = f["t"] * Fy * sec.A / 1e3
        rows.append(("tension yielding [kN]", -N, Pc, "D2 (rupture on A_e: check net section)"))
    Mnx, nx = flexure_major(sec, Fy, Lb, Cb, E)
    Mny, ny = flexure_minor(sec, Fy, E)
    Mcx, Mcy = f["b"] * Mnx, f["b"] * Mny
    # B1 amplification (Appendix 8) unless second-order moments are given
    B1x = B1y = 1.0
    if N > 0 and not second_order:
        alpha = 1.0 if method == "LRFD" else 1.6
        for ax, (r_, K, psi) in {"x": (sec.Iy, Kx, psi_x), "y": (sec.Iz, Ky, psi_y)}.items():
            Pe1 = math.pi ** 2 * E * r_ / (K * L * 1000) ** 2 / 1e3
            Cm = 0.6 - 0.4 * psi
            B1 = max(1.0, Cm / (1 - alpha * N / Pe1)) if alpha * N < Pe1 else math.inf
            if ax == "x":
                B1x = B1
            else:
                B1y = B1
    Mrx, Mry = abs(Mx) * B1x, abs(My) * B1y
    if Mx:
        rows.append((f"flexure x (B1 = {B1x:.3f}) [kNm]", Mrx, Mcx, nx))
    if My:
        rows.append((f"flexure y (B1 = {B1y:.3f}) [kNm]", Mry, Mcy, ny))
    if Vy:
        Vc, nv = shear(sec, Fy, E, f, "major", L / 2)
        rows.append(("shear (strong-axis web) [kN]", abs(Vy), Vc, nv))
    if Vx:
        Vc, nv = shear(sec, Fy, E, f, "minor", L / 2)
        rows.append(("shear (weak axis) [kN]", abs(Vx), Vc, nv))
    Pr = abs(N)
    ratio = Pr / Pc
    m = (Mrx / Mcx if Mcx else 0) + (Mry / Mcy if Mcy else 0)
    H = ratio + 8 / 9 * m if ratio >= 0.2 else ratio / 2 + m
    rows.append(("interaction H1-1 [-]", H, 1.0,
                 "P_r/P_c + 8/9·ΣM_r/M_c" if ratio >= 0.2 else "P_r/(2P_c) + ΣM_r/M_c"))
    info.update({"Mnx": Mnx, "Mny": Mny, "Pc": Pc, "Mcx": Mcx, "Mcy": Mcy, "B1x": B1x, "B1y": B1y, "Cb": Cb})
    return rows, info


def report(rows, title):
    print(title)
    print(f"{'check':<58}{'demand':>10}{'capacity':>10}{'util':>7}  basis")
    w = 0.0
    for name, d, c, note in rows:
        u = d / c if c else math.inf
        w = max(w, u)
        print(f"{name:<58}{d:10.2f}{c:10.2f}{u:7.2f}  {note}" + ("  <-- FAIL" if u > 1 else ""))
    print(f"Governing utilisation {w:.2f} -> {'OK' if w <= 1 else 'NOT OK'}")
    return w


if __name__ == "__main__":
    print("Use member_check.py --code US|SA (this module holds the AISC 360 / SBC 306 checks).")
