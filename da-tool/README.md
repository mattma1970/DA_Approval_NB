# da-tool — advisory decision support for NSW development applications (Northern Beaches)

Build for the design in `../DA-decision-support-design.md`. **Advisory only**:
the tool recommends (approve / deny / conditional) with verbatim,
retrieval-verified citations; a human officer makes the determination.
Regulations are versioned data, never hard-coded.

> **How to stay in touch (the rules this repo follows):**
> 1. This file is *the* map. It is updated in the same session as the
>    code that changes. If a row below looks stale, it is — say so.
> 2. Every pipeline layer has a **one-command proof** you can run and
>    open with your own eyes — the "Try it yourself" ladder below.
> 3. Every decision you make gets one line in the decision log, with
>    its date and reason.
> 4. Every work session ends with "here's what you can try in two
>    minutes".
> 5. One file, one job, stable name. The layout *is* the API.
> 6. **Bespoke code is a bridge, never a foundation.** It carries a
>    `# BRIDGE:` marker with a kill-criterion (what would make it
>    unnecessary or wrong), and it becomes permanent only when
>    promoted into the general layer *with tests*. Decisions are
>    scope-tagged: *arch* (survives re-implementation) vs *impl*
>    (valid only for the current data shape).

## The approach: four layers

```
  harvest/            kb/                 mvp/               eval/
 ┌────────────┐   ┌──────────────┐   ┌─────────────────┐  ┌──────────────┐
 │ pull data  │ → │ structure    │ → │ LLM adjudicates │→ │ score        │
 │ (crawls,   │   │ the law      │   │ against the KB  │  │ against      │
 │ registers) │   │ into JSON KB │   │ + machine       │  │ golden set   │
 └────────────┘   └──────────────┘   │   verification  │  └──────────────┘
        ①                    ②        │ (quotes, facts) │       ④
                                      └─────────────────┘
                                               ③
```

A case (DA proposal) enters at ③. The LLM writes a finding for every
relevant provision *with a verbatim quote*; the machine then checks the
quote actually exists in the KB, checks the arithmetic against
pre-computed facts, and writes `runs/<ts>/<case>/report.json`. ④ scores
the report against a human-built golden answer key.

**Where we are (2026-09-26):** ① partially done (ePlanning crawl
complete; registers pending), ② done for 9 instruments, **③ done and
validated on synthetic cases** (`mvp/RESULTS.md`), ④ spec'd but not
built. The MVP question — *can a 27B-class model + machine verification
adjudicate a DA case reliably enough to show a user?* — has a **yes**
answer with one structural caveat (threshold clauses need the
deterministic fact layer, now in place).

## Status at a glance (2026-09-26)

| Work item | Status |
|---|---|
| LGA profile (instrument stack, transition) | done — `config/lga-profile.yaml` |
| Golden-set spec (30 = 20 calibration / 10 sealed) | done — `config/golden-set-spec.yaml` |
| Data Broker email (Online DA Data API) | **drafted — awaiting YOU to send** — `data/data-broker-email.md` (I don't amend it) |
| Data download | ~1 GB in `kb/incoming/` — ePlanning crawl (189 pp, 0 failures), draft NBC DCP 2026 (677 MB), SREP 2005, council PDFs — see inventory below |
| KB ingestion | **9 instruments → 1,316 provisions** in `kb/provisions/`; known issue: provision-number normalisation (backlog #1) |
| Harvesters | `harvest/` mostly gutted pending rebuild (only `_probe_portal.py` remains); ePlanning crawl script to be restored (backlog #2) |
| MVP adjudication pipeline | **done + validated** — `mvp/` (LLM + citation check + fact layer + evaluator); 11 runs, 2 models, ≈$0.023 spent, outcomes 100% with fact layer |
| Rule engine (17 worked rules) | pending — Phase 1, **awaiting your go-ahead** |
| Evaluation harness (Phase 3) | pending — MVP has a mini version (`mvp/evaluate.py`) |
| Vision (DA drawings) | stretch — text-only so far (this deployment has no image input) |

## What the verdict actually covers (validated vs assumed)

The 2026-09-26 MVP verdict ("a 27B–70B-class model + machine
verification can adjudicate a DA case with real citations") is an
**architecture** verdict: it holds regardless of how values are
extracted or which KB is used. It does **not** validate the
**implementation**:

| Assumed, not yet validated | Why it's risky |
|---|---|
| The KB data model (flattened tables, positional LUT blocks, `hNNNNN` ids) | built to fit our crawler; verified on our 9 instruments only |
| Regex extraction of values from provision prose (the fact layer) | marked `# BRIDGE:` in `mvp/factcheck.py`; validated on 5 clauses of one instrument. Fails *loud* (`NOT_EVALUATED`), never *wrong* — but "no answer" ≠ "works on real data" |
| **Which provisions apply to a case** — the 12-clause block list is hand-picked to fit the Frenchs Forest case | the biggest unvalidated gap in the final product: picking applicable provisions out of 1,316 is unsolved and out of MVP scope |
| The synthetic-case scores themselves | the cases were designed by us, to fit our own parser (in-sample) |

The experiment that actually answers "does it work on a real
application": **backlog #8, the portability test** — run the same
layers end-to-end on a second, un-curated instrument *without
editing `factcheck.py`*. Until that passes, implementation-level
decisions are scoped to `warringah_lep_2011`.

## The data — what's on disk

| Where | What | Size | Status |
|---|---|---|---|
| `kb/incoming/eplanning/` | ePlanning crawl: 8 exhibits (WLEP, MLEP, PLEP, DCP, MDCP, PDCP, LEPDCP, ALLDCPLEP) + `_crawl-report.json` | 216 MB | crawled 2026-09-25; **do not touch** (frozen artifact) |
| `kb/incoming/drafts/` | Draft Northern Beaches DCP 2026, part-by-part PDFs (on exhibition Jul–Aug 2026) | 677 MB | downloaded; **not yet ingested** (needs "considered but not in force" status, see hazards) |
| `kb/incoming/reports/`, `reports_roots.json` | council report store probe | 17 MB | broken source, re-probe on backlog |
| `kb/incoming/srep-maps/`, `srep-2005-xml-*.xml` | SREP 2005 (harbour foreshore) maps + XML | 55 MB + 1 MB | downloaded |
| `kb/incoming/*.pdf` | foreshores DCP 2005 (full + partial), Pittwater 21 DCP vol 4, Warriewood Valley spec, Warringah DCP 2000 amend 4 | ~89 MB | downloaded; all ingested |
| `kb/incoming/pittwater21-dcp-portal-2021.bin` | unknown binary from portal download | 11 MB | **leave alone** until identified |
| `kb/provisions/*.json` | the actual knowledge base: 9 files | 4.8 MB | **this is what the tool reasons from** — see counts below |
| `kb/inventory.json` | per-instrument parse report (quality gate output) | 16 KB | from last ingest |

**What git tracks vs. what's just on disk** (rules live in `.gitignore` at the repo root): the ~1 GB of raw data in `kb/incoming/` is **git-ignored** — it stays on this machine as frozen artifacts. What *is* tracked: `kb/provisions/*.json` (the KB the tool actually reads) plus four small JSON provenance manifests (`_crawl-report.json`, `_harvest-notes.json`, `reports_roots.json`, `srep-maps-index.json`) so the crawl's record survives without its 1 GB of payloads. Same logic for venvs, `__pycache__`, and `mvp/.env` (the OpenRouter key never gets committed).

`kb/provisions/` contents: `warringah_lep_2011` (148 — the MVP's corpus),
`warringah_dcp_2011` (170), `warringah_dcp_2000` (11), `pittwater_lep_2014`
(114), `pittwater21_dcp` (464), `manly_lep_2013` (93), `manly_dcp_2013`
(146), `foreshores_waterways_dcp_2005` (94), Warriewood Valley spec (77).

## The code — what each file does

| File | One line | Status |
|---|---|---|
| `kb/ingest.py` | PDF/HTML → provision-shaped JSON (layout engine + regex fallback, quality-gated) | works; number-normalisation fix pending |
| `kb/query.py` | human-searchable KB viewer (`python3 kb/query.py "8.6" --full`) | **new** — your main "look at the law" tool |
| `kb/_recon_trees.py` | one-off recon for the ePlanning tree mapping | temporary; delete when harvest rebuilds (backlog #2) |
| `mvp/llm.py` | OpenRouter client: retries, per-call USD, cost ledger + $4 cap, and the **excluded-models guard** (our own local Qwen can never be the model under test) | works |
| `mvp/factcheck.py` | deterministic layer: LUT block, 8.4 DCP, 8.5(4) trigger, 8.6/8.7 minimums computed in Python *before* the LLM call | **new** — fixes the one systemic LLM failure |
| `mvp/decide.py` | the adjudication prompt + JSON schema + citation verification + self-consistency check; writes `runs/<ts>/<case>/report.json` | works, iterated over 11 runs |
| `mvp/evaluate.py` | scores a run against the golden key (`cases/<case>/golden.json`) → `evaluation.json` | works; scorecard caveats noted in RESULTS.md |
| `mvp/cases/<case>/` | 2 synthetic Frenchs Forest DAs: 4 PDFs + `proposal.json` (the case record) + `golden.json` (human answer key) | works — open the PDFs in any viewer |
| `mvp/runs/` | every run ever: `report.json` (findings + citations + facts) + `evaluation.json` | append-only evidence |
| `mvp/RESULTS.md` | **the validation story**: 11-run history, failure taxonomy, conclusions | read this to see what the MVP proved |
| `mvp/spend.json`, `mvp/config.json`, `mvp/.env` | cost ledger; model config + budget cap; OpenRouter key (chmod 600) | live |
| `harvest/_probe_portal.py` | NSW Planning Portal probe | skeleton; rebuild pending |
| `config/lga-profile.yaml`, `config/golden-set-spec.yaml` | instrument inventory; golden-set design | done |
| `data/data-broker-email.md`, `data/public-register-recon.md` | API request draft (yours to send); public register findings | frozen |
| `.venv/` vs `.venv-harvest/` | two venvs on purpose: **`.venv` = parsing** (PyMuPDF, lxml, bs4, PyYAML, llama-cpp) ← `requirements.txt`; **`.venv-harvest` = HTTP** (requests, bs4, lxml; used by `mvp/` and future `harvest/`) ← `requirements-harvest.txt`. Reproduce on any Python 3.12 machine: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` and `python3 -m venv .venv-harvest && .venv-harvest/bin/pip install -r requirements-harvest.txt`. Both verified with `pip install --dry-run` (2026-09-26). Don't merge without checking both still work | live |

## Decision log (your calls — binding)

Scope: **arch** = survives re-implementation; **impl** = valid only
for the current data shape; **data** = valid only for this KB snapshot.

| Date | Decision | Scope |
|---|---|---|
| 2026-09 | The local Qwen3.8-27B GGUF is *this agent's own* model → it can never be the model under test (circular validation). Enforced as a hard guard in `mvp/llm.py` (`excluded_models`). | arch |
| 2026-09-26 | **All LLM calls made by the tool code go through OpenRouter** (your account; $6 credit; $4 hard cap in `mvp/config.json`; actual spend ≈$0.023). Local models stay out of the loop. | arch |
| 2026-09 | Synthetic cases only until a real data source exists (Data Broker API or public register); the public register is parked, not dropped. | data |
| 2026-09 | Text-only first; vision on DA drawings is a stretch goal (also blocked: this deployment has no image input). | arch |
| standing | Never touch the 2026-09-25 crawl artifacts. Never amend the Data Broker email. No Phase-1 rules without your explicit go-ahead. | arch + data |
| 2026-09-26 | **Bridge protocol** (house rule 6): bespoke code gets a `# BRIDGE:` marker + kill-criterion; decisions are scope-tagged; the portability test (backlog #8) is the gate an implementation must pass before it may be treated as general. | arch |

## Try it yourself — the verification ladder

Each rung is independent: if one rung's output makes sense, that layer
is real. All commands from `da-tool/`.

1. **Read the law the way the tool sees it** (free, instant):
   `python3 kb/query.py "8.6" --full --instrument warringah_lep_2011`
   → prints the clause text + its parsed minimum-area table. Try
   `"design excellence"`, `"8.5"`, `"flood"`.
2. **See the raw case the model was given**: open
   `mvp/cases/ff-g-rfb-compliant/proposal.json` in any editor, and the
   four PDFs in `mvp/cases/ff-g-rfb-compliant/documents/` in a PDF
   viewer. This is the whole "DA package" — fictionally filed, obviously.
3. **Run the deterministic layer** (free, no LLM):
   `.venv-harvest/bin/python mvp/factcheck.py`
   → 10 lines: which LUT block the use is in, whether the 8.4 DCP
   exists, the 8.5(4) trigger decision, and the 8.6/8.7 minimum tests
   with the actual arithmetic. This output is exactly what gets injected
   into the model's prompt.
4. **Run a full adjudication** (costs ≈$0.002):
   `.venv-harvest/bin/python mvp/decide.py`
   → prints per-case lines (findings / citations verified / outcome /
   cost) and ends with the new `mvp/runs/<timestamp>/` dir.
5. **Score it against the human answer key**:
   `.venv-harvest/bin/python mvp/evaluate.py`
   → the scorecard table. Every row = one provision: expected
   determination vs what the model said, and whether its quote
   verifies.
6. **Open the evidence**: in the run dir, `<case>/report.json` holds
   `findings` (the model's words + quotes), `fact_checks` (the
   machine's arithmetic) and `citation_checks` (verified: true/false
   per quote). `evaluation.json` is the scorecard. `mvp/spend.json`
   is the running cost ledger.

That's the whole loop in six commands. If you can run 1→6 and the
outputs line up with what this README claims, the project is in the
state it says it's in.

## Known hazards (kept live in config)

- **EP&A Act renumbered** (in force 1 Nov 2025): 79C→4.15, 80→4.16,
  80A→4.17. Old citations in historical DAs and DCPs need the crosswalk.
- **Draft consolidated LEP/DCP on exhibition 20 Jul–30 Aug 2026**: draft
  LEP *is* considered in assessment (weighted); draft DCP is not.
  Notification is the version boundary — the KB carries a "considered
  but not in force" node that is advisory context, never citable as law.
  (`kb/incoming/drafts/` is exactly this material.)
- **Warringah LEP 2000 still applies** to deferred-matter land —
  area→instrument map, not a list.
- **Foreshore/waterways**: SREP 2005 (a REP) + Sydney Harbour Foreshores
  & Waterways DCP 2005 override local LEP/DCP.
- **Warringah LEP 2011 zone codes differ from post-2013** (e.g. C4 ≠
  General Residential). Don't auto-map.
- **LUTs are flattened** in the KB (crawl dropped the column headers):
  the block identity (no-consent / with-consent / prohibited) is
  *positional* and was verified by hand for R3 — re-verify per zone.
- **4.3/4.4 map-referenced standards**: the referenced maps are not in
  the corpus → determinations must be `indeterminate`, never assumed.

## Backlog (in suggested order)

1. `kb/ingest.py` provision-number normalisation fix + Warringah-only
   re-ingest (cheap; improves clause addressing)
2. Rebuild `harvest/`: restore the ePlanning crawl + drafts download
   scripts (the crawl itself is proven; only the script file is lost)
3. Ingest `kb/incoming/drafts/` (draft NBC DCP 2026) as
   "considered but not in force" nodes
4. Re-probe the broken council doc store (`E:\OnlineDocs\CllrPortal` —
   on your machine)
5. **Phase 1 rule engine — awaiting your go-ahead** (the 17 worked
   rules from the design doc)
6. Phase 3: golden-set evaluation harness over `config/golden-set-spec.yaml`
7. Stretch: vision on DA drawings once a vision-capable path exists
8. **Portability test** — the answer to "does this work on a real
   application": parameterise `KB_PATH` (small, safe), then re-ingest a
   second, un-curated instrument (`pittwater21_dcp` or `manly_lep_2013`)
   end-to-end through `kb/` and run the fact layer + `decide`/`evaluate`
   on cases drawn from it **without editing `factcheck.py`**. Any
   `# BRIDGE:` that breaks here is evidence for ingest v2 (typed
   fields, named LUT blocks), not for more regex. Add *hostile* golden
   cases designed to break bridges (odd threshold phrasings, missing
   fields, other zones)
