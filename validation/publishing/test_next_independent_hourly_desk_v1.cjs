'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ROOT=path.resolve(__dirname,'../..');
const next='site/fx-quant-v2/next/';
const src=fs.readFileSync(path.join(ROOT,next,'hourly-desk-ui-v1.js'),'utf8');
const pulseSrc=fs.readFileSync(path.join(ROOT,next,'home-market-pulse-v1.js'),'utf8');
const win={};const ctx={window:win};
vm.runInNewContext(pulseSrc,ctx,{filename:'home-market-pulse-v1.js',timeout:2500});
vm.runInNewContext(src,ctx,{filename:'hourly-desk-ui-v1.js',timeout:2500});
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=s=>s;
const today=()=> '2026-11-13';
const sample={
 schema:'GMFQ_NEXT_FREE_HOURLY_DESK_V1',
 status:'ACTIVE',generated_at_utc:'2026-11-13T12:50:00Z',
 edition_time_rome:'2026-11-13 13:50',
 headline:'Le aspettative monetarie si confrontano con il rischio globale',
 lead:'Azioni, credito e volatilità offrono segnali di mercato da leggere insieme.',
 desk_judgment:'Il quadro generale resta misto: la crescita e le attese monetarie tirano in direzioni diverse.',
 fx_implications:'Il dollaro dipende dai tassi relativi e dal rischio globale; EUR/USD va confrontato con USD/JPY.',
 what_changed:'Il pricing monetario estero è cambiato, mentre il resto del quadro resta da confrontare.',
 contrary_evidence:'La forza delle valute potrebbe dipendere dalla debolezza delle controparti, non solo dai tassi.',
 watch:'Guardare i prossimi dati macro, rendimenti relativi, volatilità e credito per valutare la persistenza.',
 news:[{headline:'Dati e attese Fed',
 analysis:'Le aspettative sulla banca centrale dipendono dalla sorpresa sui dati, dalla composizione e dal costo del rischio.',
 kind:'NEWS',published_date:'2026-11-13',event_date:'2026-11-13',market_area:'MACRO',
 sources:['https://www.bls.gov/news.release/ppi.htm']}],
 provenance:{web_source_urls:['https://www.bls.gov/news.release/ppi.htm']}
};
const render=feed=>win.FXQuantHourlyDesk.render({feed,esc,date,dayNow:today});
assert.equal(render(null),null,'No free edition = existing Morning remains');
assert.equal(render({...sample,status:'AWAITING_SECRET'}),null);
assert.equal(render({...sample,generated_at_utc:'2026-10-01T14:00:00Z'}),null);
const out=render(sample);
assert(out.includes('data-standalone-market-desk="active"'));
assert(out.indexOf('IL QUADRO GENERALE DEI MERCATI')<out.indexOf('Notizie e fonti di questa edizione'),
 'Overall narrative must come before article drilldown');
assert(out.includes('LE CONSEGUENZE PER IL FOREX'));
assert(out.includes('data-hourly-hero-to-sources="true"'),
 'The market-picture hero must lead to source evidence');
assert(out.includes('data-hourly-open-sources'),
 'The source dossier must have keyboard-accessible native buttons');
assert(out.includes('aria-controls="hourly-desk-news"'),
 'The source action must identify the exact expandable dossier');
assert(out.includes('Notizie e fonti'),
 'The click destination should be understandable in Italian');
const englishNews=structuredClone(sample);
englishNews.news=[
 {headline:'Hydropower generation in the Southwest fell to record lows this summer',
  analysis:'Approfondimento sulla produzione elettrica, non prova di una variazione del WTI.',
  kind:'NEWS',published_date:'2026-11-13',event_date:'2026-11-13',
  market_area:'ENERGIA',sources:['https://www.eia.gov/todayinenergy/detail.php?id=68445']},
 {headline:'The Bank of England, the Monetary Authority of Singapore, and the Bank of Thailand: Project Meridian FX APAC',
  analysis:'Comunicazione delle autorità monetarie sul progetto di collaborazione.',
  kind:'FOLLOW_UP',published_date:'2026-11-13',event_date:'2026-11-13',
  market_area:'BANCHE CENTRALI',sources:['https://www.bankofengland.co.uk/news/2026/november/the-boe-monetary-authority-of-singapore-and-bank-of-thailand-media-release']}
];
englishNews.provenance.web_source_urls=englishNews.news.map(x=>x.sources[0]);
const italian=render(englishNews);
assert(italian.includes('Produzione idroelettrica nel Sud-Ovest USA'),
 'EIA English headline should be accurately labelled in Italian');
assert(italian.includes('Progetto Meridian FX APAC: collaborazione'),
 'Bank of England collaboration should be labelled in Italian');
assert(!italian.includes('Hydropower generation')&&!italian.includes('The Bank of England'),
 'Do not show untranslated foreign RSS headlines on Home');
assert(!italian.includes('follow-up'),'News category labels must be Italian');
assert(italian.includes('https://www.eia.gov/todayinenergy/detail.php?id=68445')&&
 italian.includes('https://www.bankofengland.co.uk/news/2026/november/'),
 'Italian display labels must retain the original authoritative citations');
assert(win.FXQuantHourlyDesk.titleItaliano({headline:'New energy study released',
 market_area:'ENERGIA',sources:['https://www.eia.gov/todayinenergy/detail.php?id=68445']}).startsWith('EIA: pubblicazione su'),
 'Unknown foreign RSS title must use a conservative Italian synopsis, not invented translation');
assert(win.FXQuantHourlyDesk.titleItaliano({headline:'Forza del dollaro contro euro',
 market_area:'FOREX',sources:[]})==='Forza del dollaro contro euro',
 'Existing Italian analysis must remain unchanged');
const selectedArticle={scrolled:false,focused:false,scrollIntoView(){this.scrolled=true},focus(){this.focused=true}};
const dossier={open:false,scrolled:false,focused:false,
 scrollIntoView(){this.scrolled=true;},
 querySelector(name){return name==='summary'?{focus:()=>{this.focused=true}}:name==='[data-hourly-article="0"]'?selectedArticle:null}};
let attrs={};
const mockDesk={querySelector:sel=>sel==='details#hourly-desk-news'?dossier:null,
 querySelectorAll:sel=>sel==='[data-hourly-open-sources]'?[{setAttribute:(k,v)=>attrs[k]=v}]:[]};
const mockButton={closest:sel=>sel==='.hourly-market-desk'?mockDesk:null};
assert(win.FXQuantHourlyDesk.openSources(mockButton),
 'Button click must open the correct source dossier');
assert(dossier.open&&dossier.scrolled&&dossier.focused&&attrs['aria-expanded']==='true',
 'The dossier must expand, scroll into view and receive keyboard focus');
assert(out.includes('data-hourly-story-link="0"')&&out.includes('data-hourly-article="0"'),
 'Evidence previews must link to their exact source article');
assert(out.includes('aria-label="Apri la notizia:')&&out.includes('bls.gov <span'),
 'Native buttons and readable source hostnames replace inert previews and opaque source numbers');
assert(win.FXQuantHourlyDesk.openSources(mockButton,'0')&&selectedArticle.scrolled&&selectedArticle.focused,
 'Direct source preview navigation must open and focus the exact article');


const pulseFeed=structuredClone(sample);
pulseFeed.news=[
 {headline:'Forza del dollaro sui cross EUR/USD e USD/JPY',analysis:'Negli ultimi fixing BCE il dollaro è più forte contro EUR e JPY.',kind:'FOLLOW_UP',
  market_area:'FOREX',published_date:'2026-11-12',event_date:'2026-11-12',
  sources:['https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml']},
 {headline:'Oro e petrolio divergono nelle rilevazioni dei futures',analysis:'I prezzi futures mostrano oro e WTI con direzioni diverse.',kind:'FOLLOW_UP',
  market_area:'COMMODITIES',published_date:'2026-11-13',event_date:'2026-11-13',
  sources:['https://query1.finance.yahoo.com/v8/finance/chart/GC=F']}
];
pulseFeed.provenance.web_source_urls=pulseFeed.news.map(x=>x.sources[0]);
pulseFeed.desk_judgment+=' Oro in rialzo e petrolio in calo nelle ultime rilevazioni pubblicate.';
const stream=(date,value,previous,history)=>({
 date,value,previous,history,not_intraday:true,
 quality:'PUBLISHED_SOURCE_RESEARCH_ONLY',
 source_url:'https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500'
});
const research={streams:{
 SP500:stream('2026-11-12',101,100,[['2026-11-09',98],['2026-11-10',100],['2026-11-12',101]]),
 VIX:stream('2026-11-12',18.7,17.49,[['2026-11-09',19.5],['2026-11-10',17.49],['2026-11-12',18.7]]),
 HY_OAS:stream('2026-11-12',3.2,3.3,[['2026-11-09',3.5],['2026-11-10',3.3],['2026-11-12',3.2]])
}};
const displayDate=s=>s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4);
const officialFx={
 schema:'GMFQ_ECB_G8_PRICE_HISTORY_V1',status:'CURRENT_OFFICIAL_HISTORY',base:'EUR',
 source_url:'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml',
 last_as_of:'2026-11-13',
 rows:[{Date:'2026-11-12',USD:1.1081,JPY:176.96},
       {Date:'2026-11-13',USD:1.1052,JPY:176.83}]
};
const pulseHTML=win.FXQuantHourlyDesk.render({feed:pulseFeed,risk:research,
 currencyPrices:officialFx,esc,date:displayDate,dayNow:today});
assert(pulseHTML.includes('IL MERCATO IN UN COLPO D’OCCHIO'),'Visual pulse must remain narrative-first and dated');
assert((pulseHTML.match(/class="hourly-pulse-tile /g)||[]).length===4,
 'Only sourced numeric ECB FX, S&P, VIX and HY tiles may appear');
assert(pulseHTML.includes('USD ↑')&&pulseHTML.includes('EUR +0,26% · JPY +0,19%'),
 'USD strength must be computed from aligned, current official EUR/USD and USD/JPY fixings');
assert(pulseHTML.includes('BCE · 2 confronti, non indice USD'),
 'Two bilateral moves must never be misrepresented as broad dollar strength');
assert(!pulseHTML.includes('Oro ↑ · WTI ↓'),
 'Commodity direction is not inferred from headlines without matched numeric evidence');
assert(pulseHTML.includes('Indice VIX')&&pulseHTML.includes('Spread HY'),'Real measured market breadth shown');
assert(pulseHTML.includes('+1,00%')&&pulseHTML.includes('18,70')&&pulseHTML.includes('−10 pb'),
 'Numbers must derive from observed value/previous, preserving units');
assert((pulseHTML.match(/class="hourly-pulse-spark"/g)||[]).length===3,
 'Mini-charts must be derived from 3 actual historical streams, not drawn decoratively');
assert(pulseHTML.includes('12/11/2026')&&pulseHTML.includes('13/11/2026'),'Every observation must retain its source date');
assert(/non intraday/i.test(pulseHTML)&&!pulseHTML.includes('tempo reale</p>'),
 'The Home must explicitly separate delayed closes from live data');
assert(pulseHTML.includes('class="hourly-decision-grid"')&&pulseHTML.includes(sample.what_changed),
 'The original substantive desk interpretation survives the visual hierarchy');
const unsupported=structuredClone(research);
unsupported.streams.VIX.quality='ESTIMATED';
unsupported.streams.HY_OAS.date='2026-10-01';
const filtered=win.FXQuantHomePulse.render({feed:pulseFeed,risk:unsupported,esc,date:displayDate,dayNow:today});
assert(!filtered.includes('Indice VIX')&&!filtered.includes('Spread HY'),
 'No estimate or stale record can be promoted into a market pulse');
const mixedFx=structuredClone(officialFx);
mixedFx.rows[1].JPY=174.60;
const mixedHTML=win.FXQuantHomePulse.render({feed:pulseFeed,risk:research,
 currencyPrices:mixedFx,esc,date:displayDate,dayNow:today});
assert(mixedHTML.includes('USD misto')&&!mixedHTML.includes('USD ↑'),
 'Contradictory cross movements must never be promoted to a uniform USD direction');
const staleFx=structuredClone(officialFx);
staleFx.last_as_of='2026-11-12';
const staleHTML=win.FXQuantHomePulse.render({feed:pulseFeed,risk:research,
 currencyPrices:staleFx,esc,date:displayDate,dayNow:today});
assert(!staleHTML.includes('FORZA FX RELATIVA'),
 'A mismatched source vintage must suppress the FX claim, preserving other verified tiles');
const unverifiedFx=structuredClone(officialFx);
unverifiedFx.status='ESTIMATED';
assert(!win.FXQuantHomePulse.render({feed:pulseFeed,risk:research,
 currencyPrices:unverifiedFx,esc,date:displayDate,dayNow:today}).includes('FORZA FX RELATIVA'),
 'Estimates cannot masquerade as official fixing in the visual pulse');
assert.equal(win.FXQuantHomePulse.render({feed:pulseFeed,risk:null,esc,date,dayNow:today}),'',
 'No market source means no market pulse; the existing research stays intact');

assert(out.includes('class="hourly-hero-grid"'),'Hero has an FX research spotlight, not a one-column newspaper');
assert(out.includes('class="hourly-fx-spotlight"'),'Forex consequences must be prominent at first glance');
assert(out.includes('class="hourly-decision-grid"'),'Three-part decision map must be visible');
assert(out.includes('href="#macro">Esamina i dati macro')&&
 out.includes('href="#currencies">Confronta le valute')&&
 out.includes('href="#news">Notizie e calendario'),
 'Every evidence card must lead to an existing research page, not an inert display');
assert((out.match(/class="hourly-driver-action"/g)||[]).length===3,
 'The action design must remain exactly one useful link per decision card');
assert(out.includes('class="hourly-navigation-grid"'),'Direct research tools navigation must be present');
assert(out.includes('class="hourly-evidence-peek"'),'At-a-glance headlines must show evidence');
assert(out.includes('Le connessioni tra i mercati'),'Long-form economic context must remain accessible');
assert(out.includes(sample.desk_judgment),'The full canonical market judgment must be visible when no lead repetition exists');
const consecutive=structuredClone(sample);
consecutive.desk_judgment=sample.lead+' La persistenza dipende dai nuovi dati e dalla conferma delle coppie FX.';
const repeated=render(consecutive);
assert(repeated.includes('Lettura completa del desk')&&repeated.includes(consecutive.desk_judgment),
 'When the judgment starts with the lead, preserve the complete text in an expandable dossier');
assert(out.includes(sample.desk_judgment),'The original full market judgment cannot be dropped');
assert(out.includes(sample.fx_implications),'Original FX implications must not be rewritten');
assert(out.includes(sample.what_changed)&&out.includes(sample.contrary_evidence)&&out.includes(sample.watch),
 'All original economic judgment, contradictions and catalysts must remain available');
assert(out.includes('href="#currencies"')&&out.includes('href="#pairs"')&&
 out.includes('href="#rates"')&&out.includes('href="#macro"')&&
 out.includes('href="#risk"')&&out.includes('href="#news"'),
 'Research navigation must target real existing FX Quant routes');

assert(out.includes('La lettura alternativa.'));
assert(out.includes('<details class="morning-deep-reading hourly-desk-news" id="hourly-desk-news">'),
 'News are available on request, not stacked on Home');
assert(out.includes('https://www.bls.gov/news.release/ppi.htm'),'Cited source must be clickable');
assert(!out.includes('rank')&&!out.includes('punteggio'));
const dirty=structuredClone(sample);
dirty.news[0].sources=['javascript:alert(1)'];
assert.equal(render(dirty),null,'Unverified/unsafe citation invalidates the entire edition');
const xss=structuredClone(sample);
xss.headline='<script>alert(1)</script> mercato'; 
assert(render(xss).includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
const app=fs.readFileSync(path.join(ROOT,next,'app.js'),'utf8');
const index=fs.readFileSync(path.join(ROOT,next,'index.html'),'utf8');
assert(app.includes("get('hourlyDesk')"),'Home is wired to optional independent free research');
assert(app.includes("fetch('../../../market-desk/hourly-market-desk-current.json'"),'Optional fetch endpoint missing');
assert(!app.includes("hourlyDesk:'"),'New research must not become a mandatory operational feed');
assert(index.includes('hourly-desk-ui-v1.js?v=8'));
assert(index.includes('hourly-desk-ui-v1.css?v=4'));
assert(index.includes('home-market-pulse-v1.js?v=2')&&index.includes('home-market-pulse-v1.css?v=3'),
 'The source-based data visualization must load before the editorial Home UI');
assert(index.indexOf('home-market-pulse-v1.js?v=2')<index.indexOf('hourly-desk-ui-v1.js?v=8'),
 'Rendering order must preserve the optional pulse addon');
assert(index.includes('app.js?v=18.52-calendar-journey'));
assert(app.includes("currencyPrices:get('currencyPrices')"),'Official ECB fixing history must feed FX observations');

// Regression: on cold navigation an empty-data overview used to render first,
// then vanish as soon as the hourly desk loaded. Keep loader, not fallback.
const navStart=app.indexOf('function syncRouteChrome(route){');
const navEnd=app.indexOf("window.addEventListener('hashchange',navigate);");
assert(navStart>=0&&navEnd>navStart,'Initial navigation guard must be testable');
const navSrc=app.slice(navStart,navEnd);
let painted=0;
const navEntries=['overview','currencies'].map(route=>({
 dataset:{route},current:false,
 setAttribute(k,v){if(k==='aria-current')this.current=v==='page';},
 removeAttribute(k){if(k==='aria-current')this.current=false;}
}));
const breadcrumb={textContent:'Panoramica'};
const navCtx={
 firstResearchLoaded:false,state:{route:'overview'},
 ROUTES:{overview:'Panoramica',currencies:'Valute G8'},
 location:{hash:'#currencies'},
 document:{querySelectorAll:()=>navEntries},
 window:{scrollTo:()=>{}},
 $:id=>id==='crumb-page'?breadcrumb:
  id==='app'?{classList:{remove:()=>{}}}:
  {setAttribute:()=>{}},
 render:()=>{painted++}
};
vm.runInNewContext(navSrc,navCtx,{timeout:2500});
navCtx.navigate();
assert.equal(painted,0,'Cold load must not paint empty-data fallback content');
assert.equal(navCtx.state.route,'currencies','Deep link must remain respected while loading');
assert.equal(breadcrumb.textContent,'Valute G8','The loading breadcrumb must match the deep link');
assert(navEntries[1].current&&!navEntries[0].current,'Loading navigation must mark the real route');
navCtx.firstResearchLoaded=true;
navCtx.navigate();
assert.equal(painted,1,'After sources settle the selected route must render exactly once');
assert(/await Promise\.allSettled\(jobs\);[\s\S]*?state\.data=nextData;[\s\S]*?firstResearchLoaded=true;\s*render\(\);/.test(app),
 'Only settled sources may unlock the first full render');
assert(app.includes("document.addEventListener('visibilitychange'")&&
 app.includes('lastResearchRefresh=Date.now()'),
 'Existing in-place refresh behavior must stay intact');

const css=fs.readFileSync(path.join(ROOT,next,'hourly-desk-ui-v1.css'),'utf8');
assert(css.includes('.hourly-hero-grid')&&css.includes('.hourly-navigation-grid')&&css.includes('.hourly-desk-news-body'),
 'The new workbench CSS must style every major hierarchy layer');
assert(css.includes('button.hourly-evidence-peek-item')&&css.includes('hourly-desk-story[data-hourly-article]'),
 'Clickable previews must have accessible desktop/mobile styles');
assert(css.includes('@media(max-width:630px)')&&css.includes('@media(max-width:860px)'),
 'Premium Home must retain readable mobile and tablet behavior');
assert(css.includes('prefers-reduced-motion'),'Hover effects must respect reduced-motion accessibility');
assert(!css.includes('.sidebar')&&!css.includes('.currency-studio')&&!css.includes('.pair-studio'),
 'No unapproved restyling of other dashboard sections');
const pulseCss=fs.readFileSync(path.join(ROOT,next,'home-market-pulse-v1.css'),'utf8');
assert(pulseCss.includes('.hourly-pulse-track')&&pulseCss.includes('.hourly-decision-change'),
 'Premium hierarchy must emphasize primary driver and source-dated market observations');
assert(pulseCss.includes('a.hourly-driver-action')&&pulseCss.includes(':focus-visible'),
 'Decision cards need unmistakable, keyboard-accessible links to the actual research');
assert(pulseCss.includes('max-width:630px')&&pulseCss.includes('prefers-reduced-motion'),
 'Market pulse must be mobile-friendly and reduce motion');
assert(!pulseCss.includes('.sidebar')&&!pulseCss.includes('.pair-studio'),
 'No unrelated route restyling');
const workflow=fs.readFileSync(path.join(ROOT,'.github/workflows/next-independent-ai-hourly-desk-v1.yml'),'utf8');
assert(workflow.includes("cron: '17 * * * *'"));
assert(!workflow.includes("secrets.FXQ_MARKET_DESK_API_KEY"));
assert(workflow.includes("build_free_hourly_desk_v1.py"));
assert(!workflow.includes("api.openai.com"));
assert(!/Automations__update|automations\.update|CHATGPT_AUTOMATION_ID/.test(workflow));
assert(workflow.includes("github.event_name != 'pull_request'"));
assert(workflow.includes('market-desk/hourly-market-desk-current.json'));
assert(!workflow.includes('site/fx-quant-v2/next/hourly-market-desk-current.json'),
 'The FX V2 exact-tree rsync --delete would otherwise erase the independent feed');
assert(workflow.includes('mkdir -p "$dir/market-desk"'),
 'Hourly publishing must create a root-owned folder outside FX V2 mirroring');

console.log('NEXT_FREE_DESK_PREMIUM_UI_PASS: macro depth preserved, visual workbench, source links, responsive, ChatGPT untouched');
