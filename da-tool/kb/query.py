"""Query the knowledge base: find provisions by number or keyword across
all parsed instruments.

  python3 kb/query.py "8.6"                 # match clause number (or heading keyword)
  python3 kb/query.py "design excellence"
  python3 kb/query.py "8.6" --full          # print full text + tables
  python3 kb/query.py "8.6" --instrument warringah_lep_2011

Stdlib only; works with any python3. Output is deliberately plain and
human-readable - this is the manual-inspection entry point for the KB.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROV_DIR = Path(__file__).resolve().parent / "provisions"


def find(pattern: str, instrument: str | None) -> list:
    pat = pattern.lower().strip()
    hits = []
    for f in sorted(PROV_DIR.glob("*.json")):
        if instrument and instrument not in f.name:
            continue
        for p in json.loads(f.read_text()):
            hay = " ".join(str(p.get(k, "")) for k in
                           ("number", "heading", "id")).lower()
            if pat in hay or pat in (p.get("text") or "")[:400].lower():
                hits.append((f.stem, p))
    return hits


def snippet(p: dict, n: int = 260) -> str:
    t = re.sub(r"\s+", " ", (p.get("text") or "")).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " …"


def print_provision(fstem: str, p: dict, full: bool) -> None:
    head = (f"[{fstem}]  {p.get('number') or ''}  "
            f"{(p.get('heading') or '').strip()}")
    print(head)
    print(f"    id: {p.get('id')}   kind: {p.get('kind') or '?'}"
          + (f"   tables: {len(p.get('tables') or [])}"
             if p.get("tables") else ""))
    if full:
        print("    ---- text ----")
        print("    " + (p.get("text") or "").replace("\n", "\n    ").strip())
        for t in p.get("tables") or []:
            rows = t.get("rows") if isinstance(t, dict) else t
            print("    ---- table ----")
            for r in rows:
                print("    " + " | ".join(
                    re.sub(r"\s+", " ", c).strip() for c in r))
    else:
        print(f"    {snippet(p)}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pattern", help="clause number or keyword (e.g. '8.6', "
                    "'flood', 'design excellence')")
    ap.add_argument("--full", action="store_true",
                    help="print full text and tables")
    ap.add_argument("--instrument", default=None,
                    help="limit to one instrument file stem "
                         "(e.g. warringah_lep_2011)")
    a = ap.parse_args()

    hits = find(a.pattern, a.instrument)
    if not hits:
        print(f"no match for {a.pattern!r}"
              + (f" in {a.instrument!r}" if a.instrument else ""))
        return 1
    print(f"{len(hits)} match(es) for {a.pattern!r}:\n")
    for fs, p in hits:
        print_provision(fs, p, a.full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
