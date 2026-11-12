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
   const bothGood=priceReady&&price.fiveState==='COERENTE'&&price.twentyState==='COERENTE';
   const shortRecovery=priceReady&&price.fiveState==='COERENTE'&&price.twentyState==='CONTRARIO';
   const longOnly=priceReady&&price.fiveState==='CONTRARIO'&&price.twentyState==='COERENTE';
   const bothBad=priceReady&&price.fiveState==='CONTRARIO'&&price.twentyState==='CONTRARIO';
   const timingGood=priceReady&&price.timing==='ALIGNED';
   const valid=Boolean(modelCurrent&&priceReady&&favored&&quality!=='NON VALUTABILE');
   let tier=4,stage='Non valutabile';
   if(!modelCurrent||!priceReady){stage='Aggiornamento necessario';}
   else if(!favored||quality==='NON VALUTABILE'){stage='Vantaggio non definito';}
   else if(bothGood&&priceGood&&timingGood){tier=1;stage='Coerenza da studiare';}
   else if(shortRecovery){tier=2;stage='Recupero da verificare';}
   else if(bothGood){tier=2;stage='Timing da confermare';}
   else if(longOnly){tier=3;stage='Breve termine contrario';}
   else if(bothBad){tier=3;stage='Prezzo ancora contrario';}
   else{tier=3;stage='Divergenza da chiarire';}
   const bias=!favored?'NESSUNO':favored===key.slice(0,3)?'LONG':'SHORT';
   const support=Number(priceGood)*3+Number(timingGood)*2+
    Number(priceReady&&price.fiveState==='COERENTE')+
    Number(priceReady&&price.twentyState==='COERENTE');
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

 // Research shortlist, not a trade portfolio. Prefer distinct relative themes
 // instead of filling five places with the same currency risk.
 function selectResearchPairs(items,limit=5){
  if(!Array.isArray(items)||!Number.isInteger(limit)||limit<1)return [];
  const eligible=items.filter(x=>x&&/^[A-Z]{6}$/.test(x.key||'')&&
   x.base===x.key.slice(0,3)&&x.quote===x.key.slice(3)&&
   (x.favored===x.base||x.favored===x.quote)&&
   (x.thesisStrength==='COERENTE'||x.thesisStrength==='PARZIALE')&&
   (x.tradeAttractiveness==='DA VALIDARE'||x.tradeAttractiveness==='IN ATTESA')&&
   (x.tier===1||x.tier===2));
  const chosen=[],exposure=Object.create(null),direction=Object.create(null);
  const byOriginalRank=(a,b)=>eligible.indexOf(a)-eligible.indexOf(b);
  // Up to two appearances per currency first; relax to three only if needed.
  // At most two selections can express the same favored currency.
  for(const maxExposure of [2,3]){
   for(const x of eligible){
    if(chosen.length===limit)return chosen.sort(byOriginalRank);
    if(chosen.some(y=>y.key===x.key)||
       (exposure[x.base]||0)>=maxExposure||
       (exposure[x.quote]||0)>=maxExposure||
       (direction[x.favored]||0)>=2)continue;
    chosen.push(x);
    exposure[x.base]=(exposure[x.base]||0)+1;
    exposure[x.quote]=(exposure[x.quote]||0)+1;
    direction[x.favored]=(direction[x.favored]||0)+1;
   }
  }
  return chosen.sort(byOriginalRank);
 }


 // Pair-specific evidence gates for the FIRST reading, NOT predictive triggers.
 // Daily thresholds come only from the previous 20 ECB fixings, never from H4/OHLC.
 function pairDecisionWatch(pair,profile){
  const fallback={improve:'Servono nuovi dati macro e monetari relativi, poi una verifica del prezzo sulle stesse date.',
   weaken:'Dati relativi in direzione contraria e prezzo coerentemente opposto indebolirebbero il quadro.',
   note:'Nessuna soglia operativa o conferma H4 disponibile.'};
  if(!pair||typeof pair.key!=='string'||!/^[A-Z]{6}$/.test(pair.key))
   return fallback;
  const favored=pair.favored;
  if(!favored||![pair.base,pair.quote].includes(favored))
   return {...fallback,improve:'Occorre prima una divergenza economica o monetaria che distingua le due valute. Il solo prezzo non crea una tesi.',
    weaken:'Senza un verso fondamentale definito non c’è una tesi direzionale da invalidare.'};
  const opposite=favored===pair.base?pair.quote:pair.base;
  const hasWatch=profile?.key===pair.key&&profile?.source==='STIMA_ESPLICITA_V1'&&
   profile?.fresh===true&&profile?.watch?.ready===true&&
   profile.watch.asof===profile.asof&&Number.isFinite(profile.watch.favorable)&&
   Number.isFinite(profile.watch.adverse);
  const digits=pair.key.endsWith('JPY')?3:5;
  const fmt=v=>v.toLocaleString('it-IT',{minimumFractionDigits:digits,maximumFractionDigits:digits});
  let improve='',weaken='';
  if(pair.macroState==='CONTRARIA')
   improve='Il momentum economico relativo dovrebbe smettere di favorire '+opposite+
    ' e tornare a sostenere '+favored+'.';
  else if(pair.policyState==='CONTRARIA')
   improve='Le variazioni monetarie dovrebbero smettere di favorire '+opposite+
    ' e convergere con la lettura macro su '+favored+'.';
  else if(pair.policyState==='ASSENTE')
   improve='Serve una variazione monetaria confrontabile e datata per entrambe le valute: un proxy non può essere chiamato conferma OIS.';
  else if(hasWatch){
   const w=profile.watch;
   improve=w.favorablePassed?
    'Il fixing BCE ha già superato il riferimento '+w.favorableDirection.toLowerCase()+' '+fmt(w.favorable)+
    '; servirebbe tenuta nei prossimi fixing, senza inseguire il movimento già avvenuto.':
    'Un futuro fixing BCE '+w.favorableDirection.toLowerCase()+' '+fmt(w.favorable)+
    ' darebbe una nuova conferma daily da valutare, non un segnale di ingresso.';
  }else if(pair.fiveState==='CONTRARIO')
   improve='Le ultime cinque sedute BCE dovrebbero tornare coerenti con '+favored+
    ', mantenendo distinta la tesi economica dal timing.';
  else
   improve='Servono una conferma di prezzo successiva alla tesi e la verifica indipendente della struttura Daily/H4.';
  if(hasWatch){
   const w=profile.watch;
   weaken=w.adversePassed?
    'Il fixing è già oltre il riferimento contrario '+w.adverseDirection.toLowerCase()+' '+fmt(w.adverse)+
    ': il prezzo sta già mettendo sotto pressione la tesi.':
    'Un fixing BCE '+w.adverseDirection.toLowerCase()+' '+fmt(w.adverse)+
    ' indebolirebbe la conferma di prezzo per '+favored+'.';
  }else
   weaken='Un ritorno persistente dei fixing a 5 e 20 sedute contro '+favored+
    ' indebolirebbe il timing.';
  weaken+=' Nuovi dati di crescita/lavoro o un repricing monetario verificato a vantaggio di '+
   opposite+' indebolirebbero invece la tesi fondamentale.';
  return {improve,weaken,note:hasWatch?
   'Riferimenti ricavati dai 20 fixing BCE precedenti al '+profile.asof+
   ': non sono massimi/minimi intraday, supporti H4, livelli di ingresso o stop.':
   'Mancano riferimenti daily omogenei per questa tesi: nessun livello di prezzo inventato.'};
}

 function render(api){
  const {get,FLAGS,state,esc,sign,date}=api;
  const est=get('estimatedMacro');
  const active=est?.status==='STIMA_OPERATIVA_NON_VALIDATA'&&
    est.currencies?.length===8&&est.pairs?.length===28;
  const items=active?est.pairs:[],top=selectResearchPairs(items,5);
  const exposures=top.reduce((m,x)=>{
   m[x.base]=(m[x.base]||0)+1;
   m[x.quote]=(m[x.quote]||0)+1;
   return m;
  },{});
  const concentrated=Object.entries(exposures).filter(([,n])=>n>=3);
  const caution=concentrated.length?
   'Esposizione condivisa a '+concentrated.map(([c,n])=>c+' ('+n+' coppie)').join(', ')+
   ': i casi restano correlabili e non rappresentano trade indipendenti.':'';
  const shortlistNote=top.length<5?
   'Oggi solo '+top.length+' coppie rispettano il filtro: non inseriamo casi senza vantaggio netto o con prezzo contrario per raggiungere quota cinque.':
   'Cinque casi di ricerca selezionati cercando di limitare l’esposizione ripetuta alle stesse valute.';
  const shortReading=x=>{
   const fav=x.favored===x.base?1:-1;
   const component=(n,threshold)=>!Number.isFinite(n)||Math.abs(n)<threshold?
    'non decisiva':n>0?'a favore':'contraria';
   const macro=component(x.macroGap*fav,0.10);
   const policy=component(x.policyGap*fav,0.10);
   const price=x.opposite?'contrario':x.aligned?'coerente sui 20 fixing':'non ancora decisivo';
   return 'Tesi '+x.favored+': macro '+macro+'; variazioni tassi '+policy+
    ' (fonti anche proxy); prezzo '+price+'.';
  };
  const row=(x,i,featured=false)=>'<button class="fx-rank-pair '+
   (featured?'featured ':'')+(state.pair===x.key&&state.pairDetailOpen?'selected ':'')+
   'tier-'+x.tier+'" type="button" data-pair="'+esc(x.key)+'" aria-label="Apri tesi '+esc(x.name)+'">'+
   '<span class="fx-rank-number">'+(i+1)+'</span>'+
   '<span class="fx-rank-pair-id"><strong>'+esc(x.name)+'</strong><small>'+
   (x.bias==='NESSUNO'?'NESSUN BIAS':'STIMA '+esc(x.bias))+'</small></span>'+
   '<span class="fx-rank-pair-copy"><strong>'+esc(featured?shortReading(x):x.story)+'</strong>'+
   '<small>'+esc((featured&&x.risk?'Fonti parziali · ':'')+x.priceText)+'</small></span>'+
   '<span class="fx-rank-pair-badges"><span class="fx-rank-pill tier-'+x.tier+'">'+
   'TESI · '+esc(x.thesisStrength)+'</span><span class="fx-rank-minor">'+
   'TRADE · '+esc(x.tradeAttractiveness)+'</span></span>'+
   '<span class="fx-rank-open">Apri tesi ›</span></button>';
  const worst=active?Math.max(...est.currencies.map(x=>Math.abs(x.score)),.0001):1;
  const currencyBody=active?'<div class="fx-rank-currency-list">'+est.currencies.map((x,i)=>{
    const tone=x.score>.04?'positive':x.score<-.04?'negative':'neutral';
    return '<div class="fx-rank-currency" aria-label="'+esc(x.ccy)+' stima '+(i+1)+'">'+
      '<span class="fx-rank-number">'+(i+1)+'</span>'+
      '<strong>'+esc(FLAGS[x.ccy]||'')+' '+x.ccy+'</strong>'+
      '<div class="fx-rank-track"><span class="'+tone+'" style="width:'+
      Math.max(3,Math.abs(x.score)/worst*100).toFixed(1)+'%"></span></div>'+
      '<span class="fx-rank-return '+tone+'">'+esc(x.label)+'</span></div>';
   }).join('')+'</div>':
   '<p class="fx-rank-unavailable">Stima corrente sospesa: '+esc(est?.reason||
    'mancano fonti e prezzi sincronizzati')+'. Il vecchio punteggio di settembre non viene usato al suo posto.</p>';
  const noTrade=top.some(x=>x.tier===1)?
    'La categoria più alta identifica solo un allineamento da studiare, non un ingresso.':
    'Nessuna coppia ha tutte le conferme: questa è una selezione di ricerca, non una lista di trade.';
  return '<div class="fx-ranking-desk" id="fx-ranking-desk">'+
   '<div class="fx-rank-intro"><div><span class="mini-overline">FX / STIMA OPERATIVA V1</span>'+
   '<h2>Chi mostra più forza relativa? <em>Quali coppie meritano verifica?</em></h2>'+
   '<p>La graduatoria G8 riassume macro, tassi e prezzo; nelle coppie la tesi direzionale nasce soltanto da macro e variazioni monetarie. Il prezzo viene valutato a parte per il timing. Il vecchio modello del 25 settembre rimane archivio, non decide queste posizioni.</p></div></div>'+
   '<div class="fx-rank-two">'+
   '<section class="fx-rank-box" aria-label="Classifica stimata G8"><div class="fx-rank-head"><div><span>01 / VALUTE G8</span>'+
   '<h3>Stima relativa · otto valute</h3></div><small>NON SEGNALE</small></div>'+
   '<p class="fx-rank-sub">Un giudizio sintetico aggiornato, con fonti incomplete dichiarate. Il prezzo è solo una delle componenti.</p>'+
   currencyBody+(active?'<p class="fx-rank-source">Ricerca macro '+esc(date(est.asof))+
   ' · prezzi BCE '+esc(date(est.priceAsOf))+
   ' · GDP in accelerazione verificabile per '+est.coverage.withGDPAcceleration+
   '/8 economie; 6M ufficiale per '+est.coverage.official6M+'/8.</p>':'')+'</section>'+
   '<section class="fx-rank-box" aria-label="Cinque coppie FX stimate da studiare">'+
   '<div class="fx-rank-head"><div><span>02 / SELEZIONE FX</span><h3>Fino a 5 coppie da studiare</h3></div>'+
   '<small>STIMA, NON INGRESSO</small></div>'+
   '<p class="fx-rank-sub">Solo tesi con almeno un sostegno fondamentale e senza controprova daily immediata. Thesis Strength e Trade Attractiveness non sono la stessa cosa: nessuna delle due è un segnale di ingresso.</p>'+
   (active?'<p class="fx-rank-source">'+esc(shortlistNote)+'</p>':'')+
   (caution?'<p class="fx-rank-top-caution">'+esc(caution)+'</p>':'')+
   (top.length?'<div class="fx-rank-featured">'+top.map((x,i)=>row(x,i,true)).join('')+'</div>':
    '<p class="fx-rank-unavailable">Le tesi stimate non sono verificabili finché gli input non coincidono.</p>')+'</section></div>'+
   '<section class="fx-rank-box fx-rank-all" aria-label="Classifica completa delle ventotto coppie">'+
   '<div class="fx-rank-head"><div><span>03 / CROSS G8</span>'+
   '<h3>Classifica completa · '+items.length+' coppie</h3></div><small>STIMA DI RICERCA</small></div>'+
   '<p class="fx-rank-sub">TESI = coerenza macro e variazioni monetarie; TRADE = valutazione preliminare del timing sui 5 e 20 fixing. Senza struttura H4, trigger e rischio/rendimento, l’attrattività di ingresso non è certificata.</p>'+
   (items.length?'<div class="fx-rank-all-list">'+items.map((x,i)=>row(x,i)).join('')+'</div>':
    '<p class="fx-rank-unavailable">Ranking sospeso per fonti non aggiornate o incoerenti.</p>')+
   '<p class="fx-rank-source">'+esc(active?('Stima '+date(est.asof)+
    ' · fixing BCE '+date(est.priceFrom)+' → '+date(est.priceAsOf)):
    'Motore stimato non disponibile')+'. '+esc(noTrade)+'</p>'+
   '<details class="fx-rank-method"><summary>Come è costruita la stima e cosa manca</summary>'+
   '<p>Per il ranking delle valute: indice euristico con 50% momentum economico nazionale (45% accelerazione PIL, 20% segno del PIL, 35% variazione disoccupazione), 30% direzione del riferimento monetario settimanale, 20% forza del prezzo sui 20 fixing BCE comuni. Per la tesi delle coppie il prezzo è escluso; la componente fondamentale usa 50% economia e 30% variazioni monetarie, con soglia descrittiva fissa. Il timing considera separatamente i movimenti a 5 e 20 fixing. Non si confrontano direttamente livelli di PIL fra paesi. Contributi mancanti: omessi, non stimati zero come osservazione; qualità parziale dichiarata. Dove manca OIS/futures ufficiale, il 2Y governativo è un proxy attenuato, non una misura di aspettative Fed/ECB. L’inflazione è un contesto di pressione, non un voto meccanico a favore della valuta. Nessuna calibrazione statistica né backtest validato.</p>'+
   '<p>'+esc(est?.warning||'Le osservazioni non consentono oggi una valutazione affidabile.')+'</p>'+
   '</details></section></div>';
 }
 const api={currencyRanking,pairRanking,analyze,selectResearchPairs,pairDecisionWatch,render};
 root.FXQuantPairRankings=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
