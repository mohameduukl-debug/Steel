# Membrane design criteria: codes, factors, loads, seams, details

## 1. Verification formats

### 1.1 Permissible stress / global stress factor (most common in practice)
`n_design ≤ f_tensile / SF`
* Fabric stress factors typically 4–8 [V, Gosling et al. 2018]; another source gives 5–10 for fabric versus 2.3–3 for cables, rods and webbing [V].
* Birdair: "usually 5" [V]; practice about 4 for short-term wind, 5–6 for long-term snow and prestress [U].
* Seams: use the lesser of seam and fabric strength (ASCE 55 "effective membrane breaking strength") [V].

### 1.2 FM Global DS 1-59 (Apr 2021), Table 2.2.6.1 [V]
Minimum SF on **new-fabric** strength (assumes ≥ 75 % retention, L_t = 0.75):

| Combination | SF |
|---|---|
| P + D | 8.0 |
| P + D + (L, S or R) | 5.0 |
| P + D + W | 5.0 |
| P + D + T | 5.0 |

With less retention, increase the factor proportionally. Against end-of-life strength these are about 6.0 and 3.7.

### 1.3 ASCE/SEI 55-16 (USA)
LRFD and ASD combinations; design strength = ultimate × strength reduction factor(s); life-cycle factor
**L_t = 0.75** for membranes, non-metallic cables and webbing retaining ≥ 75 % strength in permanent structures [V];
snow not reducible for melt systems on permanent structures [V]. Numeric factors in §4.5.2 [U]. Check the standard.

### 1.4 Japan: MLIT Notification 666 (2002)
Allowable stress 1/8 of strength long-term, 1/4 short-term; membrane classes A (glass/PTFE, non-combustible), B, C [U].

### 1.5 CEN/TS 19102:2023 (EU) and predecessor A-factors
Limit states to EN 1990. Resistance = characteristic strength / (γ_M × modification factors)
with **k_biax** (biaxial), **k_age** (ageing/environment), **k_dur,M** (load duration),
**k_temp** (temperature) [V names]. Annex A material classes, Annex B ageing tests, Annex C typical k values [V].
Exact formula and numbers: [U]. Read the TS.

German A-factor method (predecessor, Minte/Reinhardt) [U values]:
`f_d = f_tk / (γ_M · A0 · A1 · A2 · A3)`, γ_M ≈ 1.4; A0 (biaxial/size) ≈ 1.2; A1 (long-term) ≈ 1.6–1.7 PVC,
1.0–1.4 PTFE; A2 (ageing) ≈ 1.1–1.2; A3 (temperature ~70 °C) ≈ 1.1–1.2 PVC, 1.0–1.1 PTFE. Actions factored separately.
Combined this gives about 3.5–4 (short-term) and 5–7 (long-term snow), consistent with the stress-factor practice above.

Partial factors on actions: a reliability calibration for a PVC hypar recommends **γ_P = 1.0 with γ_S = γ_W = 2.0**,
or **γ_P = 1.2 with γ_S = γ_W = 1.5** [V, Eng. Struct. 214 (2020)]. The hanging (sag) direction under snow governs.

## 2. Load cases (analyse each combination non-linearly)
1. **Prestress P**: permanent but relaxes. Check both initial and relaxed prestress.
2. **Dead G**: small (fabric about 1–1.7 kg/m²), plus attached lighting and services.
3. **Wind W**: uplift (suction) and downward, several directions. EN 1991-1-4 and ASCE 7 have **no Cp for hypars
   or cones**. Use conservative canopy/vault values, TensiNet App. A1, published tunnel data or project
   tunnel/CFD [V]. Consider dynamic/aeroelastic response for large flexible roofs.
4. **Snow S**: uniform, drift, asymmetric (EN 1991-1-3 / ASCE 7), plus **ponding** of meltwater or rain in
   hollows. Ponding must be avoided: iterate with load following the deformed shape.
5. **Temperature T**: cables (α = 12e-6 carbon, 16e-6 stainless) and strength reduction at high temperature.
6. **Installation**: partial or unbalanced prestress stages; PTFE folding damage.

Combinations: P+G; P+G+S; P+G+W↓; P+G+W↑; P+G+S+ψW; P+G+W+ψS; P+G+T; SLS versions for ponding, deflection and slack.

## 3. Serviceability
* No slack (zero principal stress) under SLS in large areas, otherwise wrinkling/flutter risk [U threshold].
* No universal deflection limit. Criteria are clearance (ASCE 55 §6.10), ponding, drainage and appearance.
* Minimum slope about 15° often quoted [V]; 5–10° possible when checked on the deformed shape [U].

## 4. Seams, edges and reinforcement
* Seams follow geodesic lines, warp aligned with the main load path. Seam width by material: PVC 40–60 mm
  (Types IV–V 50–80), PTFE 50–75 mm (75–100 high grades) [V/U].
* Seam testing: strip tensile at 23 °C and at elevated temperature (about 70 °C for PVC [U]), long-term seam
  creep tests (German practice) [U]. Log welding parameters.
* Corners: 1–3 extra doubler plies extending about 0.5–1.0 m, radial or aligned with the bisector [U]; belts continue into the corner plate.
* Edges: cable pocket or belt; for PTFE prefer clamp plates on external cables (see `tensile-connections`).
* Membrane belts: polyester webbing, stress factor about 2.3–3 on belts/cables [V range], textile factor 3–6 for webbing [U].

## 5. Fire, durability, UV, soiling
| Material | Fire | Life |
|---|---|---|
| glass/PTFE | A2-s1,d0; ASTM E136 base | 25–35+ |
| ETFE | B-s1,d0 | 30+ [U] |
| PES/PVC | B-s2,d0 to B-s1,d0; NFPA 701 / E84 | 15–25 [U] |
| silicone/glass | A2 or B | 20–30 |
PVC and ETFE melt away and vent in fire [U]. PTFE seams lose 60–73 % of strength at 250 °C (fabric only about 12 %) [V].
Self-cleaning: PTFE, ePTFE, ETFE. PVC depends on the topcoat.

## 6. Design check sequence
1. Get warp/weft stresses per factored combination from the non-linear analysis.
2. Pick the design basis (project spec): `membrane_check.py --method …`.
3. Check fabric warp and weft, and seams in the direction that crosses them.
4. Check corners and clamp lines with a stress-concentration factor or a local FE model.
5. Check tear propagation (critical defect length) for high-stress zones.
6. SLS: slack areas, ponding, clearances.
