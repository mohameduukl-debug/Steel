# Cable types, product data and standards

Tags: [V] = read in a named source (full standard text, datasheet or ETA; the register
`tensile-structures/reference/code_factors.json` holds the URL and quote); [C] = standard clause content whose
value an NA may change; [U] = typical value or recollection, verify. Clause and table numbers refer to
**EN 1993-1-11:2006 + AC:2009** (full text read: see `reference/validation.md`, verification log). EN 1993-1-11:2026
has replaced the 2006 edition in CEN; its numbering and some values (e.g. the FLC fatigue curve) differ — confirm
against the edition and National Annex in force.

## 1. EN 1993-1-11 groups [V: Table 1.1]
| Group | Component | Examples |
|---|---|---|
| A | rods / bars (tension rod systems, prestressing bars) | Macalloy 460/520/S460, Halfen Detan, Pfeifer PETS/UMIX, Anker Schroeder ASDO, Jakob, Carl Stahl |
| B | wire ropes | open spiral strand (OSS), full locked coil (FLC), strand ropes (6x36, 7x7, 7x19) |
| C | parallel wire / strand bundles | PWS, 7-wire strand stay systems (Freyssinet, VSL, BBR, DYWIDAG) |

## 2. Products (library: `reference/cable_products.json`, 112 entries with source URLs)
* **OSS (1x19, 1x37, 1x61, 1x91)**: galvanised/Galfan about 5–135 mm, stainless 3–80 mm [V: steelwirerope.com,
  Redaelli catalogues]. Redaelli: wire 1570 MPa, Rp0.2 1180 MPa, E = 160 ± 10 [V]. Bridon-Bekaert grades
  1570/1770/1960 [V].
* **Galfan OSS (steelwirerope.com datasheet)** [V]: 20 mm MBL 408 kN, A 244 mm², EA 39.0 MN, 2.0 kg/m;
  30 mm MBL 907 kN, A 548 mm², EA 87.7 MN; 40 mm MBL 1450 kN, A 929 mm², EA 149 MN. Swaged up to 36 mm
  (CBL = 0.9·MBL), spelter/resin sockets from 40 mm. E stated 160 ± 10 kN/mm². (The library's `OSS-Galfan-30/40`
  previously held the stainless table values — corrected.)
* **Stainless OSS (same supplier)** [V]: 30 mm MBL 753 kN, A 545 mm², E 130 ± 10; 40 mm 1198 kN, 929 mm².
* **Teufelberger-Redaelli Cable System catalogue (metric)** [V]: OSS 8–120 mm, FLC 16–156 mm, OSX/FLX stainless; gives
  F_uk (k_e = 1), F_Rd = (F_uk/1.5)/γR, A, EA, mass. E.g. OSS 40: F_uk 1520 kN, A 981 mm², EA 162 MN, 8.1 kg/m;
  FLC 40: F_uk 1615 kN, A 1077 mm², EA 178 MN, 9.0 kg/m. Stainless OSX F_Rd = F_uk/1.65, i.e. γR = 1.1.
* **FLC**: Z-wire outer layers, 16–180 mm [V], Z-wire 1370–1570 MPa [V]; best for saddles and clamps, stiff, dense.
  steelwirerope.com FLC 40: MBL 1580 kN, design load 1053 = 1580/1.5, A = 1104 mm², 9.2 kg/m, EA = 177 MN [V].
  Pfeifer VVS 1 (FLC, Galfan): average fill factor 0.811, spinning loss 0.919, E 160 ± 10, 16 mm F_min 272 kN
  (1770 grade), 1.49 kg/m [V]. Pfeifer names: PV (FLC, Galfan), PG (OSS Galfan), PE (OSS stainless) [V].
* **Stainless 1x19 (316)**: Carl Stahl I-SYS ETA-10/0358 Annex 2 [V]: A_m = 21.49 / 38.20 / 59.69 / 85.95 /
  116.99 mm² for 6 / 8 / 10 / 12 / 14 mm, k_s = 0.88, R_m = 1570, E_Q = 130 kN/mm², swaged k_e = 0.9 (6–10 mm),
  0.82 (12–14 mm), 0.78 (1x61, 22–26 mm), γM = 1.1 in its F_Rd. A_m·R_m·k_s reproduces Ronstan's breaking loads
  6/8/10/12/16 mm = 29.7/52.8/82.6/119/211 kN within 0.2 % [V]. Ronstan quotes E = 127 kN/mm² [V, earlier search].
* **Ronstan ACS2/ACS3-GS Galfan OSS** (characteristic breaking load incl. the typical 10 % swage reduction) [V:
  ronstantensilearch.com ACS3-GS page]: 8.1→59, 10.1→93, 12.2→134, 14.1→181, 17.0→260, 20.1→367, 24.4→537,
  28.3→722, 31.3→884, 36.3→1189 kN. Cable length between fittings ≥ 50d (1x19, 1x37) or 70d (1x61) [V]. Metallic
  areas are not published: the library uses EN eq. (2.2) [U].
* **Pfeifer PG** Z_B,k = 28…1129 kN with Z_R,d = Z_B,k/1.5 [V] (diameter mapping [U]).
* **Macalloy 460** (UK data sheet V4.9, Table 3) [V]: fy 460, fu 610 MPa, 19 % elongation, 27 J at −20 °C; M36
  (bar Ø34): min. yield load 364 kN, min. break load 483 kN, EC3 design resistance 348 kN (= 0.9·483/1.25), 7.3 kg/m;
  M64 (Ø59): 1204 / 1596 / 1149 kN. E 205 [U]. **Macalloy 520**: fy 520 / fu 690, ETA 21/0053 [V].

Metallic area and weight (EN 1993-1-11 2.3.1) [V]: A_m = f·π·d²/4 (eq. 2.2) with fill factor f (Table 2.2):
spiral strand 0.77 / 0.76 / 0.75 / 0.73 for 1 / 2 / 3–6 / > 6 wire layers around the core; full locked coil
0.81 / 0.84 / 0.88 for 1 / 2 / > 2 layers of Z-wires; circular wire strand ropes 0.56. Self weight g_k = w·A_m
(eq. 2.1) with w = 83 kN/m³ (spiral, FLC) or 93 kN/m³ (strand ropes) including corrosion protection. As A/d²:
spiral ≈ 0.57–0.60, FLC ≈ 0.64–0.69 (suppliers' FLC up to 0.70).

Minimum breaking force: `F_min = K·d²·R_r/1000` [kN] (EN 12385-2; EN 1993-1-11 eq. 6.5) [V], `K = (π/4)·f·k_s`.
Spinning loss k_s: 0.87–0.88 stainless OSS (Carl Stahl ETA) [V], 0.919 FLC (Pfeifer VVS 1) [V]; other
constructions [U] (about 0.86–0.90).

## 3. EN 1993-1-11 design
* **ULS (6.2)** [V]: F_Ed ≤ F_Rd = min{F_uk/(1.5·γR); F_k/γR} (eq. 6.2). F_uk = F_min·k_e (eq. 6.4) for group B;
  F_uk = A_m·f_uk (eq. 6.3) for bars and group C. Table 6.1 NOTE 2: the F_k check is not required where
  F_k ≥ F_uk/1.50 (e.g. FLC). Product ETAs/EAD 200001-00-0602 use the same format.
* **γR (Table 6.2, NDP)** [V]: 1.00, or 0.90 where measures at the anchorages reduce bending stresses (7.1(2)).
  ETAs (Fatzer ETA-15/0917, Pfeifer, Teufelberger-Redaelli ETA-18/1122) use 1.0, and DIBt does not permit values
  below 1.0 [V]. Stainless strand: Carl Stahl ETA-10/0358 γM = 1.1; Redaelli OSX F_Rd = F_uk/1.65 [V].
* **Group A (tension rods, 6.1)** [V]: designed to EN 1993-1-1 (carbon) or EN 1993-1-4 (stainless):
  N_t,Rd = min(A_g·f_y/γM0; k2·f_u·A_s/γM2), k2 = 0.9 (EN 1993-1-8 Table 3.4) [C] (`cable_calc.py rod`).
* **k_e (Table 6.3)** [V]: metal and resin sockets 1.0; ferrule-secured eye 0.9; swaged socket 0.9; U-bolt grip 0.8
  ("a reduction of preload is possible"). Product ETAs can be lower (Carl Stahl stainless swaged 0.78–0.9).
  Wedge anchorages, button heads and nuts on bars are not in the table: use the ETA.
* **SLS (7.2)** [V; NDP, NA may change]: Table 7.1 f_const = 0.60 σ_uk for the first tension components for only a
  few hours, 0.55 σ_uk after instalment of other tension components. Table 7.2 f_SLS = 0.50 σ_uk when the fatigue
  design includes bending stresses, 0.45 σ_uk without. Derivation (NOTEs 2–3): 0.66 σ_uk/(γR·γF) with
  1.0 × 1.10 / 1.0 × 1.20 for construction and 1.0 × 1.33 / 1.0 × 1.48 for service. NOTE 4: 0.45 σ_uk is the
  upper stress of the Annex A fatigue tests. The UK NA adopts the recommended values [V].
* **Moduli (Table 3.1, first estimates, E_Q for variable loads)** [V]: spiral strand 150 ± 10 (stainless 130 ± 10);
  FLC 160 ± 10; strand rope with steel core 100 ± 10 (stainless 90 ± 10), with fibre core 80 ± 10; bundle of
  parallel wires 205 ± 5; bundle of parallel strands 195 ± 5 kN/mm². Suppliers quote 160 ± 10 for Galfan spiral
  strand (steelwirerope.com, Redaelli) [V]. Use the secant modulus after ≥ 5 load cycles (3.2.2(2)) [V].
* **Fatigue (Section 9)** [V]: Table 9.1 detail categories at 2×10⁶ cycles (exposure classes 3 and 4): prestressing
  bars 105; FLC and spiral strand with metal or resin socketing 150; parallel wire strands with epoxy socketing,
  bundles of parallel strands or wires 160 N/mm². Figure 9.1: slope m = 4 down to Δσ_C at 2×10⁶, m = 6 beyond.
  Valid only with Annex A sockets, saddles/clamps to Section 6, vibration control and corrosion protection (9.2(2)).
  Threaded tension rods: EN 1993-1-9 Table 8.1 detail 14, category 50 on A_s with k_s = (30/φ)^0.25 for φ > 30 mm
  [V]. German practice for FLC bridge hangers uses Δσ_C = 112 N/mm² (BASt) [V, earlier search]; prEN 1993-1-11
  revises the FLC S-N curve (Steel Construction 2021, stco.202100009) [V]. Bending at anchorages, saddles and clamps
  reduces life [V].
* **Saddles (6.3)** [V]: radius r ≥ max(30d, 400⌀) (⌀ = wire diameter), or 20d with a soft-metal/zinc-spray bedding
  ≥ 1 mm over ≥ 60 % of the diameter; smaller radii for spiral ropes only where justified by tests. Then wire
  curvature stresses may be neglected (strength loss ≤ 3 %). Slip: F_Ed1/F_Ed2 ≤ e^(μα/γM,fr) (6.6); with clamps
  (F_Ed1 − k·F_r·μ/γM,fr)/F_Ed2 ≤ e^(μα/γM,fr) (6.7), k = 2.0 with full friction in grooves and clamp, else 1.0.
  Saddles designed for k·F_uk with k = 1.10 (6.3.4, NDP).
* **Transverse pressure (6.3.3)** [V]: q_Ed = F_r/(d′·L2) ≤ q_Rk/γM,bed, 0.6d ≤ d′ ≤ d, from the clamping force F_r
  only (the pressure from F_Ed is covered by the radius rule). Table 6.4 q_Rk without tests: FLC 40 N/mm² on steel,
  100 cushioned; spiral strand 25 and 60. γM,bed = 1.00 gives ≤ 3 % strength loss (NOTE 1) [C].
* **Clamps (6.4)** [V]: F_Ed,∥ ≤ (F_Ed,⊥ + F_r)·μ/γM,fr (6.9), γM,fr = 1.65 (NDP). **No value of μ** is given:
  determine it by a slip test. Literature: 0.15 (JTG/T D65-05), 0.2 (T/CECS 1010-2022, bare sealing cable),
  0.30–0.46 (cast-steel clamps, Ruan 2019) [V as quoted, not EN]. F_r is reduced by creep, diameter reduction
  under tension, bedding/ovalisation, external forces and temperature (6.3.2(3)); T/CECS 1010-2022 takes 25–55 %
  bolt-force loss [V as quoted]. Clamps connecting hangers are designed for 1.15·F_k of the clamped component (6.4.3).
  Bolt preload F_p,C = 0.7·f_ub·A_s (EN 1993-1-8 eq. 3.7) [V].
* **Cutting to length (3.4)** [V]: mark only at a prescribed cutting load; account for the measured elongation after
  cyclic loading, the difference between the design temperature (normally 10 °C) and the cutting temperature, long-term
  creep (0.15 mm/m without better data, 3.2.2(3)), elongation after clamp installation and first-loading set.
  Non-prestretched group B cables: prestretch by cyclic loading up to a maximum of 0.45 F_uk (3.2.2 NOTE 4).

## 4. ASCE/SEI 19
19-22 supersedes 19-16 [V]. S_d = S_n·N_f or S_n·N_d ≥ 2.2·T_n [V]. App. E seismic bracing: Ω = 2.2, T = 0.7E [V].
The 2.0 factor for transient loads (19-96 practice) and any LRFD φ in 19-22 are [U]. Prestress is a separate load in all
combinations; non-linear analysis; slack check; thermal and length-tolerance effects included [U].

## 5. Stay-cable documents
PTI DC45.1 (-12/-18): fatigue test 2×10⁶ cycles at upper stress 0.45 GUTS, ≤ 2 % wire breaks, then tensile ≥ 95 % GUTS [V];
φ ≈ 0.65, service ≈ 0.45–0.50 GUTS [U]. fib Bulletin 30 (2005), then 89 (2019) [V]. Cited for fatigue-critical stays.

## 6. Terminations and hardware
* **Poured sockets** (open/fork, closed/eye): zinc (EN 13411-4) or resin (Wirelock), k_e = 1.0 [V]. Resin is limited to about 115 °C [U].
  Factory proof-loaded and prestretched with the rope.
* **Cylindrical threaded sockets**: nut on a bearing plate; adjustment through the anchor plate.
* **Swaged fork/eye/stud**: d ≤ 26–36 mm, stainless 1x19, Galfan OSS up to 36 mm [V: steelwirerope.com swages
  6–36 mm to Z-14.7-431]; k_e 0.9 [V].
* **Adjusters**: turnbuckles, threaded fork studs, shim plates. Pfeifer adjustable sockets and rods: about 1.4 × thread
  diameter per system [V] (M36 ≈ 50 mm, M64 ≈ 90 mm). Macalloy forks M64–M120: ±25 mm per fork end [V: data sheet].
  Typical specified ranges ±20–50 mm (small swaged) to ±50–150 mm (large) [U].
* **Pin/gusset**: pin Ø ≈ 1.0–1.4 d for OSS/FLC fork sockets; gusset ≈ 0.6–1.0 d, to suit the jaw [U]. Pfeifer UMIX data
  gives S355 plate thicknesses of about 5–25 mm by size [V]. Always use the supplier's table.
* **Rotation**: socket free to rotate in the gusset plane; out-of-plane needs a toggle, cardan or spherical bearing,
  otherwise bending fatigue concentrates at the socket exit (γR = 0.90 only with such measures, Table 6.2).
* **Clamps**: cross clamps for nets at about 0.5–1.5 m mesh [U]; edge clamps; saddle clamps. Slip resistance per 6.4;
  re-tighten after stressing (diameter reduction under tension, 6.3.2(3)).
* **Saddle radius**: see §3 (30d / 400⌀ / 20d lined) [V]; wire bending stress σ_b ≈ E·δ/(2R) (Reuleaux, upper bound).

## 7. Corrosion protection
* Galvanised wire EN 10264-2, coating EN 10244-2 classes A (heaviest), AB, B [V]; class A about 250–300 g/m² for 3–5 mm wire [U].
* Galfan Zn95Al5 permitted [V]; about 2–3× the zinc life at equal mass (manufacturer claim) [U]; Ronstan states 3–6×
  slower erosion than galvanizing depending on environment [V, manufacturer claim].
* Inner filling, sealed socket exits, optional paint or PE sheath. Group C: two layers of corrosion protection (4) [V].
* Stainless: 1.4401 (316) standard for ropes [V]; 1.4436/1.4462 on request [V: steelwirerope.com]; duplex 1.4462 for
  bars [U]. Choose by the EN 1993-1-4 corrosion resistance class (coast, swimming pools).
* Isolate dissimilar metals (stainless fittings on galvanised strand); detail drainage at sockets.
