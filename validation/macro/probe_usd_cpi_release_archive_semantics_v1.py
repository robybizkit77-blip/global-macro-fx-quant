#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json, pathlib, re, urllib.request

PROBES = [
    ("2018-03", "04112018"),
    ("2020-01", "02132020"),
    ("2024-01", "02132024"),
]
UA = "Mozilla/5.0 (compatible; GLOBAL-MACRO-FX-QUANT/1.0; research validation)"


def fetch(stamp: str) -> str:
    url = f"https://www.bls.gov/news.release/archives/cpi_{stamp}.htm"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html", "Connection": "close"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def textify(raw: str) -> str:
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def snippets(text: str, pattern: str, radius: int = 240, limit: int = 6) -> list[str]:
    out=[]
    for m in re.finditer(pattern, text, flags=re.I):
        a=max(0,m.start()-radius); b=min(len(text),m.end()+radius)
        out.append(text[a:b])
        if len(out)>=limit: break
    return out


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--output", required=True, type=pathlib.Path); a=ap.parse_args()
    rows=[]
    for reference_month, stamp in PROBES:
        raw=fetch(stamp); text=textify(raw)
        exact_id = bool(re.search(r"\bCUSR0000SA0\b", raw, flags=re.I))
        explicit_sa_level_phrases = snippets(text, r"seasonally adjusted (?:index|indexes|index level|index levels)")
        all_items_context = snippets(text, r"All items", radius=380, limit=10)
        table1_context = snippets(text, r"Table 1\.", radius=700, limit=3)
        # This gate is intentionally conservative: only an explicit canonical series id or an explicit
        # seasonally-adjusted index-level table can qualify for the next parser stage.
        has_sa_index_level_candidate = exact_id or any(
            re.search(r"seasonally adjusted.{0,80}(?:index|indexes).{0,140}\b\d{3}\.\d{3}\b", x, flags=re.I)
            for x in explicit_sa_level_phrases + table1_context + all_items_context
        )
        rows.append({
            "reference_month": reference_month,
            "archive_stamp": stamp,
            "canonical_series_id_present": exact_id,
            "explicit_sa_index_level_candidate": has_sa_index_level_candidate,
            "seasonally_adjusted_index_phrase_snippets": explicit_sa_level_phrases,
            "table1_snippets": table1_context,
            "all_items_snippets": all_items_context,
        })
    candidate_all=all(r["explicit_sa_index_level_candidate"] for r in rows)
    out={
        "schema":"GMFQ_USD_CPI_RELEASE_ARCHIVE_SEMANTICS_V1",
        "status":"PARSER_CANDIDATE" if candidate_all else "SEMANTIC_WITHHELD",
        "rows":rows,
        "canonical_requirement":"Exact contemporaneous seasonally-adjusted CPI-U All Items index level compatible with CUSR0000SA0, not rounded monthly percent changes.",
        "candidate_all":candidate_all,
        "certification_implied":False,
        "prohibited_shortcuts":[
            "Do not chain rounded 0.1% seasonally-adjusted monthly changes into synthetic index levels.",
            "Do not substitute unadjusted CPI-U index levels for CUSR0000SA0.",
            "Do not use current revised SA history as historical first-release history."
        ]
    }
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out,indent=2,sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
