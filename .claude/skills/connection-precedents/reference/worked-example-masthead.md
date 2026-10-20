# Precedent board: Mast head (radiating cables / membrane peak)

Project: scale canopy, material S355 CHS 168.3x8 pinned masts, Galfan 17 mm edge cables (examples/run_demo.sh)

Searched: `tensile membrane mast head detail cables`; `flying mast head ear plates tensile structure`; `رأس عمود مظلات شد إنشائي`; `tensile structure mast head detail`

## Precedents (ranked: weighted quality x evidence x judged share)

| # | Precedent | Kind | Scale | Quality /10 | Rank | Red flags | Use |
|---|---|---|---|---|---|---|---|
| 4 | [Fabric installing by BDiR Team / Steel conveyor belt structure, Tensil](https://www.pinterest.com/pin/833165999797873668/) | photo | canopy | 8.8 | 8.2 | - | ideas + details |
| 12 | [Kaplama Galerisi - Carré des Arts Avlusu / Architektonisches tragwerks](https://www.pinterest.com/pin/904097693919301836/) | shop_drawing | canopy | 8.8 | 8.2 | - | ideas + details |
| 6 | [Metal Structure Against Blue Sky / Lonas tensadas, Tensionadas, Cubier](https://www.pinterest.com/pin/833165999803313158/) | photo | canopy | 6.9 | 6.45 | concurrent | form only |
| 7 | [Tensile Fabric Structure Details / Fabric Architecture / Concrete pipe](https://www.pinterest.com/pin/308848486923066516/) | shop_drawing | canopy | 6.2 | 5.68 | concurrent | form only |
| 10 | [Mast (Canopy) in Modernist Architecture / Marine canopy, Tensile membr](https://www.pinterest.com/pin/904097693919301611/) | photo | roof (gap 1) | 5.6 | 4.39 | - | ideas + details |
| 11 | [Cubierta de Membrana Proyecto : Dunn Arquitectura ligera Aguascaliente](https://www.pinterest.com/pin/904097693919301630/) | photo | roof (gap 1) | 5.6 | 4.39 | - | ideas + details |
| 14 | [Architectural details : Tensile Structures! / Tent structure detail, T](https://www.pinterest.com/pin/209276713930620109/) | infographic | roof (gap 1) | 0.0 | 0.0 | - | form only |

Off-topic or rejected: #2, #9, #16, #20

Not reviewed (image not viewed, not used): #1, #3, #5, #8, #13, #15, #17, #18, #19

## Ideas to take (with the precedents that show them)

- double ear plates on the mast head with one large pin  (#4)
- fork + toggle link between ear plates and corner plate: rotation in two planes  (#4)
- edge cables as threaded stainless rods into the corner plate: adjustment at the head  (#4)
- clamp bracket on the frame tube instead of welding to it  (#6)
- end cap closing the mast tube  (#7)
- open swage socket + turnbuckle on the tie-back  (#7)
- flying mast: radial cables below meet in one forged node  (#10)
- spoke ring at the head keeps the fabric clear of the mast (oculus, no point load on fabric)  (#10)
- ring with radial spokes at the mast head instead of a fabric-to-mast clamp  (#11)
- draw the lines of action (dash-dot) on the shop drawing and make them meet at the support pin  (#12)
- clevis bracket of two plates on a base plate at the support; threaded rod adjuster on the bisector  (#12)
- clamp strips on each edge, corner cut back  (#12)

## Do not copy (red flags seen)

- #6 concurrent [critical]: eccentric node: moment in the plate and the support (check with corner_plate.py)
- #7 concurrent [critical]: eccentric node: moment in the plate and the support (check with corner_plate.py)

## Agreed concept

Mast-head cap plate with a pair of ear plates in the vertical plane of the corner resultant and the tie-back; one head pin where the corner resultant, the tie-back and the mast axis meet; corner plate hung from the pin by a fork + toggle link; tie-back with open socket + threaded adjuster.
- double ear plates on the mast cap with one head pin  (from #4, #12)
- fork + toggle link to the corner plate (rotation in two planes)  (from #4)
- tie-back on the same pin as the corner (fix of the eccentric layout in #7)  (from #7, #12)
- end cap closing the mast tube  (from #7)
- lines of action drawn on the shop drawing  (from #12)

## Verification of the concept (tool output)

- corner_plate.py --v corner:-0.6767:-0.6767:-0.2900:123.4 --v tieback:0.4545:0.4545:-0.7660:183.9
- tie-back at 50 deg below horizontal needs 183.9 kN so that the head resultant is along the mast axis
- mast reaction 176.7 kN along (0, 0, 1): pure axial force in the pinned mast; out-of-plane force on the ear plates 0.000 kN

## Design requirements for our node

- [ ] Lines of action of all cables/straps meet at one point (pin, mast axis) (critical)
- [ ] Each plate lies in the plane of the force(s) it receives (critical)
- [ ] Fabric bears on rounded edges, no sharp steel against the membrane, corner cut back (critical)
- [ ] Pin, toggle or cardan lets the fitting rotate with the load direction
- [ ] Tensioning/adjustment range visible (turnbuckle, threaded fork, slotted plate, screw)
- [ ] No water or dirt trap (open sections, drain holes, sloped plates)
- [ ] Dissimilar metals isolated (stainless/aluminium/galvanised)
- [ ] Membrane and cables can be removed/replaced without cutting steel

## Verify every idea before it goes on a drawing

- `tensile-connections/pin_connection.py`
- `tensile-connections/steel_joint_checks.py weld`
- `steel-supports/mast_check.py`

A picture is not a design. Forces, plate sizes, pins, welds and bolts come from our analysis and the
tools above, not from the photo. Link to the precedents; do not copy proprietary details or images into
the drawings.
