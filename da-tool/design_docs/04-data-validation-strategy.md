# 04 — Data & validation strategy

**Status: DRAFT** · written 2026-09-27 · the rules that keep the project
*honest* at every stage — especially while no real case data exists yet.

The problem this document solves: we cannot wait for real data before
validating, but we also must not let "it works on our own synthetic cases"
be reported as "it works". The mechanism is **evidence rungs**: every
claim the project makes states which rung it stands on, and claims
*promote* (get stronger) as better data arrives — they are never silently
regraded.

## 1. The evidence rungs

| Rung | Data available | Gate to reach it | What claims it can support | What it cannot |
|---|---|---|---|---|
| **0 — parametric synthetic** (where we are) | cases generated *against the real KB's actual thresholds*; 2 human-built anchors (the Frenchs Forest cases) | none — available today | **consistency, boundary behaviour, mechanism** of every layer (fact layer, citation checker, evaluator, prompt); regression safety | *validity* — nothing on this rung says the KB says what the law says, or that the cases resemble real DAs |
| **1 — real metadata + real outcomes** | council ePlanning public register (no auth: status, dates, use, address, submissions, document inventory) + monthly consent notices (outcome labels back to 2021) | none — crawlable today (recon: `data/public-register-recon.md`); needs the sample harvester (backlog #2) | **outcome-level prediction on real determined DAs** — the first external validation of the decision path, incl. real refusals | evidence-level or drawing-level claims (no documents); the bar is a **floor**, since metadata-only cases are thinner than real packages |
| **2 — structured facts** | Online DA Data API (dwelling/storey counts, subdivision, EPI variation, status) | **your** Data Broker email (`data/data-broker-email.md` — I never amend it) | fact-extraction checked against *real ground truth* instead of against the KB | judgement-level (fields, not packages) |
| **3 — full packages** | lodged documents, determination notices, submissions for a small sample of notified DAs | permission-gated: council doc store currently broken (re-probe = backlog #4, your machine); NSW Planning Portal login-gated; a document-access ask to the broker is **your separate decision** (03, open decision b) | evidence-citation quality, conditions drafting, and (later) vision | — |
| **4 — shadow mode** | live DAs assessed alongside officers; 10-case sealed holdout consumed once at Phase 3 exit | council agreement (design doc §16) | the endgame: the system measured against what actually happened | — |

**Rung-dependency rule (binding once frozen):** every validation report —
including the MVP's RESULTS.md and any future one — states, per claim, the
rung it stands on. A claim may be reported *up to* the strongest rung the
evidence actually has; it may not be rounded up. Promotion is an explicit,
dated event (decision log), never a rewrite.

## 2. The two kinds of synthetic data (and when to use each)

They do different jobs and must not be blurred:

1. **Boundary-regression suite — machine-computed truth.** A generator
   emits many cases by varying site attributes *around the KB's actual
   thresholds* (just under / exactly meeting / just over each numeric
   standard; zone × use combinations; DCP present/absent; overlay
   present/absent). The golden answer is computed deterministically by the
   fact layer, because we built the case against known numbers. This is
   boundary-value / property-based testing applied to planning law: fast,
   cheap, run every session, guards against regression. It validates the
   system *against itself* — it can never discover that the law or the KB
   is wrong.
2. **Validity anchors — human-verified cases.** Small, deliberately grown,
   each one hand-checked against the actual instrument text by a human.
   These are the only synthetic cases with validity authority. The current
   two (`mvp/cases/`) are the seed of this set.

Plus a **differential triage** layer: two models disagree on a case → it
queues for a human look. Disagreement is a free anomaly detector (already
in use during the MVP runs).

**Separation from the golden set (sacred):** the regression suite and the
golden set are different artifacts with different purposes. The golden set
(`config/golden-set-spec.yaml`) is real, stratified, split 20 calibration /
10 sealed, and obeyed by the holdout discipline in that file (no case
moves between splits; holdout consumed at most once per phase exit; new
cases → fresh holdout; anything motivated by a holdout observation is
validated on the calibration set first). Mixing machine-generated cases
into it would silently destroy what the holdout proves.

## 3. Data sources and their gates

| Source | Access | Status | Feeds |
|---|---|---|---|
| ePlanning instrument exhibits | public crawl | **frozen 2026-09-25** (never touch); rebuild = backlog #2 | the KB (rung-0 corpus) |
| Council ePlanning public register + consent notices | public, no auth (recon done) | not yet harvested — **no gate, buildable now** | rung 1: stratified spine + outcome labels for the golden set |
| Online DA Data API | via Data Broker, **not** self-serve | your email drafted, awaiting you | rung 2: structured facts; stratification fields per spec |
| Council document store (lodged packages) | broken on the server (`E:\OnlineDocs\CllrPortal`); re-probe on **your** machine (backlog #4) | may be a transient migration state | rung 3 (part) |
| NSW Planning Portal | login-gated (B2C OAuth); no anonymous per-case register found yet | open question — verify before relying on the design doc's `portal_onlineDA` assumption | rung 3 (part) |
| Draft NBC DCP 2026 (677 MB, on exhibition) | downloaded | **not ingested**; if/when ingested: "considered but not in force" — advisory context, **never citable as law** (invariant I-4) | version-boundary reasoning, not law |
| LEC decisions | published | separate reasoning-quality set (spec: `lec_decisions`), not part of the 30 | calibration of legal reasoning, only |

## 4. The anonymisation gate

Before any **real** case enters the system, PII is stripped per the spec
(`golden-set-spec.yaml → anonymisation`): out — names of
applicants/owners/objectors, contact details; in — DA reference, address,
lot/plan, outcome, conditions, grounds, dates. This is *our*
implementation duty (spec workflow step 5), applied before ingestion, not
after. Rung-1 data (register metadata) contains applicant names — the
stripper is part of the sample harvester's contract (01, layer ①
promotion gate).

## 5. The claim register — what the project currently claims, and on which rung

| Claim | Rung | Evidence | Promotes when |
|---|---|---|---|
| "the citation checker verifies quotes and rejects fakes" | 0 | 11 runs; rejected non-verbatim quotes from both models mid-campaign; 24/24 final Gemma | rung 1 (it must do it on real case data too) |
| "outcome accuracy 100% on the two synthetic cases" | 0 (in-sample, 2 cases) | `mvp/RESULTS.md` final runs, both model families | rung 1: outcome agreement on the calibration set — **threshold to be pre-registered when that set is built** (not before: the threshold depends on the set's size and mix) |
| "the architecture is sound (LLM + machine verification + facts)" | 0 × 2 model families × 11 runs | RESULTS.md | rung 1 outcome agreement + Spike A pass |
| "the KB says what the law says" | **none yet** | — (the self-referential hole: validation checks model↔KB, not KB↔law) | **Spike A pass** (05) |
| "retrieval/selection will work" | **none yet** | — | **Spikes B/C pass** (05) |
| "the implementation generalises beyond warringah_lep_2011" | **none yet** | — | portability test (backlog #8) |

## 6. What this document is not

Not the spike register (05 — *how* unknowns get answered), not the KB
schema (02), not the build order (03). Once FROZEN, changing a rung's
definition or the holdout rules is a gate.
