#!/usr/bin/env python3
"""Steel member check to EN 1993-1-1 (default) or ANSI/AISC 360-16/360-22 (--code aisc)
for CHS, RHS/SHS and I/H sections.

For masts, struts, booms, arch segments (as straight members), edge beams and
frames of tensile structures.

Sections (--section):
  IPE200 | HEA240 | HEB300 ...        built-in EN 10365 nominal dimensions (see --list)
  CHS:219.1x8[:cold]                  circular hollow (hot-finished default)
  RHS:200x100x8[:cold]  SHS:150x8     rectangular / square hollow (EN 10210 hot / EN 10219 cold radii)
  RHS:304.8x254x8.86:aisc             AISC HSS: t = design wall thickness t_des, outside corner radius 2t_des
  I:h:b:tw:tf:r[:welded]              any doubly-symmetric I (r = root radius or weld size; AISC: r = k_des - tf)

Section properties are computed from the true outline (root radii, corner radii)
by polygon integration; plastic moduli by half-section clipping.

Checks
  * cross-section class (Table 5.2) under the actual N (+ bending)
  * section: N, V (y/z), N + My + Mz (6.2.9.1 plastic interaction for class 1–2, linear 6.2.1(7) for class 3–4)
  * flexural buckling y and z (6.3.1, curves per Table 6.2)
  * lateral-torsional buckling for I sections (6.3.2.2 general case, M_cr with C1 from NCCI SN003b Table 3.1 or --C1)
  * member interaction N + My + Mz (6.3.3, Annex B method 2)
  * tension members (N < 0): N_t,Rd = A·fy/γM0 (net section: check separately)

AISC 360-16/360-22 route (--code aisc; LRFD φ by default, --asd for Ω), see check_aisc():
  * D2 tension yielding / rupture (Ae = U·An from --An/--U), E3/E4 flexural (torsional) buckling, E7 slender
    elements (Table B4.1a, effective width; round HSS E7-7), F2 (LTB with Cb), F3/F6 flange local buckling, F7
    rectangular HSS (FLB, WLB, LTB), F8 round HSS, G2/G4/G5/G6 shear, H1-1a/b interaction, optional App. 8 B1.

Units: kN, kNm, m for loads/lengths; mm for section input; MPa for fy/fu (also in --code aisc).

Examples
  python3 member_check.py --section CHS:219.1x8 --L 7.5 --N 420 --My 12
  python3 member_check.py --section SHS:150x8 --L 6 --N 300 --My 25 --Mz 10 --cold
  python3 member_check.py --section IPE300 --L 6 --N 50 --My 80 --Vz 60 --kLT 1.0 --psi-LT 0
  python3 member_check.py --section HEB200 --L 5 --N 600 --My 30 --ky 1 --kz 1
  python3 member_check.py --code aisc --section I:359.7:369.9:12.3:19.8:15.2 --fy 345 --L 4.27 --N 1780 --My 339 --Mz 108
  python3 member_check.py --code aisc --asd --section RHS:304.8x203.2x4.42:aisc --fy 345 --L 7.32 --ky 1 --kz 1 --N 300
  python3 member_check.py --list
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as CF  # noqa: E402

# EN 10365 nominal dimensions h, b, tw, tf, r [mm]
PROFILES = {
    "IPE160": (160, 82, 5.0, 7.4, 9), "IPE200": (200, 100, 5.6, 8.5, 12), "IPE240": (240, 120, 6.2, 9.8, 15),
    "IPE300": (300, 150, 7.1, 10.7, 15), "IPE360": (360, 170, 8.0, 12.7, 18), "IPE400": (400, 180, 8.6, 13.5, 21),
    "HEA160": (152, 160, 6.0, 9.0, 15), "HEA200": (190, 200, 6.5, 10.0, 18), "HEA240": (230, 240, 7.5, 12.0, 21),
    "HEA300": (290, 300, 8.5, 14.0, 27), "HEB160": (160, 160, 8.0, 13.0, 15), "HEB200": (200, 200, 9.0, 15.0, 18),
    "HEB240": (240, 240, 10.0, 17.0, 21), "HEB300": (300, 300, 11.0, 19.0, 27),
}
CURVE_NAMES = ("a0", "a", "b", "c", "d")


def alpha_of(curve):
    """imperfection factor α of a buckling curve, from the register (EN 1993-1-1 Table 6.1 / 6.3)."""
    return CF.get("steel.imp_alpha")[curve]


def C1_end_moments(psi):
    """C1 for a segment with linear moment (end-moment ratio ψ), k = kw = 1: linear interpolation in
    NCCI SN003b Table 3.1 (register steel.C1_end_moments, computed with κ_wt = 0 → conservative)."""
    t = CF.get("steel.C1_end_moments")
    ps, cs = t["psi"], t["C1"]
    psi = max(-1.0, min(1.0, psi))
    for (p0, c0), (p1, c1) in zip(zip(ps, cs), zip(ps[1:], cs[1:])):
        if p1 <= psi <= p0:
            return c0 + (c1 - c0) * (p0 - psi) / (p0 - p1)
    return cs[-1]


# ------------------------------------------------------------ polygon tools
def arc(cx, cy, r, a0, a1, n=12):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def poly_props(P):
    """signed area, first moments, second moments about origin (y horizontal, z vertical)."""
    A = Sy = Sz = Iyy = Izz = 0.0  # Iyy = ∫z² dA (about y axis), Izz = ∫y² dA
    n = len(P)
    for i in range(n):
        y0, z0 = P[i]
        y1, z1 = P[(i + 1) % n]
        c = y0 * z1 - y1 * z0
        A += c / 2
        Sz += (y0 + y1) * c / 6      # ∫y dA
        Sy += (z0 + z1) * c / 6      # ∫z dA
        Izz += (y0 * y0 + y0 * y1 + y1 * y1) * c / 12
        Iyy += (z0 * z0 + z0 * z1 + z1 * z1) * c / 12
    return A, Sy, Sz, Iyy, Izz


def clip(P, axis, keep_positive=True):
    """Sutherland–Hodgman clip of polygon P to half-plane coord[axis] >= 0 (or <= 0)."""
    s = 1 if keep_positive else -1
    out = []
    n = len(P)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        ina, inb = s * a[axis] >= 0, s * b[axis] >= 0
        if ina:
            out.append(a)
        if ina != inb:
            t = a[axis] / (a[axis] - b[axis])
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return out


def rounded_rect(B, H, r, n=12):
    """CCW rounded rectangle centred at origin (width B along y, height H along z)."""
    if r <= 0:
        return [(-B / 2, -H / 2), (B / 2, -H / 2), (B / 2, H / 2), (-B / 2, H / 2)]
    P = []
    P += arc(B / 2 - r, -H / 2 + r, r, -90, 0, n)
    P += arc(B / 2 - r, H / 2 - r, r, 0, 90, n)
    P += arc(-B / 2 + r, H / 2 - r, r, 90, 180, n)
    P += arc(-B / 2 + r, -H / 2 + r, r, 180, 270, n)
    return P


def i_outline(h, b, tw, tf, r, n=12):
    zf = -h / 2 + tf
    zt = h / 2 - tf
    P = [(-b / 2, -h / 2), (b / 2, -h / 2), (b / 2, zf)]
    P += arc(tw / 2 + r, zf + r, r, 270, 180, n)
    P += arc(tw / 2 + r, zt - r, r, 180, 90, n)
    P += [(b / 2, zt), (b / 2, h / 2), (-b / 2, h / 2), (-b / 2, zt)]
    P += arc(-tw / 2 - r, zt - r, r, 90, 0, n)
    P += arc(-tw / 2 - r, zf + r, r, 0, -90, n)
    P += [(-b / 2, zf)]
    return P


class Section:
    def __init__(self, spec: str, cold: bool = False):
        self.spec = spec
        s = spec.upper()
        self.cold = cold or s.endswith(":COLD")
        self.welded = s.endswith(":WELDED")
        self.aisc_hss = s.endswith(":AISC")      # AISC Manual Part 1: t = t_des, outside corner radius 2 t_des
        if s in PROFILES:
            self._i(*PROFILES[s])
        elif s.startswith("I:"):
            h, b, tw, tf, r = map(float, s.split(":")[1:6])
            self._i(h, b, tw, tf, r)
        elif s.startswith("CHS:"):
            D, t = map(float, s.split(":")[1].split("X"))
            self._chs(D, t)
        elif s.startswith("RHS:") or s.startswith("SHS:"):
            dims = list(map(float, s.split(":")[1].split("X")))
            H, B, t = (dims[0], dims[0], dims[1]) if len(dims) == 2 else dims
            self._rhs(H, B, t)
        else:
            raise SystemExit(f"unknown section {spec} (see --list)")
        self._finish()

    # --- builders
    def _i(self, h, b, tw, tf, r):
        self.kind = "I"
        self.h, self.b, self.tw, self.tf, self.r = h, b, tw, tf, r
        self.outer = [i_outline(h, b, tw, tf, r)]
        self.holes = []
        a1 = (-0.042 + 0.2204 * tw / tf + 0.1355 * r / tf - 0.0865 * r * tw / tf ** 2
              - 0.0725 * tw ** 2 / tf ** 2) if r > 0 else 0.0
        D1 = ((tf + r) ** 2 + tw * (r + tw / 4)) / (2 * r + tf) if r > 0 else 0.0
        self.It = 2 / 3 * b * tf ** 3 + (h - 2 * tf) * tw ** 3 / 3 + 2 * a1 * D1 ** 4 - 0.420 * tf ** 4 * (r > 0)

    def _chs(self, D, t):
        self.kind = "CHS"
        self.D, self.t, self.h, self.b = D, t, D, D
        n = 180
        self.outer = [[(D / 2 * math.cos(2 * math.pi * k / n), D / 2 * math.sin(2 * math.pi * k / n)) for k in range(n)]]
        di = D - 2 * t
        self.holes = [[(di / 2 * math.cos(2 * math.pi * k / n), di / 2 * math.sin(2 * math.pi * k / n)) for k in range(n)]]
        self.It = math.pi * (D ** 4 - di ** 4) / 32

    def _rhs(self, H, B, t):
        self.kind = "RHS"
        self.h, self.b, self.t = H, B, t
        if self.aisc_hss:  # AISC Manual Part 1 HSS tables: design wall thickness, outside corner radius 2 t_des
            ro, ri = 2.0 * t, 1.0 * t
        elif self.cold:  # EN 10219-2
            ro, ri = ((2.0 * t, 1.0 * t) if t <= 6 else (2.5 * t, 1.5 * t) if t <= 10 else (3.0 * t, 2.0 * t))
        else:          # EN 10210-2
            ro, ri = 1.5 * t, 1.0 * t
        self.ro, self.ri = ro, ri
        self.outer = [rounded_rect(B, H, ro)]
        self.holes = [rounded_rect(B - 2 * t, H - 2 * t, ri)]
        rm = (ro + ri) / 2
        hm = 2 * ((B - t) + (H - t)) - 2 * rm * (4 - math.pi)          # mid-line perimeter
        Am = (B - t) * (H - t) - rm ** 2 * (4 - math.pi)               # enclosed mid-line area
        K = 2 * Am * t / hm
        self.It = t ** 3 * hm / 3 + 2 * K * Am

    # --- properties
    def _integ(self, polys_pos, polys_neg):
        tot = [0.0] * 5
        for P in polys_pos:
            v = poly_props(P)
            tot = [a + abs(b) if k == 0 else a + b * (1 if v[0] > 0 else -1) for k, (a, b) in enumerate(zip(tot, v))]
        for P in polys_neg:
            v = poly_props(P)
            tot = [a - abs(b) if k == 0 else a - b * (1 if v[0] > 0 else -1) for k, (a, b) in enumerate(zip(tot, v))]
        return tot

    def _finish(self):
        A, Sy, Sz, Iyy, Izz = self._integ(self.outer, self.holes)
        self.A = A
        self.Iy, self.Iz = Iyy, Izz  # symmetric sections, centroid at origin
        self.Wel_y = self.Iy / (self.h / 2)
        self.Wel_z = self.Iz / (self.b / 2)
        # plastic moduli: 2 × first moment of the half above / right of the axis
        up = self._integ([clip(P, 1) for P in self.outer], [clip(P, 1) for P in self.holes])
        rt = self._integ([clip(P, 0) for P in self.outer], [clip(P, 0) for P in self.holes])
        self.Wpl_y = 2 * up[1]
        self.Wpl_z = 2 * rt[2]
        self.iy, self.iz = math.sqrt(self.Iy / A), math.sqrt(self.Iz / A)
        if self.kind == "CHS":  # exact closed form
            D, di = self.D, self.D - 2 * self.t
            self.A = math.pi / 4 * (D ** 2 - di ** 2)
            self.Iy = self.Iz = math.pi / 64 * (D ** 4 - di ** 4)
            self.Wel_y = self.Wel_z = 2 * self.Iy / D
            self.Wpl_y = self.Wpl_z = (D ** 3 - di ** 3) / 6
            self.iy = self.iz = math.sqrt(self.Iy / self.A)
        self.Iw = self.Iz * (self.h - self.tf) ** 2 / 4 if self.kind == "I" else 0.0
        self.mass = A * 7.85e-3

    def shear_areas(self):
        if self.kind == "I":
            Avz = max(self.A - 2 * self.b * self.tf + (self.tw + 2 * self.r) * self.tf,
                      (self.h - 2 * self.tf) * self.tw)
            Avy = 2 * self.b * self.tf
        elif self.kind == "RHS":
            Avz = self.A * self.h / (self.b + self.h)
            Avy = self.A * self.b / (self.b + self.h)
        else:
            Avz = Avy = 2 * self.A / math.pi
        return Avy, Avz

    def curves(self, fy):
        if self.kind in ("CHS", "RHS"):
            c = "c" if self.cold else ("a0" if fy >= 460 else "a")
            return c, c, None
        if self.welded:
            return ("b", "c", "c" if self.h / self.b <= 2 else "d") if self.tf <= 40 else ("c", "d", "d")
        hb = self.h / self.b
        lt = "a" if hb <= 2 else "b"
        if hb > 1.2:
            yz = ("a", "b") if self.tf <= 40 else ("b", "c")
            if fy >= 460:
                yz = ("a0", "a0") if self.tf <= 40 else ("a", "a")
        else:
            yz = ("b", "c") if self.tf <= 100 else ("d", "d")
            if fy >= 460:
                yz = ("a", "a") if self.tf <= 100 else ("c", "c")
        return yz[0], yz[1], lt


def shear_area_modulus(sec: Section, direction):
    """plastic modulus of the shear area (the part whose f_y is reduced by ρ in 6.2.8)."""
    if sec.kind == "I":
        if direction == "z":
            hw = sec.h - 2 * sec.tf
            return hw ** 2 * sec.tw / 4          # ρ·A_w²/(4 t_w) with A_w = h_w t_w
        return 2 * sec.tf * sec.b ** 2 / 4       # flanges for weak-axis shear
    if sec.kind == "RHS":
        if direction == "z":
            return 2 * sec.t * (sec.h - 2 * sec.t) ** 2 / 4
        return 2 * sec.t * (sec.b - 2 * sec.t) ** 2 / 4
    return sec.Wpl_y * 2 / math.pi                # CHS: approx. share of the shear area 2A/π


def effective_section(sec: Section, fy):
    """Simplified EN 1993-1-5 §4.4 effective properties for class 4 I and RHS sections.

    Compression (ψ = 1) for A_eff; bending about y: compression flange (ψ = 1) + web (ψ = −1, kσ = 23.9).
    Neutral-axis shift of the effective section is neglected (small for doubly-symmetric sections)."""
    if sec.kind == "CHS":
        return None
    eps = math.sqrt(235 / fy)

    def rho_internal(ct, psi=1.0, ks=4.0):
        lp = ct / (28.4 * eps * math.sqrt(ks))
        return 1.0 if lp <= 0.5 + math.sqrt(0.085 - 0.055 * psi) else min(1.0, (lp - 0.055 * (3 + psi)) / lp ** 2)

    def rho_outstand(ct, ks=0.43):
        lp = ct / (28.4 * eps * math.sqrt(ks))
        return 1.0 if lp <= 0.748 else min(1.0, (lp - 0.188) / lp ** 2)

    if sec.kind == "I":
        cf = (sec.b - sec.tw - 2 * sec.r) / 2
        cw = sec.h - 2 * sec.tf - 2 * sec.r
        rf = rho_outstand(cf / sec.tf)
        rw = rho_internal(cw / sec.tw)
        dA = 4 * (1 - rf) * cf * sec.tf + (1 - rw) * cw * sec.tw
        rwb = rho_internal(cw / sec.tw, -1.0, 23.9)
        # bending y: one compression flange (2 outstands) at ±(h−tf)/2; web compression zone cw/2
        dAf = 2 * (1 - rf) * cf * sec.tf
        z_f = (sec.h - sec.tf) / 2
        bc = cw / 2
        dAw = (1 - rwb) * bc * sec.tw          # ineffective strip located near the centre of the compression zone
        z_w = bc / 2
        dI = dAf * z_f ** 2 + dAw * z_w ** 2
        W_eff_y = (sec.Iy - dI) / (sec.h / 2)
        W_eff_z = sec.Wel_z * rf                 # weak-axis bending: outstands only (conservative)
        return {"A_eff": sec.A - dA, "W_eff_y": W_eff_y, "W_eff_z": W_eff_z,
                "rho_flange": rf, "rho_web_comp": rw, "rho_web_bend": rwb}
    # RHS: four internal walls
    cH, cB = sec.h - 3 * sec.t, sec.b - 3 * sec.t
    rH, rB = rho_internal(cH / sec.t), rho_internal(cB / sec.t)
    dA = 2 * (1 - rH) * cH * sec.t + 2 * (1 - rB) * cB * sec.t
    rHb = rho_internal(cH / sec.t, -1.0, 23.9)
    rBb = rho_internal(cB / sec.t, -1.0, 23.9)
    dIy = (1 - rB) * cB * sec.t * ((sec.h - sec.t) / 2) ** 2 + 2 * (1 - rHb) * (cH / 2) * sec.t * (cH / 4) ** 2
    dIz = (1 - rH) * cH * sec.t * ((sec.b - sec.t) / 2) ** 2 + 2 * (1 - rBb) * (cB / 2) * sec.t * (cB / 4) ** 2
    return {"A_eff": sec.A - dA, "W_eff_y": (sec.Iy - dIy) / (sec.h / 2), "W_eff_z": (sec.Iz - dIz) / (sec.b / 2),
            "rho_H": rH, "rho_B": rB}


def section_class(sec: Section, fy, NEd):
    eps = math.sqrt(235 / fy)
    lims = CF.get("steel.class_limits")      # EN 1993-1-1 Table 5.2 (register)
    if sec.kind == "CHS":
        r = sec.D / sec.t
        c1, c2, c3 = (v * eps ** 2 for v in lims["chs"])
        return (1 if r <= c1 else 2 if r <= c2 else 3 if r <= c3 else 4), f"d/t={r:.1f}"
    if sec.kind == "RHS":
        cls = 1
        info = []
        for c in (sec.h - 3 * sec.t, sec.b - 3 * sec.t):
            ct = c / sec.t
            # conservative: wall in compression unless N ≈ 0
            lim = lims["internal_compression"] if NEd > 0 else lims["internal_bending"]
            k = 1 if ct <= lim[0] * eps else 2 if ct <= lim[1] * eps else 3 if ct <= lim[2] * eps else 4
            cls = max(cls, k)
            info.append(f"c/t={ct:.1f}")
        return cls, ", ".join(info)
    # I section: flange outstand + web with alpha from N
    cf = (sec.b - sec.tw - 2 * sec.r) / 2
    ctf = cf / sec.tf
    o1, o2, o3 = (v * eps for v in lims["outstand_compression"])
    kf = 1 if ctf <= o1 else 2 if ctf <= o2 else 3 if ctf <= o3 else 4
    cw = sec.h - 2 * sec.tf - 2 * sec.r
    ctw = cw / sec.tw
    alpha = min(1.0, max(0.0, 0.5 + max(NEd, 0) * 1e3 / (2 * cw * sec.tw * fy)))
    if alpha > 0.5:
        l1, l2 = 396 * eps / (13 * alpha - 1), 456 * eps / (13 * alpha - 1)
    else:
        l1, l2 = 36 * eps / max(alpha, 1e-6), 41.5 * eps / max(alpha, 1e-6)
    psi = 2 * alpha - 1  # rough elastic stress ratio
    l3 = 42 * eps / (0.67 + 0.33 * psi) if psi > -1 else 62 * eps * (1 - psi) * math.sqrt(-psi)
    kw = 1 if ctw <= l1 else 2 if ctw <= l2 else 3 if ctw <= l3 else 4
    return max(kf, kw), f"flange c/t={ctf:.1f} (cl {kf}), web c/t={ctw:.1f} (cl {kw}, α={alpha:.2f})"


def chi(lam, alpha):
    """EN 1993-1-1 eq. (6.49): Φ = 0.5[1 + α(λ̄ − 0.2) + λ̄²], χ = 1/(Φ + √(Φ² − λ̄²)) ≤ 1."""
    if lam <= 0.2:
        return 1.0
    ph = 0.5 * (1 + alpha * (lam - 0.2) + lam ** 2)
    return min(1.0, 1 / (ph + math.sqrt(ph ** 2 - lam ** 2)))


def plastic_NM(sec: Section, fy, NEd, MyRk, MzRk, gM0):
    """EN 1993-1-1 6.2.9.1 reduced plastic moments for class 1–2 sections and the biaxial exponents.

    NEd [N] (sign ignored), MyRk/MzRk [Nmm] (already reduced for shear 6.2.8). Returns MNy, MNz [Nmm], α, β.
    I/H: (6.33)–(6.38); RHS: (6.39); CHS: M_N = M_pl·cos(πn/2), the exact plastic interaction of a thin tube
    (within 0.3 % of strip integration of real CHS, see validation.md; the often quoted M_pl(1 − n^1.7) is up to
    5 % unconservative for n > 0.7)."""
    NplRd = sec.A * fy / gM0
    n = abs(NEd) / NplRd
    Mply, Mplz = MyRk / gM0, MzRk / gM0
    if n >= 1.0:
        return 0.0, 0.0, 2.0, 2.0
    if sec.kind == "CHS":
        f = math.cos(math.pi * n / 2)
        return Mply * f, Mplz * f, 2.0, 2.0
    if sec.kind == "RHS":
        aw = min((sec.A - 2 * sec.b * sec.t) / sec.A, 0.5)
        af = min((sec.A - 2 * sec.h * sec.t) / sec.A, 0.5)
        ab = min(1.66 / (1 - 1.13 * n ** 2), 6.0)
        return (min(Mply * (1 - n) / (1 - 0.5 * aw), Mply), min(Mplz * (1 - n) / (1 - 0.5 * af), Mplz), ab, ab)
    hw = sec.h - 2 * sec.tf
    a = min((sec.A - 2 * sec.b * sec.tf) / sec.A, 0.5)
    if abs(NEd) <= min(0.25 * NplRd, 0.5 * hw * sec.tw * fy / gM0):          # (6.33), (6.34)
        MNy = Mply
    else:
        MNy = min(Mply * (1 - n) / (1 - 0.5 * a), Mply)                       # (6.36)
    if abs(NEd) <= hw * sec.tw * fy / gM0 or n <= a:                          # (6.35), (6.37)
        MNz = Mplz
    else:
        MNz = Mplz * (1 - ((n - a) / (1 - a)) ** 2)                            # (6.38)
    return MNy, MNz, 2.0, max(5 * n, 1.0)


def check(sec: Section, fy, L, N, My=0.0, Mz=0.0, Vy=0.0, Vz=0.0, ky=1.0, kz=1.0, kLT=None,
          psi_y=0.0, psi_z=0.0, psi_LT=0.0, C1=None, sway_y=None, sway_z=None, Cmy=None, Cmz=None, CmLT=None):
    """EN 1993-1-1 member check. Units: fy MPa, L m, N kN (+ compression), M kNm, V kN.

    C1: LTB moment factor (default from ψ_LT via SN003b Table 3.1). sway_y/z: sway buckling mode about y/z
    (Annex B Table B.3 note: Cm = 0.9); None = automatic (k ≥ 2). Cmy/Cmz/CmLT override the Table B.3 value
    (e.g. members with transverse load). Returns (rows, info)."""
    E = CF.get("steel.E")
    G = CF.get("steel.G")
    gM0, gM1 = CF.get("steel.gM0"), CF.get("steel.gM1")
    cls, cinfo = section_class(sec, fy, N)
    Wy = sec.Wpl_y if cls <= 2 else sec.Wel_y
    Wz = sec.Wpl_z if cls <= 2 else sec.Wel_z
    A_eff = sec.A
    rows = []
    res = {"class": cls, "class_info": cinfo}
    if cls == 4:
        eff = effective_section(sec, fy)
        if eff is None:
            res["warning"] = "class 4 CHS: shell buckling to EN 1993-1-6 required — not covered"
        else:
            A_eff, Wy, Wz = eff["A_eff"], eff["W_eff_y"], eff["W_eff_z"]
            res["effective"] = eff
    NRk, MyRk, MzRk = A_eff * fy, Wy * fy, Wz * fy
    NEd, MyEd, MzEd = N * 1e3, abs(My) * 1e6, abs(Mz) * 1e6
    Avy, Avz = sec.shear_areas()
    for name, V, Av in (("Vz", Vz, Avz), ("Vy", Vy, Avy)):
        if V:
            Vpl = Av * fy / math.sqrt(3) / gM0 / 1e3
            rows.append((f"shear {name}", abs(V), Vpl, "6.2.6"))
            if abs(V) > 0.5 * Vpl:  # 6.2.8: reduced yield strength (1 − ρ) f_y in the shear area
                rho = (2 * abs(V) / Vpl - 1) ** 2
                if name == "Vz":
                    red = rho * shear_area_modulus(sec, "z")
                    MyRk = max(MyRk - red * fy, 0.0)
                else:
                    red = rho * shear_area_modulus(sec, "y")
                    MzRk = max(MzRk - red * fy, 0.0)
                res["shear_note"] = f"V > 0.5 Vpl on {name}: bending resistance reduced (6.2.8, ρ={rho:.2f})"

    def section_row(label_extra=""):
        if cls <= 2:
            MNy, MNz, a_, b_ = plastic_NM(sec, fy, NEd, MyRk, MzRk, gM0)
            res.update({"MN_y_Rd": MNy / 1e6, "MN_z_Rd": MNz / 1e6, "biax_alpha": a_, "biax_beta": b_})
            if MNy <= 0 or MNz <= 0:
                u = math.inf
            elif MzEd == 0:
                u = max(MyEd / MNy, abs(NEd) / (NRk / gM0))
            elif MyEd == 0:
                u = max(MzEd / MNz, abs(NEd) / (NRk / gM0))
            else:
                u = (MyEd / MNy) ** a_ + (MzEd / MNz) ** b_      # (6.41), the value published in worked examples
                res["biax_LHS"] = u
                u = max(u, abs(NEd) / (NRk / gM0))
            return (f"section N + My + Mz (6.2.9.1 plastic, M_N,y={MNy / 1e6:.1f} M_N,z={MNz / 1e6:.1f}){label_extra}",
                    u, 1.0, "6.2.9.1")
        u = abs(NEd) / (NRk / gM0) + MyEd / (MyRk / gM0) + MzEd / (MzRk / gM0)
        return (f"section N + My + Mz (linear 6.2.1(7), class {cls}){label_extra}", u, 1.0, "6.2.1(7) / 6.2.9.2")

    if NEd < 0:  # tension
        rows.append(("tension N_t (gross)", -N, NRk / gM0 / 1e3, "6.2.3"))
        rows.append(section_row())
        return rows, res
    rows.append(section_row())
    cy, cz, clt = sec.curves(fy)
    out = {}
    for ax, k, I, c in (("y", ky, sec.Iy, cy), ("z", kz, sec.Iz, cz)):
        Lcr = k * L * 1000
        Ncr = math.pi ** 2 * E * I / Lcr ** 2
        lam = math.sqrt(NRk / Ncr)
        x = chi(lam, alpha_of(c))
        out[ax] = (lam, x, c, Lcr / math.sqrt(I / sec.A), Ncr)
        rows.append((f"flexural buckling {ax} (curve {c}, λ̄={lam:.2f}, χ={x:.3f})", N, x * NRk / gM1 / 1e3, "6.3.1"))
    res.update({"chi_y": out["y"][1], "chi_z": out["z"][1], "lambda_y": out["y"][0], "lambda_z": out["z"][0]})
    # LTB
    chiLT = 1.0
    if sec.kind == "I" and MyEd > 0:
        Lb = (kLT if kLT is not None else kz) * L * 1000
        C1v = C1 if C1 is not None else C1_end_moments(psi_LT)
        Mcr = C1v * math.pi ** 2 * E * sec.Iz / Lb ** 2 * math.sqrt(sec.Iw / sec.Iz + Lb ** 2 * G * sec.It /
                                                                    (math.pi ** 2 * E * sec.Iz))
        lamLT = math.sqrt(Wy * fy / Mcr)
        chiLT = chi(lamLT, alpha_of(clt))
        res.update({"Mcr_kNm": Mcr / 1e6, "C1": C1v, "lambda_LT": lamLT, "chi_LT": chiLT})
        rows.append((f"LTB (curve {clt}, C1={C1v:.2f}, Mcr={Mcr / 1e6:.0f} kNm, λ̄LT={lamLT:.2f})",
                     abs(My), chiLT * MyRk / gM1 / 1e6, "6.3.2.2"))
    # Annex B interaction (method 2)
    lam_y, chi_y = out["y"][0], out["y"][1]
    lam_z, chi_z = out["z"][0], out["z"][1]
    ny = NEd / (chi_y * NRk / gM1)
    nz = NEd / (chi_z * NRk / gM1)
    cmin, csw = CF.get("steel.Cm_min"), CF.get("steel.Cm_sway")
    sway_y = (ky >= 2.0) if sway_y is None else sway_y
    sway_z = (kz >= 2.0) if sway_z is None else sway_z
    Cmy = Cmy if Cmy is not None else (csw if sway_y else max(cmin, 0.6 + 0.4 * psi_y))
    Cmz = Cmz if Cmz is not None else (csw if sway_z else max(cmin, 0.6 + 0.4 * psi_z))
    CmLT = CmLT if CmLT is not None else max(cmin, 0.6 + 0.4 * psi_LT)
    res.update({"Cmy": Cmy, "Cmz": Cmz, "CmLT": CmLT, "sway_y": sway_y, "sway_z": sway_z})
    if cls <= 2:
        kyy = min(Cmy * (1 + (lam_y - 0.2) * ny), Cmy * (1 + 0.8 * ny))
        if sec.kind == "I":
            kzz = min(Cmz * (1 + (2 * lam_z - 0.6) * nz), Cmz * (1 + 1.4 * nz))
        else:
            kzz = min(Cmz * (1 + (lam_z - 0.2) * nz), Cmz * (1 + 0.8 * nz))
        kyz = 0.6 * kzz
    else:
        kyy = min(Cmy * (1 + 0.6 * lam_y * ny), Cmy * (1 + 0.6 * ny))
        kzz = min(Cmz * (1 + 0.6 * lam_z * nz), Cmz * (1 + 0.6 * nz))
        kyz = kzz
    if sec.kind == "I" and MyEd > 0:   # Table B.2: member susceptible to torsional deformations
        if cls <= 2:
            kzy = max(1 - 0.1 * lam_z * nz / (CmLT - 0.25), 1 - 0.1 * nz / (CmLT - 0.25))
            if lam_z < 0.4:
                kzy = min(0.6 + lam_z, 1 - 0.1 * lam_z * nz / (CmLT - 0.25))
        else:
            kzy = max(1 - 0.05 * lam_z * nz / (CmLT - 0.25), 1 - 0.05 * nz / (CmLT - 0.25))
    else:                              # Table B.1
        kzy = 0.6 * kyy if cls <= 2 else 0.8 * kyy
    e61 = ny + kyy * MyEd / (chiLT * MyRk / gM1) + kyz * MzEd / (MzRk / gM1)
    e62 = nz + kzy * MyEd / (chiLT * MyRk / gM1) + kzz * MzEd / (MzRk / gM1)
    res.update({"kyy": kyy, "kyz": kyz, "kzy": kzy, "kzz": kzz, "eq661": e61, "eq662": e62})
    rows.append((f"interaction (6.61) kyy={kyy:.2f} kyz={kyz:.2f}", e61, 1.0, "6.3.3 / Annex B"))
    rows.append((f"interaction (6.62) kzy={kzy:.2f} kzz={kzz:.2f}", e62, 1.0, "6.3.3 / Annex B"))
    res.update({"slenderness_y": out["y"][3], "slenderness_z": out["z"][3]})
    return rows, res


ASSUMPTIONS = """Assumptions / model limits:
  - Section properties from the true outline (root/corner radii EN 10210 hot, EN 10219 cold); Iw = Iz(h−tf)²/4.
  - Class from EN 1993-1-1 Table 5.2 under the given N (web α from N for I sections; RHS walls conservative).
  - Section check: 6.2.9.1 plastic N+M interaction for class 1–2 (CHS M_N = M_pl·cos(πn/2)), linear 6.2.1(7)
    for class 3, effective section (EN 1993-1-5 4.4, neutral-axis shift ignored) for class 4 I/RHS; class 4 CHS
    is not designed (EN 1993-1-6).
  - Flexural buckling 6.3.1 (curves Table 6.2), LTB general case 6.3.2.2 with M_cr for a doubly-symmetric
    section, load at the shear centre, k = kw = 1 (fork supports); C1 from SN003b Table 3.1 (end moments).
  - Interaction 6.3.3 Annex B (method 2); Cm from Table B.3 for a linear moment (ψ), 0.9 for sway modes
    (auto when k ≥ 2). Use --Cmy/--Cmz/--CmLT for transverse loads. Torsion and warping stresses not checked.
  - Loads must be ULS design values; second-order sway effects belong in the global analysis (frame2d/frame3d)."""


# ============================================================ ANSI/AISC 360-16 / 360-22
# Every coefficient comes from the register section `aisc` (code_factors.json). Internal units N, mm, MPa.
def _A(key):
    return CF.get("aisc." + key)


def aisc_factor(limit_state, asd):
    """multiplier on the nominal strength: φ (LRFD) or 1/Ω (ASD), register aisc.resistance [φ, Ω]."""
    phi, om = _A("resistance")[limit_state]
    return 1.0 / om if asd else phi


def Cb_F1_1(Mmax, MA, MB, MC):
    """AISC 360 eq. (F1-1): Cb = 12.5 Mmax/(2.5 Mmax + 3 MA + 4 MB + 3 MC) (absolute values)."""
    c = _A("Cb")["coef"]
    Mmax, MA, MB, MC = (abs(x) for x in (Mmax, MA, MB, MC))
    return c[0] * Mmax / (c[1] * Mmax + c[2] * MA + c[3] * MB + c[4] * MC)


def Cb_linear(psi):
    """Cb (F1-1) for a linear moment diagram between end moments M and ψM (ψ = +1 single curvature, uniform)."""
    m = [abs(1 + (psi - 1) * x) for x in (0.25, 0.5, 0.75)]
    return Cb_F1_1(max(1.0, abs(psi)), *m)


def aisc_E3(Fy, Fe):
    """AISC 360 E3: Fcr = 0.658^(Fy/Fe)·Fy for Fy/Fe <= 2.25 (E3-2), else 0.877 Fe (E3-3)."""
    e3 = _A("E3")
    if Fe <= 0:
        return 0.0
    return e3["base"] ** (Fy / Fe) * Fy if Fy / Fe <= e3["inelastic_limit"] else e3["elastic_factor"] * Fe


def _aisc_I_geom(sec):
    """b = bf/2 (flange outstand), h = clear web depth less fillets (rolled) or between flanges (welded)."""
    h = sec.h - 2 * sec.tf - (0.0 if sec.welded else 2 * sec.r)
    kc = min(max(4 / math.sqrt(h / sec.tw), _A("B4_1a")["kc_limits"][0]), _A("B4_1a")["kc_limits"][1])
    return sec.b / 2, h, kc


def _eff_width(b, lam, lam_r, Fy, Fcr, c):
    """AISC 360 E7-2/E7-3 effective width of one element (c = [c1, c2] of Table E7.1)."""
    if Fcr <= 0 or lam <= lam_r * math.sqrt(Fy / Fcr):
        return b
    Fel = (c[1] * lam_r / lam) ** 2 * Fy                       # (E7-5)
    r = math.sqrt(Fel / Fcr)
    return min(b, b * (1 - c[0] * r) * r)                      # (E7-3)


def aisc_compression(sec, Fy, Lcy, Lcz, Lct=None):
    """AISC 360 Chapter E: E3 flexural buckling about both axes, E4 torsional buckling (doubly symmetric I),
    E7 slender elements (effective area). Lc in mm. Returns dict with Pn [N]."""
    E, G = _A("E"), _A("G")
    out = {"warning": None}
    Fe_y = math.pi ** 2 * E / (Lcy / sec.iy) ** 2
    Fe_z = math.pi ** 2 * E / (Lcz / sec.iz) ** 2
    Fe = min(Fe_y, Fe_z)
    mode = "flexural y" if Fe_y <= Fe_z else "flexural z"
    if sec.kind == "I":
        Lct = Lcz if Lct is None else Lct
        Fe_t = (math.pi ** 2 * E * sec.Iw / Lct ** 2 + G * sec.It) / (sec.Iy + sec.Iz)     # (E4-2)
        out["Fe_t"] = Fe_t
        if Fe_t < Fe:
            Fe, mode = Fe_t, "torsional (E4)"
    Fcr = aisc_E3(Fy, Fe)
    lim = _A("B4_1a")
    e7 = _A("E7")
    sE = math.sqrt(E / Fy)
    Ae = sec.A
    slender = []
    if sec.kind == "I":
        b, h, kc = _aisc_I_geom(sec)
        lam_f, lam_w = b / sec.tf, h / sec.tw
        lr_f = (lim["flange_builtup"] * math.sqrt(kc * E / Fy)) if sec.welded else lim["flange_rolled"] * sE
        lr_w = lim["web_doubly_symmetric"] * sE
        be = _eff_width(b, lam_f, lr_f, Fy, Fcr, e7["unstiffened"])
        he = _eff_width(h, lam_w, lr_w, Fy, Fcr, e7["stiffened"])
        Ae -= 4 * (b - be) * sec.tf + (h - he) * sec.tw
        out.update({"lambda_f": lam_f, "lambda_r_f": lr_f, "lambda_w": lam_w, "lambda_r_w": lr_w})
        if lam_f > lr_f:
            slender.append(f"flange b/t={lam_f:.1f} > λr={lr_f:.1f}")
        if lam_w > lr_w:
            slender.append(f"web h/tw={lam_w:.1f} > λr={lr_w:.1f}")
    elif sec.kind == "RHS":
        lr = lim["hss_rect_wall"] * sE
        for w in (sec.b - 3 * sec.t, sec.h - 3 * sec.t):      # B4.1b(d): outside dimension − 3t
            lam = w / sec.t
            we = _eff_width(w, lam, lr, Fy, Fcr, e7["hss_wall"])
            Ae -= 2 * (w - we) * sec.t
            if lam > lr:
                slender.append(f"wall b/t={lam:.1f} > λr={lr:.1f}")
        out["lambda_r"] = lr
    else:
        Dt = sec.D / sec.t
        if Dt > e7["round_limit"] * E / Fy:
            out["warning"] = f"round HSS D/t={Dt:.1f} > 0.45E/Fy: outside AISC 360 E7 (shell buckling) — not covered"
        elif Dt > lim["hss_round"] * E / Fy:
            Ae = (e7["round_coef"] * E / (Fy * Dt) + e7["round_add"]) * sec.A          # (E7-7)
            slender.append(f"D/t={Dt:.1f} > 0.11E/Fy={lim['hss_round'] * E / Fy:.1f}")
    out.update({"Fe_y": Fe_y, "Fe_z": Fe_z, "Fe": Fe, "mode": mode, "Fcr": Fcr, "Ae": Ae, "Pn": Fcr * Ae,
                "slender": slender, "KL_r": max(Lcy / sec.iy, Lcz / sec.iz)})
    return out


def _flb_linear(Mp, Mr, lam, lp, lr):
    return Mp - (Mp - Mr) * (lam - lp) / (lr - lp)


def aisc_flexure(sec, Fy, axis="y", Lb=0.0, Cb=1.0):
    """AISC 360 Chapter F nominal flexural strength Mn [Nmm] about the strong (y, AISC x) or weak (z, AISC y) axis.
    I: F2 (yielding + LTB with Cb), F3 (FLB, noncompact/slender flange), F6 (minor axis);
    rectangular HSS: F7 (yielding, FLB, WLB, LTB F7.4 for the major axis of rectangular sections); round HSS: F8."""
    E, G = _A("E"), _A("G")
    sE = math.sqrt(E / Fy)
    lb = _A("B4_1b")
    r = {"warning": None, "limits": {}}
    if sec.kind == "I":
        b, h, kc = _aisc_I_geom(sec)
        lam_f = b / sec.tf
        lp_f = lb["flange_rolled"][0] * sE
        if axis == "z":                                   # F6, Table B4.1b case 13
            f6 = _A("F3_F6")
            Mp = min(Fy * sec.Wpl_z, f6["F6_Mp_cap"] * Fy * sec.Wel_z)
            lr_f = lb["flange_rolled"][1] * sE
            if lam_f <= lp_f:
                Mn = Mp
            elif lam_f <= lr_f:
                Mn = _flb_linear(Mp, _A("F2")["FL_ratio"] * Fy * sec.Wel_z, lam_f, lp_f, lr_f)
            else:
                Mn = f6["F6_slender"] * E / lam_f ** 2 * sec.Wel_z
            r["limits"] = {"yield (F6-1)": Mp, "FLB (F6)": Mn}
            r.update({"Mn": min(Mp, Mn), "Mp": Mp, "lambda_f": lam_f, "clause": "F6"})
            return r
        f2 = _A("F2")
        FL = f2["FL_ratio"] * Fy
        Sx, Zx, J = sec.Wel_y, sec.Wpl_y, sec.It
        Mp = Fy * Zx
        ho = sec.h - sec.tf
        rts = math.sqrt(math.sqrt(sec.Iz * sec.Iw) / Sx)
        Lp = f2["Lp"] * sec.iz * sE                                                          # (F2-5)
        jt = J / (Sx * ho)
        Lr = f2["Lr"] * rts * E / FL * math.sqrt(jt + math.sqrt(jt ** 2 + f2["Lr_term"] * (FL / E) ** 2))  # (F2-6)
        if Lb <= Lp:
            M_ltb = Mp
        elif Lb <= Lr:
            M_ltb = min(Cb * _flb_linear(Mp, FL * Sx, Lb, Lp, Lr), Mp)                       # (F2-2)
        else:
            Fcr = Cb * math.pi ** 2 * E / (Lb / rts) ** 2 * math.sqrt(1 + f2["Fcr_term"] * jt * (Lb / rts) ** 2)
            M_ltb = min(Fcr * Sx, Mp)                                                        # (F2-3, F2-4)
        lr_f = (lb["flange_builtup"][1] * math.sqrt(kc * E / FL)) if sec.welded else lb["flange_rolled"][1] * sE
        if lam_f <= lp_f:
            M_flb, clause = Mp, "F2"
        elif lam_f <= lr_f:
            M_flb, clause = _flb_linear(Mp, FL * Sx, lam_f, lp_f, lr_f), "F3"                  # (F3-1)
        else:
            M_flb, clause = _A("F3_F6")["F3_slender"] * E * kc * Sx / lam_f ** 2, "F3"         # (F3-2)
        lam_w = h / sec.tw
        lp_w = lb["web_doubly_symmetric"][0] * sE
        if lam_w > lp_w:
            r["warning"] = (f"web h/tw={lam_w:.1f} > λp={lp_w:.1f}: noncompact/slender web needs AISC 360 F4/F5 "
                            f"(not implemented) — result not valid")
        r["limits"] = {"yield (F2-1)": Mp, "LTB (F2)": M_ltb, "FLB (F3)": M_flb}
        r.update({"Mn": min(Mp, M_ltb, M_flb), "Mp": Mp, "Lp": Lp, "Lr": Lr, "rts": rts, "ho": ho,
                  "lambda_f": lam_f, "lambda_w": lam_w, "clause": clause})
        return r
    if sec.kind == "RHS":
        f7 = _A("F7")
        if axis == "y":
            Z, S, I, H = sec.Wpl_y, sec.Wel_y, sec.Iy, sec.h
            bf, hw = sec.b - 3 * sec.t, sec.h - 3 * sec.t          # compression flange = side of width B
        else:
            Z, S, I, H = sec.Wpl_z, sec.Wel_z, sec.Iz, sec.b
            bf, hw = sec.h - 3 * sec.t, sec.b - 3 * sec.t
        t = sec.t
        Mp = Fy * Z
        lam, lam_w = bf / t, hw / t
        lp, lr = (c * sE for c in lb["hss_rect_flange"])
        if lam <= lp:
            M_flb = Mp
        elif lam <= lr:
            M_flb = min(Mp, Mp - (Mp - Fy * S) * (f7["flb"][0] * lam / sE - f7["flb"][1]))     # (F7-2)
        else:                                                                                   # (F7-3, F7-4)
            be = min(bf, f7["be"][0] * t * sE * (1 - f7["be"][1] / lam * sE))
            dA, zf = (bf - be) * t, (H - t) / 2
            A = sec.A
            zb = -dA * zf / (A - dA)                       # centroid shift of the effective section
            Ie = I - dA * zf ** 2 - (A - dA) * zb ** 2
            Se = Ie / (H / 2 - zb)                         # to the compression flange (governing fibre)
            M_flb = Fy * Se
            r.update({"be": be, "Se": Se})
        lpw, lrw = (c * sE for c in lb["hss_rect_web"])
        if lam_w <= lpw:
            M_wlb = Mp
        elif lam_w <= lrw:
            M_wlb = min(Mp, Mp - (Mp - Fy * S) * (f7["wlb"][0] * lam_w / sE - f7["wlb"][1]))   # (F7-5)
        else:
            M_wlb = Mp
            r["warning"] = f"HSS web h/t={lam_w:.1f} > λr={lrw:.1f}: slender web (F7.3(c)) not implemented"
        M_ltb = Mp
        ry = sec.iz if axis == "y" else sec.iy
        if axis == "y" and sec.h > sec.b and Lb > 0:      # F7.4: rectangular HSS about the major axis only
            JA = math.sqrt(sec.It * sec.A)
            Lp = f7["ltb"][0] * E * ry * JA / Mp                                               # (F7-12)
            Lr = f7["ltb"][1] * E * ry * JA / (_A("F2")["FL_ratio"] * Fy * S)                  # (F7-13)
            if Lb > Lr:
                M_ltb = min(Mp, f7["ltb"][1] * E * Cb * JA / (Lb / ry))                        # (F7-11)
            elif Lb > Lp:
                M_ltb = min(Mp, Cb * _flb_linear(Mp, _A("F2")["FL_ratio"] * Fy * S, Lb, Lp, Lr))   # (F7-10)
            r.update({"Lp": Lp, "Lr": Lr})
        r["limits"] = {"yield (F7-1)": Mp, "FLB (F7.2)": M_flb, "WLB (F7.3)": M_wlb, "LTB (F7.4)": M_ltb}
        r.update({"Mn": min(Mp, M_flb, M_wlb, M_ltb), "Mp": Mp, "lambda_f": lam, "lambda_w": lam_w,
                  "clause": "F7"})
        return r
    f8 = _A("F8")
    Dt = sec.D / sec.t
    Z, S = sec.Wpl_y, sec.Wel_y
    Mp = Fy * Z
    lp, lr = (c * E / Fy for c in lb["hss_round"])
    if Dt >= f8["limit"] * E / Fy:
        r["warning"] = f"round HSS D/t={Dt:.1f} >= 0.45E/Fy: outside AISC 360 F8 — not covered"
    if Dt <= lp:
        M_lb = Mp
    elif Dt <= lr:
        M_lb = (f8["noncompact"] * E / Dt + Fy) * S                                           # (F8-2)
    else:
        M_lb = f8["slender"] * E / Dt * S                                                     # (F8-3, F8-4)
    r["limits"] = {"yield (F8-1)": Mp, "local buckling (F8.2)": M_lb}
    r.update({"Mn": min(Mp, M_lb), "Mp": Mp, "D_t": Dt, "clause": "F8"})
    return r


def _Cv2(h_t, kv, E, Fy):
    """AISC 360 G2.2 web shear buckling coefficient Cv2 (G2-9..G2-11)."""
    c = _A("G_shear")["cv"]
    x = math.sqrt(kv * E / Fy)
    if h_t <= c[0] * x:
        return 1.0
    if h_t <= c[1] * x:
        return c[0] * x / h_t
    return c[2] * kv * E / (h_t ** 2 * Fy)


def aisc_shear(sec, Fy, direction="z", Lv=None):
    """AISC 360 Chapter G nominal shear strength Vn [N] and the resistance key.
    direction 'z' = shear parallel to the web (strong-axis bending), 'y' = weak-axis shear."""
    E = _A("E")
    g = _A("G_shear")
    if sec.kind == "I":
        if direction == "z":                              # G2.1
            b, h, _ = _aisc_I_geom(sec)
            Aw = sec.h * sec.tw
            h_t = h / sec.tw
            if not sec.welded and h_t <= g["rolled_I_limit"] * math.sqrt(E / Fy):
                return g["shear_yield"] * Fy * Aw, "shear_rolled_I", "G2.1(a)", 1.0
            x = math.sqrt(g["kv_web"] * E / Fy)
            Cv1 = 1.0 if h_t <= g["cv"][0] * x else g["cv"][0] * x / h_t                      # (G2-3, G2-4)
            return g["shear_yield"] * Fy * Aw * Cv1, "shear", "G2.1(b)", Cv1
        Cv2 = _Cv2(sec.b / (2 * sec.tf), g["kv_flange"], E, Fy)                              # G6
        return g["shear_yield"] * Fy * 2 * sec.b * sec.tf * Cv2, "shear", "G6", Cv2
    if sec.kind == "RHS":                                 # G4
        h = (sec.h if direction == "z" else sec.b) - 3 * sec.t
        Cv2 = _Cv2(h / sec.t, g["kv_hss"], E, Fy)
        return g["shear_yield"] * Fy * 2 * h * sec.t * Cv2, "shear", "G4", Cv2
    Dt = sec.D / sec.t                                    # G5
    Lv = Lv if Lv else 1e12
    Fcr = min(max(g["round"][0] * E / (math.sqrt(Lv / sec.D) * Dt ** 1.25), g["round"][1] * E / Dt ** 1.5),
              g["shear_yield"] * Fy)
    return Fcr * sec.A / 2, "shear", "G5", Fcr


def check_aisc(sec: Section, Fy, L, N, My=0.0, Mz=0.0, Vy=0.0, Vz=0.0, ky=1.0, kz=1.0, kLT=None, Cb=1.0,
               asd=False, Fu=None, An=None, U=1.0, Lv=None, B1=False, Cmy=None, Cmz=None):
    """ANSI/AISC 360-16/360-22 member check. Units: Fy/Fu MPa, L m, N kN (+ compression, − tension), M kNm, V kN,
    An mm². LRFD (φ) by default; asd=True uses Ω. Forces must be the required strengths of the method chosen
    (LRFD factored or ASD combination) and include second-order effects unless B1=True (App. 8 P-δ amplifier
    B1 = Cm/(1 − αPr/Pe1), K1 = 1, braced member; Cm = 1.0 unless Cmy/Cmz given). Returns (rows, info)."""
    E = _A("E")
    rows = []
    res = {"code": "AISC 360", "method": "ASD" if asd else "LRFD", "warnings": []}
    NEd = N * 1e3
    Lmm = L * 1000
    Lcy, Lcz = ky * Lmm, kz * Lmm
    Lb = (kLT if kLT is not None else kz) * Lmm
    lab = "Ω" if asd else "φ"
    # ---- axial
    if NEd < 0:
        f_y = aisc_factor("tension_yield", asd)
        Pc = Fy * sec.A * f_y
        rows.append((f"tension yielding D2(a) Fy·Ag ({lab})", -N, Pc / 1e3, "D2-1"))
        if Fu:
            Ae = U * (An if An else sec.A)
            Pr_ = Fu * Ae * aisc_factor("tension_rupture", asd)
            rows.append((f"tension rupture D2(b) Fu·Ae, Ae={Ae / 100:.2f} cm² (U={U:g})", -N, Pr_ / 1e3, "D2-2"))
            Pc = min(Pc, Pr_)
            res["Ae"] = Ae
        else:
            res["warnings"].append("no --fu: tension rupture D2(b) not checked (give --fu, --An, --U)")
        res["Pc"] = Pc
        r_min = min(sec.iy, sec.iz)
        res["L_r"] = Lmm / r_min
    elif NEd > 0:
        c = aisc_compression(sec, Fy, Lcy, Lcz, Lb)
        Pc = c["Pn"] * aisc_factor("compression", asd)
        res.update({"Fe": c["Fe"], "Fcr": c["Fcr"], "Ae": c["Ae"], "Pn": c["Pn"], "Pc": Pc, "KL_r": c["KL_r"],
                    "buckling_mode": c["mode"], "slender": c["slender"]})
        if c["warning"]:
            res["warnings"].append(c["warning"])
        sl = f", slender: E7 Ae={c['Ae'] / 100:.2f} cm²" if c["slender"] else ""
        rows.append((f"compression E3/E4 ({c['mode']}, Fe={c['Fe']:.0f}, Fcr={c['Fcr']:.0f} MPa{sl})", N, Pc / 1e3,
                     "E3/E4/E7"))
        if c["KL_r"] > _A("E3")["slenderness_note"]:
            res["warnings"].append(f"Lc/r = {c['KL_r']:.0f} > 200 (E2 user note: preferably not exceeded)")
    else:
        Pc = None
    # ---- moments (optionally amplified by B1)
    Mrx, Mry = abs(My) * 1e6, abs(Mz) * 1e6
    if B1 and NEd > 0:
        alpha = _A("B1")["alpha"][1 if asd else 0]
        for ax, I, Cm in (("y", sec.Iy, Cmy), ("z", sec.Iz, Cmz)):
            Pe1 = math.pi ** 2 * E * I / Lmm ** 2                                               # (A-8-5), K1 = 1
            Cm = 1.0 if Cm is None else Cm
            b1 = math.inf if alpha * NEd >= Pe1 else max(1.0, Cm / (1 - alpha * NEd / Pe1))   # (A-8-3)
            res[f"B1_{ax}"], res[f"Pe1_{ax}"] = b1, Pe1
            if ax == "y":
                Mrx *= b1
            else:
                Mry *= b1
    res.update({"Mrx": Mrx / 1e6, "Mry": Mry / 1e6})
    fb = aisc_factor("flexure", asd)
    Mcx = Mcy = None
    if Mrx > 0:
        fx = aisc_flexure(sec, Fy, "y", Lb, Cb)
        Mcx = fx["Mn"] * fb
        res["flex_y"] = fx
        if fx["warning"]:
            res["warnings"].append(fx["warning"])
        gov = min(fx["limits"], key=fx["limits"].get)
        extra = f", Cb={Cb:.2f}, Lp={fx['Lp'] / 1e3:.2f} Lr={fx['Lr'] / 1e3:.2f} m" if "Lp" in fx else ""
        rows.append((f"flexure strong axis {fx['clause']} (governs: {gov}{extra})", Mrx / 1e6, Mcx / 1e6, "Ch. F"))
    if Mry > 0:
        fz = aisc_flexure(sec, Fy, "z")
        Mcy = fz["Mn"] * fb
        res["flex_z"] = fz
        if fz["warning"] and fz["warning"] not in res["warnings"]:
            res["warnings"].append(fz["warning"])
        gov = min(fz["limits"], key=fz["limits"].get)
        rows.append((f"flexure weak axis {fz['clause']} (governs: {gov})", Mry / 1e6, Mcy / 1e6, "Ch. F"))
    res.update({"Mcx": Mcx / 1e6 if Mcx else None, "Mcy": Mcy / 1e6 if Mcy else None})
    # ---- shear
    for name, V, d in (("Vz", Vz, "z"), ("Vy", Vy, "y")):
        if V:
            Vn, key, clause, cv = aisc_shear(sec, Fy, d, Lv * 1000 if Lv else None)
            Vc = Vn * aisc_factor(key, asd)
            res[f"Vc_{d}"] = Vc / 1e3
            rows.append((f"shear {name} {clause}", abs(V), Vc / 1e3, clause))
    # ---- H1 interaction
    if Pc and (Mrx > 0 or Mry > 0):
        h1 = _A("H1")
        pr = abs(NEd) / Pc
        mm = (Mrx / Mcx if Mrx else 0.0) + (Mry / Mcy if Mry else 0.0)
        if pr >= h1["threshold"]:
            u, eq = pr + h1["factor"] * mm, "H1-1a"
        else:
            u, eq = pr / 2 + mm, "H1-1b"
        res.update({"H1": u, "H1_eq": eq, "Pr_Pc": pr})
        rows.append((f"interaction {eq} (Pr/Pc={pr:.3f}{', tension H1.2' if NEd < 0 else ''})", u, 1.0, "H1"))
    return rows, res


ASSUMPTIONS_AISC = """Assumptions / model limits (ANSI/AISC 360-16 / 360-22, --code aisc):
  - Section properties from the true outline (as the EN route); AISC HSS: give the design wall thickness t_des
    (0.93 t_nom for ERW A500) with ':aisc' (outside corner radius 2 t_des); W shapes: r = k_des − t_f.
    Width-to-thickness: b = bf/2, h = d − 2k (rolled I); b = B − 3t (HSS, B4.1b(d)).
  - Compression: E3 about both axes with Lc = k·L, E4 torsional buckling of doubly symmetric I (Lcz = LTB length),
    E7 effective width (Table E7.1) for slender elements, E7-7 for round HSS; HSS torsional buckling ignored.
  - Flexure: F2 (LTB, Cb from --Cb, --Cb-moments, or F1-1 on a linear diagram from --psi-LT; default 1.0),
    F3/F6 flange local buckling, F7 (HSS; LTB F7.4 only for the major axis of rectangular sections), F8 (round
    HSS). F4/F5 (noncompact or slender webs), singly symmetric sections, tees, angles and channels: not covered.
  - Shear: G2.1 (rolled I φv = 1.00 / Ωv = 1.50 when h/tw <= 2.24√(E/Fy)), G2.2 Cv2, G4, G5 (Lv = --Lv or ∞),
    G6; no tension-field action. Interaction H1-1a/b (H1.2 for tension, without the optional Cb increase).
  - Required strengths are the LRFD or ASD combination values (choose with --asd) and must include second-order
    effects (direct analysis, frame2d/frame3d) unless --B1 is given (App. 8 B1 with K1 = 1, EI* = EI, Cm = 1.0
    unless --Cmy/--Cmz). Tension rupture needs --fu and the net/effective area (--An, --U)."""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--section")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--cold", action="store_true", help="cold-formed hollow section")
    ap.add_argument("--fy", type=float, default=355.0)
    ap.add_argument("--L", type=float, help="system length [m]")
    ap.add_argument("--N", type=float, default=0.0, help="axial force [kN], + compression, − tension")
    ap.add_argument("--My", type=float, default=0.0, help="max moment about strong axis y [kNm]")
    ap.add_argument("--Mz", type=float, default=0.0, help="max moment about weak axis z [kNm]")
    ap.add_argument("--Vz", type=float, default=0.0)
    ap.add_argument("--Vy", type=float, default=0.0)
    ap.add_argument("--ky", type=float, default=1.0, help="effective length factor, y buckling")
    ap.add_argument("--kz", type=float, default=1.0, help="effective length factor, z buckling")
    ap.add_argument("--kLT", type=float, default=None, help="LTB length factor (default = kz)")
    ap.add_argument("--psi-y", type=float, default=None, help="end-moment ratio for Cmy (default 0; AISC: Cm for --B1)")
    ap.add_argument("--psi-z", type=float, default=None)
    ap.add_argument("--psi-LT", type=float, default=None,
                    help="end-moment ratio for C1 / CmLT (default 0); AISC: Cb from F1-1 on the linear diagram")
    ap.add_argument("--C1", type=float, default=None, help="override C1 (e.g. from LTBeam / SN003 Table 3.2)")
    ap.add_argument("--Cmy", type=float, default=None, help="override Cmy (Annex B Table B.3)")
    ap.add_argument("--Cmz", type=float, default=None)
    ap.add_argument("--CmLT", type=float, default=None)
    ap.add_argument("--sway-y", dest="sway_y", action="store_true", default=None,
                    help="sway buckling mode about y (Cmy = 0.9); default auto if ky >= 2")
    ap.add_argument("--sway-z", dest="sway_z", action="store_true", default=None)
    ap.add_argument("--factors", default=None)
    g = ap.add_argument_group("AISC 360-16/360-22 route (--code aisc)")
    g.add_argument("--code", choices=["en", "aisc"], default="en", help="design code (default en = EN 1993-1-1)")
    g.add_argument("--asd", action="store_true", help="ASD (Rn/Ω) instead of LRFD (φRn); forces = ASD combination")
    g.add_argument("--fu", type=float, default=None, help="tensile strength Fu [MPa] for D2(b) rupture")
    g.add_argument("--An", type=float, default=None, help="net area An [mm²] for D2(b) (default Ag)")
    g.add_argument("--U", type=float, default=1.0, help="shear lag factor U (Table D3.1), Ae = U·An")
    g.add_argument("--Cb", type=float, default=None, help="LTB modification factor Cb (default 1.0 or from --psi-LT)")
    g.add_argument("--Cb-moments", dest="Cb_moments", default=None,
                   help="Mmax,MA,MB,MC of the unbraced segment -> Cb from eq. (F1-1)")
    g.add_argument("--Lv", type=float, default=None, help="round HSS shear: distance max to zero shear [m] (G5)")
    g.add_argument("--B1", action="store_true", help="amplify moments by App. 8 B1 (braced member, K1 = 1)")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    if a.list:
        print("Built-in (EN 10365 nominal h b tw tf r):")
        for k, v in PROFILES.items():
            print(f"  {k:<8} {v}")
        print("Parametric: CHS:DxT  RHS:HxBxT  SHS:BxT  (add :cold, or :aisc = AISC HSS with t_des)   "
              "I:h:b:tw:tf:r[:welded]")
        return
    if not a.section or a.L is None:
        ap.error("--section and --L required")
    sec = Section(a.section, a.cold)
    print(f"Section {a.section}{' (cold-formed)' if sec.cold else ''}: A={sec.A / 100:.2f} cm²  "
          f"Iy={sec.Iy / 1e4:.1f} Iz={sec.Iz / 1e4:.1f} cm⁴  Wpl,y={sec.Wpl_y / 1e3:.1f} Wpl,z={sec.Wpl_z / 1e3:.1f} cm³  "
          f"It={sec.It / 1e4:.2f} cm⁴" + (f"  Iw={sec.Iw / 1e6:.2f}e3 cm⁶" if sec.Iw else "") +
          f"  mass={sec.mass:.1f} kg/m")
    if a.code == "aisc":
        return _main_aisc(a, sec)
    print(f"Factors: {CF.tag('steel.gM0')}, {CF.tag('steel.gM1')}, {CF.tag('steel.E')}, {CF.tag('steel.G')};  "
          f"imperfection α [{CF.status('steel.imp_alpha')}], C1 table [{CF.status('steel.C1_end_moments')}];  "
          f"fy={a.fy:g} MPa, L={a.L} m")
    print(ASSUMPTIONS)
    psi_y, psi_z, psi_LT = (0.0 if v is None else v for v in (a.psi_y, a.psi_z, a.psi_LT))
    rows, res = check(sec, a.fy, a.L, a.N, a.My, a.Mz, a.Vy, a.Vz, a.ky, a.kz, a.kLT, psi_y, psi_z, psi_LT,
                      C1=a.C1, sway_y=a.sway_y, sway_z=a.sway_z, Cmy=a.Cmy, Cmz=a.Cmz, CmLT=a.CmLT)
    print(f"Class {res['class']}  ({res['class_info']})")
    if "Cmy" in res:
        print(f"Cmy={res['Cmy']:.2f}{' (sway)' if res['sway_y'] else ''}  Cmz={res['Cmz']:.2f}"
              f"{' (sway)' if res['sway_z'] else ''}  CmLT={res['CmLT']:.2f}")
    worst = _print_rows(rows)
    if "effective" in res:
        e = res["effective"]
        print(f"Class 4 effective section (EN 1993-1-5 4.4, simplified): A_eff={e['A_eff'] / 100:.2f} cm², "
              f"W_eff,y={e['W_eff_y'] / 1e3:.1f} cm³, W_eff,z={e['W_eff_z'] / 1e3:.1f} cm³")
    for k in ("warning", "shear_note"):
        if k in res:
            print("NOTE:", res[k])
    ok = worst <= 1 and ("warning" not in res)
    print(f"Governing utilisation {worst:.2f} -> {'OK' if ok else 'NOT OK'}")
    return worst, res


def _print_rows(rows):
    print(f"{'check':<62}{'demand':>9}{'capacity':>10}{'util':>7}  ref")
    worst = 0.0
    for name, d, c, ref in rows:
        u = d / c if c else math.inf
        worst = max(worst, u)
        print(f"{name:<62}{d:9.2f}{c:10.2f}{u:7.2f}  {ref}" + ("  <-- FAIL" if u > 1 else ""))
    return worst


def _main_aisc(a, sec):
    if a.Cb is not None:
        Cb, cb_src = a.Cb, "--Cb"
    elif a.Cb_moments:
        Cb, cb_src = Cb_F1_1(*map(float, a.Cb_moments.split(","))), "F1-1 from --Cb-moments"
    elif a.psi_LT is not None:
        Cb, cb_src = Cb_linear(a.psi_LT), f"F1-1 on a linear diagram, ψ={a.psi_LT:g}"
    else:
        Cb, cb_src = 1.0, "default 1.0 (conservative)"
    cm = [a.Cmy, a.Cmz]
    for i, psi in enumerate((a.psi_y, a.psi_z)):
        if cm[i] is None and psi is not None:
            cm[i] = _A("B1")["Cm"][0] + _A("B1")["Cm"][1] * psi        # (A-8-4), ψ = −M1/M2 sign convention
    method = "ASD (Rn/Ω)" if a.asd else "LRFD (φRn)"
    print(f"Code: ANSI/AISC 360-16/360-22, {method}.  Factors: {CF.tag('aisc.E')}, {CF.tag('aisc.G')}; "
          f"φ/Ω [{CF.status('aisc.resistance')}], B4.1 limits [{CF.status('aisc.B4_1a')}/{CF.status('aisc.B4_1b')}], "
          f"E3/E7 [{CF.status('aisc.E3')}/{CF.status('aisc.E7')}], F2 [{CF.status('aisc.F2')}], "
          f"F7/F8 [{CF.status('aisc.F7')}/{CF.status('aisc.F8')}], H1 [{CF.status('aisc.H1')}];  "
          f"Fy={a.fy:g} MPa{f', Fu={a.fu:g} MPa' if a.fu else ''}, L={a.L} m, Cb={Cb:.3f} ({cb_src})")
    print(ASSUMPTIONS_AISC)
    rows, res = check_aisc(sec, a.fy, a.L, a.N, a.My, a.Mz, a.Vy, a.Vz, a.ky, a.kz, a.kLT, Cb, a.asd, a.fu,
                           a.An, a.U, a.Lv, a.B1, cm[0], cm[1])
    if "B1_y" in res:
        print(f"App. 8 B1: x-x {res['B1_y']:.3f} (Pe1={res['Pe1_y'] / 1e3:.0f} kN), y-y {res['B1_z']:.3f} "
              f"(Pe1={res['Pe1_z'] / 1e3:.0f} kN) -> Mrx={res['Mrx']:.2f}, Mry={res['Mry']:.2f} kNm")
    worst = _print_rows(rows)
    for w in res["warnings"]:
        print("NOTE:", w)
    bad = any(("not covered" in w) or ("not valid" in w) or ("not implemented" in w) for w in res["warnings"])
    ok = worst <= 1 and not bad
    print(f"Governing ratio {worst:.2f} -> {'OK' if ok else 'NOT OK'}")
    return worst, res


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
