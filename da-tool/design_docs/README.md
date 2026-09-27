# design_docs — the contract set

The five documents in this folder are **contracts**, not reports: small,
reviewable statements of what the da-tool system is, what it guarantees,
how it will be validated, and how it gets from here to the design doc.
They exist so that a human can stay in the loop by reading *pages*, not
code — and so that any later work has something to conform to (or to
deviate from, on purpose).

They are also the first worked instance of a general framework for
greenfield development with a coding agent. The seed for that framework
lives in `00-framework-observations.md` (a running note, not a contract).

## Reading order and what each answers

| Doc | Question it answers |
|---|---|
| `01-architecture-guarantees.md` | What are we building, layer by layer — what each layer guarantees, what it assumes, and the gate that would promote each assumption? |
| `04-data-validation-strategy.md` | How do we stay *valid* while no real cases exist yet? (evidence rungs, the two kinds of synthetic data, data sources and their gates) |
| `05-spike-register.md` | What don't we know yet, and which bounded experiment — with a pre-registered pass/fail rule — answers it? |
| `02-data-contract.md` | What does a "provision" *is* in the KB, what warts are known, and what must be true for the KB to be trusted? |
| `03-roadmap.md` | How do we get from the MVP to the design doc — the substitution map, the build order, and the decisions still waiting on a human? |

Why that order: 01 states what *is*; 04 states how we'll know if it *holds*;
05 lists what we'll *find out* before building more; 02 pins the data
01–05 all stand on; 03 sequences it all.

## Lifecycle — how a document becomes binding

1. **DRAFT** — written by the agent from the current state of the system.
   This is where all five start.
2. **Human correction** — you edit or reject lines. Every correction you
   make is recorded in the *Corrections* section below and, where it is a
   decision, in the da-tool README decision log with a scope tag
   (*arch* / *impl* / *data*).
3. **FROZEN** — the doc is a contract. The agent may not change it. Any
   later work that deviates from it must stop and ask (a **gate**): the
   deviation, the reason, and the doc line it touches. Your yes/no is
   logged. A FROZEN doc is only re-opened by you.

**The one-way door:** nothing enters a contract document *except through*
the spike register (05). An experiment is run against thresholds written
down *before* it ran; its verdict goes to the decision log; *then* the
relevant contract line is updated. This is what keeps assumptions from
silently becoming architecture.

## Status

| Doc | Status | Frozen date |
|---|---|---|
| 01 | DRAFT — awaiting your corrections | — |
| 04 | DRAFT — awaiting your corrections | — |
| 05 | DRAFT — awaiting your corrections (esp. the pre-registered thresholds) | — |
| 02 | DRAFT — awaiting your corrections | — |
| 03 | DRAFT — awaiting your corrections (esp. the sequence and open decisions) | — |

## Corrections

*(agent records your corrections here as they come; each gets a date and,
if it is a decision, its scope tag)*

— none yet —

## What this folder deliberately is not

- **Not** the session map. `../README.md` remains the working hub
  (layout, try-it ladder, decision log, backlog). After freezing, the
  overlapping parts of that README become pointers to this folder — one
  place states a fact, the other points at it.
- **Not** implementation detail. Code stays the source of truth for *how*
  things work; these docs are the source of truth for *what is promised*.
- **Not** a methodology document. The general framework (if it comes) is
  written later, from evidence accumulated in `00-…` — see that file.
