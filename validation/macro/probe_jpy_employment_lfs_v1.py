"""Compare whole Japan monthly employment series, original versus seasonally adjusted."""
import io,json,statistics,re,math
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from openpyxl import load_workbook
from validation.macro.prepare_chf_snb_revised_v1 import SOURCE,need
URL="https://www.e-stat.go.jp/en/stat-search/file-download?fileKind=0&statInfId=000031831358"
def fetch():
    with urlopen(Request(URL,headers={"User-Agent":"GMFQ official macro research"}),timeout=45) as r:
        raw=r.read(15_000_001)
    need(0<len(raw)<=15_000_000,"source size")
    return raw
def parse(raw,now):
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    result={}
    try:
        for label,sheet in (("SA","季節調整値"),("NSA","原数値")):
            rows=list(book[sheet].iter_rows(values_only=True))
            need("Whole Japan, Monthly Data" in rows[1][4] and rows[3][5]=="(ten thousand persons)" and rows[6][7]=="Employed person" and rows[8][7]=="Both sexes","wrong LFS source definition")
            need(("Seasonally adjusted series" if label=="SA" else "Original series") in rows[4][4],"wrong adjustment")
            obs={};year=None
            for i,line in enumerate(rows[10:],10):
                m=re.fullmatch(r"(\d{1,2})月",str(line[1] or "")) if len(line)>7 else None
                if not m:continue
                month=int(m[1])
                if month==1:
                    candidates=[x[0] for x in rows[i:i+2] if isinstance(x[0],int) and 1900<=x[0]<=2100]
                    need(len(candidates)==1,"year label ambiguous")
                    year=candidates[0]
                if isinstance(line[0],int):need(line[0]==year,"year transition mismatch")
                need(year is not None and 1<=month<=12,"invalid period")
                d=f"{year:04}-{month:02}"
                if d<"2019-10" or line[7] is None:continue
                need(isinstance(line[7],(int,float)) and math.isfinite(line[7]) and 1000<line[7]<10000 and d<now.strftime("%Y-%m") and d not in obs,"invalid observation")
                obs[d]=float(line[7])
            result[label]=obs
    finally:book.close()
    return result
def main():
    row=next(r for r in json.loads(SOURCE.read_text())["JPY"] if r["id"]=="JP_EMPLOYED_history_value")
    old=dict(zip(row["dates"],row["values"]));need(len(old)==len(row["dates"])>=36 and row["unit"]=="10k persons","legacy identity mismatch")
    for label,obs in parse(fetch(),datetime.now(timezone.utc)).items():
        need(set(old)<=set(obs),"source lacks legacy history")
        e=[abs(obs[d]-v) for d,v in old.items()]
        print("JP_LFS_OVERLAP",label,json.dumps({"overlap":len(e),"exact":sum(v==0 for v in e),"median_abs":statistics.median(e),"max_abs":max(e),"latest_date":max(obs),"latest":obs[max(obs)],"new":{d:obs[d] for d in sorted(obs) if d>max(old)}}))
if __name__=="__main__":main()
