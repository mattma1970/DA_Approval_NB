# Data Broker request — Online DA Data API (NSW Planning Portal)

*Draft — send to **data.broker@environment.nsw.gov.au** (the "Data Broker EMAIL" resource on the
dataset page: https://www.planningportal.nsw.gov.au/opendata/dataset/online-da-data-api).
Sender details and date to be filled in by the requester. We have reviewed the published data
dictionary (online-da-api-v2.0.pdf); this request is framed against its filter set.*

---

To the Data Broker,

**Re: request for the Online DA Data API dataset (data dictionary v2.0)**

We are preparing a decision-support system for development application assessment at Northern Beaches Council (NSW). To build an evaluation (golden) set of historical determinations and to profile our local DA population, we would like to request access to the **Online DA Data API** dataset (CC-BY) described at the link above.

Specifically:

1. **The daily feed and/or a historical export**, covering **CouncilName = "Northern Beaches Council"** (as listed in the data dictionary Appendix 1) for all records since **10 December 2018**. We would also appreciate the full statewide feed if it is provided as a standard unit, so we can keep the council file current without separate requests.

2. **Confirmation of field semantics**, to avoid mislabeling in our evaluation set:
   - `ApplicationStatus` — does **"Determined"** cover both granted and refused consents (an outcome-neutral bucket), and does **"Rejected"** denote rejection at lodgement (not refusal of consent)?
   - If so: is the determination *outcome* (grant / refuse / consent conditions) available anywhere in the feed or a companion extract, or is the council consent notice the authoritative source? We would like to pair each "Determined" record with its outcome for our evaluation set.
   - `EPIVariationProposedFlag` — confirmation of intended meaning (a proposed variation to an environmental planning instrument standard, as described in the dictionary).

3. **Site-identification fields** — we plan to map records to planning instruments by location. Please confirm the intended datum/units for `X`/`Y`, and that `Lot`, `PlanLabel`, `Section` and `Suburb` are populated for Northern Beaches Council records (we note they are marked Optional in the dictionary).

4. **Licence and use confirmation** — our intended use is internal evaluation of the decision-support system and, if agreed, anonymised research publication under the CC-BY terms. Please confirm whether any fields are withheld or restricted beyond the published terms, and the preferred channel for updates/changes to the feed.

If the dataset is only supplied by periodic bulk drop (e.g. S3 or secure transfer), please advise the process and any forms we need to complete.

Thank you,

[Name]
[Role / organisation]
[Email]
[Phone]
