# Shared JSON model schema

Every script exchanges this format, so the tools chain together:
`form_find_fdm.py → dynamic_relaxation.py → cutting_pattern.py / export_dxf.py / cable_schedule.py`.

```jsonc
{
  "units": {"length": "m", "force": "kN"},
  "type": "sail4 | hypar | cone | custom",
  "grid": {"nu": 16, "nv": 16, "periodic_u": false},   // optional; needed for patterning
  "nodes": [
    {"id": 0, "xyz": [0.0, 0.0, 0.0], "fixed": true,  "grid": [0, 0]},
    {"id": 1, "xyz": [0.6, 0.0, 0.2], "fixed": false, "grid": [1, 0]}
  ],
  "edges": [
    {"id": 0, "n": [0, 1], "q": 12.0, "kind": "edge_cable", "group": "EC-S"},
    {"id": 1, "n": [1, 18], "q": 1.0, "kind": "membrane"},
    {"id": 2, "n": [5, 99], "q": 4.0, "kind": "cable", "EA": 21000}      // optional per-edge EA [kN]
  ],
  "faces": [[0, 1, 18, 17]],               // quads or triangles (node ids)
  "loads": {"57": [0, 0, -1.2]},           // optional nodal loads for FDM [kN]

  // ---- written by the tools ----
  "reactions": [{"node": 0, "pull": [Fx, Fy, Fz], "magnitude": F}],   // force FROM structure ON support
  "cable_groups": [{"group": "EC-S", "force_max": 18.1, "chord": 10.4, "sag": 1.17, "sag_ratio": 0.112}],
  "membrane_stress": {"min": 1.3, "max": 2.9, "mean": 2.0},
  "surface_area_m2": 70.7
}
```

Edge results added by the tools: `length` [m], `force` [kN], `width` (tributary
width of a membrane link, m), `stress_kN_m`, `L0` and `EA` (after DR), node `disp`.

Conventions
* `kind`: `membrane` (net link representing fabric), `edge_cable`, `cable`, `strut` (not in FDM).
* `group`: a physical cable (one schedule line). All segments of an edge cable share the group.
* Grid index `[i, j]`: i along u, j along v. Warp is assumed along **u** by the DR
  tool (`--Et-u` = warp). Patterning with `--panels-along v` puts panel length (warp)
  along v, so keep the two consistent with your fabric layout.
* `pull` = what the steel/anchor must resist, pointing from the support into the structure.
