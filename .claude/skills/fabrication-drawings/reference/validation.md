# Validation of the fabrication-drawings tools

All cases are unit tests in `tests/test_fabrication_drawings.py` (run `python3 -m unittest
tests.test_fabrication_drawings -v`, about 12 s). Every reference is independent of the tool: closed-form geometry,
a hand calculation, or the file-format specification. Lengths in mm unless noted.

## 1. Patterning against exact geometry (`cutting_pattern.py`: `flatten`, `process_panel`, `main`)
| Tool | Case | Reference + source | Expected | Obtained | Error | Tolerance |
|---|---|---|---|---|---|---|
| process_panel | cone frustum r 6→2 m, H 4 m, 48 bays, panel of 4 bays (30°), no compensation | development of a right circular cone = annular sector, radii s = r / sin α (descriptive geometry; any differential-geometry text on developable surfaces) | s_in 2828.4271, s_out 8485.2814 | 2828.4271, 8485.2814 | < 1e-11 rel. | 1e-6 rel. |
| process_panel | same, sector angle | faceted cone: θ_p = n·2 asin(sin α sin(Δθ/2)); smooth cone: θ sin α | 0.370108 rad (faceted); 0.370240 (smooth) | 0.370108 | 0 (faceted); −3.6e-4 rel. (smooth, chord discretisation) | 1e-9 rad; 5e-4 |
| process_panel | same, arc lengths of the end rows | chord sum n·2r sin(Δθ/2); smooth arc r·θ | 1046.4501 / 3139.3502 (r·θ: 1047.1976 / 3141.5927) | 1046.4501 / 3139.3502 | < 3e-12 rel.; −7.1e-4 vs smooth = 1 − sin(x)/x | 1e-6; 1 − sin(x)/x |
| process_panel | same, net area | faceted development ½(s_out² − s_in²)·n sin β; smooth sector ½ θ sin α (s_out² − s_in²) | 11.826563 m² (faceted); 11.847688 m² (smooth) | 11.826563 m² | 2e-16 rel.; −1.78e-3 vs smooth | 1e-9; analytic chord bound |
| process_panel | same, flattening strain / area error | developable surface → zero strain | 0 | 4.8e-15 / 0 | — | 1e-9 |
| flatten | cone 36 bays, 3-bay panel: distances between ALL node pairs | exact polar development (s_j, k·β) | — | max abs error 2.7e-12 mm | — | 1e-6 mm |
| process_panel | cylinder R 3 m, 8 m long, 36 bays, 3-bay strip | development = rectangle L × n·2R sin(Δθ/2) (smooth R·θ) | 8000.000 × 1568.8034 (smooth 1570.7963) | 8000.000 × 1568.8034, all vertices on the rectangle | < 1e-9 | 1e-6 |
| process_panel | same + warp 1.5 % / weft 0.8 % | hand calc 8000·0.985, 1568.8034·0.992 | 7880.000 × 1556.2529 | 7880.000 × 1556.2529 | < 1e-9 | 1e-6 |
| flatten | sphere R 10 m, zone 0–60°, one 30° gore (6 bays × 24 rows) | classical gore (sinusoidal projection, Snyder 1987 USGS PP 1395 p. 243): width R Δλ cos φ, centre length R Δφ = 10471.98, area R² Δλ (sin φ2 − sin φ1) = 45.345 m² | see left | widths −0.09…+0.32 %, centre −0.83 %, area −0.21 % | within max strain | ≤ ε_max (+5e-4) ; area ≤ 2 ε_max |
| flatten | same, strain | sphere not developable (Gauss) → ε > 0; LSQ RMS ≤ RMS of the textbook sinusoidal gore of the same mesh | RMS_sin 2.21 % | ε_max 1.77 %, RMS 0.45 %, p95 1.19 %; distribution <0.1 %: 44 %, 0.1–0.3: 37 %, 0.3–0.5: 3.5 %, 0.5–1: 8.4 %, ≥1: 6.9 % | RMS 0.45 ≤ 2.21 | RMS ≤ RMS_sin |
| flatten | 15° gore (3 bays) | as above, RMS_sin 1.05 % | — | ε_max 0.41 %, RMS 0.147 %, widths −0.04…+0.05 %, centre −0.22 %, area −0.14 % | — | as above |
| flatten | strain scaling 30° → 15° gore | narrow-strip theory: ε ∝ K w² → ratio 4 | 4 | ε_max ratio 4.33, RMS ratio 3.06 | — | 3.0–5.5 |
| main | 30° / 15° gore models, warning threshold 0.5 % [U] | register `fabrication.flatten_strain_warn_pct` | WARNING / no warning | WARNING printed / not printed | — | exact |

## 2. Compensation, decompensation and allowances
| Tool | Case | Reference + source | Expected | Obtained | Error | Tolerance |
|---|---|---|---|---|---|---|
| process_panel | flat 6000 × 2000 panel, warp 1.5 %, weft 0.8 % | hand calc (1 − c) | 5910.000 × 1984.000, 11.725440 m² | same | < 1e-9 | 1e-6 mm, 1e-9 m² |
| process_panel | weft decompensation 0 % at both ends over 1500 mm, stations every 500 mm | hand calc W(1 − 0.008 min(1, d/1500)) | 2000.000, 1994.667, 1989.333, 1984.000 … | same at all 13 stations; station x = 500 s × 0.985 | < 1e-9 | 1e-6 |
| process_panel | warp decompensation 0 % on both boundary sides over 1000 mm | hand calc L(1 − 0.015 min(1, w/1000)) | 6000, 5955, 5910, 5955, 6000 | same | < 1e-9 | 1e-6 |
| offset_polygon | rectangle, 80 mm ends, 50 mm sides | exact parallel offset | (L+100) × (W+160) | same | < 1e-9 | 1e-9 |
| offset_polygon | 3-4-5 and equilateral triangle, d = 60 | uniform offset = similar triangle scaled (r+d)/r about the incentre | vertex positions | same | < 1e-9 | 1e-6 |
| offset_polygon | 20° apex (mitre 5.76 d > 4 d) → bevel | removed tip area (d/sin(θ/2) − 4d)² tan(θ/2); clearance to net ≥ d | 1363.5690 mm²; ≥ 50 | 1363.5690; 50.000 | 5e-11 | 1e-6 |
| offset_polygon | (previous version, for the record) | — | ≥ 50 | 35.6 (mitre pulled back) | −29 % | fixed |
| offset_polygon | L-shape reflex corner | exact line intersection | (1050, 1050) | same | < 1e-9 | 1e-9 |
| main | flat 4 × 6 m model, 2 panels, cw 1.5 %, cf 0.8 %, seam 50, edge 80 | hand calc | 6070 × 2114, net 11.725 m², cut 12.832 m² | same | rounding | 1 mm / 0.001 m² |

## 3. DXF correctness (`dxf_reader.py` + round trips of every writer built on `dxf_writer.py`)
| Tool | Case | Reference + source | Expected | Obtained | Error | Tolerance |
|---|---|---|---|---|---|---|
| dxf_reader | group-code value types, sections, tables, POLYLINE/VERTEX/SEQEND | Autodesk AutoCAD DXF Reference: Group Code Value Types (help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-DXF, GUID-2553CF98…), HEADER variables ($ACADVER group 1 AC1009 = R11/R12; $INSUNITS group 70, 4 = Millimeters; GUID-A85E8E67…) | 10 malformed files rejected, valid parsed | 10/10 rejected, valid parsed | — | exact |
| cutting_pattern | patterns DXF and shop sheets | JSON polygons + DXF offsets | CUT/NET polylines closed, coordinates equal, layers defined, $INSUNITS 4, title fields | equal | < 1e-5 mm (6 decimals written) | 1e-5 |
| nest_panels | nested DXF | placed polygons; roll edges y = 0 and W | equal | equal | < 1e-5 | 1e-5 |
| export_dxf | GA DXF of a sail (n = 10) | model xyz × 1000 | mesh line ends, 3D cable polylines, support circles | equal | < 1e-5 | 1e-5 |
| steel_part_dxf | lug, corner plate | input part definition | see §5 | equal | < 1e-9 | 1e-9 |
| all writers | independent parser (optional test, skipped when ezdxf is absent) | ezdxf 1.4.4 `readfile` + `audit()` | 0 errors | 0 errors on 11 files; 1147 vertices and 577 texts identical to dxf_reader | 0 | exact |

## 4. Nesting (`nest_panels.py`)
| Tool | Case | Reference + source | Expected | Obtained | Error | Tolerance |
|---|---|---|---|---|---|---|
| nest | 4 × 3000 × 1240 on a 2500 roll, gap 20 | known optimum: 2 across (1240+20+1240 = 2500) → 3000+20+3000 | 6020 | 6025 (raster step 25) | +5 | ≤ dx; util 98.8 % |
| nest | 2 × 1000 × 2400 on a 2500 roll (one across) | clearance must hold along the roll | length ≥ 2020, clearance ≥ 20 | 2025, clearance 25 | — | ≥ gap |
| nest + verify | 18 multibay panels (auto-split) | independent exact polygon distance in the test | no overlap, clearance ≥ 20, inside roll | min clearance 26.5, margin 0, overlaps 0 | — | exact |
| nest (previous version, for the record) | same layout | — | ≥ 20 | 11.1 (gap only enforced across the roll) | — | fixed |
| verify | panel copy shifted 5 mm | must flag overlap | clearance 0, 1 pair | 0, 1 pair | — | exact |

## 5. Steel part drawings (`steel_part_dxf.py`)
| Tool | Case | Reference + source | Expected | Obtained | Error | Tolerance |
|---|---|---|---|---|---|---|
| lug | d0 41, a 50, c 35, base 160, H 120, t 20 | EN 1993-1-8 Table 3.9 type A geometry (input) | hole (0,120) Ø41; end distance 50; min clear edge 35; width 160 | same; 50.000; 35.000; 160 | < 1e-6 | ≥ spec, < spec + 0.05 |
| lug | mass | closed form: base rectangle-half + trapezoid flank + semi-ellipse head − hole, ρ 7850 [C] | 3.5413 kg | 3.5414 kg | 4e-5 rel. | 0.5 % |
| corner | 4 holes, edge 45 | input hole list; convex hull outline | centres/diameters exact; clear edge distance ≥ 45 (hull holes = 45) | 45.000, 45.000, 45.000, 79.43 (inner hole) | < 1e-9 | ≥ spec, < spec + 0.05 |
| both | title block | drawing-deliverables.md §2 | PROJECT, PART, DWG No, REV, SCALE, DATE, DRAWN, CHECKED, MATERIAL, QTY, MASS, EXC, UNITS | all present with input values | — | exact |

## 6. Schedules against the model
| Tool | Case | Reference + source | Expected | Obtained | Error | Tolerance |
|---|---|---|---|---|---|---|
| cutting_pattern | sail4 n 12, strip 3: panel quantity, seam lengths, 3D area | model grid lines and faces (computed in the test) | 4 panels; seam 3D lengths; Σ area_3d = Σ face triangles | equal | < 0.1 mm; < 1e-3 m² | as stated |
| cutting_pattern | net area (no compensation) vs 3D area; mating seam lengths | flattening strain bound | |ΔA|/A ≤ 2 ε_max | within | — | 2 ε_max |
| export_dxf --csv | sail4 n 10: cable groups, segments, node-to-node lengths, supports | model xyz (sum of segment lengths) | 4 groups | equal | < 0.06 mm (CSV rounding) | 0.06 mm |
| export_dxf vs cable_schedule.py --from-model | same | both against the model | same count, L_stressed equal | equal | < 0.1 mm | 0.1 mm |

## Not covered / limits of the validation
* No comparison with a commercial patterning program (MPanel, Easy, RFEM) on a doubly curved benchmark: the
  doubly curved check is against the closed-form gore and theory (strain exists and scales with K w²), not against
  another code's pattern. Stress-based patterning quality is outside the tool's scope (see SKILL.md Limitations).
* Geodesic seam mode is checked by existing tests in `tests/test_tools.py` (geodesic on a plane = straight chord,
  mating seams equal, not longer than the grid line).
