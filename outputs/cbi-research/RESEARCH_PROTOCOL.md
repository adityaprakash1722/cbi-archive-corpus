# Evidence and Opportunity Research Protocol

## Objective

Develop a defensible, Ireland-specific startup thesis from the Central Bank of Ireland corpus. The result must identify a painful and solvable problem, show who experiences and pays for it, explain why existing approaches are inadequate, and distinguish documented evidence from inference.

## Unit of evidence

The basic evidence unit is a claim linked to:

- Content SHA-256.
- Source URL and all known aliases.
- Source page.
- Publication or effective date where available.
- Document type and institutional context.
- Exact supporting passage or structured-data observation.

Duplicate contents count once. Multiple independent documents supporting the same finding strengthen the finding; multiple URLs serving identical bytes do not.

## Temporal rules

Every material claim is labelled as one of:

- Current position.
- Historical position.
- Proposed or consulted change.
- Superseded requirement.
- Observed trend.
- Forecast or scenario.

A recent document does not automatically supersede an older one. Supersession must be explicit or supported by the relevant current rule, guidance, or official publication.

## Evidence strength

| Grade | Standard |
|---|---|
| A | Repeated quantitative evidence or an explicit current regulatory requirement/finding. |
| B | Repeated qualitative evidence across independent official documents. |
| C | One specific official finding, consultation response, or supervisory observation. |
| D | Inference from indirect evidence; requires external validation. |
| E | Hypothesis only; not suitable for a recommendation without new evidence. |

Startup recommendations require at least one Grade A or two independent Grade B signals for the core pain point.

## Problem-signal coding

Candidate passages are coded for:

- Affected party: consumer, SME, bank, credit union, insurer, fund, fintech, regulator, professional adviser, or public body.
- Problem type: access, affordability, delay, manual work, data fragmentation, reporting burden, fraud, operational failure, poor competition, switching friction, information asymmetry, compliance uncertainty, or capability gap.
- Frequency: isolated, repeated, chronic, or systemic.
- Severity: inconvenience, material cost, consumer harm, prudential risk, or financial-stability risk.
- Root cause: incentives, market structure, regulation, legacy technology, missing data, coordination failure, skills, trust, or economics.
- Existing response and evidence of its effectiveness.
- Potential payer and economic beneficiary.

## Analytical workstreams

1. Financial-system structure and participant map.
2. Household banking, mortgages, credit, arrears, and switching.
3. SME funding, payments, cash flow, and financial capability.
4. Credit unions and smaller regulated institutions.
5. Payments, e-money, fraud, AML, and consumer protection.
6. Insurance, pensions, climate, and property risk.
7. Funds, investment firms, securities, and market infrastructure.
8. Regulatory authorisation, reporting, supervision, and enforcement.
9. Operational resilience, outsourcing, cyber risk, and data quality.
10. Macroprudential policy, financial stability, and structural concentration.

## Quantitative safeguards

- Analyse CSV and spreadsheet sources directly rather than transcribing plotted values from PDFs.
- Preserve units, seasonal-adjustment status, reporting population, revisions, and breaks in series.
- Do not combine stocks, flows, percentages, index values, or nominal amounts without explicit transformations.
- Separate nominal changes from real or inflation-adjusted changes.
- Treat catalogue byte counts and metadata as operational information, not economic data.

## Opportunity scoring

Each candidate problem receives a score from 0 to 5 on the following weighted dimensions:

| Dimension | Weight |
|---|---:|
| Pain severity and frequency | 15% |
| Strength of corpus evidence | 15% |
| Identifiable buyer and willingness to pay | 12% |
| Feasibility of a narrow first product | 10% |
| Regulatory viability or tailwind | 10% |
| Existing-solution inadequacy | 10% |
| Defensibility and proprietary learning | 8% |
| Irish distinctiveness | 7% |
| EU expansion potential | 7% |
| Sales-cycle and adoption practicality | 6% |

Fatal constraints such as unavailable lawful data, a required licence disproportionate to the initial market, or no identifiable payer override the weighted score.

## Required falsification

For every finalist, the research must state:

- The strongest evidence that the problem is already being solved.
- Why an incumbent could copy the product.
- What would make customers refuse to buy.
- Which regulatory interpretation could invalidate the model.
- The cheapest real-world test that could disprove the thesis.

## Final standard

The winning idea is not the most imaginative concept. It is the highest-value problem for which the evidence, buyer, product boundary, regulatory path, and validation method fit together coherently.

## Completed-corpus controls

The final analysis applies these additional controls:

- All 5,246 logical PDFs and 323 office/archive records are represented, with
  cross-manifest SHA-256 deduplication yielding 5,568 unique indexed documents.
- Stakeholder consultation/discussion submissions have separate document classes and
  are never promoted into Central Bank findings.
- All 246 CSVs, 489 workbooks and five XML files are profiled; a file's purpose is
  classified before its contents are treated as observations.
- Topic matches are discovery signals only. Publication volume is not used as an
  incidence, importance or institutional-priority measure.
- Suppressed structured observations remain null; no confidential value is inferred
  merely to reproduce a headline.
- Fraudulent payment value, final booked loss, customer-borne loss, reimbursement,
  attempted/stopped fraud and complaint volume remain separate measures.
- When a structured release file and its published release conflict, both are recorded;
  the authoritative release may supply the fact, but the structured file is not silently
  repaired.
- Current programmes and laws are checked outside the archive when their status is
  material to the opportunity boundary.

## Decision rule used in the final synthesis

The lead hypothesis proceeds to discovery only if its core pain has Grade A/B support,
version one can operate inside a single regulated provider without moving money or
making regulated decisions, and a 50-case shadow-mode pilot can measure at least a 30%
workflow improvement. It is rejected if a committed national/vendor programme owns the
same workflow, no lawful processing model exists, no buyer has sufficient volume/budget,
or buyers treat the Ireland-specific layer as configuration rather than a product.
