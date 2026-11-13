'use strict';
/* Morning Macro & FX Desk — approved narrative-first reading, presentation only.
 * Consumes one frozen, source-dated briefing. Does not compute a trade signal.
 * An earlier edition is explicitly labelled archival; future/leaky data is rejected.
 */
(function(){
 function goodDay(x){return typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)}
 function finite(x){return typeof x==='number'&&Number.isFinite(x)}
 function sound(f){
  if(!f||f.schema!=='GMFQ_MORNING_MACRO_FX_V1'||!goodDay(f.edition_date)
   ||f.observation_cutoff_exclusive!==f.edition_date
   ||!Array.isArray(f.paragraphs)||f.paragraphs.length!==4
   ||!Array.isArray(f.charts)||f.charts.length!==2
   ||f.eligible_for_fx_signal!==false
   ||!goodDay(f.sources?.fx_fixing)||!goodDay(f.sources?.rates)
   ||f.sources.fx_fixing>=f.edition_date||f.sources.rates>=f.edition_date)return false;
  return f.charts.every(c=>goodDay(c.as_of)&&c.as_of<f.edition_date
   &&Array.isArray(c.points)&&c.points.length>=8
   &&c.points.every(p=>goodDay(p.date)&&p.date<f.edition_date&&finite(p.value)));
 }

 // Explain what's driving the ranking instead of repeating rank numbers.
 // The currency rank combines macro, rates, and 20 ECB fixings; components
 // must not be mistaken for independent FX trade evidence.
 function currencyDriver(x,position){
  if(!x||!/^[A-Z]{3}$/.test(x.ccy||''))return '';
  const sign=position==='top'?1:-1;
  const parts=[];
  if(finite(x.macroScore)&&x.macroScore*sign>0.12)
   parts.push(sign>0?'momentum interno di crescita e lavoro favorevole':
    'momentum interno di crescita e lavoro sfavorevole');
  if(finite(x.policyScore)&&x.policyScore*sign>0.10){
   const kind=x.rate?.quality==='UFFICIALE'?'variazioni 6M di OIS/futures ufficiali':
    x.rate?.quality==='PROXY'?'movimento del governativo 2Y usato come proxy':'';
   if(kind)parts.push(kind+(sign>0?' nella direzione restrittiva':' nella direzione meno restrittiva'));
  }
  if(finite(x.priceScore)&&x.priceScore*sign>0.1)
   parts.push(sign>0?'forza FX relativa nei 20 fixing BCE':
    'debolezza FX relativa nei 20 fixing BCE');
  const place=position==='top'?'in cima':'in fondo';
  const reasons=parts.length?' incidono '+parts.slice(0,2).join(' e '):
   ' nessuna singola componente offre una prova decisiva';
  return x.ccy+' '+place+' alla graduatoria stimata:'+reasons+
   (x.partial?'. Copertura macro/tassi parziale.':'.');
 }
 // A scheduled item on today's date may already have been released.
 // No clock-time guess: treat it as a result to verify, NEVER as future.
 function nextFxCatalysts(calendar,selected,now){
  const empty={today:null,next:null,relevant:null,sourceAsOf:null,reason:'CALENDARIO_NON_VERIFICABILE'};
  if(!goodDay(now)||calendar?.schema!=='GMFQ_CALENDAR_OPERATIONAL_VIEW_V3'||
     !Array.isArray(calendar.events))return empty;
  const checked=String(calendar.last_checked_at_utc||'').slice(0,10);
  const age=(Date.parse(now+'T00:00:00Z')-Date.parse(checked+'T00:00:00Z'))/864e5;
  if(!goodDay(checked)||!finite(age)||age<0||age>7)return empty;
  const eligible=calendar.events.filter(x=>x&&x.status==='UPCOMING'&&
   x.importance==='HIGH'&&typeof x.ccy==='string'&&
   /^[A-Z]{3}$/.test(x.ccy)&&goodDay(x.date)&&
   x.date>=now&&typeof x.quality==='string'&&x.quality.startsWith('OFFICIAL')&&
   ['GROWTH','LABOUR','INFLATION','CENTRAL_BANK_DECISION'].includes(x.event_type)&&
   typeof x.title==='string'&&x.title.length>0).sort((a,b)=>
   a.date.localeCompare(b.date)||a.ccy.localeCompare(b.ccy));
  const picked=Array.isArray(selected)?selected.slice(0,3):[];
  const currencies=new Set(picked.flatMap(x=>[x?.base,x?.quote]).filter(x=>
   typeof x==='string'&&/^[A-Z]{3}$/.test(x)));
  const today=eligible.find(x=>x.date===now)||null;
  const future=eligible.filter(x=>x.date>now);
  const next=future[0]||null;
  const relevant=future.find(x=>currencies.has(x.ccy))||null;
  return {today,next,relevant,sourceAsOf:checked,reason:'SEED_SENZA_CONSENSO_VALIDATO'};
 }
 function catalystReading(calendar,selected,now,date){
  const events=nextFxCatalysts(calendar,selected,now);
  if(!events.sourceAsOf)return 'Calendario G8 non aggiornato o non verificabile: non attribuiamo alcun evento futuro senza una fonte datata.';
  const name=x=>x.ccy+' · '+x.title+' ('+date(x.date)+')'+
   (x.quality==='OFFICIAL_PROVISIONAL'?' · data provvisoria':'');
  const consequence=x=>x.event_type==='GROWTH'?
   'Il dato sulla crescita può modificare le aspettative relative sulla banca centrale, non il prezzo in modo automatico.':
   x.event_type==='LABOUR'?
   'Dinamica di occupazione e disoccupazione: conta la sorpresa rispetto alle attese e il conseguente repricing.':
   x.event_type==='INFLATION'?
   'Composizione e persistenza dei prezzi possono cambiare il pricing monetario, se sorprendono le attese.':
   'Decisione e comunicazione vanno confrontate con il percorso di tassi già prezzato.';
  const lines=[];
  if(events.today)
   lines.push('Nel calendario era previsto oggi '+name(events.today)+
    '. L’esito non è confermato da questo feed: prima di interpretare l’evento servono dato effettivo, consenso e risposta del mercato.');
  if(events.next)
   lines.push('Il prossimo evento G8 programmato è '+name(events.next)+'. '+consequence(events.next));
  if(events.relevant&&events.relevant!==events.next)
   lines.push('Per le coppie selezionate, il prossimo catalizzatore diretto è '+
    name(events.relevant)+'.');
  if(!lines.length)return '';
  return lines.join(' ')+' Ultima verifica del calendario '+date(events.sourceAsOf)+
   '; consenso non disponibile: nessuna sorpresa o reazione FX attribuita in anticipo.';
 }

 // Independently dated FX research update. NEVER part of the frozen morning
 // edition, and NEVER represented as pre-opening or as an event reaction.
 function fxResearchPulse({estimated,calendar,selectResearchPairs,watchForPair,esc,date,dayNow}={}){
  if(!estimated)return '';
  const text=x=>esc(String(x??''));
  const today=dayNow();
  const valid=estimated.status==='STIMA_OPERATIVA_NON_VALIDATA'&&
   goodDay(today)&&goodDay(estimated.asof)&&goodDay(estimated.priceAsOf)&&
   estimated.asof<=today&&estimated.priceAsOf<=today&&
   Array.isArray(estimated.currencies)&&estimated.currencies.length===8&&
   Array.isArray(estimated.pairs)&&estimated.pairs.length===28&&
   typeof selectResearchPairs==='function';
  if(!valid)return '<section class="morning-fx-pulse unavailable" data-fx-pulse="unavailable"'+
   ' aria-label="Selezione Forex aggiornata non disponibile">'+
   '<div class="morning-section-label">COLLEGAMENTO FX · RICERCA INDIPENDENTE</div>'+
   '<h2>La selezione corrente è sospesa</h2>'+
   '<p>Non abbiamo una graduatoria aggiornata verificabile delle 28 coppie. Il briefing riportato sotto resta un’edizione storica; non trasformiamo dati incompleti in opportunità.</p>'+
   '<a href="#pairs">Verifica le fonti e le 28 coppie</a></section>';
  const ranking=estimated.currencies.slice().sort((a,b)=>a.rank-b.rank);
  const topCcy=ranking[0]?.ccy,lastCcy=ranking.at(-1)?.ccy;
  if(!/^[A-Z]{3}$/.test(topCcy||'')||!/^[A-Z]{3}$/.test(lastCcy||''))return '';
  const selected=selectResearchPairs(estimated.pairs,5).slice(0,3).filter(x=>
   x&&/^[A-Z]{6}$/.test(x.key)&&
   (x.favored===x.base||x.favored===x.quote)&&
   typeof x.thesisStrength==='string'&&typeof x.tradeAttractiveness==='string');
  const lead='La stima G8 mette in luce un contrasto. '+
   currencyDriver(ranking[0],'top')+' '+currencyDriver(ranking.at(-1),'bottom')+
   ' Il confronto combina macro, variazioni dei tassi e fixing: spiega l’ordine del modello, non dimostra chi sta comprando o vendendo.';
  const catalyst=catalystReading(calendar,selected,today,date);
  const showPair=x=>{
   const key=x.key,label=key.slice(0,3)+'/'+key.slice(3);
   const gate=typeof watchForPair==='function'?watchForPair(x):null;
   const improve=gate&&typeof gate.improve==='string'?gate.improve:
    'Servono un nuovo confronto economico/monetario datato e una conferma daily.';
   // One explanation per overview card; full constraints remain in the dossier.
   const firstSentence=x.thesisReason?.split('. ')[0];
   const reasoning=typeof firstSentence==='string'&&firstSentence.trim()?firstSentence:
    'La tesi fondamentale è una stima da approfondire.';
   return '<button type="button" class="morning-fx-case" data-pair="'+text(key)+'"'+
    ' aria-label="Apri dossier '+text(label)+'">'+
    '<span class="morning-fx-case-top"><strong>'+text(label)+'</strong>'+
    '<small>TESI '+text(x.thesisStrength)+' · TRADE '+text(x.tradeAttractiveness)+'</small></span>'+
    '<span class="morning-fx-case-reason">'+text(reasoning)+'</span>'+
    '<span class="morning-fx-case-watch"><b>Per migliorare:</b> '+text(improve)+'</span>'+
    '<span class="morning-fx-case-open">Apri il dossier →</span></button>';
  };
  return '<section class="morning-fx-pulse" data-fx-pulse="current"'+
   ' aria-label="Collegamento corrente Macro G8 e selezione Forex">'+
   '<div class="morning-fx-pulse-heading"><div><span class="morning-section-label">FX RESEARCH · AGGIORNAMENTO SEPARATO</span>'+
   '<h2>Dal quadro macro alle coppie da verificare</h2></div>'+
   '<small>Ricerca '+text(date(estimated.asof))+' · fixing BCE '+text(date(estimated.priceAsOf))+'</small></div>'+
   '<p class="morning-fx-pulse-intro">'+text(lead)+'</p>'+
   (catalyst?'<p class="morning-fx-pulse-catalyst"><strong>Prossime verifiche macro.</strong> '+
    text(catalyst)+'</p>':'')+
   (selected.length?
    '<p class="morning-fx-pulse-explain">Dalla Top 5 diversificata, '+selected.length+
    ' coppie meritano un controllo più attento. Il dossier spiega anche ciò che potrebbe smentirle.</p>'+
    '<div class="morning-fx-pulse-cases">'+selected.map(showPair).join('')+'</div>':
    '<p class="morning-fx-pulse-empty">Nessuna coppia supera il filtro di ricerca: non selezioniamo trade per riempire tre posti.</p>')+
   '<p class="morning-fx-pulse-notice">Ricerca stimata e datata, distinta dal briefing mattutino congelato: può includere osservazioni successive alla sua apertura. Nessun segnale d’ingresso o conferma H4.</p>'+
   '<nav class="morning-fx-pulse-links"><a href="#currencies">Classifica G8</a>'+
   '<a href="#pairs">Tutte le 28 coppie</a><a href="#news">Notizie e calendario</a></nav>'+
   '</section>';
 }


 // The published morning edition is immutable, but the current official
 // calendar may correct an omitted scheduled event. In that case, reconcile
 // the FIRST READ without rewriting or disguising the original edition.
 function localClockInRome(event){
  if(!goodDay(event?.date)||!/^\d{2}:\d{2}$/.test(event?.time_local||'')||
     typeof event?.timezone!=='string')return null;
  try{
   const probe=new Date(event.date+'T'+event.time_local+':00Z');
   const formatter=new Intl.DateTimeFormat('en-GB',{
    timeZone:event.timezone,year:'numeric',month:'2-digit',day:'2-digit',
    hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
   const parts=Object.fromEntries(formatter.formatToParts(probe)
    .filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
   const localAsUTC=Date.UTC(Number(parts.year),Number(parts.month)-1,
    Number(parts.day),Number(parts.hour),Number(parts.minute));
   const actual=new Date(probe.getTime()-(localAsUTC-probe.getTime()));
   const check=Object.fromEntries(formatter.formatToParts(actual)
    .filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
   if([check.year,check.month,check.day].join('-')!==event.date ||
      check.hour+':'+check.minute!==event.time_local)return null;
   return new Intl.DateTimeFormat('it-IT',{
    timeZone:'Europe/Rome',hour:'2-digit',minute:'2-digit',hour12:false
   }).format(actual);
  }catch{return null}
 }

 // Editorial FX lens: use the same CURRENT G8/28-pair estimate as the other
 // sections, plus strictly matched weekly government-rate changes. The
 // 2Y differential is a rates proxy, NEVER labelled an observed OIS repricing.
 function estimatedFxReading(estimated,rates,ccy,today,date){
  if(estimated?.status!=='STIMA_OPERATIVA_NON_VALIDATA'||
     !goodDay(estimated.asof)||!goodDay(estimated.priceAsOf)||
     estimated.asof>today||estimated.priceAsOf>today||
     !Array.isArray(estimated.currencies)||estimated.currencies.length!==8||
     !Array.isArray(estimated.pairs)||estimated.pairs.length!==28)return null;
  const by=Object.fromEntries(estimated.currencies.map(x=>[x.ccy,x]));
  const main=by[ccy];
  if(!main||!Number.isInteger(main.rank)||main.rank<1||main.rank>8)return null;
  const pairCodes=ccy==='USD'?['EURUSD','USDJPY']:
   ccy==='EUR'?['EURUSD','EURGBP']:
   ccy==='GBP'?['GBPUSD','EURGBP']:
   ccy==='JPY'?['USDJPY','EURJPY']:
   ccy==='CHF'?['EURCHF','USDCHF']:
   ccy==='CAD'?['USDCAD','CADJPY']:
   ccy==='AUD'?['AUDUSD','AUDJPY']:['NZDUSD','NZDJPY'];
  const sample=pairCodes.map(key=>estimated.pairs.find(x=>x.key===key)).filter(Boolean);
  const desc=p=>{
   const label=p.name||p.key.slice(0,3)+'/'+p.key.slice(3);
   const preferred=p.favored;
   const direction=preferred===ccy?'vantaggio stimato per '+ccy:
    preferred?'vantaggio stimato per '+preferred:'vantaggio fondamentale misto';
   const price=Number.isFinite(p.move5Percent)?
    (Math.abs(p.move5Percent)<0.05?'quasi stabile':
     p.move5Percent>0?'in rialzo':'in calo')+
     ' negli ultimi 5 fixing BCE':'in osservazione';
   return label+': '+direction+', prezzo '+price;
  };
  const pairText=sample.length?sample.map(desc).join('; ')+'.':'';
  let rateText='';
  if(ccy==='USD'){
   const a=rates?.USD?.weekly2_validation,b=rates?.EUR?.weekly2_validation;
   if(a&&b&&Number.isFinite(a.change_bp)&&Number.isFinite(b.change_bp)&&
      goodDay(a.start_date)&&a.start_date===b.start_date&&
      goodDay(a.end_date)&&a.end_date===b.end_date&&a.end_date<=today){
    const diff=a.change_bp-b.change_bp;
    rateText='Tra '+date(a.start_date)+' e '+date(a.end_date)+
     ' il Treasury 2Y è variato di '+a.change_bp.toLocaleString('it-IT')+
     ' pb contro '+b.change_bp.toLocaleString('it-IT')+
     ' pb del governativo Eurozona: il differenziale settimanale si è '+
     (diff>=0?'allargato di ':'ristretto di ')+
     Math.abs(diff).toLocaleString('it-IT',{maximumFractionDigits:1})+
     ' pb '+(diff>0?'a favore del dollaro.':diff<0?
      'a sfavore del dollaro.':'senza nuova direzione.')+
     ' È una misura governativa, usata come proxy del canale monetario.';
   }
  }
  const macro=main.macroScore;
  const macroReading=Number.isFinite(macro)?
   (macro>=0.2?'contributo macro domestico favorevole':
    macro<=-0.2?'contributo macro domestico sfavorevole':
    'momentum macro domestico misto'):'momentum macro in valutazione';
  return {
   meaning:'Nella stima quantitativa G8 '+ccy+' occupa la posizione '+
    main.rank+' su 8, con '+macroReading+'. '+rateText+
    (pairText?' Sul Forex: '+pairText:'')+
    ' Il ranking combina macro, tassi e fixing: è una lettura relativa, non una previsione certa.',
   watch:'Seguire se i prossimi aggiornamenti dei riferimenti monetari relativi e '+
    (sample.length?sample.map(p=>p.name||p.key.slice(0,3)+'/'+p.key.slice(3)).join(' e '):
     'le coppie di '+ccy)+
    ' rafforzano oppure contraddicono questa lettura stimata. '+
    'Le date del proxy e del fixing restano indicate nel dossier.',
   kind:'STIMA_QUANT_FX_V1'
  };
 }

 function officialReconciliation(feed,calendar,today,date,estimated,rates){
  if(feed?.edition_date!==today)return null;
  const latest=nextFxCatalysts(calendar,[],today);
  const event=latest.today;
  if(!latest.sourceAsOf||!event||event.date!==feed.edition_date||
     event.quality!=='OFFICIAL_CONFIRMED')return null;
  const original=(feed.catalyst?.title||'')+' '+(feed.headline||'');
  if(feed.catalyst?.date===event.date&&
     original.toLowerCase().includes(event.title.toLowerCase()))return null;
  const isUSProducer=event.ccy==='USD'&&event.title==='Producer Price Index';
  const name=isUSProducer?'PPI USA':event.ccy+' · '+event.title;
  const clock=localClockInRome(event);
  const when='oggi'+(clock?' alle '+clock+' italiane':'')+
   ' ('+date(event.date)+')';
  const pairs=event.ccy==='USD'?'EUR/USD e USD/JPY':
   event.ccy==='GBP'?'GBP/USD ed EUR/GBP':
   event.ccy==='JPY'?'USD/JPY ed EUR/JPY':
   'le coppie che comprendono '+event.ccy;
  const inflation=event.event_type==='INFLATION';
  const estimate=estimatedFxReading(estimated,rates,event.ccy,today,date);
  return {
   headline:name+': la prova è nelle aspettative sui tassi e nel Forex',
   lead:'Il calendario ufficiale segnala '+name+' '+when+
    '. La prima edizione non includeva questo appuntamento: lo segnaliamo senza cancellarla. '+
    'Il punto non è anticipare il risultato, ma capire se i dati modificheranno '+
    'le aspettative monetarie già incorporate nei prezzi.',
   meaning:(estimate?.meaning||
    (inflation?
     'Il dato sui prezzi orienta la lettura del dollaro attraverso le attese Fed relative: una pressione maggiore tende a sostenere il canale tassi USD, una pressione minore può indebolirlo. ':
     'Il catalizzatore può cambiare l’orientamento delle aspettative monetarie relative. ')+
    'La reazione da seguire è sul differenziale dei rendimenti e su '+pairs+'.'),
   catalyst:'Nel calendario ufficiale: '+name+' '+when+'. '+
    (event.ccy==='USD'&&inflation?
     'Con prezzi alla produzione più persistenti, osserviamo il rischio di attese Fed più restrittive e di un USD sostenuto dal front-end; con dati più deboli, l’opposto. ':
     'Una sorpresa macro più forte o più debole può modificare le aspettative relative sulla banca centrale e il pricing della valuta, soprattutto se il mercato aveva già anticipato un esito diverso. ')+
    'La direzione va confrontata con attese pre-evento, composizione e risposta su '+pairs+
    '. Gli scenari sono condizionali e precedono la pubblicazione.',
   watch:estimate?.watch||
    'Pubblicazione e confronto con attese documentate; tassi relativi e '+pairs+
    '. Separare forza valutaria dalla debolezza della controparte.',
   sourceAsOf:latest.sourceAsOf
  };
 }

 function build({feed,plot,esc,date,dayNow,currentResearch}){
  if(!sound(feed)||feed.edition_date>dayNow())return null;
  const current=feed.edition_date===dayNow();
  const correction=officialReconciliation(feed,currentResearch?.calendar,dayNow(),date,
   currentResearch?.estimated,currentResearch?.rates);
  const title=esc(correction?.headline||feed.headline);
  const text=x=>esc(String(x||''));
  const safePair=typeof feed.pair==='string'&&/^[A-Z]{6}$/.test(feed.pair)?feed.pair:null;
  const sources=feed.sources||{};
  const noteBase=!current?'Questa è l’ultima edizione archiviata, non il briefing di oggi. Il motore non ha ancora pubblicato una nuova lettura.':
   feed.edition_status==='LATE_MORNING_SNAPSHOT'?'Edizione pubblicata dopo l’orario previsto: il ritardo non viene nascosto.':
   feed.edition_status==='RECONSTRUCTION_NOT_POINT_IN_TIME'?
    'Anteprima ricostruita dalle osservazioni disponibili prima della data, non certificata come fotografia point-in-time delle 08:00.':
    'Edizione mattutina congelata: gli eventi pubblicati dopo l’apertura non modificano questo testo.';
  const note=correction?'Calendario ufficiale aggiornato al '+date(correction.sourceAsOf)+
   ': il catalizzatore odierno è stato integrato nella lettura. Edizione originale consultabile negli approfondimenti.':noteBase;
  // First-read uses only the frozen edition's source-dated evidence.
  // Do not infer a new daily FX move or a monetary-policy surprise.
  const relative=feed.relative_evidence||{};
  const comparable=safePair==='EURUSD'&&goodDay(relative.aligned_from)
   &&goodDay(relative.aligned_to)&&relative.aligned_from<=relative.aligned_to
   &&relative.aligned_to<feed.edition_date
   &&finite(relative.spread_change_aligned_bp)&&finite(relative.pair_change_aligned_pct);
  const signed=(n,d,unit)=>(n>0?'+':n<0?'−':'')+
   Math.abs(n).toLocaleString('it-IT',{minimumFractionDigits:d,maximumFractionDigits:d})+unit;
  const alignedEvidence=comparable?
   'Dal '+date(relative.aligned_from)+' al '+date(relative.aligned_to)+
   ' il differenziale dei rendimenti a 2 anni USA–Eurozona è cambiato di '+
   signed(relative.spread_change_aligned_bp,1,' punti base')+
   ' ed EUR/USD di '+signed(relative.pair_change_aligned_pct,2,'%')+'.':
   'Il briefing distingue dati macro, aspettative sui tassi e risposta delle coppie Forex. Le osservazioni disponibili non vanno trattate come un unico movimento intraday.';
  const usdCompatible=comparable&&relative.alignment==='COERENTE'
   &&relative.spread_change_aligned_bp>0&&relative.pair_change_aligned_pct<0;
  const estimatedReading=estimatedFxReading(currentResearch?.estimated,currentResearch?.rates,
   feed.catalyst?.currency||'USD',dayNow(),date);
  const fxMeaning=usdCompatible?
   'In quel periodo tassi relativi e cambio sono andati nella direzione compatibile con un USD più sostenuto contro EUR. Non dimostra chi abbia mosso il prezzo e non certifica la seduta di oggi.':
   comparable&&relative.alignment==='COERENTE'?
    'I due movimenti sono coerenti nell’intervallo confrontato, ma la coincidenza non dimostra una causa e non è un segnale operativo.':
    'Il quadro resta misto: il confronto tra rendimenti relativi e prezzo non offre ancora una direzione concorde. La forza delle singole valute va confrontata con le altre coppie.';
  const missing=feed.event_status==='AFTERMATH_UNVERIFIED'?
   'L’effetto dell’evento macro non è ancora verificato: servono dati ufficiali, sorpresa rispetto alle attese, variazioni OIS/futures confrontabili e reazione FX sulle stesse date.':
   'Prima di confermare la tesi servono dati e prezzi confrontabili nel tempo, soprattutto le aspettative sui tassi e la risposta delle singole coppie.';
  const firstRead='<section class="morning-first-read" aria-label="Implicazioni per il Forex">'+
   '<div class="morning-section-label">PERCHÉ CONTA PER IL FOREX</div>'+
   '<p class="morning-key-meaning">'+text(correction?.meaning||estimatedReading?.meaning||fxMeaning)+'</p>'+
   '<p class="morning-key-watch"><strong>Da monitorare.</strong> '+
    text(correction?.watch||estimatedReading?.watch||feed.watch)+'</p>'+
   '<div class="morning-first-links"><a href="#currencies">Forza G8</a>'+
   '<a href="#pairs">Coppie FX</a><a href="#rates">Verifica Tassi &amp; OIS</a></div>'+
   '</section>';
  const renderChart=(c,i)=>{
   const color=i===0?'#71e0bd':'#77caff';
   const show=plot({lines:[{name:c.label,color,values:c.points.map(p=>({label:p.date,value:p.value}))}],
     label:c.label,precision:c.precision??2,unit:c.unit||'',window:28});
   return '<figure class="morning-chart-card"><div class="morning-chart-top"><h3>'+text(c.label)+'</h3><strong>'+
     (finite(c.last_value)?c.last_value.toLocaleString('it-IT',{minimumFractionDigits:c.precision??2,maximumFractionDigits:c.precision??2}):'—')+
     (c.unit?' '+text(c.unit):'')+'</strong></div>'+show+
     '<figcaption>Ultima osservazione '+date(c.as_of)+'. '+(i===0?
       'Rendimenti governativi riferiti allo stesso giorno; livello di spread, non repricing Fed certificato.':
       'Fixing BCE, non prezzo intraday né reazione istantanea al dato.')+'</figcaption></figure>';
  };
  const paragraphs=feed.paragraphs.map(p=>'<p>'+text(p)+'</p>').join('');
  const scenarios=(feed.scenarios||[]).slice(0,2).map((s,i)=>
    '<article class="morning-scenario '+(i===0?'restr':'acc')+'"><h3>'+text(s.title)+'</h3><p>'+text(s.text)+'</p></article>').join('');
  // One clear entry point. Detail, estimates, graphs and alternative scenarios
  // are available on demand; they do not compete with the main desk narrative.
  return '<article class="market-letter market-dashboard morning-dashboard"'+
   (correction?' data-home-calendar-reconciled="true"':'')+
   ' aria-label="Morning Macro e Forex Research Desk">'+
   '<div class="morning-edition-header"><span>FX QUANT / MORNING MACRO & FX RESEARCH DESK</span>'+
   '<span>Edizione '+date(feed.edition_date)+' · FX BCE '+date(sources.fx_fixing)+
   ' · Tassi '+date(sources.rates)+'</span></div>'+
   '<div class="morning-archive-note'+(current?' current':'')+'">'+text(note)+'</div>'+
   '<header class="morning-lead"><span class="morning-kicker">IL TEMA CHE CONTA OGGI</span>'+
   '<h1>'+title+'</h1><p class="morning-deck">'+text(correction?.lead||feed.lead)+'</p>'+
   '<div class="morning-edition-tags"><span>Macro → aspettative → Forex</span>'+
   '<span>Fonti datate, nessun segnale automatico</span>'+
   '<span>'+(feed.edition_status==='MORNING_SNAPSHOT'?
     'Osservazioni precedenti alla seduta':'Edizione pubblicata in ritardo o ricostruita')+
   '</span></div></header>'+
   firstRead+
   '<aside class="morning-catalyst"><div class="morning-section-label">'+
   (correction?'CATALIZZATORE UFFICIALE · CALENDARIO AGGIORNATO':'IL CATALIZZATORE')+
   '</div><h2>'+text(correction?'Evento da verificare: '+(correction.headline.split(':')[0]):feed.catalyst?.title)+'</h2>'+
   '<p>'+text(correction?.catalyst||feed.catalyst?.text||feed.watch)+'</p></aside>'+
   '<section class="morning-prose" aria-label="Archivio della lettura completa">'+
   '<details class="morning-deep-reading"><summary><strong>Approfondisci la lettura originale</strong>'+
   '<span>Contesto, confronto dei tassi e limiti delle evidenze</span></summary>'+
   '<div class="morning-deep-body">'+
   (correction?'<p><strong>Edizione originale non riscritta:</strong> '+text(feed.headline)+
    '. '+text(feed.lead)+'</p>':'')+
   '<div class="morning-section-label">CONTESTO E VERIFICHE DATATE</div>'+
   paragraphs+'</div></details></section>'+
   (currentResearch?'<details class="morning-secondary-research morning-deep-reading">'+
    '<summary><strong>Esplora la forza G8 e le coppie selezionate</strong>'+
    '<span>Ranking stimato, distinto dall’analisi principale</span></summary>'+
    fxResearchPulse({...currentResearch,esc,date,dayNow})+'</details>':'')+
   '<details class="morning-supporting morning-deep-reading"><summary>'+
   '<strong>Visualizza i due grafici di supporto</strong>'+
   '<span>Fixing BCE e differenziali governativi datati, non reazioni al dato</span></summary>'+
   '<section class="morning-evidence"><div class="morning-section-label">EVIDENZA STORICA</div>'+
   '<div class="morning-chart-grid">'+feed.charts.map(renderChart).join('')+
   '</div></section></details>'+
   '<details class="morning-supporting morning-deep-reading"><summary>'+
   '<strong>Scenari e giudizio dell’edizione originale</strong>'+
   '<span>Ipotesi condizionali, non raccomandazioni di trading</span></summary>'+
   '<section class="morning-outlook"><div class="morning-scenario-grid">'+scenarios+
   '</div><aside class="morning-judgment"><strong>Giudizio della prima edizione</strong>'+
   '<p>'+text(feed.verdict)+'</p></aside></section></details>'+
   '<nav class="morning-research-links" aria-label="Approfondimenti nel Research Desk">'+
   '<a href="#macro">Scenario Macro</a><a href="#rates">Tassi &amp; OIS</a>'+
   '<a href="#currencies">Valute G8</a><a href="#pairs">28 coppie FX</a>'+
   '<a href="#cot">COT</a><a href="#news">Calendario</a></nav>'+
   '<footer class="morning-source-notes"><p>FX BCE '+date(sources.fx_fixing)+
   ' · Rendimenti governativi '+date(sources.rates)+
   ' · Eventi: calendario ufficiale verificato separatamente. '+
   text((feed.limitations||[]).join(' '))+'</p>'+
   '<p>Edizione '+text(feed.edition_status)+
   ' · Ricerca basata su regole, non revisione editoriale umana certificata.</p></footer>'+
   '</article>';
 }
 // An independently timestamped post-release note may follow a frozen opening
 // edition. It must NEVER rewrite the morning article or claim event-price proof.
 function postRelease(feed,news,esc,dayNow,nowUtc){
  const validStamp=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(x)&&Number.isFinite(Date.parse(x));
  const validDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
  const ccyNames={
   USD:['Fed','EUR/USD e USD/JPY'],EUR:['BCE','EUR/USD e EUR/GBP'],
   GBP:['BoE','GBP/USD e EUR/GBP'],JPY:['BoJ','USD/JPY e EUR/JPY'],
   CHF:['SNB','EUR/CHF e USD/CHF'],CAD:['BoC','USD/CAD e CAD/JPY'],
   AUD:['RBA','AUD/USD e AUD/CAD'],NZD:['RBNZ','NZD/USD e NZD/JPY']
  };
  const topics={
   INFLATION:'La composizione e la persistenza dei prezzi possono modificare le aspettative sui tassi.',
   LABOUR:'Assunzioni, disoccupazione e salari aiutano a distinguere resilienza della domanda da un rallentamento.',
   LABOUR_COST:'La dinamica del costo del lavoro può incidere sulla persistenza dell’inflazione dei servizi.',
   GROWTH:'La tenuta della crescita conta per la capacità della banca centrale di mantenere la propria politica.',
   CENTRAL_BANK_DECISION:'Conta la differenza fra decisione, comunicazione ufficiale e percorso già incorporato nei tassi.'
  };
  // Accept only issuer-validated categories; no scheduled-calendar-only events,
  // official RSS headline-only narratives or generic unverified market items.
  const sourceOK=x=>{
   if(typeof x.source_url!=='string')return false;
   let url;
   try{url=new URL(x.source_url)}catch(e){return false}
   if(url.protocol!=='https:'||url.username||url.password||url.port)return false;
   if(x.quality==='ISSUER_BLS_HTML_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT')
    return x.ccy==='USD'&&url.hostname==='www.bls.gov'&&url.pathname==='/news.release/cpi.htm';
   if(x.quality==='OFFICIAL_PAGE_FIRST_OBSERVATION_NOT_FIRST_RELEASE_PIT')
    return (x.ccy==='USD'&&url.hostname==='www.bls.gov'&&
        /^\/news\.release\/eci(?:\.nr0)?\.htm$/.test(url.pathname))||
     (x.ccy==='CAD'&&url.hostname==='www150.statcan.gc.ca'&&
        /^\/n1\/daily-quotidien\/261030\/dq261030[a-h]-eng\.htm$/.test(url.pathname));
   if(x.quality==='ISSUER_GDP_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT')
    return (x.ccy==='GBP'&&url.hostname==='www.ons.gov.uk'&&
       url.pathname==='/economy/grossdomesticproductgdp/bulletins/gdpfirstquarterlyestimateuk/julytoseptember2026')||
     (x.ccy==='CHF'&&url.hostname==='www.seco.admin.ch'&&url.pathname==='/en/gdp-flash');
   return false;
  };
  if(!sound(feed)||feed.edition_date!==dayNow()||!validStamp(feed.created_at_utc)
   ||!Array.isArray(news?.items))return '';
  const now=nowUtc===undefined?Date.now():Date.parse(nowUtc);
  if(!Number.isFinite(now))return '';
  const editionClock=Date.parse(feed.created_at_utc);
  const editionDay=Date.parse(feed.edition_date+'T00:00:00Z');
  const entries=news.items.filter(x=>{
   if(x?.category!=='MACRO_OFFICIAL_ACTUAL'||!Object.hasOwn(ccyNames,x.ccy)
    ||!validDay(x.as_of)||!validStamp(x.first_runner_observed_at_utc)
    ||typeof x.title!=='string'||!x.title||typeof x.detail!=='string'||!x.detail
    ||!sourceOK(x))return false;
   const eventClock=Date.parse(x.as_of+'T00:00:00Z');
   const observed=Date.parse(x.first_runner_observed_at_utc);
   const deltaDays=(editionDay-eventClock)/864e5;
   if(deltaDays<0||deltaDays>2||observed>now)return false;
   // An actual captured before a *late* briefing is still eligible if the
   // issuer release is today; the frozen opening text stays unchanged.
   if(x.as_of!==feed.edition_date&&observed<=editionClock)return false;
   const kind=x.event_type||(x.quality==='ISSUER_BLS_HTML_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT'?'INFLATION':null);
   return Object.hasOwn(topics,kind);
  }).sort((a,b)=>b.first_runner_observed_at_utc.localeCompare(a.first_runner_observed_at_utc)).slice(0,3);
  if(!entries.length)return '';
  const parts=entries.map((x,i)=>{
   const [bank,pairs]=ccyNames[x.ccy];
   const kind=x.event_type||(x.quality==='ISSUER_BLS_HTML_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT'?'INFLATION':null);
   const why=topics[kind];
   const link=sourceOK(x)?'<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte ufficiale</a>':'';
   return '<div class="morning-update-row" data-ccy="'+esc(x.ccy)+'" data-event-type="'+esc(kind)+'">'+
    '<h2>'+esc(x.title)+'</h2><p>'+esc(x.detail)+'</p>'+
    '<p><strong>Lettura Forex:</strong> '+esc(why)+' Per la '+esc(bank)+
    ' va verificato se il nuovo dato modifica il pricing relativo, non il solo livello del tasso. '+
    'Controllare '+esc(pairs)+' su date comparabili; non abbiamo una reazione intraday certificata, né un segnale automatico.</p>'+
    '<p>Prima osservazione del runner (UTC): '+esc(x.first_runner_observed_at_utc)+
    ' · '+link+' · Il briefing originale resta invariato.</p></div>';
  });
  return '<aside class="morning-catalyst" data-postrelease="official-g8-macro" aria-label="Aggiornamenti ufficiali dopo il briefing">'+
   '<div class="morning-section-label">NUOVI DATI MACRO UFFICIALI · AGGIORNAMENTO DATATO</div>'+
   parts.join('')+'</aside>';
 }
 window.FXQuantMorningDesk={sound,build,postRelease,fxResearchPulse,currencyDriver,nextFxCatalysts,catalystReading};
})();
