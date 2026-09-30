---
name: membrane-fabric
description: Membrane fabric materials and membrane design for tensile structures — PVC-coated polyester (Types I–V), PTFE-coated glass, silicone-coated glass, ETFE foil, ePTFE (Tenara), mesh and shade cloth. Use to choose a fabric, get strength/stiffness/compensation data, set prestress, check membrane and seam stresses (stress-factor, FM DS 1-59, Japanese, CEN/TS 19102 partial-factor format), define seams and reinforcements, and handle load cases, ponding, wrinkling, fire and durability.
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
- `--method partial`: n_Rd = f_k/(γM·A0·A1·A2·A3). The defaults are **indicative German A-factor values**. Replace them with CEN/TS 19102 Annex C, National Annex or project values, and feed in design stresses from factored non-linear runs.
- Seams are checked with `--seam-eff` (default 0.8; PVC HF 0.8–0.9, PTFE heat-seal 0.7–0.8).

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
