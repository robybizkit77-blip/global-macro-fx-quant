'use strict';
/* FX Quant Next · source-grounded market desk visual shell.
 * Presentation-only layer: NEVER generates news, alerts, model data or scores.
 * Uses the entire validated free desk feed and keeps source drilldown accessible.
 */
(function(root){
 const SCHEMA='GMFQ_NEXT_FREE_HOURLY_DESK_V1';
 const goodDay=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s);
 const uri=x=>typeof x==='string'&&/^https:\/\/[^/\s@]+\.[^/\s@]+(?:\/[^\s]*)?$/.test(x);

 // Source titles remain unchanged in JSON; this display-only Italian label
 // never claims to translate an unseen article or infer a policy decision.
 const englishTitle=s=>{
  const title=String(s||'');
  if(/\b(the|and|this|summer|fell|record lows|hydropower|generation|electricity|published|releases?|released|energy study|outlook for|business outlook|survey of|monetary policy|financial stability|project meridian|oil production|crude oil|natural gas|supply outlook|energy consumption)\b/i.test(title))return true;
  const words=title.toLowerCase().match(/[a-z]+/g)||[];
  const english=new Set(['bank','of','reports','report','news','minutes','new','latest','consumer','consumers','spending','survey','financial','markets','market','oil','gas','energy','demand','supply','low','lows','record','higher','lower','prices','growth','increase','increased','decrease','decreased','rose','rising','falls','falling','today','for','from','with','released','launches','announces','outlook','production','electricity','electric','economic','activity']);
  const italian=new Set(['la','il','lo','gli','le','della','delle','del','dei','su','sul','sui','per','con','tra','cresce','scende','sale','aumenta','diminuisce','produzione','prezzi','tassi','mercati','indagine','rilevazione','banca','dollaro','energia','riserva']);
  const en=words.filter(w=>english.has(w)).length,it=words.filter(w=>italian.has(w)).length;
  return en>=2&&en>it;
 };
 const titleItaliano=n=>{
  const original=String(n?.headline||'').trim();
  const isRss=['ENERGIA','BANCHE CENTRALI'].includes(String(n?.market_area||'').toUpperCase());
  const clearlyItalian=/\b(il|lo|la|gli|le|della|delle|del|dei|sul|sui|per|con|tra|banca|produzione|prezzi|tassi|indagine|decisione|mercato|scorte|energia|crescita|dollaro)\b/i.test(original);
  if(!englishTitle(original)&&(!isRss||clearlyItalian))return original;
  if(/hydropower generation/i.test(original)&&/southwest/i.test(original)&&/record lows/i.test(original))
   return 'Produzione idroelettrica nel Sud-Ovest USA scesa ai minimi storici durante l’estate';
  if(/project meridian fx apac/i.test(original))
   return 'Progetto Meridian FX APAC: collaborazione tra le autorità monetarie di Regno Unito, Singapore e Thailandia';
  const source=(n.sources||[]).find(uri)||'';
  const institute=/eia\.gov/i.test(source)?'EIA':
   /bankofengland\.co\.uk/i.test(source)?'Banca d’Inghilterra':
   /federalreserve\.gov/i.test(source)?'Federal Reserve':
   /ecb\.europa\.eu/i.test(source)?'BCE':
   /bankofcanada\.ca/i.test(source)?'Banca del Canada':
   /boj\.or\.jp/i.test(source)?'Banca del Giappone':
   /rba\.gov\.au/i.test(source)?'Banca centrale australiana':
   /rbnz\.govt\.nz/i.test(source)?'Banca centrale neozelandese':
   /snb\.ch/i.test(source)?'Banca nazionale svizzera':'Fonte ufficiale';
  const area=String(n.market_area||'').toUpperCase();
  const topic=/hydropower|electricity|power generation|wind power|solar power/i.test(original)?
   'produzione di energia elettrica':
   /crude oil|petroleum|refining|gasoline|diesel|oil inventories/i.test(original)?
   'petrolio, raffinazione e scorte':
   /natural gas/i.test(original)?'mercato del gas naturale':
   /inflation|consumer prices/i.test(original)?'inflazione e prezzi':
   /monetary policy|policy rate|interest rates?|bank rate/i.test(original)?
   'politica monetaria':
   /financial stability/i.test(original)?'stabilità finanziaria':
   /outlook|forecast|projections/i.test(original)?'prospettive economiche':
   /survey|confidence/i.test(original)?'indagini e aspettative':
   area==='ENERGIA'?'mercato energetico':
   area==='BANCHE CENTRALI'?'attività della banca centrale':
   'mercati e politica economica';
  return institute+': pubblicazione su '+topic;
 };
 const sourceHost=u=>((String(u||'').match(/^https:\/\/([^/?#:]+)/i)||[])[1]||'').replace(/^www\./,'');
 const areaIt=s=>({'COMMODITIES':'MATERIE PRIME','ENERGY':'ENERGIA','EQUITIES':'AZIONI','FOLLOW_UP':'APPROFONDIMENTO'}[String(s||'').toUpperCase()]||String(s||''));
 // Event delegation also works after the SPA re-renders the Home.
 function openSources(target,storyId){
  const desk=target?.closest?.('.hourly-market-desk');
  const dossier=desk?.querySelector?.('details#hourly-desk-news');
  if(!dossier)return false;
  dossier.open=true;
  desk.querySelectorAll?.('[data-hourly-open-sources]')?.forEach?.(b=>b.setAttribute('aria-expanded','true'));
  const article=typeof storyId==='string'&&/^\d+$/.test(storyId)?
   dossier.querySelector?.('[data-hourly-article="'+storyId+'"]'):null;
  const destination=article||dossier;
  destination.scrollIntoView?.({behavior:root.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches?'auto':'smooth',block:'start'});
  (article||dossier.querySelector?.('summary'))?.focus?.({preventScroll:true});
  return true;
 }
 if(root.document?.addEventListener){
  root.document.addEventListener('click',e=>{
   const target=e.target;
   const teaser=target?.closest?.('[data-hourly-story-link]');
   if(teaser){openSources(teaser,teaser.getAttribute('data-hourly-story-link'));return;}
   const button=target?.closest?.('[data-hourly-open-sources]');
   if(button){openSources(button);return;}
   const hero=target?.closest?.('.hourly-hero[data-hourly-hero-to-sources]');
   if(hero&&!target?.closest?.('a,button,summary'))openSources(hero);
  });
 }

 function render({feed,risk,currencyPrices,esc,date,dayNow}={}){
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
   const label=n.kind==='PREVIEW'?'Anteprima':n.kind==='FOLLOW_UP'?'Approfondimento':'Notizia';
   const headlineIt=titleItaliano(n),area=areaIt(n.market_area);
   const article='<article class="hourly-desk-story" data-hourly-article="'+i+'" tabindex="-1"><div class="hourly-story-top">'+
    '<span class="hourly-story-category">'+safe(area)+'</span>'+
    '<span class="hourly-story-date">'+safe(date(n.published_date))+'</span></div>'+
    '<span class="hourly-story-kind">'+label+'</span>'+
    '<h3>'+safe(headlineIt)+'</h3><p>'+safe(n.analysis)+'</p>'+
    '<div class="hourly-desk-citations">Fonti: '+links.map((u,j)=>
      '<a href="'+safe(u)+'" target="_blank" rel="noopener noreferrer" aria-label="Apri la fonte originale '+safe(sourceHost(u))+'">'+safe(sourceHost(u))+' <span aria-hidden="true">↗</span></a>'
    ).join(' · ')+'</div></article>';
   const preview='<button type="button" class="hourly-evidence-peek-item" data-hourly-story-link="'+i+'"'+
    ' aria-controls="hourly-desk-news" aria-label="Apri la notizia: '+safe(headlineIt)+'">'+
    '<span>'+safe(area)+' · '+safe(date(n.published_date))+'</span>'+ 
    '<strong>'+safe(headlineIt)+'</strong>'+ 
    '<small>Leggi l’approfondimento <em aria-hidden="true">↘</em></small></button>';
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
   ['pairs','Coppie FX','Dalla tesi al momento d’ingresso','FX'],
   ['rates','Tassi & OIS','Leggi cosa prezza il mercato','OIS'],
   ['macro','Scenario macro','Crescita, inflazione e lavoro','MACRO'],
   ['risk','Rischio','Credito, volatilità e mercati','RIS'],
   ['news','Notizie e calendario','Catalizzatori e pubblicazioni','FONTI']
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
    '<header class="morning-lead hourly-hero" data-hourly-hero-to-sources="true" aria-label="Il quadro generale dei mercati: clicca per aprire notizie e fonti">'+
    '<div class="hourly-hero-upper"><button type="button" class="morning-kicker hourly-kicker-sources" data-hourly-open-sources aria-controls="hourly-desk-news" aria-expanded="false">IL QUADRO GENERALE DEI MERCATI <span aria-hidden="true">↘</span></button>'+
    '<span class="hourly-research-tag">QUADRO &amp; INTERPRETAZIONE</span></div>'+
    '<h1>'+safe(feed.headline)+'</h1>'+
    '<p class="morning-deck">'+safe(feed.lead)+'</p>'+
    '<div class="hourly-hero-bottom"><span>Macro <i></i> Tassi <i></i> Mercati <i></i> Forex</span>'+
    '<div class="hourly-hero-actions"><button type="button" class="hourly-hero-sources-button" data-hourly-open-sources aria-controls="hourly-desk-news" aria-expanded="false">Notizie e fonti <span aria-hidden="true">↘</span></button>'+
    '<a href="#currencies">Esplora le valute <span aria-hidden="true">↗</span></a></div></div>'+
    '</header>'+
    '<aside class="hourly-fx-spotlight" aria-label="Implicazioni Forex">'+
    '<div class="hourly-spotlight-top"><span class="morning-section-label">LE CONSEGUENZE PER IL FOREX</span>'+
    '<span class="hourly-spotlight-symbol" aria-hidden="true">⇄</span></div>'+
    '<h2>La lettura relativa delle valute</h2>'+
    '<p>'+safe(feed.fx_implications)+'</p>'+
    '<div class="hourly-spotlight-actions"><a href="#pairs">Approfondisci le coppie FX <span aria-hidden="true">↗</span></a>'+
    '<a href="#rates">Esamina i tassi</a></div>'+
    '</aside></div>'+ 
    (root.FXQuantHomePulse?.render?.({feed,risk,currencyPrices,esc,date,dayNow})||'')+
    '<section class="hourly-decision-section" aria-label="Le tre verifiche del desk">'+
    '<div class="hourly-section-head"><div><span class="morning-section-label">LETTURA DEL DESK</span>'+
    '<h2>La mappa dei driver</h2></div>'+
    '<p>Novità, evidenze contrarie e conferme da seguire. Nessun segnale automatico.</p></div>'+
    '<div class="hourly-decision-grid">'+
    '<article class="hourly-decision-card hourly-decision-change">'+
    '<span class="hourly-decision-overline">CAMBIAMENTO</span>'+
    '<h3>Cosa è cambiato</h3><p>'+safe(feed.what_changed)+'</p>'+
    '<a class="hourly-driver-action" href="#macro">Esamina i dati macro <span aria-hidden="true">↗</span></a>'+
    '</article>'+
    '<article class="hourly-decision-card hourly-decision-contrary">'+
    '<span class="hourly-decision-overline">PROVA CONTRARIA</span>'+
    '<h3>La lettura alternativa.</h3><p>'+safe(feed.contrary_evidence)+'</p>'+
    '<a class="hourly-driver-action" href="#currencies">Confronta le valute <span aria-hidden="true">↗</span></a>'+
    '</article>'+
    '<article class="hourly-decision-card hourly-decision-watch">'+
    '<span class="hourly-decision-overline">PROSSIMA VERIFICA</span>'+
    '<h3>Da monitorare</h3><p>'+safe(feed.watch)+'</p>'+
    '<a class="hourly-driver-action" href="#news">Notizie e calendario <span aria-hidden="true">↗</span></a>'+
    '</article></div></section>'+
    '<section class="hourly-research-lens" aria-label="Analisi economica integrata">'+
    '<div class="hourly-lens-heading"><span class="morning-section-label">COSA STA SUCCEDENDO E PERCHÉ CONTA</span>'+
    '<h2>Le connessioni tra i mercati</h2></div>'+
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
    '<p class="hourly-desk-language-note">Titoli delle fonti estere sintetizzati in italiano. Per il testo originale, consulta il collegamento alla fonte.</p>'+
    '<div class="hourly-desk-news-body">'+news.map(x=>x.article).join('')+'</div></details></section>'+
    '<footer class="morning-source-notes hourly-method-note"><p>Ultima analisi pubblicata: '+
    safe(feed.edition_time_rome)+' (Europe/Rome). Metodo: confronto di dati datati, fonti ufficiali e proxy dichiarati. '+
    'I dati storici non sono movimenti intraday e l’interpretazione non costituisce un segnale di ingresso.</p>'+
    '</footer></article>';
 }
 root.FXQuantHourlyDesk={render,SCHEMA,titleItaliano,openSources};
})(typeof window!=='undefined'?window:globalThis);
