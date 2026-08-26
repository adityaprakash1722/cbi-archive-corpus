# Startup Opportunity Screen (working)

Scores reflect the completed corpus and structured-data analysis, but remain hypotheses
until buyer discovery. A high public-policy need does not imply a venture-scale company.

## Scoring model

Each category is scored 0–5 and weighted. The disqualifiers override the total.

| Category | Weight | Test |
|---|---:|---|
| Pain and consequence | 20% | Is the current failure frequent, costly, time-critical or harmful? |
| Evidence quality | 15% | Is it supported by current CBI/official findings rather than stakeholder frequency? |
| Buyer and budget | 15% | Is there a named buyer with an existing operational/compliance budget? |
| Timing | 10% | Does current regulation, technology or market change create urgency? |
| Narrow MVP | 10% | Can a useful version be deployed in under six months without replacing core systems? |
| Differentiation | 15% | Is the wedge materially different from active Irish and European vendors? |
| Regulatory feasibility | 10% | Can the first version avoid regulated decisions, funds handling and disproportionate data use? |
| Expansion | 5% | Can the product expand beyond a single small Irish buyer set? |

### Disqualifiers

- The thesis depends on treating consultation submissions as CBI findings.
- A current public/industry programme has already selected a provider for the same
  workflow and buyers will not procure a complementary layer.
- The MVP requires a new statutory data-sharing basis that does not yet exist.
- Customer acquisition requires distressed consumers to pay an untrusted recovery firm.
- The economic benefit cannot be measured in a shadow-mode pilot.

## Provisional scorecard

| ID | Opportunity | Pain | Evidence | Buyer | Timing | MVP | Diff. | Reg. | Expand | Weighted / 5 | State |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| F1 | Fraud intake, evidence and action routing | 5 | 5 | 3 | 5 | 4 | 2 | 3 | 4 | 3.90 | Lead hypothesis; buyer and differentiation unproven |
| Q1 | Consumer-outcome/complaint observability | 4 | 4 | 4 | 5 | 3 | 1 | 4 | 4 | 3.55 | Strong need, crowded horizontal category |
| O1 | DORA service/dependency evidence graph | 4 | 4 | 4 | 4 | 3 | 2 | 4 | 4 | 3.60 | Crowded; seek a narrower wedge |
| P1 | Payment/e-money safeguarding cockpit | 5 | 5 | 4 | 5 | 2 | 1 | 3 | 3 | 3.65 | High pain, crowded and assurance-heavy |
| C1 | Shared credit-union lending/risk layer | 4 | 5 | 3 | 4 | 2 | 1 | 3 | 2 | 3.15 | Existing sector initiatives weaken it |
| D1 | Regulatory data-lineage and remediation controls | 4 | 4 | 4 | 4 | 2 | 2 | 4 | 4 | 3.50 | Too horizontal without a return-specific wedge |
| M1 | Reusable mortgage-switch pack | 3 | 4 | 3 | 4 | 4 | 1 | 4 | 2 | 3.10 | Crowded and dependent on external process |

These numbers are prioritisation aids, not empirical measurements. F1 leads because
official evidence aligns the harm, regulatory obligation and workflow gap; it does not
yet lead on proven budget or defensibility. P1 fell after finding multiple current
safeguarding vendors. Q1 remains a useful adjacency rather than a standalone thesis.

## Lead thesis: Lorg Relay — fraud-response coordination for Ireland

“Lorg Relay” is a descriptive working name only; no trademark, company-name or domain
clearance has been performed.

### Problem statement

After a consumer or small business suspects fraud, urgent action is split across the
sending provider, receiving provider, Gardaí and sometimes a platform or telecom.
Ordinary fraud reports to Gardaí generally start at a local station, while the victim
must separately contact the provider and any platform. Evidence is retold, channels
vary, operational clocks continue, and the customer lacks a coherent action record.

Ireland is actively closing parts of this gap. BPFI's planned database is publicly
described as confirmed-fraud intelligence for prevention/investigation, and the
Anti-Fraud Forum is working on information sharing, a fraud charter and PSR issues.
The April 2026 Forum record nevertheless shows unresolved non-PSP actions after alerts
and incomplete “fraud stopped” measurement. Public scope does not prove that the
selected database implementation excludes intake or case exchange, so that is the
first commercial kill test—not a premise to hand-wave away.

### Initial product boundary

1. A white-label “I think I have been scammed” journey inside a regulated provider's
   authenticated app or web channel, with accessible phone/assisted-channel parity.
2. Fraud-type-adaptive evidence capture: transaction, beneficiary, communications,
   impersonated entity, platform, timeline and vulnerability/support needs—once.
3. Immediate triggers into the provider's existing freeze, card-block, recall and
   case systems; the product records actions but does not decide liability.
4. A standardized receiving-PSP packet over an existing lawful channel. A shared
   exchange is optional and later, only with contract, governance and lawful basis.
5. A customer action record: current status, what has been submitted, time-sensitive
   next step, and a Garda-ready/exportable evidence bundle without exposing protected
   investigative information.
6. CPC/PSR timers, complaint recognition, vulnerable-customer support, root-cause MI
   and a controlled metric dictionary including attempted, stopped, lost, reimbursed
   and recovered amounts.

### Explicit exclusions from version one

- No holding or moving customer money.
- No consumer-paid “fund recovery” representation.
- No fraud guilt, reimbursement or criminal-investigation decision.
- No cross-institution criminal-offence database before a lawful basis and governance
  model are established.
- No promise that reporting causes recovery.
- No direct Garda/platform/telco integration in the first release; generate a portable
  evidence/preservation packet while the institutional interfaces are validated.
- No replacement of a provider's fraud-detection engine, CRM or system of record.

### Beachhead

Start with a smaller Irish PSP/e-money firm or a credit-union shared-service organisation
that must meet the revised Consumer Protection Code but cannot justify a bespoke case
exchange. Large banks are integration partners or later buyers, not the first wedge:
at least one already reports material gains from advanced fraud tooling. Run in shadow
mode on 50 minimised/anonymised historical cases before touching live customer data.

### Pilot measures

- Median time from first customer contact to a complete case packet.
- Share of cases missing mandatory evidence on first submission.
- Number of times the customer must retell the incident.
- Time to first freeze/recall attempt and receiving-PSP acknowledgement.
- Operations minutes per case and duplicate data entry eliminated.
- Recovery/reimbursement outcome by fraud type, reported as association.
- Vulnerable-customer support and complaint/escalation outcomes.
- Attempted/stopped fraud captured under a documented, reconcilable definition.

### Kill tests

1. The BPFI database provider or Irish banks confirm that their committed scope
   includes the same consumer intake, counterparty claims and status workflow.
2. No lawful/contractual route exists even for a processor operating inside one PSP's
   existing fraud workflow.
3. Two target PSPs report fewer than 500 relevant cases per year or cannot identify a
   compliance, fraud-operations or service-quality owner with pilot budget.
4. Shadow-mode testing cannot reduce complete-intake time or handling effort by 30%.
5. Buyers require the startup to make reimbursement or fraud determinations before
   they will pay.
6. Ten qualified discovery interviews imply an obtainable Ireland-only market below
   roughly 40 buyers or annual contract values below €40,000 without a credible EU
   adapter path.

### Competitor pressure

- Pay.UK's RCMS is the clearest reference and eventual scheme-operator threat: it
  creates APP claims on victim notification, routes them to receiving PSPs, manages
  assessment/decision and repatriation, and supports UI/API access.
- Quavo, FINBOA, Velera, Casap and CaseHUB market variants of digital dispute intake,
  investigation, claims, customer communication and workflow automation.
- Featurespace and other detection platforms defend the pre-incident/transaction layer;
  Bank of Ireland's public results show that this is already an active procurement area.
- Guardexia, Safeheld and Imperium(L) make safeguarding/compliance operations a less
  differentiated adjacent thesis despite strong supervisory need.

The defensible angle therefore cannot be “claims software.” It must be a tested Irish
implementation pattern: Consumer Protection Code-native intake, current local routing,
portable evidence, vulnerable-customer support, measurement discipline, rapid deployment
for underserved PSPs, and the ability to plug into—rather than replace—the eventual
national database. If buyers view those as configuration rather than a product, F1
should be rejected.

### Market and commercial hypotheses

The observable Ireland-only buyer universe is small: 58 authorised payment/e-money
firms and 172 credit unions, with procurement likely concentrated into perhaps 40–80
realistic organisations or shared-service groups. That is a beachhead, not a large TAM.
A discovery range of €25,000–€75,000 implementation plus €3,000–€8,000 monthly software
and case-volume tiers is a test hypothesis, not a forecast. Venture scale requires
reusable adapters for EU payment-services/reimbursement regimes after an Irish proof.

### Expansion path, only after the wedge works

Provider intake → PSP-to-PSP case exchange → platform/telco evidence preservation →
shared typology feeds → European reimbursement-regime adapters. The UK Pay.UK RCMS
shows that a whole-market claims workflow can exist, but also warns that a scheme
operator may eventually own this layer; Ireland-specific speed and interoperability
must therefore precede national procurement.

### Ninety-day validation sequence

1. **Days 1–20:** obtain BPFI/vendor scope, map exact lawful channels, and interview ten
   fraud-operations/complaints leaders across PSPs, e-money firms and credit-union
   shared services.
2. **Days 21–45:** build a no-production-data prototype using synthetic APP, card and
   account-takeover cases; test evidence completeness and assisted-channel accessibility.
3. **Days 46–75:** replay 50 minimised historical cases in shadow mode; compare complete-
   packet time, retelling, recall-attempt latency and operations minutes.
4. **Days 76–90:** proceed only with a named budget owner, a documented processing model,
   at least 30% workflow improvement and a signed pilot path. Otherwise kill or pivot.
