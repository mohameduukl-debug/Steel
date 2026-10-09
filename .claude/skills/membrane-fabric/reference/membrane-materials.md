# Membrane materials: data and behaviour

Tags:
* **[V]**: confirmed from the named source (manufacturer sheet read at the URL in `materials.json`, or [JRC23] =
  JRC132615 (2023) report).
* **[E]**: manufacturer value seen only as a search excerpt.
* **[U]**: industry typical or background knowledge, not verified.

All product data are for screening and benchmarking. For design, use the supplier's certified strength (5 % fractile)
and the biaxial data of the delivered batch. Machine-readable data, with `raw` value, unit, strength basis, status
and URL for every entry, are in `materials.json`.

Units: 1 kN/m = 1 N/mm = 50 N/5cm = 5 daN/5cm. N/3cm ÷ 30 = kN/m. lb/in × 0.17513 = kN/m.

## 1. PVC-coated polyester (PES/PVC)

Woven polyester base cloth (e.g. 1670 dtex P 2/2 for Valmex Type III [V]), coated both sides with plasticised PVC
plus a topcoat (acrylic < weldable PVDF < PVDF/acrylic < PVF film/Tedlar laminate). Welding is HF (RF, 27.12 MHz),
hot-air or hot-wedge. High-PVDF lacquers are ground off at the seam [U]; some are "weldable without grinding" (Valmex
MEHATOP F1 [V]). Foldable, so suitable for demountable and retractable roofs.

Proposed harmonised classification [V, JRC23 Eurocode Outlooks 5 and 6]:

| Type | Mean N/5cm (w/f) | Mean kN/m | 5 % fractile kN/m | Tear N (EN 1875-3) | Seam 23 °C / 70 °C |
|---|---|---|---|---|---|
| I | 2750/2750 | 55/55 | 50/50 | 170/170 | ≥ 90 % / ≥ 70 % |
| II | 4000/4000 | 80/80 | 70/70 | 280/280 | ≥ 90 % / ≥ 70 % |
| III | 5500/5000 | 110/100 | 100/90 | 450/450 | ≥ 90 % / ≥ 70 % |
| IV | 7500/6500 | 150/130 | 135/120 | 750/750 | ≥ 90 % / ≥ 60 % |
| V | 9250/8000 | 185/160 | 170/145 | 1100/1100 | ≥ 80 % / ≥ 55 % |

Weights by type from the French type table: I 750/900, II 1050, III 1050/1250, IV 1350/1850 g/m² ("order of
magnitude") [V, JRC23 Code Review 3]. Type V 1450–1600 g/m² [U]. The earlier teloniabiti.com table (66/60 … 200/190 kN/m)
has been replaced.

Product data [V unless marked]:

| Product | kN/m (w/f) | Tear N | g/m² | t mm | Roll cm | Fire | Note |
|---|---|---|---|---|---|---|---|
| Serge Ferrari Tenseo Advanced 1002 S2 | 84/80 (420/400 daN/5cm, mean ±5 %) | 550/500 | 1050 | 0.78 | 267 | B-s2,d0; NFPA 701 | Tv 8 % (NFP 38511) |
| Ferrari Flexlight Advanced 1302 S2 | 160/140 | 1200/1100 | 1350 | 1.02 | 267 | C-s2,d0 (as printed) | |
| Ferrari Flexlight Advanced 1502 S2 | 200/160 | 1600/1400 | 1500 | 1.14 | 180 | C-s2,d0 (as printed) | |
| Mehler VALMEX FR 1000 MEHATOP F1 (Type III) | 120/110 (6000/5500 N/50mm) | 900/800 | 1050 | – | 250 [E] | B-s2,d0; DIN 4102 B1 | PVDF both sides |
| Verseidag Duraskin B 4915 [E] | 115/102 | 950/800 | 1100 | – | 250 | DIN 4102 B1 | 100 % PVDF variant |
| Sattler 760 Atlas Type IV | 172/168 mean (8600/8400 N/5cm) | – | – | – | – | – | values from the [JRC25] example |

Heytex: no public architectural-membrane datasheet was found, so it is not in the library.

Other properties:
* Elongation at break 15–25 % (French type table) [V, JRC23 Code Review 3].
* Stretch under prestress 1–3 % (versus < 0.5 % for PTFE) [V].
* Japanese minimum requirements: elongation ≤ 35 %, mass ≥ 500 g/m² (synthetic base cloth) [V, MLIT666 第二 2].
* Fire B-s2,d0 / B-s1,d0 (EN 13501-1) [V]; NFPA 701 / ASTM E84 [V].
* Life 15–25 years with a PVDF/PVF topcoat [U].

## 2. PTFE-coated glass fibre

Woven E-glass (B-yarn, 3.30–4.05 µm filaments in the Japanese definition [V, MLIT666 第二 2]) with sintered PTFE
coating, often with an FEP top layer for sealing. Stiff, low creep, self-cleaning. It bleaches white under UV
(initially beige) [V].

Proposed classification, mean values [V, JRC23 Eurocode Outlooks 7 and 8]:

| Type | Mean kN/m (w/f) | Tear N | Seam 23 °C / 70 °C |
|---|---|---|---|
| I | 70/50 | 150/150 | ≥ 80 % / ≥ 60 % |
| II | 85/80 | 200/250 | ≥ 90 % / ≥ 70 % |
| III | 140/120 | 300/300 | ≥ 90 % / ≥ 70 % |
| IV | 160/140 | 400/400 | ≥ 90 % / ≥ 70 % |

5 % fractiles: "to be determined by experimental investigations".

Product data [V unless marked]:

| Product | kN/m (w/f) | Basis | Tear N | g/m² | t mm | Light % | Roll mm |
|---|---|---|---|---|---|---|---|
| Chukoh FGT-600 | 122.7/98.0 (3680/2940 N/3cm) | minimum | 225/225 | 1000 | 0.60 | 15 | – |
| Chukoh FGT-800 | 147.0/117.6 (4410/3528 N/3cm) | minimum | 294/294 | 1300 | 0.80 | 12 | 3800 [E] |
| Chukoh FGT-1000 | 183.3/166.7 (5500/5000 N/3cm) | minimum | 400/450 | 1700 | 1.00 | 10 | 3800 [E] |
| Saint-Gobain Sheerfill II | 144.5/105.1 (825/600 lb/in) | min. average | 334/311 | 1305 | 0.76 | 12 (solar) | – |
| Saint-Gobain Sheerfill V EverClean | 96.3/109.5 (550/625 lb/in) | min. average | 178/289 | 983 | 0.56 | 16 (solar) | – |
| Verseidag Duraskin B 18039 [E] | 84/80 | nominal | 300/300 | 800 | – | 17 | 3000 |
| Verseidag B18089 / Tenseo Xtrem GF 7000 [E] | 140/120 | nominal | – | 1150 (conflicting 1550) | – | – | 4700 |

Further notes:
* After a crease fold, Sheerfill II keeps 680/415 lb/in (82 %/69 %) [V]. Do not fold sharply: roll on large cores and
  pad the folds.
* Service temperature −60…+260 °C (Chukoh) [V]. Fire: A2-s1,d0; ASTM E136 non-combustible substrate [V]; Japanese
  non-combustible certification NM-8665 (Chukoh FGT) [V].
* Life 25–35+ years [V].
* Heat-sealed at about 350–385 °C with FEP film; seam efficiency 70–80 % [V], JRC classes ≥ 80–90 % [V].
* Water can temporarily reduce the strength by up to about 20 % [V-search].
* PTFE panels are often seamed at 1.5–2.5 m widths (narrower than the roll) to limit curvature error [V, Architen].

## 3. Silicone-coated glass

Proposed classification, mean values [V, JRC23 Eurocode Outlooks 9 and 10]:

| Type | kN/m (w/f) | Tear N |
|---|---|---|
| I− | 52/40 | 176/133 |
| I+ | 80/78 | 190/190 |
| III | 120/112 | 400/400 |
| III+ | 150/150 | 550/550 |
| V | 200/198 | 900/850 |

Seams are stitched or glued at 70 % at 23 °C and 70 °C.

Further notes:
* Light transmission 20–30 %, up to 40 % [V]. Euroclass A2 or B [V]. Life 20–30 years [V].
* Flexible from −50 °C to 200 °C; no toxic fumes; UV-A passes [V, JRC23 §2.2.3.4].
* No architectural product sheet with values was found (Sioen S2100 is a fire-protection fabric, 480 g/m²).

## 4. ETFE foil

| Property | Value | Source |
|---|---|---|
| Film thickness | 50–300 µm (100–250 common) | [U] |
| Thickness range, Nowoflon ET 6235 Z | 80–400 µm | [V] |
| Density | 1.75 g/cm³ (200 µm ≈ 350 g/m²) | [V, Nowoflon] |
| UTS | 50 MPa, strain at break 500 % (DIN EN ISO 527) | [V, Nowoflon ET 6235 Z] |
| Stress at 10 % strain | 23 MPa | [V, Nowoflon ET 6235 Z] |
| Modulus (0.05–1 %) | 1000 MPa | [V, Nowoflon ET 6235 Z] |
| Tear | 500 N/mm (DIN 53363) | [V, Nowoflon ET 6235 Z] |
| UTS (literature range) | 35–53 MPa | [V] |
| Yield (literature range) | 20–30 MPa | [V] |
| E below first yield | ≈ 660 MPa, ν ≈ 0.42 | [V] |
| Linear viscoelastic limit | about 1.5 MPa | [V] |
| Design f_y10,23 (no tests) | 21 MPa | [V, JRC23 Outlook 44] |
| 5 % fractile strength at 23 °C (Moritz) | 47 MPa base, 30 MPa weld | [V, JRC23] |
| Light transmission | > 91 % (EN 410, 200 µm) | [V, Nowoflon] |
| Light transmission (literature) | 88–95 % | [V] |
| Fire | B-s1,d0; DIN 4102 B1 | [V] |

Cushions have 2–5 layers at 200–400 Pa, raised to 600–800 Pa under snow or wind [U]. Design recommendations:
TensiNet Appendix A5 (2013) [V] and JRC23 §6.4 / §7.3. Nowoflon roll width 1550 mm [E].

## 5. ePTFE and fluoropolymer-coated PTFE fabric

Sefar Tenara 4T40HF [V]:
* 4000/4000 N/5cm = 80/80 kN/m (ASTM D4851); trapezoidal tear 798/752 N.
* 1080 g/m², 0.55 mm thick, 157.5 cm wide; 100 % fluoropolymer coating.
* EN 13501 B-s1,d0; ASTM E84 Class A; light transmission 38 % (ASTM D1003).
* Fully and repeatedly foldable, no plasticiser, UV-stable [V]. Suited to retractable roofs.

Proposed classification at 23 °C, 5 % fractile [V, JRC23 Eurocode Outlooks 11 and 12]:

| Type | kN/m (w/f) | g/m² | Tear N | Fire |
|---|---|---|---|---|
| 0 | 30/32 | 250 | 390 | B-s1,d0 |
| I | 48/52 | 340 | 700 | B-s1,d0 |
| II | 80/80 | 1100 | 1000 | B-s1,d0 |

At 50 °C the strength drops to 0.67–0.75 of the 23 °C value, and at 70 °C to about 0.6.

## 6. Mesh and shade cloth
* PVC-coated PES mesh: 5–50 % open area, reduced wind, not waterproof [U].
* PTFE/glass open mesh exists for façades [V].
* HDPE knitted shade cloth: 180–340 g/m², 50–95 % shade factor, 8–15 year life, sewn with PTFE thread, near-isotropic,
  high elongation [U].

## 7. Mechanical behaviour and constants

| Material | E_w·t kN/m | E_f·t kN/m | ν | G·t kN/m |
|---|---|---|---|---|
| PES/PVC 1000 g/m² (E_w 476, E_f 266 MPa × 0.84 mm) | ≈ 400 | ≈ 223 | 0.35 / 0.42 | – [V] |
| PES/PVC Type III, project example (direct form EAX 1000, EAY 800, EAP 400, G 40) | 800 (inverse) | 640 (inverse) | 0.4 / 0.5 | 40 [V, JRC25 slide 99] |
| PES/PVC (design practice) | 500–1200 | 300–900 | 0.2–0.6 | 10–50 [U] |
| glass/PTFE (design practice) | 1000–2000 | 600–1500 | 0.3–0.9 | 20–100 [U] |
| ETFE (isotropic) | 660–1000 MPa × t | same | 0.42 | E/(2(1+ν)) [V] |

Notes:
* French default Poisson's ratios when not measured: warp/weft 0.3, weft/warp 0.5 [V, JRC23 Code Review 2].
* PVC moduli rise to about 600/620 MPa after cyclic loading [V]. Fitted constants depend strongly on the test protocol
  and on which ratios are included (Gosling/Bridgens, COST TU1303) [V]. The MSAJ test runs from zero to 1/4 of the
  strength and tends to give stiffer values than project load ranges (formTL) [V, JRC23 Annex B4].
* Keep **direct** (Ed, crimp interchange) and **inverse** (E, ν) stiffness apart: `biaxial_fit.py` prints both
  (JRC23 eqs. 2.5–2.12).
* Choose the set that matches the governing load state (prestress 1:1, snow, wind). Use upper and lower bound sets to
  check sensitivity [V, JRC23].

## 8. Compensation (pattern shrinkage)
From biaxial tests at the design prestress (EN 17117-2:2021).
* Example: 1.2 % warp / 2.5 % weft [V, low-authority blog].
* Typical PES/PVC: 0.5–1.5 % warp, 1–3.5 % weft. Typical glass/PTFE: 0–0.5 % warp, 1–4 % weft (large weft crimp) [U].

Compensation is batch-specific: test the delivered rolls. Apply decompensation at boundaries of fixed length (clamp
lines, rigid frames, cable pockets with a fixed cable length).

## 9. Welded seams (see the design criteria for strength use)
* PVC HF: about 140 °C, 80–90 % efficiency, 40–60 mm wide [V]; 50–80 mm for Types IV–V [U]. German minimum: 40 mm for
  Type I, 80 mm for Type IV [V, JRC23].
* Research: a 27 mm weld reached 87.8/75.8 N/mm; a 70 mm multilayer patch reached 72 kN/m (≈ 0.7 of the substrate) [V].
* PTFE heat-seal: about 380 °C, 70–80 % efficiency, 50–75 mm wide (75–100 mm for high grades [U]); Japan requires
  ≥ 75 mm for the "wide joint" divisors [V].
