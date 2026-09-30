# Cable fabrication, schedule and installation

## 1. Factory process
1. Cut the strand (allow for sockets).
2. **Prestretch**: cyclic loading to about 45–55 % F_uk [U] (EN excerpt: up to 0.45 f_uk during execution [V]). This removes
   constructional stretch; residual creep afterwards is about ≤ 0.1–0.2 mm/m [U]. Unprestretched strand rope can
   lengthen permanently by 0.25–0.5 %+ [U].
3. Measure length under a defined **measuring (reference) load** at a reference temperature (commonly 20 °C, [U] as a
   convention; state it on the drawings).
4. **Mark** socket positions and clamp/saddle positions under that load.
5. Socket (pour zinc or resin, or swage) and **proof-load**. Pfeifer: factory-stretched and marked under prescribed
   loads; elongation from C = EA/L [V].

## 2. Tolerances
No code value verified. Manufacturer practice is about ±(0.02–0.05) % of L, with a minimum of a few mm [U]. Cable nets with
pre-marked clamps need much tighter values. Do not quote "±L/5000" as a code value (unverified). Always provide adjustment.

## 3. Cable schedule: required columns
| Group | Fields |
|---|---|
| Identity | cable ID, grid location, quantity |
| Product | type and construction (OSS 1x61, FLC, 1x19 316, bar grade), nominal Ø, metallic area A, E, EA, wire grade, coating (Galfan class A, stainless grade), inner filling |
| Strength | F_min (MBL), k_e, F_uk, F_Rd (EN) or S_d (ASCE) |
| Forces | ULS max, SLS/characteristic, prestress, minimum force (slack check) |
| **Lengths** | unstressed pin-to-pin length at T_ref (and under measuring load), stressed length at prestress |
| Fittings | both ends: type, size, pin Ø, jaw width / plate thickness, thread |
| Adjustment | range and set position, turnbuckle type |
| Marks | clamp and saddle positions from the datum (unstressed) |
| Process | prestretch load and cycles, measuring load, tolerance |
| Other | mass, reel, sheath, colour, certificates (EN 10204 3.1, proof-load, ETA/CE) |
| Installation | stressing sequence, target force and measuring method (jack, load cell, strain gauge, frequency) |

`scripts/cable_schedule.py` writes most of these (CSV + Markdown); complete fittings and adjustment by hand.

## 4. Node-to-pin deductions
Form-finding gives **node-to-node** lengths (the theoretical intersection at corner plates and mast heads).
Fabrication length is **pin-to-pin**. Subtract, at each end, the distance from the theoretical node to the pin
centre on the corner plate or lug (`deduct_A_mm`, `deduct_B_mm`). Keep these consistent with the steel shop drawings.

## 5. Installation and stressing
* Pull cables through pockets (open pocket ends, or fit the second fitting after pulling).
* Set adjusters to mid-range (or the calculated set position), connect loosely, then stress in the engineered sequence.
* Measure: hydraulic jack pressure, load cell, turnbuckle turns (thread pitch × turns = shortening), vibration frequency
  (T = 4mL²f₁²), survey of geometry.
* Re-tighten clamp bolts after stressing (the strand diameter reduces under load).
* PVC roofs: plan re-tensioning after creep (weeks to months).
