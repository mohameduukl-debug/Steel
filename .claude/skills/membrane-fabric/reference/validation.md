# Validation of the membrane-fabric tools

Every computational path of `membrane_check.py`, `material_select.py` and `biaxial_fit.py` is checked against an
independent reference in `tests/test_membrane_fabric.py`. The references are published worked examples, code text read
from the primary source, or closed-form and independent numerical solutions. Run the tests with
`python3 -m unittest tests.test_membrane_fabric -v` (about 2 s).

Sources:
- **[JRC23]**: Mollaert, Dimova, Pinto, Denton (eds.), *Prospect for European Guidance for the Structural Design of
  Tensile Membrane Structures*, JRC Science for Policy report JRC132615, EUR 31430 EN, 2023 (re-edition of JRC100166, 2016).
  https://publications.jrc.ec.europa.eu/repository/bitstream/JRC132615/JRC132615_01.pdf
- **[JRC25]**: Mollaert & Stimpfle, *CEN/TS 19102 "Design of tensioned membrane structures"*, JRC workshop "The
  second-generation Eurocodes: key changes and benefits through design examples", 3–5 June 2025, slides 94–113.
  https://eurocodes.jrc.ec.europa.eu/sites/default/files/2025-08/D1_Mollaert-Stimpfle_website.pdf
- **[MLIT666]**: MLIT Notification No. 666 (2002, as amended), 第六 and 第七.
  https://www.mlit.go.jp/notice/noticedata/pdf/201703/00006526.pdf
- **[FM]**: FM Global Property Loss Prevention Data Sheet 1-59 (2021), Table 2.2.6.1.
- **[JRC25r]**: Dimova et al. (eds.), *The second-generation Eurocodes: key changes and benefits through design
  examples*, JRC report JRC144386, 2025, doi:10.2760/3056713, ch. 13 (Mollaert & Stimpfle, CEN/TS 19102).
  https://publications.jrc.ec.europa.eu/repository/bitstream/JRC144386/JRC144386_01.pdf
- **[UHL11]**: Uhlemann, Stranghöner, Schmidt, Saxe, "Effects on elastic constants of technical membranes applying
  the evaluation methods of MSAJ/M-02-1995", Structural Membranes 2011, CIMNE, ISBN 978-84-89925-58-8, pp. 648–659.
  Open access: https://hdl.handle.net/2117/186360. Raw data of test T2 (glass/PTFE B18089, 10 MSAJ load-strain
  paths × 71 points) extracted from the vector plot of Fig. 5 into `reference/data/biaxial_uhlemann2011_T2.csv`.
- **[Lamb]**: H. Lamb, "On the vibrations of an elastic plate in contact with water", Proc. R. Soc. A 98 (1920): added
  mass of a clamped circular plate on one fluid side, 0.6689·ρ·a.
- Textbooks: Graff, *Wave Motion in Elastic Solids* (§4.4, rectangular membrane); Kreyszig, *Advanced Engineering
  Mathematics* (§12.9); Anderson, *Fracture Mechanics* (centre crack, K = σ√(πa)).

| Tool / path | Case | Reference + source | Expected | Obtained | Error | Tolerance |
|---|---|---|---|---|---|---|
| membrane_check `char_strength` | f_k from mean, Vx 0.12, kn 1.64 | [JRC25] slide 112: f_k,23 = n23·(1 − kn·Vx) | 138.15 / 134.94 kN/m | 138.150 / 134.938 | < 0.002 kN/m | 0.005 |
| membrane_check `--method ts19102` | hypar Type IV, situations 1/4/5, γM 1.5 | [JRC25] slide 112: f_Rd1 18.27/17.85, f_Rd4 54.82/53.55, f_Rd5 65.79/64.26 kN/m | as left | 18.274/17.849, 54.821/53.548, 65.786/64.257 | ≤ 0.004 kN/m | 0.006 kN/m |
| same | utilisations m_d/f_Rd (m_d = 1.5·m) | [JRC25] slide 112: 0.246/0.210, 0.648/0.238, 0.579/0.626 | as left | 0.2463/0.2101, 0.6485/0.2381, 0.5792/0.6256 | ≤ 0.0005 | 0.0006 |
| same | same hypar, written report | [JRC25r] Table 50 "Eurocode 12 (TS 19102)": 65 %, 24 % (snow), 58 %, 63 % (wind) | as left | 65, 24, 58, 63 % | 0 | rounding to 1 % |
| same, `--family alt_set_PES/PVC` | Costa Diadema, Type III, f_k from 112 kN/m, γM 1.5, second published factor set; situations 1, 5, 6 (warm) | [JRC25r] Tables 48–49 = [JRC25] slides 102–103: f_k,23 89.96, f_Rd1 19.99, f_Rd5 47.98, f_Rd6 31.99 kN/m | as left | 89.958; 19.991, 47.978, 31.985 | ≤ 0.005 kN/m | 0.006 kN/m |
| register `ts19102` range | sensitivity range covers the second set | ratio of the k-products alt/default in every situation (fabric and joint) | 0.595–0.893 | inside [0.6 − 0.005, 1.0] | – | – |
| membrane_check `--method factor` | SF 5 on 172/168 kN/m | [JRC25] slide 111: utilisation 0.69, 0.74 (warp), 0.25, 0.80 (weft) | as left | 0.689, 0.738, 0.253, 0.798 | ≤ 0.003 | 0.005 |
| membrane_check `--method french` | kq 1, ke 0.85, γt 4 | [JRC25] slide 110: TD 36.55 / 35.7 kN/m; TC/TD 0.97, 1.04, 0.36, 1.13 | as left | 36.55 / 35.70; 0.973, 1.042, 0.357, 1.126 | ≤ 0.004 | 0.006 |
| `french_ke` | ke(S) formula vs table | [JRC23] Code Review 21 eq. (3b) vs Table 6-1 (0.9 for 50–200 m², 0.86 for 250–500 m²) | 0.90 / 0.86 | 0.912 (200 m²) / 0.858 (500 m²) | 0.012 / 0.002 | 0.015 / 0.005 (table is rounded per band) |
| `--corner` with `--method french` | attachment rule | [JRC23] Code Review 21 eq. (4): TD = kq·n_eff·Trm/γtloc, γtloc 5 | 18.00 kN/m for Trm 90 | 18.00 | 0 | exact |
| membrane_check `--method partial` | German A-factors, connection, Sattler Type IV | [JRC25] slide 109: zul n0 83.60, zul nϑ 57.66, zul nt 37.20 kN/m; utilisation 0.486 / 0.308 / 0.828 | as left | 83.602, 57.657, 37.198; 0.486, 0.308, 0.828 | ≤ 0.003 kN/m | 0.01 (0.03 for nt: slide rounds A1·A3 to 2.25) |
| same, register table | global reduction γf·γM·ΠA | [JRC23] Code Review 20: winter storm 2.9–3.2 (γf 1.6), permanent 4.9–6.4 (γf 1.5) | in range | 2.957 / 5.184 | in range | range |
| membrane_check `--method japan` | divisors incl. folded / narrow joints | [MLIT666] 第六 一: Fm/(80t), Fm/(40t), Fm/(50t), Fm/(100t) (Fm in N/cm, t in mm) | n = Fm/8, /4, /5, /10, /5 | identical | 0 | 1e-9 |
| membrane_check `--prestress` `prestress_minimum` | PES/PVC 200 and 80 kN/m, glass/PTFE 147 and 60 kN/m | [JRC23] §3 (TensiNet rule) + Code Review 6 (French) | 2.6, 1.5, 3.675, 2.0 kN/m | identical | 0 | 1e-9 |
| membrane_check `--method fm` | P+D, P+D+S | [FM] Table 2.2.6.1: SF 8.0, 5.0 | 12.5 / 20.0 | 12.5 / 20.0 | 0 | exact |
| ETFE check `etfe_design_strength` | permanent situation | [JRC23] Eurocode Outlook 44: "fPM,d = 21 / (1.1 · 1.05 · 1.8) = 10.1 N/mm²", "σadm = 10.1 / 1.35 = 7.5" | 10.1 / 7.5 MPa | 10.101 / 7.482 | 0.001 / 0.018 | 0.01 / 0.02 |
| same | other situations | [JRC23] Outlook 44 formulas f_LTL, f_LTR, f_ST, f_STH, kperm 3.5 | closed form | identical | 0 | 1e-9 |
| `--flutter` `panel_frequency` | modes (1,1) (2,1) (1,3) (3,2), orthotropic tension | Graff §4.4 / Kreyszig §12.9: ω_mn = π√((N_x (m/a)² + N_y (n/b)²)/ρ_s) | closed form | identical | 0 | 1e-10 |
| independent added-mass route (test code) | clamped circular plate (1 − r²)² | [Lamb]: 0.6689 | 0.6689 | 0.66892 (spatial Rayleigh sum, Richardson 24/48) | 0.00002 | 0.001 |
| `added_mass_coeff` (spectral) | square panel, mode (1,1) | independent spatial Rayleigh double sum (validated against Lamb above), Richardson 16/32 | 0.7245 | 0.7258 | 0.18 % | 0.4 % |
| `added_mass_coeff` | circular membrane mode (corroboration, not in tests) | Zhao & Yu, World J. Mech. 2 (2012) Table 2: NAVMI rises from 0.654 (plate) to 0.739 (tension parameter 10⁴) | → membrane limit | 0.746 (same integral, J0 mode) | 1 % above the 10⁴ value | trend only |
| `--corner` `corner_check` | n_eff tables | [JRC23] §6.5: French 1.9/2.6/3.1, German 1.75/2.6, Eurocode Outlook 38 +50 % | as left | identical; n(r) = R/(θr) exact | 0 | exact |
| `--curvature` | cylinder, p 0.6 kN/m², R 7.5 m, no prestress | Laplace membrane equilibrium n1/R1 + n2/R2 = p ⇒ n = pR | 4.50 kN/m | 4.50 | 0 | print precision |
| `--tear` | slit-length scaling | Anderson, centre crack K = σ√(πa) ⇒ σ_c2 = σ_c1·√(a1/a2) | 18.00 kN/m (36 kN/m at 40 → 160 mm) | 18.00 | 0 | print precision |
| biaxial_fit `direct_to_inverse` / `inverse_to_direct` | E_x^d 1000, E_y^d 800, E^d_xy 400 kN/m | [JRC23] §2.4 eqs. 2.5–2.12 with the [JRC25] slide 99 stiffness set: E_x 800, E_y 640, ν_xy 0.4, ν_yx 0.5 | as left | identical | 0 | 1e-9 |
| biaxial_fit `fit` (+ `--per-ratio`, compensation) | strains generated with the DIRECT formulation, MSAJ ratios 1:1, 2:1, 1:2, 1:0, 0:1 | [JRC23] eqs. 2.1/2.2 + 2.9–2.12 | 800 / 640 / 0.5 / 0.4; elastic compensation (E_y − E_xy)·2/det | identical | < 1e-6 | 1e-4 |
| biaxial_fit `--msaj` (data check) | S_ε of the PUBLISHED constants on the extracted data, options 1–6 | [UHL11] Table 2, T2: S_ε 32.72, 23.09, 637.19, 625.49, 2.14, 4.42 %² | as left | 32.80, 23.11, 625.15, 613.30, 2.15, 4.41 | ≤ 0.3 % (8 paths), 1.9 % (10 paths) | 1 % / 2.5 % |
| biaxial_fit `--msaj` | option 1: all ratios, 8 paths, reciprocity | [UHL11] Table 2 T2: E_x t 1292, E_y t 816, ν_xy 0.57, ν_yx 0.90 kN/m | as left | 1312, 816, 0.560, 0.900 | +1.5 %, 0.0 %, −0.010, 0.000 | 2 % / 1 % / 0.015 |
| `--msaj --no-reciprocity` | option 2: 8 paths, 4 constants | [UHL11]: 1188, 864, 0.73, 0.69 | as left | 1190, 864, 0.726, 0.689 | +0.2 %, −0.1 %, −0.004, −0.001 | same |
| `--msaj --paths 10` | option 3: 10 paths (Bridgens & Gosling), reciprocity | [UHL11]: 914, 610, 0.83, 1.24 | as left | 911, 610, 0.824, 1.231 | −0.3 %, 0.0 %, −0.006, −0.009 | same |
| `--msaj --paths 10 --no-reciprocity` | option 4 | [UHL11]: 860, 634, 0.94, 1.08 | as left | 864, 633, 0.931, 1.083 | +0.4 %, −0.1 %, −0.009, +0.003 | same |
| `--msaj --ratios 1:1,1:2` | option 6 (synclastic, practical) | [UHL11]: 1336, 824, 0.60, 0.97 | as left | 1356, 828, 0.595, 0.974 | +1.5 %, +0.5 %, −0.005, +0.004 | same |
| `fit_msaj(fix_Ew_t=1600)` | option 5 (1:1 / 2:1): published E_x t 1600 is the grid's upper bound (also T1 option 6) | [UHL11]: 1600 (bound), 924, 0.48, 0.83, S_ε 2.14 | as left | free optimum 1895 with S_ε 0.82 < 2.14; with E_x t held at 1600: 922.5, 0.483, 0.838, S_ε 2.153 | −0.2 %, +0.003, +0.008, +0.6 % | 0.5 % / 0.01 / 1 % |
| fit residual | least squares vs published grid search on the same data | S_ε of the tool ≤ S_ε of the published constants (8 paths, 4 constants exactly; reciprocity +0.5 % because the paper accepts E_x/E_y − ν_yx/ν_xy within ±0.005) | – | holds for options 1–4, 6 | – | – |
| material_select `select` | documented selection, hypar Type IV, design wind weft 40.2 kN/m, CEN/TS 19102 | [JRC25] slide 112: f_Rd5 weft 64.26 → utilisation 0.626 | 0.626 | 0.6256 | 0.0004 | 0.001 |
| materials.json | unit conversions of every published value (N/5cm, daN/5cm, N/3cm, lb/in) | manufacturer sheets / [JRC23] Outlooks 5–12 (raw value stored with each entry) | raw × unit factor | matches | ≤ 0.6 % (rounding) | 0.6 % |

Extraction uncertainty of the [UHL11] data: the PDF figures are vector graphics, so the points were read from the
plot coordinates (marker centres; axes calibrated by least squares on the grid lines, which deviate ≤ 0.06 pt from a
straight scale = 0.008 % strain, 0.02 kN/m). The same data plotted in Fig. 6 agree with Fig. 5 within 0.0085 % strain
and 0.036 kN/m. Fitting Fig. 6 instead of Fig. 5 changes E·t by ≤ 0.2 %, ν by ≤ 0.008 and S_ε by ≤ 1.6 % (options 1–6). The plotted 71
points per path are the evaluated set: S_ε is a sum, and it matches the published value within 0.3 % for 8 paths.

## Not reproduced / not validated against an external data set
- [UHL11] Table 2 options 7 and 8 (2:1 / 1:0 and 1:2 / 0:1, three paths each) are **not** reproduced: the published
  constants give S_ε 885 and 127 %² on the plotted paths, not the published 0.62 and 0.98, and the exact least-squares
  fits (1119/417/0.47/1.27 and 1146/818/0.69/0.96) do not match the published values (520/894/1.33/0.78,
  500/732/1.40/0.96). The published Ex t sits at or near 500 kN/m for all three tests, which suggests a bound of the
  authors' grid search or a different set of paths. The paper does not give enough detail to resolve this.
- The default fit (`fit`, secant through the origin of the increments) has no published counterpart on raw data; it
  gives 778/547 kN/m on test T2, against 1312/816 (8 paths) or 911/610 (10 paths) for the MSAJ fit. This spread is the
  paper's point: state the evaluation option with the constants.
- Only one data set (glass/PTFE, one test) is reproduced. No open raw data set with fitted constants was found for
  PES/PVC (see verification-log.md).
- The tear-propagation factor (`tear_factor`, U) and the added-mass model factor (`added_mass_model`, U) remain
  practice values. Their ranges are covered by `--sensitivity`.
