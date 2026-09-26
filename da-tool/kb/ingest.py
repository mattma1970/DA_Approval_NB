#!/usr/bin/env python3
"""Phase 0 KB ingestion: planning instrument PDFs/HTML -> reg_provision-shaped JSON.

PDF path v0.1 (two engines, quality-gated):
  1. PRIMARY — PyMuPDF Layout (GNN layout model via pymupdf4llm): reading order,
     heading levels, table boxes, running header/footer isolation. Handles the
     multi-column legacy layouts (e.g. Foreshores & Waterways DCP 2005) that break
     line-based parsers.
  2. FALLBACK — font-metric + numbering heuristics (pdf_lines/is_heading_candidate).
     Used automatically when the layout engine is unavailable or returns too few
     provisions for the document size (weak text layers, e.g. Warriewood 2001,
     Pittwater 21 Vol 4 where the GNN misses the A/B/C section styling).
Both preserve verbatim text in `text` (the source for RAG chunks later) and attach
tables as structured rows. HTML path: ePlanning book-page HTML (`inlinePageHeading`).

Outputs:
  kb/provisions/<instrument_id>.json   -- list of provision records
  kb/inventory.json                    -- per-instrument parse report (what a human should review)

Record schema (mirrors reg_provision in design doc §6, plus source bookkeeping):
  {id, instrument_id, path[], number, heading, text, tables[], structure,
   kind (null until the Phase 1 semantic classifier), params{}, former_number,
   rag_chunk_id, status, source: {file, page?}}

Book path v0.2: hierarchy is taken from the crawl's TOC tree
(kb/incoming/eplanning/<EXHIBIT>/_tree.json — written by
harvest/eplanning_crawl.py, or reconstructed offline from the filename
convention). Each entry becomes one provision whose path[] is the full
ancestor chain; HTML <table> elements are kept as structured rows; empty
container nodes are dropped (they survive as path segments only).

Usage:
  .venv/bin/python kb/ingest.py --all
  .venv/bin/python kb/ingest.py --file kb/incoming/foo.pdf
  .venv/bin/python kb/ingest.py --book DCP MDCP PDCP LEPDCP   (ePlanning books)
  .venv/bin/python kb/ingest.py --clean <instrument_id>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "kb" / "incoming"
PROVISIONS = ROOT / "kb" / "provisions"

EXHIBIT_MAP = {
    "MLEP": "manly_lep_2013",
    "PLEP": "pittwater_lep_2014",
    "MDCP": "manly_dcp_2013",
    "PDCP": "pittwater21_dcp",      # complete multi-section book; supersedes the vol-4 PDF
    "DCP": "warringah_dcp_2011",    # complete book (DCP 2011, eff. 9/12/2011)
    "LEPDCP": "warringah_lep_2011",  # the "LEP and DCP" exhibit is the Warringah LEP 2011 as
                                     # consolidated on ePlanning (verified 2026-09-25: cl 1.1
                                     # "This Plan is Warringah Local Environmental Plan 2011",
                                     # cl 1.3(1A) "Deferred matter" exclusion, cl 1.8 repeals
                                     # WLEP 2000; Parts 1-8, Schedules 1-6, Dictionary)
}

# Exhibits deliberately NOT ingested (verified 2026-09-25):
SKIP_BOOKS = {
    "ALLDCPLEP": "duplicate of the LEPDCP book — the same Warringah LEP 2011 under a second "
                 "exhibit slot ('Council Planning Instruments'); identical 161-node book, only "
                 "the viewer header differs",
    "WLEP": "placeholder page only (no TOC). Warringah LEP 2011 text is served under the LEPDCP "
            "exhibit; Warringah LEP 2000 (still in force for 'Deferred matter' land per WLEP 2011 "
            "cl 1.3(1A)) has no ePlanning source yet — legislation.nsw.gov.au is Cloudflare-blocked",
}

FILENAME_MAP = {
    "foreshores-waterways-dcp-2005-FULL.pdf": "foreshores_waterways_dcp_2005",
    "warringah-dcp-2000-amend4.pdf": "warringah_dcp_2000",
    "warriewood-valley-water-mgmt-spec-2001.pdf": "Warriewood Valley Water Management Specification 2001",
}

# Files in kb/incoming/ that are not planning instruments (never ingested):
IGNORED = {
    "online-da-api-data-dictionary-v2.0.pdf":
        "data dictionary for the NSW Online DA Data API — reference for the data-broker request, "
        "not a planning instrument",
}

# PDFs superseded by a more complete source (kept in incoming for audit, never
# ingested) — value is the human-readable reason:
SUPERSEDED = {
    "pittwater21-dcp-vol4-amend22.pdf":
        "superseded by the complete Pittwater 21 DCP book (kb/incoming/eplanning/PDCP); "
        "this PDF is vol 4 only",
    "foreshores-waterways-dcp-2005.pdf":
        "superseded by foreshores-waterways-dcp-2005-FULL.pdf (122-pp DPIE scan of the whole "
        "DCP); this file is the 85-pp partial — see kb/incoming/_harvest-notes.json",
}


def yaml_load_profile() -> dict:
    return yaml.safe_load((ROOT / "config" / "lga-profile.yaml").read_text())


# ---------------------------------------------------------------- numbering

RE_PART = re.compile(r"^PART\s+([0-9]+|[IVX]+|[A-Z][0-9]*)\.?\s*[-–—:]?\s*(.*)$", re.I)
RE_DIVISION = re.compile(r"^DIVISION\s+([0-9]+|[IVX]+)\.?\s*[-–—:]?\s*(.*)$", re.I)
RE_CHAPTER = re.compile(r"^CHAPTER\s+([0-9]+|[IVX]+)\.?\s*[-–—:]?\s*(.*)$", re.I)
RE_SECTION = re.compile(r"^SECTION\s+([0-9]+|[IVX]+|[A-Z])\.?\s*[-–—:]?\s*(.*)$", re.I)
# clause numbers, optionally with an amendment letter suffix ("1.8A", "1.1AA")
# or a parenthesised sub-clause ("1.3(1A)")
RE_CLAUSE = re.compile(
    r"^(?:CL(?:AUSE)?\.?\s*)?([0-9]+(?:\.[0-9]+){1,4})([A-Z]{1,2}|\([0-9]+[A-Z]?\))?\s*[-–.]?\s+(.{0,190})$")
# DCP letter sections: "B3 Side Boundary...", "G7 - Evergreen", "C3(A) Bicycle Parking..."
RE_DCPSEC = re.compile(r"^([A-Z])[.]?([0-9]+)(\([A-Z0-9]+\))?\s*[-–.]?\s+(.{0,190})$")
# DCP letter sections with dotted sub-numbers:
#   "A.1 The purpose..." / "A.1.2 ..."  (Warringah DCP style)
RE_DCPSUB = re.compile(r"^([A-Z])\.([0-9]+(?:\.[0-9]+)*)\s*[-–.]?\s+(.{0,190})$")
#   "A1.1 Name of this plan" / "G10.1 Dual Occupancies..." (Pittwater DCP style)
RE_DCPSUB2 = re.compile(r"^([A-Z])([0-9]+)\.([0-9]+(?:\.[0-9]+)*)\s*[-–.]?\s+(.{0,190})$")
RE_ZONE = re.compile(r"^ZONE\s+([A-Z]{1,2}[0-9]{1,2})\s+(.*)$", re.I)
RE_SCHEDULE = re.compile(r"^(SCHEDULE|APPENDIX)\s+[-–]?\s*([0-9]+|[IVXa-z]+)\.?\s*[-–—:]?\s*(.*)$", re.I)
RE_SUBCLAUSE = re.compile(r"^\(([0-9]+|[a-z]+)\)\s")
# one-line TOC entry: "5.3 Siting of Buildings ....... 48" / "1.2 How to Use This Plan 2"
RE_TOC_LINE = re.compile(
    r"^\(?[0-9]{1,2}(\.[0-9]{1,2}){1,3}\)?\s*[-–.]?\s.{3,80}?\s+[•.\s]{2,}\d{1,3}\s*$"
    r"|^\(?[0-9]{1,2}(\.[0-9]{1,2}){1,3}\)?\s*[-–.]?\s.{3,80}?\s+\d{1,3}\s*$")
RE_TOC_MARKER = re.compile(r"^(TABLE OF )?CONTENTS?$|^LIST OF (FIGURES|TABLES|MATERIALS|APPENDICES)", re.I)
# dangling number: "1.1" / "5.10" / "5." / "B3" on a line by itself (3-col or split-line layouts)
RE_DANGLE_CL = re.compile(r"^[0-9]{1,2}(\.[0-9]{1,2}){1,3}\.?$")
RE_DANGLE_SEC = re.compile(r"^[0-9]{1,2}\.$")
RE_DANGLE_DCP = re.compile(r"^[A-Z][0-9]+\.?$")
RE_PAGENUM = re.compile(r"^[0-9]{1,3}$|^[ivxlcdm]+$")


def classify_heading(text: str, max_level: int = 99):
    """Return (depth, kind, number, label) or None if not a structural heading.

    Families covered: PART/SECTION/DIVISION/CHAPTER, SCHEDULE/APPENDIX (incl.
    "Appendix -14"), ZONE (Land Use Table entries), letter DCP sections
    ("B3", "C3(A)", "G7 -"), letter-clause DCP sub-sections ("A.1", "A1.1",
    "G10.1"), EP&A-style clause numbers with amendment letters ("1.8A",
    "4.1AA") and parenthesised sub-clauses ("1.3(1A)"), and bare top-level
    numbered headings ("1 Introduction", "2. About ...").
    """
    t = " ".join(text.split())
    if not t or len(t) > 200:
        return None
    m = RE_PART.match(t)
    if m:
        return 0, "part", m.group(1), m.group(2).strip()
    m = RE_SECTION.match(t)
    if m:
        return 0, "section", m.group(1), m.group(2).strip()
    m = RE_DIVISION.match(t)
    if m:
        return 0, "division", m.group(1), m.group(2).strip()
    m = RE_CHAPTER.match(t)
    if m:
        return 0, "chapter", m.group(1), m.group(2).strip()
    m = RE_SCHEDULE.match(t)
    if m:
        return 0, "schedule", f"{m.group(1)} {m.group(2)}", m.group(3).strip()
    m = RE_ZONE.match(t)
    if m:
        return 0, "zone", m.group(1), m.group(2).strip()
    # dotted letter-clauses BEFORE the bare letter-section pattern, so
    # "A.1 ..." classifies as clause A.1 and not section A1
    m = RE_DCPSUB.match(t)
    if m:
        return len(m.group(2).split(".")), "clause", f"{m.group(1)}.{m.group(2)}", m.group(3).strip()
    m = RE_DCPSUB2.match(t)
    if m:
        num = f"{m.group(2)}.{m.group(3)}"
        return len(num.split(".")), "clause", f"{m.group(1)}.{num}", m.group(4).strip()
    m = RE_DCPSEC.match(t)
    if m:
        return 1, "section", f"{m.group(1)}{m.group(2)}{m.group(3) or ''}", m.group(4).strip()
    m = RE_CLAUSE.match(t)
    if m and not RE_SUBCLAUSE.match(t):
        number = m.group(1) + (m.group(2) or "")
        return max(1, len(m.group(1).split(".")) - 1), "clause", number, m.group(3).strip()
    # "1. Introduction" / "5. Design Guidelines" — top-level section (only at part-level box depth)
    m = re.match(r"^([0-9]{1,2})\.\s+([A-Z][^;]{2,190})$", t)
    if m and max_level <= 2:
        return 0, "section", m.group(1), m.group(2).strip()
    # bare single-number top-level heading: "1 Introduction", "2 About the ...",
    # "3 Use of certain land at ... , Belrose" (Schedule 6 site entries)
    m = re.match(r"^([0-9]{1,2})\s+([A-Z][^;]{2,190})$", t)
    if m:
        return 0, "section", m.group(1), m.group(2).strip()
    return None


# ---------------------------------------------------------------- PDF path

def pdf_lines(page):
    """Lines with font metrics: (text, size, bold)."""
    out = []
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            txt = "".join(s["text"] for s in line["spans"]).strip()
            if not txt:
                continue
            sizes = [s["size"] for s in line["spans"] if s.get("size")]
            flags = line["spans"][0].get("flags", 0) if line["spans"] else 0
            out.append((txt, max(sizes) if sizes else 9.0, bool(flags & 2 ** 4)))
    return out


def is_heading_candidate(line, median_size: float) -> bool:
    txt, size, bold = line
    structural = classify_heading(txt) is not None
    prominent = size >= median_size * 1.12 or (bold and size >= median_size * 1.02)
    return len(txt) <= 110 and (structural or prominent)


def tables_on_page(page):
    try:
        res = page.find_tables()
        return [t.extract() for t in res.tables]
    except Exception:
        return []


def ingest_pdf_regex(path: Path, instrument: str) -> dict:
    """Fallback PDF parser (font-metric heuristics). Used only if the layout engine is unavailable."""
    import pymupdf

    doc = pymupdf.open(path)
    samples = []
    for i in range(min(20, len(doc))):
        for _, size, _ in pdf_lines(doc[i]):
            samples.append(size)
    median_size = statistics.median(samples) if samples else 10.0

    # ---- pre-pass: line shapes for TOC pages, running headers, dangling numbers
    page_lines = [pdf_lines(doc[i]) for i in range(len(doc))]
    page_counts = {i: 0 for i in range(len(doc))}
    line_pages = {}
    for i, lines in enumerate(page_lines):
        for txt, _, _ in lines:
            k = re.sub(r"\s+", " ", txt.strip())
            line_pages.setdefault(k, set()).add(i)
            page_counts[i] += 1
    running = {k for k, ps in line_pages.items()
               if len(ps) >= 3 and len(ps) >= 0.15 * len(doc)}
    toc_pages = {i for i, lines in enumerate(page_lines)
                 if sum(1 for t, _, _ in lines
                        if RE_DANGLE_CL.match(t.strip()) or RE_DANGLE_SEC.match(t.strip())) >= 6}

    provisions, stack, issues = [], [], []
    seen_structural = False

    def close(depth):
        while stack and stack[-1][0] >= depth:
            stack.pop()

    for pno, lines in enumerate(page_lines):
        if pno in toc_pages:
            continue  # TOC page: drop entirely (numbers + titles + page numbers)
        if pno == 0:
            continue  # cover
        i = 0
        while i < len(lines):
            txt, size, bold = lines[i]
            k = re.sub(r"\s+", " ", txt.strip())
            if k in running:
                i += 1
                continue  # running header/footer on every page
            # dangling number -> join with next short line, then classify
            if (RE_DANGLE_CL.match(k) or RE_DANGLE_SEC.match(k) or RE_DANGLE_DCP.match(k)) and i + 1 < len(lines):
                nxt = lines[i + 1][0].strip()
                if 3 <= len(nxt) <= 90 and not RE_PAGENUM.match(nxt):
                    txt = f"{k} {nxt}"
                    i += 1
            if RE_TOC_MARKER.match(txt):
                i += 1
                continue
            if RE_TOC_LINE.match(txt):
                i += 1
                continue
            if is_heading_candidate((txt, size, bold), median_size) and not RE_TOC_LINE.match(txt):
                h = classify_heading(txt)
                if h:
                    depth, kind, number, label = h
                    status = "ok"
                    seen_structural = True
                else:  # prominent but unnumbered — only once real content has begun
                    if not seen_structural or txt.rstrip().endswith(":"):
                        i += 1
                        continue
                    depth, kind, number, label = (stack[-1][0] + 1 if stack else 0), "unnumbered", None, txt
                    status = "review"
                    issues.append(f"p{pno + 1}: unnumbered heading '{label[:60]}'")
                close(depth)
                stack.append((depth, kind, number, label))
                provisions.append(make_provision(
                    instrument,
                    f"{instrument}/" + "/".join((s[2] if s[2] else s[3][:24]) for s in stack),
                    [(s[3] if s[2] is None else f"{s[2]} {s[3]}".strip()) for s in stack],
                    kind, number, label, status,
                    {"file": str(path.relative_to(ROOT)), "page": pno + 1}))
            else:
                if provisions:
                    provisions[-1]["text"] += txt + "\n"
            i += 1

        # attach any tables found on this page to the last provision started here
        for rows in tables_on_page(doc[pno]):
            rows = [[(c or "").strip() for c in r] for r in rows if any((c or "").strip() for c in r)]
            if not rows:
                continue
            target = None
            for p in reversed(provisions):
                if p["source"].get("page", -1) == pno + 1:
                    target = p
                    break
            if target is None and provisions:
                target = provisions[-1]
            if target is not None:
                target["tables"].append({"rows": rows})
                if len(rows) > 3:
                    target["structure"] = "table"

    kept = [p for p in provisions if p["text"].strip() or p["tables"]]
    if not kept:
        # no structure found at all -> whole-document fallback chunk
        chunks = []
        for pg in doc:
            for b in pg.get_text("dict").get("blocks", []):
                if b.get("type") != 0:
                    continue
                for l in b.get("lines", []):
                    chunks.append("".join(s["text"] for s in l["spans"]))
        issues.append("no structural headings detected; emitting whole-document chunk")
        kept = [make_provision(instrument, f"{instrument}/whole", [path.stem], "unstructured",
                               None, path.stem, "review",
                               {"file": str(path.relative_to(ROOT))},
                               text="\n".join(chunks))]

    cover_text = "\n".join(t for t, _, _ in pdf_lines(doc[0]))
    n_pages = len(doc)
    doc.close()
    return {
        "instrument_id": instrument,
        "provisions": kept,
        "issues": issues[:40],
        "cover": {"page1": cover_text[:2000], "pages": n_pages},
    }


# ---------------------------------------------------------------- layout-aware PDF path (primary)

def make_provision(instrument: str, id: str, path: list, structure: str, number, label: str,
                   status: str, source: dict, text: str = "") -> dict:
    """Design-doc reg_provision-shaped record (see DA-decision-support-design.md §6).

    `structure` = heading level axis (part/division/chapter/section/clause/schedule/
    unnumbered/table/unstructured). `kind` = legal semantics (hard_limit,
    non_discretionary_standard, permitted_use, prohibited_use, performance_standard,
    guidance, flexibility, procedure) — assigned later by the Phase 1 semantic
    classifier, left null at ingest. `params`/`former_number`/`rag_chunk_id` likewise
    filled downstream; kept here so the loader maps 1:1."""
    return {
        "id": id,
        "instrument_id": instrument,
        "path": path,
        "structure": structure,
        "kind": None,
        "number": number,
        "heading": label,
        "text": text,
        "tables": [],
        "params": {},
        "former_number": None,
        "rag_chunk_id": None,
        "status": status,
        "source": source,
    }


def _box_lines(b):
    """Text lines of a layout box (spans -> str per line)."""
    return ["".join(s.get("text", "") for s in (l.get("spans") or [])) for l in (b.textlines or [])]


def _page_boxes(page):
    """Boxes as plain dicts in reading order; merge a numbered heading box whose
    title wrapped onto a second heading box ('2.3 IDENTIFICATION OF' + 'ECOLOGICAL COMMUNITIES')."""
    boxes = []
    for b in page.boxes:
        lines = [re.sub(r"\s+", " ", t).strip() for t in _box_lines(b)]
        lines = [t for t in lines if t]
        if not lines and b.boxclass not in ("table", "picture"):
            continue
        d = {"class": b.boxclass, "level": b.header_level, "lines": lines, "table": b.table}
        prev = boxes[-1] if boxes else None
        if (prev and prev["class"] in ("section-header", "title") and d["class"] == "section-header"
                and len(prev["lines"]) == 1 and len(d["lines"]) == 1
                and len(prev["lines"][0]) <= 90 and len(d["lines"][0]) <= 90
                and not classify_heading(d["lines"][0]) and not RE_TOC_LINE.match(d["lines"][0])):
            prev["lines"] = [prev["lines"][0] + " " + d["lines"][0]]
            continue
        boxes.append(d)
    return boxes


def _table_rows(t) -> list:
    """Structured rows from a layout table box (prefer `extract`, fall back to markdown)."""
    if not isinstance(t, dict):
        return []
    ex = t.get("extract")
    if ex:
        rows = [[(c or "").strip() for c in r] for r in ex if any((c or "").strip() for c in r)]
        if rows:
            return rows
    rows = []
    for line in (t.get("markdown") or "").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [re.sub(r"<br\s*/?>", " ", c).strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c or "---") for c in cells):
            continue
        if any(c for c in cells):
            rows.append(cells)
    return rows


def ingest_pdf(path: Path, instrument: str) -> dict:
    """Layout-engine PDF parser (PyMuPDF Layout GNN): reading order, heading levels,
    table boxes, running header/footer isolation. Falls back to ingest_pdf_regex."""
    import pymupdf

    doc = pymupdf.open(path)
    parsed = None
    try:
        from pymupdf4llm.helpers import document_layout as dl
        parsed = dl.parse_document(doc)
    except Exception as e:
        parsed = None
        print(f"  layout engine unavailable ({e}); using regex fallback")
    if parsed is None:
        return ingest_pdf_regex(path, instrument)

    provisions, stack, issues = [], [], []
    seen_structural, toc_mode = False, False

    def close(depth):
        while stack and stack[-1][0] >= depth:
            stack.pop()

    for pno, page in enumerate(parsed.pages):
        if pno == 0:
            continue  # cover
        boxes = _page_boxes(page)

        # TOC bookkeeping: mode ends when page numbering switches to arabic digits
        ftxt = " ".join(" ".join(b["lines"]) for b in boxes if b["class"] == "page-footer").strip()
        if toc_mode and re.fullmatch(r"[0-9]{1,3}", ftxt):
            toc_mode = False
        page_toc = toc_mode
        if not toc_mode:
            for b in boxes:
                if b["class"] in ("section-header", "title") and RE_TOC_MARKER.match(" ".join(b["lines"])):
                    toc_mode = True
                    page_toc = True
            if not toc_mode:
                hdrs = [b for b in boxes if b["class"] in ("section-header", "title")]
                longtext = any(b["class"] in ("text", "list-item") and len(b["lines"]) >= 3 for b in boxes)
                if len(hdrs) >= 6 and not longtext:
                    toc_mode = True
                    page_toc = True
                    issues.append(f"p{pno + 1}: presumed TOC page (many heading boxes)")
        if page_toc:
            continue

        for b in boxes:
            txt = "\n".join(b["lines"])
            if b["class"] in ("page-header", "page-footer", "picture"):
                continue
            if b["class"] == "table":
                rows = _table_rows(b["table"])
                if not rows:
                    continue
                if provisions:
                    provisions[-1]["tables"].append({"rows": rows})
                    if len(rows) > 3:
                        provisions[-1]["kind"] = "table"
                else:
                    p = make_provision(
                        instrument, f"{instrument}/table-p{pno + 1}", [f"Table (page {pno + 1})"],
                        "table", None, f"Table (page {pno + 1})", "review",
                        {"file": str(path.relative_to(ROOT)), "page": pno + 1})
                    p["tables"] = [{"rows": rows}]
                    provisions.append(p)
                continue
            if b["class"] in ("section-header", "title"):
                h = classify_heading(txt, max_level=b["level"] or 99)
                if h:
                    depth, kind, number, label = h
                    status = "ok"
                    seen_structural = True
                else:
                    if not seen_structural or txt.rstrip().endswith(":") or RE_TOC_LINE.match(txt):
                        continue
                    depth = (stack[-1][0] + 1) if stack else 0
                    kind, number, label = "unnumbered", None, txt[:120]
                    status = "review"
                    issues.append(f"p{pno + 1}: unnumbered heading '{label[:60]}'")
                close(depth)
                stack.append((depth, kind, number, label))
                provisions.append(make_provision(
                    instrument,
                    f"{instrument}/" + "/".join((s[2] if s[2] else s[3][:24]) for s in stack),
                    [(s[3] if s[2] is None else f"{s[2]} {s[3]}".strip()) for s in stack],
                    kind, number, label, status,
                    {"file": str(path.relative_to(ROOT)), "page": pno + 1}))
            else:  # text / list-item
                if provisions:
                    provisions[-1]["text"] += txt + "\n"

    if len(provisions) < max(10, len(doc) // 10):
        print(f"  layout engine returned {len(provisions)} provisions for {len(doc)} pages; regex fallback")
        return ingest_pdf_regex(path, instrument)

    kept = [p for p in provisions if p["text"].strip() or p["tables"]]
    if not kept:
        chunks = []
        for pg in doc:
            for b in pg.get_text("dict").get("blocks", []):
                if b.get("type") != 0:
                    continue
                for l in b.get("lines", []):
                    chunks.append("".join(s["text"] for s in l["spans"]))
        issues.append("no structural headings detected; emitting whole-document chunk")
        kept = [make_provision(instrument, f"{instrument}/whole", [path.stem], "unstructured",
                               None, path.stem, "review",
                               {"file": str(path.relative_to(ROOT))},
                               text="\n".join(chunks))]

    cover_lines = []
    for b in _page_boxes(parsed.pages[0]):
        if b["class"] in ("section-header", "title", "text"):
            cover_lines.extend(b["lines"])
    n_pages = len(doc)
    doc.close()
    return {
        "instrument_id": instrument,
        "provisions": kept,
        "issues": issues[:40],
        "cover": {"page1": "\n".join(cover_lines)[:2000], "pages": n_pages},
    }


# ---------------------------------------------------------------- HTML path
#
# ePlanning "Book" viewer page layout (eservices.northernbeaches.nsw.gov.au/
# ePlanning/live/Pages/Plan/Book.aspx?exhibit=<EX>&hid=<N>):
#   #page<N>                    one book page per div (usually one per file)
#     .result
#       a.bookmark#TOCt_h<hid>_ID
#         h3                    the page heading ("1.2 Where this DCP Applies")
#     .c_active .d_all          the page body (current TOC row)
#     .c_inactive .d_all        sibling rows — empty in fetched files
# Each crawled file = one book node. Container nodes have a heading but an
# empty body; their children (separate files) carry the content.

def _book_page_segments(page_div, heading: str):
    """Body text + structured tables for one #pageN div.

    Body = concatenated `d_all` content blocks with the heading echo stripped;
    tables = `<table>` elements inside those blocks (kept as structured rows —
    e.g. LEP Land Use Table / complying-development schedules / DCP parking tables).
    """
    body_parts, tables = [], []
    for d in page_div.find_all("div", class_="d_all"):
        t = re.sub(r"[ \t]+", " ", d.get_text("\n"))
        t = re.sub(r"\n{2,}", "\n", t).strip()
        if t and t != heading:
            body_parts.append(t)
        for tb in d.find_all("table"):
            rows = [[(c.get_text(" ").strip() or "") for c in tr.find_all(["th", "td"])]
                    for tr in tb.find_all("tr")]
            rows = [r for r in rows if any(c for c in r)]
            if rows:
                tables.append({"rows": rows})
    body = "\n".join(body_parts).strip()
    if heading and body.startswith(heading):
        body = body[len(heading):].strip()
    return body, tables


def _book_sort_key(fname: str) -> tuple:
    """Book reading order from the numeric path prefix of the filename
    (e.g. '05-schedule-3-parking-...' -> ('05',) then string fallback)."""
    stem = Path(fname).stem
    m = re.match(r"(\d+(?:-\d+)*)", stem)
    if m:
        return (0, tuple(int(x) for x in m.group(1).split("-")), stem)
    return (1, (), stem)


def _book_tree(bookdir: Path):
    """TOC tree from the crawler ({hid: {hid, parent_hid, order, title, depth, file}})
    or None when absent."""
    p = bookdir / "_tree.json"
    if not p.exists():
        return None
    return {n["hid"]: n for n in json.loads(p.read_text())}


def ingest_book(bookdir: Path, instrument: str) -> dict:
    """Ingest an ePlanning book: _index.json (list of entries) + raw HTML pages.

    Hierarchy comes from _tree.json (written by harvest/eplanning_crawl.py or the
    offline tree reconstruction): each entry's provision path is
    [book title] + ancestor TOC titles + own title, in reading order. Without a
    tree file the entries fall back to filename order and a flat 2-level path.
    """
    from bs4 import BeautifulSoup

    idx_path = bookdir / "_index.json"
    if not idx_path.exists():
        return {"instrument_id": instrument, "provisions": [],
                "issues": [f"no _index.json in {bookdir} (crawl pending)"],
                "cover": {"pages": 0}}
    idx = json.loads(idx_path.read_text())
    if isinstance(idx, dict):  # tolerate {title:..., pages:[...]} shape
        idx = idx.get("pages") or idx.get("entries") or []
    title = bookdir.name
    land = bookdir / "_landing.html"
    if land.exists():
        ls = BeautifulSoup(land.read_text(errors="replace"), "lxml")
        t = ls.find("title")
        if t and t.get_text(" ").strip():
            title = t.get_text(" ").strip()

    tree = _book_tree(bookdir)
    if tree:
        order = {n["hid"]: n["order"] for n in tree.values()}
        memo = {}

        def ancestors(hid):
            if hid in memo:
                return memo[hid]
            n = tree.get(hid)
            if n is None or n["parent_hid"] is None:
                memo[hid] = []
            else:
                memo[hid] = ancestors(n["parent_hid"]) + [n["title"]]
            return memo[hid]

        entries = sorted(idx, key=lambda e: order.get(e.get("hid"), 10 ** 9))
    else:
        def ancestors(hid):
            return []

        entries = sorted(idx, key=lambda e: _book_sort_key(e.get("file", "")))

    provisions, issues = [], []
    n_pages = n_empty = 0

    for entry in entries:
        if entry.get("failed"):
            issues.append(f"crawl-failed {entry.get('file')}")
            continue
        f = bookdir / entry["file"]
        if not f.exists():
            issues.append(f"missing {entry['file']}")
            continue
        soup = BeautifulSoup(f.read_text(errors="replace"), "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()

        # TOC title is authoritative for the tree; the page's own heading tag
        # (h3 for container nodes, h4/h5 for leaves) is the fallback text.
        toc_title = " ".join((entry.get("title") or "").split())
        res0 = soup.find_all(id=re.compile(r"^page\d+$"))
        page_heading = ""
        for tagname in ("h3", "h4", "h5"):
            h = res0[0].find("div", class_="result") or res0[0]
            ht = h.find(tagname)
            if ht:
                page_heading = " ".join(ht.get_text(" ").split())
                break
        heading_src = toc_title or page_heading or f.stem

        body_parts, tables, npg = [], [], 0
        pages = soup.find_all(id=re.compile(r"^page\d+$"))
        pages.sort(key=lambda p: int(re.search(r"(\d+)$", p["id"]).group(1)))
        for p in pages:
            npg += 1
            body, tbs = _book_page_segments(p, page_heading)
            if body:
                body_parts.append(body)
            tables.extend(tbs)
        body = "\n".join(body_parts).strip()
        if not body:
            n_empty += 1

        h = classify_heading(heading_src)
        number = h[2] if h else None
        label = h[3] if h else heading_src
        path = [title] + ancestors(entry.get("hid")) + [heading_src or label]
        p = make_provision(
            instrument, f"{instrument}/h{entry.get('hid')}",
            path,
            h[1] if h else "unnumbered", number, label,
            "ok" if h else "review",
            {"file": str(f.relative_to(ROOT)), "hid": entry.get("hid")},
            text=body)
        p["tables"] = tables
        if len(tables) > 3:
            p["structure"] = "table"
        provisions.append(p)
        if not h:
            issues.append(f"{f.name}: unclassified heading '{label[:60]}'")
        n_pages += npg

    # container/placeholder nodes without content are path markers only
    kept = [p for p in provisions if p["text"].strip() or p["tables"]]
    return {"instrument_id": instrument, "provisions": kept,
            "issues": issues[:40],
            "cover": {"pages": n_pages, "container_nodes": n_empty, "book": title}}


# ---------------------------------------------------------------- driver

def instrument_for_file(name: str) -> str:
    if name in FILENAME_MAP:
        return FILENAME_MAP[name]
    if name in EXHIBIT_MAP:
        return EXHIBIT_MAP[name]
    return "unknown-" + hashlib.sha1(name.encode()).hexdigest()[:8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="ingest every PDF in kb/incoming")
    ap.add_argument("--file", action="append", default=[], help="specific PDF (repeatable)")
    ap.add_argument("--book", nargs="+", default=[],
                    help="ePlanning exhibit names (MLEP, PLEP, MDCP, PDCP, DCP, LEPDCP) — dirs kb/incoming/eplanning/<NAME>")
    ap.add_argument("--clean", metavar="INSTRUMENT_ID",
                    help="delete kb/provisions/<ID>.json and its inventory entry, then exit")
    args = ap.parse_args()

    if args.clean:
        pf = PROVISIONS / f"{args.clean}.json"
        if pf.exists():
            pf.unlink()
            print(f"deleted {pf}")
        inv_path = ROOT / "kb" / "inventory.json"
        if inv_path.exists():
            inv = json.loads(inv_path.read_text())
            if args.clean in inv:
                del inv[args.clean]
                inv_path.write_text(json.dumps(inv, indent=1, ensure_ascii=False))
                print(f"removed inventory entry {args.clean}")
        else:
            print(f"no provisions file or inventory entry for {args.clean}")
        return

    profile = yaml_load_profile()
    names_by_id = {i["id"]: i["name"] for i in profile.get("instruments", [])}
    PROVISIONS.mkdir(parents=True, exist_ok=True)
    inventory = {}

    def record(res, source_file, replace=False):
        inv = inventory.setdefault(res["instrument_id"], {
            "name": names_by_id.get(res["instrument_id"]), "files": [], "pages": 0,
            "provisions": 0, "tables": 0, "issues": [], "status": "ok",
        })
        inv["files"].append(source_file)
        inv["pages"] += res["cover"].get("pages", 0)
        inv["provisions"] += len(res["provisions"])
        inv["tables"] += sum(len(p["tables"]) for p in res["provisions"])
        inv["issues"].extend(f"{source_file}: {i}" for i in res["issues"])
        if any(p["status"] == "review" for p in res["provisions"]):
            inv["status"] = "review"
        out = PROVISIONS / f"{res['instrument_id']}.json"
        existing = json.loads(out.read_text()) if out.exists() else []
        if replace:  # canonical source: drop prior content for this instrument
            existing = []
        have = {p.get("id") for p in existing}
        existing.extend(p for p in res["provisions"] if p.get("id") not in have)
        out.write_text(json.dumps(existing, indent=1, ensure_ascii=False))

    book_targets = set(args.book)
    targets = list(INCOMING.glob("*.pdf")) if args.all else []
    for f in args.file:
        p = Path(f) if Path(f).is_absolute() else ROOT / f
        targets.append(p)
    for t in targets:
        if not t.exists():
            print(f"skip (missing): {t}")
            continue
        if t.name in SUPERSEDED:
            print(f"skip (superseded): {t.name} — {SUPERSEDED[t.name]}")
            continue
        if t.name in IGNORED:
            print(f"skip (not an instrument): {t.name} — {IGNORED[t.name]}")
            continue
        print(f"ingest {t.name} ...")
        res = ingest_pdf(t, instrument_for_file(t.name))
        record(res, t.name)
        print(f"  -> {len(res['provisions'])} provisions, "
              f"{sum(len(p['tables']) for p in res['provisions'])} tables, "
              f"{res['cover']['pages']} pages")

    for b in sorted(book_targets):
        if b in SKIP_BOOKS:
            print(f"skip book {b}: {SKIP_BOOKS[b]}")
            continue
        bd = INCOMING / "eplanning" / b
        print(f"ingest book {bd} ...")
        res = ingest_book(bd, EXHIBIT_MAP.get(b, instrument_for_file(b)))
        record(res, f"eplanning/{b}", replace=True)
        print(f"  -> {len(res['provisions'])} provisions, "
              f"{sum(len(p['tables']) for p in res['provisions'])} tables")

    # keep inventory entries for instruments not touched this run
    inv_path = ROOT / "kb" / "inventory.json"
    if inv_path.exists():
        try:
            prev = json.loads(inv_path.read_text())
        except Exception:
            prev = {}
        for k, v in prev.items():
            if k not in inventory:
                inventory[k] = v
    inv_path.write_text(json.dumps(inventory, indent=1, ensure_ascii=False))
    print(f"\ninventory: {len(inventory)} instruments -> kb/inventory.json")


if __name__ == "__main__":
    main()
