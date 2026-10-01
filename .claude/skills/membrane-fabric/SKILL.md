---
name: membrane-fabric
description: Membrane fabric materials and membrane design for tensile structures — PVC-coated polyester (Types I–V), PTFE-coated glass, silicone-coated glass, ETFE foil, ePTFE (Tenara), mesh and shade cloth. Use to choose a fabric, get strength/stiffness/compensation data, set prestress, check membrane and seam stresses (stress-factor, FM DS 1-59, Japanese, CEN/TS 19102 partial-factor format, ASCE 55 for US and Saudi SBC 201), define seams and reinforcements, and handle load cases, ponding, wrinkling, fire and durability.
---

# Membrane fabric design

## When to use
- Selecting a membrane material, or comparing PVC vs PTFE vs ETFE vs silicone.
- Setting prestress levels and warp/weft ratios.
- Checking membrane stresses from analysis (fabric and seams, warp and weft).
- Biaxial stiffness, compensation values, seam widths, reinforcement at corners and edges.

## Tool: `scripts/membrane_check.py`
```bash
python3 membrane_check.py --list                                   # material library
python3 membrane_check.py --material PVC-III --nw 18.5 --nf 14.2 --case wind          # stress factor 4
python3 membrane_check.py --material Chukoh-FGT-800 --nw 31 --nf 22 --case snow \
        --method fm --fm-combo P+D+S                                                  # FM DS 1-59
python3 membrane_check.py --fw 84 --ff 80 --nw 9 --nf 7 --case snow --method partial --family PES/PVC
python3 membrane_check.py --material PVC-II --prestress 2.0 2.0                       # prestress advice
```
- `--method factor` (default): allowable = f/SF. SF = 4 short-term (wind), 5 long-term (snow, prestress); both editable.
- `--method fm`: FM Global DS 1-59 factors on new-fabric strength (8 for P+D, 5 with S/W/T/L/R).
- `--method japan`: 1/8 long-term, 1/4 short-term (reported; verify).
- `--method asce55` (US; Saudi via SBC 201 §3102.1.1; the default for `--code US|SA`): T_r = β·L_t·T_s per
  direction, plus the biaxial rule 0.8·β·L_t·(T_sw + T_sf) ≥ T_fw + T_ff.
  - β = 0.17 (P+D), 0.27 (P+D+S/Lr), 0.33 (P+D+W), 0.27 (P+D+T).
  - L_t = 0.75 for a permanent structure, ≤ 0.6 with `--handled`.
  - `--seam-type heat|adhesive|sewn|sewn-protected` multiplies L_t by 1.0 / 0.5 / 0.6 / 0.9.
  - Values from ASCE 55-10 (read in full); 55-16 is not verified.
  - Feed stresses from ASD-level runs: `loads.py make-cases --set membrane`.
  - SBC also requires the membrane to be noncombustible or pass NFPA 701.
- `--method partial`: n_Rd = f_k/(γM·A0·A1·A2·A3). The defaults are **German A-factor practice** values: fabric γM 1.4,
  A0 1.0–1.2, A1 1.6–1.7, A2 1.1–1.2, A3 1.1–1.25 (Bautechnik; Knippers' *Construction Manual*). They are not
  CEN/TS 19102 values. Replace them with CEN/TS 19102 Annex C, National Annex or project values, and feed in design
  stresses from factored non-linear runs.
- Seams are checked with `--seam-eff` (default 0.8; PVC HF 0.8–0.9, PTFE heat-seal 0.7–0.8).

More checks in the same tool:
```bash
python3 membrane_check.py --material PVC-III --envelope sail_cases_envelope.json      # every load case (warp/weft)
python3 membrane_check.py --material PVC-III --nw 12 --tear 50 45 --defect 80         # tear propagation
python3 membrane_check.py --material PVC-III --curvature 12 18 --p 0.8 --prestress 2 2   # Laplace hand sizing
python3 membrane_check.py --material ETFE-250um --nw 2.5                              # ETFE: σ = n/t vs f_y1/γ
```
- `--envelope`: reads `run_cases.py` output (max warp/weft stress and duration per case). It warns if factored cases
  are combined with a global-factor method, because safety would then be counted twice.
- `--tear A N`: the slit-tear test (slit A mm fails at N kN/m) is scaled to the design defect by n_c ∝ 1/√a.
  Allowable = n_c/tear_factor, where tear_factor is [U] and must be agreed with the checker.
- `--curvature R_res R_oth --p`: bounds from n₁/R₁ + n₂/R₂ = p. The resisting direction is ≤ n0 + pR; the other
  direction is ≥ n0 − pR, so it flags slack risk. Hand sizing only.

Panel frequency, corner reinforcement and sensitivity:
```bash
python3 membrane_check.py --material PVC-III --prestress 2 2 --flutter 6 4 --f-target 2.0   # f11 + prestress needed
python3 membrane_check.py --material PVC-III --case wind --corner 25 90 0.4 --layers 3      # radial fan at a corner
python3 membrane_check.py --material PVC-III --nw 9 --nf 8 --case snow --method partial --sensitivity
```
- `--flutter A B`: f11 = ½·√((n_w/A² + n_f/B²)/m_eff) for a flat A × B panel (lower bound: curvature stiffens it).
  m_eff = fabric mass + C_a·ρ_air·r_eq per air side. For light fabrics the air is most of the mass. C_a is [U]
  (Lamb's plate value 0.67, range 0.55–0.9). `--f-target` gives the prestress for a target frequency. No code sets a
  frequency limit, so agree the target with the wind engineer.
- `--corner R THETA R0`: the corner force fans out as n(r) = R/(θ·r). The tool checks the stress at the plate or
  clamp radius against n_all·(1 + (k−1)·η) for k plies (η [U], default 0.8) and gives how far each ply must extend.
- `--sensitivity`: re-runs every check that uses an uncertain factor (Japanese divisors, the partial-factor set as a
  scale 0.78–1.24, tear factor, ETFE γ, C_a, ply efficiency; single point or `--envelope`) at both ends of the
  factor's range. It prints ROBUST when the OK / NOT OK decision holds over the range, or DEPENDS when it does not.
  The stress-factor (4/5) and FM methods use [V] factors only.

### `scripts/material_select.py`: filter and rank fabrics for a project
```bash
python3 material_select.py --n-design 25 --case snow --fire A2 --translucency 10
python3 material_select.py --n-design 6 --case wind --foldable --life 15 --max-cost 2
```
- The strength requirement uses the same `allowable()` as `membrane_check.py`, with seams in the weaker direction.
  ETFE is checked as σ = n/t against f_y1/γ.
- Filters: EN 13501-1 class (A1 < A2 < B …), translucency, service life, foldability, family, relative cost.
- Ranking: cost index, then the utilisation closest to `--u-target` (0.8). Every excluded material is listed with
  the reason.
- Fire, light, life, fold and cost data are *typical family values* (`family_defaults`). Use them for screening and
  confirm with the product's classification report, datasheet and warranty.

### `scripts/biaxial_fit.py`: biaxial test → stiffness + compensation (EN 17117-1/-2 style)
```bash
python3 biaxial_fit.py test.csv --per-ratio --prestress 2 2 --residual 0.45 1.10
```
- Least-squares fit of E_w·t, E_f·t, ν_wf, ν_fw with reciprocity over all load ratios (CSV: ratio,n_w,n_f,eps_w,eps_f).
- `--per-ratio`: stiffness per stress state with ν fixed from the full fit (one ratio cannot identify three constants).
- Compensation = residual strain after the prestress cycles + elastic strain at the prestress, in warp and weft,
  ready to use in `cutting_pattern.py`.
- Validation: exact recovery of known constants and reciprocity on synthetic data (tests).

The library is in `reference/materials.json`. Every entry is tagged datasheet, class-table or typical. Replace it with the project datasheet.

## Core knowledge (details in `reference/`)

**Material quick facts** ([V] = confirmed from a source via search excerpt; [U] = typical, not verified)

| | PES/PVC | glass/PTFE | glass/silicone | ETFE foil | ePTFE (Tenara) |
|---|---|---|---|---|---|
| UTS warp kN/m | 66 (I) … 200 (V) [V] | 84–183 [V] | 80–140 [V] | 35–53 MPa × t | 80 [V] |
| Euroclass | B-s2,d0 / B-s1,d0 [V] | A2-s1,d0 [V] | A2 or B [V] | B-s1,d0 [V] | – |
| Light transmission | 5–20 % [U] | 12–25 % [V] | 20–40 % [V] | 88–95 % [V] | 38 % [V] |
| Life (yr) | 15–25 [U] | 25–35+ [V] | 20–30 [V] | 30+ [U] | long |
| Joint | HF / hot-air weld | heat-seal with FEP film ~350–385 °C | vulcanise / bond | thermal weld | thermal weld |
| Foldable | yes | **no** (glass cracks) | moderate | – | yes |
| Roll width | 2.50–2.67 m [V] | 3.8–4.7 m [V] | – | ~1.55 m [V] | – |

Design stress factors in the register: 4.0 short-term (wind) and 5.0 long-term (snow/prestress) are now **[V]**
(ASCE 55-10 "industry practice" FS 4/5/8 and Birdair). CEN/TS 19102 γ_M and k values remain [U].

Units: 1 kN/m = 1 N/mm = 50 N/5 cm; N/3 cm ÷ 30 = kN/m.

**Behaviour:** orthotropic (warp straighter and stiffer, weft more crimped); crimp
interchange (apparent ν can exceed 0.5); non-linear first loading with permanent
set; creep (PVC large) and relaxation (PTFE temperature-dependent). Stiffness
comes from biaxial tests (EN 17117-1, MSAJ ratios 1:1, 2:1, 1:2, 1:0, 0:1) after
shakedown cycles:
```
ε_w = n_w/(E_w t) − ν_fw n_f/(E_f t)
ε_f = n_f/(E_f t) − ν_wf n_w/(E_w t)      reciprocity  ν_wf/(E_w t) = ν_fw/(E_f t)
```

**Prestress:** PVC ≈ 1–4 kN/m (1.5–2.5 is common); PTFE 2–8 kN/m (heavy grades 6–8);
rule of thumb 1.5–3 % of UTS. Too low leads to wrinkling, flutter and ponding. Too high leads to creep, tear risk and heavy boundaries.

**Design-check philosophy:** design stress ≤ strength / (global factor) or ≤ f_k/(γ_M·Πk).
Check fabric warp/weft, seams (lesser of seam and fabric, ASCE 55), corners and clamp
lines (stress concentrations), tear propagation, elevated temperature (PTFE
seams lose 60–73 % strength at 250 °C [V]), and slack/wrinkling under SLS.

**Geometry rules:** double curvature everywhere; slope ≈ 15° is often quoted for
drainage and self-cleaning [V] (lower with a ponding check on the deformed shape); no
flat zones. Hypar rise-to-span ≈ 1/10–1/15 or deeper [U].

## References
- `reference/membrane-materials.md`: full material data, datasheet values, stiffness, compensation, roll widths.
- `reference/membrane-design-criteria.md`: codes (CEN/TS 19102, ASCE 55, FM 1-59, Japan, A-factors), load cases, combinations, seams, reinforcement, fire and durability.
- `reference/materials.json`: machine-readable library used by the tool.

## Always
- Use biaxial test data for the **delivered batch** for stiffness and compensation.
- Treat code factors as project-specific. The TS/NA may differ from the defaults here.
- Coordinate warp direction with the patterning (`fabrication-drawings`) and the analysis (`tensile-analysis`).
