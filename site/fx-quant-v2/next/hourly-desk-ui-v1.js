'use strict';
/* FX Quant Next · source-grounded market desk visual shell.
 * Presentation-only layer: NEVER generates news, alerts, model data or scores.
 * Uses the entire validated free desk feed and keeps source drilldown accessible.
 */
(function(root){
 const SCHEMA='GMFQ_NEXT_FREE_HOURLY_DESK_V1';
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
    'Aggiornamento desk · '+date(asOf);
  const sources=feed.provenance.web_source_urls;
  const news=feed.news.map((n,i)=>{
   if(!n||typeof n.headline!=='string'||typeof n.analysis!=='string'||
      !Array.isArray(n.sources))return null;
   const links=n.sources.filter(x=>uri(x)&&sources.includes(x)).slice(0,3);
   if(!links.length)return null;
   const label=n.kind==='PREVIEW'?'Anteprima':n.kind==='FOLLOW_UP'?'Contesto / follow-up':'Notizia';
   const article='<article class="hourly-desk-story"><div class="hourly-story-top">'+
    '<span class="hourly-story-category">'+safe(n.market_area)+'</span>'+
    '<span class="hourly-story-date">'+safe(date(n.published_date))+'</span></div>'+
    '<span class="hourly-story-kind">'+label+'</span>'+
    '<h3>'+safe(n.headline)+'</h3><p>'+safe(n.analysis)+'</p>'+
    '<div class="hourly-desk-citations">Fonti: '+links.map((u,j)=>
      '<a href="'+safe(u)+'" target="_blank" rel="noopener noreferrer">Fonte '+(j+1)+'</a>'
    ).join(' · ')+'</div></article>';
   const preview='<div class="hourly-evidence-peek-item"><span>'+safe(n.market_area)+
    ' · '+safe(date(n.published_date))+'</span><strong>'+safe(n.headline)+'</strong></div>';
   return {article,preview};
  }).filter(Boolean);
  if(!news.length)return null;
  // Avoid repeating the same lead twice: the full original judgment is
  // retained in the expandable full analysis. The visible continuation is
  // taken VERBATIM from the already-produced market judgment.
  const judgment=feed.desk_judgment.trim(),lead=feed.lead.trim();
  const isContinuation=judgment.startsWith(lead)&&judgment.length>lead.length;
  const followThrough=isContinuation?judgment.slice(lead.length).trim():judgment;
  const research=[
   ['currencies','Valute G8','Confronta le forze relative','G8'],
   ['pairs','Coppie FX','Dalla tesi al timing','FX'],
   ['rates','Tassi & OIS','Leggi cosa prezza il mercato','OIS'],
   ['macro','Scenario macro','Crescita, inflazione e lavoro','MACRO'],
   ['risk','Rischio','Credito, volatilità e cross-asset','RISK'],
   ['news','Calendario e news','Catalizzatori e pubblicazioni','NEWS']
  ].map(([hash,label,desc,mark])=>
    '<a class="hourly-route" href="#'+hash+'"><span class="hourly-route-mark">'+mark+'</span>'+
    '<span class="hourly-route-copy"><strong>'+label+'</strong><small>'+desc+'</small></span>'+
    '<span class="hourly-route-arrow" aria-hidden="true">↗</span></a>').join('');
  return '<article class="market-letter market-dashboard morning-dashboard hourly-market-desk"'+
    ' data-standalone-market-desk="active" aria-label="Panoramica dei mercati globale e Forex">'+
    '<div class="morning-edition-header hourly-edition-bar">'+
    '<span><span class="hourly-brand-mark" aria-hidden="true"></span> FX QUANT / GLOBAL MACRO DESK</span>'+
    '<span>'+safe(vintage)+' · '+safe(feed.edition_time_rome)+' Europe/Rome</span></div>'+
    '<div class="hourly-hero-grid">'+
    '<header class="morning-lead hourly-hero" aria-label="Il quadro generale dei mercati">'+
    '<div class="hourly-hero-upper"><span class="morning-kicker">IL QUADRO GENERALE DEI MERCATI</span>'+
    '<span class="hourly-research-tag">QUADRO &amp; INTERPRETAZIONE</span></div>'+
    '<h1>'+safe(feed.headline)+'</h1>'+
    '<p class="morning-deck">'+safe(feed.lead)+'</p>'+
    '<div class="hourly-hero-bottom"><span>Macro <i></i> Tassi <i></i> Mercati <i></i> Forex</span>'+
    '<a href="#currencies">Esplora le valute <span aria-hidden="true">↗</span></a></div>'+
    '</header>'+
    '<aside class="hourly-fx-spotlight" aria-label="Implicazioni Forex">'+
    '<div class="hourly-spotlight-top"><span class="morning-section-label">LE CONSEGUENZE PER IL FOREX</span>'+
    '<span class="hourly-spotlight-symbol" aria-hidden="true">⇄</span></div>'+
    '<h2>La lettura relativa delle valute</h2>'+
    '<p>'+safe(feed.fx_implications)+'</p>'+
    '<div class="hourly-spotlight-actions"><a href="#pairs">Approfondisci le coppie FX <span aria-hidden="true">↗</span></a>'+
    '<a href="#rates">Esamina i tassi</a></div>'+
    '</aside></div>'+
    '<section class="hourly-decision-section" aria-label="Le tre verifiche del desk">'+
    '<div class="hourly-section-head"><div><span class="morning-section-label">LETTURA DEL DESK</span>'+
    '<h2>La mappa dei driver</h2></div>'+
    '<p>Novità, evidenze contrarie e conferme da seguire. Nessun segnale automatico.</p></div>'+
    '<div class="hourly-decision-grid">'+
    '<article class="hourly-decision-card hourly-decision-change">'+
    '<span class="hourly-decision-overline">CAMBIAMENTO</span>'+
    '<h3>Cosa è cambiato</h3><p>'+safe(feed.what_changed)+'</p>'+
    '</article>'+
    '<article class="hourly-decision-card hourly-decision-contrary">'+
    '<span class="hourly-decision-overline">PROVA CONTRARIA</span>'+
    '<h3>La lettura alternativa.</h3><p>'+safe(feed.contrary_evidence)+'</p>'+
    '</article>'+
    '<article class="hourly-decision-card hourly-decision-watch">'+
    '<span class="hourly-decision-overline">PROSSIMA VERIFICA</span>'+
    '<h3>Da monitorare</h3><p>'+safe(feed.watch)+'</p>'+
    '</article></div></section>'+
    '<section class="hourly-research-lens" aria-label="Analisi economica integrata">'+
    '<div class="hourly-lens-heading"><span class="morning-section-label">COSA STA SUCCEDENDO E PERCHÉ CONTA</span>'+
    '<h2>Dentro il quadro macro</h2></div>'+
    '<div class="hourly-lens-body"><p>'+safe(followThrough)+'</p>'+
    (isContinuation?
     '<details class="hourly-full-analysis"><summary>Lettura completa del desk</summary>'+
     '<p>'+safe(judgment)+'</p></details>':'')+
    '</div></section>'+
    '<section class="hourly-navigation-section" aria-label="Continua l’analisi in FX Quant">'+
    '<div class="hourly-section-head"><div><span class="morning-section-label">DAL QUADRO AI DATI</span>'+
    '<h2>Esplora la ricerca</h2></div><p>Ogni tema della Panoramica ha un approfondimento nel sito.</p></div>'+
    '<nav class="hourly-navigation-grid" aria-label="Approfondisci il quadro generale">'+research+'</nav></section>'+
    '<section class="hourly-evidence-section" aria-label="Notizie e fonti del desk">'+
    '<div class="hourly-section-head"><div><span class="morning-section-label">VERIFICA LE FONTI</span>'+
    '<h2>Le evidenze dietro la lettura</h2></div>'+
    '<p>Pubblicazioni, dati e osservazioni di mercato con le loro date.</p></div>'+
    '<div class="hourly-evidence-peek">'+news.slice(0,3).map(x=>x.preview).join('')+'</div>'+
    '<details class="morning-deep-reading hourly-desk-news" id="hourly-desk-news">'+
    '<summary><strong>Notizie e fonti di questa edizione</strong>'+
    '<span>'+news.length+' approfondimenti · apri il dossier <span aria-hidden="true">⌄</span></span></summary>'+
    '<div class="hourly-desk-news-body">'+news.map(x=>x.article).join('')+'</div></details></section>'+
    '<footer class="morning-source-notes hourly-method-note"><p>Ultima analisi pubblicata: '+
    safe(feed.edition_time_rome)+' (Europe/Rome). Metodo: confronto di dati datati, fonti ufficiali e proxy dichiarati. '+
    'I dati storici non sono movimenti intraday e l’interpretazione non costituisce un segnale di ingresso.</p>'+
    '</footer></article>';
 }
 root.FXQuantHourlyDesk={render,SCHEMA};
})(typeof window!=='undefined'?window:globalThis);
