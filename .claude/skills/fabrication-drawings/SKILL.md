---
name: fabrication-drawings
description: Patterning (cutting patterns) and fabrication/shop drawings for tensile fabric structures with cables and steel — seam layout, flattening, compensation/decompensation, seam and edge allowances, plotter-ready DXF, panel schedules, 3D GA/setting-out DXF, cable schedules, steel part drawings (lug and corner plates) with title blocks, drawing-set contents, conventions (ISO 2553/AWS weld symbols, reference temperature, tolerances), welding/heat-sealing, QC and installation drawings.
---

# Patterning and fabrication drawings

Tags: [V] verified against a named source, [C] code clause / recommended value, [U] unverified practice value
(with a range). Sources are listed in the reference files. Practice thresholds used by the tools live in the
register `tensile-structures/reference/code_factors.json` under `fabrication.*` (read through `factors.py`).
Units: **mm** for all fabrication output and DXF (`$INSUNITS = 4`), model input in m (`--scale 1000`).

## Tools (stdlib Python; R12/AC1009 ASCII DXF read by AutoCAD, BricsCAD, Rhino, Zünd Cut Center, Lectra and others)
| Script | Produces |
|---|---|
| `scripts/cutting_pattern.py` | flattened, compensated panels with seam/edge allowances → `<out>.dxf` (CUT / NET / TEXT / WARP / DIM / NOTCH layers), `<out>.csv` panel schedule, `<out>.json` (polygons for nesting), optional per-panel shop sheets |
| `scripts/nest_panels.py` | nests the panels on the roll (warp along the roll, 0°/180° only, raster skyline) → nested DXF, positions CSV, roll length, utilisation, exact overlap/clearance verification |
| `scripts/export_dxf.py` | 3D GA / coordination DXF: membrane mesh, cable polylines (rings closed), supports with a set-out table, force labels; `--csv` cable and set-out tables |
| `scripts/steel_part_dxf.py` | steel part drawings: `lug` (fork gusset, EN 1993-1-8 Tab 3.9 geometry) and `corner` (hull from hole list, hole table), with frame, title block, mass and edge-distance report |
| `scripts/dxf_writer.py` | minimal DXF library (lines, polylines 2D/3D, arcs, circles, text, arrows, dimension lines, ISO 2553 fillet-weld symbol, title block, auto frame) |
| `scripts/dxf_reader.py` | strict DXF reader/validator (group-code types, sections, tables, layers, POLYLINE/VERTEX/SEQEND, `$ACADVER`, `$INSUNITS`) used to round-trip every output; CLI `dxf_reader.py *.dxf --units-mm` |
| `../cable-tension-members/scripts/cable_schedule.py` | cable schedule (unstressed pin-to-pin lengths at T_ref, fittings, checks) |

Every CLI prints an `Assumptions:` line first; pass it on to the user.

### cutting_pattern.py
```bash
python3 cutting_pattern.py sail.json --panels-along v --strip 3 --comp-warp 0.8 --comp-weft 1.6 \
        --seam 50 --edge 80 --roll-width 2500 --out sail_patterns          # example inputs, not recommendations
```
| Option | Meaning (default) |
|---|---|
| `--panels-along u\|v` | panel long direction = warp (v) |
| `--strip N` | mesh bays per panel width (2) — the main control of panel width and flattening strain |
| `--seams grid\|geodesic` | seams on mesh lines, or relaxed into surface geodesics between their end points (grid) |
| `--comp-warp/--comp-weft %` | compensation, shrink factor (1 − c) along the panel axes (1.0 / 1.5, placeholders: use the biaxial test of the batch) |
| `--decomp-ends %`, `--decomp-sides %`, `--decomp-length mm` | graded decompensation at fixed-length ends / boundary sides over the transition length (off / off / 500) |
| `--seam mm`, `--edge mm` | allowance on seam edges / boundary edges (50 / 80, example values) |
| `--miter-limit k` | convex allowance corners whose mitre exceeds k × allowance are bevelled (4) |
| `--roll-width mm`, `--auto-split` | usable roll width (2500); split panels that do not fit (across for curved panels, along for wide strips; new seams N1, N2 …) |
| `--notch mm` | match-mark spacing along the full seam, identical labels on both mating panels (1000) |
| `--sheets`, `--project`, `--material` | one DXF shop sheet per panel with dimensions, NET coordinate table and title block |
| `--strain-warn %`, `--seam-tol mm/m` | override the register thresholds `fabrication.flatten_strain_warn_pct` = 0.5 % [U, 0.3–1.0] and `fabrication.mating_seam_tol_mm_per_m` = 2 [U, 1–2] |
| `--scale`, `--prefix`, `--out` | model unit → mm (1000), panel ID prefix (P), output stem |

CSV columns: size, roll fit, net / cut / bounding-box area, `area_3d_m2`, `flatten_area_err_%` (flat vs 3D area
before compensation), flattening strain max / RMS / 95th percentile, 3D and compensated seam lengths, neighbours.
The summary prints the **strain distribution** over all edges and diagonals (bins <0.1, 0.1–0.3, 0.3–0.5, 0.5–1.0,
≥1.0 %), the total 3D panel area against the model `surface_area_m2`, and a NOTE when the compensated lengths of
mating seams differ by more than the tolerance.

Warnings: panel wider than the roll; flattening strain above the threshold (→ reduce `--strip`); flattening strain
above half the smaller compensation value (pattern error of the same order as the compensation).

### nest_panels.py
```bash
python3 nest_panels.py mb_patterns.json --gap 20 --dx 25 [--roll-width 2670] --out mb_nest
```
Clearance `--gap` is kept between CUT outlines in both directions (x along the roll and y across); the result is
checked with exact polygon geometry (segment distances + containment) and printed: min clearance, min roll-edge
margin, overlaps. Utilisation is reported as cut area / fabric and net area / fabric, with the area lower bound of the
roll length (cut area / roll width).

### export_dxf.py
```bash
python3 export_dxf.py sail.json --forces --csv [--no-mesh] [--max-setout 60] [--scale 1000] --out sail_GA
```
`--csv` writes `<out>_cables.csv` (group, kind, segments, end nodes and coordinates, node-to-node stressed length,
closed loop, F_max) and `<out>_setout.csv` (all fixed nodes). Use it to cross-check `cable_schedule.py --from-model`.
Branching cable groups are reported and drawn as lines.

### steel_part_dxf.py
```bash
python3 steel_part_dxf.py lug --d0 41 --d 40 --t 20 --a 50 --c 35 --base 160 --height 120 --mark LP-01 --qty 4 \
        [--radius R] [--cheek t] [--weld "double fillet a=8 ..."] [--grade S355J2+N] [--exc EXC2] [--rev A] \
        [--project ..] [--drawn ..] [--checked ..] [--out ..]
python3 steel_part_dxf.py corner --t 25 --edge 45 --hole A:0:0:52 --hole EC1:180:48:33 --hole EC2:48:180:33 \
        --hole M1:95:95:18 --mark CP-01
```
Round heads and hull arcs are drawn as circumscribed polygons, so the drawn edge distance is never less than the
specified one. Mass uses ρ = 7850 kg/m³ [C, EN 1993-1-1 3.2.6, register `fabrication.steel_density_kg_m3`].
Title block: project, part, drawing no, revision, scale, date, drawn, checked, material, quantity, mass, EXC, units.
The lug carries an ISO 2553 System A double-fillet weld symbol with the throat size. A project hook blocks this tool
until the `connection-precedents` gate has passed (see CLAUDE.md).

## Patterning workflow (details: `reference/patterning.md`)
1. **Seam layout** on the form-found (prestressed) surface: along geodesics, warp along the main stress / span,
   panels ≤ usable roll width (e.g. PVC 2.67 m Serge Ferrari [V], ETFE 1.55 m Nowoflon [V]; other products and
   PTFE widths [U], see `reference/patterning.md` §2).
2. **Flatten** each panel: unfold plus least-squares (this tool), or energy minimisation (RFEM, Easy, MPanel). Report the strain error.
3. **Compensate**: shrink warp by c_w % and weft by c_f % from biaxial tests of the batch (EN 17117-2:2021 [V]).
   **Decompensate** boundaries of fixed length (clamp lines, rigid frames, fixed-length cable pockets).
4. **Allowances**: seam overlap (weld width ≥ 25 mm PVC, ≥ 50 mm PTFE [V]; typical PVC 40–60 mm, PTFE 50–75 mm [U]),
   pockets/hems, keder pockets, corner doublers.
5. **Label**: panel ID, warp arrow, face side, match marks and notches along seams, compensation values.
6. **Nest** on the roll (0°/180° only, warp along the roll), then CNC cut (Zünd/Lectra; PTFE often laser-cut). Export dense polylines, not splines.

## Drawing set (details: `reference/drawing-deliverables.md`)
- **Membrane:** GA (plan, elevations, sections, key coordinates, prestress, warp), panel plan, cutting sheets per panel, seam details, edge details, corner details, reinforcement layering.
- **Cables:** cable schedule (pin-to-pin **unstressed length at stated reference temperature**, measuring load, fittings both ends, adjustment, clamp marks, coating, certificates).
- **Steel:** assembly and part drawings, weld symbols ISO 2553:2019 (System A/B) or AWS A2.4 [V], bolt/pin lists, coating, EXC, NDT; connection details (mast heads, corner plates, bases, anchors).
- **Site:** erection sequence, prestressing sequence with targets, measurement plan, tolerances, re-tensioning plan.

## Conventions every sheet needs
Title block (project, title, drawing number, revision table, scale, date, drawn/checked/approved), units (mm),
projection, coordinate system and datum, reference temperature for lengths, material specs, tolerance notes (steel
EN 1090-2 / AISC 303; membrane geometry and prestress tolerance per project), status (preliminary, for approval, for fabrication).

## Cross-checks before issue
- Node-to-pin deductions are identical in the cable schedule, steel drawings and membrane corner cut-backs.
- GA cable lengths (`export_dxf.py --csv`) equal the stressed lengths in `cable_schedule.py --from-model` (tested).
- Panel IDs and warp arrows match between the panel plan and the cutting DXF; panel count and 3D area match the model (tested).
- Compensation values on the cutting sheets match the biaxial test report for the delivered batch.
- Hole diameters and plate thicknesses match the fitting supplier (jaw width, pin Ø).
- The adjustment range at every adjustable end covers the tolerances plus creep.
- Run `dxf_reader.py *.dxf --units-mm` on the issued files.

## Validation (details: `reference/validation.md`)
Tests in `tests/test_fabrication_drawings.py` compare the tools with independent references: cone frustum →
exact annular sector (radii, angle, arcs, area to 1e-9), cylinder → exact rectangle, sphere gores → closed-form gore
widths/length/area (sinusoidal gore) and K·w² strain scaling, compensation/decompensation hand calculations, exact
offset geometry (rectangle, incentre-scaled triangle, bevel area), DXF round trips of every writer against the
source geometry (and the Autodesk group-code rules), nesting against a known optimum, steel part outline/holes/edge
distances/mass against the input, panel and cable schedules against the model.

## Limitations
- **Flattening is geometric** (unfold + least-squares of edge lengths of the panel mesh). It does not use the fabric
  stiffness, the stress ratio or shear stiffness, unlike energy/FE patterning (MPanel, Easy/technet, RFEM
  RF-CUTTING-PATTERN, ixForten, inverse methods). On non-developable panels the residual strain is reported, not
  minimised in stress terms. Developable panels (cones, cylinders, planes) are exact (validated).
- **Accuracy follows the mesh**: panels are built from the form-finding mesh (`--seams grid` uses mesh nodes; seams
  are polylines, chord error O(h²)); a coarse mesh gives coarse panel edges. Use a fine form-finding mesh for production.
- **Compensation is uniform per direction** (plus linear decompensation) in the panel's principal axes; it assumes
  the warp runs along the panel length. Non-linear, stress-dependent or panel-specific compensation from biaxial
  tests (EN 17117-2) must be applied by the patterner.
- End decompensation scales each rung about its midpoint. Where rungs are inclined to the seams (corner panels of
  sails) this also changes the compensated seam length, differently on the two mating panels (demo sail with
  `--decomp-ends 0 --decomp-length 500`: 2.8–3.0 mm/m; without decompensation they match within 0.3 mm/m). The tool
  flags it (`NOTE: seam … differ by … mm/m`); the patterner must equalise the seam before cutting.
- Allowances are plain offsets; pocket geometry, keder flaps, corner cut-backs, reinforcement plies and weld-shrinkage
  are not modelled; corners beyond the mitre limit are bevelled.
- Nesting is a greedy raster skyline (0°/180°), not an optimiser; compare with the cutter's nesting software.
- GA DXF shows the stressed geometry; cable fabrication lengths come from `cable_schedule.py`. Steel part drawings
  are geometry only: size and check with `tensile-connections` tools first.
- Thresholds (`fabrication.*`) are practice values [U], not code requirements.
- **All patterns and shop drawings must be checked and approved by the fabricator/patterner** (with their software
  and the batch test data) before cutting; this tool is for design-stage patterns, quantity estimates and checks.

## References
- `reference/patterning.md`: flattening methods, compensation, allowances, roll widths, nesting, DXF layer conventions.
- `reference/drawing-deliverables.md`: full list of drawings, what goes on each, templates for notes and tables.
- `reference/fabrication-processes.md`: HF/hot-air welding, PTFE heat sealing, seam testing, QC, handling, packing, installation.
- `reference/validation.md`: validation table (case, independent reference, expected, obtained, error, tolerance).
