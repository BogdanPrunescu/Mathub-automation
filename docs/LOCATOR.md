# Deterministic lesson locator v0.3

The locator consumes a v0.2+ extracted-manual directory. It never reparses the original PDF.

## Inputs

- `manifest.json`
- page JSON files
- requested lesson title

## Progressive cheap path

1. Normalize Romanian Unicode and create a diacritic-insensitive matching form.
2. Search individual extracted lines.
3. Score lexical title similarity.
4. Add heading evidence:
   - explicit section numbering;
   - short line;
   - upper-page position;
   - line height relative to page body.
5. Penalize likely TOC pages.
6. Use TOC title hits as supporting evidence for body candidates.
7. Select the strongest body anchor.
8. If the anchor is numbered, stop immediately before the next same-level peer heading.
9. Keep neighboring context pages separately.
10. Return an explicit confidence/escalation state.

## Boundary semantics

`target_region.end_exclusive_ref` points to the next peer heading. The target content ends
immediately before that line. The page containing the peer heading may therefore appear in the
coarse page range while the precise line reference remains exclusive.

## Trust behavior

The locator must never silently invent a region. Weak or ambiguous results remain
`FOUND_LOW_CONFIDENCE`, `MULTIPLE_CANDIDATES`, or `NOT_FOUND`.

Localization is broad evidence capture. It does not decide which evidence ultimately enters a CCU.
