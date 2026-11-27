'use strict';
/* CFTC Legacy non-commercial research-only positioning momentum.
 * A score of net position changes, NOT expected FX return or trade signal.
 * Canonical P104/Z104 and concentration are separate risk context. */
(function(root){
 const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
 const finite=Number.isFinite;
 const day=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d))&&new Date(Date.parse(d)).toISOString().slice(0,10)===d;
 const span=(a,b)=>day(a)&&day(b)?(Date.parse(b)-Date.parse(a))/864e5:NaN;
 const clamp=x=>Math.max(-1,Math.min(1,x));
 function evaluate({currency,history,archive,desk,today}={}){
  if(!FX.includes(currency)||!day(today)||!desk?.statistics)return null;
  const a=history?.[currency],keys=['net','long','short','netoi','percentile'];
  if(!Array.isArray(a?.dates)||a.dates.length<9||keys.some(k=>!Array.isArray(a[k])||a[k].length!==a.dates.length))return null;
  const hist=a.dates.map((date,i)=>({date,...Object.fromEntries(keys.map(k=>[k,a[k][i]]))}));
  if(hist.some((r,i)=>!day(r.date)||r.date>today||(i&&r.date<=hist[i-1].date)||
   !keys.every(k=>finite(r[k]))||r.long<0||r.short<0||Math.abs(r.long-r.short-r.net)>1||
   Math.abs(r.netoi)>100||r.percentile<0||r.percentile>100))return null;
  const q=desk.statistics({ccy:currency,hist},archive);
  if(!q)return null;
  const tail=hist.slice(-9),weekly=tail.slice(1).every((r,i)=>span(tail[i].date,r.date)===7);
  const age=span(q.date,today),fresh=age>=0&&age<=14;
  const oi=finite(q.impliedOI)&&q.impliedOI>=Math.max(hist.at(-1).long,hist.at(-1).short)?q.impliedOI:null;
  const usable=weekly&&fresh&&oi!==null;
  const flow1=usable?100*q.delta1/oi:null;
  // Previous three weeks exclude current week: no double count of impulse.
  const previous3=usable?100*(q.delta4-q.delta1)/(3*oi):null;
  const flow4=usable?100*q.delta4/oi:null;
  const flow8=usable?100*q.delta8/oi:null;
  const acceleration=usable?flow1-previous3:null;
  let persistence=null;
  if(usable){
   const d=Math.sign(q.delta1);
   persistence=0;
   if(d)for(let i=hist.length-1;i>0&&span(hist[i-1].date,hist[i].date)===7&&Math.sign(hist[i].net-hist[i-1].net)===d;i--)persistence++;
  }
  // +/-2% of inferred current OI per week is a transparent experimental
  // saturation scale. 60% current impulse, 40% preceding 3-week avg.
  const score=usable?5+5*(.6*clamp(flow1/2)+.4*clamp(previous3/2)):null;
  return {currency,asof:q.date,age,score,flow1,previous3,flow4,flow8,acceleration,persistence,
   net:q.net,netoi:q.netoi,p104:q.rounded,z104:q.z,level:q.level,crowd:q.crowd,
   dLong:q.dLong,dShort:q.dShort,flowLabel:desk.flowLabel(q),quality:usable?'ESTIMATED_OI_RESEARCH':'WITHHELD',
   reason:usable?null:!fresh?'COT datato':!weekly?'Ultime settimane non consecutive':'OI stimato non affidabile',
   affectsFxRanking:false,eligibleForTrading:false,pointInTimeCertified:false};
 }
 function render(x,esc=s=>String(s??'')){
  if(!x)return '';
  const n=(v,d=2)=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const s=v=>finite(v)?(v>0?'+':'')+n(v):'—';
  const color=v=>!finite(v)?'neutral':v>0?'up':v<0?'down':'flat';
  return '<details class="positioning-score-research" data-positioning-score-research-v1><summary><strong>Positioning Score · ricerca</strong> · '+esc(x.currency)+' '+esc(x.score===null?'Non valutabile':n(x.score)+'/10')+'</summary>'+
   '<p>CFTC Non-Commercial · rilevazione '+esc(x.asof)+' ('+x.age+' giorni dal riferimento). '+esc(x.reason||'OI stimato dal netto e Net/OI: non misura flussi spot.')+'</p>'+
   '<ul><li class="'+color(x.flow1)+'">Δ netto 1W / OI stimato: '+esc(s(x.flow1))+'%</li>'+
   '<li>Media settimanale delle 3 settimane precedenti: '+esc(s(x.previous3))+'%</li>'+
   '<li>Δ netto 4W / 8W: '+esc(s(x.flow4))+'% / '+esc(s(x.flow8))+'%</li>'+
   '<li>Accelerazione rispetto alla media precedente: '+esc(s(x.acceleration))+' pp</li>'+
   '<li>Persistenza: '+esc(n(x.persistence,0))+' settimane</li>'+
   '<li>Long '+esc(n(x.dLong,0))+' / short '+esc(n(x.dShort,0))+' · '+esc(x.flowLabel)+'</li>'+
   '<li>Stock netto '+esc(n(x.net,0))+' · Net/OI '+esc(n(x.netoi,1))+'%'+(x.crowd?' · concentrazione ≥ 30%':'')+'</li>'+
   '<li>P104 '+esc(n(x.p104,0))+' · Z104 '+esc(n(x.z104))+' · '+esc(x.level)+'</li></ul>'+
   '<p>Score 60% impulso 1W, 40% media 3W precedente; ±2% dell’OI stimato a settimana è la scala sperimentale. Estremi e stock sono contesto di rischio, non segnale automatico di inversione. Dato settimanale: non dimostra ordini, causalità o conoscenza alla data di rilevazione. Nessun effetto sul ranking FX.</p></details>';
 }
 const api={evaluate,render};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FXQuantPositioningResearchScore=api;
})(typeof window==='undefined'?globalThis:window);
