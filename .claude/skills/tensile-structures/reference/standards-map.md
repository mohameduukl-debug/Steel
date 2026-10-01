# Standards map (what covers what): with verification status

Tags: **[V]** confirmed via search excerpt of the source; **[C]** standard clause content
known with confidence but not re-read at source; **[U]** unverified, so check before use.

## Membranes
| Document | Scope / key content | Status |
|---|---|---|
| **CEN/TS 19102:2023** *Design of tensioned membrane structures* | EU limit-state design (EN 1990 partial factor method) for coated/uncoated fabrics and foils, mechanically and pneumatically prestressed. γ_M plus modification factors (k_biax, k_age, k_dur, k_temp) on characteristic strength. Annex A material classes, Annex B ageing test procedure, Annex C typical k values. Connections, edges, corners. | exists and content headings [V]; formula placement and numeric values [U] |
| JRC132615 (Stranghöner, Uhlemann et al.) | background "Prospect for European guidance" | [V] |
| **EN 17117-1:2018** | biaxial tensile stiffness test method (cruciform, load ratios) → elastic constants | [V] |
| **EN 17117-2:2021** | determination of compensation values | [V] |
| MSAJ/M-02-1995 (Japan) | biaxial test: ratios 1:1, 2:1, 1:2, 1:0, 0:1 | [V] |
| MLIT Notification 666 (Japan) | allowable stress 1/8 (long-term) and 1/4 (short-term) of strength | [U] |
| **ASCE/SEI 55-16** *Tensile Membrane Structures* | LRFD and ASD combinations; life-cycle factor L_t = 0.75; "effective breaking strength" = lesser of fabric and seam; clearance rules §6.10 | [V] (numeric reduction factors [U]) |
| **ASCE/SEI 55-10** | T_r = β·L_t·T_s ≥ T_f; β = 0.17 (P+D), 0.27 (P+D+S), 0.33 (P+D+W), 0.27 (P+D+T); L_t = 0.75 (≤ 0.6 handled); biaxial 0.8·β·L_t·ΣT_s; seams Table 4-1 (heat 1.0, adhesive 0.5, sewn 0.6/0.9); overload combos 1.4(P+D), 1.0(P+D)+1.6W … | [V] (full text read) — used by `membrane_check.py --method asce55` |
| **FM Global DS 1-59** (2021) | minimum safety factors on new fabric: P+D 8.0; P+D+(L/S/R) 5.0; P+D+W 5.0; P+D+T 5.0 | [V] |
| TensiNet *European Design Guide for Tensile Surface Structures* (Forster & Mollaert 2004) | practice: stress factors, detailing, corner types, Cp guidance (App. A1), ETFE (App. A5, 2013) | [V] |
| EN 13782:2015 | temporary structures: tents | exists [V], details [U] |
| EN 15619:2014 | coated fabrics for tents: specification | [U] |
| EN 13501-1 | reaction to fire (PTFE/glass A2-s1,d0; PVC B-s2,d0 / B-s1,d0; ETFE B-s1,d0) | [V] |

## Cables and tension components
| Document | Key content | Status |
|---|---|---|
| **EN 1993-1-11:2006** (replaced by **EN 1993-1-11:2026**) | groups A (bars), B (ropes), C (parallel wire/strand); F_Rd = F_uk/(1.5γR) (ETA route, γR ≥ 1.0) with F_uk = F_min·k_e; k_e Table 6.3 (sockets 1.0, swaged 0.9); SLS limits Tables 7.1/7.2; fatigue; saddles and clamps | structure [V], formula via EAD [V], Table values partly [U] |
| EAD 200001-00-0602 | ETA basis for tension components; F_Rd = F_uk/(1.5γR), γR not < 1.0; k_e by test | [V] |
| EN 12385 series, EN 10264-2, EN 10244-2 | ropes, rope wire, zinc/Galfan coating classes (A heaviest) | [V] |
| EN 13411-3/-4/-5/-7 | ferrules, metal/resin sockets, U-bolt grips, socket testing | [V] |
| **ASCE/SEI 19-16** (now **19-22**) | S_d = S_n·N_f (or N_d at saddles) ≥ 2.2·T_n | [V] (2.0 factor for transient loads, LRFD in 19-22 [U]) |
| PTI DC45.1 / fib Bulletin 30 → 89 | stay cables: 0.45 GUTS fatigue test, 2×10⁶ cycles, residual strength 95 % GUTS | [V] (φ and service limits [U]) |

## Steel and connections
| Document | Key content | Status |
|---|---|---|
| **EN 1993-1-1** | member buckling §6.3.1 (CHS curve a hot-finished, c cold-formed), N+M Annex B; execution class Annex C | [C] |
| **EN 1993-1-8** §3.13 | pins: Table 3.9 lug geometry types A/B, Table 3.10 shear, bearing, bending, interaction; replaceable pin SLS checks; σ_h,Ed = 0.591√(E F_Ed,ser (d₀−d)/(d² t)) ≤ 2.5 f_y/γM6,ser; M_Ed = F(b+4c+2a)/8 | [V]/[C] |
| EN 1993-1-8 §4 | welds (directional / simplified), β_w | [C] |
| **EN 1090-2** | execution: EXC classes, holes for fitted pins H11, NDT Table 24 (EXC2 10 %, EXC3 20 % for butt welds U ≥ 0.5) | [V] partly |
| EN 1993-1-4 | stainless (α = 16×10⁻⁶/K, corrosion resistance class) | [C] |
| **AISC 360-22** D5, D6, J7 | pin-connected members: b_eff = 2t + 16 mm; a ≥ 1.33 b_eff; w ≥ 2 b_eff + d; hole ≤ d + 1 mm; φ = 0.75 | [V] |
| ISO 2553:2019 / AWS A2.4 | weld symbols | [V] |

## Actions
| Document | Note |
|---|---|
| EN 1991-1-4 / ASCE 7 wind | no Cp for hypars/cones; use canopy/vault values conservatively, TensiNet A1, published tunnel data, project tunnel/CFD |
| EN 1991-1-3 / ASCE 7 snow | drift and asymmetric cases; ponding (iterative, load follows deformed shape) |
| EN 1990 | combinations; reliability-calibrated partial factors for membranes suggest γ_P = 1.0 with γ_S = γ_W = 2.0, or γ_P = 1.2 with 1.5 (Eng. Struct. 214, 2020) [V] |

## US codes (used with `--code US`)
| Document | Use in the tools | Status |
|---|---|---|
| **ASCE 7-22** | §2.3.1 LRFD / §2.4.1 ASD combinations (snow strength-level: 1.0S, 0.3S, 0.7S ASD); wind q_z = 0.613·K_z·K_zt·K_e·V², K_d moved to the pressure equation, K_z = 2.41(z/z_g)^(2/α) | [V] (≥ 2 sources) |
| ASCE 7-16 / 7-10 | K_z = 2.01(z/z_g)^(2/α), α/z_g 7/365.76, 9.5/274.32, 11.5/213.36 m; K_d inside q_z | [V] |
| **AISC 360-22** | φ/Ω (E, F, G, D, J), E3/E4/E7, F2/F3/F6/F7/F8, G2/G4/G5/G6, H1-1, J2.4 welds, J3 bolts, D5/J7 pins | [V] (spec text) |
| **ACI 318-19 Ch. 17** | N_b = k_c√f'c·h_ef^1.5 (k_c = 24 in-lb → 10 SI), ψ factors, pullout 8A_brg·f'c, φ (Table 17.5.3) | [V] in-lb; SI conversion [C] |
| ASCE 19-22 | S_d ≥ 2.2·T (19-16); LRFD format of 19-22 not verified | [V]/[U] |

## Saudi Building Code (used with `--code SA`)
| Document | Content used | Status |
|---|---|---|
| SBC 2024 edition | mandatory since 2025-07-01; base editions not found | **not checked** |
| SBC 301-18 | ASCE 7-10 base; strength combinations §2.3.2 without snow/ice; wind q = 0.613·K_z·K_zt·K_d·V², V ultimate 3-s gust ≈ 40–56 m/s | [V] Arabic text (2018) |
| SBC 306-18 | AISC 360-10 base, LRFD only; φc = 0.85, φv = 0.90 | [U] (Arabic text, confirm CR) |
| SBC 304-18 | ACI 318-14 base, Ch. 17 anchoring | [V] |
| SBC 201-18 §3102 | membranes to ASCE 55; NFPA 701 or noncombustible; not lateral restraint | [V] Arabic text |
| SBC 303-18 | soils/foundations; sabkha, collapsible, expansive soils chapters | [V] (preface) |

Details and caveats: `codes-eu-us-saudi.md`.
