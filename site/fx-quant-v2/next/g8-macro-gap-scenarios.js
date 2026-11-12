'use strict';
/*
 * FX Quant NEXT — G8 macro data-gap scenarios.
 *
 * Purpose: a transparent, automatically recalculated estimate for the
 * latest COMPLETED monthly/quarterly reference period still missing
 * from each currency's selected official macro series.
 *
 * Two predeclared candidates: flat last release vs last-six-changes drift.
 * Historical expanding-origin evaluation uses exactly the SAME number of
 * monthly/quarterly steps as today's missing observation. No look-ahead to
 * later rows. Report drift as a *model candidate* only if it beats flat on
 * MAE by >=10%, each chronological half by >=0%, and direction >=60%.
 * If not: show drift merely as an UNVALIDATED sensitivity scenario.
 *
 * Warning: source files are latest-revised histories, NOT release vintages.
 * "Pseudo OOS" is NOT a point-in-time backtest or an FX trading edge.
 * Estimates never replace observations or enter official data, evidence
 * counts, relative rates, central bank pricing, rankings or pair signals.
 */
(function(root){
 const choices={
  USD:{id:'US_PCEC96_history_value',freq:'M',rate:false},
  EUR:{id:'EA_RETAIL_VOL_history_value',freq:'M',rate:false},
  GBP:{id:'UK_RETAIL_VOL_history_value',freq:'M',rate:false},
  JPY:{id:'JP_RETAIL_history_value',freq:'M',rate:false},
  CHF:{id:'CH_RETAIL_REAL_history_value',freq:'M',rate:false},
  CAD:{id:'CA_REAL_GDP_M_history_value',freq:'M',rate:false},
  AUD:{id:'AU_REAL_GDP_QOQ_ABS_history_value',freq:'Q',rate:true},
  NZD:{id:'NZ_REAL_GDP_Q_history_value',freq:'Q',rate:true}
 };
 const num=x=>typeof x==='number'&&Number.isFinite(x);
 const period=x=>typeof x==='string'&&/^\d{4}-(0[1-9]|1[0-2])(?:-\d{2})?$/.test(x)?
  (x.length===10&&new Date(x+'T00:00:00Z').toISOString().slice(0,10)!==x?null:x.slice(0,7)):null;
 const index=x=>{const p=period(x);return p?Number(p.slice(0,4))*12+Number(p.slice(5,7))-1:null;};
 const toPeriod=i=>Math.floor(i/12)+'-'+String(i%12+1).padStart(2,'0');
 const sign=x=>x>0?'aumento':x<0?'diminuzione':'stabile';
 const mean=a=>a.reduce((v,x)=>v+x,0)/a.length;
 const p80=a=>{if(!a.length)return null;const x=a.slice().sort((a,b)=>a-b);return x[Math.ceil(.8*x.length)-1];};
 const round=(x,n=3)=>Math.round((x+Number.EPSILON)*10**n)/10**n;
 const missing=(ccy,reason)=>({ccy,status:'NON_DISPONIBILE',reason,
  sourcePeriod:null,targetPeriod:null,forecast:null,backtest:null,
  eligibleForCore:false,eligibleForTradeBacktests:false});
 function estimate(v,drift,h,rate){
  return rate?v+drift*h:v*Math.pow(1+drift/100,h);
 }
 function change(v,prev,rate){
  return rate?v-prev:prev>0?(v/prev-1)*100:null;
 }
 function unitError(pred,truth,rate){
  return rate?Math.abs(pred-truth):truth>0?100*Math.abs(pred-truth)/truth:null;
 }
 function evaluate(series,ccy,now){
  const spec=choices[ccy];
  if(!spec)return missing(ccy,'Valuta G8 non supportata');
  const at=index(now);
  if(at===null||typeof now!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(now))
   return missing(ccy,'Data corrente non verificata');
  const fullMonth=at-1;
  const target=spec.freq==='Q'?fullMonth-(fullMonth%3===2?0:(fullMonth%3+1)):fullMonth;
  const list=Array.isArray(series?.[ccy])?series[ccy]:[];
  const s=list.find(x=>x?.id===spec.id);
  if(!s||s.frequency!==spec.freq||typeof s.source_file!=='string'||
      s.source_file.trim().length<4||!Array.isArray(s.values)||
      !Array.isArray(s.dates)||s.values.length!==s.dates.length)
   return missing(ccy,'Serie, fonte o frequenza non verificabili');
  const points=[];
  for(let i=0;i<s.dates.length;i++){
   const d=index(s.dates[i]),v=s.values[i];
   if(d===null)return missing(ccy,'Data economica non interpretabile');
   // A future observation must not affect today's scenario or test.
   if(d>target)continue;
   if(!num(v)||!spec.rate&&v<=0)
    return missing(ccy,'Osservazione non numerica o livello non positivo');
   if(points.length&&d<=points.at(-1).i)
    return missing(ccy,'Date duplicate o fuori ordine');
   const prev=points.at(-1);
   if(prev&&d-prev.i!==(spec.freq==='Q'?3:1))
    return missing(ccy,'Lacuna nella storia: niente serie interpolata');
   if(spec.freq==='Q'&&d%3!==2)
    return missing(ccy,'Quarterly date non corrisponde a fine trimestre');
   points.push({i:d,v,source:s.dates[i]});
  }
  if(points.length<22)return missing(ccy,'Storico insufficiente');
  const latest=points.at(-1),steps=spec.freq==='Q'?3:1;
  const lag=target-latest.i;
  if(lag<=0)return { ...missing(ccy,'Il periodo completo risulta già osservato'),
   status:'PERIODO_GIA_OSSERVATO',sourcePeriod:toPeriod(latest.i),targetPeriod:toPeriod(target)};
  if(lag%steps!==0)return missing(ccy,'Frequenza non omogenea');
  const h=lag/steps;
  if(h>(spec.freq==='Q'?2:4))
   return missing(ccy,'Ultimo dato troppo vecchio per questo scenario');
  const changes=[];
  for(let i=1;i<points.length;i++){
   const c=change(points[i].v,points[i-1].v,spec.rate);
   if(!num(c))return missing(ccy,'Crescita storica non valida');
   changes.push(c);
  }
  const warmup=spec.freq==='Q'?12:25;
  const checks=[];
  // For each historical origin t, pretend rows after t do not yet exist.
  // The holdout at t+h is never part of the six prior changes.
  for(let t=warmup;t<points.length-h;t++){
   const past=changes.slice(t-6,t),drift=mean(past);
   const predicted=estimate(points[t].v,drift,h,spec.rate);
   const actual=points[t+h].v,modelErr=unitError(predicted,actual,spec.rate);
   const flatErr=unitError(points[t].v,actual,spec.rate);
   if(!num(modelErr)||!num(flatErr)||!num(predicted))
    return missing(ccy,'Verifica storica non calcolabile');
   checks.push({modelErr,flatErr,
    directionOK:Math.sign(predicted-points[t].v)===Math.sign(actual-points[t].v)});
  }
  const enough=checks.length>=(spec.freq==='Q'?16:24);
  if(!enough)return missing(ccy,'Campione insufficiente sullo stesso orizzonte');
  const metric=x=>{const model=mean(x.map(z=>z.modelErr)),
    baseline=mean(x.map(z=>z.flatErr));
   return baseline>0?100*(1-model/baseline):null;};
  const totalGain=metric(checks),split=Math.floor(checks.length/2);
  const left=metric(checks.slice(0,split)),right=metric(checks.slice(split));
  const hit=100*checks.filter(z=>z.directionOK).length/checks.length;
  const qualified=totalGain!==null&&totalGain>=10&&left!==null&&left>=0&&
   right!==null&&right>=0&&hit>=60;
  const drift=mean(changes.slice(-6));
  if(!num(drift)||Math.abs(drift)>(spec.rate?20:30)||
     !num(latest.v))return missing(ccy,'Variazione modellata fuori dai limiti');
  const forecast=estimate(latest.v,drift,h,spec.rate);
  if(!num(forecast)||(!spec.rate&&forecast<=0))
   return missing(ccy,'Scenario numerico non accettabile');
  // P80 is a descriptive historical error yardstick, NOT an 80% CI.
  // When the model fails the flat benchmark, use the WIDER of the
  // model and flat residual bands to avoid false precision.
  const modelP80=p80(checks.map(z=>z.modelErr)),
   flatP80=p80(checks.map(z=>z.flatErr));
  const width=Math.max(modelP80,flatP80);
  const lower=spec.rate?forecast-width:forecast*(1-width/100);
  const upper=spec.rate?forecast+width:forecast*(1+width/100);
  if(!num(lower)||!num(upper)||lower>upper||(!spec.rate&&lower<=0))
   return missing(ccy,'Intervallo indicativo non valido');
  const observed=latest.v;
  const delta=spec.rate?forecast-observed:(forecast/observed-1)*100;
  return {ccy,status:qualified?'MODELLO_RETROSPETTIVO_PROMETTENTE':'SCENARIO_NON_VALIDATO',
   asof:now,sourcePeriod:toPeriod(latest.i),targetPeriod:toPeriod(target),
   source:s.source_file,seriesId:s.id,label:s.label,unit:s.unit,
   frequency:spec.freq,horizonSteps:h,method:'MEAN_OF_LAST_6_CHANGES_FIXED',
   baseline:'LAST_OBSERVED_VALUE_NO_CHANGE',quality:'REVISED_HISTORY_NOT_POINT_IN_TIME',
   reportedRate:spec.rate,observedValue:observed,scenarioValue:round(forecast,4),
   deltaFromObserved:round(delta,3),deltaUnit:spec.rate?'punti percentuali':'%',
   baselineValue:observed,rangeLow:round(lower,4),rangeHigh:round(upper,4),
   rangeKind:'HISTORICAL_ABS_ERROR_P80_HEURISTIC_NOT_CONFIDENCE_INTERVAL',
   skillValidatedPIT:false,pseudoOOSQualified:qualified,
   historicalErrorUnit:spec.rate?'punti percentuali':'% del livello effettivo',
   backtest:{points:checks.length,horizonSteps:h,
    modelMAE:round(mean(checks.map(x=>x.modelErr)),3),
    baselineMAE:round(mean(checks.map(x=>x.flatErr)),3),
    modelP80:round(modelP80,3),flatP80:round(flatP80,3),
    improvementPct:round(totalGain,1),firstHalfGainPct:round(left,1),
    secondHalfGainPct:round(right,1),directionHitPct:round(hit,1)},
   eligibleForCore:false,eligibleForTradeBacktests:false,
   interpretation:qualified?
    'Migliora il benchmark senza variazione in un test retrospettivo, ma non è validato point-in-time.':
    'La deriva recente non batte stabilmente la previsione senza variazione: mostra solo uno scenario di sensibilità.',
   directionDescription:sign(delta)};
 }
 function analyze({macroSeries,now}){
  const currencies=Object.fromEntries(Object.keys(choices).map(ccy=>[ccy,evaluate(macroSeries,ccy,now)]));
  return {schema:'GMFQ_G8_MACRO_GAP_SCENARIOS_V1',asof:now,
   status:'ESTIMATES_RESEARCH_ONLY_REVISED_HISTORY_NOT_PIT',
   currencies,modelCandidates:Object.values(currencies)
    .filter(x=>x.pseudoOOSQualified).map(x=>x.ccy),
   readyCount:Object.values(currencies).filter(x=>x.scenarioValue!==undefined).length,
   warning:'Proiezioni della serie selezionata per il periodo economico ancora mancante, non ora di pubblicazione e non PIL totale se la serie è retail/consumi. Nessun trading edge o punteggio FX.'};
 }
 const api={evaluate,analyze,choices};
 root.FXQuantG8MacroGap=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
