# Public register reconnaissance — real notified DAs (25 Sep 2026)

Question: can real notified DAs (and their packages) be found on the web without
the Data Broker / Online DA Data API?

## Working channel: council ePlanning public register (no auth, crawlable)

Base: `https://eservices.northernbeaches.nsw.gov.au/ePlanning/live/Public/XC.Track/`
(same platform as the plan books we crawl; the council website's
`/planning-and-development/application-search` and `/property-search` redirect here.)

- **Search endpoint**: `GET applicationsearch.ashx?term=<q>` → JSON
  `{Error, Search: [{RAM_PROCESS_CTR, Type: 'app'|'prop', Description}]}`.
  - `term=DA2025/0` → prefix search on DA numbers (back to at least 2019).
  - `term=Dee Why` (suburb / street) → property hits; property pages list the
    full DA history for a lot (e.g. DA2023/0815 multi-dwelling, DA2016 subdivision,
    S96 modifications, tree permits — all in one place).
- **Case page**: `SearchApplication.aspx?id=<RAM_PROCESS_CTR>`. Fields present:
  application number, description, application type, **status** (Approved /
  Refused / Withdrawn / Under Assessment / Deferred Commencement / Deemed Refusal),
  submitted date, **exhibition period** (proves notification), determined date,
  determination level (e.g. "Council Staff"), officer, cost of work, applicant,
  address(es), **History timeline** (per-document status + dates), submissions
  received, related/other applications, and a list of lodged documents
  (names + dates: plans, SEE, fire safety statement, stamped plans, assessment
  report, notice of determination, notification map, referral responses…).
- **Lists**: `SearchApplication.aspx?d=thisweek|thismonth&k=LodgementDate|DeterminationDate&t=DevApp`
  (menu: Received this Week/Month, Determined this Month),
  `ApplicationExhibition.aspx` (44 DAs on exhibition as at 25 Sep 2026, incl.
  DA2026/1219 residential flat building, Balgowlah, $11.4M, exhibition
  25/09–09/10/2026), `ApplicationAdvertised.aspx`, `MapApplications.aspx`.
- **Outcome labels**: September-2026 "Determined this Month" sample (91 entries):
  69 Approved, 5 Refused, 1 Deferred Commencement, 1 Deemed Refusal, 6 Withdrawn,
  9 Under Assessment. Refused/conditional distinction for the golden set needs
  the determination notice (see below) — or the council's monthly consent
  notices on `northernbeaches.nsw.gov.au/.../development-consents` (published
  monthly back to 2021; lists approved DAs; conditions live in those notices).

## BROKEN channel: lodged document files

Every document on the case pages links to
`/ePlanning/live/Common/Output/Document.aspx?id=!!<token>&t=app`, which currently
returns (HTTP 200, text) the leaked ASP.NET error:

> Could not find a part of the path 'E:\OnlineDocs\CllrPortal'.

Tested: 0/10 docs on DA2025/0002, 0/24 on DA2026/1219 (both 2026-era and 2025).
Systemic council-side failure — the document store path does not exist on the
server (likely decommissioned after the 2021 migration to the NSW Planning
Portal). **Not an auth/paywall — the files simply cannot be served right now.**
Re-probe periodically; it may be a transient migration state.

## Not accessible (yet): NSW Planning Portal modern register

`apps.planningportal.nsw.gov.au` (where DAs lodge since Jul 2021) serves a
login-gated app (B2C OAuth, `oehcitizensprd` tenant) at its root. No anonymous
per-case public register found from the www site yet (`/onlineDA` is an info
page; "Track an application" resolves into the app domain). The design doc's
`portal_onlineDA` source spec assumed per-case pages for notified DAs — verify
against the logged-in or a public sub-path before relying on it.

## Implications for the golden set / MVP

- Case **metadata** (incl. outcome status, exhibition proof, history timeline,
  document inventory, submissions received) is fully harvestable today, without
  the broker — a ready-made stratified spine on top of (or substitute for) the
  Online DA Data API.
- The **document packages** (drawings, SEE, determination notice, submissions)
  are NOT retrievable from any public channel found so far. The Data Broker
  email (`data-broker-email.md`) should be extended to request document access
  for a small sample of notified DAs — the public register cannot supply it.
- For the MVP (text-first adjudication per user decision): validate on case
  metadata + KB provisions (outcome prediction / provision identification for
  real refused vs approved DAs). Drawing-comprehension (vision) remains a
  stretch goal until documents become available (synthetic drawings in the
  meantime).
