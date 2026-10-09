# Form-finding methods

## 1. Force Density Method (Schek 1974; Linkwitz and Schek)
Developed for the Munich Olympic cable-net roofs. Reference: Schek, H.-J., *CMAME* 3 (1974) 115–134.

Notation: m branches, n free nodes, n_f fixed nodes. Branch–node matrix C_s = [C | C_f] (+1/−1 per row). Q = diag(q).
```
u = C x + C_f x_f    (similarly v, w);   l = √(u² + v² + w²)
equilibrium (free nodes):  Cᵀ U L⁻¹ s = p   with q = L⁻¹ s  →
Cᵀ Q C x = p_x − Cᵀ Q C_f x_f          (same for y, z)
D = CᵀQC (n×n, SPD if all q > 0 and every free node connects to a support)
branch forces after solving: s_j = q_j·l_j
```
* Linear: one sparse solve per coordinate. Our implementation uses matrix-free Jacobi-preconditioned conjugate gradients
  (pure Python), the three coordinate systems solved in lockstep over one edge loop (961 nodes 0.1 s, 10 201 nodes 3.7 s).
* **Scaling property:** multiplying every q by k leaves the geometry unchanged and multiplies the forces by k, so pick the
  q *ratios* for shape, then scale to the target prestress (`--prestress`).
* **Non-linear FDM:** iterate q_j ← F_target,j / l_j (target forces), or target lengths or unstressed lengths (Easy, ixForten).
  `form_find_fdm.py --uniform-stress` has two methods (`--us-method`, default `auto`):
  - `width`: q_j = σ·w_j/l_j (w = tributary width) on the grid links, cables keep their q ratio. Convergence on the
    NORMAL node moves (an isotropic uniform stress leaves the mesh free to slide tangentially, the indeterminacy URS
    stabilises). Validated on the catenoid (O(h²)); used by `auto` for models without cables (rings, rigid hypar).
  - `cst` (models with cables): exact isotropic Cauchy stress σ in every triangle through the cotangent force densities
    q_ij = σ/2 (cot α + cot β) (Pinkall & Polthier 1993; the λ = 0 limit of URS for an isotropic prestress) and a
    CONSTANT force T per cable (`--cable-force`, default the linear-FDM force of each group). Each step minimises a
    majoriser of σ·A + ΣT·L (monotone; step halving as a guard); when the shape has settled, nodes move only along the
    normal (cable nodes also across the cable), which stops the tangential creep that would degenerate corner
    triangles. Result: each free edge is an arc of radius T/σ (checked, O(h²)) and the form is an exact CST
    equilibrium of `membrane_dr.py` with isotropic prestress σ (zero drift). Not realisable / stops with
    "degenerating mesh": tall cones (isotropic stress cannot reach a small high ring) and the multibay ridge/valley
    generator; use linear FDM (or anisotropic URS in an FE package) there.
* **Mesh dependence of q:** a link force is q·l, so for the same physical cable force the edge-cable q must scale with
  1/segment length: refining the mesh n → 2n at fixed `--qc` halves the cable force and enlarges the sag
  (sail4, qc 12: sag/chord 0.067 → 0.112 → 0.170 at n = 8, 16, 32) [C: tool output].
* **Plain linear FDM with uniform q is not a minimal surface**: on a fixed grid it gives the discrete harmonic map, whose
  shape depends on the grid aspect ratio (catenoid test: neck radius −17 %) [C].
* Membranes as nets: fine grid of bars (Easy, WinTess) or surface-stress-density on triangles.
* Edge cables: a higher q gives a flatter cable (smaller sag, bigger force). With p = 0, the edge satisfies T = n·R.
* On cable nets, FDM is identical to URS (Bletzinger).

Minimal numpy/scipy version (if available):
```python
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla
def fdm(xyz, edges, fixed, q, loads):
    n = len(xyz); free = np.setdiff1d(np.arange(n), fixed)
    i, j = np.array(edges).T; m = len(edges)
    Cs = sp.coo_matrix((np.r_[np.ones(m), -np.ones(m)], (np.r_[np.arange(m), np.arange(m)], np.r_[i, j])),
                       shape=(m, n)).tocsr()
    C, Cf = Cs[:, free], Cs[:, fixed]; Q = sp.diags(q)
    D, Df = (C.T @ Q @ C).tocsc(), C.T @ Q @ Cf
    X = xyz.copy(); X[free] = spla.spsolve(D, loads[free] - Df @ xyz[fixed])
    L = np.linalg.norm(Cs @ X, axis=1); return X, q * L, L
```

## 2. Dynamic Relaxation (Day 1965; Barnes 1977–1999)
Trace a fictitious damped motion of lumped masses until it stops, where the rest state is equilibrium.
```
R_i = P_i + Σ element forces       (link: f = T·(x_b − x_a)/L, T = EA(L − L0)/L0; soap film: T = const)
v_i(t+Δt/2) = A·v_i(t−Δt/2) + B·(Δt/M_i)·R_i      A = (1 − cΔt/2)/(1 + cΔt/2), B = 1/(1 + cΔt/2)
x_i(t+Δt)   = x_i(t) + Δt·v_i(t+Δt/2)
stability: Δt ≤ √(2M_i/S_i),  S_i = Σ(EA/L0 + T/L)  →  choose Δt = 1, M_i = λ·S_i·Δt²/2, λ ≥ 1
```
**Kinetic damping** (c = 0): track KE = Σ ½ M v². When KE drops, reset all v = 0 (optionally step back to the peak:
x* = x − 1.5Δt·v + (Δt²/2M)·R [U: formula from secondary literature, not checked against Barnes; not used by our tools]).
Stop when max|R| < tolerance (default 10⁻⁴ kN in the tools [C: tool default]; use a tolerance ~10⁻⁶ of the nodal load
for benchmark accuracy). Our `dynamic_relaxation.py` uses Δt = 1, M = S (λ = 2), tension-only links and follower pressure;
`membrane_dr.py` uses M = 2·K with K = A₀(D_max + Σ|S|)·|∇N|² per element (M = K saved ~20 % of the iterations but M = 0.8·K did
not converge on a 30×30 sail, so the factor 2 is kept for robustness). Iterations grow about linearly with the number of nodes along a side (explicit method, lowest mode).
Used in GSA, Kangaroo (goal solver related), Tensyl and inTENS.

## 3. Updated Reference Strategy (Bletzinger and Ramm 1999, *IJSS* 14(2))
Prescribing Cauchy stress σ on the unknown geometry is singular (the mesh "swims"). URS blends:
```
δW_λ = λ·δW_cur + (1 − λ)·δW_ref = 0
δW_cur = ∫_a t σ : δe da,    δW_ref = ∫_A t S : δE dA,   S = det(F)·F⁻¹σF⁻ᵀ
```
Solve with λ ∈ (0, 1]; set the reference X ← x; repeat until ‖x − X‖ → 0, when σ is met exactly. Small λ is more stable.
Used by RFEM 6 (inspired by), ixForten, research codes. Works with anisotropic prestress, pressure (cushions) and cables.

## 4. Soap film, anisotropy and seams
* Soap film: isotropic constant stress, 1/R₁ + 1/R₂ = 0 (minimal surface); GSA "pseudo soap-film".
* Warp/fill ratios 1:1, 2:1, 1:2 tune the curvature; strongly anisotropic targets need URS or accepting deviation.
* Typical design prestress: PVC 1–4 kN/m; PTFE heavy 6–8, light 4–6, liners 1–2 kN/m [U: practice ranges, consistent
  with `membrane-fabric` family defaults (PES/PVC 1.0–4.0, glass/PTFE 2.0–8.0 kN/m); the minimum-prestress rule there
  is [V]].
* Seam lines: surface **geodesics** (minimum waste, no seam-induced stress); Easy and WinTess generate geodesics between
  boundary points. Strip-based cutting pattern tradition: Linkwitz–Schek, Gründig, Ströbel.
* In our tools, grid lines act as seam lines: generate the mesh so its v-lines run in the intended seam and warp direction.

## 5. Practical form-finding checklist
1. Define the fixed points and boundaries (rigid or cable), and the heights.
2. Choose q ratios: membrane 1, edge cables about 5–20 at n ≈ 16 [C: tool behaviour; scale with n] (tune for 8–12 % sag
   [U: practice]), ridge/valley cables as needed.
3. Solve and inspect: no flat zones; curvature ratio at the centre; edge sags; drainage fall; clearances.
4. Scale to the target prestress. Report the edge-cable forces and support pulls.
5. Iterate the geometry (heights, sags) with the architect until approved, then move to load analysis.
