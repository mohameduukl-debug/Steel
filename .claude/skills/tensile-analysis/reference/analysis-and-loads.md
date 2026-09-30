# Structural analysis, loads and combinations

## 1. Formulation
* Geometrically non-linear (Total or Updated Lagrangian), Newton–Raphson with load steps, or DR. K_T = K_E + K_G.
* **No superposition.** Each factored combination is its own non-linear run. The reference is the prestressed state.
* Membrane elements: CST or 4–8 node membrane, no bending. Green–Lagrange strain E = ½(FᵀF − I). Material axes follow
  the warp and fill directions from the patterning mesh.
* **Wrinkling:** tension-field theory classifies points as taut (σ₂ > 0), wrinkled (σ₁ > 0 ≥ σ₂, uniaxial) or slack, and modifies the constitutive law
  so compression vanishes. Wrinkled zones under SLS mean too little prestress or curvature.
* Cables: tension-only, N = EA(L − L0)/L0 if L > L0; K = (EA/L0)nnᵀ + (N/L)(I − nnᵀ). Temperature via
  L0(T) = L0,ref[1 + α(T − T_ref)]. Use the supplier's apparent modulus.
* Orthotropic plane stress (per unit width):
```
ε_w = σ_w/E_w − ν_fw σ_f/E_f;   ε_f = −ν_wf σ_w/E_w + σ_f/E_f;   γ = τ/G;   E_i ν_ij = E_j ν_ji
```
Constants from EN 17117-1 / MSAJ biaxial tests (1:1, 2:1, 1:2, 1:0, 0:1). Apparent ν can exceed 1 from crimp interchange. G is small.
Pick the constant set matching the governing load state.

## 2. Load cases
| Case | Notes |
|---|---|
| PS: prestress | always present; check initial and relaxed (creep) values |
| G: self-weight | fabric about 0.01–0.017 kN/m², plus fittings and lights |
| S: snow | s = μ_i C_e C_t s_k (EN 1991-1-3); uniform, drift, asymmetric; **ponding** iteration |
| W: wind | several directions, pressure and suction; see §3 |
| T: temperature | cables, steel; strength reduction at high temperature |
| Erection | partial prestress, staged lifting, temporary stability |
| Maintenance | point loads and local indentation |

Typical combinations (each solved non-linearly): PS+G; PS+G+S; PS+G+W↓; PS+G+W↑; PS+G+S+ψW; PS+G+W+ψS; PS+G+T;
SLS versions for deflection, ponding and slack. Partial factors: project code (e.g. γ_P = 1.0 with γ_Q = 1.5–2.0, or
γ_P = 1.2 with 1.5: Eng. Struct. 2020 calibration) [V].

## 3. Wind on membranes
* EN 1991-1-4: monopitch and duopitch canopies (c_p,net, c_f, blockage φ), vaulted roofs, domes; **no hypars or cones** [V].
* Options: conservative mapping of canopy/vault coefficients; published tunnel data (Colliers, Mollaert, Degroote,
  Rizzo); TensiNet App. A1; project boundary-layer tunnel tests (rigid pressure model); CFD (RANS or LES, validated).
* Dynamics: large added mass (coefficient 0.68–0.90 reported for 1–50 m spans [V]) and aerodynamic damping. Buffeting and
  aeroelastic instability grow with lower prestress, higher turbulence and lower stiffness. Large roofs need aeroelastic tests or FSI. Canopies:
  quasi-static peak pressure with a dynamic factor.
* For preliminary DR runs: `--pressure +p` uplift and `--pressure −p` downward, with p = c_p,net × q_p (factored).

## 4. Snow and ponding
* Ponding: deflection removes the fall, water or snow collects, and more load leads to more deflection. **Must be avoided** (TensiNet).
  Synclastic basins in mid-field are the classic risk.
* Check: iterative non-linear analysis with load following the deformed geometry (water depth builds at low points) until
  converged or runaway. Remedies: more curvature or prestress, drainage points, steeper falls.
* The hanging (sag) direction under snow usually governs PVC.

## 5. Deflection and serviceability
No universal numeric limit [V: none found]. Criteria: clearance to steel, lights and people (ASCE 55 §6.10); no ponding;
no loss of tension or flutter under SLS; appearance, with wrinkling limited to wind peaks. Flat regions: only prestress and EA
control deflection.

## 6. Steel integration
Model everything together where possible, or export concurrent reactions per combination to the steel model, then
iterate support displacements if significant. Envelopes for members; concurrent sets for connections and foundations.

## 7. Reporting a membrane analysis (minimum contents)
Geometry and form-finding parameters; materials (strength, stiffness source, compensation); loads (sources of Cp);
combinations and factors; per combination: max/min stress maps (warp, weft), deflection map, slack zones, ponding
result, cable forces, reactions; summary utilisations (membrane, seams, cables, steel); limitations of the model.
