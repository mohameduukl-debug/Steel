# Validation: connection-precedents

The skill finds and records ideas; it does not compute resistances. Validation therefore covers (1) the scoring and
gate logic against hand-worked expectations, (2) the parsers against the real page formats, (3) the enforcement hooks,
and (4) two complete real searches whose concepts were then verified with the connection tools.

| Item | Case | Reference | Expected | Obtained | Test |
|---|---|---|---|---|---|
| Weighted quality (`precedent_search.py` assess) | all features yes except drainage (w = 1) | hand: 10 × 15/16 | 9.375 → 9.4 | 9.4 | `TestPrecedents.test_weighted_assessment` |
| n/a handling | keder track, concurrency n/a | hand: excluded from Σw | 10.0 | 10.0 | same |
| Form-only rule | critical "no", scale gap 2, AI image | rule in SKILL.md | form only | form only | same |
| Gate | corner and mast-head examples | rule list in SKILL.md | PASS | PASS | `test_gate_passes...`, `test_masthead_example...` |
| Gate failures | Arabic search removed, pins unviewed, concept feature "?", untraced idea, detail from form-only pin, critical feature "?" | rule list | FAIL on that item | FAIL on that item | `test_gate_passes_on_worked_example_and_fails_when_degraded` |
| Gate state age | 24 h window | hook rule | pass, then expired | pass, then expired | `test_gate_state_file` |
| Pin page parser (`pinterest_fetch.py`) | og:image / og:title / description | Pinterest page markup (2026-10) | signature, title | match | `test_pinterest_parsing_offline` |
| Board/ideas parser | embedded pin objects (`node_id` = base64 "Pin:") | Pinterest SSR data (2026-10) | ids + signatures | match | same; live: 25/20/25 pins on 3 boards |
| URL classes | pin, board, ideas, search | Pinterest URL scheme | 4 classes | match | same |
| Network retry | 2 resets then OK; 403 | backoff 2, 4 s; 403 not retried | 3 calls, sleeps [2, 4]; 1 call | match | `test_fetch_retry_backoff` |
| Mode B ingest | 2 images + text file | — | 2 entries, links kept, unviewed | match | `test_ingest_mode_b` |
| Hooks | sizing command blocked / skip / help / demo / grep / after gate | hook rules | deny / allow ×4 / allow | match | `test_hooks` |
| Reminder | EN and AR design prompts vs unrelated prompts | — | hit / no hit | match | `test_hooks` |
| Worked example: corner | demo sail corner, 20 pins | corner_plate.py 2D | concurrent | e = 0.3 mm | `reference/worked-example-corner.md` |
| Worked example: mast head | demo mast head, 20 pins | corner_plate.py 3D | resultant on mast axis, 0 out of plane | (0, 0, 1), 0.000 kN | `test_masthead_example_and_verification_section` |

Live checks run in the cloud container on 2026-10-01 and 2026-10-09: `pinterest_fetch.py probe` = mode A
(pages and images reachable, search pages not), Arabic query terms tested (see `search_keywords.json` note).
