import csv, io, json, requests
from datetime import date, timedelta

BASE='https://data.snb.ch/api/cube/rendoblid/data/csv/en'
end=date(2026,10,5)
start=end-timedelta(days=14)
params={'dimSel':'D0(2J,10J0)','fromDate':start.isoformat(),'toDate':end.isoformat()}
r=requests.get(BASE,params=params,timeout=120)
r.raise_for_status()
text=r.content.decode('utf-8-sig','replace')
rows=list(csv.reader(io.StringIO(text),delimiter=';'))
if not rows:
    raise SystemExit('SNB returned no rows')
header=rows[0]
body=[x for x in rows[1:] if x and any(str(v).strip() for v in x)]
print(json.dumps({'status':'PASS','url':r.url,'header':header,'rows':body[-20:]},ensure_ascii=False,indent=2))
