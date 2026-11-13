'use strict';
/* Operational macro calendar. An official release schedule is not an event
 * surprise or a measured FX reaction. No future event is presented as observed.
 */
(function(root){
 const G8=new Set(['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']);
 const validDate=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&Number.isFinite(Date.parse(x+'T12:00:00Z'));
 const validTime=x=>typeof x==='string'&&/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(x);
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
 const fmtDay=x=>validDate(x)?x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):'n.d.';
 const romeNow=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const italianTitles={'Producer Price Index':'USA · prezzi alla produzione (PPI)',
  'Swiss GDP flash':'Svizzera · PIL flash',
  'U.S. Import and Export Price Indexes':'USA · prezzi import/export',
  'Labour Force, Australia':'Australia · mercato del lavoro',
  'Japan Consumer Price Index':'Giappone · indice dei prezzi al consumo',
  'Gross domestic product':'Prodotto interno lordo (PIL)'};
 const displayTitle=t=>italianTitles[t]||t;
 const pairMap={USD:'EUR/USD · USD/JPY',EUR:'EUR/USD · EUR/GBP',GBP:'EUR/GBP · GBP/USD',
 JPY:'USD/JPY · EUR/JPY',CHF:'EUR/CHF · USD/CHF',CAD:'USD/CAD · CAD/JPY',
 AUD:'AUD/USD · AUD/NZD',NZD:'NZD/USD · AUD/NZD'};
 const country={USD:'Stati Uniti',EUR:'Eurozona',GBP:'Regno Unito',JPY:'Giappone',
 CHF:'Svizzera',CAD:'Canada',AUD:'Australia',NZD:'Nuova Zelanda'};
 function wall(utcMs,zone){
  const p=new Intl.DateTimeFormat('en-GB',{timeZone:zone,year:'numeric',month:'2-digit',
   day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(utcMs));
  const z=Object.fromEntries(p.filter(v=>v.type!=='literal').map(v=>[v.type,+v.value]));
  return {y:z.year,m:z.month,d:z.day,h:z.hour,min:z.minute};
 }
 const epoch=z=>Date.UTC(z.y,z.m-1,z.d,z.h,z.min);
 function toRome(date,time,zone){
  if(!validDate(date)||!validTime(time)||typeof zone!=='string')return null;
  try{
   const [y,m,d]=date.split('-').map(Number),[h,min]=time.split(':').map(Number);
   const target={y,m,d,h,min},wallTime=epoch(target);
   let utc=wallTime;
   for(let i=0;i<4;i++){
    const own=wall(utc,zone);
    const next=utc+(wallTime-epoch(own));
    if(next===utc)break;
    utc=next;
   }
   const original=wall(utc,zone);
   if(epoch(original)!==wallTime)return null; // DST gap or unsupported local time
   const it=wall(utc,'Europe/Rome');
   return {date:String(it.y).padStart(4,'0')+'-'+String(it.m).padStart(2,'0')+'-'+String(it.d).padStart(2,'0'),
    time:String(it.h).padStart(2,'0')+':'+String(it.min).padStart(2,'0'),timestamp:utc};
  }catch(_){return null;}
 }
 const number=x=>typeof x==='number'&&Number.isFinite(x);
 const checkedRome=x=>{
  const ms=typeof x==='string'?Date.parse(x):NaN;
  if(!Number.isFinite(ms))return null;
  const dt=new Date(ms),day=new Intl.DateTimeFormat('sv-SE',{
   timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(dt);
  const time=new Intl.DateTimeFormat('it-IT',{
   timeZone:'Europe/Rome',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(dt);
  return {day,time};
 };

 function verifiedValue(e,key){
  // Upstream must explicitly attest vintage and provenance; mere raw values
  // from an unversioned calendar are never treated as observed/consensus.
  if(key==='consensus'){
   return e.consensus_status==='VERIFIED'&&number(e.consensus)&&
    typeof e.consensus_source==='string'&&e.consensus_source.length>=2&&
    typeof e.consensus_observed_at_utc==='string'&&number(Date.parse(e.consensus_observed_at_utc))?e.consensus:null;
  }
  if(key==='actual'){
   return e.status==='RELEASED'&&e.actual_status==='OFFICIAL_VERIFIED'&&number(e.actual)&&
    typeof e.actual_first_observed_at_utc==='string'&&number(Date.parse(e.actual_first_observed_at_utc))?e.actual:null;
  }
  return null;
 }
 function why(e){
  const code=e.ccy;
  if(e.event_type==='CENTRAL_BANK_DECISION')
   return 'La decisione e soprattutto la comunicazione potrebbero modificare il percorso dei tassi atteso. Confrontare il comunicato con OIS/futures della stessa valuta, non soltanto con il livello attuale del tasso.';
  if(e.event_type==='GROWTH'){
   if(code==='GBP')return 'La crescita britannica può cambiare le aspettative sulla Bank of England. Il dato va confrontato con consumi, salari e differenziale dei tassi UK rispetto ai partner.';
   if(code==='CHF')return 'La crescita svizzera può influenzare la lettura della SNB, ma EUR/CHF dipende anche dalla domanda di franco come valuta difensiva.';
   return 'La crescita può modificare il percorso atteso della banca centrale: serve il confronto con i partner e con il pricing dei tassi.';
  }
  if(e.event_type==='LABOUR')return 'Occupazione, disoccupazione e composizione dei salari possono influenzare il percorso dei tassi. Un dato positivo non garantisce forza della valuta se già atteso.';
  if(e.event_type==='INFLATION')return 'Contano soprattutto componenti, persistenza e sorpresa rispetto alle attese. Verificare il repricing della banca centrale e il differenziale con le altre economie.';
  return 'Monitorare le aspettative della banca centrale e la forza relativa della valuta, non dedurre un trade dalla sola pubblicazione.';
 }
 function verify(e){
  const code=e.ccy;
  const pricing=e.event_type==='CENTRAL_BANK_DECISION'?'OIS/futures, 2Y e comunicato':'attese sui tassi, 2Y e revisioni';
  return 'Dopo l’evento: verificare '+pricing+' · prezzo '+(pairMap[code]||'FX G8')+
   ' · reazione su una finestra comparabile. Nessuna direzione è implicita prima dei dati.';
 }
 function parse(feed,today=romeNow(),nowMs=Date.now()){
  const empty={events:[],needsReview:[],total:0,macro:0,meetings:0,asof:null,
   consensusReady:0,status:'NON DISPONIBILE'};
  if(!validDate(today)||!feed||typeof feed!=='object'||!Array.isArray(feed.events))return empty;
  const current=number(nowMs)?nowMs:Date.now();
  const future=[],needsReview=[];
  for(const [i,e] of feed.events.entries()){
   if(!e||e.status!=='UPCOMING'||!validDate(e.date)||e.date<today||!G8.has(e.ccy)||
      typeof e.title!=='string'||!e.title.trim())continue;
   const it=toRome(e.date,e.time_local,e.timezone);
   const consensus=verifiedValue(e,'consensus'),actual=verifiedValue(e,'actual');
   const result={id:i,ccy:e.ccy,country:country[e.ccy],title:e.title,date:e.date,
     day:it?.date||e.date,romeTime:it?.time||null,
     sourceTime:validTime(e.time_local)?e.time_local:null,
     timezone:e.timezone||null,importance:e.importance||'NON CLASSIFICATA',
     kind:e.event_type==='CENTRAL_BANK_DECISION'?'Riunione banca centrale':'Pubblicazione macro',
     source:e.source_family||e.bank||e.source_layer||'Fonte non specificata',
     quality:e.quality||'non classificata',consensus,actual,reference:e.reference_period||null,
     why:why(e),verify:verify(e),pairs:pairMap[e.ccy]||'',timestamp:it?.timestamp||null};
   // An upstream UPCOMING flag may lag the announced publication time.
   // Never imply an already-scheduled release is still in the future or
   // pretend the result exists without a verified source and vintage.
   if(result.day===today&&result.timestamp===null){
    result.reviewReason='ORARIO_NON_VERIFICATO';needsReview.push(result);
   }else if(result.day<today||(result.timestamp!==null&&result.timestamp<=current)){
    result.reviewReason='ORARIO_PROGRAMMATO_TRASCORSO';needsReview.push(result);
   }else future.push(result);
  }
  const sort=(a,b)=>a.day.localeCompare(b.day)||
   (a.romeTime||'99:99').localeCompare(b.romeTime||'99:99')||
    a.title.localeCompare(b.title);
  future.sort(sort);needsReview.sort(sort);
  const all=[...future,...needsReview];
  return {events:future,needsReview,total:all.length,
   macro:all.filter(x=>x.kind==='Pubblicazione macro').length,
   meetings:all.filter(x=>x.kind==='Riunione banca centrale').length,
   asof:typeof feed.last_checked_at_utc==='string'?feed.last_checked_at_utc:null,
   consensusReady:all.filter(x=>x.consensus!==null).length,
   status:all.length?'AGENDA UFFICIALE · DATI DA VERIFICARE':'NESSUN EVENTO FUTURO VERIFICATO'};
 }
 function card(e,review=false){
  const timeText=e.romeTime?' · '+esc(e.romeTime)+' IT':' · ora non disponibile';
  const waiting=review?(e.reviewReason==='ORARIO_NON_VERIFICATO'?
   'Data odierna; ora non verificata. Controllare la fonte prima di considerare il dato pubblicato.':
   'Orario programmato trascorso. Il feed non ha ancora verificato il risultato: non è una sorpresa macro osservata.'):'';
  // The first pair is one research example, not a recommended FX trade.
  const pair=String(e.pairs||'').split(' · ')[0];
  const pairCode=pair.replace('/','');
  return '<article class="cal-event'+(review?' cal-event-review':'')+'"><div class="cal-event-head"><span>'+
   esc(e.ccy)+' · '+esc(e.kind)+'</span><time datetime="'+esc(e.day)+'">'+fmtDay(e.day)+timeText+'</time></div>'+
   '<h3>'+esc(displayTitle(e.title))+'</h3>'+
   (review?'<p class="cal-review-state"><strong>Da verificare.</strong> '+esc(waiting)+'</p>':'')+
   '<p class="cal-driver-reading"><strong>Perché conta.</strong> '+esc(e.why)+'</p>'+
   '<div class="cal-event-path" aria-label="Percorso di ricerca: aspettative, valuta e coppia">'+
   '<span class="cal-event-path-label">DALL’EVENTO ALLA VERIFICA FX</span>'+
   '<div class="cal-event-actions">'+
   '<a href="#rates" data-cal-research="rates" data-cal-currency="'+esc(e.ccy)+'" aria-label="Controlla tassi e OIS per '+esc(e.ccy)+'">Tassi &amp; OIS <span aria-hidden="true">↗</span></a>'+
   '<a href="#currencies" data-cal-research="currencies" data-cal-currency="'+esc(e.ccy)+'" aria-label="Analizza la valuta '+esc(e.ccy)+'">Valuta '+esc(e.ccy)+' <span aria-hidden="true">↗</span></a>'+
   '<a href="#pairs" data-cal-research="pairs" data-cal-currency="'+esc(e.ccy)+'" data-cal-pair="'+esc(pairCode)+'" aria-label="Analizza la coppia '+esc(pair)+' senza segnale di ingresso">'+esc(pair)+' <span aria-hidden="true">↗</span></a>'+
   '</div></div>'+
   '<details class="cal-event-evidence"><summary>Fonte, consenso e verifiche dopo l’evento</summary><div class="cal-event-evidence-body">'+
   '<p class="cal-source">Fonte: '+esc(e.source)+' · '+esc(e.quality)+
   (e.reference?' · Periodo '+esc(e.reference):'')+'</p>'+
   (displayTitle(e.title)!==e.title?'<p class="cal-source">Titolo originale: '+esc(e.title)+'</p>':'')+
   '<p class="cal-verify"><strong>Cosa controllare.</strong> '+esc(e.verify)+'</p>'+
   '<div class="cal-missing">Consenso: '+(e.consensus===null?'non certificato':esc(e.consensus))+
   ' · Effettivo: '+(e.actual===null?(review?'non verificato dal feed':'non ancora pubblicato/verificato'):esc(e.actual))+'</div>'+
   '</div></details></article>';
 }
 function render(feed,today=romeNow(),nowMs=Date.now()){
  const p=parse(feed,today,nowMs);
  const last=checkedRome(p.asof);
  const head='<section class="panel cal-panel" id="macro-calendar"><div class="panel-head"><div>'+
   '<span class="mini-overline">AGENDA OPERATIVA / EVENTI G8</span><h2>Quali dati potrebbero cambiare le tesi FX?</h2>'+
   '<p>'+p.events.length+' eventi futuri · '+p.needsReview.length+' eventi odierni da verificare'+
   (last?' · controllo '+esc(fmtDay(last.day))+' '+esc(last.time)+' IT':'')+'</p></div></div>';
  if(!p.total)return head+
   '<div class="empty"><strong>Calendario non disponibile o senza eventi futuri verificati.</strong><p>Non mostriamo date e orari presunti.</p></div></section>';
  const currentCheck=last&&last.day<today?
   '<p class="cal-feed-warning"><strong>Feed non ricontrollato oggi.</strong> Ultima verifica '+
   esc(fmtDay(last.day))+' '+esc(last.time)+' IT. Le pubblicazioni e i risultati odierni richiedono un riscontro alla fonte.</p>':'';
  const reviews=p.needsReview.length?
   '<section class="cal-review-group"><h3>Oggi · risultato ancora da verificare</h3>'+
   '<p>È trascorso l’orario programmato oppure manca un’ora attendibile. Non lo trattiamo come evento futuro, né come dato già verificato.</p>'+
   '<div class="cal-grid">'+p.needsReview.map(e=>card(e,true)).join('')+'</div></section>':'';
  const first=p.events.slice(0,4),more=p.events.slice(4);
  const upcoming=p.events.length?
   '<section class="cal-upcoming-group"><h3>Prossimi eventi</h3>'+
   '<div class="cal-grid">'+first.map(e=>card(e)).join('')+'</div>'+
   (more.length?'<details class="cal-more"><summary>Altri '+more.length+' eventi del calendario</summary><div class="cal-grid">'+more.map(e=>card(e)).join('')+'</div></details>':'')+
   '</section>':'';
  return head+'<p class="cal-intro">Ogni evento è un possibile catalizzatore, non un segnale: apri pricing, valuta e coppia per cercare conferme. Dopo l’orario previsto, esito e reazione restano da verificare.</p>'+
   currentCheck+reviews+upcoming+
   '<div class="cal-coverage"><strong>Limite dei dati:</strong> consenso numerico certificato per '+p.consensusReady+
   ' eventi su '+p.total+'. Senza confronto pre-release/effettivo non calcoliamo sorprese e non attribuiamo movimenti del Forex. L’orario italiano è mostrato solo dove la fonte indica un’ora convertibile.</div></section>';
 }
 const api={parse,render,toRome,reportType:null,verifiedValue};
 root.FXQuantMacroCalendar=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
