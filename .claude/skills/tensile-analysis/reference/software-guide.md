# Software guide for tensile structures

| Tool | Form finding | Analysis | Patterning | Notes |
|---|---|---|---|---|
| **SOFiSTiK** | geometric non-linear FE (ASE), residual-force iteration, near-zero membrane stiffness | full non-linear FE: cables, membranes, steel | TEXTILE module: surface development; cutting areas exported via SOFiPLUS | steel design in the same model |
| **Easy** (technet GmbH) | Easy.Form: linear and non-linear FDM | Easy.Stat | Easy.Cut (map-projection-like flattening, geodesics) | 5 modules; used worldwide |
| **ixForten 4000** | linear/non-linear FDM, URS | FE with prestress, material, load cases | yes, fabrication output | ForTen family |
| **Forten32** | yes | yes | yes | self-described first dedicated tensile software |
| **MPanel** (Rhino/AutoCAD) | relaxation | MPanel FEA (separate) | one-click panels, variable compensation, partial decompensation, seams, hems | fabricator tool |
| **Rhino + Grasshopper + Kangaroo2** | goal-based solver (DR-like); Length goal target 0 = tension | approximate only | via plugins/scripts | design exploration |
| **Karamba3D** | membrane form-finding example | shells without bending as membranes; cables as thin trusses; large-deformation analysis | — | no true wrinkling |
| **Oasys GSA** | DR with soap-film / force-density properties | DR non-linear fabric analysis | limited [U] | UK practice |
| **Dlubal RFEM 6** | Form-Finding add-on (URS-inspired) | full non-linear FE + steel design | Cutting Pattern add-on: energy-minimising flattening, compensation per warp/weft and per boundary line, overlaps | integrated |
| **Autodesk Robot** | none dedicated | cable elements (Professional, forces non-linear) | — | steel supports |
| **ANSYS** | user methods | tension-only links, membrane shells | user | research, FSI |
| **LS-DYNA** | user methods | explicit; *MAT_034 FABRIC (no-compression flag, warp/weft curves) | — | deployment, impact |
| **WinTess3** (UPC) | FDM | loads, deformations, stresses, foundations | DXF with layers (cut, draw, fold) | ES/EU practice |
| **Tensyl** (Buro Happold, in-house) | DR | yes | yes | Millennium Dome |
| **inTENS** (Tensys) | DR | yes | yes | 700+ projects |
| **K3-Tent** | yes | yes | yes | commercial suite |
"Inextensa" could not be found; do not cite it.

## Python ecosystem
| Purpose | Library |
|---|---|
| FDM / DR | this repo (stdlib); numpy + scipy.sparse; **COMPAS** + **compas_fd**; **JAX-FDM** (autodiff, inverse design) |
| Geodesics | potpourri3d (`EdgeFlipGeodesicSolver`), pygeodesic |
| Flattening | libigl Python (LSCM, ARAP) |
| Mesh I/O | trimesh, meshio, gmsh, pyvista |
| 2D offsets | shapely (`buffer(d, join_style=mitre)`), pyclipper |
| Nesting | SVGnest/Deepnest (JS), freecad-nesting, SqueezeNest |
| DXF | **ezdxf** (R12–R2018); this repo's `dxf_writer.py` (R12, no dependency) |

## Interop tips
* Export OBJ from `form_find_fdm.py --obj` into Rhino, then remesh or run Kangaroo for design iteration.
* 3D DXF from `export_dxf.py` for the GA and for the steel model (Tekla/Advance Steel/Revit) as setting-out.
* Reactions per combination as JSON/CSV into the steel software as nodal loads.
