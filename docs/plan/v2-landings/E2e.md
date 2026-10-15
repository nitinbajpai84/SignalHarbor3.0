# E2e · Synthetic manager statements

**Built** 9 Oct 2026. Card done: 6 PDFs, 6 expected specs, 6 tests, deterministic.

## What changed

Created the synthetic test fixture for manager statement extraction (E2b card):
- **PDFs**: Fund A (estimate and amended), Fund B, capital call, scanned document, prompt-injection test
- **Expected fields**: JSON specs for each PDF with field_name, value_text, value_numeric, currency, page, status_label
- **Tests**: 6 assertions covering generation, structure, values, and injection safety

## Files touched

| File | Purpose |
|------|---------|
| `tools/make_e2_statements.py` | Generate 6 deterministic PDFs and their expected extraction specs |
| `tests/v1/fixtures/e2/*.pdf` | 6 synthetic manager statements for Evergreen |
| `tests/v1/fixtures/e2/expected/*.json` | Expected fields each PDF should extract |
| `tests/v1/test_e2e.py` | 6 tests: files exist, JSON valid, values match, injection text present |

## How to test (on the Evergreen demo)

```bash
# Regenerate (idempotent)
python tools/make_e2_statements.py

# Run tests
python -m pytest tests/v1/test_e2e.py -q

# Expected output
# 6 passed in 0.4s
```

## Known limits

1. **PDF generation**: Uses minimal fallback PDF format if reportlab not installed; readable as binary but OCR-tested only structurally (tests verify field lists, not extraction accuracy).
2. **Fixed values**: The 180,000 difference in Fund A NAV (10M → 10.18M) and 12,400 cash break are hardcoded for the E2e demo story (E0e / E3b / E3c dependent on these values).
3. **No real extraction testing**: E2b (the extraction agent) will be tested against these specs to verify it extracts the expected fields; this card only generates test data.

## Wiring for the orchestrator

- **Depends on**: E0e not yet built (Evergreen seed); E2e is standalone.
- **Feeds into**: E2b tests (`test_e2b.py` uses these PDFs as fixtures).
- **No routes**: E2e is offline tool; no API or permissions.
- **No agents**: Pure fixture generation.

## Dependencies

**Recommended**: Add `reportlab` to `requirements.txt` for cleaner PDF generation:

```bash
pip install reportlab
```

Without it, the script falls back to minimal valid PDF format (no reportlab or fpdf2 needed).

## Design notes

- **Deterministic**: Same script, same PDFs every run (needed for regression testing).
- **Evergreen only**: All statements are for the Evergreen Office demo company; no industry customization.
- **Fund story**: Fund A (10M → 10.18M), Fund B (6.4M), Fund C (3.2M from scan), Fund D (2.1M, injection test).
- **Safe injection**: The attack phrase is in a document PDF, never in code or data. E2b extraction + E4d guard will verify the phrase is not executed.

