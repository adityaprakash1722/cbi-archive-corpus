# Handover: where the project actually stands

Written 26 August 2026, at the point of moving from a Cowork session to Claude
Code running locally.

> **Current-state addendum, 30 August 2026.** This is a dated research handover,
> not the storage/runbook authority. Corpus v5.1 is now the local current index:
> 3,844 Central Bank, 1,722 stakeholder, zero unresolved and two mixed documents;
> page-level voice, canonical engagement identifiers, final-text quality metrics,
> a preferred DOCX extraction and a recovered CP76 submission. The public release is pinned by immutable Git
> and Hugging Face revisions in `RELEASE.lock.json`. `AGENTS.md` and `STORAGE.md`
> own the current operational facts.

`CLAUDE.md`, `STORAGE.md` and `PUBLISHING.md` describe the corpus and the
infrastructure. **This document describes the research**: what has been found,
what is unfinished, what was got wrong, and what to do next. Read it after
`CLAUDE.md` and before doing any analysis.

---

## 1. What this project is for

**The scraping was never the project.** It is infrastructure, and it is done.

The goal is to use the corpus to learn how the Irish financial system actually
works, find a real and unsolved problem inside it, and design a mature, defensible
solution to that problem.

The user has explicitly chosen: **learn first, then hunt.** Build genuine
understanding of the system before shortlisting problems, so that any solution is
mature rather than merely clever. The vehicle for the eventual solution is
deliberately undecided: startup, solo product, SAP-adjacent, or none of those.
Do not assume a startup.

---

## 2. Current phase

**Learning, pass 1 of roughly six.** One of twelve reading bundles has been read
properly. Two substantive findings exist. Everything else is open.

Twelve provenance-labelled reading bundles sit at `work/learning-bundles/`,
4.6 MB total, built by `scripts/build_learning_bundles.py` from the corpus. They
are gitignored but present on disk.

| Bundle | Size | Read |
|---|---:|---|
| supervision.txt | 401 KB | **yes** |
| architecture.txt | 359 KB | no |
| consumer_protection.txt | 380 KB | no |
| banking_credit.txt | 431 KB | no |
| payments.txt | 370 KB | no |
| credit_unions.txt | 358 KB | no |
| enforcement.txt | 296 KB | no |
| funds_insurance.txt | 378 KB | no |
| data_reporting.txt | 346 KB | no |
| resilience.txt | 336 KB | no |
| history.txt | 311 KB | no |
| industry_voice.txt | 763 KB | partially, by grep |

Every excerpt in every bundle carries an `authorship:` header. Respect it.

---

## 3. Finding 1: Ireland runs a two-speed regulatory state

This is the structural spine and it holds up. All figures are from the corpus.

**PRISM** (Probability Risk and Impact SysteM) was the supervisory framework from
2011 until it was replaced in 2025. It scores every regulated firm on **impact**,
the damage its failure would cause, and **probability**, its likelihood of
failing, then allocates supervision accordingly.

The 2012 distribution, from the INED briefing presentation p7:

| Tier | Firms | Supervisors per firm |
|---|---:|---|
| Ultra High | 5 | eight each |
| High | 15 | two to four each |
| Medium High | 70 | 50% to 100% of one |
| Medium Low | 447 | 10% to 20% of one |
| **Low** | **10,259** | **reactive only** |

Roughly **94% of firms sat in the Low tier**, and `PRISM Explained` states in a
footnote that low impact firms are **not probability rated at all**. No assigned
supervisor, no scheduled engagement, no risk assessment. Automated financial
triggers, occasional thematic sweeps, and enforcement after the fact.

The Bank argues for this openly, in a boxed section of `PRISM Explained`:

> "For the lower impact firms, we will not generally be actively involved prior
> to a failure... An Garda Siochana does not take detectives off its Special
> Detective Unit to patrol shops after every case of shoplifting."

As resource allocation this is defensible. The IMF's 2014 IOSCO assessment
nevertheless rated the relevant principle **"Partly implemented"** and named the
concern precisely (IMF Country Report 14/136, April 2014, p72):

> "A primary concern is whether the calibration of PRISM is appropriate...
> The overwhelming majority of firms (well more than 90%) have been designated
> Low Impact... relies heavily on reactive processes."

In credit unions the shortfall was published and quantified: the Registry ran at
**approximately 60% of PRISM's own suggested supervisory resources**, forcing a
2015 "Temporary Supervisory Engagement Model" under which no Full Risk
Assessments were performed at all for a period (ICURN Peer Review, July 2015,
pp38, 141, 148 to 149).

**The obligations do not scale down.** Conduct Standards apply to Controlled
Function holders "in all regulated firms, including credit unions". The Consumer
Protection Code's vulnerable-consumer requirements are "applicable to all
regulated entities". Fitness and probity, AML and reporting bind everyone.

**Inference, and I think a strong one:** several thousand firms carry the full
conduct rulebook with no supervisory relationship, no assigned supervisor to ask,
and no firm-specific view of what "proportionate" means for them. They
self-interpret, and find out whether they were right through a thematic
inspection or an enforcement action.

### What is NOT yet established

- **The 10,259 figure is from 2012.** The current mandate is stated as "more than
  3,300 firms plus approximately 9,100 investment funds" in the Regulatory and
  Supervisory Outlook 2026. Those count differently and have not been reconciled.
- **PRISM was replaced in 2025** by "integrated supervision" with multi-year
  sectoral strategies. Evidence on what actually changed is thin. It may address
  the long tail, or may formalise sectoral treatment and leave it untouched.
  **This is the single most important open question**, because it decides whether
  Finding 1 is current or historical.

---

## 4. Finding 2: the industry-voice signature matches

This was reached independently, by counting, before any of Finding 1 was read.

The method only became possible after the provenance classifier was fixed. The
question asked is not "what does the Bank publish about" but "what do **firms**
raise, across how many separate consultations, over how many years". Persistence
across independent consultations is the signal, because it cannot be explained by
one consultation's politics.

Base: **1,724 documents containing stakeholder-authored pages** across **97
distinct consultations**, roughly 2006 to 2026. The count is one above the
1,722 stakeholder containers because both mixed compilations contribute
stakeholder pages too.

| What firms raise | Consultations of 97 |
|---|---:|
| Unclear requirements, need for clarity | 81% |
| Proportionality for smaller firms | 76% |
| Outsourcing and third-party oversight | 73% |
| Compliance cost and disproportionality | 72% |
| Duplicated effort and re-reporting | 55% |
| Regulatory reporting mechanics | 49% |
| Safeguarding client money | 34% |
| **Fraud and scam handling** | **26%** |
| Manual work and spreadsheets | 25% |
| **Complaints handling operations** | **19%** |

Interpretation and proportionality dominate. Operational topics do not. That is
exactly what you would predict from a population holding obligations with no
interpreter.

### The methodological catch, and why one result survives it

Consultation responses are **advocacy**. "Disproportionate" and "we would welcome
clarity" are lobbying vocabulary. The high scores at the top of that table are
partly measuring rhetorical convention, and should not be trusted on their own.

But the bias runs one way, which makes the **negative** results the trustworthy
ones. If firms wanted relief from fraud-handling or complaints-handling
obligations, advocacy incentives would push them to say so loudly. They largely
do not. That gap is the kind bias would conceal, not manufacture.

A useful cross-check from the published corpus: 236 Central Bank documents and
188 stakeholder documents contain "disproportionate". As rates that is 6.1% of
the regulator's page-voice corpus against 10.9% of the stakeholder corpus.

### Current status of these numbers

The scan has been rerun against v5.1 and is in
`analysis-v5.1/industry-pain-scan.*`. It uses page-level voice and validated
`analysis_year`, so the mixed container is handled correctly and malformed 2031
PDF timestamps no longer create future observations. These remain discovery
counts, not evidence of prevalence, causality or buyer demand.

---

## 5. What this does to the existing thesis

`outputs/IRELAND-FINANCIAL-SYSTEM-AND-STARTUP-THESIS.md` proposes **Lorg Relay**,
a fraud-response coordination layer for Irish providers. It is a corrected v1, not
final. Open critiques, in order of severity:

1. **Regulator-pushed, not industry-pulled.** The problem is validated from the
   regulator's side (the Code requires fast, accountable fraud support) and the
   consumer's side (documented harm and under-reporting). It is **not** validated
   from the buyer's side. Across twenty years of firms telling their regulator
   what is operationally painful, fraud case handling barely features at 26%. A
   regulatory obligation can create a budget where no complaint existed, but
   "validated problem" was too generous.

2. **The beachhead is the hardest possible segment.** The named first buyers are
   smaller PSPs, e-money firms and credit-union shared services. That is precisely
   the Low Impact population from Finding 1: no supervisory relationship, no
   scale, no interpretive certainty, and levies they already describe as rising.

3. **The moat and the market contradict each other.** Defensibility is claimed as
   Irish implementation detail. Scale requires EU expansion. The thing that makes
   it defensible is the thing that does not travel. There is **no kill test for
   portability**, and it decides the venture case.

4. **The market arithmetic, done properly, says consultancy.** 40 to 80 buyers at
   36k to 96k EUR recurring gives a realistic Ireland-only ceiling around 1 to 2
   million EUR ARR.

5. **The scorecard implies precision it does not have.** Eight subjective
   dimensions scored 0 to 5 separate the top four by 0.35 points. Fraud response
   and safeguarding should be treated as co-finalists, not winner and runner-up.

6. **DORA and regulatory reporting were scored against an incomplete corpus.**
   The 49 XBRL taxonomy and reporting packs most relevant to them were missing
   when they were assessed. They are now indexed and those candidates should be
   re-scored before being dismissed.

---

## 6. Corrections: do not repeat these

Two claims made during the audit were **wrong**, and Codex caught both. They are
already corrected in the outputs, but stating them prevents rediscovery.

**Safeheld and Imperium(L) are real companies.** Both were reported as
unverifiable. They exist: Safeheld sells client-funds reconciliation and breach
detection, Imperium(L) Prism sells reconciliation and safeguarding control. The
searches simply failed to surface them. The surviving point is narrower and still
useful: all three named safeguarding vendors, Guardexia included, are built around
the **UK FCA regime** (PS25/12, CASS 15, CASS 7 and 8), not the Irish one.

**The PSR provision is narrower than claimed.** It was asserted that the EU
Payment Services Regulation would treat APP fraud generally as unauthorised and
fully reimbursable. It does not. The regime covers **impersonation specifically**:
a third party pretending to be an employee of the consumer's payment service
provider. Those payments remain **authorised transactions** under a special
liability rule, conditional on a police report and prompt notification, and
defeated by gross negligence which the provider must prove.

**General lesson:** a failed web search is not evidence of absence, and a
law-firm summary is not the legislative text.

---

## 7. Who did what

The user runs **Codex and Claude in parallel** on this project. Both have made
real contributions and both have made real errors.

**Codex** built the original pipeline: the crawler, PDF conversion, validation,
indexing, structured-data profiling, and the first thesis. Later it produced the
v3 index, fixed 55 remaining provenance errors taking stakeholder from 1,601 to
1,656, expanded the classifier suite to 97 assertions, recovered two DOCX tables  <!-- historical -->
via an XML fallback, and corrected the PSR, vendor and DORA claims.

**Claude** audited that work and found three material defects: the stakeholder
classifier keyed on a single substring, 323 downloaded documents were never
converted, and "zero conversion errors" described exceptions rather than
extraction fidelity. It then rewrote the classifier, built the office pipeline,
added extraction QA, and set up the publishing infrastructure.

Treat neither as authoritative. Verify.

---

## 8. Outstanding tasks, ranked

1. **Read `consumer_protection.txt` and resolve the 2025 supervisory change.**
   Together these decide whether Finding 1 is current or historical. Highest value.
2. **Read the remaining nine bundles.**
3. **Re-score DORA and regulatory reporting** against the now-complete corpus.
4. **Then, and only then, the problem hunt**, followed by solution design.

---

## 9. How to work here

**Query the corpus without downloading anything:**

```python
import duckdb
con = duckdb.connect(); con.execute("INSTALL httpfs; LOAD httpfs;")
BASE = "https://huggingface.co/datasets/aditya487/cbi-archive-corpus/resolve/bcbd2e84bff7655794eb9985b5f6bd1e428d263e/data"
con.execute(f"SELECT authorship, count(*) FROM read_parquet('{BASE}/documents.parquet') GROUP BY 1").fetchall()
```

**Or use the local index**, which is faster for heavy work:

```bash
make index    # rebuilds cbi-corpus-v5.1-5568docs.sqlite in under a minute
              # from a fresh clone, run make materialize first
python outputs/cbi-research/scripts/search_corpus.py '"operational resilience"' \
  --database outputs/cbi-research/index/cbi-corpus-v5.1-5568docs.sqlite --limit 10
```

**Rebuild the reading bundles** after any classifier change:

```bash
python outputs/cbi-research/scripts/build_learning_bundles.py \
  --database outputs/cbi-research/index/cbi-corpus-v5.1-5568docs.sqlite \
  --output work/learning-bundles
```

**Retrieve an original document** from the published raw archive:

```bash
python publish/get_source.py --search "operational resilience" --limit 3 --fetch
```

**What you can do that the Cowork session could not:** reach huggingface.co. That
session was blocked by an egress allowlist, which is why every upload had to be
copied into PowerShell by hand. You have the `hf` login at
`C:\Users\adipr\.cache\huggingface\` already. Just run things.

---

## 10. Working preferences

- **No em dashes.** The user treats them as an AI-writing tell. Use colons,
  semicolons, commas or parentheses.
- **Explain fully.** Keep technical depth, define terms on first use, show the
  reasoning chain rather than the conclusion alone. Length is not a constraint,
  padding is.
- **Label the kind of claim**: verified from the corpus, inference, or genuine
  uncertainty. This project runs on that distinction.
- **Verify before asserting.** Both assistants have produced confident wrong
  answers here. Check the corpus, run the query, read the page.
- **Push back.** The user wants the thesis stress-tested, not validated.
