# Validation: tensile-connections

Every computational path of `pin_connection.py` (EN 1993-1-8 and AISC 360 D5/D6/J7), `corner_plate.py`, `steel_joint_checks.py` (weld, bolts, gusset,
clampbar, baseplate, anchor) and `fatigue_check.py` is reproduced against an independent reference: a published
worked example, the standard's own numbers, or a closed-form hand calculation. Tests: `tests/test_tensile_connections.py`
(class names in the last column). Errors are (obtained − expected)/expected. Most published values are rounded to
3 significant figures, which sets the tolerance.

## Sources
- **SBE5** — Steel Buildings in Europe, *Multi-storey steel buildings Part 5: Joint design* (ArcelorMittal/SCI 2009),
  https://www.steelconstruction.info/images/5/53/SBE_MS5.pdf (worked examples 2.4, 3.4, 6.5).
- **SBE4** — *Multi-storey steel buildings Part 4: Detailed design*, https://www.steelconstruction.info/images/0/01/SBE_MS4.pdf (example A.5).
- **P398** — SCI P398 *Joints in steel construction: moment-resisting joints to Eurocode 3* (2013), https://steelconstruction.info/images/5/5d/SCI_P398.pdf (Example C.1).
- **WALD** — F. Wald, *Bolts, welds, column base*, Eurocodes workshop JRC Brussels 2014,
  https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/06_Eurocodes_Steel_Workshop_WALD.pdf.
- **DOW** — B. Dowswell, *Design for gusset plate buckling with variable stress trajectories*, AISC Engineering Journal 2019 Q3,
  https://ej.aisc.org/index.php/engj/article/download/1153/1152 (design example).
- **H1–H4** — Hilti PROFIS Engineering calculation reports to EN 1992-4 published on ask.hilti.com:
  H1 https://files-ask.hilti.com/original/cf/cfip8ziqve.pdf (cast-in headed 5.8 M16, h_ef 120, C20/25 cracked),
  H2 https://files-ask.hilti.com/original/62/62zrajuzqr.pdf (narrow thin member, c1′),
  H3 https://files-ask.hilti.com/original/x0/x0w2kzspbz.pdf (lever arm), H4 https://files-ask.hilti.com/original/jh/jhtmzriaax.pdf (splitting).
- **EN1992-4** — EN 1992-4:2018 §7.2.2.5 extract hosted by Hilti, https://files-ask.hilti.com/original/29/29oep37chq.pdf.
- **EN1999** — EN 1999-1-1:2007+A1:2009 Table 8.5.
- **EN1993-1-9** — EN 1993-1-9:2005 §7.1, Table 3.1, Annex A.
- **IDEA-F** — IDEA StatiCa, *Fatigue analysis according to EN 1993-1-9*, https://www.ideastatica.com/support-center/fatigue-analysis-according-to-en-1993-1-9.
- **CONDE** — J. Conde, L. S. da Silva, T. Tankova, R. Simões, T. Abecasis, *Design of pin connections between steel
  members*, J. Constr. Steel Res. 201 (2023) 107752, open access https://oa.upm.es/85661/ (§3 counterexample; Tables 2–4,
  EC3-1-8 resistances of the two PERI prototypes from measured dimensions and strengths).
- **LBV** — Landesamt für Bauen und Verkehr Brandenburg, Bautechnisches Prüfamt, *Tipp 22/05: Bemessungswerte für
  Bolzenverbindungen nach DIN EN 1993-1-8*, https://lbv.brandenburg.de/sixcms/media.php/9/bautechnik_Tipp_22-05.pdf
  (charts of F_v,Rd, F_b,Rd/t and M_Rd per pin diameter, non-replaceable pins).
- **AISC-DE** — AISC *Design Examples* v15.1 (Companion to the Steel Construction Manual, Vol. 1),
  https://www.aisc.org/media/q5fcgxxu/v151_vol-1_design-examples.pdf, Example D.7 (pin-connected tension member) and D.8
  (eyebar). aisc.org refuses automated downloads, so the printed values were read from two university lecture notes that
  reproduce both examples line by line: https://uomustansiriyah.edu.iq/media/lectures/5/5_2021_03_15!03_29_38_PM.pdf (D.7)
  and https://uomustansiriyah.edu.iq/media/lectures/5/5_2021_03_15!03_30_02_PM.pdf (D.8, which also quotes AISC 360 D6.2).
- **P358** — SCI P358 *Joints in steel construction: Simple joints to Eurocode 3* (2011),
  https://www.steelconstruction.info/images/a/a9/SCI_P358.pdf: §7.5 Check 2 (CHS effective area), Example 4
  (column base, CHS 273), Table G.33 (CHS column bases, S275 plates), §6.8 + Example 5 (CHS end plate in tension, ring
  of bolts, rules after the CIDECT design guide). UK NA values: α_cc = 0.85, f_jd = β_j·α·f_cd with α = 1.5.
- **JOHNSON** — K. L. Johnson, *Contact Mechanics*, Cambridge University Press 1985, §4.2 (Hertz line contact,
  p₀ = (P′E*/πR)^½).

## Cases

| Tool | Case | Reference + source | Expected | Obtained | Error | Tolerance | Test |
|---|---|---|---|---|---|---|---|
| steel_joint_checks bolts | M20 8.8 shear per plane | SBE5 3.4, 0.6·800·245/1.25 | 94 kN | 94.08 | +0.1 % | 0.5 % | `TestBoltsSBE` |
| steel_joint_checks bolts | bearing fin plate, vertical (k1 = 2.12 from e2, p2; αb = 0.61 from e1, p1) | SBE5 3.4 | 89 kN | 88.3 | −0.8 % (ref. rounds k1, αb) | 1 % | `TestBoltsSBE` |
| steel_joint_checks bolts | bearing fin plate, horizontal (k1 = 2.5, αb = 0.66) | SBE5 3.4 | 114 kN | 113.4 | −0.6 % | 1 % | `TestBoltsSBE` |
| steel_joint_checks bolts | bearing beam web t = 9, no end distance, vertical / horizontal | SBE5 3.4 | 106 / 94 kN | 106.3 / 93.8 | +0.3 / −0.2 % | 1 % | `TestBoltsSBE` |
| steel_joint_checks bolts | 10-bolt group, z = 80: shear resistance (elastic method) | SBE5 3.4 | 584 kN | 584.1 | +0.0 % | 0.5 % | `TestBoltsSBE` |
| steel_joint_checks bolts | same group, bearing by components (fin plate / beam web) | SBE5 3.4 | 605 / 624 kN | 600.4 / 623.7 | −0.8 / −0.1 % | 1.5 % | `TestBoltsSBE` |
| steel_joint_checks bolts | tension M24 8.8, k2 = 0.9 | P398 C.1 sheet 5 | 203 kN | 203.3 | +0.2 % | 0.3 % | `TestBoltsSBE` |
| steel_joint_checks bolts | M20 5.6 double shear; inner bolt bearing t = 8, e2 = 35, p1 = 70 | WALD double-angle example | 117.6 / 93.4 kN | 117.6 / 93.4 | 0.0 % | 0.2 % | `TestBoltsSBE` |
| steel_joint_checks bolts | punching d_m = (s + e)/2, M24 e = 39.55 | EN 1993-1-8 T3.4 formula; e as P398 sheet 5 | 37.775 mm | 37.775 | 0 | exact | `TestBoltsSBE` |
| steel_joint_checks gusset | block tearing, eccentric (3.10): A_nt = 770, A_nv = 2210 | SBE5 3.4 §3.2.2.3 | 483 kN | 483.3 | +0.1 % | 0.2 % | `TestBlockTearingGusset` |
| steel_joint_checks gusset | block tearing (3.10), beam web 7.1 mm | WALD fin plate | 199 kN | 198.8 | −0.1 % | 0.3 % | `TestBlockTearingGusset` |
| steel_joint_checks gusset | block tearing (3.9) with γMu = 1.1 | WALD fin plate tying | 298 kN | 298.2 | +0.1 % | 0.2 % | `TestBlockTearingGusset` |
| steel_joint_checks gusset | Whitmore 30° yielding, Thornton K = 0.65 → KL/r = 21 < 25 | DOW example | 1 180 kips | 1 175 | −0.4 % | 0.5 % | `TestBlockTearingGusset` |
| steel_joint_checks gusset | width at 35.7°, AISC E3: Lc/r 47.2, Fe 128, Fcr 42.5 ksi, Pn | DOW example | 53.8 in / 42.5 ksi / 1 140 kips | 53.79 / 42.51 / 1 143 | 0.0 / 0.0 / +0.3 % | 0.5 % | `TestBlockTearingGusset` |
| steel_joint_checks gusset | AISC J4.3 block shear, n_r = 3 / 4 rows | TEH design example (AISC Eng. J. 2017 Q3, https://ej.aisc.org/index.php/engj/article/download/1117/1116) | 207 / 267 kips | 207.4 / 266.8 | +0.2 / −0.1 % | 0.3 % | `TestBlockTearingGusset` |
| steel_joint_checks gusset | EN 1993-1-1 χ, curve c, λ̄ = 0.787 | SBE4 A.5 | 0.671 | 0.6703 | −0.1 % (ref. rounds Φ) | 0.0015 | `TestBlockTearingGusset` |
| steel_joint_checks weld | simplified method F_w,Rd, S275 f_u 410, a = 5.6 | SBE5 6.5 | 1 248 N/mm | 1 247.6 | −0.0 % | 0.1 % | `TestWelds` |
| steel_joint_checks weld | directional method, full-strength double fillet a = 0.46 t (S235), 0.48 t (S275) | SBE5 §2.2.6 | util 1.00 | 1.003 / 1.001 | +0.3 / +0.1 % | 1 % | `TestWelds` |
| steel_joint_checks weld | transverse fillet σ⊥ = τ⊥, √(σ⊥² + 3τ⊥²) = 2σ⊥; moment on two weld lines W = 2L²/6 | WALD 'fillet weld in normal shear'; statics | closed form | equal | 0 | 1e-7 | `TestWelds` |
| steel_joint_checks baseplate | T-stub column flange: l_eff,cp 210, l_eff,nc 233, F_T,1 (method 2) 898, F_T,2 398, F_T,3 406 kN | P398 C.1 sheets 4–5 | as listed | 209.9 / 232.8 / 897.4 / 398.5 / 406.7 | ≤ 0.2 % | 0.2 % | `TestTStubBasePlate` |
| steel_joint_checks baseplate | T-stub end-plate extension: l_eff 191 / 125, F_T,1 901, F_T,2 377 kN | P398 C.1 sheets 6–7 | as listed | 191.0 / 125 / 900.2 / 377.3 | ≤ 0.1 % | 0.2 % | `TestTStubBasePlate` |
| steel_joint_checks baseplate | T-stub mode 1 method 2 with e_w (γMu 1.1) | SBE5 2.4 tying | 493 kN | 493.4 | +0.1 % | 0.2 % | `TestTStubBasePlate` |
| steel_joint_checks baseplate | compression HE 200 B, 340×340×18, C12/15, k_j = 2.5: f_jd, c, A_eff, N_Rd | WALD simple base plate | 13.3 MPa / 43.7 mm / 66 722 mm² / 887 kN | 13.33 / 43.63 / 66 714 / 889.5 | +0.3 / −0.2 / −0.0 / +0.3 % | 0.5 % | `TestTStubBasePlate` |
| steel_joint_checks baseplate | f_jd C30 k_j 1.5; c for t_p = 45, f_y 255 | SBE5 6.5 | 20 MPa / 93 mm | 20.0 / 92.8 | 0 / −0.2 % | 0.3 % | `TestTStubBasePlate` |
| steel_joint_checks baseplate | uplift: L_b = 8d + grout + t_p + washer + h_nut/2, L_b* = 8.8 m³A_s/(l_eff t³), mode 1-2 = 2M_pl/m | EN 1993-1-8:2005 Table 6.2 text | formula | equal | 0 | 1e-9 | `TestTStubBasePlate` |
| steel_joint_checks anchor | cone (asymmetric edges): N0 52.321 kN, A_c,N 257 050, ψs,N 0.950; pry-out V_Rd,cp 131.447 kN | H1 §4.3 | as listed | 52.32 / 257 050 / 0.95 / 131.45 | 0.0 % | 0.05 % | `TestAnchorsEN1992_4` |
| steel_joint_checks anchor | edge failure c1 150: α 0.089, β 0.064, V0 24.305, A_c,V 96 250, A0 101 250, ψs 0.967, ψh 1.134 | H1 §4.4 | V_Rd,c (EN, without Hilti grout factor 0.903) 16.88 kN | 16.88 | +0.0 % | 0.2 % | `TestAnchorsEN1992_4` |
| steel_joint_checks anchor | steel shear, k6 = 0.5 (f_uk 520), A = 201 mm² | H1 §4.1 | 52.276 kN | 52.28 | 0.0 % | 0.05 % | `TestAnchorsEN1992_4` |
| steel_joint_checks anchor | edge failure narrow thin member, c1′ = 400 (Eq. 7.50), A_c,V 390 000, ψh 1.414 | H2 §4.3 | V0 84.257 / V_Rd,c 43.029 kN | 84.25 / 43.03 | −0.0 % | 0.1 % | `TestAnchorsEN1992_4` |
| steel_joint_checks anchor | pry-out with k1 = 7.7 (ETA) | H2 §4.2 | 38.929 kN | 38.90 | −0.1 % (h_ef,ETA rounding) | 0.2 % | `TestAnchorsEN1992_4` |
| steel_joint_checks anchor | interaction concrete β^1.5, steel β² | H2 §5 (prints 90 % / 6 %, rounded up) | 0.89 < x ≤ 0.90; 0.05 < x ≤ 0.06 | 0.892 / 0.050 | — | band | `TestAnchorsEN1992_4` |
| steel_joint_checks anchor | steel with lever arm: l_a 34, M0 0.519 kNm, αM 2, γMs 1.25 | H3 §4.2 | 24.424 kN | 24.44 | +0.05 % | 0.2 % | `TestAnchorsEN1992_4` |
| steel_joint_checks anchor | splitting: A_c,N 180 000, ψs 0.85, ψec 0.990, ψh,sp 1.272 | H4 §3.4 | 89.274 kN | 89.26 | −0.02 % | 0.1 % | `TestAnchorsEN1992_4` |
| steel_joint_checks anchor | k9 1.7/2.4, A0 = 4.5c1², ψre,V 1.4, ψα,V(90°) = 2, ψec,V | EN1992-4 extract, Eq. 7.41–7.48 | as listed | equal | 0 | exact | `TestAnchorsEN1992_4` |
| steel_joint_checks clampbar | aluminium 6082-T6 bearing, Table 8.5 form, M10 t = 6 | EN1999 Table 8.5 (hand calc) | 28.65 kN | 28.65 | 0 | 0.01 kN | `TestAluminiumBearing` |
| fatigue_check | Δσ_D/Δσ_C = (2/5)^(1/3), Δσ_L/Δσ_D = (5/100)^(1/5), Δτ_L/Δτ_C = (2/100)^(1/5); knee at 5e6, cut-off at 1e8 | EN1993-1-9 §7.1 | 0.737 / 0.549 / 0.457 | register values | < 0.1 % | 0.1 % | `TestFatigue` |
| fatigue_check | Miner, Δσ_C 90, γMf 1.15: N_R 4 438 235 / 10 200 230 / ∞, D_σ | IDEA-F example | D_σ = 0.632 | 0.6317 | −0.05 % | 0.001 | `TestFatigue` |
| fatigue_check | shear Δτ_C 70: N_R 2 149 190 / 16 320 409 / ∞, D_τ | IDEA-F example | D_τ = 0.882 | 0.8818 | −0.03 % | 0.001 | `TestFatigue` |
| fatigue_check --cable | EN 1993-1-11 Fig. 9.1 bilinear curve (m1 4 to Δσ_C at 2e6, m2 6, no cut-off); `--single-slope` keeps m1 | closed form of Fig. 9.1 (register `fatigue_cables`, verified by the cable agent) | N(Δσ_C) = 2e6, N(Δσ_C/2) = 2e6·2⁶, N(2Δσ_C) = 2e6/2⁴ | equal | 0 | 1e-7 | `TestFatigue` |
| corner_plate | symmetric R = 2T cos(θ/2); general law of cosines and direction | closed-form statics | 173.2 / 70.77 kN | equal | 0 | 1e-7 | `TestCornerPlateStatics` |
| corner_plate | moment about the pin M = Σ(x F_y − y F_x), e = M/R; concurrent layout M = 0 | hand calculation | −500 kN·mm, −35.36 mm, 0 | equal | 0 | 1e-7 | `TestCornerPlateStatics` |
| corner_plate | 3D: plate normal, out-of-plane component, anchor tilt | vector hand calc (cross product) | n = z, −2 kN, R = √292, asin(2/√292) | equal | 0 | 1e-7 | `TestCornerPlateStatics` |
| pin_connection | counterexample S355 (f_u 510), d 16, a 8, b 12, c 5: F_v,Rd per plane, M_Rd = 1.5W_el f_yp/γM0, F at M_Ed = M_Rd with M_Ed = F(b + 4c + 2a)/8 | CONDE §3 | 49.2 kN / 214 kN·mm / 35.7 kN | 49.22 / 214.1 / util 1.0003 at 35.7 | +0.0 / +0.0 / +0.03 % | 0.2 % | `TestPinPublishedEN` |
| pin_connection | prototype P1 (pin 35.8, f_y 321.16, f_u 670.84; lugs 2 × 10.1, f_y 395.27; b 15, c 2), γ = 1: F_v,Rd (2 planes), F_b,Rd (2 lugs, f_y = min), F(M_Rd), F(M_Rd, F_v,Rd) | CONDE Table 4 | 808.1 / 347.9 / 399.9 / 358.4 kN | 810.3 / 348.4 / 401.9 / 360.0 | +0.27 / +0.14 / +0.50 / +0.45 % | 0.5–0.6 % | `TestPinPublishedEN` |
| pin_connection | prototype P2 (pin 19.8, f_y 457.06, f_u 777.65), γ = 1; γ code (γM2 1.25): F_v,Rd, F(M_Rd, F_v,Rd) | CONDE Table 4 | 286.8 / 237.4 / 96.4 / 91.4; 229.4 / 88.9 kN | 287.3 / 237.1 / 96.8 / 91.7; 229.9 / 89.2 | +0.17 / −0.13 / +0.41 / +0.32; +0.22 / +0.34 % | 0.5–0.6 % | `TestPinPublishedEN` |
| pin_connection | F_v,Rd d16/20/24 (f_up 490), d20/24 (360); F_b,Rd/t d24/20 (f_y 355), d24 (235); M_Rd d24/20 (f_yp 355), d24 (235) | LBV charts | 47.29 / 73.89 / 106.40 / 54.29 / 78.17 kN; 12.78 / 10.65 / 8.46 kN/mm; 0.723 / 0.418 / 0.478 kNm | equal to the printed 2–3 decimals | < 0.01 % | ±0.006 / ±0.0006 | `TestPinPublishedEN` |
| pin_connection | σ_h,Ed constant 0.591 = 1/√(π(1 − ν²)), ν = 0.3, from Hertz line contact with d·d₀ ≈ d²; cheek σ_h with F_ser/2; f_h,Rd = 2.5 min(f_y, f_yp)/γM6,ser | JOHNSON §4.2 (closed form) | 0.5914 | 0.591; equal | < 0.1 % | 0.1 % | `TestPinPublishedEN` |
| pin_connection | Table 3.9/3.10 example (F 250 kN, d 40, t 20): shear 483, bearing 426, M 1.81/6.03, a 44.9, c 31.3, F_b,ser 170.4, σ_h 624 | hand calculation per EN 1993-1-8 (`cable-steel-connections.md` §1.3) | as listed | as listed | < 0.1 % | 0.5 unit | `TestPinWorkedExample` |
| pin_connection --aisc | D.7 A36 plate t ½, w 4.25, d 1, d_h 1 1/32, a 2.25 in: b_eff = 1.61 in (edge governs over 2t + 0.63); LRFD φP_n rupture / shear / bearing / yielding; ASD P_n/Ω; bearing governs (24.3 > 20.8, 16.2 > 16.0) | AISC-DE D.7 | 70.0 / 71.8 / 24.3 / 68.9; 46.7 / 47.9 / 16.2 / 45.8 kips | 70.01 / 71.77 / 24.30 / 68.85; 46.67 / 47.85 / 16.20 / 45.81 | ≤ 0.1 % | 0.4 % | `TestPinPublishedAISC` |
| pin_connection --aisc | D.7 D5.2 a ≥ 1.33b_eff, w ≥ 2b_eff + d | AISC-DE D.7 | 2.14 / 4.22 in | 2.140 / 4.219 | 0.0 % | 0.2 % | `TestPinPublishedAISC` |
| pin_connection --aisc --eyebar-w | D.8 eyebar A36 t ⅝, w 3.00, b 2.23, d 3.00, R 8.00 in: A_g 1.875 in², P_n 67.5 kips → φP_n, P_n/Ω; D6.2 head diameter, d ≥ 7/8w, b ≥ 2/3w | AISC-DE D.8 | 60.75 / 40.42 kips; 7.49 / 2.625 / 2.00 in | 60.75 / 40.42; 7.491 / 2.625 / 2.000 | 0.0 % | 0.2 % | `TestPinPublishedAISC` |
| pin_connection | AISC D5.2 geometry b_eff 56 → a ≥ 74.5, w ≥ 152 mm | hand calculation per AISC 360 D5 | 74.5 / 152 mm | 74.48 / 152 | 0 | 0.01 | `TestPinWorkedExample` |
| steel_joint_checks baseplate --col CHS | Example 4: f_jd (C30, α_cc 0.85), N_Rd of CHS 273 (lightest, t 5.0) on 400×400×20 S275 (f_y 265) | P358 Ex. 4 sheet 1 / Table G.33 | 17 MPa / 1376 kN | 17.000 / 1376.6 | 0 / +0.04 % | 0.1 % | `TestCHSBasePlateP358` |
| steel_joint_checks baseplate --col CHS | Example 4, 273×10: A_req = 1400/17 → c = 45 mm → t_p,min = 20 mm; tool at t_p = 20: N_Rd ≥ 1400 | P358 Ex. 4 sheets 2–3 | c 45 / t_p,min 20 | 44.84 / 19.67 (→ 20) / N_Rd 1421 kN | −0.4 % (P358 rounds c) | rounding | `TestCHSBasePlateP358` |
| steel_joint_checks baseplate --col CHS | all 120 Table G.33 values for CHS 273 (plates 400–700, t_p 20–70, C16–C35): annulus, annulus cut by the plate edges (42 values), inner overlap → full disc (29 values) | P358 Table G.33 | 991 … 4 830 kN | max deviation 0.39 % | ≤ 0.39 % | 0.5 % (3 s.f.) | `TestCHSBasePlateP358` |
| steel_joint_checks baseplate --layout ring | Example 5 (CHS 273×6.3, 8 M24 8.8 on r2 = 190, e1 53.5, e2 50, t_p 20, f_y 265): r3, k1, f3, plate (Check 2), plate + bolts (Check 3), bolts (Check 4) | P358 Ex. 5 | 133.4 / 0.354 / 6.19 / 1030 / 1061 / 1624 kN | 133.35 / 0.354 / 6.193 / 1031.1 / 1063.3 (1061.6 with F_t,Rd = 203) / 1626.6 | 0 / 0 / 0 / +0.1 / +0.2 (0.0) / +0.2 % | 0.3 % | `TestCHSBasePlateP358` |
| steel_joint_checks disc_in_rect | exact area of a disc inside a rectangle (R ≤ h, R ≥ h√2, four and two circular segments) | closed-form geometry | πR², 4h², πR² − 4/2 segments | equal | 0 | 1e-6 | `TestCHSBasePlateP358` |

## Published values not reproduced (and why)
- CONDE Table 4, prototype P1/P2 "γ code" bearing (278.3 / 189.9 kN) = the γ = 1 value / 1.25: the paper divides the
  plate bearing by γM2 although its own Table 1 (Eq. 4) and EN 1993-1-8 Table 3.10 use γM0 = 1.0. The tool follows
  Table 3.10 (γM0) and is therefore checked against the γ = 1 bearing values only. Table 2 rounds the measured diameters
  to 0.1 mm: the residual +0.2 … +0.5 % on P1 disappears with d = 35.75 mm (back-calculated from the printed F_b,Rd),
  i.e. it is input rounding, not a model difference. P1's lever b + 4c + 2a = 43.2 mm is not printed; it follows from
  F(M_Rd) = 399.9 kN and matches Fig. 5 (lugs 10.1, middle plate 15, gap 2).
- CONDE P1 "γ code" F(M_Rd, F_v,Rd) = 340.8 kN: recombining its own 399.9 and 646.5 kN gives 340.1 kN (the tool: 341.6).
- AISC-DE D.7: the lecture copy checks w ≥ 2b_eff + d_h (4.25 in); AISC 360 D5.2 and the AISC example use the pin
  diameter d (4.22 in), as the tool does.
- P358 Example 4 sheet 1 compares the table value 1376 kN (lightest CHS 273) with N_Ed = 1400 kN and then proves the
  heavier 273×10 by the detailed checks; the tool gives 1376.6 kN for the lightest and 1421 kN for 273×10 with t_p = 20.
- P358 Example 5 Check 3 uses F_t,Rd rounded to 203 kN (1061 kN); the unrounded 203.3 kN gives 1063 kN (+0.2 %).
- SBE5 2.4 tying, T-stub Mode 2 printed as 793 kN: its own inputs give (2 × 6.05 + 30 × 1.925)/(59 + 30) = 785 kN.
  The tool returns 784.6 kN; the 793 is an arithmetic slip in the publication. Mode 1 (493 kN) is reproduced.
- WALD double-angle example, end bolt bearing printed as 87.3 kN with t = 8: 2.5 × 0.606 × 20 × 8 × 360/1.25 = 69.8 kN
  (87.3 corresponds to t = 10). The inner-bolt value 93.4 kN is reproduced.
- WALD rigid base-plate example: F_T,1-2 = 370 kN uses m = 60 mm in the last step although m = 53.2 mm after the weld
  deduction; not used as a reference. The T-stub path is validated with P398 instead.
- IDEA-F combined normal + shear: IDEA prints D_σ³ + D_τ⁵ = 0.786. EN 1993-1-9 Eq. (8.3) written with the Annex A.6
  damage-equivalent ranges reduces to D_σ + D_τ (= 1.51 for that spectrum); the tool keeps that (more conservative) form.
- H1 edge failure includes Hilti's own grout factor ψb,g = 0.903 (not part of EN 1992-4); the test removes it.

## Not validated / not covered
- EN 1993-1-8 replaceable-pin SLS resistances F_b,Rd,ser = 0.6tdf_y/γM6,ser and M_Rd,ser = 0.8W_el f_yp/γM6,ser: the formulas
  are as printed in CONDE Table 1 (Eqs. 5, 7), but no published numerical example was found; only the in-repo hand
  calculation and the Hertz derivation of σ_h,Ed check them. Pin clearance effects and the asymmetric (sliding) pin model
  proposed by CONDE for prEN 1993-1-8 are not implemented.
- Table 3.9 type B geometry (informative rows) has no published numerical check.
- CHS base plates with anchors at the plate corners or sides (`--layout corners|sides`): per-anchor T-stub with the
  EN 1993-1-8 Table 6.4 pattern l_eff = min(2πm, 4m + 1.25e) around the curved wall. No CHS-specific published example or
  yield-line solution was found; the T-stub resistances themselves are validated (P398, SBE5). Use `--layout ring` (P358
  Example 5) when the anchors are equally spaced on a circle around the tube.
- The P358 ring rules come from flange splices (prying against a counter-flange); for a base plate the prying reaction is
  on the grout and long anchors reduce it, so the rules are conservative there.
- P358 Table G.33 is checked in full only for CHS 273, where Example 4 fixes the wall thickness used by the table; the other
  diameters reproduce within 0.6 % with the wall thickness of the lightest section (3.2 mm for 139.7, 5.0–6.3 mm otherwise)
  fitted, not stated by P358, so they are not used as test cases.
- Blow-out (side-face) failure of headed anchors, anchor reinforcement, h′_ef for narrow members (warnings only).
- Free-edge buckling of gussets and plate FE stresses; the equivalent-column (Thornton) model is the only buckling check.
- The third AISC case of the TEH example (p = 3½ in., printed 280 kips) recomputes to 286 kips from its own areas; not used.
- Proprietary fittings (forks, sockets, turnbuckles): supplier data only.
