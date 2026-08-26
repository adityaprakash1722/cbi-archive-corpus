# Evidence Ledger (working)

This ledger records decision-relevant evidence before synthesis. It is deliberately
separate from the opportunity register: a strong observation is not automatically
a viable startup opportunity. PDF page numbers refer to the source-page markers in
the normalized Markdown, not rendered Markdown pages.

## E-001 — Fraud experience is common, but the decisive gap is post-event reporting

- **Source:** CBI research paper, *Fraud and Scams in Ireland: Who Experiences Them,
  Who Loses Money, and Why?* (2026), SHA-256
  `3f4e89167b516eb847aee8296b99288856b1e492f1dedc12658f8589b2455094`.
- **Pages:** 5, 20, 29.
- **Provenance:** CBI research; authors state that views do not necessarily reflect
  the Central Bank.
- **Finding:** In a broadly nationally representative online survey of 2,945 adults,
  35% reported having experienced fraud. Of victims, 38% reported to no authority.
  Among 661 respondents who lost money and answered the reporting/recovery sequence,
  13% of non-reporters recovered funds versus 57% of reporters.
- **Interpretation constraint:** Reporting and recovery are associated; the study
  does not establish that reporting caused the recovery difference. Bank detection
  may explain some recovery among people who said they did not report.
- **Opportunity implication:** A product should improve speed, completeness and
  routing of post-event action, not make an unsupported promise that reporting alone
  causes recovery.

## E-002 — The reporting journey itself can suppress reporting

- **Source:** Same paper as E-001.
- **Pages:** 20, 29.
- **Finding:** The paper identifies perceived authority attitudes, reporting-channel
  complexity and the number of possible reporting avenues as mechanisms that can
  discourage or overwhelm victims. The authors recommend minimizing reporting steps,
  making processes accessible, strengthening detection, simplifying channels and
  reviewing reimbursement guidance.
- **Interpretation constraint:** The mechanisms are supported partly by prior
  literature rather than experimentally isolated in the Irish survey.
- **Opportunity implication:** The narrow product hypothesis is a single evidence
  capture and case-routing layer, not a generic fraud-awareness application.

## E-003 — General financial education is not an adequate substitute for controls

- **Source:** Same paper as E-001.
- **Pages:** 5, 12–13, 24–29.
- **Finding:** Fraud-specific literacy predicts modestly lower fraud experience;
  general financial literacy does not. Risky online behaviour is the strongest
  behavioural predictor. Average fraud-literacy performance was high even though
  35% reported fraud experience.
- **Interpretation constraint:** The regression is predictive/correlational, and the
  18–24 and 65+ age groups were underrepresented before weighting checks.
- **Opportunity implication:** Education is a supporting feature. The core value must
  come from workflow, timely intervention and system safeguards.

## E-004 — The revised Consumer Protection Code creates a buyer-side obligation

- **Source:** CBI *Consumer Protection Code 2025 — Overview of Key Changes*, SHA-256
  `0fd3173b82e916e3a5b789da29c3f99c03c0963bf81753f37e4c6e3730460399`.
- **Pages:** 12–13.
- **Provenance:** CBI regulatory material.
- **Finding:** Firms must monitor fraud trends and vulnerabilities in processes and
  distribution channels, act where risk increases, and clearly communicate risks,
  available supports and actions after actual or suspected fraud. Firms must also
  assist vulnerable consumers and maintain employee escalation procedures.
- **Opportunity implication:** A white-label workflow can sell to regulated firms as
  customer support plus auditable compliance evidence; it should not depend on
  persuading distressed victims to buy a recovery service.

## E-005 — Ireland's payment sector is large enough to matter and still has control gaps

- **Source:** CBI *Regulatory & Supervisory Outlook 2026*, SHA-256
  `637fc3bcc42209a446b9cd1d0ec21363f986d28a8ce507dffbdc58865c7c0aa3`.
- **Pages:** 54–57.
- **Provenance:** CBI regulatory/supervisory material.
- **Finding:** At end-2025, 58 authorised payment/e-money firms held €11.8bn in
  safeguarded funds; they processed €702bn in 2025. The CBI reports €57m in fraudulent
  payments at Irish-resident payment/e-money institutions in 2024, a threefold
  increase, while transaction value rose 66%. It also reports persistent safeguarding
  deficiencies and inadequate wind-down triggers/customer-money-return planning.
- **Interpretation constraint:** The €57m sector figure is not interchangeable with
  the €66.4m loss or €160m total-payment-fraud measures elsewhere; definitions and
  populations must be reconciled before comparison.
- **Opportunity implication:** Smaller PSPs and e-money firms are a plausible initial
  buyer segment, but safeguarding software and fraud-case orchestration are distinct
  products and should not be combined in the first MVP.

## E-006 — Operational resilience and data-quality pain is real but horizontally crowded

- **Source:** Same 2026 Outlook as E-005.
- **Pages:** 20, 28.
- **Finding:** CBI identifies under-reporting of ICT incidents, weak third-party
  monitoring, concentration/vendor lock-in and weak exit plans. It describes data
  remediation as multi-year and warns that short-term firefighting is inefficient and
  unsustainable; causes include governance, resources and culture, not only IT.
- **Opportunity implication:** This validates demand but not differentiation. Generic
  DORA registers, GRC and data-quality tools face entrenched competitors; retain only
  narrower wedges with Ireland-specific evidence.

## E-007 — Supervisory timing favours customer-outcome and fraud-support tooling

- **Source:** Same 2026 Outlook as E-005.
- **Pages:** 32, 36, 115.
- **Finding:** The revised Code took effect in March 2026. Planned supervision includes
  complaints handling, root-cause remediation, fraud controls, incident response and
  victim treatment. CBI expects complaint management information to expose causes and
  prevent recurrence.
- **Opportunity implication:** A design partner can justify budget through both fraud
  operations and consumer-protection assurance. The product should output root-cause
  and outcome MI rather than merely open a support ticket.

## E-008 — The planned shared database is complementary, but it is a moving boundary

- **Sources:** Oireachtas *Report on Authorised Push Payment Fraud* (2024), pp. 35–38;
  BPFI opening statement to the Oireachtas Finance Committee (3 December 2025);
  CBI National Payments Strategy annual-update letter (2026), pp. 3–4.
- **Provenance:** Parliamentary report, industry representative statement and current
  CBI policy update; these are independent institutional perspectives, not product
  requirements.
- **Finding:** The planned BPFI system is described as a controlled database of
  confirmed fraud, compromised credentials, typologies and risk indicators for
  prevention, investigations and prosecution. In the latest CBI update located, the
  Department of Justice had drafted enabling regulations and circulated them across
  government; the CBI had provided feedback. BPFI also operates three Anti-Fraud
  Forum workstreams, including information sharing and a fraud charter expected in
  H2 2026.
- **Interpretation constraint:** Public descriptions do not prove that the selected
  provider's private scope excludes victim intake or post-event claims orchestration.
  Regulations and the charter are still moving boundaries.
- **Opportunity implication:** Do not compete for the confirmed-fraud intelligence
  database. Build a pre-submission case/evidence layer that can feed it where lawful,
  and make interoperability a requirement. Pause the thesis if discovery shows that
  the database vendor will deliver the same intake, recall and case-status workflow.

## E-009 — CBI guidance describes the proposed intake experience almost directly

- **Source:** CBI *Guidance on Securing Customers' Interests*, SHA-256
  `e5dabf14e1e876c484b3fd0d9b4fe86925befc868391e73aeddd6b0218a3a6cc`.
- **Pages:** 16–17.
- **Provenance:** CBI regulatory guidance.
- **Finding:** CBI says support interfaces deserve the same design attention as sales
  journeys. For suspected fraud, access should be rapid, simple, intuitive and easy to
  find; customers need to notify the firm quickly and trust that it will be acted upon
  immediately so harm can be stopped or reduced. Support must account for the
  customer's circumstances and ability to navigate systems.
- **Opportunity implication:** This is direct regulatory support for an authenticated,
  accessible in-app reporting and action journey. The MVP should benchmark discovery,
  completion and action latency—not only back-office case throughput.

## E-010 — Complaint handling is a measurable cross-sector weakness and adjacency

- **Source:** CBI *Customer Experience through the Lens of Customer Complaints —
  Cross-Sectoral Review*, SHA-256
  `b743318d8fd40d196e14b199f1dc75a4419974be8fabc1fbad1a5b69043b8548`.
- **Pages:** 3–20.
- **Provenance:** Current CBI cross-sector supervisory feedback covering life and
  non-life insurance, retail intermediaries and payment/e-money firms; banking and
  credit firms were reviewed through other work.
- **Finding:** CBI found inconsistent complaint identification, incomplete resolution,
  weak customer-centric engagement, ineffective root-cause analysis and uneven QA.
  It gives an example requiring 16 calls and 10 emails over four months before a
  third party helped the customer complain. It requires complaint-trend analysis at
  least every six months and timely MI, structured reporting and read-across analysis.
- **Opportunity implication:** This validates Q1 and provides reusable design rules
  for fraud cases: detect dissatisfaction without magic words, minimize repeat contact,
  capture the whole issue, and feed root-cause/QA loops. A generic complaints platform
  remains less differentiated than a fraud-specific workflow with this adjacency.

## E-011 — The payment-fraud headline cannot be reconstructed by summing public CSV cells

- **Sources:** CBI *Payment Fraud Statistics 2024*, SHA-256
  `9b28140dd61ae482c235a06374e9c017253ec47d836ad6b409b5aa4d2f9b5d07`,
  pp. 1–5; CBI granular Payment Transactions CSV.
- **Finding:** CBI reports €160m of fraudulent payment value in 2024, 815,000
  fraudulent transactions and €66.4m in final booked losses. Online fraud represented
  €124m (77.4%) of value. Cards (€45.4m) and credit transfers (€67.7m) reconcile from
  the public granular file to the rounded release. Several other instrument aggregates
  are confidential or suppressed, and the visible total hierarchy is non-additive.
- **Interpretation constraint:** Fraudulent transaction value, final booked loss and
  the €57m payment/e-money-sector measure in E-005 have different definitions,
  populations and timing. The public CSV is insufficient to recreate the €160m
  headline without inventing suppressed values.
- **Opportunity implication:** Product reporting needs a metric dictionary and an
  auditable reconciliation layer. It must distinguish attempted/stopped fraud,
  fraudulent payment value, customer loss, reimbursement and final booked loss.

## E-012 — Mortgage distress improved in aggregate, but the long-tail is concentrated

- **Sources:** CBI *Residential Mortgage Arrears and Repossessions Statistics: Q1
  2026*, SHA-256
  `a4d158cb9a22aa37f4dc00a0e23402796cef0c8925b36763296f63a471c7029e`,
  pp. 1–8; CBI mortgage-arrears CSV.
- **Finding:** Of 698,459 principal-dwelling-home accounts, 21,302 (3.0%) were over
  90 days in arrears, the lowest share in the release history. Of 53,818 restructured
  PDH accounts, 85% were not in arrears. Buy-to-let accounts totalled 46,272; 4,519
  were over 90 days in arrears and 3,846 were over one year. Non-banks held 15% of
  their PDH accounts over 90 days in arrears and 93% of all PDH accounts over ten
  years in arrears.
- **Data-quality finding:** The downloaded CSV parses structurally but its Q1 2026
  PDH headline rows are absent/incomplete and some rows mix quarter-end dates. The
  BTL aggregates reconcile; the release, not a silent repair, is used for PDH facts.
- **Opportunity implication:** A generic arrears dashboard is not the strongest
  startup thesis. The data instead shows why definitions, ownership cohort and
  vintage must be preserved in any consumer-outcomes analysis.

## E-013 — Domestic intermediation shows pricing and access frictions beside resilience

- **Sources:** CBI retail-interest-rate, SME lending and new-mortgage-lending CSVs.
- **Finding:** At June 2026, household overnight deposits were €150.54bn at 0.14%,
  while household term deposits up to two years averaged 2.20%; the 2.06 percentage-
  point gap is descriptive and does not assume that all overnight balances are
  transferable. New mortgages excluding renegotiations averaged 3.49%, small new NFC
  loans up to €250,000 averaged 5.87%, and new consumer loans averaged 7.48%.
  Known-sector SME balances were €14.647bn at Q1 2026, down 2.08% year-on-year;
  quarterly new lending was €1.342bn, up 12.78%, at a weighted rate of 5.04%.
- **Mortgage mix:** New mortgage lending totalled €15.459bn across 48,896 loans in
  2025. First-time buyers represented about 62% of value and count; their mean loan
  was €322,253 against a mean property value of €408,224 and income of €94,957.
- **Interpretation constraint:** These are aggregate snapshots, not proof of excess
  margin, affordability, exclusion or individual eligibility. One SME-sector value
  was suppressed and was not imputed.
- **Opportunity implication:** Competition and affordability are important research
  themes, but the public aggregates do not by themselves reveal an executable
  software wedge or prove a market failure.

## E-014 — “Everything” is a heterogeneous evidence base, not a single text corpus

- **Source:** Reproducible local archive audit and conversion/profiling outputs.
- **Finding:** The archive contains 5,246 unique PDFs (88,106 pages/pseudo-pages),
  246 CSVs, 447 XLSX files, 42 XLS files and five XML files. All PDFs were converted,
  hashed and indexed; all structured files were profiled. The 489 workbooks contain
  5,404 sheets and include published data, research support, regulatory templates,
  forms, taxonomies and official lists. The XML files are regulatory examples/schemas,
  not economic observations.
- **Quality constraint:** Nine PDF conversions contain little or no extractable text
  for explainable reasons (two heavily redacted notices and seven video placeholders).
  Four Office files mislabelled as PDF were recovered. The mortgage CSV defect in
  E-012 and suppressed fraud cells in E-011 show why file-level success is not the
  same as analytical validity.
- **Opportunity implication:** Claims in the final report must be traceable to page or
  table, document class and definition. Keyword frequency is discovery evidence only.

## E-015 — Ireland's anti-fraud programme still exposes coordination and measurement gaps

- **Source:** Irish Retail Payments Forum meeting record, 21 April 2026; CBI National
  Payments Strategy annual update, May 2026.
- **Finding:** The Anti-Fraud Forum has information-sharing, gross-negligence/PSR and
  fraud-charter workstreams, with a 2026 push toward tangible outputs. The meeting
  record says actions expected from telecom/non-PSP recipients of Trusted Flagger
  alerts were not yet agreed. Members also identified “fraud stopped” as an important
  measure that is not typically reported. Draft regulations intended to enable the
  shared fraud database were circulated and under review in the latest official
  update located.
- **Interpretation constraint:** This is a moving policy programme. “Not yet agreed”
  in an April record is not evidence of permanent institutional failure, and private
  implementation scope is unknown.
- **Opportunity implication:** The initial wedge should help a provider act and
  measure outcomes inside existing authority. Cross-institution exchange is a staged
  integration, not an MVP dependency.

## E-016 — Disputed transactions have become the largest banking-complaint conduct issue

- **Source:** FSPO *Overview of Complaints 2025*.
- **Finding:** The FSPO received 7,004 complaints in 2025, including 3,802 in banking.
  Disputed transactions accounted for 1,297 banking complaints (34%) and became the
  largest banking conduct category; it encompasses alleged fraud, missing money,
  security failures and unauthorised transactions rather than a pure APP-fraud count.
- **Opportunity implication:** There is measurable downstream friction after payment
  incidents. A workflow that recognises complaints, preserves evidence and documents
  updates can reduce escalation risk, but it must not claim that all 1,297 cases are
  addressable fraud cases.

## E-017 — The generic product category is crowded; localisation must be operational

- **Sources:** Public product materials from Pay.UK RCMS, Quavo, FINBOA, Velera,
  Casap, CaseHUB and Featurespace; safeguarding products Guardexia, Safeheld and
  Imperium(L).
- **Finding:** End-to-end intake, case management, customer updates, reimbursement
  workflows, dispute automation and fraud detection are already marketed globally.
  Pay.UK's RCMS is the clearest scheme-level analogue and long-run substitution risk.
  Bank of Ireland reports that its Featurespace deployment reduced attempted fraud,
  customer losses and case-handling time, illustrating that large banks can procure
  sophisticated detection and operations technology directly.
- **Interpretation constraint:** Vendor feature claims and buyer adoption need direct
  validation; public marketing is not evidence of equivalent Irish implementation.
- **Opportunity implication:** The differentiated claim can only be a deployable Irish
  coordination adapter: Consumer Protection Code-native intake, local evidence/routing,
  smaller-provider economics and interoperability with national/EU initiatives. If
  buyers treat that as mere configuration, reject F1.

## Open evidence tests

1. Verify whether the planned BPFI confirmed-fraud database or its selected vendor is
   already expanding into victim intake, recall/claims exchange or case-status tooling.
2. Establish the lawful basis and data-minimisation design for bank-to-bank, Garda,
   telecom and platform routing, especially criminal-offence data.
3. Interview fraud-operations leaders to quantify current handling time, missing-field
   rates, duplicate victim retelling, recall latency and recovery by fraud type.
4. Reconcile all 2024 fraud totals and denominators before using any market-size claim.
5. Test whether one smaller PSP or credit-union service organisation will supply 50
   anonymised historical cases for a shadow-mode workflow benchmark.
6. Obtain the selected BPFI database vendor's authoritative scope and interface model;
   public sources are not enough to declare complementarity.
7. Ask at least ten qualified buyers for annual incident volumes, current tooling,
   procurement threshold and willingness to pay before treating the market as viable.
