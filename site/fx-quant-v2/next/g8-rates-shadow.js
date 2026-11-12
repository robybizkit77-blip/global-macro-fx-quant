'use strict';
/*
 * G8 rates shadow estimates V1 — explicitly NON-OBSERVED.
 *
 * CHF: 2Y anchored to last official same-date SNB 2Y/10Y pair, updated by
 * the actual change of official SNB 10Y spot. Sensitivity is fit on SNB
 * daily changes with retrospective expanding-window pseudo-OOS evaluation.
 * Both 10Y dates and source identities are checked. A daily beta applied
 * across multiple days remains an unvalidated extrapolation.
 *
 * NZD: post-roll RBNZ B2 manually observed 2Y + 0/50/100% pass-through
 * of the next same-contract ASX 90d bank-bill 6M daily move. The
 * midpoint is a SENSITIVITY SCENARIO, not a statistically fitted 2Y model.
 * Never use estimates as observed 2Y, same-date 2Y/10Y curves, policy
 * changes, core FX score, backtest, or a trade confirmation.
 */
(function(root){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const isDay=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&
  !Number.isNaN(Date.parse(s+'T00:00:00Z'))&&
  new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
 const age=(a,b)=>isDay(a)&&isDay(b)?
  (Date.parse(b+'T00:00:00Z')-Date.parse(a+'T00:00:00Z'))/86400000:null;
 const round=(v,n=3)=>Math.round((v+Number.EPSILON)*Math.pow(10,n))/Math.pow(10,n);
 const unavailable=reason=>({status:'NON_DISPONIBILE',reason,eligibleForCore:false,
  eligibleForBacktests:false,observationKind:'NOT_AN_OBSERVED_GOVERNMENT_YIELD'});
 const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
 const abs80=a=>a.slice().sort((x,y)=>x-y)[Math.min(a.length-1,Math.ceil(a.length*.8)-1)];
 const beta=pairs=>{
  const den=pairs.reduce((s,x)=>s+x.x*x.x,0);
  return den>1e-8?pairs.reduce((s,x)=>s+x.x*x.y,0)/den:null;
 };
 const weekdays=(start,end)=>{
  const d=age(start,end);if(d===null||d<0||d>7)return null;
  let n=0;
  for(let i=1;i<=d;i++){
   const wd=new Date(Date.parse(start+'T00:00:00Z')+i*86400000).getUTCDay();
   if(wd!==0&&wd!==6)n++;
  }return n;
 };
 function chf({research,chfHistory,spot,now}){
  if(research?.CHF?.ratesResearch?.status!=='STORICO_UFFICIALE_NON_OPERATIVO')
   return unavailable('CHF: storico ufficiale 2Y/10Y non verificato dal bridge');
  const h=chfHistory,rows=h?.observations;
  if(h?.schema!=='GMFQ_FXV2_CHF_SNB_PAIRED_HISTORY_V1'||
     h?.quality!=='SNB_OFFICIAL_OBSERVED_HISTORICAL_RESEARCH'||
     h?.source_url!=='https://data.snb.ch/api/cube/rendeiduebd/data/json/en'||
     h?.eligible_for_core!==false||h?.eligible_for_fx_engine!==false||
     h?.eligible_for_backtests!==false||
     h?.source_latest_vintage_not_point_in_time!==true||
     !Array.isArray(rows)||rows.length<20||
     h.last_observation_date!==research.CHF.ratesResearch.asof||
     h.last_observation_date!==rows.at(-1)?.date||
     spot?.schema!=='GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1'||
     spot?.status!=='OFFICIAL_PUBLISHED_10Y_INFORMATIONAL'||
     spot?.source_url!=='https://www.snb.ch/en/the-snb/mandates-goals/statistics/statistics-pub/current_interest_exchange_rates'||
     spot?.provenance!=='SNB_PUBLIC_PAGE_DATED_EXACT_10Y'||
     spot?.capture_method!=='AUTOMATED_PINNED_OFFICIAL_WEBPAGE'||
     spot?.yield_type!=='SWISS_CONFEDERATION_ZERO_COUPON_SPOT'||
     spot?.tenor!=='10Y'||spot?.has_current_2y!==false||
     spot?.eligible_for_core_signals!==false||
     spot?.eligible_for_curve_spreads!==false||
     !/^[a-f0-9]{64}$/.test(spot?.source_html_sha256||'')||
     !finite(spot?.value_percent)||spot.value_percent< -5||spot.value_percent>15||
     !isDay(spot.as_of)||age(rows.at(-1).date,spot.as_of)<=0||
     age(rows.at(-1).date,spot.as_of)>25||
     age(spot.as_of,now)<0||age(spot.as_of,now)>5)
   return unavailable('CHF: data, famiglia spot o provenienza 10Y non allineata');
  const deltas=[];
  for(let i=1;i<rows.length;i++){
   const p=rows[i-1],q=rows[i];
   if(!isDay(p.date)||!isDay(q.date)||age(p.date,q.date)<1||
      age(p.date,q.date)>4||!finite(p['2Y'])||!finite(q['2Y'])||
      !finite(p['10Y'])||!finite(q['10Y']))return unavailable('CHF: storico irregolare');
   deltas.push({x:(q['10Y']-p['10Y'])*100,y:(q['2Y']-p['2Y'])*100});
  }
  const checks=[];
  for(let i=10;i<deltas.length;i++){
   const b=beta(deltas.slice(0,i));
   if(!finite(b))return unavailable('CHF: impossibile stimare sensibilità 2Y/10Y');
   checks.push({model:Math.abs(deltas[i].y-b*deltas[i].x),
    naive:Math.abs(deltas[i].y)});
  }
  if(checks.length<10)return unavailable('CHF: campione pseudo-out-of-sample insufficiente');
  const b=beta(deltas),modelMAE=mean(checks.map(x=>x.model)),
        baselineMAE=mean(checks.map(x=>x.naive));
  // Do not publish a fitted number if even the retrospective one-step
  // benchmark loses to simply retaining yesterday's 2Y.
  if(!finite(b)||b<0||b>1.8||!finite(modelMAE)||
     baselineMAE<=0||modelMAE>=baselineMAE)
   return unavailable('CHF: modello non migliora il benchmark senza variazione');
  const latest=rows.at(-1);
  const change10bp=(spot.value_percent-latest['10Y'])*100;
  if(!finite(change10bp)||Math.abs(change10bp)>50)
   return unavailable('CHF: variazione 10Y fuori controllo, niente estrapolazione');
  const estimate=latest['2Y']+b*change10bp/100;
  const observedGap=weekdays(latest.date,spot.as_of);
  // weekday() deliberately caps at seven days; for longer gaps,
  // the uncertainty multiplier must be computed on the entire period.
  let workdays=0;
  for(let i=1;i<=age(latest.date,spot.as_of);i++){
   const wd=new Date(Date.parse(latest.date+'T00:00:00Z')+i*86400000).getUTCDay();
   if(wd>0&&wd<6)workdays++;
  }
  const uncertaintyBp=Math.max(3,abs80(checks.map(x=>x.model))*
    Math.sqrt(Math.max(1,workdays)));
  if(!finite(estimate)||estimate< -5||estimate>15||!finite(uncertaintyBp))
   return unavailable('CHF: stima o intervallo non calcolabili');
  return {status:'STIMA_MODELLO_RICERCA',currency:'CHF',
   observationKind:'ESTIMATED_GOVERNMENT_2Y_NOT_AN_OBSERVED_QUOTE',
   asof:spot.as_of,anchorAsOf:latest.date,anchor2Y:latest['2Y'],
   estimate2Y:round(estimate),lower2Y:round(estimate-uncertaintyBp/100),
   upper2Y:round(estimate+uncertaintyBp/100),
   method:'SNB_OBSERVED_SPOT_10Y_DELTA_X_EXPANDING_OLS_BETA',
   confidence:'RICERCA_LIMITATA_NON_PIT',beta:round(b,3),
   observed10YChangeBp:round(change10bp,2),
   pseudoOOSCount:checks.length,modelMAEBp:round(modelMAE,2),
   flatBaselineMAEBp:round(baselineMAE,2),
   pseudoOOSImprovementPct:round(100*(1-modelMAE/baselineMAE),1),
   uncertaintyKind:'EURISTICA_P80_ERRORE_1D_SCALATA_RADICE_TEMPO_NON_INTERVALLO_DI_CONFIDENZA',
   eligibleForCore:false,eligibleForBacktests:false,
   note:'2Y stimato da 10Y spot SNB e sensibilità storica, non rendimento pubblicato. Il test su variazioni giornaliere è retrospettivo, con sole '+
    checks.length+' previsioni, e non valida il salto multi-giorno. Banda euristica non probabilistica.'};
 }
 function nzd({research,nzdMarket,now}){
  if(research?.NZD?.ratesResearch?.status!=='RICERCA_MANUALE_NON_CERTIFICATA')
   return unavailable('NZD: riferimento RBNZ B2 non verificato dal bridge');
  const m=nzdMarket,h=m?.horizons?.['6m'],r=research.NZD.ratesResearch;
  // Only a one-trading-day change may be passed through the earlier 2Y anchor:
  // never use a weekly ASX move as a daily government 2Y observation.
  if(m?.schema!=='GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1'||
     m?.status!=='LIVE_DIRECTIONAL_PROXY_READY'||m?.currency!=='NZD'||
     m?.source_quality!=='OFFICIAL_EXCHANGE_DIRECTIONAL_PROXY'||
     m?.instrument!=='ASX New Zealand 90 Day Bank Accepted Bill Futures (BB)'||
     !/^https:\/\/www\.asx\.com\.au\/data\/futures\/reports\/EODWebMarketSummary\d{6}ZFT\.htm$/.test(m?.source_url||'')||
     m?.governance?.substitutes_for_ois_level!==false||
     m?.governance?.policy_delta_from_proxy_allowed!==false||
     m?.governance?.core_score_effect!=='NONE'||
     m?.governance?.pair_engine_effect!=='NONE'||
     m?.governance?.informational_only!==true||
     !isDay(m.as_of)||weekdays(r.asof,m.as_of)!==1||
     age(m.as_of,now)<0||age(m.as_of,now)>4||
     !finite(h?.change_1d_bp)||Math.abs(h.change_1d_bp)>40||
     !finite(h?.settlement_change)||!finite(h?.settlement_price)||
     !finite(h?.implied_bank_bill_rate)||
     Math.abs(-100*h.settlement_change-h.change_1d_bp)>.11||
     Math.abs(100-h.settlement_price-h.implied_bank_bill_rate)>.011||
     !isDay(h.expiration)||h.expiration<=m.as_of)
   return unavailable('NZD: non c’è un movimento futures omogeneo del giorno successivo');
  // This is 50% passthrough SENSITIVITY, not an estimated empirical beta.
  // The [0%,100%] response is a range of assumptions, not a confidence band.
  const anchor=3.77;
  // The research bridge contains the display label, but the numeric input
  // must be taken explicitly from a reviewed RBNZ row, not from parsed text.
  return {status:'NZD_PENDING_NUMERIC_ANCHOR',anchor,move:h.change_1d_bp};
 }
 function nzWithAnchor(args){
  const raw=nzd(args);
  if(raw.status!=='NZD_PENDING_NUMERIC_ANCHOR')return raw;
  const r=args.nzdResearch;
  const last=r?.daily_observations?.at(-1),check=args.research.NZD.ratesResearch;
  if(r?.schema!=='GMFQ_NZD_RBNZ_B2_POSTROLL_WEB_RESEARCH_V1'||
     r?.source_capture_method!=='PUBLIC_OFFICIAL_PAGE_MANUAL_RESEARCH_NOT_AUTOMATED_FETCH'||
     r?.historical_benchmark_roll_continuity!==false||
     r?.benchmark_2Y!=='April 2029'||r?.benchmark_10Y!=='April 2037'||
     r?.eligible_for_core!==false||r?.eligible_for_backtests!==false||
     !last||last.date!==check.asof||!finite(last['2Y'])||
     Math.abs(last['2Y'])>20)
   return unavailable('NZD: 2Y osservato da RBNZ non coerente con la fonte');
  const movePct=raw.move/100,mid=last['2Y']+.5*movePct,
        low=Math.min(last['2Y'],last['2Y']+movePct),
        high=Math.max(last['2Y'],last['2Y']+movePct);
  return {status:'STIMA_SCENARIO_NON_CALIBRATA',currency:'NZD',
   observationKind:'SENSITIVITY_SCENARIO_NOT_AN_OBSERVED_GOVERNMENT_2Y',
   asof:args.nzdMarket.as_of,anchorAsOf:last.date,anchor2Y:last['2Y'],
   estimate2Y:round(mid),lower2Y:round(low),upper2Y:round(high),
   method:'RBNZ_B2_2Y_PLUS_0_50_100PCT_ASX_BANK_BILL_6M_DAILY_MOVE',
   confidence:'SCENARIO_NON_VALIDATO',marketChangeBp:raw.move,
   assumedPassThrough:0.5,eligibleForCore:false,eligibleForBacktests:false,
   uncertaintyKind:'SENSITIVITA_0_A_100PCT_NON_INTERVALLO_DI_CONFIDENZA',
   note:'Scenario su un solo giorno: 2Y RBNZ manuale '+last.date+
    ' + 50% del movimento futures ASX 6M '+args.nzdMarket.as_of+
    '. I futures bank bill incorporano basis e credito; il coefficiente è una scelta di sensibilità NON calibrata, non una previsione validata.'};
 }
 function analyze(args){
  const now=args?.now;
  if(!isDay(now))return {status:'NON_DISPONIBILE',currencies:{},
    policy:'Nessun dato futuro o data non verificata'};
  return {schema:'GMFQ_G8_RATES_SHADOW_V1',status:'RICERCA_STIME_NON_OPERATIVE',
   asof:now,currencies:{CHF:chf(args),NZD:nzWithAnchor(args)},
   policy:'Stime separate da dati osservati, differenziali, ranking FX, segnali, size e backtest.'};
 }
 const api={analyze,chf,nzd:nzWithAnchor};
 root.FXQuantG8RatesShadow=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
