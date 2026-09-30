#!/usr/bin/env python3
"""Minimal, dependency-free DXF (R12 / AC1009) writer.

R12 ASCII DXF is read by AutoCAD, BricsCAD, Rhino, DraftSight, LibreCAD,
QCAD, Zünd Cut Center, Lectra and most CNC cutting-plotter software, which
makes it the safest exchange format for cutting patterns and 2D details.

Usage (as a library):

    from dxf_writer import DXF
    d = DXF()
    d.layer("CUT", color=1)
    d.polyline([(0, 0), (1000, 0), (1000, 500)], layer="CUT", closed=True)
    d.text("P01", (500, 250), height=50, layer="TEXT")
    d.save("panel.dxf")

Units are whatever you pass in (mm is the convention for fabrication).
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

# AutoCAD Colour Index values commonly used on fabrication drawings
ACI = {"red": 1, "yellow": 2, "green": 3, "cyan": 4, "blue": 5,
       "magenta": 6, "white": 7, "grey": 8, "lightgrey": 9}


def _fmt(v: float) -> str:
    return f"{v:.6f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


class DXF:
    def __init__(self) -> None:
        self._layers: dict[str, tuple[int, str]] = {"0": (7, "CONTINUOUS")}
        self._ents: list[str] = []
        self._ext_min = [math.inf, math.inf, math.inf]
        self._ext_max = [-math.inf, -math.inf, -math.inf]

    # ------------------------------------------------------------ tables
    def layer(self, name: str, color: int | str = 7, linetype: str = "CONTINUOUS") -> None:
        if isinstance(color, str):
            color = ACI[color]
        self._layers[name] = (int(color), linetype)

    def _ensure_layer(self, name: str) -> None:
        if name not in self._layers:
            self._layers[name] = (7, "CONTINUOUS")

    def _grow(self, p: Sequence[float]) -> None:
        for k in range(3):
            v = p[k] if k < len(p) else 0.0
            self._ext_min[k] = min(self._ext_min[k], v)
            self._ext_max[k] = max(self._ext_max[k], v)

    @staticmethod
    def _xyz(p: Sequence[float]) -> tuple[float, float, float]:
        return (float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0)

    def _add(self, *pairs: tuple[int, object]) -> None:
        self._ents.append("\n".join(f"{c}\n{_fmt(v) if isinstance(v, float) else v}" for c, v in pairs))

    # ---------------------------------------------------------- entities
    def line(self, p1: Sequence[float], p2: Sequence[float], layer: str = "0") -> None:
        self._ensure_layer(layer)
        a, b = self._xyz(p1), self._xyz(p2)
        self._grow(a)
        self._grow(b)
        self._add((0, "LINE"), (8, layer), (10, a[0]), (20, a[1]), (30, a[2]),
                  (11, b[0]), (21, b[1]), (31, b[2]))

    def polyline(self, pts: Iterable[Sequence[float]], layer: str = "0",
                 closed: bool = False, three_d: bool = False) -> None:
        """2D (default) or 3D polyline. Written as POLYLINE/VERTEX/SEQEND (R12)."""
        self._ensure_layer(layer)
        pts = [self._xyz(p) for p in pts]
        if len(pts) < 2:
            return
        flags = (1 if closed else 0) | (8 if three_d else 0)
        self._add((0, "POLYLINE"), (8, layer), (66, 1), (10, 0.0), (20, 0.0), (30, 0.0), (70, flags))
        vflag = 32 if three_d else 0
        for p in pts:
            self._grow(p)
            self._add((0, "VERTEX"), (8, layer), (10, p[0]), (20, p[1]), (30, p[2]), (70, vflag))
        self._add((0, "SEQEND"), (8, layer))

    def circle(self, c: Sequence[float], r: float, layer: str = "0") -> None:
        self._ensure_layer(layer)
        x, y, z = self._xyz(c)
        self._grow((x - r, y - r, z))
        self._grow((x + r, y + r, z))
        self._add((0, "CIRCLE"), (8, layer), (10, x), (20, y), (30, z), (40, float(r)))

    def arc(self, c: Sequence[float], r: float, start_deg: float, end_deg: float, layer: str = "0") -> None:
        self._ensure_layer(layer)
        x, y, z = self._xyz(c)
        self._grow((x - r, y - r, z))
        self._grow((x + r, y + r, z))
        self._add((0, "ARC"), (8, layer), (10, x), (20, y), (30, z), (40, float(r)),
                  (50, float(start_deg)), (51, float(end_deg)))

    def text(self, s: str, at: Sequence[float], height: float = 2.5,
             layer: str = "0", rotation: float = 0.0, align_center: bool = False) -> None:
        self._ensure_layer(layer)
        x, y, z = self._xyz(at)
        self._grow((x, y, z))
        pairs = [(0, "TEXT"), (8, layer), (10, x), (20, y), (30, z), (40, float(height)),
                 (1, str(s)), (50, float(rotation))]
        if align_center:
            pairs += [(72, 1), (73, 2), (11, x), (21, y), (31, z)]
        self._add(*pairs)

    def arrow(self, tail: Sequence[float], head: Sequence[float], size: float, layer: str = "0") -> None:
        """Simple open arrow (used for warp-direction arrows on patterns)."""
        self.line(tail, head, layer)
        ang = math.atan2(head[1] - tail[1], head[0] - tail[0])
        for s in (+1, -1):
            a = ang + math.pi - s * math.radians(25)
            self.line(head, (head[0] + size * math.cos(a), head[1] + size * math.sin(a)), layer)

    def dimension_text(self, p1: Sequence[float], p2: Sequence[float], offset: float,
                       height: float, layer: str = "DIM", fmt: str = "{:.0f}") -> None:
        """Lightweight aligned dimension drawn with lines + text (no DIMENSION entity,
        so every reader/plotter shows it identically)."""
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        L = math.hypot(dx, dy)
        if L == 0:
            return
        nx, ny = -dy / L, dx / L
        a = (p1[0] + nx * offset, p1[1] + ny * offset)
        b = (p2[0] + nx * offset, p2[1] + ny * offset)
        self.line(p1, a, layer)
        self.line(p2, b, layer)
        self.line(a, b, layer)
        rot = math.degrees(math.atan2(dy, dx))
        if rot > 90 or rot < -90:
            rot += 180
        mid = ((a[0] + b[0]) / 2 + nx * height * 0.6, (a[1] + b[1]) / 2 + ny * height * 0.6)
        self.text(fmt.format(L), mid, height, layer, rotation=rot, align_center=True)

    def title_block(self, origin: Sequence[float], width: float, height: float,
                    fields: dict[str, str], text_h: float, layer: str = "TITLE") -> None:
        """Drawing frame + title block (bottom-right). `fields` e.g. {"PROJECT": .., "TITLE": ..,
        "DWG No": .., "REV": .., "SCALE": .., "DATE": .., "DRAWN": .., "CHECKED": ..}."""
        x0, y0 = origin[0], origin[1]
        m = 2 * text_h
        self.polyline([(x0, y0), (x0 + width, y0), (x0 + width, y0 + height), (x0, y0 + height)], layer, closed=True)
        self.polyline([(x0 + m, y0 + m), (x0 + width - m, y0 + m), (x0 + width - m, y0 + height - m),
                       (x0 + m, y0 + height - m)], layer, closed=True)
        rows = list(fields.items())
        rh = 2.2 * text_h
        bw = min(0.45 * width, 70 * text_h)
        bx = x0 + width - m - bw
        by = y0 + m
        self.polyline([(bx, by), (bx + bw, by), (bx + bw, by + rh * len(rows)), (bx, by + rh * len(rows))],
                      layer, closed=True)
        for k, (key, val) in enumerate(reversed(rows)):
            yy = by + k * rh
            if k:
                self.line((bx, yy), (bx + bw, yy), layer)
            self.text(f"{key}:", (bx + 0.5 * text_h, yy + 0.6 * text_h), 0.7 * text_h, layer)
            self.text(str(val), (bx + 0.30 * bw, yy + 0.6 * text_h), text_h, layer)
        self.line((bx + 0.28 * bw, by), (bx + 0.28 * bw, by + rh * len(rows)), layer)

    def frame(self, fields: dict[str, str], text_h: float, layer: str = "TITLE") -> None:
        """Draw a frame enclosing everything drawn so far, with the title block below the content."""
        if math.isinf(self._ext_min[0]):
            return
        m = 6 * text_h
        tb_h = 2.2 * text_h * len(fields) + 2 * text_h
        tb_w = 70 * text_h
        x0 = self._ext_min[0] - m
        y0 = self._ext_min[1] - m - tb_h
        w = max(self._ext_max[0] + m - x0, tb_w + 4 * text_h)
        h = self._ext_max[1] + m - y0
        self.title_block((x0, y0), w, h, fields, text_h, layer)

    # -------------------------------------------------------------- output
    def tostring(self) -> str:
        mn = [0.0 if math.isinf(v) else v for v in self._ext_min]
        mx = [0.0 if math.isinf(v) else v for v in self._ext_max]
        out = ["0\nSECTION\n2\nHEADER",
               "9\n$ACADVER\n1\nAC1009",
               "9\n$INSUNITS\n70\n4",  # 4 = millimetres (ignored by strict R12 readers)
               f"9\n$EXTMIN\n10\n{_fmt(mn[0])}\n20\n{_fmt(mn[1])}\n30\n{_fmt(mn[2])}",
               f"9\n$EXTMAX\n10\n{_fmt(mx[0])}\n20\n{_fmt(mx[1])}\n30\n{_fmt(mx[2])}",
               "0\nENDSEC",
               "0\nSECTION\n2\nTABLES",
               "0\nTABLE\n2\nLTYPE\n70\n1",
               "0\nLTYPE\n2\nCONTINUOUS\n70\n0\n3\nSolid line\n72\n65\n73\n0\n40\n0.0",
               "0\nENDTAB",
               f"0\nTABLE\n2\nLAYER\n70\n{len(self._layers)}"]
        for name, (col, lt) in self._layers.items():
            out.append(f"0\nLAYER\n2\n{name}\n70\n0\n62\n{col}\n6\n{lt}")
        out += ["0\nENDTAB", "0\nENDSEC", "0\nSECTION\n2\nENTITIES"]
        out += self._ents
        out += ["0\nENDSEC", "0\nEOF"]
        return "\n".join(out) + "\n"

    def save(self, path: str) -> None:
        with open(path, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
            f.write(self.tostring())


if __name__ == "__main__":  # smoke test
    d = DXF()
    d.layer("CUT", "red")
    d.layer("TEXT", "green")
    d.polyline([(0, 0), (1000, 0), (1000, 500), (0, 500)], layer="CUT", closed=True)
    d.text("TEST", (500, 250), 40, "TEXT", align_center=True)
    d.dimension_text((0, 0), (1000, 0), -60, 25)
    print(d.tostring()[:200])
