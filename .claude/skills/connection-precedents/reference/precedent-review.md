# Reading a connection precedent (photo, sketch or shop drawing)

[U] = practice guidance for reviewing pictures. Code requirements are in the `tensile-connections` references.

## 1. What to identify in each picture
1. **Node type and scale**: shade sail (a few kN) or roof (hundreds of kN)? Count the bolts, estimate the plate size relative to a
   hand, person or vehicle. Only take ideas from precedents of a similar scale.
2. **Load path**: follow each cable, strap or membrane edge into the steel. Where does each force enter, and through what (pin, bolt, weld,
   clamp)? Where does it leave (mast, anchor, beam)?
3. **Geometry**: do the lines of action of all members meet at one point? Is each plate in the plane of its cable?
4. **Movement**: what rotates (pins, toggles, spherical bearings) and what is fixed?
5. **Adjustment**: where is the take-up (turnbuckle, threaded fork, adjustable socket, corner screw, slotted holes, jacking at the mast)?
6. **Fabric interface**: keder, clamp bars, pocket, belts. Edges rounded? Corner cut back? Reinforcement plies visible?
7. **Finish and durability**: galvanised, painted, stainless; isolation washers; drain holes; water traps.
8. **Erection and replacement**: can the membrane be installed and tensioned with these parts, and replaced later?

## 2. Feature checklist (keys used by `precedent_search.py board`)
Weights: 3 = critical (structural safety), 2 = function, 1 = durability. `n/a` drops a feature from the score
(some are n/a per node, e.g. concurrency on a clamp bar). `?` counts as not shown.

| Key | Weight | Good when | Red flag when "no" | Verify with |
|---|---|---|---|---|
| concurrent | 3 | all lines of action through one pin or axis | eccentric moment in plate/mast | `corner_plate.py` |
| in_plane | 3 | plates lie in their force planes (toggle where the plane changes) | out-of-plane bending, weld tearing | `steel_joint_checks.py weld`, `pin_connection.py` |
| rotation | 2 | pins/toggles follow the changing load direction | bending in fork or cable end, fatigue | `pin_connection.py`, `fatigue_check.py` |
| adjustable | 2 | take-up range visible | no allowance for tolerance and creep | `cable_calc.py stress-turns` |
| membrane_safe | 3 | rounded edges, protected bolt heads | fabric tear at corners or clamps | `membrane_check.py --corner` |
| drainage | 1 | open sections, drain holes, sloped tops | water and dirt traps, corrosion | detailing |
| isolation | 1 | stainless/aluminium separated from galvanised steel | galvanic corrosion | detailing |
| replaceable | 1 | membrane/cables removable without hot work | costly replacement | detailing |

## 3. Image type and scale
| kind | Evidence factor | Notes |
|---|---|---|
| photo | 1.0 | built detail; the best evidence, also of mistakes |
| shop_drawing | 1.0 | fabrication or detail drawing |
| manufacturer | 0.9 | catalogue or product photo of structural hardware |
| sketch | 0.8 | designer's hand sketch: good for principles |
| render | 0.7 | CAD/3D render, not yet built |
| product | 0.5 | consumer listing (Home Depot, Amazon kits): counts as form only |
| infographic | 0.3 | explanatory graphic; often simplified or wrong. Not counted by the gate |
| ai_generated | 0.2 | AI image: smooth, plausible and often impossible. Not counted by the gate |

Scale: sail (a few kN), canopy (tens of kN), roof (≈100 kN and more), stadium. A gap of 2 classes from the
project makes a precedent "form only".

Signs of an AI or infographic image: perfect lighting, text labels on the picture, fittings that do not connect,
cables that end nowhere, the same bolt repeated, no weld seams.

## 4. Typical red flags in published pictures [U]
- Corner plate with holes placed "neatly" rather than on the force lines (eccentric).
- A single lug welded at an angle to the cable plane, or a fork bent by misalignment.
- Shade-sail hardware (eye bolts, open hooks, carabiners) on permanent structures.
- Steel edges or bolt threads touching the membrane. No cut-back at the corner (wrinkles, tear start).
- Aluminium clamp bars bolted to galvanised steel without isolation. Stainless bolts in aluminium without sleeves.
- Closed boxes or upturned channels that collect water.
- No adjustment anywhere in the load path.
- Edge cable wrapped round the plate and closed with wire-rope clips; cable passing through holes in the fabric hem
  (seen on regional contractor pins, worked example #20).
- Wire rope looped directly over webbing (abrasion), marine shackles as permanent hardware (worked example #13).
- Tie-back attached below the catenary connection on a pinned mast, so the lines do not meet (worked example #7).

## 5. From ideas to a design
- Write each idea as a rule we can check, e.g. "two edge-cable forks on one pin, strap on a separate hole on the bisector".
- Combine ideas from several precedents. Keep each idea traceable (precedent #, `from`). Mark `detail: true` only
  for ideas taken from an "ideas + details" precedent; from a form-only precedent take the principle, not the hardware.
- Then follow the `tensile-connections` design procedure. Change the idea when a check fails; do not change the check.
