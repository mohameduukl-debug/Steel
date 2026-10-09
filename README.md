# Steel: Claude Code skills for tensile fabric, cable and steel structures

A set of **Claude Code skills** plus **runnable, dependency-free Python tools** for the analysis,
modelling, connection design and fabrication drawings of tensile membrane structures. It covers
the fabric, the cables and the structural steel, and how the three connect.

```
.claude/skills/
├── tensile-structures/     HUB: load path, interactions, workflow, standards map, JSON schema, code-factor register
│   └── scripts/factors.py, report.py
├── membrane-fabric/        materials (PVC, PTFE, silicone, ETFE, ePTFE), prestress, stress checks, seams
│   └── scripts/membrane_check.py, material_select.py, biaxial_fit.py
├── cable-tension-members/  spiral strand / FLC / stainless / bars; EN 1993-1-11, ASCE 19; lengths; schedules
│   └── scripts/cable_calc.py, cable_schedule.py
├── steel-supports/         masts, struts, arches, rings, bases, foundations/anchors
│   └── scripts/member_check.py, frame2d.py, foundation_check.py, mast_check.py
├── connection-precedents/  FIRST step for any connection: Pinterest precedent search, image review, board, gate
│   └── scripts/precedent_search.py, pinterest_fetch.py
├── tensile-connections/    fabric↔cable, fabric↔steel, cable↔steel; pins/lugs; corner plates; mast heads
│   └── scripts/pin_connection.py, corner_plate.py, steel_joint_checks.py, fatigue_check.py
├── tensile-analysis/       form finding (FDM, DR, URS), non-linear load analysis, software guide
│   └── scripts/form_find_fdm.py, membrane_dr.py, dynamic_relaxation.py, run_cases.py
└── fabrication-drawings/   patterning, cutting DXF, GA DXF, steel part drawings, drawing-set contents
    └── scripts/cutting_pattern.py, nest_panels.py, export_dxf.py, steel_part_dxf.py, dxf_writer.py, dxf_reader.py
```

Each skill has a `SKILL.md` (loaded by Claude Code when relevant) and a `reference/` folder with the
detailed knowledge base (formulas, code clauses, product data and checklists).

## How the skills fit together

```
form_find_fdm ──► dynamic_relaxation ──► membrane_check          (membrane)
      │                  │           └──► cable_calc / cable_schedule (cables)
      │                  └──────────────► corner_plate, pin_connection, mast_check (connections, steel)
      └──► cutting_pattern, export_dxf, steel_part_dxf               (fabrication drawings)
```
All tools share one JSON model format (`.claude/skills/tensile-structures/reference/model-schema.md`).

## Quick start (Python 3.9+, no installs)

```bash
bash examples/run_demo.sh            # full pipeline for a 10 m four-point sail -> examples/output/
python3 -m unittest discover -s tests -v
```

Selected commands:
```bash
S=.claude/skills
python3 $S/tensile-analysis/scripts/form_find_fdm.py cone --R 8 --r 0.6 --H 5 --anchors 6 --prestress 2.5 --out cone --obj
python3 $S/tensile-analysis/scripts/dynamic_relaxation.py cone.json --pressure 0.8 --out cone_up
python3 $S/cable-tension-members/scripts/cable_calc.py edge --chord 10 --sag 1 --n 3
python3 $S/tensile-connections/scripts/pin_connection.py --F 250 --Fser 170 --d 40 --d0 41 --t 20 --a-lug 50 --c-lug 35 --replaceable --aisc
python3 $S/fabrication-drawings/scripts/cutting_pattern.py cone.json --strip 2 --comp-warp 0.5 --comp-weft 2 --out cone_patterns
```

## Precedents before connection design
No connection is sized before similar built details have been looked at. The `connection-precedents` skill searches
Pinterest (WebSearch filtered to pinterest.com, English, Arabic and variant queries), downloads the pins and images
(`pinterest_fetch.py`), records a weighted review of each image (concurrency, plate in cable plane, membrane-safe
edges, rotation, adjustment, drainage, isolation, replaceability; image type; scale) and builds a precedent board.
`precedent_search.py check` is the gate. Project hooks in `.claude/settings.json` remind Claude of the rule on
connection prompts and block `pin_connection.py`, `corner_plate.py`, `steel_joint_checks.py`, `fatigue_check.py` and
`steel_part_dxf.py` until a gate has passed in the last 24 h (`PRECEDENTS_SKIP=1` for re-checking an existing design).
Worked example: `examples/precedents_corner_example.json` and
`.claude/skills/connection-precedents/reference/worked-example-corner.md`.

## Code factors
Every code value (partial factors, stress factors, γR, k_e, SLS limits …) sits in one register,
`.claude/skills/tensile-structures/reference/code_factors.json`, tagged V/C/U. Override it per project with
`--factors project.json` or `TENSILE_FACTORS=project.json`. Run `factors.py report` to list unverified values.
Each uncertain factor carries a `range`. The `--sensitivity` option (membrane_check, cable_calc, cable_schedule,
fatigue_check) re-runs the check at both ends of the range and reports ROBUST (the decision does not depend on the
factor) or DEPENDS (confirm the value before issue).

## Using the skills in Claude Code
Open this repo in Claude Code and ask naturally, e.g.:
* "Form-find a 12 m hypar sail with two high points at 4 m and check the edge cables."
* "Design the corner plate and pins for 95 kN edge cables meeting at 80°."
* "Produce cutting patterns for PTFE with 0.3 % warp and 2 % weft compensation."
* "What fabric and prestress should I use for a 20 m conical tent in a snowy area?"

Claude loads `tensile-structures` first and then the specialist skills and tools.

## Validation
* Pin checks reproduce an independent EN 1993-1-8 worked example exactly (shear 483 kN, bearing 426 kN, M_Ed 1.81 kNm, a ≥ 44.9 mm …).
* FDM: symmetric reactions, zero resultant without load, geometry invariant to q-scaling.
* DR: the prestress state converges at iteration 0; under load, Σ support pulls = Σ applied load.
* Catenary matches the parabola for small sag; T_B − T_A = w·h.
* A flat (developable) panel flattens with zero strain and exact area.
* Every generated DXF was opened with `ezdxf` recover/audit (0 errors) and rendered for visual checks.
* Cable force from frequencies recovers T and EI exactly. The Irvine correction recovers T when λ² ≈ 190 (the string
  model is 3.5× off) and reproduces Irvine's crossover ω̄ = 2π at λ² = 4π². ISO 898-1 stress areas match.
* The panel frequency reduces to the classical rectangular-membrane result when the added mass is zero.

## Important limitations
* The research behind the reference files used web-search excerpts (primary standards were not accessible).
  Every value is tagged **[V] verified-search**, **[C] code knowledge** or **[U] unverified**. Check code factors against the
  edition and National Annex in force (e.g. EN 1993-1-11:2026, CEN/TS 19102:2023) and use supplier datasheets or ETAs.
* `dynamic_relaxation.py` uses a cable-net analogy (no fabric shear or Poisson coupling). Use it for concept and checking.
  Final design needs orthotropic membrane FE with wrinkling (SOFiSTiK, Easy, ixForten, RFEM, GSA …).
* These tools support, and do not replace, a qualified engineer's design and checking.
