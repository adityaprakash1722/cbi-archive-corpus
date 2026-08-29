# Central Bank of Ireland Public Archive

This is a zero-dependency Node.js CLI for inventorying and downloading public material from the Central Bank of Ireland. It has two collection lanes:

1. The official CKAN Open Data API for structured CSV datasets.
2. The official sitemap plus public page links for PDFs, spreadsheets, Word files, ZIPs, and other documents.

The tool is resumable, rate-limited, robots-aware, bounded by optional page/file/byte caps, and produces CSV and JSONL manifests with checksums and source metadata. It also preserves each fetched HTML source page by content hash, unless `--no-archive-pages` is set. It deliberately stays away from login portals and non-public systems.

## Requirements

- Node.js 20 or newer
- Enough free disk space for your selected scope

No `npm install` is needed.

## Source snapshot

The live probe on 25 August 2026 found 11,371 URLs in the main sitemap and 39 Open Data datasets with 71 CSV resources. CKAN reported a combined 162.13 MiB for those resources, but at least one live file was much larger than its catalogue value, so treat published sizes as estimates. A five-page document smoke crawl discovered four linked PDFs.

## Recommended workflow

Run a three-request probe first:

```powershell
node .\cbi-archive.mjs probe --contact "you@example.com"
```

Download the complete Open Data Portal. This is the highest-value, smallest first step:

```powershell
node .\cbi-archive.mjs inventory --scope opendata --out .\cbi-data --contact "you@example.com"
node .\cbi-archive.mjs download --only opendata --out .\cbi-data --contact "you@example.com"
```

Sample 100 sitemap pages to validate document discovery:

```powershell
node .\cbi-archive.mjs inventory --scope documents --max-pages 100 --out .\cbi-data --contact "you@example.com"
```

Inventory every sitemap page. At the default one request per second, 11,000+ pages takes a little over three hours before retries:

```powershell
node .\cbi-archive.mjs inventory --scope all --max-pages 0 --delay-ms 1000 --out .\cbi-data --contact "you@example.com"
```

Inspect `cbi-data\manifests\summary.json` and `files.csv`, then download everything discovered. Catalogue byte sizes are estimates and can be stale; the downloader enforces `--max-bytes` against the actual HTTP response stream:

```powershell
node .\cbi-archive.mjs download --out .\cbi-data --contact "you@example.com"
```

To put a hard ceiling on a run:

```powershell
node .\cbi-archive.mjs download --out .\cbi-data --max-files 500 --max-bytes 10G --contact "you@example.com"
```

Re-running either command resumes from `archive-state.json`. Download state is checkpointed at least once per minute; files completed after the latest checkpoint are detected on restart. Failed downloads are retained for inspection and can be retried explicitly:

```powershell
node .\cbi-archive.mjs download --out .\cbi-data --retry-failed --contact "you@example.com"
```

If old pages contain quote-corrupted document links, repair them before the retry pass:

```powershell
node .\cbi-archive.mjs repair --out .\cbi-data
```

## Useful scopes

- `--scope opendata`: CKAN dataset/resource metadata only; no page crawl.
- `--scope documents`: sitemap crawl for linked files.
- `--scope all`: both lanes.
- `--path-prefix /publications`: restrict a page crawl to one section.
- `--types pdf,csv,xlsx,zip`: override the document extensions.
- `--include-assets`: also discover images, media, stylesheets, scripts, and fonts. This can increase the archive substantially and is not required for a research corpus.

`--max-pages 0`, `--max-files 0`, and `--max-bytes 0` mean unlimited. The inventory default is intentionally a 100-page sample; download limits default to unlimited because `download` is an explicit second command.

## Output layout

```text
cbi-data/
  archive-state.json             resumable machine state
  metadata/ckan-packages.json    complete CKAN package metadata
  manifests/files.csv            spreadsheet-friendly inventory
  manifests/files.jsonl          full machine-readable inventory
  manifests/failed-urls.csv      source links that returned final errors
  manifests/page-snapshots.csv   page URL/status plus immutable HTML hash/path
  manifests/summary.json         counts and byte totals
  pages/<sha-prefix>/<sha>.html  content-addressed source-page context
  files/<host>/...                downloaded files, preserving URL paths
  duplicate-alias-files/         recoverable duplicate copies from URL repair
```

Every completed file gets a SHA-256 checksum, HTTP content type, ETag, last-modified value, local path, dataset/resource metadata when available, and referring page(s). Local filenames contain a short URL hash so query-string versions and paths differing only by letter case do not overwrite one another on Windows. Very long URL paths are shortened deterministically for Windows compatibility.

The August 2026 crawl predates HTML-body preservation. Its
`page-snapshots.csv` therefore retains 11,371 page URLs, statuses and fetch
times, but its HTML hash/path fields are empty: the original wording cannot be
recovered retroactively. A refreshed or future crawl writes the bodies by
default; `publish/build_blob_tree.py` includes them under `page-context/` in the
raw tier without counting them as source documents.

## Operational notes

- Keep the default delay or make it slower. Do not raise request concurrency against the public site without written permission.
- Use a real contact email or URL in `--contact` for a long crawl.
- `robots.txt` is rechecked before download. If it cannot be checked and there is no cached copy, downloading stops.
- HTTP 429 and transient server errors use exponential backoff and `Retry-After` where supplied.
- Partial downloads use `.part` files and resume with HTTP Range requests when the server supports them. A byte-capped run pauses cleanly rather than marking the file failed.
- The crawler only follows files on `centralbank.ie`, `www.centralbank.ie`, and `opendata.centralbank.ie`; it does not archive external sites.
- Open Data resource requests may follow CKAN's redirect to the Bank's exact public file bucket, `cbi-prod-filestore-public.s3.amazonaws.com`. Other external redirects are refused.
- Publicly accessible does not mean attribution-free. Keep the manifests and follow the licence notes in [LEGAL.md](./LEGAL.md).

## Tests

```powershell
npm test
```
