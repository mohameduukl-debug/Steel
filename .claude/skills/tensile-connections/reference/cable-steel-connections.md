# Cable-to-steel connections, corner plates, mast heads, tensioning

## 1. Fork (clevis) → pin → lug (gusset)
Arrangement: rope socket (open spelter, swaged fork, adjustable fork) → pin → single lug welded to the steel.
The lug plane contains the cable line of action. The fitting rotates about the pin in that plane; out-of-plane
rotation needs a toggle or spherical bearing. Pins must be secured (split pin, circlip, nut) [C]. A non-rotating pin
shorter than 3d may be designed as a bolt [C].

### 1.1 EN 1993-1-8 Table 3.9: lug geometry [C]
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
**Contact stress (replaceable pins)**: σ_h,Ed = 0.591·√(E·F_b,Ed,ser·(d₀ − d)/(d²·t)) ≤ f_h,Rd = 2.5·f_y/γM6,ser [V/C],
per plate (lug F_ser, each cheek F_ser/2), f_y = lower of plate and pin. 0.591 = 1/√(π(1 − ν²)) with ν = 0.3: Hertz line
contact of the pin in its hole with d·d₀ ≈ d² (Johnson, *Contact Mechanics*, §4.2).
Published checks of Table 3.10: Conde et al., JCSR 201 (2023) 107752 (counterexample and test prototypes) and the
Brandenburg Prüfamt *Tipp 22/05* design charts — see `validation.md`.
Smaller clearance lowers σ_h, which is better for fatigue and wear under wind flutter.

### 1.3 Worked example (EN, hand calculation to Tables 3.9/3.10): reproduced by `pin_connection.py`
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
D6 eyebars (`--eyebar-w`): strength = body yielding F_y·w·t with w ≤ 8t; R (head-to-body transition) ≥ head diameter
d₀ + 2b; pin d ≥ 7/8 w; d₀ ≤ d + 1 mm; 2/3 w ≤ b (≤ 3/4 w credited); t < 13 mm only with nuts clamping the plies;
F_y > 485 MPa: d₀ ≤ 5t [V]. D.7 (pin plate) and D.8 (eyebar) of the AISC Design Examples are reproduced in the tests. Pin flexure (F11): M_n = F_y·Z ≤ 1.6M_y, Z = d³/6.
Same example in AISC terms: b_eff = 56 mm, so a ≥ 74.5 mm and w ≥ 152 mm. **AISC edge distances are much larger than EC3 type A.**

### 1.5 Lugs, cheek plates, welds
* Cheek (doubler) plates add bearing thickness; load share ∝ thickness; size each cheek's perimeter fillet for its share; bore after
  welding in one operation.
* Welds (EN 1993-1-8 §4.5.3): directional √(σ⊥² + 3(τ⊥² + τ∥²)) ≤ f_u/(β_w γM2) and σ⊥ ≤ 0.9f_u/γM2; simplified
  F_w,Rd = a·f_u/(√3 β_w γM2). β_w 0.8 / 0.85 / 0.9 (S235 / S275 / S355) [C].
* Lugs slotted into tubes (mast heads): full-penetration butt welds; Z-quality (EN 10164) where the plate is pulled through its thickness.

## 2. Corner plates
Forces: two edge cables T₁, T₂ (angle θ), membrane strap/plate force F_m (≈ along the bisector), anchor/tie-back.
* Resultant of the edge cables (statics, validated in `validation.md`): R = √(T₁² + T₂² + 2T₁T₂cosθ); symmetric: **R = 2T·cos(θ/2)** along the bisector.
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

## 7. Gusset and corner plates with bolt groups (`steel_joint_checks.py gusset`)
* **Block tearing** (EN 1993-1-8:2005 3.10.2) [C]: concentric V_eff,1,Rd = f_u A_nt/γM2 + f_y A_nv/(√3 γM0) (3.9);
  eccentric V_eff,2,Rd = 0.5 f_u A_nt/γM2 + f_y A_nv/(√3 γM0) (3.10). A_nt, A_nv are net areas (holes deducted;
  half a hole at the end of a shear plane). U-block (gusset, two shear planes) or L-block (fin plate, one shear plane).
  Reproduces SBE Part 5 fin plate 483 kN and Wald's examples (`validation.md`). EN 1993-1-8:2024 changed the formula.
  AISC 360 J4.3 [C]: R_n = 0.60F_uA_nv + U_bsF_uA_nt ≤ 0.60F_yA_gv + U_bsF_uA_nt, φ = 0.75 (Teh & Deierlein 2017 example reproduced).
* **Whitmore section** [V, 30° per Dowswell EJ 2019]: b_e = w + 2·l·tan 30° at the last bolt row (w = gauge between
  outer bolt lines, l = length of the bolt group) or at the end of the welds; clip it to the actual plate width.
  Tension: b_e·t·f_y/γM0 and the net section at the last row.
* **Compression** of the gusset: equivalent column of width b_e and length K·l_avg (Thornton 1984: l_avg = average of
  the free lengths l1, l2, l3 along the force; K = 0.65 corner gussets [C, practice]); EN 1993-1-1 curve c
  (α = 0.49 [V]) or AISC J4.4 (KL/r ≤ 25 → F_cr = F_y [V], else E3). Dowswell (2019) proposes a variable trajectory
  angle and K = 0.40 / 0.50 with φ = 0.75 — research, not code.
* Bolt bearing in corner plates: the force on a hole is rarely parallel to an edge; verify the components parallel and
  normal to the edge (EN 1993-1-8 Table 3.4 note) — the tool does this per bolt.

## 8. Base plates and cast-in anchors
* **Compression** (EN 1993-1-8 6.2.5) [C]: f_jd = β_j k_j f_ck/γ_c with β_j = 2/3 [V] (grout ≥ 0.2 f_ck and
  thickness ≤ 0.2 × smallest plate width) and k_j = √(A_c1/A_c0) ≤ 3 [C]; additional bearing width
  c = t√(f_y/(3 f_jd γM0)). Wald's simple base plate (HE 200 B, t = 18, C12/15): c = 43.7 mm, N_Rd = 887 kN.
  f_cd inside F_Rdu carries α_cc (EN 1992-1-1 3.1.6, recommended 1.0, UK NA 0.85 → `--alpha-cc`).
  CHS mast: A_eff = π(D − t)(t + 2c), or π(D + 2c)²/4 when c > D/2 − t, cut exactly by the plate edges (SCI P358 Check 2;
  e.g. CHS 273×5 on 400×400×20 S275, C30, UK NA: f_jd = 17 MPa, c = 45.6 mm, N_Rd = 1376 kN = P358 Table G.33).
* **Uplift** [C]: equivalent T-stub per anchor row (Table 6.2): modes 1, 2, 3 when prying can develop (L_b ≤ L_b*),
  otherwise mode 1-2 = 2M_pl,1/m and mode 3. Anchor elongation length L_b = 8d + grout + plate + washer + h_nut/2 [V];
  long anchors usually give no prying. CHS with n ≥ 4 anchors on a circle (`--layout ring`): ring-flange rules of
  SCI P358 §6.8 (after CIDECT): r2 = D/2 + e1, r3 = (D − t)/2, k1 = ln(r2/r3), k3 = k1 + 2,
  f3 = (k3 + √(k3² − 4k1))/(2k1); plate N = t_p² f_y π f3/(2γM0); plate + anchors N = nF_t,Rd/(1 − 1/f3 +
  1/(f3 ln(r1/r2))), r1 = r2 + min(e2, 1.25e1); anchors nF_t,Rd. P358 Example 5 (273×6.3, 8 M24, t_p 20):
  f3 = 6.19, 1030 / 1061 / 1624 kN — reproduced by the tool.
* **Shear**: friction C_f,d·N_c,Ed with C_f,d = 0.20 for sand-cement mortar [V] (zero under uplift) plus the anchors
  F_2,vb,Rd = α_bc f_ub A_s/γM2, α_bc = 0.44 − 0.0003 f_yb (235 ≤ f_yb ≤ 640) [V]; or a shear key.
* **Anchors in the concrete (EN 1992-4)** — `steel_joint_checks.py anchor`; factors with sources in the register:
  - Tension: steel N_Rk,s = A_s f_uk, γMs = 1.2 f_uk/f_yk ≥ 1.4 [V]; pull-out N_Rk,p = k2 A_h f_ck (k2 = 7.5 / 10.5) [V];
    cone N⁰ = k1√f_ck h_ef^1.5 (k1 = 8.9 / 12.7 cast-in headed) [V] × A_c,N/A⁰_c,N (s_cr = 3h_ef, c_cr = 1.5h_ef) × ψs,N
    (0.7 + 0.3c/c_cr ≤ 1) × ψre,N × ψec,N; splitting with c_cr,sp, h_min from the ETA and ψh,sp ≤ 2 [V];
    blow-out for c < 0.5h_ef is NOT computed (warning only).
  - Shear: steel k7·k6·A_s·f_uk (k6 0.6 / 0.5 [V], k7 1.0 / 0.8 [C]); lever arm V = αM M_Rk,s/l_a with
    M⁰ = 1.2 W_el f_uk, l_a = 0.5d + e1, αM = 2 restrained [V]; pry-out k8·N_Rk,c (k8 = 2 for h_ef ≥ 60 mm) [V];
    concrete edge V⁰ = k9 d^α l_f^β √f_ck c1^1.5 (k9 = 1.7 / 2.4, α = 0.1(l_f/c1)^0.5, β = 0.1(d/c1)^0.2,
    l_f ≤ 12d) [V] × A_c,V/(4.5c1²) × ψs,V × ψh,V × ψα,V × ψec,V × ψre,V (1.0, or 1.4 cracked with edge
    reinforcement) [V]; narrow thin members c1′ = max(c2,max/1.5, h/1.5, s2,max/3) [V].
  - With normal hole clearance the anchors of the row nearest the edge take all the shear for edge failure.
  - Interaction (Table 7.3): steel β_N² + β_V² ≤ 1; concrete β_N^1.5 + β_V^1.5 ≤ 1, largest β per type [V].
  - γMc = γMp = γMsp = 1.5 [V] (γc 1.5 × γinst 1.0 for cast-in).

## 9. Fatigue of lugs, welds and terminations (`fatigue_check.py`)
* EN 1993-1-9 nominal-stress curves [V]: Δσ_C at 2×10⁶, m = 3 to 5×10⁶ (Δσ_D = 0.737Δσ_C), m = 5 to 10⁸
  (Δσ_L = 0.549Δσ_D), shear m = 5 with Δτ_L = 0.457Δτ_C; γMf from Table 3.1 (safe life 1.15 / 1.35, damage tolerant
  1.00 / 1.15 for low / high consequence) [V]. Palmgren–Miner D = Σ n_i/N_i ≤ 1 (Annex A).
* Combined normal and shear: Eq. (8.3) with the Annex A.6 equivalent ranges = D_σ + D_τ ≤ 1 (tool).
* Membrane flutter loads fittings with many small cycles: ranges below Δσ_L do not count, ranges between Δσ_L and
  Δσ_D use the m = 5 branch (EN 1993-1-9 7.1(3)), so the count of small cycles still matters. Detail categories: read EN 1993-1-9 Tables 8.1–8.10 for the actual detail
  (do not assume one); rope terminations from supplier tests.
