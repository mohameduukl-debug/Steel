---
name: tensile-analysis
description: Form finding, structural analysis and modelling of tensile membrane / cable-net structures with steel supports — Force Density Method, Dynamic Relaxation, Updated Reference Strategy, geometrically non-linear load analysis (prestress, wind uplift/pressure, snow, ponding), wrinkling/slack checks, reactions for steel design, and guidance on software (SOFiSTiK, Easy, ixForten, RFEM, GSA, Kangaroo, Karamba, MPanel, WinTess, Robot, ANSYS, LS-DYNA). Includes runnable pure-Python FDM and DR solvers.
---

# Form finding, analysis and modelling

Tags: **[V]** confirmed at the cited source; **[C]** computed/derived here or textbook content known with confidence;
**[U]** unverified or practice value (range given), check before use. Validation of every tool against independent
references: `reference/validation.md`.

## Tools (stdlib Python, one CPU)
### `scripts/form_find_fdm.py`: Force Density Method
```bash
python3 form_find_fdm.py sail4 --size 10 --high 3 --n 16 --qc 12 --prestress 2.0 --out sail --obj
python3 form_find_fdm.py hypar --size 8 --high 2 --n 16 --prestress 1.5 --out hypar     # rigid frame edges
python3 form_find_fdm.py cone  --R 8 --r 0.6 --H 5 --anchors 6 --nr 12 --nc 36 --prestress 2.5 --out cone
python3 form_find_fdm.py arch  --L 20 --B 10 --H 4 --arches 3 --nu 24 --nv 12 --prestress 2 --out arch
python3 form_find_fdm.py multibay --bays 3 --bay 8 --B 10 --h-hi 6 --h-lo 3 --m 4 --nv 12 --qc 3 --prestress 2 --out mb
python3 form_find_fdm.py rings --R 5 --r 5 --H 3 --nr 12 --nc 48 --prestress 2 --uniform-stress --out hourglass
python3 form_find_fdm.py sail4 --n 24 --prestress 2 --uniform-stress --cable-force 16 --out sail_us   # soap-film sail
python3 form_find_fdm.py --input mymodel.json --prestress 2.0 --out result              # any topology
```
- Shapes: `sail4` (4-point sail, cable edges), `hypar` (rigid boundary), `cone` (top ring + anchors, `--anchors`,
  `--nr`, `--nc`), `arch` (arch-supported tunnel), `multibay` (ridge/valley), `rings` (membrane between two coaxial
  rigid rings, bottom radius `--R`, top `--r`, distance `--H`; hourglass/catenoid or a cone on a ring beam).
- `--qm` / `--qc` / `--qr`: membrane, edge-cable and ridge/valley-cable force densities (relative). **`--qc` is a ratio
  per link and is mesh dependent** [C, shown in `validation.md`]: a link force is q × segment length, so the same `--qc`
  on a finer mesh gives a weaker cable and a bigger sag (sail4, qc 12: sag 6.7 % at n = 8, 11.2 % at n = 16, 17.0 % at
  n = 32). Tune `--qc` for the sag you want (8–12 % of chord is common practice [U: practice; span/8–span/15 in
  `tensile-connections`]) at the mesh you use, and scale `--qc`/`--qr` with n when you refine (`mesh_convergence.py`
  does this automatically).
- `--prestress`: scales every q so the mean membrane stress equals the target (FDM geometry depends only on q ratios).
- `--uniform-stress` (+ `--us-method auto|cst|width`, `--cable-force T`, `--ff-maxiter` 300, `--ff-tol`): form finding
  for a uniform isotropic membrane stress σ = `--prestress` (soap-film-like). `auto` picks `cst` when the model has
  cables, `width` otherwise.
  - `cst`: exact isotropic stress σ in every triangle (cotangent force densities, Pinkall–Polthier; URS with λ = 0) and
    a CONSTANT force T in every cable (`--cable-force`, default the linear-FDM force of each group scaled to σ), so each
    free edge becomes an arc of radius R = T/σ (choose T = σ·R for the sag you want). Monotone majorise–minimise steps,
    then normal-only moves (cable nodes also across the cable) to stop tangential mesh creep. Robust at the corners of
    free cable-edged sails: radius error 0.45 % → 0.14 % → 0.04 % at n = 8/16/32, and the result is an exact CST
    prestress equilibrium (zero drift in `membrane_dr.py`) [C: `validation.md`]. Stops with "degenerating mesh" (NOT
    CONVERGED) where an isotropic field is not realisable — tall cones on a small ring — and on the `multibay`
    generator: use linear FDM there. Membrane links get stress = σ; reactions are the exact element forces.
  - `width`: q = σ·w/L on the grid links (w tributary width), cables keep their q; converges to the catenoid with O(h²)
    error; degenerates at the corners of cable-edged sails (kept for rings / rigid boundaries).
- `arch`: reports the total pull and line load on each arch (ARCH-k) and rail (RAIL-S/N). `multibay`: ridge cables sag
  below their chord, valley cables hog above it (`mid_dz` < 0 / > 0); support groups MAST-k / ANCHOR-k; `--qc 3` gives
  about 8–10 % scallop sag at the default mesh [C: tool output].
- Output: JSON (coordinates, edge forces, membrane stress estimate, cable-group sag/force, support pulls, area,
  `solver.uniform_stress` info) and an OBJ mesh (`--obj`). The CLI prints its assumptions first.

### `scripts/membrane_dr.py`: orthotropic MEMBRANE analysis (recommended for load cases)
```bash
python3 membrane_dr.py sail.json --Ew 800 --Ef 600 --nu 0.3 --G 30 --EA-cable 14000 --pressure 0.9 --out up
python3 membrane_dr.py sail.json --snow 0.75 --ponding --out snow
python3 membrane_dr.py flat.json --prestress 2 2 --pressure 0.1 --no-wrinkling --tol 1e-6 --maxit 200000 -v
python3 membrane_dr.py sail.json --pressure 0.9 --solver newton --out up        # implicit, 5-80x faster, same result
```
- Solvers (same residual, same outputs): `--solver dr` (default; explicit kinetic-damping DR) or `--solver newton`
  (Newton–Raphson with the consistent tangent of the TL CST: material + geometric stiffness, tension-field tangent by
  central differences, cable stiffness, symmetric part of the follower-pressure stiffness (`--no-follower-stiffness` to
  drop it; snow on plan is a dead load in the tangent); adaptive load steps, energy line search, modified-Newton reuse
  of the factor, skyline Cholesky in RCM/input order, Levenberg–Marquardt shift when K is not positive definite, and
  DR fallback). Newton = DR on every benchmark (node positions to ~1e-5 m) [C]. Use `newton` for meshes above ~12×12
  and for unstressed starts (airbags, Hencky), DR for small meshes or when the output `analysis.newton.fallback_dr` is
  true anyway. `--tol` on very wrinkled unstressed starts: 1e-5 kN or larger (smaller can stall → slow DR fallback).
- Supports per component: a node may carry `"fix": [fx, fy, fz]` (booleans) instead of `"fixed": true` — symmetry
  planes, rollers (CST solver only; reported in `reactions` with the free components ≈ 0).
- Constant-strain triangles, Total-Lagrangian (F, Green strain, PK2 stress per unit reference width, exact large
  rotations). Orthotropic plane stress in warp/weft axes: E_w·t, E_f·t, ν_wf (ν_fw by reciprocity), G·t. Quads take warp
  from the grid u direction; triangle faces from the model's optional `"warp_dir"` (default global x).
- **Wrinkling** (tension-field theory, Roddeman et al. 1987; mixed criterion): taut if the minor principal stress ≥ 0;
  slack if the major principal elastic strain ≤ 0; otherwise the element carries a uniaxial stress σ·n⊗n, with n and
  σ = ε_nn/C_nn(n) solved so that the rest of the strain is wrinkling contraction. Exact for linear orthotropy, including
  off-axis tension; isotropic: n = major principal strain direction, σ = E·t·ε₁. Counts of wrinkled/slack elements
  are reported. (Earlier versions projected the linear stress: in the uniaxial benchmark that gave 6.65 instead of 8.0 kN/m,
  −17 %, and declared off-axis tension states slack.)
- Initial stress from the form finding (warp/weft per quad) or uniform `--prestress W F`. The prestress state is first
  relaxed to equilibrium, and the drift and stress ranges are reported. Cables are tension-only links.
- Loads: follower pressure (+ = uplift), snow per plan area, ponding (`--ponding`, same algorithm as the net solver).
- `run_cases.py` uses it with `"solver": "cst"` (DR) or `"cst-newton"` in the cases file (material gains `nu`, `G`);
  `mesh_convergence.py --solver cst-newton` likewise.

### `scripts/dynamic_relaxation.py`: non-linear load analysis (cable-net analogy; fast screening)
```bash
python3 dynamic_relaxation.py sail.json --Et-u 800 --Et-v 600 --EA-cable 14000 --pressure 0.9 --out up     # uplift
python3 dynamic_relaxation.py sail.json --Et-u 800 --Et-v 600 --EA-cable 14000 --pressure -0.5 --out down
python3 dynamic_relaxation.py sail.json --snow 0.75 --ponding --depth-limit 1.0 --tol 1e-4 --maxit 200000 -v
```
Kinetic-damping DR on the cable-net analogy: tension-only links (slack membrane links flag wrinkling), membrane link
EA = E·t × tributary width, unstressed length from the form-finding force. Pressure is a follower load normal to the
surface; snow acts on plan area. Output: displacements, forces, stresses, slack count, reactions. A zero-load run
converges at iteration 0, which proves the prestress state is in equilibrium.

**Ponding** (`--ponding`): after the snow/rain case converges, a priority-flood fills every basin of the **deformed**
surface to its spill level (outlets = free edges, supports, nodes with `"drain": true`), applies the water weight
(γ_w = 10 kN/m³: 9.81 rounded up [C]) and re-runs until the water volume converges or grows (PONDING INSTABILITY,
or depth > `--depth-limit`). Any basin counts as a FAIL: ponding must be avoided.

### `scripts/run_cases.py`: load-case sets and envelopes
```bash
python3 run_cases.py sail.json examples/load_cases_example.json --out sail_cases [-v]
python3 ../../cable-tension-members/scripts/cable_schedule.py --from-model sail.json \
        --envelope sail_cases_envelope.json --product Ronstan-ACS2-GS-17.0 --deduct 250
```
Each case is solved non-linearly and separately. Options per case: uniform `pressure`, `snow`, pressure `zones` (plan
polygons), a directional `gradient` (windward → leeward, to screen wind directions), `factor`, `ponding`, `tol`,
`duration`. Cases-file keys: `solver` (`net` | `cst`), `material` (`Et_u`, `Et_v`, `nu`, `G`, `EA_cable`).
Outputs: `_envelope.json` (edge and cable-group max/min with governing case, reactions per support per case, reaction
envelope) and `_summary.md`. Cp zones and gradients must come from tunnel data, TensiNet guidance or conservative code
values.

### `scripts/mesh_convergence.py`: mesh-convergence study
```bash
python3 mesh_convergence.py sail4 --size 10 --high 3 --n 8 --qc 12 --prestress 2 --solver cst --pressure 0.9 --levels 1 2 3
python3 mesh_convergence.py --models coarse.json medium.json fine.json --solver net --snow 0.6 --json conv.json
```
Regenerates a built-in shape at 2–4 mesh densities (`--levels`, multipliers of every mesh count), scales `--qc`/`--qr`
with the mesh so the design is unchanged (`--keep-qc` to see the effect of not doing so), runs the load case with
`--solver none|net|cst` (`--pressure`, `--snow`, `--Et-u`, `--Et-v`, `--nu-wf`, `--G`, `--EA-cable`, `--tol`) and prints
max displacement, max/min stress, max cable force, max reaction, wrinkled count and time per level, the change between
levels, and for geometric levels (1 2 4) the observed order and a Richardson-extrapolated value. "Converged" = last
change < `--target` % (default 5 % [U: engineering judgement, not a code value]). Custom meshes: `--models`.
Example (sail, net, pressure 0.9): max displacement changes +0.06 % / +0.14 %, max stress +0.56 % / +0.08 % from
8×8 → 16×16 → 32×32; the minimum stress (a corner peak) changes −13 % / −5 % and converges slowest.

### `scripts/benchmarks.py`: validation benchmarks
```bash
python3 benchmarks.py            # all cases, prints the validation table and timings (~2 min)
python3 benchmarks.py --quick    # coarse meshes (~15 s)
python3 benchmarks.py --case hencky fichter square catenoid cable_point cable_udl cable_catenary wrinkling airbag \
                             sail_us newton speed
```
Reproduces `reference/validation.md` on the user's machine; exit code 1 if a check fails.

## Validation summary (details and sources: `reference/validation.md`)
All results [C]: computed by `benchmarks.py` / the tests against the cited independent references.
| Benchmark | Tool | Result |
|---|---|---|
| Hencky clamped circular membrane (Fichter 1997 series, ν = 0.3) | CST | w₀ +0.12 %, centre N_r −1.6 %, edge N_r +0.2 % (217 nodes) |
| Same with follower pressure, q = 0.01 (Fichter 1997 table) | CST | centre N_r −2.9 % (217 nodes), −2.1 % (469 nodes) |
| Prestressed square, n∇²w = −p, w_max = 0.07367·p·a²/n (Navier) | net and CST | −1.25 % (8×8), −0.36 % (16×16), −0.19 % (24×24), O(h²) |
| Catenoid between rings, r = c·cosh(z/c) | FDM `--uniform-stress` | max radius error 4e-4 → 1e-4 → 2.5e-5 (R = 1), O(h²); plain linear FDM: −17 % neck |
| Cable point load / load on plan / self-weight (Irvine 1981) | net DR | < 1e-5 / 0.03 % / 0.03 % |
| Tension field: uniaxial, off-axis orthotropic, Wagner shear panel | CST wrinkling | exact (≤ 1e-7) |
| **Published** inflated square airbag (Jarasjarungkiat, Wüchner & Bletzinger 2009 et al., tabulated in arXiv:2504.03400) | CST Newton + wrinkling, partial supports | w_M +0.39 % (8×8), +0.11 % (16×16 vs 10×10); u_B +1.6/+2.3 %; σ₁(M) +3.1/+1.8 % |
| Cable-edged sail, uniform stress: edge cable radius = T/σ | FDM `--us-method cst` | 0.45 % → 0.14 % → 0.04 % (n = 8/16/32), O(h²); zero CST drift |
| Newton vs DR (Hencky, square, sail 16×16 and 30×30) | CST | same equilibrium (≤ 1e-5 m, 6 digits on the references) |

Net (cable-net analogy) versus CST: with a uniform isotropic prestress on a regular grid the two give the same answer
(the CST geometric stiffness equals the 5-point Laplacian of the net); they differ where fabric shear stiffness, Poisson
coupling and wrinkling matter. On the 10 m test sail under 0.9 kN/m² uplift the CST gives 14–19 % smaller deflection than
the net [C: tool output, n = 10–30], and the existing chain test bounds the ratio to 0.6–1.2.

## Performance (one CPU, pure Python; `validation.md` §Timings)
Measured times [C] (this container, Python 3.11); "was" = previous implementation, identical results.
| Mesh (sail4) | FDM | net DR, 0.9 kN/m² | CST DR, prestress + 0.9 kN/m² | CST `--solver newton` |
|---|---|---|---|---|
| 10×10 (121 nodes) | 0.01 s | 0.2 s (was 0.6 s) | 1.0 s (was 2.6 s) | 0.12 s |
| 20×20 (441 nodes) | 0.06 s | 1.6 s (was 5.3 s) | 10 s (was 24.8 s) | 0.7 s |
| 30×30 (961 nodes) | 0.1 s | 5.5 s (was 17.3 s) | 33 s (was ~100 s) | 4.0–4.4 s |
| 50×50 (2601 nodes) | 0.55 s | — | minutes | 14 s |
FDM: matrix-free Jacobi-PCG, three coordinates in one edge loop (60×60: 0.9 s; 100×100: 3.7 s). DR: flat arrays, O(edges +
faces) per iteration, iterations grow about linearly with the mesh side. Newton: ~11 iterations at every mesh size,
cost dominated by the banded Cholesky (~N²): use it for the CST on any mesh above ~12×12; beyond ~80×80 a commercial
solver is the practical choice. Uniform-stress `cst` form finding: 0.2 s (8×8), 0.8 s (16×16), 7 s (32×32).

## Limitations (state them in any report)
**Fit for:** concept design, form exploration, screening of load cases, order-of-magnitude reactions for steel and
foundations, independent verification of a commercial model (deflection, stresses, cable forces within the accuracy
above), teaching. **Not a replacement** for Easy, SOFiSTiK, ixForten, RFEM or another validated membrane package for
final design, and not for permit calculations on its own.
- Material: linear-elastic orthotropic (one set of E·t, ν, G); no non-linear/hysteretic fabric law, no load-history,
  creep or prestress loss, no crimp interchange beyond the constant ν; temperature effects not included.
- Elements: CST membrane (no bending, no shell action); net solver ignores shear and Poisson coupling entirely. Stresses
  are element (CST) or link (net) averages: peaks at corners, clamp plates and supports need a finer local mesh or a
  local model; corner/edge minima converge slowest (mesh_convergence.py).
- Form finding: linear FDM (shape from q ratios; stress uniform only on an "isotropic" grid) or the isotropic
  uniform-stress iteration (`cst`: robust on sails and arch ends; not realisable on tall cones, fails on the multibay
  generator). No anisotropic URS (warp/weft ratio ≠ 1), no seam/patterning-driven form.
- Tension-field equilibria are not unique on coarse meshes (airbag 8×8: DR and Newton stop at two different wrinkle
  patterns, w 0.2220 vs 0.2174 m, the lower-energy one is Newton's); compare two meshes on wrinkle-dominated cases.
- Analysis: static, quasi-static wind; no dynamic or aeroelastic response, no fluid–structure interaction, no
  buckling/flutter, follower-load stiffness not used in the prestress relaxation. Cables are straight tension-only links
  (no sag within a segment, no friction at clamps/saddles). Supports are rigid unless the steel is modelled.
- Wrinkling: tension-field model gives the stress state and wrinkled area, not the wrinkle wavelength/amplitude.
- Ponding: fill-to-spill with blocked drains (conservative), water as nodal loads on the current geometry.
- Loads: the user supplies Cp, snow shapes and factors; tools do not apply code partial factors (cases file `factor`).
- Units kN, m; stresses kN/m; defaults E_w·t 800, E_f·t 600 kN/m, ν 0.3, G·t 30 kN/m, EA 14 000 kN are illustrative
  [U: PES/PVC family defaults of `membrane-fabric/reference/materials.json` are 800/600 kN/m, glass/PTFE 1400/1000,
  glass/silicone 1000/800 ("typical"); G·t is small and must come from tests, run a sensitivity with G·t halved and
  doubled; cable EA from the supplier]. Use `biaxial_fit.py` and supplier data.

## Method summary (details: `reference/form-finding-methods.md`)
- **FDM** (Schek 1974): q = F/L makes equilibrium linear: `D x = p − D_f x_f`, with `D = CᵀQC` (SPD if all q > 0 and every
  free node is connected to a support). Solve x, y, z separately. Non-linear FDM iterates q ← F_target/L.
- **DR** (Day 1965, Barnes 1999): fictitious masses M_i = λ(Δt²/2)S_i with S = EA/L₀ + T/L; leapfrog integration; kinetic
  damping (reset velocities at the KE peak). No stiffness matrix, so it handles slack, large displacement and form finding.
- **URS** (Bletzinger and Ramm 1999): homotopy blend of Cauchy stress on the current geometry with PK2 on the reference,
  updating the reference until they coincide. Handles anisotropic prestress on continuum membranes. On cable nets it is
  equivalent to FDM.
- Soap film (isotropic, zero mean curvature) versus anisotropic prestress: an arbitrary anisotropic field is generally not
  realisable, so it needs stabilisation.
- Equilibrium check: `n₁/R₁ + n₂/R₂ = p`; with p = 0, `n_w/R_w = n_f/R_f`.

## Analysis rules (details: `reference/analysis-and-loads.md`)
1. **Geometrically non-linear**, large displacement; K_T = K_E + K_G. **No superposition.** Apply partial factors before each run.
2. Membrane: CST or quad membrane elements without bending; orthotropic E_w·t, E_f·t, ν, G from biaxial tests; tension-field or wrinkling model.
3. Cables: tension-only, EA from the supplier (prestretched), temperature through L₀(T).
4. Steel: include masts, rings and arches (their flexibility changes the prestress); or iterate the support displacements.
5. Load cases: PS (initial and relaxed), G, S (uniform, drift, asymmetric, ponding), W (several directions, ±; no code Cp for
   hypars and cones, so use tunnel data, TensiNet guidance or conservative canopy/vault values; dynamic/aeroelastic for large roofs), T, erection.
6. Results to check: warp/weft/principal stress, min stress (slack), deflection versus clearance, **ponding** (load follows
   the deformed shape), cable max/min, reactions (envelopes and concurrent sets).
7. Mesh: run `mesh_convergence.py` on the governing case before reporting peaks.

## Software guide (details: `reference/software-guide.md`)
| Need | Typical choice |
|---|---|
| Full commercial chain (form → analysis → patterns) | Easy (technet), ixForten 4000, SOFiSTiK + TEXTILE, RFEM 6 + Form-Finding + Cutting Pattern, Forten32, WinTess3, K3-Tent, inTENS, Tensyl (Buro Happold in-house) |
| Design exploration | Rhino + Grasshopper + Kangaroo2 (goal solver), Karamba3D (approximate) |
| Fabricator patterning | MPanel (Rhino/AutoCAD) |
| General non-linear FE / research | ANSYS, LS-DYNA (*MAT_FABRIC), Oasys GSA (DR, soap-film form finding) |
| Steel design of supports | RFEM, SOFiSTiK, Robot, Tekla Structural Designer, SAP2000 |
| Python | these scripts; COMPAS + compas_fd; JAX-FDM; libigl (LSCM/ARAP), potpourri3d (geodesics), ezdxf |

Different packages give noticeably different answers for the same membrane: the TensiNet round robin (Gosling et al.
2013, Eng. Struct. 48:313–328) reported "very high levels of variability in terms of stresses, displacements, reactions"
[V]. Validate any tool (including these) on the benchmarks above before trusting it.

## Handover
- To `membrane-fabric`: max warp/weft stress per combination → `membrane_check.py`.
- To `cable-tension-members`: cable forces (max, min) → `cable_calc.py resist`, `cable_schedule.py --from-model`.
- To `steel-supports` / `tensile-connections`: `reactions[].pull` per combination → mast, corner-plate, pin and foundation checks.
- To `fabrication-drawings`: the form-found mesh (prestress geometry) → `cutting_pattern.py`, `export_dxf.py`.
