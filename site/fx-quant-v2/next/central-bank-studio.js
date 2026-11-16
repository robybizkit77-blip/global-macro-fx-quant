'use strict';
/* FX Quant Next — G8 Central Bank Research Studio.
 * WANT = dated official communication; CAN = observed macro constraints;
 * PRICE = dated market instrument. Never conflate the three.
 */
(function(root){
 const valid=x=>/^(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)$/.test(x||'');
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&
  Number.isFinite(Date.parse(x))&&new Date(x).toISOString().slice(0,10)===x;
 const ITALIAN_CONTEXT={
  GBP:{date:'2026-11-05',text:'La BoE ha alzato il tasso di 25 punti base. Le mosse successive dipendono dai dati.'},
  AUD:{date:'2026-11-03',text:'La RBA ha alzato il tasso di 25 punti base. Il percorso successivo dipende dai dati.'},
  CHF:{date:'2026-09-24',text:'La SNB ha mantenuto il tasso allo 0%. Segnala un lieve aumento delle pressioni inflazionistiche e resta disponibile a intervenire sul cambio se necessario.'}
 };
 function classifyAction(bank){
  const x=String(bank?.action||'').toUpperCase();
  if(x.includes('RIALZO')||x.includes('AUMENT'))return {label:'ULTIMA DECISIONE · RIALZO',tone:'hawk'};
  if(x.includes('TAGLIO')||x.includes('RIDUZ'))return {label:'ULTIMA DECISIONE · TAGLIO',tone:'dove'};
  if(x.includes('INVARIATO')||x.includes('INVARIATA'))return {label:'ULTIMA DECISIONE · INVARIATA',tone:'neutral'};
  return {label:'DECISIONE DA VERIFICARE',tone:'unknown'};
 }
 function stanceReading(bank){
  const bias=String(bank?.official_bias||bank?.stance||'').toUpperCase();
  if(bias.includes('RISCHIO RIALZO')||bias.includes('ALTRE STRETTE'))return 'Lascia aperta la porta a un rialzo';
  if(bias.includes('DATA-DIPENDENT')||bias.includes('DATI DIPENDENTI'))return 'Decide riunione per riunione';
  if(bias.includes('DOVISH')||bias.includes('ACCOMODANTE'))return 'Comunicazione accomodante';
  if(bias.includes('HAWKISH'))return 'Comunicazione orientata alla stretta';
  return 'Orientamento da verificare';
 }
 function observation(series,today){
  if(!finite(series?.latest_value)||typeof series.as_of!=='string')return null;
  const date=series.as_of;
  if((!day(date)&&!/^\d{4}-(0[1-9]|1[0-2])$/.test(date))||date>today)return null;
  return series;
 }
 function constraint(macro,today){
  const inflation=observation(macro?.inflation,today);
  const labour=observation(macro?.labour,today);
  const inf=String(inflation?.direction||'').toUpperCase();
  const unemp=/disoccupazione|unemployment/i.test(labour?.label||'')?
   String(labour.direction||'').toUpperCase():'';
  let title='I dati lasciano aperta la prossima mossa';
  let text='Conta se i prossimi dati su crescita e salari confermano un cambiamento che possa spostare la decisione.';
  if(inf==='SALE'&&unemp==='SALE'){
   title='Prezzi e lavoro tirano in direzioni opposte';
   text='I prezzi spingono alla prudenza sui tagli, mentre il lavoro si indebolisce. Conta quale dei due movimenti persiste.';
  }else if(inf==='SALE'&&unemp==='SCENDE'){
   title='Meno urgenza di allentare';
   text='Prezzi in salita e disoccupazione in calo riducono l’urgenza di tagliare. Una sorpresa su inflazione o lavoro può cambiare il quadro.';
  }else if(inf==='SCENDE'&&unemp==='SALE'){
   title='Potrebbe aprirsi spazio per allentare';
   text='Prezzi in rallentamento e disoccupazione in aumento danno più spazio a un taglio, se entrambi i movimenti persistono.';
  }else if(inf==='SCENDE'&&unemp==='SCENDE'){
   title='Prezzi in rallentamento, lavoro in tenuta';
   text='L’inflazione lascia più spazio di manovra. La tenuta del lavoro riduce l’urgenza di usarlo.';
  }else if(!inflation&&!labour){
   title='Margine di manovra da verificare';
   text='Per giudicarlo servono osservazioni datate su inflazione e lavoro.';
  }
  return {title,text,inflation,labour};
 }
 function macroEvidence(reading,fmt,date){
  const month=value=>day(value)?date(value):value.slice(5,7)+'/'+value.slice(0,4);
  const trend={SALE:'in aumento',SCENDE:'in calo',STABILE:'stabile'};
  return [reading.inflation,reading.labour].filter(Boolean).map(x=>{
   const unit=/yoy/i.test(x.transformation||'')?'% annua':/disoccupazione|unemployment/i.test(x.label||'')?'%':'';
   return (x.label||'Dato macro')+' '+fmt(x.latest_value,2)+unit+
    (trend[x.direction]?' '+trend[x.direction]:'')+' · '+month(x.as_of);
  }).join(' | ');
 }
 function marketReading(ccy,get,today,fmt,date){
  const snapshot=get('ois'),o=snapshot?.currencies?.[ccy],h=o?.horizons?.['6m'];
  if(!finite(h?.rate)||!day(h.as_of)||h.as_of>today)
   return {title:'Aspettative a sei mesi da verificare',text:'Manca un riferimento di mercato con livello e data utilizzabili.'};
  const model=root.FXQuantPricingMoves?.readCurrency?.(ccy,snapshot,get('oisOperational'),
    get('oisSameContract'),get('nzdDirectionalProxy'),today);
  const row=model?.rows.find(x=>x.tenor==='6m');
  const kind={'OIS':'OIS','FUTURES':'Futures','FUTURES SECONDARI':'Futures secondari · stima indicativa',
   'PROXY FUTURES':'Proxy sui tassi bancari'}[o.kind]||'Strumento da verificare';
  const historical=Date.parse(today)-Date.parse(h.as_of)>7*864e5;
  const refs=[['1D',row?.one],['1W',row?.week]].filter(([,v])=>finite(v?.bp));
  const deltas=refs.map(([window,v])=>{
   const sign=v.bp>0?'+':v.bp<0?'−':'';
   return window+' '+sign+Math.abs(v.bp).toLocaleString('it-IT',{maximumFractionDigits:2})+' pb';
  });
  return {
   title:historical?'Ultimo riferimento storico a sei mesi':'Riferimento a sei mesi',
   text:deltas.length?'Variazione verificata sullo strumento: '+deltas.join(' · ')+'.':
    historical?'Per leggere il movimento corrente serve una quotazione più recente.':
    'La fonte fornisce il livello. La variazione giornaliera o settimanale resta da verificare.',
   evidence:fmt(h.rate,3)+'% · '+kind+' · '+date(h.as_of)
  };
 }
 function pricing(o,esc,fmt,date,today){
  const horizons=['3m','6m','12m'].map(k=>{
   const x=o?.horizons?.[k],ok=finite(x?.rate)&&day(x?.as_of)&&x.as_of<=today;
   return '<div class="drivers-fact"><span>'+k.toUpperCase()+' / RIFERIMENTO DI MERCATO</span><strong>'+
    (ok?esc(fmt(x.rate,3)+'%'):'Quotazione da verificare')+'</strong><small>'+esc(ok?date(x.as_of):'Fonte o data assente')+'</small></div>';
  }).join('');
  return '<div class="drivers-facts">'+horizons+'</div>';
 }
 const FX_TESTS={
 USD:'Su EUR/USD, verifica se le attese Fed cambiano più di quelle BCE. Se si muovono solo i Treasury o aumenta la domanda di dollari rifugio, il cambio può raccontare una storia diversa.',
 EUR:'Su EUR/GBP conta se i dati spostano le attese BCE più di quelle BoE. Cerca la stessa direzione nei riferimenti monetari confrontabili e nella reazione del cambio.',
 GBP:'Su EUR/GBP conta se il mercato aggiunge o toglie restrizione futura BoE rispetto alla BCE. Il prezzo aiuta a capire se quel cambiamento trova conferma.',
 JPY:'Su USD/JPY verifica se il divario delle attese USA–Giappone si restringe. Uno yen più forte anche con divario fermo è compatibile con una riduzione del carry, da verificare con il rischio globale.',
 CHF:'Per CHF il percorso SNB va confrontato con quello BCE. EUR/CHF può reagire anche alla domanda di rifugio e a eventuali interventi: il differenziale monetario non identifica da solo il flusso.',
 CAD:'Su AUD/CAD confronta le attese BoC e RBA. Se il cambio si muove con il petrolio mentre il divario dei tassi cambia poco, considera il contributo delle commodity.',
 AUD:'Su AUD/CAD verifica se i dati australiani cambiano le attese RBA più di quelle BoC. Crescita cinese e petrolio possono spiegare un movimento anche a differenziale fermo.',
 NZD:'Su AUD/NZD verifica se le attese RBNZ cambiano rispetto alla RBA. Il proxy neozelandese dà contesto e il prezzo aiuta a capire se il movimento trova conferma.'
 };
 function render(api){
  const {get,FX,FLAGS,NAMES,state,pageHero,esc,fmt,date,dayNow}=api;
  const banks=get('cb')||{},ois=get('ois')?.currencies||{},mac=get('macro')?.currencies||{};
  const selected=valid(state.cbCcy)?state.cbCcy:'USD',b=banks[selected],o=ois[selected];
  const today=dayNow(),stance=classifyAction(b),can=constraint(mac[selected],today);
  const last=day(b?.last_date)&&b.last_date<=today?b.last_date:null;
  const nextMeeting=day(b?.next_meeting)&&b.next_meeting>=today?b.next_meeting:null;
  const rate=last?(b?.rate_text||(finite(b?.rate)?fmt(b.rate,3)+'%':'n.d.')):'n.d.';
  const market=marketReading(selected,get,today,fmt,date);
  const audit=root.FXQuantDriverMarketAudit;
  const fx=audit?.fx(selected,get('pairs'),today);
  const risk=audit?.riskCheck(get('risk'),today);
  const localized=ITALIAN_CONTEXT[selected];
  const context=localized?.date===last?localized.text:b?.context;
  const cards=FX.map(k=>{
   const x=banks[k],action=classifyAction(x);
   return '<button class="drivers-country" type="button" data-bank-country="'+k+'" aria-pressed="'+String(k===selected)+'">'+
    '<span class="drivers-country-head"><b>'+esc(FLAGS[k]||'')+' '+k+'</b><small>'+esc(x?.bank||NAMES[k]||k)+'</small></span>'+
    '<span class="drivers-mini-state" data-tone="'+action.tone+'">'+esc(action.label.replace('ULTIMA DECISIONE · ',''))+'</span>'+
    '<span class="drivers-country-date">'+esc(day(x?.last_date)&&x.last_date<=today?date(x.last_date):'Data da verificare')+'</span></button>';
  }).join('');
  const evidence=macroEvidence(can,fmt,date);
  const source=[b?.policy_decision_source,b?.official_source_url].find(x=>typeof x==='string'&&/^https:\/\//i.test(x));
  return pageHero('BANCHE CENTRALI G8','Banche centrali. <em>Cosa possono fare da qui?</em>',
   'Confronta l’ultima comunicazione con i dati di crescita, lavoro e inflazione. Poi verifica quanto si vede nei tassi attesi e nel cambio.')+
   '<section class="drivers-panel" id="central-bank-studio"><div class="drivers-head"><div><h2>Seleziona una banca centrale</h2></div></div>'+
   '<div class="drivers-country-grid">'+cards+'</div></section>'+
   '<section class="drivers-panel drivers-selection" aria-label="Scheda banca centrale '+selected+'">'+
   '<div class="drivers-head"><div><span class="mini-overline">'+esc(FLAGS[selected]||'')+' '+selected+'</span>'+
   '<h2>'+esc(b?.full_name||b?.bank||NAMES[selected]||selected)+'</h2></div>'+
   '<span class="drivers-status" data-tone="'+stance.tone+'">'+esc(stance.label)+'</span></div>'+
   '<p class="drivers-lead">Tasso ufficiale <strong>'+esc(rate)+'</strong> · decisione '+esc(last?date(last):'da verificare')+
   (nextMeeting?' · prossima riunione '+esc(date(nextMeeting)):' · prossima riunione da verificare')+'</p>'+
   '<div class="drivers-want-can">'+
    '<article class="drivers-analysis"><span>WANT · COSA COMUNICA</span><h3>'+esc(stanceReading(last?b:null))+'</h3><p>'+
      esc(last&&context?context:'Comunicazione ufficiale da verificare.')+'</p></article>'+
    '<article class="drivers-analysis"><span>CAN · MARGINE DI MANOVRA</span><h3>'+esc(can.title)+'</h3><p>'+esc(can.text)+'</p>'+
      (evidence?'<small>'+esc(evidence)+'</small>':'')+'</article>'+
   '</div>'+
   '<div class="drivers-market-audit" aria-label="Mercato e Forex '+selected+'"><div class="drivers-market-grid">'+
    '<div class="drivers-market-item"><span>COSA PREZZA IL MERCATO</span><h3>'+esc(market.title)+'</h3>'+
      (market.evidence?'<p class="drivers-observation">'+esc(market.evidence)+'</p>':'')+'<p>'+esc(market.text)+'</p></div>'+
    '<div class="drivers-market-item"><span>CONFERMA SUL FOREX</span><p>'+esc(fx?.text||'Conferma del prezzo da verificare.')+'</p>'+
      '<p>'+esc(FX_TESTS[selected])+'</p></div>'+
   '</div></div>'+
   '<div class="drivers-links"><button type="button" data-bank-open="rates" data-bank-target="'+selected+'">Esamina Tassi & OIS ↗</button>'+
   '<button type="button" data-bank-open="currencies" data-bank-target="'+selected+'">Valuta '+selected+' ↗</button><a href="#macro">Scenario macro ↗</a><a href="#news">Calendario e Notizie ↗</a></div>'+
   '<details class="drivers-fold drivers-bank-sources"><summary>Scadenze 3M / 6M / 12M e fonti</summary>'+
   pricing(o,esc,fmt,date,today)+
   '<p class="drivers-source-note">'+(source?'<a href="'+esc(source)+'" target="_blank" rel="noopener noreferrer">Comunicazione ufficiale ↗</a> · ':'')+
   esc(o?.source||'Fonte di mercato da verificare')+'. '+esc(risk||'')+'</p></details></section>';
 }
 const api={classifyAction,render};
 root.FXQuantCentralBanks=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
