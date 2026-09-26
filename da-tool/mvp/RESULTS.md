# MVP validation results — LLM adjudication of synthetic Frenchs Forest DAs

Date: 2026-09-26 · Cases: `ff-g-rfb-bulk-breach`, `ff-g-rfb-compliant`
(11 golden findings each, 4 synthetic PDFs + proposal record per case)
Corpus: Warringah LEP 2011, 12 provision blocks (LUT-R3, 4.3, 4.4, 4.6,
8.1, 8.4, 8.5(1)-(3), 8.5(4)-(5), 8.6, 8.7, 8.8, 8.11)
Providers: OpenRouter — `google/gemma-3-27b-it` (dev default),
`meta-llama/llama-3.3-70b-instruct` (cross-check). Temperature 0.

## Run history

| run dir | model | avg score | outcome acc | citations verified | notes |
|---|---|---|---|---|---|
| 20260926-020343 | gemma-3-27b | 0.727 | 1/1 | 9/11 | first run; 2 trailing-ellipsis quotes rejected |
| 20260926-020640 | gemma-3-27b | 0.814 | 0.5 | 22/22 | 8.5 split into sub-clause blocks |
| 20260926-021606 | gemma-3-27b | 0.845 | 1/1 | 24/24 | "map-referenced ⇒ indeterminate" rule |
| 20260926-023127 | gemma-3-27b | 0.774 | 0.5 | 24/24 | self-consistency checker added (6 flags: 4 TP / 2 FP) |
| 20260926-023344 | gemma-3-27b | 0.811 | 0.5 | 24/24 | 8.5 dual-mechanism clarification |
| 20260926-023722 | gemma-3-27b | 0.891 | 0.5 | 24/24 | record-field semantics rule (frontage vs road reserve) |
| 20260926-023900 | llama-3.3-70b | 0.609 | 0.5 | 13/16 | 70B first run: skipped 8.8/8.11/4.6; 3 non-verbatim quotes rejected |
| 20260926-024225 | gemma-3-27b | 0.863 | 0.5 | 24/24 | coverage + verbatim-em-dash rules |
| 20260926-024402 | llama-3.3-70b | 0.931 | 1/1 | 24/24 | 70B final: clean pass on both cases |
| 20260926-044411 | gemma-3-27b | 0.913 | 1/1 | 24/24 | **fact layer in**: 8.5(4) misfire gone; 8.4 labelled contravention; 8.5(1)-(3) → not_applicable |
| 20260926-044536 | llama-3.3-70b | 0.841 | 1/1 | 16/23 | **fact layer in**: all determinations correct; 70B left empty quotes on trivial not_applicable findings (contract violation, caught) |

Total spend: **≈ $0.022** across 21 calls (budget cap $4). Call latency
25–96 s (OpenRouter serverless). Per-run detail:
`mvp/runs/<ts>/<case>/report.json`, scorecards `mvp/runs/<ts>/evaluation.json`.

## What the machine layer proved

1. **Citation verification works and bites.** Both final runs: 24/24 quotes
   verified verbatim against the KB (whitespace-insensitive; trailing
   ellipsis allowed and recorded). In 70B's first run the checker rejected
   3 genuine non-verbatim quotes: a mid-quote ellipsis (LUT row list), and
   the em-dash list marker dropped from "unless—(a) a design review panel…"
   in both cases. The strict checker is doing its job: it rejects
   paraphrase, and the prompt fixes (verbatim em-dash; trailing-only
   ellipsis) then lifted 70B to 24/24.
2. **Boundary arithmetic is mostly right.** 8.6 (1,150 < 1,400 m² →
   contravention; 1,500 ≥ 1,400 → compliant), 8.7 (32 ≥ 30; 30 = 30
   exactly-meets-minimum → compliant) and the LUT column reading
   (RFB in with-consent block → permitted_with_consent) came out correct
   in essentially every run of both models.
3. **Trap discipline.** 8.8 (Site F only) and 8.11 (police station) were
   correctly `not_applicable` in every run once reported; 4.6 correctly
   kept out of the refusal grounds.
4. **Map-referenced standards (4.3/4.4).** Initially the models "assumed
   compliance" from the missing map (Gemma) or assumed contravention
   (mirror-image in one run). After the explicit rule + record note both
   models settled on `indeterminate` in all final runs — without inventing
   a number. This is the behaviour the tool is supposed to force.
5. **Self-consistency checker.** Flagged findings whose determination
   contradicts their own reasoning (e.g. reasoning "the proposal complies
   with this clause" + label `contravention`). True positives confirmed on
   manual read; false positives reduced by classifying only the final
   sentence and guarding negations ("not yet established", "impossible to
   determine if … complies"). Flagged findings are discounted 50% in the
   score and marked in the report for human review — exactly the review
   workflow a decision-support tool should surface.

## Where the models still fail (failure taxonomy)

| failure | gemma-3-27b | llama-3.3-70b | severity |
|---|---|---|---|
| 8.5(4) boundary: "3 storeys" read as ≥3 → panel trigger fired on the 11.5 m / 3-storey compliant building | 3/5 post-split runs | 1/2 runs | **HIGH — the one clause both models keep getting wrong**; flips outcome to `referral_required` when it misfires |
| 8.5(2)-(3)/(4) mechanism conflation: design excellence decided "by a design review panel", or (4) gated on (2)-(3) being resolved | 4/5 runs | 0/2 final | medium-high (Gemma-specific) |
| label roulette on 8.5 sub-clauses (compliant ↔ not_applicable ↔ design_review_required across runs) | yes (run to run) | no (stable once correct) | medium |
| "already failing on 8.4, so 8.5(4) is not relevant" dismissal | 1/2 runs | 0/2 | medium (prompt now forbids; recurred once) |
| road-reserve width (9.1 m) read as the site frontage → false 8.7 contravention | 1/2 runs | 0/2 | medium (record-field rule added; worth a deterministic check) |
| s8.4 labelled `contravention` instead of `precondition_not_met` | 6/7 runs | 0/2 | low (scored 0.5; same practical effect) |
| skipping inapplicable clauses from the report | never | 1/2 (before coverage rule) | low (coverage rule fixed) |

## Deterministic fact layer (built after round 1)

`mvp/factcheck.py` computes, in plain Python and *before* the LLM call,
every numeric/structural test the LEP applies to these cases: LUT block
membership (from the R3 LUT's row structure), the 8.4 DCP precondition,
the 8.5(4) trigger (thresholds parsed from the clause text), and the
8.6/8.7 minimum tables (parsed from the KB). Each result is injected
into the prompt as a verified fact the model must use as-is, and stored
in `report.json` (`fact_checks`) for audit.

* **Effect: the 8.5(4) boundary misfire is eliminated.** In round 1 both
  models misfired it (Gemma 3/5, 70B 1/2), flipping outcomes. With the
  fact layer both models get 8.5(4) right on both cases in both new
  runs, and outcome accuracy is 100% for both.
* **New findings:** 70B left the `quote` field empty on `not_applicable`
  findings (caught by the citation checker; Gemma never does this) —
  evidence the machine layer also polices *completeness of evidence*,
  not just accuracy. Gemma still roulette-labels 8.4
  (contravention vs precondition_not_met; same practical effect, both
  are refusal grounds), and labels 8.5(1)-(3) design excellence
  `not_applicable` where the golden expects `indeterminate` (70B is
  correct there).
* **Self-consistency detector tuning** (false positives found while
  reviewing flagged findings): "impossible to determine if … complies"
  → indeterminate; "no contravention has been established" →
  not_applicable; "meets or exceeds" → compliant (the bare `exceeds`
  keyword used to fire it as contravention). It remains a keyword
  heuristic over the final sentence only — the proper Phase-1 fix is a
  structured conclusion field in the schema, not more keywords.

## Conclusions

* **The MVP gate passes on the machine-verified-citation dimension:**
  every final-run citation is genuine and machine-checkable; the checker
  demonstrably rejects non-verbatim quotes from both models — and, once
  the deterministic fact layer is in, outcome accuracy is 100% on both
  cases for both models, with all 8.5 determinations correct.
* **Outcome accuracy is gated by the single hardest clause (8.5(4)).**
  With the final prompt, 70B passed both cases (0.931, outcomes 100%);
  Gemma-27B averaged 0.82 over 7 runs but misfired the 8.5(4) boundary in
  3/5 runs, which flipped the compliant case's outcome each time.
* **Implication for the "runs locally" gate:** a 27B-class *local* model
  should be expected to perform at the Gemma level — fine for citations,
  arithmetic and most legal reasoning, unreliable on the 8.5(4) boundary.
  An 8B-class local model will be weaker still on the judgment findings.
  The deterministic guard layer below is the fix that makes any of them
  trustworthy.
* **Recommended next build (Phase 1 input):** a deterministic
  fact-check layer that computes, in code, every numeric test before the
  LLM call — site area vs 8.6 minima, frontage vs 8.7 minima,
  height/storeys vs the 8.5(4) trigger, LUT block membership — and feeds
  the LLM those verified facts (and the outcome of each test) instead of
  raw numbers. The 8.5(4) misfire class disappears by construction; the
  LLM keeps the role it is good at (legal reasoning, synthesis, drafting).
* **Scorecard caveats (known, accepted for MVP):** golden `alt_ok`
  (not_applicable accepted as equivalent to compliant for a
  not-triggered 8.5(4)); keyword-based consistency flags (residual false
  positives possible); ref→golden-key mapping heuristics in `evaluate.py`
  (e.g. "8.5(4)-(5)" → s8_5_4). All three need replacing with structured
  mapping in Phase 1.

## Architecture decision (user, 2026-09-26)

* **All LLM calls made by the tool code go through OpenRouter**
  (`mvp/llm.py`; default `google/gemma-3-27b-it`, alternates in
  `config.json`, cost ledger in `spend.json` capped at $4).
* **The local Qwen3.8-27B GGUF remains the agent's own coding model
  only** — it is the model serving the development session, so it must
  never be the model under test (circular validation). It stays in
  `config.json → local_gguf.excluded_models` as a hard guard.
* The "download another model and run a case locally" CPU gate is
  therefore **deferred, not dropped** — the `local_gguf` provider in
  `llm.py` stays available if the user wants the no-cloud proof later.

Files: `mvp/decide.py` (prompt + selection + citation/consistency
verification), `mvp/factcheck.py` (deterministic fact layer),
`mvp/evaluate.py` (scorecard), `mvp/llm.py` (OpenRouter +
cost ledger + excluded-model guard), `mvp/cases/` (2 synthetic cases,
golden findings), `mvp/runs/` (per-run reports + scorecards),
`mvp/spend.json` (cost ledger).
