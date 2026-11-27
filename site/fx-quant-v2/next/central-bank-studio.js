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
 const BANK_NAMES={USD:'La Fed',EUR:'La BCE',GBP:'La Bank of England',JPY:'La Bank of Japan',
  CHF:'La Banca nazionale svizzera',CAD:'La Bank of Canada',AUD:'La banca centrale australiana',NZD:'La banca centrale neozelandese'};
 const ITALIAN_CONTEXT={
  USD:{date:'2026-10-28',lead:'L’inflazione resta una preoccupazione e alcuni membri avrebbero preferito alzare già i tassi.'},
  EUR:{date:'2026-10-29',lead:'La BCE vede nel caro energia un rischio di prezzi più alti e crescita più debole.'},
  GBP:{date:'2026-11-05',text:'La BoE ha alzato il tasso di 25 punti base. Le mosse successive dipendono dai dati.',
   lead:'Dopo il rialzo, la banca ha legato la prossima mossa ai dati.'},
  JPY:{date:'2026-10-30',lead:'Un membro del consiglio avrebbe preferito alzare subito i tassi.'},
  CHF:{date:'2026-09-24',text:'La SNB ha mantenuto il tasso allo 0%. Segnala un lieve aumento delle pressioni inflazionistiche e resta disponibile a intervenire sul cambio se necessario.',
   lead:'La banca resta pronta a intervenire sul cambio se le condizioni lo richiedono.'},
  CAD:{date:'2026-10-28',lead:'La banca vuole evitare che il caro energia si trasmetta agli altri prezzi.'},
  AUD:{date:'2026-11-03',text:'La RBA ha alzato il tasso di 25 punti base. Il percorso successivo dipende dai dati.',
   lead:'Il rialzo lascia aperta la prossima decisione, che dipenderà dai dati.'},
  NZD:{date:'2026-10-28',lead:'Parte del consiglio avrebbe preferito alzare subito. Un’eventuale stretta dipende dai prossimi dati.'}
 };
 const dayLabel=new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'long',timeZone:'UTC'});
 const when=x=>dayLabel.format(new Date(x+'T12:00:00Z'));
 function classifyAction(bank){
  const x=String(bank?.action||'').trim().toUpperCase();
  if(/^(INVARIAT[OA]|MANTEN|CONFERM|HOLD)/.test(x))return {label:'ULTIMA DECISIONE · INVARIATA',tone:'neutral'};
  if(x.includes('RIALZO')||x.includes('AUMENT'))return {label:'ULTIMA DECISIONE · RIALZO',tone:'hawk'};
  if(x.includes('TAGLIO')||x.includes('RIDUZ'))return {label:'ULTIMA DECISIONE · TAGLIO',tone:'dove'};
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
 function direction(series,today){
  if(!series||!['M','Q'].includes(series.frequency)||!Array.isArray(series.history))return '';
  const [y,m]=series.as_of.slice(0,7).split('-').map(Number);
  const age=(Number(today.slice(0,4))-y)*12+Number(today.slice(5,7))-m;
  const last=series.history.at(-1),prior=series.history.at(-2);
  if(age>(series.frequency==='Q'?6:3)||!finite(prior)||last!==series.latest_value||
     !['source','history','latest','transformation'].every(k=>series.validation?.[k]===true))return '';
  const change=last-prior;
  return Math.abs(change)<.025?'STABILE':change>0?'SALE':'SCENDE';
 }
 function constraint(macro,today){
  const inflation=observation(macro?.inflation,today);
  const labour=observation(macro?.labour,today);
  const inf=direction(inflation,today);
  const unemp=/disoccupazione|unemployment/i.test(labour?.label||'')?
   direction(labour,today):'';
  let title='I dati lasciano aperta la prossima mossa';
  let text='Conta se i prossimi dati su crescita e salari confermano un cambiamento che possa spostare la decisione.';
  if(inf==='SALE'&&unemp==='SALE'){
   title='Prezzi e lavoro tirano in direzioni opposte';
   text='L’inflazione in salita invita a tenere i tassi alti, mentre la disoccupazione in aumento spinge nella direzione opposta.';
  }else if(inf==='SALE'&&unemp==='SCENDE'){
   title='Meno urgenza di allentare';
   text='Con l’inflazione in salita e la disoccupazione in calo, la banca ha meno urgenza di tagliare i tassi.';
  }else if(inf==='SCENDE'&&unemp==='SALE'){
   title='Potrebbe aprirsi spazio per allentare';
   text='Se l’inflazione continua a rallentare e la disoccupazione a salire, la banca avrà più spazio per allentare.';
  }else if(inf==='SCENDE'&&unemp==='SCENDE'){
   title='Prezzi in rallentamento, lavoro in tenuta';
   text='L’inflazione lascia più spazio di manovra. La tenuta del lavoro riduce l’urgenza di usarlo.';
  }else if(inf==='SALE'){
   title='L’inflazione invita alla prudenza';
   text='Se l’inflazione continua a salire, la banca avrà meno spazio per abbassare i tassi.';
  }else if(unemp==='SALE'){
   title='Il lavoro richiede attenzione';
   text='Se la disoccupazione continua a salire, peseranno di più i rischi per la crescita.';
  }else if(!inf&&!unemp){
   title='Margine di manovra da verificare';
   text='Per giudicarlo servono osservazioni datate su inflazione e lavoro.';
  }
  return {title,text,inflation,labour,inf,unemp};
 }
 // Same admitted macro data as the country dossier. Descriptive CAN, not a rate forecast.
 function policyMacroContext({engine,catalog,overlay,country,today}){
  if(!engine||!catalog||!valid(country)||!day(today))return null;
  const clean=x=>x?.available&&finite(x.value)&&!x.stale&&['M','Q'].includes(x.freq);
  const prices=engine.inflationContext(catalog,today,country,overlay)||[];
  const wages=engine.wageContext(catalog,today,country,overlay)||[];
  const jobs=(engine.model(catalog,today,country,overlay)||[]).find(r=>r.key==='jobs');
  const core=prices.slice(1).filter(clean),wage=wages.filter(clean);
  const up=x=>x.direction==='accelera',down=x=>x.direction==='rallenta';
  const sentences=[];
  if(core.length){
   if(core.every(up))sentences.push('Le misure di inflazione sottostante accelerano: aumenta il vincolo sui prezzi.');
   else if(core.every(down))sentences.push('Le misure di inflazione sottostante rallentano: il vincolo sui prezzi potrebbe attenuarsi.');
   else sentences.push('Le misure di inflazione sottostante non mostrano una direzione uniforme di accelerazione.');
  }else sentences.push('Inflazione sottostante corrente non verificabile.');
  if(wage.length){
   const proxy=wage.some(x=>/proxy/i.test(x.label));
   sentences.push((proxy?'Il riferimento salariale settoriale, non i salari dell’intera economia,':'La crescita salariale nominale')+
    (wage.every(up)?' accelera.':wage.every(down)?' rallenta.':' non mostra un’accelerazione uniforme.'));
  }else sentences.push('Manca una misura salariale corrente utilizzabile: nessuna inferenza sui salari.');
  if(jobs?.signal?.tone==='red')sentences.push('Il quadro del lavoro segnala deterioramento: attenzione al rischio per la crescita.');
  if(jobs?.signal?.tone==='green')sentences.push('Il quadro del lavoro è favorevole secondo gli indicatori disponibili.');
  if(jobs?.signal?.tone==='amber')sentences.push('Il quadro del lavoro presenta segnali misti o moderati.');
  return {sentences,prices:prices.filter(clean),wages:wage,missingWages:!wage.length,jobs:jobs?.signal?.tone||'neutral',researchOnly:true};
 }
 function renderPolicyMacroContext(x,esc,fmt){
  if(!x)return '';
  const row=a=>'<li>'+esc(a.label)+' · '+esc(fmt(a.value,2))+'% · '+esc(a.period)+' · '+esc(a.direction||'direzione n.d.')+' · '+esc(a.source||'Fonte n.d.')+'</li>';
  return '<div class="drivers-analysis" data-cb-canonical-macro-context><span>CAN · INFLAZIONE SOTTOSTANTE, SALARI E LAVORO</span>'+
   '<p>'+esc(x.sentences.join(' '))+'</p><details><summary>Osservazioni e fonti del dossier macro</summary><ul>'+
   [...x.prices,...x.wages].map(row).join('')+'</ul><p>Frequenze e definizioni nazionali possono differire. Non è una previsione della prossima decisione.</p></details></div>';
 }
 function macroEvidence(reading,fmt,date){
  const month=value=>day(value)?date(value):value.slice(5,7)+'/'+value.slice(0,4);
  const trend={SALE:'in aumento',SCENDE:'in calo',STABILE:'stabile'};
  return [[reading.inflation,reading.inf],[reading.labour,reading.unemp]].filter(([x])=>x).map(([x,dir])=>{
   const unit=/yoy/i.test(x.transformation||'')?'% annua':/disoccupazione|unemployment/i.test(x.label||'')?'%':'';
   return (x.label||'Dato macro')+' '+fmt(x.latest_value,2)+unit+
    (trend[dir]?' '+trend[dir]:'')+' · '+month(x.as_of);
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
  const latest=row?.week||row?.one;
  const direction=latest?.bp>0?'in rialzo':latest?.bp<0?'in calo':'stabile';
  const window=row?.week?'Nel confronto con la settimana precedente':'Nell’ultimo confronto';
  const indicative=o.kind==='PROXY FUTURES'||o.kind==='FUTURES SECONDARI';
  const subject=o.kind==='PROXY FUTURES'?'il riferimento dei tassi bancari':indicative?
   'la stima dei tassi dei prossimi mesi':'il riferimento di mercato per i tassi dei prossimi mesi';
  const plain=finite(latest?.bp)?window+', '+subject+' è '+direction+'.'+
   (o.kind==='PROXY FUTURES'?' È un’indicazione di direzione.':''):
   !historical&&indicative?'Per i tassi dei prossimi mesi c’è una stima indicativa. Una nuova quotazione chiarirà se la direzione cambia.':'';
  return {
   plain,title:historical?'Ultimo riferimento storico a sei mesi':'Riferimento a sei mesi',
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
  USD:'Su EUR/USD conta se le attese sui tassi americani si muovono più di quelle europee. In una fase di avversione al rischio, la domanda di dollari può pesare anche a tassi fermi.',
  EUR:'Su EUR/GBP, guarda se le attese sulla BCE si spostano rispetto a quelle sulla banca britannica e se il cambio si muove nella stessa direzione.',
  GBP:'Su EUR/GBP, guarda se il mercato si aspetta tassi più alti più a lungo nel Regno Unito che nell’area euro e se la sterlina ne beneficia.',
  JPY:'Su USD/JPY, conta se si restringe il divario tra i tassi attesi negli Stati Uniti e in Giappone. Lo yen può guadagnare terreno anche quando gli operatori riducono il rischio.',
  CHF:'Su EUR/CHF, guarda se cambiano le attese sui tassi svizzeri rispetto a quelli europei. Anche la domanda di franco come bene rifugio può muovere il cambio.',
  CAD:'Su AUD/CAD, guarda se cambiano le attese sui tassi canadesi rispetto a quelli australiani. Se si muove il petrolio, verifica anche la risposta del dollaro canadese.',
  AUD:'Su AUD/CAD, verifica se il mercato cambia idea sui tassi australiani più di quelli canadesi. Anche la domanda cinese e il petrolio possono muovere il cambio.',
  NZD:'Su AUD/NZD, guarda se cambia il divario tra le attese sui tassi australiani e neozelandesi e se il cambio segue.'
 };
 function policyOpening(ccy,action,last,b,localized){
  const name=BANK_NAMES[ccy];
  const phrase={hawk:'ha alzato i tassi',dove:'ha tagliato i tassi',neutral:'ha tenuto fermi i tassi'}[action.tone];
  const title=last&&phrase?name+' '+phrase:'La prossima decisione sui tassi';
  const view=stanceReading(b);
  const bias={
   'Lascia aperta la porta a un rialzo':'La banca lascia aperta la possibilità di un rialzo.',
   'Decide riunione per riunione':'La prossima mossa dipende dai dati.',
   'Comunicazione orientata alla stretta':'La comunicazione indica cautela sui prezzi.',
   'Comunicazione accomodante':'La comunicazione lascia spazio a una politica meno restrittiva.'
  }[view];
  const lead=last?['La decisione risale al '+when(last)+'.',localized?.lead||bias].filter(Boolean).join(' '):'';
  return {title,lead};
 }
 function editorialReading(can,market,nextCheck){
  const support=[
   can.inf==='SCENDE'?'L’inflazione rallenta e lascia più spazio di manovra.':'',
   can.unemp==='SCENDE'?'La disoccupazione scende, riducendo l’urgenza di sostenere il lavoro.':''
  ].filter(Boolean);
  const constraints=[
   can.inf==='SALE'?'L’inflazione sale e rende più difficile allentare la politica monetaria.':'',
   can.unemp==='SALE'?'La disoccupazione sale e aumenta il rischio di tenere i tassi restrittivi troppo a lungo.':''
  ].filter(Boolean);
  const historical=market.title==='Ultimo riferimento storico a sei mesi';
  const marketNote=historical?'Serve una quotazione più recente per leggere le aspettative di mercato.':market.plain;
  return {
   support:support.join(' ')||'Nei dati disponibili manca un segnale netto di sollievo da prezzi o lavoro.',
   constraint:constraints.join(' ')||can.text,
   watch:[marketNote,nextCheck].filter(Boolean).join(' ')
  };
 }
 function render(api){
  const {get,FX,FLAGS,NAMES,state,pageHero,esc,fmt,date,dayNow}=api;
  const banks=get('cb')||{},ois=get('ois')?.currencies||{},mac=get('macro')?.currencies||{};
  const selected=valid(state.cbCcy)?state.cbCcy:'USD',b=banks[selected],o=ois[selected];
  const today=dayNow(),stance=classifyAction(b),can=constraint(mac[selected],today);
  const last=day(b?.last_date)&&b.last_date<=today?b.last_date:null;
  const nextMeeting=day(b?.next_meeting)&&b.next_meeting>=today?b.next_meeting:null;
  const rate=last?(b?.rate_text||(finite(b?.rate)?fmt(b.rate,3)+'%':'n.d.')):'n.d.';
  const market=marketReading(selected,get,today,fmt,date);
  const macroContext=policyMacroContext({engine:root.FXQuantRecessionLight,catalog:get('macroSeries'),overlay:get('semaphoreExtra'),country:selected,today});
  const audit=root.FXQuantDriverMarketAudit;
  const fx=audit?.fx(selected,get('pairs'),today);
  const risk=audit?.riskCheck(get('risk'),today);
  const note=ITALIAN_CONTEXT[selected],localized=note?.date===last?note:null;
  const context=localized?.text||b?.context;
  const story=policyOpening(selected,stance,last,b,localized);
  const reading=editorialReading(can,market,FX_TESTS[selected]);
  const bank=b?.full_name||b?.bank||NAMES[selected]||selected;
  const cards=FX.map(k=>{
   const entry=banks[k],validDate=day(entry?.last_date)&&entry.last_date<=today;
   const action=classifyAction(validDate?entry:null);
   const rateText=validDate?(entry.rate_text||(finite(entry.rate)?fmt(entry.rate,2)+'%':'—')):'—';
   return '<button class="drivers-country" type="button" data-bank-country="'+k+'" aria-pressed="'+String(k===selected)+'">'+
    '<span class="drivers-country-head"><b>'+esc(FLAGS[k]||'')+' '+k+'</b><small>'+esc(entry?.bank||NAMES[k]||k)+'</small></span>'+
    '<span class="bank-first-rate">'+esc(rateText)+'</span><span class="bank-first-action '+action.tone+'">'+esc(action.label.replace('ULTIMA DECISIONE · ',''))+'</span>'+
    '<small class="bank-first-date">'+esc(validDate?date(entry.last_date):'Data da verificare')+'</small></button>';
  }).join('');
  const evidence=macroEvidence(can,fmt,date);
  const source=[b?.policy_decision_source,b?.official_source_url].find(x=>typeof x==='string'&&/^https:\/\//i.test(x));
  return pageHero('POLITICA MONETARIA','Banche centrali',
   'Scegli una banca per capire la sua ultima mossa, cosa le permettono i dati e cosa conta per la valuta.')+
   '<section class="drivers-panel" id="central-bank-studio" aria-label="Scegli una banca centrale">'+
   '<div class="drivers-country-grid">'+cards+'</div></section>'+
   '<section class="drivers-panel drivers-selection" aria-label="Scheda banca centrale '+selected+'">'+
   '<div class="drivers-head"><div><span class="mini-overline">'+esc(FLAGS[selected]||'')+' '+esc(bank)+'</span>'+
   '<h2>'+esc(story.title)+'</h2></div></div>'+
   '<div class="drivers-bank-story">'+
   (last&&story.lead?'<p class="drivers-lead">'+esc(story.lead)+'</p>':'')+
   '<div class="bank-first-grid">'+
   '<article class="bank-first-axis"><h3>Cosa va</h3><p>'+esc(reading.support)+'</p></article>'+
   '<article class="bank-first-axis"><h3>Cosa frena</h3><p>'+esc(reading.constraint)+'</p></article>'+
   '<article class="bank-first-axis"><h3>Cosa guardare</h3><p>'+esc(reading.watch)+'</p></article>'+
   '</div>'+
   (root.FXQuantIssuerContext?.narrative(get('macroObserved'),[selected],today)?'<p class="drivers-lead">'+esc(root.FXQuantIssuerContext.narrative(get('macroObserved'),[selected],today))+'</p>':'')+
   '</div>'+
   '<div class="drivers-links"><button type="button" data-bank-open="rates" data-bank-target="'+selected+'">Vedi i tassi attesi ↗</button>'+
   '<button type="button" data-bank-open="currencies" data-bank-target="'+selected+'">Valuta '+selected+' ↗</button><a href="#macro">Scenario macro ↗</a><a href="#news">Calendario e Notizie ↗</a></div>'+
   '<details class="drivers-fold drivers-bank-sources"><summary>Apri decisione, tassi attesi e fonti</summary>'+
   (root.FXQuantIssuerContext?.render(get('macroObserved'),[selected],today)||'')+
   '<p class="drivers-lead">Tasso ufficiale <strong>'+esc(rate)+'</strong> · decisione '+esc(last?date(last):'da verificare')+
   (nextMeeting?' · prossima riunione '+esc(date(nextMeeting)):' · prossima riunione da verificare')+'</p>'+
   '<div class="drivers-want-can">'+
    '<article class="drivers-analysis"><span>WANT · COSA COMUNICA</span><h3>'+esc(stanceReading(last?b:null))+'</h3><p>'+
      esc(last&&context?context:'Comunicazione ufficiale da verificare.')+'</p></article>'+
    '<article class="drivers-analysis"><span>CAN · MARGINE DI MANOVRA</span><h3>'+esc(can.title)+'</h3><p>'+esc(can.text)+'</p>'+
      (evidence?'<small>'+esc(evidence)+'</small>':'')+'</article>'+
   '</div>'+
   renderPolicyMacroContext(macroContext,esc,fmt)+
   '<div class="drivers-market-audit" aria-label="Mercato e Forex '+selected+'"><div class="drivers-market-grid">'+
    '<div class="drivers-market-item"><span>COSA PREZZA IL MERCATO</span><h3>'+esc(market.title)+'</h3>'+
      (market.evidence?'<p class="drivers-observation">'+esc(market.evidence)+'</p>':'')+'<p>'+esc(market.text)+'</p></div>'+
    '<div class="drivers-market-item"><span>CONFERMA SUL FOREX</span><p>'+esc(fx?.text||'Conferma del prezzo da verificare.')+'</p>'+
     '</div>'+
   '</div></div>'+
   pricing(o,esc,fmt,date,today)+
   '<p class="drivers-source-note">'+(source?'<a href="'+esc(source)+'" target="_blank" rel="noopener noreferrer">Comunicazione ufficiale ↗</a> · ':'')+
   esc(o?.source||'Fonte di mercato da verificare')+'. '+esc(risk||'')+'</p></details></section>';
 }
 const api={classifyAction,render,policyMacroContext,renderPolicyMacroContext};
 root.FXQuantCentralBanks=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
