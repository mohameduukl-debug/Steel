---
name: fabrication-drawings
description: Patterning (cutting patterns) and fabrication/shop drawings for tensile fabric structures with cables and steel — seam layout, flattening, compensation/decompensation, seam and edge allowances, plotter-ready DXF, panel schedules, 3D GA/setting-out DXF, cable schedules, steel part drawings (lug and corner plates) with title blocks, drawing-set contents, conventions (ISO 2553/AWS weld symbols, reference temperature, tolerances), welding/heat-sealing, QC and installation drawings.
---

# Patterning and fabrication drawings

## Tools (stdlib Python, R12 DXF readable by AutoCAD, BricsCAD, Rhino, Zünd Cut Center, Lectra and others)
| Script | Produces |
|---|---|
| `scripts/cutting_pattern.py` | flattened, compensated panels with seam/edge allowances → `patterns.dxf` (CUT / NET / TEXT / WARP / DIM layers) + `patterns.csv` (size, roll fit, area, flattening strain) |
| `scripts/export_dxf.py` | 3D GA / coordination DXF: membrane mesh, edge-cable polylines, supports with a set-out table, force labels |
| `scripts/steel_part_dxf.py` | steel part drawings: `lug` (fork gusset, Tab 3.9 geometry) and `corner` (hull from hole list, hole table), with frame and title block |
| `scripts/dxf_writer.py` | minimal DXF library (lines, polylines 2D/3D, arcs, circles, text, arrows, dimensions, title block, auto frame) |
| `../cable-tension-members/scripts/cable_schedule.py` | cable schedule (unstressed pin-to-pin lengths at T_ref, fittings, checks) |

```bash
python3 cutting_pattern.py sail.json --panels-along v --strip 3 --comp-warp 0.8 --comp-weft 1.6 \
        --seam 50 --edge 80 --roll-width 2500 --out sail_patterns
python3 export_dxf.py sail.json --forces --out sail_GA
python3 steel_part_dxf.py lug --d0 41 --d 40 --t 20 --a 50 --c 35 --base 160 --height 120 --mark LP-01 --qty 4
python3 steel_part_dxf.py corner --t 25 --edge 45 --hole A:0:0:52 --hole EC1:180:48:33 --hole EC2:48:180:33 \
        --hole M1:95:95:18 --mark CP-01
```
**Geodesic seams + decompensation:**
```bash
python3 cutting_pattern.py sail.json --seams geodesic --strip 2 --comp-warp 0.8 --comp-weft 1.6 \
        --decomp-ends 0 --decomp-length 500 --out sail_patterns
```
- `--seams geodesic`: every seam is relaxed on the surface into the shortest path between its boundary end points
  (multi-level string shortening with closest-point projection). Adjacent panels share the same 3D seam curve, so
  mating seam lengths match. A geodesic that would run into a concave (scalloped) edge is rejected for that seam; the
  grid line is used and a NOTE is printed.
- `--decomp-ends X`: weft compensation at the panel ends (edge-cable pockets or clamp lines of fixed length) grades
  linearly from the full value to X % over `--decomp-length` mm. `--decomp-sides X` does the same for warp along
  boundary sides (not seams). Exactness is tested: a 0 % end keeps its 3D width.

Read the warnings: panel wider than the roll, or flattening strain > 0.5 %, means reduce `--strip` (narrower panels).
Flattening starts at the panel centre and relaxes to convergence, so results are symmetric for symmetric shapes;
remaining strain reflects real double curvature (e.g. arch-supported bays), so use narrower panels there.

## Patterning workflow (details: `reference/patterning.md`)
1. **Seam layout** on the form-found (prestressed) surface: along geodesics, warp along the main stress / span,
   panels ≤ usable roll width (PVC 2.50–2.67 m, PTFE 3.8–4.7 m, ETFE ~1.55 m [V]). PTFE is often seamed at 1.5–2.5 m.
2. **Flatten** each panel: unfold plus least-squares (as in this tool), or energy minimisation (RFEM, Easy, MPanel). Report the strain error.
3. **Compensate**: shrink warp by c_w % and weft by c_f % (biaxial tests of the batch, EN 17117-2). **Decompensate**
   boundaries of fixed length (clamp lines, rigid frames, fixed-length cable pockets).
4. **Allowances**: seam overlap (PVC 40–60 mm, PTFE 50–75 mm), pockets/hems, keder pockets, corner doublers.
5. **Label**: panel ID, warp arrow, face side, match marks and notches along seams, compensation values.
6. **Nest** on the roll (0°/180° only, warp along the roll), then CNC cut (Zünd/Lectra; PTFE often laser-cut). Export dense polylines, not splines.

## Drawing set (details: `reference/drawing-deliverables.md`)
- **Membrane:** GA (plan, elevations, sections, key coordinates, prestress, warp), panel plan, cutting sheets per panel, seam details, edge details, corner details, reinforcement layering.
- **Cables:** cable schedule (pin-to-pin **unstressed length at stated reference temperature**, measuring load, fittings both ends, adjustment, clamp marks, coating, certificates).
- **Steel:** assembly and part drawings, weld symbols ISO 2553 (System A/B) or AWS A2.4, bolt/pin lists, coating, EXC, NDT; connection details (mast heads, corner plates, bases, anchors).
- **Site:** erection sequence, prestressing sequence with targets, measurement plan, tolerances, re-tensioning plan.

## Conventions every sheet needs
Title block (project, title, drawing number, revision table, scale, date, drawn/checked/approved), units (mm),
projection, coordinate system and datum, reference temperature for lengths, material specs, tolerance notes (steel
EN 1090-2 / AISC 303; membrane geometry and prestress tolerance per project), status (preliminary, for approval, for fabrication).

## Cross-checks before issue
- Node-to-pin deductions are identical in the cable schedule, steel drawings and membrane corner cut-backs.
- Panel IDs and warp arrows match between the panel plan and the cutting DXF.
- Compensation values on the cutting sheets match the biaxial test report for the delivered batch.
- Hole diameters and plate thicknesses match the fitting supplier (jaw width, pin Ø).
- The adjustment range at every adjustable end covers the tolerances plus creep.

## References
- `reference/patterning.md`: flattening methods, compensation, allowances, roll widths, nesting, DXF layer conventions.
- `reference/drawing-deliverables.md`: full list of drawings, what goes on each, templates for notes and tables.
- `reference/fabrication-processes.md`: HF/hot-air welding, PTFE heat sealing, seam testing, QC, handling, packing, installation.
