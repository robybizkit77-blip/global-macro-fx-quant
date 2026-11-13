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
 schema:'GMFQ_NEXT_INDEPENDENT_HOURLY_AI_DESK_V1',
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
assert.equal(render(null),null,'No AI edition = existing Morning remains');
assert.equal(render({...sample,status:'AWAITING_SECRET'}),null);
assert.equal(render({...sample,generated_at_utc:'2026-10-01T14:00:00Z'}),null);
const out=render(sample);
assert(out.includes('data-standalone-market-desk="active"'));
assert(out.indexOf('IL QUADRO GENERALE DEI MERCATI')<out.indexOf('Notizie e fonti di questa edizione'),
 'Overall narrative must come before article drilldown');
assert(out.includes('LE CONSEGUENZE PER IL FOREX'));
assert(out.includes('La lettura alternativa.'));
assert(out.includes('<details class="morning-deep-reading hourly-desk-news">'),
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
assert(app.includes("get('hourlyDesk')"),'Home is wired to optional independent AI research');
assert(app.includes("fetch('./hourly-market-desk-current.json'"),'Optional fetch endpoint missing');
assert(!app.includes("hourlyDesk:'"),'New research must not become a mandatory operational feed');
assert(index.includes('hourly-desk-ui-v1.js?v=1'));
assert(index.includes('hourly-desk-ui-v1.css?v=1'));
assert(index.includes('app.js?v=18.45-hourly'));
const workflow=fs.readFileSync(path.join(ROOT,'.github/workflows/next-independent-ai-hourly-desk-v1.yml'),'utf8');
assert(workflow.includes("cron: '17 * * * *'"));
assert(workflow.includes("secrets.FXQ_MARKET_DESK_API_KEY"));
assert(!/Automations__update|automations\.update|CHATGPT_AUTOMATION_ID/.test(workflow));
assert(workflow.includes("github.event_name != 'pull_request'"));
assert(workflow.includes('site/fx-quant-v2/next/hourly-market-desk-current.json'));
console.log('NEXT_INDEPENDENT_AI_DESK_UI_PASS: valid AI only, general-market narrative, source links, optional feed, ChatGPT untouched');
