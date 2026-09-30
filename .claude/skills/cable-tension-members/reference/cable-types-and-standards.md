# Cable types, product data and standards

[V] = confirmed via search excerpt; [U] = recollection or typical, verify. EN 1993-1-11:2026 has replaced the
2006 edition in CEN (clause and table numbers below refer to 2006 + AC:2009).

## 1. EN 1993-1-11 groups [V]
| Group | Component | Examples |
|---|---|---|
| A | rods / bars | Macalloy 460/520/S460, Halfen Detan, Pfeifer PETS/UMIX, Anker Schroeder ASDO, Jakob, Carl Stahl |
| B | wire ropes | open spiral strand (OSS), full locked coil (FLC), strand ropes (6x36, 7x7, 7x19) |
| C | parallel wire / strand bundles | PWS, 7-wire strand stay systems (Freyssinet, VSL, BBR, DYWIDAG) |

## 2. Products
* **OSS (1x19, 1x37, 1x61, 1x91)**: galvanised/Galfan about 5–100+ mm, stainless 3–40 mm.
  Redaelli: wire 1570 MPa, Rp0.2 1180 MPa, E = 160 ± 10 [V]. Bridon-Bekaert grades 1570/1770/1960 [V].
* **FLC**: Z-wire outer layers, 20–180 mm [V], Z-wire 1370–1570 MPa [V]; best for saddles and clamps, stiff, dense.
  Pfeifer names: PV (FLC, Galfan), PG (OSS Galfan), PE (OSS stainless) [V].
* **Stainless 1x19 (316)**: Ronstan E = 127 kN/mm²; breaking load 6/8/10/12/16 mm = 29.7/52.8/82.6/119/211 kN,
  less about 10 % when swaged [V].
* **Galfan OSS (steelwirerope.com)**: 30 mm A = 545 mm², MBL 753 kN; 40 mm A = 929 mm², MBL 1198 kN [V].
* **FLC 40 mm**: MBL 1580 kN, "design load" 1053 = 1580/1.5, A = 1104 mm², 9.2 kg/m, EA = 177 MN [V].
* **Ronstan ACS2-GS Galfan OSS** (characteristic breaking load incl. about 10 % swage reduction) [V]:
  8.1→59, 10.1→93, 12.2→134, 14.1→181, 17.0→260, 20.1→367, 24.4→537, 28.3→722, 31.3→884, 36.3→1189 kN.
* **Pfeifer PG** Z_B,k = 28…1129 kN with Z_R,d = Z_B,k/1.5 [V] (diameter mapping [U]).
* **Macalloy 460**: fy 460, fu 610, 19 % elongation, 27 J at −20 °C, E 205, M10–M100. **Macalloy 520**: fy 520 / fu 660, ETA 21/0053 [V].

Minimum breaking force: `F_min = K·d²·R_r/1000` [kN] (EN 12385-2), `K = (π/4)·f·k_s` [V]. K ≈ 0.50–0.56 for
spiral strand, 0.33–0.36 for stranded rope [U]; spinning loss k_s 0.86–0.90 OSS, 0.88–0.92 FLC [U].

## 3. EN 1993-1-11 design
* **ULS** [V via EAD 200001-00-0602]: F_Ed ≤ F_Rd = F_uk/(1.5·γR); F_uk = F_min·k_e; γR ≥ 1.0.
  The 2006 text as recalled [U]: F_Rd = min{F_uk/(1.5γR); F_k/γR}. The F_k term matters for bars.
* **k_e (Table 6.3)**: metal and resin sockets 1.0 [V]; swaged 0.9 [V]; ferrules 0.9 [U]; U-bolt grips 0.8 [U];
  wedge anchorages, button heads, nuts on bars 1.0 [U]; cement-grout sockets listed [V], value [U].
* **SLS (Tables 7.1/7.2)**: UK NA adopts recommended values [V]; numbers not retrieved. Prestretch by cyclic
  loading up to 0.45 f_uk during execution [V excerpt]. Practice: ≈ 0.50 F_uk characteristic, ≈ 0.45 where fatigue governs [U].
* **Fatigue**: Δσ_c at 2×10⁶ cycles; spiral strand and FLC with sockets ≈ 150 MPa, parallel wire ≈ 160, threaded bars ≈ 50 [U];
  slopes m = 4–5 for ropes [U]. Bending at anchorages, saddles and clamps reduces life [V].
* **Saddles and clamps**: transverse pressure limits (FLC about 40 N/mm² [U]); friction μ ≈ 0.1 bare galvanised strand
  on steel, γM,fr ≈ 1.65 [U]; minimum radius as a multiple of d [U].
* **Moduli**: bars 210; spiral strand 150 ± 10 (code table, [U]; suppliers use 160 ± 10 [V]); FLC 160 ± 10; strand rope
  100 ± 10; parallel wires 205 ± 5; parallel strands 195 ± 5 [U].

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
* **Swaged fork/eye/stud**: d ≤ 26–36 mm, stainless 1x19, Galfan OSS up to about 36 mm; k_e 0.9 [V].
* **Adjusters**: turnbuckles, threaded fork studs, shim plates. Pfeifer adjustable sockets and rods: about 1.4 × thread
  diameter per system [V] (M36 ≈ 50 mm, M64 ≈ 90 mm). Typical specified ranges ±20–50 mm (small swaged) to ±50–150 mm (large) [U].
* **Pin/gusset**: pin Ø ≈ 1.0–1.4 d for OSS/FLC fork sockets; gusset ≈ 0.6–1.0 d, to suit the jaw [U]. Pfeifer UMIX data
  gives S355 plate thicknesses of about 5–25 mm by size [V]. Always use the supplier's table.
* **Rotation**: socket free to rotate in the gusset plane; out-of-plane needs a toggle, cardan or spherical bearing,
  otherwise bending fatigue concentrates at the socket exit.
* **Clamps**: cross clamps for nets at about 0.5–1.5 m mesh; edge clamps; saddle clamps. Slip resistance = μ × clamp force;
  re-tighten after stressing (diameter reduction under tension) [U].
* **Saddle radius**: OSS about 20–30 d, FLC about 20–40 d [U]; wire bending stress σ_b ≈ E·δ/(2R).

## 7. Corrosion protection
* Galvanised wire EN 10264-2, coating EN 10244-2 classes A (heaviest), AB, B [V]; class A about 250–300 g/m² for 3–5 mm wire [U].
* Galfan Zn95Al5 permitted [V]; about 2–3× the zinc life at equal mass (manufacturer claim) [U].
* Inner filling, sealed socket exits, optional paint or PE sheath.
* Stainless: 1.4401 (316) standard for ropes [V]; 1.4436/1.4404 also used; duplex 1.4462 for bars [U]. Choose by the
  EN 1993-1-4 corrosion resistance class (coast, swimming pools).
* Isolate dissimilar metals (stainless fittings on galvanised strand); detail drainage at sockets.
