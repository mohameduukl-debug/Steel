#!/usr/bin/env python3
"""Membrane stress check (warp & weft, fabric & seam) with selectable design basis.

Methods (--method)
------------------
  factor   permissible stress / global stress factor (DEFAULT): allowable = f / SF,
           SF 4.0 short-term (wind), 5.0 long-term (prestress, snow) [V: ASCE 55-10 industry practice]
  fm       FM Global DS 1-59 (2021) Table 2.2.6.1 on NEW-fabric strength: P+D 8.0; P+D+(L|S|R|W|T) 5.0 [V]
  japan    MLIT Notification 666 (Japan) 第六 一: Fm/8 long-term, Fm/4 short-term (Fm/5 when the membrane
           is folded); joints narrower than 40 mm (75 mm for glass/PTFE): Fm/10 and Fm/5 [V, primary text]
  partial  German A-factor practice (JRC132615 Code Review 20, DIN 4134 / Minte):
              n_Rd = f_k / (γM · A-factors of the design situation)
              long-term (prestress, dead, snow, live)  γM·A0·A1·A2·A3
              short-term cold (wind, installation)     γM·A0·A2          ("winter storm")
              short-term warm (temperature)            γM·A0·A2·A3       ("summer storm")
           γM 1.4 fabric, 1.5 connections (seam rows). Input = DESIGN stress (factored loads, γf).
  ts19102  CEN/TS 19102 format  f_d = f_k,23 / (γM·kbiax·kage·kdur·ktemp·ksize), prCEN values for PES/PVC
           from the JRC 2025 worked example (γM0 1.4 fabric, γM2 1.5 joints):
              prestress/dead  kdur,P·ktemp,70 ; snow/live  kdur,M (--ts-snow L: kdur,L, > 1000 m altitude)
              wind/installation  -- ; temperature  ktemp,70.     Input = DESIGN stress (factored loads).
  french   French recommendations (JRC132615 Code Review 21): TD = kq·ke·Trm/γt, γt 4 (medium) / 4.5 (heavy
           pollution), ke = (50/S)^(1/15) for S > 50 m², kq = 1 (0.8 without certified quality control);
           corner/attachment check TD = kq·neff·Trm/γtloc with γtloc = 5

Strength basis: factor/fm/french use the datasheet (mean / nominal) strip strength; partial/ts19102 need the
characteristic 5 % value f_k: taken from the library (fk_w/fk_f) or from --vx (f_k = f·(1 − 1.64·Vx));
japan uses Fm, the ministerially designated standard strength of the product.

Always checked: fabric warp & weft and seams (strength × seam efficiency; for 'japan' the joint class is in the
divisor); optional no-slack (--nmin) and prestress level vs. strength.

Extra checks
  --envelope        every case of a run_cases.py envelope (warp/weft max)
  --tear A N        slit-tear test scaled to the design defect, n_c ∝ 1/√a (LEFM), allowable n_c/tear_factor [U]
  --curvature       Laplace hand sizing n1/R1 + n2/R2 = p
  --flutter A B     natural frequencies of a prestressed flat panel A × B (A along warp), exact rectangular
                    membrane f_mn = ½·√((n_w·(m/A)² + n_f·(n/B)²)/m_eff); m_eff = fabric + added air mass computed
                    per panel and mode (Rayleigh integral, baffled panel); --modes K lists K modes
  --corner R THETA R0   corner force fanning radially n(r) = R/(θ·r) with published reinforcement factors n_eff
  ETFE foil         σ = n/t against f_y10,23/(γM·k) of the design situation (JRC Eurocode Outlook 44)
  --sensitivity     re-runs checks over the range of every factor that carries one ([U] or published spread)

Examples
  python3 membrane_check.py --list
  python3 membrane_check.py --material PVC-III --nw 18.5 --nf 14.2 --case wind
  python3 membrane_check.py --material Chukoh-FGT-800 --nw 31 --nf 22 --case snow --method fm --fm-combo P+D+S
  python3 membrane_check.py --fw 172 --ff 168 --vx 0.12 --nw 35.55 --nf 12.75 --case snow --method ts19102
  python3 membrane_check.py --material PVC-III --nw 9 --nf 8 --case snow --method partial --sensitivity
  python3 membrane_check.py --material Sattler-Atlas-760-IV --nw 38.1 --nf 40.2 --case wind --method french \
          --area 600 --ke 0.85
  python3 membrane_check.py --material PVC-III --prestress 2 2 --flutter 6 4 --f-target 2.0 --modes 4
  python3 membrane_check.py --material PVC-III --case wind --corner 25 90 0.4 --layers 2
  python3 membrane_check.py --material ETFE-250um --nw 2.5 --case snow
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "reference", "materials.json")

CASES = {"prestress": "long", "dead": "long", "snow": "long", "live": "long",
         "wind": "short", "temperature": "short", "installation": "short"}
# design situation used by the partial-factor formats (German A-factors, CEN/TS 19102, ETFE Outlook 44)
SITUATION = {"prestress": "permanent", "dead": "permanent", "snow": "long", "live": "long",
             "wind": "short", "installation": "short", "temperature": "warm"}
METHODS = ["factor", "fm", "japan", "partial", "ts19102", "french"]

sys.path.insert(0, os.path.join(HERE, "..", "..", "tensile-structures", "scripts"))
import factors as F  # noqa: E402  central code-factor register (V/C/U tagged)


def load_lib():
    with open(LIB) as fh:
        return json.load(fh)


# ----------------------------------------------------------------------------------------------- strengths
def char_strength(f_mean, vx, kn=None):
    """characteristic 5 % strength f_k = f_mean·(1 − kn·Vx) (EN 1990 Annex D, Vx known)."""
    kn = F.get("membrane.fractile_kn") if kn is None else kn
    return f_mean * (1.0 - kn * vx)


def _partial_table(family):
    tab = F.get("membrane.partial")
    fam = family if family in tab and isinstance(tab[family], dict) else "other"
    return fam, tab[fam]


def factor_key(method, case, family=None):
    """register key of the factor (or factor table) that governs allowable() for this method/case."""
    dur = CASES[case]
    if method == "partial":
        fam, p = _partial_table(family or "other")
        return f"membrane.partial.{fam}" if "range" in p else "membrane.partial"
    return {"factor": f"membrane.stress_factor_{dur}", "fm": None,
            "japan": f"membrane.japan_{dur}_divisor", "ts19102": "membrane.ts19102",
            "french": "membrane.french_gamma_t"}[method]


def french_ke(area=None, ke=None):
    """French scale factor ke = 1 (S <= 50 m²) or (50/S)^(1/15)."""
    if ke is not None:
        return ke
    if area is None:
        return 1.0
    s0 = F.get("membrane.french_ke_area_ref")
    return 1.0 if area <= s0 else (s0 / area) ** (1.0 / 15.0)


def allowable(f, method, case, family, sf_short=None, sf_long=None, fm_combo="P+D+W", override=None, opts=None):
    """allowable membrane stress [kN/m] for strip strength f [kN/m]; factors not given come from the register.

    override = {register key: value} replaces a register value (used by --sensitivity; for tables such as
    'membrane.partial' the value is a scale on the factor product).
    opts: joint (bool, seam/connection row), japan_joint ('wide'|'narrow'), folded (bool), ts_snow ('M'|'L'),
          area (m², french), ke, kq, pollution ('medium'|'heavy')."""
    ov = override or {}
    o = opts or {}
    dur = CASES[case]
    sit = SITUATION[case]
    if method == "factor":
        key = "membrane.stress_factor_long" if dur == "long" else "membrane.stress_factor_short"
        given = sf_long if dur == "long" else sf_short
        sf = given if given is not None else ov.get(key, F.get(key))
        st = "user" if given is not None else F.status(key)
        return f / sf, f"SF = {sf:g} ({dur}-term) [{st}]"
    if method == "fm":
        key = "membrane.fm159_PD" if fm_combo == "P+D" else "membrane.fm159_other"
        sf = F.get(key)
        return f / sf, f"FM DS 1-59 SF = {sf:g} for {fm_combo} [{F.status(key)}]"
    if method == "japan":
        narrow = o.get("japan_joint", "wide") == "narrow"
        if dur == "long":
            key = "membrane.japan_long_divisor_narrow" if narrow else "membrane.japan_long_divisor"
        elif narrow:
            key = "membrane.japan_short_divisor_narrow"
        else:
            key = "membrane.japan_short_divisor_folded" if o.get("folded") else "membrane.japan_short_divisor"
        k = ov.get(key, F.get(key))
        return f / k, (f"Fm/{k:g} ({dur}-term, joint {'narrow' if narrow else 'wide/none'}"
                       f"{', folded' if o.get('folded') and dur == 'short' else ''}) [{F.status(key)}]")
    if method == "partial":
        fam, p = _partial_table(family)
        sub = f"membrane.partial.{fam}"
        st = p.get("status", F.status("membrane.partial"))
        A1 = p["A1_long"] if sit in ("permanent", "long") else p.get("A1_short", 1.0)
        A3 = p["A3"] if sit in ("permanent", "long", "warm") else 1.0
        gM = p.get("gM_joint", p["gM"]) if o.get("joint") else p["gM"]
        scale = ov.get(sub, ov.get("membrane.partial", 1.0))
        k = gM * p["A0"] * A1 * p["A2"] * A3 * scale
        note = "replace with tested / NA values" if st == "U" else "JRC132615 Code Review 20 practice values"
        return f / k, (f"{sit}: γM {gM} × A0 {p['A0']} × A1 {A1} × A2 {p['A2']} × A3 {A3} = {k:.2f} "
                       f"[{st}, {fam}] ({note})")
    if method == "ts19102":
        tab = F.get("membrane.ts19102")
        if family not in tab or not isinstance(tab[family], dict):
            raise ValueError(f"no CEN/TS 19102 modification factors for '{family}' in the register: add them "
                             "(membrane.ts19102.<family>) in a project factor file (--factors)")
        p = tab[family]
        gM = p["gM2"] if o.get("joint") else p["gM0"]
        if sit == "permanent":
            ks, kname = p["kdur_P"] * p["ktemp70"], f"kdur,P {p['kdur_P']} × ktemp,70 {p['ktemp70']}"
        elif sit == "long":
            kd = p["kdur_L"] if o.get("ts_snow", "M") == "L" else p["kdur_M"]
            ks, kname = kd, f"kdur,{'L' if o.get('ts_snow', 'M') == 'L' else 'M'} {kd}"
        elif sit == "warm":
            ks, kname = p["ktemp70"], f"ktemp,70 {p['ktemp70']}"
        else:
            ks, kname = 1.0, "no kdur/ktemp (short-term)"
        k = gM * p["kbiax"] * p["kage"] * ks * p["ksize"] * ov.get("membrane.ts19102", 1.0)
        return f / k, (f"{sit}: γM{'2' if o.get('joint') else '0'} {gM} × kbiax {p['kbiax']} × kage {p['kage']} × "
                       f"{kname} × ksize {p['ksize']} = {k:.2f} [{F.status('membrane.ts19102')}]")
    if method == "french":
        gt = F.get("membrane.french_gamma_t")[o.get("pollution", "medium")]
        gt = ov.get("membrane.french_gamma_t", 1.0) * gt
        ke = french_ke(o.get("area"), o.get("ke"))
        kq = o.get("kq", 1.0)
        return kq * ke * f / gt, (f"TD = kq {kq:g} × ke {ke:.3f} × Trm / γt {gt:g} "
                                  f"({o.get('pollution', 'medium')} pollution) [{F.status('membrane.french_gamma_t')}]")
    raise ValueError(method)


def _has_range(key):
    return key is not None and F.frange(key) is not None


def env_case(r):
    dur = r.get("duration", "short")
    case = "wind" if dur == "short" else "snow"
    if r["case"].upper() in ("PS", "PRESTRESS"):
        case = "prestress"
    return case, ("P+D" if case == "prestress" else ("P+D+W" if case == "wind" else "P+D+S"))


def _seam_eff(method, seam_eff):
    """the Japanese table already sets the divisor by joint class -> no extra seam efficiency."""
    return 1.0 if method == "japan" else seam_eff


def envelope_utils(env, fw, ff, method, family, seam_eff, sf_short=None, sf_long=None, override=None, opts=None):
    """[(row, dur, nw, nf, u_fabric, u_seam)] for every case of a run_cases.py envelope."""
    out = []
    se = _seam_eff(method, seam_eff)
    for r in env["summary"]:
        case, combo = env_case(r)
        nw_, nf_ = r.get("warp_max") or 0.0, r.get("weft_max") or 0.0
        aw, _ = allowable(fw, method, case, family, sf_short, sf_long, combo, override, opts)
        af, _ = allowable(ff, method, case, family, sf_short, sf_long, combo, override, opts)
        uf = max(nw_ / aw, nf_ / af)
        js = dict(opts or {}, joint=True)
        aws, _ = allowable(fw * se, method, case, family, sf_short, sf_long, combo, override, js)
        afs, _ = allowable(ff * se, method, case, family, sf_short, sf_long, combo, override, js)
        out.append((r, r.get("duration", "short"), nw_, nf_, uf, max(nw_ / aws, nf_ / afs)))
    return out


def point_utils(nw, nf, fw, ff, method, case, family, seam_eff, seam_dir="both", sf_short=None, sf_long=None,
                fm_combo="P+D+W", override=None, opts=None):
    """[(item, n, n_allowable, basis)] for the single-point check (fabric + seams)."""
    rows = []
    se = _seam_eff(method, seam_eff)
    for name, n, f in (("warp", nw, fw), ("weft", nf, ff)):
        if n is None:
            continue
        al, basis = allowable(f, method, case, family, sf_short, sf_long, fm_combo, override, opts)
        rows.append((f"fabric {name}", n, al, basis))
        if seam_dir in (name, "both"):
            al_s, basis_s = allowable(f * se, method, case, family, sf_short, sf_long, fm_combo, override,
                                      dict(opts or {}, joint=True))
            tag = "joint in divisor" if method == "japan" else f"eff {se:g}"
            rows.append((f"seam (stress {name}, {tag})", n, al_s, basis_s))
    return rows


def prestress_minimum(family, f_short):
    """published minimum prestress [kN/m] for the family: (value, text) or (None, text).

    TensiNet rule (quoted in JRC132615): PES/PVC >= 1.3 % of the short-term strength; glass/PTFE >= 2.5 % but
    >= 2.0 kN/m; French recommendations >= 1.5 kN/m for all structural membranes."""
    t = F.get("membrane.prestress_min")
    fr = t["abs_french_kN_m"]
    if family == "PES/PVC":
        v = t["pct_PES/PVC"] / 100 * f_short
        return max(v, fr), f"TensiNet {t['pct_PES/PVC']} % of strength = {v:.2f}; French >= {fr:g} kN/m"
    if family == "glass/PTFE":
        v = max(t["pct_glass/PTFE"] / 100 * f_short, t["abs_glass/PTFE_kN_m"])
        return max(v, fr), (f"TensiNet {t['pct_glass/PTFE']} % of strength, >= {t['abs_glass/PTFE_kN_m']:g} kN/m "
                            f"= {v:.2f}; French >= {fr:g} kN/m")
    return fr, f"French recommendations >= {fr:g} kN/m (no TensiNet rule for {family})"


# ----------------------------------------------------------------------------------------------- ETFE
def etfe_design_strength(case, gamma=None, fy=None, single_unregulated=False):
    """design strength [MPa] of ETFE foil for the design situation (JRC132615 Eurocode Outlook 44)."""
    k = F.get("membrane.etfe_k")
    g = F.get("membrane.etfe_gamma") if gamma is None else gamma
    fy = k["fy10_23_MPa"] if fy is None else fy
    sit = {"prestress": "PM", "dead": "PM", "snow": "LTL", "live": "LTR", "wind": "ST", "installation": "ST",
           "temperature": "STH"}[case]
    kperm = k["kperm_single_unregulated"] if single_unregulated else k["kperm"]
    kk, txt = {"PM": (k["kage"] * kperm, f"kage {k['kage']} × kperm {kperm} (permanent)"),
               "LTL": (k["kage"] * k["klong"] * k["ktemp0"],
                       f"kage {k['kage']} × klong {k['klong']} × ktemp0 {k['ktemp0']} (long-term, 0 °C)"),
               "LTR": (k["kage"] * k["klong"], f"kage {k['kage']} × klong {k['klong']} (long-term, 23 °C)"),
               "ST": (k["kage"], f"kage {k['kage']} (short-term)"),
               "STH": (k["kage"] * k["ktemp50"], f"kage {k['kage']} × ktemp50 {k['ktemp50']} (short-term, 50 °C)")}[sit]
    return fy / (g * kk), f"f_y10,23 {fy:g} / (γM {g:g} × {txt}) [{F.status('membrane.etfe_k')}]"


# ----------------------------------------------------------------------------------------------- dynamics
def mass_kg_m2(m):
    """fabric mass [kg/m²] from a library entry ('weight_gm2' may be a range string -> mid value)."""
    w = m.get("weight_gm2")
    if w is None:
        return None
    if isinstance(w, str):
        lo, hi = (float(x) for x in w.split("-"))
        w = 0.5 * (lo + hi)
    return w / 1000.0


def _sine_ft2(k, a, m):
    """|∫0^a sin(mπx/a)·e^{-ikx} dx|²."""
    p = m * math.pi / a
    d = p * p - k * k
    if abs(d) < 1e-9 * p * p:
        return a * a / 4.0
    return p * p * 2.0 * (1.0 - (-1) ** m * math.cos(k * a)) / (d * d)


def added_mass_coeff(A, B, m=1, n=1, nk=None, nt=None):
    """added-air-mass coefficient C_a of a flat baffled rectangular panel, one fluid side, mode (m, n).

    m_a = ρ·∫|ŵ(k)|²/|k| d²k / ((2π)²·∫w² dA)  (Rayleigh integral in wavenumber space), C_a = m_a/(ρ·r_eq),
    r_eq = √(AB/π). Depends on the aspect ratio and mode only."""
    L = max(A, B)
    a, b = A / L, B / L
    mm = max(m, n)
    nk = nk or 600 * mm      # midpoint rule converges fast (smooth integrand): 1e-5 vs a 7x finer grid
    nt = nt or 48 * mm
    kmax = 60.0 * math.pi * mm / min(a, b)
    dk, dt = kmax / nk, 0.5 * math.pi / nt
    tot = 0.0
    for i in range(nt):
        th = (i + 0.5) * dt
        c, s = math.cos(th), math.sin(th)
        tot += sum(_sine_ft2((j + 0.5) * dk * c, a, m) * _sine_ft2((j + 0.5) * dk * s, b, n) for j in range(nk))
    tot *= 4.0 * dk * dt
    ma = tot / ((2 * math.pi) ** 2 * (a * b / 4.0))
    return ma / math.sqrt(a * b / math.pi)


def panel_frequency(nw, nf, A, B, mass, sides=2, Ca=None, m=1, n=1):
    """natural frequency f_mn [Hz] of a flat rectangular membrane panel A (warp) × B (weft), pinned edges.

    f_mn = ½·√((n_w·(m/A)² + n_f·(n/B)²)/m_eff), n in N/m, m_eff = mass + sides·C_a·ρ_air·r_eq.
    C_a None -> computed for this panel and mode × membrane.added_mass_model."""
    if Ca is None:
        Ca = added_mass_coeff(A, B, m, n) * F.get("membrane.added_mass_model")
    rho = F.get("membrane.rho_air")
    r_eq = math.sqrt(A * B / math.pi)
    m_eff = mass + sides * Ca * rho * r_eq
    return 0.5 * math.sqrt((nw * 1e3 * (m / A) ** 2 + nf * 1e3 * (n / B) ** 2) / m_eff), m_eff


def prestress_for_frequency(f_target, A, B, m_eff, ratio=1.0):
    """warp prestress [kN/m] (weft = warp/ratio) giving f11 = f_target."""
    k = 1 / A ** 2 + 1 / (ratio * B ** 2)
    return 4 * f_target ** 2 * m_eff / k / 1e3


# ----------------------------------------------------------------------------------------------- corner
def reinforcement_neff(layers, basis="ts", eff=None):
    """effective number of plies (base fabric + reinforcements) and whether the table was exceeded."""
    if basis == "eta" or eff is not None:
        e = F.get("membrane.corner_ply_eff") if eff is None else eff
        return 1.0 + (layers - 1) * e, False
    tab = F.get("membrane.reinforcement_neff")[basis]
    if layers <= len(tab):
        return tab[layers - 1], False
    return tab[-1], True


def corner_check(R, theta_deg, r0, n_all, layers, eff=None, basis=None):
    """radial spreading of a corner force: n(r) = R/(θ·r).

    eff given -> linear ply model n_eff = 1 + (k−1)·eff (legacy); otherwise the published n_eff table `basis`
    ('ts' Eurocode Outlook 38 safe-sided, 'french', 'german', 'eta'). Returns the stress at the plate edge,
    the reinforced allowable n_all·n_eff and the radius from which k plies suffice."""
    basis = "eta" if eff is not None else (basis or "ts")
    th = math.radians(theta_deg)
    n0 = R / (th * r0)
    neff, beyond = reinforcement_neff(layers, basis, eff)
    n_reinf = n_all * neff
    r_k = {k: R / (th * n_all * reinforcement_neff(k, basis, eff)[0]) for k in range(1, layers + 1)}
    return {"n_r0": n0, "n_all_reinf": n_reinf, "u_r0": n0 / n_reinf, "r_base": R / (th * n_all),
            "r_k": r_k, "neff": neff, "beyond_table": beyond, "basis": basis}


# ----------------------------------------------------------------------------------------------- CLI
def _strengths(a, m):
    """(fw, ff, label): strength used by the chosen method."""
    fw, ff = (m["fw"], m["ff"]) if m else (a.fw, a.ff)
    if a.method in ("partial", "ts19102"):
        if a.vx is not None:
            return (char_strength(fw, a.vx), char_strength(ff, a.vx),
                    f"f_k = f·(1 − {F.get('membrane.fractile_kn')}·{a.vx}) from mean {fw}/{ff}")
        if m and "fk_w" in m:
            return m["fk_w"], m["fk_f"], "library 5 % fractile f_k"
        return fw, ff, ("given strength taken as characteristic 5 % value — if it is a datasheet MEAN, "
                        "use --vx (fabric ≈ 0.06, joints ≈ 0.12, JRC132615 §6.3)")
    if a.method == "japan":
        return fw, ff, "strength taken as Fm (designated standard strength) — use the certified Fm"
    return fw, ff, "datasheet strip strength (mean / nominal)"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list library materials")
    ap.add_argument("--material", help="library key (see --list)")
    ap.add_argument("--fw", type=float, help="warp strip tensile strength [kN/m]")
    ap.add_argument("--ff", type=float, help="weft strip tensile strength [kN/m]")
    ap.add_argument("--vx", type=float, default=None,
                    help="coefficient of variation: converts mean strength to f_k (partial / ts19102)")
    ap.add_argument("--family", default=None, help="PES/PVC | glass/PTFE | other (partial / ts19102)")
    ap.add_argument("--nw", type=float, help="max warp stress from analysis [kN/m]")
    ap.add_argument("--nf", type=float, help="max weft stress from analysis [kN/m]")
    ap.add_argument("--nmin", type=float, default=None, help="min principal stress (slack check) [kN/m]")
    ap.add_argument("--case", choices=list(CASES), default="wind")
    ap.add_argument("--method", choices=METHODS, default="factor")
    ap.add_argument("--sf-short", type=float, default=None, help="override short-term stress factor")
    ap.add_argument("--sf-long", type=float, default=None, help="override long-term stress factor")
    ap.add_argument("--factors", default=None, help="project code-factor file (overrides register)")
    ap.add_argument("--fm-combo", default="P+D+W", choices=["P+D", "P+D+S", "P+D+W", "P+D+T", "P+D+L", "P+D+R"])
    ap.add_argument("--japan-joint", choices=["wide", "narrow"], default="wide",
                    help="japan: joint/weld >= 40 mm (75 mm glass/PTFE) or no joint = wide")
    ap.add_argument("--folded", action="store_true", help="japan: membrane is folded (short-term Fm/5)")
    ap.add_argument("--ts-snow", choices=["M", "L"], default="M",
                    help="ts19102: snow load duration M (<= 1000 m altitude) or L (> 1000 m)")
    ap.add_argument("--area", type=float, default=None, help="french: area S of the membrane element [m²]")
    ap.add_argument("--ke", type=float, default=None, help="french: scale factor ke (overrides --area)")
    ap.add_argument("--kq", type=float, default=1.0, help="french: quality factor kq (1.0 or 0.8)")
    ap.add_argument("--pollution", choices=["medium", "heavy"], default="medium", help="french: exposure")
    ap.add_argument("--seam-eff", type=float, default=None, help="seam strength / fabric strength (default register)")
    ap.add_argument("--seam-dir", choices=["warp", "weft", "both"], default="both",
                    help="which stress acts ACROSS seams (seams usually run in warp -> weft stress crosses)")
    ap.add_argument("--prestress", type=float, nargs=2, metavar=("PW", "PF"),
                    help="warp & weft prestress [kN/m] for level advice")
    ap.add_argument("--envelope", default=None, help="run_cases.py _envelope.json: check every case (warp/weft max)")
    ap.add_argument("--tear", type=float, nargs=2, metavar=("A_TEST", "N_TEST"),
                    help="slit-tear test: slit length [mm] and critical stress [kN/m] -> tear propagation check")
    ap.add_argument("--defect", type=float, default=50.0, help="design slit/defect length [mm] for --tear")
    ap.add_argument("--curvature", type=float, nargs=2, metavar=("R_RES", "R_OTH"),
                    help="radii [m] of the direction resisting the load and of the other direction (hand estimate)")
    ap.add_argument("--p", type=float, default=0.0, help="surface load for --curvature [kN/m2]")
    ap.add_argument("--flutter", type=float, nargs=2, metavar=("A", "B"),
                    help="panel spans [m] (A along warp) for the natural-frequency check (uses --prestress)")
    ap.add_argument("--mass", type=float, default=None, help="fabric mass [kg/m²] (default from library)")
    ap.add_argument("--sides", type=int, choices=[1, 2], default=2,
                    help="air sides for the added mass (2 open canopy, 1 closed building)")
    ap.add_argument("--ca", type=float, default=None, help="fixed added-mass coefficient (default: computed)")
    ap.add_argument("--modes", type=int, default=1, help="number of panel modes to list with --flutter")
    ap.add_argument("--f-target", type=float, default=None, help="target f11 [Hz] -> required prestress")
    ap.add_argument("--corner", type=float, nargs=3, metavar=("R", "THETA", "R0"),
                    help="corner force [kN], fan angle [deg], plate/clamp radius [m]")
    ap.add_argument("--layers", type=int, default=2, help="total plies at the corner incl. base fabric")
    ap.add_argument("--neff-basis", choices=["ts", "french", "german", "eta"], default="ts",
                    help="reinforcement factor table for --corner (ts = Eurocode Outlook 38, safe-sided)")
    ap.add_argument("--etfe-single-unregulated", action="store_true",
                    help="ETFE single-layer foil with no regulation in the attachment details (kperm 3.5)")
    ap.add_argument("--sensitivity", action="store_true", help="check the decision over the range of factors")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    if a.seam_eff is None:
        a.seam_eff = F.get("membrane.seam_efficiency")
    opts = {"japan_joint": a.japan_joint, "folded": a.folded, "ts_snow": a.ts_snow, "area": a.area, "ke": a.ke,
            "kq": a.kq, "pollution": a.pollution}
    notes = []

    lib = load_lib()
    if a.list:
        print(f"{'key':<30}{'family':<16}{'fw':>7}{'ff':>7}{'fk_w':>7}{'g/m²':>11}  status")
        for k, m in lib["materials"].items():
            fk = m.get("fk_w", "")
            print(f"{k:<30}{m['family']:<16}{m['fw']:>7g}{m['ff']:>7g}{fk!s:>7}{m.get('weight_gm2', '-')!s:>11}  "
                  f"{m['status']}")
        print("\nfw/ff = strip strength [kN/m] as published (basis per entry: mean, minimum or nominal); "
              "fk = 5 % fractile where published. Typical / class values: screening only, use the supplier's "
              "certified data for design.")
        return
    family = a.family or "other"
    m = None
    if a.material:
        m = lib["materials"].get(a.material)
        if not m:
            sys.exit(f"unknown material {a.material}; use --list")
        family = a.family or m["family"]
        print(f"Material {a.material}: {family}, fw/ff = {m['fw']}/{m['ff']} kN/m ({m.get('strength_basis', '?')}) "
              f"[{m['status']}: {m['source']}]")
    else:
        if a.fw is None or a.ff is None:
            sys.exit("give --material or --fw/--ff")
        print(f"Material: fw/ff = {a.fw}/{a.ff} kN/m ({family})")
    fw, ff, sbasis = _strengths(a, m)
    if family != "ETFE":
        notes.append(f"strength: {sbasis} -> {fw:.2f}/{ff:.2f} kN/m")

    if a.prestress:
        pw, pf = a.prestress
        print(f"\nPrestress {pw}/{pf} kN/m = {100 * pw / fw:.1f} % / {100 * pf / ff:.1f} % of strength")
        rng = lib["family_defaults"].get(family, {}).get("prestress_kN_m", "n/a")
        print(f"  typical range for {family}: {rng} kN/m [U]; practice 1.8–3.5 kN/m [V, JRC132615]")
        if family != "ETFE":
            pmin_w, txt = prestress_minimum(family, fw)
            pmin_f, _ = prestress_minimum(family, ff)
            print(f"  minimum (published guidance): warp {pmin_w:.2f} / weft {pmin_f:.2f} kN/m ({txt}) "
                  f"[{F.status('membrane.prestress_min')}]")
            if pw < pmin_w or pf < pmin_f:
                print("  LOW: below the published minimum — risk of wrinkling / flutter / ponding; raise prestress "
                      "or curvature")
        if max(pw / fw, pf / ff) > 0.05:
            print("  HIGH: creep, relaxation and tear risk; heavy boundary forces")
        ratio = max(pw, pf) / min(pw, pf)
        if ratio > 3:
            print(f"  warp/weft ratio {ratio:.1f} is extreme — anisotropic form-finding needs URS / checking")

    if a.curvature:
        Rr, Ro = a.curvature
        n0r, n0o = (a.prestress if a.prestress else (2.0, 2.0))
        n_res = n0r + a.p * Rr
        n_oth = n0o - a.p * Ro
        print(f"\nCurvature estimate (Laplace n1/R1 + n2/R2 = p, bounds): p = {a.p} kN/m², "
              f"R_resisting = {Rr} m, R_other = {Ro} m")
        print(f"  resisting direction  ≤ n0 + p·R = {n_res:.2f} kN/m (upper bound, other direction keeps prestress)")
        print(f"  other direction      ≥ n0 − p·R = {n_oth:.2f} kN/m (lower bound)"
              + ("  -> may go SLACK: raise prestress or curvature" if n_oth <= 0 else ""))
        print("  (hand sizing only; confirm with the non-linear analysis)")
        notes.append("curvature: membrane equilibrium bounds only (no stiffness, no large deflection)")
        if a.nw is None and a.nf is None:
            a.nw = max(n_res, 0.0)

    if a.tear:
        at, nt = a.tear
        n_crit = nt * math.sqrt(at / a.defect)       # LEFM centre-crack scaling σ_c·√a = const
        gt = F.get("membrane.tear_factor")
        n_dem = max(v for v in (a.nw, a.nf) if v is not None) if (a.nw or a.nf) else None
        print(f"\nTear propagation: slit test {at:g} mm @ {nt:g} kN/m -> critical stress for a {a.defect:g} mm "
              f"defect ≈ {n_crit:.2f} kN/m (scaled ∝ 1/√a); allowable = /{gt:g} [{F.status('membrane.tear_factor')}]"
              f" = {n_crit / gt:.2f} kN/m")
        if n_dem is not None:
            u = n_dem / (n_crit / gt)
            print(f"  design stress {n_dem:.2f} kN/m -> util {u:.2f}" + ("  <-- FAIL" if u > 1 else "  OK"))
            if a.sensitivity:
                print(F.sens_line("tear factor", F.sensitivity(lambda g: n_dem / (n_crit / g),
                                                                "membrane.tear_factor")))
        notes.append("tear: LEFM 1/√a scaling of ONE slit test (same specimen width/biaxial ratio); coated fabrics "
                     "deviate from 1/√a (yarn-count effects) — test near the design defect length; tear_factor [U]")

    if a.envelope:
        with open(a.envelope) as fh:
            env = json.load(fh)
        print(f"\nEnvelope check ({a.envelope}), method '{a.method}':")
        print(f"{'case':<14}{'dur':>6}{'warp':>8}{'weft':>8}{'u fabric':>10}{'u seam':>8}")
        rows_e = envelope_utils(env, fw, ff, a.method, family, a.seam_eff, a.sf_short, a.sf_long, opts=opts)
        for r, dur, nw_, nf_, uf, us in rows_e:
            print(f"{r['case']:<14}{dur:>6}{nw_:8.2f}{nf_:8.2f}{uf:10.2f}{us:8.2f}" + ("  <-- FAIL" if us > 1 else ""))
        worst_all = max(max(x[4], x[5]) for x in rows_e)
        print(f"Governing (fabric/seams, eff {_seam_eff(a.method, a.seam_eff):g}): {worst_all:.2f} -> "
              f"{'OK' if worst_all <= 1 else 'NOT OK'}")
        if a.sensitivity:
            keys = sorted({factor_key(a.method, env_case(r)[0], family) for r in env["summary"]} - {None})
            keys = [k for k in keys if _has_range(k)]
            for key in keys:
                res = F.sensitivity(lambda v, key=key: max(max(x[4], x[5]) for x in envelope_utils(
                    env, fw, ff, a.method, family, a.seam_eff, a.sf_short, a.sf_long, {key: v}, opts)), key)
                print(F.sens_line(_sens_name(key) + " (envelope)", res))
            if not keys:
                print("  sensitivity: no factor with a range in this method (all [V]/[C] values or user values)")
        if a.method not in ("partial", "ts19102") and any(abs(r.get("factor", 1.0) - 1.0) > 1e-9
                                                         for r in env["summary"]):
            print("WARNING: some cases were run with load factors ≠ 1, but global stress-factor methods "
                  "(factor/fm/japan/french) expect CHARACTERISTIC loads -> safety counted twice (conservative). "
                  "Run characteristic cases for these methods, or use --method partial/ts19102 with factored cases.")

    if family == "ETFE" and a.material and (a.nw or a.nf):
        mm = lib["materials"][a.material]
        fy = mm.get("fy10_MPa")
        fd, basis = etfe_design_strength(a.case, fy=fy, single_unregulated=a.etfe_single_unregulated)
        s_ = max(v for v in (a.nw, a.nf) if v) / mm["t_mm"]  # kN/m / mm = MPa
        print(f"\nETFE foil check ({a.case}, design stress input): σ = n/t = {s_:.2f} MPa vs f_d = {basis} = "
              f"{fd:.2f} MPa -> util {s_ / fd:.2f}" + ("  <-- FAIL" if s_ > fd else "  OK"))
        print("  SLS (strain/deformation limits) usually governs ETFE: check cushion deflection and the "
              "permanent stress separately (TensiNet App. A5).")
        notes.append("ETFE: JRC132615 Eurocode Outlook 44 design proposal (f_y10,23 = 10 % strain stress; "
                     "confirm against CEN/TS 19102 §8.3/Annex C.5); welds need their own strength (≈ 30 MPa)")
        _print_notes(notes, a)
        return s_ / fd

    if a.flutter:
        _flutter(a, lib, notes)

    if a.corner:
        R, th, r0 = a.corner
        if a.method == "french":
            n_all = a.kq * min(fw, ff) / F.get("membrane.french_gamma_tloc")
            nb = f"French attachment rule kq·Trm/γtloc (γtloc {F.get('membrane.french_gamma_tloc'):g})"
        else:
            n_all = min(allowable(fw, a.method, a.case, family, a.sf_short, a.sf_long, a.fm_combo, None, opts)[0],
                        allowable(ff, a.method, a.case, family, a.sf_short, a.sf_long, a.fm_combo, None, opts)[0])
            nb = f"weaker direction, case '{a.case}', method '{a.method}'"
        c = corner_check(R, th, r0, n_all, a.layers, basis=a.neff_basis)
        nst = F.status("membrane.corner_ply_eff" if c["basis"] == "eta" else "membrane.reinforcement_neff")
        print(f"\nCorner: R = {R} kN fanning over {th:g}° from r0 = {r0} m; base allowable {n_all:.2f} kN/m ({nb})")
        print(f"  n(r0) = R/(θ·r0) = {c['n_r0']:.2f} kN/m vs {a.layers} plies: n_all·n_eff, n_eff = {c['neff']:g} "
              f"('{c['basis']}' basis [{nst}]) = {c['n_all_reinf']:.2f} kN/m -> util {c['u_r0']:.2f}"
              + ("  <-- FAIL: more plies or larger plate/clamp radius" if c['u_r0'] > 1 else "  OK"))
        if c["beyond_table"]:
            print(f"  NOTE: the '{c['basis']}' table credits at most {len(F.get('membrane.reinforcement_neff')[c['basis']])}"
                  " plies (Eurocode Outlook 38: more than one reinforcement layer needs tests)")
        rk = c["r_k"]
        print(f"  with {a.layers} plies the plate/clamp must reach r ≥ {rk[a.layers]:.2f} m"
              + ("" if rk[a.layers] <= r0 else f" (now {r0} m)") + "; ply k must extend to "
              + ", ".join(f"ply {k}: {rk[k - 1]:.2f} m" for k in range(a.layers, 1, -1))
              + f"; base fabric alone beyond {rk[1]:.2f} m")
        if a.sensitivity:
            us = {b: corner_check(R, th, r0, n_all, a.layers, basis=b)["u_r0"] for b in ("ts", "german", "french", "eta")}
            robust = len({u <= 1 for u in us.values()}) == 1
            print("  sensitivity n_eff basis: " + ", ".join(f"{b} util {u:.2f}" for b, u in us.items())
                  + (" -> ROBUST" if robust else " -> DEPENDS on the reinforcement factor: test the corner"))
        notes.append("corner: radial-fan equilibrium estimate; belt/strap force and clamp bolts not included; "
                     "n_eff from JRC132615 §6.5 tables (ts = Eurocode Outlook 38 safe-sided)")

    if a.nw is None and a.nf is None:
        _print_notes(notes, a)
        return
    rows = point_utils(a.nw, a.nf, fw, ff, a.method, a.case, family, a.seam_eff, a.seam_dir, a.sf_short,
                       a.sf_long, a.fm_combo, None, opts)
    worst = 0.0
    print(f"\nCheck — case '{a.case}' ({CASES[a.case]}-term, situation {SITUATION[a.case]}), method '{a.method}'")
    print(f"{'item':<38}{'n [kN/m]':>10}{'n_all':>9}{'util':>7}  basis")
    for item, n, al, basis in rows:
        u = n / al
        worst = max(worst, u)
        print(f"{item:<38}{n:10.2f}{al:9.2f}{u:7.2f}  {basis}" + ("  <-- FAIL" if u > 1 else ""))
    if a.nmin is not None:
        print(f"{'no-slack (min principal stress)':<38}{a.nmin:10.2f}{'> 0':>9}"
              + ("   OK" if a.nmin > 0 else "   SLACK/WRINKLING -> check SLS appearance, flutter, ponding"))
    print(f"Governing utilisation {worst:.2f} -> {'OK' if worst <= 1 else 'NOT OK'}")
    if a.sensitivity:
        key = factor_key(a.method, a.case, family)
        given = a.sf_long if CASES[a.case] == "long" else a.sf_short
        if _has_range(key) and not (a.method == "factor" and given is not None):
            res = F.sensitivity(lambda v: max(n / al for _, n, al, _ in point_utils(
                a.nw, a.nf, fw, ff, a.method, a.case, family, a.seam_eff, a.seam_dir, a.sf_short, a.sf_long,
                a.fm_combo, {key: v}, opts)), key)
            print(F.sens_line(_sens_name(key), res))
        else:
            print(f"  sensitivity: method '{a.method}' uses no factor with a range here ([V]/[C] or user values)")
    print("Also check: tear propagation at critical defect, corner/clamp stress concentrations, "
          "ponding under deformed shape, strength at elevated temperature (seams).")
    _method_notes(a, notes)
    _print_notes(notes, a)
    return worst


def _sens_name(key):
    parts = key.split(".")
    if parts[1] == "partial":
        return "partial" + (f" ({parts[2]})" if len(parts) > 2 else "")
    return parts[-1]


def _method_notes(a, notes):
    txt = {"factor": "global stress factor on CHARACTERISTIC (unfactored) load effects; SF [V] ASCE 55-10 practice",
           "fm": "FM DS 1-59 factors apply to NEW-fabric strength and characteristic load effects",
           "japan": "MLIT 666 allowable stress on characteristic effects; Fm = designated standard strength; "
                    "the notification also limits deformation (1/15, 1/20 of support spacing) and anchorages (Fj/6, Fj/3)",
           "partial": "German A-factor format on DESIGN (factored) stresses; A-factors are material-specific "
                      "(take them from the material approval / tests when available)",
           "ts19102": "CEN/TS 19102 format on DESIGN stresses; prCEN factor values for PES/PVC from the JRC 2025 "
                      "worked example — confirm against the published TS Annex C and the National Annex",
           "french": "French recommendations; TC = stress under the recommendation's combinations (the JRC 2025 "
                     "example applies 1.5 to the characteristic stress); Trm = mean strength"}[a.method]
    notes.append(f"method: {txt}")


def _flutter(a, lib, notes):
    A, B = a.flutter
    mass = a.mass if a.mass is not None else (mass_kg_m2(lib["materials"][a.material]) if a.material else None)
    if mass is None:
        sys.exit("--flutter needs --mass (no fabric weight in the library entry)")
    pw, pf = a.prestress if a.prestress else (None, None)
    model = F.get("membrane.added_mass_model")
    ca11 = a.ca if a.ca is not None else added_mass_coeff(A, B) * model
    ca_src = ("user value" if a.ca is not None else
              f"computed, baffled panel × model factor {model:g} [{F.status('membrane.added_mass_model')}]")
    print(f"\nPanel frequency: {A} m (warp) × {B} m (weft), fabric {mass:.2f} kg/m², air on {a.sides} side(s), "
          f"C_a(1,1) = {ca11:.3f} ({ca_src}), ρ_air = {F.get('membrane.rho_air')} [{F.status('membrane.rho_air')}]")
    if pw:
        f11, m_eff = panel_frequency(pw, pf, A, B, mass, a.sides, ca11)
        print(f"  m_eff = {m_eff:.2f} kg/m² (air {100 * (1 - mass / m_eff):.0f} %)  ->  f11 = {f11:.2f} Hz "
              f"at prestress {pw}/{pf} kN/m (flat-panel lower bound; curvature raises it)")
        if a.modes > 1:
            modes = []
            for mi in range(1, 4):
                for ni in range(1, 4):
                    ca = a.ca if a.ca is not None else added_mass_coeff(A, B, mi, ni) * model
                    modes.append((panel_frequency(pw, pf, A, B, mass, a.sides, ca, mi, ni)[0], mi, ni, ca))
            modes.sort()
            print("  modes: " + "; ".join(f"f{mi}{ni} = {f:.2f} Hz (C_a {ca:.2f})" for f, mi, ni, ca in modes[:a.modes]))
        if a.sensitivity and a.ca is None:
            ca0 = added_mass_coeff(A, B)
            res = F.sensitivity(lambda s: panel_frequency(pw, pf, A, B, mass, a.sides, ca0 * s)[0],
                                "membrane.added_mass_model")
            print(f"  sensitivity added-mass model: f11 = {res['u']:.2f} Hz at {res['value']}, {res['u_lo']:.2f} at "
                  f"{res['lo']}, {res['u_hi']:.2f} at {res['hi']}"
                  + (f" -> target {a.f_target} Hz {'met over the range' if min(res['u'], res['u_lo'], res['u_hi']) >= a.f_target else 'DEPENDS on the added mass'}"
                     if a.f_target else ""))
    else:
        f11, m_eff = None, panel_frequency(1.0, 1.0, A, B, mass, a.sides, ca11)[1]
    if a.f_target:
        ratio = (pw / pf) if pw else 1.0
        n_req = prestress_for_frequency(a.f_target, A, B, m_eff, ratio)
        print(f"  prestress for f11 ≥ {a.f_target} Hz: warp {n_req:.2f} / weft {n_req / ratio:.2f} kN/m"
              + (f"  ({'OK' if pw >= n_req else 'RAISE prestress or reduce the panel span'})" if pw else ""))
    print("  No code gives a frequency limit: agree the target with the wind engineer (gusts, vortex "
          "shedding); flutter/aero-elastic checks need wind-tunnel data for large, flat panels.")
    notes.append("flutter: flat rectangular panel, pinned edges, linear (small amplitude), still air, added mass of a "
                 "baffled panel (upper bound; isolated canopies ≈ 0.5–1.0 × [U]); curvature and wind flow ignored")


def _print_notes(notes, a):
    if not notes:
        return
    print("\nAssumptions:")
    for n in notes:
        print(f"  - {n}")
    print("  - library values are published typical/class/datasheet figures: use the supplier's certified "
          "strength and biaxial data for the delivered batch; confirm code factors against the edition and NA in force")


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
