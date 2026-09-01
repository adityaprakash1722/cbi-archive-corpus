#!/usr/bin/env python3
"""Assemble provenance-labelled reading bundles from the corpus.

Each bundle answers one learning question. Pages are selected by relevance from
the FTS index, deduplicated, and written with a header carrying title, URL, page
number and, critically, **institutional voice and review status**. A reader of the bundle must never be able
to mistake an industry lobbying claim for a Central Bank finding, which is the
single discipline this whole corpus was built to preserve.
"""
from __future__ import annotations
import argparse, json, re, sqlite3, time
from pathlib import Path

BUNDLES = {
 "architecture": ("Who the actors are and how the system is wired", [
   '"our mandate" OR "statutory objectives" OR "functions of the Central Bank" OR "Commission of the Central Bank"',
   '"Single Supervisory Mechanism" OR "European Central Bank" OR "national competent authority" OR "European Banking Authority" OR "EIOPA" OR "ESMA"',
   '"Financial Services and Pensions Ombudsman" OR "Competition and Consumer Protection Commission" OR "Department of Finance" OR "An Garda" OR "Banking and Payments Federation"',
   '"memorandum of understanding" OR "cooperation agreement" OR "information sharing" AND authorities',
   '"deposit guarantee" OR "Investor Compensation" OR "Insurance Compensation Fund" OR "resolution authority"',
 ]),
 "supervision": ("How supervision actually works, then and now", [
   '"PRISM" OR "impact category" OR "probability rating" OR "engagement model"',
   '"integrated supervision" OR "supervisory strategy" OR "supervisory approach" OR "multi-year"',
   '"gatekeeping" OR "authorisation process" OR "application for authorisation" OR "key facts document"',
   '"thematic inspection" OR "themed inspection" OR "review found" OR "we expect firms"',
   '"proportionate" AND (supervision OR supervisory)',
 ]),
 "enforcement": ("Consequences: enforcement, accountability, redress", [
   '"administrative sanctions" OR "enforcement action" OR "settlement agreement" OR "monetary penalty"',
   '"Individual Accountability" OR "SEAR" OR "senior executive accountability" OR "conduct standards"',
   '"fitness and probity" OR "pre-approval controlled function" OR "PCF"',
   '"prohibition notice" OR "revocation" OR "direction issued"',
 ]),
 "consumer_protection": ("The consumer rulebook and how it evolved", [
   '"Consumer Protection Code" OR "the Code" AND consumer',
   '"securing customers interests" OR "customers best interests" OR "consumer protection outcomes"',
   '"vulnerable" OR "vulnerability" AND (consumer OR customer)',
   '"complaints handling" OR "complaints process" OR "root cause" OR "错误" OR "errors and remediation"',
   '"informing effectively" OR "disclosure" OR "key information"',
 ]),
 "banking_credit": ("Household and SME credit, arrears, switching", [
   '"household credit market" OR "mortgage measures" OR "loan to income" OR "loan to value"',
   '"arrears" OR "restructure" OR "forbearance" OR "repossession"',
   '"switching" OR "switcher" OR "refinance" OR "cashback"',
   '"SME" OR "small and medium" AND (credit OR lending OR rejection)',
   '"non-bank" OR "credit servicing" OR "loan sale" OR "portfolio sale"',
 ]),
 "credit_unions": ("The mutual sector: reach, constraints, restructuring", [
   '"credit union" AND (restructuring OR consolidation OR amalgamation OR transfer)',
   '"loan to asset" OR "lending capacity" OR "business model" AND "credit union"',
   '"common bond" OR "shared services" OR "CUSO" OR "collaboration" AND "credit union"',
   '"credit union" AND (governance OR "risk management" OR skills OR resources)',
 ]),
 "payments": ("Payments, e-money, fraud and the national plumbing", [
   '"payment institution" OR "electronic money" OR "e-money" OR "safeguarding"',
   '"PSD2" OR "payment services regulations" OR "strong customer authentication" OR "open banking"',
   'fraud OR scam OR "authorised push payment" OR "money mule" OR impersonation',
   '"National Payments Strategy" OR "retail payments" OR "cash access" OR "SEPA" OR "instant payments"',
 ]),
 "funds_insurance": ("The export platform: funds, insurance, reinsurance", [
   '"UCITS" OR "AIF" OR "fund management company" OR "depositary" OR "administrator"',
   '"liquidity management" OR "leverage" OR "valuation" OR "delegation" AND fund',
   '"Solvency II" OR "own risk and solvency" OR "reserving" OR "underwriting"',
   '"differential pricing" OR "claims" OR "protection gap" AND insurance',
 ]),
 "data_reporting": ("Regulatory reporting, data and the plumbing of compliance", [
   '"regulatory reporting" OR "returns" AND (accuracy OR quality OR timeliness OR resubmission)',
   '"taxonomy" OR "XBRL" OR "reporting template" OR "validation rules" OR "filing"',
   '"Central Credit Register" OR "credit reporting" OR "data collection"',
   '"data quality" OR "data governance" OR "aggregation" OR "lineage"',
 ]),
 "resilience": ("Operational resilience, outsourcing, technology", [
   '"operational resilience" OR "business continuity" OR "critical or important"',
   '"outsourcing" OR "third party" OR "intragroup" OR "concentration risk" OR "exit plan"',
   '"DORA" OR "digital operational resilience" OR "ICT" OR "cyber" OR "incident reporting"',
   '"legacy" OR "technology" AND (investment OR debt OR modernisation)',
 ]),
 "history": ("How the system got here", [
   '"financial crisis" OR "Honohan" OR "Nyberg" OR "Programme of Support" OR "troika"',
   '"tracker mortgage" OR "examination" AND redress',
   '"Financial Measures Programme" OR "PCAR" OR "PLAR" OR "recapitalisation"',
   '"lessons learned" OR "root causes" OR "we did not" OR "failure of supervision"',
 ]),
}

INDUSTRY = ("industry_voice", "What firms themselves say is broken", [
   '"disproportionate" OR "administrative burden" OR "cost of compliance" OR "resource intensive"',
   '"unclear" OR "ambiguous" OR "further clarity" OR "we would welcome clarity"',
   '"duplication" OR "duplicative" OR "already reported" OR "already provided"',
   '"smaller firms" OR "proportionality" OR "one size fits all"',
   '"manual" OR "spreadsheet" OR "system changes" OR "IT systems" OR "lead time"',
   '"practical difficulties" OR "operational challenge" OR "in practice" AND difficult',
])


def collect(cur, queries, voice, per_query, seen):
    picked = []
    for query in queries:
        rows = cur.execute("""
            SELECT d.title, d.source_url, pg.authorship, pg.institutional_voice,
                   pg.voice_review_status, d.document_class, d.source_sha256,
                   p.page_number, p.text, bm25(pages_fts,0,0,1.5,1.0) AS rank
            FROM pages_fts AS p
            JOIN pages AS pg USING(document_id, page_number)
            JOIN documents AS d USING(document_id)
            WHERE pages_fts MATCH ? AND pg.institutional_voice = ?
            ORDER BY rank LIMIT ?""", (query, voice, per_query)).fetchall()
        for r in rows:
            key = (r["source_sha256"], r["page_number"])
            if key in seen:
                continue
            seen.add(key)
            picked.append(r)
    return picked


def render(rows) -> str:
    out = []
    for r in rows:
        body = re.sub(r"\n{3,}", "\n\n", r["text"]).strip()
        if len(body) < 200:
            continue
        out.append(
            f"\n===== SOURCE =====\n"
            f"voice: {r['institutional_voice'].upper()}   review: {r['voice_review_status']}\n"
            f"legacy_authorship: {r['authorship'].upper()}   class: {r['document_class']}\n"
            f"title: {r['title']}\n"
            f"page: {r['page_number']}   sha256: {r['source_sha256'][:16]}\n"
            f"url: {r['source_url']}\n"
            f"------------------\n{body}\n"
        )
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--per-query", type=int, default=26)
    ap.add_argument("--max-bytes", type=int, default=760_000)
    args = ap.parse_args()
    con = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = []

    for name, (question, queries) in BUNDLES.items():
        seen = set()
        rows = collect(cur, queries, "cbi-institutional", args.per_query, seen)
        # a minority of industry pages for contrast, clearly labelled
        rows += collect(cur, queries, "stakeholder", max(4, args.per_query // 4), seen)
        text = render(rows)[: args.max_bytes]
        header = (f"# Reading bundle: {name}\n# Question: {question}\n"
                  f"# Every excerpt is labelled with institutional voice and review status.\n"
                  f"# CBI-INSTITUTIONAL is evidence-supported regulator material. STAKEHOLDER is\n"
                  f"# a regulated firm or trade body writing to\n"
                  f"# the regulator, which is advocacy and must never be reported as a finding.\n")
        (args.output / f"{name}.txt").write_text(header + text, encoding="utf-8")
        manifest.append({"bundle": name, "question": question, "pages": len(rows), "bytes": len(header + text)})
        print(f"  {name:22s} {len(rows):4d} pages  {len(header+text)/1000:7.0f} KB")

    name, question, queries = INDUSTRY
    seen = set()
    rows = collect(cur, queries, "stakeholder", 60, seen)
    text = render(rows)[: args.max_bytes]
    header = (f"# Reading bundle: {name}\n# Question: {question}\n"
              f"# EVERY excerpt here is STAKEHOLDER advocacy written to the regulator. It is\n"
              f"# evidence of what firms CLAIM is painful, not evidence that the claim is true.\n"
              f"# Weight specificity: a named process, a quantified cost or a concrete workflow is\n"
              f"# worth far more than the words 'burdensome' or 'disproportionate'.\n")
    (args.output / f"{name}.txt").write_text(header + text, encoding="utf-8")
    manifest.append({"bundle": name, "question": question, "pages": len(rows), "bytes": len(header + text)})
    print(f"  {name:22s} {len(rows):4d} pages  {len(header+text)/1000:7.0f} KB")

    (args.output / "bundles.json").write_text(json.dumps(
        {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "bundles": manifest}, indent=2) + "\n",
        encoding="utf-8")
    print(f"\ntotal {sum(b['bytes'] for b in manifest)/1e6:.1f} MB across {len(manifest)} bundles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
