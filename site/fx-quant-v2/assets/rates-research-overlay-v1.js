/* V2 research-only government yield view.
 * Shares the dated CHF/NZD working model and observed RBA weekly F2
 * across Valute, Macro and Coppie. NEVER promotes to FX Core/backtests.
 */
(function(root){
 "use strict";
 const EXPECTED='GMFQ_FXV2_AUD_RBA_F2_RESEARCH_V1';
 const valid=(v,min=-5,max=25)=>typeof v==='number'&&Number.isFinite(v)&&v>min&&v<max;
 const iso=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&!Number.isNaN(Date.parse(d+'T00:00:00Z'));
 const age=(now,date)=>Math.round((Date.parse(now+'T12:00:00Z')-Date.parse(date+'T12:00:00Z'))/86400000);
 const cloneRow=x=>x&&typeof x==='object'?{...x}:x;
 function apply({canonical,research=null,proxy=null,anchor=null,aud=null,today}){
  const rates={};
  for(const [c,r] of Object.entries(canonical||{}))rates[c]=cloneRow(r);
  const result={schema:'GMFQ_FXV2_RESEARCH_RATES_SHARED_V1',
   rates,applied:[],working:null,no_core_effect:true,
   eligible_for_fx_engine:false,eligible_for_backtests:false};
  if(!iso(today)||!canonical||typeof canonical!=='object')return result;
  const model=root.FXV2RatesWorking?.derive(canonical,research,today,proxy,anchor);
  if(model?.schema==='GMFQ_FXV2_WORKING_RATES_V1'&&
    model.eligible_for_fx_engine===false&&model.eligible_for_backtests===false){
   result.working=model;
   for(const c of ['CHF','NZD']){
    const row=model.rates?.[c];
    if(row&&iso(row.date)&&row.date<=today&&
       valid(row['2Y'])&&valid(row['10Y'])&&row.no_core_effect===true&&
       (!iso(canonical[c]?.date)||row.date>canonical[c].date)){
     rates[c]={...rates[c],...row};
     result.applied.push(c);
    }
   }
  }
  const x=aud, r=canonical?.AUD;
  if(x?.schema===EXPECTED&&x.currency==='AUD'&&
     x.status==='OFFICIAL_F2_CSV_FETCHED_RESEARCH_ONLY'&&
     x.source_download_verified===true&&x.same_date_same_source===true&&
     x.eligible_for_core===false&&x.eligible_for_fx_pair_engine===false&&
     x.eligible_for_backtests===false&&
     x.canonical_government_rates_untouched===true&&x.research_only===true&&
     x.source_url==='https://www.rba.gov.au/statistics/tables/csv/f2-data.csv'&&
     x.series_2Y==='FCMYGBAG2D'&&x.series_10Y==='FCMYGBAG10D'&&
     iso(x.as_of)&&iso(x.publication_date)&&iso(x.previous_same_series_as_of)&&
     x.previous_same_series_as_of<x.as_of&&
     x.as_of<=x.publication_date&&x.publication_date<=today&&
     x.as_of>(r?.date||'')&&x.as_of<=today&&
     valid(x['2Y'])&&valid(x['10Y'])&&valid(x.curve_bp,-1000,2000)&&
     Math.abs((x['10Y']-x['2Y'])*100-x.curve_bp)<0.03&&
     Number.isFinite(x.change_2y_bp)&&Number.isFinite(x.change_10y_bp)&&
     age(today,x.as_of)>=0){
    const stale=age(today,x.as_of)>10;
    rates.AUD={...rates.AUD,'2Y':x['2Y'],'10Y':x['10Y'],date:x.as_of,
      curve_bp:x.curve_bp,chg2_bp:x.change_2y_bp,chg10_bp:x.change_10y_bp,
      quality:'RBA F2 2Y/10Y OSSERVATI · RICERCA V2'+(stale?' · RIFERIMENTO STORICO':''),
      source:x.source,source_date:x.as_of,evidence_date:x.as_of,
      estimated:true,research_observed:true,stale_source:stale,
      tenor_quality:{'2Y':'OSSERVATO','10Y':'OSSERVATO'},
      working_method:'RBA_F2_SAME_DATE_OBSERVED_RESEARCH',
      assumptions:'RBA F2 stessa osservazione 2Y/10Y '+x.as_of+
       '; confronto precedente '+x.previous_same_series_as_of+
       '. Pubblicazione '+x.publication_date+', settimanale. Non Core.',
      no_core_effect:true,no_inferred_market_move:false};
    result.applied.push('AUD');
  }
  return result;
 }
 const SOURCE='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/';
 async function retrieve(url){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8500);
  try{
   const res=await fetch(url,{cache:'no-store',signal:controller.signal});
   if(!res.ok)throw Error('V2 research source HTTP '+res.status);
   return res.json();
  }finally{clearTimeout(timer);}
 }
 async function firstAvailable(urls,fetchJson){
  for(const u of urls)try{return await fetchJson(u);}catch(error){
   if(u===urls.at(-1))console.warn('[FXV2 Rates Research] Dated source unavailable:',u,error);
  }
  return null;
 }
 async function load({canonical,today,fetchJson=retrieve}){
  const [research,aud,anchor,proxy]=await Promise.all([
   firstAvailable(['./chf-nzd-benchmark-research.json',
    SOURCE+'site/fx-quant-v2/chf-nzd-benchmark-research.json'],fetchJson),
   firstAvailable(['./aud-rba-f2-research.json',
    SOURCE+'site/fx-quant-v2/aud-rba-f2-research.json'],fetchJson),
   firstAvailable(['./nzd-asx-government-anchor-v1.json'],fetchJson),
   firstAvailable([SOURCE+'live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json'],fetchJson)
  ]);
  return apply({canonical,research,aud,anchor,proxy,today});
 }
 const api=Object.freeze({apply,load});
 root.FXV2RatesResearchOverlay=api;
 if(typeof module==='object'&&module&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
