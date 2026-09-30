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
```
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
k_e: metal/resin sockets 1.0; swaged 0.9 [V]; ferrules 0.9, U-bolt grips 0.8 [U].
Manufacturer check: Pfeifer Z_R,d = Z_B,k/1.5 (γR = 1.0) [V].

**ASCE/SEI 19** [V]: `S_d = S_n·N_f (or N_d) ≥ 2.2·T_n`. The older 2.0 factor with transient loads, and any LRFD in 19-22, are [U].

**SLS:** keep the characteristic force around ≤ 0.45–0.50 F_uk (NA Table 7.1/7.2) [U numbers]. Prestretch cyclically to ~0.45–0.55 F_uk.
**No-slack:** F > 0 in every combination (with favourable prestress, temperature and length tolerance).

**Mechanics:**
- Parabola (w per horizontal m): `H = wL²/(8f)`, `T_max = H√(1+16n²)`, `S ≈ L_c + 8f²/(3L_c)`.
- Catenary (w per arc length): `y = a cosh(x/a)`, `a = H/w`.
- Unstressed length: `S₀ = S − ∫T/EA ds`, then correct to T_ref: `/(1+αΔT)`.
- Edge cable: `T = n·R`, `R = c²/(8s) + s/2`. Sag about 8–12 % of chord.
- Irvine for load and temperature changes; Ernst equivalent modulus for sagging stays; string frequency `f_n = n/(2L)·√(T/m)`.

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
