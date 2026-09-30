# Cable-to-steel connections, corner plates, mast heads, tensioning

## 1. Fork (clevis) → pin → lug (gusset)
Arrangement: rope socket (open spelter, swaged fork, adjustable fork) → pin → single lug welded to the steel.
The lug plane contains the cable line of action. The fitting rotates about the pin in that plane; out-of-plane
rotation needs a toggle or spherical bearing. Pins must be secured (split pin, circlip, nut) [C]. A non-rotating pin
shorter than 3d may be designed as a bolt [C].

### 1.1 EN 1993-1-8 Table 3.9: lug geometry
| Type | Given | Requirement |
|---|---|---|
| A | thickness t | a ≥ F_Ed·γM0/(2t·f_y) + 2d₀/3 ;  c ≥ F_Ed·γM0/(2t·f_y) + d₀/3 |
| B | geometry | t ≥ 0.7·√(F_Ed·γM0/f_y) (some texts use F_Ed,ser·γM6,ser) ;  d₀ ≤ 2.5t |
a = end distance (hole edge to plate end, along the force); c = side distance (hole edge to plate side).
Type B figure proportions (plate width 2.5d₀ etc.): read them from the figure [U].

### 1.2 EN 1993-1-8 Table 3.10: pin checks [V]
| Mode | ULS | Replaceable pin: additional SLS |
|---|---|---|
| Pin shear | F_v,Rd = 0.6·A·f_up/γM2 (per plane) | — |
| Bearing plate and pin | F_b,Rd = 1.5·t·d·f_y/γM0 | F_b,Rd,ser = 0.6·t·d·f_y/γM6,ser |
| Pin bending | M_Rd = 1.5·W_el·f_yp/γM0 | M_Rd,ser = 0.8·W_el·f_yp/γM6,ser |
| Shear + bending | (M_Ed/M_Rd)² + (F_v,Ed/F_v,Rd)² ≤ 1 | — |
f_y in bearing = lower of plate and pin. W_el = πd³/32. γM0 = 1.0, γM2 = 1.25, γM6,ser = 1.0 (recommended) [V].
**Pin moment** (Fig. 3.11): M_Ed = F_Ed·(b + 4c + 2a)/8, with b = lug thickness, a = fork cheek thickness, c = gap [C].
**Contact stress (replaceable pins)**: σ_h,Ed = 0.591·√(E·F_Ed,ser·(d₀ − d)/(d²·t)) ≤ f_h,Rd = 2.5·f_y/γM6,ser [V/C].
Smaller clearance lowers σ_h, which is better for fatigue and wear under wind flutter.

### 1.3 Worked example (EN): reproduced exactly by `pin_connection.py`
F_Ed = 250 kN, F_Ed,ser = 170 kN, lug t = 20 mm S355, pin d = 40 mm (f_yp 640, f_up 800), d₀ = 41 mm, cheeks 15 mm, gap 2 mm.
* Pin shear per plane 0.6·1257·800/1.25 = **483 kN** ≥ 125 kN ✔
* Bearing on lug 1.5·20·40·355 = **426 kN** ≥ 250 ✔
* M_Ed = 250·(20 + 8 + 30)/8 = **1.81 kNm**; M_Rd = 1.5·6283·640 = **6.03 kNm**; interaction 0.16 ✔
* Type A: a ≥ 17.6 + 27.3 = **44.9 mm**; c ≥ 17.6 + 13.7 = **31.3 mm**
* Replaceable: F_b,Rd,ser = 0.6·20·40·355 = **170.4 kN** ≈ 170 (util 1.00); σ_h = **624 MPa** ≤ 888 ✔
```bash
python3 pin_connection.py --F 250 --Fser 170 --d 40 --d0 41 --t 20 --a-lug 50 --c-lug 35 \
   --pin-fy 640 --pin-fu 800 --fork-t 15 --gap 2 --replaceable
```

### 1.4 AISC 360 D5 / J7 [V]
P_n = min of:
1. tensile rupture F_u·2t·b_eff (φ 0.75 / Ω 2.00), b_eff = 2t + 16 mm ≤ actual edge distance ⟂ force;
2. shear rupture 0.6F_u·A_sf, A_sf = 2t(a + d/2) (φ 0.75);
3. bearing (J7) 1.8F_y·d·t (φ 0.75);
4. gross yielding (D2) F_y·A_g (φ 0.90).

D5.2 geometry: a ≥ 1.33 b_eff; w ≥ 2 b_eff + d; c ≥ a; hole ≤ d + 1 mm (1/32 in) if the pin moves under load.
D6 eyebars: t ≥ 12 mm, width ≤ 8t, pin d ≥ 7/8 × body width [C]. Pin flexure (F11): M_n = F_y·Z ≤ 1.6M_y, Z = d³/6.
Same example in AISC terms: b_eff = 56 mm, so a ≥ 74.5 mm and w ≥ 152 mm. **AISC edge distances are much larger than EC3 type A.**

### 1.5 Lugs, cheek plates, welds
* Cheek (doubler) plates add bearing thickness; load share ∝ thickness; size each cheek's perimeter fillet for its share; bore after
  welding in one operation.
* Welds (EN 1993-1-8 §4.5.3): directional √(σ⊥² + 3(τ⊥² + τ∥²)) ≤ f_u/(β_w γM2) and σ⊥ ≤ 0.9f_u/γM2; simplified
  F_w,Rd = a·f_u/(√3 β_w γM2). β_w 0.8 / 0.85 / 0.9 (S235 / S275 / S355) [C].
* Lugs slotted into tubes (mast heads): full-penetration butt welds; Z-quality (EN 10164) where the plate is pulled through its thickness.

## 2. Corner plates
Forces: two edge cables T₁, T₂ (angle θ), membrane strap/plate force F_m (≈ along the bisector), anchor/tie-back.
* Resultant of the edge cables: R = √(T₁² + T₂² + 2T₁T₂cosθ); symmetric: **R = 2T·cos(θ/2)** along the bisector.
  T = 100 kN: θ = 90° gives R = 141 kN; θ = 60° gives R = 173 kN, so acute corners attract large forces.
* The anchor axis lies on the line of action of R + F_m. **All lines concurrent** at one point, otherwise the plate rotates and the
  fabric wrinkles. Plate plane = plane of the two edge cables (≈ membrane tangent plane); use a toggle or cardan if the anchor is out of plane.
* Holes: one pin hole per edge-cable fork; a hole group or slot for the membrane plate/strap; the main anchor hole on the bisector.
  A row of alternative holes (25–50 mm pitch [U]) gives coarse adjustment; turnbuckles give fine adjustment.
* Thickness about 12–20 mm (small PVC) to 25–50 mm (large PTFE) or a double plate [U]; check every hole with Table 3.9/3.10 or D5.
* Workflow: `corner_plate.py` with the concurrent forces for each governing combination, then adjust the hole positions until the eccentricity is about 0.

## 3. Mast heads
* Radiating ear plates, **each in the plane of its cable**. All cable lines meet at one point on the mast axis (no eccentric
  moment); otherwise design for M = R·e. Cap plate and ring stiffener. Anchor radial and ridge cables to the ring or head [V].

## 4. Mast bases
* Pinned (why: axial mast, no foundation moment, follows the membrane, easy erection with hinge-up and jack) [practice].
  Details: pin + clevis (1 or 2 axes), cardan, spherical bearing. Fixed base: big foundation moments (Birdair: "guyed or moment
  connected at the base") [V].

## 5. Tensioning devices and prestress introduction [V, Architen]
* Devices: turnbuckles/rigging screws (jaw-jaw, jaw-stud), threaded fork adjusters, adjustable spelter sockets, corner tension rods,
  U-bolts, belt tensioners, hollow-ram jacks with temporary bars.
* Ranges: Pfeifer adjustable sockets and rods about 1.4 × thread Ø [V]; Ronstan Type 10 single-end fine thread, dissimilar metals
  against galling [V]; typical specs ±50 mm (small) to ±100–150 mm (large) [U]; cover creep plus fabrication and erection tolerance
  (often 1–3 % of the adjacent edge length [U]).
* Methods: (1) **mast jacking** in a sand pot or telescopic section (cones, high points); (2) **corners** by rigging screws, U-bolts or
  shortening tie-backs; (3) **edge cables** shortened at swaged studs on the membrane plate; (4) **rigid edges** by drawing out adjustable tracks.
* Tension gradually and evenly in sequence; verify prestress and geometry [V]. Keep ≥ 1d thread engagement at full extension; lock nuts or wire.

## 6. Ground anchors
Helical guy anchors (square shaft, to ~890 kN ult; HA150 ≈ 133 kN, HA175 ≈ 222 kN allowable, torque-correlated [V]); grouted rock
anchors; deadman blocks; tension piles. Anchor head on the cable line with an articulated fork.
