#!/usr/bin/env python3
"""Precedent search (Pinterest first) before designing a steel or fabric connection.

Before a connection is designed, look at how similar nodes have been built, take the good ideas, and record the
mistakes visible in the pictures. Search plan -> fetch (pinterest_fetch.py) -> review images -> board -> gate.

CLI
  python3 precedent_search.py list
  python3 precedent_search.py queries corner-plate [--material PTFE] [--extra "stainless"] [--json]
  python3 precedent_search.py template corner-plate > precedents.json      # skeleton (or use pinterest_fetch.py)
  python3 precedent_search.py board precedents.json [--out board]           # weighted, ranked board (.md + .json)
  python3 precedent_search.py check precedents.json                          # gate: PASS before any sizing

Precedent fields: title, url, source, image, viewed (true once the image was looked at), kind, scale,
relevant (false = off-topic pin), ideas [...], features {key: yes/no/?/n/a}, notes.
Board-level fields: node, searched [...], project {scale, material}, concept {summary, ideas: [{idea, from: [#]}],
features {key: yes/n/a}}.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
KEYWORDS = os.path.join(HERE, "..", "reference", "search_keywords.json")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
GATE_FILE = os.path.join(os.environ.get("CLAUDE_PROJECT_DIR") or ROOT, ".claude", "state", "precedent_gate.json")

# key: (weight, what good looks like, red flag when "no"). Weight 3 = critical (structural safety).
FEATURES = {
    "concurrent": (3, "Lines of action of all cables/straps meet at one point (pin, mast axis)",
                   "eccentric node: moment in the plate and the support (check with corner_plate.py)"),
    "in_plane": (3, "Each plate lies in the plane of the force(s) it receives",
                 "plate loaded out of plane: bending/tearing at the weld"),
    "membrane_safe": (3, "Fabric bears on rounded edges, no sharp steel against the membrane, corner cut back",
                      "sharp edge or bolt against the fabric: tear risk"),
    "rotation": (2, "Pin, toggle or cardan lets the fitting rotate with the load direction",
                 "fixed fitting: bending in the cable end or fork under changing loads"),
    "adjustable": (2, "Tensioning/adjustment range visible (turnbuckle, threaded fork, slotted plate, screw)",
                   "no adjustment: tolerances and membrane creep cannot be taken up"),
    "drainage": (1, "No water or dirt trap (open sections, drain holes, sloped plates)",
                 "water trap: corrosion and staining"),
    "isolation": (1, "Dissimilar metals isolated (stainless/aluminium/galvanised)",
                  "bimetallic contact without isolation: galvanic corrosion"),
    "replaceable": (1, "Membrane and cables can be removed/replaced without cutting steel",
                    "not replaceable: membrane replacement needs hot work"),
}
CRITICAL = [k for k, v in FEATURES.items() if v[0] == 3]
# how much a picture can be trusted as evidence of a working detail
KINDS = {"photo": 1.0, "shop_drawing": 1.0, "manufacturer": 0.9, "sketch": 0.8, "render": 0.7,
         "product": 0.5, "infographic": 0.3, "ai_generated": 0.2, "?": 0.6}
SCALES = {"sail": 1, "canopy": 2, "roof": 3, "stadium": 4}
MIN_RELEVANT, MIN_REAL, MIN_QUERIES = 5, 3, 3
REAL = ("photo", "shop_drawing", "manufacturer")
ARABIC = re.compile(r"[؀-ۿ]")


def load_library(path=KEYWORDS):
    with open(path) as fh:
        return json.load(fh)


def pinterest_url(q):
    return "https://www.pinterest.com/search/pins/?q=" + urllib.parse.quote(q)


def build_queries(node, material=None, extra=None, lib=None):
    """Search plan for one node type."""
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
    pin = ["pinterest.com"]
    fb = [d["domain"] for d in lib.get("_fallback_sources", {}).get("domains", []) if d["status"].endswith("ok")]
    return {
        "node": node,
        "title": n["title"],
        "websearch": [{"query": s, "allowed_domains": pin, "group": "primary"} for s in primary]
        + [{"query": s, "allowed_domains": pin, "group": "variant"} for s in variants]
        + [{"query": s, "allowed_domains": pin, "group": "arabic"} for s in arabic],
        "site_queries": [f"site:pinterest.com {s}" for s in primary + variants],
        "pinterest_urls": [pinterest_url(s) for s in primary + variants + arabic],
        "fallback_websearch": [{"query": s, "allowed_domains": fb} for s in primary[:2]],
        "na": n.get("na", []),
        "checks": n.get("checks", []),
    }


def template(node, lib=None):
    plan = build_queries(node, lib=lib)
    feats = {k: ("n/a" if k in plan["na"] else "?") for k in FEATURES}
    return {
        "node": node,
        "project": {"scale": "?", "material": ""},
        "searched": [w["query"] for w in plan["websearch"]],
        "precedents": [{"title": "", "url": "", "source": "pinterest", "image": "", "viewed": False, "kind": "?",
                        "scale": "?", "relevant": True, "ideas": [], "features": dict(feats), "notes": ""}],
        "concept": {"summary": "", "ideas": [{"idea": "", "from": []}],
                    "features": {k: ("n/a" if k in plan["na"] else "?") for k in FEATURES}},
    }


def _norm(v):
    v = str(v).strip().lower()
    if v in ("yes", "y", "true"):
        return "yes"
    if v in ("no", "n", "false"):
        return "no"
    if v in ("n/a", "na", "-"):
        return "n/a"
    return "?"


def assess(p, na=(), project_scale="?"):
    """Weighted assessment of one precedent: quality 0-10, evidence factor, rank value, flags."""
    f = {k: ("n/a" if k in na else _norm(p.get("features", {}).get(k, "?"))) for k in FEATURES}
    app = [k for k in FEATURES if f[k] != "n/a"]
    wsum = sum(FEATURES[k][0] for k in app) or 1
    quality = 10.0 * sum(FEATURES[k][0] for k in app if f[k] == "yes") / wsum
    judged = sum(FEATURES[k][0] for k in app if f[k] != "?") / wsum
    kind = p.get("kind", "?") if p.get("kind", "?") in KINDS else "?"
    evidence = KINDS[kind]
    flags = [k for k in app if f[k] == "no"]
    critical_no = [k for k in flags if k in CRITICAL]
    scale_gap = None
    if p.get("scale") in SCALES and project_scale in SCALES:
        scale_gap = abs(SCALES[p["scale"]] - SCALES[project_scale])
    form_only = bool(critical_no) or (scale_gap is not None and scale_gap >= 2) or kind in ("infographic", "ai_generated")
    return {"features": f, "quality": round(quality, 1), "judged": round(judged, 2), "evidence": evidence,
            "rank": round(quality * evidence * (0.5 + 0.5 * judged), 2), "flags": flags,
            "critical_no": critical_no, "scale_gap": scale_gap, "form_only": form_only, "kind": kind}


def _relevant(p):
    return p.get("relevant", True) is not False and (p.get("url") or p.get("title"))


def make_board(data, lib=None):
    """Precedent board as (markdown, summary dict)."""
    lib = lib or load_library()
    node = data.get("node", "")
    nd = lib["nodes"].get(node, {})
    na = nd.get("na", [])
    pscale = (data.get("project") or {}).get("scale", "?")
    allp = data.get("precedents", [])
    idx = [(i, p) for i, p in enumerate(allp, 1) if _relevant(p) and p.get("viewed")]
    unreviewed = [i for i, p in enumerate(allp, 1) if _relevant(p) and not p.get("viewed")]
    if not idx:
        raise ValueError("no reviewed precedents: view the images, set viewed=true and judge the features")
    rows, ideas, flags = [], {}, []
    for i, p in idx:
        a = assess(p, na, pscale)
        rows.append((i, p, a))
        for idea in p.get("ideas", []):
            if idea.strip():
                ideas.setdefault(idea.strip(), []).append(i)
        for k in a["flags"]:
            flags.append((i, k))
    ranked = sorted(rows, key=lambda r: (-r[2]["rank"], r[0]))

    L = [f"# Precedent board: {nd.get('title', node)}", ""]
    if data.get("project"):
        L += [f"Project: scale {pscale}, material {data['project'].get('material') or '?'}", ""]
    if data.get("searched"):
        L += ["Searched: " + "; ".join(f"`{s}`" for s in data["searched"]), ""]
    off = [i for i, p in enumerate(allp, 1) if p.get("relevant", True) is False]
    L += ["## Precedents (ranked: weighted quality x evidence x judged share)", "",
          "| # | Precedent | Kind | Scale | Quality /10 | Rank | Red flags | Use |", "|---|---|---|---|---|---|---|---|"]
    for i, p, a in ranked:
        t = (p.get("title") or "(untitled)").replace("|", "/")[:70]
        link = f"[{t}]({p['url']})" if p.get("url") else t
        use = "form only" if a["form_only"] else "ideas + details"
        sc = p.get("scale", "?") + (f" (gap {a['scale_gap']})" if a["scale_gap"] else "")
        L.append(f"| {i} | {link} | {a['kind']} | {sc} | {a['quality']} | {a['rank']} | "
                 f"{', '.join(a['flags']) or '-'} | {use} |")
    if off:
        L += ["", f"Off-topic or rejected: #{', #'.join(map(str, off))}"]
    if unreviewed:
        L += ["", f"Not reviewed (image not viewed, not used): #{', #'.join(map(str, unreviewed))}"]
    L += ["", "## Ideas to take (with the precedents that show them)", ""]
    for idea, who in sorted(ideas.items(), key=lambda kv: -len(kv[1])):
        L.append(f"- {idea}  (#{', #'.join(map(str, who))})")
    if not ideas:
        L.append("- (none recorded)")
    L += ["", "## Do not copy (red flags seen)", ""]
    for i, k in flags:
        L.append(f"- #{i} {k}{' [critical]' if k in CRITICAL else ''}: {FEATURES[k][2]}")
    if not flags:
        L.append("- none seen")
    c = data.get("concept") or {}
    if c.get("summary") or any(x.get("idea") for x in c.get("ideas", [])):
        L += ["", "## Agreed concept", "", c.get("summary", "")]
        for x in c.get("ideas", []):
            if x.get("idea"):
                L.append(f"- {x['idea']}  (from #{', #'.join(map(str, x.get('from', []))) or '?'})")
    if data.get("verification"):
        L += ["", "## Verification of the concept (tool output)", ""]
        L += [f"- {v}" for v in data["verification"]]
    L += ["", "## Design requirements for our node", ""]
    for k, (w, good, _) in FEATURES.items():
        if k in na:
            continue
        L.append(f"- [ ] {good}{' (critical)' if w == 3 else ''}")
    L += ["", "## Verify every idea before it goes on a drawing", ""]
    for chk in nd.get("checks", []):
        L.append(f"- `{chk}`")
    L += ["", "A picture is not a design. Forces, plate sizes, pins, welds and bolts come from our analysis and the",
          "tools above, not from the photo. Link to the precedents; do not copy proprietary details or images into",
          "the drawings."]
    summary = {"node": node, "n_precedents": len(idx), "unreviewed": unreviewed, "ranking": [r[0] for r in ranked],
               "assessment": {r[0]: r[2] for r in rows}, "ideas": ideas, "red_flags": flags,
               "checks": nd.get("checks", [])}
    return "\n".join(L) + "\n", summary


def gate(data, lib=None, base_dir="."):
    """Gate before sizing. Returns (passed, [(item, ok, detail)])."""
    lib = lib or load_library()
    node = data.get("node", "")
    nd = lib["nodes"].get(node)
    res = [("node type known", nd is not None, node or "missing")]
    na = nd.get("na", []) if nd else []
    pscale = (data.get("project") or {}).get("scale", "?")
    res.append(("project scale set", pscale in SCALES, pscale))
    s = data.get("searched", [])
    res.append((f">= {MIN_QUERIES} searches", len(s) >= MIN_QUERIES, f"{len(s)}"))
    res.append(("an Arabic search", any(ARABIC.search(x) for x in s), ""))
    var = [v.lower() for v in (nd or {}).get("variants", [])]
    res.append(("a variant-solution search", any(any(v in x.lower() for v in var) for x in s), ""))
    allp = data.get("precedents", [])
    rel = [(i, p) for i, p in enumerate(allp, 1) if _relevant(p)]
    viewed = []
    for i, p in rel:
        img = p.get("image", "")
        if p.get("viewed") and (not img or os.path.exists(os.path.join(base_dir, img)) or os.path.exists(img)):
            viewed.append((i, p))
    counted = [(i, p) for i, p in viewed
               if p.get("kind", "?") not in ("infographic", "ai_generated", "product") and p.get("url")]
    res.append((f">= {MIN_RELEVANT} relevant precedents viewed, with a link (no infographics/products)",
                len(counted) >= MIN_RELEVANT, f"{len(counted)}"))
    real = [i for i, p in counted if p.get("kind") in REAL]
    res.append((f">= {MIN_REAL} of them real evidence (photo, shop drawing, manufacturer)",
                len(real) >= MIN_REAL, f"{len(real)}"))
    unj = [i for i, p in counted if any(assess(p, na, pscale)["features"][k] == "?" for k in CRITICAL if k not in na)]
    res.append(("critical features judged on every counted precedent", not unj,
                f"open on #{', #'.join(map(str, unj))}" if unj else ""))
    c = data.get("concept") or {}
    ideas = [x for x in c.get("ideas", []) if x.get("idea", "").strip()]
    valid = {i for i, _ in rel}
    bad = [x["idea"][:40] for x in ideas if not x.get("from") or not set(x["from"]) <= valid]
    res.append(("concept with ideas traced to relevant precedents", bool(ideas) and not bad,
                f"untraced: {bad}" if bad else f"{len(ideas)} ideas"))
    copied = []
    for x in ideas:
        for j in x.get("from", []):
            p = allp[j - 1] if 0 < j <= len(allp) else {}
            if assess(p, na, pscale)["form_only"] and x.get("detail", False):
                copied.append(j)
    res.append(("no detail copied from a 'form only' precedent", not copied,
                f"#{', #'.join(map(str, copied))}" if copied else ""))
    cf = {k: _norm((c.get("features") or {}).get(k, "?")) for k in CRITICAL if k not in na}
    miss = [k for k, v in cf.items() if v != "yes"]
    res.append(("concept satisfies all critical features", not miss, ", ".join(miss)))
    return all(ok for _, ok, _ in res), res


def write_gate(data, path_json, passed, gate_file=GATE_FILE):
    os.makedirs(os.path.dirname(gate_file), exist_ok=True)
    state = {}
    if os.path.exists(gate_file):
        try:
            with open(gate_file) as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            state = {}
    state[data.get("node", "?")] = {"passed": passed, "file": os.path.abspath(path_json),
                                    "time": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                                    "concept": (data.get("concept") or {}).get("summary", "")}
    with open(gate_file, "w") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    return gate_file


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
    g = sub.add_parser("check", help="gate: must PASS before the connection is sized")
    g.add_argument("file")
    g.add_argument("--no-record", action="store_true", help="do not write the gate state for the hooks")
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
        print("listed at the end. Arabic results are mostly contractor photos (overall form, regional practice).\n")
        for grp, label in (("primary", "1. WebSearch, allowed_domains = pinterest.com"), ("variant", "   variants"),
                           ("arabic", "   Arabic")):
            print(label + ":")
            for w in plan["websearch"]:
                if w["group"] == grp:
                    print(f"   - {w['query']}")
        print("\n2. Fetch the pin/board/ideas URLs from the results and view the images:")
        print(f"   python3 {os.path.join(HERE, 'pinterest_fetch.py')} fetch <URL> [<URL> ...] --node {args.node} "
              f"--out prec_{args.node} --details")
        print("\n3. Fallback if fewer than 5 relevant precedents (WebSearch with these domains):")
        for w in plan["fallback_websearch"]:
            print(f"   - {w['query']}   [{', '.join(w['allowed_domains'])}]")
        print("\n   Pinterest search pages for the user (need a login):")
        for u in plan["pinterest_urls"][:3]:
            print(f"   - {u}")
        print(f"\n4. Review (features, kind, scale, ideas), then: board, check. Features n/a for this node: "
              f"{', '.join(plan['na']) or 'none'}")
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
    if args.cmd == "board":
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
    passed, res = gate(data, lib, base_dir=os.path.dirname(os.path.abspath(args.file)))
    print(f"Precedent gate for '{data.get('node', '?')}'")
    for item, ok, detail in res:
        print(f"  [{'PASS' if ok else 'FAIL'}] {item}{(' - ' + detail) if detail else ''}")
    print("GATE PASSED: size the connection with tensile-connections." if passed else
          "GATE FAILED: finish the precedent review before sizing the connection.")
    if not args.no_record:
        print(f"gate state -> {write_gate(data, args.file, passed)}")
    if not passed:
        raise SystemExit(1)
    return res


if __name__ == "__main__":
    main()
