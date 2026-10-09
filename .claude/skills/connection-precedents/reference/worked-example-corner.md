# Precedent board: Membrane corner plate (edge cables + strap to anchor/mast)

Project: scale canopy, material PVC-III, Galfan edge cables 17 mm, 10 m four-point sail (examples/run_demo.sh)

Searched: `tensile membrane corner plate detail`; `shade sail corner plate stainless detail`; `tensile structure mast head detail`; `membrane structure connection detail drawing`; `corner plate with belt tensioner membrane`; `مظلات شد إنشائي تفاصيل`; `تفاصيل تثبيت مظلات شد إنشائي`; `مظلات شد إنشائي تفاصيل الأركان`; `tensile membrane corner detail [architen, birdair, tensinet]`

## Precedents (ranked: weighted quality x evidence x judged share)

| # | Precedent | Kind | Scale | Quality /10 | Rank | Red flags | Use |
|---|---|---|---|---|---|---|---|
| 6 | [Tensile Fabric Connection Detail in Futuristic Architecture / Boat anc](https://www.pinterest.com/pin/335799715957731749/) | photo | canopy | 8.8 | 8.2 | - | ideas + details |
| 18 | [Membrane Plate and Anchor Point on Tensile Fabric Shade Sail / Tensile](https://www.pinterest.com/pin/663295851342129190/) | photo | roof (gap 1) | 8.8 | 8.2 | - | ideas + details |
| 20 | [‏تركيب مظلات شد إنشائي / مظلات حديثة بتصاميم هندسية مميزة، تتحمل الظرو](https://www.pinterest.com/pin/191895634120374424/) | photo | sail (gap 1) | 6.2 | 6.05 | membrane_safe, rotation | form only |
| 16 | [ผ้าใบ / รีสอร์ท, ซุ้มไม้เลื้อย](https://www.pinterest.com/pin/663295851342129193/) | manufacturer | canopy | 7.5 | 5.91 | - | ideas + details |
| 13 | [Anchor Point for Sun Sail / Backyard shade solutions, How to install s](https://www.pinterest.com/pin/663295851342129201/) | photo | sail (gap 1) | 5.8 | 5.83 | membrane_safe, adjustable | form only |
| 7 | [Tensile Fabric Structure Details / Fabric Architecture / Concrete pipe](https://www.pinterest.com/pin/73324300182659113/) | shop_drawing | canopy | 6.2 | 5.68 | concurrent | form only |
| 8 | [Membrane Structure Architecture by Anne Peterson / Tension structure c](https://www.pinterest.com/pin/567875834239641912/) | sketch | canopy | 7.5 | 5.25 | - | ideas + details |
| 3 | [Detalles Constructivos de Arquitectura Textil / Tijerales, Membranas a](https://www.pinterest.com/pin/335799715957547409/) | render | canopy | 7.5 | 4.59 | - | ideas + details |
| 10 | [Arqzon Arquitectura added a new photo. - Arqzon Arquitectura / Estruct](https://www.pinterest.com/pin/162903711518234098/) | infographic | canopy | 0.0 | 0.0 | - | form only |

Off-topic or rejected: #2, #4, #5, #15, #17, #19

Not reviewed (image not viewed, not used): #1, #9, #11, #12, #14

## Ideas to take (with the precedents that show them)

- threaded-rod adjusters from the corner bracket to the frame (adjustment in several directions)  (#3)
- curved two-part clamp plate following the corner cut-back  (#3)
- edge cables end in threaded rod terminals with nuts bearing on lugs on the plate sides (adjustment at the corner)  (#6)
- single fork at the apex pinned to the mast lug (rotation free)  (#6)
- open swage socket + turnbuckle on the tie-back, pinned base plate  (#7)
- membrane corner plate pinned to a fork on the mast head, both edge cables into the plate  (#8)
- corner cut back so the fabric stops short of the pin  (#8)
- one ring as the single concurrency point for both edge cables and the strap  (#13)
- two-part plate: separate curved clamp strip over the membrane, main plate carries the loads  (#16)
- U-bolt / threaded adjuster on the bisector at the apex  (#16)
- short tubes welded at both sides as edge-cable terminations  (#16)
- curved bolted clamp plate along the cut-back corner, membrane plies visible as reinforcement  (#18)
- edge cables enter through lugs at the plate sides with threaded terminals and nuts  (#18)
- eye/fork at the apex on the bisector  (#18)
- single threaded rod on the bisector as the tensioner (simple, compact)  (#20)

## Do not copy (red flags seen)

- #7 concurrent [critical]: eccentric node: moment in the plate and the support (check with corner_plate.py)
- #13 membrane_safe [critical]: sharp edge or bolt against the fabric: tear risk
- #13 adjustable: no adjustment: tolerances and membrane creep cannot be taken up
- #20 membrane_safe [critical]: sharp edge or bolt against the fabric: tear risk
- #20 rotation: fixed fitting: bending in the cable end or fork under changing loads

## Agreed concept

Two-part steel corner plate in the plane of the two edge cables: curved clamp strip bolted over the cut-back, reinforced membrane corner; edge cables end in threaded terminals through side lugs; one pin hole at the apex on the bisector for the fork to the mast/anchor; strap on a separate hole on the bisector.
- curved two-part clamp plate on the cut-back corner  (from #18, #16, #3)
- edge cables in threaded terminals through side lugs, nuts give adjustment  (from #18, #6)
- single fork pinned at the apex on the bisector  (from #6, #8, #18)
- all lines through one point (ring idea), but with a pinned plate, not marine hardware  (from #13)

## Verification of the concept (tool output)

- corner_plate.py --m EC1:15:83:180:48 --m EC2:105:83:-48:180 --m strap:60:6:100:173
- anchor force 123.4 kN at -120 deg, on the edge-cable bisector (deviation 0.0 deg)
- moment about the anchor pin from the hole layout 0.038 kNm -> eccentricity 0.3 mm: lines of action concurrent

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

- `tensile-connections/corner_plate.py`
- `tensile-connections/pin_connection.py`
- `membrane-fabric/membrane_check.py --corner`

A picture is not a design. Forces, plate sizes, pins, welds and bolts come from our analysis and the
tools above, not from the photo. Link to the precedents; do not copy proprietary details or images into
the drawings.
