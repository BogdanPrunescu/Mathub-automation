# v0.3 integration test — ALL manual

Test source: `manual_xii_M2_Editura ALL.pdf` (257 pages)

Command:

```powershell
mathub-locate ".\outputs\manual-all" --lesson "Legi de compoziție"
```

Observed result:

```text
Status: FOUND_HIGH_CONFIDENCE
Anchor: p.6 — 1.1. Legi de compoziţie
Score: 1.000
End: before p.9 — 1.2. Proprietăţi ale legilor de compoziţie
```

Additional evidence:

- TOC page detection found pages 3 and 4.
- TOC page 3 independently contains `1.1. Legi de compoziţie ... 6`.
- The body heading on page 6 was chosen over the TOC hit.
- Boundary was inferred from numbered hierarchy: `1.1` → next peer `1.2`.
- One page of context before the target is retained (`p0005`).
- The peer-heading page is retained as after-boundary context (`p0009`).
- No embeddings, LLM calls, vector database, OCR, or API calls were used.

This is a localization/evidence-capture result only. It does not decide final lesson inclusion.
