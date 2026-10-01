# CLAUDE.md

This repository is a knowledge base plus toolset (Claude Code skills) for **tensile fabric structures: membrane
fabric + steel cables + structural steel**, covering analysis, modelling, connections and fabrication drawings.

## Working rules
- Start with the `tensile-structures` skill (hub), then load the specialist skill(s) for the task.
- Before designing any metal or fabric connection, run the `connection-precedents` skill first: search Pinterest for
  similar details, view the images, build the precedent board, take ideas from it, pass `precedent_search.py check`, and only
  then size the connection with `tensile-connections`. Hooks in `.claude/settings.json` enforce this; use `PRECEDENTS_SKIP=1`
  only when the user says to skip the step or an existing design is re-checked.
- Prefer running the scripts in `.claude/skills/*/scripts/` over hand calculation. All are stdlib Python 3 (no pip).
- Every script prints its assumptions. Pass them on to the user, with the model limitations (e.g. the DR tool is a cable-net analogy).
- Code values: quote the tag from the reference files ([V]/[C]/[U]). Never present an [U] value as a code requirement.
  Tell the user to confirm factors against the standard edition and National Annex in force.
- Code factors live only in `tensile-structures/reference/code_factors.json` (read via `tensile-structures/scripts/factors.py`).
  Never hard-code a code value in a tool; add it to the register with a V/C/U status and a source.
- Keep the shared JSON model schema (`tensile-structures/reference/model-schema.md`) backward compatible when editing tools.
- Units: kN, m for analysis; mm for fabrication and DXF; kN/m for membrane stress; °C.

## Tests
`python3 -m unittest discover -s tests -v`. Keep them green. Add a test for every new calculation, ideally against an
independent worked example. `bash examples/run_demo.sh` must run without errors (output goes to `examples/output/`, which is gitignored).
