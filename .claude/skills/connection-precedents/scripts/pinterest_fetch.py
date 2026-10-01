#!/usr/bin/env python3
"""Fetch Pinterest precedents (pins, boards, ideas pages) and download their images for review.

The search itself is done with WebSearch filtered to pinterest.com (see precedent_search.py queries). Pinterest
search pages need a login and return nothing here, so pass the pin / board / ideas URLs that WebSearch returned.
The images are saved locally so they can be opened and reviewed (the Read tool shows images).

CLI
  python3 pinterest_fetch.py probe                                     # what can be reached from here
  python3 pinterest_fetch.py fetch URL [URL ...] --node corner-plate --out prec_corner [--max 15] [--per-board 6]
          [--details] [--merge prec_corner/precedents.json]

Output: <out>/NN_<pinid>.jpg and <out>/precedents.json (the precedent_search.py format, features still "?").
Consumer products (shop listings, "ft." kits) are pushed to the end and marked; they are rarely structural precedents.
Stdlib only. Uses HTTPS_PROXY and SSL_CERT_FILE from the environment when set.
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
IMG = "https://i.pinimg.com/{size}/{a}/{b}/{c}/{sig}.jpg"
# words that mark a shop listing or a consumer kit rather than a built structural detail
CONSUMER = re.compile(r"home depot|amazon|walmart|\bkit\b|\bft\.?\b|\$|buy now|price|sale|hardware kit", re.I)


def _ctx():
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    return ssl.create_default_context(cafile=ca if ca and os.path.exists(ca) else None)


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,ar;q=0.8"})
    with urllib.request.urlopen(req, context=_ctx(), timeout=timeout) as r:
        return r.status, r.read()


def classify(url):
    p = urllib.parse.urlparse(url)
    if "pinterest." not in p.netloc:
        return "other"
    path = urllib.parse.unquote(p.path)
    if re.search(r"/pin/", path):
        return "pin"
    if path.startswith("/ideas/"):
        return "ideas"
    if path.startswith("/search/"):
        return "search"
    if len([s for s in path.split("/") if s]) >= 2:
        return "board"
    return "other"


def pin_id_from_url(url):
    m = re.search(r"/pin/(?:[^/]*?-+)?(\d{6,})/?", urllib.parse.unquote(url))
    return m.group(1) if m else None


def img_url(sig, size="736x"):
    return IMG.format(size=size, a=sig[0:2], b=sig[2:4], c=sig[4:6], sig=sig)


def _meta(h, name):
    m = re.search(r'<meta[^>]*?content="([^"]*)"[^>]*?(?:property|name)="%s"' % re.escape(name), h) or \
        re.search(r'<meta[^>]*?(?:property|name)="%s"[^>]*?content="([^"]*)"' % re.escape(name), h)
    return htmlmod.unescape(m.group(1)).strip() if m else ""


def parse_pin_page(h):
    """Title, description, image and outbound link of a single pin page."""
    img = _meta(h, "og:image")
    sig = re.search(r"/([0-9a-f]{32})\.(?:jpg|png|webp)", img)
    link = _meta(h, "og:see_also") or ""
    return {"title": _meta(h, "og:title"), "description": _meta(h, "og:description") or _meta(h, "description"),
            "image_sig": sig.group(1) if sig else None, "image_url": img, "link": link}


def parse_collection_page(h):
    """Pins embedded in a board or ideas page: list of {id, sig}. Page title."""
    dec = json.JSONDecoder()
    pins, seen = [], set()
    for m in re.finditer(r'\{"node_id":"UGlu', h):          # base64 of "Pin:" -> pin objects in the SSR data
        try:
            o, _ = dec.raw_decode(h, m.start())
        except ValueError:
            continue
        sig = o.get("image_signature")
        if not sig:
            u = ((o.get("images") or {}).get("736x") or {}).get("url", "")
            s = re.search(r"/([0-9a-f]{32})\.", u)
            sig = s.group(1) if s else None
        pid = str(o.get("id", ""))
        if sig and pid and pid not in seen:
            seen.add(pid)
            pins.append({"id": pid, "sig": sig, "title": o.get("grid_title") or o.get("title") or "",
                         "description": o.get("description") or ""})
    if not pins:                                               # fallback: preloaded image sets, no pin ids
        for sig in dict.fromkeys(re.findall(r"i\.pinimg\.com/736x/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{2}/([0-9a-f]{32})", h)):
            pins.append({"id": "", "sig": sig, "title": "", "description": ""})
    return pins, _meta(h, "og:title")


def is_consumer(text):
    return bool(CONSUMER.search(text or ""))


def probe():
    rows = []
    for name, url in (("pinterest pages", "https://www.pinterest.com/ideas/tensile-structure-detail/913003401530/"),
                      ("pinterest images", img_url("bcbbc7878f99ca1e291354ce043073e8", "236x")),
                      ("pinterest search page", "https://www.pinterest.com/search/pins/?q=tensile%20membrane")):
        try:
            st, body = get(url, timeout=15)
            ok = st == 200 and len(body) > 1000
            if name == "pinterest search page":
                ok = ok and bool(parse_collection_page(body.decode("utf-8", "replace"))[0])
            rows.append((name, st, ok))
        except Exception as e:  # noqa: BLE001 - report any network failure
            rows.append((name, type(e).__name__, False))
    return rows


def fetch(urls, out, node="", max_n=15, per_board=6, details=False, merge=None, log=print):
    os.makedirs(out, exist_ok=True)
    data = {"node": node, "searched": [], "precedents": []}
    if merge and os.path.exists(merge):
        with open(merge) as fh:
            data = json.load(fh)
    have = {p.get("pin_id") or p.get("url") for p in data["precedents"]}
    cand = []
    for url in urls:
        kind = classify(url)
        if kind in ("other", "search"):
            log(f"skip {url}: {'search pages need a login, use WebSearch' if kind == 'search' else 'not a Pinterest URL'}")
            continue
        try:
            st, body = get(url)
        except Exception as e:  # noqa: BLE001
            log(f"fail {url}: {e}")
            continue
        h = body.decode("utf-8", "replace")
        if kind == "pin":
            m = parse_pin_page(h)
            if m["image_sig"]:
                cand.append({"id": pin_id_from_url(url) or "", "sig": m["image_sig"], "title": m["title"],
                             "description": m["description"], "link": m["link"], "from": url})
        else:
            pins, ptitle = parse_collection_page(h)
            log(f"{kind} '{ptitle[:60]}': {len(pins)} pins, taking {min(per_board, len(pins))}")
            for p in pins[:per_board]:
                p["from"] = url
                p.setdefault("link", "")
                cand.append(p)
    # dedupe, consumer listings last
    uniq = {}
    for c in cand:
        key = c["id"] or c["sig"]
        if key not in uniq and key not in have:
            uniq[key] = c
    ordered = sorted(uniq.values(), key=lambda c: is_consumer(c["title"] + " " + c["description"]))
    n0 = len(data["precedents"])
    for c in ordered[:max_n]:
        if details and c["id"] and not c["title"]:
            try:
                m = parse_pin_page(get(f"https://www.pinterest.com/pin/{c['id']}/")[1].decode("utf-8", "replace"))
                c["title"], c["description"], c["link"] = m["title"], m["description"], m["link"]
            except Exception:  # noqa: BLE001
                pass
        k = len(data["precedents"]) + 1
        fn = os.path.join(out, f"{k:02d}_{c['id'] or c['sig'][:10]}.jpg")
        try:
            with open(fn, "wb") as fh:
                fh.write(get(img_url(c["sig"]))[1])
        except Exception as e:  # noqa: BLE001
            log(f"image fail {c['sig']}: {e}")
            fn = ""
        url = f"https://www.pinterest.com/pin/{c['id']}/" if c["id"] else c["from"]
        data["precedents"].append({
            "title": c["title"] or f"pin {c['id'] or c['sig'][:10]}", "url": url, "source": "pinterest",
            "pin_id": c["id"], "found_via": c["from"], "image": fn, "image_url": img_url(c["sig"]),
            "description": c["description"][:300], "outbound_link": c.get("link", ""),
            "consumer_product": is_consumer(c["title"] + " " + c["description"]),
            "viewed": False, "scale": "?", "ideas": [], "features": {}, "notes": "",
        })
    path = os.path.join(out, "precedents.json")
    with open(path, "w") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    log(f"{len(data['precedents']) - n0} new precedents ({len(data['precedents'])} total) -> {path}")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="check access to Pinterest pages and images")
    f = sub.add_parser("fetch", help="download pins/boards/ideas pages and images")
    f.add_argument("urls", nargs="+")
    f.add_argument("--node", default="")
    f.add_argument("--out", required=True)
    f.add_argument("--max", type=int, default=15)
    f.add_argument("--per-board", type=int, default=6)
    f.add_argument("--details", action="store_true", help="also open each board pin for its title (slower)")
    f.add_argument("--merge", help="existing precedents.json to add to")
    a = ap.parse_args(argv)
    print("Assumptions: images are downloaded only for private design review; cite the pin URL, do not reuse the image.")
    if a.cmd == "probe":
        rows = probe()
        for name, st, ok in rows:
            print(f"  {name:22s} {str(st):>6s}  {'OK' if ok else 'not available'}")
        if rows[0][2] and rows[1][2]:
            print("Mode A: fetch pins/boards found by WebSearch and review the images yourself.")
        else:
            print("Mode B: Pinterest not reachable from here. Use WebSearch titles, give the user the Pinterest URLs and")
            print("ask for screenshots, or allow pinterest.com and i.pinimg.com in the environment's network settings.")
        return rows
    return fetch(a.urls, a.out, a.node, a.max, a.per_board, a.details, a.merge)


if __name__ == "__main__":
    main()
