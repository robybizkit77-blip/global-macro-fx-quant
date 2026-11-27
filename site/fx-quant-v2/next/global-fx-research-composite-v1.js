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
  return {currency,baseline,indicative,affectsFxRanking:false,eligibleForTrading:false,pointInTimeCertified:false,
   status:'RESEARCH_ONLY',rank:null,method:'FIXED_EXPERIMENTAL_WEIGHTS_WITH_MISSING_WEIGHT_BOUNDS'};
 }
 function render(x,esc=s=>String(s??'')){
  if(!x)return '';
  const n=v=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:2}):'—';
  const b=x.baseline,tone=v=>!finite(v)?'neutral':v>5?'up':v<5?'down':'flat';
  const table=b.factors.map(f=>'<tr><td>'+esc(f.label)+'</td><td>'+f.weight+'%</td><td class="'+tone(f.score)+'">'+esc(n(f.score))+'</td><td>'+esc(n(f.effective))+'%</td><td>'+esc(f.quality)+'</td></tr>').join('');
  const band=s=>esc(n(s.lower)+' – '+n(s.upper));
  return '<details class="global-fx-research-composite" data-global-fx-research-v1 open><summary><strong>Sintesi Global FX · ricerca</strong> · '+esc(x.currency)+'</summary>'+
   '<p><strong>Stima condizionata alle componenti disponibili: '+esc(n(b.conditional))+'/10</strong> · copertura del peso '+esc(n(b.known))+'%. Intervallo teorico con componenti mancanti: '+band(b)+'/10.</p>'+
   '<div style="overflow-x:auto"><table><thead><tr><th>Fattore</th><th>Peso</th><th>Score</th><th>Peso osservabile</th><th>Qualità</th></tr></thead><tbody>'+table+'</tbody></table></div>'+
   (x.indicative?'<p>Scenario con riferimento monetario indicativo: '+esc(n(x.indicative.conditional))+'/10, copertura '+esc(n(x.indicative.known))+'%; intervallo '+band(x.indicative)+'/10. Non equivalente a fonte ufficiale.</p>':'')+
   '<p>WANT/CAN (inflazione, salari, decisioni) resta contesto qualitativo, senza doppio conteggio del repricing. Pesi fissi sperimentali 40/30/15/15; il 5 è il centro delle scale, non una previsione. L’intervallo rappresenta valori estremi dei pesi non osservabili, non un intervallo di confidenza. Fonti, orizzonti e scale differiscono: nessuna graduatoria certificata né modifica ai segnali operativi.</p></details>';
 }
 const api={evaluate,render,WEIGHTS};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FXQuantGlobalResearchComposite=api;
})(typeof window==='undefined'?globalThis:window);
