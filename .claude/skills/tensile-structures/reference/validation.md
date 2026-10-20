# Validation: tensile-structures (hub)

The hub owns the factor register, the report and the validation matrix. Its own independent check is statics of
the whole chain: whatever solver is used, the supports must carry exactly the applied load.

| Tool | Case | Independent reference | Expected | Obtained | Tolerance | Test |
|---|---|---|---|---|---|---|
| Chain (`form_find_fdm.py` → `dynamic_relaxation.py`) | 10 m sail, snow 0.75 kN/m² on plan | statics: ΣR_z = s·A_plan, ΣR_x = ΣR_y = 0; A_plan by shoelace formula in the test | s·A | within 1 % | 1 % | `TestChainStatics.test_snow_cable_net` |
| Chain (`form_find_fdm.py` → `membrane_dr.py`) | same, orthotropic CST | same | s·A | within 1 % | 1 % | `TestChainStatics.test_snow_cst_membrane` |
| Chain (analysis → `corner_plate.py`) | most loaded support, 3D | node equilibrium: anchor force = support reaction | R | within 2 % | 2 % | `test_corner_reaction_passes_to_corner_plate` |
| `factors.py` | project file overrides one key | override semantics in the module docstring | new value, status V; default unchanged | match | exact | `TestFactorRegister.test_project_override_precedence` |
| `factors.py` register | every entry | register rules (CLAUDE.md) | status V/C/U, source, range for numeric U | all | — | `test_every_entry_has_status_source_and_range_when_uncertain` |
| `report.py` | precedents (2 PASS, 1 degraded FAIL) + validation matrix | gate rules of connection-precedents | PASS rows; FAIL listed as governing | match | — | `TestReportAndValidation.test_report_with_precedents_and_validation` |
| `report.py` | design basis, load cases, membrane check | — | sections present | present | — | `tests/test_tools.py TestReport` |
| `validate_all.py` | Markdown tables with header/separator rows | Markdown table syntax | data rows only | match | exact | `test_table_rows_parser` |
| `validate_all.py` | every skill | — | all skills listed, coverage of scripts | match | — | `test_matrix_covers_all_skills` |

The per-skill validations (closed-form solutions, published worked examples, the standards' own numbers) are in each
skill's `reference/validation.md`. `python3 scripts/validate_all.py --run-tests` prints the current matrix.

## `loads.py` (code systems EU / US / SA; merged from the code-systems branch)

| Tool | Case | Reference | Expected | Obtained | Tolerance | Test |
|---|---|---|---|---|---|---|
| `loads.py combos` | ASCE 7-22 LRFD | ASCE 7-22 2.3.1 | 0.9D+1.0W; 1.2D+1.0S+0.5W | exact | exact | `test_tools` (combos) |
| `loads.py combos` | SBC 301-18 | SBC 301-18 (no snow) | no S term | exact | exact | same |
| `loads.py combos` | EN 1990 | EN 1990 Table A1.2(B), ψ0,W = 0.6 | 1.35G+1.5S+0.9W | exact | exact | same |
| `loads.py combos --set membrane` | ASCE 55 β | ASCE 55-10 Table 4-2 | 0.33 (P+D+W), 0.17 (P+D) | exact | exact | same |
| `loads.py wind` | ASCE 7-22 K_z, exposure B, 100 ft; ASCE 7-16 exposure C, 20 ft | ASCE 7 Table 26.10-1 | 0.95, 0.90 | within 0.01 | 0.01 | `test_tools` (wind) |
| `loads.py wind` | EN 1991-1-4 peak pressure | EN 1991-1-4 eq. 4.8 | q_p closed form | within 0.005 kN/m² | 0.005 | same |
