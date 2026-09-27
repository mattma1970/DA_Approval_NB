# 00 — Framework observations (running note)

**Not a contract.** Append-only working note, seed material for a
*general* human+agent development framework — to be distilled into an
actual document **later**, when this project has produced evidence, not
before. (House rule 6 applied at meta scale: the framework itself is a
bridge until a project has survived it.)

Format: `date · category · observation`.
Categories: **WORKED** (the discipline paid off — something was caught,
prevented, or clarified) · **FRICTION** (cost without benefit) ·
**BOUNDARY-ERROR** (the human/agent line was in the wrong place) ·
**DISCREPANCY** (a factual error found in the record).

## The three invariants (the seed)

1. **One-way door** — unknowns may enter a contract only through a
   pre-registered experiment (05); everything else stays marked.
2. **Rung-labelled evidence** — every claim states the strength of the
   data it stands on; promotion is explicit (04).
3. **Pre-registration** — pass/fail thresholds are written down before
   the experiment runs; changing them after = a new experiment number (05).

## Entries

- **2026-09-27 · WORKED** · Writing 01 forced an out what had been
  silently accumulating: the MVP sends case data to OpenRouter (off
  premises), while the design doc's privacy posture (§12/13) is on-prem
  only. It had been *safe* (synthetic cases, no PII) but *unstated* —
  nobody could object to what nobody had written down. It is now a named
  decision gate (03 row 7). → *Contract writing catches unstated
  deviations; the deviation had been invisible precisely because the
  build was working.*
- **2026-09-27 · WORKED** · Rung-labelling shrank a claim instead of
  inflating it: "100% outcome accuracy" became "100% on 2 synthetic,
  in-sample cases (rung 0)". The same number, honest scope. No work was
  lost by being precise — and the gap to rung 1 is now visible, which
  the unlabelled number hid.
- **2026-09-27 · WORKED** · The user's recurring worry ("will RAG /
  parsing actually work — I can't tell") became *two entries in a
  register with pre-registered verdicts* (05: A, B) instead of an
  anxious open question. The human did not need to be a retrieval expert
  to approve the *design* of the experiment; they only needed to check
  the question and the pass line. → *The division of labour works: agent
  carries technical risk, human carries decision authority.*
- **2026-09-27 · DISCREPANCY** · `mvp/runs/` contains **12** run
  directories; `mvp/RESULTS.md` records **11** — the run `20260926-052816`
  (a fact-layer run; Gemma) has no row in the history table. Either the
  table needs the row or the run needs a note explaining its absence.
  (Not fixed by this note — RESULTS.md is the validation record; the
  owner decides.)
- **2026-09-27 · DISCREPANCY** · Provision count: README and earlier
  records say **1,316**; a fresh count of `kb/provisions/` on
  2026-09-27 gives **1,317** (77+94+146+93+464+114+11+170+148).
  Off-by-one, direction unknown (one provision added by a later ingest,
  or a count slip). Also: README says spend ≈$0.023, RESULTS.md says
  ≈$0.022 (same 21 calls). Both to be reconciled when next touching
  those files.
- **2026-09-27 · FRICTION (anticipated, to verify after freeze)** · The
  da-tool README (session map) and this folder (contracts) now
  deliberately overlap in places (status lines, backlog, hazards). Plan:
  after freezing, slim the README's overlapping sections to pointers to
  the contract docs — one place states a fact, the other points at it.
  If the two documents drift apart in practice, that is itself a
  framework finding.
- **2026-09-27 · BOUNDARY-ERROR (past, for the record)** · During the
  MVP, implementation-level decisions (KB schema shape, regex-as-
  extraction, the 12-block selection) were made by the agent and reported
  *after* the fact; the user absorbed them as facts instead of deciding
  them. That is the failure this whole folder is the corrective to. The
  fix is the lifecycle in `README.md` of this folder: contracts *before*
  builds, deviations as gates. Whether it actually works is the question
  this note is collecting evidence for.

## Distillation trigger

When the project reaches its first phase exit (Phase 3 holdout consumed,
or the user declares the MVP era over): group entries, keep the ones
that repeated, drop the one-offs, and write the general framework from
the survivors — with this project as the cited case study.
