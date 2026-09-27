# 02 — Data contract: what a "provision" is

**Status: DRAFT** · written 2026-09-27 · the contract the knowledge base
(`kb/provisions/*.json`) must satisfy, the warts stated openly, and the
quality metric that will fill in as Spike A (05) runs.

A provision is **one citable unit of law**: a chunk of an instrument with
a stable identity, a place in the document tree, and provenance back to
the exact source page it was parsed from. Every other layer of the system
reasons *through* provisions — this document is what "the law, as the
tool sees it" actually means.

## 1. The schema (as it stands on disk)

Each `kb/provisions/<instrument_id>.json` is a **list** of provision
records. Current schema, field by field:

| Field | Type | Meaning / contract |
|---|---|---|
| `id` | str | `"<instrument_id>/h<hid>"` — unique within the instrument; `hid` is the crawl's element id, **stable across re-crawls of the same exhibit** |
| `instrument_id` | str | the instrument's slug (e.g. `warringah_lep_2011`) |
| `path` | [str] | position in the document tree as the crawler saw it (e.g. `["LEP and DCP", "Schedule 2 Exempt development"]`) |
| `structure` | str | the document-structure class the parser assigned (`schedule`, `unnumbered`, …) |
| `kind` | str\|null | reserved classification (currently unused) |
| `number` | str\|null | the provision's number where the document numbers them (`"Schedule 2"`, `"8.6"`, …); **null when unnumbered** |
| `heading` | str | the provision's title line |
| `text` | str | the provision body, verbatim-except-artefacts (see warts: hyperlink wrapping). Sub-subclauses stay inline — the MVP splits some by hand (8.5) |
| `tables` | [{rows: [[str]]}] | tables found inside the provision. **Untyped and headerless** (crawl dropped column headers) — cells are positional. This is the single most consequential wart (below) |
| `params` | {…} | reserved for typed parameters (ingest v2 will populate: thresholds, areas, counts) |
| `former_number` | str\|null | crosswalk field for the EP&A Act renumbering (79C→4.15, 80→4.16, 80A→4.17) |
| `rag_chunk_id` | str\|null | reserved for retrieval (Phase 2) |
| `status` | str | parser's own review flag: `ok` / `review` |
| `source` | {file, hid} | **provenance**: which crawl file + which element — every provision must trace to a frozen source (invariant I-3) |

**Invariants (to become a machine lint in ingest v2 — not yet enforced):**

1. `id` unique per instrument file.
2. `number` present iff `structure` indicates numbered material.
3. `source.file` exists in `kb/incoming/` and `hid` resolves within it
   (re-crawl reproducibility: same source → same `hid`).
4. `status` ∈ {`ok`, `review`}; a `review` provision must carry a note
   saying why.
5. No content beyond what is published in the instrument (the law is
   public data; drafts are handled by the considered-not-in-force flag,
   I-4).
6. **A run must record the KB version it used** (fingerprint of
   `kb/provisions/` in `report.json`) — *gap today: runs reference the KB
   implicitly; fix with ingest v2 or a one-line change in `decide.py`.*

## 2. Known warts (stated, with consequences)

| # | Wart | Where | Consequence | Status |
|---|---|---|---|---|
| W-1 | **LUTs are flattened**: the crawl dropped the Land Use Table's column headers, so block identity (no-consent / with-consent / prohibited) is **positional** | all LEPs; worst in `warringah_lep_2011` | zone-level permission decisions rest on a positional assumption; **verified by hand for R3 only** — re-verify per zone before use, or fix in ingest v2 (named blocks) | open; Spike A audits the rows; ingest v2 fixes the structure |
| W-2 | **Map-referenced standards** (Warringah 4.3/4.4) reference maps not in the corpus | `warringah_lep_2011` | determinations must be `indeterminate` — this is *correct system behaviour* (I-2), not a defect; the tool must never assume compliance | permanent until maps enter the corpus |
| W-3 | **EP&A Act renumbering** (in force 1 Nov 2025): 79C→4.15, 80→4.16, 80A→4.17 | cross-instrument | historical DAs/DCPs cite the old numbers; `former_number` exists for the crosswalk but is unpopulated; ingestion of any instrument citing old numbers needs the mapping | backlog #1 territory (normalisation) |
| W-4 | **2011 zone vocabulary ≠ post-2013** (e.g. C4 ≠ "General Residential") | `warringah_lep_2011`, `warringah_dcp_2011` | **no auto-mapping** between the vocabularies — a lookup table is a Phase-1 decision, not a parser job | open decision (Phase 1) |
| W-5 | **Hyperlink wrapping**: the ePlanning crawl wraps the names of referenced instruments in link markup, so KB text and source text differ in whitespace/anchors | all ePlanning-sourced provisions | verbatim citation matching is whitespace-insensitive *because of this*; it also means exact string diffing against source is meaningless — fidelity auditing (Spike A) must diff on *normalized* text | understood; Spike A's diff procedure bakes it in |
| W-6 | **Provision-number normalisation** imperfect across some instruments | several (see backlog #1) | clause addressing by number can be unreliable outside Warringah | backlog #1 (fix + re-ingest); ingest v2 subsumes it |
| W-7 | **Draft DCP 2026 not yet ingested** (677 MB in `kb/incoming/drafts/`) | future | the version-boundary reasoning the design doc requires (notification = boundary; draft DCP = considered-not-in-force) has no data node yet; **never citable as law** if/when ingested (I-4) | backlog #3 |

## 3. Quality table (Spike A fills this; until then the only audited
instrument is Warringah R3)

Counts verified 2026-09-27 (total **1,317**):

| Instrument | Provisions | Source | Text fidelity | Tables/LUT rows | Notes |
|---|---|---|---|---|---|
| `warringah_lep_2011` | 148 | ePlanning | — | R3 hand-verified; rest — | the MVP corpus |
| `warringah_dcp_2011` | 170 | ePlanning | — | — | |
| `warringah_dcp_2000` | 11 | council PDF | — | — | deferred-matter land (area→instrument map) |
| `pittwater_lep_2014` | 114 | ePlanning | — | — | |
| `pittwater21_dcp` | 464 | council PDF | — | — | largest file; `.bin` companion left untouched |
| `manly_lep_2013` | 93 | ePlanning | — | — | post-2013 zone vocabulary |
| `manly_dcp_2013` | 146 | ePlanning | — | — | |
| `foreshores_waterways_dcp_2005` | 94 | council PDF | — | — | state-instrument override (SREP 2005 area) |
| Warriewood Valley spec 2001 | 77 | council PDF | — | — | |

*Fidelity definitions: "text fidelity" = sampled provisions whose body
matches the source on normalized text (W-5) with no decision-relevant
error; "tables/LUT rows" = sampled table rows verified cell-by-cell,
100% required (they carry the numbers the fact layer tests against).*

## 4. Versioning and re-ingestion policy

- The KB is a **snapshot**: re-ingesting a changed instrument produces a
  new version of its file; runs pin the version they used (invariant 6).
- **Idempotence requirement (ingest v2):** same source files → byte-identical
  provision files (deterministic ordering, deterministic ids). Today's
  `kb/ingest.py` is not guaranteed this — an audit finding if Spike A
  shows it.
- The frozen crawl artifacts (`kb/incoming/`, 2026-09-25) are the
  single source of truth for what "the law said on 2026-09-25"; re-crawls
  are a different, dated event and must say so in their manifest.

## 5. Relationship to the synthetic cases

The two Frenchs Forest cases were **built against this KB's shape**
(its 12-block corpus, its R3 LUT, its 8.6/8.7 table layout). That is the
in-sample caveat in 04: the cases will keep working if we re-implement
the *extraction* (architecture verdict), and may stop working if the KB
*contract* changes — which is exactly why this document must be frozen
**before** ingest v2 starts.
