# Validation of the steel-supports tools

Every computational path of `member_check.py`, `mast_check.py`, `frame2d.py`, `frame3d.py` and
`foundation_check.py` is compared with an **independent** reference: a closed-form solution, a published worked example
or the standard's own tables. The tests are in `tests/test_steel_supports.py` (this skill) and `tests/test_tools.py`
(`TestFrame2D`, `TestMemberCheck`, `TestClass4AndFoundations`). Run `python3 -m unittest tests.test_steel_supports -v`.

Sources

- **[ESDEP]** ESDEP lecture notes, §5.2 "Basis of the ECCS buckling curves", *Table 1 Reduction factors* (χ for curves
  a–d, λ̄ = 0.2–3.0). Copy: <https://hobbielektronika.hu/forum/getfile.php?id=6912>.
- **[EC3]** EN 1993-1-1:2005+A1:2014: eq. (6.49), Table 6.1 (α), Table 5.2 (class limits), 5.3.2(11) eq. (5.9)/(5.10)
  (unique global and local imperfection), 6.2.9.1, Annex B.
- **[SN003b]** NCCI SN003b-EN-EU *Elastic critical moment for lateral torsional buckling*, eq. (3), eq. (4) and
  Table 3.1. <https://www.steelconstruction.info/images/0/0f/SN003b.pdf>.
- **[G&N]** Gardner & Nethercot, *Designers' Guide to EN 1993-1-1*, Thomas Telford 2005, Examples 6.6, 6.7, 6.8 and 6.10.
  The handbook values are quoted in the Autodesk Robot *Verification Manual Eurocodes*, Verification Examples 2–5
  (<https://help.autodesk.com/sfdcarticles/attachments/Verification_Manual_Eurocodes.pdf>).
- **[T&G]** Timoshenko & Gere, *Theory of Elastic Stability*, 2nd ed.: Euler columns, beam-column with a
  concentrated load (M = QL/4 · tan u/u), parabolic arches (γ factors).
- **[Mech]** Classical beam theory: PL³/3EI, TL/GJ, 5qL⁴/384EI, qL²/8. The plastic N–M interaction of an annulus is
  integrated from first principles (circular-cap area and first moment) inside the test.
- **[ESR]** ICC-ES ESR-2794 (Hubbell CHANCE, reissued May 2026) §4.1.5, eq. (3)–(5):
  <https://www.icc-es.org/wp-content/uploads/report-directory/ESR-2794.pdf>. **[SW]** Supportworks Model 150 helical
  anchor page (HA150: 6,500 ft-lb → Qu = Kt × T = 65.0 kips, Kt = 10 ft⁻¹):
  <https://commercial.supportworks.com/products/helical-anchors-tiebacks/model-150-helical-anchor-system.html>.
- **[EC7]** EN 1997-1: 2.4.7.2 eq. (2.4) (EQU), 6.5.3 eq. (6.3a) (sliding), Annex D (effective width B' = B − 2e).
- **[DE16]** AISC *Design Examples* V16.0, companion to the 16th ed. Steel Construction Manual (ANSI/AISC 360-22),
  free from AISC: <https://www.aisc.org/publications/steel-construction-manual-resources/16th-ed-steel-construction-manual/manual-companion-for-16th-edition>.
  The published final strengths were read from the tables that list each AISC example number with its value in the
  Dlubal verification documents VE 1030 (Ch. D), 1031 (Ch. E), 1032 (Ch. F), 1033 (Ch. G) and 1034 (Ch. H), e.g.
  <https://www.dlubal.com/en/downloads-and-information/examples-and-tutorials/verification-examples/001031>.
- **[DE15.1]** AISC Design Examples V15.1 (ANSI/AISC 360-16): intermediate values of E.10 (F_cr, A_e) and H.4 (ASD) as
  listed by ClearCalcs, *Steel Column Validation Examples* (<https://support.clearcalcs.com/article/164-steel-column-validation-examples>).
- **[DE14]** AISC Design Examples V14.0 (ANSI/AISC 360-10). Used only where the clause is unchanged in 360-16/360-22:
  F.1-2B C_b and L_p/L_r, E.2/E.3 F_e, and G.4 (value as reproduced in the SDC Verifier AISC 360-10 benchmark).

## member_check.py / mast_check.py

| tool | case | reference + source | expected | obtained | error | tolerance |
|---|---|---|---|---|---|---|
| member_check `chi` | curves a, b, c, d at λ̄ = 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0 (28 values) | [ESDEP] Table 1 | e.g. λ̄ = 1.0: 0.6656 / 0.5970 / 0.5399 / 0.4671 | 0.66564 / 0.59700 / 0.53993 / 0.46711 | ≤ 4.8·10⁻⁵ abs (table rounding) | 6·10⁻⁵ |
| member_check `chi` | curve a0 (α = 0.13) at λ̄ = 0.3, 0.5, 1.0, 2.0 | [EC3] eq. (6.49) + Table 6.1, evaluated independently | 0.985935, 0.951321, 0.725344, 0.232299 | same | < 10⁻⁶ | 2·10⁻⁶ |
| member_check M_cr | IPE 300, L = 6 m, uniform moment (C1 = 1) | [SN003b] eq. (3) with table Iz = 603.8 cm⁴, It = 20.12 cm⁴, Iw = 125.9·10³ cm⁶ | 90.47 kNm | 90.21 kNm | −0.29 % | 1 % |
| member_check C1 | ψ = 1, 0.5, 0, −0.5, −1 and interpolation | [SN003b] Table 3.1 | 1.00, 1.31, 1.77, 2.33, 2.55 | same | 0 | 10⁻⁶ |
| member_check M_cr, χ_LT | UB 762×267×173 S275, L = 5.10 m, C1 = 1.879 | [G&N] Ex. 6.8 | 4311 kNm; 0.82 | 4312 kNm; 0.822 | +0.03 %; +0.002 | 0.5 %; 0.006 |
| member_check class | CHS d/t vs 50ε², 70ε², 90ε² (8 sections × S235/S355/S460) | [EC3] Table 5.2 | class by hand | identical | 0 | exact |
| member_check, mast_check | CHS 244.5×10 S275, L = 4 m, N = 1630 kN | [G&N] Ex. 6.7 | N_c,Rd 2026.8 kN, λ̄ 0.56, N_b,Rd 1836.5 kN | 2025.9 kN, 0.555, 1835.9 kN | −0.04 %, −0.005, −0.03 % | 0.2 %, 0.006, 0.3 % |
| member_check 6.2.9.1 | UB 457×191×98 S235, N = 1400 kN | [G&N] Ex. 6.6 | M_pl,y,Rd 524.5, M_N,y,Rd 342.2 kNm | 524.7, 343.2 kNm | +0.03 %, +0.30 % | 0.3 %, 0.5 % |
| member_check Annex B | UC 305×305×240 S275, L = 4.2 m, N = 3440, My = 420, Mz = 110 | [G&N] Ex. 6.10 | (6.41) 0.33; (6.61) 0.66; (6.62) 0.97; kzy 0.79; kzz 0.78 | 0.341; 0.660; 0.972; 0.794; 0.784 | +0.011; 0.000; +0.002; +0.004; +0.004 | 0.015; 0.01 |
| member_check, mast_check CHS M_N | CHS 219.1×8 and 168.3×12.5, n = 0.2–0.9 | [Mech] exact plastic annulus | e.g. n = 0.9: 0.1579 / 0.1611 | cos(πn/2) = 0.1564 | −0.9 % / −2.9 % (safe side); n ≤ 0.5: ≤ 0.1 % | +0.3 % / −4 % |
| member_check 6.2.9.1 RHS | RHS 200×100×8 S355, N = 500 kN | [EC3] eq. (6.39) with EN 10210-2 table A = 44.8 cm², W_pl,y = 282 cm³ | M_N,y,Rd = 91.52 kNm | 91.43 kNm | −0.10 % | 2 % |
| member_check tension / class 3 | CHS 219.1×8 N = −300 kN; CHS 323.9×6.3 (class 3) N = 200, M = 30 | [EC3] 6.2.3 A·f_y; 6.2.1(7) linear with W_el, closed-form A and W_el | by hand | identical | < 10⁻⁹ | 10⁻⁶ |
| member_check, mast_check Cm | sway mode (k = 2) | [EC3] Annex B Table B.3 note | Cm = 0.9 | 0.9 | 0 | exact |
| mast_check | N_cr, χ for k = 1, 2 | [T&G] Euler + [EC3] eq. (6.49) by hand | — | identical | < 10⁻⁹ | 10⁻⁶ |
| mast_check vs frame2d vs frame3d | CHS 219.1×8, L = 10 m, pinned (k = 1) and cantilever (k = 2) | [T&G] π²EI/(kL)² | 613.42 / 153.355 kN | frame2d 613.42 / 153.355; frame3d 613.42 / 153.355 | < 3·10⁻⁶ | 0.2 % |

## member_check.py --code aisc (ANSI/AISC 360-16 / 360-22)

Test class `TestAISC360DesignExamples`. Inputs are converted from US units (1 in = 25.4 mm, 1 ksi = 6.894757 MPa,
1 kip = 4.448222 kN, 1 kip-ft = 1.355818 kNm). Sections are built from AISC nominal dimensions (W: d, b_f, t_w, t_f, r =
k_des − t_f; HSS and pipe: design wall thickness t_des, HSS outside corner radius 2t_des), so the errors include the
rounding of the section properties (the tool reproduces Manual A, I, Z, S, J, C_w to about 0.3 %). Values are LRFD
(φR_n) / ASD (R_n/Ω), in kips or kip-ft.

| example | case / path | reference | published | obtained | error | tolerance |
|---|---|---|---|---|---|---|
| D.1 | W8×21 A992, yielding D2(a) | [DE16] | 277 / 184 | 277.4 / 184.6 | +0.14 % / +0.30 % | 1 % |
| D.1 | rupture D2(b), A_n = 4.76 in², U = 0.908 | [DE16] | 211 / 141 | 210.7 / 140.5 | −0.14 % / −0.38 % | 1 % |
| D.5 | HSS6.000×0.500 (t_des 0.465), F_y = 50, yielding | [DE16] | 364 / 242 | 363.9 / 242.1 | −0.04 % / +0.04 % | 1 % |
| E.1C | W14×132, L_c = 30 ft, E3 | [DE16] (ASD from E.1A Manual Table 4-1a) | 892 / 594 | 893.0 / 594.2 | +0.12 % / +0.03 % | 1 % |
| E.1D | W14×90, L_cx = 30, L_cy = 15 ft (x-x governs) | [DE16] | 927 / 617 | 926.9 / 616.7 | −0.01 % / −0.05 % | 1 % |
| E.2 | built-up I, slender web, E7 effective width (c1 = 0.18, c2 = 1.31) | [DE16]; F_e [DE14] | 500 / 332; F_e 38.3 ksi | 498.1 / 331.4; 38.19 | −0.38 % / −0.18 %; −0.3 % | 1 %; 0.5 % |
| E.3 | built-up I, slender flanges (k_c = 0.743), E7 | [DE16]; F_e [DE14] | 318 / 211; F_e 65.9 ksi | 317.5 / 211.2; 66.0 | −0.16 % / +0.11 %; +0.2 % | 1 %; 0.5 % |
| E.9 | HSS12×10×3/8, L_c = 16 ft, non-slender | [DE16] | 556 / 370 | 553.9 / 368.5 | −0.38 % / −0.40 % (A 14.55 vs 14.6 in²) | 1 % |
| E.10 | HSS12×8×3/16, L_c = 24 ft, slender walls E7 (c1 = 0.20, c2 = 1.38) | [DE16]; [DE15.1] | 151 / 101; F_cr 29.1 ksi, A_e 5.77 in² | 151.3 / 100.6; 29.10, 5.776 | +0.18 % / −0.35 %; −0.01 %, +0.11 % | 1 %; 0.5 % |
| F.1-2B | C_b eq. (F1-1), middle / end thirds | [DE14] = [DE16] | 1.01 / 1.46 | 1.014 / 1.459 | +0.004 / −0.001 | 0.005 |
| F.1-3B | C_b, uniform load braced at midspan (Manual Table 3-1) | [DE16] | 1.30 | 1.299 (F1-1 on the parabola) | −0.001 | 0.005 |
| F.1-1B | W18×50, continuously braced, F2-1 | [DE16] | 379 / 252 | 378.0 / 251.5 | −0.28 % / −0.21 % | 1 % |
| F.1-2B | W18×50, L_b = 11.67 ft, C_b = 1.01, F2-2; L_p, L_r | [DE16]; [DE14] | 304 / 202; 5.83 / 16.9 ft | 305.2 / 203.1; 5.84 / 16.9 | +0.40 % / +0.53 % | 1 %; 0.5 % |
| F.1-3B | W18×50, L_b = 17.5 ft, C_b = 1.30, F2-3 | [DE16] | 289 / 192 | 288.3 / 191.8 | −0.25 % / −0.11 % | 1 % |
| F.6 | HSS3½×3½×1/8, F_y = 50 (flange just noncompact), F7 | [DE16] | 7.21 / 4.79 | 7.22 / 4.80 | +0.13 % / +0.28 % | 1 % |
| F.7B | HSS10×6×3/16, noncompact flange b/t = 31.5, F7-2 | [DE16] | 59.7 / 39.7 | 59.74 / 39.75 | +0.06 % / +0.12 % | 1 % |
| F.8A | HSS8×8×3/16, slender flange F7-3/F7-4 (Manual Table 3-13) | [DE16] | 46.3 | 46.27 | −0.06 % | 1 % |
| F.8B | same, hand calculation | [DE16] | 45.4 / 30.2 | 46.27 / 30.79 | +1.9 % / +1.9 % (see below) | 2.5 % |
| F.9B | Pipe 8 XS, t_des = 0.465 in, F_y = 35, compact, F8-1 | [DE16] | 81.4 / 54.1 | 81.36 / 54.13 | −0.04 % / +0.06 % | 1 % |
| G.1B | W24×62, G2.1(a) φ_v = 1.00, Ω_v = 1.50 | [DE16] | 306 / 204 | 306.2 / 204.2 | +0.08 % | 1 % |
| G.4 | HSS6×4×3/8 F_y = 46, G4 (A_w = 2ht, h = H − 3t) | [DE14] | 85.9 (LRFD) | 85.88 | −0.03 % | 1 % |
| G.5 | HSS16.000×0.375 (t_des 0.349), F_y = 50, G5 (F_cr = 0.6F_y governs) | [DE16] | 232 / 155 | 231.7 / 154.1 | −0.15 % / −0.56 % | 1 % |
| G.6 | W21×48, weak-axis shear G6 | [DE16] | 189 / 126 | 189.0 / 125.8 | +0.01 % / −0.19 % | 1 % |
| H.1A | W14×99, L = 14 ft: P_c, M_cx (F3 noncompact flange + F2 LTB), M_cy (F6), H1-1a | [DE16] | LRFD 1130, 642, 311, 0.928; ASD 750, 427, 207, 0.931 | 1129.2, 642.9, 311.4, 0.928; 751.3, 427.8, 207.2, 0.931 | ≤ 0.18 % | 0.5 % |
| H.4 | W10×33 ASD, App. 8 B1 (C_m = 1), C_b = 1.14, H1-1b | [DE15.1] | P_c 168, M_rx 61.2, M_ry 8.72, M_cx 91.0, M_cy 34.9, H1 0.982 | 168.2, 61.13, 8.755, 91.00, 34.99, 0.981 | ≤ 0.4 % | 0.5 % |
| transitions | E3-2/E3-3 at F_y/F_e = 2.25; E7-3 at the boundary for each Table E7.1 [c1, c2]; F2-3 at L_r = 0.7F_yS_x; F7-11 at L_r; G2-10/G2-11 | [AISC 360] continuity built into the equations | 1 | 1.000–1.002; F2: 0.9988 (rounded 1.95 and 6.76 in F2-6) | ≤ 0.2 % | 0.3 % |

Known differences (AISC route)

- **F.8B.** The hand calculation gives 45.4 kip-ft, Manual Table 3-13 (F.8A) gives 46.3 kip-ft for the same section. The tool's
  effective section modulus uses the neutral axis of the effective section (S_e = 12.34 in³) and reproduces the Manual
  table. The F.8B value corresponds to S_e ≈ 12.1 in³, about 2 % lower. That is close to what removing the ineffective
  width from both flanges gives (12.07 in³), so the hand calculation is probably simplified that way. The tool is 1.9 %
  less conservative than F.8B and matches F.8A.
- **E.1C ASD.** VE 1031 lists 598 kips, which does not match its own LRFD value (892/0.90/1.67 = 593.5). The test uses
  594 kips, the Manual Table 4-1a value quoted in E.1A for the same shape and length.
- **H.4 M_ry.** The example rounds B1 to 1.09 (8.72 kip-ft). The unrounded B1 = 1.094 gives 8.755 kip-ft (+0.4 %).
- **F.1-2B.** +0.4 % / +0.5 %: the V16.0 hand calculation rounds L_p and L_r to 5.83 and 16.9 ft. With the tool's
  section properties they are 5.84 and 16.90 ft.

Paths of the AISC route without a published example: E4 torsional buckling as the governing mode (computed in E.2, E.3,
E.1D but not governing), E7-7 (slender round HSS), F3-2/F6-3 (slender flanges), F7-5 (noncompact HSS web), F7.4 LTB of
rectangular HSS, F8-2/F8-3 (noncompact/slender round HSS), G2.1(b) C_v1 < 1 and G2.2 C_v2 < 1, H1.2 (tension + bending)
and the C_b from `--psi-LT`. The transitions test above checks their constants against the continuity the equations are
built on. It is not an independent example.

## frame3d.py (new) and frame2d.py

| tool | case | reference + source | expected | obtained | error | tolerance |
|---|---|---|---|---|---|---|
| frame3d | cantilever L = 4 m, P_y = 10, P_z = −20 kN | [Mech] PL³/3EI about both axes | 50.794 mm, −25.397 mm | same | < 10⁻⁸ | 10⁻⁴ |
| frame3d | same, torque T = 5 kNm | [Mech] TL/GJ | 8.2305·10⁻³ rad | same | < 10⁻⁸ | 10⁻⁴ |
| frame3d | Euler, pinned column CHS 219.1×8, L = 10 m (div 8) | [T&G] π²EI/L² | 613.42 kN | 613.44 kN | +3·10⁻⁵ | 5·10⁻⁴ |
| frame3d | Euler, cantilever | [T&G] π²EI/4L² | 153.355 kN | 153.355 kN | +2·10⁻⁶ | 5·10⁻⁴ |
| frame3d releases | fixed supports + pinned member ends, IPE 300, q = 10 kN/m, L = 6 m | [Mech] 5qL⁴/384EI, qL²/8, M_end = 0 | 9.612 mm, 45.0 kNm, 0 | same | < 10⁻⁶ | 10⁻⁴ |
| frame3d cables | guyed mast, two prestressed guys (T0 = 10 kN), P = 5 kN: both guys active | hand 2-DOF stiffness solution (in test) | δx 3.4722 mm, T 13.966 / 5.633 kN, N_mast −15.679 kN | same | < 10⁻⁸ | 10⁻⁵ |
| frame3d tension-only | same, P = 40 kN: leeward guy slack | hand solution, one guy; statics T = P/cosθ | δx 47.791 mm, T 66.667 kN, N_mast −53.333 kN | same; leeward guy 0 (slack) | < 10⁻⁸ | 10⁻⁵ |
| frame3d truss | two-bar truss, span 8 m, rise 3 m, P = 100 kN, EA = 2·10⁵ kN | statics N = −P/(2 sinθ); virtual work δ = PL/(2EA sin²θ) | −83.333 kN; 2.0833 mm | same | < 10⁻⁹ | 10⁻⁶ |
| frame3d `--imp sway` | cantilever mast h = 8 m | [EC3] 5.3.2(3) φ0 = 1/200 | 40 mm | 40 mm | 0 | exact |
| frame3d vs frame2d | parabolic arch L = 30, f = 6, CHS 323.9×10, q = 12 kN/m, pinned / fixed | frame2d (independent planar code, itself validated against [T&G] γ = 28.5, 45.4, 101) | α_cr 3.6341 / 8.1519; M 1.0712 / 4.7655 kNm | 3.6341 / 8.1519; 1.0712 / 4.7655 | < 10⁻⁷ | 10⁻⁴ |
| frame3d vs frame2d | same arch + 80 kN point load at node 6, second order | frame2d P-Δ | M = 263.679 kNm | 263.679 kNm | < 10⁻⁷ | 10⁻³ |
| frame3d second order | pinned column, N = 0.5 N_cr, lateral midspan Q | [T&G] M₂/M₁ = tan u/u, u = (π/2)√0.5 | 1.81683 | 1.81683 | < 10⁻⁶ | 0.5 % |
| frame3d imperfection | unique imperfection 5.3.2(11), pinned column at N = χN_Rk (CHS 219.1×8 L 7.5 m S355, L 15 m S275; IPE 300 L 5 m weak axis) | [EC3] eq. (5.9)/(5.10) ⇔ eq. (6.49): N/N_Rk + M_II/M_Rk = 1 | 1.000 | 0.997, 0.995, 0.995 | −0.3 % … −0.5 % | 0.8 % |
| frame3d import | membrane `reactions[].pull` on the mast head (map and xyz match, factor 1.5) | global equilibrium ΣR = −Σpull | (−6, 2, 3) kN, ×1.5 | same | < 10⁻⁶ | 10⁻⁵ |
| frame2d | Euler, beam, tan u/u, parabolic arches | [T&G], [Mech] (tests/test_tools.py `TestFrame2D`) | γ = 28.5, 45.4, 101 | within 1.5–2.5 % | | 4 % |

## foundation_check.py

| tool | case | reference + source | expected | obtained | error | tolerance |
|---|---|---|---|---|---|---|
| block | 2.5×2.5×1.5 m, V = 60, H = 45 kN at 0.3 m above the top, μ = 0.45 | [EC7] hand calculation: uplift 0.9W, sliding (0.9W − V)μ/1.1, M_dst = H(D + h_a) + V·B/2, M_stb = 0.9W·B/2, q = N/(B'L), B' = B − 2e | 202.5 kN; 58.30 kN; 156.0 / 253.1 kNm; 53.12 kPa (γ_G = 1.35, e = 0.332 m) | same | < 10⁻⁹ | 10⁻⁶ |
| block `--unfactored` | pull × γ_Q,dst | [EC7] Table A.1 γ_Q,dst = 1.5 | 60 / 45 kN | same | 0 | exact |
| helical | T = 6,500 ft-lb, square shaft | [SW] HA150 Qu = 65.0 kips; [ESR] Kt = 10 ft⁻¹ (32.8 m⁻¹), Q_all = 0.5 Q_ult | 65.0 kips; Q_all = Q_u/2 | 64.98 kips | −0.03 % (32.8 vs 32.81 m⁻¹) | 0.2 % |
| helical | Kt by shaft (RS3500) | [ESR] 7 ft⁻¹ (23 m⁻¹) | 230 kN at 10 kNm | 230 kN | 0 | exact |

## Known differences (not errors)

- **C1 for end moments.** The tool uses SN003b Table 3.1 (ψ = 0 → C1 = 1.77, calculated with κ_wt = 0, conservative).
  Gardner & Nethercot and the older ENV 1993-1-1 Annex F use 1.879 for ψ = 0, which is about 6 % higher. For IPE 300,
  L = 6 m, ψ = 0 the tool gives M_cr = 160 kNm (169 kNm with C1 = 1.88). Use `--C1` for a value from LTBeam.
- **G&N Ex. 6.10 M_cr.** Robot reports M_cr = 16 778 kNm, and the tool gives 14 441 kNm (C1 from ψ = −0.5).
  χ_LT is 0.98–0.99 either way, so the published interaction values are reproduced. The handbook does not tabulate this M_cr.
- **CHS plastic interaction.** The often-quoted M_N = M_pl(1 − n^1.7) is up to 5 % above the exact plastic
  capacity for n > 0.7. The tools now use cos(πn/2), the thin-tube exact curve.
