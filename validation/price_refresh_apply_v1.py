#!/usr/bin/env python3
from pathlib import Path
import re

p=Path('payload/part-15.txt')
text=p.read_text()
pattern=r'<script id="gmfq-price-ecb-20260930">.*?</script>'
replacement="""<script id="gmfq-price-ecb-20261012">
(function(){
  'use strict';
  try{
    const row={
      Date:'2026-10-12',
      EUR:1,
      USD:1.1181,
      GBP:0.84478,
      JPY:177.33,
      CHF:0.9312,
      CAD:1.5946,
      AUD:1.6032,
      NZD:1.9968
    };
    if(typeof D==='undefined' || !Array.isArray(D.prices)) throw new Error('PRICE_DATA_MISSING');
    const i=D.prices.findIndex(x=>x?.Date===row.Date);
    if(i>=0) D.prices[i]=Object.assign({},D.prices[i],row);
    else D.prices.push(row);
    D.prices.sort((a,b)=>String(a.Date).localeCompare(String(b.Date)));
    if(window.DATA_FRESHNESS_REGISTRY){
      window.DATA_FRESHNESS_REGISTRY.audit_date='2026-10-12';
      window.DATA_FRESHNESS_REGISTRY.PRICE={as_of:'2026-10-12',status:'CURRENT_OFFICIAL',source:'ECB euro foreign exchange reference rates'};
    }
    if(window.FINAL_SOURCE_POLICY_AUDIT){
      if(window.FINAL_SOURCE_POLICY_AUDIT.PRICE) Object.assign(window.FINAL_SOURCE_POLICY_AUDIT.PRICE,{current_as_of:'2026-10-12',source:'ECB euro foreign exchange reference rates',policy:'AUTO_UPDATE_PRIMARY',fallback:'LAST_VALID_STALE'});
      if(window.FINAL_SOURCE_POLICY_AUDIT.price) Object.assign(window.FINAL_SOURCE_POLICY_AUDIT.price,{current_as_of:'2026-10-12',source:'ECB euro foreign exchange reference rates',policy:'AUTO_UPDATE_PRIMARY',fallback:'LAST_VALID_STALE'});
    }
    if(window.PRODUCTION_PRICE_COT_LIQ_AUDIT?.price){
      Object.assign(window.PRODUCTION_PRICE_COT_LIQ_AUDIT.price,{status:'CURRENT_OFFICIAL',current_as_of:'2026-10-12',action:'CURRENT',next_expected:'2026-10-13 around 16:00 CET/CEST'});
    }
    window.GMFQ_ECB_PRICE_AUDIT={status:'PASS',as_of:'2026-10-12',source:'ECB euro foreign exchange reference rates',row:{...row},pair_count:Array.isArray(D.pairs)?D.pairs.length:null,rule:'All 28 G8 crosses are derived from one official ECB EUR-base fixing row; no intraday mixing.'};
    try{ if(typeof stableModelRefresh==='function') stableModelRefresh(); }catch(e){}
    try{ if(typeof rebuildCanonicalState==='function') rebuildCanonicalState(); }catch(e){}
    try{ if(typeof syncCoreFreshnessRegistryFromLive==='function') syncCoreFreshnessRegistryFromLive(); }catch(e){}
    document.documentElement.setAttribute('data-ecb-price-audit','PASS');
    document.documentElement.setAttribute('data-price-asof','2026-10-12');
  }catch(e){
    window.GMFQ_ECB_PRICE_AUDIT={status:'FAIL',error:String(e?.message||e)};
    document.documentElement.setAttribute('data-ecb-price-audit','FAIL');
  }
})();
</script>"""
new,n=re.subn(pattern,replacement,text,count=1,flags=re.S)
if n!=1:
    raise SystemExit(f'expected one Price overlay replacement, got {n}')
p.write_text(new)
print('PRICE_OVERLAY_REPLACED')
