# Cable mechanics: formulas and worked examples

All implemented in `scripts/cable_calc.py`.

## 1. Catenary (load w per unit arc length, e.g. self-weight)
Supports A(0,0), B(L,h); a = H/w:
```
y(x) = a·cosh((x − x0)/a) + c
x0 = L/2 − a·asinh( h / (2a·sinh(L/(2a))) )
S  = a·[sinh((L−x0)/a) − sinh(−x0/a)]
T(x) = H·cosh((x−x0)/a)             (T = √(H² + V²))
level supports: S = 2a·sinh(L/2a), f = a[cosh(L/2a) − 1], T_max = H + w·f
```
Example (tool): L = 20 m, w = 0.05 kN/m, f = 0.8 m → H = 3.13 kN, S = 20.085 m, T_max = 3.17 kN.

## 2. Parabola (load w per unit horizontal length, e.g. membrane or roof load)
```
y = 4f·x(L−x)/L²      H = wL²/(8f)      V = wL/2 (level)
inclined: V_A = wL/2 − H·h/L,  V_B = wL/2 + H·h/L
T_max = H·√(1+16n²)  (n = f/L)
S ≈ L[1 + (8/3)n² − (32/5)n⁴]     inclined chord Lc: S ≈ Lc + 8f²/(3Lc)
```
Parabola and catenary differ by < 1 % for f/L ≤ 1/8.

## 3. Unstressed (fabrication) length
```
S0 = ∫ ds / (1 + T/EA)  ≈  S − ∫ T/EA ds
S0(T_ref) = S0(T_install) / (1 + α·(T_install − T_ref))
```
For a straight pretensioned member: L0 = L/(1 + F/EA).
Example (tool): L = 12 m, w = 1.8 kN/m, H = 60 kN, EA = 17 000 kN, installed at 30 °C with T_ref = 20 °C →
S = 12.0649 m, stretch 42.8 mm, **S0(20 °C) = 12.0206 m**.

## 4. Edge cable of a membrane
```
T = n·R        R = c²/(8s) + s/2        (circular arc, chord c, sag s)
tangent angle at the ends: θ = asin(c/(2R))
```
Example: c = 10 m, s = 1.0 m (10 %), n = 3 kN/m → R = 13.0 m, **T = 39 kN** (characteristic; factor per combination).
Sag 8–12 % of chord is normal. At s/c = 10 %, R ≈ 1.30c.

## 5. Irvine's cable equation (change of H, parabolic cable, level supports)
```
(H − H0)·Le/EA − [w1²L³/(24H²) − w0²L³/(24H0²)] + α·ΔT·Le = 0      (solve for H)
Le ≈ L(1 + 8n²)
λ² = (wL/H)² · L/(H·Le/EA)     (λ² < ~1: behaves like a taut string; ≫ 1: sag-dominated)
```

## 6. Ernst equivalent modulus (sagging stay)
`E_eq = E / [1 + (γ·l)²·E / (12σ³)]`, with γ = specific weight incl. coating, l = horizontal projection, σ = stress.

## 7. Stiffness and vibration
* Geometric lateral stiffness of a straight cable: k_g = T/L. Axial: EA/L.
* Tension-only element: N = EA(L − L0)/L0 if L > L0 else 0; tangent K = (EA/L0)nnᵀ + (N/L)(I − nnᵀ).
* String frequencies: f_n = (n/2L)·√(T/m). Keep f₁ away from vortex-shedding and rain-wind ranges; dampers or
  helical fillets on long stays; check the Scruton number.

## 8. Temperature and pretension loss
ΔL = α·ΔT·L (α 12e-6 carbon, 16e-6 stainless). Losses: relaxation/creep of prestretched strand about 1–3 % [U], seating
of fittings, membrane creep (PVC significant), temperature, support flexibility. Provide re-tensioning.
