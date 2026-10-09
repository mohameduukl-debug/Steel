#!/usr/bin/env python3
"""Validation matrix for the whole tool set: what is validated, against what, and what is still unverified.

For every skill it reads `reference/validation.md` (table rows = validated cases against an independent reference),
checks that every script of the skill is named there, and counts the U / C / V factors of the register sections the
skill owns. With --run-tests it also runs the unit tests and reports the totals.

CLI
  python3 validate_all.py                    # Markdown matrix to stdout
  python3 validate_all.py --run-tests        # + unittest totals
  python3 validate_all.py --strict           # exit 1 if a script is not covered by its validation.md
  python3 validate_all.py --out validation_matrix   # also write .md
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(SK, "..", ".."))
REGISTER = os.path.join(HERE, "..", "reference", "code_factors.json")
# register sections owned by each skill
SECTIONS = {
    "membrane-fabric": ["membrane"],
    "cable-tension-members": ["cable", "fatigue_cables"],
    "steel-supports": ["steel", "aisc", "geotech"],
    "tensile-connections": ["anchor_EN1992_4", "aluminium", "fatigue_EN1993_1_9", "connections"],
}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def skills():
    return sorted(d for d in os.listdir(SK) if os.path.isfile(os.path.join(SK, d, "SKILL.md")))


def table_rows(md):
    """Data rows of all Markdown tables (header and separator rows removed)."""
    rows, lines = [], md.splitlines()
    for i, ln in enumerate(lines):
        if not ln.lstrip().startswith("|") or re.match(r"^\s*\|[\s:|-]+\|\s*$", ln):
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if re.match(r"^\s*\|[\s:|-]+\|\s*$", nxt):      # this is a header row
            continue
        rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return rows


def factor_status(sections, path=REGISTER):
    with open(path) as fh:
        reg = json.load(fh)
    n = {"V": 0, "C": 0, "U": 0}
    for s in sections:
        for k, e in reg.get(s, {}).items():
            if isinstance(e, dict) and e.get("status") in n:
                n[e["status"]] += 1
    return n


def matrix():
    out = []
    for d in skills():
        sdir = os.path.join(SK, d, "scripts")
        scripts = sorted(f for f in os.listdir(sdir) if f.endswith(".py")) if os.path.isdir(sdir) else []
        vpath = os.path.join(SK, d, "reference", "validation.md")
        vmd = _read(vpath) if os.path.exists(vpath) else ""
        uncovered = [f for f in scripts if f not in vmd and f[:-3] not in vmd]
        refmd = ""
        rdir = os.path.join(SK, d, "reference")
        for f in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
            if f.endswith(".md"):
                refmd += _read(os.path.join(rdir, f))
        refmd += _read(os.path.join(SK, d, "SKILL.md"))
        out.append({
            "skill": d, "scripts": len(scripts), "validation_md": bool(vmd),
            "cases": len(table_rows(vmd)), "uncovered": uncovered,
            "tags": {t: refmd.count(f"[{t}]") for t in ("V", "C", "U")},
            "factors": factor_status(SECTIONS.get(d, [])) if d in SECTIONS else None,
        })
    return out


def run_tests():
    suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "tests"), top_level_dir=ROOT)
    res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return res.testsRun, len(res.failures), len(res.errors), len(res.skipped)


def render(rows, tests=None):
    L = ["# Validation matrix", "",
         "Validated cases = rows of each skill's `reference/validation.md` (independent reference: closed form, published "
         "worked example or the standard's own numbers). Tags = [V]/[C]/[U] in the skill's text. Factors = register "
         "entries owned by the skill.", "",
         "| Skill | Scripts | Validated cases | Scripts not in validation.md | Text tags V/C/U | Register V/C/U |",
         "|---|---|---|---|---|---|"]
    for r in rows:
        f = r["factors"]
        L.append(f"| {r['skill']} | {r['scripts']} | {r['cases'] if r['validation_md'] else 'no validation.md'} | "
                 f"{', '.join(r['uncovered']) or '-'} | {r['tags']['V']}/{r['tags']['C']}/{r['tags']['U']} | "
                 f"{'%d/%d/%d' % (f['V'], f['C'], f['U']) if f else '-'} |")
    if tests:
        n, fl, er, sk = tests
        L += ["", f"Unit tests: {n} run, {fl} failures, {er} errors, {sk} skipped."]
    L += ["", "A U value is acceptable only if no check that governs depends on it (`--sensitivity` = ROBUST) or it is "
          "replaced by a project value. Validation shows the tools reproduce their references; it does not replace the "
          "independent check of a design by a qualified engineer."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-tests", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    rows = matrix()
    md = render(rows, run_tests() if a.run_tests else None)
    print(md)
    if a.out:
        with open(a.out + ".md", "w") as fh:
            fh.write(md)
    if a.strict and any(r["uncovered"] or not r["validation_md"] for r in rows):
        raise SystemExit(1)
    return rows


if __name__ == "__main__":
    main()
