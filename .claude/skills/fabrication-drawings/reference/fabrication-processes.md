# Fabrication processes, QC and installation

Tags: [V] verified (source below), [C] code/standard content, [U] unverified practice value (range given).

## 1. Welding and sealing
| Material | Process | Parameters / notes |
|---|---|---|
| PES/PVC | **HF (RF, dielectric) welding** | field oscillating at 27.12 MHz [V, F1]; fusion ≈ 140 °C [U, 130–160 °C]; seam efficiency 0.80–0.90 typical [V, register `membrane.seam_efficiency`], 68–96 % reported [U]; weld width dominates strength [V, F2] |
| PES/PVC | hot-air / hot-wedge (Leister) | hand/automatic hot-air welders adjustable about 40–620 °C [V, F3]; working air temperature 300–600 °C [U]; long seams, repairs, site work |
| glass/PTFE | **heat sealing** with FEP (or PFA) film interlayer, hot-bar or impulse | sealing equipment 370–385 °C (700–740 °F) for PTFE and PTFE-coated fabrics; equipment minimum 288 °C for FEP film, 316 °C for PFA film [V, F4]; seams 50–75 mm [U] (welded width ≥ 50 mm [V, F2]); seams lose 60–73 % at 250 °C [U, not re-traced] |
| ETFE | thermal (impulse) welding | welded width ≥ 10 mm [V, F2]; details [U] |
| silicone/glass | vulcanising / bonding / sewing | [U] |
| HDPE shade cloth | sewing with PTFE thread | [U] |
PVDF-lacquered PVC: grind off at the weld line or use a weldable lacquer [U].

## 2. Seam testing and QC
* Test coupons per machine, per shift and per batch; strip tensile (EN ISO 1421 strip method, 50 mm strip [C]) of
  seam versus base fabric.
* Peel/adhesion tests; elevated-temperature seam tests (about 70 °C for PVC [U, 50–80 °C]); long-term seam creep
  (German practice) [U].
* Log parameters (temperature, pressure, time, speed); batch/roll traceability; panel dimension checks against the patterns;
  visual inspection of every seam.
* Biaxial tests of the delivered batch for compensation (EN 17117-2:2021 [V, see patterning.md S4]) before cutting.

## 3. Handling, packing, storage
* PTFE/glass: **no sharp folds**. Roll on large cores or fold loosely with padding at the folds; store dry and flat (water
  can cause a partly reversible strength loss of up to about 20 % [U, 10–20 %]).
* PVC: fold with care at low temperatures (cold cracking of the coating) [U]; protect from soiling.
* Label packages with panel IDs and unfolding direction consistent with the installation sequence.

## 4. Installation sequence (typical)
1. Survey the supports and anchors (as-built versus design coordinates) and adjust cable lengths if needed.
2. Erect masts and steel (temporary guys), set adjusters to their set positions.
3. Unpack and unfold the membrane on a protected surface, temporary net or platform.
4. Attach corner and edge hardware on the ground (corner plates, edge cables in pockets, clamp plates).
5. Lift (crane, spreader beams, hoists on masts); connect the edges loosely.
6. **Tension gradually and evenly** in the engineered sequence: mast jacking (sand pot or telescopic section), corner screws,
   tie-back shortening, edge-cable studs, adjustable keder tracks.
7. Verify prestress and geometry against the measurement plan; record turnbuckle positions.
8. Re-tighten clamp bolts; seal and cap.
9. Re-tension after creep (PVC) per the maintenance plan; periodic inspection (seams, corners, cable fittings, corrosion, drainage).

## Sources
- F1 3M application guide for RF welding: "oscillates at a frequency of 27.12 MHz" (polar plastics such as PVC),
  https://multimedia.3m.com/mws/media/157027O/high-gloss-film.pdf
- F2 Journal of Industrial Textiles 54 (2024), doi 10.1177/15280837241300935: minimum welded widths PTFE 50 mm,
  PVC 25 mm, ETFE 10 mm (design regulation); welded width has the greatest influence on seam stiffness;
  Taguchi study (Trends in Sciences 2022) on PVC/PES: seam width the most significant factor,
  https://tis.wu.ac.th/index.php/tis/article/view/3463
- F3 Leister Triac AT product data (reseller): "40 to 620 degrees C with stepless setting", banner and tarp welding,
  https://www.chemical-concepts.com/product/leister-triac-at-hot-air-plastic-welder/
- F4 Textiles Coated International, Films for Welding (architectural) datasheet: "For heat sealing of PTFE and
  PTFE-coated fabrics, sealing equipment capable of 700°-740°F (370-385°C) is typically required"; minimum 550 °F
  (288 °C) for FEP, 600 °F (316 °C) for PFA, https://www.textilescoated.com/uploads/files/Films%20for%20Welding_Architectural_DS.pdf
