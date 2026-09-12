# Changelog

## v0.3.0

- Added `mathub-locate` deterministic lesson-localization CLI.
- Added diacritic-insensitive title normalization and lexical candidate search.
- Added structural heading scoring from numbering, line geometry, page position and line length.
- Added heuristic TOC-page detection; TOC hits support but do not become body anchors.
- Added numbered heading hierarchy and `NEXT_PEER_HEADING` end-boundary detection.
- Added one-page neighboring context preservation by default.
- Added explicit localization outcomes:
  - `FOUND_HIGH_CONFIDENCE`
  - `FOUND_LOW_CONFIDENCE`
  - `MULTIPLE_CANDIDATES`
  - `NOT_FOUND`
- Added machine-readable localization JSON plus human-readable `.txt` report.
- Added locator tests including TOC-vs-body disambiguation and peer-heading boundaries.
- No embeddings, LLMs, vector DB, OCR or API calls were added.

## v0.2.0

- Replaced the single huge `document.json` with `manifest.json` plus one compact JSON file per page.
- Added deterministic page-level text quality assessment.
- Added progressive extraction:
  1. PyMuPDF native text first.
  2. Poppler `pdftotext -bbox-layout` only when native extraction is suspect/unusable.
- Added deterministic repair of common legacy Romanian encoding artefacts.
- Preserved unresolved PDF control/symbol glyphs as explicit `�` + source-code provenance instead of guessing them.
- Added extraction backend/version provenance.
- Added human-readable `report.txt` and machine-readable `report.json`.
- Added `--backend auto|native|poppler` and `--pdftotext PATH`.
- Kept embedded images as content-addressed assets.
- Reduced the tested ALL manual output from roughly 114 MB in v0.1 to roughly 23 MB in v0.2 while making it page-addressable.
- Added tests for quality gating, Romanian normalization, unresolved glyph preservation, and page-based extraction.

### Integration test on the real ALL manual

The uploaded 257-page ALL manual was processed successfully with:

- overall status: `USABLE_WITH_WARNINGS`
- 222 pages `GOOD`
- 33 pages `SUSPECT`
- 2 pages `EMPTY`
- 0 pages `UNUSABLE`
- Poppler selected for 254 pages
- PyMuPDF native selected for 3 pages

The remaining warnings are mostly unresolved mathematical/symbol glyphs. They are intentionally surfaced for later visual validation rather than guessed.
