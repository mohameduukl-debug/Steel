#!/usr/bin/env python3
"""Cable calculator: catenary / sag-tension, unstressed (fabrication) length,
edge-cable force, thermal effects and resistance checks.

Sub-commands
------------
  sag       exact catenary between two supports (any height difference) for a
            given horizontal tension H, sag f, or cable length S; reports
            support forces, Tmax, length and parabolic cross-check
  length    unstressed length S0 at reference temperature from the stressed
            geometry (removes elastic stretch and thermal strain)
  edge      membrane edge cable: T = n·R, with R from chord & sag
  resist    tension resistance: EN 1993-1-11 (F_Rd = F_uk / (1.5·γR),
            F_uk = F_min·k_e) and ASCE/SEI 19 (S_d = S_n·N_f >= 2.2·T)
  irvine    change of horizontal tension due to load change / temperature
            (Irvine's cable equation, parabolic cable)
  freq      natural frequencies of a taut cable f_n = n/(2L)·sqrt(T/m)
  freq-tension  cable force from MEASURED frequencies (taut string + bending stiffness;
            least-squares T and EI from several modes; sag warning via Irvine λ²)
  rod       group A tension rod (threaded bar): EN 1993-1-1/1-8 route min(A_g·f_y/γM0,
            k2·f_u·A_s/γM2) and EN 1993-1-11 route min(F_k/γR, F_uk/(1.5γR)); fitting capacity
  stress-turns  turnbuckle / fork adjustment for a force change: ΔL = ΔF·(L/EA_sec + 1/k_sup),
            turns = ΔL / lead (Ernst secant modulus for a sagging cable)
  clamp     slip resistance of a bolted cable clamp
  saddle    cable over a saddle: transverse pressure, R/d, outer-wire bending

--sensitivity (resist, clamp, saddle): re-runs the check at both ends of the range
of every UNVERIFIED [U] factor it uses and says whether the OK / NOT OK decision
depends on that factor.

Units: kN, m, mm (diameters), kN/m (loads), °C.

Examples
--------
  python3 cable_calc.py sag --L 20 --h 2 --w 0.05 --f 0.8
  python3 cable_calc.py sag --L 12 --w 1.8 --H 60 --EA 17000
  python3 cable_calc.py length --L 12 --w 1.8 --H 60 --EA 17000 --T-install 30 --T-ref 20
  python3 cable_calc.py edge --chord 10 --sag 1.0 --n 3.0
  python3 cable_calc.py resist --Fmin 537 --ke 0.9 --FEd 240 --gammaR 1.0
  python3 cable_calc.py irvine --L 20 --w0 0.1 --H0 50 --w1 1.0 --EA 20000
  python3 cable_calc.py freq --L 15 --T 80 --m 3.4
  python3 cable_calc.py freq-tension --L 15 --m 3.4 --EI 2.0 --f 1:2.75 --f 2:5.52 --f 3:8.30
  python3 cable_calc.py rod --d 30 --fy 460 --fu 610 --FEd 180 --fitting-Rd 250
  python3 cable_calc.py stress-turns --L 10 --EA 14000 --F1 5 --F2 20 --pitch 3.5 --w 0.02
  python3 cable_calc.py resist --Fmin 367 --termination ferrule --FEd 125 --Fser 85 --sensitivity

Code values: γR=1.0, k_e (1.0 sockets / 0.9 swaged) and the ASCE 2.2 factor
are defaults taken from EAD 200001-00-0602 / ETAs / ASCE 19 practice — always
confirm against the edition of the standard and National Annex in force
(EN 1993-1-11:2026 has replaced the 2006 edition in some countries).
"""
from __future__ import annotations

import argparse
import math
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as F  # noqa: E402  central code-factor register (V/C/U tagged)


# ---------------------------------------------------------------- catenary
class Catenary:
    """y(x) = a·cosh((x−x0)/a) + c through (0,0) and (L,h); a = H/w.

    w = load per unit ARC length (self-weight). For loads per unit horizontal
    length (membrane edge, roof load), use the parabola results (see .parabola()).
    """

    def __init__(self, L: float, h: float, w: float, H: float):
        self.L, self.h, self.w, self.H = L, h, w, H
        a = self.a = H / w
        self.x0 = L / 2 - a * math.asinh(h / (2 * a * math.sinh(L / (2 * a))))
        self.c = -a * math.cosh(-self.x0 / a)

    def y(self, x):
        return self.a * math.cosh((x - self.x0) / self.a) + self.c

    def slope(self, x):
        return math.sinh((x - self.x0) / self.a)

    def T(self, x):
        return self.H * math.cosh((x - self.x0) / self.a)

    @property
    def length(self):
        a, x0 = self.a, self.x0
        return a * (math.sinh((self.L - x0) / a) - math.sinh(-x0 / a))

    @property
    def sag_mid(self):
        """vertical sag at mid-span measured from the chord."""
        return self.h / 2 - self.y(self.L / 2)

    @property
    def sag_max(self):
        """max vertical distance chord -> cable (where slope = chord slope)."""
        xs = self.x0 + self.a * math.asinh(self.h / self.L)
        return self.h * xs / self.L - self.y(xs)

    def stretch(self, EA: float, n: int = 400) -> float:
        """elastic elongation ∫T/EA ds (Simpson)."""
        L = self.L
        f = lambda x: self.T(x) * math.cosh((x - self.x0) / self.a) / EA
        hstep = L / n
        s = f(0) + f(L) + sum((4 if k % 2 else 2) * f(k * hstep) for k in range(1, n))
        return s * hstep / 3

    def unstretched(self, EA: float, n: int = 400) -> float:
        """unstressed length ∫ ds/(1 + T/EA) of the stressed geometry (Simpson): exact for linear-elastic strain,
        L/(1 + F/EA) for a straight member; S − ∫T/EA ds is its first-order approximation."""
        L = self.L
        f = lambda x: math.cosh((x - self.x0) / self.a) / (1 + self.T(x) / EA)  # noqa: E731
        hstep = L / n
        s = f(0) + f(L) + sum((4 if k % 2 else 2) * f(k * hstep) for k in range(1, n))
        return s * hstep / 3


def solve_H(L, h, w, target, kind):
    """find H such that sag_mid (kind='f') or length (kind='S') equals target."""
    chord = math.hypot(L, h)
    if kind == "S" and target <= chord:
        raise SystemExit("cable length must exceed chord length")
    lo, hi = 1e-6 * w * L, 1e7 * w * L
    for _ in range(300):
        mid = math.sqrt(lo * hi)
        c = Catenary(L, h, w, mid)
        val = c.sag_mid if kind == "f" else c.length
        # sag & length both decrease with H
        if val > target:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def parabola_length(L, h, f):
    """exact arc length of the parabola through (0,0) and (L,h) with mid-span sag f below the chord."""
    if f == 0:
        return math.hypot(L, h)
    B = 8 * f / (L * L)                       # du/dx of the slope u = y'(x)
    G = lambda u: 0.5 * (u * math.sqrt(1 + u * u) + math.asinh(u))  # noqa: E731  ∫√(1+u²)du
    return (G(h / L + 4 * f / L) - G(h / L - 4 * f / L)) / B


def parabola(L, h, w, H=None, f=None):
    """parabolic cable, w per unit horizontal length."""
    if H is None:
        H = w * L * L / (8 * f)
    else:
        f = w * L * L / (8 * H)
    VA = w * L / 2 - H * h / L
    VB = w * L / 2 + H * h / L
    TA, TB = math.hypot(H, VA), math.hypot(H, VB)
    n = f / L
    Lc = math.hypot(L, h)
    return {"H": H, "f": f, "V_low": VA, "V_high": VB, "T_low": TA, "T_high": TB, "Tmax": max(TA, TB),
            "length": parabola_length(L, h, f), "length_approx": Lc + 8 * f * f / (3 * Lc), "sag_ratio": n}


def assumptions(*lines):
    """print the modelling assumptions of a sub-command (CLAUDE.md: every tool prints its assumptions)."""
    print("Assumptions:")
    for ln in lines:
        print(f"  - {ln}")


KE_KEY = {"socket": "cable.ke_socket", "swaged": "cable.ke_swaged", "ferrule": "cable.ke_ferrule",
          "ubolt": "cable.ke_ubolt"}


def fill_factors(a):
    """fill unspecified code values from the factor register and remember their status."""
    if getattr(a, "factors", None):
        os.environ["TENSILE_FACTORS"] = a.factors
    if getattr(a, "termination", None):
        if a.ke is not None:
            raise SystemExit("give --ke or --termination, not both")
        a.ke, a.ke_st = F.get(KE_KEY[a.termination]), F.status(KE_KEY[a.termination])
    elif hasattr(a, "ke"):
        a.ke, a.ke_st = (1.0, "socket default") if a.ke is None else (a.ke, "user")
    a.fsls_key = "cable.f_sls_bending_checked" if getattr(a, "bending_checked", False) else "cable.f_sls"
    for attr, key in (("gammaR", "cable.gammaR"), ("fsls", a.fsls_key), ("asce", "cable.asce19_factor"),
                      ("alpha", "cable.alpha_carbon")):
        if hasattr(a, attr) and getattr(a, attr) is None:
            setattr(a, attr, F.get(key))
            setattr(a, attr + "_st", F.status(key))
        elif hasattr(a, attr):
            setattr(a, attr + "_st", "user")


# ----------------------------------------------------------------- commands
def cmd_sag(a):
    if sum(v is not None for v in (a.H, a.f, a.S)) != 1:
        raise SystemExit("give exactly one of --H, --f, --S")
    H = a.H if a.H is not None else solve_H(a.L, a.h, a.w, a.f if a.f is not None else a.S,
                                            "f" if a.f is not None else "S")
    c = Catenary(a.L, a.h, a.w, H)
    VA = H * c.slope(0)
    VB = H * c.slope(a.L)
    print(f"Catenary  span L={a.L} m  height diff h={a.h} m  w={a.w} kN/m (per arc length)")
    print(f"  H (horizontal tension)   = {H:10.3f} kN")
    print(f"  sag at mid-span (chord)  = {c.sag_mid:10.4f} m   (max {c.sag_max:.4f} m)   "
          f"sag/span = {c.sag_mid / a.L:.4f}")
    print(f"  cable length S           = {c.length:10.4f} m   chord = {math.hypot(a.L, a.h):.4f} m")
    print(f"  support A (x=0):  V = {-VA:9.3f} kN (up)   T = {c.T(0):9.3f} kN")
    print(f"  support B (x=L):  V = {VB:9.3f} kN (up)   T = {c.T(a.L):9.3f} kN")
    print(f"  Tmax = {max(c.T(0), c.T(a.L)):.3f} kN")
    p = parabola(a.L, a.h, a.w, H=H)
    print(f"  parabola check (same H, w per horizontal m): f = {p['f']:.4f} m, Tmax = {p['Tmax']:.3f} kN, "
          f"S = {p['length']:.4f} m (exact parabola arc)")
    if a.EA:
        st = c.stretch(a.EA)
        print(f"  elastic stretch ∫T/EA ds = {st * 1000:.2f} mm  -> unstressed length ∫ds/(1+T/EA) = "
              f"{c.unstretched(a.EA):.4f} m")
    assumptions("w is per unit ARC length (self-weight): exact catenary; pinned supports; geometry of the loaded cable",
                "the parabola line uses w per HORIZONTAL length (membrane/roof load) with the same H — it is a "
                "different load case, so H, f and Tmax differ by O(n²) (see reference/validation.md)",
                "unstressed length = ∫ds/(1 + T/EA) over the loaded geometry (linear-elastic, prestretched cable)")
    return c


def cmd_length(a):
    H = a.H if a.H is not None else solve_H(a.L, a.h, a.w, a.f, "f")
    c = Catenary(a.L, a.h, a.w, H)
    S = c.length
    st = c.stretch(a.EA)
    S0_inst = c.unstretched(a.EA)
    S0_ref = S0_inst / (1 + a.alpha * (a.T_install - a.T_ref))
    print(f"Stressed geometric length S          = {S:.4f} m  (H = {H:.2f} kN, Tmax = {c.T(0 if c.T(0) > c.T(a.L) else a.L):.2f} kN)")
    print(f"Elastic stretch ∫T/EA ds             = {st * 1000:.2f} mm  (EA = {a.EA:.0f} kN)")
    print(f"Unstressed length at {a.T_install:>5.1f} °C        = {S0_inst:.4f} m")
    print(f"Unstressed length at ref {a.T_ref:>5.1f} °C    = {S0_ref:.4f} m   (alpha = {a.alpha:.1e}/K [{a.alpha_st}])")
    if getattr(a, "creep", False):
        cr = F.get("cable.creep_shortening_mm_per_m")
        S0_ref -= cr * S0_ref / 1000
        print(f"Creep allowance {cr} mm/m [{F.status('cable.creep_shortening_mm_per_m')}] (EN 1993-1-11 3.2.2(3) NOTE 1) "
              f"-> cut length {S0_ref:.4f} m")
    if a.fittings:
        print(f"Cable length excl. fittings          = {S0_ref - a.fittings / 1000:.4f} m "
              f"(pin-to-pin minus {a.fittings:.0f} mm of fittings)")
    print("Note: specify on the cable schedule: length is pin-to-pin, unstressed (or under the "
          "stated reference load), at the reference temperature; prestretched cable.")
    assumptions("catenary geometry with w per arc length; unstressed length S0 = ∫ds/(1 + T/EA) (exact for "
                "linear-elastic strain; = L/(1 + F/EA) for a straight member)",
                "uniform temperature, linear thermal strain α·ΔT on the unstressed length (EN 1993-1-11 3.3)",
                "prestretched cable with stable E (EN 1993-1-11 3.2.2(2)); EN 3.4(2) also lists creep, clamp "
                "seating and first-loading set — add them (e.g. --creep) or use the supplier's measured values")
    return S0_ref


def cmd_edge(a):
    c, s = a.chord, a.sag
    R = c * c / (8 * s) + s / 2
    T = a.n * R
    ratio = s / c
    print(f"Edge cable  chord c = {c} m, sag s = {s} m (s/c = {ratio:.3f}), membrane stress n = {a.n} kN/m")
    print(f"  radius R = c²/(8s) + s/2 = {R:.3f} m")
    print(f"  cable force T = n·R      = {T:.2f} kN")
    # resultant at each end along the chord ~ T; angle between chord and cable tangent
    theta = math.degrees(math.asin(min(1.0, c / (2 * R))))
    print(f"  tangent angle to chord at ends = {theta:.1f} deg")
    if not 0.07 <= ratio <= 0.13:
        print("  NOTE: typical edge-cable sag is ~8–12 % of chord (≈10 % common). Flatter -> higher T "
              "and anchor forces; deeper -> fabric loss, softer edge.")
    assumptions("uniform membrane stress n normal to the cable, in the plane of the edge: the cable is a circular "
                "arc with constant T = n·R (hoop equilibrium)",
                "no tangential (shear) load from the membrane; cable self-weight neglected",
                "T is characteristic unless n is a factored (design) stress; use the analysis for non-uniform n")
    return T


def cmd_resist(a):
    Fuk = a.Fmin * a.ke
    FRd_en = Fuk / (1.5 * a.gammaR)
    if a.Fk:
        FRd_en = min(FRd_en, a.Fk / a.gammaR)
    print("EN 1993-1-11 (6.2) — group B/C tension component")
    print(f"  F_min = {a.Fmin:.1f} kN  k_e = {a.ke:.2f}  ->  F_uk = {Fuk:.1f} kN")
    print(f"  F_Rd = F_uk/(1.5·γR) = {Fuk / (1.5 * a.gammaR):.1f} kN   (γR = {a.gammaR} [{getattr(a, 'gammaR_st', '?')}])"
          + (f";  F_k/γR = {a.Fk / a.gammaR:.1f} kN" if a.Fk else ""))
    rows = [("EN ULS", a.FEd, FRd_en)]
    if a.Fser is not None:
        lim = a.fsls * Fuk
        rows.append((f"EN SLS (≤{a.fsls:.2f}·F_uk [{getattr(a, 'fsls_st', '?')}])", a.Fser, lim))
    Sd = a.Fmin * a.Nf
    rows.append((f"ASCE 19 (S_d ≥ {a.asce:.1f}·T [{getattr(a, 'asce_st', '?')}])", a.asce * (a.T_asce or a.FEd / 1.4), Sd))
    for name, dem, cap in rows:
        print(f"  {name:<44} demand {dem:9.1f}  capacity {cap:9.1f}  util {dem / cap:5.2f}"
              + ("  <-- FAIL" if dem > cap else ""))
    if a.Fmin_force is not None:
        print(f"  No-slack check: minimum force under all combinations = {a.Fmin_force:.1f} kN "
              + ("OK (>0)" if a.Fmin_force > 0 else "SLACK -> increase prestress / revise geometry"))
    assumptions(f"k_e = {a.ke:.2f} [{getattr(a, 'ke_st', '?')}] (EN 1993-1-11 Table 6.3); give --Fk for components "
                "that need the proof-strength term of eq. (6.2) (bars; not needed for ropes with F_k ≥ F_uk/1.5)",
                "F_Ed is the ULS design force from a geometrically non-linear analysis; F_ser the characteristic force",
                "ASCE 19 line: T = --T-asce, else F_Ed/1.4 as a rough unfactored force (give --T-asce)",
                "group A tension rods are designed to EN 1993-1-1/1-8 (EN 1993-1-11 6.1): use the 'rod' sub-command")
    if getattr(a, "sensitivity", False):
        resist_sensitivity(a)
    return FRd_en


def resist_utils(a, ke=None, fsls=None):
    """(ULS, SLS) utilisations of the EN 1993-1-11 check for given k_e / f_sls."""
    ke = a.ke if ke is None else ke
    fsls = a.fsls if fsls is None else fsls
    Fuk = a.Fmin * ke
    FRd = Fuk / (1.5 * a.gammaR)
    if a.Fk:
        FRd = min(FRd, a.Fk / a.gammaR)
    return a.FEd / FRd, (a.Fser / (fsls * Fuk) if a.Fser is not None else None)


def resist_sensitivity(a):
    """re-check at the ends of the range of each [U] factor used (register values only)."""
    out = []
    print("Sensitivity to uncertain factors:")
    if getattr(a, "termination", None):
        key = KE_KEY[a.termination]
        res = F.sensitivity(lambda k: max(u for u in resist_utils(a, ke=k) if u is not None), key)
        print(F.sens_line(f"k_e ({a.termination}) on max(ULS, SLS)", res))
        if res["lo"] is not None:
            out.append(res)
    if a.Fser is not None and a.fsls_st != "user" and F.frange(a.fsls_key):
        res = F.sensitivity(lambda f: resist_utils(a, fsls=f)[1], a.fsls_key)
        print(F.sens_line("f_sls on SLS", res))
        out.append(res)
    if not out:
        print("  no factor with an uncertainty range used in this check (γR, 1.5, k_e and ASCE 2.2 are [V]; "
              "user values are yours)")
    return out


def cmd_irvine(a):
    """(H−H0)·L/(EA/Le) ... solve for H with parabolic cable, level supports."""
    L, w0, w1, H0, EA = a.L, a.w0, a.w1, a.H0, a.EA
    f0 = w0 * L * L / (8 * H0)
    Le = L * (1 + 8 * (f0 / L) ** 2)

    def g(H):
        return (H - H0) * Le / EA - (w1 * w1 * L ** 3 / (24 * H * H) - w0 * w0 * L ** 3 / (24 * H0 * H0)) \
            + a.alpha * a.dT * Le

    lo, hi = 1e-6, 1e7
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if g(mid) > 0:
            hi = mid
        else:
            lo = mid
    H = 0.5 * (lo + hi)
    f = w1 * L * L / (8 * H)
    lam2 = (w0 * L / H0) ** 2 * L / (H0 * Le / EA)
    print(f"Irvine: L={L} m, w0={w0} -> w1={w1} kN/m, ΔT={a.dT} K, EA={EA:.0f} kN")
    print(f"  initial  H0 = {H0:.2f} kN, sag f0 = {f0:.4f} m (f/L = {f0 / L:.4f})")
    print(f"  final    H  = {H:.2f} kN, sag f  = {f:.4f} m, Tmax ≈ {H * math.sqrt(1 + 16 * (f / L) ** 2):.2f} kN")
    print(f"  Irvine parameter λ² = {lam2:.2f}  ({'taut-string like' if lam2 < 1 else 'sag-dominated'})")
    assumptions("Irvine (1981) cable equation: parabolic profile, level supports, w per horizontal length, "
                "uniformly distributed load before and after",
                "L_e = L(1 + 8n²) from the initial state; unstressed length constant (no slip, no support movement)",
                "small sag (f/L ≲ 1/8); error vs the exact elastic catenary < 1 % at f/L = 1/20 "
                "(reference/validation.md)")
    return H


def bolt_preload(a):
    """F_p,C = 0.7·f_ub·A_s [kN] (EN 1993-1-8 eq. (3.7), factor from the register), or the user's --Fp per bolt."""
    if getattr(a, "Fp", None):
        return a.Fp
    AS = {10: 58, 12: 84.3, 16: 157, 20: 245, 24: 353, 27: 459, 30: 561}
    fub = {"8.8": 800, "10.9": 1000, "A4-70": 700, "A4-80": 800}[a.grade]
    As = AS.get(int(a.bolt_d), 0.78 * math.pi * a.bolt_d ** 2 / 4)
    return F.get("cable.clamp_preload_factor") * fub * As / 1e3


def clamp_factor(a, attr, key):
    """user value (--mu / --retained) or register value."""
    v = getattr(a, attr, None)
    return (v, "user") if v is not None else (F.get(key), F.status(key))


def clamp_frd(a, mu=None, gfr=None, kl=None):
    """slip resistance [kN] of a bolted cable clamp, EN 1993-1-11 eq. (6.9):
    F_Rd = μ·(n_s·n_b·F_p·k_ret + F_Ed,⊥)/γM,fr  (n_s friction surfaces, F_r = n_b·F_p·k_ret)."""
    Fp = bolt_preload(a)
    mu = clamp_factor(a, "mu", "cable.clamp_mu")[0] if mu is None else mu
    gfr = F.get("cable.clamp_gamma") if gfr is None else gfr
    kl = clamp_factor(a, "retained", "cable.clamp_loss")[0] if kl is None else kl
    Fperp = getattr(a, "Fperp", 0.0) or 0.0
    return mu * (a.surfaces * a.nb * Fp * kl + Fperp) / gfr, Fp


def cmd_clamp(a):
    """slip resistance of a bolted cable clamp (cross clamp, edge clamp, saddle clamp)."""
    FRd, Fp = clamp_frd(a)
    (mu, mu_st), (kl, kl_st) = clamp_factor(a, "mu", "cable.clamp_mu"), clamp_factor(a, "retained", "cable.clamp_loss")
    gfr = F.get("cable.clamp_gamma")
    Fperp = getattr(a, "Fperp", 0.0) or 0.0
    src = "given (--Fp)" if getattr(a, "Fp", None) else f"0.7·f_ub·A_s, M{a.bolt_d:g} {a.grade}"
    print(f"Cable clamp: {a.nb} bolts, F_p = {Fp:.1f} kN each ({src}), {a.surfaces} friction surfaces"
          + (f", F_Ed,⊥ = {Fperp:g} kN" if Fperp else ""))
    print(f"  μ = {mu} [{mu_st}], preload retained {kl} [{kl_st}], γM,fr = {gfr} [{F.status('cable.clamp_gamma')}]")
    print(f"  F_r = n_b·F_p·k = {a.nb * Fp * kl:.1f} kN;  F_Rd = μ(n_s·F_r + F_Ed,⊥)/γM,fr  (EN 1993-1-11 eq. 6.9)")
    u = a.dT / FRd
    print(f"  slip resistance F_Rd = {FRd:.1f} kN  vs  force to hold {a.dT:.1f} kN  -> util {u:.2f}"
          + ("  <-- FAIL" if u > 1 else "  OK"))
    print("  Re-tighten bolts after stressing (strand diameter reduces under tension); confirm μ by clamp test.")
    if getattr(a, "sensitivity", False):
        print("Sensitivity to uncertain factors (one at a time, others at register value):")
        worst = {}
        for key, name, kw, bad, attr in (("cable.clamp_mu", "μ", "mu", 0, "mu"), ("cable.clamp_gamma", "γM,fr", "gfr", 1, None),
                                         ("cable.clamp_loss", "preload retained", "kl", 0, "retained")):
            if attr and getattr(a, attr, None) is not None:
                print(f"  sensitivity {name}: user value {getattr(a, attr)} (no range)")
                continue
            print(F.sens_line(name, F.sensitivity(lambda v, kw=kw: a.dT / clamp_frd(a, **{kw: v})[0], key)))
            if F.frange(key):
                worst[kw] = F.frange(key)[bad]
        uw = a.dT / clamp_frd(a, **worst)[0]
        print(f"  all ranged factors at their unfavourable ends: util {uw:.2f} -> "
              + ("still OK" if uw <= 1 else "NOT OK: test the clamp (slip test, EN 1993-1-11 has no default μ) or add bolts"))
    assumptions("EN 1993-1-11 6.4.1 eq. (6.9); μ has NO code value (slip test, Annex A) — register 0.1 is a placeholder",
                "clamping force F_r = bolts × preload × retained fraction; the retained fraction covers creep, diameter "
                "reduction under tension, bedding and temperature (6.3.2(3)) — 0.8 assumes re-tightening after stressing",
                "n_s = 2 for a two-half clamp gripping the cable (friction on both halves); F_Ed,⊥ counted once",
                "transverse pressure of F_r to 6.3.3 / Table 6.4 is checked with 'saddle --Fr' (not here)")
    return u


def saddle_checks(a, mu=None):
    """EN 1993-1-11 6.3 checks of a cable over a saddle -> dict of results (forces kN, lengths mm)."""
    lined = getattr(a, "lined", False)
    rd_key = "cable.saddle_min_R_over_d_lined" if lined else "cable.saddle_min_R_over_d"
    Rmm = a.R * 1000
    Rmin = max(F.get(rd_key) * a.d, F.get("cable.saddle_min_R_over_wire") * a.delta)
    r = {"Rmin": Rmin, "u_radius": Rmin / Rmm, "rd_key": rd_key, "sigma_b": a.E * 1000 * a.delta / (2 * Rmm)}
    T2, wrap = getattr(a, "T2", None), getattr(a, "wrap", None)
    if T2 and wrap:
        mu = F.get("cable.clamp_mu") if mu is None else mu
        g = F.get("cable.clamp_gamma")
        alpha = math.radians(wrap)
        T1, T2 = max(a.T, T2), min(a.T, T2)
        Fr = getattr(a, "Fr", None) or 0.0
        k = F.get("cable.saddle_k_clamp") if getattr(a, "k_clamp", None) is None else a.k_clamp
        r["u_slip"] = (T1 - k * Fr * mu / g) / (T2 * math.exp(mu * alpha / g))      # eq. (6.6) / (6.7)
        r["L2"] = Rmm * alpha
    Fr, L2 = getattr(a, "Fr", None), getattr(a, "L2", None) or r.get("L2")
    if Fr and L2:
        dp = getattr(a, "dprime", None) or a.d
        if not 0.6 * a.d - 1e-9 <= dp <= a.d + 1e-9:
            raise SystemExit("EN 1993-1-11 6.3.3: 0.6·d ≤ d' ≤ d")
        key = ("cable.saddle_p_lim_FLC" if a.type == "FLC" else "cable.saddle_p_lim_OSS") + ("_lined" if lined else "")
        q = Fr * 1e3 / (dp * L2)
        r["q"], r["qRd"] = q, F.get(key) / F.get("cable.saddle_gamma_bed")
        r["u_pressure"] = q / r["qRd"]
    return r


def cmd_saddle(a):
    """cable over a saddle / deviator: EN 1993-1-11 6.3 radius, slip, clamping pressure; groove pressure; wire bending.

    Returns p/q_Rk with p = T/(R·d) (indicative groove pressure, kept for API compatibility); the EN checks are printed."""
    p = a.T * 1e3 / (a.R * 1000 * a.d)                             # N/mm² on projected width d
    lined = getattr(a, "lined", False)
    key = ("cable.saddle_p_lim_FLC" if a.type == "FLC" else "cable.saddle_p_lim_OSS") + ("_lined" if lined else "")
    plim = F.get(key)
    r = saddle_checks(a)
    sb = r["sigma_b"]                                              # MPa, outer wire bending (Reuleaux)
    print(f"Saddle: T = {a.T} kN, R = {a.R} m, cable Ø{a.d:g} mm ({a.type}), wire δ = {a.delta} mm"
          + (", soft-metal / zinc-spray bedding ≥ 1 mm" if lined else ", steel groove"))
    print(f"  EN 6.3.1 radius: R ≥ max({F.get(r['rd_key']):g}d, {F.get('cable.saddle_min_R_over_wire'):g}δ) = "
          f"{r['Rmin']:.0f} mm [{F.status(r['rd_key'])}]  vs  R = {a.R * 1000:.0f} mm  -> util {r['u_radius']:.2f}"
          + ("  OK: wire curvature stresses may be neglected (≤ 3 % strength loss)" if r["u_radius"] <= 1 else
             "  <-- below: curvature stresses NOT covered — reduce the strength per tests/supplier (6.3.1(4))"))
    if "u_slip" in r:
        print(f"  EN 6.6/6.7 slip: (F1 − k·F_r·μ/γ)/F2 ≤ e^(μα/γM,fr), μ = {F.get('cable.clamp_mu')} "
              f"[{F.status('cable.clamp_mu')}], α = {a.wrap:g}° -> util {r['u_slip']:.2f}" + ("  <-- FAIL" if r["u_slip"] > 1 else "  OK"))
    if "u_pressure" in r:
        print(f"  EN 6.8 clamping pressure q = F_r/(d'·L2) = {r['q']:.1f} N/mm² vs q_Rk/γM,bed = {r['qRd']:.0f} "
              f"[{F.status(key)}] -> util {r['u_pressure']:.2f}" + ("  <-- FAIL" if r["u_pressure"] > 1 else "  OK"))
    if getattr(a, "Fuk", None):
        print(f"  EN 6.3.4 saddle design force k·F_uk = {F.get('cable.saddle_k')} × {a.Fuk:g} = "
              f"{F.get('cable.saddle_k') * a.Fuk:.0f} kN [{F.status('cable.saddle_k')}]")
    print(f"  groove pressure p = T/(R·d) = {p:.1f} N/mm² (indicative vs q_Rk {plim:g}: util {p / plim:.2f}; EN 6.3.3 "
          "NOTE: the pressure from F_Ed is covered by the radius rule, q_Rk applies to F_r)")
    print(f"  outer-wire bending stress σ_b = E·δ/(2R) = {sb:.0f} MPa (Reuleaux upper bound — inter-wire slip lowers it; "
          "relevant for fatigue; use a liner)")
    if getattr(a, "sensitivity", False):
        print("Sensitivity to uncertain factors:")
        if "u_slip" in r:
            print(F.sens_line("μ on saddle slip", F.sensitivity(lambda v: saddle_checks(a, mu=v)["u_slip"], "cable.clamp_mu")))
        print(F.sens_line(f"radius rule ({r['rd_key'].split('.')[-1]})",
                          F.sensitivity(lambda v: max(v * a.d, F.get('cable.saddle_min_R_over_wire') * a.delta) / (a.R * 1000),
                                        r["rd_key"])))
    assumptions("EN 1993-1-11 6.3: radius rule (6.3.1), slip (6.6/6.7, needs --T2 and --wrap), clamping pressure "
                "(6.8, needs --Fr and --L2 or --wrap), saddle force k·F_uk (6.3.4, needs --Fuk)",
                "μ cable/saddle has no code value: register placeholder (slip test); γM,fr = 1.65; γM,bed = 1.0",
                "the 400δ wire term is kept with a lined groove (conservative reading of 6.3.1(3))",
                "σ_b = E·δ/(2R) assumes no inter-wire slip (upper bound)")
    return p / plim


def cmd_freq(a):
    print(f"Taut cable L={a.L} m, T={a.T} kN, m={a.m} kg/m")
    c = math.sqrt(a.T * 1000 / a.m)
    freqs = [n * c / (2 * a.L) for n in range(1, a.modes + 1)]
    for n, fn in enumerate(freqs, 1):
        print(f"  mode {n}: f = {fn:.2f} Hz")
    print("Keep f1 clear of vortex-shedding / rain-wind ranges; add dampers or helical fillets on long stays.")
    print("EN 1993-1-11 8.3: provide for dampers (damping ratio > 0.5 %) on stays > 80 m; keep the stay frequency "
          "> 20 % away from the structure's ω and 2ω; amplitude ≤ L/500 at 15 m/s wind.")
    assumptions("taut string f_n = n/(2L)·√(T/m): pinned ends, no bending stiffness, no sag",
                "sag raises the symmetric modes (Irvine λ²): check with 'freq-tension --EA' or keep λ² ≪ 1",
                "m includes coating, sheath and fittings spread along L")
    return freqs


def metric_pitch(d):
    """ISO 261 coarse pitch; tension-rod sizes above M64 normally use the 6 mm fine series."""
    coarse = {10: 1.5, 12: 1.75, 16: 2.0, 20: 2.5, 22: 2.5, 24: 3.0, 27: 3.0, 30: 3.5, 33: 3.5, 36: 4.0,
              39: 4.0, 42: 4.5, 45: 4.5, 48: 5.0, 52: 5.0, 56: 5.5, 60: 5.5, 64: 6.0}
    if d in coarse:
        return coarse[d]
    if d > 64:
        return 6.0
    raise SystemExit(f"no default pitch for M{d:g}: give --pitch")


def stress_area(d, P):
    """ISO 898-1 tensile stress area A_s = π/4·(d − 0.9382·P)² [mm²]."""
    return math.pi / 4 * (d - 0.9382 * P) ** 2


def cmd_rod(a):
    """group A tension rod (EN 1993-1-11 group A: design to EN 1993-1-1 / 1-8)."""
    P = a.pitch or metric_pitch(a.d)
    As = getattr(a, "As", None) or stress_area(a.d, P)
    dg = a.d_shank or a.d
    Ag = math.pi * dg * dg / 4
    gM0, gM2, gR = F.get("steel.gM0"), F.get("steel.gM2"), F.get("cable.gammaR")
    k2 = F.get("steel.k2_thread")
    Npl = Ag * a.fy / gM0 / 1e3
    Nthr = k2 * a.fu * As / gM2 / 1e3
    NRd = min(Npl, Nthr)
    Fk, Fuk = a.fy * As / 1e3, a.fu * As / 1e3
    N11 = min(Fk / gR, Fuk / (1.5 * gR))
    print(f"Tension rod M{a.d:g}x{P:g} (thread A_s = {As:.0f} mm²), shank Ø{dg:g} (A_g = {Ag:.0f} mm²), "
          f"f_y = {a.fy:g}, f_u = {a.fu:g} MPa")
    print(f"  EN 1993-1-1 6.2.3 gross yield   A_g·f_y/γM0      = {Npl:8.1f} kN  (γM0 = {gM0} [{F.status('steel.gM0')}])")
    print(f"  EN 1993-1-8 T3.4 thread         k2·f_u·A_s/γM2   = {Nthr:8.1f} kN  (k2 = {k2} "
          f"[{F.status('steel.k2_thread')}], γM2 = {gM2} [{F.status('steel.gM2')}])")
    print(f"  -> N_t,Rd (group A route)                        = {NRd:8.1f} kN  governed by "
          f"{'thread' if Nthr < Npl else 'shank yield'}")
    print(f"  EN 1993-1-11 6.2 route: min(F_k/γR, F_uk/(1.5γR)) on A_s = {N11:.1f} kN  (γR = {gR} "
          f"[{F.status('cable.gammaR')}]) — for comparison / system products with an ETA")
    caps = [("rod (group A route)", NRd)]
    if a.fitting_Rd:
        caps.append(("fittings (supplier / ETA design value)", a.fitting_Rd))
    for name, cap in caps:
        u = a.FEd / cap
        print(f"  {name:<40} N_Ed {a.FEd:7.1f} / {cap:7.1f} kN  util {u:5.2f}" + ("  <-- FAIL" if u > 1 else ""))
    if a.fy / a.fu > 0.9:
        print("  NOTE: f_y/f_u > 0.9 — little ductility reserve: the thread governs; check the product ETA.")
    print("  Notes: f_y/f_u depend on the diameter (EN 10025 thickness steps; bar products per ETA). Rolled "
          "threads improve fatigue, not static A_s. Rods need prestress so they never go slack (no compression).")
    assumptions("EN 1993-1-11 6.1: tension rod systems to EN 1993-1-1 / 1-8 (gross yield + thread k2·f_u·A_s/γM2)",
                "A_s = " + ("supplier value (--As)" if getattr(a, "As", None) else
                            "ISO 898-1 π/4·(d − 0.9382P)² for an ISO metric thread (give --As for rolled/upset threads)"),
                "f_y, f_u are product values (e.g. Macalloy 460: 460/610 MPa); fatigue: EN 1993-1-9 detail 14 (cat. 50)")
    return min(NRd, a.fitting_Rd or math.inf)


def tension_from_freqs(L, m, pairs, EI=None):
    """T [kN] from measured (n, f_n) pairs of a taut cable with pinned ends.

    f_n² = n²/(4L²)·(T/m) + n⁴π²EI/(4mL⁴)   (taut string + bending, hinged ends)
    With EI given: T_n = 4mL²f_n²/n² − n²π²EI/L² for each mode.
    With EI None and ≥ 2 modes: least squares of y = f_n²/n² on x = n² gives T and EI."""
    per = []
    if EI is not None:
        for n, f in pairs:
            per.append((n, f, (4 * m * L * L * f * f / (n * n) - n * n * math.pi ** 2 * EI / (L * L)) / 1e3))
        return sum(t for *_, t in per) / len(per), EI, per
    if len(pairs) < 2:
        for n, f in pairs:
            per.append((n, f, 4 * m * L * L * f * f / (n * n) / 1e3))
        return per[0][2], 0.0, per
    xs = [n * n for n, _ in pairs]
    ys = [f * f / (n * n) for n, f in pairs]
    xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - xm) ** 2 for x in xs)
    b = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / sxx
    a0 = ym - b * xm
    T = 4 * m * L * L * a0 / 1e3
    EIfit = max(0.0, b * 4 * m * L ** 4 / math.pi ** 2)
    for n, f in pairs:
        per.append((n, f, (4 * m * L * L * f * f / (n * n) - n * n * math.pi ** 2 * EIfit / (L * L)) / 1e3))
    return T, EIfit, per


def irvine_symmetric(k, lam2):
    """k-th symmetric in-plane root ω̄ = ωL/√(H/m) of Irvine's equation tan(ω̄/2) = ω̄/2 − (4/λ²)(ω̄/2)³."""
    a, b = (2 * k - 1) * math.pi / 2, (2 * k + 1) * math.pi / 2
    if lam2 <= 1e-12:
        return 2 * a
    lo, hi = a + 1e-12, b - 1e-12
    g = lambda x: math.tan(x) - x + 4 * x ** 3 / lam2   # noqa: E731  increasing on (a, b)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if g(mid) > 0:
            hi = mid
        else:
            lo = mid
    return lo + hi


def sag_corrected_tension(L, m, pairs, EI=None, EA=None, g=9.81, iters=50):
    """tension_from_freqs with Irvine's sag correction of the symmetric (odd) modes.

    Each odd-mode frequency is mapped to the taut-string frequency it would have without sag,
    f_eq = f·nπ/ω̄(λ²), with λ² = (mgL/T)²·L/(T·L/EA) evaluated at the current T; repeated to convergence."""
    T, EIf, per = tension_from_freqs(L, m, pairs, EI)
    if not EA:
        return T, EIf, per, None
    lam2 = 0.0
    for _ in range(iters):
        w = m * g / 1e3
        lam2 = (w * L / T) ** 2 * L / (T * L / EA)
        eq = [(n, f * n * math.pi / irvine_symmetric((n + 1) // 2, lam2) if n % 2 else f) for n, f in pairs]
        T_new, EIf, per = tension_from_freqs(L, m, eq, EI)
        if abs(T_new - T) < 1e-7 * T:
            T = T_new
            break
        T = T_new
    return T, EIf, per, lam2


def cmd_freq_tension(a):
    pairs = []
    for s in a.f:
        n, f = s.split(":")
        pairs.append((int(n), float(f)))
    T0, _, per0 = tension_from_freqs(a.L, a.m, pairs, a.EI)
    T, EI, per, lam2 = sag_corrected_tension(a.L, a.m, pairs, a.EI, a.EA)
    print(f"Cable force from measured frequencies: L = {a.L} m (free length between fittings), m = {a.m} kg/m")
    for (n, f, t0), (_, _, t) in zip(per0, per):
        print(f"  mode {n}: f = {f:.3f} Hz  ->  T = {t0:.2f} kN (taut string + EI)"
              + (f", {t:.2f} kN sag-corrected" if lam2 is not None and n % 2 else ""))
    src = "given" if a.EI is not None else ("least-squares fit" if len(pairs) > 1 else "neglected (one mode)")
    print(f"  T = {T:.2f} kN   EI = {EI:.3g} N·m² ({src})")
    if lam2 is not None:
        print(f"  Irvine λ² = {lam2:.3f} at this T; symmetric modes corrected with Irvine's equation "
              f"(string-only estimate {T0:.2f} kN, {100 * (T0 / T - 1):+.1f} %)")
    else:
        print("  No --EA: sag not checked. Symmetric modes (1, 3 …) read HIGH on sagging cables; prefer mode 2 "
              "or give --EA.")
    spread = (max(t for *_, t in per) - min(t for *_, t in per)) / T if len(per) > 1 else 0.0
    if spread > 0.05:
        print(f"  WARNING: modes disagree by {spread * 100:.0f} % — check mode numbering, end fixity, L and m "
              "(include sockets/dampers in m and L).")
    assumptions("pinned ends, uniform cable, level chord, T ≈ H (small sag); clamped ends raise f "
                "(the fitted EI absorbs part of it)",
                "f_n² = n²T/(4mL²) + n⁴π²EI/(4mL⁴) (hinged beam-string); symmetric modes corrected with Irvine's "
                "equation when --EA is given (in-plane modes; out-of-plane modes are not affected by sag)",
                "L = free vibrating length between the fittings; m incl. coating/sheath")
    return T


def cmd_stress_turns(a):
    """turnbuckle turns to change a cable force from F1 to F2."""
    if a.F1 <= 0 and a.w:
        raise SystemExit("F1 must be > 0 with --w (the Ernst modulus needs tension)")
    EA = a.EA
    if a.w:
        EA = a.EA / (1 + (a.w * a.L) ** 2 * (a.F1 + a.F2) * a.EA / (24 * a.F1 ** 2 * a.F2 ** 2))
    flex = a.L / EA + (1 / a.k_sup if a.k_sup else 0.0)
    dL = (a.F2 - a.F1) * flex * 1000                           # mm
    lead = a.pitch * (2 if a.thread == "double" else 1)
    turns = dL / lead
    print(f"Stressing: F {a.F1:g} -> {a.F2:g} kN, L = {a.L} m, EA = {a.EA:.0f} kN"
          + (f", self-weight w = {a.w} kN/m -> Ernst secant EA = {EA:.0f} kN" if a.w else ""))
    print(f"  flexibility L/EA{' + 1/k_sup' if a.k_sup else ''} = {flex * 1e3:.4f} mm/kN")
    print(f"  shortening needed ΔL = {dL:.1f} mm")
    print(f"  thread pitch {a.pitch} mm, {a.thread} ({'left+right hand' if a.thread == 'double' else 'one end'}) "
          f"-> lead {lead:g} mm/turn -> {turns:.1f} turns")
    print("  Verify force by measurement (load cell, jack pressure or freq-tension); relieve torsion; lock nuts.")
    assumptions("ΔL = ΔF·(L/EA_sec + 1/k_sup): cable linear-elastic, supports elastic (k_sup) or rigid",
                "with --w: Ernst secant modulus for the sag change between F1 and F2 (level chord, w per length); "
                "validated against the exact elastic catenary in reference/validation.md",
                "lead = pitch (single) or 2·pitch (left/right-hand turnbuckle); thread friction/torsion ignored")
    return turns


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--factors", default=None, help="project code-factor file (give before the sub-command)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("sag")
    s.add_argument("--L", type=float, required=True, help="horizontal span [m]")
    s.add_argument("--h", type=float, default=0.0, help="height of B above A [m]")
    s.add_argument("--w", type=float, required=True, help="load per unit length [kN/m]")
    s.add_argument("--H", type=float)
    s.add_argument("--f", type=float, help="mid-span sag from chord [m]")
    s.add_argument("--S", type=float, help="cable length [m]")
    s.add_argument("--EA", type=float, help="axial stiffness [kN] (optional)")

    s = sp.add_parser("length")
    s.add_argument("--L", type=float, required=True)
    s.add_argument("--h", type=float, default=0.0)
    s.add_argument("--w", type=float, required=True)
    s.add_argument("--H", type=float)
    s.add_argument("--f", type=float)
    s.add_argument("--EA", type=float, required=True)
    s.add_argument("--alpha", type=float, default=None, help="1/K (register: carbon 12e-6; stainless 16e-6)")
    s.add_argument("--T-install", type=float, default=20.0)
    s.add_argument("--T-ref", type=float, default=20.0)
    s.add_argument("--fittings", type=float, default=0.0, help="total fitting length both ends [mm]")
    s.add_argument("--creep", action="store_true",
                   help="subtract the EN 1993-1-11 3.2.2(3) creep allowance (register, 0.15 mm/m) from the cut length")

    s = sp.add_parser("edge")
    s.add_argument("--chord", type=float, required=True)
    s.add_argument("--sag", type=float, required=True)
    s.add_argument("--n", type=float, required=True, help="membrane stress normal to cable [kN/m]")

    s = sp.add_parser("resist")
    s.add_argument("--Fmin", type=float, required=True, help="minimum breaking force of the rope [kN]")
    s.add_argument("--ke", type=float, default=None, help="termination loss factor (1.0 socket, 0.9 swaged)")
    s.add_argument("--termination", choices=sorted(KE_KEY), default=None, help="k_e from the register")
    s.add_argument("--sensitivity", action="store_true", help="re-check over the range of [U] factors")
    s.add_argument("--gammaR", type=float, default=None, help="EN 1993-1-11 Table 6.2 / NA (register default)")
    s.add_argument("--Fk", type=float, default=None, help="0.2%% proof force (bars) [kN]")
    s.add_argument("--FEd", type=float, required=True, help="ULS design force [kN]")
    s.add_argument("--Fser", type=float, default=None, help="characteristic (SLS) force [kN]")
    s.add_argument("--fsls", type=float, default=None, help="SLS limit as fraction of F_uk (register default)")
    s.add_argument("--bending-checked", action="store_true",
                   help="fatigue incl. bending stresses is verified -> f_SLS = 0.50 (EN 1993-1-11 Table 7.2)")
    s.add_argument("--Nf", type=float, default=1.0, help="ASCE 19 fitting factor")
    s.add_argument("--asce", type=float, default=None, help="ASCE 19 factor on T (register default 2.2)")
    s.add_argument("--T-asce", type=float, default=None, help="unfactored ASCE combination tension [kN]")
    s.add_argument("--Fmin-force", type=float, default=None, help="min. cable force in any combination [kN]")

    s = sp.add_parser("irvine")
    s.add_argument("--L", type=float, required=True)
    s.add_argument("--w0", type=float, required=True)
    s.add_argument("--H0", type=float, required=True)
    s.add_argument("--w1", type=float, required=True)
    s.add_argument("--EA", type=float, required=True)
    s.add_argument("--dT", type=float, default=0.0)
    s.add_argument("--alpha", type=float, default=None)

    s = sp.add_parser("clamp")
    s.add_argument("--dT", type=float, required=True, help="force the clamp must hold along the cable [kN]")
    s.add_argument("--nb", type=int, default=2, help="number of clamp bolts")
    s.add_argument("--bolt-d", type=float, default=16.0)
    s.add_argument("--grade", default="8.8", choices=["8.8", "10.9", "A4-70", "A4-80"])
    s.add_argument("--surfaces", type=int, default=2, help="friction surfaces (clamp halves on the cable)")
    s.add_argument("--Fp", type=float, default=None, help="bolt preload per bolt [kN] (else 0.7·f_ub·A_s)")
    s.add_argument("--mu", type=float, default=None, help="friction coefficient from a slip test (else register)")
    s.add_argument("--retained", type=float, default=None, help="retained preload fraction (else register)")
    s.add_argument("--Fperp", type=float, default=0.0, help="external design load pressing the cable into the clamp [kN]")
    s.add_argument("--sensitivity", action="store_true")

    s = sp.add_parser("saddle")
    s.add_argument("--T", type=float, required=True, help="cable force [kN]")
    s.add_argument("--R", type=float, required=True, help="saddle radius [m]")
    s.add_argument("--d", type=float, required=True, help="cable diameter [mm]")
    s.add_argument("--type", choices=["FLC", "OSS"], default="OSS")
    s.add_argument("--delta", type=float, default=5.0, help="outer wire diameter [mm]")
    s.add_argument("--E", type=float, default=160.0, help="cable modulus [kN/mm²]")
    s.add_argument("--lined", action="store_true",
                   help="soft metal / zinc spray ≥ 1 mm bedding (EN 1993-1-11 6.3.1(3) 20d, Table 6.4 cushioned)")
    s.add_argument("--T2", type=float, default=None, help="cable force on the other side of the saddle [kN] (slip)")
    s.add_argument("--wrap", type=float, default=None, help="deviation angle of the cable over the saddle [deg]")
    s.add_argument("--Fr", type=float, default=None, help="radial clamping force of saddle clamps [kN]")
    s.add_argument("--k-clamp", type=float, default=None, help="k of eq. (6.7) (register 2.0 full friction, else 1.0)")
    s.add_argument("--L2", type=float, default=None, help="contact length between tangent points [mm] (else R·α)")
    s.add_argument("--dprime", type=float, default=None, help="contact width d' [mm], 0.6d ≤ d' ≤ d (default d)")
    s.add_argument("--Fuk", type=float, default=None, help="characteristic breaking strength -> saddle force k·F_uk")
    s.add_argument("--sensitivity", action="store_true")

    s = sp.add_parser("freq")
    s.add_argument("--L", type=float, required=True)
    s.add_argument("--T", type=float, required=True, help="tension [kN]")
    s.add_argument("--m", type=float, required=True, help="mass [kg/m]")
    s.add_argument("--modes", type=int, default=3)

    s = sp.add_parser("freq-tension")
    s.add_argument("--L", type=float, required=True, help="free vibrating length [m]")
    s.add_argument("--m", type=float, required=True, help="mass incl. coating [kg/m]")
    s.add_argument("--f", action="append", required=True, help="n:f_n measured (mode number:Hz), repeatable")
    s.add_argument("--EI", type=float, default=None, help="bending stiffness [N·m²] (else fitted from ≥ 2 modes)")
    s.add_argument("--EA", type=float, default=None, help="axial stiffness [kN] for the sag (λ²) check")

    s = sp.add_parser("rod")
    s.add_argument("--d", type=float, required=True, help="thread nominal diameter [mm]")
    s.add_argument("--pitch", type=float, default=None, help="thread pitch [mm] (default ISO coarse, 6 above M64)")
    s.add_argument("--d-shank", type=float, default=None, help="shank diameter if different (upset ends) [mm]")
    s.add_argument("--As", type=float, default=None, help="thread tensile stress area from the supplier [mm²]")
    s.add_argument("--fy", type=float, required=True, help="yield / 0.2%% proof strength [MPa] (product data)")
    s.add_argument("--fu", type=float, required=True, help="tensile strength [MPa] (product data)")
    s.add_argument("--FEd", type=float, required=True)
    s.add_argument("--fitting-Rd", type=float, default=None, help="fork/turnbuckle design resistance [kN]")

    s = sp.add_parser("stress-turns")
    s.add_argument("--L", type=float, required=True, help="cable length [m]")
    s.add_argument("--EA", type=float, required=True, help="[kN]")
    s.add_argument("--F1", type=float, required=True, help="current force [kN]")
    s.add_argument("--F2", type=float, required=True, help="target force [kN]")
    s.add_argument("--pitch", type=float, required=True, help="thread pitch [mm]")
    s.add_argument("--thread", choices=["single", "double"], default="double",
                   help="double = turnbuckle with left+right threads (lead 2·pitch)")
    s.add_argument("--k-sup", type=float, default=None, help="support/anchor stiffness along the cable [kN/m]")
    s.add_argument("--w", type=float, default=0.0, help="self-weight [kN/m] (Ernst sag correction)")

    a = ap.parse_args(argv)
    fill_factors(a)
    return {"sag": cmd_sag, "length": cmd_length, "edge": cmd_edge, "resist": cmd_resist,
            "irvine": cmd_irvine, "freq": cmd_freq, "clamp": cmd_clamp, "saddle": cmd_saddle,
            "freq-tension": cmd_freq_tension, "rod": cmd_rod, "stress-turns": cmd_stress_turns}[a.cmd](a)


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
