#!/usr/bin/env python3
"""Run the existing EUR Retail release-chain crawler in a bounded chunk.

This wrapper intentionally does not duplicate crawler logic. It executes the
frozen crawler source with tighter network bounds and a maximum of 8 release
steps per run, so every successful run can reach the workflow commit step.
It also bridges verified historical Eurostat releases that are exposed only
as direct PDF documents rather than product pages.
"""
from pathlib import Path

src_path = Path("validation/crawl_eur_retail_release_chain.py")
src = src_path.read_text(encoding="utf-8")
src = src.replace("def fetch(url,tries=5,timeout=15):", "def fetch(url,tries=3,timeout=8):")
src = src.replace("raw,ctype,final=fetch(u,tries=4,timeout=15)", "raw,ctype,final=fetch(u,tries=2,timeout=8)")
src = src.replace("while txt and guard<90:", "while txt and guard<8:")

needle = "def load_candidate(ds):\n    for _pass in range(2):"
replacement = '''def load_candidate(ds):
    direct_releases={
      "2022-10-06":"https://ec.europa.eu/eurostat/documents/2995521/15131934/4-06102022-AP-EN.pdf/30dbcae1-1162-7035-4b3e-ae69a64df586"
    }
    if ds in direct_releases:
        u=direct_releases[ds]
        raw,ctype,final=fetch(u,tries=2,timeout=8)
        if raw is not None:
            try:
                txt=textify(raw,ctype)
                low=txt.lower()
                if "volume of retail trade" in low or "retail trade volume" in low:
                    return raw,ctype,final or u,txt
            except Exception:
                pass
    for _pass in range(2):'''
src = src.replace(needle, replacement)
if "while txt and guard<8:" not in src:
    raise RuntimeError("Chunk guard patch did not apply; frozen crawler changed unexpectedly")
if '"2022-10-06":"https://ec.europa.eu/eurostat/documents/' not in src:
    raise RuntimeError("Historical direct-release fallback patch did not apply")
exec(compile(src, str(src_path), "exec"), {"__name__": "__main__", "__file__": str(src_path)})
