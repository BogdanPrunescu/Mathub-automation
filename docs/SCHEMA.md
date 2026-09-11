# Canonical extraction schema v0.2.0

v0.2 separates source-wide metadata from per-page evidence and adds extraction-quality provenance.

## Output layout

```text
<manual-output>/
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

## Stable source identity

A page/span reference is meaningful together with:

- manual ID;
- source PDF SHA-256;
- schema version;
- extractor version.

Changing the source PDF hash means a different source artifact, even if its filename is unchanged.

## Canonical page representation

Each page stores:

- PDF page identity and geometry;
- one chosen text layer;
- text quality metrics;
- ordered text blocks;
- ordered lines;
- source spans/words with bounding boxes;
- image assets and bounding boxes;
- warnings.

Text is stored only at span/word level. Block/page text is derived when needed, avoiding the v0.1 duplication that made `document.json` very large.

## Text backends

### `PYMUPDF_NATIVE`

Used when native PDF Unicode extraction passes the quality gate. It retains font and span metadata.

### `POPPLER_PDFTOTEXT`

Used only when the native quality gate is worse and Poppler is available. Poppler's `-bbox-layout` mode supplies deterministic word coordinates. Known Romanian legacy-encoding artefacts are normalized without rewriting content.

Invalid PDF glyph/control codes that cannot be represented in XML are **not guessed**. The visible text contains `�`, while `unresolved_source_codes` preserves the original code (for example `U+001D`). Such spans receive `REQUIRES_VISUAL_CHECK`.

## Quality states

- `GOOD`: machine-readable text is suitable for downstream localization/unitization.
- `SUSPECT`: mostly usable, but some glyphs require checking against the original page.
- `EMPTY`: no machine-readable text was found.
- `UNUSABLE`: do not create SEUs from the extracted text.

The original PDF is always the source authority.
