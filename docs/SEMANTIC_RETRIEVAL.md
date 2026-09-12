# Semantic lesson retrieval prototype (v0.4)

This is an experimental retrieval layer for locating lesson content when textbook titles and section structures differ too much for lexical matching.

It does **not** create SEUs and does **not** decide final lesson boundaries. It answers a narrower question:

> Which chunks of this manual are semantically closest to the requested lesson concept?

## Model

Default model:

```text
intfloat/multilingual-e5-small
```

The model runs locally through SentenceTransformers. The first run downloads the model from Hugging Face; later runs reuse the local model cache.

For E5-style retrieval, indexed chunks use the `passage:` prefix and lesson queries use the `query:` prefix.

## Retrieval chunks

Chunks are temporary search artifacts, not Source Evidence Units.

Current prototype defaults:

- chunks never cross a PDF page;
- approximately 220 words per chunk;
- 60-word overlap;
- exact start/end line IDs are retained;
- original extracted text is retained;
- a search-only repaired copy is embedded so known legacy Romanian PDF encodings do not damage retrieval;
- TOC chunks are indexed but explicitly marked in results.

## Cache

Each already-extracted manual receives:

```text
<manual-output>/
└── semantic_index/
    ├── meta.json
    ├── chunks.json
    └── vectors.npy
```

The index is automatically rebuilt if the source PDF hash, model, chunk size, overlap, or semantic-index version changes.

Search results are written to:

```text
<manual-output>/
└── semantic_search/
    ├── <query-slug>.json
    └── <query-slug>.txt
```

## Installation

From the repository virtual environment:

```powershell
python -m pip install -e ".[dev,semantic]"
```

The semantic extra installs NumPy, SentenceTransformers, and its local inference dependencies.

## Run

Example:

```powershell
mathub-semantic ".\outputs\manual-corint" `
  --lesson "Legi de compoziție" `
  --top-k 15
```

Repeat for each manual. On the first run for a manual, the command builds the vector index. Later lesson queries reuse it.

Useful options:

```text
--top-k 15
--chunk-words 220
--overlap-words 60
--batch-size 32
--model intfloat/multilingual-e5-small
--rebuild
```

If memory is tight, lower `--batch-size` to 8 or 16.

## What to inspect in the experiment

For each manual and the same requested lesson, inspect the top 10–15 matches and answer:

1. Is the actual lesson content in the top results?
2. Roughly what rank does the first genuinely relevant body chunk have?
3. Do several relevant hits cluster on neighboring pages?
4. Are TOC entries dominating the results, or is body content also retrieved strongly?
5. Are exercises mentioning the concept outranking the explanatory/theory section?
6. Does the model still work when the manual uses a different title, singular/plural form, or alternative wording?

Do not interpret a cosine score as a universal confidence threshold. Scores are model-relative and useful primarily for ranking.

## Experimental success criterion

Before integrating embeddings into Stage B, the prototype should retrieve the correct lesson region near the top across all four MVP manuals without manual-specific title rules.
