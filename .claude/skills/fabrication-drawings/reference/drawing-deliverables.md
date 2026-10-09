# Fabrication and shop drawing deliverables

Tags: [V] verified (source below), [C] code/standard content, [U] unverified practice value (range given).
Series numbers in §1 are a numbering convention, not design values.

## 1. Drawing register (typical numbering)
| Series | Package | Drawings |
|---|---|---|
| 000 | General | cover, drawing register, general notes, design criteria |
| 100 | GA | plan, elevations, sections, 3D view, setting-out coordinates of all support points |
| 200 | Membrane | panel plan (seams, IDs, warp), cutting sheets (one per panel), seam details, edge details, corner details, reinforcement layering, fabric spec |
| 300 | Cables | cable layout, cable schedule, fitting details, clamp details |
| 400 | Steel | assembly drawings (masts, rings, arches, frames), part drawings (plates, lugs, pins), bolt/pin lists, coating spec |
| 500 | Connections | corner plates, mast heads, bases, anchors, keder/clamp-bar details |
| 600 | Foundations / anchors | anchor layout, anchor details, test requirements |
| 700 | Site | erection sequence, prestressing sequence and targets, measurement plan, tolerances, maintenance and re-tensioning |

## 2. What goes on each drawing
### GA
Stressed geometry; coordinate system and datum; key node coordinates (supports, corners, mast heads); membrane
material and prestress (warp/weft); warp direction; edge types (pocket, keder, belt, clamp); cable IDs; steel member
marks; reference to the analysis report. Tool: `export_dxf.py` (3D) plus the architect's 2D views.

### Panel plan
Seam lines, panel IDs, warp arrows, reinforcement zones, edge-type legend, corner IDs, installation orientation.

### Cutting sheets (per panel)
Flat outline with chord and diagonal dimensions or a coordinate table; CUT and NET lines; compensation values; seam and
hem allowances; match marks; material, batch and roll ID; panel ID; face side. Tool: `cutting_pattern.py` (DXF and CSV).

### Seam, edge and corner details
Weld type (HF, hot-air, heat-seal) and width; number of plies; required seam strength (≥ efficiency × fabric,
tested); pocket geometry; keder size and track; clamp-bar size, bolt size and spacing (≤ ~200 mm [U, 150–250 mm; size by calculation]); belt specification;
corner plate with membrane plate and cut-back; doubler layering.

### Cable schedule
See `cable-tension-members/reference/cable-fabrication.md`. **Unstressed pin-to-pin length at the stated reference
temperature** (and measuring load), stressed length, prestress, F_min, F_Rd, fittings both ends, adjustment range and set
position, clamp marks, coating, certificates. Tool: `cable_schedule.py`.

### Steel assembly and part drawings
* Assembly: member marks, overall dimensions, workpoints, lug orientation (in the cable plane), weld symbols, bolt/pin
  references, coating, EXC, NDT requirements.
* Part: plate outline, thickness, grade (e.g. S355J2+N; Z-quality where needed), holes with tolerance (pin holes H11 per ISO 286-2 fit system [C]; the fit is a project choice [U]),
  edge preparation, mass. Tool: `steel_part_dxf.py` for lugs and corner plates.
* Weld symbols: **ISO 2553:2019** (System A dual reference line; System B single reference line, similar to
  **AWS A2.4**) [V, D1]. Systems A and B shall not be mixed; state the system on the drawing [V, D1].
* Lists: bolts (property class 8.8/10.9 to EN ISO 898-1 [C], preloaded or not; stainless A4-70/80 to EN ISO 3506-1 [C]), pins (grade, diameter, retainer), nuts and washers, BOM.
* Surface treatment: hot-dip galvanising (EN ISO 1461 [C]) with vent and drain holes, or a paint system to the corrosivity category;
  isolation details for aluminium and stainless.

### Site drawings
Erection sequence (stages, temporary works, lifting points and weights); prestressing sequence (which adjusters,
order, target forces, turnbuckle turns or jack pressures); measurement plan (load cells, frequency method, survey targets
and tolerances); hold points; re-tensioning plan.

## 3. Standard general notes (template)
```
1. All dimensions in mm unless noted. Do not scale.
2. Coordinates refer to project grid / datum ____ (+0.000 = ____ m AOD).
3. Geometry shown is the PRESTRESSED design geometry at reference temperature __ °C (commonly 20 °C [U, project choice]).
4. Membrane: ______ (type/class), prestress warp __ kN/m / weft __ kN/m. Compensation per biaxial test report ____.
5. Cable lengths are pin-to-pin, unstressed, at __ °C (= T_ref of the cable schedule), for prestretched cables; measured under __ kN.
6. Steel: EN 1090-2 EXC__; grade ____; welding ISO 2553 System __; NDT per EN 1090-2 (extent of supplementary NDT, Table 24 [C, check the table number in the edition in force]) + ____.
7. Pin holes H11 after coating. Pins ____ with retainers.
8. Isolate aluminium from stainless and galvanised steel (sleeves, washers, tape).
9. No site welding. All site connections pinned or bolted.
10. Tolerances: steel EN 1090-2 geometrical tolerances (Annex B essential / functional tolerances [C]); membrane geometry ±__ mm; prestress ±__ %.
```

## 4. Revision control
Revision table (rev, date, description, drawn, checked, approved), clouds around changes, status stamp (Preliminary /
For comment / For fabrication / As built). Keep the analysis model version referenced on the GA.

## 5. What the tools put on the drawings (tested)
* `steel_part_dxf.py`: title block PROJECT, PART, DWG No, REV, SCALE, DATE, DRAWN, CHECKED, MATERIAL, QTY, MASS, EXC,
  UNITS; outline, holes (HOLES layer, exact centres and diameters), centre marks, dimensions, notes, ISO 2553 weld
  symbol (lug), hole table (corner). Edge distances on the drawn outline are never less than specified.
* `cutting_pattern.py --sheets`: PROJECT, PANEL, MATERIAL, DWG No, REV, SCALE, COMP, SEAMS, NET AREA; CUT and NET
  outlines, notches, warp arrow, overall dimensions, NET-line coordinate table.
* `export_dxf.py`: 3D mesh, cable polylines, support circles and set-out text table (mm, model origin).

## Sources
- D1 ISO 2553:2019 Welding and allied processes - Symbolic representation on drawings - Welded joints (AWS store
  page https://pubs.aws.org/p/1950/iso-25532019-welding-and-allied-processes-symbolic-representation-on-drawings-welded-joints);
  system A/B description and "System A and B shall not be mixed" (secondary: https://materialwelding.com/iso-weld-symbols-explained/,
  SOLIDWORKS forum quoting clause 4.3).
