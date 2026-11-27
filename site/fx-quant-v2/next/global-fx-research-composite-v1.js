'use strict';
/* Experimental synthesis, not a calibrated FX forecast.
 * WANT/CAN is a qualitative constraint, not an extra correlated factor.
 * Official-rate-only baseline; missing weight remains an identification range.
 * Never feeds the operational rank or 28-pair engine. */
(function(root){
 const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
 const WEIGHTS=[['macro','Macro',40],['rates','Tassi attesi',30],['positioning','Posizionamento',15],['price','Prezzo',15]];
 const finite=Number.isFinite;
 const good=x=>finite(x)&&x>=0&&x<=10;
 // Completion at SCORE level, never synthetic economic observations.
 // Each family keeps its intended weight; missing dimensions inherit its
 // conditional score, an explicit within-family extrapolation assumption.
 function macroEnhanced(a){
  const expected={gdp:15,jobs:20,demand:15,industry:10,services:15,house:10,finance:10,leading:5};
  if(!a||!Array.isArray(a.families)||a.families.length!==8)return null;
  const keys=new Set();
  for(const f of a.families){
   if(!Object.hasOwn(expected,f.key)||keys.has(f.key)||f.weight!==expected[f.key]||
     !good(f.score)||!finite(f.coverage)||f.coverage<=0||f.coverage>1)return null;
   keys.add(f.key);
  }
  const observed=a.families.reduce((s,f)=>s+f.weight*f.coverage,0);
  if(Math.abs(observed-a.effectiveCoverage)>1e-7)return null;
  return {score:a.families.reduce((s,f)=>s+f.weight*f.score/100,0),
   estimatedShare:100-observed,quality:'ESTRAPOLAZIONE DELLO SCORE PER FAMIGLIA'};
 }
 function ratesEnhanced(b){
  if(!b)return null;
  if(b.quality==='UFFICIALE'&&good(b.officialScore))return {score:b.officialScore,quality:'UFFICIALE',estimated:false,bp:b.week,asof:b.asof};
  if(['SECONDARIA','PROXY'].includes(b.quality)&&good(b.score)&&finite(b.week))return {score:b.score,quality:b.quality,estimated:true,bp:b.week,asof:b.asof};
  const recent=b.recentSecondaryWeek;
  if(b.quality==='NON VERIFICATA'&&recent?.kind==='RECENT_EXACT_SECONDARY_WEEK'&&finite(recent.bp)&&recent.contract&&recent.source&&
    (Date.parse(recent.to)-Date.parse(recent.from))/864e5===7&&(Date.parse(b.asof)-Date.parse(recent.to))/864e5===1)
   return {score:5+5*Math.max(-1,Math.min(1,recent.bp/25)),quality:'SECONDARIA · settimana precedente',estimated:true,bp:recent.bp,asof:recent.to,from:recent.from,source:recent.source,contract:recent.contract};
  // A conservative proxy for the SCORE, not an inferred OIS quote.
  // Shrink 2Y weekly changes by 50%: heuristic, not fitted beta.
  const g=b.gov;
  if(g?.kind==='GOV_2Y_NOT_OIS'&&finite(g.bp)&&typeof g.source==='string'&&g.source.length>8&&
    typeof g.from==='string'&&typeof g.to==='string'&&(Date.parse(g.to)-Date.parse(g.from))/864e5===7)
   return {score:5+2.5*Math.max(-1,Math.min(1,g.bp/25)),quality:'PROXY 2Y · attenuazione 50%',estimated:true,bp:g.bp,asof:g.to,from:g.from,source:g.source};
  return null;
 }
 function enhancedModel(a,b,c,d){
  const m=macroEnhanced(a),r=ratesEnhanced(b);
  const values=[
   {key:'macro',label:'Macro',weight:40,score:m?.score??null,estimatedWeight:m?40*m.estimatedShare/100:0,quality:m?.quality||'ASSENTE'},
   {key:'rates',label:'Tassi attesi',weight:30,score:r?.score??null,estimatedWeight:r?.estimated?30:0,quality:r?.quality||'ASSENTE'},
   {key:'positioning',label:'Posizionamento',weight:15,score:c?.score??null,estimatedWeight:c?15:0,quality:c?'OI stimato · '+c.asof:'ASSENTE'},
   {key:'price',label:'Prezzo',weight:15,score:d?.score??null,estimatedWeight:0,quality:d?'Fixing BCE · '+d.asof:'ASSENTE'}
  ];
  const coverage=values.reduce((s,f)=>s+(good(f.score)?f.weight:0),0);
  const estimatedWeight=values.reduce((s,f)=>s+f.estimatedWeight,0);
  const lower=values.reduce((s,f)=>s+(good(f.score)?f.weight*f.score/100:0),0);
  return {score:coverage===100?lower:null,coverage,estimatedWeight,nonImputedWeight:coverage-estimatedWeight,
   values,macro:m,rates:r,complete:coverage===100,
   status:coverage===100?'FULL_SCORE_WITH_ESTIMATES':'INCOMPLETE_NO_SYNTHETIC_FILL'};
 }
 function evaluate({currency,macro,rates,positioning,price}={}){
  if(!FX.includes(currency))return null;
  const valid=x=>x?.affectsFxRanking===false&&x.eligibleForTrading===false;
  const a=valid(macro)&&macro.country===currency&&good(macro.score)&&finite(macro.effectiveCoverage)&&macro.effectiveCoverage>0&&macro.effectiveCoverage<=100?macro:null;
  const b=valid(rates)&&rates.row?.currency===currency?rates.row:null;
  const c=valid(positioning)&&positioning.currency===currency&&good(positioning.score)&&positioning.quality==='ESTIMATED_OI_RESEARCH'?positioning:null;
  const d=valid(price)&&price.currency===currency&&good(price.score)&&price.quality==='OFFICIAL_REFERENCE_FIXINGS'?price:null;
  const items={
   macro:{score:a?.score??null,fraction:a?a.effectiveCoverage/100:0,quality:'Euristico; copertura delle dimensioni misurate'},
   rates:{score:b?.quality==='UFFICIALE'&&good(b.officialScore)?b.officialScore:null,fraction:b?.quality==='UFFICIALE'&&good(b.officialScore)?1:0,quality:b?.quality||'ASSENTE'},
   positioning:{score:c?.score??null,fraction:c?1:0,quality:c?'OI stimato; rilevazione '+c.asof:'ASSENTE'},
   price:{score:d?.score??null,fraction:d?1:0,quality:d?'Fixing BCE '+d.asof:'ASSENTE'}
  };
  function summarize(rateScenario){
   const factors=WEIGHTS.map(([key,label,weight])=>{
    const x=key==='rates'&&rateScenario?{score:b.score,fraction:1,quality:b.quality+' · scenario indicativo'}:items[key];
    const effective=weight*x.fraction;
    return {key,label,weight,effective,score:x.score,quality:x.quality,contribution:good(x.score)?effective*x.score/100:0};
   });
   const known=factors.reduce((s,x)=>s+x.effective,0);
   const min=factors.reduce((s,x)=>s+x.contribution,0);
   const max=min+(100-known)/10;
   // The conditional estimate is explicitly NOT a full score or ranking.
   const conditional=known>=50?min*100/known:null;
   return {factors,known,lower:min,upper:Math.min(10,max),conditional,complete:Math.abs(known-100)<1e-9};
  }
  const baseline=summarize(false);
  const indicative=b&&['SECONDARIA','PROXY'].includes(b.quality)&&good(b.score)?summarize(true):null;
  const enhanced=enhancedModel(a,b,c,d);
  return {currency,baseline,indicative,enhanced,affectsFxRanking:false,eligibleForTrading:false,pointInTimeCertified:false,
   status:'RESEARCH_ONLY',rank:null,method:'FIXED_EXPERIMENTAL_WEIGHTS_WITH_MISSING_WEIGHT_BOUNDS'};
 }
 function render(x,esc=s=>String(s??'')){
  if(!x)return '';
  const n=v=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:2}):'—';
  const b=x.baseline,tone=v=>!finite(v)?'neutral':v>5?'up':v<5?'down':'flat';
  const table=b.factors.map(f=>'<tr><td>'+esc(f.label)+'</td><td>'+f.weight+'%</td><td class="'+tone(f.score)+'">'+esc(n(f.score))+'</td><td>'+esc(n(f.effective))+'%</td><td>'+esc(f.quality)+'</td></tr>').join('');
  const band=s=>esc(n(s.lower)+' – '+n(s.upper));
  const e=x.enhanced;
  const enhanced=e?'<section class="global-fx-enhanced-research" data-global-fx-enhanced-v1><h3>Enhanced · stime esplicite</h3>'+
   '<p><strong>'+esc(e.complete?n(e.score)+'/10':'Non valutabile')+'</strong> · copertura di calcolo '+esc(n(e.coverage))+'% · peso stimato/proxy '+esc(n(e.estimatedWeight))+'% (include OI COT stimato).</p>'+
   '<div style="overflow-x:auto"><table><thead><tr><th>Fattore</th><th>Score</th><th>Peso stimato</th><th>Metodo</th></tr></thead><tbody>'+
   e.values.map(f=>'<tr><td>'+esc(f.label)+'</td><td>'+esc(n(f.score))+'</td><td>'+esc(n(f.estimatedWeight))+'%</td><td>'+esc(f.quality)+'</td></tr>').join('')+'</tbody></table></div>'+
   (e.rates?.contract?'<p>Futures secondari '+esc(e.rates.contract)+': '+esc(n(e.rates.bp))+' pb · '+esc(e.rates.from+' → '+e.rates.asof)+' · '+esc(e.rates.source)+'. Ultima settimana esatta disponibile, termina un giorno prima del livello corrente. Non OIS ufficiale.</p>':e.rates?.source?'<p>Proxy governativo 2Y: '+esc(n(e.rates.bp))+' pb · '+esc(e.rates.from+' → '+e.rates.asof)+' · '+esc(e.rates.source)+'. Attenuazione euristica del 50%, non una stima certificata del 6M.</p>':'')+
   '<p>Macro: le dimensioni mancanti ereditano lo score condizionato della loro famiglia; nessuna serie economica è inventata. La copertura 100% indica solo che tutti i pesi sono valorizzabili, non che i dati siano tutti osservati. Il Core e il suo intervallo teorico restano distinti. Se manca una famiglia o un proxy ammissibile, non si forza il 100%. Metodo non calibrato, non validato in backtest.</p></section>':'';

  return '<details class="global-fx-research-composite" data-global-fx-research-v1 open><summary><strong>Sintesi Global FX · ricerca</strong> · '+esc(x.currency)+'</summary>'+
   '<p><strong>Stima condizionata alle componenti disponibili: '+esc(n(b.conditional))+'/10</strong> · copertura del peso '+esc(n(b.known))+'%. Intervallo teorico con componenti mancanti: '+band(b)+'/10.</p>'+
   '<div style="overflow-x:auto"><table><thead><tr><th>Fattore</th><th>Peso</th><th>Score</th><th>Peso osservabile</th><th>Qualità</th></tr></thead><tbody>'+table+'</tbody></table></div>'+
   (x.indicative?'<p>Scenario con riferimento monetario indicativo: '+esc(n(x.indicative.conditional))+'/10, copertura '+esc(n(x.indicative.known))+'%; intervallo '+band(x.indicative)+'/10. Non equivalente a fonte ufficiale.</p>':'')+
   enhanced+
   '<p>WANT/CAN (inflazione, salari, decisioni) resta contesto qualitativo, senza doppio conteggio del repricing. Pesi fissi sperimentali 40/30/15/15; il 5 è il centro delle scale, non una previsione. L’intervallo rappresenta valori estremi dei pesi non osservabili, non un intervallo di confidenza. Fonti, orizzonti e scale differiscono: nessuna graduatoria certificata né modifica ai segnali operativi.</p></details>';
 }
 const api={evaluate,render,WEIGHTS,macroEnhanced,ratesEnhanced};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FXQuantGlobalResearchComposite=api;
})(typeof window==='undefined'?globalThis:window);
