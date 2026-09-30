# Patterning (cutting patterns)

## 1. Seam layout
* Seams on **geodesic lines** of the prestressed surface: minimum waste, no seam-induced stress [V].
* Drivers: warp direction (along principal stress / main span, panel length), roll width, aesthetics, fabric yield,
  curvature. Add seams where the flattening error becomes too large (spec 13 31 23) [V].
* Radial seams on cones; seams parallel to the high-low diagonal or across the span on hypars. Avoid seams ending at
  corner plates with sharp angles.

## 2. Roll widths [V]
| Material | Product | Width |
|---|---|---|
| PES/PVC | Serge Ferrari Précontraint/Tenseo 1002 S2, 1302 S2, Flexlight | 267 cm |
| PES/PVC | Serge Ferrari Advanced 902–1502 S2 (Gumpp) | 260 / 180 cm |
| PES/PVC | Mehler Valmex FR 1000 Type III | 250 cm (300 on request) |
| PES/PVC | Verseidag Duraskin B4915 / B4951 | 250 cm |
| glass/PTFE | Verseidag Duraskin B18089 | 470 cm (up to 5 m) |
| glass/PTFE | Chukoh FGT-800 / FGT-1000 | 3800 mm |
| ETFE | Nowoflon ET 6235 Z | 1550 mm |
Usable width = roll − selvedges − seam allowances.

## 3. Flattening methods
* Geometric triangle unfolding (exact along one path; errors accumulate).
* **Least squares on edge lengths** (this repo): unfold, then iterative relaxation of all edges and diagonals; report max/RMS strain.
* LSCM / ARAP (libigl), angle/length distortion minimisation.
* **Minimum strain energy** with the real material (RFEM "frictionless press", compensation as a strain load) [V].
* Inverse methods (Bletzinger et al.) that optimise the pattern so the stresses after assembly match the prestress.
Accept flattening strain well below the compensation values (≤ ~0.3–0.5 % [U rule]); otherwise narrow the panels.

## 3b. Geodesic seams in this repo
`cutting_pattern.py --seams geodesic`: the start polyline (mesh grid line) is shortened on the triangulated surface. Each
interior point moves to the projection of the midpoint of its neighbours, first on 5 points, then refined 9 → 17 → … up to
the mesh density (multi-level, so it converges in a few sweeps). Panels are rebuilt as ladders between neighbouring seams
(rungs projected on the surface; curved end rows blended into the nearby rungs). Sampling is kept at mesh density: finer
sampling of a faceted mesh concentrates curvature at the facet folds and inflates the flattening strain. Seams whose
geodesic would run into a concave boundary fall back to the grid line.

## 4. Compensation and decompensation
* Shrink each panel by warp and weft percentages so that stressing to prestress recovers the design geometry. Values come from biaxial tests at
  design prestress and stress ratio (EN 17117-2:2021) [V]. Example 1.2 % warp / 2.5 % weft [V, blog]; typical PVC 0.5–2 %
  warp, 1–4 % weft; PTFE warp 0–1 %, weft larger [U].
* Compensation depends on stress level and ratio and on viscoelasticity, so it is batch-specific.
* **Decompensation:** edges that must match a fixed length (clamp lines, frames, pockets with fixed cable length) get
  reduced or zero compensation along that edge (MPanel variable/partial; RFEM per boundary line) [V].
* This repo's tool: global warp/weft compensation along the panel axes, plus graded decompensation
  (`--decomp-ends`, `--decomp-sides`, `--decomp-length`). Each rung (or panel-length line) is scaled about its midpoint
  so the local compensation goes linearly from the decompensation value at the fixed edge to the full value at the
  transition length (MPanel-style partial decompensation).

## 5. Allowances and details
| Item | Typical |
|---|---|
| PVC HF seam overlap | 40–60 mm (≥ 25 mm minimum in some rules) [V]; 50–80 mm heavy types [U] |
| PTFE heat-seal seam | 50–75 mm [V]; 75–100 mm high grades [U] |
| Cable pocket | lay-flat ≈ 1.5–2 d + weld; 25–50 mm closing overlap [V/U] |
| Keder pocket | keder Ø (6–12 mm) + weld flap |
| Corner reinforcement | 1–3 doubler plies, 0.5–1.0 m [U] |
| Hem / edge flap | per edge detail |

## 6. Labelling and marks
Panel ID matching the panel plan; warp arrow; "top/face side"; match marks or notches at seam ends and every
about 0.5–1.0 m along seams; weld lines (pen layer); installation reference marks (centre lines, corner IDs); compensation values used.

## 7. Nesting and cutting
* Rotation 0° or 180° only (warp along the roll). Strip-packing on a fixed-width roll: SVGnest/Deepnest, freecad-nesting, SqueezeNest.
* Cutters: Zünd (draw, score, thru-cut modules; Cut Center reads DXF/PDF/AI) [V]; Lectra; PTFE often laser-cut (Architen) [V].
* DXF layer convention (WinTess style: cut / draw / fold [V]): this repo uses **CUT** (thru-cut), **NET** (weld/seam line = pen),
  **TEXT**, **WARP**, **DIM**. Map layers to cutter tools in the plotter software.
* Export polylines with dense vertices (not splines or ellipses) for robust import.

## 8. Quality checks on patterns
Seam lengths of mating panels equal (after compensation) within about 1–2 mm/m; total area versus the 3D area; roll fit; flattening
strain; warp arrows consistent; pocket and corner allowances present; decompensated edges flagged.
