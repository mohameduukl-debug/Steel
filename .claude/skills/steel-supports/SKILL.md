---
name: steel-supports
description: Structural steel supports of tensile fabric structures — masts (pinned, guyed, flying, tapered), struts, booms, arches, compression/tension rings, edge beams, frames, base hinges, base plates and foundations/ground anchors. Use to size and check steel members carrying membrane and cable forces (EN 1993-1-1 / AISC 360), choose base fixity, handle second-order effects, execution class (EN 1090-2) and pass reactions between membrane model and steel design.
---

# Steel supports for tensile structures

## Tool: `scripts/member_check.py` (CHS, RHS/SHS, I/H to EN 1993-1-1)
```bash
python3 member_check.py --list                                                     # built-in IPE/HEA/HEB
python3 member_check.py --section CHS:219.1x8 --L 7.5 --N 420 --My 12              # pinned mast
python3 member_check.py --section SHS:150x8:cold --L 6 --N 300 --My 25 --Mz 10     # strut / boom
python3 member_check.py --section IPE300 --L 6 --N 50 --My 80 --Vz 60 --psi-LT 0   # edge beam with LTB
python3 member_check.py --section I:500:250:10:20:12:welded --L 8 --N 200 --My 300 # welded girder
```
- Section properties from the true outline (root and corner radii, EN 10210 hot / EN 10219 cold). They match the section tables within ~1–2 % (tested).
- Class (Table 5.2, web α from N), shear, N + My + Mz section check, flexural buckling y/z (curves per Table 6.2),
  **LTB** for I sections (M_cr with C1 from ψ, 6.3.2.2), interaction 6.61/6.62 (Annex B), tension members.
- Class 4 is flagged and not designed (effective sections not implemented).

- **Class 4** I/RHS: effective section to EN 1993-1-5 §4.4 (ρ for internal and outstand parts, web in bending
  ψ = −1; neutral-axis shift neglected). Class 4 CHS stops with a warning (EN 1993-1-6 shell buckling).
- **Shear–moment interaction** 6.2.8: for V > 0.5 V_pl, the bending resistance is reduced with ρ = (2V/V_pl − 1)².

## Tool: `scripts/frame2d.py` (arches, tapered/guyed masts, frames: stability + 2nd order)
```bash
python3 frame2d.py arch --L 30 --f 6 --n 24 --section CHS:323.9x10 --q 12 --supports pinned --check --Lz 5
python3 frame2d.py arch --L 30 --f 6 --shape circular --supports fixed --section CHS:273x10 --q 10 --check
python3 frame2d.py mast --H 12 --D-base 219.1 --D-mid 323.9 --D-top 219.1 --t 8 --N 600 --Hlat 5 --check
python3 frame2d.py mast --H 12 --N 400 --base pinned --guy 6:30000 --guy -6:30000 --check      # guyed mast
python3 frame2d.py --input frame.json --check                                                  # any planar frame
```
- Beam-column elements with consistent geometric stiffness, truss elements for guys, banded solver.
- **α_cr** by inverse iteration → EN 1993-1-1 5.2.1: first-order analysis is adequate if α_cr ≥ 10.
- **Second order** with a buckling-mode imperfection, amplitude e0·L from Table 5.1 (elastic) for the member's curve.
- **Member design**, two methods reported: (a) equivalent column with in-plane L_cr = π√(EI/(α_cr N_Ed)) and first-order M;
  (b) second-order M with imperfection, then a cross-section check. Out-of-plane buckling uses `--Lz` (restraint spacing).
- Validation (tests): Euler pinned and cantilever columns exact; simply supported beam deflection, moment and reactions exact;
  beam-column amplification = exact tan(u)/u within 0.3 %; two-hinged and fixed parabolic arches within 1.5–2.5 % of
  Timoshenko & Gere's γ (28.5, 45.4, 101 for f/L 0.1, 0.2, 0.2 fixed). Deep arches (f/L = 0.3) come out ~5–6 % above the
  classical energy-method values, so use a small margin there.
- Loads are dead (fixed direction). Follower pressure on rings/arches is not modelled; for a ring under hydrostatic
  pressure use q_cr = 3EI/R³.

## Tool: `scripts/foundation_check.py` (gravity blocks, helical anchors)
```bash
python3 foundation_check.py block --B 2.5 --L 2.5 --D 1.5 --V 60 --H 45 --ha 0.3 --mu 0.45 --qRd 200
python3 foundation_check.py helical --T 8 --pull 110
```
- block: uplift (EQU, γ_G,stb), sliding (GEO, γ_R,h), overturning about the toe, bearing on B' = B − 2e, and eccentricity
  within B/6. Passive resistance on the block face is ignored (conservative). μ and q_Rd come from the geotechnical report.
- helical: Q_u = K_t·T (manufacturer torque correlation, [U]); allowable = Q_u/FS; a proof-load test is required.

## Tool: `scripts/mast_check.py` (quick CHS mast, same results as member_check for CHS)
```bash
python3 mast_check.py --D 219.1 --t 8 --L 7.5 --N 420 --M 12            # pinned mast, hot-finished (curve a)
python3 mast_check.py --D 168.3 --t 6.3 --L 5 --N 150 --M 20 --cold    # cold-formed (curve c)
python3 mast_check.py --D 273 --t 10 --L 6 --N 300 --M 40 --k 2.0      # cantilever mast (fixed base)
```
It checks section class (Table 5.2), the N+M section check (plastic interaction for CHS), flexural buckling
(§6.3.1, α by curve) and the N+M member check (Annex B, Cm from ψ).

## Support types and how they work with the membrane

| Element | Typical form | Behaviour | Watch |
|---|---|---|---|
| **Pinned mast** | CHS, tapered "cigar" CHS, lattice | near-axial N; guyed by tie-backs; rotates with the membrane | buckling K = 1.0; eccentricity at head; erection stability |
| **Fixed (moment) mast** | larger CHS / box | cantilever, no guys | K ≈ 2.0; big base moment and foundation |
| **Flying mast** | strut hung in cables | compression without reaching the ground | stability relies on cables; check all load reversals |
| **Boom / outrigger** | CHS or truss from a building | bending + axial | torsion if cables are off-axis |
| **Arch** | CHS, truss, bent tube | membrane sits on or clamps to it; compression + bending | in-plane and out-of-plane buckling; asymmetric snow/wind; restraint from the membrane is unreliable under suction |
| **Compression ring** | box or CHS ring | balances radial cable pulls (stadium roofs, cones) | ring buckling; uneven pulls; joints |
| **Top ring (bale ring)** | CHS ring + plates | collects cone membrane or radial cables | ring bending between hangers |
| **Edge beam / frame** | CHS, RHS, I | rigid boundary with keder/clamp | continuous line load from the membrane (n in kN/m); torsion from eccentric clamp |

## Design rules
1. **Get reactions per combination** from the non-linear membrane analysis (never superpose). Use the
   `pull` vectors in the model JSON (force from structure on support). Keep **concurrent** force sets
   (same combination) for connection and foundation design, and envelopes for members.
2. **Masts pinned at the base** unless there is a reason not to. The pin gives near-pure axial load,
   no foundation moment, and follows membrane movement. It needs guys/tie-backs for stability.
3. **Concurrency at heads.** Arrange lugs so all cable lines meet on the mast axis. Otherwise design for
   M = R·e. Plates go in the cable planes (no weak-axis bending).
4. **Second-order.** Include the initial bow (EN 1993-1-1 Table 5.1, elastic analysis: e0/L = 1/350 a0, 1/300 a,
   1/250 b, 1/200 c, 1/150 d),
   head eccentricity and support flexibility. Include steel flexibility in the membrane model if the head moves
   more than about 1–2 % of the membrane span.
5. **Buckling.** N_cr = π²EI/(kL)². CHS curve **a** hot-finished, **c** cold-formed. Tapered masts: use the
   tapered-member stiffness (energy method) or FE buckling.
6. **Arches.** Check in-plane buckling (≈ antisymmetric mode) and out-of-plane; use an FE eigenvalue plus imperfection.
   Treat membrane restraint cautiously (it vanishes where the membrane goes slack).
7. **Foundations.** Uplift = wind suction + prestress pull. Tie-back anchors: helical (e.g. 133–222 kN allowable per
   anchor, torque-proven [V]), grouted rock anchors, deadman blocks, tension piles. Align anchor heads with the
   cable line (articulated head).
8. **Execution** (EN 1090-2): EXC2 typical for CC2 canopies; EXC3 for fatigue-prone lugs/anchorages (wind flutter)
   and for CC3 stadium roofs. 100 % VT; supplementary NDT per Table 24 (butt welds U ≥ 0.5: EXC2 10 %, EXC3 20 % [V]).
9. **Corrosion.** Hot-dip galvanise (drain and vent holes in CHS), duplex paint for C4/C5. Isolate aluminium clamp
   extrusions and stainless bolts from galvanised steel.
10. **Erection.** Hinged masts are raised and then jacked (sand pot or telescopic section). Check temporary stability
    before the membrane is stressed.

## References
- `reference/steel-support-design.md`: EN 1993-1-1 buckling formulas, CHS classes, arch/ring notes, base hinges, base plates, anchors, reaction transfer workflow.
- Connections at heads, bases and corners: see the `tensile-connections` skill.
