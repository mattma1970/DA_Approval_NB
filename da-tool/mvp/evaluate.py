"""Compare a decide.py run against the hand-written golden findings.

Scores, per golden finding (max 1.0):
  0.6 * determination match
      exact = 1; {compliant, permitted_with_consent} = 0.5;
      indeterminate-vs-concrete either way = 0.25; else 0
  0.4 * citation
      verified quote containing a golden 'citation_must_contain'
      phrase = 1; verified only = 0.5; unverified = 0
Plus overall outcome and refusal-ground set checks. Findings the
model raised that match no golden key are listed as 'additional'
(no penalty - they may be legitimate extra observations).

  .venv-harvest/bin/python mvp/evaluate.py [case ...] [--run DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
sys.path.insert(0, str(HERE))


def wnorm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def map_ref(model_ref: str, quote: str, reasoning: str):
    """Map a model finding's provision ref to a golden key."""
    r = wnorm(model_ref)
    hay = wnorm((quote or "") + " " + (reasoning or ""))
    if any(t in r for t in ("lut-r3", "landusetable")) or "r3" in r:
        return "lut_r3"
    if "4.3" in r:
        return "s4_3"
    if "4.4" in r:
        return "s4_4"
    if "4.6" in r:
        return "s4_6"
    if "8.8" in r:
        return "s8_8"
    if "8.11" in r or "police" in hay:
        return "s8_11"
    if "8.4" in r:
        return "s8_4"
    if "8.6" in r:
        return "s8_6"
    if "8.7" in r:
        return "s8_7"
    if "8.5" in r:
        # explicit sub-clause refs take precedence over content
        if "(4)" in r or "(5)" in r:
            return "s8_5_4"
        if any(s in r for s in ("(1)", "(2)", "(3)")):
            return "s8_5_design"
        if "12metres" in hay or "designreviewpanel" in hay \
                or "3storeys" in hay:
            return "s8_5_4"
        return "s8_5_design"
    if "8.5" in hay[:60]:
        return "s8_5_4" if "12metres" in hay or "designreviewpanel" in hay \
            else "s8_5_design"
    return None


DET_SCORE = {
    ("compliant", "compliant"): 1.0,
    ("permitted_with_consent", "permitted_with_consent"): 1.0,
    ("contravention", "contravention"): 1.0,
    ("precondition_not_met", "precondition_not_met"): 1.0,
    ("design_review_required", "design_review_required"): 1.0,
    ("indeterminate", "indeterminate"): 1.0,
    ("not_applicable", "not_applicable"): 1.0,
    ("compliant", "permitted_with_consent"): 0.5,
    ("permitted_with_consent", "compliant"): 0.5,
    ("contravention", "precondition_not_met"): 0.5,
    ("precondition_not_met", "contravention"): 0.5,
}


# golden key -> clause ref, so refusal-ground sets can be compared on
# the model's reference vocabulary
KEY_TO_REF = {
    "lut_r3": "LUT", "s4_3": "4.3", "s4_4": "4.4", "s4_6": "4.6",
    "s8_4": "8.4", "s8_5_4": "8.5(4)", "s8_5_design": "8.5",
    "s8_6": "8.6", "s8_7": "8.7", "s8_8": "8.8", "s8_11": "8.11",
}


def refs_match(a: str, b: str) -> bool:
    a, b = wnorm(a), wnorm(b)
    return a == b or (len(a) >= 3 and len(b) >= 3
                      and (a in b or b in a))


def det_score(expected: str, actual: str) -> float:
    if expected == actual:
        return 1.0
    if (expected, actual) in DET_SCORE:
        return DET_SCORE[(expected, actual)]
    if expected == "indeterminate" or actual == "indeterminate":
        return 0.25
    return 0.0


def cite_score(check: dict | None, must: str) -> float:
    if not check:
        return 0.0
    if not check.get("verified"):
        return 0.0
    return 1.0 if wnorm(must) in wnorm(check.get("quote", "")) \
        else 0.5


def latest_run() -> Path:
    runs = sorted((HERE / "runs").iterdir())
    return runs[-1]


def evaluate_case(case_id: str, run_dir: Path, show: bool = True):
    cdir = CASES / case_id
    golden = json.loads((cdir / "golden.json").read_text())
    report = json.loads((run_dir / case_id / "report.json").read_text())

    findings = (report.get("parsed") or {}).get("findings", [])
    checks = report.get("citation_checks", [])

    by_key = {}
    additional = []
    for f in findings:
        k = map_ref(f.get("provision", ""), f.get("quote", ""),
                    f.get("reasoning", ""))
        if k:
            by_key.setdefault(k, []).append(f)
        else:
            additional.append(f)

    rows = []
    total = 0.0
    for g in golden["findings"]:
        key = g["key"]
        matches = by_key.get(key, [])
        if not matches:
            rows.append((key, g["expected"], "<not reported>",
                         0.0, 0.0, 0.0))
            continue
        f = max(matches, key=lambda m: (
            det_score(g["expected"], m.get("determination", "")),
            len(m.get("quote", ""))))
        det = f.get("determination", "")
        ds = 1.0 if det in (g.get("alt_ok") or []) \
            else det_score(g["expected"], det)
        # a finding whose determination contradicts its own reasoning
        # is discounted even if the label happens to match
        if f.get("self_inconsistent"):
            ds *= 0.5
        quote = f.get("quote", "")
        # citation check entry is keyed by the model's own ref; find the
        # one whose normalised quote matches this finding's quote
        chk = None
        for c in report.get("citation_checks", []):
            if wnorm(c.get("quote", "")) == wnorm(quote) or \
                    (c.get("provision") and wnorm(c["provision"]) ==
                     wnorm(f.get("provision", ""))):
                chk = c
                break
        cs = cite_score(chk, g["citation_must_contain"]) if chk \
            else (0.5 if any(wnorm(g["citation_must_contain"]) in
                             wnorm(c.get("quote", "")) and
                             c.get("verified")
                             for c in report.get("citation_checks", []))
                 else 0.0)
        score = 0.6 * ds + 0.4 * cs
        total += score
        rows.append((key, g["expected"], f.get("determination", "?"),
                     ds, cs, score, bool(f.get("self_inconsistent"))))

    overall = (report.get("parsed") or {}).get("overall", {})
    outcome_ok = overall.get("outcome") == golden["expected_outcome"]
    grounds = [g for g in (overall.get("refusal_grounds") or [])]
    exp_grounds = set(golden["expected_refusal_grounds"])
    exp_refs = [KEY_TO_REF[k] for k in exp_grounds if k in KEY_TO_REF]
    # a model ground 'covers' an expected one if the refs match loosely;
    # extra model grounds count as over-refusal only if none match an
    # expected ref.
    matched_exp = set()
    for g in grounds:
        for er, k in zip(exp_refs, exp_grounds):
            if k not in matched_exp and refs_match(g, er):
                matched_exp.add(k)
    missing = exp_grounds - matched_exp
    extra = [g for g in grounds
             if not any(refs_match(g, er) for er in exp_refs)]
    grounds_ok = not missing and not extra

    if show:
        print(f"\n=== {case_id} ===")
        print(f"  {'golden key':<14} {'expected':<24} {'model':<24}"
              f"{'det':>4} {'cit':>4} {'score':>6}")
        for row in rows:
            key, exp, act, ds, cs, sc = row[:6]
            warn = " (self-inconsistent!)" if len(row) > 6 \
                and row[6] else ""
            mark = "+" if ds == 1 else ("~" if ds >= 0.5 else "-")
            print(f"  {key:<14} {exp:<24} {str(act)[:22]:<24}"
                  f"{mark}{ds:>3.1f} {cs:>4.1f} {sc:>6.2f}{warn}")
        print(f"  overall: expected={golden['expected_outcome']} "
              f"model={overall.get('outcome')} -> "
              f"{'OK' if outcome_ok else 'WRONG'}")
        print(f"  refusal grounds: expected refs={exp_refs} "
              f"model={sorted(grounds)} -> "
              f"{'OK' if grounds_ok else 'DIFF'}"
              + (f" (missing={sorted(missing)} extra={extra})"
                 if not grounds_ok else ""))
        for a in additional:
            print(f"  additional finding (not in golden): "
                  f"{a.get('provision')} -> {a.get('determination')}")
        n = len(golden["findings"])
        print(f"  case score: {total / n:.2f} ({n} findings) | "
              f"usd=${report.get('usd', 0):.4f}")

    return {
        "case_id": case_id,
        "findings": [
            {"key": k, "expected": e, "model": a, "det_score": ds,
             "cite_score": cs, "score": sc,
             "self_inconsistent": bool(r[0]) if r else False}
            for k, e, a, ds, cs, sc, *r in rows],
        "expected_outcome": golden["expected_outcome"],
        "model_outcome": overall.get("outcome"),
        "outcome_ok": outcome_ok,
        "expected_grounds": sorted(exp_grounds),
        "expected_ground_refs": exp_refs,
        "model_grounds": sorted(grounds),
        "grounds_missing": sorted(missing),
        "grounds_extra": extra,
        "grounds_ok": grounds_ok,
        "additional": [
            {"provision": a.get("provision"),
             "determination": a.get("determination")}
            for a in additional],
        "case_score": round(total / len(golden["findings"]), 3),
        "usd": report.get("usd"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*",
                    default=[p.name for p in CASES.iterdir() if p.is_dir()])
    ap.add_argument("--run", default=None,
                    help="run dir (default: most recent)")
    args = ap.parse_args()

    run_dir = Path(args.run) if args.run else latest_run()
    print(f"evaluating run: {run_dir}")
    results = []
    for case_id in args.cases:
        if not (run_dir / case_id / "report.json").exists():
            print(f"  {case_id}: no report in this run, skipping")
            continue
        results.append(evaluate_case(case_id, run_dir))
    summary = {
        "run": str(run_dir),
        "cases": results,
        "avg_case_score": round(sum(r["case_score"] for r in results) /
                                max(1, len(results)), 3) if results else None,
        "outcome_acc": round(sum(r["outcome_ok"] for r in results) /
                             max(1, len(results)), 3) if results else None,
    }
    if results:
        out = run_dir / "evaluation.json"
        out.write_text(json.dumps(summary, indent=1))
        print(f"\navg case score: {summary['avg_case_score']} | "
              f"outcome accuracy: {summary['outcome_acc']}")
        print(f"saved: {out}")


if __name__ == "__main__":
    main()
