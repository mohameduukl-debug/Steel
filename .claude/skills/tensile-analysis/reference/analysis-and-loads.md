# Structural analysis, loads and combinations

## 1. Formulation
* Geometrically non-linear (Total or Updated Lagrangian), Newton–Raphson with load steps, or DR. K_T = K_E + K_G.
  `membrane_dr.py` has both: `--solver dr` (default) and `--solver newton` (consistent K_T of the TL CST, tension-field
  tangent by central differences, symmetrised follower-pressure stiffness, energy line search, skyline Cholesky, DR
  fallback); they give the same equilibrium (`validation.md`).
* **No superposition.** Each factored combination is its own non-linear run. The reference is the prestressed state.
* Membrane elements: CST or 4–8 node membrane, no bending. Green–Lagrange strain E = ½(FᵀF − I). Material axes follow
  the warp and fill directions from the patterning mesh.
* **Wrinkling:** tension-field theory (Wagner 1929; Mansfield, *The Bending and Stretching of Plates*, 2nd ed. 1989;
  Roddeman et al., *J. Appl. Mech.* 54 (1987) 884–887) classifies points as taut (σ₂ > 0), wrinkled (uniaxial stress
  σ·n⊗n plus a stress-free wrinkling contraction across n) or slack (no positive strain), so compression vanishes.
  Mixed criterion used in `membrane_dr.py`: taut if σ₂(linear) ≥ 0, slack if ε₁(elastic) ≤ 0, else wrinkled with
  σ = ε_nn/C_nn(n) and n from ε_nm = σ·C_nm(n) [C: derivation in `validation.md`]. For an orthotropic fabric n is NOT the
  principal stress or strain direction. Wrinkled zones under SLS mean too little prestress or curvature.
* Cables: tension-only, N = EA(L − L0)/L0 if L > L0; K = (EA/L0)nnᵀ + (N/L)(I − nnᵀ). Temperature via
  L0(T) = L0,ref[1 + α(T − T_ref)]. Use the supplier's apparent modulus.
* Orthotropic plane stress (per unit width):
```
ε_w = σ_w/E_w − ν_fw σ_f/E_f;   ε_f = −ν_wf σ_w/E_w + σ_f/E_f;   γ = τ/G;   E_i ν_ij = E_j ν_ji
```
Constants from EN 17117-1 / MSAJ biaxial tests (load ratios 1:1, 2:1, 1:2, 1:0, 0:1 [C]). Apparent ν can exceed 1 from crimp
interchange. G is small; take it from tests and run a sensitivity (×0.5, ×2) [U].
Pick the constant set matching the governing load state.

## 2. Load cases
| Case | Notes |
|---|---|
| PS: prestress | always present; check initial and relaxed (creep) values |
| G: self-weight | fabric about 0.0025–0.017 kN/m² (0.25–1.7 kg/m², `membrane-fabric/reference/materials.json`) [C], plus fittings and lights |
| S: snow | s = μ_i C_e C_t s_k (EN 1991-1-3); uniform, drift, asymmetric; **ponding** iteration |
| W: wind | several directions, pressure and suction; see §3 |
| T: temperature | cables, steel; strength reduction at high temperature |
| Erection | partial prestress, staged lifting, temporary stability |
| Maintenance | point loads and local indentation |

Typical combinations (each solved non-linearly): PS+G; PS+G+S; PS+G+W↓; PS+G+W↑; PS+G+S+ψW; PS+G+W+ψS; PS+G+T;
SLS versions for deflection, ponding and slack. Partial factors: project code. Research calibration for one PVC hypar
type (De Smedt et al., "Reliability-based calibration of partial factors for the design of membrane structures",
*Eng. Struct.* 214 (2020) 110632, doi:10.1016/j.engstruct.2020.110632, abstract): prestress 1.0 with snow and wind
uplift 2.0, or prestress 1.2 if snow/wind keep 1.5 [V: abstract; valid for the structure type studied, not a code value].
Code factors used by the tools live only in `tensile-structures/reference/code_factors.json`.

## 3. Wind on membranes
* EN 1991-1-4: monopitch and duopitch canopies (c_p,net, c_f, blockage φ), vaulted roofs, domes; **no hypars or cones** [V].
* Options: conservative mapping of canopy/vault coefficients; published tunnel data (Colliers, Mollaert, Degroote,
  Rizzo); TensiNet App. A1; project boundary-layer tunnel tests (rigid pressure model); CFD (RANS or LES, validated).
* Dynamics: large added mass (`membrane-fabric` computes the coefficient per panel and mode from Lamb's baffled-plate
  theory: square 0.726, circular 0.746 [C: see its verification-log]) and aerodynamic damping. Buffeting and
  aeroelastic instability grow with lower prestress, higher turbulence and lower stiffness. Large roofs need aeroelastic tests or FSI. Canopies:
  quasi-static peak pressure with a dynamic factor.
* For preliminary DR runs: `--pressure +p` uplift and `--pressure −p` downward, with p = c_p,net × q_p (factored).

## 4. Snow and ponding
* Ponding: deflection removes the fall, water or snow collects, and more load leads to more deflection. **Must be avoided** (TensiNet).
  Synclastic basins in mid-field are the classic risk.
* Check: iterative non-linear analysis with load following the deformed geometry (water depth builds at low points) until
  converged or runaway. Remedies: more curvature or prestress, drainage points, steeper falls.
* The hanging (sag) direction under snow usually governs PVC.
* Tool: `dynamic_relaxation.py --ponding`. Algorithm: (1) solve the snow/rain case; (2) priority-flood (Barnes et al. 2014)
  over the mesh graph from the outlets (free edges, supports, drains) gives each node's spill level, so depth = level − z;
  (3) nodal water load = γ_w·depth·plan area (γ_w = 10 kN/m³), fill-to-spill = blocked drains; (4) re-solve from the
  deformed shape; (5) repeat until the volume changes < 1 % (stable basin, still a FAIL) or depth > limit / no convergence
  (instability). A surface that drains everywhere reports "no basin". γ_w = 10 kN/m³ is 9.81 kN/m³ rounded up [C].

## 5. Deflection and serviceability
No universal numeric limit [U: none found in the searched sources]. Criteria: clearance to steel, lights and people
(ASCE/SEI 55 serviceability provisions [U: clause not re-checked]); no ponding;
no loss of tension or flutter under SLS; appearance, with wrinkling limited to wind peaks. Flat regions: only prestress and EA
control deflection.

## 6. Steel integration
Model everything together where possible, or export concurrent reactions per combination to the steel model, then
iterate support displacements if significant. Envelopes for members; concurrent sets for connections and foundations.

## 7. Reporting a membrane analysis (minimum contents)
Geometry and form-finding parameters; materials (strength, stiffness source, compensation); loads (sources of Cp);
combinations and factors; per combination: max/min stress maps (warp, weft), deflection map, slack zones, ponding
result, cable forces, reactions; summary utilisations (membrane, seams, cables, steel); limitations of the model.

## 8. Mesh and accuracy of the tools in this skill
* Mesh: refine until max deflection and max stress change < 5 % [U: engineering judgement] between two densities;
  `mesh_convergence.py` automates it and scales the cable force densities with the mesh (FDM q is per link).
* Accuracy demonstrated on benchmarks (`validation.md`): deflections within 0.2 % and stresses within 2–3 % on
  217–625-node meshes; O(h²) convergence for the Poisson (prestressed square) and catenoid problems.
* Cable-net analogy vs CST: identical for uniform isotropic prestress on a regular grid; the net is softer (no shear)
  by ~15–19 % in deflection on the test sail; prefer the CST for stresses, the net for quick screening.
