# Validation authority

This folder contains research and validation material. It is **not runtime code**.

The authoritative classification is `REPOSITORY_AUTHORITY_MANIFEST_V1_2026-10-02.json`.

Rules:
- Browser runtime = `index.html` + `payload/part-00.txt` … `part-15.txt`.
- Validation artifacts never affect production unless explicitly promoted.
- Files from failed/superseded experiments may remain for audit history but are archive-only.
- Only workflows listed as active in the authority manifest should remain under `.github/workflows/`.
- PIT work must not tune model thresholds or silently replace missing first-release data.
