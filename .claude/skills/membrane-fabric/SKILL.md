---
name: membrane-fabric
description: Membrane fabric materials and membrane design for tensile structures — PVC-coated polyester (Types I–V), PTFE-coated glass, silicone-coated glass, ETFE foil, ePTFE (Tenara), mesh and shade cloth. Use to choose a fabric, get strength/stiffness/compensation data, set prestress, check membrane and seam stresses (stress-factor, FM DS 1-59, Japanese MLIT 666, German A-factors, CEN/TS 19102, French recommendations), corners, tear, panel frequency and ETFE foil, and handle load cases, ponding, wrinkling, fire and durability.
---

# Membrane fabric design

## When to use
- Selecting a membrane material, or comparing PVC with PTFE, ETFE, silicone or ePTFE.
- Setting prestress levels and warp/weft ratios.
- Checking membrane stresses from the analysis (fabric and seams, warp and weft, corners, tear, ETFE foil).
- Getting biaxial stiffness, compensation values, seam widths, and reinforcement at corners and edges.

Tags in this skill:
* **[V]**: confirmed from a named source (URL and quote in `reference/verification-log.md`).
* **[C]**: standard recommended value; the National Annex may differ.
* **[U]**: unverified practice value. It carries a range, and `--sensitivity` checks that range.

## Tool: `scripts/membrane_check.py`
```bash
python3 membrane_check.py --list                                                      # material library
python3 membrane_check.py --material PVC-III --nw 18.5 --nf 14.2 --case wind           # stress factor 4
python3 membrane_check.py --material Chukoh-FGT-800 --nw 31 --nf 22 --case snow --method fm --fm-combo P+D+S
python3 membrane_check.py --material PVC-III --nw 12 --nf 10 --case wind --method japan --folded
python3 membrane_check.py --material PVC-III --nw 9 --nf 8 --case snow --method partial --sensitivity
python3 membrane_check.py --fw 172 --ff 168 --vx 0.12 --family PES/PVC --nw 35.55 --nf 12.75 --case snow --method ts19102
python3 membrane_check.py --material Sattler-Atlas-760-IV --nw 38.1 --nf 40.2 --case wind --method french --area 600
python3 membrane_check.py --material PVC-II --prestress 2.0 2.0                          # prestress vs published minimum
```

Methods (`--method`). Cases (`--case`): prestress, dead, snow, live (long-term); wind, installation (short-term);
temperature (short-term, warm).

| Method | Format | Load effects | Factors |
|---|---|---|---|
| `factor` (default) | f/SF | characteristic | SF 4 short-term, 5 long-term [V, ASCE 55-10 practice]; `--sf-short/--sf-long` override |
| `fm` | f/SF on new-fabric strength | characteristic | FM DS 1-59 Table 2.2.6.1: P+D 8, others 5 [V]; `--fm-combo` |
| `japan` | Fm/K | characteristic | MLIT 666: Fm/8 long-term, Fm/4 short-term, Fm/5 folded (`--folded`), Fm/10 and Fm/5 for narrow joints (`--japan-joint narrow`) [V, primary text]. Fm = designated standard strength. No extra seam efficiency (the joint class is in the divisor). |
| `partial` | f_k/(γM·ΠA) | design (factored) | German A-factors by situation: long-term γM·A0·A1·A2·A3, wind γM·A0·A2, temperature γM·A0·A2·A3; γM 1.4 fabric, 1.5 seams. PES/PVC [V, JRC132615 Code Review 20]; glass/PTFE and other [U] |
| `ts19102` | f_k/(γM·kbiax·kage·kdur·ktemp·ksize) | design (factored) | prCEN values for PES/PVC from the JRC 2025 worked example [V, single source]: γM0 1.4, γM2 1.5 (seams), kage 1.4, kdur P/L/M 1.8/1.7/1.2, ktemp,70 2.0. `--ts-snow L` for snow above 1000 m. Other families: add the values with `--factors`. |
| `french` | kq·ke·Trm/γt | per the French combinations | γt 4 / 4.5 (`--pollution`), ke = (50/S)^(1/15) (`--area` or `--ke`), kq 1 / 0.8 (`--kq`) [V, JRC132615 Code Review 21] |

Strength input:
- `factor`, `fm` and `french` use the datasheet strip strength (mean or nominal).
- `partial` and `ts19102` need the 5 % fractile f_k. The tool takes `fk_w`/`fk_f` from the library or computes
  f_k = f·(1 − 1.64·Vx) with `--vx` [C, EN 1990 Annex D]. Without either, it warns.
- `--seam-eff` (default 0.8 [V]; JRC classes ≥ 0.9 at 23 °C) and `--seam-dir` set the seam check. `--nmin` checks for
  slack.
- `--factors project.json` replaces register values.

More checks in the same tool:
```bash
python3 membrane_check.py --material PVC-III --envelope sail_cases_envelope.json --method partial --sensitivity
python3 membrane_check.py --material PVC-III --nw 12 --tear 50 45 --defect 80               # tear propagation
python3 membrane_check.py --material PVC-III --curvature 12 18 --p 0.8 --prestress 2 2       # Laplace hand sizing
python3 membrane_check.py --material PVC-III --prestress 2 2 --flutter 6 4 --f-target 2.0 --modes 4 --sensitivity
python3 membrane_check.py --material PVC-III --case wind --corner 25 90 0.4 --layers 2 --neff-basis ts --sensitivity
python3 membrane_check.py --material ETFE-250um --nw 2.5 --case snow                        # ETFE foil
```
- `--envelope`: reads the `run_cases.py` output and checks every case (max warp/weft stress, fabric and seams). It
  warns when factored cases are combined with a global-factor method, because safety would then be counted twice.
- `--tear A N --defect a`: scales the slit-tear test result to the design defect, n_c = N·√(A/a) (LEFM centre crack).
  Allowable = n_c/tear_factor. The tear_factor (2.0, range 1.5–3) is **[U]**: no code gives one.
- `--curvature R_res R_oth --p`: bounds from n₁/R₁ + n₂/R₂ = p. The resisting direction is ≤ n0 + pR; the other
  direction is ≥ n0 − pR, which flags slack risk.
- `--flutter A B`: exact flat rectangular membrane modes f_mn = ½·√((n_w(m/A)² + n_f(n/B)²)/m_eff), pinned edges.
  - m_eff = fabric mass + sides·C_a·ρ_air·r_eq (`--sides 2` open canopy, `1` closed building).
  - C_a is **computed** for the panel aspect ratio and mode with the Rayleigh integral of a baffled panel (square
    0.726; it reproduces Lamb's 0.6689 for a clamped plate) and multiplied by `added_mass_model` (1.0, range 0.5–1.0
    for isolated canopies) [U].
  - `--ca` fixes C_a, `--modes K` lists modes, `--mass` overrides the library weight, and `--f-target` gives the
    prestress for a target f11.
  - No code sets a frequency limit: agree the target with the wind engineer.
- `--corner R THETA R0 --layers k`: radial fan n(r) = R/(θ·r) against n_all·n_eff.
  - Published n_eff tables (`--neff-basis`): `ts` (Eurocode Outlook 38 safe-sided, 1.5 for one extra ply; more plies
    need tests), `french` (1.9 / 2.6 / 3.1), `german` (1.75 / 2.6) [V, JRC132615 §6.5].
  - `eta` uses the linear ply model with corner_ply_eff 0.8 [U].
  - With `--method french`, the base is the attachment rule Trm/γtloc (γtloc 5) [V].
  - The output gives how far each ply must extend.
- ETFE: σ = n/t against f_y10,23/(γM·k) of the design situation. γM 1.1, kage 1.05, kperm 1.8 (3.5 with
  `--etfe-single-unregulated`), klong 1.2, ktemp0 0.7, ktemp50 1.2, f_y10,23 = 21 MPa without tests [V, JRC132615
  Eurocode Outlook 44 proposal].
- `--sensitivity`: re-runs every check whose factor carries a range: partial (published spread 0.78–1.24; [U] for
  glass/PTFE), tear factor, added-mass model, and the corner n_eff bases. It prints ROBUST when the OK / NOT OK
  decision holds over the range, or DEPENDS when it does not. The `factor`, `fm`, `japan`, `ts19102` and `french`
  factors are [V] and carry no range.
- Every run ends with an **Assumptions** block: strength basis, method, model limits.

### `scripts/material_select.py`: filter and rank fabrics for a project
```bash
python3 material_select.py --n-design 25 --case snow --fire A2 --translucency 10
python3 material_select.py --n-design 6 --case wind --foldable --life 15 --max-cost 2
python3 material_select.py --n-design 40.2 --case wind --method ts19102 --family PES/PVC --seam-eff 1.0
```
- Strength uses the same `allowable()` as `membrane_check.py` (all six methods, `--area` for `french`), with the seam
  in the weaker direction and the joint partial factor. `partial`/`ts19102` use the library f_k where one exists. ETFE
  is checked as σ = n/t against the Outlook 44 design strength. A method without factors for a family excludes it with
  the reason.
- Filters: EN 13501-1 class (`--fire`, A1 < A2 < B …), using the product's class when the entry states one (e.g. Ferrari
  1302 S2 prints C-s2,d0), otherwise the family default; `--translucency`, `--life`, `--foldable`, `--family`,
  `--max-cost`.
- Ranking: cost index, then the utilisation closest to `--u-target` (0.8). Every excluded material is listed with the
  reason.
- Fire, light, life, fold and cost defaults are *typical family values* (`family_defaults`).

### `scripts/biaxial_fit.py`: biaxial test → stiffness + compensation (EN 17117-1/-2 style)
```bash
python3 biaxial_fit.py test.csv --per-ratio --prestress 2 2 --residual 0.45 1.10
```
- Least-squares fit of E_w·t, E_f·t, ν_wf and ν_fw with reciprocity over all load ratios (CSV:
  ratio,n_w,n_f,eps_w,eps_f; kN/m and %).
- `--per-ratio`: stiffness per stress state, with ν fixed from the full fit.
- Prints the **direct** stiffness form as well (Ed_w, Ed_f, crimp interchange Ed_wf), for programs that use it.
  `direct_to_inverse()` / `inverse_to_direct()` convert between the forms (JRC132615 eqs. 2.5–2.12).
- Compensation = residual strain after the prestress cycles + elastic strain at the prestress, for `cutting_pattern.py`.

### Library `reference/materials.json`
36 entries:
- PES/PVC classes I–V (JRC Outlooks 5–6, mean and 5 % fractile).
- Ferrari 1002/1302/1502 S2, Valmex FR 1000, Verseidag B4915 [E], Sattler Atlas IV (published example).
- Chukoh FGT-600/800/1000, Sheerfill II/V, Verseidag B18039/B18089 [E], glass/PTFE classes I–IV.
- Silicone/glass classes.
- Tenara 4T40HF and fluoropolymer-coated PTFE classes.
- ETFE 200/250 µm and Nowoflon ET 6235 Z.

Each entry has `raw` (value and unit as published), `strength_basis`, `status` (datasheet / excerpt / class-table /
published-example / typical) and `source_url`. Tear, weight, thickness, roll width, fire class and light transmission
are included where published.

## Core knowledge (details in `reference/`)

**Material quick facts**

| | PES/PVC | glass/PTFE | glass/silicone | ETFE foil | ePTFE (Tenara) |
|---|---|---|---|---|---|
| UTS warp, kN/m | 55 (I) … 185 (V) mean [V, JRC] | 70–183 [V] | 52–200 [V, JRC] | 50 MPa × t [V, Nowoflon] | 80 [V] |
| Euroclass | B-s2,d0 (some C-s2,d0) [V] | A2-s1,d0 [V] | A2 or B [V] | B-s1,d0 [V] | B-s1,d0 [V] |
| Light transmission | 4–13 % [V, Ferrari; French table] | 10–18 % [V] | 20–40 % [V] | > 91 % [V] | 38 % [V] |
| Life (yr) | 15–25 [U] | 25–35+ [V] | 20–30 [V] | 30+ [U] | long [U] |
| Joint | HF / hot-air weld | heat-seal with FEP film ~350–385 °C [V] | stitched / glued, 70 % [V] | thermal weld | thermal weld |
| Foldable | yes | **no** (glass cracks; crease fold leaves 69–82 % [V, Sheerfill II]) | moderate | – | yes [V] |
| Roll width | 1.80–2.67 m [V] | 3.0–4.7 m [E] | – | ~1.55 m [E] | 1.575 m [V] |

Units: 1 kN/m = 1 N/mm = 50 N/5cm; N/3cm ÷ 30 = kN/m; lb/in × 0.1751 = kN/m.

**Behaviour:** orthotropic (the warp is straighter and stiffer, the weft more crimped); crimp interchange (the
apparent ν can exceed 0.5); non-linear first loading with permanent set; creep (large for PVC) and relaxation
(temperature-dependent for PTFE). Stiffness comes from biaxial tests (EN 17117-1; MSAJ ratios 1:1, 2:1, 1:2, 1:0, 0:1)
after shakedown cycles:
```
ε_w = n_w/(E_w t) − ν_fw n_f/(E_f t)
ε_f = n_f/(E_f t) − ν_wf n_w/(E_w t)      reciprocity  ν_wf/(E_w t) = ν_fw/(E_f t)
```

**Prestress:** published minimums are PES/PVC ≥ 1.3 % of the short-term strength; glass/PTFE ≥ 2.5 % and ≥ 2.0 kN/m
(TensiNet guide); all structural membranes ≥ 1.5 kN/m (French recommendations). Practice is 1.8–3.5 kN/m [V, JRC132615
ch. 3]. `--prestress` checks these minimums. Typical ranges: PVC 1–4 kN/m, PTFE 2–8 kN/m (heavy grades 6–8) [U]. Too
low gives wrinkling, flutter and ponding. Too high gives creep, tear risk and heavy boundaries.

**Design-check philosophy:** design stress ≤ strength/(global factor) or ≤ f_k/(γM·Πk). Check:
* fabric warp and weft;
* seams (the lesser of seam and fabric, ASCE 55);
* corners and clamp lines;
* tear propagation;
* elevated temperature (seams at 70 °C ≥ 55–70 % [V, JRC]; PTFE seams lose 60–73 % at 250 °C [V]);
* slack and wrinkling under SLS.

**Geometry rules:** double curvature everywhere. A slope of about 15° is often quoted for drainage and self-cleaning
[V]; lower slopes need a ponding check on the deformed shape. No flat zones. Hypar rise-to-span about 1/10–1/15 or
deeper [U].

## Limitations
- **Material data are published typical, class or datasheet values** (class tables are the JRC *proposed*
  classification). They are for screening and benchmarking only. Design with the supplier's certified 5 % fractile
  strength, seam strength at 23 °C and 70 °C, and the biaxial stiffness and compensation of the **delivered batch**.
  Entries marked `excerpt` or `typical` are not verified at source.
- Code factors are project-specific. The `ts19102` values are prCEN values from one published worked example; the
  published CEN/TS 19102:2023 Annex C table could not be read. Confirm every factor against the edition and National
  Annex in force (CEN/TS 19102 is a Technical Specification, not yet an EN). glass/PTFE and "other" A-factors are [U].
- Stress-factor methods expect characteristic load effects; `partial`/`ts19102` expect factored ones. Mixing them
  double counts or omits safety.
- The checks are point checks on stresses from the analysis. They do not model stress concentrations at clamps,
  holes or seams, and the corner check is a radial-fan equilibrium estimate without belt or bolt forces.
- Tear: one slit test is scaled by LEFM 1/√a. Coated fabrics deviate from it (yarn-count and biaxial effects), and the
  tear factor is [U]. Test near the design defect length.
- Panel frequency: flat panel, small amplitude, still air, baffled added mass (upper bound). Curvature, wind flow and
  aeroelastic effects are not included and need wind-tunnel or CFD data for large flat panels.
- `biaxial_fit.py` fits a linear orthotropic law with reciprocity. It does not identify shear stiffness or
  non-linear, history-dependent behaviour. It has been validated against the published direct/inverse formulation,
  not yet against a published raw test data set (see `reference/validation.md`).
- ETFE: the ULS check uses the JRC Outlook 44 proposal on f_y10,23. SLS (strain, deformation) usually governs, and weld
  strength (about 30 MPa) must be checked separately.

## References
- `reference/membrane-materials.md`: material data with sources, class tables, products, stiffness, compensation, seams.
- `reference/membrane-design-criteria.md`: verification formats (stress factor, FM, ASCE 55, Japan, German A-factors,
  CEN/TS 19102, French, ETFE), load cases, SLS, seams, reinforcement, fire and durability.
- `reference/materials.json`: machine-readable library used by the tools.
- `reference/validation.md`: validation table (tool, case, reference, expected, obtained, error, tolerance).
- `reference/verification-log.md`: what was searched and changed for every register factor and material entry.

## Always
- Use the biaxial test data of the **delivered batch** for stiffness and compensation.
- Treat code factors as project-specific. Run `--sensitivity` and do not issue a check that DEPENDS on a [U] factor.
- Coordinate the warp direction with the patterning (`fabrication-drawings`) and the analysis (`tensile-analysis`).
