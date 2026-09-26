#!/usr/bin/env python
"""One-off: reconstruct the ePlanning book TOC trees from the 2026-09-25 crawl.

The crawler that produced kb/incoming/eplanning/* saved each book node as
one HTML file named:

    {root_idx:02d}-{slug(self)[:40]}-{slug(anc_farthest)[:40]}-...-{slug(anc_nearest)[:40]}.html

where slug(t) = lowercase, runs of non-alphanumerics collapsed to '-',
and root_idx is the 1-based position of the node's topmost ancestor in the
book's root TOC.  The raw response's TOC links were stripped when the file
was saved, so parent links are recovered here by matching those slugs
against the _index.json titles.  Output: <book>/_tree.json
(list of {hid, parent_hid, order, title, depth}).
"""
import json
import re
from pathlib import Path

KB = Path(__file__).parent
EPLAN = KB / "incoming" / "eplanning"


def slug(t: str) -> str:
    return re.sub(r"^[^a-z0-9]+", "", re.sub(r"[^a-z0-9]+", "-", t.lower())).strip("-")


def cap(t: str) -> str:
    return slug(t)[:40].rstrip("-")


def load(book: str):
    idx = json.loads((EPLAN / book / "_index.json").read_text())
    for e in idx:
        e["_cap"] = cap(e["title"])
    return idx


def match_ancestors(rest: str, idx, by_first_tok):
    """Parse rest (farthest->nearest ancestor caps, each <=40) into a chain.
    Returns (chain, ok) with chain = [farthest, ..., nearest]."""
    chain = []
    while rest:
        first, _, tail = rest.partition("-")
        best = None
        for cand in by_first_tok.get(first, ()):
            c = cand["_cap"]
            if c and rest.startswith(c) and (len(rest) == len(c) or rest[len(c)] == "-"):
                if best is None or len(c) > len(best["_cap"]):
                    best = cand
        if best is None:
            return chain, False
        if any(c is best for c in chain):
            return chain, False
        chain.append(best)
        rest = rest[len(best["_cap"]):].lstrip("-")
    return chain, True


def reconstruct(book: str):
    idx = load(book)
    by_first_tok = {}
    for e in idx:
        by_first_tok.setdefault(e["_cap"].split("-", 1)[0], []).append(e)

    # Roots: stem == {i:02d}-{cap}. In the DFS crawl the roots are exactly the
    # first K index entries; keep the contiguous prefix of matches.
    matches = [i for i, e in enumerate(idx, 1) if e["file"][:-5] == f"{i:02d}-{e['_cap']}"]
    roots = []
    for i in matches:
        if i == len(roots) + 1:
            roots.append(idx[i - 1])
    for i, e in enumerate(roots, 1):
        e["_root_idx"] = i

    unresolved = []
    for e in idx:
        if e in roots:
            e["_parent"], e["_depth"] = None, 1
            continue
        stem = e["file"][:-5]
        m = re.match(r"^(\d{2})-(.*)$", stem, re.S)
        if not m:
            unresolved.append((e["file"], "no-numeric-prefix"))
            continue
        ri, rest = int(m.group(1)), m.group(2)
        c = e["_cap"]
        if rest == c:
            # own slug only: node is a root we missed? treat as root-level
            unresolved.append((e["file"], "root-not-found", ri))
            continue
        if not (rest.startswith(c) and (len(rest) == len(c) or rest[len(c)] == "-")):
            unresolved.append((e["file"], "own-cap-mismatch", rest[:60]))
            continue
        tail = rest[len(c):].lstrip("-")
        chain, ok = match_ancestors(tail, idx, by_first_tok)
        if not ok or not chain:
            unresolved.append((e["file"], "ancestor-parse-fail", tail[:60]))
            continue
        if not any(ch.get("_root_idx") == ri for ch in chain):
            unresolved.append((e["file"], "root-index-mismatch", ri, chain[0]["title"]))
            continue
        e["_parent"] = chain[-1]["hid"]
        e["_depth"] = len(chain) + 1
        e["_root_idx"] = ri

    # Known artifact of the original ad-hoc crawler: DCP node "1 Introduction"
    # (hid 12840, child of Part G1 hid 12839) was saved with a stray "-2"
    # token between its own slug and the ancestor slugs. The live TOC title
    # is clean ("1 Introduction"), so parent it by override.
    overrides = {12840: 12839} if book == "DCP" else {}
    by_hid = {e["hid"]: e for e in idx}
    for hid, par in overrides.items():
        e = by_hid.get(hid)
        if e:
            e["_parent"] = par
            e["_depth"] = by_hid[par].get("_depth", 1) + 1
            unresolved = [u for u in unresolved if u[0] != e["file"]]

    tree = [
        {"hid": e["hid"], "parent_hid": e.get("_parent"), "order": i,
         "title": e["title"], "depth": e.get("_depth", 0),
         "file": e["file"]}
        for i, e in enumerate(idx, 1)
    ]
    (EPLAN / book / "_tree.json").write_text(json.dumps(tree, indent=1))
    return len(idx), len(roots), len(unresolved), unresolved


if __name__ == "__main__":
    for book in ["MLEP", "PLEP", "MDCP", "PDCP", "DCP", "LEPDCP", "ALLDCPLEP"]:
        n, nr, nu, unres = reconstruct(book)
        print(f"{book}: {n} nodes, {nr} roots, {nu} unresolved")
        for u in unres[:6]:
            print("   UNRESOLVED:", u)
