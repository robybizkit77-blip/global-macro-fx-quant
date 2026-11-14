'use strict';
/* Relative 6M repricing: two instrument moves must share their observation
 * dates; listed futures also must retain the same contract across both days.
 * This is research-only, NOT an OIS-to-OIS spread or a directional FX signal.
 */
(function(root){
 const CCY=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
 const fmt=(n,p=1)=>finite(n)?(n>0?'+':n<0?'−':'')+Math.abs(n).toFixed(p).replace('.',','):'—';
 const date=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)?
  x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):'n.d.';
 const grade=k=>k==='OIS'?'OIS ufficiale':k==='FUTURES'?'futures ufficiale':
  k==='FUTURES SECONDARI'?'futures secondario':k==='PROXY FUTURES'?'proxy bank-bill':'fonte non validata';
 const points=(row)=>Array.isArray(row?.tenors?.['6m'])?row.tenors['6m']:[];
 function historicalIntervals(a,b){
  const bridge=root.FXQuantPricingHistory;
  if(!a||!b||!bridge?.connect)return [];
  const A=points(a),B=points(b),db=new Map(B.map(p=>[p.date,p]));
  const out=[];
  for(let i=1;i<A.length;i++){
   const ea=A[i],pa=A[i-1],eb=db.get(ea.date),pb=db.get(pa.date);
   if(!eb||!pb||pa.derived||ea.derived||pb.derived||eb.derived)continue;
   if(!bridge.connect(pa,ea)||!bridge.connect(pb,eb))continue;
   if(!(pa.date<pb.date||pa.date===pb.date))continue;
   const main=(ea.rate-pa.rate)*100,peer=(eb.rate-pb.rate)*100;
   if(!finite(main)||!finite(peer))continue;
   out.push({from:pa.date,to:ea.date,aBp:Math.round(main*100)/100,
    bBp:Math.round(peer*100)/100,bp:Math.round((main-peer)*100)/100,
    aContract:ea.contract||null,bContract:eb.contract||null});
  }
  return out.slice(-10);
 }
 function read({ccy,other,window='1d',today,snapshot,operational,research,nzd,history,pairs}){
  if(!CCY.includes(ccy)||!CCY.includes(other)||ccy===other)return null;
  const api=root.FXQuantPricingMoves,archive=root.FXQuantPricingHistory;
  if(!api?.readCurrency||!archive?.country)return null;
  const a=api.readCurrency(ccy,snapshot,operational,research,nzd,today);
  const b=api.readCurrency(other,snapshot,operational,research,nzd,today);
  const mode=window==='1w'?'week':'one';
  const ar=a?.rows?.find(x=>x.tenor==='6m'),br=b?.rows?.find(x=>x.tenor==='6m');
  const am=ar?.[mode],bm=br?.[mode];
  const dateMatch=Boolean(am&&bm&&ar.asof&&br.asof&&ar.asof===br.asof&&
   am.until===bm.until&&am.until===ar.asof&&finite(am.bp)&&finite(bm.bp));
  const fromMatch=dateMatch&&am.from&&bm.from&&am.from===bm.from;
  // The older rate dates remain visible; a mismatch never becomes a relative
  // "today" move. A shared end date with an unknown start is indicative only.
  const live=dateMatch?{asof:ar.asof,aBp:am.bp,bBp:bm.bp,
   relativeBp:Math.round((am.bp-bm.bp)*100)/100,
   from:fromMatch?am.from:null,grade:fromMatch?'MATCHED_EXACT_INTERVAL':'SAME_END_REFERENCE_UNVERIFIED'}:null;
  const ha=archive.country(history,ccy,60),hb=archive.country(history,other,60);
  const observations=historicalIntervals(ha,hb);
  const direct=ccy+other,reverse=other+ccy;
  const pair=pairs?.pairs?.[direct]?direct:pairs?.pairs?.[reverse]?reverse:null;
  return {ccy,other,window:window==='1w'?'1w':'1d',a,b,ar,br,live,observations,
   latestCommon:observations.at(-1)||null,pair,
   historyAsOf:history?.as_of||null};
 }
 function bar(bp,max){
  if(!finite(bp))return '<span class="rr6-bar rr6-bar-missing"></span>';
  const magnitude=Math.min(47,Math.abs(bp)/Math.max(1,max)*47);
  const left=bp>=0?50:50-magnitude;
  return '<span class="rr6-bar" aria-hidden="true"><i></i><b class="'+
   (bp>0?'rr6-plus':bp<0?'rr6-minus':'rr6-zero')+'" style="left:'+
   left.toFixed(2)+'%;width:'+Math.max(1.4,magnitude).toFixed(2)+'%"></b></span>';
 }
 function render(args){
  const m=read(args);
  if(!m)return '<section class="rates-relative-pricing" id="rates-relative-pricing"><p>Confronto monetario relativo non verificabile: fonti mancanti.</p></section>';
  const {ccy,other,live,latestCommon,observations,a,b,ar,br,pair}=m;
  const window=m.window==='1w'?'una settimana':'la seduta precedente';
  const finalDates='Ultime rilevazioni 6M: '+ccy+' '+date(ar?.asof)+' · '+other+' '+date(br?.asof)+'.';
  const allMatched=live&&live.grade==='MATCHED_EXACT_INTERVAL';
  let headline,context;
  if(live){
   headline=Math.abs(live.relativeBp)<.05?'Le due variazioni 6M sono quasi equivalenti.':
    live.relativeBp>0?ccy+' ha registrato un aumento relativo del 6M rispetto a '+other+'.':
    other+' ha registrato un aumento relativo del 6M rispetto a '+ccy+'.';
   context='Su '+window+' (fine '+date(live.asof)+'), '+ccy+' '+fmt(live.aBp)+
    ' pb e '+other+' '+fmt(live.bBp)+' pb. Differenza delle variazioni: '+fmt(live.relativeBp)+' pb. '+
    (allMatched?'Periodo comune '+date(live.from)+' → '+date(live.asof)+'.':
     'La data finale coincide, ma non è certificata la stessa data iniziale per entrambe le fonti: confronto indicativo.');
  }else{
   headline='Le ultime rilevazioni non permettono un confronto simultaneo.';
   context=finalDates+' Evitiamo di sottrarre variazioni riferite a sedute differenti.'+
    (latestCommon?' L’ultimo intervallo archivistico comune è '+date(latestCommon.from)+
    ' → '+date(latestCommon.to)+' (differenza delle variazioni '+fmt(latestCommon.bp)+' pb), non è la variazione odierna.':
    ' Lo storico non offre ancora un intervallo comune per questo confronto.');
  }
  const max=Math.max(1,...observations.map(x=>Math.abs(x.bp)));
  const rows=observations.map(x=>'<div class="rr6-day" data-rr6-day="'+esc(x.to)+
   '" title="'+esc(x.from+' → '+x.to+' · '+ccy+' '+fmt(x.aBp)+' pb · '+other+
   ' '+fmt(x.bBp)+' pb')+'"><time>'+date(x.to).slice(0,5)+'</time>'+
   bar(x.bp,max)+'<b class="'+(x.bp>0?'rr6-pos':x.bp<0?'rr6-neg':'')+'">'+fmt(x.bp)+' pb</b></div>').join('');
  const details='<div><strong>Strumenti.</strong> '+esc(ccy)+' · '+esc(grade(a.kind))+
    ' · '+esc(a.quality)+'. '+esc(other)+' · '+esc(grade(b.kind))+' · '+esc(b.quality)+'.</div>'+
    '<div><strong>Stato confronto 1D/1W.</strong> '+(live?
    (allMatched?'Data iniziale e finale comuni.':'Solo data finale comune; data iniziale non verificata.')+
    ' '+esc(ccy)+': '+esc(a.rows[1][m.window==='1w'?'week':'one']?.method||'n.d.')+
    ' · '+esc(other)+': '+esc(b.rows[1][m.window==='1w'?'week':'one']?.method||'n.d.'):
    'Non contemporaneo oppure una o entrambe le variazioni mancano.')+'</div>'+
    '<div><strong>Storico.</strong> '+observations.length+' intervalli 6M con due date uguali e consecutive per entrambi i paesi. I futures secondari richiedono lo stesso contratto nelle due date, nessun riferimento NZD ricostruito viene trattato da osservazione.</div>';
  const call=pair?'<button type="button" data-rates-openpair="'+esc(pair)+'">'+
    'Apri '+esc(pair.slice(0,3)+'/'+pair.slice(3))+' <span aria-hidden="true">↗</span></button>':'';
  return '<section class="rates-relative-pricing" id="rates-relative-pricing" data-rr6-status="'+
   (live?esc(live.grade):'NOT_ALIGNED')+'" data-rr6-pair="'+esc(pair||'')+'" aria-label="Repricing relativo 6M tra due valute">'+
   '<div class="rates-section-head"><div><span class="chapter-kicker">DAL PRICING ALLA FORZA RELATIVA · 6M</span>'+
   '<h2>Chi sta riprezzando di più <em>le aspettative monetarie?</em></h2></div>'+
   '<p>Confronto della variazione del 6M fra '+esc(ccy)+' e '+esc(other)+
   ', non dei livelli né della forza spot. Cambia le valute dal selettore Tassi in alto.</p></div>'+
   '<div class="rr6-main"><div class="rr6-firstread"><span class="micro-over">'+
   esc(ccy)+' VS '+esc(other)+' · '+(m.window==='1w'?'1 SETTIMANA':'1 SEDUTA')+
   ' · '+(live?(allMatched?'INTERVALLO VERIFICATO':'INDICATIVO · BASE NON CERTIFICATA'):'DATE NON ALLINEATE')+
   '</span><h3>'+esc(headline)+'</h3><p>'+esc(context)+'</p>'+
   '<span class="rr6-bottomline">Per il cambio conta il differenziale relativo, ma da solo non prova chi ha comprato o venduto la valuta.</span></div>'+
   '<div class="rr6-summary"><span class="micro-over">Δ6M RELATIVO</span><strong class="'+
   (live?.relativeBp>0?'rr6-pos':live?.relativeBp<0?'rr6-neg':'')+'">'+
   (live?fmt(live.relativeBp)+' pb':'Non confrontabile')+'</strong>'+
   '<small>'+esc(finalDates)+'</small></div></div>'+
   '<div class="rr6-secondary"><div><span class="micro-over">ULTIMI INTERVALLI COMUNI · ARCHIVIO 6M</span>'+
   '<h3>Come evolve la differenza delle variazioni?</h3>'+
   '<p>Ogni barra = Δ6M '+esc(ccy)+' − Δ6M '+esc(other)+' sulle stesse due date, senza unire contratti diversi.</p></div>'+
   (rows?'<div class="rr6-days">'+rows+'</div>':
   '<div class="rr6-no-history">Non ci sono ancora intervalli con due date comuni e fonti confrontabili: nessuna barra artificiale.</div>')+
   '<details class="rr6-source"><summary>Fonti, limiti e date dei confronti</summary>'+
   '<div>'+details+'</div></details></div>'+
   '<div class="rr6-action">'+call+
   '<p>Verifica la reazione del prezzo FX nel dossier della coppia: una variazione del pricing non è una tesi direzionale completa.</p></div></section>';
 }
 const api={read,historicalIntervals,render};
 root.FXQuantRelativePricing=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
