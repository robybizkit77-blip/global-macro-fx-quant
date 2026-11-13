'use strict';
/* FX Quant Next — editorial display of an INDEPENDENT GitHub AI market desk.
 * Never generates alerts, never talks to ChatGPT Automations.
 * If the source is absent/invalid the canonical existing Panoramica remains.
 */
(function(root){
 const SCHEMA='GMFQ_NEXT_INDEPENDENT_HOURLY_AI_DESK_V1';
 const goodDay=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s);
 const uri=x=>typeof x==='string'&&/^https:\/\/[^/\s@]+\.[^/\s@]+(?:\/[^\s]*)?$/.test(x);
 function render({feed,esc,date,dayNow}={}){
  if(feed?.schema!==SCHEMA||feed.status!=='ACTIVE'||typeof esc!=='function'||
     !goodDay(feed.generated_at_utc?.slice(0,10))||!goodDay(dayNow?.())||
     feed.generated_at_utc.slice(0,10)>dayNow()||
     !Array.isArray(feed.news)||!feed.news.length||feed.news.length>6||
     !Array.isArray(feed.provenance?.web_source_urls)||
     feed.provenance.web_source_urls.length===0||
     ['headline','lead','desk_judgment','fx_implications','what_changed',
      'contrary_evidence','watch'].some(k=>typeof feed[k]!=='string'||!feed[k].trim()))return null;
  const safe=x=>esc(String(x??''));
  const today=dayNow(),asOf=feed.generated_at_utc.slice(0,10);
  const days=Math.floor((Date.parse(today+'T12:00:00Z')-Date.parse(asOf+'T12:00:00Z'))/86400000);
  if(days<0||days>14)return null;
  const vintage=days>1?'Ultima edizione conservata · '+date(asOf):
    'Aggiornamento desk indipendente · '+date(asOf);
  const sources=feed.provenance.web_source_urls;
  const news=feed.news.map((n,i)=>{
   if(!n||typeof n.headline!=='string'||typeof n.analysis!=='string'||
      !Array.isArray(n.sources))return '';
   const links=n.sources.filter(x=>uri(x)&&sources.includes(x)).slice(0,3);
   if(!links.length)return '';
   const label=n.kind==='PREVIEW'?'Anteprima':n.kind==='FOLLOW_UP'?'Contesto / follow-up':'Notizia';
   return '<article class="hourly-desk-story"><span class="morning-section-label">'+
    label+' · '+safe(n.market_area)+' · '+safe(date(n.published_date))+'</span>'+
    '<h3>'+safe(n.headline)+'</h3><p>'+safe(n.analysis)+'</p>'+
    '<div class="hourly-desk-citations">Fonti: '+links.map((u,j)=>
      '<a href="'+safe(u)+'" target="_blank" rel="noopener noreferrer">Fonte '+(j+1)+'</a>'
    ).join(' · ')+'</div></article>';
  }).filter(Boolean);
  if(!news.length)return null;
  return '<article class="market-letter market-dashboard morning-dashboard hourly-market-desk"'+
    ' data-standalone-market-desk="active" aria-label="Panoramica dei mercati globale e Forex">'+
    '<div class="morning-edition-header"><span>FX QUANT / GLOBAL MACRO RESEARCH DESK</span>'+
    '<span>'+safe(vintage)+' · '+safe(feed.edition_time_rome)+' Europe/Rome</span></div>'+
    '<header class="morning-lead"><span class="morning-kicker">IL QUADRO GENERALE DEI MERCATI</span>'+
    '<h1>'+safe(feed.headline)+'</h1><p class="morning-deck">'+safe(feed.lead)+'</p>'+
    '<div class="morning-edition-tags"><span>Macro · FX · Cross-Asset</span>'+
    '<span>Ricerca AI · fonti collegate</span><span>Edizione effettiva '+safe(feed.edition_time_rome)+'</span></div>'+
    '</header>'+
    '<section class="morning-first-read" aria-label="Giudizio del desk sui mercati">'+
    '<div class="morning-section-label">COSA STA SUCCEDENDO E PERCHÉ CONTA</div>'+
    '<p class="morning-key-meaning">'+safe(feed.desk_judgment)+'</p>'+
    '<div class="morning-section-label">LE CONSEGUENZE PER IL FOREX</div>'+
    '<p class="morning-key-meaning">'+safe(feed.fx_implications)+'</p></section>'+
    '<aside class="morning-catalyst"><div class="morning-section-label">COSA È CAMBIATO</div>'+
    '<p>'+safe(feed.what_changed)+'</p></aside>'+
    '<section class="hourly-desk-check" aria-label="Prove contrarie e prossima verifica">'+
    '<p><strong>La lettura alternativa.</strong> '+safe(feed.contrary_evidence)+'</p>'+
    '<p><strong>Da monitorare.</strong> '+safe(feed.watch)+'</p></section>'+
    '<details class="morning-deep-reading hourly-desk-news">'+
    '<summary><strong>Notizie e fonti di questa edizione</strong>'+
    '<span>'+news.length+' sviluppi · notizie, contesto e anteprime distinti</span></summary>'+
    '<div class="hourly-desk-news-body">'+news.join('')+'</div></details>'+
    '<nav class="morning-research-links" aria-label="Approfondisci il quadro generale">'+
    '<a href="#currencies">Valute G8</a><a href="#pairs">Coppie FX</a>'+
    '<a href="#macro">Macro</a><a href="#rates">Tassi &amp; OIS</a>'+
    '<a href="#risk">Rischio</a><a href="#news">Calendario / News</a></nav>'+
    '<footer class="morning-source-notes"><p>Ultima analisi pubblicata: '+
    safe(feed.edition_time_rome)+' (Europe/Rome). Fonti e date consultabili nelle notizie. '+
    'I dati storici e i proxy non sono movimenti intraday, le interpretazioni non sono segnali di ingresso.</p>'+
    '</footer></article>';
 }
 root.FXQuantHourlyDesk={render,SCHEMA};
})(typeof window!=='undefined'?window:globalThis);
