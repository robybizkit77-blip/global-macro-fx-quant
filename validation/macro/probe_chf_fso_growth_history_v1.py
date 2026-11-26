"""Read-only discovery of exact FSO monthly production and real retail history."""
import io, json, math, re, statistics
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen
from openpyxl import load_workbook

BASE = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/{}/master"
SOURCES = {
    "CH_PRODUCTION_history_value": [37030901, 37030907, 37030895],
    "CH_RETAIL_REAL_history_value": [36970302],
}
def month(v):
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m")
    s = str(v or "").strip()
    m = re.fullmatch(r"(20\d{2})[-./mM](0?[1-9]|1[0-2])(?:[-./]\d{1,2})?", s)
    if m:
        return f"{int(m[1]):04}-{int(m[2]):02}"
    m = re.fullmatch(r"(0?[1-9]|1[0-2])[./-](20\d{2})", s)
    if m:
        return f"{int(m[2]):04}-{int(m[1]):02}"
    for fmt in ("%b %Y", "%B %Y", "%b-%Y", "%Y %b"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m")
        except ValueError:
            pass
    return None

def scan(lines, old, sheet, orientation):
    results = []
    for ai, axis in enumerate(lines):
        pairs = [(i, d) for i, v in enumerate(axis) if (d := month(v))]
        if len(pairs) < 36:
            continue
        dates = [d for _, d in pairs]
        if len(set(dates)) != len(dates) or not set(old).issubset(dates):
            continue
        for li, line in enumerate(lines):
            if li == ai:
                continue
            obs = {d: float(line[i]) for i, d in pairs if i < len(line)
                   and isinstance(line[i], (int, float)) and not isinstance(line[i], bool)
                   and math.isfinite(line[i])}
            if not set(old).issubset(obs):
                continue
            errors = [abs(obs[d]-v) for d, v in old.items()]
            results.append({"sheet":sheet,"orientation":orientation,"axis":ai+1,
                            "series":li+1,"header":[str(v)[:100] for v in line[:12] if v is not None],
                            "overlap":len(errors),"exact":sum(e<1e-7 for e in errors),
                            "median_abs":statistics.median(errors),"max_abs":max(errors),
                            "new":{d:obs[d] for d in sorted(obs) if max(old)<d<="2026-09"}})
    return results

def main():
    doc=json.loads(Path("live_data/sections/MACRO_SERIES.json").read_text())
    for ident, assets in SOURCES.items():
        row=next(r for r in doc["CHF"] if r["id"]==ident)
        old=dict(zip(row["dates"],row["values"]))
        assert len(old)==len(row["dates"])==len(row["values"])>=36
        for asset in assets:
            with urlopen(Request(BASE.format(asset),headers={"User-Agent":"GMFQ official source audit"}),timeout=45) as response:
                raw=response.read(10_000_001)
            assert 0<len(raw)<=10_000_000
            book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
            candidates=[]
            try:
                for ws in book.worksheets:
                    if ws.max_row and ws.max_column and ws.max_row*ws.max_column>2_000_000:
                        print("OVERSIZED_SHEET",ws.title,ws.max_row,ws.max_column)
                        continue
                    lines=list(ws.iter_rows(values_only=True))
                    if not lines: continue
                    print("FSO_LAYOUT",asset,ws.title,ws.max_row,ws.max_column,json.dumps([[str(v)[:100] if v is not None else None for v in l[:18]] for l in lines[:14]],ensure_ascii=False))
                    candidates+=scan(lines,old,ws.title,"column")
                    candidates+=scan(list(zip(*lines)),old,ws.title,"row")
            finally:
                book.close()
            candidates.sort(key=lambda x:(-x["exact"],x["median_abs"],x["max_abs"]))
            print("FSO_IDENTITY",ident,asset,json.dumps(candidates[:5],ensure_ascii=False))
    print("DIAGNOSTIC_ONLY_NO_CANONICAL_WRITES")
if __name__=="__main__":
    main()
