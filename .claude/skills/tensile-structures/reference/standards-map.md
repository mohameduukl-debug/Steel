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
