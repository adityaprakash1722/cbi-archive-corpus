# Publishing this, for someone who has not used these tools before

Everything runs **on Windows, in PowerShell**, from the project folder. Not
inside the Cowork VM: that VM has no internet access, so nothing can be pushed
from there.

```powershell
cd C:\Users\adipr\Documents\Codex\2026-08-25\want-to-mass-download-everything-from
```

You already have Python 3.12 on Windows. I can tell because the pipeline built a
virtual environment at `work\pdf-env` containing `cp312-win_amd64` binaries,
which only a real Python 3.12 install produces.

---

## What these two services are

**Hugging Face** is a hosting platform for datasets and machine-learning models.
Think of it as GitHub for data. Each dataset lives at a URL like
`huggingface.co/datasets/yourname/cbi-archive-corpus`, is versioned, is free for
public data, and is designed for files far larger than git handles comfortably.
It is where the 47 MB corpus goes.

**GitHub** hosts code. It is where the pipeline, the manifests and the analysis
go: 238 repository files, about 13 MB before generated data artifacts.

They are separate because the two kinds of content have different needs. Code is
small, changes constantly, and benefits from line-by-line diffs. A 46 MB Parquet
file is none of those things.

---

# Part 1: Hugging Face

## Step 1. Create an account

Go to https://huggingface.co/join. Email, username, password. The username you
pick becomes part of your dataset's permanent URL, so pick one you are happy to
see in public.

Free. No card. No paid tier needed for anything here.

## Step 2. Authenticate

The current CLI supports the browser OAuth device flow, which issues a
refreshable credential with write access to your own namespace. Prefer that to
copying a long-lived token into a terminal.

## Step 3. Install the command line tool

```powershell
pip install -U huggingface_hub
```

Check it worked:

```powershell
hf version
```

You should see a version number. If PowerShell says `hf` is not recognised, your
installed version is older and the command is `huggingface-cli` instead. Use
that name everywhere below. If `pip` itself is not recognised, use
`python -m pip install -U huggingface_hub`.

## Step 4. Log in

```powershell
hf auth login
```

Follow the browser/device-flow prompt and approve the sign-in. Confirm the
identity before uploading with `hf auth whoami`.

Success looks like: `Login successful`.

## Step 5. Put your username into the example commands

The dataset card contains example queries with a `<user>` placeholder. Those
examples are the first thing anyone reads, so a broken one is worse than none.

```powershell
python publish\set-username.py YOUR_USERNAME
```

Just the username, not `username/dataset`. It prints which files it changed and
the URL your dataset will live at.

## Step 6. Upload

```powershell
hf upload YOUR_USERNAME/cbi-archive-corpus publish/hf . --repo-type=dataset
```

Reading that command: upload to a repository called `cbi-archive-corpus` under
your account, take the contents of the local `publish/hf` folder, put them at the
root of the repository (`.`), and make it a dataset rather than a model.

The repository is created automatically. You do not need to make it first.

It uploads 10 files totalling about 48 MB. The 46.8 MB `pages.parquet` is most of it.
Expect a progress bar and under a minute on a normal connection.

## Step 7. Check it worked

Open `https://huggingface.co/datasets/YOUR_USERNAME/cbi-archive-corpus`.

You should see your dataset card rendered, and a **Data Studio** viewer showing a
table of pages you can scroll and search in the browser. The viewer appears
automatically because the card's frontmatter tells Hugging Face where the Parquet
files are. It can take a minute or two to build the first time.

Now the real test, that anyone anywhere can query it without downloading it:

```powershell
pip install duckdb
duckdb -c "SELECT authorship, count(*) FROM 'https://huggingface.co/datasets/YOUR_USERNAME/cbi-archive-corpus/resolve/main/data/documents.parquet' GROUP BY 1"
```

Expect exactly:

```
central-bank   3807
stakeholder    1671
mixed             1
unresolved       89
```

If you get those three numbers, the corpus is live and reachable from any
machine on earth. That query downloaded only the one column it needed, not the
file.

---

# Part 2: GitHub

## Step 1. Install git, if you do not have it

```powershell
git --version
```

If that fails: `winget install Git.Git`, then close and reopen PowerShell.

## Step 2. Tell git who you are

Only needed once per machine.

```powershell
git config --global user.name "Adi Prakash"
git config --global user.email "aditya.prakash1722@gmail.com"
```

## Step 3. Check what would be committed

This matters. The folder contains 7.5 GB of downloaded PDFs that must not go to
GitHub. A `.gitignore` file already excludes them, but verify before pushing
rather than after.

```powershell
git init
git add .
git status --short | Measure-Object -Line
```

Expect roughly **238 files** in a clean release candidate. If you see thousands, stop: something
slipped past the ignore rules.

```powershell
git count-objects -vH
```

Look at `size-pack`. Expect tens of megabytes. If it says gigabytes, stop.

## Step 4. Commit

```powershell
git commit -m "CBI archive corpus: crawler, pipeline, manifests and analysis"
```

## Step 5. Push

Easiest way, using GitHub's own command line tool:

```powershell
winget install GitHub.cli
gh auth login
gh repo create cbi-archive-corpus --public --source=. --push
```

`gh auth login` opens a browser to confirm. Answer GitHub.com, HTTPS, yes to
authenticate git.

If you would rather not install `gh`: create the repository at
https://github.com/new, name it `cbi-archive-corpus`, add no README or
`.gitignore` since you already have both, then:

```powershell
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/cbi-archive-corpus.git
git branch -M main
git push -u origin main
```

---

# Part 3: What you can now do

On any machine, with nothing installed but Python:

```powershell
git clone https://github.com/YOUR_GITHUB_USERNAME/cbi-archive-corpus.git
cd cbi-archive-corpus
python outputs/cbi-research/scripts/bootstrap.py --dataset YOUR_HF_USERNAME/cbi-archive-corpus
```

That pulls the 47 MB corpus. Claude Code or Codex opened in that folder reads
`CLAUDE.md` or `AGENTS.md` and knows the layout, which index is current, and the
five mistakes that would otherwise cost an hour each.

Or query it with no clone and no download at all, which is the part worth
remembering:

```sql
SELECT d.title, p.page_number, substr(p.text, 1, 300)
FROM  'https://huggingface.co/datasets/YOU/cbi-archive-corpus/resolve/main/data/pages.parquet' p
JOIN  'https://huggingface.co/datasets/YOU/cbi-archive-corpus/resolve/main/data/documents.parquet' d
  USING (document_id)
WHERE d.authorship = 'central-bank'
  AND lower(p.text) LIKE '%operational resilience%'
LIMIT 20;
```

---

# Things that commonly go wrong

**`hf` is not recognised.** Older `huggingface_hub`. Use `huggingface-cli`
instead, or upgrade with `pip install -U huggingface_hub`.

**401 or 403 on upload.** Run `hf auth whoami`. If the account is wrong or the
OAuth credential is stale, run `hf auth login --force` and approve the browser
flow again.

**The dataset page shows files but no table viewer.** Give it a few minutes.
If it still does not appear, the `configs:` block at the top of
`publish/hf/README.md` is what points the viewer at the Parquet files, so check
that survived the username edit.

**`git add .` seems to hang.** It is walking a folder containing thousands of
files. Let it finish once. It is fast afterwards.

**Push rejected, file too large.** Something got past `.gitignore`. Run
`git rm -r --cached .` then `git add .` to re-apply the rules, and check
`git status --short | Measure-Object -Line` again before recommitting.

---

# Part 4: The raw archive, 6.56 GB

This puts the original PDFs and spreadsheets somewhere you can reach them from
any machine, which the Parquet corpus cannot do because it holds only the text.

**Why Hugging Face rather than Cloudflare R2.** R2 requires a payment method on
file to activate, even inside its free 10 GB tier. Hugging Face public datasets
have no hard size limit on a free account: the documented guidance is fewer than
100,000 files per repository, fewer than 10,000 per folder, and under 200 GB per
file. 6,309 files at 6.56 GB sits well inside all three, on the account you
already have.

## Step 1. Lay the files out by content hash

```powershell
python publish\build_blob_tree.py
```

This creates `publish\blobs\<ab>\<cd>\<sha256>.pdf` for every unique file, using
**hard links**, which are extra directory entries pointing at bytes already on
disk rather than copies. It therefore costs essentially no additional space.

It also collapses the 654 files that are byte-identical content served at more
than one URL, taking 7.48 GB down to 6.56 GB before anything is uploaded. Both
`blob-catalog.csv` and `blob-summary.json` are written alongside, recording every
URL that served each hash so the provenance survives the rename.

Expect roughly 6,309 files across 256 top-level directories, about 25 files in
each, which keeps every folder far below the 10,000-file limit.

## Step 2. Upload

```powershell
hf upload aditya487/cbi-archive-raw publish/blobs . --repo-type=dataset
```

**Note the trailing `.`, and note what it does.** The third argument is
`PATH_IN_REPO`. Omitting it uploads the *contents* of `publish/blobs` to the
repository root, which is what happened on the first run: the files live at
`<ab>/<cd>/<sha256><ext>`, not under a `blobs/` prefix. That layout is now the
standard one, and `get_source.py`, `blob-catalog.csv` and every document agree
on it. The explicit `.` says the same thing on purpose rather than by accident.

Use `hf upload`, not `hf upload-large-folder`. The latter is deprecated as of
CLI 1.28 and prints so; `hf upload` is resumable and handles thousands of files.

This is a real 6.56 GB upload. At 20 Mbps that is around 45 minutes, at 50 Mbps
around 18, at 100 Mbps around 9. Start it and leave it.

Then add the catalogue so the repository describes itself:

```powershell
hf upload aditya487/cbi-archive-raw publish/blob-catalog.csv blob-catalog.csv --repo-type=dataset
hf upload aditya487/cbi-archive-raw publish/blob-summary.json blob-summary.json --repo-type=dataset
```

## Step 3. Test the whole loop

```powershell
python publish\get_source.py --search "operational resilience" --authorship central-bank --limit 3
python publish\get_source.py --search "operational resilience" --authorship central-bank --limit 1 --fetch
```

The first lists matching documents and prints the blob URL for each. The second
downloads an actual original PDF, from a search of the text, without you knowing
in advance where the file was.
