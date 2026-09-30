---
name: tensile-connections
description: Connection design and detailing between membrane fabric, cables and steel in tensile structures — fabric-to-cable (pockets, belts, clamp plates), fabric-to-steel (keder tracks, clamp bars, bale rings), cable-to-steel (forks/clevis, pins, lugs/gussets per EN 1993-1-8 §3.13 and AISC 360 D5/J7), corner plates (force concurrency), mast heads, base hinges, tensioning devices/turnbuckles, ground anchors, tolerances, execution class and bimetallic isolation.
---

# Connections: fabric ↔ cable ↔ steel

## Tools
### `scripts/pin_connection.py`: fork/eye + pin + lug (gusset)
```bash
python3 pin_connection.py --F 250 --Fser 170 --d 40 --d0 41 --t 20 --a-lug 50 --c-lug 35 \
        --pin-fy 640 --pin-fu 800 --fork-t 15 --gap 2 --replaceable [--aisc]
```
EN 1993-1-8 Table 3.9 (type A geometry a, c; type B info), Table 3.10 (pin shear per plane, bearing of lug and
fork cheeks, pin bending M = F(b+4c+2a)/8, interaction), replaceable-pin SLS checks and contact stress
σ_h,Ed = 0.591√(E·F_ser(d₀−d)/(d²t)) ≤ 2.5f_y/γM6,ser, and lug net section. `--aisc` adds D5.1(a)(b), J7, D2 and D5.2 geometry.
It reproduces the EN worked example in `reference/cable-steel-connections.md` exactly.

### `scripts/corner_plate.py`: force resolution and concurrency
```bash
python3 corner_plate.py --m EC1:15:48:180:48 --m EC2:105:52:48:180 --m strap:60:6:100:173     # 2D + hole layout
python3 corner_plate.py --v EC1:9.8:1.2:-2.1:48 --v EC2:1.0:10.1:-1.9:52 --v strap:5:5:-1.5:6  # 3D
```
It gives the required anchor force and direction, the edge-cable bisector, the moment/eccentricity from the hole layout
(it must be ≈ 0), and in 3D the plate plane plus any out-of-plane component.

### `scripts/steel_joint_checks.py`: welds, bolts, clamp bars, base plates (EN 1993-1-8)
```bash
python3 steel_joint_checks.py weld --F 250 --angle 60 --L 200 --a 8 --e 120 --grade S355     # lug-to-member fillets
python3 steel_joint_checks.py bolts --n-rows 2 --n-cols 2 --p1 80 --p2 80 --Vy 120 --M 4 --d 20 --grade 8.8 \
        --t 15 --e1 45 --e2 40                                                                  # eccentric bolt group
python3 steel_joint_checks.py clampbar --n 12 --spacing 150 --d 12 --grade A4-70 --t 10       # membrane clamp line
python3 steel_joint_checks.py baseplate --col CHS --D 219.1 --tc 8 --B 400 --H 400 --tp 25 \
        --Nc 450 --Nt 120 --V 40 --anchors 4 --anchor-d 24 --edge 60 --layout corners          # mast base
```
- weld: double fillet with N⊥, V∥ and in-plane moment (lever arm e to the hole). Directional method 4.5.3.2 and simplified 4.5.3.3; β_w from the register.
- bolts: elastic bolt-group method; shear (α_v by grade and thread), bearing (k1, α_b from e1, e2, p1, p2), tension with prying, punching, combined; carbon 4.6–10.9 and stainless A2/A4.
- clampbar: bolt force = n × peak factor × spacing; warns above ~200 mm spacing. The aluminium plate goes to EN 1999 separately.
- baseplate: compression with the equivalent T-stub (c = t√(f_y/3f_jd)), uplift with T-stub modes 1, 2, 1-2 (no prying) and 3 per anchor, shear by friction plus anchors (α_bc). Anchor embedment and concrete breakout (EN 1992-4) are not included.

## The connection families (details in `reference/`)

| Interface | Standard solutions | Governing checks |
|---|---|---|
| Fabric → cable | cable in welded pocket (cable must slide) · external cable + clamp-plate pairs on keder edge (PTFE) · webbing belts · belts parallel to edge for shear | pocket clearance, seam peel, clamp spacing ≤ ~200 mm, slip at corner |
| Fabric → steel | keder in aluminium track (slot ≈ 60–70 % of keder Ø) · flat clamp bars with stainless bolts ≤ ~200 mm · adjustable track on studs · bale ring at cone top | pull-out, bolt/plate bending, chamfered segment joints, bimetallic isolation |
| Fabric corner | TensiNet 5 corner types (plate apart or clamped, keder, continuous cable, belts) · membrane cut-back · doubler plies | concurrency, rotation stiffness at acute corners, wrinkle-free geometry |
| Cable → steel | fork/eye + pin + lug in cable plane · threaded socket through plate · saddle/clamp | Tab. 3.9/3.10 or AISC D5/J7; weld of lug; plate in plane; rotation freedom |
| Mast head | radiating ear plates, each in its cable plane, lines concurrent on the mast axis; cap and ring plates | eccentricity moment, plate buckling, through-thickness (Z-quality) |
| Mast base | pin/clevis, cardan, spherical bearing, sand-pot jacking seat | rotation range, uplift, pin design |
| Tensioning | turnbuckles, threaded fork adjusters, adjustable sockets (≈ 1.4 × thread Ø take-up, Pfeifer [V]), corner screws, mast jacking | range ≥ tolerances + creep; thread engagement ≥ 1d; locking |
| Ground | helical, rock, deadman, tension piles | uplift, proof test, anchor on cable line |

## Design procedure for any node
1. Collect **concurrent** forces for every combination at the node (from the non-linear analysis).
2. Set the geometry so **all lines of action meet at one point** (corner-plate pin, mast axis). Check it with `corner_plate.py`.
3. Put each plate **in the plane of the force(s)** it receives (use a toggle or cardan where the plane changes).
4. Size the pins and lugs (`pin_connection.py`). Match the cable fitting (jaw width, pin Ø from the supplier; forks are proprietary and
   matched to cable MBL).
5. Check the welds (EN 1993-1-8 §4.5.3; β_w 0.8 / 0.85 / 0.9 for S235 / S275 / S355), cheek plates (load ∝ thickness),
   through-thickness properties.
6. Check fabric-side stresses at clamps and corners (stress concentration) with `membrane-fabric`.
7. Adjustment: range covers fabrication + erection tolerance plus membrane creep. Record the set position.
8. Tolerances: holes for fitted pins H11 (EN 1090-2 [V]); pin clearance small (AISC ≤ 1 mm for moving pins [V];
   EC3 penalises clearance through σ_h). Bore after welding and galvanising, or allow for the zinc.

## References
- `reference/fabric-cable-connections.md`: pockets, clamp plates, belts, corner types, cut-back, reinforcement.
- `reference/fabric-steel-connections.md`: keder, clamp bars, adjustable edges, arches, bale rings, low points, isolation.
- `reference/cable-steel-connections.md`: pins/lugs (full EN and AISC formulas plus worked examples), mast heads, bases, tensioning, anchors, corner plates.
- `reference/fabrication-tolerances.md`: EN 1090-2 execution, NDT, hole tolerances, galvanising, supplier hardware list.
