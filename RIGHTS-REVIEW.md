# Rights and personal-data review

Written 26 August 2026, before treating the three-tier publication as finished.

**This is not legal advice and I am not qualified to give it.** It is a factual
screen of what the corpus actually contains, so that whoever decides how public
this should be is deciding with the numbers in front of them.

---

## 1. Why this was done at all

Every document in this corpus was already public on centralbank.ie. That is not
the same as being publishable in bulk.

An individual's consultation response sitting on a regulator's website is
findable by someone who goes looking for that response. The same response inside
a downloadable, indexed, full-text-searchable corpus is findable by someone who
was not looking for it at all, and who may be looking for the person rather than
the consultation. The shorthand for what is lost in that move is **practical
obscurity**, and losing it is a real change in exposure even when every input
was technically public.

The Central Bank's reuse terms carve out personal information and third-party
rights from the general permission to reuse. So the question is not "was this
public" but "what is in it".

## 2. Licence position

From `files.csv`, 6,984 download records:

| Licence | Files |
|---|---:|
| Creative Commons Attribution 4.0 | **71** |
| No explicit licence metadata | **6,913** |

*Verified.* Only the open-data portal datasets carry an explicit licence. The
other 99% are ordinary published documents whose reuse rests on the site's
general terms, which are the terms that exclude personal data. That asymmetry is
the whole reason this review exists.

## 3. What the screen found

`scripts/scan_personal_data.py` pattern-screened all 88,783 v5 pages. It stores
counts and truncated hashes, never values.

| Signal | Documents | Stakeholder | Central Bank |
|---|---:|---:|---:|
| Irish PPS number shape | 17 | 13 | 4 |
| IBAN shape | 4 | 0 | 4 |
| Email, personal-looking local part | 509 | 152 | 348 |
| Email, any | 2,406 | 618 | 1,758 |
| Irish phone number shape | 226 | 124 | 97 |
| Date of birth label | 2 | 0 | 2 |
| Signature block | 1,827 | 731 | 1,065 |
| Home address label | 14 | 3 | 11 |
| Written as a private individual | 39 | 20 | 19 |

3,196 of 5,568 documents carry at least one signal. The remaining signal rows
are 29 unresolved documents and one mixed composite; column totals can overlap.
That number is alarming and
almost entirely meaningless on its own, which is why every high-severity
category was then read individually.

## 4. Triage of the severe categories

**All 21 PPSN and IBAN candidates are false positives.** I read the context of
every one.

The 17 PPSN hits are **VAT registration numbers**. An Irish VAT number and an
Irish PPS number share the same shape: seven digits followed by a letter. Every
hit was a company VAT number on a letterhead or footer, of the form
`VAT No. IE 1234567X`, alongside a company registration number and a registered
office. One further hit was garbled numeric table data from a document already
graded as extracting badly.

*This is worth encoding permanently: any PPSN screen run over Irish corporate
documents will be dominated by VAT numbers, and a future reviewer should not
re-raise the alarm.*

The 4 IBAN hits are the **Central Bank's own institutional accounts**, published
deliberately so that regulated firms can pay levies and prospectus fees. They
appear next to `Account Name: Central Bank of Ireland` and a public BIC.

**Conclusion: no national identifiers and no personal bank details were found.**

## 5. The category that is real

Submissions written by private individuals rather than firms. These are the
documents where a name, an occupation, a personal circumstance and an opinion
appear together, which is what makes them sensitive in aggregate.

`qa/individual-submission-review.csv` lists **18 candidates**: 11 stakeholder,
6 central-bank, 1 unresolved. That is **0.66% of the 1,671 stakeholder
documents**.

They were found three ways: a title styled as a personal name, a URL styled the
same way, or first-person self-description in the text ("I write to you as an
individual", "my name is", "this submission is made in a personal capacity").

The raw "personal capacity" signal was 39 documents; most were false positives
in the privacy sense, because the phrase has technical uses in this domain. A
Head of Actuarial Function certifies "in a personal capacity"; a credit union is
regulated "as an individual entity". Those are not private citizens.

What survives is a genuinely small set, including a retired non-executive
director writing about his own career, a self-identified journalist giving his
name and employment history, and a consultation whose published title is
literally "Consumer and Individual Submissions".

**18 documents is reviewable by a person in an afternoon.** That is the most
useful finding here: this is not a mass problem requiring an automated
redaction pipeline, it is a short worklist.

## 6. Titles, an exposure path the body-text screen missed

Screening page text does not cover everything that gets published. Document
**titles** are a column in `documents.parquet`, and some of them come from PDF
metadata written by Outlook, which puts a `From:` line into the title.

Checked separately across all 5,568 titles and source URLs: **5 distinct email
addresses**, all institutional. Five at `centralbank.ie`, one at a trade
association, one at a law firm. **Zero personal-looking addresses**, meaning
none in `first.last` form.

*Verified, and clear.* But it is worth recording how it was found: the QA output
of this very review was itself checked for leakage before being committed, and
that check is what surfaced the titles. A privacy screen that publishes the data
it screened for has failed at its own job. The addresses are masked in
`qa/personal-data-scan.csv`, and `scan_personal_data.py` stores counts and
truncated hashes only.

## 7. The Bank already redacts

| Marker | Pages | Documents |
|---|---:|---:|
| "redacted", "withheld", "anonymised" | 358 | 206 |
| Character-masked strings (`markxxxxxxx`) | 38 | 28 |
| "name withheld", "details supplied" | 1 | 1 |

*Verified.* The Central Bank applies redaction before publishing, and at least
one individual's email address in the corpus arrives already masked by them.
This does not discharge the obligation, but it does mean the upstream publisher
made its own pass, and the corpus inherits that.

## 8. Assessment

*Inference, and I hold it with reasonable confidence:*

The bulk-republication risk here is **low but not zero**, and it is concentrated
in a set small enough to handle by hand. The absence of national identifiers and
payment details is the reassuring part. The presence of a handful of identifiable
private individuals writing about their own circumstances is the part that needs
a decision.

The corpus's own framing makes this sharper, not softer. `CLAUDE.md` warns that
stakeholder documents are advocacy and must be labelled as such. A private
individual's submission is advocacy too, but it is advocacy attached to a real
person with no press office, which is a different thing from a bank's lobbying
position.

## 9. Recommendations

1. **Done. All 18 were reviewed and all 18 are preserved.** See section 11 for
   the decision and its reasoning.
2. **Publish a takedown route.** The raw dataset card must carry a named contact
   and an undertaking to remove on request. This is the single highest-value
   mitigation and it costs nothing.
3. **State the licence position honestly on both cards**: 71 files CC-BY-4.0,
   the rest reused under the Bank's site terms, with personal data and
   third-party rights excluded from that permission.
4. **Do not treat the screen as a clearance.** It is a pattern screen with known
   noise. `scan_personal_data.py` should be re-run after any corpus change, and
   the PPSN-versus-VAT finding kept in mind.
5. **Leave the 2,406 documents containing email addresses alone.** They are
   overwhelmingly corporate contact points on letterheads, already published, and
   redacting them would damage the corpus for no meaningful privacy gain.

## 10. Reproducing this

```bash
python outputs/cbi-research/scripts/scan_personal_data.py \
  --database outputs/cbi-research/index/cbi-corpus-v5-5568docs.sqlite \
  --output outputs/cbi-research/qa
```

Outputs `qa/personal-data-scan.csv` (per-document worklist),
`qa/personal-data-scan.json` (summary) and, from the follow-up pass,
`qa/individual-submission-review.csv`.

---

## 11. Decision on the 18 candidates: preserve all of them

Taken 26 August 2026 by the maintainer, who is the data controller here. The
instruction was explicit: preserve all data. Recorded per document in
`qa/individual-submission-review.csv`, in the `assessment`, `action` and
`mitigation` columns.

### The split, after reading each one

**9 are public-role**, and the "personal" signal was misleading:

| Document | Why it is not a private individual |
|---|---|
| Career Stories (two documents) | Central Bank staff profiles, published by the Bank for recruitment |
| Opening Statement of Mr Peter Hinchliffe | Statutory inquiry opening statement, deliberately public |
| Quinn Insurance Limited Inquiry statement | The same |
| IFSAT decision | Tribunal ruling on a regulatory appeal, public record |
| 2019 Insurance Conference | Speakers in professional capacity |
| Mr Bernard Sheridan | The Central Bank's Director of Consumer Protection, official capacity |
| Dr. Laura E. Kodres | Academic economist submitting professionally |
| Comments on Regulation and Guidance | Named professional commentary |

Publishing these carries no meaningful privacy exposure. They are people acting
in public roles in documents the Bank published on purpose.

**9 are private individuals** writing about their own circumstances, across
CP33, CP45, CP55, CP56, CP63, CP76, CP87, CP114 and CP141.

### What was decided, and why

**All 18 preserved. Nothing removed, nothing redacted.**

The reasoning:

1. **Deletion is irreversible and the exposure is reversible.** A takedown on
   request can be granted at any time. A document deleted from an archive is
   gone, and this crawl is not trivially repeatable: source URLs rot, and the
   Bank reorganises its site.
2. **The nine private submissions are 0.54% of the stakeholder pile.** Removing
   them would put a silent, undocumented hole in a corpus whose entire value is
   that it is a complete and checkable record. A researcher who later found the
   gap could not tell whether it was censorship, crawler failure, or the Bank
   never publishing them.
3. **The mitigation is already live and costs nothing.** The raw dataset card
   carries a takedown route that requires no justification and promises no
   argument. That converts a permanent decision into a request anyone affected
   can make.
4. **The Bank redacted first.** These documents reached the corpus after the
   Central Bank's own pass; one of the nine arrives with its email address
   already masked upstream.

### What this decision is not

It is **not** a finding that publication is risk-free. Section 8's assessment
stands: the risk is low but not zero, and it sits with these nine documents.
Preserving them is a choice to keep the record complete and handle objections as
they arrive, rather than to pre-emptively thin the archive.

*If that trade looks wrong later, the reversal is easy and the worklist is
already written.* That asymmetry is the point.
