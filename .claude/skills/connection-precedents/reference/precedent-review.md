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
| Key | Good when | Red flag when "no" | Verify with |
|---|---|---|---|
| concurrent | all lines of action through one pin or axis | eccentric moment in plate/mast | `corner_plate.py` |
| in_plane | plates lie in their force planes (toggle where the plane changes) | out-of-plane bending, weld tearing | `steel_joint_checks.py weld`, `pin_connection.py` |
| rotation | pins/toggles follow the changing load direction | bending in fork or cable end, fatigue | `pin_connection.py`, `fatigue_check.py` |
| adjustable | take-up range visible | no allowance for tolerance and creep | `cable_calc.py stress-turns` |
| membrane_safe | rounded edges, protected bolt heads | fabric tear at corners or clamps | `membrane_check.py --corner` |
| drainage | open sections, drain holes, sloped tops | water and dirt traps, corrosion | detailing |
| isolation | stainless/aluminium separated from galvanised steel | galvanic corrosion | detailing |
| replaceable | membrane/cables removable without hot work | costly replacement | detailing |

## 3. Typical red flags in published pictures [U]
- Corner plate with holes placed "neatly" rather than on the force lines (eccentric).
- A single lug welded at an angle to the cable plane, or a fork bent by misalignment.
- Shade-sail hardware (eye bolts, open hooks, carabiners) on permanent structures.
- Steel edges or bolt threads touching the membrane. No cut-back at the corner (wrinkles, tear start).
- Aluminium clamp bars bolted to galvanised steel without isolation. Stainless bolts in aluminium without sleeves.
- Closed boxes or upturned channels that collect water.
- No adjustment anywhere in the load path.

## 4. From ideas to a design
- Write each idea as a rule we can check, e.g. "two edge-cable forks on one pin, strap on a separate hole on the bisector".
- Combine ideas from several precedents. Keep each idea traceable (precedent #).
- Then follow the `tensile-connections` design procedure. Change the idea when a check fails; do not change the check.
