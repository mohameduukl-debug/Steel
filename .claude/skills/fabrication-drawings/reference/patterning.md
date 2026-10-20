# Patterning (cutting patterns)

Tags: [V] verified (source below), [C] code/standard content, [U] unverified practice value (range given).
Values marked [U] are rules of thumb; confirm with the fabricator, the fabric manufacturer and the project specification.

## 1. Seam layout
* Seams on **geodesic lines** of the prestressed surface: minimum waste, no seam-induced stress (general patterning
  practice, e.g. RFEM RF-CUTTING-PATTERN uses geodesic cutting lines [S5]).
* Drivers: warp direction (along principal stress / main span, panel length), roll width, aesthetics, fabric yield,
  curvature, prestress uniformity. Add seams where the flattening error becomes too large.
* Structural fabrics are manufactured with a typical width of 2–3 m and a maximum width of about 5 m, so larger
  structures need multiple panels [V, S6: "Structural fabrics are manufactured with a typical width of 2–3 m, and a
  maximum width of 5 m"].
* Radial seams on cones; seams parallel to the high-low diagonal or across the span on hypars. Avoid seams ending at
  corner plates with sharp angles.

## 2. Roll widths
| Material | Product | Width | Tag |
|---|---|---|---|
| PES/PVC | Serge Ferrari Précontraint / Flexlight / Tenseo Advanced 1002 S2 | 267 cm | [V, S1] |
| PES/PVC | Serge Ferrari other S2 grades, Advanced 902–1502 S2 | 260–267 cm (180 cm reported for some grades) | [U] |
| PES/PVC | Mehler Valmex FR 1000 Type III | 250 cm (300 on request) | [U] (no datasheet found) |
| PES/PVC | Verseidag Duraskin B4915 / B4951 | 250 cm | [U] |
| glass/PTFE | Verseidag Duraskin B 18039 / B 18656 | 300 cm | [V, S3] |
| glass/PTFE | Verseidag Duraskin B18089, Chukoh FGT-800/1000 | 380–470 cm reported | [U] (not confirmed by the searched catalogues) |
| ETFE | Nowoflon ET 6235 Z | 1550 mm (others on request) | [V, S2] |
Usable width = roll − selvedges − seam allowances. Always take the width from the current datasheet of the ordered product.

## 3. Flattening methods
* Geometric triangle unfolding (exact along one path; errors accumulate).
* **Least squares on edge lengths** (this repo): unfold from the panel centre, then Gauss–Seidel relaxation of all
  quad edges and diagonals; reports max/RMS/95th-percentile strain, the strain distribution and the area error.
  Exact for developable panels (validated: cone frustum, cylinder, plane — `reference/validation.md`).
* LSCM / ARAP (libigl), angle/length distortion minimisation.
* **Minimum strain energy** with the real material (RFEM RF-CUTTING-PATTERN, compensation as a strain load, strains
  after flattening output to evaluate the pattern) [V, S5].
* Inverse methods (Bletzinger et al.) that optimise the pattern so the stresses after assembly match the prestress.
* Doubly curved panels cannot be flattened without strain (Gauss); for a narrow strip of width w on a surface with
  Gaussian curvature K the strain grows with K·w² — halving the panel width divides it by about 4 (validated on
  sphere gores: 30° → 15° gore, max strain 1.77 % → 0.41 %).
* Warning threshold: flattening strain ≤ 0.5 % [U, range 0.3–1.0 %, register `fabrication.flatten_strain_warn_pct`];
  keep it well below the compensation values. No published numeric limit was found (searched: Dlubal, Warwick/TUM
  patterning papers); agree the limit with the patterner.

## 3b. Geodesic seams in this repo
`cutting_pattern.py --seams geodesic`: the start polyline (mesh grid line) is shortened on the triangulated surface. Each
interior point moves to the projection of the midpoint of its neighbours, first on 5 points, then refined 9 → 17 → … up to
the mesh density (multi-level, so it converges in a few sweeps). Panels are rebuilt as ladders between neighbouring seams
(rungs projected on the surface; curved end rows blended into the nearby rungs). Sampling is kept at mesh density: finer
sampling of a faceted mesh concentrates curvature at the facet folds and inflates the flattening strain. Seams whose
geodesic would run into a concave boundary, or wander more than half a panel width, fall back to the grid line;
seams on a support/cable line (arch, ridge, valley) stay on that line.

## 4. Compensation and decompensation
* Shrink each panel by warp and weft percentages so that stressing to prestress recovers the design geometry. Values
  come from biaxial tests at design prestress and stress ratio: EN 17117-2:2021 "Rubber- or plastics-coated fabrics —
  Mechanical test methods under biaxial stress states — Part 2: Determination of the pattern compensation values";
  the final interpretation remains the responsibility of the project engineer [V, S4].
* Typical ranges: PVC 0.5–2 % warp, 1–4 % weft; PTFE/glass warp 0–1 %, weft larger [U]. (The value 1.2 % / 2.5 % quoted
  earlier from a blog could not be re-traced: treat as [U] example only.)
* Convention in this tool: compensated length = (1 − c) × 3D length. (The alternative L/(1 + ε) differs by c², i.e.
  < 0.02 % for c ≤ 1.5 %.) Validated by hand calculation: 6000 × 2000 mm panel, 1.5 % / 0.8 % → 5910.000 × 1984.000 mm.
* Compensation depends on stress level and ratio and on viscoelasticity, so it is batch-specific.
* **Decompensation:** edges that must match a fixed length (clamp lines, frames, pockets with fixed cable length) get
  reduced or zero compensation along that edge (RFEM: different compensations per boundary line [V, S5]; MPanel
  variable/partial compensation).
* This repo's tool: global warp/weft compensation along the panel axes, plus graded decompensation
  (`--decomp-ends`, `--decomp-sides`, `--decomp-length`). Each rung (or panel-length line) is scaled about its midpoint
  so the local compensation goes linearly from the decompensation value at the fixed edge to the full value at the
  transition length (validated station by station against the hand calculation).

## 5. Allowances and details
| Item | Typical | Tag |
|---|---|---|
| Minimum welded width | PVC ≥ 25 mm, PTFE ≥ 50 mm, ETFE ≥ 10 mm (design regulation quoted in S7) | [V, S7] |
| PVC HF seam overlap | 40–60 mm; 50–80 mm heavy types | [U] |
| PTFE heat-seal seam | 50–75 mm; 75–100 mm high grades | [U] (≥ 50 mm [V, S7]) |
| Cable pocket | lay-flat ≈ 1.5–2 d + weld; 25–50 mm closing overlap | [U] |
| Keder pocket | keder Ø 6–12 mm + weld flap | [U] |
| Corner reinforcement | 1–3 doubler plies, 0.5–1.0 m | [U] |
| Hem / edge flap | per edge detail | — |
Tool: allowances are exact parallel offsets of the NET line (seam allowance on seams, edge allowance on boundaries);
convex corners sharper than the mitre limit (default 4 × allowance) are bevelled so the cut line never comes closer
than the allowance (the earlier version pulled the mitre point back and left only 35.6 mm of a 50 mm allowance at a
20° corner — fixed and tested).

## 6. Labelling and marks
Panel ID matching the panel plan; warp arrow; "top/face side"; match marks or notches at seam ends and every
about 0.5–1.0 m [U] along seams; weld lines (pen layer); installation reference marks (centre lines, corner IDs);
compensation values used.

## 7. Nesting and cutting
* Rotation 0° or 180° only (warp along the roll). Strip-packing on a fixed-width roll: SVGnest/Deepnest, freecad-nesting, SqueezeNest.
* This repo: `nest_panels.py`, greedy raster skyline with the clearance kept in both directions and an exact
  polygon check of the result (validated against a known optimum: 4 × 3000 × 1240 mm on a 2500 mm roll, optimum
  6020 mm, tool 6025 mm = optimum + raster step).
* Cutters: Zünd (draw, score, thru-cut modules; Cut Center reads DXF/PDF/AI); Lectra; PTFE often laser-cut (Architen) [U].
* DXF layer convention (WinTess style: cut / draw / fold [U]): this repo uses **CUT** (thru-cut), **NET** (weld/seam line = pen),
  **TEXT**, **WARP**, **DIM**, **NOTCH**. Map layers to cutter tools in the plotter software.
* DXF: R12 (AC1009) ASCII, `$INSUNITS` 70 = 4 (millimetres) [V, S8]; dense polylines (not splines or ellipses) for
  robust import; check issued files with `dxf_reader.py --units-mm`.

## 8. Quality checks on patterns
Seam lengths of mating panels equal (after compensation) within about 1–2 mm/m [U, register
`fabrication.mating_seam_tol_mm_per_m` = 2]; total area versus the 3D area; roll fit; flattening strain; warp arrows
consistent; pocket and corner allowances present; decompensated edges flagged.

## Sources
- S1 Serge Ferrari Tenseo Advanced 1002 S2 datasheet (ex Précontraint / Flexlight Advanced 1002 S2): "Width 267 cm",
  https://makmax.com.au/wp-content/uploads/2025/02/Serge-Ferrari-Tenseo-Advanced-1002S2-EN.pdf ; renaming:
  https://www.sergeferrari.com/us-en/serge-ferrari/news/new-names-serge-ferrari-products
- S2 Nowoflon ET 6235 Z datasheet: width 1,550 mm, other widths on request,
  https://www.buitink-technology.com/pdf/Nowoflon_ET_6235%20Z.pdf ; Tectonica: "standard width of 1550 mm",
  https://tectonica.archi/materials/lamina-transparente-de-etfe/
- S3 Verseidag-Indutex duraskin catalogue pages (B 18039, B 18656: width 300 cm),
  https://pdf.archiexpo.com/pdf/verseidag-indutex/duraskin-b-18039/61073-129885.html
- S4 EN 17117-2:2021 (CEN/TC 248/WG 4), BSI/DIN catalogue entries,
  https://knowledge.bsigroup.com/products/bs-en-17117-2-rubber-or-plastics-coated-fabrics-mechanical-test-methods-under-biaxial-stress-states-part-2-determination-of-the-pattern-compensation-values ,
  https://www.dinmedia.de/en/standard/din-en-17117-2/342737914
- S5 Dlubal RF-CUTTING-PATTERN (geodesic cutting lines, uniform or linear compensation in warp and weft, different
  compensation for boundary lines, strains after flattening output),
  https://dlubal.com/en/products/older-products/rfem-add-on-modules/tensile-membrane-structures/rf-cutting-pattern
- S6 Gale & Lewis, Patterning of tensile fabric structures with a discrete element model using dynamic relaxation,
  Computers & Structures 169 (2016) 112–121 ("Structural fabrics are manufactured with a typical width of 2–3 m [9], and a maximum width of 5 m [10]"),
  https://wrap.warwick.ac.uk/id/eprint/78675/1/WRAP_1-s2.0-S0045794916300608-main.pdf
- S7 Journal of Industrial Textiles 54 (2024), welded seams of PVC membranes: "the design regulation recommends that the
  welded width of PTFE, PVC, and ETFE membrane should not be less than 50 mm, 25 mm, and 10 mm",
  https://journals.sagepub.com/doi/10.1177/15280837241300935
- S8 Autodesk AutoCAD DXF Reference, HEADER variables ($ACADVER group 1, AC1009 = R11 and R12; $INSUNITS group 70,
  4 = Millimeters), https://help.autodesk.com/cloudhelp/2018/ENU/AutoCAD-DXF/files/GUID-A85E8E67-27CD-4C59-BE61-4DC9FADBE74A.htm
