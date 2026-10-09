---
name: cable-tension-members
description: Steel cables and tension components for tensile fabric, cable-net and cable-stayed structures — spiral strand, full locked coil, stainless 1x19, wire rope, tension rods/bars (Macalloy, Pfeifer, Ronstan, Jakob, Carl Stahl). Use for catenary/sag-tension, edge-cable force (T = n·R), unstressed fabrication length at reference temperature, EN 1993-1-11 and ASCE 19 resistance checks, end terminations (sockets, swaged, forks), prestretching, corrosion protection, vibration and producing a cable schedule.
---

# Cables and tension members

Tags: [V] read in a named source (EN 1993-1-11:2006 + AC:2009 full text, datasheet or ETA — URL and quote in the
register `tensile-structures/reference/code_factors.json` or in the reference files), [C] code content an NA may
change, [U] typical value (has a `range` used by `--sensitivity`). Confirm every factor against the standard edition
(EN 1993-1-11:2026 has replaced 2006 in CEN) and the National Annex in force.

## Tools
All stdlib Python 3. Every sub-command prints its assumptions; code factors come only from the register via
`tensile-structures/scripts/factors.py` (`--factors project.json`, given before the sub-command, overrides them).

### `scripts/cable_calc.py`
```bash
python3 cable_calc.py sag    --L 20 --h 2 --w 0.05 --f 0.8 [--EA 17000]   # exact catenary (+ --H or --S instead of --f)
python3 cable_calc.py length --L 12 --w 1.8 --H 60 --EA 17000 --T-install 30 --T-ref 20 --fittings 420 [--creep]
python3 cable_calc.py edge   --chord 10 --sag 1.0 --n 3.0                  # T = n·R
python3 cable_calc.py resist --Fmin 537 --ke 0.9 --FEd 240 --Fser 170 --Fmin-force 12
python3 cable_calc.py resist --Fmin 367 --termination ferrule --FEd 125 --Fser 85 --sensitivity
python3 cable_calc.py irvine --L 20 --w0 0.1 --H0 50 --w1 1.0 --EA 20000 [--dT -30]
python3 cable_calc.py freq   --L 15 --T 80 --m 3.4 [--modes 3]
python3 cable_calc.py freq-tension --L 15 --m 3.4 --EA 20000 --f 1:2.75 --f 2:5.52 --f 3:8.30   # force from frequencies
python3 cable_calc.py rod    --d 36 --fy 460 --fu 610 --FEd 300 --d-shank 34 --As 792 --fitting-Rd 400
python3 cable_calc.py stress-turns --L 10 --EA 14000 --F1 5 --F2 20 --pitch 3.5 --w 0.02   # turnbuckle turns
python3 cable_calc.py clamp  --dT 12 --nb 2 --bolt-d 16 [--Fp 60 --mu 0.15 --retained 0.6 --Fperp 5] --sensitivity
python3 cable_calc.py saddle --T 400 --R 2.1 --d 40 --type FLC --delta 5 [--lined] --T2 380 --wrap 20 --Fr 100 --Fuk 1580
python3 ../../tensile-connections/scripts/fatigue_check.py --cable spiral_socket --spectrum 60:2e6   # fatigue
```
| Sub-command | Options | What it does |
|---|---|---|
| `sag` | `--L --h --w` + one of `--H/--f/--S`; `--EA` | exact catenary (w per arc length): H, sag, length, end forces; parabola line with the same H (w per horizontal m, exact arc length); unstressed length ∫ds/(1+T/EA) |
| `length` | `--L --h --w --H/--f --EA --alpha --T-install --T-ref --fittings --creep` | unstressed length ∫ds/(1+T/EA) of the loaded catenary, corrected to T_ref (α [V] 12e-6, stainless: `--alpha 16e-6`); `--creep` subtracts 0.15 mm/m [V, EN 3.2.2(3)] |
| `edge` | `--chord --sag --n` | edge cable T = n·R, R = c²/(8s) + s/2, end angle |
| `resist` | `--Fmin --ke`/`--termination {socket,swaged,ferrule,ubolt} --gammaR --Fk --FEd --Fser --fsls --bending-checked --Nf --asce --T-asce --Fmin-force --sensitivity` | EN 1993-1-11 eq. (6.2) F_Rd = min(F_uk/(1.5γR), F_k/γR), F_uk = F_min·k_e; SLS f_SLS·F_uk; ASCE 19 S_d ≥ 2.2T; no-slack |
| `irvine` | `--L --w0 --H0 --w1 --EA --dT --alpha` | change of H for a load change and/or ΔT (Irvine's cable equation), λ² |
| `freq` | `--L --T --m --modes` | taut-string frequencies; EN 8.3 vibration rules |
| `freq-tension` | `--L --m --f n:Hz (repeat) --EI --EA` | T (and EI) from measured frequencies; least squares over modes; `--EA` corrects symmetric modes for sag (Irvine) |
| `rod` | `--d --pitch --d-shank --As --fy --fu --FEd --fitting-Rd` | group A rod: min(A_g·f_y/γM0, k2·f_u·A_s/γM2) [C]; EN 1993-1-11 6.2 route for comparison; `--As` = supplier stress area |
| `stress-turns` | `--L --EA --F1 --F2 --pitch --thread {single,double} --k-sup --w` | ΔL = ΔF·(L/EA_sec + 1/k_sup), turns = ΔL/lead; `--w` = Ernst secant modulus |
| `clamp` | `--dT --nb --bolt-d --grade --surfaces --Fp --mu --retained --Fperp --sensitivity` | EN eq. (6.9): F_Rd = μ(n_s·n_b·F_p·k_ret + F⊥)/γM,fr; F_p = 0.7·f_ub·A_s [V] unless `--Fp` |
| `saddle` | `--T --R --d --type {FLC,OSS} --delta --E --lined --T2 --wrap --Fr --k-clamp --L2 --dprime --Fuk --sensitivity` | EN 6.3: radius R ≥ max(30d, 400δ) (20d lined); slip (6.6/6.7); clamping pressure q = F_r/(d′L2) ≤ q_Rk (Table 6.4); k·F_uk; Reuleaux σ_b; returns the indicative groove pressure ratio T/(R·d)/q_Rk |

- `--sensitivity` (resist, clamp, saddle; also `cable_schedule.py --sensitivity` for f_sls and
  `fatigue_check.py --cable … --sensitivity` for Δσ_C and m): repeats the check at both ends of each factor's
  `range` in the register and prints ROBUST or DEPENDS. Clamps also get a combined worst-case run.
- `freq-tension`: f_n² = n²T/(4mL²) + n⁴π²EI/(4mL⁴); with two or more modes T and EI are fitted; with `--EA` the odd
  modes are corrected with tan(ω̄/2) = ω̄/2 − (4/λ²)(ω̄/2)³, iterated on λ².

### `scripts/cable_schedule.py`
```bash
python3 cable_schedule.py schedule.json --out cable_schedule [--sensitivity] [--factors project.json]
python3 cable_schedule.py --from-model sail.json --envelope sail_cases_envelope.json [--envelope-sls sls.json] \
        --product Ronstan-ACS2-GS-17.0 --deduct 250 [--uls-factor 3 --sls-factor 2] --out sail_cables
python3 cable_schedule.py --list                                   # product library
```
Builds the fabrication schedule (CSV and Markdown) from a JSON list or a form-finding model. For each cable: EA,
pin-to-pin stressed length (node-to-pin deductions), **unstressed length at the reference temperature**
L0 = L_pin/(1 + F/EA)/(1 + αΔT), length under the measuring load, clamp marks, EN utilisation (γR = max(project,
product `gammaR_ETA`)), ASCE and SLS utilisation, slack check. `--envelope` takes ULS forces and minimum forces from
`run_cases.py`; without it the ULS/SLS forces are placeholders (factor × prestress).

Product data: `reference/cable_products.json` — 112 entries (Ronstan, steelwirerope.com Galfan/stainless OSS and FLC,
Teufelberger-Redaelli OSS/FLC/OSX/FLX, Pfeifer VVS 1, Carl Stahl I-SYS ETA, Macalloy 460), each with `source` URL and
a `status` (V: read in the datasheet/ETA; U: computed/estimate). Replace with the supplier's ETA for design.

## Key design rules
**Resistance (EN 1993-1-11 6.2)** [V]: `F_Rd = min{F_uk/(1.5·γR); F_k/γR}`, `F_uk = F_min·k_e` (group B).
γR = 1.00, or 0.90 with measures against bending at the anchorages (Table 6.2, NDP); ETAs use 1.0 (DIBt: not below
1.0); stainless strand ETAs may use 1.1. k_e (Table 6.3): metal/resin sockets 1.0, ferrule-secured eye 0.9, swaged
0.9, U-bolt grip 0.8 [V]; product ETAs can be lower (Carl Stahl stainless swaged 0.78–0.9 [V]).
Bars (group A, 6.1): EN 1993-1-1/1-8 route (`rod`). Manufacturer check: Pfeifer Z_R,d = Z_B,k/1.5 [V].

**ASCE/SEI 19** [V]: `S_d = S_n·N_f (or N_d) ≥ 2.2·T_n`. The older 2.0 factor with transient loads and any LRFD in 19-22 are [U].

**SLS (Tables 7.1/7.2)** [V, NDP]: f_SLS = 0.45 σ_uk, or 0.50 σ_uk when the fatigue design includes bending
stresses (`--bending-checked`). Construction: 0.60 σ_uk for the first components for a few hours, 0.55 σ_uk after the
others are installed. Prestretch non-prestretched cables cyclically up to 0.45 F_uk (3.2.2 NOTE 4) [V].
**No-slack:** F > 0 in every combination (with favourable prestress, temperature and length tolerance).

**Saddles (6.3)** [V]: R ≥ max(30d, 400δ), 20d with a ≥ 1 mm soft-metal/zinc bedding; then curvature stresses may be
neglected. Slip F1/F2 ≤ e^(μα/γM,fr) (with clamps: (F1 − k·F_r·μ/γM,fr)/F2, k = 2.0). Clamping pressure
q = F_r/(d′·L2) ≤ q_Rk (Table 6.4: FLC 40, spiral 25 N/mm² on steel; 100/60 cushioned). Saddle force 1.10·F_uk.
**Clamps (6.4.1)**: F_∥ ≤ μ(F_⊥ + F_r)/γM,fr, γM,fr = 1.65 [V]. EN gives **no μ**: slip test. 0.1 is a placeholder
[U, range 0.08–0.2]; retained preload 0.8 after re-tightening [U, range 0.45–0.8].
**Fatigue (Section 9)** [V]: Δσ_C = 150 (FLC and spiral strand with metal/resin sockets), 160 (parallel wires/strands),
105 (prestressing bars); slope 4 to 2×10⁶, then 6. Threaded rods: EN 1993-1-9 detail 14, category 50 with
(30/φ)^0.25. Palmgren–Miner with `fatigue_check.py`.

**Mechanics** (`reference/cable-mechanics.md`):
- Parabola (w per horizontal m): `H = wL²/(8f)`, `T_max = H√(1+16n²)`. Catenary (w per arc length): `y = a cosh(x/a)`,
  `a = H/w`. Same w and sag: H differs by ≈ 4n²/3 (2 % at f/L = 1/8), lengths by 0.03 %.
- Unstressed length: `S₀ = ∫ds/(1 + T/EA)`, then `/(1+αΔT)` to T_ref; α = 12×10⁻⁶ (16×10⁻⁶ stainless) [V].
- Edge cable: `T = n·R`, `R = c²/(8s) + s/2`. Sag about 8–12 % of chord [U, practice].
- Irvine for load and temperature changes; Ernst secant modulus for sagging stays; `f_n = n/(2L)·√(T/m)`.

**Moduli (EN Table 3.1, metallic area, first estimates)** [V]: spiral strand 150 ± 10 (stainless 130 ± 10; suppliers
quote 160 ± 10 for Galfan); FLC 160 ± 10; strand rope 100 ± 10 (fibre core 80 ± 10); parallel wires 205 ± 5;
parallel strands 195 ± 5 kN/mm². Bars 205–210 [U]. Fill factor f = A_m/(πd²/4) (Table 2.2) [V]: spiral 0.73–0.77,
FLC 0.81–0.88, strand rope 0.56; unit weight 83 kN/m³ incl. corrosion protection.

## Selection guidance
| Need | Choose |
|---|---|
| Edge, ridge and valley cables for PVC/PTFE canopies, 8–40 mm | Galfan OSS (swaged ≤ 36 mm, poured sockets above) |
| High stiffness, clamps and saddles, large forces, corrosion | Full locked coil (16–180 mm) |
| Small architectural cables, balustrades, visible stainless | 1x19 AISI 316 (lower E, higher α) |
| Short stiff ties, bracing, tie-backs with adjustment | Tension rod/bar (Macalloy 460/520, S460 stainless) |
| Bridge-type stays, fatigue-critical | Parallel wire/strand to PTI DC45.1 / fib 89 |

## Limitations
- `sag`/`length` treat one span between two pinned supports with uniform load per arc length; no point loads,
  clamps, saddles or support movement. Membrane-loaded edge cables need the form-finding/DR results, not `edge`
  alone (`edge` assumes uniform normal stress and a circular arc).
- `irvine` is the parabolic, level-support cable equation (≤ 0.3 % vs the exact elastic catenary for f/L ≤ 0.1);
  `stress-turns --w` uses Ernst's secant modulus (level chord, self-weight only).
- `freq-tension` assumes pinned ends, a uniform cable and a level chord; clamped ends, dampers and sockets shift the
  frequencies (the fitted EI absorbs part of it). Use measured lengths and masses incl. fittings.
- `resist` is the EN 1993-1-11 / ASCE 19 static check of the free length; anchorage, socket and fitting resistances
  come from the ETA. The ASCE line uses F_Ed/1.4 when `--T-asce` is not given.
- `clamp`/`saddle`: μ has no code value; the register μ and retained preload are placeholders ([U]) — test the
  clamp. The tool counts F_⊥ once and uses n_s friction surfaces for F_r. `saddle` returns the indicative groove
  pressure ratio for API compatibility; the EN checks are printed.
- `cable_schedule.py` treats each cable as straight (sag shortening and force variation along the cable neglected)
  and does not deduct creep, clamp seating or fitting tolerances; product data must be replaced by the supplier's
  certified values. Products without published metallic area use EN eq. (2.2) estimates (status U).
- Fatigue categories are for exposure classes 3–4 with Annex A sockets; bending at sockets/saddles needs tests.
- Validation of every path: `reference/validation.md`.

## References
- `reference/cable-types-and-standards.md`: types, product data, EN 1993-1-11 and ASCE 19 details, terminations, corrosion.
- `reference/cable-mechanics.md`: all formulas (catenary, parabola, Irvine, Ernst, T = nR, vibration) with worked examples.
- `reference/cable-fabrication.md`: prestretching, length measurement, tolerances, marking, schedule contents, installation and stressing.
- `reference/cable_products.json`: product library with sources.
- `reference/validation.md`: benchmark table (tool, case, reference, error) and the register verification log.

## Always
- Specify lengths as **pin-to-pin, unstressed (or under a stated measuring load), at a stated reference temperature**, for prestretched cable.
- Provide adjustment ≥ fabrication + erection tolerance plus membrane creep re-tensioning.
- Match fittings to the cable (fork jaw width = lug thickness + clearance; pin Ø from the supplier).
- Pass the printed assumptions and the model limitations on to the user.
