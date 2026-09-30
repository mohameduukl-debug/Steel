# Design workflow checklist: tensile fabric + cable + steel

Tick each item. Items marked ⛔ are hold points: do not proceed until resolved.

## 0. Brief and basis of design
- [ ] Design life, consequence class (CC1/2/3), permanent vs temporary (EN 13782 for tents).
- [ ] Codes, editions and National Annexes (see `standards-map.md`). Client/insurer rules (e.g. FM DS 1-59).
- [ ] Site: wind (basic velocity, terrain, topography), snow (s_k, altitude), seismic, corrosivity category, temperature range.
- [ ] Functional needs: clearances, drainage, lighting, translucency, fire (Euroclass), acoustics, maintenance access.
- [ ] Material family chosen (PVC/PES, glass/PTFE, silicone/glass, ETFE, ePTFE, mesh): strength class, roll width.

## 1. Form finding
- [ ] Boundary: fixed points, rigid edges, cable edges, masts, rings (heights and plan).
- [ ] Prestress target (warp/weft, ratio) and edge-cable force density or sag target (8–12 % chord).
- [ ] Double curvature everywhere; no flat zones; slope/drainage direction checked.
- [ ] Mesh / seam direction chosen (warp along main span or principal stress).
- ⛔ Architect approval of form (heights, sags, clearances).

## 2. Analysis
- [ ] Material stiffness from biaxial tests (EN 17117-1) or justified literature values.
- [ ] Cable EA from supplier (prestretched E × metallic area); steel stiffness included.
- [ ] Load cases: PS, G, S (uniform, drift, asymmetric), W (several directions, pressure and suction; tunnel/CFD or conservative Cp), T, erection stages, relaxed prestress.
- [ ] Combinations analysed non-linearly and separately (no superposition).
- [ ] Results: membrane stress (warp, weft, principal), deflections, slack/wrinkled zones, ponding check on the deformed shape, cable forces (max and min), reactions (envelope + concurrent sets).
- ⛔ No ponding, no slack cables where not permitted, clearances respected.

## 3. Member design
- [ ] Membrane: fabric + seams + corners (stress factor / partial factor method), tear propagation.
- [ ] Cables: ULS (F_Rd), SLS limit, no-slack, fatigue if wind-excited; fittings matched.
- [ ] Steel: masts/struts buckling (EN 1993-1-1 §6.3), arches (in- and out-of-plane), rings, frames, base plates.
- [ ] Foundations: uplift, sliding, overturning, anchor tests.

## 4. Connections
- [ ] Corner plates: concurrency, plate in the cable plane, pins and lugs (Tab. 3.9/3.10), membrane plate/strap.
- [ ] Mast heads: plates in the cable planes, concurrency on the mast axis, weld design, Z-quality if through-thickness.
- [ ] Clamp lines / keder tracks: spacing, bolt size, extrusion, bimetallic isolation.
- [ ] Tensioning devices: adjustment range covers fabrication + erection tolerance + creep re-tensioning.
- [ ] Execution class (EXC2 typical, EXC3 fatigue/CC3), NDT scope.

## 5. Patterning and fabrication information
- [ ] Seam layout (geodesic), panel widths ≤ usable roll width, warp directions.
- [ ] Compensation values from biaxial tests of the delivered batch (EN 17117-2); decompensation at fixed-length boundaries.
- [ ] Allowances: seams, pockets, hems, keder; corner reinforcement layers.
- [ ] Cutting DXF (CUT / NET / TEXT / WARP layers), panel IDs, match marks.
- [ ] Cable schedule: unstressed pin-to-pin lengths at reference temperature, fittings, clamp marks, measuring load.
- [ ] Steel shop drawings: assemblies, parts, weld symbols (ISO 2553 / AWS A2.4), bolts and pins list, coating.
- ⛔ Cross-check: node-to-pin deductions consistent between cable schedule, steel drawings and membrane corners.

## 6. Installation
- [ ] Erection sequence, temporary works, lifting points.
- [ ] Prestress introduction method (mast jacking, corner screws, cable shortening) and sequence.
- [ ] Prestress/measurement plan: target forces, turnbuckle positions, survey points, tolerances.
- [ ] Re-tensioning plan (PVC creep) and inspection/maintenance manual.
