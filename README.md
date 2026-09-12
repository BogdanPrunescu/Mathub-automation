# Mathub Material Extractor

Source-grounded PDF ingestion and lesson localization for the Mathub Automation of Material Extraction project.

Current prototype layers:

```text
PDF
 ↓
deterministic ingestion (v0.2 schema)
 ↓
canonical page JSON + provenance
 ↓
lexical/structural locator (v0.3.2, conservative)
 ↓
local embedding retrieval prototype (v0.4)
```

The original PDF remains authoritative. Retrieval and localization artifacts never rewrite the canonical extracted source.

## Windows + VS Code setup

Python 3.12 is recommended.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

In VS Code: `Ctrl+Shift+P` -> `Python: Select Interpreter` -> choose `.venv\Scripts\python.exe`.

### Poppler

Poppler is used when a manual's native PDF text layer fails the deterministic quality gate.

```powershell
winget install --id oschwartz10612.Poppler -e
```

Open a new terminal and verify:

```powershell
pdftotext -v
```

## Run tests

```powershell
pytest
```

GitHub Actions also runs the test suite on Windows and Ubuntu for every push.

# Deterministic ingestion

```powershell
mathub-extract "C:\Manuals\manual.pdf" `
  --manual-id manual-example `
  --output ".\outputs\manual-example"
```

The default extraction policy is:

```text
PyMuPDF native extraction
        ↓
quality gate
        ↓
if needed: Poppler pdftotext fallback
        ↓
quality gate + unresolved-glyph warnings
        ↓
page-based canonical source representation
```

There are no LLM/API calls and no OCR in ingestion. Known deterministic Romanian legacy-encoding forms are repaired where safe; unresolved mathematical/symbol glyphs are surfaced rather than guessed.

Output:

```text
outputs/manual-example/
├── manifest.json
├── report.json
├── report.txt
├── pages/
│   ├── p0001.json
│   └── ...
└── assets/
```

# Deterministic locator (v0.3.2)

```powershell
mathub-locate ".\outputs\manual-example" `
  --lesson "Legi de compoziție"
```

The deterministic locator uses lexical, layout, numbering and TOC signals. It only creates an automatic evidence region when deterministic localization is high confidence. Otherwise it returns `NEEDS_SEMANTIC_LOCALIZATION` rather than inventing a region.

This layer remains useful as structural evidence, but it is no longer expected to solve every variation in lesson naming across textbooks.

# Semantic retrieval prototype (v0.4)

The semantic prototype uses a local multilingual embedding model to retrieve textbook content by meaning rather than exact lesson-title wording.

Install the optional dependencies:

```powershell
python -m pip install -e ".[dev,semantic]"
```

Default model:

```text
intfloat/multilingual-e5-small
```

The first semantic run downloads the model from Hugging Face. Later runs reuse the local model cache.

Run a query:

```powershell
mathub-semantic ".\outputs\manual-example" `
  --lesson "Legi de compoziție" `
  --top-k 15
```

The first query for a manual builds and caches a vector index. Future queries reuse it.

Semantic cache:

```text
<manual-output>/semantic_index/
├── meta.json
├── chunks.json
└── vectors.npy
```

Query results:

```text
<manual-output>/semantic_search/
├── <query-slug>.json
└── <query-slug>.txt
```

Current retrieval chunks:

- never cross a PDF page;
- target ~220 words;
- overlap by 60 words;
- retain exact start/end source line IDs;
- retain original extracted text;
- embed a separate search-repaired copy for legacy Romanian PDF encodings;
- mark TOC chunks explicitly.

Retrieval chunks are temporary search artifacts, **not Source Evidence Units**. Cosine scores are ranking signals, not universal confidence thresholds.

See `docs/SEMANTIC_RETRIEVAL.md` for the experiment protocol.

# Core invariants

1. The original PDF is always authoritative.
2. Canonical extracted text is never semantically rewritten.
3. Provenance remains attached to source evidence.
4. Retrieval/index artifacts are disposable and reproducible from canonical extraction.
5. Unresolved uncertainty is surfaced instead of silently invented.
6. Semantic retrieval locates candidate evidence; it does not approve lesson content or replace human review.
