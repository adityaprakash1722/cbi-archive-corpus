# Publishing setup: decisions, accounts and runbook

Audience: an agent or engineer who needs to change, update or reason about where
this project is published. `STORAGE.md` describes **what** is stored and **how to
read it**. This document covers **why these services**, **how they are wired**,
and **how to operate them**.

Read the decision log before proposing changes. Most of the obvious alternatives
were considered and rejected for concrete reasons, and re-litigating them costs
time.

---

## 1. What this was for

The project lived entirely on one Windows machine: 7.5 GB of crawled source, a
663 MB search index, and a pipeline that only ran there. Three problems followed.

1. **Single point of failure.** A dead drive loses a crawl snapshot that cannot
   be reproduced, because re-running the crawler captures the site as it is now,
   not as it was on 25 August 2026.
2. **No cross-machine access.** Nothing was usable from any other computer.
3. **Agents could not reach it.** Claude Code and Codex work from a checkout.
   They cannot orient in a folder they have no copy of.

The goal was therefore: reachable from anywhere, readable by agents, and free.

---

## 2. Decision log

### Decision 1: split by cost to recreate, not by size

**Chosen:** three tiers. Code and manifests in git. Extracted text as Parquet on
a dataset host. Raw source files in cold object storage.

**Rejected: one repository holding everything.** Git handles a 46 MB Parquet file
badly and a 6.56 GB archive not at all. Cloning would take hours and every agent
session would start with a huge checkout.

**Rejected: syncing the SQLite index.** It is 663 MB and rebuilds from the corpus
in about eight seconds. Storing it is paying to move something you can recreate
faster than you can download it. It is a build product and is gitignored.

### Decision 2: Parquet rather than shipping the Markdown corpus

**Chosen:** convert the corpus to two Parquet files, 47 MB total.

The Markdown corpus is 202 MB across 5,569 files, covering 5,568 unique documents
(one SHA-256 was converted by both the PDF and the Office pipeline). As Parquet it
is 47 MB in two
files, and, more importantly, **queryable over HTTPS without downloading**.
DuckDB reads the file footer, finds which byte ranges hold the columns in the
query, and fetches only those. A query filtering on `authorship` never touches
the 46 MB text column.

**Rejected: a zip or tarball of the Markdown.** Would require a full download
before any question could be answered.

**Rejected: publishing the SQLite index.** Same size problem, and SQLite over
HTTP is not a standard access pattern.

### Decision 3: Hugging Face for the data

**Chosen:** Hugging Face public datasets.

- No hard size limit on free accounts. The documented guidance is under 100,000
  files per repository, under 10,000 per folder, under 200 GB per file. Both
  repos sit far inside all three.
- Free egress.
- Native Parquet support: the dataset viewer renders it, `datasets.load_dataset`
  streams it, DuckDB queries it over HTTPS.
- Individual files addressable by plain URL, which is what makes the raw archive
  usable per-document rather than all-or-nothing.

**Rejected: Cloudflare R2.** This was the original recommendation and it was
changed. R2 requires a payment method on file to activate, even inside the free
10 GB tier. Since the data is public and Hugging Face imposes no such
requirement, R2 added a card, a second account and a new tool for no gain. R2
remains the right answer if this ever needs to be **private**.

**Rejected: OneDrive, Dropbox, Google Drive.** Specifically wrong for this data.
The crawler had to create `_long` directories with truncated hash-suffixed
filenames to survive Windows path length limits. Six thousand files, deeply
nested, with hashed names, is close to the worst case for a desktop sync client:
slow indexing, path length failures and silent partial syncs.

**Rejected: Git LFS.** 1 GB of free storage and 1 GB of monthly bandwidth. The
corpus alone would consume it, and bandwidth burns every time a machine clones.

### Decision 4: GitHub for the code

**Chosen:** a public GitHub repository, 196 files, 10 MB.

Both Claude Code and Codex have first-class GitHub integration, and it is where
anyone looks for code by default.

**Considered: pushing code to Hugging Face instead.** Hugging Face repositories
are ordinary git repositories, so this works, and it would have avoided a second
signup. It was rejected because Hugging Face has three repository types, models,
datasets and spaces, and plain code fits none of them cleanly.

### Decision 5: content-address the raw archive

**Chosen:** store each file at `<sha[0:2]>/<sha[2:4]>/<sha256><ext>`.

The crawler stored one file per URL under a path mirroring the website. Content
addressing gives three things:

1. **Automatic deduplication.** 654 of 6,963 downloads were byte-identical
   content served at more than one URL. As one object each, 7.476 GB becomes
   6.559 GB with no logic.
2. **Self-verifying downloads.** Hash what you got, compare to the filename.
3. **A free join key.** `documents.parquet` already carries `source_sha256`, so
   any search result resolves to its original document with no lookup table.

The 256 top-level directories hold about 25 files each, well under the
10,000-per-folder limit.

**Rejected: uploading in the original URL-shaped layout.** Keeps the 0.92 GB of
duplication and exports the meaningless `_long` paths to everyone else.

### Decision 6: make it public

The Central Bank's re-use terms permit re-use under a licence consistent with
CC BY 4.0, so publishing is allowed. Public also means free on Hugging Face, no
tokens needed to read, and the dataset viewer works for anyone.

The required attribution is in the dataset card and in `ATTRIBUTION.md`:

> Contains Irish Public Sector Information licensed under a Creative Commons
> Attribution 4.0 International (CC BY 4.0) licence.

---

## 3. Accounts and locations

| Service | Account | Holds |
|---|---|---|
| GitHub | `adityaprakash1722` | `cbi-archive-corpus`, the code, 196 files, 10 MB |
| Hugging Face | `aditya487` | `cbi-archive-corpus` dataset, the text, 48 MB |
| Hugging Face | `aditya487` | `cbi-archive-raw` dataset, the source files, 6.56 GB |

Note the two usernames differ. Anything constructing a URL must use the right
one for the right service.

- Code: `https://github.com/adityaprakash1722/cbi-archive-corpus`
- Corpus: `https://huggingface.co/datasets/aditya487/cbi-archive-corpus`
- Raw: `https://huggingface.co/datasets/aditya487/cbi-archive-raw`

---

## 4. Current state

| Item | State |
|---|---|
| GitHub repo | published. First commit `f20eebd`, 196 files, 188,785 lines |
| Hugging Face corpus | published and verified. 9 files, 49.4 MB, commit `3d8b9d8` |
| Hugging Face raw archive | published. 6,309 blobs plus `blob-catalog.csv`, 6.56 GB |

`verify_dataset.py` was run against the live corpus and passed: authorship
3,809 / 1,656 / 103, totals 5,568 documents and 88,782 pages, plus a working
cross-file join query.

Until the raw archive is uploaded, `get_source.py --fetch` will fail. Everything
else works. The blob URLs it prints are correct in advance, because the layout is
deterministic from the hash.

---

## 5. Authentication

### Hugging Face

Authenticated with `hf auth login` using the **browser OAuth device flow**, not a
manually created token. Practical consequences:

- The token carries write scope for the user's own namespace automatically, so
  the common 401 and 403 failure cannot occur.
- It **refreshes itself** when it expires. A hand-made token does not.
- It is stored at `C:\Users\adipr\.cache\huggingface\stored_tokens` and
  `C:\Users\adipr\.cache\huggingface\token`, named `oauth-aditya487`.

Check with `hf auth whoami`. Re-authenticate with `hf auth login`.

### GitHub

GitHub CLI 2.98.0, authenticated with `gh auth login` over HTTPS, with git
credential helper configured during that flow. `git push` needs no further
credentials.

Check with `gh auth status`.

---

## 6. Runbook

### After changing the analysis, scripts or documents

```powershell
git add .
git commit -m "what changed"
git push
```

### After rebuilding the index, so the published corpus reflects it

```powershell
make dataset
hf upload aditya487/cbi-archive-corpus publish/hf . --repo-type=dataset
python publish\verify_dataset.py aditya487
```

`make dataset` regenerates the two Parquet files from the current v3 index.
Always run `verify_dataset.py` afterwards: it catches a stale or half-uploaded
dataset immediately.

### Publishing the raw archive, still outstanding

```powershell
python publish\build_blob_tree.py
hf upload-large-folder aditya487/cbi-archive-raw publish/blobs --repo-type=dataset
hf upload aditya487/cbi-archive-raw publish/blob-catalog.csv blob-catalog.csv --repo-type=dataset
python publish\get_source.py --search "operational resilience" --limit 1 --fetch
```

`upload-large-folder` rather than `upload`: it parallelises and resumes, so an
interrupted 6.56 GB transfer is not a restart.

### Setting up a new machine

```bash
git clone https://github.com/adityaprakash1722/cbi-archive-corpus.git
cd cbi-archive-corpus
python outputs/cbi-research/scripts/bootstrap.py --dataset aditya487/cbi-archive-corpus
```

No Hugging Face account is needed to read. Both datasets are public.

### If the username ever changes

`publish/set-username.py` rewrites the placeholder occurrences across the dataset
card, the root README and the Makefile. It also treats the literal string
`YOUR_USERNAME` as a placeholder, so a mistaken run is recoverable.

---

## 7. Windows environment notes

These cost time during setup and will recur.

**Python is 3.13, from the Microsoft Store.** Store Python installs
pip-provided commands into
`%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts`
and does **not** add that to PATH. Every pip-installed tool, `hf` included, is
invisible until it is added. It has been added permanently to the user PATH.

Note also that `work\pdf-env` is a **Python 3.12** virtual environment built by a
different interpreter. Two Pythons exist on this machine.

**A process reads PATH once, at start.** After installing anything that changes
PATH, open a new terminal. This is why `gh` was not found immediately after
`winget install`.

**`pip install duckdb` gives the library, not a command.** There is no
`duckdb.exe`. The CLI is a separate install, `winget install DuckDB.cli`. The
project's scripts use the Python library and do not need it.

**Do not run git against this folder from the Cowork Linux VM.** It is a FUSE
network mount. A `git add` there was killed by a shell timeout mid-write, leaving
an `index.lock` and 199 half-written objects that had to be deleted. Run git
natively on Windows.

**`.gitattributes` normalises line endings to LF.** The first `git add` prints a
warning per file about CRLF conversion. That is the intended behaviour, and it is
what stops CSVs changing hash between platforms, which matters because hashes are
how this project proves things.

---

## 8. What is deliberately not published

| Item | Size | Reason |
|---|---:|---|
| `cbi-corpus-v3-5568docs.sqlite` | 663 MB | rebuilds in 8 seconds |
| v2 and v1 indices | 1.28 GB | superseded, kept locally for audit history |
| `work/live-index/` | 423 MB | partial build from an interrupted run |
| `corpus/markdown/` | 202 MB | superseded by the Parquet |
| `archive-state.json` | 16 MB | crawler resume state |
| `work/pdf-env`, `pip-cache`, `python-deps` | ~30 MB | build environments |
| `directory_structure.txt` | 3.3 MB | 60,196-line tree dump, stale on arrival |
| A 27.9 MB smoke-test CSV | 27.9 MB | crawler development leftover |

The last two were caught by inspecting what git was about to commit. That check
is worth repeating before any push:

```powershell
git status --short | Measure-Object -Line   # expect low hundreds
git count-objects -vH                       # expect tens of MB
```

Thousands of files or gigabytes means something escaped `.gitignore`.

---

## 9. Cost

Zero, at every service, with no payment method on file anywhere.

| Service | Tier | Limit | Usage |
|---|---|---|---|
| GitHub | free public | soft, around 1 GB | 10 MB |
| Hugging Face | free public | best-effort, no hard cap | 6.6 GB across two datasets |

The one thing that would change this is making the data private, which on Hugging
Face has a much smaller free quota. Cloudflare R2 would then be the right move,
at which point the card requirement becomes unavoidable.

---

## 10. Related documents

- `STORAGE.md`: the technical map. Tiers, schemas, access patterns, rebuild
  commands, integrity model.
- `CLAUDE.md` and `AGENTS.md`: working rules. The authorship discipline and the
  gotchas that cost an hour each.
- `publish/UPLOAD.md`: the step-by-step publishing walkthrough, written for
  someone who has not used these services before.
