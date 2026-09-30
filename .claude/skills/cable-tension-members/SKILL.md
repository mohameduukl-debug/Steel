---
name: cable-tension-members
description: Steel cables and tension components for tensile fabric, cable-net and cable-stayed structures — spiral strand, full locked coil, stainless 1x19, wire rope, tension rods/bars (Macalloy, Pfeifer, Ronstan, Jakob, Carl Stahl). Use for catenary/sag-tension, edge-cable force (T = n·R), unstressed fabrication length at reference temperature, EN 1993-1-11 and ASCE 19 resistance checks, end terminations (sockets, swaged, forks), prestretching, corrosion protection, vibration and producing a cable schedule.
---

# Cables and tension members

## Tools
### `scripts/cable_calc.py`
```bash
python3 cable_calc.py sag    --L 20 --h 2 --w 0.05 --f 0.8 [--EA 17000]   # exact catenary + parabola check
python3 cable_calc.py length --L 12 --w 1.8 --H 60 --EA 17000 --T-install 30 --T-ref 20 --fittings 420
python3 cable_calc.py edge   --chord 10 --sag 1.0 --n 3.0                  # T = n·R
python3 cable_calc.py resist --Fmin 537 --ke 0.9 --FEd 240 --Fser 170 --Fmin-force 12
python3 cable_calc.py irvine --L 20 --w0 0.1 --H0 50 --w1 1.0 --EA 20000 [--dT -30]
python3 cable_calc.py freq   --L 15 --T 80 --m 3.4
python3 cable_calc.py clamp  --dT 12 --nb 2 --bolt-d 16             # cross / edge clamp slip resistance
python3 cable_calc.py saddle --T 400 --R 0.6 --d 40 --type FLC [--lined]   # transverse pressure, R/d, wire bending
python3 cable_calc.py rod    --d 30 --fy 460 --fu 610 --FEd 180 --fitting-Rd 250   # group A tension rod
python3 cable_calc.py freq-tension --L 15 --m 3.4 --EA 20000 --f 1:2.75 --f 2:5.52 --f 3:8.30   # force from frequencies
python3 cable_calc.py stress-turns --L 10 --EA 14000 --F1 5 --F2 20 --pitch 3.5 --w 0.02   # turnbuckle turns
python3 cable_calc.py resist --Fmin 367 --termination ferrule --FEd 125 --Fser 85 --sensitivity
python3 ../../tensile-connections/scripts/fatigue_check.py --cable spiral_socket --spectrum 60:2e6   # fatigue
```
- `rod`: EN 1993-1-11 group A bars are designed to EN 1993-1-1/1-8. N_t,Rd = min(A_g·f_y/γM0, k2·f_u·A_s/γM2),
  with A_s = π/4·(d − 0.9382P)² (ISO 898-1) and k2 = 0.9 [C]. The EN 1993-1-11 route min(F_k/γR, F_uk/(1.5γR)) is
  printed for comparison, and a supplier fitting capacity can be added. f_y and f_u are product data.
- `freq-tension`: cable force from measured frequencies (lift-off or jack readings can be checked this way).
  f_n² = n²T/(4mL²) + n⁴π²EI/(4mL⁴). With two or more modes it fits T and EI by least squares; with `--EI` it solves
  each mode. With `--EA`, the symmetric (odd) modes are corrected for sag with Irvine's equation
  tan(ω̄/2) = ω̄/2 − (4/λ²)(ω̄/2)³, iterated on λ². Tests: exact recovery of T and EI, and Irvine's crossover
  ω̄ = 2π at λ² = 4π².
- `stress-turns`: ΔL = ΔF·(L/EA_sec + 1/k_sup) and turns = ΔL/lead, where lead = 2·pitch for a left/right-hand
  turnbuckle. `--w` applies Ernst's secant modulus EA/(1 + (wL)²(F1+F2)EA/(24F1²F2²)) for a sagging cable.
- `--sensitivity` (resist, clamp, saddle; also `cable_schedule.py --sensitivity` for f_sls and
  `fatigue_check.py --cable … --sensitivity` for Δσ_C and m): repeats the check at both ends of each uncertain
  factor's range (`range` in the register) and prints ROBUST or DEPENDS. Clamps also get a combined
  worst-case run.

### `scripts/cable_schedule.py`
Builds the fabrication schedule (CSV and Markdown) from a JSON list, or straight from a
form-finding model (`--from-model sail.json`). For each cable it gives:
- EA
- pin-to-pin stressed length (node-to-pin deductions applied)
- **unstressed length at the reference temperature**
- length under the measuring load
- clamp marks
- EN and ASCE utilisation
- slack check

Product data comes from `reference/cable_products.json` (tagged by source; replace it with the supplier's ETA).

## Key design rules
**Resistance (EN 1993-1-11, ETA/EAD route)** [V]:
`F_Rd = F_uk / (1.5·γR)`, where `F_uk = F_min · k_e`. γR = 1.0 (not less, per EAD; NA Table 6.2).
Bars also get `F_k/γR` (0.2 % proof) or EN 1993-1-1/1-8 threaded-section checks.
k_e: metal/resin sockets 1.0; swaged 0.9 [V]; ferrules 0.9, U-bolt grips 0.8 [U] (`--termination` reads them).
γR = 0.90 is allowed only with anchorage measures against bending from cable rotation (7.1(4)); ETAs use 1.0.
Manufacturer check: Pfeifer Z_R,d = Z_B,k/1.5 (γR = 1.0) [V].

**ASCE/SEI 19** [V]: `S_d = S_n·N_f (or N_d) ≥ 2.2·T_n`. The older 2.0 factor with transient loads, and any LRFD in 19-22, are [U].

**Clamps and saddles:** slip resistance F_∥ ≤ μ(F_⊥ + F_r)/γM,fr, computed as
F_Rd = n_s·μ·n_b·F_p,C·k_loss/γM,fr with F_p,C = 0.7·f_ub·A_s. γM,fr = 1.65 [V]. EN 1993-1-11 gives **no default μ**,
so determine it by a slip test. 0.1 is a conservative placeholder [U] (literature 0.15–0.2).
Saddle pressure p = T/(R·d) is checked against the EN 1993-1-11 Table 6.4 q_Rk without tests [C]: FLC 40 N/mm²
(lined 100) and spiral strand 25 (lined 60). The saddle is designed for k·F_uk (k is an NDP). Also checked: the R/d
minimum [U] and outer-wire bending σ_b = E·δ/(2R) (Reuleaux upper bound).
**Fatigue:** Palmgren–Miner with `fatigue_check.py` (EN 1993-1-9 curve for steel details; single-slope cable curve).

**SLS (EN 1993-1-11 Table 7.2)** [C]: f_SLS = 0.45 σ_uk by default, or 0.50 σ_uk when fatigue including bending
stresses is verified (`--bending-checked`). The condition wording comes from one snippet of the standard, so confirm it.
Installation limit f_const = 0.60/0.55 σ_uk (Table 7.1, by phase). Prestretch cyclically to about 0.45–0.55 F_uk.
**No-slack:** F > 0 in every combination (with favourable prestress, temperature and length tolerance).

**Mechanics:**
- Parabola (w per horizontal m): `H = wL²/(8f)`, `T_max = H√(1+16n²)`, `S ≈ L_c + 8f²/(3L_c)`.
- Catenary (w per arc length): `y = a cosh(x/a)`, `a = H/w`.
- Unstressed length: `S₀ = S − ∫T/EA ds`, then correct to T_ref: `/(1+αΔT)`.
- Edge cable: `T = n·R`, `R = c²/(8s) + s/2`. Sag about 8–12 % of chord.
- Irvine for load and temperature changes; Ernst equivalent modulus for sagging stays; string frequency `f_n = n/(2L)·√(T/m)`.
- Force from frequencies: `T = 4mL²f_n²/n² − n²π²EI/L²`. Symmetric modes read high on sagging cables, so use mode 2
  or the Irvine correction.

**Moduli (on metallic area, prestretched)** [V/U]: spiral strand 150–160 kN/mm² (suppliers quote 160 ± 10);
FLC 160 ± 10; IWRC strand rope ≈ 100 ± 10; stainless 1x19 ≈ 127 (Ronstan); bars 205–210.
α = 12×10⁻⁶ /K (carbon), 16×10⁻⁶ /K (stainless).

**Fill / area factor A/d²** [U]: OSS ≈ 0.58–0.61; FLC ≈ 0.66–0.70; 6x36 IWRC ≈ 0.52–0.55.

## Selection guidance
| Need | Choose |
|---|---|
| Edge, ridge and valley cables for PVC/PTFE canopies, 8–40 mm | Galfan OSS (swaged ≤ ~36 mm, poured sockets above) |
| High stiffness, clamps and saddles, large forces, corrosion | Full locked coil (20–180 mm) |
| Small architectural cables, balustrades, visible stainless | 1x19 AISI 316 (lower E, higher α) |
| Short stiff ties, bracing, tie-backs with adjustment | Tension rod/bar (Macalloy 460/520, S460 stainless) |
| Bridge-type stays, fatigue-critical | Parallel wire/strand to PTI DC45.1 / fib 89 |

## References
- `reference/cable-types-and-standards.md`: types, product data, EN 1993-1-11 and ASCE 19 details, terminations, corrosion.
- `reference/cable-mechanics.md`: all formulas (catenary, parabola, Irvine, Ernst, T = nR, vibration) with worked examples.
- `reference/cable-fabrication.md`: prestretching, length measurement, tolerances, marking, schedule contents, installation and stressing.
- `reference/cable_products.json`: product library.

## Always
- Specify lengths as **pin-to-pin, unstressed (or under a stated measuring load), at a stated reference temperature**, for prestretched cable.
- Provide adjustment ≥ fabrication + erection tolerance plus membrane creep re-tensioning.
- Match fittings to the cable (fork jaw width = lug thickness + clearance; pin Ø from the supplier).
