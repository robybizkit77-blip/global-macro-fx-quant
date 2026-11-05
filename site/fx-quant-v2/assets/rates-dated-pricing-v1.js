/* FX Quant V2 — Rates page only. Keep each horizon's actual quote date.
 * Never promote indicative futures, NZ bank-bill proxies or stale snapshots
 * into a certified OIS observation, FX Core vote or backtest feature.
 */
(function(root){"use strict";
const C=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"],T=["3m","6m","12m"];
const kinds=["OIS","FUTURES","FUTURES SECONDARI","PROXY FUTURES"];
const iso=s=>typeof s==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&
 Number.isFinite(Date.parse(s+"T12:00:00Z"))&&
 new Date(s+"T12:00:00Z").toISOString().slice(0,10)===s;
const good=(v)=>typeof v==="number"&&Number.isFinite(v)&&v>-5&&v<30;
const copy=x=>JSON.parse(JSON.stringify(x||{}));
const stamp=(h,row)=>h?.quote_as_of||h?.as_of||row?.as_of;
function merge(previous,official,estimated,nzd,today){
 if(!iso(today))throw Error("invalid research as-of");
 const pricing=copy(previous),accepted={official:0,secondary:0,proxy:0},rejected=[];
 function commit(c,t,rate,day,kind,quality,source,h,origin){
  if(!C.includes(c)||!T.includes(t)||!good(rate)||!iso(day)||
     day>today||!kinds.includes(kind)||!source){
   rejected.push({currency:c,tenor:t,reason:"INVALID_OR_FUTURE_QUOTE"});return false;
  }
  const row=pricing[c]||{horizons:{}},old=row.horizons?.[t];
  if(old&&good(old.rate)&&iso(old.as_of)&&
      (old.as_of>day||(old.as_of===day&&old.origin==="feed"&&origin!=="feed")))return false;
  const next={rate,as_of:day,quality,kind,source,origin,
    contract:h?.contract||h?.symbol||h?.expiry_label||null,
    change_1d_bp:goodBp(h?.change_1d_bp)?h.change_1d_bp:null,
    change_1w_bp:goodBp(h?.change_1w_bp)?h.change_1w_bp:null};
  row.horizons={...(row.horizons||{}),[t]:next};
  const dates=Object.values(row.horizons).map(x=>x.as_of).filter(iso);
  row.as_of=dates.length?dates.sort().at(-1):day;
  row.quality=quality;
  row.source_type=kind==="OIS"?"OIS · certificato":
   kind==="FUTURES"?"Futures impliciti · certificato":
   kind==="FUTURES SECONDARI"?"Futures · indicativo (non OIS)":
   "ASX NZ bank-bill futures · proxy direzionale, non OIS";
  row.source=source;
  row.eligible_for_fx_engine=false;
  row.eligible_for_backtests=false;
  pricing[c]=row;return true;
 }
 function goodBp(v){return typeof v==="number"&&Number.isFinite(v)&&Math.abs(v)<20000;}
 const officialOK=official?.schema==="GMFQ_OIS_OPERATIONAL_VIEW_V1"&&
 official.official_runtime_untouched===true;
 const estimatedOK=estimated?.schema==="GMFQ_CB_PRICING_ESTIMATED_V1"&&
 estimated.official_ois_runtime_untouched===true;
 const nzdOK=nzd?.schema==="GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1"&&
 nzd.status==="LIVE_DIRECTIONAL_PROXY_READY"&&nzd.currency==="NZD"&&
 nzd.governance?.eligible_for_fx_engine!==true;
 for(const c of C){
  const o=officialOK?official.currencies?.[c]:null;
  const isOfficial=o?.operational_status==="GREEN_OFFICIAL"&&
     o.official_status==="ACTIVE"&&o.quality==="OFFICIAL_CERTIFIED";
  if(isOfficial){
   for(const t of T){const h=o.horizons?.[t];
    if(h&&commit(c,t,h.rate,stamp(h,o),c==="GBP"?"OIS":"FUTURES",
                  "FONTE UFFICIALE",o.source,h,"feed"))accepted.official++;
   }
   // Never mix indicative futures into an officially certified currency.
   continue;
  }
  if(c==="NZD"&&nzdOK){
   for(const t of T){const h=nzd.horizons?.[t];
    if(h&&commit(c,t,h.implied_bank_bill_rate,stamp(h,nzd),"PROXY FUTURES",
                 "PROXY DIREZIONALE",nzd.source,h,"feed"))accepted.proxy++;
   }
   continue;
  }
  const e=estimatedOK?estimated.currencies?.[c]:null;
  if(!["ESTIMATED_ACTIVE","ESTIMATED_PARTIAL"].includes(e?.status))continue;
  for(const t of T){const h=e.horizons?.[t];
   if(h&&commit(c,t,h.rate,stamp(h,e),"FUTURES SECONDARI",
                "STIMA INFORMATIVA",e.source,h,"feed"))accepted.secondary++;
  }
 }
 const coverage=Object.fromEntries(C.map(c=>[c,T.filter(t=>good(pricing[c]?.horizons?.[t]?.rate)&&
  iso(pricing[c].horizons[t].as_of)&&pricing[c].horizons[t].as_of<=today).length]));
 return {pricing,accepted,coverage,
  loaded_levels:Object.values(coverage).reduce((a,b)=>a+b,0),
  all_24_levels_present:Object.values(coverage).every(n=>n===3),
  rejected,eligible_for_fx_engine:false,eligible_for_backtests:false};
}
const api=Object.freeze({merge});
root.FXV2RatesDatedPricing=api;
if(typeof module==="object"&&module&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
