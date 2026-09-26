"""Adjudicate a synthetic DA case with an LLM and machine-verify its
citations.

Pipeline (design doc sections 5/8.4 in miniature):
  case facts (proposal.json) + selected KB provisions
      -> LLM returns structured findings, each with a verbatim quote
      -> every quote is machine-checked against the KB text
         (whitespace-insensitive substring; the crawl wraps hyperlink
         names so exact matching over-rejects)
      -> report.json per case under runs/<ts>/

Run with the requests-capable venv:
  .venv-harvest/bin/python mvp/decide.py [case-id ...] [--model M]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent / "kb"
sys.path.insert(0, str(HERE))
import factcheck  # noqa: E402
import llm  # noqa: E402

CASES = HERE / "cases"


def wnorm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def kb_provisions() -> list:
    return json.loads(
        (KB / "provisions" / "warringah_lep_2011.json").read_text())


def provision_by_hid(hid: int) -> dict | None:
    for p in kb_provisions():
        if p["id"] == f"warringah_lep_2011/h{hid}":
            return p
    return None


def tree_node(title_prefix: str) -> dict | None:
    tree = json.loads((KB / "incoming" / "eplanning" / "LEPDCP" /
                       "_tree.json").read_text())
    for n in tree:
        if n["title"].startswith(title_prefix):
            return n
    return None


def render_provision(p: dict) -> str:
    """Provision as text for the prompt (and for citation checking):
    heading + clause text + tables rendered row by row."""
    parts = [f"[{p['heading']}]", p["text"] or ""]
    for t in p.get("tables") or []:
        for r in t["rows"]:
            cells = " | ".join((c or "").strip().replace("\n", " ")
                               for c in r if (c or "").strip())
            if cells:
                parts.append(cells)
    return "\n".join(parts)


# Curated selection for the Frenchs Forest Site-G cases. This is a
# hand-picked stand-in for relevance ranking (a later scaling problem):
# R3 LUT row + general standards + the whole Frenchs Forest Precinct
# part (including the Site-F-only clauses, which are deliberate
# over-application traps).
def selected_provisions() -> list[tuple[str, dict]]:
    out = []
    # Zone R3 LUT (heading = zone name; locate via tree title)
    node = tree_node("Zone R3")
    if node:
        out.append(("LUT-R3", provision_by_hid(node["hid"])))
    for hid, ref in [(111, "4.3"), (163, "4.4"), (180, "4.6")]:
        out.append((ref, provision_by_hid(hid)))
    for prefix, ref in [("8.1 Definitions", "8.1"),
                        ("8.4", "8.4"), ("8.5", "8.5"),
                        ("8.6", "8.6"), ("8.7", "8.7"),
                        ("8.8", "8.8"),
                        ("8.11", "8.11")]:
        node = tree_node(prefix)
        if node:
            out.append((ref, provision_by_hid(node["hid"])))
    out = [(r, p) for r, p in out if p]
    # Split 8.5 into its two independent condition blocks so the model
    # treats design excellence (2)-(3) and the height/storeys trigger
    # (4) as separate matters:
    for i, (ref, p) in enumerate(out):
        if ref == "8.5":
            text = p["text"] or ""
            m = re.search(r"(?m)^\(4\)\s*$", text)
            if m:
                a = {**p, "text": text[:m.start()].strip(), "tables": []}
                b = {**p, "text": text[m.start():].strip(), "tables": []}
                out[i:i + 1] = [("8.5(1)-(3)", a), ("8.5(4)-(5)", b)]
            break
    assert out, "no provisions selected"
    return out


SYSTEM = """You are an experienced senior planning officer adjudicating a
development application (DA) under the Warringah Local Environmental Plan
2011 (LEP 2011). You are given the case record and a set of relevant
LEP provisions (some of which do NOT apply to this case).

Produce ONLY a JSON object of exactly this shape:
{
  "findings": [
    {"provision": "<clause ref you are assessing, e.g. '8.6', '8.5(4)', '4.3', 'LUT-R3'>",
     "determination": "<one of: permitted_with_consent | compliant | contravention | precondition_not_met | design_review_required | indeterminate (use when the record does not allow a determination, e.g. a referenced map is absent - do not substitute an assumption) | not_applicable>",
     "quote": "<a verbatim quotation of 1-3 sentences from the cited provision's text>",
     "reasoning": "<1-3 sentences connecting the quoted requirement to the specific case facts>",
     "confidence": "high | medium | low"}
  ],
  "overall": {
    "outcome": "refused | no_refusal_ground | referral_required",
    "refusal_grounds": ["<provision refs that independently bar consent>"],
    "summary": "<2-4 sentences>"
  }
}

Rules:
- The materials include a DETERMINISTIC FACT CHECKS section: each line
  is a pre-verified arithmetic or structural fact about this case,
  computed by the tool from the case record and the LEP tables (LUT
  block membership, the 8.4 DCP precondition, the 8.5(4) trigger, the
  8.6/8.7 minimums). Use them exactly as given - do not recompute,
  second-guess or contradict any of them, and your findings on those
  clauses must be consistent with them (e.g. if a fact check says the
  8.5(4) trigger does NOT engage, the 8.5(4) finding cannot be
  design_review_required on height or storeys grounds).
- Produce a finding for EVERY provision block listed in the materials,
  including ones that plainly do not apply (report those as
  not_applicable with a one-line reason).
- 'contravention' and 'precondition_not_met' are refusal grounds when
  the clause says consent 'must not be granted' unless a condition is
  met.
- Map-referenced standards: where a clause refers to a map or exhibit
  that is NOT in this record (e.g. the Height of Buildings Map or the
  Floor Space Ratio Map), the determination is 'indeterminate' - even
  if the proposal 'appears' or is 'likely to be' compliant and even if
  no objection is raised. Name the missing item in reasoning. Never
  invent a value (height, FSR, area) from a map you cannot see.
- Clause 8.5 contains TWO independent mechanisms. (2)-(3): 'design
  excellence' is a qualitative judgement made by the consent authority
  ITSELF - it is not decided by a design review panel. (4): a separate
  trigger based solely on height/storeys (higher than 12 metres or 3
  storeys) which requires review by a design review panel. The (4)
  trigger does not depend on design excellence, and design excellence
  is not decided by the panel.
- A design statement prepared by the applicant is an assertion, not
  evidence; where a clause turns on a qualitative judgment, say
  'indeterminate' and what would decide it.
- Numeric thresholds are strict: 'higher than 12 metres' means strictly
  greater than 12 metres, and '3 storeys' in that phrase means MORE
  than 3 storeys (a building of exactly 3 storeys does NOT trigger
  it). Exactly meeting a minimum (e.g. exactly 30 metres of frontage)
  complies.
- Site facts come from the proposal record fields: site.frontage_m is
  the site's street frontage; site.road_frontage_m is the road reserve
  width, not the frontage.
- Each numbered sub-clause block with its own condition (e.g.
  '8.5(1)-(3)' and '8.5(4)-(5)') is its own finding - never merge
  blocks. A finding must never be downgraded to 'not_applicable'
  because the application is 'already failing' on another clause.
- The determination field must be logically consistent with the
  conclusion of your own reasoning.
- 'refusal_grounds' lists only refs whose finding is
  'contravention', 'precondition_not_met' or 'design_review_required'
  - never refs whose finding is 'indeterminate', 'not_applicable' or
  'compliant'.
- Quote text must be verbatim from the provisions, including any em
  dashes or list markers inside the quoted passage (e.g. keep
  'unless—(a) a design review panel...' exactly as printed).
  Line-wrap differences are acceptable; a single trailing ellipsis is
  allowed; no ellipses or omissions inside the quote.
- For a Land Use Table finding use 'permitted_with_consent' when the
  proposed use appears in the with-consent column; quote the
  use-classification row that applies, not the zone objectives.
- outcome: 'refused' only if at least one refusal ground is
  established; 'no_refusal_ground' if none is (even if matters remain
  indeterminate); 'referral_required' only where a mandatory referral
  is triggered and unresolved (for this record, a design review panel
  under 8.5(4) - never design excellence, which is the consent
  authority's own judgment)."""


def build_user_message(proposal: dict, provisions,
                       facts: list | None = None) -> str:
    doc = []
    doc.append("=== CASE RECORD ===")
    doc.append(json.dumps(proposal, indent=1))
    if facts:
        doc.append("\n" + factcheck.render_facts(facts))
    doc.append("\n=== LEP 2011 PROVISIONS (selected) ===")
    for ref, p in provisions:
        doc.append(f"\n----- {ref} -----\n{render_provision(p)}")
    doc.append("\nRecord note: the maps referenced by clauses 4.3 and "
               "4.4 (the Height of Buildings Map and the Floor Space "
               "Ratio Map) are NOT included in this record; any "
               "determination under 4.3 or 4.4 must reflect that.")
    doc.append("\nAssess the case against these provisions and return "
               "the JSON object.")
    return "\n".join(doc)


def verify_citation(quote: str, provisions) -> dict:
    """Check the quote appears (whitespace-insensitive) in one of the
    provided provisions. A single trailing ellipsis (standard quote
    convention) is stripped before matching and recorded.
    Returns {verified, matched_ref, ellipsis_stripped, len}."""
    ellipsis_stripped = False
    q = quote.rstrip()
    if q.endswith(("…", "...")):
        q = q[:-1].rstrip()
        ellipsis_stripped = True
    q = wnorm(q)
    if len(q) < 12:
        return {"verified": False, "matched_ref": None,
                "ellipsis_stripped": ellipsis_stripped,
                "reason": "quote too short", "len": len(q)}
    for ref, p in provisions:
        hay = wnorm(render_provision(p))
        if q in hay:
            return {"verified": True, "matched_ref": ref,
                    "ellipsis_stripped": ellipsis_stripped,
                    "reason": None, "len": len(q)}
    return {"verified": False, "matched_ref": None,
            "ellipsis_stripped": ellipsis_stripped,
            "reason": "no provision contains this quote", "len": len(q)}


FAMILIES = {
    "compliant": {"compliant", "permitted_with_consent"},
    "contravention": {"contravention", "precondition_not_met"},
    "indeterminate": {"indeterminate"},
    "not_applicable": {"not_applicable"},
    "design_review_required": {"design_review_required"},
}


def family_of(det: str) -> str | None:
    for fam, members in FAMILIES.items():
        if det in members:
            return fam
    return None


def reasoning_family(r: str) -> str | None:
    """Classify the CONCLUSION of the reasoning (last sentence only, so
    quoted clause text earlier in the reasoning cannot mislead)."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+",
                                         (r or "").strip()) if s]
    w = wnorm(sents[-1] if sents else r)
    if "cannotbedetermined" in w or "indeterminate" in w \
            or "cannotbeascertained" in w or "impossibletodetermine" in w:
        return "indeterminate"
    if "doesnotapply" in w or "notrelevant" in w or "notapplicable" in w \
            or "doesnotcreateabasis" in w or "nobasis" in w \
            or "notyetestablished" in w or "notestablished" in w \
            or "nocontravention" in w:
        return "not_applicable"
    if ("designreviewpanel" in w or "reviewpanel" in w
            or "designreview" in w) \
            and ("required" in w or "must" in w or "threshold" in w) \
            and not ("hasnot" in w or "cannotbedetermined" in w
                     or "notbeen" in w):
        return "design_review_required"
    if any(k in w for k in ("compliant", "complieswith", "complies",
                            "meetsthe", "meetsorexceeds", "satisfies")):
        return "compliant"
    if any(k in w for k in ("contraven", "breach", "violation",
                            "noncompliant", "exceeds")):
        return "contravention"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*",
                    default=[p.name for p in CASES.iterdir() if p.is_dir()])
    ap.add_argument("--model", default=None,
                    help="OpenRouter model id (default from config)")
    args = ap.parse_args()

    config = llm.load_config()
    engine = llm.get_llm(config, args.model)
    provisions = selected_provisions()
    prov_map = {ref: p for ref, p in provisions}
    print(f"model: {engine.model}  | provisions: {list(prov_map)}")

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = HERE / "runs" / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    for case_id in args.cases:
        cdir = CASES / case_id
        proposal = json.loads((cdir / "proposal.json").read_text())
        facts = factcheck.run_fact_checks(proposal)
        user = build_user_message(proposal, provisions, facts)
        result = engine.chat_json(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": user}],
            max_tokens=6000,
            hint="JSON object with 'findings' and 'overall'")
        out = {
            "case_id": case_id,
            "model": engine.model,
            "fact_checks": facts,
            "ms": result.get("ms"), "usd": result.get("usd"),
            "in_tokens": result.get("in_tokens"),
            "out_tokens": result.get("out_tokens"),
            "attempts": result.get("attempts"),
            "llm_error": result.get("error"),
            "raw": result.get("content"),
            "parsed": result.get("json"),
            "citation_checks": [],
        }
        for f in (result.get("json") or {}).get("findings", []):
            # self-consistency: does the determination match the
            # conclusion of the model's own reasoning?
            df = family_of(f.get("determination", ""))
            rf = reasoning_family(f.get("reasoning", ""))
            f["self_inconsistent"] = bool(df and rf and df != rf)
            if f["self_inconsistent"]:
                f["inconsistent_with"] = rf
            check = verify_citation(f.get("quote", ""), provisions)
            out["citation_checks"].append({
                "provision": f.get("provision"),
                "determination": f.get("determination"),
                "quote": f.get("quote"),
                "self_inconsistent": f["self_inconsistent"],
                **check})
        (run_dir / case_id / "report.json").parent.mkdir(
            parents=True, exist_ok=True)
        (run_dir / case_id / "report.json").write_text(
            json.dumps(out, indent=1))
        n = len(out["citation_checks"])
        v = sum(1 for c in out["citation_checks"] if c["verified"])
        inc = sum(1 for c in out["citation_checks"]
                  if c.get("self_inconsistent"))
        verdict = (result.get("json") or {}).get("overall", {}).get(
            "outcome", "?")
        print(f"  {case_id}: findings={n} citations_verified={v}/{n} "
              f"self_inconsistent={inc} "
              f"outcome={verdict} usd=${result.get('usd', 0):.4f} "
              f"ms={result.get('ms')}")
    print(f"run dir: {run_dir}")


if __name__ == "__main__":
    main()
