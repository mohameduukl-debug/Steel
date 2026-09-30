---
name: tensile-structures
description: Hub skill for tensile fabric (membrane) structures built from membrane fabric, steel cables and structural steel. Use it first for any question about how fabric, cables and steel work together — load path, design workflow, which specialist skill or tool to use. It covers concept, form finding, analysis, connection design, patterning and fabrication/shop drawings for canopies, sails, hypars, cones, arches, cable nets, masts and stadium roofs. Routes to membrane-fabric, cable-tension-members, steel-supports, tensile-connections, tensile-analysis and fabrication-drawings.
---

# Tensile Structures — system hub

A tensile structure is **one structural system in three materials**. The membrane
carries load only by tension and curvature. Cables collect the membrane force at
free edges, ridges and valleys. Steel (masts, arches, rings, frames) and
foundations take the concentrated cable and membrane forces to the ground.
None of the three can be designed on its own. A change in one (sag,
prestress, mast stiffness) changes the forces in the other two.

## The load path (memorise this)

```
 surface load p [kN/m²] (wind, snow)
        │  membrane equilibrium  n1/R1 + n2/R2 = p   (anticlastic: warp & weft curvatures opposite)
        ▼
 MEMBRANE stress n [kN/m] (warp/weft)  ── seams, reinforcements, clamp lines
        │  edge equilibrium  T = n · R          (R = edge radius, typical sag 8–12 % of chord)
        ▼
 EDGE / RIDGE / VALLEY CABLES  T [kN]   ── pockets, belts, clamp plates
        │  concurrency at corner plate:  R_anchor = Σ T_i + F_strap   (all lines of action through one pin)
        ▼
 CORNER PLATE / MAST HEAD / RING  ── forks, pins, lugs (EN 1993-1-8 §3.13)
        │  mast (pinned → axial), tie-back / guy, arch, frame, ring beam
        ▼
 STEEL SUPPORTS  N, M, V   ── base hinge, base plate, anchors
        ▼
 FOUNDATIONS  (uplift! tension piles, helical/rock anchors, deadman)
```

Key couplings:
* **Curvature ↔ prestress ↔ stiffness.** A flat membrane (large R) needs very high
  prestress to resist load, and it ponds. Double curvature is the design goal.
* **Edge sag ↔ cable force ↔ anchor force.** Halving the sag roughly doubles T and the corner
  reactions, but a deeper scallop loses fabric area.
* **Steel flexibility ↔ membrane stress.** Mast head or ring deflection relaxes the
  prestress. Model the steel with the membrane, or iterate the support displacements.
* **Everything is geometrically non-linear.** Never superpose load cases. Analyse each
  factored combination separately.
* **Fabrication is part of the structure.** Compensation, cable unstressed lengths and
  adjustment ranges decide whether the built prestress equals the design prestress.

## Workflow (and which skill/tool to use)

| # | Stage | Output | Skill → tool |
|---|-------|--------|--------------|
| 1 | Concept: shape type, supports, material family, prestress level | sketch, plan, heights | this skill + `membrane-fabric` |
| 2 | **Form finding** | equilibrium surface, cable sags, first reactions | `tensile-analysis` → `form_find_fdm.py` |
| 3 | Load analysis (prestress, wind ↑↓, snow, temperature) | stresses, deflections, reactions, slack/ponding | `tensile-analysis` → `dynamic_relaxation.py` (prelim), FE software (final) |
| 4 | Membrane checks | warp/weft/seam utilisation | `membrane-fabric` → `membrane_check.py` |
| 5 | Cable design and schedule | sizes, F_Rd, unstressed lengths | `cable-tension-members` → `cable_calc.py`, `cable_schedule.py` |
| 6 | Steel supports | mast, arch, ring, foundation checks | `steel-supports` → `mast_check.py` |
| 7 | Connections | corner plates, pins, lugs, clamps, mast heads | `tensile-connections` → `pin_connection.py`, `corner_plate.py` |
| 8 | Patterning | cutting patterns (compensated), seam layout | `fabrication-drawings` → `cutting_pattern.py` |
| 9 | Fabrication and shop drawings | GA, panel plan, patterns DXF, cable schedule, steel shop drawings, erection and prestress plan | `fabrication-drawings` → `export_dxf.py`, DXF writer |

Loop back as needed. Connection geometry changes the cable lengths
(node-to-pin deductions). Steel stiffness changes the stresses. Patterning can
move the seams, which changes the warp direction and so the stiffness.

## End-to-end quick run (all tools are stdlib Python 3, no installs)

```bash
S=.claude/skills
python3 $S/tensile-analysis/scripts/form_find_fdm.py sail4 --size 10 --high 3 --n 16 --qc 12 --prestress 2.0 --out sail --obj
python3 $S/tensile-analysis/scripts/dynamic_relaxation.py sail.json --Et-u 800 --Et-v 600 --EA-cable 14000 --pressure 0.9 --out sail_up
python3 $S/membrane-fabric/scripts/membrane_check.py --material PVC-II --nw 8.5 --nf 8.5 --case wind
python3 $S/cable-tension-members/scripts/cable_schedule.py --from-model sail.json --product Ronstan-ACS2-GS-20.1 --deduct 250 --out sail_cables
python3 $S/tensile-connections/scripts/corner_plate.py --m EC1:15:83:180:48 --m EC2:105:83:48:180 --m strap:60:6:100:173
python3 $S/tensile-connections/scripts/pin_connection.py --F 150 --d 30 --d0 31 --t 20 --a-lug 45 --c-lug 35
python3 $S/steel-supports/scripts/member_check.py --section CHS:168.3x8 --L 6 --N 250 --My 5
python3 $S/fabrication-drawings/scripts/cutting_pattern.py sail.json --panels-along v --strip 3 --comp-warp 0.8 --comp-weft 1.6 --out sail_patterns
python3 $S/fabrication-drawings/scripts/export_dxf.py sail.json --forces --out sail_GA
```
`examples/run_demo.sh` runs this whole pipeline.

## Rules of thumb to sanity-check any design (verify for the project)

* Membrane prestress: PVC ≈ 1–4 kN/m (often 1.5–2.5); glass/PTFE ≈ 2–8 kN/m (heavy grades 6–8); about 1.5–3 % of UTS.
* Edge-cable sag: 8–12 % of chord (≈ 10 %). T = n·R, R = c²/(8s) + s/2.
* Membrane stress factors on strength: about 4 (short-term wind) and 5–6 (long-term snow/prestress). FM DS 1-59: 8 (P+D), 5 (with S/W/T).
* Cables: F_Rd = F_min·k_e/(1.5·γR) (EN 1993-1-11 / ETA route); ASCE 19: S_d ≥ 2.2·T.
* Masts are normally pin-based and loaded near-axially. All cables at a head or plate should be concurrent.
* Slope ≥ ~15° is often quoted for drainage and self-cleaning. Always check ponding on the deformed shape.

## References in this skill
* `reference/system-interconnections.md`: how each pair of components interacts, every interface, failure modes.
* `reference/design-workflow-checklist.md`: stage-by-stage checklist with deliverables and hold points.
* `reference/model-schema.md`: JSON model format shared by all tools.
* `reference/standards-map.md`: which standard covers what (EU/US/JP), with verification status.

## Code-factor register (one place for every code value)
All tools read partial factors, stress factors, γR, k_e, SLS limits, ASCE factors and more from
`reference/code_factors.json`. Each entry is tagged **V** (confirmed from a source), **C** (standard
recommended value, NA may differ) or **U** (unverified), and every tool prints the tag next to the value it uses.
```bash
python3 .claude/skills/tensile-structures/scripts/factors.py report                  # list; flags U values
python3 .claude/skills/tensile-structures/scripts/factors.py template > project_factors.json
# fill in values from your code edition + National Annex, then either:
export TENSILE_FACTORS=project_factors.json        # all tools
python3 <tool>.py ... --factors project_factors.json   # one run (cable_calc: before the sub-command)
```
A project file only needs the keys you change (see `examples/project_factors_example.json`).
Before issuing calculations, make sure no **U** factor governs a check.

## Honesty about code values
Research for this skill used web search excerpts (primary PDFs were not
accessible). Values are tagged **[verified-search]**, **[code-knowledge]** or
**[unverified]** in the references. Before issuing calculations, confirm every
code factor against the edition and National Annex in force (e.g. EN 1993-1-11:2026
replaced the 2006 edition; CEN/TS 19102:2023 is a Technical Specification, not yet
a full EN). Always use the supplier's datasheet or ETA for actual products.
