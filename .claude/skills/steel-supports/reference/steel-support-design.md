# Steel support design guide for tensile structures

How the steel that carries membrane and cable forces is analysed and checked: masts, struts and booms, arches, rings,
edge beams, frames, bases and foundations. The guide covers EN 1993-1-1 and AISC 360 and points to the tools in `../scripts`.

**Tags.** **[V]** means confirmed from the named public source, with a URL or a quote. **[C]** means the content of the cited
standard clause (recommended value, so the National Annex may differ) or a classical closed form that a unit test
reproduces (see `validation.md`). **[U]** means an unverified practice value; a range is always given.
Confirm every [C] factor against the edition and National Annex in force. Never present a [U] value as a code requirement.
Code factors used by the tools live only in `tensile-structures/reference/code_factors.json`.

---

## 1. Load path and reaction transfer (membrane model ↔ steel model)

1. Where possible, model the membrane, cables and steel together, because steel flexibility changes the prestress.
   If you model them separately, include the steel stiffness in the membrane model as springs when the head
   moves more than about 1–2 % of the membrane span [U, range 1–2 %, practice].
2. Export reactions **per load combination** from the non-linear membrane run. The shared model JSON writes
   `reactions[].pull`, which is the force **from the membrane on the support** (`model-schema.md`). Never superpose
   non-linear results.
3. Apply the reactions to the steel model. `frame3d.py --reactions model.json` does this, matching each reaction by
   `--map` or by xyz. Envelopes are fine for member sizing. Use **concurrent** force sets (from the same combination)
   for connections, anchors and foundations.
4. If the head displacements are significant, feed them back to the membrane as support displacements and rerun.
5. Partial factors: apply the design combination in the membrane analysis (factored prestress and loads). Otherwise
   use `--reaction-factor` with care, because a membrane's response is not linear in the load.

## 2. Support types

| Element | Typical form | Behaviour | Main checks | Tool |
|---|---|---|---|---|
| Pinned mast | CHS, tapered "cigar" CHS, lattice | near-axial N, held by tie-backs; rotates with the membrane | buckling L_cr = L (pinned–pinned) or from α_cr (guyed); head eccentricity; erection | `member_check`, `mast_check`, `frame3d mast` |
| Fixed (cantilever) mast | larger CHS or box | flagpole | L_cr = 2L, sway Cm = 0.9 [C], base moment and foundation | `mast_check --k 2`, `frame3d` |
| Guyed mast | CHS + 3–4 guys | head held by the guys' axial and string stiffness | guy slackening, α_cr with the guy stiffness, mast as a beam-column on an elastic support | `frame3d` (tension-only cables + prestress) |
| Flying mast | strut hung in the cable net | compression without reaching the ground | stability comes only from cable tension; check load reversal and slackening; mechanism | `frame3d` |
| Tapered mast | CHS cone or cigar | stiffness varies along the length | no closed form: use the FE eigenvalue | `frame2d mast --D-base/--D-mid/--D-top` |
| Strut / boom / outrigger | CHS, RHS, truss | bending + axial; torsion if the cables are off-axis | N + M + T, LTB for I sections | `member_check`, `frame3d` |
| Arch | CHS, truss, bent tube | compression + bending; the membrane sits on or clamps to it | in-plane (antisymmetric) and out-of-plane buckling; asymmetric snow/wind | `frame2d arch`, `frame3d` |
| Compression ring | box, CHS | balances radial cable pulls (N = qR) | ring buckling, uneven pulls, joints | `frame3d` (dead loads only) |
| Tension ring / bale ring | CHS + plates | collects radial cables or a cone membrane | bending between hangers, joints, fatigue | `frame3d`, `member_check` |
| Edge beam / frame | CHS, RHS, I | rigid boundary with keder or clamp | line load n [kN/m], torsion from an eccentric clamp, deflection | `frame3d`, `member_check` |

## 3. Global analysis and second-order effects (EN 1993-1-1 §5.2)

- **α_cr ≥ 10** (elastic global analysis): first-order analysis may be used. For plastic analysis the limit is **15**
  [C, 5.2.1(3), eq. (5.1); register `steel.alpha_cr_min_elastic`]. `frame2d`/`frame3d` print α_cr and the verdict.
- For portal-type frames with shallow roof slopes and small axial force, α_cr may be estimated from the sway:
  α_cr = (H_Ed/V_Ed)(h/δ_H,Ed) [C, 5.2.1(4)B, eq. (5.2)]. **Not valid** for masts, arches or cable-held structures:
  use the eigenvalue instead.
- Sway effects may be allowed for by amplifying the horizontal loads by 1/(1 − 1/α_cr) when α_cr ≥ 3 [C, 5.2.2(5)B].
  Below 3, use a full second-order analysis (`frame3d` / `frame2d`).
- Methods [C, 5.2.2(3)]: (a) a global second-order analysis with all imperfections, followed by cross-section checks
  only; (b) a global second-order analysis with sway imperfections, followed by member checks with non-sway
  buckling lengths; (c) equivalent-column checks with L_cr from the global buckling mode. `frame3d --check` reports (a)
  with the unique imperfection and (c) with L_cr = π√(EI/(α_cr N_Ed)).
- Tension structures: cable prestress stiffens the steel through the string stiffness T/L. Slack cables remove that
  restraint, so analyse every combination, including prestress-only and wind uplift, with tension-only cables.
- **Snap-through and limit points.** Shallow arches, flat cable-held struts and flying masts can fail by a limit point
  below the bifurcation load. The tools here are P-Δ (linearised) only and do **not** capture snap-through. For these
  cases use a large-displacement FE analysis (SOFiSTiK, RFEM, ANSYS) with imperfections.

## 4. Imperfections (EN 1993-1-1 §5.3)

| Item | Value | Tag |
|---|---|---|
| global sway φ = φ0·αh·αm | φ0 = **1/200**; αh = 2/√h, 2/3 ≤ αh ≤ 1 (h in m); αm = √(0.5(1 + 1/m)) | [C, 5.3.2(3); register `steel.phi0`] |
| sway imperfection may be neglected | when H_Ed ≥ 0.15 V_Ed | [C, 5.3.2(4)B] |
| local bow e0/L, elastic analysis | a0 **1/350**, a **1/300**, b **1/250**, c **1/200**, d **1/150** | [C, Table 5.1; register `steel.e0_elastic`] |
| local bow e0/L, plastic analysis | a0 1/300, a 1/250, b 1/200, c 1/150, d 1/100 | [C, Table 5.1] |
| bow needed in the global analysis | if a member has at least one moment-resisting end and λ̄ > 0.5√(A f_y/N_Ed) | [C, 5.3.2(6)] |
| unique global + local imperfection | η_init = e0·N_cr/(EI·η''_cr,max)·η_cr, e0 = α(λ̄ − 0.2)(M_Rk/N_Rk)(1 − χλ̄²/γM1)/(1 − χλ̄²) | [C, 5.3.2(11), eq. (5.9)/(5.10)] |

`frame3d --imp unique` (the default) applies 5.3.2(11) at the most axially loaded cross-section. The test shows that it
reproduces the buckling-curve resistance to within 0.5 % (`validation.md`). `--imp sway` uses φ0·h with αh = αm = 1
(conservative), and `--imp mm:<a>` scales the mode to a given amplitude. `frame2d` uses e0·L from Table 5.1 along the mode.
For guyed masts, also consider the erection tolerances of the mast and the guy-length tolerances. Imperfection rules
specific to guyed masts were not verified here [U]: take at least the EN 1993-1-1 values above.

## 5. Member resistance (EN 1993-1-1 §6.2 and §6.3)

### 5.1 Cross-section classification (Table 5.2) [C]; ε = √(235/f_y); register `steel.class_limits`
| Part | class 1 | class 2 | class 3 |
|---|---|---|---|
| CHS d/t | 50ε² | 70ε² | 90ε² |
| internal part, compression c/t | 33ε | 38ε | 42ε |
| internal part, bending c/t | 72ε | 83ε | 124ε |
| outstand flange, compression c/t | 9ε | 10ε | 14ε |
| web under N + M (α > 0.5) | 396ε/(13α − 1) | 456ε/(13α − 1) | 42ε/(0.67 + 0.33ψ) |

Class 4: for I/RHS use effective widths to EN 1993-1-5 4.4 [C]: λ̄_p = (c/t)/(28.4ε√k_σ); internal part
ρ = (λ̄_p − 0.055(3 + ψ))/λ̄_p² ≤ 1; outstand ρ = (λ̄_p − 0.188)/λ̄_p² ≤ 1 (k_σ = 4 for an internal part in compression,
0.43 for an outstand, 23.9 for an internal part in pure bending). `member_check` implements this, ignoring the neutral-axis
shift. **Class 4 CHS** (d/t > 90ε²) needs shell buckling design to EN 1993-1-6 and is **not** designed by the tools.
In practice, choose d/t ≤ 90ε² for masts.

### 5.2 Section resistance [C]
- N_pl,Rd = A f_y/γM0, V_pl,Rd = A_v (f_y/√3)/γM0 (6.18). If V_Ed > 0.5 V_pl,Rd, reduce f_y in the shear area by
  ρ = (2V_Ed/V_pl,Rd − 1)² (6.2.8).
- N + M, class 1–2 (6.2.9.1): I/H sections M_N,y = M_pl,y(1 − n)/(1 − 0.5a) ≤ M_pl,y with a = (A − 2bt_f)/A ≤ 0.5. There is no
  reduction about y while N ≤ 0.25 N_pl and N ≤ 0.5 h_w t_w f_y/γM0. M_N,z = M_pl,z for n ≤ a, otherwise
  M_pl,z[1 − ((n − a)/(1 − a))²]. RHS: M_N,y = M_pl,y(1 − n)/(1 − 0.5a_w). Biaxial (6.41): (M_y/M_N,y)^α + (M_z/M_N,z)^β ≤ 1
  with α = 2, β = 5n ≥ 1 (I/H); α = β = 2 (CHS); α = β = 1.66/(1 − 1.13n²) ≤ 6 (RHS).
- CHS N + M: M_N = M_pl·cos(πn/2), the exact plastic curve of a thin tube. It is within 0.1 % of the exact annulus for
  n ≤ 0.5 and conservative above that [C, classical plastic theory, reproduced by test]. The frequently quoted
  M_pl(1 − n^1.7) is up to 5 % unconservative for n > 0.7 (validation.md).
- Class 3: linear elastic interaction with W_el (6.2.1(7)/6.2.9.2). Class 4: A_eff, W_eff (6.2.9.3), ignoring the
  e_N shift moment.

### 5.3 Flexural buckling (6.3.1) [C]
N_b,Rd = χ A f_y/γM1. Φ = 0.5[1 + α(λ̄ − 0.2) + λ̄²], χ = 1/(Φ + √(Φ² − λ̄²)) ≤ 1, λ̄ = √(A f_y/N_cr).
Imperfection factors α (Table 6.1, register `steel.imp_alpha`): a0 **0.13**, a **0.21**, b **0.34**, c **0.49**, d **0.76**.
The tabulated χ (ECCS/ESDEP) is reproduced to within 5·10⁻⁵ (validation.md).

| Section (Table 6.2) | curve y-y / z-z (S235–S420) | S460 |
|---|---|---|
| CHS/RHS hot-finished | a | a0 |
| CHS/RHS cold-formed | c | c |
| rolled I, h/b > 1.2, t_f ≤ 40 mm | a / b | a0 / a0 |
| rolled I, h/b ≤ 1.2, t_f ≤ 100 mm | b / c | a / a |
| welded I, t_f ≤ 40 mm | b / c | b / c |

Effective lengths: pinned–pinned 1.0L, flagpole 2.0L, fixed–pinned about 0.7L and fixed–fixed about 0.5L (ideal end
conditions) [C, Euler theory]. For guyed, tapered and flying masts and arches, take L_cr from the eigenvalue.

### 5.4 Lateral-torsional buckling (6.3.2, I sections) [C]
- M_cr = C1·π²EI_z/L²·√(I_w/I_z + L²GI_t/(π²EI_z)) for fork supports and loads at the shear centre (SN003b eq. (3));
  I_w = I_z(h − t_f)²/4 (SN003b eq. (4)); G = 81 000 N/mm² [C, 3.2.6].
- C1 for end moments, k = 1: ψ = +1: 1.00, +0.5: 1.31, 0: **1.77**, −0.5: 2.33, −1: 2.55
  [V, SN003b Table 3.1, <https://www.steelconstruction.info/images/0/0f/SN003b.pdf>, "values have been calculated with
  the assumption that κ = 0. This assumption leads to conservative values of C1"]. The older ENV value of 1.879 at
  ψ = 0 (used in Gardner & Nethercot Ex. 6.8) is about 6 % higher.
- Use the general case (6.3.2.2): curve a for rolled I with h/b ≤ 2 and b for h/b > 2; curve c for welded I with h/b ≤ 2 and
  d for h/b > 2 (Table 6.4).

### 5.5 Beam-columns (6.3.3, Annex B method 2) [C]
N/(χ_y N_Rk/γM1) + k_yy M_y/(χ_LT M_y,Rk/γM1) + k_yz M_z/(M_z,Rk/γM1) ≤ 1 (6.61), and likewise (6.62).
For class 1–2: k_yy = C_my[1 + (λ̄_y − 0.2)n_y] ≤ C_my(1 + 0.8n_y). For I sections, k_zz = C_mz[1 + (2λ̄_z − 0.6)n_z] ≤ C_mz(1 + 1.4n_z);
for hollow sections, k_zz is the same form as k_yy. k_yz = 0.6k_zz. For members prone to torsional deformation (Table B.2),
k_zy = 1 − 0.1λ̄_z n_z/(C_mLT − 0.25) ≥ …, and for λ̄_z < 0.4, k_zy = 0.6 + λ̄_z ≤ that value.
C_m = 0.6 + 0.4ψ ≥ **0.4** for a linear moment, and **0.9** for a sway buckling mode (Table B.3 and its note; register `steel.Cm_min`,
`steel.Cm_sway`). `member_check` sets sway automatically when k ≥ 2. Use `--Cmy` for transverse loading (Table B.3 rows 2–3).
Gardner & Nethercot Ex. 6.10 is reproduced to within 0.01 (validation.md).

## 6. Masts

- **Pinned base** is the default: near-axial load, no foundation moment, and the mast follows membrane movement. A pinned
  mast needs at least three non-coplanar tie-backs, or a membrane plus back-stays that keep it stable in every
  combination, including prestress only and uplift. With the anchors at base level, two guys in one plane give a mast
  pinned at the base **zero** out-of-plane stiffness: the string stiffness 2T/L_c cancels the mast's −N/H. Always add the third direction.
- **Head eccentricity.** If the cable lines do not meet on the mast axis, design for M = R·e (connection precedents
  and `tensile-connections`).
- **Guyed masts.** Model the guys as tension-only cables with their prestress (`frame3d`). Check that no guy goes slack
  in the design combinations, or that the structure stays stable if one does. Guy pretension in practice is about 5–15 %
  of the breaking strength [U, range 5–15 %; EN 1993-1-11 and EN 1993-3-1 govern guys, no value verified here].
  EN 1993-3 (towers, masts and chimneys) applies to "self-supporting towers and guyed masts", and states "(6) Provisions
  for the guys of guyed structures are given in EN 1993-1-11 and supplemented in this document" [V, scope of
  EN 1993-3 / EN 1993-3-1, <https://standards.iteh.ai/catalog/standards/cen/a64200b3-c62b-4993-8cbc-addb16ff38f4/en-1993-3-1-2006>].
  Global analysis of guyed masts is second-order and non-linear because of the guys [U: the clause was not verified here].
- **Flying masts.** Run the eigenvalue with the cables (`frame3d`). In every combination the cables must hold the strut in
  all directions. A slack cable can turn the system into a mechanism, which `frame3d` reports as a near-mechanism note.
- **Tapered masts.** Use `frame2d mast --D-base --D-mid --D-top` (piecewise-tapered CHS) for α_cr. Check the section at
  the point of maximum M/N, not only at mid-height.
- **Slenderness.** Above about L/i = 180 [U, range 150–200], check wind-induced vibration (vortex shedding, EN 1991-1-4
  Annex E) and erection handling (`mast_check` prints a note).
- **Base hinges.** Use a single pin and clevis (one axis), two orthogonal pins (cardan), or a spherical bearing. Design
  the pins to EN 1993-1-8 §3.13 (`tensile-connections/pin_connection.py`) and allow the analysed rotation plus erection.

## 7. Struts, booms and outriggers
Struts fixed to a building carry bending, axial force and, when the cables are off-axis, torsion. `frame3d` reports
the St Venant torque T. Torsion and warping stresses are **not** included in `member_check`. Prefer CHS and RHS
for torsion, and check the building connection for the concurrent force set.

## 8. Arches
- In-plane buckling is usually antisymmetric. For uniformly loaded parabolic arches q_cr = γEI/L³ with
  γ = 28.5 (two-hinged, f/L = 0.1), 45.4 (two-hinged, f/L = 0.2) and 101 (fixed, f/L = 0.2)
  [C, Timoshenko & Gere, reproduced by `frame2d` within 1.5–2.5 %; deep arches with f/L = 0.3 come out about 5–6 % above the energy values].
- Out-of-plane: the membrane gives no dependable restraint because it goes slack under suction. Use purlins, cables or
  bracing that stay in tension, and model them in `frame3d` (`--Lz` in `frame2d`).
- Asymmetric snow and wind govern bending. Run an eigenvalue and then a second-order analysis with the mode imperfection.
  EN 1993-2 Annex D gives bridge-arch buckling factors, which are useful as background [C, not reproduced here].
- Shallow arches can snap through (§3): use a large-displacement analysis.

## 9. Rings
- Compression ring under a uniform radial line load q: N = qR [C, statics].
- In-plane buckling of a ring under follower (hydrostatic) pressure: q_cr = **3EI/R³** [V, Abaqus Benchmarks
  "Buckling of a ring in a plane under external pressure", <https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-ringbuckling.htm>:
  "a critical pressure of 3EI/R³"]. Cable pulls on a ring act roughly as dead loads, not follower loads, and the same
  source warns that the load type changes the result by up to 50 % for thin rings (Boresi 1955). The tools apply
  **dead** loads only, so model the actual cable geometry in `frame3d`.
- Uneven cable pulls cause bending; model them explicitly. Tension rings: check the joints and the fatigue at the cable clamps.

## 10. Edge beams and frames
The membrane line load n [kN/m] comes from the membrane stress at the boundary. An eccentric keder or clamp adds
torsion n·e. Deflection limits used in practice (characteristic combination):

| Member | Limit | Tag |
|---|---|---|
| cantilevers | length/180 | [V, UK NA to BS EN 1993-1-1 via SDC Verifier help "Deflection": "Cantilevers — Length/180"] |
| beams carrying a brittle finish | span/360 | [V, same source] |
| other beams | span/200 | [V, same source] |
| edge beam with a membrane clamp | span/200–span/300 | [U, practice: the membrane must not wrinkle or unload] |
| mast head, horizontal | H/100–H/300 | [U, practice; feed the movement back to the membrane model if it exceeds 1–2 % of the span] |

## 11. Base fixity, base plates and anchors
- A pinned base gives the smallest foundation and allows rotation. A fixed base needs a moment base plate (EN 1993-1-8
  6.2.5–6.2.8, T-stubs, concrete bearing f_jd) and anchors to EN 1992-4 (`tensile-connections/steel_joint_checks.py`).
- Mast uplift is common, so check the anchor tension with prying.
- A sand pot or jacking base gives a temporary seat for introducing the prestress.

## 12. Foundations and ground anchors (`foundation_check.py`)
- **Gravity block / deadman.** Check uplift (EQU) with γ_G,stb = 0.9 on the weight, and overturning about the toe (EQU)
  [C, EN 1997-1 Table A.1]. Sliding: R = (γW − V)·tan δ/γ_R,h with γ_R,h = 1.1 [C, EN 1997-1 Table A.5, DA2]. The tool uses
  0.9W, which is conservative compared with γ_G,inf = 1.0. Bearing uses B' = B − 2e [C, EN 1997-1 Annex D] with
  γ_G = 1.35 or 1.0, whichever governs [C, Table A.3]. An eccentricity above B/3 needs special precautions [C, 6.5.4].
  Concrete unit weight 24 kN/m³ (plain) [C, EN 1991-1-1 Table A.1].
- **Helical anchors.** Q_ult = K_t·T, with K_t = **10 ft⁻¹ (32.8 m⁻¹)** for 1.5 in and 1.75 in square shafts (CHANCE SS5/SS175),
  9 ft⁻¹ (30 m⁻¹) for 2-7/8 in pipe (RS2875), 7 ft⁻¹ (23 m⁻¹) for RS3500 and 5.5 ft⁻¹ (18.0 m⁻¹) for RS4500. Q_all = 0.5 Q_ult,
  and F.S. is "not less than 2.0" (2.5 under the IRC without a geotechnical investigation). Q_ult is capped at 248.6 kN
  (SS5, tension) and 255.3 kN (SS175, tension)
  [V, ICC-ES ESR-2794 §4.1.5, <https://www.icc-es.org/wp-content/uploads/report-directory/ESR-2794.pdf>; register
  `geotech.helical_Kt_per_m`, `helical_Kt_by_shaft`, `helical_FS`]. T is the average of the last three readings for
  tension [V, same source]. K_t is product-specific: use the ESR of the actual product, and always proof-test.
- Grouted rock or soil anchors: proof-test them (EN 1997-1 / EN ISO 22477-5). Tension piles and micropiles take combined uplift and shear.
- Keep the anchor head on the cable line and use an articulated fork, so the bar is not bent.

## 13. Execution, welding and NDT
- Execution class selection: EN 1993-1-1:2005+A1:2014 Annex C (normative), which replaces EN 1090-2 Annex B. UK NA Table NA.4:
  RC1/CC1 and RC2/CC2 → **minimum EXC2** without fatigue design, **generally EXC3** with fatigue (Part 1-9);
  RC3/CC3 → **EXC3** (minimum EXC3 with fatigue). "EXC2 is the anticipated Class for most building structures".
  [V, SCI Advisory Desk AD 394 (NSC Feb 2016), <https://www.steelconstruction.info/images/7/70/AD-394.pdf>]. Use EXC3
  for fatigue-prone lugs and anchorages (wind flutter) and for CC3 stadium roofs.
- Supplementary NDT, EN 1090-2 Table 24: 100 % visual testing. For transverse butt and partial-penetration welds in tension
  (U ≥ 0.5): EXC2 10 %, EXC3 20 %, EXC4 100 % [C, EN 1090-2 Table 24 content; percentages for fillet welds: read the table].
- WPS/WPQR to EN ISO 15614; preheat to EN 1011-2 for thick S355.
- Membrane specifications usually ask for no site welding: use bolted or pinned site assembly [U, practice].

## 14. Corrosion and fire
- Corrosivity categories C1–C5 and CX [C, ISO 12944-2]. Hot-dip galvanising to EN ISO 1461. Minimum mean coating
  thickness for steel over 6 mm thick: 85 µm (local 70 µm) [C, EN ISO 1461 Table 3]. CHS and RHS need vent and drain holes for
  galvanising. Use a duplex system (galvanising plus paint) for C4/C5. Isolate aluminium clamp extrusions and stainless
  bolts from galvanised steel (bimetallic corrosion).
- Fire: open membrane canopies often have no fire-resistance requirement, but confirm with the authority. Where
  fire resistance is needed, the critical temperature is θ_cr = 39.19 ln[1/(0.9674 μ0^3.833) − 1] + 482 °C
  [C, EN 1993-1-2 eq. (4.22)], with μ0 the utilisation in fire. Cable sockets and PVC/PTFE membranes lose strength at much lower
  temperatures than steel.

## 15. AISC 360-16 / 360-22 (`member_check.py --code aisc`)
The values below are in the register section `aisc` (`code_factors.json`). [V] means the clause text or factor is printed
in a named AISC Design Example. [C] means the Specification clause content as in 360-16. The 360-22 Design Examples
V16.0 reproduce the clauses the tool uses, within 0.6 % (see `validation.md`). Still confirm the edition adopted by your
building code. The V16.0 examples take F_y = 50 ksi for round HSS (D.5, G.5), the same as rectangular HSS, so check the
ASTM A500 edition specified for the job.

| Topic | AISC 360-16 / 360-22 | Tag |
|---|---|---|
| Stability design | Ch. C direct analysis: second-order analysis, notional loads N_i = 0.002αY_i (α = 1.0 LRFD) (C2.2b), stiffness reduction 0.8τ_b·EI and 0.8·EA (C2.3); τ_b = 1.0 for αP_r/P_ns ≤ 0.5, otherwise 4(αP_r/P_ns)(1 − αP_r/P_ns); K = 1 for member checks. App. 8: B1 = C_m/(1 − αP_r/P_e1) ≥ 1, α = 1.0 LRFD / 1.6 ASD, C_m = 0.6 − 0.4M1/M2 (`--B1`, braced members only) | [C] |
| φ / Ω | tension yielding 0.90 / 1.67; rupture 0.75 / 2.00 (D.1); compression 0.90 / 1.67; flexure 0.90 / 1.67 (V14 Ch. F); shear 0.90 / 1.67; rolled I webs h/t_w ≤ 2.24√(E/F_y): 1.00 / 1.50 (G.1B) | [V] |
| E, G | 29 000 ksi (200 000 MPa), 11 200 ksi (77 200 MPa) | [C] |
| Tension (D2) | P_n = F_y A_g (yielding), F_u A_e with A_e = U·A_n (rupture, Table D3.1); L/r ≤ 300 user note | [C] |
| Slenderness, compression (B4.1a) | λ_r: rolled-I flange b/t = (b_f/2)/t_f 0.56√(E/F_y); built-up flange 0.64√(k_cE/F_y), k_c = 4/√(h/t_w) in 0.35–0.76; I web h/t_w 1.49√(E/F_y); rectangular HSS wall (B − 3t)/t 1.40√(E/F_y); round HSS D/t 0.11E/F_y | [C] |
| Slenderness, flexure (B4.1b) | [λ_p, λ_r]: rolled-I flange 0.38/1.0√(E/F_y); built-up flange λ_r 0.95√(k_cE/F_L); I web 3.76/5.70; HSS flange 1.12/1.40; HSS web 2.42/5.70; round HSS 0.07/0.31 E/F_y | [C] |
| Compression (E3, E4) | F_e = π²E/(L_c/r)²; F_cr = 0.658^(F_y/F_e)·F_y if F_y/F_e ≤ 2.25 (L_c/r ≤ 4.71√(E/F_y)), else 0.877F_e; torsional F_e = (π²EC_w/L_cz² + GJ)/(I_x + I_y) | [C] |
| Slender elements (E7) | P_n = F_cr A_e; b_e = b(1 − c1√(F_el/F_cr))√(F_el/F_cr) for λ > λ_r√(F_y/F_cr), F_el = (c2λ_r/λ)²F_y; c1/c2 = 0.18/1.31 stiffened, 0.20/1.38 HSS walls, 0.22/1.49 unstiffened; round HSS A_e = (0.038E/(F_y D/t) + 2/3)A_g | [C] |
| Flexure, I (F2, F3, F6) | M_p = F_yZ_x; L_p = 1.76r_y√(E/F_y); L_r per F2-6; inelastic F2-2 and elastic F2-3/F2-4 with C_b = 12.5M_max/(2.5M_max + 3M_A + 4M_B + 3M_C); FLB F3-1/F3-2; minor axis M_p = min(F_yZ_y, 1.6F_yS_y) and F6 FLB | [V] F2, C_b; [C] F3, F6 |
| Flexure, HSS (F7, F8) | FLB M_p − (M_p − F_yS)(3.57(b/t)√(F_y/E) − 4.0); slender F_yS_e with b_e = 1.92t√(E/F_y)(1 − 0.38/(b/t)·√(E/F_y)); WLB 0.305/0.738; LTB of rectangular HSS (F7.4) L_p = 0.13Er_y√(JA)/M_p, L_r = 2Er_y√(JA)/(0.7F_yS); round HSS (D/t < 0.45E/F_y) noncompact (0.021E/(D/t) + F_y)S, slender 0.33E/(D/t)·S | [C] |
| Shear (G) | V_n = 0.6F_yA_wC_v; I web A_w = d·t_w; C_v1 (G2.1(b), k_v = 5.34) or C_v2 (G2.2); rectangular HSS A_w = 2ht, h = H − 3t, k_v = 5 (G4); round HSS F_cr = max(1.60E/(√(L_v/D)(D/t)^1.25), 0.78E/(D/t)^1.5) ≤ 0.6F_y, V_n = F_crA_g/2 (G5); weak-axis I (G6, k_v = 1.2) | [C] |
| Combined (H1) | P_r/P_c ≥ 0.2: P_r/P_c + 8/9(M_rx/M_cx + M_ry/M_cy) ≤ 1.0 (H1-1a); otherwise P_r/(2P_c) + (M_rx/M_cx + M_ry/M_cy) ≤ 1.0 (H1-1b); H1.2 tension the same (the optional C_b increase is not used) | [V] |
| HSS torsion | H3 (torsional strength of round/rectangular HSS, combined H3-6): not in the tool, so check it by hand | [C] |

Not covered by the tool: F4/F5 (noncompact or slender webs), slender HSS webs, D/t ≥ 0.45E/F_y, tension-field action,
singly symmetric shapes, channels, tees, angles and H3 torsion. The tool flags these cases NOT OK and does not design them.
frame2d and frame3d `--check` remain Eurocode. Take their second-order forces into `member_check --code aisc`.

## 16. frame2d.py input schema (planar frames)
```jsonc
{"nodes": [[x, y], ...],                           // m, y vertical
 "supports": {"0": [1, 1, 0], "12": [1, 1, 1]},    // restrained ux, uy, rz (1 = fixed)
 "members": [{"name": "ARCH", "nodes": [0, 1, 2, ...], "section": "CHS:323.9x10", "fy": 355},
             {"name": "GUY", "nodes": [13, 12], "truss": true, "A": 3.0e-4, "fy": null}],  // A in m2
 "loads": {"nodal": {"6": [Fx, Fy, M]},             // kN, kNm (global)
           "udl": [{"member": "ARCH", "qy": -12.0, "per_horizontal": true}]}}   // kN/m
```
frame2d trusses carry compression too (no slackening): use frame3d for tension-only guys.

## 17. frame3d.py input schema (space frames, z vertical)
```jsonc
{"nodes": [[x, y, z], ...],                                  // m (or {"id":.., "xyz": [...]})
 "supports": {"0": "pinned" | "fixed" | [ux, uy, uz, rx, ry, rz]},   // 1 = restrained (global axes)
 "members": [
   {"name": "MAST", "nodes": [0, 1], "section": "CHS:219.1x8", "fy": 355, "div": 6,
    "release_start": "pinned" | "pinned_y" | "pinned_z" | "fixed", "release_end": "fixed",
    "ref": [1, 0, 0],                 // direction of local z (section depth); default global Z, or X for vertical members
    "Lcr_y": 8.0, "Lcr_z": 8.0, "Lb": 4.0},        // optional overrides for the member checks
   {"name": "B2", "nodes": [3, 4], "A": 5e-3, "Iy": 8e-5, "Iz": 2e-5, "J": 3e-5},    // explicit properties, m2/m4
   {"name": "TIE1", "nodes": [1, 2], "type": "cable", "EA": 30000, "prestress": 15},    // tension-only, kN
   {"name": "TIE2", "nodes": [1, 5], "type": "cable", "section": "CHS:...", "L0": 9.98}, // or unstressed length
   {"name": "STRUT", "nodes": [6, 7], "type": "truss", "EA": 2e5}],                     // two-way bar
 "loads": {"nodal": {"1": [Fx, Fy, Fz, Mx, My, Mz]},              // kN, kNm, design values
           "udl": [{"member": "MAST", "q": [qx, qy, qz]}]},          // kN/m, global
 "reactions": {"file": "sail.json", "map": {"0": 1}, "factor": 1.0, "tol": 0.05}}   // membrane pulls (optional)
```
The local axes are x along the member, z along `ref` (section depth: I_y bends about local y) and y = z × x. A "pinned" support
word restrains translations only. Restrain torsion somewhere, for example rz at a mast base (`[1,1,1,0,0,1]`),
otherwise `frame3d` reports a near-mechanism.
