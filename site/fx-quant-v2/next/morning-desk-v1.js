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
   '<section class="morning-prose" aria-label="La lettura del desk">'+
   '<div class="morning-section-label">DA DOVE ARRIVIAMO · COSA PUÒ CAMBIARE OGGI</div>'+
   paragraphs+'</section>'+
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
 window.FXQuantMorningDesk={sound,build};
})();
