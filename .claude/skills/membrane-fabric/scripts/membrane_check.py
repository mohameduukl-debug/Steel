#!/usr/bin/env python3
"""Membrane stress check (warp & weft, fabric & seam) with selectable design basis.

Methods
-------
  factor   permissible-stress / global stress-factor practice (DEFAULT)
           allowable = f / SF ; SF_short (wind) = 4.0, SF_long (prestress, snow) = 5.0
           — industry practice (Birdair "usually 5"; literature range 4–8).
  fm       FM Global DS 1-59 (2021) Table 2.2.6.1 minimum safety factors on
           NEW-fabric strength: P+D 8.0 ; P+D+(L|S|R) 5.0 ; P+D+W 5.0 ; P+D+T 5.0
           (these assume ≥75 % strength retention, i.e. ASCE 55 L_t = 0.75)
  japan    MLIT Notification 666 style: 1/8 of strength long-term, 1/4 short-term
           (value reported in literature — verify before use)
  partial  limit-state format of CEN/TS 19102:2023 / German "A-factor" practice:
              n_Rd = f_k / (γ_M · k1 · k2 · k3 · k4)
           with the k (A) factors for biaxial/size, load duration, ageing,
           temperature. Default factors are INDICATIVE (German A-factor
           practice) and must be replaced by CEN/TS 19102 Annex C / National
           Annex / project values. Stress input must be the DESIGN value from the
           factored non-linear combination (γ_P ≈ 1.0, γ_Q ≈ 1.5).

Always checked: fabric warp & weft, seams (strength × seam efficiency),
no-slack (min stress > 0) and prestress level vs. strength.

Extra checks
  --flutter A B     fundamental frequency of a prestressed panel A × B [m] (A along warp)
                    f11 = ½·√((n_w/A² + n_f/B²)/m_eff), m_eff = fabric mass + added air mass
                    C_a·ρ_air·r_eq per side (flat-panel lower bound: curvature raises f);
                    --f-target gives the prestress needed for a target frequency
  --corner R THETA R0   corner force R [kN] spreading radially over THETA [deg] from the
                    plate/clamp radius R0 [m]: n(r) = R/(θ·r); checks the reinforced zone and
                    gives the radius where the base fabric alone is enough
  --sensitivity     re-runs every check that uses an UNVERIFIED [U] factor at both ends of the
                    factor's range and says whether the OK / NOT OK decision depends on it

Examples
--------
  python3 membrane_check.py --material PVC-III --nw 18.5 --nf 14.2 --case wind
  python3 membrane_check.py --material Chukoh-FGT-800 --nw 31 --nf 22 --case snow --method fm
  python3 membrane_check.py --fw 84 --ff 80 --nw 9 --nf 7 --case snow --method partial
  python3 membrane_check.py --material PVC-II --prestress 2.0 2.0     (prestress level advice)
  python3 membrane_check.py --material PVC-III --prestress 2 2 --flutter 6 4 --f-target 2.0
  python3 membrane_check.py --material PVC-III --case wind --corner 60 90 0.15 --layers 3
  python3 membrane_check.py --material PVC-III --nw 9 --nf 8 --case snow --method partial --sensitivity
  python3 membrane_check.py --list
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

sys.path.insert(0, os.path.join(HERE, "..", "..", "tensile-structures", "scripts"))
import factors as F  # noqa: E402  central code-factor register (V/C/U tagged)


def load_lib():
    with open(LIB) as fh:
        return json.load(fh)


def factor_key(method, case):
    """register key of the factor that governs allowable() for this method/case."""
    dur = CASES[case]
    return {"factor": f"membrane.stress_factor_{dur}", "fm": None,
            "japan": f"membrane.japan_{dur}_divisor", "partial": "membrane.partial"}[method]


def allowable(f, method, case, family, sf_short=None, sf_long=None, fm_combo="P+D+W", override=None):
    """allowable membrane stress; factors not given explicitly come from the factor register.

    override = {register key: value} replaces a register value (used by --sensitivity; for the
    'membrane.partial' table the value is a scale on γM·ΠA)."""
    ov = override or {}
    dur = CASES[case]
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
        key = "membrane.japan_long_divisor" if dur == "long" else "membrane.japan_short_divisor"
        k = ov.get(key, F.get(key))
        return f / k, f"1/{k:g} of strength ({dur}-term) [{F.status(key)}]"
    if method == "partial":
        tab = F.get("membrane.partial")
        p = tab.get(family, tab["other"])
        A1 = p["A1_long"] if dur == "long" else p["A1_short"]
        k = p["gM"] * p["A0"] * A1 * p["A2"] * p["A3"] * ov.get("membrane.partial", 1.0)
        st = F.status("membrane.partial")
        note = "INDICATIVE — replace with CEN/TS 19102 / NA values" if st == "U" else "project values"
        return f / k, (f"γM {p['gM']} × A0 {p['A0']} × A1 {A1} × A2 {p['A2']} × A3 {p['A3']} = {k:.2f} "
                       f"[{st}] ({note})")
    raise ValueError(method)


def _unverified(key):
    return key is not None and F.status(key) == "U" and F.frange(key) is not None


def env_case(r):
    dur = r.get("duration", "short")
    case = "wind" if dur == "short" else "snow"
    if r["case"].upper() in ("PS", "PRESTRESS"):
        case = "prestress"
    return case, ("P+D" if case == "prestress" else ("P+D+W" if case == "wind" else "P+D+S"))


def envelope_utils(env, fw, ff, method, family, seam_eff, sf_short=None, sf_long=None, override=None):
    """[(row, dur, nw, nf, u_fabric, u_seam)] for every case of a run_cases.py envelope."""
    out = []
    for r in env["summary"]:
        case, combo = env_case(r)
        nw_, nf_ = r.get("warp_max") or 0.0, r.get("weft_max") or 0.0
        aw, _ = allowable(fw, method, case, family, sf_short, sf_long, combo, override)
        af, _ = allowable(ff, method, case, family, sf_short, sf_long, combo, override)
        uf = max(nw_ / aw, nf_ / af)
        out.append((r, r.get("duration", "short"), nw_, nf_, uf, uf / seam_eff))
    return out


def point_utils(nw, nf, fw, ff, method, case, family, seam_eff, seam_dir="both", sf_short=None, sf_long=None,
                fm_combo="P+D+W", override=None):
    """[(item, n, n_allowable, basis)] for the single-point check (fabric + seams)."""
    rows = []
    for name, n, f in (("warp", nw, fw), ("weft", nf, ff)):
        if n is None:
            continue
        al, basis = allowable(f, method, case, family, sf_short, sf_long, fm_combo, override)
        rows.append((f"fabric {name}", n, al, basis))
        if seam_dir in (name, "both"):
            al_s, _ = allowable(f * seam_eff, method, case, family, sf_short, sf_long, fm_combo, override)
            rows.append((f"seam (stress {name}, eff {seam_eff:g})", n, al_s, basis))
    return rows


def mass_kg_m2(m):
    """fabric mass [kg/m²] from a library entry ('weight_gm2' may be a range string -> mid value)."""
    w = m.get("weight_gm2")
    if w is None:
        return None
    if isinstance(w, str):
        lo, hi = (float(x) for x in w.split("-"))
        w = 0.5 * (lo + hi)
    return w / 1000.0


def panel_frequency(nw, nf, A, B, mass, sides=2, Ca=None):
    """fundamental frequency [Hz] of a flat rectangular membrane panel A (warp) × B (weft), pinned edges.

    f11 = ½·√((n_w/A² + n_f/B²)/m_eff) with n in N/m, m_eff = mass + sides·C_a·ρ_air·r_eq, r_eq = √(AB/π)."""
    Ca = F.get("membrane.added_mass_coeff") if Ca is None else Ca
    rho = F.get("membrane.rho_air")
    r_eq = math.sqrt(A * B / math.pi)
    m_eff = mass + sides * Ca * rho * r_eq
    return 0.5 * math.sqrt((nw * 1e3 / A ** 2 + nf * 1e3 / B ** 2) / m_eff), m_eff


def prestress_for_frequency(f_target, A, B, m_eff, ratio=1.0):
    """warp prestress [kN/m] (weft = warp/ratio) giving f11 = f_target."""
    k = 1 / A ** 2 + 1 / (ratio * B ** 2)
    return 4 * f_target ** 2 * m_eff / k / 1e3


def corner_check(R, theta_deg, r0, n_all, layers, eff=None):
    """radial spreading of a corner force: n(r) = R/(θ·r).

    Returns dict with the stress at the plate edge, the reinforced allowable
    n_all·(1 + (layers−1)·eff) and the radius beyond which the base fabric alone suffices."""
    eff = F.get("membrane.corner_ply_eff") if eff is None else eff
    th = math.radians(theta_deg)
    n0 = R / (th * r0)
    n_reinf = n_all * (1 + (layers - 1) * eff)
    return {"n_r0": n0, "n_all_reinf": n_reinf, "u_r0": n0 / n_reinf,
            "r_base": R / (th * n_all),
            # r_k[k] = radius beyond which k plies are enough (k = 1 -> base fabric alone)
            "r_k": {k: R / (th * n_all * (1 + (k - 1) * eff)) for k in range(1, layers + 1)}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list library materials")
    ap.add_argument("--material", help="library key (see --list)")
    ap.add_argument("--fw", type=float, help="warp strip tensile strength [kN/m]")
    ap.add_argument("--ff", type=float, help="weft strip tensile strength [kN/m]")
    ap.add_argument("--family", default=None, help="PES/PVC | glass/PTFE | other (for --method partial)")
    ap.add_argument("--nw", type=float, help="max warp stress from analysis [kN/m]")
    ap.add_argument("--nf", type=float, help="max weft stress from analysis [kN/m]")
    ap.add_argument("--nmin", type=float, default=None, help="min principal stress (slack check) [kN/m]")
    ap.add_argument("--case", choices=list(CASES), default="wind")
    ap.add_argument("--method", choices=["factor", "fm", "japan", "partial"], default="factor")
    ap.add_argument("--sf-short", type=float, default=None, help="override short-term stress factor")
    ap.add_argument("--sf-long", type=float, default=None, help="override long-term stress factor")
    ap.add_argument("--factors", default=None, help="project code-factor file (overrides register)")
    ap.add_argument("--fm-combo", default="P+D+W", choices=["P+D", "P+D+S", "P+D+W", "P+D+T", "P+D+L", "P+D+R"])
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
    ap.add_argument("--f-target", type=float, default=None, help="target f11 [Hz] -> required prestress")
    ap.add_argument("--corner", type=float, nargs=3, metavar=("R", "THETA", "R0"),
                    help="corner force [kN], fan angle [deg], plate/clamp radius [m]")
    ap.add_argument("--layers", type=int, default=2, help="total plies at the corner incl. base fabric")
    ap.add_argument("--sensitivity", action="store_true", help="check the decision over the range of [U] factors")
    a = ap.parse_args(argv)
    if a.factors:
        os.environ["TENSILE_FACTORS"] = a.factors
    if a.seam_eff is None:
        a.seam_eff = F.get("membrane.seam_efficiency")

    lib = load_lib()
    if a.list:
        print(f"{'key':<28}{'family':<16}{'fw':>6}{'ff':>6}  status")
        for k, m in lib["materials"].items():
            print(f"{k:<28}{m['family']:<16}{m['fw']:>6}{m['ff']:>6}  {m['status']}")
        return
    family = a.family or "other"
    if a.material:
        m = lib["materials"].get(a.material)
        if not m:
            sys.exit(f"unknown material {a.material}; use --list")
        fw, ff, family = m["fw"], m["ff"], a.family or m["family"]
        print(f"Material {a.material}: {family}, fw/ff = {fw}/{ff} kN/m  [{m['status']}: {m['source']}]")
    else:
        if a.fw is None or a.ff is None:
            sys.exit("give --material or --fw/--ff")
        fw, ff = a.fw, a.ff
        print(f"Material: fw/ff = {fw}/{ff} kN/m ({family})")

    if a.prestress:
        pw, pf = a.prestress
        print(f"\nPrestress {pw}/{pf} kN/m = {100 * pw / fw:.1f} % / {100 * pf / ff:.1f} % of strength")
        rng = lib["family_defaults"].get(family, {}).get("prestress_kN_m", "n/a")
        print(f"  typical range for {family}: {rng} kN/m; rule of thumb ~1.5–3 % of UTS")
        if min(pw / fw, pf / ff) < 0.01:
            print("  LOW: risk of wrinkling / flutter / ponding — raise prestress or curvature")
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
        if a.nw is None and a.nf is None:
            a.nw = max(n_res, 0.0)

    if a.tear:
        at, nt = a.tear
        n_crit = nt * math.sqrt(at / a.defect)       # LEFM-type scaling σ_c ∝ 1/√a from the slit test
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

    if a.envelope:
        with open(a.envelope) as fh:
            env = json.load(fh)
        print(f"\nEnvelope check ({a.envelope}), method '{a.method}':")
        print(f"{'case':<14}{'dur':>6}{'warp':>8}{'weft':>8}{'u fabric':>10}{'u seam':>8}")
        rows_e = envelope_utils(env, fw, ff, a.method, family, a.seam_eff, a.sf_short, a.sf_long)
        for r, dur, nw_, nf_, uf, us in rows_e:
            print(f"{r['case']:<14}{dur:>6}{nw_:8.2f}{nf_:8.2f}{uf:10.2f}{us:8.2f}" + ("  <-- FAIL" if us > 1 else ""))
        worst_all = max(x[5] for x in rows_e)
        print(f"Governing (seams, eff {a.seam_eff:g}): {worst_all:.2f} -> {'OK' if worst_all <= 1 else 'NOT OK'}")
        if a.sensitivity:
            keys = sorted({factor_key(a.method, env_case(r)[0]) for r in env["summary"]} - {None})
            keys = [k for k in keys if _unverified(k)]
            for key in keys:
                res = F.sensitivity(lambda v, key=key: max(x[5] for x in envelope_utils(
                    env, fw, ff, a.method, family, a.seam_eff, a.sf_short, a.sf_long, {key: v})), key)
                print(F.sens_line(f"{key.split('.')[-1]} (envelope, seams)", res))
            if not keys:
                print("  sensitivity: no unverified factor in this method (all [V]/[C] or user values)")
        if a.method != "partial" and any(abs(r.get("factor", 1.0) - 1.0) > 1e-9 for r in env["summary"]):
            print("WARNING: some cases were run with load factors ≠ 1, but global stress-factor methods "
                  "(factor/fm/japan) expect CHARACTERISTIC loads -> safety counted twice (conservative). "
                  "Run characteristic cases for these methods, or use --method partial with factored cases.")

    if family == "ETFE" and a.material and (a.nw or a.nf):
        m = lib["materials"][a.material]
        g = F.get("membrane.etfe_gamma")
        s_ = max(v for v in (a.nw, a.nf) if v) / m["t_mm"]  # kN/m / mm = MPa
        print(f"\nETFE stress check: σ = n/t = {s_:.1f} MPa vs f_y1/γ = {m['fy1_MPa']}/{g} = {m['fy1_MPa'] / g:.1f} MPa "
              f"[{F.status('membrane.etfe_gamma')}] -> util {s_ / (m['fy1_MPa'] / g):.2f} "
              "(temperature and load duration reduce f_y — see TensiNet App. A5)")
        if a.sensitivity:
            print(F.sens_line("ETFE γ", F.sensitivity(lambda gg: s_ / (m["fy1_MPa"] / gg), "membrane.etfe_gamma")))
        return

    if a.flutter:
        A, B = a.flutter
        mass = a.mass if a.mass is not None else (mass_kg_m2(lib["materials"][a.material]) if a.material else None)
        if mass is None:
            sys.exit("--flutter needs --mass (no fabric weight in the library entry)")
        pw, pf = a.prestress if a.prestress else (None, None)
        Ca_st = F.status("membrane.added_mass_coeff")
        print(f"\nPanel frequency: {A} m (warp) × {B} m (weft), fabric {mass:.2f} kg/m², air on {a.sides} side(s), "
              f"C_a = {F.get('membrane.added_mass_coeff')} [{Ca_st}], ρ_air = {F.get('membrane.rho_air')} "
              f"[{F.status('membrane.rho_air')}]")
        if pw:
            f11, m_eff = panel_frequency(pw, pf, A, B, mass, a.sides)
            print(f"  m_eff = {m_eff:.2f} kg/m² (air {100 * (1 - mass / m_eff):.0f} %)  ->  f11 = {f11:.2f} Hz "
                  f"at prestress {pw}/{pf} kN/m (flat-panel lower bound; curvature raises it)")
            if a.sensitivity:
                res = F.sensitivity(lambda c: panel_frequency(pw, pf, A, B, mass, a.sides, c)[0],
                                    "membrane.added_mass_coeff")
                print(f"  sensitivity C_a: f11 = {res['u']:.2f} Hz at {res['value']}, {res['u_lo']:.2f} at "
                      f"{res['lo']}, {res['u_hi']:.2f} at {res['hi']}"
                      + (f" -> target {a.f_target} Hz {'met over the range' if min(res['u_lo'], res['u_hi']) >= a.f_target else 'DEPENDS on C_a'}"
                         if a.f_target else ""))
        else:
            _, m_eff = panel_frequency(1.0, 1.0, A, B, mass, a.sides)
        if a.f_target:
            ratio = (pw / pf) if pw else 1.0
            n_req = prestress_for_frequency(a.f_target, A, B, m_eff, ratio)
            print(f"  prestress for f11 ≥ {a.f_target} Hz: warp {n_req:.2f} / weft {n_req / ratio:.2f} kN/m"
                  + (f"  ({'OK' if pw >= n_req else 'RAISE prestress or reduce the panel span'})" if pw else ""))
        print("  No code gives a frequency limit: agree the target with the wind engineer (gusts, vortex "
              "shedding); flutter/aero-elastic checks need wind-tunnel data for large, flat panels.")

    if a.corner:
        R, th, r0 = a.corner
        n_all = min(allowable(fw, a.method, a.case, family, a.sf_short, a.sf_long, a.fm_combo)[0],
                    allowable(ff, a.method, a.case, family, a.sf_short, a.sf_long, a.fm_combo)[0])
        c = corner_check(R, th, r0, n_all, a.layers)
        eff = F.get("membrane.corner_ply_eff")
        print(f"\nCorner: R = {R} kN fanning over {th:g}° from r0 = {r0} m; base allowable {n_all:.2f} kN/m "
              f"(weaker direction, case '{a.case}', method '{a.method}')")
        print(f"  n(r0) = R/(θ·r0) = {c['n_r0']:.2f} kN/m vs {a.layers} plies: n_all·(1+(k−1)·{eff}) "
              f"[{F.status('membrane.corner_ply_eff')}] = {c['n_all_reinf']:.2f} kN/m -> util {c['u_r0']:.2f}"
              + ("  <-- FAIL: more plies or larger plate/clamp radius" if c['u_r0'] > 1 else "  OK"))
        rk = c["r_k"]
        print(f"  with {a.layers} plies the plate/clamp must reach r ≥ {rk[a.layers]:.2f} m"
              + ("" if rk[a.layers] <= r0 else f" (now {r0} m)") + "; ply k must extend to "
              + ", ".join(f"ply {k}: {rk[k - 1]:.2f} m" for k in range(a.layers, 1, -1))
              + f"; base fabric alone beyond {rk[1]:.2f} m")
        if a.sensitivity:
            print(F.sens_line("ply efficiency", F.sensitivity(
                lambda e: corner_check(R, th, r0, n_all, a.layers, e)["u_r0"], "membrane.corner_ply_eff")))
        print("  Radial-fan estimate (belt/strap force not included): check the belt, clamp plate bolts and "
              "the analysis stress at the corner; stagger the ply edges.")

    if a.nw is None and a.nf is None:
        return
    rows = point_utils(a.nw, a.nf, fw, ff, a.method, a.case, family, a.seam_eff, a.seam_dir, a.sf_short,
                       a.sf_long, a.fm_combo)
    worst = 0.0
    print(f"\nCheck — case '{a.case}' ({CASES[a.case]}-term), method '{a.method}'")
    print(f"{'item':<34}{'n [kN/m]':>10}{'n_all':>9}{'util':>7}  basis")
    for item, n, al, basis in rows:
        u = n / al
        worst = max(worst, u)
        print(f"{item:<34}{n:10.2f}{al:9.2f}{u:7.2f}  {basis}" + ("  <-- FAIL" if u > 1 else ""))
    if a.nmin is not None:
        print(f"{'no-slack (min principal stress)':<34}{a.nmin:10.2f}{'> 0':>9}"
              + ("   OK" if a.nmin > 0 else "   SLACK/WRINKLING -> check SLS appearance, flutter, ponding"))
    print(f"Governing utilisation {worst:.2f} -> {'OK' if worst <= 1 else 'NOT OK'}")
    if a.sensitivity:
        key = factor_key(a.method, a.case)
        given = a.sf_long if CASES[a.case] == "long" else a.sf_short
        if _unverified(key) and not (a.method == "factor" and given is not None):
            res = F.sensitivity(lambda v: max(n / al for _, n, al, _ in point_utils(
                a.nw, a.nf, fw, ff, a.method, a.case, family, a.seam_eff, a.seam_dir, a.sf_short, a.sf_long,
                a.fm_combo, {key: v})), key)
            print(F.sens_line(key.split(".")[-1], res))
        else:
            print(f"  sensitivity: method '{a.method}' uses no unverified factor here ([V]/[C] or user values)")
    print("Also check: tear propagation at critical defect, corner/clamp stress concentrations, "
          "ponding under deformed shape, strength at elevated temperature (seams).")
    return worst


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
