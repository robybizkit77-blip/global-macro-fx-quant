'use strict';
/*
 * FX Quant Next — G8 inflation and labour gap models.
 *
 * Forecast subject: latest completed month/quarter missing from the site's
 * SELECTED historical series. These are gaps in the repository, NOT claims
 * that an official release has not yet been published to the outside world.
 *
 * Inflation: headline CPI year-on-year, except USD derived YoY from the
 * official CPI headline INDEX series (12 same-month lags). Labour: unemployment
 * rate. All forecasts and historical errors are in PERCENTAGE POINTS.
 *
 * Fixed candidates: retain latest observed rate (flat) or project average
 * of six previous one-period rate changes over the actual missing horizon.
 * Backtest expanding historical origins against the same horizon, compare
 * MAE and halves and direction. Without verified advantage, use flat as
 * central baseline and show drift ONLY as an alternative sensitivity.
 *
 * Historical input revisions and release vintages are not point-in-time
 * certified. No estimate changes canonical data or FX signals. No estimates
 * of economic releases, OIS, trades, probabilities or FX ranking.
 */
(function(root){
 const specs={
  USD:{inflation:{id:'US_CPIAUCSL_history_value',freq:'M',kind:'CPI_INDEX_DERIVED_YOY'},
       labour:{id:'US_UNRATE_history_value',freq:'M'}},
  EUR:{inflation:{id:'EA_HICP_HEADLINE_YOY_history_value',freq:'M'},
       labour:{id:'EA_UNEMP_history_value',freq:'M'}},
  GBP:{inflation:{id:'UK_CPI_HEADLINE_YOY_history_value',freq:'M'},
       labour:{id:'UK_UNEMP_RATE_history_value',freq:'M'}},
  JPY:{inflation:{id:'JP_CPI_HEADLINE_YOY_history_value',freq:'M'},
       labour:{id:'JP_UNEMP_RATE_history_value',freq:'M'}},
  CHF:{inflation:{id:'CH_CPI_HEADLINE_YOY_history_value',freq:'M'},
       labour:{id:'CH_UNEMP_RATE_history_value',freq:'M'}},
  CAD:{inflation:{id:'CA_CPI_HEADLINE_YOY_history_value',freq:'M'},
       labour:{id:'CA_UNEMP_RATE_history_value',freq:'M'}},
  AUD:{inflation:{id:'AU_CPI_HEADLINE_Q_YOY_history_value',freq:'Q'},
       labour:{id:'AU_UNEMP_RATE_history_value',freq:'M'}},
  NZD:{inflation:{id:'NZ_CPI_HEADLINE_YOY_history_value',freq:'Q'},
       labour:{id:'NZ_UNEMP_RATE_history_value',freq:'Q'}}
 };
 const expectedFiles={
  US_CPIAUCSL_history_value:'US_CPIAUCSL_history.csv',
  US_UNRATE_history_value:'US_UNRATE_history.csv',
  EA_HICP_HEADLINE_YOY_history_value:'EA_HICP_HEADLINE_YOY_history.csv',
  EA_UNEMP_history_value:'EA_UNEMP_history.csv',
  UK_CPI_HEADLINE_YOY_history_value:'UK_CPI_HEADLINE_YOY_history.csv',
  UK_UNEMP_RATE_history_value:'UK_UNEMP_RATE_history.csv',
  JP_CPI_HEADLINE_YOY_history_value:'JP_CPI_HEADLINE_YOY_history.csv',
  JP_UNEMP_RATE_history_value:'JP_UNEMP_RATE_history.csv',
  CH_CPI_HEADLINE_YOY_history_value:'CH_CPI_HEADLINE_YOY_history.csv',
  CH_UNEMP_RATE_history_value:'CH_UNEMP_RATE_history.csv',
  CA_CPI_HEADLINE_YOY_history_value:'CA_CPI_HEADLINE_YOY_history.csv',
  CA_UNEMP_RATE_history_value:'CA_UNEMP_RATE_history.csv',
  AU_CPI_HEADLINE_Q_YOY_history_value:'AU_CPI_HEADLINE_Q_YOY_history.csv',
  AU_UNEMP_RATE_history_value:'AU_UNEMP_RATE_history.csv',
  NZ_CPI_HEADLINE_YOY_history_value:'NZ_CPI_HEADLINE_YOY_history.csv',
  NZ_UNEMP_RATE_history_value:'NZ_UNEMP_RATE_history.csv'
 };
 const number=x=>typeof x==='number'&&Number.isFinite(x);
 const monthIndex=s=>{
  if(typeof s!=='string'||!/^\d{4}-(?:0[1-9]|1[0-2])(?:-\d{2})?$/.test(s))return null;
  if(s.length===10){
   const ms=Date.parse(s+'T00:00:00Z');
   if(!Number.isFinite(ms)||new Date(ms).toISOString().slice(0,10)!==s)return null;
  }
  return Number(s.slice(0,4))*12+Number(s.slice(5,7))-1;
 };
 const isoMonth=m=>Math.floor(m/12)+'-'+String(m%12+1).padStart(2,'0');
 const round=(v,n=3)=>Math.round((v+Number.EPSILON)*10**n)/10**n;
 const mean=x=>x.reduce((v,r)=>v+r,0)/x.length;
 const percentile80=x=>{const z=x.slice().sort((a,b)=>a-b);
  return z.length?z[Math.ceil(z.length*.8)-1]:null;};
 const unavailable=(ccy,axis,reason)=>({ccy,axis,status:'NON_DISPONIBILE',
  reason,eligibleForCore:false,eligibleForTrading:false,forecast:null,
  observedValue:null,targetPeriod:null,backtest:null});
 const describe=(axis)=>axis==='inflation'?'Inflazione headline YoY':'Disoccupazione';
 function evaluate(series,ccy,axis,now){
  const spec=specs[ccy]?.[axis];
  if(!spec)return unavailable(ccy,axis,'Asse macro non supportato');
  if(typeof now!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(now)||
     !Number.isFinite(Date.parse(now+'T00:00:00Z'))||
     new Date(now+'T00:00:00Z').toISOString().slice(0,10)!==now)
   return unavailable(ccy,axis,'Data di valutazione non valida');
  const month=monthIndex(now),lastCompleted=month-1;
  const target=spec.freq==='Q'?lastCompleted-((lastCompleted+1)%3):lastCompleted;
  const chosen=(Array.isArray(series?.[ccy])?series[ccy]:[]).filter(s=>s?.id===spec.id);
  if(chosen.length!==1)return unavailable(ccy,axis,'Serie storica mancante o ambigua');
  const s=chosen[0];
  if(s.frequency!==spec.freq||!Array.isArray(s.values)||
     !Array.isArray(s.dates)||s.values.length!==s.dates.length||
     s.source_file!==expectedFiles[spec.id])
   return unavailable(ccy,axis,'Identità, frequenza o fonte non verificata');
  const points=[];
  const freqStep=spec.freq==='Q'?3:1;
  let equivalentDuplicates=0,missingHistoricalPeriods=0;
  for(let i=0;i<s.dates.length;i++){
   const p=monthIndex(s.dates[i]);
   if(p===null)return unavailable(ccy,axis,'Periodo storico malformato');
   if(p>target)continue; // Never use observations after the as-of target
   if(spec.freq==='Q'&&p%3!==2)return unavailable(ccy,axis,'Trimestre non omogeneo');
   const v=s.values[i];
   if(!number(v)||v < (spec.kind==='CPI_INDEX_DERIVED_YOY'?1:-30)||
      v > (spec.kind==='CPI_INDEX_DERIVED_YOY'?1000:100))
    return unavailable(ccy,axis,'Dato storico non valido');
   if(points.length){
    const old=points.at(-1),delta=p-old.m;
    if(delta===0){
     // Actual US unemployment archive carries same-month YYYY-MM and
     // YYYY-MM-DD rows. Dedupe only if their numeric facts are IDENTICAL.
     if(Math.abs(v-old.v)>1e-10)
      return unavailable(ccy,axis,'Duplicato con valori discordanti');
     equivalentDuplicates++;
     continue;
    }
    if(delta<0||delta%freqStep!==0)
     return unavailable(ccy,axis,'Periodi fuori ordine o frequenze diverse');
    // Gaps such as missing US CPI October 2025 are NEVER interpolated.
    // Only calendar-contiguous historical windows become eligible for OOS.
    missingHistoricalPeriods+=delta/freqStep-1;
   }
   points.push({m:p,v});
  }
  if(points.length<35)return unavailable(ccy,axis,'Campione insufficiente');
  const derived=spec.kind==='CPI_INDEX_DERIVED_YOY';
  const byIndex=new Map(points.map(p=>[p.m,p.v]));
  // An actual CPI YoY needs a twelve-month calendar-aligned index, not
  // a row twelve observations back (which breaks around missing months).
  const rates=derived?points.filter(p=>byIndex.has(p.m-12)).map(p=>({
    m:p.m,v:100*(p.v/byIndex.get(p.m-12)-1)})):points;
  if(rates.length<23)return unavailable(ccy,axis,'Campione trasformato insufficiente');
  if(rates.some(p=>!number(p.v)||p.v< -30||p.v>100))
   return unavailable(ccy,axis,'Tasso percentuale derivato non valido');
  const byRate=new Map(rates.map(p=>[p.m,p.v]));
  const last=rates.at(-1),step=freqStep,gap=target-last.m;
  if(gap<0||gap%step!==0)return unavailable(ccy,axis,'Periodo più recente non allineato');
  const info={
   ccy,axis,label:describe(axis),unit:'%',source:s.source_file,
   seriesId:spec.id,frequency:spec.freq,sourcePeriod:isoMonth(last.m),
   targetPeriod:isoMonth(target),observedValue:round(last.v,3),
   sourceQuality:derived?'CPI_INDEX_YOY_DERIVED_FROM_HISTORICAL_INDEX':
    'REPORTED_HISTORICAL_RATE',
   historicalVintage:'LATEST_REVISED_HISTORY_NO_RELEASE_TIMESTAMP',
   sourceQualityAudit:{
    missingHistoricalPeriods,identicalMonthRowsDeduplicated:equivalentDuplicates,
    imputedHistoricalMonths:0,calendarAlignedYoY:derived
   },
   eligibleForCore:false,eligibleForTrading:false,
  };
  if(gap===0)return {...info,status:'GIA_OSSERVATO',forecast:null,
   reason:'Il periodo economico completato è già presente: nessuna stima necessaria',
   backtest:null};
  const horizon=gap/step;
  if(horizon>(spec.freq==='Q'?2:3))
   return {...unavailable(ccy,axis,'Gap troppo esteso: niente estrapolazione'),...info,
    targetPeriod:isoMonth(target),status:'FONTE_TROPPO_VECCHIA'};
  const sixChanges=m=>{
   const changes=[];
   for(let j=0;j<6;j++){
    const cur=byRate.get(m-j*step),prev=byRate.get(m-(j+1)*step);
    if(!number(cur)||!number(prev))return null;
    changes.push(cur-prev);
   }
   return mean(changes);
  };
  const warm=spec.freq==='Q'?12:25,checks=[];
  for(let i=warm;i<rates.length;i++){
   const origin=rates[i],actual=byRate.get(origin.m+horizon*step);
   const avg=sixChanges(origin.m);
   if(!number(actual)||!number(avg))continue; // never bridge missing history
   const drift=origin.v+avg*horizon,flat=origin.v;
   if(![drift,flat,actual].every(number))
    return unavailable(ccy,axis,'Calcolo non finito');
   checks.push({model:Math.abs(actual-drift),flat:Math.abs(actual-flat),
    direction:Math.sign(drift-flat)===Math.sign(actual-flat)});
  }
  if(checks.length<(spec.freq==='Q'?16:24))
   return {...unavailable(ccy,axis,'Esempi pseudo-OOS sufficienti non disponibili'),...info};
  const metrics=xs=>{
   if(!xs.length)return null;
   const b=mean(xs.map(x=>x.flat));
   return b>1e-10?100*(1-mean(xs.map(x=>x.model))/b):null;
  };
  const split=Math.floor(checks.length/2);
  const gain=metrics(checks),gain1=metrics(checks.slice(0,split)),
        gain2=metrics(checks.slice(split));
  const hit=100*checks.filter(x=>x.direction).length/checks.length;
  const qualifies=gain!==null&&gain>=10&&gain1!==null&&gain1>=0&&
    gain2!==null&&gain2>=0&&hit>=60;
  const past=sixChanges(last.m);
  if(!number(past))return {...unavailable(ccy,axis,
    'Ultime sei variazioni non consecutive: impossibile stimare'),...info};
  const trend=last.v+past*horizon;
  if(!number(trend)||Math.abs(trend-last.v)>12)
   return unavailable(ccy,axis,'Scenario di trend fuori dai limiti');
  // Fallback is an estimate too, but it is only the constant-rate baseline;
  // do not call a losing moving-average model statistically predictive.
  const forecast=qualifies?trend:last.v,alternative=qualifies?last.v:trend;
  const errP80=percentile80(checks.map(x=>x.model)),
        baseP80=percentile80(checks.map(x=>x.flat)),
        width=Math.max(errP80,baseP80);
  const low=axis==='labour'?Math.max(0,forecast-width):forecast-width,
        high=forecast+width;
  if(![forecast,alternative,width,low,high].every(number))
   return unavailable(ccy,axis,'Stima o incertezza non calcolabile');
  return {...info,status:qualifies?'MODELLO_RETROSPETTIVO_PROMETTENTE':
     'SCENARIO_BASELINE_NON_VALIDATO',
   forecast:round(forecast,3),alternativeScenario:round(alternative,3),
   driftScenario:round(trend,3),flatScenario:round(last.v,3),
   forecastMethod:qualifies?'SIX_CHANGE_DRIFT_HORIZON_MATCHED':
    'FLAT_RATE_BENCHMARK_NO_VALIDATED_TREND',
   estimatedChangePp:round(forecast-last.v,3),horizonSteps:horizon,
   pseudoOOSQualified:qualifies,skillValidatedPIT:false,
   uncertainty:{low:round(low,3),high:round(high,3),
    historicalP80ErrorPp:round(width,3),
    interpretation:'FASCIA_ERRORE_STORICO_NON_INTERVALLO_DI_CONFIDENZA'},
   backtest:{count:checks.length,horizonSteps:horizon,
    modelMAEPp:round(mean(checks.map(x=>x.model)),3),
    flatMAEPp:round(mean(checks.map(x=>x.flat)),3),
    gainPct:round(gain,1),firstHalfGainPct:round(gain1,1),
    secondHalfGainPct:round(gain2,1),directionHitPct:round(hit,1)},
   interpretation:qualifies?'Il trend batte il benchmark senza variazione in un test retrospettivo; non è verificato point-in-time.':
    'Il trend non dimostra vantaggio rispetto al dato invariato: stima centrale conservativa, con scenario di trend separato.'
  };
 }
 function analyze({macroSeries,now}){
  const currencies={};
  for(const ccy of Object.keys(specs)){
   currencies[ccy]={
    inflation:evaluate(macroSeries,ccy,'inflation',now),
    labour:evaluate(macroSeries,ccy,'labour',now),
   };
  }
  const rows=Object.values(currencies).flatMap(x=>[x.inflation,x.labour]);
  return {schema:'GMFQ_FXV2_G8_INFLATION_LABOUR_SHADOW_V1',asof:now,
   status:'RESEARCH_GAPS_ONLY_NOT_PIT',
   currencies,
   estimates:rows.filter(x=>typeof x.forecast==='number').length,
   alreadyObserved:rows.filter(x=>x.status==='GIA_OSSERVATO').length,
   retrospectiveCandidates:rows.filter(x=>x.pseudoOOSQualified).map(x=>x.ccy+'_'+x.axis),
   policy:'Solo gap archivio: non sostituire dati ufficiali, cambiare score, pricing monetario, ranking o segnali FX. Non sono anticipazioni dei comunicati né previsioni di sorpresa.'
  };
 }
 const api={analyze,evaluate,specs};
 root.FXQuantInflationLabourShadow=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
