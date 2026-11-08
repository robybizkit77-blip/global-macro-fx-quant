'use strict';
/* FX Quant Next V9: research-to-decision, never a trade-signal generator.
 * Uses dated FX model snapshots and reconstructed DAILY ECB fixing crosses.
 * No candlesticks, H4 levels, entry/stop prices or inferred quantitative edge.
 */
(function(){
 const pairName=k=>String(k||'').slice(0,3)+'/'+String(k||'').slice(3,6);
 const validDay=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s);
 const finite=n=>typeof n==='number'&&Number.isFinite(n);
 const isoDays=(a,b)=>validDay(a)&&validDay(b)?Math.round((Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5):null;
 const clean=(s,max=220)=>String(s||'').trim().slice(0,max);
 function series(doc,pair,asof,now){
  if(!/^[A-Z]{6}$/.test(pair||'')||!validDay(asof)||asof>now||!Array.isArray(doc?.rows))return [];
  const a=pair.slice(0,3),b=pair.slice(3),observed=new Map();
  for(const row of doc.rows){
   const d=row?.Date,base=row?.[a],quote=row?.[b];
   if(!validDay(d)||d>asof||d>now||!finite(base)||!finite(quote)||base<=0||quote<=0)continue;
   const value=quote/base;
   if(finite(value)&&value>0)observed.set(d,value);
  }
  const rows=[...observed].sort((x,y)=>x[0].localeCompare(y[0])).map(([label,value])=>({label,value}));
  // The chart must end at the exact date used for the pair model.
  return rows.at(-1)?.label===asof?rows:[];
 }
 // Conservative DAILY reference thresholds from the previous 20 ECB fixings.
 // These are not intraday highs/lows, entries, stops or tested trading triggers.
 function watchLevels({asof,fresh,latest,direction,breakHigh,breakLow}){
  const ready=Boolean(fresh)&&validDay(asof)&&finite(latest)&&latest>0&&
   (direction===1||direction===-1)&&finite(breakHigh)&&finite(breakLow)&&
   breakHigh>=breakLow&&breakLow>0;
  if(!ready)return {ready:false,asof:validDay(asof)?asof:null,
   reason:'Riferimenti di prezzo non verificabili sulla stessa data, oppure vantaggio valutario non definito.'};
  const favorable=direction===1?breakHigh:breakLow;
  const adverse=direction===1?breakLow:breakHigh;
  const favorablePassed=direction*(latest-favorable)>0;
  const adversePassed=direction*(latest-adverse)<0;
  const favorableDistancePct=direction*(favorable/latest-1)*100;
  const adverseDistancePct=-direction*(adverse/latest-1)*100;
  return {ready:true,asof,favorable,adverse,
   favorableDirection:direction>0?'Sopra':'Sotto',
   adverseDirection:direction>0?'Sotto':'Sopra',
   favorablePassed,adversePassed,favorableDistancePct,adverseDistancePct,
   favorableStatus:favorablePassed?'OLTRE IL RIFERIMENTO':'DA VERIFICARE',
   adverseStatus:adversePassed?'CONTRASTO GIÀ OSSERVATO':'DA MONITORARE'};
 }
 function profile(key,doc,prices,now){
  const obj=doc?.pairs?.[key],s=obj?.setup||{},f=obj?.decision_frame||{};
  const asof=doc?.price_asof;
  const price=s.price||{},timing=s.timing||{};
  const fav=s.structuralFav||f.fav||null;
  const q=s.quality||'NON VALUTABILE';
  const age=isoDays(asof,now),fresh=age!==null&&age>=0&&age<=5;
  const closes=series(prices,key,asof,now);
  const usable=fresh&&closes.length>=22;
  const latest=closes.at(-1),p1=closes.at(-2),p5=closes.at(-6),p6=closes.at(-7),p20=closes.at(-21);
  const m1=usable&&p1?.value>0?(latest.value/p1.value-1)*100:null;
  const m5=usable&&p5?.value>0?(latest.value/p5.value-1)*100:null;
  const prior5=usable&&p6?.value>0&&p1?.value>0?(p1.value/p6.value-1)*100:null;
  const change5=finite(m5)&&finite(prior5)?m5-prior5:null;
  const m20=usable&&p20?.value>0?(latest.value/p20.value-1)*100:null;
  // Direction matters: EUR/USD falling favours USD, while USD/CAD rising favours USD.
  // These signs are descriptive observations, not statistically validated thresholds.
  const direction=fav===key.slice(0,3)?1:fav===key.slice(3,6)?-1:0;
  const stateOf=v=>!usable||!finite(v)||!direction?'NON VALUTABILE':
    Math.abs(v)<1e-9?'STABILE':v*direction>0?'COERENTE':'CONTRARIO';
  const fiveState=stateOf(m5),twentyState=stateOf(m20);
  const alignment=fiveState==='COERENTE'&&twentyState==='COERENTE'?'COERENTE SU 5 E 20 SEDUTE':
    fiveState==='COERENTE'&&twentyState==='CONTRARIO'?'RECUPERO A 5 SEDUTE, 20 SEDUTE CONTRARIE':
    fiveState==='CONTRARIO'&&twentyState==='COERENTE'?'PAUSA A 5 SEDUTE, 20 SEDUTE COERENTI':
    fiveState==='CONTRARIO'&&twentyState==='CONTRARIO'?'5 E 20 SEDUTE CONTRARIE':
    'CONFERMA DAILY NON CONCLUSIVA';
  const horizonConflict=fiveState==='CONTRARIO'||twentyState==='CONTRARIO';
  const window=usable?closes.slice(-21,-1):[];
  const breakHigh=window.length===20?Math.max(...window.map(x=>x.value)):null;
  const breakLow=window.length===20?Math.min(...window.map(x=>x.value)):null;
  const structure=usable&&finite(breakHigh)&&finite(breakLow)
    ?latest.value>breakHigh?'Sopra i massimi dei 20 fixing precedenti'
      :latest.value<breakLow?'Sotto i minimi dei 20 fixing precedenti'
      :'All’interno del range dei 20 fixing precedenti'
    :'Struttura daily da verificare';
  const alignedDaily=closes.length>=22;
  const watch=watchLevels({asof,fresh,latest:latest?.value??null,direction,breakHigh,breakLow});
  const eligible=Boolean(fav)&&fresh&&alignedDaily&&q==='PULITO'&&price.state==='GOOD'&&timing.state==='ALIGNED';
  const research=Boolean(fav)&&fresh&&alignedDaily&&q!=='NON VALUTABILE'&&price.state==='GOOD'&&timing.state==='ALIGNED';
  const caution=q==='CON RISCHI'?'Il motore segnala rischi: controlla soprattutto COT, liquidità e fattori contrari.'
    :q==='DA MONITORARE'||q==='DA CONFERMARE'?'La struttura non è ancora completamente convincente.'
    :q==='NON VALUTABILE'?'Il modello non dispone di un confronto abbastanza solido per questa coppia.'
    :'La qualità della struttura resta da verificare nel dossier.';
  const why=research?'Prezzo e timing coerenti con il vantaggio di '+fav+', ma il modello classifica la coppia '+q+'.'
    :q==='NON VALUTABILE'?'Non emerge un confronto strutturale sufficientemente verificabile.'
    :price.state==='BAD'?'Il prezzo contraddice la direzione relativa preferita dal modello.'
    :timing.state==='ADVERSE'?'Il timing resta contrario alla tesi strutturale.'
    :price.state==='NEUTRAL'?'La risposta del prezzo non conferma la tesi.'
    :'La combinazione di prezzo, timing e struttura richiede ulteriori conferme.';
  const next=!(fresh)?'Prima di tutto serve un fixing aggiornato, coerente con lo snapshot del modello.'
    :price.state==='BAD'?'Attendere che il prezzo daily smetta di contraddire il vantaggio relativo e rivalutare la struttura.'
    :timing.state==='ADVERSE'?'Attendere un miglioramento verificabile del timing, senza anticiparlo dal solo livello di prezzo.'
    :research?'Verificare struttura H4 e Daily, eventuale breakout seguito da retest e volatilità prima di considerare un ingresso.'
    :'Attendere maggiore coerenza tra vantaggio macro/pricing, prezzo e cambiamenti del timing.';
  return {key,asof,age,fresh,eligible,research,fav,direction,fiveState,twentyState,alignment,horizonConflict,quality:q,price:price.state||'UNKNOWN',
    priceText:price.text||'Non disponibile',timing:timing.state||'UNKNOWN',timingText:timing.text||'Non disponibile',
    why,next,caution,structure,closes,latest:latest?.value??null,m1,m5,m20,prior5,change5,breakHigh,breakLow,watch,
    relation:f.relation||s.structural?.relation||'Nessuna tesi verificabile',
    missing:f.missing||'La conferma indipendente è ancora aperta',
    cot:s.cot?.text||'Dato COT non classificato',
    liquidity:s.liquidity?.text||'Liquidità non classificata',
    bar:s.extension?.text||'Estensione non calcolata'};
 }
 function snapshot(doc,prices,now){
  const keys=Object.keys(doc?.pairs||{}).filter(x=>/^[A-Z]{6}$/.test(x)).sort();
  const cases=keys.map(k=>profile(k,doc,prices,now));
  const worth=cases.filter(x=>x.research).sort((a,b)=>a.key.localeCompare(b.key));
  // Qualifying list is NOT a score or rank: stable alphabetical, no false edge.
  return {asof:doc?.price_asof||null,age:isoDays(doc?.price_asof,now),total:keys.length,
    clean:cases.filter(x=>x.quality==='PULITO').length,
    invalid:cases.filter(x=>x.quality==='NON VALUTABILE').length,
    atRisk:cases.filter(x=>x.quality==='CON RISCHI').length,
    qualified:worth.length,examples:worth.slice(0,3),cases,
    priceAvailable:validDay(prices?.last_as_of)&&prices.last_as_of===doc?.price_asof};
 }
 function build(api){
  const {get,state,plot,fmt,sign,date,dayNow,esc}=api;
  const market=get('pairs'),history=get('currencyPrices');
  const now=dayNow();
  const data=snapshot(market,history,now);
  function overview(){
   if(data.total===0)return '<section class="decision-overview"><h2>Dal research alla decisione</h2><p>Il feed delle 28 coppie non è disponibile: nessuna selezione operativa viene ricostruita artificialmente.</p></section>';
   const status=(!validDay(data.asof)||data.age===null||data.age<0||data.age>5)
    ?'I fixing FX non sono recenti: osservazione storica, non selezione operativa corrente.'
    :data.clean===0?'Nessuna delle '+data.total+' coppie è attualmente classificata pulita. Non proponiamo ingressi.'
    :'La classificazione del motore include '+data.clean+' coppie pulite: la verifica tecnica H4/Daily resta comunque necessaria.';
   const examples=data.examples.map(x=>'<button class="decision-case" type="button" data-pair="'+x.key+'" aria-label="Esamina '+pairName(x.key)+'">'
     +'<span class="decision-case-head"><strong>'+pairName(x.key)+'</strong><small>'+esc(x.quality)+'</small></span>'
     +'<p>'+esc(x.why)+'</p><p class="decision-case-horizon">Controllo daily BCE: '+esc(x.alignment.toLowerCase())+'.</p><span class="decision-case-bottom">Da confermare: '+esc(x.next)+' <b>↗</b></span></button>').join('');
   return '<section class="decision-overview" aria-label="Dalla panoramica alla scelta delle coppie">'
     +'<div class="dashboard-section-head"><span>05 / DALLA TESI ALLA DECISIONE</span><p>Solo casi di studio, non una classifica di trade.</p></div>'
     +'<div class="decision-overview-layout"><div class="decision-summary"><span class="decision-kicker">VERDETTO OPERATIVO</span>'
     +'<h2>'+esc(data.clean===0?'Nessun setup pulito. Ma ci sono casi da studiare.':'Dalla struttura alla verifica del prezzo.')+'</h2>'
     +'<p>'+esc(status)+'</p><div class="decision-totals"><span><strong>'+data.qualified+'</strong> con prezzo e timing coerenti</span><span><strong>'+data.invalid+'</strong> non valutabili</span><span><strong>'+data.atRisk+'</strong> con rischi</span></div>'
     +'<small>Snapshot FX '+date(data.asof)+' · fixing BCE '+date(history?.last_as_of)+'. La presenza di una coppia qui non indica convenienza al prezzo attuale.</small></div>'
     +'<div class="decision-cases">'+(examples||'<div class="empty"><strong>Non emergono coppie con prezzo e timing coerenti.</strong><p>La selezione resta vuota anziché produrre suggerimenti artificiali.</p></div>')+'</div></div></section>';
  }
  function pair(){
   const item=profile(state.pair||'EURUSD',market,history,now),isFull=item.closes.length>=22;
   const window=[20,60,120].includes(Number(state.pairPriceWindow))?Number(state.pairPriceWindow):60;
   const selected=item.closes.slice(-window);
   const watch=item.watch||{ready:false};
   const showReferences=watch.ready&&state.pairShowReferences!==false;
   const referenceLines=showReferences?[
     {kind:'favorable',value:watch.favorable},
     {kind:'adverse',value:watch.adverse}
   ]:[];
   const graph=selected.length>1&&isFull?plot({lines:[{name:pairName(item.key)+' · fixing BCE daily',color:'#9bd9cc',values:selected}],referenceLines,precision:item.key.endsWith('JPY')?3:5,label:'Prezzo daily BCE per '+pairName(item.key)})
     :'<div class="empty"><strong>Grafico daily non validato</strong><p>Servono almeno 22 fixing con l’ultima data esattamente coincidente con il modello della coppia. Non ricostruiamo prezzi mancanti.</p></div>';
   const gain=Number.isFinite(item.m20)?sign(item.m20,2,'%'):'—';
   const lastDay=Number.isFinite(item.m1)?sign(item.m1,2,'%'):'—';
   const move=Number.isFinite(item.m5)?sign(item.m5,2,'%'):'—';
   const attractive=item.horizonConflict&&item.research?'OSSERVAZIONE · MOMENTUM DAILY DISCORDANTE':
     item.eligible?'STRUTTURA PULITA · TIMING DA VALIDARE':item.research?'SOLO OSSERVAZIONE · RISCHI APERTI':'ATTENDERE · CONFERME INSUFFICIENTI';
   const side=item.direction>0?'rialzo di '+pairName(item.key):item.direction<0?'ribasso di '+pairName(item.key):'direzione relativa non validata';
   const pulse=item.direction&&Number.isFinite(item.change5)?
     'Rispetto al fixing precedente, il rendimento sulle 5 sedute è cambiato di '+sign(item.change5,2,' punti percentuali')+'; il suo contributo alla direzione favorita è '+(item.change5*item.direction>0?'migliorato':item.change5*item.direction<0?'peggiorato':'invariato')+'. Non è una prova di persistenza.':
     'La variazione dell’impulso a 5 sedute rispetto al fixing precedente non è verificabile.';
   const discordance=item.direction===0?'Il vantaggio strutturale non è definito: non esiste un verso da confermare.'
      :item.alignment==='COERENTE SU 5 E 20 SEDUTE'?'Le ultime 5 e 20 sedute hanno entrambe un segno coerente con '+side+'. La direzione osservata non garantisce la prosecuzione.'
      :item.alignment==='RECUPERO A 5 SEDUTE, 20 SEDUTE CONTRARIE'?'Il movimento delle ultime 5 sedute favorisce '+side+', ma quello sulle 20 sedute è ancora contrario. È un recupero, non un trend uniformemente confermato.'
      :item.alignment==='PAUSA A 5 SEDUTE, 20 SEDUTE COERENTI'?'Il movimento a 20 sedute è coerente con '+side+', mentre le 5 più recenti si muovono in senso contrario. Il momentum si sta indebolendo.'
      :item.alignment==='5 E 20 SEDUTE CONTRARIE'?'Sia a 5 sia a 20 sedute il prezzo si è mosso contro '+side+'. Non interpretiamo la tesi strutturale come confermata dal prezzo.'
      :'I dati giornalieri non sono sufficienti per confermare una direzione coerente fra orizzonti.';
   const range=Number.isFinite(item.breakLow)&&Number.isFinite(item.breakHigh)?
       fmt(item.breakLow,item.key.endsWith('JPY')?3:5)+' – '+fmt(item.breakHigh,item.key.endsWith('JPY')?3:5):
       'Non disponibile';
   const rateBridge=typeof window!=='undefined'&&window.FXQuantRatesBridge?.build?
     window.FXQuantRatesBridge:
     typeof require==='function'?require('./fx-rates-bridge.js'):null;
   const ratesEvidence=rateBridge?.build?
     rateBridge.build({get,state,plot,fmt,sign,date,dayNow,esc}).render():
     '<section class="decision-rates-bridge"><h2>Confronto FX/2Y non disponibile</h2><p>Manca il modulo di verifica delle date comuni.</p></section>';
   const quote=item.latest!==null?fmt(item.latest,item.key.endsWith('JPY')?3:5):'—';
   const pxDigits=item.key.endsWith('JPY')?3:5;
   const watchFavor=watch.ready?watch.favorableDirection+' '+fmt(watch.favorable,pxDigits):'Non disponibile';
   const watchAdverse=watch.ready?watch.adverseDirection+' '+fmt(watch.adverse,pxDigits):'Non disponibile';
   const watchNext=watch.ready
     ?watch.favorablePassed
       ?'Il fixing è già oltre il massimo/minimo di riferimento nella direzione favorita: osservare persistenza e nuovo contesto, senza considerarlo un ingresso.'
       :watch.adversePassed
         ?'Il prezzo è già oltre il riferimento contrario: verificare se la tesi relativa regge ancora.'
         :'Al prossimo fixing, osservare un superamento di '+watchFavor+' nella direzione favorita; un movimento '+watchAdverse+' indicherebbe invece contrasto del prezzo.'
     :'Nessun riferimento operativo daily verificabile. Serve una nuova sequenza allineata o un vantaggio strutturale definito.';
   const gateNext=watch.ready
     ?watch.favorablePassed?'Riferimento favorevole già superato: controllare la persistenza.'
       :watch.adversePassed?'Riferimento contrario già superato: riesaminare prezzo e tesi.'
       :'Riferimento favorevole '+watchFavor+'; contrario '+watchAdverse+'.'
     :item.next;
   const watchHtml='<div class="decision-daily-watch"><div class="decision-daily-watch-head"><span>COSA OSSERVARE AL PROSSIMO FIXING BCE</span><small>Riferimenti dagli ultimi 20 fixing precedenti · '+date(watch.asof||item.asof)+'</small></div>'
     +(watch.ready
       ?'<div class="decision-watch-columns"><div class="decision-watch-line"><span>VERSO FAVOREVOLE</span><strong>'+esc(watchFavor)+'</strong><small>'+esc(watch.favorableStatus)+' · '+(watch.favorablePassed?'già oltre il livello':fmt(watch.favorableDistancePct,2)+'% di distanza dal fixing')+'</small></div>'
       +'<div class="decision-watch-line contrary"><span>VERSO CONTRARIO</span><strong>'+esc(watchAdverse)+'</strong><small>'+esc(watch.adverseStatus)+' · '+(watch.adversePassed?'già oltre il livello':fmt(watch.adverseDistancePct,2)+'% di distanza dal fixing')+'</small></div></div>'
       :'<p class="decision-watch-unavailable">'+esc(watch.reason||'Dati da verificare')+'</p>')
     +'<p class="decision-watch-next">'+esc(watchNext)+'</p>'
     +'<small class="decision-watch-caveat">Livelli statistici di fixing, non supporti o resistenze intraday. Un superamento non basta: servono conferme di prezzo e contesto aggiornato.</small></div>';
   return '<section class="decision-deepdive" aria-label="Dalla tesi al timing di '+esc(pairName(item.key))+'">'
     +'<div class="decision-dossier-head"><span>RESEARCH → PRICING → PREZZO → DECISIONE</span><h2>'+pairName(item.key)+' · Che cosa sappiamo, che cosa aspettiamo?</h2>'
     +'<p>Il motore può segnalare una direzione favorevole senza che esista un ingresso interessante. Separiamo le due cose.</p></div>'
     +'<div class="decision-gates"><div><span>THESIS STRENGTH</span><strong>'+esc(item.fav?'Vantaggio '+item.fav+' · '+item.quality:'Nessun vantaggio verificato')+'</strong><small>'+esc(item.relation)+'</small></div>'
     +'<div><span>TRADE ATTRACTIVENESS</span><strong>'+esc(attractive)+'</strong><small>'+esc(item.why)+'</small></div>'
     +'<div><span>LA PROSSIMA VERIFICA</span><strong>Che cosa aspettiamo?</strong><small>'+esc(gateNext)+'</small></div></div>'
     +'<div class="decision-price-grid"><div class="decision-price-chart"><div class="decision-price-head"><div><span>PREZZO REALE · ECB DAILY</span><h3>'+pairName(item.key)+' · '+quote+'</h3><small>Fixing BCE '+date(item.asof)+' · ultima seduta '+lastDay+' · 5 sedute '+move+' · 20 sedute '+gain+'</small></div>'
     +'<div class="decision-chart-tools"><div class="pill-controls">'+[20,60,120].map(w=>'<button type="button" data-v9-price-window="'+w+'" class="pill '+(w===window?'active':'')+'" aria-pressed="'+String(w===window)+'">'+w+'</button>').join('')+'</div>'
     +(watch.ready?'<button type="button" data-v12-reference-toggle="1" class="pill decision-reference-toggle '+(showReferences?'active':'')+'" aria-pressed="'+String(showReferences)+'">'+(showReferences?'Riferimenti visibili':'Mostra riferimenti')+'</button>':'')+'</div></div>'
     +graph+(showReferences?'<p class="decision-reference-caption">Tratti <strong>verdi</strong> e <strong>rossi</strong> a destra: riferimenti calcolati con gli ultimi 20 fixing precedenti al '+date(item.asof)+'. Non sono livelli storici costanti né segnali.</p>':'')
     +'<div class="decision-price-evidence"><div class="decision-evidence-cell"><span>5 FIXING</span><strong>'+move+'</strong><small>'+esc(item.fiveState)+'</small></div><div class="decision-evidence-cell"><span>20 FIXING</span><strong>'+gain+'</strong><small>'+esc(item.twentyState)+'</small></div><div class="decision-evidence-cell"><span>RANGE 20 FIXING PRECEDENTI</span><strong class="range">'+esc(range)+'</strong><small>'+esc(item.structure)+'</small></div></div><p class="decision-price-context">'+esc(discordance)+' '+esc(pulse)+'</p>'+watchHtml+'<p class="decision-source">Cross '+pairName(item.key)+' ricostruito dai fixing BCE giornalieri (quote/base). Nessun OHLC o candela H4. Il segno di 5/20 sedute non misura significatività statistica né individua breakout intraday.</p></div>'
     +'<aside class="decision-price-reading"><span>IL GIUDIZIO SUL PREZZO</span><h3>'+esc(item.priceText)+'</h3><p>'+esc(item.timingText)+'</p><div class="decision-stop"><strong>Che cosa dicono le 5 e 20 sedute?</strong><p>'+esc(discordance)+'</p></div><div class="decision-stop"><strong>Che cosa frena il trade?</strong><p>'+esc(item.caution)+'</p></div>'
     +'<div class="decision-stop"><strong>Cosa invaliderebbe la tesi?</strong><p>'+esc(item.missing)+'</p></div>'
     +'<div class="decision-stop"><strong>Positioning e flussi</strong><p>'+esc(item.cot)+' · '+esc(item.liquidity)+'</p></div></aside></div>'
     +ratesEvidence
     +'<p class="decision-footer">Nessun livello d’ingresso, stop o conferma H4 è generato: il feed contiene fixing giornalieri, non candele intraday. Lo storico e la narrativa non dimostrano un edge forward.</p></section>';
  }
  return {overview,pair,data};
 }
 if(typeof window!=='undefined')window.FXQuantDecisionJourney={build,snapshot,profile,series,watchLevels};
 if(typeof module!=='undefined'&&module.exports)module.exports={build,snapshot,profile,series,watchLevels};
})();