import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { Readable, Writable } from "node:stream";
import { pipeline } from "node:stream/promises";

import {
  byteLimitTransform,
  canonicalUrl,
  extractLinks,
  extractSitemapLocations,
  filePathForUrl,
  isFileCandidate,
  parseArgs,
  parseBytes,
  parseRobots,
  repairMalformedUrl,
  robotsAllows,
  safeSegment,
} from "../cbi-archive.mjs";

test("parses CLI flags and values", () => {
  assert.deepEqual(parseArgs(["inventory", "--max-pages", "0", "--include-assets", "--no-refresh-pages"]), {
    _: ["inventory"],
    maxPages: "0",
    includeAssets: true,
    refreshPages: false,
  });
});

test("parses human byte limits", () => {
  assert.equal(parseBytes("500M"), 500 * 1024 * 1024);
  assert.equal(parseBytes("1.5GiB"), Math.floor(1.5 * 1024 ** 3));
  assert.equal(parseBytes(undefined), 0);
  assert.throws(() => parseBytes("a lot"));
});

test("enforces byte limits on the streamed response body", async () => {
  const sink = new Writable({ write(chunk, encoding, callback) { callback(); } });
  await assert.rejects(
    pipeline(Readable.from([Buffer.alloc(4), Buffer.alloc(4)]), byteLimitTransform(6), sink),
    /byte cap reached/i,
  );
});

test("applies longest robots rule with Allow winning ties", () => {
  const groups = parseRobots(`
User-agent: *
Allow: /
Disallow: /Sitefinity/
Disallow: /private/*
Allow: /private/public$
`);
  assert.equal(robotsAllows(groups, "https://www.centralbank.ie/about"), true);
  assert.equal(robotsAllows(groups, "https://www.centralbank.ie/Sitefinity/admin"), false);
  assert.equal(robotsAllows(groups, "https://www.centralbank.ie/private/secret"), false);
  assert.equal(robotsAllows(groups, "https://www.centralbank.ie/private/public"), true);
});

test("extracts decoded sitemap locations", () => {
  const xml = `<urlset><url><loc>https://example.test/a&amp;b</loc></url><url><loc>https://example.test/c</loc></url></urlset>`;
  assert.deepEqual(extractSitemapLocations(xml), ["https://example.test/a&b", "https://example.test/c"]);
});

test("extracts and resolves useful HTML links", () => {
  const html = `<a href="/docs/report.pdf?x=1&amp;y=2">Report</a><img src='/img/chart.png'><a href="mailto:x@y.ie">Mail</a>`;
  assert.deepEqual(extractLinks(html, "https://www.centralbank.ie/page"), [
    "https://www.centralbank.ie/docs/report.pdf?x=1&y=2",
    "https://www.centralbank.ie/img/chart.png",
  ]);
});

test("repairs encoded quote pollution in legacy document links", () => {
  const malformed = "https://www.centralbank.ie/publication/consultation-papers/%22/docs/default-source/publications/consultation-papers/cp153/annex.pdf?sfvrsn=123%22%3EAnnex";
  assert.equal(
    repairMalformedUrl(malformed),
    "https://www.centralbank.ie/docs/default-source/publications/consultation-papers/cp153/annex.pdf?sfvrsn=123",
  );
  assert.equal(repairMalformedUrl("https://www.centralbank.ie/docs/report.pdf"), null);
});

test("repairs legacy path prefixes and corrupt revision suffixes", () => {
  assert.equal(
    repairMalformedUrl("https://www.centralbank.ie/news/article/docs/default-source/news/report.pdf?sfvrsn=2%2B"),
    "https://www.centralbank.ie/docs/default-source/news/report.pdf?sfvrsn=2%2B",
  );
  assert.equal(
    repairMalformedUrl("https://www.centralbank.ie/docs/default-source/reports/climate.pdf?sfvrsn=e6df991d_9http%3A%2F%2F"),
    "https://www.centralbank.ie/docs/default-source/reports/climate.pdf?sfvrsn=e6df991d_9",
  );
  assert.equal(
    repairMalformedUrl("https://www.centralbank.ie/docs/default-source/reports/valid.pdf?sfvrsn=1"),
    null,
  );
});

test("selects only approved Central Bank file URLs", () => {
  const types = new Set(["pdf", "csv"]);
  assert.equal(isFileCandidate("https://www.centralbank.ie/docs/a.PDF?x=1", types), true);
  assert.equal(isFileCandidate("https://opendata.centralbank.ie/download/a.csv", types), true);
  assert.equal(isFileCandidate("https://evil.example/a.pdf", types), false);
  assert.equal(isFileCandidate("https://www.centralbank.ie/about", types), false);
});

test("normalizes URLs and produces safe bounded paths", () => {
  assert.equal(canonicalUrl("https://WWW.CENTRALBANK.IE/a.pdf?z=2&a=1#x"), "https://www.centralbank.ie/a.pdf?a=1&z=2");
  assert.equal(safeSegment("CON"), "_CON");
  const result = filePathForUrl("C:\\archive", `https://www.centralbank.ie/${"very-long/".repeat(40)}report.pdf?sfvrsn=1`);
  assert.ok(result.length < 240);
  assert.equal(path.extname(result), ".pdf");
  assert.notEqual(
    filePathForUrl("C:\\archive", "https://www.centralbank.ie/docs/Report.pdf"),
    filePathForUrl("C:\\archive", "https://www.centralbank.ie/docs/report.pdf"),
  );
});
