#!/usr/bin/env python3
"""Steel member check to EN 1993-1-1 for CHS, RHS/SHS and I/H sections.

For masts, struts, booms, arch segments (as straight members), edge beams and
frames of tensile structures.

Sections (--section):
  IPE200 | HEA240 | HEB300 ...        built-in EN 10365 nominal dimensions (see --list)
  CHS:219.1x8[:cold]                  circular hollow (hot-finished default)
  RHS:200x100x8[:cold]  SHS:150x8     rectangular / square hollow (EN 10210 hot / EN 10219 cold radii)
  I:h:b:tw:tf:r[:welded]              any doubly-symmetric I (r = root radius or weld size)

Section properties are computed from the true outline (root radii, corner radii)
by polygon integration; plastic moduli by half-section clipping.

Checks
  * cross-section class (Table 5.2) under the actual N (+ bending)
  * section: N, V (y/z), N + My + Mz (conservative linear 6.2.1(7) for class 1–3)
  * flexural buckling y and z (6.3.1, curves per Table 6.2)
  * lateral-torsional buckling for I sections (6.3.2.2 general case, M_cr with C1)
  * member interaction N + My + Mz (6.3.3, Annex B method 2)
  * tension members (N < 0): N_t,Rd = A·fy/γM0 (net section: check separately)

Units: kN, kNm, m for loads/lengths; mm for section input.

Examples
  python3 member_check.py --section CHS:219.1x8 --L 7.5 --N 420 --My 12
  python3 member_check.py --section SHS:150x8 --L 6 --N 300 --My 25 --Mz 10 --cold
  python3 member_check.py --section IPE300 --L 6 --N 50 --My 80 --Vz 60 --kLT 1.0 --psi-LT 0
  python3 member_check.py --section HEB200 --L 5 --N 600 --My 30 --ky 1 --kz 1
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
ALPHA = {"a0": 0.13, "a": 0.21, "b": 0.34, "c": 0.49, "d": 0.76}


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
        if self.cold:  # EN 10219-2
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
    if sec.kind == "CHS":
        r = sec.D / sec.t
        return (1 if r <= 50 * eps ** 2 else 2 if r <= 70 * eps ** 2 else 3 if r <= 90 * eps ** 2 else 4), f"d/t={r:.1f}"
    if sec.kind == "RHS":
        cls = 1
        info = []
        for c in (sec.h - 3 * sec.t, sec.b - 3 * sec.t):
            ct = c / sec.t
            # conservative: wall in compression unless N ≈ 0
            lim = (33, 38, 42) if NEd > 0 else (72, 83, 124)
            k = 1 if ct <= lim[0] * eps else 2 if ct <= lim[1] * eps else 3 if ct <= lim[2] * eps else 4
            cls = max(cls, k)
            info.append(f"c/t={ct:.1f}")
        return cls, ", ".join(info)
    # I section: flange outstand + web with alpha from N
    cf = (sec.b - sec.tw - 2 * sec.r) / 2
    ctf = cf / sec.tf
    kf = 1 if ctf <= 9 * eps else 2 if ctf <= 10 * eps else 3 if ctf <= 14 * eps else 4
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
    if lam <= 0.2:
        return 1.0
    ph = 0.5 * (1 + alpha * (lam - 0.2) + lam ** 2)
    return min(1.0, 1 / (ph + math.sqrt(ph ** 2 - lam ** 2)))


def check(sec: Section, fy, L, N, My=0.0, Mz=0.0, Vy=0.0, Vz=0.0, ky=1.0, kz=1.0, kLT=None,
          psi_y=0.0, psi_z=0.0, psi_LT=0.0):
    E = CF.get("steel.E")
    G = E / 2.6
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
    if NEd < 0:  # tension
        rows.append(("tension N_t (gross)", -N, NRk / gM0 / 1e3, "6.2.3"))
        u = -NEd / (NRk / gM0) + MyEd / (MyRk / gM0) + MzEd / (MzRk / gM0)
        rows.append(("section N + My + Mz (linear)", u, 1.0, "6.2.1(7)"))
        return rows, res
    u_sec = NEd / (NRk / gM0) + MyEd / (MyRk / gM0) + MzEd / (MzRk / gM0)
    rows.append(("section N + My + Mz (linear, conservative)", u_sec, 1.0, "6.2.1(7)"))
    cy, cz, clt = sec.curves(fy)
    out = {}
    for ax, k, I, c in (("y", ky, sec.Iy, cy), ("z", kz, sec.Iz, cz)):
        Lcr = k * L * 1000
        Ncr = math.pi ** 2 * E * I / Lcr ** 2
        lam = math.sqrt(NRk / Ncr)
        x = chi(lam, ALPHA[c])
        out[ax] = (lam, x, c, Lcr / math.sqrt(I / sec.A))
        rows.append((f"flexural buckling {ax} (curve {c}, λ̄={lam:.2f}, χ={x:.3f})", N, x * NRk / gM1 / 1e3, "6.3.1"))
    # LTB
    chiLT = 1.0
    if sec.kind == "I" and MyEd > 0:
        Lb = (kLT if kLT is not None else kz) * L * 1000
        C1 = min(1.88 - 1.40 * psi_LT + 0.52 * psi_LT ** 2, 2.7)
        Mcr = C1 * math.pi ** 2 * E * sec.Iz / Lb ** 2 * math.sqrt(sec.Iw / sec.Iz + Lb ** 2 * G * sec.It /
                                                                   (math.pi ** 2 * E * sec.Iz))
        lamLT = math.sqrt(Wy * fy / Mcr)
        chiLT = chi(lamLT, ALPHA[clt])
        rows.append((f"LTB (curve {clt}, C1={C1:.2f}, Mcr={Mcr / 1e6:.0f} kNm, λ̄LT={lamLT:.2f})",
                     abs(My), chiLT * MyRk / gM1 / 1e6, "6.3.2.2"))
    # Annex B interaction
    lam_y, chi_y = out["y"][0], out["y"][1]
    lam_z, chi_z = out["z"][0], out["z"][1]
    ny = NEd / (chi_y * NRk / gM1)
    nz = NEd / (chi_z * NRk / gM1)
    Cmy = max(0.4, 0.6 + 0.4 * psi_y)
    Cmz = max(0.4, 0.6 + 0.4 * psi_z)
    CmLT = max(0.4, 0.6 + 0.4 * psi_LT)
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
    if sec.kind == "I" and MyEd > 0 and lam_z >= 0.4:  # torsionally flexible member
        kzy = max(1 - 0.1 * lam_z * nz / (CmLT - 0.25), 1 - 0.1 * nz / (CmLT - 0.25)) if cls <= 2 else \
            max(1 - 0.05 * lam_z * nz / (CmLT - 0.25), 1 - 0.05 * nz / (CmLT - 0.25))
    else:
        kzy = 0.6 * kyy if cls <= 2 else 0.8 * kyy
    e61 = ny + kyy * MyEd / (chiLT * MyRk / gM1) + kyz * MzEd / (MzRk / gM1)
    e62 = nz + kzy * MyEd / (chiLT * MyRk / gM1) + kzz * MzEd / (MzRk / gM1)
    rows.append((f"interaction (6.61) kyy={kyy:.2f} kyz={kyz:.2f}", e61, 1.0, "6.3.3 / Annex B"))
    rows.append((f"interaction (6.62) kzy={kzy:.2f} kzz={kzz:.2f}", e62, 1.0, "6.3.3 / Annex B"))
    res.update({"slenderness_y": out["y"][3], "slenderness_z": out["z"][3]})
    return rows, res


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
    ap.add_argument("--psi-y", type=float, default=0.0, help="end-moment ratio for Cmy")
    ap.add_argument("--psi-z", type=float, default=0.0)
    ap.add_argument("--psi-LT", type=float, default=0.0, help="end-moment ratio for C1 / CmLT")
    ap.add_argument("--factors", default=None)
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    if a.list:
        print("Built-in (EN 10365 nominal h b tw tf r):")
        for k, v in PROFILES.items():
            print(f"  {k:<8} {v}")
        print("Parametric: CHS:DxT  RHS:HxBxT  SHS:BxT  (add :cold)   I:h:b:tw:tf:r[:welded]")
        return
    if not a.section or a.L is None:
        ap.error("--section and --L required")
    sec = Section(a.section, a.cold)
    print(f"Section {a.section}{' (cold-formed)' if sec.cold else ''}: A={sec.A / 100:.2f} cm²  "
          f"Iy={sec.Iy / 1e4:.1f} Iz={sec.Iz / 1e4:.1f} cm⁴  Wpl,y={sec.Wpl_y / 1e3:.1f} Wpl,z={sec.Wpl_z / 1e3:.1f} cm³  "
          f"It={sec.It / 1e4:.2f} cm⁴" + (f"  Iw={sec.Iw / 1e6:.2f}e3 cm⁶" if sec.Iw else "") +
          f"  mass={sec.mass:.1f} kg/m")
    print(f"Partial factors: {CF.tag('steel.gM0')}, {CF.tag('steel.gM1')};  fy={a.fy:g} MPa, L={a.L} m")
    rows, res = check(sec, a.fy, a.L, a.N, a.My, a.Mz, a.Vy, a.Vz, a.ky, a.kz, a.kLT, a.psi_y, a.psi_z, a.psi_LT)
    print(f"Class {res['class']}  ({res['class_info']})")
    print(f"{'check':<62}{'demand':>9}{'capacity':>10}{'util':>7}  ref")
    worst = 0.0
    for name, d, c, ref in rows:
        u = d / c if c else math.inf
        worst = max(worst, u)
        print(f"{name:<62}{d:9.2f}{c:10.2f}{u:7.2f}  {ref}" + ("  <-- FAIL" if u > 1 else ""))
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


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
