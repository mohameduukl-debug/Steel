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
