---
name: tensile-connections
description: Connection design and detailing between membrane fabric, cables and steel in tensile structures — fabric-to-cable (pockets, belts, clamp plates), fabric-to-steel (keder tracks, clamp bars, bale rings), cable-to-steel (forks/clevis, pins, lugs/gussets per EN 1993-1-8 §3.13 and AISC 360 D5/J7), corner plates (force concurrency), gusset block tearing and Whitmore buckling, welds, bolt groups, base plates, EN 1992-4 cast-in anchors (tension, shear, interaction), fatigue (EN 1993-1-9), mast heads, base hinges, tensioning devices/turnbuckles, ground anchors, tolerances, execution class and bimetallic isolation.
---

# Connections: fabric ↔ cable ↔ steel

Tags: [V] confirmed from a named source (URL + quote in `tensile-structures/reference/code_factors.json` or the
reference files), [C] standard clause content / recommended value (National Annex may differ), [U] unverified typical
value (always with a range). All code factors come from the register through `factors.py`; `--factors project.json`
(before the sub-command) overrides them. Every tool prints its factors and its assumptions — pass them on.
Validation of every computational path: `reference/validation.md` (tests in `tests/test_tensile_connections.py`).

## Tools
### `scripts/pin_connection.py`: fork/eye + pin + lug (gusset)
```bash
python3 pin_connection.py --F 250 --Fser 170 --d 40 --d0 41 --t 20 --a-lug 50 --c-lug 35 \
        --pin-fy 640 --pin-fu 800 --fork-t 15 --gap 2 --replaceable [--aisc --method LRFD|ASD] [--factors p.json]
```
Options: `--F` ULS force [kN]; `--Fser` SLS force (default F/1.4); `--d` pin, `--d0` hole, `--t` lug [mm]; `--a-lug`
end distance and `--c-lug` side distance from the hole edge [mm]; `--fy/--fu` plate (355/490), `--pin-fy/--pin-fu`
pin (460/610); `--fork-t` cheek thickness (default 0.6t); `--gap` (2 mm); `--replaceable` adds the SLS checks;
`--aisc` adds AISC 360 D5.1(a)(b), J7, D2 and D5.2 geometry (φ from the register).
EN 1993-1-8 Table 3.9 (type A geometry a, c; type B for information), Table 3.10 (pin shear per plane, bearing of lug
and cheeks, pin bending M = F(b + 4c + 2a)/8, interaction), replaceable-pin SLS checks and contact stress
σ_h,Ed = 0.591√(E·F_ser(d₀−d)/(d²t)) ≤ 2.5f_y/γM6,ser [C], lug net section 0.9·2c·t·f_u/γM2 [C].

### `scripts/corner_plate.py`: force resolution and concurrency
```bash
python3 corner_plate.py --m EC1:15:48:180:48 --m EC2:105:52:48:180 --m strap:60:6:100:173     # 2D name:angle:F[:x:y]
python3 corner_plate.py --v EC1:9.8:1.2:-2.1:48 --v EC2:1.0:10.1:-1.9:52 --v strap:5:5:-1.5:6  # 3D name:dx:dy:dz:F
```
The first two members are the edge cables. It gives the required anchor force and direction, the edge-cable bisector,
the moment about the anchor pin from the hole layout and the eccentricity e = M/R (it must be ≈ 0; < 5 mm reported
as concurrent [U] practice), and in 3D the plate plane, every out-of-plane component and the anchor tilt
(> 2° flagged [U] practice). Functions `resolve2d`/`resolve3d` return the same values without printing.

### `scripts/steel_joint_checks.py`: welds, bolts, gussets, clamp bars, base plates, anchors
```bash
python3 steel_joint_checks.py weld --F 250 --angle 60 --L 200 --a 8 --e 120 [--x 0 --grade S355 --fu 470 --sides 2]
python3 steel_joint_checks.py bolts --n-rows 2 --n-cols 2 --p1 80 --p2 80 --Vy 120 --M 4 --d 20 --grade 8.8 \
        --t 15 --e1 45 --e2 40 [--Vx --N --prying 1.3 --coords "x:y;..." --d0 22 --fu-plate 490 --shank]
python3 steel_joint_checks.py gusset --F 300 --n1 3 --n2 2 --p1 70 --p2 60 --e1 40 --e2 40 --d 20 --t 12 \
        [--fy 355 --fu 490 --width 250 --l-avg 150 --K 0.65 --block U|L --aisc --grade 8.8 --d0 --shank]
python3 steel_joint_checks.py clampbar --n 12 --spacing 150 --d 12 --grade A4-70 --t 10 \
        [--mode shear|tension --prying 1.3 --peak 1.5 --plate steel|alu6082 --fu-plate 490]
python3 steel_joint_checks.py baseplate --col CHS --D 219.1 --tc 8 --B 400 --H 400 --tp 25 \
        --Nc 450 --Nt 120 --V 40 --anchors 4 --anchor-d 24 --edge 60 --layout corners \
        [--col I --hc --bf --tfc --twc --fy 355 --fck 30 --kj 1.5 --anchor-grade 8.8 --weld 6 --Lb --grout 30 --washer 5]
python3 steel_joint_checks.py anchor --n1 2 --n2 2 --s1 200 --s2 200 --c1 400 --c2 400 --hef 250 --d 24 \
        --N 150 --V 40 [--c1b --c2b --dh --grade --fck --uncracked --psi-re --k1 --ccr-sp --hmin --cv --no-edge \
        --cv2a --cv2b --h --alpha-v --eV --edge-reinf --standoff --alphaM --brittle --A-shear]
```
- **weld**: double fillet T-joint, N⊥, V∥ and in-plane moment (lever arm `--e` to the hole, offset `--x`).
  Directional method 4.5.3.2 (√(σ⊥² + 3(τ⊥² + τ∥²)) ≤ f_u/(β_w γM2), σ⊥ ≤ 0.9f_u/γM2) and simplified 4.5.3.3
  (F_w,Rd = a·f_u/(√3 β_w γM2)); β_w 0.8 / 0.85 / 0.9 / 1.0 (S235 / S275 / S355 / S420–S460) [C] from the register.
- **bolts**: elastic bolt group (Vx, Vy, torsion M), shear (α_v 0.6 for 4.6/5.6/8.8, 0.5 for 10.9 [C]; stainless
  0.5 [V, EN 1999-1-1 T8.5]), bearing per bolt with k1 = min(2.8e2/d0 − 1.7, 1.4p2/d0 − 1.7, 2.5) and
  αb = min(e1/3d0, p1/3d0 − 1/4, f_ub/f_u, 1) [C], verified by components parallel/normal to the edge
  √((f_x/F_b,x)² + (f_y/F_b,y)²) ≤ 1; tension k2 = 0.9 [C] with a prying factor, punching with d_m from ISO 4032 nut
  dimensions, combined F_v/F_v,Rd + F_t/(1.4F_t,Rd) ≤ 1 [C]. y = direction 1 (e1, p1), x = direction 2 (e2, p2);
  0 = not applicable.
- **gusset**: bolted gusset or corner plate with a concentric force (+ tension, − compression): bolt shear and
  bearing, block tearing EN 1993-1-8:2005 3.10.2 (U = two shear planes, Eq. 3.9; L = one shear plane, eccentric,
  Eq. 3.10), Whitmore width b_e = (n2 − 1)p2 + 2(n1 − 1)p1·tan 30° [V] (clipped by `--width`), Whitmore yielding
  and net section, compression as an equivalent column K·l_avg with K = 0.65 (Thornton) [C] and EN 1993-1-1
  curve c α = 0.49 [V]; `--aisc` adds AISC J4.3 block shear (0.6F_uA_nv + U_bsF_uA_nt ≤ 0.6F_yA_gv + U_bsF_uA_nt, hole + 1.6 mm,
  U_bs = 0.5 for the L block with two lines) and J4.1 yielding / J4.4 (KL/r ≤ 25 → F_y [V], else E3).
- **clampbar**: bolt force = n × peak factor × spacing; warns above ~200 mm spacing [V, TensiNet]; e1 = 3d,
  e2 = 1.5d assumed. `--plate alu6082`: bearing on 6082-T6 per EN 1999-1-1 Table 8.5 [V] (f_u 290 / 310 MPa for
  t ≤ 5 / > 5 mm, γM2 = 1.25 [V]).
- **baseplate**: compression with the equivalent T-stub (c = t√(f_y/(3f_jd γM0)), f_jd = β_j k_j f_ck/γ_c,
  β_j = 2/3 [V]); I column A_eff = (b+2c)(h+2c) − (b − t_w)(h − 2t_f − 2c) form clipped to the plate; CHS annulus.
  Uplift per anchor with a T-stub (l_eff = min(2πm, 4m + 1.25e)), prying decided by L_b (= 8d + grout + t_p +
  washer + h_nut/2 [V]) against L_b* = 8.8m³A_s/(l_eff t³) [C]: modes 1, 2, 3 with prying, else modes 1-2 and 3.
  Shear: friction C_f,d = 0.2 × N_c [V] (none with uplift) plus anchors α_bc = 0.44 − 0.0003f_yb [V].
- **anchor** (EN 1992-4, cast-in headed, rectangular group; edge distances per side `--c1/--c1b/--c2/--c2b`):
  tension — steel (γMs = 1.2f_uk/f_yk ≥ 1.4 [V]), pull-out N_Rk,p = k2·A_h·f_ck (k2 = 7.5 cracked / 10.5 uncracked
  [V]), concrete cone N⁰ = k1√f_ck·h_ef^1.5 (k1 = 8.9 / 12.7 [V], `--k1` from an ETA) × A_c/A⁰ × ψs × ψre × ψec with
  s_cr = 3h_ef, c_cr = 1.5h_ef [V], splitting (Eq. 7.23/7.24 with `--ccr-sp`, `--hmin` from the ETA; ψh,sp ≤ 2 [V]);
  shear — steel without lever arm k7·k6·A_s·f_uk (k6 = 0.6 / 0.5 for f_uk ≤ / > 500 [V], k7 = 1.0 / 0.8 [C],
  γMs,V = f_uk/f_yk ≥ 1.25 or 1.5 [V]), with lever arm (`--standoff` e1: l_a = 0.5d + e1, M⁰ = 1.2W_el f_uk,
  αM = 2 restrained [V] / 1 free), pry-out k8·N_Rk,c (k8 = 1 / 2 for h_ef < / ≥ 60 mm [V]), concrete edge
  V⁰ = k9·d^α·l_f^β·√f_ck·c1^1.5 (k9 = 1.7 / 2.4 [V]) × A_c,V/(4.5c1²) × ψs,V × ψh,V × ψα,V × ψec,V × ψre,V
  (1.0 / 1.4 with `--edge-reinf` [V]) with c1′ for narrow thin members; interaction steel β_N² + β_V² ≤ 1 and
  concrete β_N^1.5 + β_V^1.5 ≤ 1 [V]. γMc = γMp = γMsp = 1.5 [V].

### `scripts/fatigue_check.py`: EN 1993-1-9 details and tension components
```bash
python3 fatigue_check.py --category 71 --spectrum 40:1e6 --spectrum 25:5e6                # welded lug detail
python3 fatigue_check.py --category 90 --spectrum 60:1.5e6 --shear-category 70 --shear-spectrum 60:1.5e6
python3 fatigue_check.py --cable spiral_socket --spectrum 60:2e6 --sensitivity             # tension component
```
Options: `--category` Δσ_C or `--cable spiral_socket|parallel_wire|threaded_bar`; `--spectrum Δσ:n` (repeat);
`--shear-category` Δτ_C and `--shear-spectrum Δτ:n`; `--method safe-life|damage-tolerant`, `--consequence high|low`
(γMf 1.35 / 1.15 / 1.15 / 1.00, EN 1993-1-9 Table 3.1 [V]); `--gFf` (1.0); `--sensitivity` and `--single-slope` (cables).
Normal stress curve m = 3 to 5×10⁶ (Δσ_D = 0.737Δσ_C), m = 5 to 10⁸ (Δσ_L = 0.549Δσ_D = 0.405Δσ_C, cut-off) [V];
shear m = 5, Δτ_L = 0.457Δτ_C at 10⁸ [V]; Palmgren–Miner D = Σn/N ≤ 1 (Annex A); combined Eq. (8.3) with the
Annex A.6 equivalent ranges = D_σ + D_τ ≤ 1. Cable categories and slopes come from the `fatigue_cables` register
section (owned by `cable-tension-members`): EN 1993-1-11 Fig. 9.1 curve, m1 = 4 down to Δσ_C at 2×10⁶, then m2 = 6,
no cut-off [V per register]; `--single-slope` keeps m1 beyond the knee (conservative, former behaviour); the German NA
route uses 112 N/mm² for FLC hangers (low end of the Δσ_C range); `--sensitivity` re-runs the damage over the ranges. Use supplier fatigue data.

## The connection families (details in `reference/`)

| Interface | Standard solutions | Governing checks |
|---|---|---|
| Fabric → cable | cable in welded pocket (cable must slide) · external cable + clamp-plate pairs on keder edge (PTFE) · webbing belts · belts parallel to edge for shear | pocket clearance, seam peel, clamp spacing ≤ ~200 mm [V], slip at corner |
| Fabric → steel | keder in aluminium track (slot ≈ 60–70 % of keder Ø [V]) · flat clamp bars with stainless bolts ≤ ~200 mm [V] · adjustable track on studs · bale ring at cone top | pull-out, bolt/plate bending, chamfered segment joints, bimetallic isolation |
| Fabric corner | TensiNet 5 corner types (plate apart or clamped, keder, continuous cable, belts) · membrane cut-back · doubler plies | concurrency, rotation stiffness at acute corners, wrinkle-free geometry |
| Cable → steel | fork/eye + pin + lug in cable plane · threaded socket through plate · saddle/clamp | Tab. 3.9/3.10 or AISC D5/J7; weld of lug; plate in plane; rotation freedom |
| Gusset / corner plate | bolted or welded plate collecting several members | block tearing, Whitmore yield/buckling, bolt bearing, concurrency |
| Mast head | radiating ear plates, each in its cable plane, lines concurrent on the mast axis; cap and ring plates | eccentricity moment, plate buckling, through-thickness (Z-quality) |
| Mast base | pin/clevis, cardan, spherical bearing, sand-pot jacking seat; base plate on cast-in anchors | rotation range, uplift (T-stub), EN 1992-4 anchors, pin design |
| Tensioning | turnbuckles, threaded fork adjusters, adjustable sockets (≈ 1.4 × thread Ø take-up, Pfeifer [V]), corner screws, mast jacking | range ≥ tolerances + creep; thread engagement ≥ 1d [U, practice 1–1.5d]; locking |
| Ground | helical, rock, deadman, tension piles | uplift, proof test, anchor on cable line |

## Design procedure for any node
0. **Precedents first**: run the `connection-precedents` skill (search Pinterest, view and score the images, precedent
   board, concept agreed with the user, `precedent_search.py check` = PASS). Then size that concept with the steps below.
   A project hook blocks the tools of this skill until the gate has passed.
1. Collect **concurrent** forces for every combination at the node (from the non-linear analysis).
2. Set the geometry so **all lines of action meet at one point** (corner-plate pin, mast axis). Check it with `corner_plate.py`.
3. Put each plate **in the plane of the force(s)** it receives (use a toggle or cardan where the plane changes).
4. Size the pins and lugs (`pin_connection.py`). Match the cable fitting (jaw width, pin Ø from the supplier; forks are proprietary and
   matched to cable MBL). Bolted gussets and corner plates: `steel_joint_checks.py gusset`.
5. Check the welds (`weld`; EN 1993-1-8 §4.5.3), cheek plates (load ∝ thickness), through-thickness properties.
6. Bases: `baseplate` for the plate, `anchor` for the concrete (EN 1992-4); fatigue of lugs and welds under flutter with
   `fatigue_check.py`.
7. Check fabric-side stresses at clamps and corners (stress concentration) with `membrane-fabric`.
8. Adjustment: range covers fabrication + erection tolerance plus membrane creep. Record the set position.
9. Tolerances: holes for fitted pins H11 (EN 1090-2 [V]); pin clearance small (AISC ≤ 1 mm for moving pins [V];
   EC3 penalises clearance through σ_h). Bore after welding and galvanising, or allow for the zinc.

## Limitations
- Hand-calculation models only: no finite-element analysis of plates, lugs or welds. Plate stresses around holes,
  free-edge buckling of gussets, local buckling of slender ear plates and stress concentrations are not computed;
  use FE (e.g. IDEA StatiCa, ANSYS) for irregular corner plates and mast heads.
- Gusset compression is the Thornton equivalent column on the Whitmore width (K = 0.65 [C] practice); Dowswell (2019)
  shows the 30° width and K are approximations.
- Block tearing and bolt bearing follow EN 1993-1-8:2005; the 2024 edition (EN 1993-1-8:2024) changes both — check the
  edition in force.
- Bolt groups: elastic method with a rigid plate; no slip-resistant (category B/C) or preloaded bolt checks; no long-joint
  (β_Lf) or packing reductions; oversized/slotted holes not handled.
- Welds: fillets only (no partial-penetration or butt welds); the lug T-joint model assumes 45° fillets.
- Base plates: rigid plate, uniform anchor tension; no bending moment (M–N interaction) of the column base, no plate
  stiffness/rotation; L_b* uses n_b = 1 per T-stub.
- Anchors: cast-in headed anchors in plain concrete; no blow-out, no supplementary/anchor reinforcement, no h′_ef rule
  for narrow members with ≥ 3 edges, no fatigue/seismic/fire, no torsion or eccentric loads beyond ψec; post-installed
  anchors only through `--k1` and ETA values. Splitting needs c_cr,sp and h_min from the product's ETA.
- Fatigue: nominal-stress S-N curves; detail category, stress concentration factors and cycle counting are the user's
  input; cable S-N curves are the EN 1993-1-11 type curve — use supplier test data where available.
- Proprietary fittings (forks, sockets, turnbuckles, rope clamps, keder profiles) are not designed here: take their
  resistances from the supplier's catalogue or ETA, matched to the cable MBL.
- Code factors are recommended values; confirm them against the standard edition and the National Annex in force.

## References
- `reference/fabric-cable-connections.md`: pockets, clamp plates, belts, corner types, cut-back, reinforcement.
- `reference/fabric-steel-connections.md`: keder, clamp bars, adjustable edges, arches, bale rings, low points, isolation.
- `reference/cable-steel-connections.md`: pins/lugs (full EN and AISC formulas plus worked examples), gussets (block tearing,
  Whitmore), mast heads, bases (base plate, EN 1992-4 anchors), tensioning, anchors, corner plates, fatigue.
- `reference/fabrication-tolerances.md`: EN 1090-2 execution, NDT, hole tolerances, galvanising, supplier hardware list.
- `reference/validation.md`: every tool path against published worked examples (SBE/SCI, Wald, Dowswell, Hilti PROFIS, IDEA StatiCa).
