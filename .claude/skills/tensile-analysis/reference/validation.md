# Validation of the tensile-analysis tools

Every computational path of `scripts/form_find_fdm.py`, `scripts/dynamic_relaxation.py`, `scripts/membrane_dr.py`,
`scripts/run_cases.py` and `scripts/mesh_convergence.py` is checked against an independent reference (closed-form
solution, published series/table, or exact statics) in `tests/test_tensile_analysis.py`
(`python3 -m unittest tests.test_tensile_analysis -v`, about 25 s). `membrane_dr.py` has two solvers for the same
residual, `--solver dr` (default) and `--solver newton`; each is validated separately. The reference values are computed in the test file
itself, not by the tools. `scripts/benchmarks.py` reruns the same cases at finer meshes and prints this table (exit
code 1 on a failure). Older regression and statics tests stay in `tests/test_tools.py` (patch test, simple shear, ponding
bowl, sail equilibrium) and in the hub (`tensile-structures/reference/validation.md`: chain statics).

## Sources
- **[F97]** Fichter, W.B. (1997) *Some solutions for the large deflections of uniformly loaded circular membranes*,
  NASA TP-3658, https://ntrs.nasa.gov/citations/19970023537 — corrected Hencky (1915) power series, eqs. (12a,b),
  (20)–(29), (30)–(31), (34); table "b0": ν = 0.2/0.3/0.4 → 1.6827/1.7244/1.7769; table of N_r(0)/(Eh) for Hencky's
  problem (lateral load) and for uniform (follower) pressure. Coefficient b8 is illegible in the scan; it is
  re-derived from recurrence (17): b8 = −17/(18 b0¹¹), and the whole series is checked against the published b0, the
  a2n coefficients of eq. (34) and the stress table (`TestReferencesThemselves`).
- **[NAV]** Navier double-sine-series solution of n∇²w = −p on a square with w = 0 on the edges:
  w(a/2, a/2) = (16 p a²/(π⁴ n)) Σ_{m,k odd} sin(mπ/2) sin(kπ/2)/(m k (m² + k²)) = 0.07367 p a²/n (series evaluated in the
  test). Cross-check through the Prandtl membrane analogy: torsion constant of a square of half-side c, J ≈ 2.25 c⁴
  (Roark's Formulas for Stress and Strain, 7th ed., quoted at https://en.wikipedia.org/wiki/Torsion_constant)
  = 4∫∫w dA·n/p, reproduced to 3 digits.
- **[CAT]** Catenoid (Euler 1744): the minimal surface between coaxial rings of radius R at z = ±h is r = c·cosh(z/c) with
  R = c·cosh(h/c), stable (larger) root; e.g. https://en.wikipedia.org/wiki/Catenoid.
- **[IRV]** Irvine, H.M. (1981) *Cable Structures*, MIT Press (Dover 1992): ch. 1 (straight segments, point loads),
  ch. 2 elastic catenary span = H·L0/EA + 2(H·L0/W)·asinh(W/2H), mid sag W·L0/(8EA) + (H·L0/W)(√(1+(W/2H)²) − 1);
  parabolic funicular of a load per horizontal length.
- **[TF]** Tension-field theory: Wagner (1929); Mansfield, *The Bending and Stretching of Plates*, 2nd ed., CUP 1989;
  Roddeman, Drukker, Oomens & Janssen, "The wrinkling of thin membranes: Part I — Theory", *J. Appl. Mech.* 54 (1987)
  884–887. Orthotropic off-axis compliance: Jones, *Mechanics of Composite Materials*, 2nd ed., 1999, §2.6.
- **[AB]** Inflated square airbag (published full-structure benchmark): Bauer et al. (1975); Contri, P. & Schrefler,
  B.A. (1988) *A geometrically nonlinear finite element analysis of wrinkled membrane surfaces by a no-compression
  material model*, Commun. Appl. Numer. Methods 4:5–15; Kang, S. & Im, S. (1999) CMAME 173:227–240; Jarasjarungkiat,
  A., Wüchner, R. & Bletzinger, K.-U. (2009) *Efficient sub-grid scale modeling of membrane wrinkling by a projection
  method*, CMAME 198:1097–1116. Model data and all values used here are taken from the comparison tables of Zhang, Y.
  & Kiendl, J., *A variationally consistent membrane wrinkling model based on spectral decomposition of the stress
  tensor*, arXiv:2504.03400 (2025), §5.4, Tables 1–2 (https://arxiv.org/abs/2504.03400): diagonal AC = 120 cm,
  t = 0.06 cm, E = 588 MPa, ν = 0.4, follower pressure 5000 Pa, quarter model, symmetry on the inner edges, outer edges
  held in the mid-plane (u_z = 0). Published w_M (vertical displacement of the centre M) [m]: 8×8 meshes 0.2050 (C&S),
  0.2140 (K&I), 0.2166 (JWB); 10×10: 0.2167 (JWB), 0.2167 / 0.2163 (Z&K strain / mixed). σ₁ at M: 3.8 MPa (JWB 8×8 and
  10×10). u_B: 0.1227 (JWB 8×8), 0.1237 (JWB 10×10).
- **[PP]** Pinkall, U. & Polthier, K. (1993) *Computing discrete minimal surfaces and their conjugates*, Experimental
  Mathematics 2(1):15–36 — cotangent formula for the area gradient of a triangle mesh (= isotropic CST stress) and the
  iterative minimisation used by `--us-method cst`. Bletzinger, K.-U. & Ramm, E. (1999) *A general finite element
  approach to the form finding of tensile structures by the updated reference strategy*, Int. J. Space Struct. 14(2).
- **[CR]** Cable on a soap film: equilibrium of a cable element with constant tension T loaded by a membrane stress σ
  normal to it gives T·κ = σ, i.e. radius R = T/σ (also `form-finding-methods.md`: T = n·R).
- **[ST]** Statics: total support reaction = integral of the applied pressure over the plan (midpoint rule exact for a
  linear field on each triangle).

## Validation table
Material for the membrane benchmarks: isotropic E·t = 1000 kN/m, ν = 0.3 (Hencky); E·t = 800 kN/m, prestress n = 2 kN/m
(square). DR tolerances are set to ~10⁻⁷ of the nodal load. "Error" = obtained/expected − 1.

| Tool | Case | Reference + source | Expected | Obtained | Error | Tolerance |
|---|---|---|---|---|---|---|
| `membrane_dr.py` (CST, snow = lateral load) | Hencky, q = pa/Et = 10⁻³, w₀/a, 217 nodes | [F97] series, w₀ = 0.6534·a·q^⅓ | 0.065345 | 0.065426 | +0.12 % | 1 % |
| same | centre N_r/(Et), 217 nodes | [F97] series and table 0.00431 | 0.004311 | 0.004242 | −1.60 % | 2.5 % |
| same | edge N_r/(Et) of the outer-ring elements, 217 nodes | [F97] series at the element centroid radius | 0.003467 | 0.003473 | +0.18 % | 2 % |
| same, 469 nodes | w₀/a; centre N_r; edge N_r | [F97] | 0.065345; 0.004311; 0.003423 | 0.065438; 0.004275; 0.003438 | +0.14 %; −0.85 %; +0.45 % | 1 %; 2 %; 3 % (benchmarks.py) |
| `membrane_dr.py` (CST, follower pressure) | q = 0.01, centre N_r/(Et), 217 / 469 nodes | [F97] table, uniform pressure, ν = 0.3: 0.0207 | 0.0207 | 0.02010 / 0.02026 | −2.9 % / −2.1 % | 4 % / 5 % |
| same (snow) | q = 0.01, centre N_r/(Et), 217 / 469 nodes | [F97] table, Hencky: 0.0200 | 0.0200 | 0.01954 / 0.01970 | −2.3 % / −1.5 % | 4 % / 5 % |
| same | ratio follower / lateral load, q = 0.01 | [F97] table 0.0207/0.0200 = 1.035 | > 1.01 | 1.029 | — | > 1.01 |
| `dynamic_relaxation.py` (net) | prestressed flat square 10 m, n = 2 kN/m, p = 0.002 kN/m², w·n/(p a²), 8×8 / 16×16 / 24×24 | [NAV] 0.073671 | 0.073671 | 0.072747 / 0.073409 / 0.073533 | −1.25 % / −0.36 % / −0.19 % | 1.5 % / 0.5 % / 1 % |
| `membrane_dr.py` (CST) | same, 8×8 / 12×12 / 16×16 / 24×24 | [NAV] | 0.073671 | 0.072736 / 0.073224 / 0.073398 / 0.073523 | −1.27 % / −0.61 % / −0.37 % / −0.20 % | 1.5 % / 0.8 % / 1 % / 1 % |
| `form_find_fdm.py --uniform-stress` | catenoid R = 1, h = 0.4: max \|r − c·cosh(z/c)\| over all nodes, meshes 4×16 / 8×32 / 16×64 / 32×128 | [CAT] c = 0.910738 | 0 | 4.0e-4 / 1.0e-4 / 2.5e-5 / 6.3e-6 | O(h²), ratio 4.0 | < 5e-5 at 16×64, ratio > 3.5 |
| same | neck radius, 16×64 | [CAT] | 0.910738 | 0.910760 | +0.002 % | 0.1 % |
| same, CLI `rings` | R = r = 5, H = 3, σ = 2 kN/m: ring axial force = σ·2π·c; membrane stress | [CAT] | 59.84 kN; 2.00 | 59.82 kN; 2.00–2.00 | −0.03 % | 1 % |
| `form_find_fdm.py --uniform-stress --us-method cst` | catenoid R = 1, h = 0.4: max \|r − c·cosh(z/c)\|, 4×16 / 8×32 / 16×64 / 32×128 | [CAT] | 0 | 3.7e-3 / 9.1e-4 / 2.3e-4 / 5.6e-5 | O(h²), ratio 4.0 | neck 0.5 % / 0.15 % / 0.15 %; test: < 1.2e-3 at 8×32, ratio > 3.5 |
| same, sail4 10 m, high 3 m, σ = 2 kN/m, T = 16 kN (free cable edges) | curvature radius of edge cable EC-S at every interior node / (T/σ), worst node, n = 8 / 16 / 32 | [CR] R = T/σ = 8 m | 1 | 1.0045 / 1.0014 / 1.0004 | +0.45 % / +0.14 % / +0.04 %, O(h²) | 0.5 % / 0.15 % / 0.06 % |
| same | form-found sail fed to `membrane_dr.py --prestress 2 2` (CST): prestress relaxation drift; stress range | exact CST equilibrium (cot formula [PP]) | 0 mm; 2.00–2.00 | 0.0 mm; 2.00–2.00 | — | drift < 0.5 mm, ±0.02 kN/m |
| same | sum of the four corner reactions (prestress only) | [ST] self-equilibrated | 0 | < 0.05 kN | — | 0.05 kN |
| `form_find_fdm.py` (linear, Jacobi-PCG) | uniform q between rings R = 2, H = 1.5, 10×24: radius r_j | closed form of the linear recurrence r_{j+1} + r_{j−1} = (4 − 2cos Δ) r_j: r_j = R·cosh(κ(j − nr/2))/cosh(κ·nr/2), cosh κ = 2 − cos(2π/nc) | exact | max diff 1.6e-14 m | 0 | 1e-8 m |
| same (contrast) | uniform q on the catenoid grid 8×32: neck radius | [CAT] | 0.9107 | 0.7562 | −17 % | shows plain FDM ≠ minimal surface |
| `dynamic_relaxation.py` (`relax`) | cable L = 10 m, EA = 10 000 kN, pretension 10 kN, P = 5 kN at mid-span, 20 segments: sag; tension | [IRV] ch. 1, two straight segments, bisection on θ in the test | 0.35542 m; 35.258 kN | 0.35542 m; 35.258 kN | < 1e-5 | 1e-5 |
| same | load per horizontal length w = 1 kN/m, unstressed 10.25 m, EA 20 000 kN, 40 segments: H; sag; nodes on y = w·x(L−x)/(2H) | [IRV] parabola, H from the elastic length integral (Simpson, test-side) | 12.599 kN; 0.99216 m; 0 | 12.595 kN; 0.99246 m; < 1e-9 m | −0.03 %; +0.03 %; exact | 0.2 %; 1e-6 |
| same | self-weight W = 10 kN on unstressed 10.25 m (equal loads on equal unstressed segments): H; sag | [IRV] elastic catenary closed form | 12.473 kN; 0.98963 m | 12.469 kN; 0.98993 m | −0.03 %; +0.03 % | 0.2 % |
| `membrane_dr.py` `wrinkle` | warp tension σ = 8 kN/m with excess lateral contraction β = 0.01 (E_w·t 800, E_f·t 600, ν 0.3, G·t 30) | [TF] uniaxial: σ_w = E_w·t·ε_w, σ_f = τ = 0 (linear law gives σ_f = −6.43, σ_w = 6.07) | 8, 0, 0 | 8, 0, 0 | < 1e-9 | 1e-9 |
| same | off-axis uniaxial σ at 30° / 75° / −40° + wrinkle strain | [TF] + [Jones] off-axis compliance: stress = σ·n⊗n, minor principal 0 | e.g. 3.75, 1.25, 2.165 | same | < 1e-7 | 1e-7 |
| same | all strains negative | slack: zero stress | 0, 0, 0 | 0, 0, 0 (flag 2) | exact | exact |
| `membrane_dr.py` (relax + wrinkling) | Wagner shear panel, isotropic, pure shear γ = 0.02 imposed on the boundary: shear flow S12 | [TF] diagonal tension σ₁ = E·t·ε₁ (ε₁ = γ/2 + γ²/8 Green), τ = σ₁/2 (linear membrane: G·t·γ = 6.15) | 4.0200 | 4.0200 | < 1e-6 | 1e-6 |
| `membrane_dr.py --solver newton` | Hencky q = 10⁻³, 217 nodes: w₀/a; centre N_r | [F97] | 0.065345; 0.004311 | 0.065426; 0.004242 (= DR to 6 digits) | +0.12 %; −1.6 % | 1 %; 2.5 % |
| same | follower pressure q = 0.01, centre N_r/(Et), 217 nodes | [F97] table 0.0207 | 0.0207 | 0.02010 | −2.9 % | 4 % |
| same | prestressed square 8×8 / 16×16: w·n/(p a²) | [NAV] 0.073671 | 0.073671 | 0.072736 / 0.073398 (= DR) | −1.27 % / −0.37 % | 1.5 % / 0.5 % |
| same | 10 m sail 16×16 (and 30×30 in benchmarks.py), 0.9 kN/m² uplift: nodes, max n₁, reactions vs DR | DR result (same residual) | — | max node difference ~1e-5 m, n₁ ±2e-4 kN/m, reactions ±2e-3 kN, same wrinkled count | — | 1e-4 m; 2e-3 kN/m; 5e-3 kN |
| same | demo sail (`examples/run_demo.sh`, sail4 16×16, qc 12, prestress 2): uplift 0.9 / snow 0.75 + ponding / down 0.6 kN/m² vs DR | DR result | — | max displacement 723 / 658 / 577 mm both; max n₁ equal to 1e-3 kN/m; nodes ≤ 2e-5 m; reactions ≤ 1.5e-3 kN; 0.4 s vs 4.9 s | — | (benchmark run) |
| same | every factorisation made to fail (test) | DR fallback must take over | DR result | fallback used, same max displacement | < 1e-4 m | 1e-4 m |
| `membrane_dr.py` skyline Cholesky | random SPD variable-band matrix, 40 equations; indefinite 2×2 | dense residual | 0; failure flag | < 1e-12; False | — | 1e-12 |
| `membrane_dr.py --solver newton`, partial supports (`"fix"`) | **published airbag** [AB], quarter 8×8 quads (128 CST): w_M; u_B; σ₁ at M | JWB 2009 8×8 (Z&K Table 1–2) | 0.2166 m; 0.1227 m; 3.8 MPa | 0.21744; 0.12468; 3.92 | +0.39 %; +1.6 %; +3.1 % | 1 %; 3 %; 5 % |
| same | quarter 16×16 (512 CST, benchmarks.py) vs finest published 10×10 | JWB 2009 / Z&K 10×10 | 0.2167; 0.1237; 3.8 | 0.21695; 0.12656; 3.87 | +0.11 %; +2.3 %; +1.8 % | 1 %; 3 %; 5 % |
| `run_cases.py` (gradient, zones, factor) | flat 10 m square, gradient 0.02 → 0.01 kN/m² × 1.5; zone 0.03 on 4 m strip + 0.01 elsewhere: Σ vertical support pull | [ST] 1.5·100·0.015 = 2.25 kN; 0.03·40 + 0.01·60 = 1.80 kN | 2.25; 1.80 | 2.249999; 1.79996 | −5e-7; −2e-5 | 0.2 % |
| `mesh_convergence.py` (`richardson`) | f(h) = 1 + h² at h = 1, ½, ¼ | analytic: order 2, limit 1 | 2; 1 | 2; 1 | < 1e-9 | 1e-9 |
| `mesh_convergence.py` (q scaling) | sail4 n = 8 → 16, qc 12, form finding only: max cable force ratio; with `--keep-qc` | [ST] link force = q·L: scaled q keeps the force, fixed q halves it | ≈ 1; ≈ 0.5 | 1.00; < 0.7 | — | ±5 %; < 0.7 |
| `dynamic_relaxation.py` ponding | 3×3 bowl, centre 1 m below the rim | exact fill-to-spill depth | 1.0 m | 1.0 m | 0 | exact (`tests/test_tools.py`) |
| `benchmarks.py` | references themselves | [F97] b0 = 1.7244 (ν = 0.3), eq. (30) residual, table N_r(0); [NAV] 0.07367 and J = 2.25c⁴ | as published | as published | < 2e-4 | 1e-3 |

Fast kernels (flat arrays) are additionally checked to reproduce the original dictionary-based formulation
(`external_loads`, `element_state`) to 1e-9 (`test_fast_kernels_match_reference_formulation`); this is a regression
check, not a validation.

## Mesh convergence
Prestressed square (Poisson problem), error of w_max: net −1.25 % → −0.36 % → −0.19 % (8 → 16 → 24 divisions), CST
−1.27 % → −0.37 % → −0.20 %. Observed order ≈ 1.8 (O(h²) expected for the 5-point Laplacian). The CST on a
regular split-quad mesh with uniform isotropic stress has the same geometric stiffness as the net (its linear-triangle
Laplacian is the 5-point stencil), so both converge to the same discrete values; the difference (≤ 0.01 %) is the
elastic stiffening of the CST (Poisson, shear) at this tiny load.

Hencky (CST): w₀ error −0.01 % / +0.12 % / +0.14 % at 61 / 217 / 469 nodes; centre N_r −5.5 % / −1.6 % / −0.85 % (the
centre value is the mean of the six elements around the centre, i.e. an average over ρ ≈ 0.1–0.2, where N_r is
lower). w₀ converges to +0.14 % above the series: the CST uses Green strain and PK2 stress (exact kinematics) while
Hencky's equations use the Föppl approximation; the difference is of the order of the strain (0.4 %).

Catenoid (uniform-stress FDM): max radius error 4.0e-4, 1.0e-4, 2.5e-5, 6.3e-6 for 4×16 … 32×128 — exactly O(h²).

Sail4 10 m, high 3 m, qc 12 at n = 8, uplift 0.9 kN/m² (`mesh_convergence.py`, qc scaled with the mesh):

| Solver | Levels | Max displacement | Max stress | Min stress | Max cable force | Max reaction |
|---|---|---|---|---|---|---|
| net | 8 → 16 → 32 | 1022 → 1023 → 1024 mm (+0.06 %, +0.14 %) | 7.30 → 7.34 → 7.34 kN/m (+0.56 %, +0.08 %) | 4.66 → 4.12 → 3.92 (−13 %, −5.1 %) | 96.6 → 97.0 → 97.2 kN | 167.5 → 169.1 → 169.8 kN |
| CST | 8 → 16 → 24 | 866 → 871 → 872 mm (+0.53 %, +0.20 %) | n₁ 9.51 → 9.32 → 9.16 kN/m (−2.1 %, −1.7 %) | n₂ = 0 (wrinkled: 6 → 22 → 48 elements) | 93.4 → 94.3 → 94.6 kN | 157.1 → 157.6 → 157.6 kN |

Uniform-stress sail (`--us-method cst`, T = 16 kN, σ = 2 kN/m): edge-cable sag 1.9039 / 1.9090 / 1.9103 m at
n = 8 / 16 / 32 (changes −0.27 %, −0.07 %, ratio 4.1 → O(h²); Richardson 1.9107 m); cable radius error 0.45 % → 0.14 %
→ 0.04 % (above). The cable is not a plane circle (its torsion is not zero), so the chord/sag relation of a circle
(1.938 m) does not apply; the curvature check is the exact one.

Global quantities converge fast; local stress extremes (corner minimum, peak n₁ next to the corners) converge slowly,
and the wrinkled region is resolved better on finer meshes. Report peaks from a converged mesh or say how they changed.

## Published full-structure benchmark: inflated square airbag [AB]
Why this case: it is a complete structure (not a closed-form special case) with fully published model data, it was
solved independently by several groups (including Wüchner & Bletzinger's group), and it exercises everything the CST
tool does: large displacement from a flat, unstressed start (singular initial stiffness), follower pressure,
Green-strain/PK2 St. Venant–Kirchhoff material, and wrinkling over most of the edge region (368 of 512 elements
wrinkled at 16×16). Model here (`benchmarks.py airbag_model`): quarter square of side 0.4243 m, n×n quads split into
CST, E·t = 352.8 kN/m, ν = 0.4, G·t = E·t/2.8, p = 5 kN/m² follower, node supports per component (`"fix"`): x = 0 →
u_x = 0, y = 0 → u_y = 0, outer edges → u_z = 0.

| Mesh (quarter) | w_M [m] here | Published (same mesh size) | u_B [m] here / JWB | σ₁(M) [MPa] here / JWB |
|---|---|---|---|---|
| 4×4 (32 CST) | 0.2205 | 0.2090 (C&S), 0.2150 (K&I), 0.2149 (JWB) | 0.1284 / 0.1202 | 3.59 / 3.2 |
| 8×8 (128 CST) | 0.21744 | 0.2050 (C&S), 0.2140 (K&I), 0.2166 (JWB) | 0.1247 / 0.1227 | 3.92 / 3.8 |
| 12×12 (288 CST) | 0.21700 | — | 0.1250 / — | — |
| 16×16 (512 CST) | 0.21695 | 10×10: 0.2167 (JWB), 0.2167 / 0.2163 (Z&K) | 0.1266 / 0.1237 (10×10) | 3.87 / 3.8 |

Agreement: w_M converges to 0.2169–0.2170 m, +0.1 % above the finest published values (0.2163–0.2167), and inside the
published spread at every mesh. Differences and their reasons: (1) element type: linear triangles here versus
bilinear quads in the references, so the same "8×8" is a different discretisation (the 4×4 row shows the coarse CST
is stiffer in a different way); (2) wrinkling models differ (Contri & Schrefler: no-compression stress model,
JWB: projection with sub-grid scale, Z&K: spectral decomposition; here the mixed stress/strain criterion with an exact
uniaxial tension field), which mainly affects the in-plane edge displacements; (3) σ₁ at M is the mean of the elements
around the centre here (the references quote a nodal/Gauss value), +2–3 %. The corner displacement r_A is NOT used as a
check: the source text does not define it precisely and the published values scatter from 0.047 to 0.097 m between
models and meshes (here 0.049 m, inside that range). Definitions used: M = centre, B = mid-point of the outer edge on
the x axis (u_B = inward x-displacement), A = outer corner (r_A = inward move along the diagonal) [interpretation].

Non-uniqueness found by this benchmark: the tension-field equations can have more than one equilibrium on coarse
meshes. At 8×8 the explicit DR (tol 10⁻⁶ kN) stops at w_M = 0.2220 m, the Newton solver at 0.2174 m; both have a
residual below the tolerance, but the potential Π = U − p·V is lower for the Newton state (−0.077167 vs −0.076649 kJ),
so the DR state is a metastable wrinkle pattern. At 16×16 both solvers give the same state (0.21695 m, same Π). Advice:
on wrinkle-dominated problems compare two meshes (and, if in doubt, both solvers).

Tolerance note: with an unstressed flat start and many wrinkled elements the Newton residual stalls near 3·10⁻⁵ kN at
16×16 (elements switching between taut and wrinkled); with `--tol 1e-5` it converges (3.2 s); with 10⁻⁷ it falls
back to DR (same answer, minutes). DR alone needs 166 000 iterations (266 s) at 16×16.

## Cable-net analogy versus CST (honest comparison)
- Identical answers when the prestress is uniform and isotropic on a regular grid and the load is small (square test).
- The net has no shear stiffness and no Poisson coupling. On the 10 m sail under 0.9 kN/m² the net deflects 14–19 % more
  than the CST (959/820, 804/679, 744/603 mm at n = 10/20/30 with the same qc) and its link stresses are lower than the
  CST principal stresses (7.3 vs 9.2–9.5 kN/m); cable forces and reactions agree within ~3–7 %.
- The net cannot represent wrinkling except as slack links; the CST tension-field model is exact for linear
  orthotropy (checked above).
- Use the net for fast screening of many cases, the CST for the governing cases and for stresses.

## Derivation used by the wrinkling model (for review)
With elastic strain ε (Green strain plus the prestress pre-strain C·S₀) and compliance C (C11 = 1/E_w t, C22 = 1/E_f t,
C12 = −ν_wf/E_w t, C66 = 1/G t), a wrinkled state is σ·n⊗n with n = (cos θ, sin θ) and a wrinkling strain −β·m⊗m
(m ⟂ n, β ≥ 0). Projections: ε_nn = σ·C_nn(θ) (wrinkling strain has no nn part) and ε_nm = σ·C_nm(θ) (nor an nm part),
with C_nn = C11c⁴ + (2C12 + C66)c²s² + C22s⁴, C_nm = ((C12 − C11)c² + (C22 − C12)s²)cs + ½C66·cs(c² − s²). θ is the
root of ε_nm − ε_nn·C_nm/C_nn = 0 (Newton from the previous θ of the element, scan + bisection fallback), with σ > 0 and
β = σ·C_mm − ε_mm ≥ 0. For isotropy C_nm ≡ 0, so n is the principal strain direction and σ = E·t·ε₁.

## Timings (one CPU, Python 3.11, this container)
| Mesh (sail4) | Nodes | FDM | Net DR, 0.9 kN/m² (iterations) | CST DR: prestress relax + 0.9 kN/m² (iterations) | CST Newton, same case (iterations / factorisations) |
|---|---|---|---|---|---|
| 10×10 | 121 | 0.01 s | 0.2 s (770); before: 0.6 s | 1.0 s (1920); before: 2.6 s | 0.12 s (11 / 7) |
| 20×20 | 441 | 0.06 s | 1.6 s (1590); before: 5.3 s | 10.1 s (5105); before: 24.8 s | 0.7 s (11 / 7) |
| 30×30 | 961 | 0.11 s | 5.5 s (2528); before: 17.3 s | 33 s (7758); before: ~100 s | 4.0–4.4 s (11 / 8) |
| 50×50 | 2601 | 0.55 s | — | not run (minutes) | 14 s (11 / 8) |
| 60×60 / 100×100 | 3721 / 10 201 | 0.9 s / 3.7 s | — | — | — |

Other Newton timings: Hencky 469 nodes 1.2 s (DR 6.0 s); prestressed square 24×24 0.35 s (DR 16 s); airbag 16×16
3.2 s (DR 266 s). Newton cost: one skyline Cholesky ≈ 0.5 s at 30×30 (2871 equations, profile 272 000; the
smaller of the RCM and the input numbering is used), O(N·b²) so ~N² for square grids; DR cost ~N^1.5. Newton iteration
counts do not grow with the mesh (11 at 10×10 … 50×50).

"Before" = the previous (dictionary-based) implementation with identical results (`--no-wrinkling` CST and the net give
bit-identical output; the CST with wrinkling differs only through the corrected tension-field law). The 30×30 form finding
plus one net DR load case is asserted to take < 5 s + < 45 s in `test_30x30_formfind_and_dr_load_case`.
Remaining cost driver: explicit DR needs O(n_side) iterations, each O(elements) in pure Python; Newton is dominated by
the banded factorisation (pure Python), so beyond ~80×80 a sparse direct solver (nested dissection) would be needed.

## Not validated / open
- No published benchmark with agreed numbers was found for a complete fabric SAIL or HYPAR with cables: the TensiNet
  round robin (Gosling et al. 2013, *Eng. Struct.* 48:313–328) reports "very high levels of variability" between
  participants rather than reference values. The published full-structure check is the airbag above (membrane +
  wrinkling + follower pressure, no cables). The hypar cable-net test of Lewis, Jones & Rushton (1984) (experimental
  and DR displacements reproduced in arXiv:2401.05609, Table 9) could not be used: the node coordinates are not given
  in an accessible source. A comparison with Easy / SOFiSTiK / ixForten on a real project is still recommended.
- `--uniform-stress --us-method cst` is validated on the sail (cable radius, CST equilibrium) and the catenoid; it
  stops with "degenerating mesh" on tall cones (an isotropic stress field is not realisable there) and on the multibay
  ridge/valley generator — use linear FDM for those. `--us-method width` on free cable-edged sails still degenerates at
  the corners (kept for rings / rigid boundaries, where it is validated).
- Newton: the follower-pressure stiffness is only its symmetric part, snow-on-plan stiffness is omitted, and wrinkled
  elements use a finite-difference tangent; these affect only the convergence rate, not the solution (same residual as
  DR, checked). Wrinkle-dominated unstressed starts can stall below ~10⁻⁴ of the nodal load (DR fallback, slow).
- Partial supports (`"fix"`) are implemented in `membrane_dr.py` only (not in the net DR or FDM).
- Ponding (beyond the bowl depth check), multibay/arch generators and the cone are checked by statics and symmetry in
  `tests/test_tools.py`, not against an independent closed form.
