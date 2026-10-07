#!/usr/bin/env python3
from __future__ import annotations
import io,json,re,urllib.request
from pathlib import Path
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
EVID=ROOT/'validation/NZD_RBNZ_2Y_PROBE_V1_2026-10-07.json'
PAGE='https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates'
URL='https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)','Accept':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8'}

def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=60) as r:return r.read()

def main():
    data=get(URL)
    wb=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
    matches=[]
    for ws in wb.worksheets:
        for ri,row in enumerate(ws.iter_rows(min_row=1,max_row=min(ws.max_row,40),values_only=True),1):
            vals=[str(x).strip() if x is not None else '' for x in row]
            joined=' | '.join(vals).lower()
            for i,v in enumerate(vals):
                if re.search(r'2\s*(?:year|yr)',v,re.I) and ('government' in joined or 'secondary market' in joined or 'bond' in joined):
                    matches.append({'sheet':ws.title,'row_index':ri,'column_index':i+1,'header':v,'row':vals})
    payload={'schema':'GMFQ_NZD_RBNZ_2Y_PROBE_V1','status':'PASS_PROBE_NOT_CERTIFIED' if matches else 'FAIL','created_at':'2026-10-07','source':'Reserve Bank of New Zealand Wholesale interest rates (B2)','page_url':PAGE,'xlsx_url':URL,'workbook_sheets':wb.sheetnames,'xlsx_bytes':len(data),'header_matches':matches[:20],'note':'Probe only. Certification requires exact column identity, daily date parsing, anchors and same-basis coverage gate.','changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    EVID.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8');print(json.dumps(payload,indent=2))
    if not matches:raise SystemExit(1)
if __name__=='__main__':main()
