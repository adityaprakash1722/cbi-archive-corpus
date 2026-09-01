# Institutional-voice review protocol

Version 5.2 separates where a file is hosted, who issued it, what role it plays,
and whose institutional position its text expresses. This protocol governs the
remaining human review. It does not turn an unreviewed rule into a verified
label.

## Safety rule

Use `institutional_voice` together with `voice_review_status`. Only
`institutional_voice = 'cbi-institutional'` is eligible for a regulator-only
claim. `cbi-staff` is attributable to a named staff member, not automatically to
the institution. `stakeholder` is advocacy. `external-authority`,
`judicial-tribunal`, `third-party`, and `mixed` must be attributed explicitly.
`unknown` stays excluded from voice-specific conclusions.

## What v5.2 does and does not establish

The v5.2 rules and 114 adjudications repair known unsafe v5.1 classifications.
The earlier 32-document authorship sample was used during development. It is not
an untouched test set, it was not independently double-reviewed, and it cannot
support a population accuracy claim for the new ontology.

The deterministic queue at
`outputs/cbi-research/qa/voice-review-scope.csv` includes:

1. every document associated with a Discussion Paper identifier;
2. consultation documents whose label depends on content scoring rather than a
   stronger filename or page-path cue; and
3. currently unknown documents whose metadata contains an external-authority,
   court, or tribunal cue.

The queue is deliberately a risk-focused worklist, not a representative sample.
Its generator is `export_voice_review_scope.py`.

## Review procedure

1. Two reviewers work independently from the rendered source where available,
   not only the extracted text.
2. Each records one allowed `institutional_voice` value and quotes or describes
   the issuer evidence. A hosting URL alone is not evidence of voice.
3. Agreement can be promoted to `authorship-overrides.csv` with the reviewers,
   date, and evidence recorded. Disagreement is resolved by a third review and
   documented in `resolution_notes`.
4. Composite documents are reviewed page by page and represented through
   `page-authorship-overrides.csv`; the container remains `mixed`.
5. A document remains `unknown` whenever the evidence is insufficient. This is
   the safety outcome, not a classification failure.

## Future accuracy evaluation

A population accuracy claim requires a newly sampled, stratified, held-out set
covering consultation and non-consultation material, formats, dates, and every
predicted voice class. It must be double-reviewed without showing the model
label, report agreement and adjudication, and remain untouched until the rules
are frozen. The development sample and this risk queue must not be reused for
that purpose.
