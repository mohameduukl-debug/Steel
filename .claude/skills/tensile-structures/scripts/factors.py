#!/usr/bin/env python3
"""Central code-factor register (shared by all tensile-structure tools).

Defaults live in ../reference/code_factors.json, each tagged V / C / U.
A project file with only the keys you want to change overrides them:

    {"cable": {"gammaR": {"value": 1.0, "status": "V", "source": "UK NA to EN 1993-1-11"}},
     "steel": {"gM0": {"value": 1.05, "status": "V", "source": "NA"}}}

Select it with  --factors project.json  (tools that accept it) or
the environment variable  TENSILE_FACTORS=project.json.

CLI
  python3 factors.py report [--factors p.json]      list all factors, flag unverified ones
  python3 factors.py template > project_factors.json   editable copy of the unverified factors
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "..", "reference", "code_factors.json")


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


_cache: dict[str, dict] = {}


def load(project: str | None = None) -> dict:
    project = project or os.environ.get("TENSILE_FACTORS")
    key = project or ""
    if key not in _cache:
        with open(DEFAULT) as fh:
            data = json.load(fh)
        if project:
            with open(project) as fh:
                data = _merge(copy.deepcopy(data), json.load(fh))
            data["_project_file"] = project
        _cache[key] = data
    return _cache[key]


def get(path: str, project: str | None = None):
    """get('cable.gammaR') -> value ; returns dict for grouped entries."""
    node = load(project)
    for p in path.split("."):
        node = node[p]
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node


def status(path: str, project: str | None = None) -> str:
    node = load(project)
    parts = path.split(".")
    for p in parts:
        node = node[p]
    return node.get("status", "?") if isinstance(node, dict) else "?"


def tag(path: str, project: str | None = None) -> str:
    """short printable provenance, e.g. 'gammaR=1.0 [V]'."""
    return f"{path.split('.')[-1]}={get(path, project)} [{status(path, project)}]"


def iter_entries(d=None, prefix=""):
    d = load() if d is None else d
    for k, v in d.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and "status" in v:
            yield prefix + k, v
        elif isinstance(v, dict):
            yield from iter_entries(v, prefix + k + ".")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["report", "template"])
    ap.add_argument("--factors", default=None)
    a = ap.parse_args(argv)
    data = load(a.factors)
    if a.cmd == "report":
        n_u = 0
        print(f"Code factors ({data.get('_project_file', 'defaults only')})")
        print(f"{'factor':<34}{'value':>12}  st  source")
        for path, e in iter_entries(data):
            val = e.get("value", "(table)")
            n_u += e["status"] == "U"
            flag = "  <-- VERIFY" if e["status"] == "U" else ""
            print(f"{path:<34}{str(val):>12}  {e['status']:<3} {e.get('source', '')[:70]}{flag}")
        print(f"\n{n_u} factor(s) unverified. Put confirmed values in a project file (see `template`).")
    else:
        tpl = {}
        for path, e in iter_entries(data):
            if e["status"] != "U":
                continue
            node = tpl
            parts = path.split(".")
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            new = copy.deepcopy(e)
            new["status"] = "U"
            new["source"] = "ENTER: standard, edition, clause, National Annex"
            node[parts[-1]] = new
        json.dump(tpl, sys.stdout, indent=2)
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
