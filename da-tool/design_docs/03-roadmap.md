# 03 — MVP → full application roadmap

**Status: DRAFT** · written 2026-09-27 · the path from the current build
to the design doc (`../../DA-decision-support-design.md`), as a
substitution map: for every component the design doc specifies, what the
MVP has instead, what evidence that substitution stands on, and the
**named condition that promotes it to the designed thing**.

## 1. The substitution map

| # | Design-doc component | Design doc says | The MVP has | Stands on (rung) | Promotes when (the gate) | Phase |
|---|---|---|---|---|---|---|
| 1 | Reasoning LLM (§5.6) | local open-weight model, vLLM-served, on-prem | OpenRouter: Gemma-3-27B default, Llama-3.3-70B alternate; `local_gguf` provider built, guarded, deferred | 0 (2 families × 11 runs) | (a) row 7's privacy decision forces on-prem for real data, **or** (b) you revive the local gate (Spike D) — either way the provider already exists | 2/3 |
| 2 | Retrieval (§5.7) | bge-m3-class embeddings → Qdrant hybrid (dense + BM25) + re-rank; "exact clause-number matches must not be drowned by semantic similarity" | none — a hand-picked 12-provision block list per case; no vector store | **none yet** | **Spike B** (can we even retrieve, zero-infra BM25) **and Spike C** (can an LLM pick the id set) both pass → build the hybrid index; a B-fail pointing at well-formedness routes to ingest v2 first | 2 |
| 3 | Storage (§5.10) | PostgreSQL 16 + JSONB, MinIO with object lock | flat JSON in git (`kb/provisions/`, 4.8 MB) | fits 9 instruments / 1,317 provisions + 12 runs | promote when the 30-case set + real packages (rung 3) or concurrent access make flat files painful — not before | 2–3 |
| 4 | Rule engine (§5.8, §7) | declarative YAML rules + thin Python evaluator; 17 worked NSW examples (§7.2) | none — `mvp/factcheck.py` has 10 **per-clause** deterministic checks (bridge code, `# BRIDGE:` marked), not a general rule language | the fact layer works on 5 clause types (rung 0); it *eliminates* the one systemic LLM failure, which is the strongest argument the design doc's architecture is right | **Phase 1 — your explicit go-ahead is a standing binding decision and has not been given.** First sub-components in order: deterministic selection skeleton (design doc Layer 3A: instrument + zone + use + site flags), then the 17 §7.2 rules, then the structured finding schema (§6.3) replacing evaluate.py's mapping heuristics | **1** |
| 5 | Case ingestion (§3) | DA package: PDFs, drawings, forms → extracted facts (§6.1) | manual `proposal.json` per case + 4 synthetic PDFs | 0 (in-sample) | rung 1 (register metadata → case record) for the golden set; Data Broker API (rung 2) for structured facts; document access (rung 3) for real packages | 0/1 |
| 6 | Evaluation (§11.2, App. D) | 30-case golden (20 calibration / 10 sealed holdout), stratified, holdout discipline; shadow mode | `mvp/evaluate.py` + 2 synthetic goldens (rung 0) | the mechanics are proven (11 runs); the *set* is not real | golden-set build (sequence item 4 below) using the sample harvester; holdout sealed and consumed **once** at Phase 3 exit; any holdout-motivated change validated on calibration first (spec discipline) | 3 |
| 7 | Privacy & deployment (§12, §13) | on-prem only — NSW PPIP 1998 / GIPA; case data never leaves council premises | **OpenRouter — case data leaves the premises.** This is safe *only because the cases are synthetic and contain no PII.* The moment rung-2 data (real applicants) enters, this substitution collides with the design doc's privacy posture. | **a decision gate, not a technical one** | **your call, before any real data:** (a) on-prem serving (local CPU per Spike D, or vLLM on suitable hardware), or (b) a data-processing arrangement with the council/broker covering OpenRouter. No rung-2 build starts without this decision. | before 3 |
| 8 | Vision / drawings (§5.3, §5.4) | vision LLM for scanned drawings + CAD, JSON-schema output, cross-checked | none — text-only (binding decision for this deployment; no image input here either) | — | a vision-capable path **and** rung-3 documents (the council doc store re-probe, backlog #4, is on your machine) | 3+ stretch |
| 9 | Officer interface & reports (§5.11, §10) | Streamlit pilot → React production; Determination Support Report (PDF/DOCX) | JSON reports + markdown scorecards | enough to validate the pipeline | Streamlit pilot once Phase 2 retrieval + Phase 1 rules exist (a UI before them would freeze the wrong contract) | 2–3 |

## 2. The sequence (given today's knowledge)

Ungated work first; every item states what it produces and what it
unblocks. Items marked ◆ are **your decisions**, in the order they come.

1. **Freeze this contract set** (you correct the five docs; corrections
   logged; freeze dates set). *Unblocks everything below — after this,
   deviations are gates.*
2. **Spike A — KB fidelity audit** (05). Produces the quality table
   (02 §3). *Unblocks B, C, and any further KB-dependent build. If it
   fails systemically → ingest v2 moves to item 3 instead.*
3. **Ingest v2 (conditional on A's verdict)** — typed fields (`params`),
   named LUT blocks, number normalisation (absorbs backlog #1),
   idempotent re-ingest, KB fingerprint in runs. *Or, if A passes:
   the harvest rebuild* — restore the ePlanning crawler (diff one
   exhibit against the frozen artifact) + the golden-set sample
   harvester (register + consent notices, with the anonymisation
   stripper in its contract).
4. **Spike B + Spike C** (05) — retrieval and selection evidence, in
   that order.
5. **Build the golden set** per `config/golden-set-spec.yaml`: stratified
   30 from the rung-1 harvest, human-reviewed, anonymised, split 20/10,
   holdout sealed. Then **run the tool on the calibration set** — this is
   the first rung-1 validation: outcome agreement on real DAs, with the
   pass threshold pre-registered in the build (04 §5).
6. ◆ **Phase 1 go/no-go** (rule engine + deterministic selection, row 4).
   *Standing binding decision; the evidence available at this point:
   A's audit, B/C's numbers, rung-1 outcome agreement, and the
   portability test (below) if you want it run first.*
7. **Portability test** (backlog #8) — same layers, second un-curated
   instrument (`manly_lep_2013` or `pittwater21_dcp`), **no edits to
   `factcheck.py`**; any bridge that breaks → evidence for the next
   ingest iteration, not more regex. *Cheap (≈$0.002); sits anywhere
   after A, recommended before 6 so Phase 1 is decided on
   generalising layers.*
8. ◆ **Phase 2** — retrieval build (per B/C verdicts), storage promotion
   if scale requires (row 3), and **row 7's privacy gate must be closed
   before any rung-2/3 data enters**.
9. **Phase 3** — golden harness over the sealed set, holdout consumed
   once, shadow-mode negotiation with the council (design doc §16).
   ◆ **Vision** and ◆ **UI** decisions attach here (rows 8–9).

## 3. Open decisions — the ones waiting on a human, in order

| # | Decision | Blocks | Note |
|---|---|---|---|
| a | **Correcting/freezing the five contract docs** (this folder) | everything (item 1) | the fastest thing you can do that changes the most |
| b | **Document access for a small sample of notified DAs** — the recon (`data/public-register-recon.md`) recommends asking; your standing rule says the Data Broker email is never amended, so this is a *separate* follow-up from you, or we wait for rung 3 another way | row 2/row 8 of the map, partially | rung 1 doesn't need it — the golden set can start without it |
| c | **Phase 1 go/no-go** (rule engine) | item 6 | standing binding decision; no rules before your explicit go-ahead |
| d | **Privacy path for real data** (row 7): on-prem vs data-processing arrangement | item 8 (Phase 2) | not needed while synthetic-only holds |
| e | **Spike D revival** (local-CPU no-cloud proof) | nothing on the critical path | deferred, not dropped — trigger is yours |
| f | **Re-probe of the council doc store** (`E:\OnlineDocs\CllrPortal`) | rung 3 (part) | on your machine (backlog #4) |

## 4. What this document deliberately does not contain

No timeline in calendar terms (the sequence *is* the schedule; dates
arrive when gates clear), no per-feature detail (that's code), and no
speculation beyond the design doc — if a component above has no design
doc counterpart, that's flagged in the map itself, not hidden in prose.

Once FROZEN: re-sequencing is a gate; adding a substitution row without a
promotion condition is forbidden (it's how assumptions become
architecture); adding a spike is always allowed (05 is append-only).
