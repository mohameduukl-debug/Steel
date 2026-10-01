#!/usr/bin/env python3
"""Precedent search (Pinterest first) before designing a steel or fabric connection.

Before a connection is designed, look at how similar nodes have been built, take the good ideas, and note the
mistakes visible in the photos. This tool does not search by itself (stdlib, no network). It prepares the
searches, and after the search it turns the precedents you collected into a precedent board.

CLI
  python3 precedent_search.py list
  python3 precedent_search.py queries corner-plate [--material PTFE] [--extra "stainless"] [--json]
  python3 precedent_search.py template corner-plate > precedents.json      # skeleton to fill after the search
  python3 precedent_search.py board precedents.json [--out board]           # markdown board (+ .json)

Feature keys for each precedent (value "yes" / "no" / "?"): see FEATURES below.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
KEYWORDS = os.path.join(HERE, "..", "reference", "search_keywords.json")

# Things a photo or sketch can show. "no" on any of these is a red flag that must not be copied.
FEATURES = {
    "concurrent": ("Lines of action of all cables/straps meet at one point (pin, mast axis)",
                   "eccentric node: moment in the plate and the support (check with corner_plate.py)"),
    "in_plane": ("Each plate lies in the plane of the force(s) it receives",
                 "plate loaded out of plane: bending/tearing at the weld"),
    "rotation": ("Pin, toggle or cardan lets the fitting rotate with the load direction",
                 "fixed fitting: bending in the cable end or fork under changing loads"),
    "adjustable": ("Tensioning/adjustment range visible (turnbuckle, threaded fork, slotted plate, screw)",
                   "no adjustment: tolerances and membrane creep cannot be taken up"),
    "membrane_safe": ("Fabric bears on rounded edges, no sharp steel against the membrane",
                      "sharp edge or bolt head against the fabric: tear risk"),
    "drainage": ("No water or dirt trap (open sections, drain holes, sloped plates)",
                 "water trap: corrosion and staining"),
    "isolation": ("Dissimilar metals isolated (stainless/aluminium/galvanised)",
                  "bimetallic contact without isolation: galvanic corrosion"),
    "replaceable": ("Membrane and cables can be removed/replaced without cutting steel",
                    "not replaceable: membrane replacement needs hot work"),
}


def load_library(path=KEYWORDS):
    with open(path) as fh:
        return json.load(fh)


def pinterest_url(q):
    return "https://www.pinterest.com/search/pins/?q=" + urllib.parse.quote(q)


def build_queries(node, material=None, extra=None, lib=None):
    """Return a dict with the search plan for one node type."""
    lib = lib or load_library()
    nodes = lib["nodes"]
    if node not in nodes:
        raise KeyError(f"unknown node '{node}'. Known: {', '.join(sorted(nodes))}")
    n = nodes[node]
    pre = " ".join(x for x in (material, extra) if x)

    def q(s):
        return f"{pre} {s}".strip() if pre else s

    primary = [q(s) for s in n["en"]]
    variants = [q(s) for s in n.get("variants", [])]
    arabic = list(n.get("ar", []))
    # WebSearch with allowed_domains=["pinterest.com"] is the main route; site: form for engines without a filter.
    websearch = [{"query": s, "allowed_domains": ["pinterest.com"]} for s in primary + variants]
    websearch += [{"query": s, "allowed_domains": ["pinterest.com"]} for s in arabic]
    return {
        "node": node,
        "title": n["title"],
        "websearch": websearch,
        "site_queries": [f"site:pinterest.com {s}" for s in primary + variants],
        "pinterest_urls": [pinterest_url(s) for s in primary + variants + arabic],
        "fallback_websearch": [{"query": f"{s} {lib['_suffixes'][0]}"} for s in primary[:2]],
        "checks": n.get("checks", []),
    }


def template(node, lib=None):
    plan = build_queries(node, lib=lib)
    return {
        "node": node,
        "searched": [w["query"] for w in plan["websearch"]],
        "precedents": [{
            "title": "", "url": "", "source": "pinterest",
            "ideas": [""],
            "features": {k: "?" for k in FEATURES},
            "notes": "",
        }],
    }


def _norm(v):
    v = str(v).strip().lower()
    return v if v in ("yes", "no") else "?"


def make_board(data, lib=None):
    """Precedent board as (markdown, summary dict)."""
    lib = lib or load_library()
    node = data.get("node", "")
    nd = lib["nodes"].get(node, {})
    precs = [p for p in data.get("precedents", []) if p.get("url") or p.get("title")]
    if not precs:
        raise ValueError("no precedents in the file: search first, then fill 'precedents'")
    rows, ideas, flags, unknown = [], {}, [], set()
    for i, p in enumerate(precs, 1):
        f = {k: _norm(p.get("features", {}).get(k, "?")) for k in FEATURES}
        score = sum(v == "yes" for v in f.values())
        nflag = [k for k, v in f.items() if v == "no"]
        rows.append((i, p.get("title") or "(untitled)", p.get("url", ""), p.get("source", "pinterest"), score, nflag))
        for idea in p.get("ideas", []):
            idea = idea.strip()
            if idea:
                ideas.setdefault(idea, []).append(i)
        for k in nflag:
            flags.append((i, k))
        unknown.update(k for k, v in f.items() if v == "?")
    ranked = sorted(rows, key=lambda r: (-r[4], len(r[5]), r[0]))

    L = [f"# Precedent board: {nd.get('title', node)}", ""]
    if data.get("searched"):
        L += ["Searched: " + "; ".join(f"`{s}`" for s in data["searched"]), ""]
    L += ["## Precedents (ranked by good features shown)", "",
          "| # | Precedent | Source | Good features | Red flags |", "|---|---|---|---|---|"]
    for i, t, u, s, sc, nf in ranked:
        link = f"[{t}]({u})" if u else t
        L.append(f"| {i} | {link} | {s} | {sc}/{len(FEATURES)} | {', '.join(nf) or '-'} |")
    L += ["", "## Ideas to take (with the precedents that show them)", ""]
    for idea, who in sorted(ideas.items(), key=lambda kv: -len(kv[1])):
        L.append(f"- {idea}  (#{', #'.join(map(str, who))})")
    if not ideas:
        L.append("- (none recorded)")
    L += ["", "## Do not copy (red flags seen)", ""]
    for i, k in flags:
        L.append(f"- #{i} {k}: {FEATURES[k][1]}")
    if not flags:
        L.append("- none seen")
    L += ["", "## Design requirements for our node (from the checklist)", ""]
    for k, (good, _) in FEATURES.items():
        tag = " (not visible in any precedent: decide it ourselves)" if k in unknown and all(
            _norm(p.get("features", {}).get(k, "?")) == "?" for p in precs) else ""
        L.append(f"- [ ] {good}{tag}")
    L += ["", "## Verify every idea before it goes on a drawing", ""]
    for c in nd.get("checks", []):
        L.append(f"- `{c}`")
    L += ["", "A picture is not a design. Forces, plate sizes, pins, welds and bolts come from our analysis and the",
          "tools above, not from the photo. Link to the precedents; do not copy proprietary details or images into",
          "the drawings."]
    summary = {"node": node, "n_precedents": len(precs), "ranking": [r[0] for r in ranked],
               "ideas": {k: v for k, v in ideas.items()}, "red_flags": flags, "checks": nd.get("checks", [])}
    return "\n".join(L) + "\n", summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="node types in the keyword library")
    a = sub.add_parser("queries", help="search plan for one node type")
    a.add_argument("node")
    a.add_argument("--material", help="e.g. PTFE, PVC, ETFE, stainless")
    a.add_argument("--extra", help="extra words added to every query")
    a.add_argument("--json", action="store_true")
    t = sub.add_parser("template", help="skeleton precedents.json")
    t.add_argument("node")
    b = sub.add_parser("board", help="precedent board from a filled precedents.json")
    b.add_argument("file")
    b.add_argument("--out", help="write <out>.md and <out>.json")
    args = ap.parse_args(argv)

    lib = load_library()
    if args.cmd == "list":
        for k, v in sorted(lib["nodes"].items()):
            print(f"{k:18s} {v['title']}")
        return lib["nodes"]
    if args.cmd == "queries":
        try:
            plan = build_queries(args.node, args.material, args.extra, lib)
        except KeyError as e:
            sys.exit(str(e))
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            return plan
        print(f"Precedent search plan: {plan['title']}")
        print("Assumptions: Pinterest is a source of ideas, not of verified details; every idea is checked with the tools")
        print("listed at the end. Searches use WebSearch filtered to pinterest.com (direct fetch of pinterest.com may be")
        print("blocked by the network; then give the user the URLs below and ask for screenshots/links).\n")
        print("1. WebSearch (allowed_domains = pinterest.com):")
        for w in plan["websearch"]:
            print(f"   - {w['query']}")
        print("\n2. Pinterest search pages (open in a browser):")
        for u in plan["pinterest_urls"]:
            print(f"   - {u}")
        print("\n3. Fallback if Pinterest gives too little (any domain):")
        for w in plan["fallback_websearch"]:
            print(f"   - {w['query']}")
        print("\n4. Then: precedent_search.py template " + args.node + " > precedents.json, fill it, run 'board'.")
        print("\nChecks for the chosen idea:")
        for c in plan["checks"]:
            print(f"   - {c}")
        return plan
    if args.cmd == "template":
        try:
            tpl = template(args.node, lib)
        except KeyError as e:
            sys.exit(str(e))
        print(json.dumps(tpl, ensure_ascii=False, indent=2))
        return tpl
    with open(args.file) as fh:
        data = json.load(fh)
    try:
        md, summary = make_board(data, lib)
    except ValueError as e:
        sys.exit(str(e))
    print(md)
    if args.out:
        with open(args.out + ".md", "w") as fh:
            fh.write(md)
        with open(args.out + ".json", "w") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
        print(f"wrote {args.out}.md, {args.out}.json")
    return md


if __name__ == "__main__":
    main()
