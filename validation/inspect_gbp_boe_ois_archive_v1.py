import io,json,urllib.request,zipfile
from pathlib import Path
URL='https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/oisddata.zip'
OUT=Path('validation/GBP_BOE_OIS_ARCHIVE_INSPECTION_2026-10-06.json')

def main():
    req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 GMFQ-PIT-audit/1.0'})
    with urllib.request.urlopen(req,timeout=90) as r: data=r.read()
    z=zipfile.ZipFile(io.BytesIO(data))
    names=z.namelist()
    audit={'schema':'GMFQ_GBP_BOE_OIS_ARCHIVE_INSPECTION_V1','status':'PASS','source_url':URL,'zip_bytes':len(data),'files':names,'excel_probe':[]}
    try:
        import pandas as pd
        for n in names[:20]:
            if not n.lower().endswith(('.xls','.xlsx','.xlsm')): continue
            try:
                b=io.BytesIO(z.read(n)); book=pd.ExcelFile(b)
                item={'file':n,'sheets':book.sheet_names}
                probes=[]
                for s in book.sheet_names[:4]:
                    df=pd.read_excel(book,sheet_name=s,header=None,nrows=12)
                    probes.append({'sheet':s,'shape':[int(df.shape[0]),int(df.shape[1])],'rows':df.fillna('').astype(str).values.tolist()[:8]})
                item['probes']=probes;audit['excel_probe'].append(item)
            except Exception as e:audit['excel_probe'].append({'file':n,'error':str(e)[:300]})
    except Exception as e:audit['pandas_error']=str(e)
    OUT.write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
