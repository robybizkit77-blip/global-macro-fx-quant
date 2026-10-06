import io,csv,json,urllib.request,zipfile
from pathlib import Path
import pandas as pd
URL='https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/oisddata.zip'
OUT=Path('history/pit_v1/GBP_BOE_OIS_SPOT_2Y_DAILY_2018_2026.csv')
AUDIT=Path('validation/GBP_BOE_OIS_2Y_MATERIALIZATION_2026-10-06.json')

def main():
    req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 GMFQ-PIT-audit/1.0'})
    with urllib.request.urlopen(req,timeout=90) as r:data=r.read()
    z=zipfile.ZipFile(io.BytesIO(data)); rows=[]; source_files=[]
    for n in z.namelist():
        if not n.lower().endswith('.xlsx'):continue
        if not any(k in n for k in ['2016 to 2024','2025 to present']):continue
        book=pd.ExcelFile(io.BytesIO(z.read(n)))
        # Prefer the full spot curve rather than the short-end-only sheet.
        spot=[s for s in book.sheet_names if 'spot curve' in s.lower()]
        if not spot: spot=[s for s in book.sheet_names if 'spot' in s.lower() and 'short end' not in s.lower()]
        if not spot: raise ValueError(f'full spot sheet missing {n}: {book.sheet_names}')
        sheet=spot[0]
        df=pd.read_excel(book,sheet_name=sheet,header=None)
        years_row=None
        for i in range(min(10,len(df))):
            if str(df.iloc[i,0]).strip().lower().startswith('years'):
                years_row=i;break
        if years_row is None:raise ValueError(f'years row missing {n}')
        vals=[]
        for j in range(1,df.shape[1]):
            try: vals.append((abs(float(df.iloc[years_row,j])-2.0),j,float(df.iloc[years_row,j])))
            except: pass
        dist,col,tenor=min(vals)
        if dist>1e-6:raise ValueError(f'2Y tenor not exact in {n}: {tenor}')
        count=0
        for i in range(years_row+1,len(df)):
            d=df.iloc[i,0]
            if pd.isna(d):continue
            try: dt=pd.to_datetime(d)
            except:continue
            if dt.year<2018:continue
            v=df.iloc[i,col]
            if pd.isna(v):continue
            try:x=float(v)
            except:continue
            rows.append({'date':dt.strftime('%Y-%m-%d'),'gbp_ois_spot_2y_pct':x,'source_file':n})
            count+=1
        source_files.append({'file':n,'sheet':sheet,'tenor_years':tenor,'rows_2018_plus':count})
    ded={r['date']:r for r in rows}; rows=[ded[k] for k in sorted(ded)]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    audit={'schema':'GMFQ_GBP_BOE_OIS_2Y_MATERIALIZATION_V1','status':'PASS' if len(rows)>1500 else 'PARTIAL','created_at':'2026-10-06','source_url':URL,'curve':'sterling OIS spot','tenor_years':2.0,'rows':len(rows),'start':rows[0]['date'],'end':rows[-1]['date'],'source_files':source_files,'guardrails':['single full OIS spot curve only','exact 2Y tenor','no gilt substitution','daily official BoE archive','no engine/live_data changes']}
    AUDIT.write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit,indent=2))
    if audit['status']!='PASS':raise SystemExit(2)
if __name__=='__main__':main()
