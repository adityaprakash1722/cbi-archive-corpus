# Extraction review: the 33 flagged stakeholder documents

Written 26 August 2026. Closes the qualitative half of a sensitivity check whose
quantitative half was run the same day.

---

## 1. The question

`qa/extraction-quality.csv` grades 112 documents as extracting badly: 63 `gappy`,
26 `garbled`, 16 `thin`, 7 `empty`. **33 of those are stakeholder documents**, and
the stakeholder pile is what drives Finding 2's industry pain scan.

I had claimed that extraction failure "can only cause false negatives, never
false positives", and that its effect was uniform across themes. Codex pushed
back on both, correctly. Neither claim had been tested, and one of them was
wrong as a general statement: garbled text can in principle fabricate a token
that matches a keyword.

So the question is not whether the general claim holds. It is what actually
happens in this corpus.

## 2. The quantitative half, already run

Dropping all 33 documents entirely moves each theme's consultation count by
**at most one**, and by zero on 17 of 20 themes. The three that move are
outsourcing (70 to 69), fitness and probity (46 to 45), and fraud and scam
handling (25 to 24).

They are spread across **20 of 97 consultations**, mildly clustered in CP76 and
CP88, which `CLAUDE.md` already names as skew risks for unrelated reasons.

## 3. What reading them actually shows

### The damage is far more concentrated than the grade suggests

Measuring the share of each document's text that is the Unicode replacement
character, meaning bytes the extractor could not resolve to a character:

**Exactly one of the 33 is genuinely unreadable.** `Submission Chpt 13 re CP76
31.3.14.pdf` is **94.2%** replacement characters. It holds 12,066 characters of
text and essentially all of it is noise, a font-encoding failure rather than a
scanning failure. Every other flagged document sits **below 5%**.

That single document is the honest loss. The `garbled` grade on the other six is
misleading if read as "unreadable": those documents are 0.8% to 0.9% damaged,
which is a handful of mangled characters in an otherwise clean submission.

### The `gappy` grade is mostly cover pages, not lost argument

The 25 `gappy` documents share a shape: two or three pages, exactly one of them
empty, one to five thousand characters of clean text. Reading them, the empty
page is almost always a scanned letterhead or a signature page. The argument is
in the page that extracted.

Across all 33, 41 of 144 pages are empty (28%), against 1.7% for the stakeholder
pile as a whole. So the 33 hold **1.2% of stakeholder pages but 19.6% of all
empty stakeholder pages**: the failures are real and concentrated, they are just
concentrated in pages that mostly carried a letterhead.

### One document is a substantial loss

`Minister for Finance response to CP158` has **eight of nine pages empty**. What
survives is the opening of the cover letter:

> "I welcome the recent publication of the consultation paper on the revise..."

and then nothing. A submission from the Minister for Finance to the Governor is
not a routine stakeholder response, and 90% of it is absent from the corpus.
*This one should be read from the original PDF before any conclusion about CP158
is drawn.* `publish/get_source.py` now works, so that is a one-line fetch.

### One flagged document is not a defect at all

`Derek Lawler`, graded `thin` at 146 characters, is complete:

> "An Post feedback has been incorporated within the BPFI response. Many thanks"

That is the whole document. A one-line note redirecting the reader to another
submission. The grade is correct that it is thin and wrong to imply anything is
missing. It also resolves a question raised by the rights review: a
personal-name title here is a corporate compliance manager signing off, not a
private individual.

## 4. The false-positive question, tested

Codex was right in principle. In this corpus it does not bite.

The two load-bearing low-scoring themes were checked directly, along with
safeguarding:

| Theme | Flagged docs matching | Damage in those documents |
|---|---:|---|
| Safeguarding client money | 0 of 33 | not applicable |
| Fraud and scam handling | 2 of 33 | 0.8% and 0.9% unreadable |
| Complaints handling | 2 of 33 | 0.9% and 0.0% unreadable |

**Every match sits on clean text.** The one 94%-unreadable document matches no
theme at all, which is what you would expect: its text is replacement characters,
and a replacement character cannot spell "fraud". The spurious-token mechanism
Codex describes is real, but it requires garbling that produces plausible words,
and this corpus's garbling produces `�`.

*So the direction claim holds empirically here, and I should not have asserted it
as a principle before checking. It is a property of how these particular
documents fail, not a law.*

## 5. What this does to Finding 2

Nothing, and slightly in its favour.

Fraud moves from 25 consultations to 24 when the flagged documents are dropped,
which is 25.8% to 24.7% of the 97-consultation base. It moves **down**, which
mildly widens the gap Finding 2 rests on. Complaints handling does not move at
all, staying at 14 consultations.

The residual risk is unmeasurable rather than large: the eight empty pages of the
Minister's submission could say anything, and 41 empty pages across the 33 could
collectively contain themes nobody counted. That is a real limit and it is why
`mine_industry_pain.py` describes its own output as a discovery layer requiring
document reading, which remains the right posture.

## 6. Actions

1. **Fetch and read `Minister for Finance response to CP158` from the original.**
   The only document here where the loss is large enough to change a reading.
   ```bash
   python publish/get_source.py --search "Minister for Finance response to CP158" --limit 1 --fetch
   ```
2. **Treat `Submission Chpt 13 re CP76 31.3.14.pdf` as absent.** At 94.2% noise it
   should not be quoted from, and arguably should be excluded from text scans
   rather than left to contribute nothing but weight.
3. **Consider narrowing the `garbled` grade.** Six of seven garbled documents are
   under 1% damaged. A grade that groups those with a 94% failure is not helping
   the reader decide anything. A threshold at, say, 5% would separate them.
4. **Leave the rest.** 25 gappy cover pages are not worth remediating.
