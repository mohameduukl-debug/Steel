#!/usr/bin/env python3
"""Strict, dependency-free DXF (ASCII) reader and validator.

Parses a DXF file back into group-code / value pairs and checks it against the
Autodesk DXF reference, so every DXF this skill writes can be round-tripped and
compared numerically with the source geometry (tests/test_fabrication_drawings.py).

Checks (any failure raises DXFError, the CLI exits 1):
  * file = (code, value) line pairs; every code an integer; value types per the
    Autodesk "Group Code Value Types" table: 0-9 string, 10-39 double (3D point
    coordinate), 40-59 double, 60-79 16-bit int, 90-99 32-bit int, 210-239 double;
    every float finite
  * sections: 0 SECTION / 2 <name> ... 0 ENDSEC, names from the reference,
    no duplicates, file ends with 0 EOF (nothing after it)
  * HEADER: 9 $VARIABLE followed by its value pairs; $ACADVER present; optional
    required unit ($INSUNITS 70 = 4 -> millimetres)
  * TABLES: 0 TABLE / 2 <type> / 70 <max entries> ... 0 ENDTAB; entry count <= max;
    LAYER entries carry 2 name, 70 flags, 62 colour (1..255, negative = off), 6 linetype
    present in the LTYPE table
  * ENTITIES: every entity has 8 <layer> and that layer exists in the LAYER table;
    required codes per entity type (LINE 10/20/11/21, CIRCLE 10/20/40>0, ARC +50/51,
    TEXT 10/20/40>0/1, VERTEX 10/20); POLYLINE carries 66 = 1, is followed only by
    VERTEX entities and closed by SEQEND; no VERTEX/SEQEND outside a POLYLINE;
    no repeated group code inside a simple entity
  * entity types outside the supported list are rejected in strict mode

References: Autodesk AutoCAD DXF Reference - "Group Code Value Types",
"HEADER Section Group Codes" ($ACADVER group 1, AC1009 = R11/R12; $INSUNITS
group 70, 4 = Millimeters), "Common Symbol Table Group Codes", "LAYER",
"POLYLINE"/"VERTEX"/"SEQEND", "TEXT", "CIRCLE", "ARC", "LINE"
(help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-DXF/).

CLI
  python3 dxf_reader.py file.dxf [--units-mm] [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys

SECTIONS = {"HEADER", "CLASSES", "TABLES", "BLOCKS", "ENTITIES", "OBJECTS", "THUMBNAILIMAGE"}
TABLE_TYPES = {"VPORT", "LTYPE", "LAYER", "STYLE", "VIEW", "UCS", "APPID", "DIMSTYLE", "BLOCK_RECORD"}
SUPPORTED = {"LINE", "POLYLINE", "VERTEX", "SEQEND", "CIRCLE", "ARC", "TEXT", "POINT", "LWPOLYLINE",
             "3DFACE", "SOLID", "INSERT", "DIMENSION", "MTEXT"}
REQUIRED = {"LINE": (10, 20, 11, 21), "CIRCLE": (10, 20, 40), "ARC": (10, 20, 40, 50, 51),
            "TEXT": (10, 20, 40, 1), "VERTEX": (10, 20), "POINT": (10, 20), "POLYLINE": (66,)}
UNITS = {0: "unitless", 1: "inches", 2: "feet", 4: "millimetres", 5: "centimetres", 6: "metres"}


class DXFError(ValueError):
    pass


def value_type(code: int) -> str:
    """Autodesk DXF Reference, Group Code Value Types."""
    if 0 <= code <= 9 or code in (100, 102) or 300 <= code <= 309 or 410 <= code <= 419 or code == 999 \
            or 1000 <= code <= 1009:
        return "str"
    if 10 <= code <= 59 or 110 <= code <= 149 or 210 <= code <= 239 or 460 <= code <= 469 or 1010 <= code <= 1059:
        return "float"
    if 60 <= code <= 79 or 170 <= code <= 179 or 270 <= code <= 289 or 370 <= code <= 389 or 400 <= code <= 409 \
            or 1060 <= code <= 1070:
        return "int16"
    if 90 <= code <= 99 or 420 <= code <= 429 or 440 <= code <= 449 or code == 1071:
        return "int32"
    if code == 105 or 310 <= code <= 369 or 390 <= code <= 399 or 480 <= code <= 481:
        return "hex"
    if 290 <= code <= 299:
        return "bool"
    return "str"


def _convert(code: int, raw: str, lineno: int):
    t = value_type(code)
    try:
        if t == "float":
            v = float(raw)
            if not math.isfinite(v):
                raise DXFError(f"line {lineno}: group {code} value {raw!r} is not finite")
            return v
        if t in ("int16", "int32", "bool"):
            v = int(raw.strip())
            if t == "int16" and not -32768 <= v <= 32767:
                raise DXFError(f"line {lineno}: group {code} value {v} outside 16-bit range")
            return v
    except ValueError as e:
        if isinstance(e, DXFError):
            raise
        raise DXFError(f"line {lineno}: group {code} expects {t}, got {raw!r}") from None
    return raw


def read_pairs(text: str) -> list[tuple[int, object]]:
    lines = text.splitlines()
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) % 2:
        raise DXFError(f"odd number of lines ({len(lines)}): group code without value")
    pairs = []
    for i in range(0, len(lines), 2):
        c = lines[i].strip()
        if not c.lstrip("-").isdigit():
            raise DXFError(f"line {i + 1}: group code {c!r} is not an integer")
        code = int(c)
        raw = lines[i + 1]
        if value_type(code) == "str":
            raw = raw.rstrip("\r")
        pairs.append((code, _convert(code, raw, i + 2)))
    return pairs


class Entity(dict):
    """dict of the entity's group codes (first occurrence) + type, layer, codes (all pairs)."""


class DXFDoc:
    def __init__(self):
        self.header: dict[str, list[tuple[int, object]]] = {}
        self.tables: dict[str, list[dict]] = {}
        self.layers: dict[str, dict] = {}
        self.ltypes: set[str] = set()
        self.entities: list[Entity] = []      # flat list as written (POLYLINE has .vertices)
        self.sections: list[str] = []

    # convenient decoded views -----------------------------------------
    def of(self, etype: str, layer: str | None = None):
        return [e for e in self.entities if e["type"] == etype and (layer is None or e["layer"] == layer)]

    def polylines(self, layer: str | None = None):
        return self.of("POLYLINE", layer)

    def texts(self, layer: str | None = None):
        return [e["text"] for e in self.of("TEXT", layer)]

    def used_layers(self) -> set[str]:
        s = {e["layer"] for e in self.entities}
        for e in self.of("POLYLINE"):
            s |= {v["layer"] for v in e["vertices"]}
        return s

    def header_value(self, var: str):
        pairs = self.header.get(var)
        if not pairs:
            return None
        if len(pairs) == 1:
            return pairs[0][1]
        return tuple(v for _, v in pairs)

    def summary(self) -> dict:
        cnt: dict[str, int] = {}
        for e in self.entities:
            cnt[e["type"]] = cnt.get(e["type"], 0) + 1
        return {"version": self.header_value("$ACADVER"), "insunits": self.header_value("$INSUNITS"),
                "sections": self.sections, "layers": sorted(self.layers), "entities": cnt,
                "used_layers": sorted(self.used_layers())}


def _entity(pairs, strict) -> Entity:
    e = Entity(type=pairs[0][1], codes=pairs[1:])
    seen = set()
    for c, v in pairs[1:]:
        if c in seen and strict and e["type"] not in ("LWPOLYLINE", "MTEXT", "DIMENSION"):
            raise DXFError(f"{e['type']}: group code {c} repeated")
        seen.add(c)
        e.setdefault(c, v)
    if 8 not in e:
        raise DXFError(f"{e['type']}: missing layer (group 8)")
    e["layer"] = e[8]
    for c in REQUIRED.get(e["type"], ()):
        if c not in e:
            raise DXFError(f"{e['type']} on layer {e['layer']}: missing group {c}")
    t = e["type"]
    if t in ("LINE", "VERTEX", "POINT", "CIRCLE", "ARC", "TEXT"):
        e["p"] = (e[10], e[20], e.get(30, 0.0))
    if t == "LINE":
        e["q"] = (e[11], e[21], e.get(31, 0.0))
    if t in ("CIRCLE", "ARC"):
        e["r"] = e[40]
        if e["r"] <= 0:
            raise DXFError(f"{t}: radius {e['r']} <= 0")
    if t == "TEXT":
        e["text"] = e[1]
        e["height"] = e[40]
        if e["height"] <= 0:
            raise DXFError("TEXT: height <= 0")
        if e.get(72, 0) or e.get(73, 0):
            if 11 not in e or 21 not in e:
                raise DXFError(f"TEXT {e[1]!r}: justified text needs an alignment point (11/21)")
    if t == "POLYLINE":
        if e[66] != 1:
            raise DXFError("POLYLINE: 66 (vertices follow) must be 1")
        e["closed"] = bool(e.get(70, 0) & 1)
        e["three_d"] = bool(e.get(70, 0) & 8)
        e["vertices"] = []
    return e


def parse(text: str, strict: bool = True) -> DXFDoc:
    pairs = read_pairs(text)
    doc = DXFDoc()
    i = 0
    n = len(pairs)
    while i < n:
        c, v = pairs[i]
        if (c, v) == (0, "EOF"):
            if i != n - 1:
                raise DXFError("data after EOF")
            break
        if (c, v) != (0, "SECTION"):
            raise DXFError(f"pair {i}: expected 0/SECTION or 0/EOF, got {c}/{v!r}")
        if i + 1 >= n or pairs[i + 1][0] != 2:
            raise DXFError("SECTION without name (group 2)")
        name = pairs[i + 1][1]
        if name not in SECTIONS:
            raise DXFError(f"unknown section {name!r}")
        if name in doc.sections:
            raise DXFError(f"duplicate section {name}")
        doc.sections.append(name)
        j = i + 2
        while j < n and pairs[j] != (0, "ENDSEC"):
            if pairs[j] == (0, "SECTION") or pairs[j] == (0, "EOF"):
                raise DXFError(f"section {name} not closed by ENDSEC")
            j += 1
        if j >= n:
            raise DXFError(f"section {name} not closed by ENDSEC")
        body = pairs[i + 2:j]
        {"HEADER": _header, "TABLES": _tables, "ENTITIES": _entities}.get(name, lambda d, b, s: None)(doc, body,
                                                                                                    strict)
        i = j + 1
    else:
        raise DXFError("missing 0/EOF")
    if "$ACADVER" not in doc.header:
        raise DXFError("HEADER: $ACADVER missing")
    # every layer used by an entity must exist in the LAYER table
    if strict:
        missing = doc.used_layers() - set(doc.layers)
        if missing:
            raise DXFError(f"layers used but not defined in the LAYER table: {sorted(missing)}")
    return doc


def _header(doc, body, strict):
    k = 0
    while k < len(body):
        c, v = body[k]
        if c != 9 or not str(v).startswith("$"):
            raise DXFError(f"HEADER: expected 9/$VARIABLE, got {c}/{v!r}")
        vals = []
        k += 1
        while k < len(body) and body[k][0] != 9:
            vals.append(body[k])
            k += 1
        if not vals:
            raise DXFError(f"HEADER: {v} has no value")
        doc.header[v] = vals


def _tables(doc, body, strict):
    k = 0
    while k < len(body):
        if body[k] != (0, "TABLE"):
            raise DXFError(f"TABLES: expected 0/TABLE, got {body[k]}")
        if k + 1 >= len(body) or body[k + 1][0] != 2 or body[k + 1][1] not in TABLE_TYPES:
            raise DXFError(f"TABLES: TABLE without valid type: {body[k + 1] if k + 1 < len(body) else None}")
        ttype = body[k + 1][1]
        k += 2
        maxn = None
        while k < len(body) and body[k][0] != 0:
            if body[k][0] == 70:
                maxn = body[k][1]
            k += 1
        entries = []
        while k < len(body) and body[k] != (0, "ENDTAB"):
            c, v = body[k]
            if c != 0 or v != ttype:
                raise DXFError(f"TABLE {ttype}: unexpected entry {c}/{v!r}")
            e = {}
            k += 1
            while k < len(body) and body[k][0] != 0:
                e.setdefault(body[k][0], body[k][1])
                k += 1
            if 2 not in e:
                raise DXFError(f"TABLE {ttype}: entry without name")
            entries.append(e)
        if k >= len(body):
            raise DXFError(f"TABLE {ttype}: missing ENDTAB")
        k += 1
        if strict and maxn is not None and len(entries) > maxn:
            raise DXFError(f"TABLE {ttype}: {len(entries)} entries > declared maximum {maxn}")
        doc.tables[ttype] = entries
    doc.ltypes = {e[2] for e in doc.tables.get("LTYPE", [])}
    for e in doc.tables.get("LAYER", []):
        for req in (70, 62, 6):
            if req not in e:
                raise DXFError(f"LAYER {e[2]}: missing group {req}")
        if not 1 <= abs(e[62]) <= 255:
            raise DXFError(f"LAYER {e[2]}: colour {e[62]} outside ACI 1..255")
        if strict and e[6] not in doc.ltypes:
            raise DXFError(f"LAYER {e[2]}: linetype {e[6]} not in the LTYPE table")
        if e[2] in doc.layers:
            raise DXFError(f"LAYER {e[2]} defined twice")
        doc.layers[e[2]] = {"color": e[62], "linetype": e[6], "flags": e[70]}


def _entities(doc, body, strict):
    k = 0
    cur_poly = None
    while k < len(body):
        if body[k][0] != 0:
            raise DXFError(f"ENTITIES: expected group 0, got {body[k]}")
        j = k + 1
        while j < len(body) and body[j][0] != 0:
            j += 1
        e = _entity(body[k:j], strict)
        t = e["type"]
        if strict and t not in SUPPORTED:
            raise DXFError(f"unsupported entity {t}")
        if cur_poly is not None:
            if t == "VERTEX":
                cur_poly["vertices"].append(e)
            elif t == "SEQEND":
                pts = [v["p"] for v in cur_poly["vertices"]]
                if len(pts) < 2:
                    raise DXFError("POLYLINE with fewer than 2 vertices")
                if cur_poly["three_d"] and any(not (v.get(70, 0) & 32) for v in cur_poly["vertices"]):
                    raise DXFError("3D POLYLINE vertex without flag 32")
                cur_poly["pts"] = pts
                cur_poly = None
            else:
                raise DXFError(f"{t} inside a POLYLINE before SEQEND")
        elif t in ("VERTEX", "SEQEND"):
            raise DXFError(f"{t} outside a POLYLINE")
        else:
            doc.entities.append(e)
            if t == "POLYLINE":
                cur_poly = e
        k = j
    if cur_poly is not None:
        raise DXFError("POLYLINE not closed by SEQEND")


def read(path: str, strict: bool = True, units_mm: bool = False) -> DXFDoc:
    with open(path, encoding="ascii", errors="strict", newline="") as fh:
        text = fh.read()
    doc = parse(text, strict)
    if units_mm and doc.header_value("$INSUNITS") != 4:
        raise DXFError(f"$INSUNITS = {doc.header_value('$INSUNITS')} (expected 4 = millimetres)")
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dxf", nargs="+")
    ap.add_argument("--units-mm", action="store_true", help="require $INSUNITS = 4 (millimetres)")
    ap.add_argument("--lenient", action="store_true", help="allow unknown entity types / undefined layers")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    a = ap.parse_args(argv)
    print("Assumptions: ASCII DXF; group-code value types and section/table/entity rules per the Autodesk DXF "
          "Reference; only the entity types written by this skill are decoded in full; geometry is NOT checked "
          "for self-intersection here (see the tests).")
    bad = 0
    out = {}
    for p in a.dxf:
        try:
            doc = read(p, strict=not a.lenient, units_mm=a.units_mm)
            out[p] = doc.summary()
            if not a.json:
                s = out[p]
                print(f"OK  {p}: {s['version']}, units {UNITS.get(s['insunits'], s['insunits'])}, "
                      f"layers {len(s['layers'])}, entities {s['entities']}")
        except (DXFError, UnicodeDecodeError) as e:
            bad += 1
            print(f"FAIL {p}: {e}")
    if a.json:
        print(json.dumps(out, indent=1))
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main(sys.argv[1:])
