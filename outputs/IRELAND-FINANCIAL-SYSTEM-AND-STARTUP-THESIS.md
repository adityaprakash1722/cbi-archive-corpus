# Ireland’s Financial System: Evidence Map and Startup Thesis

> **Status, 26 August 2026.** This is a corrected v1, not a final publication.
> An independent audit found that the stakeholder-submission safeguard did not
> work, that 323 downloaded documents were never analysed, and that the
> opportunity ranking separated its top two candidates by less than its own
> scoring noise. Section 1 and section 5 below are corrected. The lead thesis
> survives: it rests on named, dated Central Bank documents, every figure in
> which was re-verified against its source page. See
> `REMEDIATION-2026-08-26.md`.

**Archive snapshot:** 25 August 2026  
**Analysis completed:** 26 August 2026  
**Scope:** the downloaded public Central Bank of Ireland archive, supplemented only
where necessary by current official institutional and competitor sources.

## Executive conclusion

Ireland’s financial system is not defined by a single weakness. It is a resilient,
highly international financial hub sitting beside a much smaller domestic market. It
has world-scale funds, insurance, banking and payments activity; a credit-union system
with exceptional reach; and a modern consumer-protection regime. Its recurring weaknesses
are operational: fragmented handoffs, uneven capability between large and small firms,
data that is available but difficult to reconcile, and customer-support processes that
do not consistently turn individual harm into fast action and institutional learning.

The strongest startup hypothesis is therefore **not** a new bank, fraud detector,
consumer recovery service, generic complaints tool or national fraud database. It is:

> **Lorg Relay** — a provider-embedded fraud-response coordination layer that captures
> the incident and evidence once, triggers the provider’s existing urgent actions,
> creates a standardized counterparty/evidence packet, gives the customer a coherent
> action record, and produces Consumer Protection Code-ready outcome and root-cause data.

The initial buyers would be smaller payment/e-money firms and credit-union shared-service
organisations, not consumers. Version one would operate inside one provider, move no
money, make no fraud/reimbursement/criminal decision, and depend on no new national
data-sharing law. Cross-provider, Garda, telecom and platform connections are later
interfaces, after their lawful and contractual design is proven.

This is a **validated problem, not yet a validated company**. The two decisive unknowns
are whether the selected BPFI shared-database provider is already building the same
case layer, and whether a sufficiently large set of smaller providers has enough case
volume and budget. The correct next move is a 90-day falsification programme, not a
full product build.

“Lorg Relay” is a working name only. No company-name, trademark or domain clearance has
been performed.

## 1. What was actually analysed

The archive was treated as a provenance-controlled evidence base, not as a folder to
summarise with an LLM.

| Asset class | Logical files | Treatment |
|---|---:|---|
| PDF | 5,246 | Converted to page-anchored Markdown, selectively OCR’d, hashed, validated and indexed |
| CSV | 246 | Stream-profiled directly; key datasets analysed without imputing suppressed cells |
| XLSX | 447 | Workbook/sheet structure, samples and purpose profiled |
| XLS | 42 | Read directly, including three protected files through their read-only default-password path |
| XML | 5 | Parsed and classified as regulatory examples/schemas |
| DOCX | 201 | Converted to Markdown; mostly application forms and guidance notes |
| DOC | 71 | Converted through LibreOffice; forms, checklists and templates |
| ZIP | 49 | Inventoried and profiled; XBRL taxonomy and reporting packages |
| PPTX | 2 | One page per slide; includes a Governor roundtable deck |

The final four rows are the correction. Those 323 documents, 387 MB, were
downloaded in the crawl but excluded from the first analysis because the
conversion pipeline filtered on `format == "PDF"`. The corpus now holds 5,568
documents and 88,782 pages.

The PDF corpus contains **88,106 source pages or recovered pseudo-pages**. Of 5,246
documents, 5,237 raised no conversion error. A separate extraction-fidelity pass,
which structural validation cannot perform, grades 5,486 of 5,568 unique converted
documents as clean and flags 82: 30 with substantially blank pages, 26 garbled by
encoding damage, 19 thin and seven empty. Nine low-text results are explainable:
two heavily redacted notices and seven one-page video placeholders. Four Office files
served with a `.pdf` suffix were recovered. All source and Markdown hashes, page-marker
sequences and logical-document mappings passed validation with zero unexplained orphans.

The 489 workbooks contain 5,404 sheets. Their purpose matters: 120 are published data,
130 research-supporting data, 112 regulatory reporting templates, 72 applications/forms,
47 taxonomies or validation artifacts, six official lists/disclosures and two mapping
tools. The five XML files are reporting examples, not economic observations. Treating
every structured file as a statistical series would be a category error.

The page index separates **1,656 stakeholder consultation and discussion
submissions** from Central Bank research, findings, rules and feedback, and marks a
further 103 documents `unresolved` rather than defaulting them to the Bank.

The original figure was 1,134, and it was wrong. A consultation-hosted document was
treated as a stakeholder submission only if its filename contained the substring
`response`, so 289 files named `...-submission-from-...`, 123 named
`...-feedback-from-...` and an unknown number published under the responder's bare
name were all recorded as Central Bank material. Classification is now two-pass,
filename then document text, with 97 regression tests (including all 55 known
generic-document-type/explicit-attribution conflicts) and a stored basis and
confidence for every label. Stakeholder submissions can reveal pain or objections;
being hosted on centralbank.ie does not turn them into Central Bank conclusions, and
the safeguard that was supposed to enforce that now does.

## 2. The system Ireland actually has

The [Central Bank’s 2026 Regulatory & Supervisory Outlook](https://www.centralbank.ie/docs/default-source/publications/regulatory-and-supervisory-outlook-reports/regulatory-supervisory-outlook-report-2026.pdf)
shows two systems layered together:

| Segment | Verified scale | What it says about Ireland |
|---|---:|---|
| International-facing banks | About €456bn assets at Q4 2025 | Ireland is deeply connected to cross-border finance |
| Domestic retail banks | About €317bn assets | Household and SME outcomes sit in a smaller, more concentrated domestic system |
| Payment/e-money firms | 58 firms; €11.8bn safeguarded; €702bn transactions in 2025 | Innovation and EEA reach are substantial; safeguarding, fraud and wind-down remain supervisory concerns |
| Retail non-bank credit | 36 retail credit firms, 19 servicers, 28 high-cost providers; about €47bn AUM and 958,000 accounts | Credit and servicing are more diverse than the bank count suggests, but customer journeys can fragment |
| Credit unions | 172 institutions; 3.7m members; €18.7bn savings; €7.7bn loans | Exceptional distribution and trust reach coexist with uneven technology, risk and specialist capacity |
| Insurance/reinsurance | More than 170 firms; fourth-largest EU sector by gross written premium | Ireland is an export platform and risk hub, not merely a domestic insurance market |
| Funds | About 9,100 funds; nearly €5.3tn NAV; more than €1.9tn in ETFs | A genuine global strength, with liquidity, leverage, valuation and operational-risk externalities |

These quantities must not be added: they describe different stocks, flows, populations
and mandates. International scale also does not prove competitive domestic outcomes.

### Structural strengths

1. **Post-crisis resilience.** Capital, liquidity and solvency are materially stronger;
   the most repeated current weaknesses are conduct, operations, data, technology and
   customer service rather than an immediate system-wide solvency crisis.
2. **A global financial-services platform.** Banking, insurance, payments and funds
   generate deep specialist capability and potential launch paths into the EU.
3. **Unusually broad mutual distribution.** Credit unions reach 3.7 million members.
   That is a powerful channel when specialist infrastructure can be shared safely.
4. **Outcome-oriented regulation.** The [Consumer Protection Code 2025](https://www.centralbank.ie/regulation/consumer-protection/consumer-protection-code)
   took effect on 24 March 2026 and makes customer interests, vulnerability, fraud
   support, complaints and root-cause learning operational obligations.
5. **Rich public evidence.** Ireland publishes granular statistics, research and
   supervisory findings. The archive can support unusually transparent product design—
   if definitions, revisions, suppressed cells and source classes are preserved.

### Cross-system weaknesses

1. **Handoffs fail at the moment of harm.** Fraud, complaints, account access, arrears
   and claims can move across front line, operations, risk, another institution and a
   public body. Context and accountability degrade between them.
2. **Evidence is assembled after the event.** Firms often have a system of record but
   not an event trail linking customer impact, evidence, action, decision and read-across.
3. **Capability is uneven.** Large groups can buy sophisticated platforms. Smaller
   PSPs, e-money firms, credit unions and intermediaries face comparable obligations
   without comparable teams or integration budgets.
4. **Fast payment rails meet slow coordination.** Instant or near-instant value transfer
   increases the cost of delay in customer recognition, freeze/recall, counterparty
   contact, evidence preservation and reporting.
5. **Public data is parseable but not automatically safe to aggregate.** Suppression,
   shifted dates, incomplete rows and incompatible definitions survived successful
   technical parsing. This is a governance problem, not a file-format problem.

## 3. Domestic banking and household evidence

### Savings, credit and pricing

At June 2026, the Central Bank’s retail-rate datasets show:

- €150.54bn of household overnight deposits at an average 0.14%;
- household term deposits up to two years at 2.20%;
- new mortgages excluding renegotiations at 3.49%;
- new small non-financial-company loans up to €250,000 at 5.87%; and
- new consumer loans at 7.48%.

The 2.06-point overnight/term deposit gap is a useful choice-architecture signal, not
an estimate of consumer loss: the products have different liquidity and maturity, and
not every overnight balance can or should move.

Known-sector SME credit outstanding was €14.647bn at Q1 2026, down 2.08% year-on-year,
while quarterly new lending was €1.342bn, up 12.78%, at a 5.04% weighted rate. One
sector was suppressed in both comparison periods and was not imputed. A falling stock
alongside a rising quarterly flow can reflect repayment, composition and timing; it is
not by itself proof of credit rationing.

New mortgage lending in 2025 was €15.459bn across 48,896 loans. First-time buyers made
up about 62% of value and count. Their mean loan was €322,253, mean property value
€408,224 and mean income €94,957; mean LTI was 3.5, LTV 79.8%, and 88.7% were fixed.
These averages do not reveal rejected applicants or the distribution around the mean.

### Arrears: aggregate success, concentrated long tail

The [Q1 2026 mortgage-arrears release](https://www.centralbank.ie/docs/default-source/statistics/data-and-analysis/credit-and-banking-statistics/mortgage-arrears/2026-q1-release.pdf?sfvrsn=2729711a_2)
reports 698,459 principal-dwelling-home accounts and 21,302 over 90 days in arrears—
3.0%, the lowest share in the series. Of 53,818 restructured PDH accounts, 85% were not
in arrears. Yet buy-to-let accounts still included 4,519 over 90 days and 3,846 over a
year. Non-banks held 15% of their PDH accounts over 90 days and 93% of all PDH accounts
over ten years in arrears.

The accompanying CSV has incomplete Q1 2026 PDH headline rows and anomalous quarter-end
dates. BTL totals reconcile; the PDF release is used for PDH facts. No rows were silently
repaired. The lesson is broader than mortgages: technically valid data pipelines still
need semantic controls.

## 4. Why fraud response is the strongest wedge

### The harm is documented

The 2026 Central Bank research paper [*Caught in the Net*](https://www.centralbank.ie/docs/default-source/publications/research-technical-papers/caught-in-net-patterns-and-predictors-of-fraud-incidence-ireland.pdf)
surveyed 2,945 adults. Thirty-five percent reported a fraud experience and 38% of
victims reported it to no authority. Among 661 money-losing respondents who completed
the relevant sequence, 13% of non-reporters recovered funds compared with 57% of
reporters. That is an association, not proof that reporting caused recovery. The paper
also finds risky online behaviour more predictive than general financial literacy and
recommends simpler, more accessible reporting processes.

The [2024 payment-fraud release](https://www.centralbank.ie/docs/default-source/statistics/data-and-analysis/payment-fraud-statistics/payment-fraud-statistics-202485f0d58e-4a6d-4a27-aed4-03717c7bdcd7.pdf?sfvrsn=3a96e1a_1)
reports €160m of fraudulent payment value across 815,000 transactions, up from €129m
and 579,000 in 2023. Online fraud represented €124m, or 77.4%. Final booked losses were
€66.4m; 66% were borne by payment-service users. Fraud value is not booked loss, and
loss can be recognised after the incident period.

The public granular CSV exactly supports the rounded 2024 card (€45.4m) and credit-
transfer (€67.7m) components. Other instrument aggregates are suppressed and the visible
hierarchy is non-additive, so the €160m headline cannot be recreated safely. The €57m
payment/e-money-sector statistic in the Supervisory Outlook is narrower again. These
measures should never be combined into a synthetic TAM.

Downstream friction is also visible. The FSPO’s [*Overview of Complaints 2025*](https://fspo.ie/documents/Overview-of-Complaints-2025.pdf)
records 7,004 complaints, including 3,802 banking complaints. Disputed transactions
were the largest banking conduct category at 1,297 (34%); that category includes alleged
fraud, missing money, security failures and unauthorised transactions, not APP fraud alone.

### The required experience is explicit

The Central Bank’s [Guidance on Securing Customers’ Interests](https://www.centralbank.ie/docs/default-source/regulation/consumer-protection/other-codes-of-conduct/consumer-protection-code-review/securing-customers-interests-guidance.pdf?sfvrsn=955d631a_9)
says fraud-support interfaces should be rapid, simple, intuitive and easy to find, and
that notifications must be acted on immediately to stop or reduce harm. The [cross-
sector complaints review](https://www.centralbank.ie/docs/default-source/regulation/consumer-protection/compliance-monitoring/themed-inspections/cross-sectoral/customer-experience-through-lens-customer-complaints-cross-sectoral-review.pdf?sfvrsn=6c71761a_3)
found inconsistent issue identification, incomplete resolution, weak root-cause analysis
and uneven quality assurance. One example involved 16 calls and ten emails over four
months before third-party help prompted a complaint.

The current public journey is genuinely multi-channel. Garda guidance tells a victim
to notify the relevant financial institution or platform promptly to minimise loss and
preserve evidence, while fraud in Ireland is reported to a [local Garda station](https://www.garda.ie/en/crime/fraud/i-believe-i-have-been-a-victim-of-fraud-should-i-report-this-to-an-garda-siochana-.html).
That institutional division is legitimate, but it makes evidence portability and clear
next actions valuable.

### National initiatives reduce—and clarify—the opportunity

The 2024 [Oireachtas APP-fraud report](https://www.oireachtas.ie/en/press-centre/press-releases/20241023-committee-on-finance-public-expenditure-and-reform-and-taoiseach-publishes-report-on-authorised-push-payment-fraud-recommends-shared-fraud-database-greater-coordination-and-communication-by-stakeholders/)
called for a shared database, uniform reporting, a lead entity and direct communication
among financial institutions, platforms and internet providers. BPFI’s December 2025
[statement](https://bpfi.ie/bpfi-opening-statement-to-oireachtas-finance-committee-3rd-december-2025/)
described the database as shared intelligence on confirmed fraud, compromised accounts,
typologies and risk indicators and said enabling legislation had not yet been enacted.

The latest official update located, from May 2026, says the Department of Justice had
circulated [draft regulations](https://www.centralbank.ie/docs/default-source/publications/correspondence/dept-of-finance-correspondence/letter-to-the-t%C3%A1naiste-and-minister-for-finance-simon-harris-national-payments-strategy-annual-update.pdf?sfvrsn=ad60701a_3)
which, if enacted, would allow the database to be established. The April 2026
[Irish Retail Payments Forum record](https://www.centralbank.ie/docs/default-source/financial-system/irish-retail-payments-forum/meetings/irish-retail-payments-forum-meeting-21-april-2026.pdf?sfvrsn=dd73701a_2)
shows information-sharing, gross-negligence/PSR and fraud-charter workstreams moving
toward delivery. It also records that financial firms had not yet agreed the actions
expected from telecom/non-PSP recipients after a Trusted Flagger alert, and that
“fraud stopped” is important but not typically reported.

This is not evidence that Ireland is doing nothing. It is evidence that the national
architecture is moving and that a startup must be complementary, interoperable and
able to create value inside one provider before shared exchange exists.

## 5. Opportunity screen

| Rank | Opportunity | Score / 5 | Decision |
|---:|---|---:|---|
| 1 | Fraud intake, evidence and action routing | 3.90 | Co-finalist; problem strong, buyer/differentiation unproven |
| 2 | Payment/e-money safeguarding cockpit | 3.65 | Co-finalist; clearer recurring compliance budget, real competition |
| 3 | DORA service/dependency evidence graph | 3.60 | Reopened; directly relevant office documents were missing |
| 4 | Consumer-outcome/complaint observability | 3.55 | Strong regulatory adjacency; generic category crowded |
| 5 | Regulatory data-lineage/remediation controls | 3.50 | Too horizontal without a specific return/workflow wedge |
| 6 | Shared credit-union lending/risk layer | 3.15 | Broad reach, but existing sector initiatives and difficult shared governance |
| 7 | Reusable mortgage-switch pack | 3.10 | Helpful but crowded, low differentiation and externally dependent |

Scores weight pain, official evidence, buyer, timing, MVP scope, differentiation,
regulatory feasibility and expansion. They are decision aids, not measurements. A
disqualifier (no lawful data path, direct overlap with a committed national vendor,
no budget owner, or an unmeasurable pilot) overrides the score.

**The gap between ranks 1 and 2 is smaller than the model's own resolution.** Eight
subjective dimensions scored 0 to 5 separate the top four by 0.35 points, and a
single sub-score moving by one point on the 20%-weighted pain dimension shifts a
total by 0.20. Fraud response and safeguarding should therefore be treated as
co-finalists entering parallel buyer discovery, not as a winner and a runner-up. The
DORA and regulatory-reporting candidates were also scored before the office corpus
was indexed, so their ranking is not yet safe. The 49 ZIPs are mainly Solvency and
regulatory-reporting taxonomy packs, not DORA evidence by themselves; the directly
relevant additions include a DORA PPTX and DOCX.

### Why the runners-up lost

- **Safeguarding:** Central Bank findings are strong, and
  [Guardexia](https://guardexia.com/ps25-12/), [Safeheld](https://safeheld.com/) and
  [Imperium(L)](https://www.imperiuml.com/payments-e-money-cass-15/) market variants
  of this solution. Guardexia explicitly markets both UK PS25/12 and EU PSD2 Article
  10 support; Safeheld markets EU PSD2/MiCA and global support; Imperium(L) Prism is
  UK CASS-focused. An Irish adapter may still matter,
  but the public evidence does not prove an empty Irish/EU category. Competitive
  discovery is therefore a core kill test, not a confirmed moat.
- **Complaints:** the need is explicit, but generic complaints/CRM/workflow vendors can
  absorb it. It is better used as a fraud-product capability.
- **DORA/data lineage:** repeated evidence, broad budgets, little Irish
  distinctiveness. This judgement predates the office and archive corpus, which
  contains the Central Bank's own reporting packs, schemas and filing instructions.
  It should be revisited against that material before the candidate is dismissed.
- **Credit unions:** compelling distribution but shared platforms, sector programmes,
  governance and procurement make a generic proposition hard to differentiate.
- **Mortgage switching:** real friction, but it depends on lender/conveyancing processes
  and offers weak software defensibility.

## 6. Lorg Relay: exact product definition

### User journey

1. The customer selects **“I think I’ve been scammed”** in the provider’s authenticated
   app, web channel, branch or assisted phone process.
2. The journey adapts to APP scam, card fraud, account takeover or impersonation and
   captures transactions, beneficiary, communications, platform, timeline and support
   needs once.
3. Provider-owned actions are triggered through existing systems: card/account controls,
   freeze flags, recall request, evidence preservation and specialist escalation.
4. The system creates a standardized receiving-PSP packet over an already lawful channel.
5. The customer sees what has been recorded, the current status and the next time-sensitive
   step. A portable Garda-ready bundle can be exported; the startup does not file or
   investigate the crime in version one.
6. The provider receives CPC/PSR timers, vulnerable-customer markers, complaint recognition,
   quality controls, root-cause categories and reconciled outcome metrics.

### What it explicitly does not do

- Hold or move funds.
- Charge victims for “recovery.”
- Determine fraud, criminal guilt, gross negligence or reimbursement.
- Create a cross-institution criminal-offence database.
- Replace detection, CRM or the provider’s system of record.
- Promise that reporting causes recovery.
- Require a Garda, platform or telecom API for the initial product to work.

### Buyer and economics hypothesis

The beachhead is a smaller Irish PSP/e-money firm or credit-union shared-service group.
Large banks are later buyers or integration partners: Bank of Ireland’s [public account
of its Featurespace programme](https://www.bankofireland.com/about-bank-of-ireland/press-releases/2026/ai-technology-sees-customer-payment-fraud-losses-at-bank-of-ireland-drop-25/)
shows that at least one can already fund sophisticated prevention and case technology.

Ireland has 58 payment/e-money firms and 172 credit unions, but the realistically
obtainable buyer set may be only 40–80 after groups, shared services, low volumes and
procurement readiness are considered. Ireland is a proving ground, not a standalone
venture-scale TAM. A discovery range of €25k–€75k implementation plus €3k–€8k monthly
software and case-volume tiers is a hypothesis to test, not a forecast. Scale requires
EU reimbursement/regulatory adapters after the Irish workflow works.

### Competitive boundary

[Pay.UK’s RCMS](https://www.wearepay.uk/rcms-core/) is the strongest analogue and long-run
scheme-operator threat: it supports APP-claim creation, PSP routing, assessment,
notifications and repatriation. Quavo, FINBOA, Velera, Casap and CaseHUB cover variants
of fraud/dispute intake and case automation. Featurespace and peers cover detection.

The defensible claim cannot be “we built claims software.” It must be measurable Irish
implementation IP: CPC-native intake and assistance, local evidence/routing adapters,
controlled metric definitions, smaller-provider deployment economics, and compatibility
with the national database and eventual EU rules. If qualified buyers call this mere
configuration, the thesis fails.

The EU PSR/PSD3 package also remains a moving boundary. The co-legislators reached a
provisional agreement in November 2025; the Council’s [2026 compromise record](https://data.consilium.europa.eu/doc/document/ST-8221-2026-INIT/en/pdf)
shows final text work continuing. Product requirements must be updated against enacted
text and Irish implementation, not designed from a provisional summary.

## 7. Regulatory and data design

Version one should be a processor inside one regulated provider’s documented fraud and
complaints workflow. Its minimum architecture is:

- tenant-separated storage and provider-controlled retention;
- field-level purpose and lawful-basis register;
- explicit separation of ordinary personal data, vulnerability/support information and
  alleged criminal-offence data;
- no free-form sharing when a structured, minimized field will do;
- immutable event log for evidence received, action triggered and customer update;
- human decision points for reimbursement, fraud classification and complaint outcome;
- export/deletion/correction pathways aligned with provider policy;
- role- and case-based access, encryption and auditable break-glass controls;
- metric definitions that reconcile attempted, stopped, lost, reimbursed and recovered
  amounts rather than summing them.

Payment Services Regulations 2018 contain a fraud-prevention/investigation processing
provision, but that is not a blanket authority for every inter-organisational flow.
GDPR, Irish data-protection law, criminal-offence data rules, banking secrecy, provider
contracts and specific statutory powers still require counsel and data-protection review.

## 8. Ninety-day falsification plan

### Days 1–20: kill the overlap and buyer risks

- Obtain an authoritative BPFI/vendor scope and interface map.
- Interview ten heads of fraud operations, complaints or consumer protection across
  PSPs, e-money firms and credit-union shared services.
- Record annual relevant case volume, current tools, handoffs, operations minutes,
  incomplete-intake rate, recall latency, recovery by fraud type, procurement threshold
  and named budget owner.
- Map current lawful channels before proposing any new exchange.

### Days 21–45: prove workflow, not AI theatre

- Build a clickable or thin functional prototype using synthetic APP, card and
  account-takeover cases.
- Test authenticated self-service and assisted-channel parity.
- Create the metric dictionary and standardized evidence packet.
- Conduct a DPIA-style threat/purpose exercise before production data.

### Days 46–75: shadow-mode benchmark

Replay 50 minimized historical cases without live actions. Compare:

- median time to a complete packet;
- missing mandatory fields on first submission;
- number of victim retellings;
- time to first freeze/recall attempt;
- operations minutes and duplicate entry;
- acknowledgement/update timeliness;
- complaint/escalation and vulnerable-customer outcomes; and
- ability to measure attempted/stopped fraud consistently.

Recovery should be tracked by fraud type but described as association, not proof of the
workflow’s causal effect.

### Days 76–90: proceed only if all gates pass

1. No committed national/vendor overlap with the same intake and case exchange.
2. A documented lawful single-provider processing design.
3. A named budget owner and credible annual case volume.
4. At least 30% improvement in complete-intake time or handling effort.
5. A signed path to a paid pilot without delegating reimbursement/fraud decisions.
6. A credible EU adapter path if Ireland’s obtainable market is below 40 buyers or ACV
   is below €40,000.

If any of the first five fail, stop. That discipline is part of the startup thesis.

## 9. What the archive does—and does not—justify

### Strong conclusions

- Ireland has a large, resilient and internationally important financial system whose
  current recurring weaknesses are often operational and conduct-related.
- Fraud experience, non-reporting, fragmented action and downstream disputed-transaction
  complaints are real, independently documented problems.
- Current consumer-protection guidance gives regulated providers a direct obligation to
  make fraud support fast, accessible, actionable and measurable.
- Ireland’s national anti-fraud architecture is advancing, so a startup must complement
  it and be valuable before cross-sector exchange.
- Smaller regulated firms plausibly face a capability gap, but public data does not
  quantify their workflow economics.

### Conclusions that would be overstated

- “Ireland loses €160m every year and the startup can recover it.” The €160m is payment
  value, not recoverable loss, and one year is not a stable TAM.
- “Reporting causes four times more recovery.” The survey demonstrates association.
- “The shared fraud database solves only prevention.” That is its public description;
  private vendor scope must be checked.
- “There are 230 buyers.” Entity counts do not equal obtainable accounts.
- “AI is the moat.” The moat, if one exists, is workflow deployment, controlled evidence,
  local interfaces, outcome data and institutional trust.

## Final recommendation

Proceed with **customer and vendor-scope discovery for Lorg Relay**, not with full product
engineering. The problem is unusually well supported: customer harm, under-reporting,
regulatory obligations, complaint failures and inter-institutional coordination needs
all converge. The proposed MVP can stay inside one provider and avoid regulated decisions.

But the opportunity is narrow and time-sensitive. A national scheme operator, the BPFI
database vendor, a generic disputes platform or an incumbent integrator could own the
same layer. The company is worth building only if a smaller-provider workflow benchmark
demonstrates at least 30% operational improvement and buyers pay for the Ireland-specific
adapter rather than treating it as consultancy configuration.

That is the most defensible “unique, solvable and challenging” problem in the archive:
**not detecting that fraud exists, but turning a frightened customer’s first report into
a complete, immediate, portable and accountable chain of action.**
