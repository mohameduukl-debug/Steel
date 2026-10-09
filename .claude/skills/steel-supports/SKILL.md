---
name: steel-supports
description: Structural steel supports of tensile fabric structures — masts (pinned, guyed, flying, tapered), struts, booms, arches, compression/tension rings, edge beams, frames, base hinges, base plates and foundations/ground anchors. Use to size and check steel members carrying membrane and cable forces (EN 1993-1-1 / AISC 360), run 2D/3D frame analysis with tension-only prestressed cables, α_cr and second-order effects with EN 1993-1-1 imperfections, choose base fixity, check gravity blocks and helical anchors, execution class (EN 1090-2) and pass reactions between membrane model and steel design.
---

# Steel supports for tensile structures

Workflow: membrane reactions (`reactions[].pull`, one combination at a time) → **`frame3d.py`** (mast + tie-backs +
cables: α_cr, second order, member checks) or `frame2d.py` (planar arches and tapered masts) → `member_check.py` /
`mast_check.py` for single members → `foundation_check.py` for blocks and anchors → connections (`connection-precedents`
first, then `tensile-connections`). All tools are stdlib Python 3, print their assumptions, and read code factors from
`tensile-structures/reference/code_factors.json` (pass `--factors project.json` for a National Annex).
Validation against independent references is in `reference/validation.md`.

## Tool: `scripts/frame3d.py` (3D frames + tension-only cables: linear, α_cr, second order)
```bash
python3 frame3d.py mast --H 8 --section CHS:219.1x8 --base pinned --tie=-5,0,0:25000:10 \
      --tie 2.5,4.33,0:25000:10 --tie 2.5,-4.33,0:25000:10 --load 12,4,-3 --check        # guyed mast
python3 frame3d.py mast --H 6 --section CHS:168.3x8 --tie=-5,0,0:20000:5 --tie 3,4,0:20000:5 \
      --tie 3,-4,0:20000:5 --reactions sail.json --node 0 --reaction-factor 1.0 --check   # membrane corner pull on the head
python3 frame3d.py --input frame3d.json --check --imp unique --out res                  # any space frame (schema: reference §17)
python3 frame3d.py --input frame3d.json --reactions sail.json --map 0:1,12:9            # attach membrane reactions by id
```
- Elements: 12-DOF beam-columns (consistent geometric stiffness, members subdivided by `div`, default 4; mast generator 8).
  End releases `pinned`/`pinned_y`/`pinned_z`. `truss` bars, and **tension-only `cable`s with prestress** (`prestress` T0 in
  kN, or unstressed length `L0`). Slack cables drop out by status iteration.
- Analyses: first order (cables with string stiffness N/L); **α_cr** by Sturm-sequence bisection + shifted inverse
  iteration (EN 1993-1-1 5.2.1(3): α_cr ≥ 10 → first order adequate); **second order** (K_E + K_G(N) iterated) on an
  imperfect geometry: `--imp unique` (default, EN 1993-1-1 5.3.2(11) eq. 5.9/5.10), `sway` (φ0·h), `mm:<amplitude>`, `none`.
- Membrane reactions: `--reactions model.json` reads `reactions[].pull` (force from the membrane on the support).
  The `mast` generator uses `--node <membrane id>` (applied at the head). `--input` uses `--map m:f,...`, or else
  matches by xyz within `--match-tol` (0.05 m). In the JSON: `"reactions": {"file", "map", "factor", "tol"}`.
- `--check`: EN 1993-1-1 checks with `member_check` for every beam with a section: (a) equivalent column, first-order
  forces with L_cr = π√(EI/(α_cr N_Ed)) about both axes (conservative) or the member's `Lcr_y`/`Lcr_z`, LTB over `Lb`
  (default the member length); (b) second-order forces + 6.2.9 cross-section check.
- Output: α_cr, imperfection used, N/My/Mz/T per member (first and second order), cable slack flags, reactions,
  max displacements, near-mechanism notes. `--out` writes JSON. `--factors` overrides the register.
- Validated: PL³/3EI, TL/GJ, Euler π²EI/L² and π²EI/4L², releases (5qL⁴/384EI), a two-guy hand solution in both
  regimes (both guys active / one slack), tan u/u amplification, agreement with frame2d (α_cr, N, M, P-Δ, < 10⁻³), and
  the 5.3.2(11) imperfection reproducing χ to within 0.5 %.

## Tool: `scripts/member_check.py` (CHS, RHS/SHS, I/H to EN 1993-1-1)
```bash
python3 member_check.py --list                                                     # built-in IPE/HEA/HEB
python3 member_check.py --section CHS:219.1x8 --L 7.5 --N 420 --My 12              # pinned mast
python3 member_check.py --section SHS:150x8:cold --L 6 --N 300 --My 25 --Mz 10     # strut / boom
python3 member_check.py --section IPE300 --L 6 --N 50 --My 80 --Vz 60 --psi-LT 0   # edge beam with LTB
python3 member_check.py --section I:500:250:10:20:12:welded --L 8 --N 200 --My 300 # welded girder
python3 member_check.py --section CHS:273x10 --L 6 --N 300 --My 40 --ky 2 --kz 2    # cantilever (sway Cm = 0.9 auto)
```
- Section properties from the true outline (root and corner radii, EN 10210 hot / EN 10219 cold), within 1–2 % of tables.
- Class (Table 5.2, web α from N; limits from the register). Shear with the 6.2.8 reduction. Section N + My + Mz:
  **6.2.9.1 plastic interaction** for class 1–2 (I/H, RHS; CHS with M_N = M_pl·cos(πn/2)), linear for class 3,
  effective section (EN 1993-1-5 4.4, simplified) for class 4 I/RHS. Class 4 CHS stops with a warning (EN 1993-1-6).
- Flexural buckling y/z (curves from Table 6.2, α from the register). **LTB** for I sections: M_cr with C1 from
  **NCCI SN003b Table 3.1** (ψ via `--psi-LT`) or `--C1`, length factor `--kLT`. Interaction 6.61/6.62 (Annex B,
  Table B.2 k_zy incl. λ̄_z < 0.4). Cm from ψ (`--psi-y/--psi-z/--psi-LT`), 0.9 for sway (`--sway-y/--sway-z`, auto at
  k ≥ 2), overrides `--Cmy/--Cmz/--CmLT`. Tension members: N_t + N-M section check.
- Options: `--cold`, `--fy`, `--ky/--kz`, `--Vy/--Vz`, `--factors`.
- Validated: χ against the ECCS/ESDEP table (28 values, ≤ 5·10⁻⁵); M_cr closed form (−0.3 %); Gardner & Nethercot
  Ex. 6.6 (M_N,y), 6.7 (CHS N_b,Rd), 6.8 (M_cr, χ_LT) and 6.10 (Annex B: 0.66/0.97, k_zy, k_zz) all within 0.5 % or 0.01.

## Tool: `scripts/frame2d.py` (planar: arches, tapered/guyed masts, frames: stability + second order)
```bash
python3 frame2d.py arch --L 30 --f 6 --n 24 --section CHS:323.9x10 --q 12 --supports pinned --check --Lz 5
python3 frame2d.py arch --L 30 --f 6 --shape circular --supports fixed --section CHS:273x10 --q 10 --check
python3 frame2d.py mast --H 12 --D-base 219.1 --D-mid 323.9 --D-top 219.1 --t 8 --N 600 --Hlat 5 --check
python3 frame2d.py mast --H 12 --N 400 --base pinned --guy 6:30000 --guy=-6:30000 --check      # guyed mast (two-way bars)
python3 frame2d.py --input frame.json --check --out res                                        # any planar frame (reference §16)
```
- Beam-columns with consistent geometric stiffness, truss elements for guys (these carry compression: use frame3d for
  tension-only cables). Banded solver. α_cr by inverse iteration. Second order with a buckling-mode imperfection
  of amplitude e0·L (Table 5.1, register). Member design: (a) equivalent column with in-plane
  L_cr = π√(EI/(α_cr N)) and first-order M; (b) second-order M + cross-section check. `--Lz` is the out-of-plane
  restraint spacing. Options: `--n`, `--shape`, `--supports`, `--q`, `--base`, `--N`, `--Hlat`, `--guy dx:EA`
  (write `--guy=-6:...` for a negative offset), `--fy`, `--factors`.
- Validated: Euler columns, beams, tan u/u, and Timoshenko & Gere arch γ (28.5, 45.4, 101) within 1.5–2.5 %
  (deep arches with f/L = 0.3: +5–6 %).

## Tool: `scripts/mast_check.py` (quick CHS mast; same results as member_check for CHS)
```bash
python3 mast_check.py --D 219.1 --t 8 --L 7.5 --N 420 --M 12            # pinned mast, hot-finished (curve a)
python3 mast_check.py --D 168.3 --t 6.3 --L 5 --N 150 --M 20 --cold    # cold-formed (curve c)
python3 mast_check.py --D 273 --t 10 --L 6 --N 300 --M 40 --k 2.0      # cantilever mast (fixed base, sway Cm = 0.9)
```
It checks the class (Table 5.2), N + M on the section (M_pl·cos(πn/2)), flexural buckling (§6.3.1) and N + M on the member
(Annex B 6.61, Cm from `--psi`, 0.9 when `--sway` or k ≥ 2). Options: `--curve`, `--fy`, `--factors`. Validated against
Euler, eq. (6.49) by hand, frame2d/frame3d N_cr (< 10⁻⁵) and Gardner & Nethercot Ex. 6.7.

## Tool: `scripts/foundation_check.py` (gravity blocks, helical anchors)
```bash
python3 foundation_check.py block --B 2.5 --L 2.5 --D 1.5 --V 60 --H 45 --ha 0.3 --mu 0.45 --qRd 200 [--cover 0.5] [--unfactored]
python3 foundation_check.py helical --T 8 --pull 110 [--shaft SS175|SS5|RS2875|RS3500|RS4500] [--FS 2.5]
```
- block: uplift (EQU, γ_G,stb), sliding ((γW − V)μ/γ_R,h), overturning about the toe, bearing on B' = B − 2e with
  γ_G = 1.35 or 1.0 (worst), and e ≤ B/3 (EN 1997-1 6.5.4; a note above B/6). Passive resistance is ignored. μ and q_Rd come
  from the geotechnical report.
- helical: Q_u = K_t·T with K_t from **ICC-ES ESR-2794** (10 ft⁻¹ = 32.8 m⁻¹ square shaft; 30/23/18 m⁻¹ pipe shafts),
  allowable = Q_u/FS with FS ≥ 2.0 [V]. Compare with the service pull, observe the ESR capacity caps, and proof-test.

## Design rules (details and sources in `reference/steel-support-design.md`)
1. **Reactions per combination** from the non-linear membrane analysis; never superpose. Envelopes for members,
   concurrent sets for connections and foundations.
2. **Masts pinned at the base** unless there is a reason not to. Give them ≥ 3 non-coplanar tie-backs: with two guys in one
   plane, a mast pinned at the base has zero out-of-plane stiffness. Restrain mast torsion somewhere.
3. **Concurrency at heads.** All cable lines should meet on the mast axis, otherwise design for M = R·e.
4. **Stability.** Check α_cr. If it is below 10, use second order with imperfections (`frame3d --imp unique`). Use the
   eigenvalue L_cr for guyed, tapered and flying masts and for arches, not textbook k factors. Snap-through of shallow arches and
   flying struts needs large-displacement FE.
5. **Arches and rings.** The membrane gives no dependable out-of-plane restraint under suction. Ring q_cr = 3EI/R³ is for
   follower pressure, while the tools apply dead loads.
6. **Foundations.** Uplift = wind suction + prestress pull. Use torque-proven helical anchors, rock anchors or deadman blocks,
   with the anchor head on the cable line.
7. **Execution.** EXC2 is the minimum for CC1/CC2; EXC3 with fatigue (lugs and anchorages under wind flutter) and for CC3
   (EN 1993-1-1 Annex C / UK NA Table NA.4) [V]. Galvanise with vent holes; isolate aluminium and stainless parts.
8. **Erection.** Hinged masts are raised and then jacked. Check temporary stability before the membrane is stressed.

## Limitations
- Linear elastic material. Second order is P-Δ/P-δ by geometric stiffness (no large rotations, no snap-through,
  no follower loads). Cables are straight (no sag or Ernst modulus) and tension-only. α_cr scales the whole load,
  prestress included.
- frame3d: no warping torsion, no shear deformation. **Torsional and lateral-torsional buckling are not in α_cr**:
  LTB is checked per member. Rigid supports (no springs or settlements).
- member_check: doubly-symmetric sections only. M_cr assumes fork supports with the load at the shear centre (C1 from end
  moments; use `--C1` otherwise). Class 4 is simplified (no neutral-axis shift) and class 4 CHS is not designed. No torsion,
  fatigue, fire or net-section checks.
- Cm comes from a linear moment (ψ). For transverse loads give `--Cmy/--Cmz/--CmLT`.
- foundation_check: rigid block, drained sliding, no passive resistance, no group or interaction effects. The helical K_t is
  product-specific (CHANCE ESR-2794).
- Eurocode checks only. The AISC 360 equivalents are listed in reference §15 for hand checks.
- Every factor is a recommended value (status C/V in the register). Confirm against the National Annex in force.

## References
- `reference/steel-support-design.md`: design guide covering support types, §5.2/5.3 stability and imperfections, member resistance, masts
  (pinned, guyed, flying, tapered), arches, rings, edge beams, base fixity, foundations and anchors, execution class/NDT,
  corrosion/fire, AISC 360 equivalents, deflection limits, and the frame2d/frame3d schemas. Every value is tagged [V]/[C]/[U].
- `reference/validation.md`: independent validation table (case, reference, expected, obtained, error, tolerance).
- Connections at heads, bases and corners: `connection-precedents` first, then `tensile-connections`.
