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

Code values: γR=1.0, k_e (1.0 sockets / 0.9 swaged) and the ASCE 2.2 factor
are defaults taken from EAD 200001-00-0602 / ETAs / ASCE 19 practice — always
confirm against the edition of the standard and National Annex in force
(EN 1993-1-11:2026 has replaced the 2006 edition in some countries).
"""
from __future__ import annotations

import argparse
import math
import sys


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
    S = math.hypot(L, h) + 8 * f * f / (3 * math.hypot(L, h))  # chord approx
    return {"H": H, "f": f, "V_low": VA, "V_high": VB, "T_low": TA, "T_high": TB, "Tmax": max(TA, TB),
            "length": S, "sag_ratio": n}


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
    print(f"  parabola check (w per horizontal m): f = {p['f']:.4f} m, Tmax = {p['Tmax']:.3f} kN, "
          f"S = {p['length']:.4f} m")
    if a.EA:
        st = c.stretch(a.EA)
        print(f"  elastic stretch ∫T/EA ds = {st * 1000:.2f} mm  -> unstressed length {c.length - st:.4f} m")
    return c


def cmd_length(a):
    H = a.H if a.H is not None else solve_H(a.L, a.h, a.w, a.f, "f")
    c = Catenary(a.L, a.h, a.w, H)
    S = c.length
    st = c.stretch(a.EA)
    S0_inst = S - st
    S0_ref = S0_inst / (1 + a.alpha * (a.T_install - a.T_ref))
    print(f"Stressed geometric length S          = {S:.4f} m  (H = {H:.2f} kN, Tmax = {c.T(0 if c.T(0) > c.T(a.L) else a.L):.2f} kN)")
    print(f"Elastic stretch ∫T/EA ds             = {st * 1000:.2f} mm  (EA = {a.EA:.0f} kN)")
    print(f"Unstressed length at {a.T_install:>5.1f} °C        = {S0_inst:.4f} m")
    print(f"Unstressed length at ref {a.T_ref:>5.1f} °C    = {S0_ref:.4f} m   (alpha = {a.alpha:.1e}/K)")
    if a.fittings:
        print(f"Cable length excl. fittings          = {S0_ref - a.fittings / 1000:.4f} m "
              f"(pin-to-pin minus {a.fittings:.0f} mm of fittings)")
    print("Note: specify on the cable schedule: length is pin-to-pin, unstressed (or under the "
          "stated reference load), at the reference temperature; prestretched cable.")
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
    return T


def cmd_resist(a):
    Fuk = a.Fmin * a.ke
    FRd_en = Fuk / (1.5 * a.gammaR)
    if a.Fk:
        FRd_en = min(FRd_en, a.Fk / a.gammaR)
    print("EN 1993-1-11 (6.2) — group B/C tension component")
    print(f"  F_min = {a.Fmin:.1f} kN  k_e = {a.ke:.2f}  ->  F_uk = {Fuk:.1f} kN")
    print(f"  F_Rd = F_uk/(1.5·γR) = {Fuk / (1.5 * a.gammaR):.1f} kN   (γR = {a.gammaR})"
          + (f";  F_k/γR = {a.Fk / a.gammaR:.1f} kN" if a.Fk else ""))
    rows = [("EN ULS", a.FEd, FRd_en)]
    if a.Fser is not None:
        lim = a.fsls * Fuk
        rows.append((f"EN SLS (≤{a.fsls:.2f}·F_uk, check NA Table 7.2)", a.Fser, lim))
    Sd = a.Fmin * a.Nf
    rows.append((f"ASCE 19 (S_d = S_n·N_f ≥ {a.asce:.1f}·T)", a.asce * (a.T_asce or a.FEd / 1.4), Sd))
    for name, dem, cap in rows:
        print(f"  {name:<44} demand {dem:9.1f}  capacity {cap:9.1f}  util {dem / cap:5.2f}"
              + ("  <-- FAIL" if dem > cap else ""))
    if a.Fmin_force is not None:
        print(f"  No-slack check: minimum force under all combinations = {a.Fmin_force:.1f} kN "
              + ("OK (>0)" if a.Fmin_force > 0 else "SLACK -> increase prestress / revise geometry"))
    return FRd_en


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
    return H


def cmd_freq(a):
    print(f"Taut cable L={a.L} m, T={a.T} kN, m={a.m} kg/m")
    c = math.sqrt(a.T * 1000 / a.m)
    for n in range(1, a.modes + 1):
        print(f"  mode {n}: f = {n * c / (2 * a.L):.2f} Hz")
    print("Keep f1 clear of vortex-shedding / rain-wind ranges; add dampers or helical fillets on long stays.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
    s.add_argument("--alpha", type=float, default=12e-6, help="1/K (12e-6 carbon, 16e-6 stainless)")
    s.add_argument("--T-install", type=float, default=20.0)
    s.add_argument("--T-ref", type=float, default=20.0)
    s.add_argument("--fittings", type=float, default=0.0, help="total fitting length both ends [mm]")

    s = sp.add_parser("edge")
    s.add_argument("--chord", type=float, required=True)
    s.add_argument("--sag", type=float, required=True)
    s.add_argument("--n", type=float, required=True, help="membrane stress normal to cable [kN/m]")

    s = sp.add_parser("resist")
    s.add_argument("--Fmin", type=float, required=True, help="minimum breaking force of the rope [kN]")
    s.add_argument("--ke", type=float, default=1.0, help="termination loss factor (1.0 socket, 0.9 swaged)")
    s.add_argument("--gammaR", type=float, default=1.0, help="EN 1993-1-11 Table 6.2 / NA (min 1.0 per EAD)")
    s.add_argument("--Fk", type=float, default=None, help="0.2%% proof force (bars) [kN]")
    s.add_argument("--FEd", type=float, required=True, help="ULS design force [kN]")
    s.add_argument("--Fser", type=float, default=None, help="characteristic (SLS) force [kN]")
    s.add_argument("--fsls", type=float, default=0.5, help="SLS limit as fraction of F_uk (verify NA)")
    s.add_argument("--Nf", type=float, default=1.0, help="ASCE 19 fitting factor")
    s.add_argument("--asce", type=float, default=2.2, help="ASCE 19 factor on T (2.2)")
    s.add_argument("--T-asce", type=float, default=None, help="unfactored ASCE combination tension [kN]")
    s.add_argument("--Fmin-force", type=float, default=None, help="min. cable force in any combination [kN]")

    s = sp.add_parser("irvine")
    s.add_argument("--L", type=float, required=True)
    s.add_argument("--w0", type=float, required=True)
    s.add_argument("--H0", type=float, required=True)
    s.add_argument("--w1", type=float, required=True)
    s.add_argument("--EA", type=float, required=True)
    s.add_argument("--dT", type=float, default=0.0)
    s.add_argument("--alpha", type=float, default=12e-6)

    s = sp.add_parser("freq")
    s.add_argument("--L", type=float, required=True)
    s.add_argument("--T", type=float, required=True, help="tension [kN]")
    s.add_argument("--m", type=float, required=True, help="mass [kg/m]")
    s.add_argument("--modes", type=int, default=3)

    a = ap.parse_args(argv)
    return {"sag": cmd_sag, "length": cmd_length, "edge": cmd_edge, "resist": cmd_resist,
            "irvine": cmd_irvine, "freq": cmd_freq}[a.cmd](a)


if __name__ == "__main__":
    main(sys.argv[1:])
