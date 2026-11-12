'use strict';
/*
 * FX Quant Next — G8 shadow growth model V1.
 *
 * This model predicts the NEXT OBSERVATION-TO-OBSERVATION CHANGE of one
 * *existing selected series* per currency. It does NOT forecast GDP for all
 * countries, release surprises, FX spot, CB policy, or the G8 ranking.
 *
 * Evaluation is strictly expanding-window on the supplied historical ARRAY,
 * but that array can contain REVISIONS and does not include true issue-time
 * release vintages. Therefore the result is retrospective pseudo-OOS,
 * never point-in-time validated; all forecasts remain RESEARCH ONLY.
 *
 * Static policy (no in-sample hyperparameter tuning):
 *   baseline: next change = 0;
 *   candidate: arithmetic average of previous SIX changes;
 *   first 25 changes as minimum warmup, then one-step rolling evaluation;
 *   gate: >=24 monthly or >=16 quarterly pseudo-OOS points,
 *         >=10% reduction in MAE vs flat baseline,
 *         >=60% directional agreement and no negative improvement
 *         in either chronological half, plus source-recency check.
 */
(function(root){
 const target={
  USD:{id:'US_PCEC96_history_value',frequency:'M',reportedRate:false},
  EUR:{id:'EA_RETAIL_VOL_history_value',frequency:'M',reportedRate:false},
  GBP:{id:'UK_RETAIL_VOL_history_value',frequency:'M',reportedRate:false},
  JPY:{id:'JP_RETAIL_history_value',frequency:'M',reportedRate:false},
  CHF:{id:'CH_RETAIL_REAL_history_value',frequency:'M',reportedRate:false},
  CAD:{id:'CA_REAL_GDP_M_history_value',frequency:'M',reportedRate:false},
  AUD:{id:'AU_REAL_GDP_QOQ_ABS_history_value',frequency:'Q',reportedRate:true},
  NZD:{id:'NZ_REAL_GDP_Q_history_value',frequency:'Q',reportedRate:true}
 };
 const number=v=>typeof v==='number'&&Number.isFinite(v);
 const normalized=p=>typeof p==='string'&&/^\d{4}-(?:0[1-9]|1[0-2])(?:-\d{2})?$/.test(p)?p.slice(0,7):null;
 const monthNumber=p=>{const s=normalized(p);return s?Number(s.slice(0,4))*12+Number(s.slice(5,7)):null;};
 const nextPeriod=(d,step)=>{const m=monthNumber(d);if(m===null)return null;
  const y=Math.floor((m-1+step)/12),mo=(m-1+step)%12+1;
  return y+'-'+String(mo).padStart(2,'0');};
 const mean=x=>x.reduce((s,v)=>s+v,0)/x.length;
 const mae=(list,property)=>mean(list.map(x=>Math.abs((property==='guess'?x.guess:0)-x.real)));
 const gain=arr=>arr.length&&mae(arr,'base')>0?100*(1-mae(arr,'guess')/mae(arr,'base')):null;
 const quantile80=x=>{const a=x.slice().sort((b,c)=>b-c);if(!a.length)return null;
   return a[Math.min(a.length-1,Math.ceil(a.length*.80)-1)];};
 const direction=arr=>arr.length?100*arr.filter(x=>Math.sign(x.guess)===Math.sign(x.real)).length/arr.length:null;
 const unavailable=(ccy,reason)=>({ccy,status:'UNAVAILABLE',candidate:false,reason,
   method:'SHADOW_MEAN_6_CHANGES_V1',quality:'NOT_PIT',forecast:null,backtest:null});
 function evaluate(series,ccy,now){
  const meta=target[ccy];
  if(!meta)return unavailable(ccy,'Valuta non supportata');
  const list=Array.isArray(series?.[ccy])?series[ccy]:[];
  const s=list.find(v=>v?.id===meta.id);
  if(!s||!Array.isArray(s.dates)||!Array.isArray(s.values)||s.dates.length!==s.values.length)
   return unavailable(ccy,'Storico selezionato non disponibile o incompleto');
  const nowM=monthNumber(now);
  if(nowM===null)return unavailable(ccy,'Data di valutazione non valida');
  const points=s.dates.map((p,i)=>({raw:p,period:normalized(p),value:s.values[i]}))
   .filter(x=>x.period&&monthNumber(x.period)<=nowM&&number(x.value))
   .sort((a,b)=>a.period.localeCompare(b.period));
  const step=meta.frequency==='Q'?3:1;
  const changes=[];
  for(let i=1;i<points.length;i++){
   const prev=points[i-1],cur=points[i],gap=monthNumber(cur.period)-monthNumber(prev.period);
   if(gap!==step||(!meta.reportedRate&&prev.value<=0))return unavailable(ccy,'Serie con lacune o date duplicate: confronto rifiutato');
   const v=meta.reportedRate?cur.value-prev.value:(cur.value/prev.value-1)*100;
   if(!number(v))return unavailable(ccy,'Variazione non calcolabile');
   changes.push({period:cur.period,value:v});
  }
  if(changes.length<=25)return unavailable(ccy,'Storico insufficiente per la finestra walk-forward');
  const checks=[];
  for(let t=25;t<changes.length;t++){
   const past=changes.slice(t-6,t).map(x=>x.value);
   const guess=mean(past),real=changes[t].value;
   if(!number(guess)||!number(real))return unavailable(ccy,'Backtest numericamente non valido');
   checks.push({period:changes[t].period,guess,real});
  }
  const mid=Math.floor(checks.length/2),first=checks.slice(0,mid),second=checks.slice(mid);
  const totalGain=gain(checks),firstGain=gain(first),secondGain=gain(second);
  const hit=direction(checks);
  const latest=points.at(-1),latestAge=nowM-monthNumber(latest.period);
  const maxAge=meta.frequency==='Q'?6:2;
  const sufficient=checks.length>=(meta.frequency==='Q'?16:24);
  const skill=sufficient&&totalGain!==null&&totalGain>=10&&
   firstGain!==null&&firstGain>=0&&secondGain!==null&&secondGain>=0&&hit!==null&&hit>=60;
  const recent=latestAge>=0&&latestAge<=maxAge;
  const estimate=mean(changes.slice(-6).map(x=>x.value));
  const residuals=checks.map(x=>Math.abs(x.guess-x.real));
  const candidate=Boolean(skill&&recent);
  const changeUnit=meta.reportedRate?'punti percentuali':'%';
  return {ccy,seriesId:s.id,label:s.label,latestPeriod:latest.period,
   nextObservationPeriod:nextPeriod(latest.period,step),frequency:meta.frequency,
   status:candidate?'RESEARCH_CANDIDATE':!sufficient?'INSUFFICIENT_SAMPLE':
    !skill?'NO_BENCHMARK_EDGE':!recent?'STALE_INPUT':'UNAVAILABLE',
   candidate,quality:'RETROSPECTIVE_NOT_POINT_IN_TIME',method:'SHADOW_MEAN_6_CHANGES_V1',
   changeUnit,
   // Never exposed to core signals and only displayed for qualifying candidates.
   forecast:candidate?{nextChange:estimate,unit:changeUnit}:null,
   backtest:{testObservations:checks.length,meanAbsoluteError:mae(checks,'guess'),
    baselineMAE:mae(checks,'base'),improvementPct:totalGain,
    firstHalfImprovementPct:firstGain,secondHalfImprovementPct:secondGain,
    directionalAgreementPct:hit,absoluteErrorP80:quantile80(residuals)},
   restrictions:[
    'Previsione della variazione di una serie osservata, non del PIL complessivo né del cambio FX.',
    'Backtest pseudo-out-of-sample su storico corrente, potenzialmente revisionato: NON point-in-time.',
    'Periodo dell’osservazione non equivale alla data di rilascio ufficiale.',
    'Nessun effetto su classifica G8, pricing monetario, tesi FX o raccomandazioni.'
   ]};
 }
 function analyze({macroSeries,now}){
  const currencies=Object.fromEntries(Object.keys(target).map(ccy=>[ccy,evaluate(macroSeries,ccy,now)]));
  return {schema:'GMFQ_G8_GROWTH_SHADOW_V1',asof:now,
   status:'RESEARCH_ONLY_NOT_PIT',currencies,
   qualified:Object.values(currencies).filter(x=>x.candidate).map(x=>x.ccy),
   disclaimer:'Retrospettivo con dati revisionabili e senza release-vintage. Non utilizzare per il timing FX.'};
 }
 const api={analyze,evaluate,targets:target};
 root.FXQuantGrowthShadow=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
