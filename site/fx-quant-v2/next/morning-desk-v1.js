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
 function build({feed,plot,esc,date,dayNow}){
  if(!sound(feed)||feed.edition_date>dayNow())return null;
  const current=feed.edition_date===dayNow();
  const title=esc(feed.headline);
  const text=x=>esc(String(x||''));
  const safePair=typeof feed.pair==='string'&&/^[A-Z]{6}$/.test(feed.pair)?feed.pair:null;
  const sources=feed.sources||{};
  const note=!current?'Questa è l’ultima edizione archiviata, non il briefing di oggi. Il motore non ha ancora pubblicato una nuova lettura.':
   feed.edition_status==='LATE_MORNING_SNAPSHOT'?'Edizione pubblicata dopo l’orario previsto: il ritardo non viene nascosto.':
   feed.edition_status==='RECONSTRUCTION_NOT_POINT_IN_TIME'?
    'Anteprima ricostruita dalle osservazioni disponibili prima della data, non certificata come fotografia point-in-time delle 08:00.':
    'Edizione mattutina congelata: gli eventi pubblicati dopo l’apertura non modificano questo testo.';
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
  const fxMeaning=usdCompatible?
   'In quel periodo tassi relativi e cambio sono andati nella direzione compatibile con un USD più sostenuto contro EUR. Non dimostra chi abbia mosso il prezzo e non certifica la seduta di oggi.':
   comparable&&relative.alignment==='COERENTE'?
    'I due movimenti sono coerenti nell’intervallo confrontato, ma la coincidenza non dimostra una causa e non è un segnale operativo.':
    'Non abbiamo una conferma univoca tra tassi relativi e prezzo: la tesi Forex resta da verificare, senza forzare una direzione.';
  const missing=feed.event_status==='AFTERMATH_UNVERIFIED'?
   'L’effetto dell’evento macro non è ancora verificato: servono dati ufficiali, sorpresa rispetto alle attese, variazioni OIS/futures confrontabili e reazione FX sulle stesse date.':
   'Prima di confermare la tesi servono dati e prezzi confrontabili nel tempo, soprattutto le aspettative sui tassi e la risposta delle singole coppie.';
  const firstRead='<section class="morning-first-read" aria-label="Lettura immediata del mercato">'+
   '<div class="morning-section-label">IL QUADRO IN BREVE · PRIMA IL SIGNIFICATO</div>'+
   '<div class="morning-first-read-grid">'+
   '<div class="morning-first-item"><span>01 / COSA È CAMBIATO</span><p>'+text(alignedEvidence)+'</p></div>'+
   '<div class="morning-first-item"><span>02 / CHE COSA SIGNIFICA PER IL FOREX</span><p>'+text(fxMeaning)+'</p></div>'+
   '<div class="morning-first-item"><span>03 / COSA MANCA PER CONFERMARE</span><p>'+text(missing)+'</p></div>'+
   '</div><p class="morning-first-watch"><strong>Da controllare.</strong> '+
   text(feed.watch)+'</p>'+
   '<div class="morning-first-links"><a href="#pairs">Apri le 28 coppie FX</a><a href="#rates">Verifica Tassi &amp; OIS</a></div>'+
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
  return '<article class="market-letter market-dashboard morning-dashboard" aria-label="Morning Macro e Forex Research Desk">'+
   '<div class="morning-edition-header"><span>FX QUANT / MORNING MACRO & FX RESEARCH DESK</span>'+
   '<span>Edizione '+date(feed.edition_date)+' · Fixing '+date(sources.fx_fixing)+
   ' · Tassi '+date(sources.rates)+'</span></div>'+
   '<div class="morning-archive-note'+(current?' current':'')+'">'+text(note)+'</div>'+
   '<header class="morning-lead"><span class="morning-kicker">IL TEMA MACRO DELLA GIORNATA</span>'+
   '<h1>'+title+'</h1><p class="morning-deck">'+text(feed.lead)+'</p>'+
   '<div class="morning-edition-tags"><span>Macro → aspettative → Forex</span><span>Eventi datati</span>'+
   '<span>Osservazioni pre-apertura</span></div></header>'+
   firstRead+
   '<section class="morning-prose" aria-label="Ragionamento macro completo">'+
   '<details class="morning-deep-reading"><summary><strong>Leggi il ragionamento completo</strong>'+
   '<span>Contesto macro, tassi, prezzo e limiti delle evidenze</span></summary>'+
   '<div class="morning-deep-body">'+
   '<div class="morning-section-label">DA DOVE ARRIVIAMO · COSA PUÒ CAMBIARE OGGI</div>'+
   paragraphs+'</div></details></section>'+
   '<aside class="morning-catalyst"><div class="morning-section-label">IL CATALIZZATORE</div>'+
   '<h2>'+text(feed.catalyst?.title)+'</h2><p>'+text(feed.watch)+'</p></aside>'+
   '<p class="morning-time-note">Il briefing non viene riscritto retroattivamente dopo la pubblicazione dei dati. Eventuali aggiornamenti post-evento devono avere un orario e fonti propri.</p>'+
   '<section class="morning-evidence"><div class="morning-section-label">LE EVIDENZE CHE SOSTENGONO LA LETTURA</div>'+
   '<h2>Due grafici, una sola domanda: il prezzo conferma la tesi?</h2>'+
   '<p class="morning-subtitle">Selezionati in base al catalizzatore macro, non ripetuti automaticamente per tutte le giornate.</p>'+
   '<div class="morning-chart-grid">'+feed.charts.map(renderChart).join('')+'</div></section>'+
   '<section class="morning-outlook"><div class="morning-section-label">COSA POTREBBE CAMBIARE LA TESI</div>'+
   '<h2>Scenari alternativi da verificare</h2><div class="morning-scenario-grid">'+scenarios+'</div>'+
   '<aside class="morning-judgment"><strong>Giudizio del desk</strong><p>'+text(feed.verdict)+'</p></aside></section>'+
   '<nav class="morning-research-links" aria-label="Approfondimenti nel Research Desk">'+
   '<a href="#macro">Scenario Macro</a><a href="#rates">Tassi & OIS</a>'+
   '<a href="#currencies">Valute G8</a><a href="#pairs">28 coppie FX</a>'+
   '<a href="#cot">Posizionamento COT</a><a href="#news">Notizie & Calendario</a></nav>'+
   '<footer class="morning-source-notes"><p>Fonte fixing: BCE al '+date(sources.fx_fixing)+
   ' · Differenziali: governativi G8 al '+date(sources.rates)+
   ' · Calendario: fonti ufficiali. '+text((feed.limitations||[]).join(' '))+'</p>'+
   '<p>Edizione '+text(feed.edition_status)+' · Lettura basata su regole ed evidenze datate, non un giudizio editoriale umano verificato. Nessun segnale o variazione del motore delle 28 coppie.</p></footer>'+
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
 window.FXQuantMorningDesk={sound,build,postRelease};
})();
