# Cable mechanics: formulas and worked examples

All implemented in `scripts/cable_calc.py`; each formula is checked against an independent reference in
`reference/validation.md`. Formulas are mechanics (no code values) unless a tag says otherwise.

## 1. Catenary (load w per unit arc length, e.g. self-weight)
Supports A(0,0), B(L,h); a = H/w (Irvine, *Cable Structures*, 1981, Ch. 1):
```
y(x) = a·cosh((x − x0)/a) + c
x0 = L/2 − a·asinh( h / (2a·sinh(L/(2a))) )
S  = a·[sinh((L−x0)/a) − sinh(−x0/a)]
T(x) = H·cosh((x−x0)/a)             (T = √(H² + V²);  T_B − T_A = w·h)
level supports: S = 2a·sinh(L/2a), f = a[cosh(L/2a) − 1], T_max = H + w·f
```
Example (tool): L = 20 m, w = 0.05 kN/m, f = 0.8 m → H = 3.13 kN, S = 20.085 m, T_max = 3.17 kN.

## 2. Parabola (load w per unit horizontal length, e.g. membrane or roof load)
```
y = 4f·x(L−x)/L²      H = wL²/(8f)      V = wL/2 (level)
inclined: V_A = wL/2 − H·h/L,  V_B = wL/2 + H·h/L
T_max = H·√(1+16n²)  (n = f/L, level)
S (exact, level) = (L/2)·√(1+16n²) + (L/8n)·asinh(4n)  ≈ L[1 + (8/3)n² − (32/5)n⁴]
inclined chord Lc: S ≈ Lc + 8f²/(3Lc)  (the tool integrates the exact arc)
```
**Catenary vs parabola** (same span, sag and w; tool comparison, `validation.md`): H and T_max differ by about
4n²/3 — 0.3 % at f/L = 1/20, 1 % at f/L ≈ 1/11, **2 % at 1/8**, 5 % at 1/5. Lengths differ by O(n⁴): 0.03 % at 1/8.
Use the catenary for self-weight-dominated cables with f/L > 1/10.

## 3. Unstressed (fabrication) length
```
S0 = ∫ ds / (1 + T/EA)                       (tool; exact for linear-elastic strain)
   ≈ S − ∫ T/EA ds                           (first order)
S0(T_ref) = S0(T_install) / (1 + α·(T_install − T_ref))
straight pretensioned member: L0 = L/(1 + F/EA)
```
α = 12×10⁻⁶ /K steel wires, 16×10⁻⁶ /K stainless wires [V: EN 1993-1-11 3.3(1)].
Creep allowance for cutting to length: 0.15 mm/m when no better data [V: EN 1993-1-11 3.2.2(3) NOTE 1]
(`length --creep`).
Example (tool): L = 12 m, w = 1.8 kN/m, H = 60 kN, EA = 17 000 kN, installed at 30 °C with T_ref = 20 °C →
S = 12.0649 m, stretch 42.8 mm, **S0(20 °C) = 12.0208 m** (exact elastic catenary: 12.0208 m).

## 4. Edge cable of a membrane
```
T = n·R        R = c²/(8s) + s/2        (circular arc, chord c, sag s)
tangent angle at the ends: θ = asin(c/(2R));  equilibrium check 2T·sin θ = n·c
```
Example: c = 10 m, s = 1.0 m (10 %), n = 3 kN/m → R = 13.0 m, **T = 39 kN** (characteristic; factor per combination).
Sag 8–12 % of chord is normal practice [U: design guidance, not a code value]. At s/c = 10 %, R ≈ 1.30c.

## 5. Irvine's cable equation (change of H, parabolic cable, level supports)
```
(H − H0)·Le/EA − [w1²L³/(24H²) − w0²L³/(24H0²)] + α·ΔT·Le = 0      (solve for H)
Le ≈ L(1 + 8n²)
λ² = (wL/H)² · L/(H·Le/EA)     (λ² < ~1: behaves like a taut string; ≫ 1: sag-dominated)
added uniform load w* = Δw/w (Irvine 1981 Ch. 3):
h*³ + (2 + λ²/24)h*² + (1 + λ²/12)h* − (λ²/12)·w*(1 + w*/2) = 0,   h* = ΔH/H
limits: λ² → ∞: h* = w* (inextensible);  λ² → 0: ΔH = −EA·α·ΔT (restrained bar)
```
Accuracy vs the exact elastic catenary: ≤ 0.3 % for f/L ≤ 0.1 (`validation.md`).

## 6. Ernst equivalent modulus (sagging stay)
Tangent: `E_eq = E / [1 + (γ·l)²·E / (12σ³)]`; secant between σ1 and σ2 (used by `stress-turns --w`):
`E_sec = E / [1 + (γ·l)²(σ1+σ2)·E / (24σ1²σ2²)]`, with γ = specific weight incl. coating, l = horizontal projection,
σ = stress (Ernst 1965, Der Bauingenieur 40). The secant form reproduces the exact elastic catenary shortening within
0.3 % for the cases in `validation.md`.

## 7. Stiffness and vibration
* Geometric lateral stiffness of a straight cable: k_g = T/L. Axial: EA/L.
* Tension-only element: N = EA(L − L0)/L0 if L > L0 else 0; tangent K = (EA/L0)nnᵀ + (N/L)(I − nnᵀ).
* String frequencies: f_n = (n/2L)·√(T/m). With bending stiffness (hinged ends):
  f_n² = n²T/(4mL²) + n⁴π²EI/(4mL⁴).
* Sag (Irvine & Caughey 1974; Irvine 1981 Ch. 4): antisymmetric in-plane modes ω̄ = 2nπ are unaffected; symmetric
  modes satisfy tan(ω̄/2) = ω̄/2 − (4/λ²)(ω̄/2)³, ω̄ = ωL/√(H/m). The first symmetric mode equals the first
  antisymmetric at λ² = 4π²; for λ² → ∞, ω̄ = 2 × 4.4934 = 2.86π. Force from frequencies (`freq-tension --EA`)
  corrects the odd modes with this equation.
* EN 1993-1-11 8.3 [V]: stays shorter than about 70–80 m generally need no dampers; above 80 m provide for dampers
  giving a damping ratio > 0.5 %; keep the stay excitation frequency more than 20 % away from the structure's
  frequency or twice it; amplitude ≤ L/500 at 15 m/s wind. Check the Scruton number; helical fillets against
  rain–wind vibration.

## 8. Temperature and pretension loss
ΔL = α·ΔT·L (α as in §3). Losses: relaxation/creep of prestretched strand about 1–3 % [U: practice range, no code
value], seating of fittings, membrane creep (PVC significant), temperature, support flexibility. Provide
re-tensioning.
