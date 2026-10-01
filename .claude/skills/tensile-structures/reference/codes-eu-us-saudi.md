# Code systems: Eurocodes (EU), US codes and the Saudi Building Code (SA)

Select a code system with `--code EU|US|SA` on any tool that supports it, or for all tools with
`export TENSILE_CODE=US` (a project factor file may also carry `"_code": "SA"`). The default is EU.
Tags: **[V]** confirmed from a named source, **[C]** clause content known, not re-read, **[U]** unverified
(each U factor has a `range` in `code_factors.json` and the tools can run `--sensitivity` on it).

## 1. Which document governs what

| Component | EU | US | Saudi (SBC) |
|---|---|---|---|
| Loads and combinations | EN 1990 + EN 1991-1-3/1-4 (+ NA) | ASCE 7-22 (IBC 2024) | SBC 301 (2018: ASCE 7-10 based) |
| Membrane | CEN/TS 19102:2023, or stress factors (TensiNet/ASCE 55 practice) | ASCE 55 (β·L_t method; 55-10 values used) | SBC 201 §3102.1.1 → ASCE 55 |
| Membrane fire | EN 13501-1 classes | IBC 3102 / NFPA 701 | SBC 201 §3102.3.1: noncombustible or NFPA 701 Test 1/2 |
| Cables | EN 1993-1-11 (+ ETA, EAD 200001) | ASCE 19 (S_d ≥ 2.2·T) | not covered by SBC: ASCE 19 (via ASCE 55) or EN 1993-1-11 |
| Steel members | EN 1993-1-1 | AISC 360-22, LRFD or ASD | SBC 306 (2018: AISC 360-10 based, **LRFD only**) |
| Connections | EN 1993-1-8 | AISC 360-22 Ch. J, D5/J7 pins | SBC 306 (AISC based) |
| Anchors in concrete | EN 1992-4 | ACI 318-19 Ch. 17 | SBC 304 Ch. 17 (2018: ACI 318-14) |
| Foundations | EN 1997-1 (EQU/GEO) | IBC Ch. 18 + ASCE 7 combinations | SBC 303 (adds sabkha, collapsible, expansive soils) |

## 2. Load combinations used by `loads.py`

**EU, EN 1990 eq. 6.10 [C]:** 1.35G + 1.5S + 1.5·0.6W; 1.35G + 1.5W + 1.5·0.5S; 1.0G + 1.5W (uplift);
1.35G + 1.5Lr. The SLS check uses characteristic combinations. Prestress P is permanent with γP = 1.0.

**US, ASCE 7-22 §2.3.1 (LRFD) [V]:**
- 1.4D
- 1.2D + 1.6L + 0.3S
- 1.2D + (1.6Lr or 1.0S) + 0.5W
- 1.2D + 1.0W + L + (0.5Lr or 0.3S)
- 0.9D + 1.0W

Snow is now strength-level, so its factor is 1.0. Under ASCE 7-16 it was 1.6.

**US, §2.4.1 (ASD) [V]:**
- D
- D + 0.7S
- D + Lr
- D + 0.6W
- D + 0.75(0.6W) + 0.75(0.7S)
- 0.6D + 0.6W

**Saudi, SBC 301-18 §2.3.2 (from the Arabic text) [V]:**
- 1.4D
- 1.2D + 1.6(Lr or R) + 0.5W
- 1.2D + 1.0W + 0.5(Lr or R)
- 0.9D + 1.0W

Snow (Ch. 7) and ice (Ch. 10) are deleted. The Arabic text gives the live-load combination as
1.4D + 1.7L + 0.5(Lr or R), which may be a translation issue; L is rare on membrane roofs anyway. SBC 306
has no ASD format, so `loads.py combos --code SA --set asd` falls back to the ASCE 7 ASD forms for checks
that need service-level loads, such as the ASCE 55 membrane check [U].

**Membrane set (`--set membrane`):**
- EU: characteristic combinations P+G, P+G+S, P+G+W, plus their ψ0 combinations.
- US and SA: ASCE 55 at ASD-level loads: P+D (β 0.17), P+D+0.7S (0.27; US only), P+D+Lr (0.27),
  P+D+0.6W (0.33).
- The ASCE 55-10 β values were calibrated with service-level ASCE 7-98 wind. Using 0.6W with today's
  strength-level wind maps is therefore an inference [U]; ASCE 55-16 was not available to check.

## 3. Wind reference pressure (`loads.py wind`)

| | Formula | Constants |
|---|---|---|
| EU | q_p = [1 + 7·I_v]·½ρ·(c_r·c_o·v_b)², c_r = k_r·ln(z/z0), k_r = 0.19(z0/0.05)^0.07 | z0 / z_min by terrain 0–IV [C]; v_b from the NA map |
| US 7-22 | q_z = 0.613·K_z·K_zt·K_e·V² (N/m²); K_d goes in p = q·K_d·G·C_N | K_z = 2.41(z/z_g)^(2/α): B 7.5/1000 m, C 9.8/750 m, D 11.5/590 m [V] |
| US 7-16 | q_z = 0.613·K_z·K_zt·K_d·K_e·V² | K_z = 2.01(z/z_g)^(2/α): B 7/365.76, C 9.5/274.32, D 11.5/213.36 [V] |
| SA (SBC 301-18) | q_z = 0.613·K_z·K_zt·K_d·V² (ASCE 7-10 form, no K_e) | 7-10 constants (same as 7-16); V = ultimate 3-s gust at 10 m, exposure C |

Approximate KSA basic wind speeds, Risk Category II (700-year return period), **read by eye from the SBC
301-18 maps; use the official figure**:

| City | V (m/s) |
|---|---|
| Riyadh | ≈ 50 |
| Jeddah | ≈ 46–48 |
| Makkah | ≈ 48–50 |
| Madinah | ≈ 49–50 |
| Dammam | ≈ 46–48 |
| Abha | ≈ 50 |
| Tabuk | ≈ 48–50 |

Risk Category III–IV is about 2–4 m/s higher and Risk Category I about 2–4 m/s lower.

None of these codes give pressure coefficients for hypars, cones or saddles. Use wind-tunnel data, CFD,
or conservative canopy values.

## 4. Resistance factors

| | EU | US (AISC 360-22 [V]) | SA (SBC 306-18, AR text [U]) |
|---|---|---|---|
| Compression | γM1 = 1.0 [C] | φc = 0.90 / Ωc = 1.67 | **φc = 0.85** |
| Flexure | γM0 / γM1 = 1.0 | φb = 0.90 / 1.67 | 0.90 (as AISC) |
| Shear | γM0 = 1.0 | φv = 1.0 for rolled I webs, else 0.90 | **φv = 0.90 in all cases** |
| Bolts, welds | γM2 = 1.25 | φ = 0.75 / Ω = 2.00 | 0.75 |
| Concrete anchors | γMc = 1.5 | φ 0.70 breakout (cast-in, no supplementary reinforcement), 0.75 steel | same (ACI 318-14 base) |
| Membrane | γM·ΠA (CEN/TS 19102), or stress factor 4/5 | β·L_t (0.17–0.33 × 0.75) | ASCE 55 (as US) |
| Cables | F_uk/(1.5·γR), γR = 1.0 | S_d ≥ 2.2·T (ASCE 19) | ASCE 19 |

## 5. Saudi specifics and caveats

- **Edition.** The SBC 2024 edition has been mandatory since 1 July 2025. The values here come from the 2018 edition
  (official Arabic text, 2019 print). The English CR text governs over the Arabic. Confirm every SBC value
  against the edition in force before issue (`sbc.*` entries are tagged accordingly).
- **SBC 201 §3102:**
  - Applies to membrane structures erected for more than 180 days; shorter ones fall under SBC 801.
  - Design to ASCE 55.
  - The membrane must be noncombustible, or pass NFPA 701 Test Method 1 or 2.
  - The membrane must not be counted as lateral restraint for frame members (§3102.7.1).
  - §3102.7 still lists snow, inherited from the IBC, although SBC 301 deletes snow.
- **SBC 303:** sabkha, collapsible and expansive soils are common. The anchors and footings of tensile
  structures need the geotechnical report, which gives the bearing resistance and μ.
- **Temperature.** Steel and cable temperature ranges in KSA are large: up to 70–80 °C surface temperature
  on dark steel in summer. Use project-specific ranges for cable lengths and prestress loss; this is
  engineering practice, not an SBC value.
- **Sand and dust.** SBC 301-18 has no specific load for them. Consider abrasion of coatings and fabric, and
  dust accumulation on low-slope membranes, in the maintenance and design brief.
