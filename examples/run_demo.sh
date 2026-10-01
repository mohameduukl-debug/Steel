#!/usr/bin/env bash
# End-to-end demo: 10 m four-point PVC sail with Galfan edge cables and pinned corners.
# Form finding -> load analysis -> membrane/cable/steel/connection checks -> patterns, GA, schedule, part drawings.
# Everything is pure Python 3 (no pip installs). Output goes to examples/output/.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../.claude/skills"
OUT="$HERE/output"
mkdir -p "$OUT" && cd "$OUT"

echo "== 1. Form finding (FDM) =="
python3 "$S/tensile-analysis/scripts/form_find_fdm.py" sail4 --size 10 --high 3 --n 16 --qc 12 \
        --prestress 2.0 --out sail --obj

echo; echo "== 2. Load analysis (dynamic relaxation): wind uplift and snow (factored values) =="
python3 "$S/tensile-analysis/scripts/dynamic_relaxation.py" sail.json --Et-u 800 --Et-v 600 \
        --EA-cable 14000 --pressure 0.9 --out sail_wind_up
python3 "$S/tensile-analysis/scripts/dynamic_relaxation.py" sail.json --Et-u 800 --Et-v 600 \
        --EA-cable 14000 --snow 0.75 --out sail_snow

python3 "$S/tensile-analysis/scripts/membrane_dr.py" sail.json --Ew 800 --Ef 600 --nu 0.3 --G 30 \
        --EA-cable 14000 --pressure 0.9 --out sail_cst_up

echo; echo "== 2b. Load-case set (wind directions, zones, snow + ponding) and envelope =="
python3 "$S/tensile-analysis/scripts/run_cases.py" sail.json "$HERE/load_cases_example.json" --out sail_cases

echo; echo "== 3. Membrane: material choice, checks, panel frequency, corner, sensitivity =="
python3 "$S/membrane-fabric/scripts/material_select.py" --n-design 8.6 --case wind --fire B --life 15 | sed -n 1,8p
python3 "$S/membrane-fabric/scripts/membrane_check.py" --material PVC-III --nw 8.6 --nf 8.6 --case wind
python3 "$S/membrane-fabric/scripts/membrane_check.py" --material PVC-III --nw 7.4 --nf 7.4 --case snow \
        --method partial --sensitivity
python3 "$S/membrane-fabric/scripts/membrane_check.py" --material PVC-III --prestress 2 2 --flutter 5 5 \
        --f-target 2.0 --sensitivity | sed -n '/Panel frequency/,$p'
python3 "$S/membrane-fabric/scripts/membrane_check.py" --material PVC-III --case wind --corner 30 90 0.35 \
        --layers 3 | sed -n '/Corner/,$p'

echo; echo "== 4. Cables: edge-cable check + schedule =="
python3 "$S/cable-tension-members/scripts/cable_calc.py" edge --chord 10.44 --sag 1.17 --n 8.0
python3 "$S/cable-tension-members/scripts/cable_calc.py" resist --Fmin 367 --termination swaged --FEd 125 --Fser 85 \
        --Fmin-force 10 --sensitivity
python3 "$S/cable-tension-members/scripts/cable_schedule.py" --from-model sail.json \
        --envelope sail_cases_envelope.json --product Ronstan-ACS2-GS-17.0 --deduct 250 --out sail_cables
python3 "$S/cable-tension-members/scripts/cable_schedule.py" "$HERE/schedule_example.json" --out schedule_example \
        --sensitivity
python3 "$S/cable-tension-members/scripts/cable_calc.py" clamp --dT 8 --nb 2 --bolt-d 16 --sensitivity
python3 "$S/tensile-connections/scripts/fatigue_check.py" --cable spiral_socket --spectrum 40:2e6 --spectrum 20:1e7 \
        --sensitivity
python3 "$S/cable-tension-members/scripts/cable_calc.py" rod --d 30 --fy 460 --fu 610 --FEd 150 --fitting-Rd 250
python3 "$S/cable-tension-members/scripts/cable_calc.py" stress-turns --L 10.44 --EA 14000 --F1 5 --F2 20 \
        --pitch 3.5 --w 0.013
python3 "$S/cable-tension-members/scripts/cable_calc.py" freq-tension --L 10.44 --m 1.3 --EA 14000 \
        --f 1:6.22 --f 2:12.4 --f 3:18.7

echo; echo "== 5. Corner plate resolution + pin/lug check (corner forces from the uplift run) =="
python3 "$S/tensile-connections/scripts/corner_plate.py" --m EC1:15:83:180:48 --m EC2:105:83:-48:180 \
        --m strap:60:6:100:173
python3 "$S/tensile-connections/scripts/pin_connection.py" --F 210 --Fser 150 --d 36 --d0 37 --t 25 \
        --a-lug 50 --c-lug 35 --fork-t 16 --pin-fy 640 --pin-fu 800 --replaceable --aisc

echo; echo "== 6. Mast (6 m pinned CHS 168.3x8), lug weld, base plate =="
python3 "$S/steel-supports/scripts/member_check.py" --section CHS:168.3x8 --L 6 --N 260 --My 6
python3 "$S/tensile-connections/scripts/steel_joint_checks.py" weld --F 210 --angle 70 --L 180 --a 8 --e 110
python3 "$S/tensile-connections/scripts/steel_joint_checks.py" baseplate --col CHS --D 168.3 --tc 8 --B 350 --H 350 \
        --tp 25 --Nc 300 --Nt 60 --V 25 --anchors 4 --anchor-d 20 --edge 55

python3 "$S/steel-supports/scripts/frame2d.py" arch --L 20 --f 4 --n 20 --section CHS:219.1x8 --q 3.5 --check --Lz 5
python3 "$S/tensile-connections/scripts/steel_joint_checks.py" anchor --n1 2 --n2 2 --s1 200 --s2 200 --c1 400 \
        --c2 400 --hef 250 --d 24 --N 60
python3 "$S/steel-supports/scripts/foundation_check.py" block --B 2.5 --L 2.5 --D 1.5 --V 60 --H 45 --ha 0.3 --mu 0.45 --qRd 200
python3 "$S/steel-supports/scripts/foundation_check.py" helical --T 10 --pull 90 --sensitivity
python3 "$S/steel-supports/scripts/frame2d.py" arch --L 20 --f 4 --n 40 --shape circular --section CHS:219.1x8 \
        --p-normal 3.5 | sed -n 1p

echo; echo "== 7. Patterns, GA DXF and steel part drawings =="
python3 "$S/fabrication-drawings/scripts/cutting_pattern.py" sail.json --panels-along v --strip 2 --seams geodesic \
        --comp-warp 0.8 --comp-weft 1.6 --decomp-ends 0 --decomp-length 500 --seam 50 --edge 80 \
        --roll-width 2500 --out sail_patterns
python3 "$S/fabrication-drawings/scripts/export_dxf.py" sail.json --forces --out sail_GA
python3 "$S/fabrication-drawings/scripts/steel_part_dxf.py" lug --d0 37 --d 36 --t 25 --a 50 --c 35 \
        --base 150 --height 110 --mark LP-01 --qty 4 --project "Demo sail"
python3 "$S/fabrication-drawings/scripts/steel_part_dxf.py" corner --t 25 --edge 45 --hole A:0:0:52 \
        --hole EC1:180:48:37 --hole EC2:48:180:37 --hole M1:100:100:18 --mark CP-01 --qty 4 --project "Demo sail"

echo; echo "== 8. Other shapes: arch-supported tunnel and multi-bay ridge/valley roof =="
python3 "$S/tensile-analysis/scripts/form_find_fdm.py" arch --L 20 --B 10 --H 4 --arches 3 --nu 24 --nv 12 \
        --prestress 2 --out arch | sed -n '/Support groups/,/RAIL-S/p'
python3 "$S/tensile-analysis/scripts/form_find_fdm.py" multibay --bays 3 --bay 8 --B 10 --h-hi 6 --h-lo 3 --m 4 \
        --nv 12 --qc 3 --prestress 2 --out multibay | grep -E "RIDGE|VALLEY"
python3 "$S/tensile-analysis/scripts/dynamic_relaxation.py" multibay.json --snow 0.8 --ponding | grep -E "Ponding|RIDGE|VALLEY"
python3 "$S/fabrication-drawings/scripts/cutting_pattern.py" multibay.json --seams geodesic --strip 1 --roll-width 2670 \
        --auto-split --notch 1000 --sheets --project "Demo market roof" --out multibay_patterns | tail -4
python3 "$S/fabrication-drawings/scripts/nest_panels.py" multibay_patterns.json --gap 20 --out multibay_nest

echo; echo "== 9. Calculation report =="
python3 "$S/tensile-structures/scripts/report.py" --title "Demo sail" --model sail.json --cases sail_cases_envelope.json \
        --material PVC-III --method partial --cables sail_cables.csv --patterns sail_patterns.csv --out sail_report

echo; echo "Done. Files in $OUT:"; ls -1 "$OUT"
