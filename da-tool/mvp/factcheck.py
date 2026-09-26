"""Deterministic fact checks for the MVP adjudication.

Computes, in plain Python, every numeric/structural test the LEP applies
to the synthetic Frenchs Forest cases, BEFORE the LLM call:

  LUT-R3   use listed in the R3 Land Use Table, and in which block
  s8_4     site-specific DCP precondition (Part 8.4)
  s8_5_4   height/storeys vs the 8.5(4) design-review-panel trigger
  s8_6     site area vs the Part 8.6 minimum-area table
  s8_7     street frontage vs the Part 8.7 minimum-frontage table

Every value is parsed from the KB (`kb/provisions/warringah_lep_2011.json`)
or the case record - nothing is hard-coded except the R3 LUT
row->block mapping (verified by hand against the 2011 LUT layout:
objectives, then block (a) no consent needed, block (b) with consent,
block (c) prohibited; the crawl flattened the column headers, so the
block identity is positional). If any structure is unrecognisable the
check reports "not evaluated" instead of guessing.

The rendered fact list is injected into the adjudication prompt so the
model works from verified facts (this is what eliminates the one failure
class both dev models kept producing: misreading the 8.5(4) boundary).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent.parent / "kb" / "provisions" / \
    "warringah_lep_2011.json"


def load_kb() -> list:
    return json.loads(KB_PATH.read_text())


def _norm(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "", (s or "").lower())
    return s[:-1] if s.endswith("s") and len(s) > 3 else s


def _table_rows(p: dict) -> list:
    """Flatten a KB provision's tables into a list of cell lists."""
    rows = []
    for t in p.get("tables") or []:
        if isinstance(t, dict):
            rows.extend(t.get("rows") or [])
        elif isinstance(t, list):
            rows.extend(t)
    return rows


def _provision(kb: list, hid: int) -> dict | None:
    for p in kb:
        if p["id"] == f"warringah_lep_2011/h{hid}":
            return p
    return None


def _site_label(proposal: dict) -> str | None:
    """'Site G' etc. from the record's precinct_site field."""
    m = re.search(r"(Site\s+[A-Z])", proposal.get("site", {}).get(
        "precinct_site", "") or "")
    return m.group(1) if m else None


def _zone_code(proposal: dict) -> str | None:
    """'R3' etc. from the record's zone field."""
    m = re.search(r"\b([A-Z]\d+)\b", proposal.get("site", {}).get("zone", "")
                  or "")
    return m.group(1) if m else None


def _use_name(proposal: dict) -> str:
    """'Residential flat building' from 'Residential flat building (4 dwg)'."""
    u = proposal.get("proposal", {}).get("use", "") or ""
    return re.split(r"\s*\(", u)[0].strip()


def _match_use(cell: str, use: str) -> bool:
    n_use = _norm(use)
    for cand in re.split(r"[;,]", cell):
        if _norm(cand) == n_use:
            return True
    return False


def _match_zone(cell: str, zone: str | None) -> bool:
    if not zone:
        return False
    return zone in cell


def _parse_length(cell: str) -> tuple[float, str] | None:
    """'1,400 square metres' -> (1400.0, 'm2');
    '30 metres' -> (30.0, 'm'); '225 square metres per dwelling'
    -> (225.0, 'm2/dwelling')."""
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(square\s*)?metres?"
                  r"(?:\s*per\s*(\w+))?", cell, re.I)
    if not m:
        return None
    val = float(m.group(1).replace(",", ""))
    unit = "m2" if (m.group(2) or "").strip() else "m"
    if m.group(3):
        unit += f"/{m.group(3).lower()}"
    return val, unit


def check_lut(kb: list, proposal: dict) -> dict:
    """Block membership of the proposed use in the zone LUT.

    R3 (hid 31) layout, verified by hand: objectives bullets, then the
    three LUT blocks in column order - (1) no consent needed,
    (2) with consent, (3) prohibited catch-all.
    """
    use = _use_name(proposal)
    text = _provision(kb, 31)["text"] or ""
    lines = [ln for ln in text.split("\n") if ln.strip()]
    blocks = [ln for ln in lines if not ln.strip().startswith("•")]
    names = ["no consent needed", "with development consent",
             "prohibited"]
    out = {"ref": "LUT-R3", "name": "land use table block",
           "inputs": {"use": use, "zone": "R3"}}
    if len(blocks) != 3 or not blocks[-1].startswith(
            "Any development not specified"):
        out["result"] = "NOT_EVALUATED"
        out["detail"] = ("R3 LUT row structure not recognisable; "
                         "block mapping not applied")
        return out
    for i, block in enumerate(blocks):
        uses = [u.strip() for u in block.split(";") if u.strip()]
        if any(_match_use(u, use) for u in uses):
            out["result"] = f"IN_{names[i].upper().replace(' ', '_')}"
            out["detail"] = (f"use '{use}' is listed in the LUT block "
                             f"'{names[i]}'")
            return out
    out["result"] = "NOT_LISTED"
    out["detail"] = (f"use '{use}' appears in none of the LUT blocks "
                     "(falls to the prohibited catch-all)")
    return out


def check_s8_4(proposal: dict) -> dict:
    dcp = proposal.get("site_specific_dcp") or {}
    met = bool(dcp.get("present"))
    return {
        "ref": "8.4", "name": "site-specific DCP precondition",
        "inputs": {"dcp_present": met,
                   "note": dcp.get("note") or ""},
        "result": "MET" if met else "NOT_MET",
        "detail": ("a site-specific development control plan is recorded"
                   if met else
                   "no site-specific development control plan is recorded "
                   "for the site - consent must not be granted (8.4)"),
    }


def check_s8_5_4(kb: list, proposal: dict) -> dict:
    p = _provision(kb, 15888)
    m = re.search(r"higher than\s+([\d.]+)\s+metres?\s+or\s+(\d+)\s+storeys?",
                  p["text"] or "", re.I)
    if not m:
        return {"ref": "8.5(4)", "name": "design review panel trigger",
                "inputs": {}, "result": "NOT_EVALUATED",
                "detail": "8.5(4) threshold not parseable from KB text"}
    h_thr, s_thr = float(m.group(1)), float(m.group(2))
    h = float(proposal["proposal"]["max_height_m"])
    s = float(proposal["proposal"]["storeys"])
    h_hit, s_hit = h > h_thr, s > s_thr
    triggered = h_hit or s_hit
    parts = [f"height {h:g} m {'>' if h_hit else '<='} {h_thr:g} m",
             f"{s:g} storeys {'>' if s_hit else '<='} {s_thr:g} storeys"]
    return {
        "ref": "8.5(4)", "name": "design review panel trigger",
        "inputs": {"max_height_m": h, "storeys": s,
                   "thresholds": {"height_m": h_thr, "storeys": s_thr}},
        "result": "TRIGGERED" if triggered else "NOT_TRIGGERED",
        "detail": ("the trigger engages (a building "
                   + " and ".join(parts)
                   + " is higher than the threshold) - design review "
                     "panel review is a precondition of consent"
                   if triggered else
                   "the trigger does NOT engage: " + ", ".join(parts)
                   + "; 'higher than' is a strict comparison and "
                     f"{s:g} storeys is not more than {s_thr:g} storeys"),
    }


def check_min_table(kb: list, proposal: dict, hid: int,
                    field: str, clause: str, what: str) -> dict:
    """Generic Part 8 minimums-table check (8.6 area / 8.7 frontage)."""
    p = _provision(kb, hid)
    rows = _table_rows(p)
    if not rows:
        return {"ref": clause, "name": what, "inputs": {},
                "result": "NOT_EVALUATED",
                "detail": f"no table found in {clause}"}
    site = _site_label(proposal)
    zone = _zone_code(proposal)
    use = _use_name(proposal)
    value = float(proposal["site"][field])
    for r in rows[1:]:  # skip header
        if len(r) < 4 or not _match_zone(r[0], site) \
                or not _match_zone(r[1], zone) \
                or not _match_use(r[2], use):
            continue
        parsed = _parse_length(r[3])
        if not parsed:
            return {"ref": clause, "name": what,
                    "inputs": {"row": r}, "result": "NOT_EVALUATED",
                    "detail": f"unparseable table value {r[3]!r}"}
        thr, unit = parsed
        if "/dwelling" in unit:
            return {"ref": clause, "name": what, "inputs": {"row": r},
                    "result": "NOT_EVALUATED",
                    "detail": "per-dwelling minimum; not evaluated in MVP"}
        passes = value >= thr
        return {
            "ref": clause, "name": what,
            "inputs": {field: value, "threshold": thr, "unit": unit,
                       "site": site, "zone": zone, "use": use},
            "result": "PASSES" if passes else "FAILS",
            "detail": (f"site {what.split()[-1] if what else ''} "
                       f"{value:g} {unit} "
                       f"{'>=' if passes else '<'} required {thr:g} "
                       f"{unit} ({site}, Zone {zone}, {use.lower()})"
                       + (" - exactly meets the minimum, which complies"
                          if passes and value == thr else "")),
        }
    return {"ref": clause, "name": what,
            "inputs": {"site": site, "zone": zone, "use": use,
                       field: value},
            "result": "NOT_MATCHED",
            "detail": f"no {clause} table row for {site} / Zone {zone} / "
                      f"'{use}'"}


def run_fact_checks(proposal: dict) -> list:
    kb = load_kb()
    return [
        check_lut(kb, proposal),
        check_s8_4(proposal),
        check_s8_5_4(kb, proposal),
        check_min_table(kb, proposal, 15889, "area_sqm", "8.6",
                        "minimum site area"),
        check_min_table(kb, proposal, 15890, "frontage_m", "8.7",
                        "minimum street frontage"),
    ]


def render_facts(facts: list) -> str:
    doc = ["=== DETERMINISTIC FACT CHECKS ===",
           "(computed by the tool from the case record and the LEP "
           "tables; treat every line below as a verified fact - do not "
           "recompute, second-guess or override it)"]
    for f in facts:
        doc.append(f"- {f['ref']} ({f['name']}): {f['result']} - "
                   f"{f['detail']}")
    return "\n".join(doc)


if __name__ == "__main__":
    import sys
    base = Path(__file__).resolve().parent / "cases"
    for name in sys.argv[1:] or [d.name for d in base.iterdir()
                                 if d.is_dir()]:
        prop = json.loads((base / name / "proposal.json").read_text())
        print(f"== {name}")
        for f in run_fact_checks(prop):
            print(f"  {f['ref']:<8} {f['result']:<16} {f['detail']}")
