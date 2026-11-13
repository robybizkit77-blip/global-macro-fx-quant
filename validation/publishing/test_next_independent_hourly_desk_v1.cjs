'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ROOT=path.resolve(__dirname,'../..');
const next='site/fx-quant-v2/next/';
const src=fs.readFileSync(path.join(ROOT,next,'hourly-desk-ui-v1.js'),'utf8');
const win={};const ctx={window:win};
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
assert(out.includes('class="hourly-hero-grid"'),'Hero has an FX research spotlight, not a one-column newspaper');
assert(out.includes('class="hourly-fx-spotlight"'),'Forex consequences must be prominent at first glance');
assert(out.includes('class="hourly-decision-grid"'),'Three-part decision map must be visible');
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
assert(index.includes('hourly-desk-ui-v1.js?v=3'));
assert(index.includes('hourly-desk-ui-v1.css?v=2'));
assert(index.includes('app.js?v=18.47-free-desk-persist'));
const css=fs.readFileSync(path.join(ROOT,next,'hourly-desk-ui-v1.css'),'utf8');
assert(css.includes('.hourly-hero-grid')&&css.includes('.hourly-navigation-grid')&&css.includes('.hourly-desk-news-body'),
 'The new workbench CSS must style every major hierarchy layer');
assert(css.includes('@media(max-width:630px)')&&css.includes('@media(max-width:860px)'),
 'Premium Home must retain readable mobile and tablet behavior');
assert(css.includes('prefers-reduced-motion'),'Hover effects must respect reduced-motion accessibility');
assert(!css.includes('.sidebar')&&!css.includes('.currency-studio')&&!css.includes('.pair-studio'),
 'No unapproved restyling of other dashboard sections');
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
