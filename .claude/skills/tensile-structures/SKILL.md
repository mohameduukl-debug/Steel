---
name: tensile-structures
description: Hub skill for tensile fabric (membrane) structures built from membrane fabric, steel cables and structural steel. Use it first for any question about how fabric, cables and steel work together — load path, design workflow, which specialist skill or tool to use. It covers concept, form finding, analysis, connection design, patterning and fabrication/shop drawings for canopies, sails, hypars, cones, arch-supported tunnels, multi-bay ridge/valley roofs, cable nets, masts and stadium roofs. Routes to membrane-fabric, cable-tension-members, steel-supports, tensile-connections, tensile-analysis and fabrication-drawings.
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
| 1 | Concept: shape, supports, material family, prestress level | sketch, plan, heights | this skill + `membrane-fabric` |
| 2 | **Form finding** (sail, hypar, cone, arch tunnel, multi-bay ridge/valley, custom) | equilibrium surface, cable sags, support/arch loads | `tensile-analysis` → `form_find_fdm.py` |
| 3 | Material data | E·t, ν, compensation from biaxial tests | `membrane-fabric` → `biaxial_fit.py` |
| 4 | **Load analysis**: prestress, wind (directions, zones), snow, ponding | stresses (warp/weft/principal), wrinkling, deflection, envelopes | `tensile-analysis` → `membrane_dr.py` (orthotropic CST), `dynamic_relaxation.py` (net, fast), `run_cases.py` |
| 5 | Membrane checks | material choice, fabric/seam utilisation per case, tear, corners, panel frequency, ETFE | `membrane-fabric` → `material_select.py`, `membrane_check.py --envelope --sensitivity` |
| 6 | Cables | F_Rd, SLS, rods, clamps, saddles, fatigue, schedule with unstressed lengths, stressing turns, force from frequencies | `cable-tension-members` → `cable_calc.py`, `cable_schedule.py --envelope` |
| 7 | Steel supports | members (CHS/RHS/I, LTB, class 4), arch/mast stability (α_cr, 2nd order), foundations | `steel-supports` → `member_check.py`, `frame2d.py`, `foundation_check.py` (`mast_check.py` quick) |
| 8 | Connections | pins/lugs, corner plates, welds, bolts, base plates, EN 1992-4 anchors, aluminium clamps, fatigue | `tensile-connections` → `pin_connection.py`, `corner_plate.py`, `steel_joint_checks.py`, `fatigue_check.py` |
| 9 | Patterning | geodesic seams, compensation/decompensation, auto-split, notches, panel sheets, nesting | `fabrication-drawings` → `cutting_pattern.py`, `nest_panels.py` |
| 10 | Drawings | GA/setting-out DXF, steel part drawings with weld symbols | `fabrication-drawings` → `export_dxf.py`, `steel_part_dxf.py`, `dxf_writer.py` |
| 11 | **Calculation report** | Markdown + HTML report with factors (V/C/U), results, governing utilisations, limitations | this skill → `scripts/report.py` |

Loop back as needed. Connection geometry changes the cable lengths (node-to-pin deductions); steel stiffness
changes the stresses; patterning can move the seams (warp direction and stiffness).

### Calculation report
```bash
python3 .claude/skills/tensile-structures/scripts/report.py --title "Project X" --model sail.json \
        --cases sail_cases_envelope.json --material PVC-III --cables sail_cables.csv \
        --patterns sail_patterns.csv --extra steel_checks.txt --out project_report
```
Sections: design basis (every factor with its V/C/U tag and the list of unverified ones), form finding, load cases
and envelopes, membrane check per case, cable schedule, patterns, further checks (pasted tool output), governing
utilisations and limitations.

## End-to-end quick run (all tools are stdlib Python 3, no installs)

```bash
S=.claude/skills
python3 $S/tensile-analysis/scripts/form_find_fdm.py sail4 --size 10 --high 3 --n 16 --qc 12 --prestress 2.0 --out sail --obj
python3 $S/tensile-analysis/scripts/run_cases.py sail.json examples/load_cases_example.json --out sail_cases
python3 $S/membrane-fabric/scripts/membrane_check.py --material PVC-III --envelope sail_cases_envelope.json
python3 $S/cable-tension-members/scripts/cable_schedule.py --from-model sail.json --envelope sail_cases_envelope.json --product Ronstan-ACS2-GS-17.0 --deduct 250 --out sail_cables
python3 $S/tensile-connections/scripts/pin_connection.py --F 150 --d 30 --d0 31 --t 20 --a-lug 45 --c-lug 35
python3 $S/steel-supports/scripts/frame2d.py mast --H 6 --D-base 168.3 --D-mid 168.3 --D-top 168.3 --t 8 --N 250 --check
python3 $S/fabrication-drawings/scripts/cutting_pattern.py sail.json --seams geodesic --strip 2 --auto-split --sheets --out sail_patterns
python3 $S/fabrication-drawings/scripts/nest_panels.py sail_patterns.json --out sail_nest
python3 $S/tensile-structures/scripts/report.py --model sail.json --cases sail_cases_envelope.json --material PVC-III --cables sail_cables.csv --patterns sail_patterns.csv --out report
```
`examples/run_demo.sh` runs the whole pipeline, including the arch and multi-bay examples.

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

**Sensitivity to uncertain factors.** Every U factor, and C factors quoted from a single source, carries a `range`
with a `range_source`. `--sensitivity` in `membrane_check.py`, `cable_calc.py` (resist, clamp, saddle),
`cable_schedule.py`, `fatigue_check.py`, `foundation_check.py helical` and `steel_joint_checks.py clampbar`
re-runs the check at both ends of the range. Every U factor in the register has a range (a test enforces this). The
report (`report.py`) adds a "Sensitivity to uncertain factors" table for the membrane envelope and the cable SLS. It reports **ROBUST** (the
OK / NOT OK decision does not depend on the factor) or **DEPENDS** (confirm the value before issue). A ROBUST result
lets you issue the check while the factor is still being verified. State that in the report.

## Honesty about code values
Research for this skill used web search excerpts (primary PDFs were not
accessible). Values are tagged **[verified-search]**, **[code-knowledge]** or
**[unverified]** in the references. Before issuing calculations, confirm every
code factor against the edition and National Annex in force (e.g. EN 1993-1-11:2026
replaced the 2006 edition; CEN/TS 19102:2023 is a Technical Specification, not yet
a full EN). Always use the supplier's datasheet or ETA for actual products.
