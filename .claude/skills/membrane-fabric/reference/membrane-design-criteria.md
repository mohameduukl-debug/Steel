# Membrane design criteria: codes, factors, loads, seams, details

Tags: **[V]** = confirmed from the named source (URL and quote in `verification-log.md`); **[C]** = standard clause or
recommended value, the National Annex may differ; **[U]** = typical practice value, not verified, with a `--sensitivity`
range. Short source keys: **[JRC23]** = JRC132615 (2023) *Prospect for European Guidance for the Structural Design of
Tensile Membrane Structures*; **[JRC25]** = Mollaert & Stimpfle, CEN/TS 19102 slides, JRC workshop June 2025;
**[MLIT666]** = Japanese MLIT Notification 666. Full references are in `validation.md`.

## 1. Verification formats (`membrane_check.py --method …`)

### 1.1 Global stress factor (`factor`, default)
`n_char ≤ f / SF` on CHARACTERISTIC load effects.
* SF 4.0 short-term (wind) and 5.0 long-term (snow, prestress) [V, ASCE 55-10 "current industry practice"; Birdair
  "usually 5"]. P + D alone: 8.0 [V].
* Fabric stress factors in the literature: 4–8 [V, Gosling et al. 2018]. Another source gives 5–10 for fabric and
  2.3–3 for cables, rods and webbing [V].
* A global factor of 5 on the mean strength was used in the [JRC25] hypar comparison (utilisation 0.69–0.80) [V].
* Seams: use the lesser of seam and fabric strength (ASCE 55 "effective membrane breaking strength") [V].

### 1.2 FM Global DS 1-59 (Apr 2021), Table 2.2.6.1 (`fm`) [V]
Minimum SF on **new-fabric** strength. It assumes at least 75 % strength retention (L_t = 0.75):

| Combination | SF |
|---|---|
| P + D | 8.0 |
| P + D + (L, S or R) | 5.0 |
| P + D + W | 5.0 |
| P + D + T | 5.0 |

With less retention, increase the factor proportionally. Against end-of-life strength these are about 6.0 and 3.7.

### 1.3 ASCE/SEI 55-16 (USA)
LRFD and ASD combinations; design strength = ultimate × strength reduction factor(s).
* Life-cycle factor L_t = 0.75 for membranes, non-metallic cables and webbing that keep at least 75 % of their strength
  in permanent structures [V].
* Snow may not be reduced for melt systems on permanent structures [V].
* The numeric factors in §4.5.2 are [U]: check the standard.
* The biaxial test of ASCE 55-10 uses the ratios 1:1, 2:1 and 1:2, similar to MSAJ/M-02 [V, Xu et al. 2024 abstract].

### 1.4 Japan: MLIT Notification 666 (`japan`) [V, primary text, 第六]
Allowable tensile stress σ = Fm/(K·t) [N/mm²], with Fm in N/cm (the ministerially designated standard strength of the
product, 第八) and t in mm. Per unit width this gives **n_allow = Fm/K'**:

| Joint condition | Long-term | Short-term, not folded | Short-term, folded |
|---|---|---|---|
| no joint, or joint/weld width ≥ 40 mm (≥ 75 mm for glass/PTFE class (一)) | Fm/8 | Fm/4 | Fm/5 |
| narrower joints | Fm/10 | Fm/5 | Fm/5 |

Further rules in the same notification:
* Material strength: Fm/(40 t), i.e. 1/4 (第七).
* Anchorages: Fj/6 long-term, Fj/3 short-term, with Fj = tensile strength from a test of the actual anchorage (第六 二).
* Relative deformation under snow and wind (half the wind pressure for spans ≤ 4 m): ≤ 1/15 and ≤ 1/20 of the support
  spacing (1/10 at a cable edge) for spans ≤ 4 m; ≤ 1/15 (1/10) for longer spans (第五 3).
* Minimum material requirements (第二 2): thickness ≥ 0.5 mm; mass ≥ 550 g/m² (500 g/m² for synthetic base cloth);
  tensile strength ≥ 200 N/cm; elongation at break ≤ 35 %; tear strength ≥ 100 N and ≥ 15 % of the tensile strength ×
  1 cm; creep elongation ≤ 15 % (25 % synthetic).

`--japan-joint narrow` and `--folded` select the columns. Seam rows use no extra seam efficiency, because the joint
class is already in the divisor.

### 1.5 German A-factor practice (`partial`) [V for PES/PVC, JRC23 Code Review 20]
`f_d = f_k,23 / (γf · γM · A_i)`, where f_k,23 is the 5 % fractile at 23 °C. The tool takes γf on the stress side, so
the input must be the DESIGN stress.
* γM = 1.4 for fabric, 1.5 for connections.
* A0 = 1.0–1.2 (1.2): biaxial. A1 = 1.6–1.7 (1.5–3.4): long-term load. A2 = 1.1–1.2 (1.2): pollution and ageing.
  A3 = 1.1–1.25 (1.4–1.95): temperature, about 70 °C. Values in brackets are for connections.
* Load factors in current German practice: γf = 1.5 permanent, 1.6 winter storm, 1.5 maximum snow.

Design situations:

| Situation | Factors | Global γf·γM·ΠA |
|---|---|---|
| winter storm (wind) | γM·A0·A2 | 2.9–3.2 |
| maximum snow | γM·A0·A1·A2 | 4.4–5.1 |
| permanent | γM·A0·A1·A2·A3 | 4.9–6.4 |
| connections | – | 6.7–9.5 permanent, 3.5 storm, 4.9 snow |

Tool mapping:
* prestress, dead, snow, live → A0·A1·A2·A3. This follows the conservative choice of the [JRC25] example, which
  treats snow as a long-term load with A1 × A3.
* wind, installation → A0·A2.
* temperature → A0·A2·A3 ("summer storm").

Register table (`membrane.partial`):
* PES/PVC: γM 1.4 / 1.5 (joints), A0 1.2, A1 1.7, A2 1.1, A3 1.1. This is inside the published ranges [V].
* glass/PTFE (A1 1.4, A3 1.05) and "other" have no published set [U]. Replace them with tested or approval values.
* DIN 18204-1:2007 gives only the product A_mod·γM.
* `--sensitivity` scales ΠA over 0.78–1.24, the published spread.

### 1.6 CEN/TS 19102:2023 (`ts19102`)
Limit states to EN 1990; Eurocode Outlooks 32–37 [JRC23]:
`f_d = f_k,23 / (γM · kbiax · kage · kdur · ktemp · ksize)`.
* f_k,23 = mean·(1 − kn·Vx) [C, EN 1990 Annex D, kn 1.64]. Coefficient of variation: Vx ≤ 6 % for fabric and
  ≤ 12 % for joints [V, JRC23 §6.3, Minte].
* Annex A of the TS: material classes. Annex B (normative): procedures for the modification factors. Annex C
  (informative): typical modification factors (C.3 PES-PVC, C.4 glass-PTFE, C.5/C.6 ETFE) [V, TS contents page].

prCEN values for PES/PVC used in the [JRC25] worked example [V, single source; confirm against the TS Annex C and the NA]:

| Factor | Value |
|---|---|
| γM0 (material) / γM2 (joint) | 1.4 / 1.5 |
| kbiax | 1.0 |
| kage | 1.4 |
| kdur,P / kdur,L / kdur,M | 1.8 / 1.7 / 1.2 |
| ktemp,70 | 2.0 |
| ksize | 1.0 |

Situations:
* prestress (1): kdur,P·ktemp,70.
* snow ≤ 1000 m (4): kdur,M. Use `--ts-snow L` above 1000 m.
* wind (5): no kdur or ktemp.
* temperature: ktemp,70.

Prestress partial factors γP,inf 0.9 and γP,sup 1.25: check the prestress level that is most unfavourable (×1, ×0.9 or
×1.25) [V, JRC25 slide 49].

prCEN SLS temperature factors k_temp,0 = 0.8 and k_temp,50 = 1.2–1.4 (proposed 1.4–1.5) were reported by Stranghöner
(TexComp 2021) [U, not re-read].

### 1.7 French recommendations (`french`) [V, JRC23 Code Review 21]
`TC ≤ TD = kq · ke · Trm / γt`, where Trm is the mean strength.
* kq = min(kt, ks) = 1 with ISO 9001 or externally validated control, otherwise 0.8.
* ke = 1 for S ≤ 50 m², otherwise (50/S)^(1/15).
* γt = 4 for medium pollution, 4.5 for heavy pollution.
* Attachments: TD = kq · n_eff · Trm / γtloc with γtloc = 5 (n_eff 1.9 / 2.6 / 3.1 for 1 / 2 / 3 reinforcements).
* Edges: SF ≥ 2.5 on the lowest of three or more tests.
* Connections: γa = 2 for cables, 2.5 for other parts.

### 1.8 ETFE foil [V, JRC23 Eurocode Outlook 44 proposal]
`f_d = f_y10,23 / (γM · k)`, with γM = 1.1 and f_y10,23 = 21 MPa (10 % strain stress) unless tested. The k factors by
situation:

| Situation | k |
|---|---|
| permanent | kage 1.05 · kperm 1.8 (3.5 for single layer without regulation) |
| long-term, 0 °C | kage · klong 1.2 · ktemp0 0.7 |
| long-term, 23 °C | kage · klong |
| short-term | kage |
| short-term, 50 °C | kage · ktemp50 1.2 |

ktemp70 = 1.7. Worked value: f_PM,d = 10.1 MPa.

Moritz concept, ULS: f_u,k 47 MPa (base) and 30 MPa (weld) at 23 °C [V, JRC23 Tables 6-5/6-6].

### 1.9 Partial factors on actions
A reliability calibration for a PVC hypar recommends either of these sets [V, Eng. Struct. 214 (2020)]:
* γ_P = 1.0 with γ_S = γ_W = 2.0;
* γ_P = 1.2 with γ_S = γ_W = 1.5.

The hanging (sag) direction under snow governs. Apply γF to the action or to the action effect depending on the
stiffening or softening response [V, JRC23 ch. 3 quoting EN 1990 (non-linear analysis, single predominant action)].

## 2. Load cases (analyse each combination non-linearly)
1. **Prestress P**: permanent but relaxes. Check both the initial and the relaxed prestress.
2. **Dead G**: small (fabric about 0.25–1.7 kg/m², see `materials.json`), plus attached lighting and services.
3. **Wind W**: uplift (suction) and downward, several directions. EN 1991-1-4 and ASCE 7 give **no Cp for hypars or
   cones**. Use conservative canopy/vault values, TensiNet App. A1, published tunnel data or project tunnel/CFD [V].
   Consider the dynamic/aeroelastic response for large flexible roofs.
4. **Snow S**: uniform, drift and asymmetric (EN 1991-1-3 / ASCE 7), plus **ponding** of meltwater or rain in
   hollows. Ponding must be avoided: iterate with the load following the deformed shape.
5. **Temperature T**: cables (α = 12e-6 carbon, 16e-6 stainless) and strength reduction at high temperature
   (seams at 70 °C ≥ 55–70 % of the fabric strength [V, JRC23 Outlook 5]).
6. **Installation**: partial or unbalanced prestress stages; PTFE folding damage.

Combinations: P+G; P+G+S; P+G+W↓; P+G+W↑; P+G+S+ψW; P+G+W+ψS; P+G+T; SLS versions for ponding, deflection and slack.

## 3. Serviceability
* No slack (zero principal stress) under SLS in large areas, otherwise there is a wrinkling/flutter risk [U threshold].
* There is no universal deflection limit. Criteria are clearance (ASCE 55 §6.10), ponding, drainage and appearance.
  The exception is the Japanese relative-deformation limits in §1.4 [V].
* SLS limits are agreed per project (Eurocode Outlook 39) [V, JRC23 §7.1].
* A minimum slope of about 15° is often quoted [V]. 5–10° is possible when checked on the deformed shape [U].
* Panel frequency: no code limit. `--flutter` gives exact flat-panel modes with computed added air mass.

## 4. Seams, edges and reinforcement
* Seams follow geodesic lines, with the warp aligned with the main load path.
* Minimum weld widths: PES/PVC 3–4 cm (French type table) [V, JRC23 Code Review 3]; 40 mm for Type I and 80 mm for
  Type IV (German practice) [V, JRC23 Code Review 20]; Japan ≥ 40 mm, ≥ 75 mm for glass/PTFE [V, MLIT666].
* Seam strength: PES/PVC ≥ 90 % at 23 °C (Type V ≥ 80 %), ≥ 55–70 % at 70 °C; glass/PTFE ≥ 80–90 % at 23 °C,
  ≥ 60–70 % at 70 °C; silicone/glass 70 % [V, JRC23 Outlooks 5, 7, 9]. The register default is 0.8.
* Seam testing: strip tensile at 23 °C and 70 °C, plus long-term seam creep tests (German practice) [V, JRC23].
  Log the welding parameters.
* Reinforcement plies: n_eff = 1.5 for one extra layer (safe-sided; more layers need tests) [V, Eurocode Outlook 38];
  French 1.9 / 2.6 / 3.1; German 1.75 / 2.6 [V, JRC23 §6.5]. Corner doublers extend about 0.5–1.0 m [U]. Belts
  continue into the corner plate.
* Edges: cable pocket or belt; for PTFE prefer clamp plates on external cables (see `tensile-connections`).
* Membrane belts: polyester webbing, stress factor about 2.3–3 on belts and cables [V range], textile factor 3–6 for
  webbing [U].

## 5. Fire, durability, UV, soiling

| Material | Fire | Life (yr) |
|---|---|---|
| glass/PTFE | A2-s1,d0; ASTM E136 base; Japan non-combustible (Chukoh NM-8665) [V] | 25–35+ [V] |
| ETFE | B-s1,d0 [V]; DIN 4102 B1 (Nowoflon) [V] | 30+ [U] |
| PES/PVC | B-s2,d0 (Valmex, Ferrari 1002 S2) [V]; some sheets print C-s2,d0 (Ferrari 1302/1502 S2) [V]; NFPA 701 / E84 | 15–25 [U] |
| silicone/glass | A2 or B [V] | 20–30 [V] |
| ePTFE (Tenara) | B-s1,d0, ASTM E84 Class A [V] | long [U] |

* PVC and ETFE melt away and vent in a fire [U].
* PTFE seams lose 60–73 % of their strength at 250 °C, fabric only about 12 % [V].
* Self-cleaning materials: PTFE, ePTFE, ETFE. For PVC it depends on the topcoat.

## 6. Design check sequence
1. Get warp/weft stresses per combination from the non-linear analysis: characteristic for `factor`/`fm`/`japan`/`french`,
   factored for `partial`/`ts19102`.
2. Pick the design basis (project specification) with `membrane_check.py --method …`.
3. Check fabric warp and weft, and seams in the direction that crosses them.
4. Check corners and clamp lines (`--corner` or a local FE model).
5. Check tear propagation (critical defect length) in high-stress zones (`--tear`, factor [U]).
6. SLS: slack areas, ponding, clearances, panel frequency (`--flutter`).
