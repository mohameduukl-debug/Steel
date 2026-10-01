---
name: connection-precedents
description: Mandatory first step before designing any steel or fabric connection in a tensile structure (corner plate, mast head or base, edge-cable clamp, keder or clamp bar, bale ring, cable fork/lug, tensioner, ridge/valley, saddle, arch attachment, ground anchor, low point). Search Pinterest for similar built details, collect 5–10 precedents, take the ideas worth using and list the mistakes not to copy (precedent board), then design and verify with tensile-connections. Use whenever the user asks to design, detail, sketch or improve a connection (وصلة معدنية، وصلة قماش، تفصيلة).
---

# Connection precedents: look at Pinterest first, then design

Rule: **before designing any metal connection or fabric connection, search Pinterest for similar details and take
ideas from them.** Only then size it with `tensile-connections` (and the other specialist skills). The precedents give
the form; our forces and the tools give the dimensions.

## Workflow
1. **Define the node.** Interface (fabric ↔ cable ↔ steel), number and directions of the forces, material (PVC/PTFE/ETFE,
   galvanised/stainless), and whether it must be adjustable or replaceable. Pick the node type:
   `python3 scripts/precedent_search.py list`.
2. **Build the search plan.**
   ```bash
   python3 scripts/precedent_search.py queries corner-plate --material PTFE
   ```
   It prints the WebSearch queries, the Pinterest search URLs and the fallback queries (`--json` for machine use).
   The keyword library is `reference/search_keywords.json` (English plus Arabic terms, alternative solutions, and the checks for each node).
3. **Search Pinterest.** Run `WebSearch` with `allowed_domains: ["pinterest.com"]` for the primary queries plus at least one
   variant (different solution) and one Arabic query. Open boards or pins with `WebFetch` when the network allows. In some
   environments pinterest.com cannot be fetched. Then work from the search titles/snippets, give the user the Pinterest
   URLs from step 2, and ask them to share screenshots or pin links. Read the images they send.
   If Pinterest gives fewer than 5 useful precedents, use the fallback queries (manufacturer galleries, TensiNet, project pages).
4. **Review each precedent** with `reference/precedent-review.md`. Write down the ideas worth taking, and mark each
   feature yes / no / ? (concurrency, plate in cable plane, rotation, adjustment, membrane-safe edges, drainage,
   bimetallic isolation, replaceability).
   ```bash
   python3 scripts/precedent_search.py template corner-plate > precedents.json   # fill it in
   python3 scripts/precedent_search.py board precedents.json --out corner_board
   ```
   The board ranks the precedents, groups the ideas, lists the red flags not to copy, gives the design checklist and
   names the tools that must verify the chosen idea.
5. **Show the board to the user** with links to the sources, and propose 1–3 concept options (each idea traced to its precedent #).
   Agree on one.
6. **Design and verify** with `tensile-connections` (design procedure steps 1–8: `corner_plate.py`, `pin_connection.py`,
   `steel_joint_checks.py`, `fatigue_check.py`), then draw with `fabrication-drawings`.

## Rules
- A picture is not a design. Never take a plate thickness, pin diameter, weld or bolt size from a photo; size
  everything from the analysis forces with the tools.
- Precedents are often small shade sails. Check that the scale and the load level match before taking an idea for a large roof.
- Photos show the good and the bad. Many built details are eccentric, have no adjustment or trap water. List them under red flags.
- Respect copyright and proprietary products: cite and link the pins, and do not paste their images into our drawings.
  Proprietary hardware (forks, sockets, keder profiles) comes from the supplier's data.
- Record in the report what was searched and which precedent each idea came from (keep the board `.md`).
- Every script prints its assumptions. Pass them on, and say clearly that this step finds ideas, not code compliance.

## References
- `reference/search_keywords.json`: node types, English/Arabic search phrases, variant solutions, tools to verify.
- `reference/precedent-review.md`: how to read a connection photo, the feature checklist, typical red flags, mapping to checks.
