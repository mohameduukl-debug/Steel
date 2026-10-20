# Cable fabrication, schedule and installation

Tags as in `cable-types-and-standards.md` ([V] read in a named source, [C] code content an NA may change,
[U] practice value). EN = EN 1993-1-11:2006 + AC:2009.

## 1. Factory process
1. Cut the strand (allow for sockets).
2. **Prestretch**: EN 3.2.2 NOTE 4 recommends prestretching non-prestretched group B cables by cyclic loading up to a
   maximum of 0.45 F_uk [V]; the modulus for analysis is the secant value after at least 5 cycles between the
   minimum and maximum characteristic forces (3.2.2(2)) [V]. Teufelberger-Redaelli cycle the master length "from
   approx. 5% to 50-55% of the strand minimum breaking force for five or more times" and mark under preload after the
   last cycle [V: Cable System catalogue]. This removes constructional stretch; residual creep is then
   small: allow 0.15 mm/m for cutting to length without better data [V: EN 3.2.2(3) NOTE 1]. Unprestretched strand
   rope can lengthen permanently by 0.25–0.5 %+ [U].
3. Mark to length only **at a prescribed cutting (measuring) load** [V: EN 3.4(1)], at a stated reference temperature.
   EN 3.4(2) lists what the cut length must allow for [V]: the elongation measured between the minimum and maximum
   force after cyclic loading, the difference between the **design temperature (normally 10 °C)** and the cutting
   temperature, long-term creep, the elongation after clamp installation and the deformation after first loading.
   Many suppliers measure at 20 °C [U: convention] — state the reference temperature on the drawings.
4. **Mark** socket positions and clamp/saddle positions under that load.
5. Socket (pour zinc or resin, or swage) and **proof-load**. Pfeifer: factory-stretched and marked under prescribed
   loads; elongation from C = EA/L [V]. Ronstan swaged cables: length between fittings ≥ 50d (1x19, 1x37) or
   70d (1x61) [V].

## 2. Tolerances
No code value verified. Manufacturer practice is about ±(0.02–0.05) % of L, with a minimum of a few mm [U]. Cable nets with
pre-marked clamps need much tighter values. Do not quote "±L/5000" as a code value (unverified). Always provide adjustment.

## 3. Cable schedule: required columns
| Group | Fields |
|---|---|
| Identity | cable ID, grid location, quantity |
| Product | type and construction (OSS 1x61, FLC, 1x19 316, bar grade), nominal Ø, metallic area A, E, EA, wire grade, coating (Galfan class A, stainless grade), inner filling |
| Strength | F_min (MBL), k_e, F_uk, F_Rd (EN) or S_d (ASCE), γR used |
| Forces | ULS max, SLS/characteristic, prestress, minimum force (slack check) |
| **Lengths** | unstressed pin-to-pin length at T_ref (and under measuring load), stressed length at prestress |
| Fittings | both ends: type, size, pin Ø, jaw width / plate thickness, thread |
| Adjustment | range and set position, turnbuckle type |
| Marks | clamp and saddle positions from the datum (unstressed) |
| Process | prestretch load and cycles, measuring load, tolerance |
| Other | mass, reel, sheath, colour, certificates (EN 10204 3.1, proof-load, ETA/CE) |
| Installation | stressing sequence, target force and measuring method (jack, load cell, strain gauge, frequency) |

`scripts/cable_schedule.py` writes most of these (CSV + Markdown); complete fittings and adjustment by hand.
Its lengths treat each cable as straight (L0 = L_pin/(1 + F/EA)); for sagging cables use `cable_calc.py length`,
which integrates ∫ds/(1 + T/EA) over the catenary. Worked hand check of one schedule line: `validation.md`.

## 4. Node-to-pin deductions
Form-finding gives **node-to-node** lengths (the theoretical intersection at corner plates and mast heads).
Fabrication length is **pin-to-pin**. Subtract, at each end, the distance from the theoretical node to the pin
centre on the corner plate or lug (`deduct_A_mm`, `deduct_B_mm`). Keep these consistent with the steel shop drawings.

## 5. Installation and stressing
* Pull cables through pockets (open pocket ends, or fit the second fitting after pulling).
* Set adjusters to mid-range (or the calculated set position), connect loosely, then stress in the engineered sequence.
* Construction stress limits: 0.60 σ_uk for the first tension components for only a few hours, 0.55 σ_uk after the
  other components are installed [V: EN Table 7.1, NDP].
* Measure: hydraulic jack pressure, load cell, turnbuckle turns (`cable_calc.py stress-turns`: lead × turns =
  shortening), vibration frequency (`freq-tension`, T = 4mL²f₁² for a taut string; use mode 2 or `--EA` on sagging
  cables), survey of geometry.
* Re-tighten clamp bolts after stressing (the strand diameter reduces under load, EN 6.3.2(3)) [V].
* PVC roofs: plan re-tensioning after creep (weeks to months).
