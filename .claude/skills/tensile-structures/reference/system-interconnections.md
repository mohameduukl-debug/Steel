# How fabric, cables and steel connect and interact

## 1. Structural roles

| Component | Carries | Stiffness comes from | Cannot do |
|---|---|---|---|
| Membrane (PVC/PES, glass/PTFE, silicone/glass, ETFE, ePTFE) | biaxial tension n_w, n_f [kN/m] | prestress × curvature (geometric stiffness) + E·t | compression, bending, point loads |
| Cables (spiral strand, FLC, wire rope, rods) | axial tension T [kN] | EA/L (elastic) + T/L (geometric) | compression, bending; slack = no stiffness |
| Steel (masts, struts, arches, rings, frames, booms) | compression, bending, shear | EI, EA | usually designed to avoid bending from cables (concurrent geometry) |
| Foundations / anchors | uplift, horizontal pull, compression | soil / rock / mass | — |

## 2. Governing equilibrium relations

* Membrane surface: n₁/R₁ + n₂/R₂ = p (principal directions). With no load (p = 0) on
  an anticlastic surface: n_w/R_w = n_f/R_f. So **stress ratio = curvature ratio**.
* Edge cable: T = n·R (n = membrane stress normal to the cable, R = cable radius in
  the membrane tangent plane). Circular approximation R = c²/(8s) + s/2.
* Straight cable under distributed load w: H = wL²/(8f); T_max = H·√(1+16(f/L)²).
* Corner plate: Σ F = 0 **and** Σ M = 0. The lines of action of the edge cables,
  membrane strap and anchor meet at one point, and the plate lies in the plane of the
  edge cables.
* Mast head: resultant of all cable forces along the mast axis (pinned base), or
  moment into the mast and foundation (fixed base).

## 3. Interfaces (every one needs a detail and a check)

### Fabric ↔ cable
| Detail | Use | Key checks |
|---|---|---|
| Cable in welded **pocket/sleeve** (catenary edge) | PVC and some PTFE edges | pocket width (cable + clearance so it slides), seam peel, edge shear; belts parallel to edge on larger canopies |
| **External cable + clamp plates** (keder edge held by plate pairs, strap or U-bolt to cable) | PTFE/glass, large spans | clamp spacing ≤ ~200 mm (TensiNet), keder not squeezed through gap, slip |
| **Webbing belt edge** | small PVC canopies | belt MBL / high textile factor, stitch/weld efficiency |
| Ridge/valley cable over the fabric (cushion strip) | multi-bay hypar/saddle roofs | abrasion, local radius, clamp slip |

### Fabric ↔ steel (rigid boundary)
| Detail | Use | Key checks |
|---|---|---|
| **Keder** (6–12 mm PVC rope) in aluminium luff-track | frames, arches, façades | slot ≈ 60–70 % of keder dia, pull-out, extrusion bending, bimetallic isolation |
| **Clamp bar** (flat bar strips, stainless bolts) | rigid edges, corners, ring beams | bolt spacing ≤ ~200 mm, segment joints staggered and chamfered |
| Adjustable edge (track on threaded studs) | tensioning at rigid boundary | adjustment range, stud bending |
| Arch sleeve / pad or keder rails both sides | arch-supported roofs | abrasion, sliding vs fixed boundary |
| **Bale ring / top ring** (cone) | conic tents | ring bending, fabric clamping, rain cap |

### Cable ↔ steel
| Detail | Use | Key checks |
|---|---|---|
| **Fork (clevis) + pin + lug/gusset** | almost all cable ends | EN 1993-1-8 Tab. 3.9/3.10, AISC D5/J7; lug in cable plane |
| Eye + pin in double lug (fork on steel) | alternative | same checks |
| Threaded socket through anchor plate + nut | stays, adjustable anchors | bearing plate, thread, fatigue |
| Saddle / clamp on mast head or ring | continuous cables | min radius, transverse pressure, slip resistance |
| Turnbuckle / threaded fork / tension rod | adjustment | range, thread engagement, locking |

### Steel ↔ ground
Hinged mast base (pin, cardan or spherical bearing), base plate + anchor bolts,
ground anchors for tie-backs (helical, grouted rock, deadman), tension piles.

## 4. How design decisions ripple through the system

| Change | Membrane | Cables | Steel/foundations | Fabrication |
|---|---|---|---|---|
| Increase edge sag | more curvature at edge, less fabric area | T ↓ | corner reactions ↓ | shorter panels near edge |
| Increase prestress | stiffer, less deflection/ponding, more creep | T ↑ | all reactions ↑ | larger compensation, higher installation force |
| Lower high points (flatter) | stresses ↑, ponding risk | T ↑ | mast N ↓ but tie-back ↑ | — |
| Pinned → fixed mast base | — | — | mast M, foundation moment ↑↑ | stiffer base detail |
| Glass/PTFE instead of PVC | stiffer, low creep, no folding | clamp-plate edges preferred | similar | heat-sealed seams, careful handling |
| Mast head deflects | prestress lost locally | T changes | second-order effects | adjustment range must cover |

## 5. Typical failure / damage modes by interface

* Corner wrinkling: non-concurrent corner plate, too little cut-back, unequal edge-cable forces.
* Edge-pocket seam peel: cable friction in a tight pocket, no edge belts.
* Tear from clamp-bar ends: sharp segment joints, no chamfer or radius.
* Ponding: flat zones, low prestress, snow on synclastic basin.
* Flutter / fatigue: low prestress, loose pins (large d₀ − d), cable vibration at sockets.
* Mast-head plate bending: plates not in the cable planes, non-concurrent cables.
* Foundation pull-out: uplift under wind suction plus the prestress pull.
* Slack cables in some combinations (lost stiffness): check F_min > 0 in every combination.
