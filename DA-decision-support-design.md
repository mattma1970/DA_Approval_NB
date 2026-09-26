# DA Decision Support — Design Document

**Subject:** An AI-assisted decision support tool for property development applications (DAs) assessed by an NSW local council (local government area, LGA).

**Jurisdiction:** New South Wales (Australia).

**Status:** Design / concept stage. The regulatory corpus and sample DA packages have not yet been supplied; this document specifies the system, the technology choices (with discussion of alternatives), and the work needed to go from design to operation.

**Version:** 1.0 — 2026-07

---

## Table of contents

1. [Purpose, scope, non-goals](#1-purpose-scope-non-goals)
2. [Regulatory context (NSW)](#2-regulatory-context-nsw)
3. [Inputs: the DA package](#3-inputs-the-da-package)
4. [System architecture](#4-system-architecture)
5. [Technology choices and discussion](#5-technology-choices-and-discussion)
6. [Data model](#6-data-model)
7. [Rule language and NSW examples](#7-rule-language-and-nsw-examples)
8. [LLM adjudication design](#8-llm-adjudication-design)
9. [Decision logic](#9-decision-logic)
10. [Output specification](#10-output-specification)
11. [Human-in-the-loop, audit and evaluation](#11-human-in-the-loop-audit-and-evaluation)
12. [Legal, ethical and governance considerations](#12-legal-ethical-and-governance-considerations)
13. [Deployment and security](#13-deployment-and-security)
14. [Phased roadmap](#14-phased-roadmap)
15. [Risks and mitigations](#15-risks-and-mitigations)
16. [What we need from the council](#16-what-we-need-from-the-council)
- [Appendix A — Glossary](#appendix-a--glossary)
- [Appendix B — Key current EP&A Act provisions (verified, Nov 2025 compilation)](#appendix-b--key-current-epa-act-provisions)
- [Appendix C — Public data sources for building a golden set (NSW)](#appendix-c--public-data-sources-for-building-a-golden-set-nsw)
- [Appendix D — Northern Beaches LGA: instrument stack and transition state](#appendix-d--northern-beaches-lga-instrument-stack-and-transition-state-verified-july-2026)

---

## 1. Purpose, scope, non-goals

### 1.1 What the tool is

A **decision support** system that:

1. Ingests a **regulatory corpus** — the LGA's Local Environment Plan (LEP), Development Control Plan (DCP), applicable State Environmental Planning Policies (SEPPs), the Environmental Planning and Assessment (EP&A) Act and Regulation, and Commonwealth overlays (notably the EPBC Act 1999).
2. Ingests a **development application package** in PDF form: statutory form and free-text answers, site/contour/plan drawings, consultant reports (architecture, landscape, traffic, noise, ecology, heritage, stormwater/water, fire, structural, energy/BASIX, etc.), and optionally objector submissions and site-visit notes.
3. **Extracts structured facts** from the package (building height, footprint, FSR/LDR inputs, setbacks, dwelling count, parking, vegetation removal, water features, use class, lot attributes, …).
4. **Analyses compliance** against the corpus using a hybrid engine:
   - **deterministic rules** for codified, measurable standards (height limits, FSR/LDR caps, setbacks, parking schedules, BASIX applicability, flood levels, prohibited uses);
   - **LLM adjudication** for judgment-based criteria (amenity, character, outlook, noise impact, heritage significance, visual impact), each finding **required to cite** the regulation it relies on and the evidence it was drawn from.
5. **Recommends** one of: **approve**, **conditional approval**, or **refuse** — plus the conditions, referral triggers, and drafted reasons supporting that recommendation.
6. Produces a **cited, auditable determination package** for the planning officer, who reviews, amends, and signs.

### 1.2 What the tool is not (non-goals)

- **It does not determine.** Under the EP&A Act the consent authority (the council, or a delegated officer within delegation, or the Minister) makes the determination. The tool's output is a *recommendation and a reasoned analysis*. No output of the tool is a legal determination, and the tool must be designed so that this boundary is structurally obvious (separate "recommendation" and "determination" artefacts, separate roles).
- **It does not replace site visits, public consultation, or statutory notification.** It processes documents supplied to it.
- **It does not make planning policy.** The regulatory corpus is data; the tool applies it, it does not amend it.
- **It does not handle building certification** (Part 6 of the Act — principal certifying builder, occupation certificate) as a decision; it flags matters that will be relevant at certification (NCC/BCA compliance, fire) as information for the officer.

### 1.3 Users

| Role | Use of the tool |
|---|---|
| Planner / planning officer | Primary user. Reviews extracted facts, findings, recommendation; amends; signs. |
| Head of planning / delegation-holder | Reviews escalated/low-confidence cases; approves final determination package. |
| Council / committee | Receives the final determination package (as under existing delegation and standing orders). |
| Applicants and objectors | Do not interact directly; they are affected via the reasons for determination and conditions, which the tool drafts but humans finalise. |
| Records / legal | Audit trail access; records management. |

### 1.4 Design principles

1. **Advisory, never binding.** The tool recommends; a named human decides.
2. **Cited reasoning.** Every finding must cite (a) the specific instrument provision and (b) the specific evidence (document, page, figure, form field). No citation, no finding. Citations are **machine-verified** against the corpus (see §8.4).
3. **Reproducible.** Deterministic rules are versioned code/data; LLM calls are version-pinned (model + prompt) and fully logged.
4. **Human-verifiable inputs.** Numeric facts that drive hard outcomes (height, setbacks, FSR) carry confidence scores and are surfaced for officer confirmation before a hard refusal is recommended.
5. **Records-native.** Everything produced is a durable record of the DA file (see §13).
6. **Jurisdiction as data.** NSW instruments are loaded into the knowledge base as versioned data; nothing NSW-specific is hard-coded except the *shape* of the rule language.

---

## 2. Regulatory context (NSW)

### 2.1 The hierarchy the tool must reason with

| Layer | Instrument (examples) | What it governs |
|---|---|---|
| Commonwealth | Environment Protection and Biodiversity Conservation Act 1999 (EPBC Act); National Construction Code (NCC/BCA, referenced for building matters) | Referrable actions (listed species, Commonwealth marine, Ramsar wetlands); building performance referenced in assessment |
| NSW legislation | **EP&A Act 1979** (currently renumbered — see §2.2); Environmental Planning and Assessment Regulation 2021; Local Government Act 2009; Heritage Act 1977; Biodiversity Conservation Act 2016; Roads Act 1993; WHS Act 2011 | The decision framework itself; delegation; heritage; offsets; road access; construction safety |
| State planning instruments | SEPPs (see list below) | State-wide development standards and policies (flood, bushfire, biodiversity, heritage, views, noise, water, coastal zone, BASIX, …) |
| Local planning instruments | The LGA's **LEP** (zoning, use classes, height/FSR/LDR standards, overlays) and **DCP** (design standards: setbacks, parking, character, landscape, traffic, amenity) | The primary compliance baseline for the DA |
| Guidance (non-binding) | DCP guidelines, Transport for NSW traffic requirements, NSW Fire Brigade requirements, Australian Planning Standards, council standard-conditions library | Inputs to judgment-based findings; source of standard condition wording |

> **Note on the SEPP list.** The tool loads whatever instruments the council confirms for its LGA. A typical relevant set includes: SEPP (Resilience and Hazards) 2021 (flood, bushfire, land slip, earthquake, coastal hazards); SEPP (Biodiversity and Conservation) 2021; SEPP (Heritage) 2021; SEPP (Visual Amenity) 2013; SEPP (Noise) 1997 (as amended); SEPP (Water) 2020; SEPP (Building Sustainability Index: BASIX) 2004 (as updated 2023); SEPP (Coastal Zone) 2021. The exact inventory is confirmed with the council (§16) and versioned in the KB.

### 2.2 The EP&A Act has been comprehensively renumbered — a core design constraint

As of the current compilation (in force from 1 November 2025; accessed 12 November 2025), the EP&A Act 1979 has been **renumbered into decimal division form**. Key provisions the tool's decision logic depends on:

| Current provision | Former provision | Content relevant to the tool |
|---|---|---|
| 4.1 / 4.2 / 4.3 | (Division 4.1) | Development that does not / does / must not need consent (exempt, consent-required, prohibited) |
| 4.10 | — | Designated development (notification & submission period) |
| 4.12 | (s 4.1 et seq.) | Application (form, content) |
| 4.13 | — | Consultation and concurrence (agencies that must be consulted) |
| 4.15 | **s 79C** | **Evaluation** — matters for consideration: (a) environmental planning instruments incl. proposed instruments, DCP, planning agreements, regulations; (b) likely impacts (natural/built environment, social/economic); (c) site suitability; (d) submissions; (e) public interest. Plus **4.15(2)–(3)** non-discretionary development standards logic and **4.15(3A)** DCP flexibility, **4.15(4)** BCA-accredited products |
| 4.16 | **s 80** | **Determination** — grant (unconditional/conditional) or refuse; **4.16(2)** subdivision that would contravene the Act/instrument/regulation **must** be refused; **4.16(3)** deferred-commencement consent; **4.16(4)** total or **partial consent** |
| 4.17 | **s 80A** | **Conditions** — a condition may be imposed if it relates to a matter in 4.15(1) of relevance to the development (among other grounds) — this is the *relevance test* for every condition the tool drafts |
| 4.18 | s 81 | Post-determination notification (applicant, objectors, council) |
| 4.20 | s 83 | Date consent has effect (NSW planning portal registration; 28-day delay for designated development) |
| Division 4.4 | s 83A/83B | Concept development applications |
| Division 4.5 | — | Complying development (CCDs) — the tool can flag when a DA could have proceeded as a CCD |
| Division 4.7 | s 89C et seq. | **State significant development** — referral pathway (Minister / Independent Planning Commission) |
| Division 4.8 | — | Integrated development (e.g. mining + other development) — approval body coordination |
| Division 4.9 | — | Lapsing (4.53), modification (4.55), revocation (4.57) |
| Part 5 | — | Environmental impact assessment (5.5 duty to consider environmental impact) |

Consequences for the design:

- **Nothing is hard-coded.** The KB stores the *current* text of each provision, its new number, and the PCO cross-reference ("cf previous s X"), which is machine-parseable. Legacy documents (old determinations, older LEPs, consultant reports citing "s 89" or "s 79C") are mapped to current numbering automatically.
- **Versioned law.** The status information of the current compilation lists *uncommenced* amendments (e.g. 24-Hour Economy Legislation Amendment (Vibrancy Reforms) Act 2024 No 76; Environmental Planning and Assessment Amendment Act 2025 No 24 (partially commenced); the 60-day deemed approval bill 2025; the Planning System Reforms bill 2025). The KB must distinguish *in-force*, *commenced-pending*, and *not-commenced* provisions, and the tool must warn when a pending amendment (e.g. deemed-approval changes) materially affects a live case's timeline.
- **Legislative watch.** A standing task monitors the NSW legislation register for changes to the EP&A Act/Regulation and each loaded SEPP; changes produce a KB version bump and a regression run against the golden set (§11).

### 2.3 The decision-relevant logic in 4.15–4.17 (the engine's backbone)

Three statutory mechanisms drive the decision logic (§9) and must be first-class in the KB/rule model:

1. **Non-discretionary development standards — 4.15(2)–(3).** Many LEP/DCP standards (height, FSR/LDR, setbacks) are designated *non-discretionary*. If the DA **complies**, the consent authority is not entitled to take them into further consideration, **must not refuse** on that ground, and **must not impose a condition more onerous** than the standard. If the DA **does not comply**, the discretion is not so limited, and any instrument *flexibility provision* (e.g. a LEP clause permitting variation on demonstrated design conflict) may be engaged.
2. **DCP standards — 4.15(3A).** If the DA complies with a DCP standard, the authority must not require a more onerous standard. If it does not comply, the authority **must be flexible** and allow reasonable alternative solutions that achieve the *objects* of the standard; the DCP may only be considered in connection with assessing this DA.
3. **Conditions — 4.17.** A condition must relate to a matter in 4.15(1) (or another listed ground) of relevance to the development. Every condition the tool drafts is checked against this relevance test and must be capable of compliance.

---

## 3. Inputs: the DA package

### 3.1 Typical contents of the PDF package

| Document | Form | Extraction target |
|---|---|---|
| Statutory application form + **free-text answers** | Text-layer PDF (form fields) or scanned | Use class, site address/lot, applicant, building height, dwelling count, parking, and free-text answers to each form question |
| Site plan, contour plan | Vector in PDF or scanned raster | Boundaries, lot size, existing buildings, vegetation (protected species, VPO), flood levels, bushfire (BAL) zones, topography, neighbours |
| Proposed plans: site plan, elevations, sections, floor plans, landscape plan | Vector or raster | Building envelope, height above NPD, footprint areas per floor (→ FSR/LDR), side/rear/front setbacks, car spaces, landscape area, wall heights/fences |
| Consultant reports | Text (with tables, charts, figures) | Traffic (access, turning, parking demand), noise (levels, receptors), ecology (species, habitat, offsets), heritage (significance, impact), stormwater/water (discharge, treatment), fire (access, separation, egress), energy/BASIX (score, systems), structural/geo |
| Objector submissions (optional input) | Mixed | Each objection, mapped to a 4.15(1) consideration |
| Site-visit notes, correspondence (optional) | Text | Off-record facts the officer records |

**Free-text answers** deserve special treatment: each Q&A pair is parsed, then *classified* as (a) factual claim, (b) mitigation commitment, or (c) representation. Commitments (e.g. "we will provide an additional car space") become **candidate conditions**; claims are cross-checked against reports and drawings, and **contradictions are flagged** (e.g. form says 8.4 m, section shows 9.6 m) — a common, high-value finding type.

### 3.2 Drawings

Drawings are usually embedded in the PDF either as **vector** (directly extractable geometry) or as **scanned raster** (requires image understanding). The tool handles both (§5.4). Drawing-derived facts (heights, setbacks, areas) are treated as *measured facts* with a confidence score and are cross-checked against applicant-stated facts on the form.

### 3.3 Ingestion rules

- Files are fingerprinted (SHA-256) on receipt; the original is never modified (object-locked storage, §13).
- Every page is classified (form / site plan / elevation / section / report / correspondence / other) — by LLM + heuristics — and a *page manifest* is kept, because every finding must be able to point at `document, page, region`.
- Native CAD (DWG/DXF) files, if supplied, take the vector path (§5.5).

---

## 4. System architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                LAYER 0 — INTAKE                            │
│  Officer uploads DA package (PDFs, optional CAD) + case metadata           │
│  → fingerprint, store (MinIO, object-locked) → page manifest → Postgres    │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        LAYER 1 — EXTRACTION & UNDERSTANDING                │
│  text pages ── PyMuPDF ──→ form fields + free-text Q&A → structured facts │
│  tables ───── pdfplumber ─→ report tables (noise levels, traffic counts)  │
│  drawings ── vector path (pdf vector ops / ezdxf) → geometric facts       │
│           └─ raster path (rasterise → vision LLM, JSON schema) → facts    │
│  reports ─── LLM summariser → per-report issue summaries + key numbers    │
│  ALL facts carry: value, unit, method, confidence, evidence (doc/page)    │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 2 — REGULATORY KNOWLEDGE BASE                  │
│  structured provisions (YAML): id, instrument+version, path, kind,        │
│    params (hard limits, schedules), flexibility refs, "cf previous" map   │
│  full-text RAG index: provisions + guidance, embedded (bge-m3 class),     │
│    stored in Qdrant; effective-date & commenced status per version        │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 3 — COMPLIANCE ENGINE (hybrid)                 │
│  A. Deterministic evaluator: rules (YAML) × facts → findings               │
│     (zone/use, height, FSR/LDR, setbacks, parking, flood, BASIX, …)       │
│  B. LLM adjudicator: issue prompts + RAG-retrieved provisions + facts →    │
│     findings for judgment criteria (amenity, character, outlook, noise,    │
│     heritage, ecology, visual impact) — each finding must cite provision  │
│     and evidence; citations machine-verified; confidence scored           │
│  C. Submissions mapper: each objection → 4.15(1) consideration → finding  │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 4 — DECISION SYNTHESIS                         │
│  findings → aggregation: approve / conditional approval / refuse /         │
│    request-additional-information; referrals (Div 4.7, EPBC, heritage);   │
│    condition drafting (each with 4.17 relevance basis + template);         │
│    drafted reasons (4.15 matters, submissions responses); confidence gate │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    LAYER 5 — OFFICER INTERFACE & RECORDS                   │
│  officer dashboard: review facts (confirm/amend), findings (accept/        │
│    override), conditions, recommendation; sign-off → DETERMINATION         │
│  package (machine JSON + human report PDF/DOCX); immutable audit trail of │
│  every LLM call, rule version, human edit → records system + evaluation   │
└────────────────────────────────────────────────────────────────────────────┘
```

**Cross-cutting:** the audit/evaluation service (call logs, golden-set harness, legislative watcher) sits alongside all layers; the LLM serving stack (vLLM, local GPUs) is a shared dependency of Layers 1, 3B and 4.

---

## 5. Technology choices and discussion

This section is the core of the design decision: for each component, the candidates, the trade-offs, the choice, the rationale, and the fallback.

### 5.0 Summary table

| # | Component | Chosen | Rejected / fallback |
|---|---|---|---|
| 1 | Language/runtime | **Python 3.12** | TypeScript (UI only), Java/.NET |
| 2 | PDF text extraction | **PyMuPDF** (+ pdfplumber for tables) | pdfminer.six, Tika, unstructured.io |
| 3 | OCR / scanned-page understanding | **Vision LLM (primary); Tesseract (fallback)** | Cloud OCR (Textract/DocAI) |
| 4 | Drawing comprehension | **Vision LLM with JSON-schema output on rasterised pages; vector parsing where available** | Classical CV/OCR pipelines |
| 5 | CAD (optional) | **ODA File Converter → ezdxf** | commercial SDKs |
| 6 | Reasoning LLM (adjudication, synthesis) | **Local open-weight (Qwen-class 70B), served by vLLM** | Cloud frontier API (optional escalation tier only) |
| 7 | Extraction LLM | **Same local model (32B class sufficient)** | separate small model (only if GPU budget is tight) |
| 8 | Embeddings / RAG | **bge-m3-class embeddings → Qdrant** | pgvector (fallback), commercial vector DB |
| 9 | Rule engine | **Declarative YAML + thin Python evaluator** | OPA/Rego (fallback if rules grow complex), embedded code |
| 10 | Orchestration | **asyncio pipeline + Postgres job state (pilot); Temporal (scale)** | Celery/Redis, Airflow |
| 11 | Storage | **PostgreSQL 16 (+JSONB) + MinIO with object lock** | MongoDB, cloud S3 |
| 12 | Officer UI | **Streamlit (pilot) → Next.js/React (production)** | low-code/BI tools |
| 13 | Report generation | **Jinja2 + WeasyPrint (PDF), docxtpl (DOCX)** | HTML print CSS only |
| 14 | Model ops | **vLLM + prompt/model versioning in git; immutable call log; response cache** | LangChain-style framework (replaced by thin direct calls) |

### 5.1 Language and runtime — Python 3.12

**Options.** Python; TypeScript/Node; Java or .NET.

**Choice: Python 3.12.** The entire pipeline is document-processing + LLM-centric: PyMuPDF, pdfplumber, ezdxf, vLLM clients, embedding models and the evaluation harness are all strongest in Python. One language across pipeline and evaluation reduces cognitive load for a small team. **Discussion:** TypeScript would have been defensible (the officer UI is React anyway) but buys nothing on the data side and splits the stack; Java/.NET would suit a large enterprise IT shop but there is no document-processing ecosystem advantage and most councils' IT teams and vendors are Python-friendly. The production UI is TypeScript (a separate, well-isolated package) — the pipeline and UI are separate deployables and the UI talks to a small JSON API.

### 5.2 PDF text extraction — PyMuPDF (+ pdfplumber for tables)

**Options.** PyMuPDF (fitz); pdfminer.six; Apache Tika; unstructured.io; OCR-first (everything through Tesseract).

**Choice: PyMuPDF as the workhorse.** It is fast, permissive about messy council PDFs, extracts both text *and* embedded images (which the drawing pipeline needs), and gives geometry (page rectangles, image bboxes) needed to record evidence pointers. **pdfplumber** is used where layout-accurate tables matter (traffic counts, noise levels, BASIX numbers). **Discussion:** pdfminer.six is more faithful to low-level PDF semantics but slower and clumsier for image extraction — a poor fit when drawings are half the input. Tika is Java-centric and a poor fit for a Python stack. unstructured.io is attractive (partitions docs into elements) but adds an opaque pipeline and, at the time of writing, weaker control over *where on the page* a fact came from — the evidence-pointer requirement (§8.4) makes raw-geometry access important. OCR-first is wrong because the vast majority of DA PDFs have a text layer (they are born-digital from CAD/word processors); paying an OCR cost for everything would be both slower and less accurate than reading the actual text layer.

### 5.3 OCR / scanned-page understanding — vision LLM primary, Tesseract fallback

**Options.** (a) Tesseract 5 (local, classic OCR); (b) cloud OCR (AWS Textract, Google Document AI); (c) a vision-capable LLM.

**Choice: the vision LLM is primary for scanned pages and all drawing pages; Tesseract is a cheap fallback for plain scanned text pages.** **Discussion.** This is the most consequential choice in the system. DA packages routinely contain *scanned* drawings — and a drawing is not text: it is dimensions, height markers, scale bars, symbolised vegetation, and annotations that classical OCR mangles (dimension leaders break up numbers, scale-dependent text, rotated labels). A vision LLM (see §5.6) reads a rasterised plan page the way a planner does and can return *structured* output (JSON: heights, setbacks, areas) with a stated confidence. Cloud OCR is technically excellent for scanned *text* but (i) sends the council's confidential DA data off-site — a hard privacy objection for planning data — and (ii) still cannot "understand" drawings. Tesseract stays in the stack for two reasons: zero-cost fallback when the GPU is busy, and a second opinion (disagreement between Tesseract and the vision LLM on the same page is a useful confidence signal).

### 5.4 Drawing comprehension — vision LLM with JSON-schema output, cross-checked

**Approach.** Each drawing page is rasterised at 200–300 DPI and sent to the vision model with a **page-type-specific JSON schema** (site-plan schema ≠ section schema ≠ landscape schema). The model returns measured facts (e.g. `{"building_max_height_npd_m": 14.2, "confidence": 0.87, "region": "upper-right"}`) plus a short note on *how* it derived each value (scale bar, height marker, dimension string). **Two safeguards:**

1. **Scale discipline.** The schema requires the model to first identify and report the scale (1:100 etc.) and the datum reference (NPD, AHD) before reporting measurements; the evaluator re-checks that dimension strings and scale are mutually consistent where possible.
2. **Cross-checking.** Drawing-derived facts are compared with (a) applicant-stated facts on the form and (b) other drawing pages (the section height must match the elevation). Discrepancies become *flagged findings* rather than silent failures — and any discrepancy that would drive a hard refusal requires officer confirmation of the number before the recommendation can be final (§9.6).

**Discussion.** Pure classical CV (Hough lines, symbol detection) was rejected: it is brittle across drawing styles (every architect draws differently), requires heavy per-project tuning, and still cannot read annotations. Vector-path parsing (below) is used *in addition* where the PDF carries real vector geometry, because measured vector geometry is more accurate than vision — but vision is the universal path and the one that handles the common case of scanned drawings.

### 5.5 Native CAD (optional input) — ODA File Converter → ezdxf

If a DA is lodged with DWG files (common for larger applications), the **ODA File Converter** (free, from the Open Design Alliance) converts DWG → DXF, which **ezdxf** parses into geometry: exact lot polygons, building footprints, wall heights where annotated, survey marks. This yields *exact* geometry for FSR/LDR/setback computation at zero inference cost. It is optional: the vision path already covers PDF-only packages, and DWG availability is inconsistent. Commercial CAD SDKs (RealDWG,ODA commercial) were rejected on cost and licensing for a tool whose CAD path is secondary.

### 5.6 The reasoning LLM — local open-weight (Qwen-class), vLLM-served

**Options.** (a) Cloud frontier APIs (GPT-4o/Claude-class); (b) local open-weight models (Qwen3 dense/MoE 70B-class, Llama 3.3 70B, Qwen2.5-VL/Qwen3-VL for vision); (c) hybrid: local for everything, cloud escalation for low-confidence cases.

**Choice: local-first — a 70B-class open-weight model (Qwen class; exact generation selected at build time and *pinned per deployment*) served by vLLM on 1–2 high-end GPUs; a smaller (8–32B) sibling model for bulk extraction tasks; vision model (72B-class VL) for drawings. A cloud escalation tier is *permitted but off by default*, and if enabled sends only minimised data (the specific retrieved provision text + extracted facts for the issue in question — never whole documents).**

**Discussion.**
- *Why not cloud-first?* DA packages contain confidential applicant information (personal, commercial, sometimes land-valuation-sensitive material) and objector data; processing them through a third-party API is a privacy, records-management, and (for a public authority) political exposure. NSW's PPIP Act 1998 and GIPA obligations make on-prem processing the clean position. It also removes per-token cost, latency variance, and vendor dependence, and — critically — **pinning an exact model+prompt version is what makes the audit trail and regression testing meaningful**; a cloud model that silently changes behaviour under the hood (API version drift) is an audit liability.
- *What about the capability gap?* A 70B-class open model is not a frontier model on adversarial reasoning, but the task here is *structured legal-compliance reasoning with mandatory citation*, which recent open models handle well — and the design compensates: every citation is machine-verified against the corpus (§8.4), judgment findings carry confidence scores, and low-confidence outcomes route to humans rather than to a stronger cloud model. If evaluation (§11) shows the local model under-performing on a specific issue type, the options are: fine-tune the local model on the council's own annotated golden set (data stays on-site), or enable the minimised cloud tier for that issue type only, with a governance sign-off.
- *Why Qwen class specifically?* Strong document/long-context behaviour (64k+ context fits an entire DA + retrieved provisions in one call), good structured-output (JSON) compliance, a vision member of the same family (fewer integration seams), and it runs comfortably on commodity datacentre GPUs via vLLM. Llama 3.3 70B is a reasonable alternative; the model is a **configuration item**, not a dependency — the pipeline consumes it through one thin adapter, so swapping model generations is a config change + regression run, not a rewrite.
- *Hardware.* 1× A100-80GB (or 2× L40S-48GB) runs the 70B reasoning model at Q4/Q8 quantisation with vLLM plus the vision model; a second CPU node runs the pipeline, Postgres and MinIO. A single consumer 48GB GPU (2× 24GB) is the bare-minimum pilot configuration using the 32B dense model.

### 5.7 Embeddings and vector search — bge-m3-class → Qdrant

**Options.** Embedding models: bge-m3 (multilingual, strong on technical/legal text), Qwen embedding models, OpenAI embeddings (rejected — same data-egress objection as §5.6). Vector stores: Qdrant, pgvector, Weaviate, Milvus.

**Choice: bge-m3-class embeddings stored in Qdrant.** **Discussion.** The regulatory corpus is small (tens of thousands of chunks at most) — any of these stores would work, which makes the decision about *operations*, not capacity: Qdrant is a single-binary, low-ops, fast service with hybrid (dense + sparse/BM25) search, which matters for legal text where exact clause-number matches ("s 4.15", "Clause 2.1") must not be drowned by semantic similarity. pgvector is the zero-extra-service fallback (the index lives in the same Postgres the app already uses) and is what a two-person ops team might prefer; it is kept as the sanctioned alternative. Retrieval is always **hybrid** (vector + keyword) with re-ranking, and the top-k provision *text* (with instrument, version and clause path) is what the adjudicator sees — the LLM never "remembers" law, it only reasons over text handed to it (this is the primary anti-hallucination design, §8.4).

### 5.8 The rule engine — declarative YAML + thin Python evaluator

**Options.** (a) Rules as Python code; (b) a general policy engine — OPA/Rego, Drools; (c) a bespoke declarative schema (YAML) interpreted by a small typed-evaluation library.

**Choice: (c)** — a small YAML schema (see §7) validated by JSON Schema and interpreted by a ~500-line Python evaluator with unit tests per rule. **Discussion.**
- *Against code:* rules embedded in Python cannot be read, amended or governed by planning staff, and change control becomes a software-release problem. The rule set is policy: it should live next to the instruments, be diff-able, versioned, and amendable by a non-developer (with officer sign-off).
- *Against OPA/Rego:* OPA is the right tool when policy logic becomes genuinely complex (DAGs of conditions, cross-resource queries). NSW DA rules are mostly *threshold tests with applicability predicates* (zone × use × overlay × lot attributes → limit → compare fact). At that shape, a bespoke schema is more legible to non-engineers, has no separate runtime to run, and its evaluation is trivially auditable (the YAML *is* the explanation of the check). OPA remains the escalation path: the evaluator's interface is the same, so a rule that outgrows the schema can be ported without touching the findings model.
- *Against Drools:* Java-centric, heavier, and the ecosystem mismatch with a Python stack is not justified here.

### 5.9 Orchestration — asyncio pipeline + Postgres job state (pilot); Temporal at scale

**Options.** Celery/Redis; Airflow; Temporal; a single-process asyncio pipeline with a Postgres-backed job table.

**Choice: the pilot is a single asyncio service** (one process, in-process LLM calls, Postgres `jobs`/`case_state` tables recording every stage, so a crashed run resumes from its last committed stage) **and the scale path is Temporal.** **Discussion.** A council's DA volume (a few to a few hundred per month) does not need a distributed task queue; the real requirements are *durability* (a run may take 20–60 minutes — it must survive restarts), *observability* (every stage logged) and *replayability* (re-run a stage with a new model version). A Postgres state table gives all three with minimal moving parts. Airflow was rejected (it is a batch-scheduler, a poor fit for per-case long-running stateful workflows with human-in-the-loop interrupts). Celery/Redis adds a second state store without buying anything at this volume. Temporal is the right long-term choice (durable workflows, retries, versioned code, human-signal interrupts map directly onto the officer-review gates) and is pre-selected so the pilot's stage definitions port with minimal change — but adopting it in week one of a pilot would be premature process overhead.

### 5.10 Storage — PostgreSQL 16 (+ JSONB) + MinIO with object lock

**Options.** Postgres; MongoDB; a document-database-centric stack; cloud object storage (S3).

**Choice: PostgreSQL for all relational and semi-structured state** (cases, documents, facts, findings, conditions, decisions, audit events — extracted facts live in JSONB columns with a partial index on their keys) **and MinIO for object storage** (original PDFs, rasterised pages, generated reports) **with object lock enabled (WORM)** so the evidentiary record cannot be altered after the fact. **Discussion.** The domain is strongly relational with one JSON-heavy shape (facts) — JSONB in Postgres covers it with transactional consistency, which a multi-store split would lose. MongoDB's flexible schema buys nothing and costs transactions. S3-class cloud storage is excluded for the same data-egress reason as the LLM choice (§5.6); MinIO is S3-API-compatible, so nothing in the code assumes on-prem — if the council later runs in a sovereign cloud (e.g. a government-region S3), the storage adapter is the only thing that changes.

### 5.11 Officer interface — Streamlit (pilot) → Next.js/React (production)

**Options.** Streamlit/Gradio; Next.js/React; an internal low-code platform.

**Choice: Streamlit for the pilot** (days to build; the review workflow — list facts → confirm/amend → list findings → accept/override → conditions → sign-off — is a linear form-driven flow that Streamlit handles well) **and Next.js (React) for production.** **Discussion.** The production UI needs what Streamlit does not: proper access control integration with the council's SSO, concurrent users on different cases, printable sign-off pages, and a clean compliance-matrix presentation. Building the production UI in Streamlit would become a fight against the framework. The thin JSON API underneath (cases/findings/conditions/decisions resources) is identical for both, so the pilot is not sunk cost. Low-code platforms were rejected: the sign-off workflow and audit annotations are bespoke enough that buying flexibility beats buying speed here.

### 5.12 Report generation — Jinja2 + WeasyPrint (PDF) and docxtpl (DOCX)

The determination package report (§10.2) is rendered from the same machine-readable decision JSON (single source of truth): Jinja2 templates → WeasyPrint for the PDF (the official record format), docxtpl for an editable DOCX for council minutes/committee packs. WeasyPrint over headless-Chrome printing: deterministic pagination, no browser dependency, good enough for document-style reports.

### 5.13 Model ops — thin direct LLM calls, versioned, logged, cached

Deliberately **not** a heavy orchestration framework (LangChain-class). The system makes a small number of well-defined LLM calls (page classification, per-drawing extraction, per-report summarisation, per-issue adjudication, condition drafting, reasons drafting). Each call site is a named function with: a **prompt version** (git-tracked), a **model version** (deployment-pinned), structured output enforced by **guided decoding** (JSON schema at decode time — the model *cannot* emit a malformed citation), and an **immutable log entry** (case, call type, prompt hash, model id, input hashes, output, tokens, latency). Responses are cached on (prompt-version, model-version, input-hash) so re-runs are cheap and byte-reproducible. **Discussion.** Frameworks buy convenience at the cost of exactly the properties this tool is judged on: reproducibility, auditability, and the ability to say *precisely* what the model was told. With ~8 call sites, a thin adapter (~300 lines over the vLLM client) is more maintainable than any framework integration.

---

## 6. Data model

Entity sketch (Postgres; JSONB shapes shown for the flexible ones):

| Entity | Key fields |
|---|---|
| `reg_instrument` | id, name, jurisdiction, version, effective_from, effective_to, status (in_force / pending / repealed), source_url, sha256 of loaded text |
| `reg_provision` | id, instrument_id, path (part/clause/para), kind (`hard_limit`, `non_discretionary_standard`, `permitted_use`, `prohibited_use`, `performance_standard`, `guidance`, `flexibility`, `procedure`), text (current), params (JSONB), former_number ("cf previous s 79C"), rag_chunk_id |
| `rule` | id, version, provision_ids, applies_when (JSONB predicate), checks (JSONB, see §7), on_fail (JSONB), effective_from/to, approved_by |
| `da_case` | id, lga, site_address, lot, zone, overlays[], use_class, lodged, category (new dwelling / addition / subdivision / commercial / …), applicant, status |
| `document` | id, case_id, kind (form/siteplan/elevation/section/landscape/traffic/noise/ecology/heritage/stormwater/fire/basix/report/other), sha256, page_count, path (MinIO key) |
| `page` | id, document_id, page_no, render_path, text_sha256, classification |
| `fact` | id, case_id, key (e.g. `building.max_height_npd_m`), value, unit, method (`form_field`/`vision`/`vector`/`report_llm`/`officer`), confidence, evidence (JSONB: [{doc, page, region, quote}]), status (`proposed`/`confirmed`/`amended`), officer_note |
| `finding` | id, case_id, rule_id or issue_type, provision_cited (id, validated), status (`pass`/`fail_hard`/`fail_mitigable`/`undetermined`/`n_a`), facts_used, reasoning, confidence, evidence (JSONB), conditions (ids), officer (status, note) |
| `condition` | id, case_id, text, stage (`pre_construction`/`construction`/`ongoing`/`deferred_commencement`), source (`standard_template`/`bespoke`), template_id?, legal_basis (provision id + 4.17(1) matter), finding_ids |
| `referral` | id, case_id, trigger, instrument/authority, status |
| `decision_recommendation` | id, case_id, recommendation (`approve`/`conditional`/`refuse`/`request_info`), confidence, summary, model_versions (JSONB), created_at |
| `determination` | id, case_id, officer_id, decision (`grant`/`grant_conditional`/`refuse`), conditions (final), reasons (final), signed_at — **created only by a human** |
| `audit_event` | id, ts, actor (service/llm/officer id), case_id, entity, action, before/after hashes, model_id, prompt_version, input_hash, output |

### 6.1 Example — extracted fact

```json
{
  "key": "building.max_height_npd_m",
  "value": 14.2,
  "unit": "m",
  "method": "vision",
  "confidence": 0.87,
  "evidence": [{
    "document": "DA-2025-123-drawings.pdf",
    "page": 12,
    "region": "section-5-north",
    "quote": "RIDGE 14.2m AHD"
  }],
  "status": "proposed",
  "cross_check": {
    "form_value": 14.2,
    "elevation_value": 14.0,
    "consistent": false,
    "note": "Section 5 shows 14.2 m; north elevation shows 14.0 m — officer to confirm."
  }
}
```

### 6.2 Example — rule (see §7 for the language)

```yaml
rule_id: dcp-height-max
version: 3
provision_ids: [dcp2012-2.1-height]
applies_when:
  zone_in: ["R2", "R3"]
  use_class_in: ["2a", "2b", "2c"]
checks:
  - name: height_within_standard
    fact: building.max_height_npd_m
    op: lte
    param: max_height_m          # resolved from provision params, e.g. 12.0
on_fail:
  classification: fail_hard
  allow_flexibility: true        # check LEP flexibility provision before hard refusal
  condition_curable: false
  officer_confirmation_required: true
```

### 6.3 Example — finding

```json
{
  "finding_id": "F-014",
  "rule_id": "dcp-height-max",
  "status": "fail_mitigable",
  "provision_cited": {
    "instrument": "DCP 2012 (LGA)",
    "path": "Clause 2.1 (Building height)",
    "provision_id": "dcp2012-2.1-height",
    "verified": true
  },
  "facts_used": {
    "building.max_height_npd_m": {"value": 14.2, "status": "confirmed"},
    "lot.area_m2": {"value": 850, "status": "confirmed"}
  },
  "reasoning": "Proposed height 14.2 m exceeds the DCP maximum of 12 m applicable to lots under 1,000 m2. The LEP flexibility provision (Pt 4.3 cl 2) does not engage on the materials provided; the officer may consider a variation, but as drafted the development does not comply with a non-discretionary standard.",
  "confidence": 0.93,
  "evidence": [
    {"document": "DA-2025-123-drawings.pdf", "page": 12, "region": "section-5-north"}
  ],
  "conditions": ["C-003"],
  "officer": {"status": "accepted"}
}
```

### 6.4 Example — machine-readable decision

```json
{
  "case_id": "DA-2025-123",
  "recommendation": "conditional_approval",
  "confidence": 0.86,
  "requires_officer_review": true,
  "review_reasons": ["One finding at confidence 0.87 < 0.9 on a non-discretionary standard"],
  "findings_summary": {"pass": 18, "fail_mitigable": 2, "fail_hard": 0, "undetermined": 1},
  "referrals": [],
  "conditions": [
    {
      "id": "C-003",
      "text": "Prior to the start of construction, a revised site plan and sections showing a maximum building height not exceeding 12.0 m above NPD shall be submitted and approved by the consent authority.",
      "stage": "pre_construction",
      "source": "bespoke",
      "legal_basis": {"provision_id": "dcp2012-2.1-height", "s417_matter": "4.15(1)(a)(iii) DCP"},
      "finding_ids": ["F-014"]
    }
  ],
  "statutory_timelines": {
    "determination_deadline_days": 60,
    "deemed_approval_risk": "Pending 60-day deemed approval legislation (not commenced) — monitor",
    "days_remaining": 23
  },
  "model_versions": {"reasoning": "qwen3-72b-instruct-2025-xx (rev 3)", "vision": "qwen3-vl-72b (rev 1)", "embeddings": "bge-m3"},
  "audit_ref": "audit://DA-2025-123/2026-07-01T03:12:00Z"
}
```

---

## 7. Rule language and NSW examples

### 7.1 Schema (YAML, JSON-Schema-validated)

```yaml
rule_id: <stable-id>
version: <int>
provision_ids: [<reg_provision.id> ...]     # the law the rule operationalises
applies_when:                                # applicability predicate over case attributes
  zone_in: [...]          # or zone_not_in
  use_class_in: [...]
  overlay_any_of: [...]   # e.g. EP&A overlay, VPO, flood, bushfire BAL
  lot_area_lt_m2: <n>     # arbitrary typed predicates
  not_complying_development: true
checks:                                  # all must pass for the rule to "pass"
  - name: <check-name>
    fact: <fact.key>
    op: lte | gte | eq | in | between | is_true
    param: <param-name>                  # resolved from provision.params
    # or: expression: "<python-safe expr over facts/params>"  (restricted, audited)
on_fail:
  classification: fail_hard | fail_mitigable | undetermined
  allow_flexibility: true | false        # check for an instrument flexibility provision first
  flexibility_provision_ids: [...]
  condition_curable: true | false
  officer_confirmation_required: true | false
  on_undetermined: request_info          # drives "request additional information"
```

Design notes: (i) a rule *operationalises* provisions — the provisions hold the law and their versioning; the rule holds the logic. A change to the instrument triggers a review of every rule citing it (the KB link makes this mechanical). (ii) `param` values come from the provision (so amending a height standard in the DCP changes the limit without touching rule logic). (iii) expressions are a *restricted* Python subset (no imports, no I/O) — evaluated, logged, and unit-tested; anything expressible as an op + param is preferred.

### 7.2 Worked NSW examples

**R1 — Use in zone (prohibition check).**
`provision_ids: [lep-2011-3.2-zoning-r2]`; `applies_when: {zone: R2, use_class: <from form>}`; check `use in permitted_or_exempt_uses` → `fail_hard`, `condition_curable: false`. Rationale: a use not permitted in the zone is the classic non-curable ground (subject to any specific LEP exemptions, which are provisions too).

**R2 — Height vs non-discretionary standard (with flexibility gate).**
`provision_ids: [dcp-2.1-height]`; params `{max_height_m: 12}`; `applies_when: {zone_in: [R2,R3], use_class_in: [2a,2b,2c], lot_area_lt_m2: 1000}`; check `building.max_height_npd_m lte max_height_m`; `on_fail: {classification: fail_hard, allow_flexibility: true, flexibility_provision_ids: [lep-4.3-cl2-flexibility], officer_confirmation_required: true}`. The evaluator: if the flexibility provision's stated grounds are engaged by the facts/reports, the finding becomes `fail_mitigable` (variation possible) rather than a hard refusal — mirroring 4.15(2)–(3) and the LEP's own flexibility clause.

**R3 — FSR / LDR.**
Facts: `building.gross_floor_area_m2` (sum of floor-plan areas from drawings/vector) and `lot.area_m2`; provision params `{max_fsr: 0.45, max_ldr: 1.25}`; check `gross_floor_area/lot_area lte max_fsr`. FSR/LDR are non-discretionary in most SILeP-style LEPs → `fail_hard` with flexibility gate.

**R4 — Setbacks.**
Facts: `setback.rear_m`, `setback.side_m` (vector-measured or vision-measured from site plan) vs DCP `{min_rear_m: 6, min_side_m: 3}`. Non-compliance is usually **not** curable by a condition on an already-drawn design → `fail_hard` unless the DCP permits a variation; where the design *could* be amended, the tool proposes the amendment as a **pre-construction condition** (plan resubmission) — the distinction between "curable by condition" and "curable by amendment" is part of the rule's `on_fail`.

**R5 — Parking.**
Facts: `car_spaces.provided` vs the DCP parking schedule resolved from `use_class + dwelling_count/vehicle assumption`; non-compliance → `fail_mitigable` only where the DCP or LEP allows alternatives (e.g. off-site, shared, transport-accessibility-based reduction); otherwise `fail_hard` (you cannot condition a built design into more spaces, but a pre-construction plan-amendment condition is proposed).

**R6 — Stormwater / water.**
SEPP (Water) 2020 + DCP: discharge must meet council's stormwater requirements; if the report is absent or non-compliant → `fail_mitigable` with a standard condition (e.g. "prior to commencement, a stormwater management plan meeting [DCP clause] shall be approved"); absence of the report itself → `undetermined` → *request additional information*.

**R7 — Flood hazard (SEPP (Resilience and Hazards) 2021).**
Facts: site within flood extent (from site plan / council data) and `building.min_floor_elev_m` vs the required flood level (e.g. 1:20 AEP + 0.5 m). Non-compliance → `fail_hard` for the affected area (cannot be conditioned away); the finding must identify *which* part of the development is non-compliant.

**R8 — Bushfire (BAL) area.**
Site within BPZ (site plan / BAL assessment report): check that the report exists, is current, and that design provisions (construction, access, water) match the BAL rating → typically `fail_mitigable` (conditions) where the report is incomplete, `fail_hard` where design does not meet the SEPP for the BAL zone.

**R9 — Heritage.**
Site/adjacent heritage item (LEP item or SHR) + development within curtilage: the report must assess significance and impact. No adequate assessment → `undetermined` (request information). Significant adverse impact not mitigated in the design → `fail_hard`; impact mitigated by design/plan changes → `fail_mitigable` with a heritage conservation condition. Where the item is of State significance, a **referral** is raised (Heritage Act 1977 / Ministerial pathway) rather than a local determination.

**R10 — Vegetation / biodiversity.**
Removal of protected vegetation (VPO, LEP protected species, BC Act offsets): if removal is proposed without a vegetation management plan / offset assessment → `fail_mitigable` with conditions (removal permit, offset); if the proposal contravenes a non-discretionary protection standard → `fail_hard`.

**R11 — BASIX (SEPP (Building Sustainability Index: BASIX) 2004, as updated).**
New/added residential dwellings (and alterations meeting the SEPP's thresholds) → a BASIX certificate must be provided or the energy proposal must meet BASIX targets. Missing/non-compliant → `fail_mitigable` with the standard BASIX condition. (The 2023 BASIX update raises targets and adds solar/EV-readiness requirements for new residential — loaded as provision params, not hard-coded.)

**R12 — Subdivision (mandatory-refusal rule, 4.16(2)).**
For subdivision DAs: lot size, access, drainage and any LEP subdivision standards → any resulting contravention of the Act/instrument/regulation triggers the **mandatory refusal** rule. This is the one decision the Act takes out of the council's discretion — the tool must be exact here, and these rules carry the strictest test coverage.

**R13 — Traffic / road access (Roads Act 1993; TfNSW requirements; DCP).**
Access to a declared road requires compliance (crossover approval, sight triangles, on-site parking). Non-compliance → `fail_mitigable` where curable by design/condition; access not achievable → `fail_hard`.

**R14 — Noise (SEPP (Noise) 1997; DCP).**
Report-based: predicted levels at sensitive receptors vs limits → `fail_mitigable` with acoustic conditions (mitigation, hours of operation) where achievable; otherwise `fail_hard`.

**R15 — Amenity / outlook / visual impact (DCP; SEPP (Visual Amenity) 2013).**
*No deterministic check* — this is the LLM adjudication track (§8): wall heights and fence heights near neighbours, built form against DCP design objectives, visual intrusion into protected views. Output findings with citations and confidence; typical outcome is `fail_mitigable` with design-refinement conditions.

**R16 — NCC / fire (informational + conditions).**
Not a DA-determination ground in most cases, but the tool flags: buildings above thresholds requiring fire design, inadequate fire access on the plan, egress concerns — and generates the standard fire-related conditions where triggered (BCA accreditation note: 4.15(4) prevents refusal on accredited products).

**R17 — Referral triggers (not "failures" — routing rules).**
State significant development (Division 4.7, 4.36 et seq.), integrated development (Division 4.8), designated development (4.10), EPBC referrable actions (EPBC Act 1999 — e.g. listed species habitat, Ramsar), State heritage. Each trigger is a rule with `on_fail: classification: referral` that routes the case and annotates the report with the statutory basis.

---

## 8. LLM adjudication design

### 8.1 When the LLM adjudicates

Judgment-based 4.15(1) considerations that cannot be reduced to a threshold test: amenity impacts, character and built form, outlook and visual impact, noise (interpretation of modelling), heritage significance, ecological impacts, traffic (beyond counts — access design adequacy), and the **free-text answers and submissions** (interpretation, contradiction detection).

### 8.2 The adjudication call

For each issue, the model receives:
1. the **issue brief** (what to decide, the 4.15(1) consideration it maps to);
2. the **retrieved provisions** — top-k from the hybrid RAG search (provision text + instrument + version + clause path); the model is told: *you may rely only on the provisions given*;
3. the **extracted facts** relevant to the issue (with their evidence pointers);
4. the **relevant report excerpts** (retrieved by embedding, not whole reports);
5. for submissions: the **objection text** and the facts it challenges.

It must return (guided-decoded JSON): `finding` (pass / fail / concern), `severity` (hard / mitigable / note), `citations[]` (each: `instrument`, `clause`, `quote` — a verbatim span), `evidence[]` (each: document, page, region/quote), `reasoning` (short, in plain language a planner would say), `confidence` (0–1), `proposed_condition` (if mitigable), `counter_arguments` (what an objector/appellant would say — used to stress-test the finding).

### 8.3 Two-pass self-check

A second, cheap call reviews the first pass' output against the retrieved provisions and the evidence: "Is every citation present verbatim in the provided text? Does the reasoning follow from the facts?" Disagreement or unverifiable citation → the finding is downgraded in confidence and flagged to the officer. This is inexpensive insurance against the single most dangerous failure mode (a confident, uncited finding).

### 8.4 Citation verification (the anti-hallucination core)

- **Retrieval-bound reasoning.** The model only ever sees provisions supplied by the RAG layer. It cannot cite law from memory.
- **Verbatim check.** Every `quote` in a citation is string-matched (normalised) against the provision text in the KB; a match is required for `verified: true`. Non-verbatim "citations" are rejected at the interface — the finding cannot be marked verified.
- **Clause-exists check.** The cited clause must exist in the instrument version in force on the lodgement date (not a repealed version).
- **Evidence-exists check.** The cited evidence (page/region/quote) must exist in the page manifest; for drawing facts, the region box is shown to the officer in the UI with the underlying image.
- A finding whose citation or evidence fails verification is **automatically downgraded** to `undetermined`/flagged — the system fails toward human review, never toward a confident answer.

### 8.5 Confidence and disagreement

Confidence combines: the model's stated confidence, the two-pass agreement, the extraction confidences of the facts used, and (for rule findings) whether cross-checks agreed. A global **confidence gate** (§9.6) routes low-confidence material findings to the officer. Where two adjudications (different issue, same underlying fact) conflict, the conflict is surfaced, not silently resolved.

### 8.6 What the LLM is never asked to do

- Invent facts not in the package (no "assume a typical setback").
- Cite a provision not in the retrieval set.
- Make the final determination (it outputs recommendations; §9).
- See data from any other case (no cross-case context — privacy and contamination control).

---

## 9. Decision logic

### 9.1 Finding taxonomy

| Status | Meaning | Consequence |
|---|---|---|
| `pass` | Requirement met | None (recorded in the compliance matrix) |
| `fail_hard` | Non-compliance that cannot be cured by a condition, and no applicable flexibility/discretion on the materials | Drives a **refuse** recommendation (or partial consent, §9.3) |
| `fail_mitigable` | Non-compliance or a 4.15 concern that *can* be cured by a condition (or plan amendment before construction) | Drives **conditional approval** |
| `undetermined` | Material 4.15 matter that cannot be assessed on the materials (e.g. missing report) | Drives **request additional information** (not a determination; the statutory clock is affected — the tool flags this) |
| `n_a` | Provision not applicable (zone/use/overlay) | Recorded for completeness of the matrix |

### 9.2 Aggregation to a recommendation

| Situation (after all findings) | Recommendation |
|---|---|
| Any `referral` trigger | **Refer** (to the relevant authority) — the tool's assessment continues as support to the referral; the local authority does not determine |
| Any `undetermined` on a material matter | **Request additional information** (specify exactly what, citing the 4.15(1) matter it bears on) — with a note on statutory timing effects |
| Any `fail_hard` (flexibility not engaged, officer confirmation complete) | **Refuse** — with reasons per finding |
| No `fail_hard`; one or more `fail_mitigable` with valid conditions | **Conditional approval** |
| All `pass` (standard conditions only) | **Approve** |
| Mixed hard + mitigable, or hard fail confined to a separable part of the development | **Flag to officer**: refuse, or **partial consent** under 4.16(4) (consent for the compliant part/aspect), or defer-commencement under 4.16(3) — the tool presents the options with analysis; the choice is the officer's |
| Any material finding below the confidence gate | **Draft — officer review required** (all of the above, but marked non-final) |

The 4.15(2)–(3) non-discretionary logic is applied *inside* the aggregation: where the DA **complies** with a non-discretionary standard, the tool must not produce a refusal ground or a more-onerous condition on that basis (it is blocked at the output level, not merely by convention); where it **does not comply**, the flexibility provision (if any and engaged) is checked before the finding is classified `fail_hard`.

### 9.3 Conditions

Each condition is generated as a first-class object (§6) with: **text** (from the council's standard-conditions template where one fits; bespoke otherwise), **stage** (pre-construction / construction / ongoing / deferred-commencement), **legal basis** (the provision it implements + the 4.15(1) matter it relates to — the 4.17 relevance test, recorded explicitly), **finding links** (what problem it solves), and **enforceability** (who must comply, by when, verifiable how).

Checks applied to every condition before it may appear in a recommendation:
1. It relates to a 4.15(1) matter of relevance (4.17(1)(a)) — the tool states which.
2. It is capable of compliance (no unachievable precision; deadlines are achievable).
3. It is not more onerous than a non-discretionary standard the DA complies with (4.15(2)(c)).
4. It is not duplicative of a standard that already binds.
5. Deferred-commencement conditions (4.16(3)) are flagged as creating a consent that does not operate — a structurally different instrument, requiring explicit officer awareness.

### 9.4 Referrals

Referral rules (§7 R17) produce referral objects with the statutory trigger, the target authority, and the required documentation. The tool tracks referral status against the determination clock (4.16(6)–(7): a consent authority must not determine while a Minister-requested IPC review is pending; the tool hard-blocks a "determine now" action in that state).

### 9.5 Statutory timelines

The tool tracks: lodgement date, notification/submission period (designated development, Schedule 1), the determination deadline (60 days for most DAs under current provisions; **watch-item**: the 60-day *deemed approval* bill 2025 — if it commences while a case is live, the clock semantics change and the tool re-baselines with a prominent warning), lapsing (4.53), and the 28-day effect delay for designated development (4.20). Deemed-approval risk is a standing field in the decision JSON.

### 9.6 Confidence gate and human-in-the-loop

- **Automatic officer review is required when:** any finding on a non-discretionary standard is below confidence 0.9; any drawing-derived fact used in a hard-fail was not cross-check-consistent; any citation failed two-pass self-check; any conflict exists between adjudications; a mandatory-refusal rule (4.16(2)) fired.
- The officer workflow: (1) confirm/amend **facts** (the UI shows the evidence image/quote behind each number — a planner glances at the section drawing to confirm 14.2 m, it takes seconds); (2) accept/override each **finding** (override requires a note — the note becomes evaluation data); (3) edit **conditions** (template-aware); (4) review the **draft reasons** and the recommendation; (5) **sign** — which writes the `determination` record (a record type only humans can create).
- After sign-off, the tool's recommendation is frozen into the audit trail alongside the officer's final determination — the delta between the two is the core measurement of the system's accuracy (§11).

---

## 10. Output specification

### 10.1 Machine-readable

The `decision_recommendation` JSON of §6.4 is the system of record for the tool's output: stable schema, versioned, API-accessible, and the single source from which all human documents are rendered. It includes the full findings array (with citations and evidence), conditions, referrals, statutory-timelines block, model/prompt versions, and the audit reference.

### 10.2 Human report — "Determination Support Report"

Structure (Jinja2 → WeasyPrint PDF; DOCX variant for committee packs):

1. **Case summary** — site, lot, zone, use, applicant, lodgement date, category.
2. **Description of the development** (from form + drawings).
3. **Compliance matrix** — one row per applicable provision: *provision (instrument, clause, version) | requirement | finding status | evidence (doc/page) | comment*. This is the heart of the document; the officer and any reviewer should be able to audit the whole assessment from this table.
4. **Issues and analysis** — the fail/undetermined findings in narrative, each with its reasoning, citations, and evidence figures (drawing extracts embedded).
5. **Submissions** — each objection, the consideration it engages (4.15(1)), and the response (mapped to findings/reasons).
6. **Recommended determination** — approve / conditional / refuse / refer / request-information, with confidence and review status.
7. **Proposed conditions** — numbered, staged, each with its basis (provision + 4.17 matter).
8. **Draft reasons for determination** — structured on the 4.15(1) matters actually in play; written to stand as the reasons given under the Act if adopted (they are a *draft*; the officer owns the final reasons).
9. **Referrals and consultations** — with status.
10. **Statutory timeline** — deadline, deemed-approval watch-item, lapsing.
11. **Appendices** — evidence index (every cited doc/page/figure); extraction log summary (which facts were vision-measured vs form-stated); audit reference and model/prompt versions.

### 10.3 Notification

The final determination (human-signed) feeds the council's existing notification workflow (4.18; NSW planning portal registration per 4.20) — the tool does not notify; it hands over a packet formatted for the council's process.

---

## 11. Human-in-the-loop, audit and evaluation

### 11.1 Audit trail

Every LLM call, rule evaluation, fact extraction, officer action and sign-off is an immutable `audit_event` (§6): actor, timestamp, input/output hashes, model id, prompt version. The determination record is append-only; amendments after sign-off create new versions (the original is never altered — consistent with records management obligations, §13).

### 11.2 Evaluation harness

**Golden set — 30-case bootstrap, 20 calibration + 10 sealed holdout.** A set of 30 historical DAs from the LGA, each with its actual determination (outcome, plus conditions and grounds where available), anonymised before it enters the system.

- **20 calibration cases** — used throughout the build: validating extraction accuracy, tuning rules and thresholds (including the §9.6 confidence gate), revising prompts, and as the mandatory regression set before any model/prompt change ships. This is *calibration, not model training* — at this scale the hybrid engine has no learned parameters: the deterministic rules are fixed against these cases (test-driven, not statistically fitted), and the LLM layer is a pinned foundation model whose prompts get revised. Fine-tuning the local model (the §5.6 option) would need a few hundred labelled findings — that is the growth step below, not the bootstrap step.
- **10 holdout cases** — sealed until the end of Phase 3, then run **once** as a go/no-go gate and never used to tune anything. Honest framing for n = 10: a pooled agreement number is reference-only (a 95% confidence interval on 10 cases is roughly ±30 points). The real signal is the *per-case* readout — which cases disagree, on which findings, and whether each disagreement traces to a rule/prompt defect (fix on the calibration set, re-run) or to genuinely novel facts (accepted as a known limit).

**Diversity means stratification, not randomness.** Selection uses the Online DA Data API (Appendix C, source 1) for its stratification fields (DevelopmentType, dwelling/storey counts, SubdivisionProposedFlag, EPIVariationProposedFlag, VPAStatus, ApplicationStatus) and the determination registers/notices for outcome labels. Target mix (bend to the LGA's actual base rates, but keep every class present in *both* splits where possible):

| Axis | Target across the 30 |
|---|---|
| Development class | New residential (~6), addition/alteration (~5), subdivision (~4), small commercial / change of use (~4), large or complex (~4), other (~3) |
| Outcome | ≥ 10 approved, ≥ 10 conditional, ≥ 5 refused — with each outcome class present in the holdout (e.g. 3/3/4) |
| Standard variation | ≥ 6 with a development-standard variation proposed; ≥ 3 of those approved |
| Submissions | ≥ 8 with at least one public submission/objection |
| Overlays / hazards | ≥ 4 on flood, bushfire, heritage or vegetation-protection land |
| Document form | ≥ 6 with scanned (raster) drawings, to exercise the vision path; the rest born-digital |
| Foreshore / waterways | ≥ 3 DAs on SREP / Sydney Harbour Foreshores & Waterways DCP area (Manly–Pittwater foreshore) — exercises the state-instrument-over-local-instrument override reasoning (Appendix D) |
| Former-area span | ≥ 8 per former LGA area (Manly / Pittwater / Warringah) — the three coexisting LEPs differ in structure, so the area→instrument mapping must be tested across all three |
| Transition generation | ≥ 5 DAs determined after the draft Northern Beaches LEP went to exhibition (draft-consideration reasoning) and ≥ 5 from before — both sides of the instrument version boundary |

**Split discipline.** (i) No case ever moves between splits; (ii) the holdout is consumed at most once per phase exit and re-sealed afterwards — a *new* holdout must be drawn from fresh cases whenever the set grows; (iii) any change motivated by a holdout observation is validated on the calibration set before it ships. **Growth path:** the public sources (Appendix C) extend the set toward 100–200 cases, at which point a formal 80/20 split with meaningful confidence intervals becomes the benchmark, and fine-tuning (if the error patterns justify it) becomes feasible.

**Metrics:**
- **Outcome agreement** — recommendation vs actual determination (approve/conditional/refuse), and *with reasons* (does the tool's reasoning track the recorded reasons?).
- **Citation precision** — for a sample of findings, human-annotated: does the cited provision actually support the finding? Target: ≥ 95% of verified citations.
- **Fact accuracy** — sample of extracted numeric facts vs human reading of the drawings; target: ≥ 95% exact, ≥ 99% within engineering tolerance, with the discrepancy rate *reported per source method* (form vs vector vs vision).
- **Condition acceptance** — of conditions proposed by the tool, what fraction does the officer adopt unedited / amended / reject?
- **Override rate** — findings overridden by officers, by type — the main leading indicator of model/prompt problems.
- **Runtime and cost** — minutes and tokens per DA, by complexity class.

**Shadow mode.** For the first N live DAs, the tool runs in parallel and its recommendations are compared to the officers' actual determinations *without influencing them*. This measures real-world agreement before any case is touched by the tool's output in a visible way.

**Continuous loop.** Every officer override/annotation is labelled data: it feeds the golden set, triggers targeted prompt revision, and (if a pattern emerges) fine-tuning of the local model. Model or prompt changes require a full golden-set regression run before deployment — the "reproducible" principle (§1.4) is enforced by process, not hope.

---

## 12. Legal, ethical and governance considerations

| Area | Position |
|---|---|
| **Advisory only** | The tool never determines. The determination record is human-created. Outputs are labelled "recommendation — decision support". Delegation rules (Local Government Act 2009; council delegation policy) decide who may sign; the tool routes accordingly. |
| **Natural justice** | Applicants/objectors are entitled to a fair process and to reasons. The tool drafts reasons; humans adopt them. No tool output goes to a third party without human review. Where the tool's analysis influences a response to a submission, that response is officer-authored. |
| **Conditions legality** | Every condition carries its recorded 4.17 relevance basis; the more-onerous-than-standard prohibition (4.15(2)(c)) is an output-level block. A condition without a legal basis cannot be rendered. |
| **Privacy** | DA packages contain personal information (NSW PPIP Act 1998; Commonwealth Privacy Act where applicable). All processing is on-prem (§5.6); the cloud escalation tier (if ever enabled) transmits minimised extracts only, under a signed data-processing arrangement and governance approval; no case data leaves the site by default. |
| **Records** | Everything produced (package, extractions, findings, recommendation, determination, audit trail) is part of the DA file under the Government Records Act 1997. Object-locked storage, append-only records, and retention per the council's records schedule. |
| **Transparency / AI disclosure** | The determination support report states that it was produced with AI assistance (model versions recorded). Whether reasons issued to objectors should disclose AI drafting is a policy decision for the council (recommended: disclose in the file, use human-authored language in issued reasons). |
| **Bias and fairness** | The golden set is stratified by DA type and site character; agreement metrics are reported per stratum so systematic bias (e.g. against a particular use class or neighbourhood profile) is visible. The officer-override log is the same instrument in live operation. |
| **Liability and governance** | The tool is a decision-support system within the council's existing planning functions; it does not create a new decision-maker. Professional indemnity, the council's ICT/technology policy, and a documented governance approval (head of planning + CEO line) precede go-live. The tool is not legal advice; officers retain professional judgment and, where needed, seek legal advice. |
| **Legislative change** | The legislative watcher (§2.2) plus versioned KB means an amendment is a controlled data change with a regression run — not a code emergency. |

---

## 13. Deployment and security

- **Placement.** On-prem in the council's data centre or a sovereign-government cloud region — the entire stack (vLLM on 1–2 GPUs, pipeline service, Postgres, MinIO, UI) fits a small footprint and can be **air-gapped** if required (all components are open-source; no external API is mandatory).
- **Hardware (indicative).** GPU node: 1× A100-80GB (or 2× L40S) for the 70B-class reasoning + 72B-class vision models at quantised precision; CPU node: 8–16 cores for pipeline, Postgres, MinIO, UI. Pilot minimum: one 2×24GB-GPU workstation running the 32B dense model.
- **Security.** Council SSO (OIDC) for the UI; role-based access (officer / head-of-planning / records); per-case access lists; audit log on every access to case material; network segmentation between GPU zone and office LAN; MinIO object lock for originals; TLS everywhere; secrets in the council's existing vault.
- **Operational.** The pipeline runs as a supervised service with stage-level checkpoints (§5.9); failed stages surface in the UI with retry; model deployments are versioned artefacts (weights + config + prompt bundle) that the deployment pipeline pins.

---

## 14. Phased roadmap

| Phase | Scope | Exit criteria | Indicative duration |
|---|---|---|---|
| **0 — Foundations** | Environment (Postgres, MinIO, vLLM, model serving); DA package ingestion; page classification; text + free-text extraction; fact schema v1 | On 5 sample DAs: ≥ 90% of form-stated facts extracted correctly; page manifest complete | 2–3 wks |
| **1 — Regulatory KB + rules** | Load LEP/DCP/SEPPs (with current-compilation renumbering and versioning); provision schema; build the first ~20 rules (R1–R13, §7); deterministic evaluator + compliance matrix output | Rules unit-tested; on sample DAs the matrix matches officer expectations on a test panel | 4–6 wks |
| **2 — Adjudication + synthesis** | Vision drawing pipeline; report summarisation; RAG; adjudication calls with citation verification; decision aggregation; condition drafting; decision JSON + report v1 | On the **20-case calibration set**: outcome agreement ≥ 80%, citation precision ≥ 90%, conditions ≥ 50% adopted unedited | 4–6 wks |
| **3 — Officer workflow + shadow mode** | Streamlit (then Next.js) review UI; sign-off flow; audit trail; golden-set regression harness; shadow run on live DAs | 20+ live DAs assessed in shadow with no errors reaching a determination; officer time per review case ≤ 15 min; **one-shot run of the 10-case sealed holdout** (go/no-go; then re-sealed) | 4–6 wks |
| **4 — Assistive operation** | Tool output presented to officers on live DAs (advisory); override feedback loop; legislative watcher live; deemed-approval watch-item active; production UI | 90 days of assisted operation with measured metrics at targets (§11); governance review | ongoing |

The build is deliberately ordered so that **every layer earns its place against the golden set before the next is built** — no phase depends on an unmeasured assumption about model capability.

---

## 15. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Hallucinated regulation** (finding cites a clause that doesn't say that) | Medium | Severe | Retrieval-bound reasoning; verbatim citation verification; clause-exists check; two-pass self-check; fail-toward-human (§8.4) |
| **Drawing mis-read** (height/setback off by 1–2 m on a scanned plan) | Medium | Severe (wrong hard-fail) | Cross-check form vs drawings vs multiple pages; confidence-gated officer confirmation before any hard-fail recommendation; vector path where available |
| **Model version drift** (behaviour changes between runs) | Medium | High | Pinned model + prompt versions; immutable call log; full re-run reproducibility; regression gate on any change |
| **Legislative change mid-life** (renumbering again; deemed approval commences) | High (this area of law is actively amending) | Medium | Versioned KB with commenced/pending status; legislative watcher; timeline re-baselining with warnings (§2.2, §9.5) |
| **Automation bias** (officers rubber-stamp) | Medium | Severe | UI presents evidence prominently; low-confidence items *require* a reasoned note to accept; override analytics reported to governance; periodic "tool-off" audit of a sample of determinations |
| **Over-reliance on free-text answers** (applicant representations taken as fact) | Medium | Medium | Representations are classified separately from verified facts; contradictions between form claims, reports and drawings are flagged, not resolved silently |
| **Data privacy breach** (DA data egresses) | Low (design) | Severe | On-prem default; cloud tier off by default, minimised-data, governed; audit of all egress |
| **Golden set too small / unrepresentative** (30 cases) | Medium | Medium (weak calibration, noisy benchmark) | 30-case stratified protocol with a sealed 10-case holdout (§11.2): per-case readout instead of pooled percentages; shadow mode early as live data; grow to 100–200 via public sources (Appendix C) before making statistical claims or fine-tuning |
| **Volume surprise** (DA volume exceeds pilot assumptions) | Low | Medium | Temporal scale path pre-designed (§5.9); horizontal model endpoints |
| **Council capacity to maintain** (rules/KB need upkeep) | Medium | Medium | KB changes are data, not code; rule amendments are YAML diffs with officer sign-off; legislative watcher automates detection; maintenance burden estimated and agreed in the governance approval |

---

## 16. What we need from the council

To move from this design to build, the following are required:

1. **Instruments (Northern Beaches — per Appendix D)** — current consolidated PDFs: **Manly LEP 2013** + Manly DCP 2013 + "Manly Planning Rules and Associated Documents"; **Pittwater LEP 2014** + Pittwater 21 DCP + appendices (all volumes); **Warringah LEP 2011** + Warringah DCP 2011, **plus** Warringah LEP 2000/DCP 2000 (still applying to "deferred matter" land); **SREP (Sydney Harbour Catchment) 2005** + **Sydney Harbour Foreshores and Waterways Area DCP 2005** (Planning NSW); Warriewood Valley Water Management Specification 2001; the exhibition copy of the **draft Northern Beaches LEP/DCP**; the council's confirmed list of applicable SEPPs and council policies (e.g. the Water Management for Development Policy); and the gazette dates of the latest amendment to each instrument.
2. **Standard-conditions library** — the council's existing template conditions (the tool should reuse the council's own wording wherever possible).
3. **Sample DA packages (the golden set)** — **30 historical DAs** from the LGA (20 calibration + 10 sealed holdout), stratified per §11.2 (development class × outcome × variation × submissions × overlays × document form), each with its full PDF package **and the actual determination** (outcome + conditions + grounds where available). The council's own archive is the preferred source (richest "human evaluation"); where a stratum isn't covered there, the public sources (Appendix C) fill the gap. Anonymisation guidance to be agreed.
4. **Delegation and process policy** — who may determine what, the council's notification workflow, and its records schedule for DA files.
5. **IT environment** — data-centre/cloud options, GPU availability (or procurement path), SSO details, network/air-gap constraints.
6. **Volume and mix** — DAs per year by category, and the current officer time per determination (the baseline for the benefit case).
7. **Policy decisions** — the council's position on: AI disclosure in issued reasons; the cloud escalation tier (yes/no/conditions); and the governance approval line for go-live.

## Appendix A — Glossary

| Term | Meaning |
|---|---|
| **DA** | Development application — the statutory application for development consent under the EP&A Act |
| **Consent authority** | The body that determines the DA (council, delegated officer, Minister, or other as designated) |
| **LEP** | Local Environment Plan — the LGA's environmental planning instrument (zoning, standards, overlays) |
| **DCP** | Development Control Plan — guidance/standards instrument implementing the LEP |
| **SEPP** | State Environmental Planning Policy — state-wide planning instrument |
| **Non-discretionary standard** | A development standard designated as such in the instrument; compliance forecloses refusal on that ground (4.15(2)) |
| **Flexibility provision** | An instrument provision allowing variation from a standard on stated grounds (e.g. demonstrated design conflict) |
| **CCD** | Complying development certificate — fast-track certification for development meeting prescribed standards (Division 4.5) |
| **State significant / designated development** | Categories triggering referral/Ministerial pathways (Divisions 4.7, 4.10) |
| **IPC** | Independent Planning Commission — NSW's planning review body (2025 reforms) |
| **RAG** | Retrieval-augmented generation — supplying the model with retrieved text it may rely on |
| **Golden set** | The 30-case labelled set (20 calibration + 10 sealed holdout) used to tune and benchmark the system (§11.2) |
| **Shadow mode** | Running the tool on live DAs without its output influencing the decision, to measure agreement |

## Appendix B — Key current EP&A Act provisions

Verified against the current compilation (in force from 1 November 2025; accessed 12 November 2025; NSW Parliament, *Environmental Planning and Assessment Act 1979* No 203, available at legislation.nsw.gov.au and mirrored at faolex.fao.org). The PCO cross-references ("cf previous s X") are part of the text and are stored in the KB.

| Current | Former | Use in this design |
|---|---|---|
| 4.1–4.3 (Division 4.1) | — | Exempt / consent-required / prohibited classification (rule R1) |
| 4.10 | — | Designated development (notification, submission period, 28-day effect delay) |
| 4.12 | — | Application content (drives extraction schema) |
| 4.13 | — | Consultation and concurrence (agencies to consult — referral routing) |
| 4.15(1)(a)–(e) | s 79C | The evaluation considerations — the backbone of findings, reasons and conditions |
| 4.15(2)–(3) | s 79C | Non-discretionary standard logic (comply → no refusal/no more-onerous condition; non-comply → discretion + flexibility) |
| 4.15(3A) | s 79C | DCP standards: compliance limits, non-compliance requires flexibility/alternative solutions |
| 4.15(4) | s 79C | BCA-accredited products — refusal bar |
| 4.16(1)–(2) | s 80 | Grant/refuse; **mandatory refusal** of subdivisions that would contravene |
| 4.16(3) | s 80 | Deferred-commencement consent |
| 4.16(4)–(5) | s 80 | Total or **partial consent** (basis of the "partial approval" option) |
| 4.16(6)–(7) | s 80 | IPC review — determination must wait |
| 4.17 | s 80A | **Conditions** — relevance test to 4.15(1) matters (the legal basis every condition must record) |
| 4.18 | s 81 | Post-determination notification |
| 4.20 | s 83 | Date consent has effect (NSW planning portal; 28-day designated-development delay) |
| Division 4.4 | s 83A/83B | Concept DAs (flag as alternative pathway) |
| Division 4.5 | — | Complying development (CCD) — flag where the DA could have proceeded as a CCD |
| Division 4.7 | s 89C et seq. | State significant development — referral pathway |
| Division 4.8 | — | Integrated development — approval-body coordination |
| Division 4.9 | — | Lapsing (4.53), modification (4.55), revocation (4.57) — timeline module |
| Part 5 (5.5 et seq.) | — | EIA duty — triggers for larger/impactful DAs |

**Pending amendments on the status page of that compilation (must be tracked in the KB):** 24-Hour Economy Legislation Amendment (Vibrancy Reforms) Act 2024 No 76 (not commenced); Environmental Planning and Assessment Amendment Act 2025 No 24 (partially not commenced); EP&A Amendment (60 Day Deemed Approval) Bill 2025 (non-government); EP&A Amendment (Planning System Reforms) Bill 2025.

**Other instruments to load (per LGA — for Northern Beaches, Appendix D):** EP&A Regulation 2021; the LGA instrument stack; SEPP (Resilience and Hazards) 2021; SEPP (Biodiversity and Conservation) 2021; SEPP (Heritage) 2021; SEPP (Visual Amenity) 2013; SEPP (Noise) 1997 (as amended); SEPP (Water) 2020; SEPP (Building Sustainability Index: BASIX) 2004 (2023 update); SEPP (Coastal Zone) 2021; EPBC Act 1999 (referral triggers); Heritage Act 1977; Biodiversity Conservation Act 2016; Roads Act 1993; Local Government Act 2009 (delegation); NCC (referenced at building stage).

---

## Appendix C — Public data sources for building a golden set (NSW)

*Added 2026-07: in response to the question of whether a dataset of DAs with human evaluations exists publicly. Short answer: no single off-the-shelf "golden set" — but four public sources combine into one, and the council's own archive (§16) fills the rest.*

| # | Source | What it gives | Gaps | Access |
|---|---|---|---|---|
| 1 | **NSW Planning Portal — Online DA Data API** (Open Data, CC-BY; updated daily; all DAs lodged on the portal since 10/12/2018, complete statewide coverage from 01/07/2021 when councils were mandated to use it) | Structured record per DA: portal application number (PAN-xxx), full address (with lot/plan/section + X/Y coordinates), council, development type(s), dwelling count, storeys, subdivision flag/type/lot count, **EPI variation proposed flag**, **variation approved flag**, VPA flag/status, SIC flag, lodgement/submission/determination dates, determination authority, exhibition dates, estimated cost, application status (`Determined`, `Withdrawn`, `Pending Court Appeal`, …) | No grant-vs-refuse label in the status field (an outcome bucket, not the outcome itself); no reasons; no documents; "Rejected" appears to mean rejected at lodgement, not refused consent | Request via the portal's **Data Broker** (email); data dictionary v2.0 published |
| 2 | **NSW Planning Portal case pages** (local DA search; state significant development notices) | For *notified* DAs: the public notice, the lodged documents, public **submissions/objections**, and after determination the **notice of determination with reasons and conditions** (published within 14 days of determination). The only place where a *full package and the human evaluation of it* coexist publicly for the same case | Not bulk-downloadable — case-by-case; only notified categories (designated, state significant, and some local); privacy — packages contain personal information, use requires care and anonymisation for any secondary use | Public website; a script can harvest a stratified sample case-by-case |
| 3 | **Council determination registers** | Most NSW councils publish weekly/monthly registers of determinations (granted / granted with conditions / refused), frequently with links to **reasons for determination** PDFs (e.g. City of Sydney's public development-application search). The best source of *local-scale* outcomes + reasons, since most local DAs are never exhibited on the portal | Formats vary per council; requires a per-council harvester; some reasons are terse | Public website (per council) |
| 4 | **Land and Environment Court (LEC) decisions** (planning appeals) | Full judicial reasons on contested determinations — the highest-quality public text on how s 4.15 matters are actually weighed and how reasons are challenged on appeal. Ideal for evaluating the *reasoning layer* (citation quality, argument structure, failure modes) | Selection bias: contested cases only (over-represents refusals and hard amenity/height/heritage disputes); not a distribution of ordinary local DAs | Public (lec.nsw.gov.au/decisions) |

**Cross-jurisdictional (pipeline development only — different legislation, do not calibrate NSW rule logic against these):** Brisbane City Council open data (development applications), City of Melbourne open data (development permits), and scraped UK local-authority decision registers used in academic work. These are cheap, large, and structured — useful for building and stress-testing the ingestion/extraction machinery in Phase 0, but their outcomes reflect Qld/Vic/UK planning law.

**Assembly plan for the golden set.** Use source 1 (Online DA Data API) as the structured *spine*: it stratifies the population (council × development type × subdivision × variation-proposed × outcome status × dates) so the sample is designable rather than haphazard. Then, for a stratified sample (~100–200 DAs per council), pull the case page (source 2) where notified — package, submissions, determination notice — and the council register (source 3) for the rest, attaching reasons where available. Source 4 (LEC decisions) is a separate *reasoning-quality* set, not part of the outcome benchmark. Anonymise PII before the set enters the system (§12). What this public assembly *cannot* provide, and why the council's own archive (§16, item 3) still matters: complete packages for non-notified local DAs (often only the determination notice is public), the council's own assessment reports (the "human evaluation" in the richest sense), and pre-2019 history.

---

## Appendix D — Northern Beaches LGA: instrument stack and transition state (verified July 2026)

*Verified against the council's planning-controls and development-applications pages and the NSW Legislation register. Instrument names and links are verified; **applicability of individual state instruments to particular land (e.g. water-supply areas, airport noise contours) is to be confirmed with the council before KB load.** The LGA is an unusually good stress test for this design: three coexisting LEPs, a deferred-matter trap, a state SEPP/DCP pair overriding local controls on the foreshore, and a fresh draft LEP/DCP mid-transition.*

**Current stack (three former-LGA patchwork + state instruments):**

| Area (former LGA) | LEP | DCP | Notes |
|---|---|---|---|
| Former Manly (Manly, Freshwater, Dee Why, Narrabeen, Collaroy) | Manly LEP 2013 | Manly DCP 2013 + "Manly Planning Rules and Associated Documents" | **SREP (Sydney Harbour Catchment) 2005** (a Regional Environmental Plan, not a SEPP) plus the **Sydney Harbour Foreshores and Waterways Area DCP 2005** (Planning NSW) apply to the harbour foreshore/waterways — a state pair that overrides the local LEP/DCP there. Heritage-dense (LEP Schedule 5 items). |
| Former Pittwater (Bridgemain, Elanora, Mungangata, Warratah, Brookvale) | Pittwater LEP 2014 | "Pittwater 21 DCP" + appendices (multi-volume) | Council publishes a **Development Variation Register** (DAs determined with a standard variation under the LEP's variation clause) — a directly harvestable public source for the variation stratum. |
| Former Warringah (St Ives and hinterland, Warriewood) | Warringah LEP 2011 | Warringah DCP 2011 (read together with the LEP) | **Warringah LEP 2000 still applies to "deferred matter" land** — a state-deferred carve-out from the 2011 LEP; the KB therefore needs an *area→instrument* map, not just an instrument list. **Warriewood Valley Water Management Specification 2001** is a local water instrument. |

**Transition state (critical for the KB).** The consolidated **draft Northern Beaches LEP and DCP are on public exhibition 20 July – 30 August 2026**. The council's stated position: the draft LEP **must be considered** in DA assessment alongside the existing Manly/Pittwater/Warringah controls, with weight depending on the nature of the proposal and how advanced the draft is; the **draft DCP is not considered**. Consequences for the tool:

- The KB carries **four coexisting LEP generations**. The draft LEP is a version node in a *"considered but not in force"* state: the rule engine treats it as advisory context, findings citing it are tagged accordingly, and it must never be cited as law in the reasons.
- A DA lodged on 1 September 2026 may face different instruments than one lodged on 31 August 2026 → the lodgement-date filter (§5.7) plus a watch item on the draft's progress (exhibition → modifications → notification); notification is the next version boundary, and the old three-LEP set then moves to "historical" state for pre-notification DAs.
- The golden set must span **both sides** of the transition (stratum row, §11.2).

**State instruments with local anchors (applicability TBC per parcel):** SEPP (Resilience and Hazards) 2021 — the council's Flood Hazard Map (Pittwater basin) and the RFS-certified Northern Beaches Bush Fire Prone Land Map (certified 2020); SEPP (Biodiversity and Conservation) 2021 — hinterland reserves; SEPP (Heritage) 2021; SEPP (Visual Amenity) 2013 — headland/foreshore views; SEPP (Coastal Zone) 2021; SEPP (Water) 2020 — Pittwater water-supply area (TBC); SEPP (BASIX) 2004 (2023 update). **TBC:** possible Sydney Airport noise-contour overlap over the Pittwater/St Ives area — not listed on the council's controls page; confirm before loading a noise overlay.

**Volume and shape (verify against the council's own Development Activity Reports):** a third-party portal-data estimate of ~4,700 DAs/yr since 2021. A high share of residential A&A on older, character/heritage stock (since 1 Jan 2026, Class 1 A&A lodgements must include a Concept Stormwater Plan + engineer certification under the Water Management for Development Policy — a **new document type for the intake layer**); subdivision pressure on small lots; a flow of multi-unit/apartment DAs (new rail line context); SSDs occur in the LGA (council publishes a list).

**Public harvest entry points (all confirmed on the council's site):** (1) application search — per-case pages with lodged documents for notified DAs; (2) **Development consents** — monthly approved-consent notices (the local determination register); (3) **Development variation register**; (4) **Development Activity Reports** — the volume/mix baseline for the stratum targets; (5) the SSD list. The NSW Planning Portal local-DA search covers the same cases with the statutory determination notices (Appendix C, source 2–3).

---

*Prepared for the council's decision-support design review. The tool described is advisory: it recommends, and it does not determine.*
