'use strict';
/* FX Quant Next — visual ranking research layer.
 * Currency list: observed ECB fixing relative performance over 20 common sessions.
 * Pair list: ordinal research priority from existing dated model and daily price
 * confirmations, NOT a trade score, probability, backtest or entry signal.
 */
(function(root){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const validDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const age=(a,b)=>validDay(a)&&validDay(b)?Math.round((Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5):null;
 const safe=(s,max=175)=>String(s||'').trim().slice(0,max);
 const symbol=k=>k.slice(0,3)+'/'+k.slice(3,6);

 function currencyRanking(prices,now,FX){
  if(prices?.source!=='ECB euro foreign exchange reference rates'||!Array.isArray(prices.rows))return null;
  const common=prices.rows.filter(r=>validDay(r?.Date)&&r.Date<=now&&
   FX.every(c=>finite(r[c])&&r[c]>0)).sort((a,b)=>a.Date.localeCompare(b.Date));
  if(common.length<21)return null;
  const last=common.at(-1),first=common.at(-21);
  if(!validDay(last.Date)||first.Date===last.Date)return null;
  const moves=FX.map(ccy=>{
   const logReturn=FX.filter(c=>c!==ccy).reduce((sum,other)=>
    sum+Math.log((last[other]/last[ccy])/(first[other]/first[ccy])),0)/(FX.length-1);
   return {ccy,percent:(Math.exp(logReturn)-1)*100};
  }).sort((a,b)=>b.percent-a.percent||a.ccy.localeCompare(b.ccy));
  return {asof:last.Date,from:first.Date,commonSessions:20,items:moves};
 }

 function pairRanking(model,prices,now,profileFn){
  const keys=Object.keys(model?.pairs||{}).filter(k=>/^[A-Z]{6}$/.test(k)).sort();
  const modelAge=age(model?.price_asof,now);
  const modelCurrent=modelAge!==null&&modelAge>=0&&modelAge<=5;
  const result=keys.map(key=>{
   const record=model.pairs[key]||{},setup=record.setup||{},frame=record.decision_frame||{};
   const quality=String(setup.quality||'NON VALUTABILE');
   const favored=[key.slice(0,3),key.slice(3)].includes(setup.structuralFav)?setup.structuralFav:null;
   let price=null;
   try{price=typeof profileFn==='function'?profileFn(key,model,prices,now):null;}catch(e){price=null;}
   const priceReady=Boolean(price?.fresh&&price?.closes?.length>=22&&price?.asof===model.price_asof);
   const priceGood=priceReady&&price.price==='GOOD';
   const priceBad=priceReady&&(price.price==='BAD'||price.horizonConflict);
   const momentumGood=priceReady&&price.fiveState==='COERENTE'&&price.twentyState==='COERENTE';
   const timingGood=priceReady&&price.timing==='ALIGNED';
   const valid=Boolean(modelCurrent&&priceReady&&favored&&quality!=='NON VALUTABILE');
   let tier=4,stage='Non valutabile';
   if(!modelCurrent||!priceReady){stage='Aggiornamento necessario';}
   else if(!favored||quality==='NON VALUTABILE'){stage='Vantaggio non definito';}
   else if(priceBad){tier=3;stage='Prezzo in contrasto';}
   else if(priceGood&&momentumGood&&timingGood){tier=1;stage='Coerenza da studiare';}
   else{tier=2;stage='Conferme incomplete';}
   const bias=!favored?'NESSUNO':favored===key.slice(0,3)?'LONG':'SHORT';
   const support=Number(priceGood)+Number(momentumGood)+Number(timingGood);
   const qualityOrder=quality==='PULITO'?3:quality==='DA CONFERMARE'||quality==='DA MONITORARE'?2:quality==='CON RISCHI'?1:0;
   const story=safe(frame.relation||setup.structural?.relation||'Nessuna tesi relativa verificabile.',190);
   const missing=safe(frame.missing||setup.structural?.missing||'Servono conferme indipendenti.',150);
   const priceText=priceReady?(price.alignment||'Prezzo da verificare'):'Daily non confrontabile';
   return {key,name:symbol(key),favored,bias,quality,tier,stage,support,qualityOrder,
    story,missing,priceText,modelCurrent,priceReady,modelAsOf:model?.price_asof,
    risk:quality==='CON RISCHI',valid};
  });
  result.sort((a,b)=>a.tier-b.tier||b.support-a.support||
   b.qualityOrder-a.qualityOrder||a.key.localeCompare(b.key));
  return {asof:model?.price_asof||null,macroAsOf:model?.macro_baseline_asof||null,
   count:result.length,modelCurrent,items:result};
 }

 function analyze({model,prices,now,FX,profileFn}){
  return {currencies:currencyRanking(prices,now,FX),pairs:pairRanking(model,prices,now,profileFn)};
 }

 function render(api){
  const {get,FX,FLAGS,state,esc,sign,date,dayNow}=api,now=dayNow();
  const profileFn=root.FXQuantDecisionJourney?.profile;
  const view=analyze({model:get('pairs'),prices:get('currencyPrices'),now,FX,profileFn});
  const cur=view.currencies,pr=view.pairs,top=pr.items.slice(0,5);
  const worst=cur?Math.max(...cur.items.map(x=>Math.abs(x.percent)),0.0001):1;
  const tag=x=>'<span class="fx-rank-pill tier-'+x.tier+'">'+esc(x.stage)+'</span>';
  const risk=x=>x.risk?'<span class="fx-rank-risk">CON RISCHI</span>':x.quality!=='NON VALUTABILE'?
   '<span class="fx-rank-minor">'+esc(x.quality)+'</span>':'';
  const row=(x,i,featured=false)=>'<button class="fx-rank-pair '+(featured?'featured ':'')+
   (state.pair===x.key&&state.pairDetailOpen?'selected ':'')+'tier-'+x.tier+
   '" type="button" data-pair="'+esc(x.key)+'" aria-label="Apri tesi '+esc(x.name)+'">'+
   '<span class="fx-rank-number">'+(i+1)+'</span>'+
   '<span class="fx-rank-pair-id"><strong>'+esc(x.name)+'</strong><small>'+
   (x.bias==='NESSUNO'?'NESSUN BIAS':'BIAS '+esc(x.bias))+'</small></span>'+
   '<span class="fx-rank-pair-copy"><strong>'+esc(x.story)+'</strong>'+
   '<small>'+esc(x.priceText)+'</small></span>'+
   '<span class="fx-rank-pair-badges">'+tag(x)+risk(x)+'</span>'+
   '<span class="fx-rank-open">Apri tesi ›</span></button>';
  const currencyBody=cur?'<div class="fx-rank-currency-list">'+cur.items.map((x,i)=>{
   const tone=x.percent>0.00001?'positive':x.percent<-.00001?'negative':'neutral';
   return '<div class="fx-rank-currency" aria-label="'+esc(x.ccy)+' posizione '+(i+1)+'">'+
    '<span class="fx-rank-number">'+(i+1)+'</span><strong>'+esc(FLAGS[x.ccy]||'')+' '+x.ccy+'</strong>'+
    '<div class="fx-rank-track"><span class="'+tone+'" style="width:'+Math.max(3,Math.abs(x.percent)/worst*100).toFixed(1)+'%"></span></div>'+
    '<span class="fx-rank-return '+tone+'">'+esc(sign(x.percent,2,'%'))+'</span></div>';
  }).join('')+'</div>':
   '<p class="fx-rank-unavailable">Mancano almeno 21 fixing BCE comuni verificabili per tutte le valute. Classifica di forza sospesa.</p>';
  const currencyDate=cur?'20 intervalli comuni · '+date(cur.from)+' → '+date(cur.asof):
   'Periodo non verificabile';
  const pairDates='Snapshot coppie '+date(pr.asof)+' · baseline macro del motore '+date(pr.macroAsOf);
  const warnings=[];
  if(pr.count!==28)warnings.push('Copertura coppie incompleta: '+pr.count+'/28.');
  if(!pr.modelCurrent)warnings.push('Snapshot delle tesi non recente: le priorità non sono attuali.');
  if(pr.macroAsOf&&age(pr.macroAsOf,now)>30)warnings.push('Baseline macro storica: richiede nuova verifica prima di una decisione.');
  if(!pr.items.some(x=>x.tier===1))warnings.push('Nessuna coppia raggiunge la massima coerenza del filtro: la Top 5 non equivale a cinque trade pronti.');
  const warningText=warnings.length?'<p class="fx-rank-warning">'+esc(warnings.join(' '))+'</p>':'';
  return '<div class="fx-ranking-desk" id="fx-ranking-desk">'+
   '<div class="fx-rank-intro"><div><span class="mini-overline">FX / GERARCHIA DI RICERCA</span>'+
   '<h2>Chi è più forte? <em>Quale coppia vale un approfondimento?</em></h2>'+
   '<p>Due graduatorie diverse: forza di prezzo osservata delle otto valute e priorità di studio delle 28 tesi. Nessuna classifica è un segnale di ingresso.</p></div></div>'+
   '<div class="fx-rank-two">'+
   '<section class="fx-rank-box" aria-label="Forza relativa delle otto valute"><div class="fx-rank-head"><div><span>01 / VALUTE G8</span><h3>Dalla più forte alla più debole</h3></div><small>PREZZO RELATIVO</small></div>'+
   '<p class="fx-rank-sub">Media geometrica della performance contro le altre sette, da fixing BCE. Non misura la qualità macro.</p>'+
   currencyBody+'<p class="fx-rank-source">'+esc(currencyDate)+'</p></section>'+
   '<section class="fx-rank-box" aria-label="Top cinque coppie da approfondire"><div class="fx-rank-head"><div><span>02 / SELEZIONE FX</span><h3>Le prime 5 da studiare</h3></div><small>NON SEGNALI</small></div>'+
   '<p class="fx-rank-sub">Ordine basato su tesi del modello, conferma daily e timing. I rischi non vengono nascosti.</p>'+
   (top.length?'<div class="fx-rank-featured">'+top.map((x,i)=>row(x,i,true)).join('')+'</div>':
   '<p class="fx-rank-unavailable">Nessuna coppia caricata dal motore.</p>')+'</section></div>'+
   '<section class="fx-rank-box fx-rank-all" aria-label="Classifica completa delle ventotto coppie">'+
   '<div class="fx-rank-head"><div><span>03 / TUTTO IL G8</span><h3>Classifica completa · '+pr.count+' coppie</h3></div><small>PRIORITÀ DI RICERCA</small></div>'+
   '<p class="fx-rank-sub">Dall’evidenza più coerente ai dossier non valutabili. Il posto in classifica non è un punteggio statistico né una probabilità di successo. Seleziona una coppia per la tesi completa.</p>'+
   (pr.items.length?'<div class="fx-rank-all-list">'+pr.items.map((x,i)=>row(x,i)).join('')+'</div>':
   '<p class="fx-rank-unavailable">Il feed delle 28 coppie non è disponibile.</p>')+
   '<p class="fx-rank-source">'+esc(pairDates)+'. Le priorità vengono ricalcolate dai feed disponibili; Macro, COT e prezzi possono avere date diverse.</p>'+
   warningText+'</section></div>';
 }
 const api={currencyRanking,pairRanking,analyze,render};
 root.FXQuantPairRankings=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
