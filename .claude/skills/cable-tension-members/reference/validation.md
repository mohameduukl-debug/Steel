# Validation of the cable tools

Every computational path of `scripts/cable_calc.py` and `scripts/cable_schedule.py` is checked against an
independent reference in `tests/test_cable_tension_members.py` (run: `python3 -m unittest
tests.test_cable_tension_members -v`). "Exact elastic catenary" means the closed-form span equation of Irvine,
*Cable Structures* (MIT Press 1981, Dover 1992), §2: `span = H·L0/EA + (2H/w0)·asinh(W/(2H))` for level supports,
solved by an independent bisection in the test.

| Tool / path | Case | Reference + source | Expected | Obtained | Error | Tolerance |
|---|---|---|---|---|---|---|
| `sag` (solve_H, Catenary) | L = 20 m, w = 0.05 kN/m, f = 0.8 m | level catenary closed form f = a(cosh(L/2a) − 1), S = 2a·sinh(L/2a), T = H + w·f (Irvine 1981 Ch. 1) | H 3.13164, S 20.08508, T 3.17164 | same | < 1e-15 | 1e-7 |
| `sag` (Catenary.T) | inclined, h = −3, 4, 10 m | T_B − T_A = w·h (catenary property, Irvine Ch. 1) | w·h | same | < 1e-12 | 1e-9 |
| `sag` (parabola_length) | L = 30 m, n = 0.125 | exact arc (L/2)√(1+16n²) + (L/8n)·asinh(4n); inclined: Simpson integral of √(1+y′²) | 31.20686 m | 31.20686 m | 1e-16 | 1e-9 |
| `sag` catenary vs parabola | same span/sag/w, n = 0.05 / 0.1 / 0.125 / 0.2 | series H_cat/H_par ≈ 1 + 4n²/3 (expansion of the two closed forms) | 1.0033 / 1.0133 / 1.0208 / 1.0533 | 1.0033 / 1.0131 / 1.0202 / 1.0494 | ≤ 0.4 % (series truncation) | 15 % of 4n²/3 |
| `sag` catenary vs parabola length | same, n = 0.125 / 0.2 | O(n⁴) difference | — | +0.028 % / +0.14 % | — | 0.14 % |
| `sag`/`length` (stretch) | 12 m, H 60, EA 17 000; 25 m inclined | ∫T/EA ds = (H/EA)[x/2 + (a/4)sinh(2(x−x0)/a)] | 42.81 mm | 42.81 mm | 1e-12 | 1e-9·L |
| `length` (unstretched) | L = 12 m, w = 1.8, H = 60, EA = 17 000 | exact elastic catenary L0 with the same total weight (Irvine §2) | 12.022244 m | 12.022243 m | 0.001 mm | 0.01 mm |
| `length` (temperature) | same, installed 30 °C, T_ref 20 °C | L0/(1 + αΔT), α = 12e-6 (EN 1993-1-11 3.3) | 12.020802 m | 12.020801 m | 0.001 mm | 0.01 mm |
| `length` (straight member) | 10 m, F = 50 kN, EA = 20 000, ΔT = 15 K | L0 = L/(1 + F/EA)/(1 + αΔT) (Hooke) | 9.9732672 m | 9.9732672 m | 2e-14 m | 1e-8 m |
| `length --creep` | same | −0.15 mm/m (EN 1993-1-11 3.2.2(3) NOTE 1) | ×(1 − 1.5e-4) | same | 0 | 1e-9 |
| `edge` | c = 10 m, s = 1 m, n = 3 kN/m (+3 more) | arc equilibrium 2T·sin φ = n·c with tan(φ/2) = 2s/c (independent geometry) | 39.000 kN | 39.000 kN | 0 | 1e-9 rel |
| `edge` shallow limit | c = 20, s = 0.5 | parabola H = n·c²/(8s) | 300 kN | 300.75 kN | 0.25 % | 1 % |
| `irvine` (load change) | L 20, w0 0.1 → w1 1.0, H0 50, EA 20 000 (λ² = 0.64) + 2 more | Irvine (1981) Ch. 3 cubic h*³ + (2+λ²/24)h*² + (1+λ²/12)h* − (λ²/12)w*(1+w*/2) = 0 | 89.9013 kN | 89.9013 kN | < 1e-9 | 1e-7 rel |
| `irvine` limits | λ² → ∞; w = 0 with ΔT = −20 K | inextensible: H ∝ w; restrained bar: H = H0 − EA·α·ΔT | 150.0 / 54.8 kN | 150.0 / 54.8 kN | < 1e-7 | 1e-5 |
| `irvine` vs exact | 4 cases, f/L 0.005–0.1, ΔT −30…+20 K | exact elastic catenary with same unstrained length (+αΔT) and total load | e.g. 107.204 kN | 107.484 kN | ≤ 0.26 % | 0.4 % |
| `freq` | L 15, T 80 kN, m 3.4 kg/m | taut string f_n = n/(2L)√(T/m) (Irvine Ch. 4) | 5.11310 Hz | 5.11310 Hz | 0 | 1e-12 |
| `freq-tension` (Irvine roots) | λ² → ∞; λ² = 4π², 16π²; λ² = 0.01 | roots of tan x = x: 4.493409457909064, 7.725251836937707 (Abramowitz & Stegun Table 4.19); crossovers ω̄ = 2kπ at λ² = 4k²π² (Irvine & Caughey 1974); expansion π + 4λ²/π³ | 8.986819 / 2π / 4π / 3.142883 | same | ≤ 4e-11 / 0 / 0 / 3e-7 | 1e-6 / 1e-9 / 1e-5 |
| `freq-tension` (beam-string) | L 15, m 3.4, T 50 kN, EI 3000 N·m² | hinged beam-string f_n = n/(2L)√(T/m)√(1 + n²π²EI/(TL²)) | T 50.000, EI 3000 | same | < 1e-9 | 1e-6 |
| `freq-tension --EA` (sag) | H 30 kN, L 30 m, m 4 kg/m, λ² = 2.05 | frequencies from Irvine's theory (symmetric roots, antisymmetric 2nπ) | 30.000 kN | 30.000 kN (string-only mode 1: 35.0) | 1e-8 | 1e-4 |
| `resist` | F_uk 240 / 1520 / 1615 / 10 075 kN, sockets | Teufelberger-Redaelli Cable System catalogue (metric) F_Rd = (F_uk/1.5)/γR: 160 / 1013 / 1077 / 6717 kN | as listed | 160.0 / 1013.3 / 1076.7 / 6716.7 | ≤ 0.4 kN (rounding) | 0.5 kN |
| `resist` γR = 1.1 | OSX 40 stainless, F_uk 1385 | same catalogue: F_Rd 839 (= F_uk/1.65) | 839 | 839.4 | 0.4 kN | 0.5 kN |
| `resist` k_e | Galfan OSS 20 mm swaged / 40 mm socketed | steelwirerope.com OSS datasheet 'Design Load' 245 / 967 kN (MBL 408 / 1450, k_e 0.9 / 1.0, EN Table 6.3) | 245 / 967 | 244.8 / 966.7 | 0.2 / 0.3 kN | 0.5 kN |
| `rod` (stress area) | M16–M39 | ISO 898-1 nominal stress areas (optimas.com table): 157, 245, 353, 561, 817, 976 mm² | as listed | 156.7 … 975.8 | ≤ 0.21 % | 0.6 % |
| `rod --As` | Macalloy 460 M30 / M36 / M48 / M64 | Macalloy Tension Structures data sheet V4.9 Table 3 'Design Resistance to EC3': 238 / 348 / 630 / 1149 kN | as listed | 237.6 / 347.8 / 630.0 / 1149.1 | ≤ 0.4 kN | 1 kN |
| `stress-turns` | straight cable | ΔL = ΔF·L/EA, lead 2·pitch | 10.71 mm / 1.53 turns | same | 0 | 1e-12 |
| `stress-turns --w` (Ernst) | (10 m, 0.02 kN/m, 5→20 kN), (30, 0.05, 10→40), (20, 0.1, 5→30) | exact elastic catenary L0(F1) − L0(F2) at fixed span | 11.32 / 71.22 / 154.74 mm | 11.34 / 71.37 / 154.63 mm | +0.17 / +0.21 / −0.07 % | 0.3 % |
| `clamp` | 4 bolts × 60 kN, μ 0.2, 2 surfaces, retained 0.25 / 0.55, γ 1.65 | Sun et al. 2025 (Sci. Rep. 15, doi:10.1038/s41598-025-89571-3), T/CECS 1010-2022 worked values 14.55 / 32 kN | 14.55 / 32.0 | 14.545 / 32.000 | 0.005 kN | 0.01 kN |
| `clamp` | 4 × 30.6 kN effective, μ 0.1, 1 surface | same paper, EN 1993-1-11 eq. (6.9) worked value 7.418 kN | 7.418 | 7.418 | 2e-4 kN | 1e-3 kN |
| `clamp` (preload) | M16 / M20 / M24 8.8 | EN 1993-1-8 eq. (3.7) F_p,C = 0.7·f_ub·A_s | 87.92 / 137.2 / 197.68 kN | same | 0 | 0.01 kN |
| `saddle` | T 400, R 2.1 m, d 40, δ 5, T2 380, α 20°, F_r 100 | EN 1993-1-11 6.3.1(2)/(3) R_min = max(30d, 400δ) / 20d; eq. (6.7) slip; eq. (6.8) q = F_r/(d′L2); Reuleaux σ_b = Eδ/D (Feyrer, *Wire Ropes*) — hand calculation | R_min 2000 / 800 mm, util slip 0.9994, q 3.41 N/mm², σ_b 190.5 MPa | same | < 1e-9 | 1e-9 |
| `cable_schedule.py` | cable EC-1 of `examples/schedule_example.json` | hand calculation: EA = 160 × 238.0 = 38 080 kN; L_pin = 10.62 − 0.50 = 10.120 m; L0 = L_pin/(1 + 18/EA)/(1 + 12e-6·8) | L0 10.11425 m, marks 2.2487 / 4.7473 / 7.2459 m, L(F_meas) 10.11903 m, F_Rd 244.7 kN, utils 0.388 / 0.360 / 0.363 | 10.1142, same marks, 10.1190, 244.7, same | < 0.05 mm (4-decimal rounding) | 0.05 mm |
| `cable_schedule.py` stressing | EC-1, 5 → 18 kN, M20 turnbuckle (pitch 2.5) | ΔL = 13 × 10.12/38 080 = 3.455 mm → 0.691 turns | 0.691 | 0.691 | < 1e-9 | 1e-3 |
| `cable_schedule.py` γR from ETA | Redaelli OSX 40 | catalogue F_Rd 839 kN (γR 1.1) | 839 | 839.4 | 0.4 kN | 0.5 kN |
| `cable_schedule.py --from-model/--envelope` | 2 segments 3 m @ 10 kN + 7 m @ 20 kN | length-weighted mean 17 kN, sum 10 m, envelope max/min copied | 10.0 m, 17.0, 60.0, 40.0; 55.0 / 3.33 | same | 0 | exact |
| `cable_products.json` (112 entries) | every entry | EN 1993-1-11 Table 2.2 fill factors (spiral 0.73–0.77, FLC 0.81–0.88; margin for supplier data) and unit weight 83 kN/m³ (eq. 2.1); Table 3.1 moduli (spiral 150 ± 10, suppliers 160 ± 10; stainless 130 ± 10; FLC 160 ± 10); F/A within the rope-wire strength range; published EA, F_uk, F_Rd and EC3 N_Rd reproduced | — | all pass | mass ≤ 12 %, EA ≤ 3.5 %, F_Rd ≤ 1 kN + 0.2 % | — |
| `cable_products.json` stainless 1x19 | 6 / 8 / 10 / 12 mm | F_min = A_m·R_m·k_s (Carl Stahl ETA-10/0358 Annex 2) vs Ronstan's published 29.7 / 52.8 / 82.6 / 119 kN | as listed | 29.7 / 52.8 / 82.5 / 118.7 | ≤ 0.2 % | 0.3 % |

Notes
- The catenary/parabola comparison corrects an earlier statement: at f/L = 1/8 the horizontal force and T_max of a
  catenary (w per arc length) and a parabola (w per horizontal metre) with the same w and sag differ by about 2 %
  (1 % at f/L ≈ 1/11); their lengths differ by only 0.03 %.
- `length` now integrates ∫ds/(1 + T/EA) (exact for linear-elastic strain). The former first-order S − ∫T/EA ds was
  0.15 mm short on the 12 m example (worked example now 12.0208 m instead of 12.0206 m).
- `saddle` returns p/q_Rk with p = T/(R·d) for backward compatibility; this is indicative only. EN 1993-1-11 6.3.3
  NOTE says the pressure from F_Ed is covered by the radius rule; q_Rk (Table 6.4) applies to the clamping force F_r.

## Verification log (register values, October 2026)

Sources found and read:
1. **EN 1993-1-11:2006 + AC:2009, full English text**. Read: Table 2.2, 3.1, 3.3, 3.4, 6.2
   (eq. 6.2–6.5, Tables 6.1–6.3), 6.3 (Fig. 6.1, radius rules, eq. 6.6–6.8, Table 6.4, 6.3.4), 6.4, 7 (Tables 7.1,
   7.2), 8.3, 9 (Fig. 9.1, Table 9.1). Quotes:
   - Table 6.3: "Ferrule-secured eye 0,9 … Swaged socket 0,9 … U-bolt grip 0,8 *) For U-bolt grip a reduction of
     preload is possible." → `cable.ke_ferrule`, `cable.ke_ubolt` U → V.
   - 6.3.1(2): "The radius r1 of the saddle should not be less than the greater of 30d or r1 ≥ 400⌀"; (3) "may be
     reduced to 20d when the bedding … is coated with soft metal or zinc spray with a minimum thickness of 1 mm" →
     `cable.saddle_min_R_over_d` 20 [U] → 30 [V]; new `saddle_min_R_over_d_lined` 20, `saddle_min_R_over_wire` 400.
   - 6.3.4 NOTE: "The value of k = 1,10 is recommended" → new `cable.saddle_k`.
   - 6.4.1 NOTE 1 / 6.3.2 NOTE: "γM,fr = 1,65 is recommended" (confirms `clamp_gamma`).
   - Table 7.1: "First tension components for only a few hours 0,60 σuk; After instalment of other tension
     components 0,55 σuk"; Table 7.2: "Fatigue design including bending stresses 0,50 σuk; … without bending stresses
     0,45 σuk" → `f_const_install`, new `f_const_after`, `f_sls`, `f_sls_bending_checked` C → V.
   - Table 9.1: "Prestressing bars 105; Fully locked coil rope with metal or resin socketing 150; Spiral strands with
     metal or resin socketing 150; Parallel wire strands with epoxy socketing 160; Bundle of parallel strands 160;
     Bundle of parallel wires 160"; Figure 9.1: slope 1:4 to Δσc at 2×10⁶, then 1:6 → `fatigue_cables.*` U → V
     (+ `dsC_prestressing_bar`, `m2_rope`, `N_knee_rope`).
   - 3.3(1): αT = 12×10⁻⁶ (steel wires), 16×10⁻⁶ (stainless wires); 3.2.2(3) NOTE 1: creep "additional shortening
     of 0,15 mm/m"; Table 3.1 moduli; Table 2.2 fill factors and unit weight.
2. **EN 1993-1-9:2005 full text**,
   Table 8.1 detail 14: "Bolts and rods with rolled or cut threads in tension", category 50, size effect
   ks = (30/φ)^0.25 for φ > 30 mm → `dsC_threaded_bar` U → V (range 37–50 = size effect M30…M100).
3. **EN 1993-1-8:2005 full text**,
   3.9.1(2) eq. (3.7) F_p,C = 0,7·f_ub·A_s → new `cable.clamp_preload_factor` (was hard-coded).
4. **Sun et al. 2025**, Sci. Rep. 15, s41598-025-89571-3 (https://www.nature.com/articles/s41598-025-89571-3):
   quotes T/CECS 1010-2022 "φ_B is the high-strength bolt reduction factor, take 0.25–0.55" and "comprehensive
   friction coefficient … the outer bare sealing cable is 0.2"; "the loss rate of the initial tightening force of
   high-strength bolts is 49%"; uses μ = 0.1 and γM,fr = 1.65 with EN eq. (6.9).

Still [U] (no code value exists; evidence gives a range, covered by `--sensitivity`):
- `cable.clamp_mu` 0.1, range 0.08–0.2. EN 1993-1-11 defines μ but gives no value (slip test, Annex A). Chinese
  T/CECS 1010-2022 uses 0.2 (bare sealing cable), JTG/T D65-05 0.15, tests on cast-steel clamps 0.30–0.46
  (Ruan 2019). Not upgraded: no European source and strong dependence on coating (Galfan/zinc lowers it).
- `cable.clamp_loss` 0.8 (re-tightened), range widened from 0.7–0.9 to 0.45–0.8: T/CECS 1010-2022 φ_B 0.25–0.55
  without re-tightening. The default stays 0.8 because the SKILL requires re-tightening after stressing and the
  shared regression test pins it; projects without re-tightening should set 0.45–0.5 in a project factor file.
- Not found despite searching: the German NA/DIBt fatigue categories for spiral strand (only the BASt FLC-hanger
  value 112 N/mm², kept as the low end of the `dsC_spiral_socket` range), a public prEN 1993-1-11:2023 draft
  (Steel Construction 2021, doi:10.1002/stco.202100009 reports a revised FLC S-N curve), the Bridon-Bekaert
  Structural Systems catalogue (university mirror unreachable), and Jakob 1x19 tables (catalogue only as images).
