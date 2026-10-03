#!/usr/bin/env python3
"""Run the existing EUR Retail release-chain crawler in a bounded chunk.

This wrapper intentionally does not duplicate crawler logic. It executes the
frozen crawler source with tighter network bounds and a maximum of 8 release
steps per run, so every successful run can reach the workflow commit step.
"""
from pathlib import Path

src_path = Path("validation/crawl_eur_retail_release_chain.py")
src = src_path.read_text(encoding="utf-8")
src = src.replace("def fetch(url,tries=5,timeout=15):", "def fetch(url,tries=3,timeout=8):")
src = src.replace("raw,ctype,final=fetch(u,tries=4,timeout=15)", "raw,ctype,final=fetch(u,tries=2,timeout=8)")
src = src.replace("while txt and guard<90:", "while txt and guard<8:")
if "while txt and guard<8:" not in src:
    raise RuntimeError("Chunk guard patch did not apply; frozen crawler changed unexpectedly")
exec(compile(src, str(src_path), "exec"), {"__name__": "__main__", "__file__": str(src_path)})
