# Canonical extraction schema v0.1.0

The JSON output is a deterministic source representation, not a semantic educational representation.

## Top level

- `schema_version`
- `extractor`
- `source`
- `pdf_metadata`
- `toc`
- `pages`

## Source

- `manual_id`: stable logical identifier supplied by the caller
- `filename`
- `sha256`
- `size_bytes`

## Page

Each page has:

- `id`: `p0001`, `p0002`, ...
- `pdf_page_index`: 0-based
- `pdf_page_number`: 1-based
- `page_label`: PDF page label if defined
- `width`
- `height`
- `rotation`
- `text_char_count`
- `plain_text_reading_order`
- `blocks`
- `warnings`

## Text block

- `id`: e.g. `p0042-b0007`
- `type`: `text`
- `source_block_number`: PyMuPDF block number
- `raw_order_index`: order in the PDF text representation
- `reading_order_index`: PyMuPDF's top-left reading-order result
- `bbox`
- `text`: canonical extracted block text
- `search_text`: separate normalized text for cheap search
- `lines`

## Line

- `id`
- `index`
- `bbox`
- `writing_mode`
- `direction`
- `text`
- `spans`

## Span

- `id`
- `index`
- `text`
- `bbox`
- `origin`
- `font`
- `size`
- `flags`
- `flag_names`
- `color`
- `ascender`
- `descender`

A later semantic stage can form SEUs by referencing one or more span / line / block IDs without copying or inventing source text.

## Image block

Embedded image bytes are written once to `assets/` under a SHA-256-derived filename. The JSON stores:

- source location;
- bbox;
- metadata;
- `asset_sha256`;
- `asset_path`.

## Stable-reference rule

A reference into the extracted representation is meaningful together with:

- source PDF SHA-256;
- schema version;
- extractor version.

If the source PDF changes, it is a different source artifact even if the filename is unchanged.
