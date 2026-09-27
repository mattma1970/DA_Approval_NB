# 05 — Spike register (de-risking experiments)

**Status: DRAFT** · written 2026-09-27 · the standing list of unknowns,
each with a bounded experiment and a **pre-registered** verdict rule.

## The protocol

1. **Pre-registration is the rule.** Each spike's pass/fail thresholds
   are written here *before the spike runs*. A threshold changed after
   results exist voids the spike: you file it as a new number (e.g.
   A2). This is the whole point — a spike with movable goals is a story,
   not an experiment.
2. **One-way door.** A spike's verdict goes to the decision log, *then*
   the relevant contract line (01/02/03/04) is updated. Nothing else
   enters a contract document.
3. **Budgets are real.** Each spike states its expected OpenRouter cost;
   total register spend must fit the standing $4 cap (spend to date
   ≈$0.022, `mvp/spend.json`).
4. **Bounded.** A spike is a script plus a number, not a product. Its
   artefacts (data, diff lists, scorecards) are kept; the code may be
   thrown away.
5. **Order is fixed by dependency:** A → B → C. D is parked until its
   trigger. No new spike may be started while an earlier one is
   unresolved, unless it blocks it.

---

## A — KB fidelity audit ("does the KB say what the legislation says?")

- **Question:** is the parse faithful? (The self-referential hole, 04 §5:
  everything validated so far checks model↔KB, not KB↔law.)
- **Bears on:** 02 (data contract, quality table), 01 layer ②, 04 claim
  register row 4; prerequisite for B (you can't trust retrieval results
  over a KB you haven't verified) and for all further KB-dependent work.
- **Method:**
  1. Per instrument, sample: **all** provisions whose tables are
     decision-relevant (LUT-like: ≥3 columns — block identity rides on
     them) + 10 random table provisions (max) + 15 random prose
     provisions. (Warringah: 148 provisions, so most of the decision
     table is in-sample; others scale down.)
  2. For each sampled provision, an OpenRouter call diffs the KB record
     against the corresponding source (ePlanning HTML / council PDF text
     in `kb/incoming/`), emitting a structured mismatch list
     (field, KB value, source value, severity: transcription-error /
     normalisation-artefact / model-diff-error).
  3. **I adjudicate every mismatch** (the LLM diffs; a human rules).
     Artefacts we already understand (hyperlink wrapping, flattened
     headers) are classed, not counted.
- **Budget:** ≈$0.50–2 (Gemma-3-27B-class diff calls, ~200–300 items).
- **Pass (pre-registered):** prose fidelity ≥ 95% of sampled provisions
  with no *decision-relevant* transcription error; sampled LUT/table rows
  **100%** — or each miss documented in the KB (a note field) and shown
  not to change any determination.
- **Fail / kill:** a *systemic* pattern (e.g. header flattening silently
  re-ordered a block, or numbers shifted between schedules) → **stop all
  KB-dependent validation**; ingest v2 (typed fields, named LUT blocks,
  02) becomes the next build, ahead of everything. Localised misses →
  patch the KB, record the fix, re-run the affected diffs.
- **Status:** queued — first, on document freeze.

## B — Retrieval feasibility ("can we even *find* the right clauses?")

- **Question:** is the KB structured well enough to index, and can a
  zero-infrastructure baseline retrieve the right provisions for natural
  language questions? (Your RAG worry, tested *before* any RAG is built.)
- **Bears on:** 01 layer ③ assumption (a), 03 row 2 (Phase 2 retrieval),
  02 (path/heading well-formedness).
- **Method:**
  1. **Well-formedness** (free script): per instrument — provision number
     unique? heading present? path depth sane? tables have consistent
     column counts? Report as a quality table (feeds 02).
  2. **BM25-only index** over `heading + number + text` (pure Python,
     ~30 lines, no new dependency, no Qdrant, no embeddings, **no LLM**).
  3. **Query set, human-authored:** from the 2 golden cases' 22 findings,
     write natural-language paraphrases ("What minimum site area applies
     to dual occupancy in R3 in Warringah?") each with its expected
     provision id(s). (I draft; you correct — this is human-authored
     core, not agent-generated.)
  4. Measure recall@10 and precision@10 per query, on
     `warringah_lep_2011` (148 provisions — a clean test of the
     *mechanism*; scale to 1,317 is a Phase-2 concern, not a spike
     concern).
- **Budget:** ≈$0 (no LLM in the loop).
- **Pass (pre-registered):** recall@10 ≥ 0.9 and precision@10 ≥ 0.5 on
  the query set.
- **Fail — with a built-in diagnosis (the value of the spike):**
  - if well-formedness is the failure (bad numbers/paths) → the fix is
    **ingest v2**, not a better retriever;
  - if well-formedness is fine but BM25 misses → the gap is *semantic*
    (prose vs question vocabulary) → a dense index (bge-m3-class, design
    doc §5.7) is the justified remedy, and the risk is quantified.
- **Status:** queued — after A.

## C — LLM selection pass ("can a model pick the applicable provisions?")

- **Question:** given the full provision catalogue (not a hand-picked
  12-block list), can one LLM call return the id set that the golden
  key says applies?
- **Bears on:** the **biggest unvalidated gap** in the final product
  (01 layer ③ assumption (a); 04 claim register row 5); the first
  sub-component of Phase 1 (03 row 4).
- **Method:** per golden case, one OpenRouter call (Gemma-3-27B, then
  Llama-3.3-70B; temperature 0; 2 calls each for variance). Input: the
  `warringah_lep_2011` catalogue — id + heading + first ~200 chars of
  each of the 148 provisions (~9k tokens; fits comfortably). Output:
  list of provision ids. **Every returned id is machine-checked to
  exist** (same verification discipline as citations — a hallucinated id
  is a hard failure, recorded). Precision/recall measured against
  `golden.json`'s 11 findings per case.
- **Budget:** ≈$0.25–0.50 (8 calls).
- **Pass (pre-registered):** recall ≥ 0.85 and precision ≥ 0.7, with
  zero hallucinated ids, on both cases.
- **Fail:** selection stays **deterministic/curated** (the Phase-1
  skeleton — instrument + zone + use + site flags — remains the design
  doc's Layer 3A) and the LLM catalogue pass is revisited at scale (with
  the hybrid index from B's verdict) rather than now.
- **Status:** queued — after B.

## D — Local-CPU model gate *(parked, trigger-based)*

- **Question:** can a **different** local 27B-class GGUF (the excluded
  models guard makes this mandatory) run a full case acceptably on this
  hardware, as the no-cloud proof the "runs locally" gate was deferred
  for?
- **Knowns (2026-09):** 27B Q4 loads in 8.8 s, 3–5 tok/s, ~20 GB of 61 GB
  RAM; a case is a few thousand output tokens → ≈20–40 min per case.
- **Trigger:** you decide to revive it (decision log, standing
  "deferred, not dropped"). Not on the critical path.
- **Method (if triggered):** download e.g. an unsloth Gemma-3-27B GGUF
  (never `Qwen3.8-27B` — the coding model, `excluded_models` guard), run
  both cases through the existing `local_gguf` provider in
  `mvp/llm.py`.
- **Pass (pre-registered):** both cases complete in under 2 h wall time
  with ≥90% citations verified and outcomes matching the OpenRouter runs
  (the 8.5(4) boundary correct — the fact layer should make model
  size mostly irrelevant to it).
- **Status:** parked.

---

## Standing rule

No new component may enter 01 or 03 whose effectiveness is unproven,
without a row in this register. Unknowns get **filed**, never silently
built. This register is append-only; verdicts and threshold changes are
never deleted, only superseded by new numbers.

**Total register budget: ≈$1–3**, against the $4 standing cap (≈$0.022
spent to date). A + B together cost essentially nothing and both produce
the numbers the rest of the plan is waiting on.
