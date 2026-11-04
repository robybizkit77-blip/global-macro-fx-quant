/* FX Quant V2 — read-only Macro -> pricing context per FX pair.
 * Operative Pair Setup is NEVER modified. Missing data are not invented.
 * This adapter does not compute policy meeting probabilities, carry, signals or
 * cross-instrument rate-change spreads.
 */
(function(root){"use strict";
const C=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"];
const T=["3m","6m","12m"];
const SCHEMA="GMFQ_FXV2_PAIR_MACRO_PRICING_RESEARCH_V1";
const ISO=/^\d{4}-\d{2}-\d{2}$/;
function validDate(s,today){
 if(typeof s!=="string"||!ISO.test(s)||s>today)return false;
 const d=new Date(s+"T12:00:00Z");
 return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===s;
}
function normalRate(v){return typeof v==="number"&&Number.isFinite(v)&&v>-5&&v<30;}
function patch(out,c,k,rate,stamp,kind,quality,source,origin,change1d,change1w,contract,today){
 if(!C.includes(c)||!T.includes(k)||!normalRate(rate)||!validDate(stamp,today)||
    !["OIS","FUTURES","FUTURES SECONDARI","PROXY FUTURES"].includes(kind)||
    typeof source!=="string"||!source.trim())return false;
 const row=out[c]||(out[c]={}),older=row[k];
 if(older&&(older.date>stamp||(older.date===stamp&&older.origin==="feed"&&origin==="snapshot")))return false;
 row[k]={rate,date:stamp,kind,quality:quality||"QUALITÀ NON VERIFICATA",
  source,origin,contract:contract||null,
  change_1d_bp:Number.isFinite(change1d)?change1d:null,
  change_1w_bp:Number.isFinite(change1w)?change1w:null};
 return true;
}
function build(snapshot,ois,estimated,nzd,today){
 if(!validDate(today,today))throw Error("invalid today");
 const out=Object.create(null);
 if(snapshot?.schema==="GMFQ_FXV2_PRICING_SNAPSHOT_V1"&&
    snapshot.eligible_for_fx_engine===false&&snapshot.ui_only===true){
  for(const c of C){const v=snapshot.currencies?.[c];if(!v)continue;
   for(const k of T){const h=v.horizons?.[k];if(!h)continue;
    patch(out,c,k,h.rate,h.as_of||h.quote_as_of||v.as_of,
     v.kind,v.quality,v.source,"snapshot",h.change_1d_bp,h.change_1w_bp,h.contract,today);
   }
  }
 }
 if(ois?.currencies&&typeof ois.currencies==="object"){
  for(const c of C){const v=ois.currencies[c];if(v?.operational_status!=="GREEN_OFFICIAL")continue;
   for(const k of T){const h=v.horizons?.[k];if(!h)continue;
    patch(out,c,k,h.rate,v.as_of,c==="GBP"?"OIS":"FUTURES",
     "FONTE UFFICIALE",v.source,"feed",h.change_1d_bp,h.change_1w_bp,h.contract,today);
   }
  }
 }
 if(estimated?.official_ois_runtime_untouched===true&&estimated.currencies){
  for(const c of C){if(ois?.currencies?.[c]?.operational_status==="GREEN_OFFICIAL")continue;
   const v=estimated.currencies[c];
   if(!["ESTIMATED_ACTIVE","ESTIMATED_PARTIAL"].includes(v?.status))continue;
   for(const k of T){const h=v.horizons?.[k];if(!h)continue;
    patch(out,c,k,h.rate,h.quote_as_of||h.as_of||v.as_of,
     "FUTURES SECONDARI","STIMA INDICATIVA",v.source,"feed",
     h.change_1d_bp,h.change_1w_bp,h.contract||h.symbol,today);
   }
  }
 }
 if(nzd?.status==="LIVE_DIRECTIONAL_PROXY_READY"&&nzd.horizons){
  for(const k of T){const h=nzd.horizons[k];if(!h)continue;
   patch(out,"NZD",k,h.implied_bank_bill_rate,nzd.as_of,
    "PROXY FUTURES","PROXY DIREZIONALE",nzd.source,"feed",
    h.change_1d_bp,h.change_1w_bp,h.expiry_label,today);
  }
 }
 return {schema:SCHEMA,ui_only:true,eligible_for_fx_engine:false,
  eligible_for_backtests:false,currencies:out};
}
function view(context,pair){
 const p=String(pair||"").replace("/","").toUpperCase();
 if(!context||context.schema!==SCHEMA||!context.ui_only||
    context.eligible_for_fx_engine!==false||context.eligible_for_backtests!==false||
    !/^[A-Z]{6}$/.test(p))return null;
 const a=p.slice(0,3),b=p.slice(3);if(a===b||!C.includes(a)||!C.includes(b))return null;
 const aa=context.currencies[a]||{},bb=context.currencies[b]||{};
 const x=aa["6m"],y=bb["6m"];
 const hasBoth=!!(x&&y);
 const sameDate=hasBoth&&x.date===y.date;
 const sameType=hasBoth&&x.kind===y.kind;
 // Even equal labels do NOT prove the same index, basis or a policy-OIS spread.
 return {pair:p,base:a,quote:b,baseTenors:aa,quoteTenors:bb,
  sixMonthGapBp:hasBoth?Math.round((x.rate-y.rate)*1000)/10:null,
  matchingDate:sameDate,matchingType:sameType,
  comparableForRateChange:false,spreadChange1dBp:null,spreadChange1wBp:null,
  priceInference:null,policyProbability:null,tradeSignal:null,
  complete:T.every(k=>aa[k]&&bb[k])};
}
root.FXV2PairMacroPricing={SCHEMA,build,view};
})(typeof window!=="undefined"?window:globalThis);
