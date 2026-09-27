# 01 — Architecture & guarantees

**Status: DRAFT** · written 2026-09-27 · describes the system as it stands
on disk today; unproven things are marked, not hidden (see 05 for the
experiments that would promote them).

## 1. What the system is

An **advisory** decision-support tool for NSW development applications
(Northern Beaches LGA): it reads a DA case and the planning instruments
that apply, and recommends *approve / deny / conditional* with **verbatim,
machine-verified citations** and **deterministic fact-checks**. A human
officer makes the determination. The full target design is
`../../DA-decision-support-design.md` (the "design doc"); this document
describes the **current build** and its guarantees. §6 lists where the
build deviates from the design doc.

## 2. The four layers

```
 ① harvest/         ② kb/                ③ mvp/                  ④ eval
┌──────────────┐   ┌───────────────┐   ┌───────────────────┐   ┌─────────────┐
│ pull law +   │ → │ structure the │ → │ LLM adjudicates   │ → │ score the   │
│ registers    │   │ law into JSON │   │ against ②, checked│   │ report      │
│ (raw docs)   │   │ (the KB)      │   │ by ② + a fact     │   │ against a   │
└──────────────┘   └───────────────┘   │ layer computed    │   │ human golden│
      frozen 2026-09-25    9 instruments   before the LLM     │   │ key         │
                                       └───────────────────┘   └─────────────┘
   OpenRouter (external LLM) and the human officer sit outside the pipeline.
```

A case enters at ③. The LLM writes one finding per applicable provision,
each with a verbatim quote. The machine checks every quote exists in the
KB, checks the model's reasoning against pre-computed facts, and writes
`runs/<ts>/<case>/report.json`. ④ scores that report against a
human-built answer key (`cases/<case>/golden.json`).

## 3. System-wide invariants

These hold across all layers and are the part of the architecture the
2026-09-26 verdict rests on.

| # | Invariant | Enforced by |
|---|---|---|
| I-1 | **Nothing the LLM says is trusted until a machine has checked it.** Every quote is verified verbatim against the KB (whitespace-insensitive; trailing ellipsis allowed and recorded). Every finding is self-consistency-checked (label vs its own reasoning; flagged findings discounted and marked for human review). | `mvp/decide.py` (citation checker, consistency detector) — design doc §8.4 |
| I-2 | **Fail loud, never fail wrong.** Unrecognised structure, missing data (e.g. a map that isn't in the corpus) → `NOT_EVALUATED` / `indeterminate`, explicitly reported — never a guessed answer. | `mvp/factcheck.py` (`NOT_EVALUATED`), prompt rule "map-referenced ⇒ indeterminate" |
| I-3 | **The law is versioned data, never hard-coded code.** Every provision carries provenance (`source.file` + `hid` into the crawl); instruments are versioned JSON. | `kb/ingest.py`, provision schema (02) |
| I-4 | **Material that is considered but not in force is never citable as law.** (Draft DCP 2026 = advisory context only; the status flag in the KB carries this.) | provision `status` field (02) |
| I-5 | **Spend and models are governed.** Hard $4 budget cap, per-call cost ledger, temperature 0, and an excluded-models guard: the model serving this development session (local Qwen3.8-27B) can never be the model under test. | `mvp/config.json`, `mvp/llm.py` |
| I-6 | **Advisory only.** The tool recommends; it never determines. | design doc §1.1; report output |

## 4. Layer by layer

For each layer: **contract** (what goes in, what comes out), **guarantees**
(what is actually evidenced, with where), **assumptions** (what is *not*
evidenced yet, each pointed at the spike or backlog that settles it), and
**promotion gate** (what must be true before the assumptions stop being
assumptions).

### ① harvest — pull data

- **Contract in/out:** external instrument documents (ePlanning exhibits,
  council PDFs, registers) → raw files in `kb/incoming/` plus small JSON
  provenance manifests (tracked in git); the ~1 GB payload stays local,
  git-ignored, frozen.
- **Guarantees:** the 2026-09-25 ePlanning crawl completed with 0 failures
  over 189 pages and produced the corpus that ② ingested (evidence:
  `kb/incoming/eplanning/_crawl-report.json`, frozen; `kb/inventory.json`
  quality-gate report). The rebuild path on another machine is pinned
  (`requirements.txt`, `requirements-harvest.txt`, both dry-run verified).
- **Assumptions:** the crawl *script* is lost (only `harvest/_probe_portal.py`
  remains) — reproducibility currently rests on artifacts + notes, not code
  (backlog #2). Register/consent-notice harvesters are not built (backlog #2,
  second deliverable; spec: `config/golden-set-spec.yaml` workflow step 2).
- **Promotion gate:** rebuilt crawler re-crawls **one** exhibit and diffs
  against the frozen 2026-09-25 artifact → identical = faithful. The sample
  harvester's gate is the golden-set build itself (03, sequence item 4).

### ② kb — structure the law

- **Contract in/out:** instrument documents → `kb/provisions/*.json`:
  9 instruments, **1,317 provisions** (counted 2026-09-27), each a
  provision-shaped record per the data contract (02).
- **Guarantees:** parse *completeness* against the crawl manifest — every
  exhibit's pages are accounted for in the inventory report; the one LUT
  used by the MVP (Warringah LEP 2011, R3) was **hand-verified** block by
  block. Clause lookup works (`kb/query.py`).
- **Assumptions:** text **fidelity** of the parse (does the JSON say what
  the PDF/HTML says?) — **unaudited**; this is the self-referential hole:
  our validation checks model↔KB fidelity, not KB↔law fidelity (Spike A).
  LUT block identity is *positional* (crawl dropped column headers) and
  verified only for R3 (02, warts). Provision-number normalisation is
  known-imperfect (backlog #1). Map-referenced standards (4.3/4.4) are
  correctly unanswerable — the maps are absent; that is the system
  working as designed, not a gap.
- **Promotion gate:** **Spike A** (05) — sampled fidelity audit per
  instrument with pre-registered thresholds.

### ③ mvp — LLM adjudication + machine verification

- **Contract in/out:** a case (record `proposal.json` + document PDFs) and
  a **selected set** of provisions in → `report.json` per case: findings
  (determination + reasoning + verbatim quote per provision), `fact_checks`
  (deterministic tests computed *before* the LLM call), `citation_checks`
  (verified true/false per quote).
- **Guarantees** (evidence: 11 recorded runs, 2026-09-26,
  `mvp/RESULTS.md`; 2 model families — Gemma-3-27B, Llama-3.3-70B,
  temperature 0, spend ≈$0.022 of the $4 cap):
  - the citation checker **bites**: it rejected non-verbatim quotes from
    both models mid-campaign; final Gemma run 24/24 verified, final
    Llama-70B run 16/23 with all 7 failures being *empty quotes on
    not_applicable findings* — i.e. it also polices completeness, and the
    misses were caught, not silent;
  - with the deterministic fact layer, **outcome accuracy 100%** on both
    synthetic cases for both model families; the one systemic failure
    (the 8.5(4) height boundary) is eliminated by construction;
  - the failure taxonomy is documented per model, including what each
    model still gets wrong (RESULTS.md) — known weaknesses, not mysteries.
- **Assumptions:** (a) the **12-provision block list is hand-picked** to
  fit the two Frenchs Forest cases — selecting applicable provisions from
  1,316 is the biggest unsolved gap (Spike C for the LLM half; Phase 1
  for the deterministic half); (b) `factcheck.py`'s value extraction is
  **bridge code** (`# BRIDGE:` markers, kill-criteria in the docstring) —
  validated on 5 clause types of one instrument; (c) the cases are
  in-sample (rung 0, doc 04).
- **Promotion gate:** Spikes A→B→C, then the **portability test**
  (backlog #8): same layers, second un-curated instrument, **no edits to
  `factcheck.py`** — any bridge that breaks there is evidence for ingest
  v2, not more regex.

### ④ eval — score against the golden

- **Contract in/out:** `report.json` + `cases/<case>/golden.json`
  (human answer key: expected determination per finding, with `alt_ok`
  equivalents) → `evaluation.json` scorecard: per-finding
  `det_score` / `cite_score` / `self_inconsistent`, case and run totals.
- **Guarantees:** the scoring mechanics work and have been exercised
  across all 11 recorded runs; scorecard caveats are documented
  (RESULTS.md: keyword-based consistency flags, ref→key mapping
  heuristics, `alt_ok` semantics).
- **Assumptions:** the golden set itself is **2 synthetic, in-sample
  cases** (rung 0). The Phase-3 golden set (30 real cases, 20/10
  split, holdout discipline) is specced (`config/golden-set-spec.yaml`)
  but unbuilt and blocked on rung-1 data (doc 04).
- **Promotion gate:** golden-set build (03, sequence item 4); structured
  finding schema (design doc §6.3) replacing the mapping heuristics.

## 5. What the 2026-09-26 verdict does and does not cover

**Does cover (architecture-level — survives re-implementation):** LLM +
machine citation-verification + deterministic fact layer can adjudicate a
DA case reliably enough to show a user, across two model families, with
every claim machine-checkable.

**Does not cover (implementation-level — see 02 and 05):** the KB data
model, regex extraction, the hand-picked selection, in-sample scores.
Every implementation-level decision in this project is therefore
**scoped to `warringah_lep_2011`** until the portability test passes.

## 6. Deviations from the design doc (the current build is a miniature)

| Design doc | Says | This build has | Disposition |
|---|---|---|---|
| §5.6 | local open-weight LLM, vLLM-served | OpenRouter (Gemma-3-27B default; Llama-3.3-70B alternate); local `gguf` provider built but deferred | decision 2026-09-26; **privacy consequence stated in 03 row 7** |
| §5.7 | bge-m3 embeddings → Qdrant hybrid | no retrieval — curated 12-block selection | Spikes B/C → Phase 2 |
| §5.8, §7 | declarative YAML rule language | none (per-clause Python bridges in `factcheck.py`) | **Phase 1 — user go-ahead required (standing decision)** |
| §5.10 | PostgreSQL 16 + MinIO | flat JSON in git (4.8 MB) | promote when scale requires (03) |
| §3, §5.3–5.4 | DA-package ingestion incl. drawings (vision) | manual `proposal.json` + synthetic PDFs; text-only | rungs 1–3 + vision stretch |
| §11.2, App. D | 30-case golden harness + shadow mode | `evaluate.py` + 2 synthetic goldens | rungs 1–4, Phase 3 |
| §5.11, §10 | officer UI + report generation | JSON reports + markdown scorecards | Phase 2–3 |
| §12/§13 | on-prem only (PPIP/GIPA) | OpenRouter (data leaves premises) | **safe only while cases are synthetic — 03 row 7 is the gate** |

## 7. What this document is not

Not implementation detail (the code is the source of truth for *how*),
not a list of unknowns (05), not the data strategy (04), not the session
map (`../README.md`). Once FROZEN, any change here is a gate.
