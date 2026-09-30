#!/usr/bin/env python3
"""Steel mast / strut check — circular hollow section (CHS) to EN 1993-1-1.

Masts in tensile structures are usually pin-ended (hinged base, cables at the
head) and therefore predominantly axially loaded; bending comes from eccentric
cable connections, wind on the mast and base fixity if any.

Checks
  * cross-section class (Table 5.2: d/t <= 50e2 / 70e2 / 90e2)
  * section resistance N + M (6.2.9, CHS class 1-2 via plastic interaction)
  * flexural buckling 6.3.1 (curve a hot-finished, curve c cold-formed)
  * member N + M interaction 6.3.3, Annex B (method 2) for CHS (no LTB)

Optional: geometric-length check of the mast base-to-head for fabrication and
the "flying mast" warning.

Units: kN, kNm, m, mm, MPa.

Example: 7.5 m hinged mast, CHS 219.1x8 S355 hot-finished, N=420 kN, M=12 kNm
  python3 mast_check.py --D 219.1 --t 8 --L 7.5 --N 420 --M 12 --fy 355
"""
from __future__ import annotations

import argparse
import math
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tensile-structures", "scripts"))
import factors as F  # noqa: E402  central code-factor register (V/C/U tagged)

CURVES = {"a0": 0.13, "a": 0.21, "b": 0.34, "c": 0.49, "d": 0.76}


def chs(D, t):
    d = D - 2 * t
    A = math.pi / 4 * (D ** 2 - d ** 2)
    I = math.pi / 64 * (D ** 4 - d ** 4)
    Wel = 2 * I / D
    Wpl = (D ** 3 - d ** 3) / 6
    i = math.sqrt(I / A)
    return A, I, Wel, Wpl, i


def check(D, t, L, N, M, fy, k=1.0, curve=None, cold=False, psi=0.0, E=None, gM0=None, gM1=None):
    E = F.get("steel.E") if E is None else E
    gM0 = F.get("steel.gM0") if gM0 is None else gM0
    gM1 = F.get("steel.gM1") if gM1 is None else gM1
    eps = math.sqrt(235 / fy)
    r = D / t
    cls = 1 if r <= 50 * eps ** 2 else 2 if r <= 70 * eps ** 2 else 3 if r <= 90 * eps ** 2 else 4
    A, I, Wel, Wpl, i = chs(D, t)
    W = Wpl if cls <= 2 else Wel
    curve = curve or ("c" if cold else "a")
    alpha = CURVES[curve]
    Lcr = k * L * 1000
    Ncr = math.pi ** 2 * E * I / Lcr ** 2
    NRk = A * fy
    lam = math.sqrt(NRk / Ncr)
    phi = 0.5 * (1 + alpha * (lam - 0.2) + lam ** 2)
    chi = min(1.0, 1 / (phi + math.sqrt(phi ** 2 - lam ** 2)))
    NbRd = chi * NRk / gM1
    MRk = W * fy
    NEd, MEd = N * 1e3, M * 1e6
    # section (CHS plastic interaction, 6.2.9.1(6) M_N = M_pl (1 - n^1.7))
    n = NEd / (NRk / gM0)
    MNRd = MRk / gM0 * (1 - n ** 1.7) if cls <= 2 else MRk / gM0 * (1 - n)
    sec = MEd / MNRd if MNRd > 0 else math.inf
    # member, Annex B, Cm for linear moment ratio psi
    Cm = max(0.4, 0.6 + 0.4 * psi)
    nb = NEd / (chi * NRk / gM1)
    kyy = Cm * (1 + min(lam - 0.2, 0.8) * nb) if cls <= 2 else Cm * (1 + min(0.6 * lam, 0.6) * nb)
    memb = nb + kyy * MEd / (MRk / gM1)
    return {"class": cls, "D/t": r, "A_mm2": A, "I_mm4": I, "i_mm": i, "slenderness_L/i": Lcr / i,
            "Ncr_kN": Ncr / 1e3, "lambda_bar": lam, "curve": curve, "chi": chi, "NbRd_kN": NbRd / 1e3,
            "MRd_kNm": MRk / 1e6, "u_section": max(n, sec) if MEd else n, "u_buckling": nb,
            "kyy": kyy, "u_member_NM": memb, "mass_kg_m": A * 7.85e-3}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--D", type=float, required=True, help="outside diameter [mm]")
    ap.add_argument("--t", type=float, required=True, help="wall thickness [mm]")
    ap.add_argument("--L", type=float, required=True, help="system length [m]")
    ap.add_argument("--N", type=float, required=True, help="design compression [kN]")
    ap.add_argument("--M", type=float, default=0.0, help="max design moment [kNm]")
    ap.add_argument("--psi", type=float, default=0.0, help="end-moment ratio for Cm (0 = pinned end, moment at head)")
    ap.add_argument("--k", type=float, default=1.0, help="effective length factor (1.0 pinned-pinned, 2.0 cantilever)")
    ap.add_argument("--fy", type=float, default=355.0)
    ap.add_argument("--cold", action="store_true", help="cold-formed CHS (curve c)")
    ap.add_argument("--curve", choices=list(CURVES), default=None)
    ap.add_argument("--factors", default=None, help="project code-factor file")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    print(f"Partial factors: {F.tag('steel.gM0')}, {F.tag('steel.gM1')}")
    r = check(a.D, a.t, a.L, a.N, a.M, a.fy, a.k, a.curve, a.cold, a.psi)
    print(f"CHS {a.D}x{a.t}  S{int(a.fy)}  L={a.L} m  k={a.k}  N_Ed={a.N} kN  M_Ed={a.M} kNm")
    for key, v in r.items():
        print(f"  {key:<16} {v:.4g}" if isinstance(v, float) else f"  {key:<16} {v}")
    worst = max(r["u_section"], r["u_buckling"], r["u_member_NM"])
    print(f"Governing utilisation {worst:.2f} -> {'OK' if worst <= 1 else 'NOT OK'}")
    if r["class"] == 4:
        print("WARNING: class 4 section – effective properties (EN 1993-1-6 / 1-5) required")
    if r["slenderness_L/i"] > 180:
        print("NOTE: slenderness > 180 – check wind-induced vibration and erection handling")
    return r


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
