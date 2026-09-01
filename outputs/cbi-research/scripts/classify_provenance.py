#!/usr/bin/env python3
"""Two-pass provenance classifier for the CBI corpus.

Why this exists
---------------
The original ``classify_source`` in ``build_search_index.py`` decided that a
consultation-hosted document was a stakeholder submission if and only if its
filename contained the substring ``response``. That test missed three whole
families of stakeholder document:

  1. ``cp45-submission-from-aib.pdf``            (says "submission", not "response")
  2. ``cp51-feedback-from-generali-paneurope.pdf`` (says "feedback-from")
  3. ``blackrock.pdf``                           (bare responder name, no cue at all)

Family 3 cannot be resolved from the filename at all, so this module adds a
second pass over the indexed page text.

Output contract
---------------
``classify(url, first_pages_text)`` returns a ``Provenance`` with:

  authorship      central-bank | stakeholder | external-authority |
                  judicial-tribunal | third-party | mixed | unresolved
  legacy_authorship  the v5.1 four-value result, retained only for migration
  institutional_voice  the safe analytical voice class
  author_org      reviewed authoring institution where known
  document_role   proposal, submission, feedback, report, etc.
  review_status   manual-reviewed | rule-classified | unreviewed
  review_evidence evidence supporting the voice label
  document_class  the original 15-class taxonomy, corrected
  consultation_id canonical CP identifier, e.g. cp158, or None
  engagement_id   canonical CP or DP identifier, e.g. cp158 or dp10
  basis           the rule that fired, so every label is auditable
  confidence      high | medium | low

Nothing here guesses silently. When neither pass produces evidence the answer
is ``unresolved``, which is a real answer and must not be read as
"Central Bank material".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


# --------------------------------------------------------------------------
# Pass 1: filename and path signals
# --------------------------------------------------------------------------

# Strong issuer-specific exceptions. These are checked before stakeholder
# attribution because the filenames identify the Central Bank/Financial
# Regulator itself as the author, or are exact public-response titles known
# from the archive.
STRONG_CBI_DOCTYPE = re.compile(
    r"""(
        feedback-statement
      | statement-on-cp
      | note-from-the-(?:central-bank|financial-regulator)
      | a-note-from-the-central-bank
      | consumer-protection-code(?:-for-licensed-moneylenders)?-public-response
      | ^cp-?\d+[a-z]?(?:\.pdf)?$
      | ^dp-?\d+[a-z]?(?:\.pdf)?$
    )""",
    re.VERBOSE,
)

# Generic Central Bank document-type cues. These apply only when the filename
# does not explicitly attribute a response/submission to somebody else.
CBI_DOCTYPE = re.compile(
    r"""(
        consultation-paper
      | discussion-paper
      | cp-?\d+[a-z]?-+consultation
      | consultation-on-
      | summary-of-(?:submissions|responses|comments)
      | regulatory-impact
      | impact-analysis
      | impact-assessment
      | ^gn-?\d
      | guidance-note
      | code-of-(?:practice|conduct)
      | -requirements(?:-|\.|$)
      | addendum
      | rulebook
      | -regulations(?:-|\.|$)
      | cross-industry-guidance
      | guidance-on-
      | -guidelines(?:-|\.|$)
      | administrative-sanctions
      | consumer-protection-code
      | macroprudential-framework
      | macro-prudential-policy
      | frequently-asked-questions
      | minimum-competency
    )""",
    re.VERBOSE,
)

# An attribution preposition, or a bare submission/response token. Includes the
# two misspellings that actually occur in the archive ("reponse", "repsonse").
ATTRIBUTED = re.compile(
    r"""(
        (?:submission|response|reponse|repsonse|replies|feedback|comments?|cover-letter|cover-e-?mail|letter)
        [-_ ]*(?:from|by)[-_ ]
      | (?:submission|response|reponse|repsonse)[-_ ]*to[-_ ]
      | [-_](?:submission|response|reponse|repsonse|replies|comments)(?:[-_.(]|$)
      | ^(?:response|submission)[-_]
      | -to-cp-?\d
    )""",
    re.VERBOSE,
)

# A file named "cp140---cross-industry-guidance..." carries the consultation's own
# number as its prefix. With no attribution cue in the rest of the name, that is a
# Central Bank consultation artefact rather than a respondent's letter.
CP_PREFIXED = re.compile(r"^(?:cp|dp)-?\d+[a-z]?[-_ ]+\S")

CONSULTATION_ID = re.compile(r"/(cp[-_ ]?\d+[a-z]?)/")
DISCUSSION_ID = re.compile(
    r"/(?:dp[-_ ]?0*(\d+)[a-z]?|dis(?:cus|ucs)sion-paper[-_ ]?0*(\d+))/"
)
CONSULTATION_PATHS = ("/consultation-papers/", "/discussion-papers/")

# These are not guesses based on a word in the filename. Each exception names a
# composite that has been opened and page-audited. Page-level ownership lives in
# qa/page-authorship-overrides.csv; this rule only labels the container.
MIXED_DOCUMENTS = {
    "/publications/corporate-reports/strategic-plan/submissions/"
    "strategic-plan2019-2021-public-engagement-submissions.pdf": (
        "cbi-corporate-report",
        "audited-composite:cbi-framing-pages-1-5;stakeholder-submissions-pages-6-114",
    ),
}

# These stakeholder submissions sit under a sector-engagement directory rather
# than the consultation archive, so the normal consultation filename rules do
# not see them. Each file has been opened and its authorship manually verified.
# Keep this list exact: generic words such as "submission" also occur in genuine
# Central Bank submissions and correspondence elsewhere in the archive.
AUDITED_NON_CONSULTATION_STAKEHOLDER = {
    "/sector-stakeholder-dialogues/"
    "lending-framework-review-2024-joint-submission-from-cuda-cuma-ilcu-and-nsf.pdf":
        "joint-credit-union-sector-submission",
    "/sector-stakeholder-dialogues/"
    "lending-framework-review-2024-submission-from-collaborative-finance-clg.pdf":
        "collaborative-finance-submission",
}

# The CBI directory is misnumbered: every document under /cp71/ describes CP70,
# including feedback-statement-on-cp70.pdf and respondent letters headed CP70.
# The actual CP71 material is stored separately under /cp071/.
CONSULTATION_PATH_OVERRIDES = {
    "/consultation-papers/cp71/": "cp70",
}


@dataclass
class Provenance:
    authorship: str
    document_class: str
    consultation_id: str | None
    engagement_id: str | None
    basis: str
    confidence: str
    legacy_authorship: str | None = None
    host: str = "centralbank.ie"
    author_org: str | None = None
    document_role: str | None = None
    institutional_voice: str | None = None
    review_status: str | None = None
    review_evidence: str | None = None

    def __post_init__(self) -> None:
        if self.legacy_authorship is None:
            self.legacy_authorship = self.authorship
        if self.institutional_voice is None:
            self.institutional_voice = {
                "central-bank": "cbi-institutional",
                "stakeholder": "stakeholder",
                "external-authority": "external-authority",
                "judicial-tribunal": "judicial-tribunal",
                "third-party": "third-party",
                "mixed": "mixed",
                "unresolved": "unknown",
            }[self.authorship]
        if self.author_org is None and self.institutional_voice == "cbi-institutional":
            self.author_org = "Central Bank of Ireland"
        if self.document_role is None:
            if self.document_class.startswith("stakeholder-"):
                self.document_role = "consultation-submission"
            elif self.document_class == "cbi-consultation-feedback":
                self.document_role = "feedback-statement"
            elif self.document_class in {"cbi-consultation-material", "cbi-discussion-material"}:
                self.document_role = "consultation-or-discussion-material"
            elif self.document_class == "external-authority-report":
                self.document_role = "external-assessment"
            elif self.document_class == "judicial-or-tribunal-material":
                self.document_role = "judicial-or-tribunal-record"
            elif self.document_class == "cbi-research":
                self.document_role = "research-paper"
            elif self.document_class == "cbi-speech-or-news-material":
                self.document_role = "speech-or-news"
            elif self.document_class == "cbi-policy-analysis":
                self.document_role = "policy-analysis"
            elif self.document_class == "cbi-regulatory-material":
                self.document_role = "regulatory-material"
            elif self.document_class == "cbi-statistical-material":
                self.document_role = "statistical-material"
            elif self.document_class == "cbi-correspondence":
                self.document_role = "correspondence"
            elif self.document_class == "cbi-corporate-report":
                self.document_role = "corporate-report"
            elif self.document_class == "cbi-consumer-material":
                self.document_role = "consumer-information"
            else:
                self.document_role = "other"
        if self.review_status is None:
            self.review_status = (
                "manual-reviewed"
                if self.basis.startswith(("adjudicated:", "audited-", "manual-"))
                else "unreviewed" if self.institutional_voice == "unknown"
                else "rule-classified"
            )
        if self.review_evidence is None:
            self.review_evidence = self.basis


# --------------------------------------------------------------------------
# Pass 2: content signals, used only when pass 1 is inconclusive
# --------------------------------------------------------------------------

CBI_TEXT_MARKERS = (
    # A respondent cites the consultation it is answering, so a bare reference to
    # "Consultation Paper CP76" is weak evidence of authorship, not strong evidence.
    ("consultation paper cp", 1),
    ("discussion paper dp", 1),
    ("feedback statement", 3),
    # "Feedback Response to CP93" is a Central Bank title, but "response to cp"
    # is a stakeholder cue, so without this the Bank's own feedback document
    # scores as a submission. The giveaways are that only the decision-maker
    # announces next steps, counts the submissions it received, and thanks the
    # parties who made them.
    ("feedback response", 4),
    ("submissions were received in response", 4),
    ("would like to thank all parties", 4),
    ("key decisions and next steps", 4),
    ("closing date for submissions", 3),
    ("the central bank invites", 3),
    ("we invite comments", 2),
    ("responses to this consultation", 2),
    ("this consultation paper", 3),
    ("this discussion paper", 3),
    ("central bank of ireland\nbosca", 2),
    ("t: +353 (0)1 224", 2),
    ("comments should be addressed to", 3),
    ("\u00a9 central bank of ireland", 3),
    ("this paper is for consultation", 3),
    ("submissions should be sent", 3),
)

# Phrases that only appear when the Central Bank is the issuer, checked against the
# opening of the document where a title block sits.
CBI_TITLE_MARKERS = ("central bank of ireland", "financial regulator", "central bank commission")

STAKEHOLDER_TEXT_MARKERS = (
    ("we welcome the opportunity", 3),
    ("welcomes the opportunity to respond", 3),
    ("thank you for the opportunity", 3),
    ("dear sir", 2),
    ("dear madam", 2),
    ("yours sincerely", 2),
    ("yours faithfully", 2),
    ("on behalf of our members", 3),
    ("our response to", 2),
    ("this submission", 3),
    ("our submission", 3),
    ("re: cp", 2),
    ("response to cp", 3),
    ("response to consultation paper", 3),
    ("submission to the central bank", 3),
    ("we would like to thank the central bank", 3),
    ("in response to the central bank", 3),
    ("appreciate the opportunity", 2),
    ("appreciates the opportunity", 3),
    ("welcomes the opportunity to comment", 3),
    ("welcomes the opportunity to provide", 3),
    ("response to the consultation", 3),
    ("submission to the financial regulator", 3),
    ("mabs submission", 3),
    ("the following comments", 3),
    ("i attended the session", 3),
    ("i am a member", 2),
)


def _score(text: str, markers) -> tuple[int, list[str]]:
    lowered = text.lower()
    total = 0
    hits: list[str] = []
    for phrase, weight in markers:
        if phrase in lowered:
            total += weight
            hits.append(phrase)
    return total, hits


def canonical_cp(value: str) -> str:
    """Normalise raw CP path fragments without erasing audited path overrides."""
    match = re.fullmatch(r"cp[-_ ]?0*(\d+)([a-z]?)", value.casefold())
    if not match:
        raise ValueError(f"invalid CP identifier: {value!r}")
    return f"cp{int(match.group(1))}{match.group(2)}"


def consultation_id_for(path: str) -> str | None:
    for marker, consultation_id in CONSULTATION_PATH_OVERRIDES.items():
        if marker in path:
            return consultation_id
    match = CONSULTATION_ID.search(path)
    if not match:
        return None
    return canonical_cp(match.group(1))


def engagement_id_for(path: str, consultation_id: str | None = None) -> str | None:
    """Return a normalised join key spanning consultation and discussion papers."""
    if consultation_id:
        return consultation_id
    match = DISCUSSION_ID.search(path)
    if not match:
        return None
    number = next(group for group in match.groups() if group is not None)
    return f"dp{int(number)}"


def topical_class(path: str) -> str:
    """The non-consultation part of the original taxonomy, unchanged."""
    if (
        "/research-technical-papers/" in path
        or "/economic-letters/" in path
        or "/financial-stability-notes/" in path
        or "/consumer-protection-research/" in path
    ):
        return "cbi-research"
    if (
        "/financial-stability-review/" in path
        or "/quarterly-bulletins/" in path
        or "/macro-financial-review/" in path
        or "/regulatory-and-supervisory-outlook-reports/" in path
        or "/household-credit-market-report/" in path
        or "/sme-market-reports/" in path
        or "/systemic-risk-pack/" in path
        or "/financial-crime-bulletin/" in path
        or "/irish-retail-payments-forum/" in path
    ):
        return "cbi-policy-analysis"
    if "/corporate-reports/" in path or "/annual-reports" in path:
        return "cbi-corporate-report"
    if "/regulation/" in path:
        return "cbi-regulatory-material"
    if "/statistics/" in path:
        return "cbi-statistical-material"
    if "/correspondence/" in path:
        return "cbi-correspondence"
    if "/news-and-media/" in path or "/media-release/" in path:
        return "cbi-speech-or-news-material"
    if "/consumer-hub" in path:
        return "cbi-consumer-material"
    return "other-cbi-material"


def classify(url: str, first_pages_text: str = "") -> Provenance:
    path = unquote(urlparse(url).path).casefold()
    name = Path(path).name
    is_consultation = any(marker in path for marker in CONSULTATION_PATHS)
    consultation = consultation_id_for(path)
    engagement = engagement_id_for(path, consultation)
    discussion = "/discussion-papers/" in path

    for marker, (document_class, basis) in MIXED_DOCUMENTS.items():
        if marker in path:
            return Provenance(
                authorship="mixed",
                document_class=document_class,
                consultation_id=consultation,
                engagement_id=engagement,
                basis=basis,
                confidence="high",
            )

    for marker, evidence in AUDITED_NON_CONSULTATION_STAKEHOLDER.items():
        if marker in path:
            return Provenance(
                authorship="stakeholder",
                document_class="stakeholder-consultation-submission",
                consultation_id=None,
                engagement_id=engagement,
                basis=f"audited-non-consultation-stakeholder:{evidence}",
                confidence="high",
            )

    if not is_consultation:
        return Provenance(
            # v5.1 treated every file outside the consultation directories as
            # Central Bank speech. That confused hosting location with author:
            # IMF assessments and tribunal material are counterexamples. Keep
            # the old result only as migration metadata and make the safe label
            # unknown until issuer evidence or a manual review exists.
            authorship="unresolved",
            document_class=topical_class(path),
            consultation_id=consultation,
            engagement_id=engagement,
            basis="host-path-only:non-consultation",
            confidence="low",
            legacy_authorship="central-bank",
            institutional_voice="unknown",
            author_org=None,
            review_status="unreviewed",
            review_evidence="centralbank.ie host path is not authorship evidence",
        )

    strong_cbi_cue = STRONG_CBI_DOCTYPE.search(name)
    third_party_cue = ATTRIBUTED.search(name)
    cbi_cue = CBI_DOCTYPE.search(name)

    if strong_cbi_cue:
        return Provenance(
            authorship="central-bank",
            document_class=(
                "cbi-consultation-feedback"
                if "feedback-statement" in name or "statement-on-cp" in name
                else "cbi-discussion-material" if discussion else "cbi-consultation-material"
            ),
            consultation_id=consultation,
            engagement_id=engagement,
            basis=f"filename-strong-cbi-doctype:{strong_cbi_cue.group(0).strip('-')}",
            confidence="high",
        )

    if third_party_cue:
        return Provenance(
            authorship="stakeholder",
            document_class=(
                "stakeholder-discussion-submission" if discussion
                else "stakeholder-consultation-submission"
            ),
            consultation_id=consultation,
            engagement_id=engagement,
            basis=f"filename-attribution:{third_party_cue.group(0).strip('-')}",
            confidence="high",
        )

    # DP5 exposed a whole filename family that identifies the respondent first
    # and merely repeats the discussion-paper title afterwards, for example
    # ``allianz---discussion-paper-on-payment-of-commission...``. The generic
    # words "discussion paper" are the subject, not the author.
    # Require the archive's actual respondent/title delimiter. A generic prefix
    # such as ``review-of-the-`` or ``dis-2-`` is part of the Bank's document
    # title, not an organisation name. DP5 respondent files consistently use
    # two or more hyphens immediately before ``discussion-paper``.
    respondent_title = re.search(r"-{2,}discussion-paper", name)
    if discussion and cbi_cue and respondent_title:
        prefix = name[:cbi_cue.start()].strip("-_ .")
        if prefix and not re.fullmatch(r"(?:dp|discussion-paper)[-_ ]?\d*[a-z]?", prefix):
            return Provenance(
                authorship="stakeholder",
                document_class="stakeholder-discussion-submission",
                consultation_id=consultation,
                engagement_id=engagement,
                basis=f"filename-discussion-responder-prefix:{prefix[:80]}",
                confidence="high",
            )

    if cbi_cue:
        if first_pages_text.strip():
            cbi_points, _cbi_hits = _score(first_pages_text, CBI_TEXT_MARKERS)
            third_points, third_hits = _score(first_pages_text, STAKEHOLDER_TEXT_MARKERS)
            # One marker is not enough to reverse a filename that identifies a
            # Central Bank document. The Bank's consultation papers naturally
            # say "our submission" when explaining how respondents should write
            # to it. Demand four stakeholder points plus a three-point margin.
            if third_points >= max(cbi_points + 3, 4):
                return Provenance(
                    authorship="stakeholder",
                    document_class=(
                        "stakeholder-discussion-submission" if discussion
                        else "stakeholder-consultation-submission"
                    ),
                    consultation_id=consultation,
                    engagement_id=engagement,
                    basis=(f"content-overrides-generic-doctype({third_points}v{cbi_points}):"
                           f"{';'.join(third_hits[:3])}"),
                    confidence="medium",
                )
        return Provenance(
            authorship="central-bank",
            document_class="cbi-discussion-material" if discussion else "cbi-consultation-material",
            consultation_id=consultation,
            engagement_id=engagement,
            basis=f"filename-cbi-doctype:{cbi_cue.group(0).strip('-')}",
            confidence="high",
        )

    cp_prefixed = CP_PREFIXED.search(name)
    if cp_prefixed:
        return Provenance(
            authorship="central-bank",
            document_class="cbi-discussion-material" if discussion else "cbi-consultation-material",
            consultation_id=consultation,
            engagement_id=engagement,
            basis="filename-cp-prefix-without-attribution",
            confidence="medium",
        )

    # Pass 2. No filename cue, so read the document.
    if first_pages_text.strip():
        cbi_points, cbi_hits = _score(first_pages_text, CBI_TEXT_MARKERS)
        third_points, third_hits = _score(first_pages_text, STAKEHOLDER_TEXT_MARKERS)
        opening = first_pages_text[:300].lower()
        if any(marker in opening for marker in CBI_TITLE_MARKERS) and third_points == 0:
            cbi_points += 2
            cbi_hits.append("cbi-name-in-title-block")
        if third_points >= cbi_points + 3:
            return Provenance(
                authorship="stakeholder",
                document_class=(
                    "stakeholder-discussion-submission" if discussion
                    else "stakeholder-consultation-submission"
                ),
                consultation_id=consultation,
                engagement_id=engagement,
                basis=f"content-stakeholder({third_points}v{cbi_points}):{';'.join(third_hits[:3])}",
                confidence="medium",
            )
        if cbi_points >= third_points + 3:
            return Provenance(
                authorship="central-bank",
                document_class="cbi-discussion-material" if discussion else "cbi-consultation-material",
                consultation_id=consultation,
                engagement_id=engagement,
                basis=f"content-cbi({cbi_points}v{third_points}):{';'.join(cbi_hits[:3])}",
                confidence="medium",
            )
        return Provenance(
            authorship="unresolved",
            document_class="consultation-hosted-unresolved",
            consultation_id=consultation,
            engagement_id=engagement,
            basis=f"content-inconclusive({cbi_points}v{third_points})",
            confidence="low",
        )

    return Provenance(
        authorship="unresolved",
        document_class="consultation-hosted-unresolved",
        consultation_id=consultation,
        engagement_id=engagement,
        basis="no-filename-cue-and-no-text",
        confidence="low",
    )
