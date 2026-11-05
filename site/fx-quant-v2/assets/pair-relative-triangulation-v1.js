/* FX Quant V2: combine dated research prices, macro observations, and
 * indicative front-end LEVEL contrasts. Read-only: no inferred FX or policy vote.
 */
(function(root){"use strict";
const SCHEMA="GMFQ_FXV2_RELATIVE_PRICING_28PAIR_RESEARCH_V1";
const H=["3m","6m","12m"],C=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"];
const numeric=n=>typeof n==="number"&&Number.isFinite(n);
const iso=s=>typeof s==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&
 Number.isFinite(Date.parse(s+"T12:00:00Z"))&&
 new Date(s+"T12:00:00Z").toISOString().slice(0,10)===s;
const days=(a,b)=>Math.round((Date.parse(a+"T12:00:00Z")-Date.parse(b+"T12:00:00Z"))/86400000);
const fmt=(v,n=1)=>numeric(v)?(v>0?"+":v<0?"−":"")+
 Math.abs(v).toLocaleString("it-IT",{minimumFractionDigits:n,maximumFractionDigits:n}):"n.d.";
function validate(doc,today){
 if(!iso(today)||!doc||doc.schema!==SCHEMA||
    doc.eligible_for_fx_engine!==false||doc.eligible_for_backtests!==false||
    doc.eligible_for_automatic_core_rebase!==false||
    doc.canonical_fx_core_untouched!==true||
    doc.not_ois_equivalent!==true||doc.not_policy_repricing!==true||
    doc.not_fx_carry!==true||doc.no_cross_date_market_move_inferred!==true||
    doc.same_bucket_does_not_guarantee_same_expiry_or_index!==true||
    doc.summary?.pairs!==28||doc.summary?.currencies!==8||
    doc.summary?.horizon_comparisons!==84||
    doc.summary?.generated_fx_signals!==0||
    doc.summary?.generated_policy_repricing_signals!==0||
    !iso(doc.pricing_source_snapshot_date)||
    doc.pricing_source_snapshot_date>today||
    typeof doc.pairs!=="object"||Object.keys(doc.pairs).length!==28)return false;
 const seen=new Set(),pairCodes=new Set();
 for(const [pair,entry] of Object.entries(doc.pairs)){
  if(!/^[A-Z]{3}[/][A-Z]{3}$/.test(pair)||!entry)return false;
  const a=pair.slice(0,3),b=pair.slice(4,7);
  if(!C.includes(a)||!C.includes(b)||a===b||
     entry.base!==a||entry.quote!==b||
     entry.fx_signal!==null||entry.expected_return!==null||
     entry.carry_estimate!==null||Object.keys(entry.horizons||{}).length!==3)return false;
  const canonical=[a,b].sort().join("");
  if(seen.has(canonical))return false;
  seen.add(canonical);pairCodes.add(pair);
  for(const t of H){
   const v=entry.horizons[t];
   if(!v||!numeric(v.spread_bp)||!numeric(v.base_rate_pct)||
      !numeric(v.quote_rate_pct)||v.fx_signal!==null||
      v.policy_repricing_bp!==null||
      !iso(v.base_as_of)||!iso(v.quote_as_of)||
      v.base_as_of>doc.pricing_source_snapshot_date||
      v.quote_as_of>doc.pricing_source_snapshot_date||
      v.same_date!==(v.base_as_of===v.quote_as_of)||
      v.date_gap_days!==Math.abs(days(v.base_as_of,v.quote_as_of))||
      Math.abs(v.spread_bp-100*(v.base_rate_pct-v.quote_rate_pct))>.002||
      !["OIS","FUTURES","FUTURES SECONDARI","PROXY FUTURES"].includes(v.base_kind)||
      !["OIS","FUTURES","FUTURES SECONDARI","PROXY FUTURES"].includes(v.quote_kind))
      return false;
  }
 }
 return seen.size===28&&pairCodes.size===28;
}
function view(doc,pair,today,macro,macroApi,macroDynamics,price,priceMeta){
 if(!validate(doc,today))return null;
 const clean=String(pair||"").replace("/","").toUpperCase();
 if(!/^[A-Z]{6}$/.test(clean))return null;
 const a=clean.slice(0,3),b=clean.slice(3);
 const q=doc.pairs[a+"/"+b];if(!q)return null;
 const x=q.horizons,mid=x["6m"],mixed=H.filter(t=>!x[t].same_date);
 const estimated=H.some(t=>x[t].estimate_involved);
 const proxy=H.some(t=>x[t].proxy_involved);
 const quality=(proxy?"Proxy NZD incluso. ":"")+
   (estimated?"Almeno una stima inclusa. ":"")+
   (mixed.length?mixed.length+" scadenze con date diverse. ":"Le due gambe riportano la stessa data per ogni scadenza. ");
 const old=days(today,doc.pricing_source_snapshot_date)>7;
 const ratesText="PRICING RELATIVO · fonte "+doc.pricing_source_snapshot_date+
   (old?" (snapshot oltre 7 giorni, non corrente)":"")+
   " · "+a+"/"+b+": 3M "+fmt(x["3m"].spread_bp)+" pb; 6M "+
   fmt(mid.spread_bp)+" pb; 12M "+fmt(x["12m"].spread_bp)+" pb. "+
   "Al 6M "+a+" "+mid.base_rate_pct+"% ("+mid.base_as_of+
   ", "+mid.base_kind+") e "+b+" "+mid.quote_rate_pct+"% ("+
   mid.quote_as_of+", "+mid.quote_kind+"). "+quality+
   "Sono DIFFERENZE DI LIVELLO, non variazioni OIS, carry, tassi forward o segnali FX.";
 let macroText="MACRO V3 · lettura dinamica non disponibile o periodi/fonte non verificati; tesi canonica invariata.";
 try{
  if(macro&&macroApi?.validate?.(macro,today)&&macroDynamics?.evaluate){
   const m=macroDynamics.evaluate(macro,clean,today,macroApi.validate);
   if(m&&m.fx_bias===null&&m.safe_to_modify_core===false&&m.safe_for_backtest===false){
    const c=m.comparable;
    macroText="MACRO V3 · osservazioni del "+m.as_of_research+
     ": inflazione "+(c.inflation_trend_same_period?"periodi allineati":"periodi non allineati")+
     ", disoccupazione "+(c.labour_trend_same_period?"periodi allineati":"periodi non allineati")+
     ", accelerazione PIL "+(c.growth_acceleration?"confrontabile":"non confrontabile")+
     ". I dati sono rivisti, non point-in-time: nessun nuovo voto FX.";
   }
  }
 }catch(e){/* research source incompatible: never infer a missing macro vote */}
 let priceText="PREZZO · osservazione non verificata; nessuna conferma dedotta.";
 const when=priceMeta?.as_of,verified=priceMeta?.verified===true;
 if(iso(when)&&when<=today&&price&&typeof price==="object"){
  const older=days(today,when)>7;
  const movement=numeric(price.ret1m)?
   "variazione 1M "+fmt(price.ret1m)+"%":"variazione 1M non disponibile";
  const state=["GOOD","BAD","NEUTRAL"].includes(price.pstate)?price.pstate:null;
  const stateText=state==="GOOD"?"allineato alla tesi canonica":
   state==="BAD"?"contrario alla tesi canonica":
   state==="NEUTRAL"?"non risolutivo":"non classificato";
  priceText="PREZZO FX · fixing "+when+(older?" (datato)":"")+
   " · "+movement+"; stato motore: "+stateText+
   (verified?" (feed verificato).":" (snapshot, verificare).")+
   " Il ritorno 1M non misura la reazione a un repricing 6M sincronizzato.";
 }
 return {pair:a+"/"+b,ratesText,macroText,priceText,
  caveatText:"CONTROLLO DA FARE: verificare nuove variazioni 1D/1W di contratti identici, notizie macro e risposta del cambio alla stessa data. Nessun segnale, probabilità di meeting, expected return o backtest generato.",
  mixedDates:mixed.length,estimateInvolved:estimated,proxyInvolved:proxy,
  isTradingSignal:false,policyRepricing:null,expectedReturn:null,
  sourceSnapshotDate:doc.pricing_source_snapshot_date};
}
const api=Object.freeze({SCHEMA,validate,view});
root.FXV2PairTriangulation=api;
if(typeof module==="object"&&module&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
