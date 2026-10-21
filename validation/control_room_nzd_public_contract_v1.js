'use strict';
/** Validate the *published* NZD RBNZ B2 snapshot against the approved repo.
 * Official/manual is a source quality; recency is a separate calendar test.
 * This never promotes a new quote or recalculates a rate/model.
 */
const fs=require('node:fs');
const path=require('node:path');

const RATES='live_data/sections/NATIVE_RATES_DATA.json';
const REGISTRY='validation/RATES_SOURCE_ADAPTERS_V1_2026-10-05.json';

function readApproved(root='.') {
 const rates=JSON.parse(fs.readFileSync(path.join(root,RATES),'utf8'));
 const registry=JSON.parse(fs.readFileSync(path.join(root,REGISTRY),'utf8'));
 const approved=registry.currencies?.NZD;
 if(!approved||!rates.NZD)throw Error('NZD approved canonical Rates/registry unavailable');
 return {approved,canonical:rates.NZD};
}
function same(a,b){return typeof a==='number'&&typeof b==='number'&&Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-9}
function normalized(nz) {
 const hist=(key)=>{const h=nz?.[key]||{};return {date:h.last_date||null,value:h.last_value??null,
   tailDate:Array.isArray(h.dates)?h.dates.at(-1):null,
   tailValue:Array.isArray(h.values)?h.values.at(-1):null}};
 const tenor=(t)=>{const r=nz?.tenors?.filter(x=>x.tenor===t)||[];return r.length===1?{date:r[0].date,value:r[0].value}:null};
 return {date:nz?.date,y2:nz?.['2Y'],y10:nz?.['10Y'],
  quality:nz?.quality,source:nz?.source,
  history2:hist('history2'),history10:hist('history10'),
  tenor2:tenor('2Y'),tenor10:tenor('10Y')};
}
function utcAgeDays(iso,now=new Date()) {
 if(typeof iso!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(iso))throw Error('invalid NZD as-of');
 const v=new Date(iso+'T00:00:00Z');
 if(!Number.isFinite(v.getTime())||v.toISOString().slice(0,10)!==iso)throw Error('invalid NZD calendar date');
 const nowUtc=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());
 return (nowUtc-v.getTime())/86400000;
}
function verifyPublicNzd(mirror,approved,canonical,notes='',now=new Date()) {
 const x=normalized(mirror),y=normalized(canonical);
 if(!approved||!canonical||!mirror||x.date!==approved.current_snapshot||x.date!==y.date||
    !same(x.y2,approved.current_2Y)||!same(x.y10,approved.current_10Y)||
    !same(x.y2,y.y2)||!same(x.y10,y.y10))
    throw Error('NZD public Rates differs from approved date/2Y/10Y');
 if(x.quality!=='FULL_CURRENT_OFFICIAL_MANUAL_VERIFIED'||x.quality!==y.quality||
    x.source!==y.source||!x.source.includes('Reserve Bank of New Zealand')||
    !x.source.includes('B2')||!x.source.includes(x.date))
    throw Error('NZD public source quality/provenance mismatch');
 for(const [tenor,h,t] of [['2Y','history2','tenor2'],['10Y','history10','tenor10']]){
    const value=tenor==='2Y'?x.y2:x.y10;
    if(!x[t]||x[t].date!==x.date||!same(x[t].value,value)||
       x[h].date!==x.date||x[h].tailDate!==x.date||
       !same(x[h].value,value)||!same(x[h].tailValue,value)||
       JSON.stringify(x[h])!==JSON.stringify(y[h])||
       JSON.stringify(x[t])!==JSON.stringify(y[t]))
       throw Error('NZD public '+tenor+' history/tenor source mismatch');
 }
 const age=utcAgeDays(x.date,now);
 if(age<0)throw Error('NZD future snapshot');
 const recent=age<=4; // matches the approved v10 ratesAll freshness contract
 if(recent&&String(notes).includes('NZD/AUD'))
    throw Error('NZD recent approved official snapshot wrongly shown as AUD proxy');
 // A dated official observation stays official, but may no longer be current.
 // An optional AUD beta proxy is allowed only when the official NZD is stale.
 return {status:'PASS',as_of:x.date,age_calendar_days:age,
  official_manual_verified:true,operationally_recent:recent,
  aud_proxy_allowed:!recent,automatic_promotion:false};
}
module.exports={readApproved,normalized,utcAgeDays,verifyPublicNzd};
