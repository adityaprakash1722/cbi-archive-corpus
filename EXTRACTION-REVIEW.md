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

---

## 7. Superseded in part: the recovery pass

Written later the same day, after acting on section 6.

Actions 1 and 2 of section 6 said to fetch the Minister's submission from the
original and treat one document as absent. Investigating why they were damaged
found a bug rather than a limitation, and most of the damage turned out to be
repairable in place.

### The bug

`pymupdf4llm` returns an empty string for any page carrying a full-page
background image, even when a readable text layer sits underneath it. Plain
`page.get_text()` reads the same pages without difficulty.

The clearest case is a 22-page prohibition notice where 20 pages came out empty
and 43,085 characters were in the file the whole time. Every page has a
letterhead image.

### What was recovered

| Method | Pages | Characters | Documents |
|---|---:|---:|---:|
| Direct text-layer re-extraction | 1,167 | 157,263 | 509 |
| OCR of image-only pages | 258 | 284,347 | 132 |
| **Total** | **1,425** | **441,610** | **609** |

Corpus-wide, empty pages fell from **1,723 to 298**, a reduction of 83%.
Documents graded below `ok` fell from **112 to 82**, with `gappy` more than
halving from 63 to 30.

An honest note on the first row: about 95% of those 1,167 pages yield under 200
characters and are running headers, footers and page numbers. Treating them as
empty was defensible. The substance is 37 pages across 9 documents.

### The two documents this section named

**`Minister for Finance response to CP158` is recovered.** OCR read all eight
missing pages, 17,409 characters, cleanly. It no longer needs to be read from
the original.

**`Submission Chpt 13 re CP76 31.3.14.pdf` is still absent, and now the reason is
known.** Its text is not scanned or damaged: it is a subsetted font with a custom
encoding and no ToUnicode map, so the glyph codes are literally `\x01\x02\x03`
with nothing to map them to. It renders correctly in a PDF viewer and extracts
as noise. Its pages carry no image either, so OCR has nothing to render. Action
2 stands: treat it as absent.

### What it did to the analysis

Almost nothing, which is the reassuring part.

Re-running the industry pain scan against the recovered corpus, **19 of 20 themes
hold their consultation count exactly**. The only movement is complaints handling,
from 14 consultations to 15, which is 14.4% to 15.5% of the 97-consultation base.
Fraud and scam handling stays at 25 consultations. Twelve themes gain between one
and three documents.

The stakeholder base is unchanged at 1,656, so Finding 2's denominator is intact
and its conclusion is unaffected: interpretation and proportionality still
dominate, operational themes still sit at the bottom.

### One thing the recovery broke, and how it was caught

Two previously `unresolved` documents became classifiable once their opening
pages had text. One resolved correctly. The other, the Central Bank's own
*Central Credit Register Feedback Response to CP93*, was classified as
**stakeholder** because it contains the phrase "response to cp".

Its fourth page reads: "20 submissions were received in response to CP93. The
Central Bank would like to thank all parties who took the time to make a
submission." That is the regulator's own feedback statement, and putting it in
the industry pile is precisely the error `CLAUDE.md` names as the cardinal one,
running in the opposite direction.

Fixed by giving four decision-maker phrases precedence over the generic
stakeholder cue, on the reasoning that only the body making the decision counts
the submissions it received, thanks the parties who made them, and sets out next
steps. Three regression assertions cover it, including the mirror case of a
genuine respondent citing the same consultation. The suite is now 97 assertions.

*The general lesson is worth keeping: recovering data changed a classification,
and a classifier that was correct on an empty document was wrong on a full one.
Any future recovery pass should diff the authorship split before and after, and
read every document that moves.*
