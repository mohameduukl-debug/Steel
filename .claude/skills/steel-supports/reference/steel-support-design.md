# Steel support design notes

## 1. EN 1993-1-1 formulas used by `mast_check.py` [C]
* ε = √(235/f_y). CHS class limits (Table 5.2): d/t ≤ 50ε² (1), 70ε² (2), 90ε² (3), otherwise class 4 (EN 1993-1-6).
* N_cr = π²EI/L_cr²;  λ̄ = √(A f_y / N_cr);  Φ = 0.5[1 + α(λ̄ − 0.2) + λ̄²];  χ = 1/(Φ + √(Φ² − λ̄²)) ≤ 1.
* Imperfection factor α: a0 0.13, a 0.21, b 0.34, c 0.49, d 0.76. CHS hot-finished: a (S235–S420), a0 for S460; cold-formed: c.
* N_b,Rd = χ A f_y / γ_M1 (γ_M1 = 1.0 recommended; check NA).
* CHS class 1–2 section interaction: M_N,Rd = M_pl,Rd (1 − n^1.7).
* Member (Annex B, no LTB for CHS): N/(χN_Rk/γM1) + k_yy·M/(M_Rk/γM1) ≤ 1,
  k_yy = C_my[1 + (λ̄ − 0.2)·n] ≤ C_my(1 + 0.8n) (class 1–2); C_my = 0.6 + 0.4ψ ≥ 0.4 (linear moment).
* Effective lengths: pinned-pinned 1.0 L; flagpole 2.0 L; guyed masts depend on guy stiffness (use elastic critical analysis).

## 2. AISC 360 equivalents
E3: F_e = π²E/(KL/r)²; F_cr = 0.658^(F_y/F_e)·F_y if KL/r ≤ 4.71√(E/F_y), else 0.877F_e; φ_c = 0.90.
H1 interaction: P_r/P_c ≥ 0.2 → P_r/P_c + 8/9(M_r/M_c) ≤ 1. CHS slenderness D/t ≤ 0.11E/F_y (compact).

## 3. Arches
* Typical in-plane buckling of two-hinged circular arches (textbook): N_cr ≈ (π²EI)/(β·S/2)² with β ≈ 1.0–1.2 for
  antisymmetric mode (S = arch length) [textbook, verify with FE].
* Out-of-plane: restrained by purlins or cables only where these stay in tension. The membrane gives no dependable
  restraint under suction.
* Asymmetric snow/wind govern bending. Run an FE eigenvalue and an imperfect non-linear analysis (EN 1993-2 Annex D gives arch
  buckling guidance for bridges, useful as background).

## 4. Rings
* Compression ring under uniform radial load q: N = q·R; the in-plane buckling load of a ring under hydrostatic load is
  q_cr = 3EI/R³ (textbook). Uneven cable pulls cause bending; model explicitly.
* Tension (inner) rings (spoked wheel): check joints and fatigue at cable clamps.

## 5. Base details
* **Hinge types**: single pin + clevis (one axis), two orthogonal pins (cardan), spherical bearing or ball-and-socket.
  Design pins to EN 1993-1-8 §3.13 (`pin_connection.py`). Allow the rotation range expected from the analysis (+ erection).
* **Base plate + anchor bolts** for fixed masts: EN 1993-1-8 §6.2.5–6.2.8 (T-stub, concrete bearing f_jd), anchor
  design to EN 1992-4. Mast uplift is common, so check anchor tension plus prying.
* **Sand pot / jacking base**: temporary jacking seat for prestress introduction.

## 6. Ground anchors for tie-backs
| Type | Notes |
|---|---|
| Helical (screw) anchors | Square-shaft guy anchors up to ~890 kN ultimate; HA150 ≈ 133 kN, HA175 ≈ 222 kN allowable [V, Hubbell]; capacity from installation torque; proof-test |
| Grouted rock / soil anchors | 25–40 mm threaded bar, proof-tested (EN 1997-1 / EN ISO 22477-5) |
| Deadman / gravity block | uplift, sliding, bearing; concrete mass |
| Tension piles / micropiles | combined uplift + shear |
Keep the anchor on the cable line; use an articulated fork head so the bar is not bent.

## 7. Reaction transfer workflow (membrane model ↔ steel model)
1. Model membrane + cables + steel together where possible (steel stiffness affects prestress).
2. Otherwise export reactions (per combination, concurrent sets) from the membrane model: node, Fx, Fy, Fz.
   `form_find_fdm.py` / `dynamic_relaxation.py` write them as `reactions[].pull`.
3. Apply to the steel model (RFEM, SOFiSTiK, Robot, Tekla, SAP2000 …) as nodal loads; run EN 1993 / AISC checks.
4. If head displacements are significant, feed them back as support displacements and re-run the membrane.
5. Use envelopes for members and concurrent sets for connections, anchors and foundations.

## 8. Execution class and NDT (EN 1090-2 / EN 1993-1-1 Annex C) [V]
CC1/CC2 → EXC2 minimum; CC2 with fatigue (SC2) → EXC3; CC3 → EXC3. UK NA: EXC2 default for buildings.
NDT Table 24: 100 % VT; transverse butt and partial-penetration welds in tension (U ≥ 0.5) EXC2 10 %, EXC3 20 %, EXC4 100 %;
fillet percentages: read Table 24 [U]. WPS/WPQR to EN ISO 15614; preheat per EN 1011-2 for thick S355.
No field welding: bolted or pinned site assembly (typical membrane specifications) [V].

## 9. frame2d.py input schema (planar frames)
```jsonc
{"nodes": [[x, y], ...],                           // m, y vertical
 "supports": {"0": [1, 1, 0], "12": [1, 1, 1]},    // restrained ux, uy, rz (1 = fixed)
 "members": [{"name": "ARCH", "nodes": [0, 1, 2, ...], "section": "CHS:323.9x10", "fy": 355},
             {"name": "GUY", "nodes": [13, 12], "truss": true, "A": 3.0e-4, "fy": null}],  // A in m2
 "loads": {"nodal": {"6": [Fx, Fy, M]},             // kN, kNm (global)
           "udl": [{"member": "ARCH", "qy": -12.0, "per_horizontal": true}]}}   // kN/m
```
Design forces must be factored (ULS combination). Run each combination separately (non-linear).
