"""Read-only full historical overlap diagnostic for Japan Labour Force Survey table 1-a-1."""
import io,json,statistics,re
from datetime import datetime,date,timezone
from urllib.request import Request,urlopen
from openpyxl import load_workbook
from validation.macro.prepare_chf_snb_revised_v1 import SOURCE,need
URL="https://www.e-stat.go.jp/en/stat-search/file-download?fileKind=0&statInfId=000031831358"
def main():
    row=next(r for r in json.loads(SOURCE.read_text())["JPY"] if r["id"]=="JP_EMPLOYED_history_value")
    old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"])>=36 and row["unit"]=="10k persons","legacy identity mismatch")
    with urlopen(Request(URL,headers={"User-Agent":"GMFQ official macro research"}),timeout=45) as r:
        raw=r.read(15_000_001)
    need(0<len(raw)<=15_000_000,"source size")
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    try:
        for ws in book.worksheets:
            rows=list(ws.iter_rows(values_only=True));print("JP_LFS_SHEET",ws.title,"ROWS",len(rows))
            print("JP_LFS_HEAD",json.dumps(rows[:18],default=str,ensure_ascii=False)[:16000])
            print("JP_LFS_TAIL",json.dumps(rows[-8:],default=str,ensure_ascii=False)[:10000])
    finally:book.close()
if __name__=="__main__":main()
