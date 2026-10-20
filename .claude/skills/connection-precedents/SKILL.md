---
name: connection-precedents
description: Mandatory first step before designing any steel or fabric connection in a tensile structure (corner plate, mast head or base, edge-cable clamp, keder or clamp bar, bale ring, cable fork/lug, tensioner, ridge/valley, saddle, arch attachment, ground anchor, low point). Search Pinterest for similar built details, download and view the images, score them, take the ideas worth using and list the mistakes not to copy (precedent board), agree a concept, pass the gate, then size it with tensile-connections. Use whenever the user asks to design, detail, sketch or improve a connection (وصلة معدنية، وصلة قماش، تفصيلة).
---

# Connection precedents: look at Pinterest first, then design

Rule: **before designing any metal connection or fabric connection, search Pinterest for similar details, look at the
pictures and take ideas from them.** Only then size the connection with `tensile-connections`. The precedents give the form;
our forces and the tools give the dimensions. Project hooks enforce this (see Enforcement).

## Workflow
1. **Define the node**: interface (fabric ↔ cable ↔ steel), forces and directions, material, project scale
   (sail / canopy / roof / stadium), adjustable or replaceable. `python3 scripts/precedent_search.py list`.
2. **Search plan**: `python3 scripts/precedent_search.py queries corner-plate --material PVC`.
   It prints primary, variant and Arabic queries, the fetch command, fallback domains, and the features that do not apply to the node.
3. **Search**: `WebSearch` with `allowed_domains: ["pinterest.com"]`. Run the primary queries, at least one variant and one Arabic
   query. Arabic: use the market term "مظلات شد إنشائي" plus the node word. Literal terms ("وصلة ركن") return tents and furniture.
   The Arabic results are mostly contractor photos (form, regional practice, typical local mistakes).
4. **Fetch and view**: pass the pin, board and ideas URLs from the results:
   ```bash
   python3 scripts/pinterest_fetch.py probe        # mode A (fetch here) or B (ask the user for screenshots)
   python3 scripts/pinterest_fetch.py fetch <URL> ... --node corner-plate --out prec_corner --details
   ```
   It saves `NN_<pin>.jpg` and `precedents.json`. Shop listings go last. Pinterest search pages need a login, so use the
   WebSearch results. **Open every image you judge with the Read tool.** Never judge a pin from its title.
   If fewer than 5 relevant pins, use the fallback domains (Architen, Birdair, TensiNet, Fabritecture, Pfeifer, Macalloy …).
   In mode B, give the user the Pinterest URLs, read the screenshots they send and register them with
   `python3 scripts/pinterest_fetch.py ingest <folder> --node corner-plate [--links links.json]`.
   `fetch` retries network errors and 429/5xx with backoff (2, 4, 8 s) and de-duplicates by pin id and image signature.
5. **Review** each viewed image with `reference/precedent-review.md`. Set `viewed`, `kind` (photo, shop_drawing,
   manufacturer, sketch, render, product, infographic, ai_generated), `scale`, `relevant`, the `ideas`, and the features
   yes / no / ? / n/a. Mark off-topic pins `relevant: false`.
6. **Board**: `python3 scripts/precedent_search.py board prec_corner/precedents.json --out corner_board`.
   - Weighted score: critical ×3 (concurrency, plate in plane, membrane-safe), ×2 (rotation, adjustment), ×1 (drainage, isolation, replacement).
   - Evidence factor by image type (photo 1.0 … AI image 0.2).
   - "form only" for a critical red flag, a scale gap of 2 or more, or an infographic/AI image.
   - Unreviewed pins are listed and not used.
7. **Concept**: propose 1–3 options to the user. Every idea is traced to precedent numbers (`from`). An idea is marked
   `detail: true` only when taken from an "ideas + details" precedent. Write the agreed concept into `concept`, with its
   features (all critical = yes).
8. **Gate**: `python3 scripts/precedent_search.py check prec_corner/precedents.json` must PASS:
   - ≥ 3 searches, including Arabic and variant;
   - ≥ 5 relevant viewed precedents, ≥ 3 of them real evidence;
   - critical features judged;
   - concept traced, no detail copied from a form-only precedent, all critical features satisfied.

   A pass is recorded in `.claude/state/precedent_gate.json`.
9. **Design and verify** with `tensile-connections` (`corner_plate.py`, `pin_connection.py`, `steel_joint_checks.py`,
   `fatigue_check.py`), then draw with `fabrication-drawings`. Record the tool results that prove the concept in the
   `verification` list of precedents.json; the board prints them. Keep the board `.md` with the calculation report.

## Enforcement (project hooks, `.claude/settings.json`)
- `.claude/hooks/precedent_reminder.py` (UserPromptSubmit) adds this rule to connection-design prompts, English or Arabic.
- `.claude/hooks/precedent_gate.py` (PreToolUse, Bash) blocks `pin_connection.py`, `corner_plate.py`,
  `steel_joint_checks.py`, `fatigue_check.py` and `steel_part_dxf.py` until a gate has passed in the last 24 h.
  Prefix `PRECEDENTS_SKIP=1` only when the user said to skip the precedent step, or to re-check an existing design. Say so when you do.
  `bash examples/run_demo.sh` and the unit tests are not affected.

## Rules
- A picture is not a design. Never take a plate thickness, pin diameter, weld or bolt size from a photo. Size
  everything from the analysis forces with the tools.
- Small shade-sail hardware (rings, shackles, carabiners, eye bolts) is "form only" for permanent structures.
- AI-generated images and infographics are not evidence. They do not count toward the gate.
- Respect copyright: images are downloaded only for private review. Cite and link the pins, and never paste their images into
  drawings or reports. Proprietary hardware comes from the supplier's data.
- Every script prints its assumptions. Pass them on, and state that this step finds ideas, not code compliance.

## Limitations
- Pinterest pages are parsed from their embedded data; if Pinterest changes its page format, `fetch` returns no pins.
  Then switch to mode B (screenshots + `ingest`). Search pages need a login, so discovery relies on WebSearch.
- The same drawing is often re-uploaded under different pins and image signatures (worked examples: corner #7 and
  mast head #7). Duplicate images are not detected automatically without an image library; note them by hand.
- Judging a feature from a photo is an engineering opinion. The board records every judgement next to its link so a
  reviewer can check it. The gate checks that the work was done, not that every judgement is right.
- Precedents never replace the checks: the concept is sized and verified with `tensile-connections`.

## References
- `reference/search_keywords.json`: 14 node types, English/Arabic queries (Arabic tested 2026-10), variants, n/a features,
  checks, fallback domains with reachability.
- `reference/precedent-review.md`: how to read a connection picture, image types, scale, feature weights, typical red flags.
- `reference/worked-example-corner.md`: real search for the demo sail corner (20 pins, 15 viewed, gate passed, concept
  verified with corner_plate.py: 0.3 mm eccentricity). Data: `examples/precedents_corner_example.json`.
- `reference/worked-example-masthead.md`: real search for the demo mast head (20 pins, 11 viewed, gate passed, concept
  verified in 3D: mast reaction along the axis, zero out-of-plane force on the ear plates). Data:
  `examples/precedents_masthead_example.json`.
- `reference/validation.md`: what is tested and how.
