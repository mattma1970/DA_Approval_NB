"""Build the synthetic Frenchs Forest DA cases for the MVP.

Two cases on Site G, Frenchs Forest Precinct (Warringah LEP 2011 Part 8),
Zone R3, residential flat building:

  ff-g-rfb-bulk-breach   1,150 m2 lot, 32 m frontage, 4 storeys / 13.5 m,
                         no site-specific DCP  ->  expected REFUSED
  ff-g-rfb-compliant     1,500 m2 lot, 30 m frontage, 3 storeys / 11.5 m,
                         DCP adopted 10/09/2026 ->  expected no refusal ground

Each case dir gets: proposal.json (form-like facts), documents/*.pdf
(vector drawings + design statement, PyMuPDF), golden.json (hand-written
expected findings for evaluate.py). All content is fictional; nothing
here is a real application or real person.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
KB = HERE.parent.parent / "kb"

# ------------------------------------------------------------------ KB ---

def kb_provisions() -> list:
    return json.loads(
        (KB / "provisions" / "warringah_lep_2011.json").read_text())


def norm(s: str) -> str:
    return " ".join((s or "").split()).lower()


def norm2(s: str) -> str:
    """Whitespace-erased comparison form. Needed because the ePlanning
    crawl wraps hyperlink names (e.g. 'Height of Buildings Map' ->
    'BuildingsMap'), so exact substring checks over-quote-fail."""
    return re.sub(r"\s+", "", (s or "")).lower()


def find_provision(heading_prefix: str):
    hits = [p for p in kb_provisions()
            if norm(p["heading"] or "").startswith(norm(heading_prefix))]
    if hits:
        return hits[0]
    # zone LUT nodes: heading is the zone *name* (e.g. "Medium Density
    # Residential"); the tree title carries the code ("Zone R3 ...").
    tree = json.loads((KB / "incoming" / "eplanning" / "LEPDCP" /
                       "_tree.json").read_text())
    nodes = [n for n in tree
             if norm(n["title"]).startswith(norm(heading_prefix))]
    assert nodes, f"no KB provision or tree node for {heading_prefix!r}"
    node = nodes[0]
    hits = [p for p in kb_provisions()
            if p["id"] == f"warringah_lep_2011/h{node['hid']}"]
    assert hits, f"tree node {node['title']} has no provision"
    return hits[0]


def provision_text(hid: int) -> str:
    for p in kb_provisions():
        if p["id"] == f"warringah_lep_2011/h{hid}":
            return p["text"] or ""
    raise KeyError(hid)


# Citation anchors: (provision ref, phrase that must appear in KB text).
# Every anchor is verified against the KB before the case is written.
ANCHORS = [
    ("lut_r3",   "Zone R3",
     ["Residential flat buildings"]),
    ("s4_3",     "4.3",
     ["not to exceed the maximum height shown for the land on the",
      "Height of Buildings Map"]),
    ("s4_4",     "4.4",
     ["not to exceed the floor space ratio shown for the land on the",
      "Floor Space Ratio Map"]),
    ("s4_6",     "4.6",
     ["Development consent may, subject to this clause, be granted for "
      "development even though the development would contravene a "
      "development standard"]),
    ("s8_4",     "8.4",
     ["Development consent must not be granted to development on land in the",
      "Frenchs Forest Precinct unless a development control plan has been "
      "prepared for the land"]),
    ("s8_5",     "8.5",
     ["Development consent must not be granted unless the consent authority "
      "considers that the development exhibits design excellence",
      "higher than 12 metres or 3 storeys",
      "a design review panel has reviewed the development"]),
    ("s8_6",     "8.6",
     ["unless the site area is equal to or greater than the area shown in "
      "Column 4",
      "1,400 square metres"]),
    ("s8_7",     "8.7",
     ["unless the street frontage of the site area is equal to or greater "
      "than the length shown in Column 4",
      "30 metres"]),
    ("s8_8",     "8.8",
     ["Development consent must not be granted to development on Site F",
      "5,500 square metres"]),
    ("s8_11",    "8.11",
     ["relocation of the Frenchs Forest Police Station"]),
]


def verify_anchors() -> dict:
    """Return {key: [anchor phrases]} after checking each phrase occurs in
    the KB provision text (whitespace-normalised). Aborts on failure."""
    out = {}
    for key, heading, phrases in ANCHORS:
        p = find_provision(heading)
        text = norm(p["text"] or "")
        for ph in phrases:
            if norm2(ph) not in norm2(text):
                # try matching against table cells too
                ttext = norm2(" ".join(
                    c for t in (p["tables"] or []) for r in t["rows"]
                    for c in r))
                assert norm2(ph) in ttext, (
                    f"anchor NOT in KB: {key} -> {ph!r}")
        out[key] = phrases
        print(f"  anchor ok: {key} ({heading}) x{len(phrases)} phrases")
    return out


# ------------------------------------------------------------- drawings ---

def _title_block(page, lines):
    r = fitz.Rect(40, page.rect.height - 78, page.rect.width - 40,
                  page.rect.height - 40)
    page.draw_rect(r, width=1)
    for i, ln in enumerate(lines):
        page.insert_text((48, page.rect.height - 70 + 14 * i), ln,
                         fontsize=9, fontname="helv")


def site_plan(case: dict) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)  # A4 landscape
    s = 5.0  # 1 m = 5 pt
    w, d = case["lot_w_m"] * s, case["lot_d_m"] * s
    x0, y0 = 260, 150
    # road strip
    page.draw_rect(fitz.Rect(x0 - 40, y0 + d, x0 + w + 40,
                             y0 + d + case["road_w_m"] * s),
                   color=None, fill=(0.85, 0.85, 0.85))
    page.insert_text((x0 + 8, y0 + d + case["road_w_m"] * s / 2 + 4),
                     "FRENCHS FOREST ROAD EAST (road reserve "
                     f"{case['road_w_m']} m)", fontsize=10, fontname="hebo")
    # lot
    page.draw_rect(fitz.Rect(x0, y0, x0 + w, y0 + d), width=2)
    page.insert_text((x0 + w / 2 - 70, y0 + d / 2 - 8),
                     f"LOT {case['lot_no']}  DP{case['dp']}",
                     fontsize=12, fontname="hebo")
    page.insert_text((x0 + w / 2 - 60, y0 + d / 2 + 10),
                     f"{case['area_m2']} m2 (approx.)  R3  Site G",
                     fontsize=10)
    # building footprint
    bw = w - 2 * 3.0 * s
    bx = x0 + 3.0 * s
    by = y0 + 4.5 * s
    bh = d - 10.0 * s
    page.draw_rect(fitz.Rect(bx, by, bx + bw, by + bh), color=None,
                   fill=(0.45, 0.5, 0.55), width=1.5)
    page.insert_text((bx + 6, by + 14), "PROPOSED BUILDING "
                     f"({case['storeys']} storeys)", fontsize=8)
    # frontage dimension
    dy = y0 + d + case["road_w_m"] * s + 18
    page.draw_line((x0, dy), (x0 + w, dy))
    page.draw_line((x0, dy - 5), (x0, dy + 5))
    page.draw_line((x0 + w, dy - 5), (x0 + w, dy + 5))
    page.insert_text((x0 + w / 2 - 30, dy - 6),
                     f"{case['frontage_m']} m FRONTAGE", fontsize=9,
                     fontname="hebo")
    # north arrow
    nx, ny = 60, 80
    page.draw_line((nx, ny), (nx, ny - 34), width=2)
    page.draw_line((nx, ny - 34), (nx - 6, ny - 24))
    page.draw_line((nx, ny - 34), (nx + 6, ny - 24))
    page.insert_text((nx - 4, ny + 12), "N", fontsize=12, fontname="hebo")
    _title_block(page, [
        f"{case['id']} - SITE PLAN  SP-01",
        f"{case['address']}",
        "SYNTHETIC CASE (fictional) - MVP  Sept 2026",
        "Scale 1:500 @ A4 landscape",
    ])
    p = case["dir"] / "documents" / "site-plan.pdf"
    doc.save(p)
    doc.close()
    return p


def elevation(case: dict) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    s = 12.0  # 1 m = 12 pt
    x0, ground = 120, 560
    h = case["height_m"] * s
    w = 240
    # storeys
    fh = 3.2 * s
    for i in range(case["storeys"]):
        top = ground - (i + 1) * fh
        page.draw_line((x0, top), (x0 + w, top), width=1)
        for j in range(4):  # window bays
            wx = x0 + 18 + j * 54
            page.draw_rect(fitz.Rect(wx, top + 8, wx + 34, top + fh - 8),
                           width=0.8)
    page.draw_rect(fitz.Rect(x0, ground - h, x0 + w, ground), width=2)
    page.draw_line((x0 - 30, ground), (x0 + w + 60, ground), width=1.5)
    # height dimension
    xd = x0 + w + 40
    page.draw_line((xd, ground), (xd, ground - h))
    page.draw_line((xd - 5, ground), (xd + 5, ground))
    page.draw_line((xd - 5, ground - h), (xd + 5, ground - h))
    page.insert_textbox(fitz.Rect(xd + 8, ground - h, xd + 70, ground),
                        f"{case['height_m']} m\nto top of building",
                        fontsize=10, fontname="hebo")
    # 12 m trigger line
    y12 = ground - 12 * s
    page.draw_line((x0 - 30, y12), (x0 + w + 60, y12), color=(1, 0, 0),
                   dashes="[4 4]")
    page.insert_text((x0 - 28, y12 - 12),
                     "12 m - cl 8.5(4) design review panel trigger",
                     fontsize=9, color=(1, 0, 0))
    # 12 m above ground only makes sense if building exceeds it:
    if case["height_m"] <= 12:
        page.insert_text((x0 - 28, y12 + 4),
                         "(building below trigger)", fontsize=8,
                         color=(1, 0, 0))
    _title_block(page, [
        f"{case['id']} - STREET ELEVATION  E-01",
        case["address"],
        "SYNTHETIC CASE (fictional) - MVP  Sept 2026",
    ])
    p = case["dir"] / "documents" / "elevation.pdf"
    doc.save(p)
    doc.close()
    return p


def concept(case: dict) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    s = 10.0
    x0, ground = 110, 600
    h = case["height_m"] * s
    w = 260
    bands = 14
    for i in range(bands):  # boardmarked weatherboard bands
        t = i / bands
        top = ground - (i + 1) * (h / bands)
        shade = 0.72 + 0.05 * (i % 3)
        page.draw_rect(fitz.Rect(x0, top, x0 + w, top + h / bands),
                       color=None, fill=(shade, shade * 0.98, shade * 0.93))
    # stone base
    page.draw_rect(fitz.Rect(x0, ground - 1.2 * s, x0 + w, ground),
                   color=None, fill=(0.55, 0.5, 0.45))
    # roof
    page.draw_rect(fitz.Rect(x0 - 8, ground - h - 14, x0 + w + 8,
                             ground - h), color=None, fill=(0.3, 0.3, 0.32))
    # entry recess
    page.draw_rect(fitz.Rect(x0 + 110, ground - 3.4 * s, x0 + 160, ground),
                   color=None, fill=(0.85, 0.82, 0.78))
    page.draw_line((x0 - 40, ground), (x0 + w + 90, ground), width=1.5)
    _title_block(page, [
        f"{case['id']} - CONCEPT (artist's impression, indicative)  C-01",
        case["address"],
        "SYNTHETIC CASE (fictional) - MVP  Sept 2026",
    ])
    p = case["dir"] / "documents" / "concept.pdf"
    doc.save(p)
    doc.close()
    return p


def design_statement(case: dict) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    body = fitz.Rect(60, 90, 535, 780)
    parts = [
        f"DESIGN STATEMENT - {case['id']}",
        "",
        f"{case['address']} (Zone R3; Site G, Frenchs Forest Precinct)",
        "",
    ]
    parts += case["ds_paras"]
    parts += [
        "",
        "The applicant submits that the development exhibits 'design "
        "excellence' within the meaning of clause 8.5 of the Warringah "
        "Local Environmental Plan 2011 and that all site-specific "
        "requirements of Part 8 of that Plan are met.",
        "",
        "(Synthetic document - fictional. Statements are the applicant's "
        "own and are not independently verified.)",
    ]
    text = "\n".join(parts)
    rc = page.insert_textbox(body, text, fontsize=10.5, fontname="helv")
    assert rc >= 0, "design statement overflow"
    p = case["dir"] / "documents" / "design-statement.pdf"
    doc.save(p)
    doc.close()
    return p


# --------------------------------------------------------------- cases ---

DS_BULK = [
    "The proposed four-storey residential flat building provides four "
    "dwellings over a basement car park. The design responds to the "
    "precinct's rising skyline with a stepped roof form that, in the "
    "applicant's view, preserves winter solar access to the street and to "
    "the lagoon views to the south.",
    "A high standard of architectural design, materials and detailing will "
    "be achieved: a boardmarked weatherboard and natural stone palette, "
    "dark metal joinery, and a recessed entry terrace that contributes to "
    "the public domain. Two mature trees are retained and permeable "
    "paving is provided across the street-facing area.",
    "The building's 13.5 m height is justified as consistent with the "
    "precinct's west-to-east height transition. Overshadowing to adjacent "
    "lots will be negligible given the site's orientation.",
]

DS_COMP = [
    "The proposed three-storey residential flat building provides four "
    "dwellings over a basement car park. The massing is deliberately "
    "modest, respecting the prevailing two-to-three storey streetscape "
    "while providing a consistent street wall.",
    "A high standard of architectural design, materials and detailing will "
    "be achieved: a boardmarked weatherboard palette with natural stone "
    "base, a deep entry reveal, and generous permeable paving. Mature "
    "trees are retained and the roof form steps down toward the rear "
    "boundary.",
]

CASES = [
    {
        "id": "ff-g-rfb-bulk-breach",
        "title": "Demolition and construction of a 4-storey residential "
                 "flat building (4 dwellings) on a sub-minimum site",
        "address": "12 Frenchs Forest Road East, Frenchs Forest (fictional)",
        "lot_no": "SP12345", "dp": "123456",
        "zone": "R3 Medium Density Residential (Warringah LEP 2011)",
        "precinct_site": "Site G, Frenchs Forest Precinct (Part 8)",
        "lot_w_m": 32.0, "lot_d_m": 35.9, "area_m2": "1,150",
        "frontage_m": "32", "road_w_m": 9.1,
        "use": "Residential flat building (4 dwellings)",
        "storeys": 4, "height_m": 13.5, "fsr": 1.4,
        "site_coverage_pct": 45,
        "carpark": "Basement, 4 spaces", "demolition": True,
        "dcp": {"present": False,
                "note": "No site-specific development control plan has "
                        "been prepared for this site."},
        "ds_paras": DS_BULK,
        "expected_outcome": "refused",
        "findings": [
            {"key": "lut_r3", "provision": "LEP 2011 Pt 2 - Zone R3 Land "
             "Use Table", "expected": "permitted_with_consent",
             "citation_must_contain": "Residential flat buildings",
             "notes": "RFB is in the 'with development consent' block; "
                      "not a refusal ground. Trap: a model reading the "
                      "flattened text as one list might miscall the "
                      "column."},
            {"key": "s8_4", "provision": "LEP 2011 8.4 Development "
             "control plans", "expected": "precondition_not_met",
             "citation_must_contain": "development control plan has been "
             "prepared", "notes": "REFUSAL GROUND 1: 'must not be "
             "granted ... unless a development control plan has been "
             "prepared'. No DCP in the record."},
            {"key": "s8_6", "provision": "LEP 2011 8.6 Minimum site "
             "areas", "expected": "contravention",
             "citation_must_contain": "1,400 square metres",
             "notes": "REFUSAL GROUND 2: 1,150 m2 < 1,400 m2 for RFB on "
                      "Site G / R3."},
            {"key": "s8_7", "provision": "LEP 2011 8.7 Minimum street "
             "frontages", "expected": "compliant",
             "citation_must_contain": "30 metres",
             "notes": "32 m >= 30 m. Contrast finding: not every "
                      "Part 8 table bites here."},
            {"key": "s8_5_4", "provision": "LEP 2011 8.5(4)",
             "expected": "design_review_required",
             "citation_must_contain": "higher than 12 metres or 3 storeys",
             "notes": "13.5 m > 12 m AND 4 storeys > 3: consent must not "
                      "be granted unless a design review panel has "
                      "reviewed the development. Process finding."},
            {"key": "s8_5_design", "provision": "LEP 2011 8.5(2)-(3)",
             "expected": "indeterminate",
             "citation_must_contain": "exhibits design excellence",
             "notes": "SUBJECTIVE: the record contains only the "
                      "applicant's self-assertion. Correct behaviour: do "
                      "not affirm or deny; flag for council / design "
                      "review determination."},
            {"key": "s4_3", "provision": "LEP 2011 4.3 Height of "
             "buildings", "expected": "indeterminate",
             "citation_must_contain": "Height of Buildings Map",
             "notes": "DATA GAP: standard is map-referenced; the map is "
                      "not in the text corpus. Must not invent a number."},
            {"key": "s4_4", "provision": "LEP 2011 4.4 Floor space "
             "ratio", "expected": "indeterminate",
             "citation_must_contain": "Floor Space Ratio Map",
             "notes": "DATA GAP: FSR standard is map-referenced."},
            {"key": "s8_8", "provision": "LEP 2011 8.8 Deep soil zone",
             "expected": "not_applicable",
             "citation_must_contain": "Site F",
             "notes": "TRAP: applies to Site F only; case is Site G. "
                      "Flagging it is an over-application error."},
            {"key": "s8_11", "provision": "LEP 2011 8.11 Police station "
             "relocation", "expected": "not_applicable",
             "citation_must_contain": "relocation of the Frenchs Forest "
             "Police Station",
             "notes": "TRAP: applies to the police station site only."},
            {"key": "s4_6", "provision": "LEP 2011 4.6 Exceptions to "
             "development standards", "expected": "not_applicable",
             "citation_must_contain": "contravene a development "
             "standard",
             "notes": "4.6 flexibility applies to development standards; "
                      "the Part 8 'must not be granted' gates are consent "
                      "conditions, so no variation route for them."},
        ],
        "expected_refusal_grounds": ["s8_4", "s8_6"],
    },
    {
        "id": "ff-g-rfb-compliant",
        "title": "Demolition and construction of a 3-storey residential "
                 "flat building (4 dwellings) meeting Part 8 minimums",
        "address": "18 Frenchs Forest Road East, Frenchs Forest (fictional)",
        "lot_no": "SP12347", "dp": "123456",
        "zone": "R3 Medium Density Residential (Warringah LEP 2011)",
        "precinct_site": "Site G, Frenchs Forest Precinct (Part 8)",
        "lot_w_m": 30.0, "lot_d_m": 50.0, "area_m2": "1,500",
        "frontage_m": "30", "road_w_m": 9.1,
        "use": "Residential flat building (4 dwellings)",
        "storeys": 3, "height_m": 11.5, "fsr": 0.9,
        "site_coverage_pct": 35,
        "carpark": "Basement, 4 spaces", "demolition": True,
        "dcp": {"present": True,
                "note": "Site-specific development control plan for the "
                        "site adopted 10 September 2026; record taken at "
                        "face value."},
        "ds_paras": DS_COMP,
        "expected_outcome": "no_refusal_ground",
        "findings": [
            {"key": "lut_r3", "provision": "LEP 2011 Pt 2 - Zone R3 Land "
             "Use Table", "expected": "permitted_with_consent",
             "citation_must_contain": "Residential flat buildings",
             "notes": "RFB permitted with DA in R3."},
            {"key": "s8_4", "provision": "LEP 2011 8.4 Development "
             "control plans", "expected": "compliant",
             "citation_must_contain": "development control plan has been "
             "prepared",
             "notes": "Site-specific DCP adopted 10/09/2026 - "
                      "precondition met on the record."},
            {"key": "s8_6", "provision": "LEP 2011 8.6 Minimum site "
             "areas", "expected": "compliant",
             "citation_must_contain": "1,400 square metres",
             "notes": "1,500 m2 >= 1,400 m2."},
            {"key": "s8_7", "provision": "LEP 2011 8.7 Minimum street "
             "frontages", "expected": "compliant",
             "citation_must_contain": "30 metres",
             "notes": "BOUNDARY TRAP: 30 m exactly meets 'equal to or "
                      "greater than 30 metres'. Flagging it is an error."},
            {"key": "s8_5_4", "provision": "LEP 2011 8.5(4)",
             "expected": "compliant",
             "citation_must_contain": "higher than 12 metres or 3 storeys",
             "notes": "BOUNDARY TRAP: 11.5 m < 12 m and 3 storeys is NOT "
                      "'higher than 3 storeys'. Trigger not reached. "
                      "'not_applicable' (trigger not engaged) is an "
                      "equally correct labelling of the same conclusion.",
             "alt_ok": ["not_applicable"]},
            {"key": "s8_5_design", "provision": "LEP 2011 8.5(2)-(3)",
             "expected": "indeterminate",
             "citation_must_contain": "exhibits design excellence",
             "notes": "SUBJECTIVE even in the approvable case: design "
                      "excellence remains a matter for the consent "
                      "authority; no refusal ground, but the finding "
                      "should say so, not assert excellence."},
            {"key": "s4_3", "provision": "LEP 2011 4.3 Height of "
             "buildings", "expected": "indeterminate",
             "citation_must_contain": "Height of Buildings Map",
             "notes": "DATA GAP: map-referenced."},
            {"key": "s4_4", "provision": "LEP 2011 4.4 Floor space "
             "ratio", "expected": "indeterminate",
             "citation_must_contain": "Floor Space Ratio Map",
             "notes": "DATA GAP: map-referenced."},
            {"key": "s8_8", "provision": "LEP 2011 8.8 Deep soil zone",
             "expected": "not_applicable",
             "citation_must_contain": "Site F",
             "notes": "TRAP: Site F only."},
            {"key": "s8_11", "provision": "LEP 2011 8.11 Police station "
             "relocation", "expected": "not_applicable",
             "citation_must_contain": "relocation of the Frenchs Forest "
             "Police Station",
             "notes": "TRAP: police station only."},
            {"key": "s4_6", "provision": "LEP 2011 4.6 Exceptions to "
             "development standards", "expected": "not_applicable",
             "citation_must_contain": "contravene a development "
             "standard",
             "notes": "No standard contravention on the record, so no "
                      "4.6 request needed."},
        ],
        "expected_refusal_grounds": [],
    },
]


def build_case(case: dict) -> Path:
    d = HERE / case["id"]
    case["dir"] = d
    (d / "documents").mkdir(parents=True, exist_ok=True)

    proposal = {
        "case_id": case["id"],
        "lga": "Warringah",
        "title": case["title"],
        "synthetic": True,
        "applicant": {"name": "Synthetic Development No. 1 Pty Ltd "
                               "(fictional)"},
        "site": {
            "address": case["address"],
            "lot_dp": f"Lot {case['lot_no']} DP{case['dp']}",
            "zone": case["zone"],
            "precinct_site": case["precinct_site"],
            "area_sqm": int(case["area_m2"].replace(",", "")),
            "frontage_m": int(case["frontage_m"]),
            "lot_dimensions_m": [case["lot_w_m"], case["lot_d_m"]],
            "road_frontage_m": case["road_w_m"],
        },
        "proposal": {
            "use": case["use"],
            "storeys": case["storeys"],
            "max_height_m": case["height_m"],
            "fsr": case["fsr"],
            "site_coverage_pct": case["site_coverage_pct"],
            "carpark": case["carpark"],
            "demolition": case["demolition"],
        },
        "site_specific_dcp": case["dcp"],
        "documents": [
            "documents/site-plan.pdf",
            "documents/elevation.pdf",
            "documents/concept.pdf",
            "documents/design-statement.pdf",
        ],
    }
    (d / "proposal.json").write_text(json.dumps(proposal, indent=2))

    for fn in (site_plan, elevation, concept, design_statement):
        fn(case)

    golden = {
        "case_id": case["id"],
        "expected_outcome": case["expected_outcome"],
        "expected_refusal_grounds": case["expected_refusal_grounds"],
        "findings": case["findings"],
        "determination_enum": [
            "permitted_with_consent", "compliant", "contravention",
            "precondition_not_met", "design_review_required",
            "indeterminate", "not_applicable"],
    }
    (d / "golden.json").write_text(json.dumps(golden, indent=2))
    return d


def main():
    print("verifying citation anchors against KB ...")
    anchors = verify_anchors()
    print("\nbuilding cases ...")
    for c in CASES:
        d = build_case(c)
        n_docs = len(list((d / "documents").glob("*.pdf")))
        print(f"  {d.name}: {n_docs} pdfs, {len(c['findings'])} golden "
              f"findings, outcome={c['expected_outcome']}")


if __name__ == "__main__":
    main()
