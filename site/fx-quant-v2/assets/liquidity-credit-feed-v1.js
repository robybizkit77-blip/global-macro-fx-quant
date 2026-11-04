/* FX Quant V2 — read-only ICE/FRED credit overlay for Liquidity & Credit.
 * Never upgrades a feed timestamp to the current time and never writes FX Core.
 */
(function(root){"use strict";
const SCHEMA="GMFQ_FXV2_CROSS_ASSET_SOURCE_OVERLAY_V1";
const EXPECTED={
 IG:{id:"IG_OAS",url:"https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLC0A0CM",name:"US IG OAS"},
 HY:{id:"HY_OAS",url:"https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2",name:"US HY OAS"}
};
const iso=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&
 new Date(x+"T12:00:00Z").toISOString().startsWith(x);
const n=x=>typeof x==="number"&&Number.isFinite(x);
const dayDiff=(a,b)=>Math.round((Date.parse(a+"T12:00:00Z")-Date.parse(b+"T12:00:00Z"))/86400000);
function validate(row,old,today,spec){
 if(!row||typeof row!=="object"||!old||!iso(today)||!iso(old.date)||!iso(row.date)||
    row.date<old.date||row.date>today)return "SOURCE_DATE_INVALID_OR_OLDER";
 if(dayDiff(today,row.date)>7)return "SOURCE_PUBLICATION_TOO_OLD";
 if(row.quality!=="PUBLISHED_SOURCE_RESEARCH_ONLY"||
    row.publisher!=="ICE Data Indices via FRED"||
    row.source_url!==spec.url||
    row.kind!=="CREDIT_OAS"||row.unit!=="percent"||
    row.no_core_or_backtest_effect!==true||
    row.not_intraday!==true||!n(row.value)||row.value<0||row.value>40)
    return "CREDIT_SERIES_PROVENANCE_OR_VALUE_INVALID";
 if(!Array.isArray(row.history)||row.history.length<2)return "CREDIT_HISTORY_MISSING";
 const last=row.history.at(-1);
 if(!Array.isArray(last)||last.length!==2||last[0]!==row.date||
    !n(last[1])||Math.abs(last[1]-row.value)>.00001)
    return "CREDIT_HISTORY_LATEST_MISMATCH";
 for(let i=0;i<row.history.length;i++){
  const x=row.history[i];
  if(!Array.isArray(x)||x.length!==2||!iso(x[0])||
     !n(x[1])||x[1]<0||x[1]>40||x[0]>row.date||
     (i>0&&x[0]<=row.history[i-1][0]))return "CREDIT_HISTORY_BAD";
 }
 if(row.previous_date&&(!iso(row.previous_date)||row.previous_date>=row.date))return "PREVIOUS_DATE_BAD";
 if(row.previous_date&&n(row.previous)){
  const a=row.history.find(x=>x[0]===row.previous_date);
  if(a&&Math.abs(a[1]-row.previous)>.00001)return "PREVIOUS_READING_MISMATCH";
 }
 return null;
}
function merge(snapshot,live,today){
 const result={schema:"GMFQ_FXV2_CREDIT_CONSUMER_V1",data:snapshot,
   applied:[],rejected:[],source_status:"SNAPSHOT_ONLY"};
 if(!snapshot||!snapshot.credit||!live||live.schema!==SCHEMA||
    live.eligible_for_fx_core!==false||live.eligible_for_backtest!==false||
    live.source_dates_independent!==true){
   result.rejected.push({reason:"INCOMPATIBLE_CROSS_ASSET_FEED"});
   return result;
 }
 let credit={...snapshot.credit};
 for(const [c,spec] of Object.entries(EXPECTED)){
  const row=live.streams?.[spec.id];
  const problem=validate(row,credit[c],today,spec);
  if(problem){result.rejected.push({ccy:c,reason:problem});continue;}
  credit[c]={...credit[c],date:row.date,value:row.value,
    previous:row.previous,history:row.history.map(x=>x.slice()),
    unit:"% OAS",quality:"FRED/ICE · FONTE PUBBLICATA, RICERCA V2",
    source:row.publisher,source_url:row.source_url,
    source_type:"AUTOMATIC_FRED_PUBLISHED_CREDIT_OAS",
    source_as_of:row.date};
  result.applied.push({ccy:c,date:row.date,value:row.value,source:row.publisher});
 }
 result.data={...snapshot,credit};
 result.source_status=result.applied.length===2?"CREDIT_2_OF_2_LIVE_SOURCE":
   result.applied.length===1?"CREDIT_1_OF_2_PARTIAL":"SNAPSHOT_ONLY";
 return result;
}
const api=Object.freeze({merge,validate,EXPECTED});
root.FXV2CreditOverlay=api;
if(typeof module==="object"&&module&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
