#!/usr/bin/env python3
"""Regression tests for the provenance classifier.

Run: python3 test_classify_provenance.py
Every case below is a real URL pattern taken from the archive.
"""
import sys
from classify_provenance import classify

BASE = "https://www.centralbank.ie/docs/default-source/publications/consultation-papers"
DISC = "https://www.centralbank.ie/docs/default-source/publications/discussion-papers"

CASES = [
    # --- family 1: "submission", the family the original classifier missed ---
    (f"{BASE}/cp45/cp45-submission-from-aib.pdf", "stakeholder", "cp45"),
    (f"{BASE}/cp45/cp45-submission-from-bank-of-ireland.pdf", "stakeholder", "cp45"),
    (f"{BASE}/cp43/cp43-submission-from-matheson-ormsby-prentice.pdf", "stakeholder", "cp43"),
    (f"{BASE}/cp116/isme-submission-to-cp116.pdf", "stakeholder", "cp116"),
    (f"{BASE}/cp116/eddie-hobbs-submission-to-cp116-(1-of-2).pdf", "stakeholder", "cp116"),
    (f"{BASE}/cp47/seamus-o'dalaigh-submission.pdf", "stakeholder", "cp47"),

    # --- family 2: "feedback-from", wrongly filed as CBI feedback ---
    (f"{BASE}/cp51/cp51-feedback-from-generali-paneurope.pdf", "stakeholder", "cp51"),
    (f"{BASE}/cp41/cp41-feedback-from-institute-of-directors-in-ireland.pdf", "stakeholder", "cp41"),
    (f"{BASE}/cp51/cp51-feedback-from-deloitte-and-touche.pdf", "stakeholder", "cp51"),

    # --- the original "response" family must NOT regress ---
    (f"{BASE}/cp167/bpfi-response-to-cp167.pdf", "stakeholder", "cp167"),
    (f"{BASE}/cp154/mason-hayes-and-curran-solicitors-response-to-cp154.pdf", "stakeholder", "cp154"),
    (f"{DISC}/dp11/irish-funds-response-to-dp11.pdf", "stakeholder", None),
    (f"{BASE}/cp69/response-to-cp69---grant-thornton.pdf", "stakeholder", "cp69"),

    # --- misspellings that occur in the archive ---
    (f"{BASE}/cp120/susquehanna-international-securities-limited---reponse-to-cp-120.pdf", "stakeholder", "cp120"),
    (f"{BASE}/cp162/irish-funds-repsonse-to-cp162.pdf", "stakeholder", "cp162"),
    (f"{BASE}/cp136/european-principal-traders-association-to-cp136.pdf", "stakeholder", "cp136"),

    # --- Central Bank material must win even when it mentions submissions ---
    (f"{BASE}/cp43/note-from-the-financial-regulator-in-relation-to-submissions-received-on-cp43.pdf",
     "central-bank", "cp43"),
    (f"{BASE}/cp47/a-note-from-the-central-bank-of-ireland---re-publication.pdf", "central-bank", "cp47"),
    (f"{BASE}/cp117/feedback-statement-on-cp117.pdf", "central-bank", "cp117"),
    (f"{BASE}/cp158/feedback-statement-cp158-consultation-consumer-protection-code.pdf", "central-bank", "cp158"),
    (f"{BASE}/cp81/cp81.pdf", "central-bank", "cp81"),
    (f"{BASE}/cp154/consultation-paper-154.pdf", "central-bank", "cp154"),
    (f"{BASE}/cp140/cp140---cross-industry-guidance-on-operational-resilience.pdf", "central-bank", "cp140"),
    (f"{BASE}/cp73/cp73-consultation-on-requirements-for-reserving-and-pricing.pdf", "central-bank", "cp73"),
    (f"{BASE}/cp31/cp-31-guidance-note-1-05.pdf", "central-bank", "cp31"),
    (f"{BASE}/cp10/consumer-protection-code-public-response-to-cp10.pdf", "central-bank", "cp10"),
    (f"{BASE}/cp33/consumer-protection-code-for-licensed-moneylenders-public-response-document.pdf",
     "central-bank", "cp33"),

    # --- non-consultation paths are unchanged ---
    ("https://www.centralbank.ie/docs/default-source/publications/research-technical-papers/caught-in-net.pdf",
     "central-bank", None),
    ("https://www.centralbank.ie/docs/default-source/statistics/data-and-analysis/mortgage-arrears/2026-q1-release.pdf",
     "central-bank", None),
    # Audited stakeholder submissions filed outside the consultation archive.
    ("https://www.centralbank.ie/docs/default-source/regulation/industry-market-sectors/credit-unions/"
     "communications/sector-stakeholder-dialogues/lending-framework-review-2024-joint-submission-from-"
     "cuda-cuma-ilcu-and-nsf.pdf", "stakeholder", None),
    ("https://www.centralbank.ie/docs/default-source/regulation/industry-market-sectors/credit-unions/"
     "communications/sector-stakeholder-dialogues/lending-framework-review-2024-submission-from-"
     "collaborative-finance-clg.pdf", "stakeholder", None),
    # A page-audited composite: Bank-authored framing followed by 22 public and
    # stakeholder submissions. The page-level split is tested by the index test.
    ("https://www.centralbank.ie/docs/default-source/publications/corporate-reports/strategic-plan/"
     "submissions/strategic-plan2019-2021-public-engagement-submissions.pdf",
     "mixed", None),
    # The directory is named cp71, but both the proposal and its feedback
    # statement identify this consultation as CP70. Actual CP71 is under cp071.
    (f"{BASE}/cp71/feedback-statement-on-cp70.pdf", "central-bank", "cp70"),
    (f"{BASE}/cp71/aema-submission.pdf", "stakeholder", "cp70"),
    (f"{BASE}/cp071/cp71.pdf", "central-bank", "cp071"),
]

# Complete regression set from the 2026-08-26 precedence audit: these 55 real
# filenames all have explicit third-party attribution, despite also containing
# a generic Central Bank document-type word.
CASES += [
    (f"{BASE}/cp67/response-to-consultation-on-authorisation-services-standards---{name}.pdf",
     "stakeholder", "cp67")
    for name in (
        "dima", "iba", "ifia-appendix", "ifia", "insurance-ireland", "maples",
        "piba", "william-fry-(1)", "william-fry-(2)",
    )
]
CASES += [
    (f"{BASE}/cp77/al-goodbody-response-to-central-bank-consultation-cp-77-on-publication-of-ucits-rulebook.pdf",
     "stakeholder", "cp77"),
    (f"{BASE}/cp77/ifia-response-to-cp-77---ucits-rulebook-28-march-2014---final.pdf",
     "stakeholder", "cp77"),
]
CASES += [
    (f"{DISC}/discussion-paper-4/{name}---response-to-risk-appetite-discussion-paper.pdf",
     "stakeholder", None)
    for name in (
        "aon-insurance-managers-(dublin)-limited", "axa-life-invest-(ali)", "bny-mellon",
        "brian-woods", "colm-fagan", "credit-union-development-association-(cuda)",
        "dima", "ifia", "institute-of-directors-in-ireland", "irish-banking-federation",
        "linkresq", "risk-management-international", "society-of-actuaries-in-ireland",
        "state-street-corporation", "three-rock-capital-management",
    )
]
CASES += [
    (f"{DISC}/discussion-paper-6/{name}-response-etf-discussion-paper.pdf",
     "stakeholder", None)
    for name in (
        "afg", "amundi", "blackrock", "bny-mellon", "computershare", "deutsche-am",
        "etfs", "fidelity-international", "flow-traders", "hsbc", "ici-global",
        "icma-amic", "irish-funds", "ise", "lseg", "lyxor", "maples", "pwc",
        "rory-flynn", "ssga", "the-investment-association", "vanguard-group",
        "william-fry", "wisdomtree",
    )
]
CASES += [
    (f"{DISC}/discussion-paper-6/jp-morgan-response-to-etf-discussion-paper.pdf",
     "stakeholder", None),
    (f"{DISC}/disucssion-paper-2/dis-2-irish-banking-federation-submission---discussion-paper-on-switching-code.pdf",
     "stakeholder", None),
    (f"{DISC}/disucssion-paper-2/dis-2-money-advice-and-budgeting-service-submission---discussion-paper-on-switching-code.pdf",
     "stakeholder", None),
    (f"{DISC}/disucssion-paper-2/dis-2national-consumer-agency-submission---discussion-paper-on-switching-code.pdf",
     "stakeholder", None),
    (f"{BASE}/cp43/cp43-cover-e-mail-from-the-office-of-the-director-of-corporate-enforcement.pdf",
     "stakeholder", "cp43"),
]

# Bare responder names: filename gives nothing, so content decides.
CONTENT_CASES = [
    # The Bank's own feedback document carries "response to cp", a stakeholder
    # cue. Only the decision-maker counts submissions, thanks the parties who
    # made them, and sets out next steps, so those outrank it. Recovering lost
    # page text surfaced this: the document was 'unresolved' while its opening
    # pages were empty, and landed in the stakeholder pile once they were not.
    (f"{BASE}/cp93/feedbackresponse_cp93.pdf",
     "Central Credit Register Feedback Response to CP93 2016. Overview of key "
     "decisions and next steps. 20 submissions were received in response to CP93. "
     "The Central Bank would like to thank all parties who took the time to make "
     "a submission on CP93.",
     "central-bank"),
    (f"{BASE}/cp72/feedback-on-cp-72-final.pdf",
     "Feedback Statement on Consultation Process for CP 72 March 2014. "
     "Introduction. Submissions. Main issues highlighted. Next steps.",
     "central-bank"),
    # The mirror image must keep working: a genuine respondent citing the same
    # consultation is still a stakeholder.
    (f"{BASE}/cp93/aib-response.pdf",
     "AIB welcomes the opportunity to respond to CP93. This submission sets out "
     "our response to consultation paper CP93. Yours sincerely.",
     "stakeholder"),
    (f"{BASE}/cp71/blackrock.pdf",
     "BlackRock welcomes the opportunity to respond to the Central Bank of Ireland "
     "consultation. Yours sincerely, BlackRock Investment Management.",
     "stakeholder"),
    (f"{BASE}/cp47/money-advice-and-budgeting-service-submission.pdf",
     "Dear Sir, on behalf of our members we would like to thank the Central Bank.",
     "stakeholder"),
    (f"{BASE}/cp47/consumer-protection-code.pdf",
     "Consultation Paper CP47. This consultation paper sets out proposals. "
     "Closing date for submissions is 30 June. The Central Bank invites comments.",
     "central-bank"),
    (f"{BASE}/cp23/stakeholder-protocol.pdf", "", "unresolved"),
    # A respondent quoting the consultation number must never be read as the issuer.
    (f"{BASE}/cp76/gurranabraher-credit-union-limited.pdf",
     "Re: Consultation Paper CP76. Dear Sir, our submission on behalf of our members. Yours sincerely.",
     "stakeholder"),
    (f"{BASE}/cp76/irish-league-of-credit-unions.pdf",
     "Irish League of Credit Unions response to Consultation Paper CP76. "
     "We welcome the opportunity to respond.",
     "stakeholder"),
]

CLASS_CASES = [
    (f"{BASE}/cp51/cp51-feedback-from-generali-paneurope.pdf", "stakeholder-consultation-submission"),
    (f"{BASE}/cp117/feedback-statement-on-cp117.pdf", "cbi-consultation-feedback"),
    (f"{DISC}/dp11/irish-funds-response-to-dp11.pdf", "stakeholder-discussion-submission"),
    (f"{BASE}/cp23/stakeholder-protocol.pdf", "consultation-hosted-unresolved"),
    ("https://www.centralbank.ie/docs/default-source/publications/corporate-reports/strategic-plan/"
     "submissions/strategic-plan2019-2021-public-engagement-submissions.pdf",
     "cbi-corporate-report"),
]

def main() -> int:
    failures = []
    for url, want_authorship, want_cp in CASES:
        got = classify(url)
        if got.authorship != want_authorship:
            failures.append(f"authorship {url.rsplit('/',1)[-1]}: want {want_authorship}, got {got.authorship} ({got.basis})")
        if got.consultation_id != want_cp:
            failures.append(f"consultation_id {url.rsplit('/',1)[-1]}: want {want_cp}, got {got.consultation_id}")
    for url, text, want_authorship in CONTENT_CASES:
        got = classify(url, text)
        if got.authorship != want_authorship:
            failures.append(f"content {url.rsplit('/',1)[-1]}: want {want_authorship}, got {got.authorship} ({got.basis})")
    for url, want_class in CLASS_CASES:
        got = classify(url)
        if got.document_class != want_class:
            failures.append(f"class {url.rsplit('/',1)[-1]}: want {want_class}, got {got.document_class}")

    total = len(CASES) + len(CONTENT_CASES) + len(CLASS_CASES)
    if failures:
        print(f"FAIL {len(failures)} of {total} assertions")
        for line in failures:
            print("  -", line)
        return 1
    print(f"PASS {total} assertions across {len(CASES)} filename, "
          f"{len(CONTENT_CASES)} content and {len(CLASS_CASES)} class cases")
    return 0

if __name__ == "__main__":
    sys.exit(main())
