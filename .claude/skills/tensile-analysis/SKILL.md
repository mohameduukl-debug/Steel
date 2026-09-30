---
name: tensile-analysis
description: Form finding, structural analysis and modelling of tensile membrane / cable-net structures with steel supports — Force Density Method, Dynamic Relaxation, Updated Reference Strategy, geometrically non-linear load analysis (prestress, wind uplift/pressure, snow, ponding), wrinkling/slack checks, reactions for steel design, and guidance on software (SOFiSTiK, Easy, ixForten, RFEM, GSA, Kangaroo, Karamba, MPanel, WinTess, Robot, ANSYS, LS-DYNA). Includes runnable pure-Python FDM and DR solvers.
---

# Form finding, analysis and modelling

## Tools (stdlib Python)
### `scripts/form_find_fdm.py`: Force Density Method
```bash
python3 form_find_fdm.py sail4 --size 10 --high 3 --n 16 --qc 12 --prestress 2.0 --out sail --obj
python3 form_find_fdm.py hypar --size 8 --high 2 --n 16 --prestress 1.5 --out hypar     # rigid frame edges
python3 form_find_fdm.py cone  --R 8 --r 0.6 --H 5 --anchors 6 --nr 12 --nc 36 --prestress 2.5 --out cone
python3 form_find_fdm.py --input mymodel.json --prestress 2.0 --out result              # any topology
```
- `--qc`: edge-cable to membrane force-density ratio. It controls the edge sag; aim for 8–12 % of chord.
- `--prestress`: scales every q so the mean membrane stress equals the target (FDM geometry depends only on q ratios).
- Output: JSON (coordinates, edge forces, membrane stress estimate, cable-group sag/force, support pulls, area) and an OBJ mesh.

### `scripts/dynamic_relaxation.py`: non-linear load analysis
```bash
python3 dynamic_relaxation.py sail.json --Et-u 800 --Et-v 600 --EA-cable 14000 --pressure 0.9 --out up     # uplift
python3 dynamic_relaxation.py sail.json --Et-u 800 --Et-v 600 --EA-cable 14000 --pressure -0.5 --out down
python3 dynamic_relaxation.py sail.json --Et-u 800 --Et-v 600 --EA-cable 14000 --snow 0.75 --out snow
```
This uses kinetic-damping DR on the cable-net analogy. Links are tension-only, and slack membrane links flag wrinkling. Pressure is a follower load
normal to the surface; snow acts on plan area. Output: displacements, forces, stresses, slack count, reactions.
A zero-load run converges at iteration 0, which proves the prestress state is in equilibrium.

**Ponding** (`--ponding`): after the snow/rain case converges, a priority-flood fills every basin of the
**deformed** surface to its spill level (outlets = free edges, supports, nodes with `"drain": true`), applies the
water weight and re-runs until the water volume converges or grows (reported as PONDING INSTABILITY). Any basin
counts as a FAIL: ponding must be avoided.
```bash
python3 dynamic_relaxation.py flat.json --snow 0.5 --ponding -v
```

### `scripts/run_cases.py`: load-case sets and envelopes
```bash
python3 run_cases.py sail.json examples/load_cases_example.json --out sail_cases
python3 ../../cable-tension-members/scripts/cable_schedule.py --from-model sail.json \
        --envelope sail_cases_envelope.json --product Ronstan-ACS2-GS-17.0 --deduct 250
```
Each case is solved non-linearly and separately. Options per case: uniform `pressure`, `snow`, pressure `zones` (plan
polygons), a directional `gradient` (windward → leeward, to screen wind directions), `factor`, `ponding`.
Outputs: `_envelope.json` (edge and cable-group max/min with governing case, reactions per support per case, reaction
envelope) and `_summary.md`. Cp zones and gradients must come from tunnel data, TensiNet A1 or conservative code values.

**Limits (state them in any report):** a net model ignores fabric shear stiffness and Poisson coupling, with warp along
grid u. Use it for concept, sizing and checking. Final design needs orthotropic membrane FE with wrinkling in
dedicated software.

## Method summary (details: `reference/form-finding-methods.md`)
- **FDM** (Schek 1974): q = F/L makes equilibrium linear: `D x = p − D_f x_f`, with `D = CᵀQC` (SPD if all q > 0 and every free node is connected to a support). Solve x, y, z separately. Non-linear FDM iterates q ← F_target/L.
- **DR** (Day 1965, Barnes 1999): fictitious masses M_i = λ(Δt²/2)S_i with S = EA/L₀ + T/L; leapfrog integration; kinetic damping (reset velocities at the KE peak). No stiffness matrix, so it handles slack, large displacement and form finding.
- **URS** (Bletzinger and Ramm 1999): homotopy blend of Cauchy stress on the current geometry with PK2 on the reference, updating the reference until they coincide. Handles anisotropic prestress on continuum membranes (RFEM form finding is URS-inspired). On cable nets it is equivalent to FDM.
- Soap film (isotropic, zero mean curvature) versus anisotropic prestress: an arbitrary anisotropic field is generally not realisable, so it needs stabilisation.
- Equilibrium check: `n₁/R₁ + n₂/R₂ = p`; with p = 0, `n_w/R_w = n_f/R_f`.

## Analysis rules (details: `reference/analysis-and-loads.md`)
1. **Geometrically non-linear**, large displacement; K_T = K_E + K_G. **No superposition.** Apply partial factors before each run.
2. Membrane: CST or quad membrane elements without bending; orthotropic E_w·t, E_f·t, ν, G from biaxial tests; tension-field or wrinkling model.
3. Cables: tension-only, EA from the supplier (prestretched), temperature through L₀(T).
4. Steel: include masts, rings and arches (their flexibility changes the prestress); or iterate the support displacements.
5. Load cases: PS (initial and relaxed), G, S (uniform, drift, asymmetric, ponding), W (several directions, ±; no code Cp for hypars and cones, so use tunnel data, TensiNet A1 or conservative canopy/vault values; dynamic/aeroelastic for large roofs), T, erection.
6. Results to check: warp/weft/principal stress, min stress (slack), deflection versus clearance, **ponding** (load follows the deformed shape), cable max/min, reactions (envelopes and concurrent sets).

## Software guide (details: `reference/software-guide.md`)
| Need | Typical choice |
|---|---|
| Full commercial chain (form → analysis → patterns) | Easy (technet), ixForten 4000, SOFiSTiK + TEXTILE, RFEM 6 + Form-Finding + Cutting Pattern, Forten32, WinTess3, K3-Tent, inTENS, Tensyl (Buro Happold in-house) |
| Design exploration | Rhino + Grasshopper + Kangaroo2 (goal solver), Karamba3D (approximate) |
| Fabricator patterning | MPanel (Rhino/AutoCAD) |
| General non-linear FE / research | ANSYS, LS-DYNA (*MAT_FABRIC), Oasys GSA (DR, soap-film form finding) |
| Steel design of supports | RFEM, SOFiSTiK, Robot, Tekla Structural Designer, SAP2000 |
| Python | these scripts; COMPAS + compas_fd; JAX-FDM; libigl (LSCM/ARAP), potpourri3d (geodesics), ezdxf |

## Handover
- To `membrane-fabric`: max warp/weft stress per combination → `membrane_check.py`.
- To `cable-tension-members`: cable forces (max, min) → `cable_calc.py resist`, `cable_schedule.py --from-model`.
- To `steel-supports` / `tensile-connections`: `reactions[].pull` per combination → mast, corner-plate, pin and foundation checks.
- To `fabrication-drawings`: the form-found mesh (prestress geometry) → `cutting_pattern.py`, `export_dxf.py`.
