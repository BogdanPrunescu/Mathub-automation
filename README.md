# Mathub Material Extractor

Deterministic first-stage ingestion for the Mathub Automation of Material Extraction project.

The tool reads a selectable-text PDF and creates a source-faithful JSON representation containing:

- document metadata and SHA-256;
- PDF table of contents where available;
- page identity, page labels, dimensions, and rotation;
- text blocks;
- lines and spans;
- bounding boxes and font metadata;
- both raw PDF block order and a derived reading-order index;
- extracted image assets and their page positions;
- canonical text plus a separate normalized search form.

It deliberately does **not**:

- create Source Evidence Units;
- classify definitions / properties / examples;
- rewrite text;
- use an LLM;
- perform OCR;
- synthesize lesson content;
- infer mathematical meaning.

That separation is intentional: this repository establishes the deterministic source layer that later semantic stages can reference.

## Windows + VS Code setup

### 1. Install Python

Use a 64-bit Python installation from python.org. Python 3.12 or 3.13 is recommended for this project.

Verify from PowerShell:

```powershell
py --version
```

### 2. Open the repository in VS Code

```powershell
cd path\to\mathub-material-extractor
code .
```

Install Microsoft's **Python** extension if VS Code does not already have it.

### 3. Create a virtual environment

From the VS Code terminal:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell refuses to run the activation script, run once:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again.

### 4. Install the project

```powershell
python -m pip install -e ".[dev]"
```

### 5. Select the interpreter in VS Code

Press `Ctrl+Shift+P` -> **Python: Select Interpreter** -> choose:

```text
.venv\Scripts\python.exe
```

### 6. Run tests

```powershell
pytest
```

### 7. Extract a manual

```powershell
mathub-extract "C:\path\manual.pdf" `
  --manual-id manual-a `
  --output "C:\path\outputs\manual-a"
```

The result is:

```text
outputs/
└── manual-a/
    ├── document.json
    └── assets/
        └── image-<sha256>.<ext>
```

You can also run the module directly:

```powershell
python -m mathub_extractor.cli "C:\path\manual.pdf" --manual-id manual-a --output ".\outputs\manual-a"
```

## Design invariants

1. `text` is the canonical PyMuPDF-extracted text. Never silently normalize it in place.
2. `search_text` is derived and disposable. It is not source truth.
3. All geometry is retained as PDF coordinates.
4. Original block number and derived reading order are both stored.
5. Image bytes are stored as separate assets rather than embedded in JSON.
6. Every run records source file hash, extractor version, schema version, and PyMuPDF version.
7. Semantic classification belongs in a later stage.

## Current limitation

This v0.1 captures text and embedded image blocks. It does not serialize arbitrary PDF vector drawings as educational evidence. Before trusting a lesson region containing important graphs or vector-only mathematics, that case must be handled explicitly.
