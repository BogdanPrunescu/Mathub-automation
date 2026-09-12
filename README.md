# Mathub Material Extractor v0.2

Deterministic source ingestion for the Mathub Automation of Material Extraction project.

v0.2 fixes the main problem found on the first real ALL manual: a PDF may look/select normally while its native Unicode text map is unusable. The extractor now uses progressive extraction depth:

```text
PyMuPDF native extraction
        ↓
quality gate
        ↓
if needed: Poppler pdftotext fallback (still deterministic, no OCR)
        ↓
quality gate + unresolved-glyph warnings
        ↓
page-based canonical source representation
```

There are **no LLM/API calls** and **no OCR** in v0.2.

## Why Poppler is included as a fallback

The ALL textbook tested during development contains old custom PDF fonts. PyMuPDF correctly recovers geometry, but the native text map contains control characters. Poppler is able to decode most of that legacy text deterministically. v0.2 uses Poppler only when the cheaper/native text quality gate says it is needed.

Known Romanian legacy forms such as `compoziþie`, `Sã`, and `cunoºtinþã` are converted deterministically to `compoziţie`, `Să`, and `cunoştinţă`.

Mathematical/symbol glyphs that remain unresolved are never guessed; they are marked for visual checking.

# Windows + VS Code setup

## 1. Python

Python 3.12 is recommended.

```powershell
py --version
```

Create and activate a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

In VS Code: `Ctrl+Shift+P` -> `Python: Select Interpreter` -> choose `.venv\Scripts\python.exe`.

## 2. Install Poppler on Windows

Poppler is needed for manuals whose native PDF text map fails the quality gate.

The easiest Windows Package Manager installation is:

```powershell
winget install --id oschwartz10612.Poppler -e
```

Open a **new terminal** afterward and verify:

```powershell
pdftotext -v
```

If `pdftotext` is not on PATH, you can still use v0.2 by passing its full executable path:

```powershell
mathub-extract "C:\Manuals\manual.pdf" `
  --manual-id manual-all `
  --output ".\outputs\manual-all" `
  --pdftotext "C:\path\to\pdftotext.exe"
```

## 3. Run tests

```powershell
pytest
```

## 4. Process a manual

```powershell
mathub-extract "C:\Manuals\manual_xii_M2_Editura ALL.pdf" `
  --manual-id manual-all `
  --output ".\outputs\manual-all"
```

The default backend policy is `auto`:

- use PyMuPDF native text when it is clean;
- invoke Poppler only if native extraction is suspect/unusable;
- choose the better page representation;
- preserve unresolved glyphs as warnings rather than inventing them.

For debugging you can force one backend:

```powershell
mathub-extract "C:\Manuals\manual.pdf" --manual-id test --output ".\outputs\test" --backend native
mathub-extract "C:\Manuals\manual.pdf" --manual-id test --output ".\outputs\test" --backend poppler
```

# Output

```text
outputs/manual-all/
├── manifest.json
├── report.json
├── report.txt
├── pages/
│   ├── p0001.json
│   ├── p0002.json
│   └── ...
└── assets/
    └── image-<sha256>.<ext>
```

Start by reading `report.txt`, **not the JSON**. It tells you whether the manual is usable and which fallback was used.

The page JSON is machine-facing evidence for later lesson localization and SEU creation.

# v0.2 invariants

1. The original PDF is always authoritative.
2. No semantic rewriting occurs during ingestion.
3. Native text is preferred when reliable.
4. More expensive/complex fallback runs only where the native path fails.
5. Unresolved symbols are surfaced, not guessed.
6. Provenance includes source PDF hash, page coordinates, backend, backend version, and extraction quality.
7. Text is stored once at span/word level to avoid v0.1's massive duplication.
8. Images remain separate content-addressed assets.
9. SEUs, alignment, lesson synthesis, embeddings, LLMs, and OCR remain outside this repository stage.


## v0.3: deterministic lesson localization

After extracting a manual once, locate a lesson without rereading the PDF and without any model/API call:

```powershell
mathub-locate ".\outputs\manual-all" `
  --lesson "Legi de compoziție"
```

The locator performs:

1. Romanian/diacritic-insensitive lexical normalization;
2. line-level title matching;
3. heading-likeness scoring using numbering, geometry, length and page position;
4. TOC-page detection and TOC support without selecting the TOC as lesson evidence;
5. numbered heading hierarchy analysis;
6. exclusive boundary detection at the next peer heading;
7. one-page context preservation by default;
8. explicit `FOUND_HIGH_CONFIDENCE`, `FOUND_LOW_CONFIDENCE`,
   `MULTIPLE_CANDIDATES`, or `NOT_FOUND` outcomes.

Default output:

```text
<manual-output>/
└── locations/
    ├── legi-de-compozitie.json
    └── legi-de-compozitie.txt
```

The localization result is an evidence-capture proposal, not a final lesson-inclusion decision.

No embeddings, LLMs, vector database or API calls are used by v0.3 localization.
