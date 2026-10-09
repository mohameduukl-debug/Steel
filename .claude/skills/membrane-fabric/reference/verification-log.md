# Verification log: register factors and material data (membrane section)

This log records what was searched, what was found (URL and quoted text), and what was changed in
`tensile-structures/reference/code_factors.json` (section `membrane`) and `reference/materials.json`. The search was
run in October 2026 with web search, direct PDF downloads and pdftotext. Paywalled hosts (ScienceDirect, SAGE,
Springer, ResearchGate, UPCommons, ArchiExpo PDF pages) returned 403 and could not be read.

## Factors upgraded U → V

| Key | Old | New | Evidence (URL + quote) |
|---|---|---|---|
| `japan_long_divisor` 8 | U (secondary ETFE paper) | **V** | MLIT Notification 666, 第六 一, https://www.mlit.go.jp/notice/noticedata/pdf/201703/00006526.pdf: "膜材料の引張りの許容応力度は…次の表の数値によらなければならない" with the row "接合部のない場合又は接合幅若しくは溶着幅が四十ミリメートル（…七十五ミリメートル）以上の場合 … Fm／80t (long-term) … Fm／40t (short-term, 折りたたみを行わない場合)". Fm is in N/cm and t in mm, so n_allow = σ·t = Fm/80 N/mm = (Fm/10 kN/m)/8. |
| `japan_short_divisor` 4 | U | **V** | same table: "Fm／40t" (not folded) |
| new `japan_short_divisor_folded` 5 | – | V | same table: "折りたたみを行う場合 … Fm／50t" |
| new `japan_long_divisor_narrow` 10, `japan_short_divisor_narrow` 5 | – | V | same table, row (二) "（一）項に掲げる場合以外の場合 Fm／100t, Fm／50t" |
| new `japan_anchorage_long/short` 6 / 3 | – | V | 第六 二: "Fj／6 … Fj／3" (Fj = tensile strength of the actual anchorage from a test) |
| `etfe_gamma` 1.1 | U (one paper line) | **V** | JRC132615 (2023) Eurocode Outlook No. 44: "The recommended value for foil structures is γM= 1.1"; Moritz concept Table 6-7 "γm, ULS … 1.1". https://publications.jrc.ec.europa.eu/repository/bitstream/JRC132615/JRC132615_01.pdf |
| new `etfe_k` | – | V | same Outlook 44: "kage = 1.05", "klong = 1.2", "kperm = 1.8", "kperm = 3.5" (single layer, no regulation), "ktemp0 = 0.7", "ktemp50 = 1.2", "ktemp70 = 1.7", "fy10%,23 = 21 N/mm²"; "fPM,d = 21 / (1.1 · 1.05 · 1.8) = 10.1 N/mm²" |
| `partial` (PES/PVC subtable) | U (Bautechnik / Knippers, search excerpts) | **V for PES/PVC**, U for glass/PTFE and other | JRC132615 Code Review No. 20 (p. 98): "fd = fk,23 / (γf · γM · Ai)", "γM = 1.4 within the fabric surface, γM = 1.5 for connections", "A0 = 1.0 – 1.2 (1.2)", "A1 = 1.6 – 1.7 (1.5 – 3.4)", "A2 = 1.1 – 1.2 (1.2)", "A3 = 1.1 – 1.25 (1.4 – 1.95)"; "Winter storm: · Ares = γf · γM · A0 · A2 = 2.9 – 3.2", "Maximum snow: … A0 · A1 · A2 = 4.4 – 5.1", "Permanent: … A0 · A1 · A2 · A3 = 4.9 – 6.4". The tool now applies the A-factors by design situation (wind: A0·A2; temperature: A0·A2·A3; long-term: A0·A1·A2·A3). glass/PTFE values have no published source and stay U. |
| new `ts19102` (PES/PVC) | – | V (single source) | [JRC25] slide 112, https://eurocodes.jrc.ec.europa.eu/sites/default/files/2025-08/D1_Mollaert-Stimpfle_website.pdf: "modification factors according prCEN/TS 19102 … kbiax 1.00, kage 1.40, kdur,P 1.80, kdur,L 1.70, kdur,M 1.20, ktemp,70 2.00, ksize 1.00", "mat.: γM0 = 1.4, det.: γM2 = 1.5", "fRd4 … fk,23 /(γM · kbiax · kage · kdur,M · ksize)". These are prCEN values. The published TS Annex C.3 table was not readable: the iTeh preview of SIST-TS CEN/TS 19102:2024 shows only the contents ("C.3 Typical modification factors for PES-PVC membrane", "C.4 … glass-PTFE", "C.5/C.6 … ETFE"). |
| new `french_*` | – | V | JRC132615 Code Review No. 21: "TC ≤ TD = kq·ke·Trm/γt", Table 6-2 "γt … 4 … 4.5", "kq … equal to 0.8 otherwise", "ke = 1 for S ≤ 50 m²", "ke = (50/S)^(1/15)", "γtloc: local safety factor, equal to 5" |
| new `reinforcement_neff` | – | V | JRC132615 §6.5: "Strength (fabric + 1 reinforcement): neff =1.9 … + 2 …: 2.6 … + 3 …: 3.1"; "one reinforcement layer calculated with 75%: neff = 1.75, second … 50%: neff = 1.75·1.5 = 2.6"; Eurocode Outlook No. 38 "the design resistance is increased by 50% unless a more precise evaluation by tests has been performed. NOTE For more than 1 reinforcement layer tests have to be performed." |
| `seam_efficiency` 0.8 | V | V (more evidence) | JRC132615 Eurocode Outlook No. 5: seam strength at 23 °C "≥90%" (Types I–IV), "≥80%" (Type V); at 70 °C "≥70% … ≥60% … ≥55%" |
| new `prestress_min` | – | V | JRC132615 §3: "for PVC coated polyester fabrics not less than 1.3% of the short term tensile strength", "for PTFE coated glass fibre fabrics not less than 2.5% … but not less than 2.0 kN/m" (TensiNet guide); Code Review 6 (French): "initial prestress of at least 1.5 kN/m"; "in practice values between 180 and 350 daN/m (1.8 kN/m and 3.5 kN/m) are considered" |
| new `fractile_kn` 1.64 | – | C | EN 1990 Annex D Table D1 (Vx known, n → ∞); used in [JRC25] slide 112 "kn 1.64 … known material for n= ∞" |

## Factors that remain U (with range for `--sensitivity`)

| Key | Value, range | Search done | Why still U |
|---|---|---|---|
| `tear_factor` | 2.0, [1.5, 3.0] | JRC132615 §7.7 "Tear control" (read in full); CEN/TS 19102 §9.5 "Tear control" (title only, iTeh preview); web searches on slit-tear design factors (Bao et al. 2022; central-crack studies, abstracts only) | JRC: "The calculation of tear propagation using the methods of fracture mechanics may help to define allowable tear widths … This is currently a topic of research"; German practice "neglects the potential tear propagation" (Code Review 20). No code factor exists. |
| `added_mass_model` (new, replaces `added_mass_coeff`) | 1.0, [0.5, 1.0] | Lamb 1920; Zhao & Yu 2012 (World J. Mech. 2, 361–368, Table 2, open access); own Rayleigh-integral computation (reproduces Lamb 0.6689 and the piston value 8/(3π)) | The coefficient is now **computed** per panel and mode (square 0.726, 2:1 0.704, 4:1 0.646; circular membrane 0.746). The remaining uncertainty is the model: baffled flat panel in still air versus an isolated canopy (air flows round the edges, about half the added mass for a rigid disk), curvature and wind flow. |
| `corner_ply_eff` | 0.8, [0.5, 0.9] | as `reinforcement_neff` | Used only with `--neff-basis eta` (linear ply model). The published tables are used by default. |
| `partial` glass/PTFE and other subtables | γM 1.4, A-factors, scale [0.78, 1.24] | JRC132615 Code Reviews 20–21; Mollaert/Stimpfle 2025 | No published A-factor set for glass/PTFE, silicone/glass or ePTFE was found. |

The old `japan_*` ranges (7–8, 3.5–4) were removed because the values now come from the primary text.
`added_mass_coeff` (0.67, Lamb's clamped-plate value) was removed. The computed membrane coefficient is larger (0.73
for a square panel), so the old value gave too little added mass.

## Material data (materials.json)

| Source | Result | URL |
|---|---|---|
| Serge Ferrari Tenseo Advanced 1002 S2 | read: 420/400 daN/5cm, tear 55/50 daN, 1050 g/m², 0.78 mm, 267 cm, B-s2,d0, Tv 8 % | https://makmax.com.au/wp-content/uploads/2025/02/Serge-Ferrari-Tenseo-Advanced-1002S2-EN.pdf |
| Serge Ferrari Flexlight Advanced 1302 S2 / 1502 S2 | read: 800/700 and 1000/800 daN/5cm, tear 120/110 and 160/140 daN, 1350 / 1500 g/m², Euroclass printed C-s2,d0 | buitink-technology.com PDFs (see entries) |
| Mehler VALMEX FR 1000 MEHATOP F1 type III | read: 6000/5500 N/50 mm, tear 900/800 N, 1050 g/m², B-s2-d0, DIN 4102 B1 | https://www.tensaform.com/Uploads/Document/b23c5048-6b4f-4501-8e14-27841a4e1ad7.pdf |
| Verseidag Duraskin B4915, B18039 | search excerpts only (ArchiExpo returns 403) → status `excerpt` | pdf.archiexpo.com (see entries) |
| Sattler Atlas | no public datasheet found (protex.sattler.com gives no values). The published JRC 2025 example gives 8600/8400 N/5cm (Type IV) → status `published-example` | [JRC25] |
| Heytex | no architectural-membrane datasheet found (only mesh / print media sheets) → not added | – |
| Chukoh SKYTOP FGT-600/800/1000 | read: minimum tensile N/3cm, tear, mass, thickness, transmittance, MLIT non-combustible certification | https://www.chukoh.com/products/skytop/fgt/ |
| Saint-Gobain Sheerfill II / V EverClean | read (Birdair ASTM sheets): 825/600 and 550/625 lb/in, tear, oz/yd², solar transmission 12 / 16 % | birdair.com/files/specifications/ |
| Sefar Tenara 4T40HF | read: 4000/4000 N/5cm, tear 798/752 N, 1080 g/m², 0.55 mm, 157.5 cm, B-s1,d0, LT 38 % | https://www.birdair.com/files/specifications/Sefar_TENARA_Specs_4T40HF_en.pdf |
| Nowofol Nowoflon ET 6235 Z | read: 50 MPa, 500 %, 23 MPa at 10 % strain, 1000 MPa modulus, tear 500 N/mm, 1.75 g/cm³, LT > 91 % | https://www.buitink-technology.com/pdf/Nowoflon_ET_6235%20Z.pdf |
| AGC Fluon ETFE film | only thin-film distributor data (39 MPa, 12–40 µm) → not added | knowde.com (AGC listings) |
| Silicone/glass products | no architectural product sheet found; JRC Outlook 9/10 class table used | [JRC23] |
| Class tables PES/PVC I–V, glass/PTFE I–IV, glass/silicone, fluoropolymer-coated PTFE | read: JRC132615 Eurocode Outlooks 5–12 (means, 5 % fractiles where given, seam ratios, tear) | [JRC23] |

The earlier PES/PVC class table (teloniabiti.com: 66/60 … 200/190 kN/m) was replaced by the JRC proposed harmonised
classification (55/55 … 185/160 kN/m mean, 50/50 … 170/145 kN/m 5 % fractile).
