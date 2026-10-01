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


def frange(path: str, project: str | None = None):
    """(lo, hi) sensitivity range of an unverified factor, or None."""
    node = load(project)
    for p in path.split("."):
        node = node[p]
    r = node.get("range") if isinstance(node, dict) else None
    return tuple(r) if r else None


def sensitivity(check_fn, path: str, project: str | None = None):
    """Evaluate check_fn(value) -> utilisation at the register value and both ends of the factor range.

    Returns dict(value, lo, hi, u, u_lo, u_hi, robust) where robust = the OK/NOT OK decision is the same
    over the whole range. check_fn receives the factor value (scale for table entries)."""
    base = get(path, project)
    if isinstance(base, dict):          # table entry (e.g. membrane.partial): the range is a scale on it
        base = 1.0
    rng = frange(path, project)
    u = check_fn(base)
    if not rng:
        return {"value": base, "u": u, "robust": True, "lo": None, "hi": None, "u_lo": u, "u_hi": u}
    u_lo, u_hi = check_fn(rng[0]), check_fn(rng[1])
    decisions = {x <= 1.0 for x in (u, u_lo, u_hi)}
    return {"value": base, "lo": rng[0], "hi": rng[1], "u": u, "u_lo": u_lo, "u_hi": u_hi,
            "robust": len(decisions) == 1}


def sens_line(name: str, res: dict) -> str:
    if res["lo"] is None:
        return f"  sensitivity {name}: no range, value taken as fixed ([V]/[C])"
    verdict = ("ROBUST — decision unchanged over the range" if res["robust"] else
               "DEPENDS ON THIS UNCERTAIN FACTOR — confirm the value before issue")
    pts = [(res["value"], res["u"])] + [(v, u) for v, u in ((res["lo"], res["u_lo"]), (res["hi"], res["u_hi"]))
                                           if v != res["value"]]
    return (f"  sensitivity {name}: " + ", ".join(f"util {u:.2f} at {v:g}" for v, u in pts) + f" -> {verdict}")


CODES = ("EU", "US", "SA")


def code(explicit: str | None = None, project: str | None = None) -> str:
    """active design-code system: explicit argument > env TENSILE_CODE > project file '_code' > 'EU'."""
    c = explicit or os.environ.get("TENSILE_CODE") or load(project).get("_code") or "EU"
    c = c.upper()
    if c not in CODES:
        raise SystemExit(f"unknown code system '{c}' (EU, US, SA)")
    return c


def code_label(c: str) -> str:
    return {"EU": "Eurocodes (EN)", "US": "US codes (ASCE 7 / AISC 360 / ASCE 55 / ACI 318)",
            "SA": "Saudi Building Code (SBC 301/306/304/201, 2018 values)"}[c]


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
    import signal
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet exit when piped into head/grep
    main(sys.argv[1:])
