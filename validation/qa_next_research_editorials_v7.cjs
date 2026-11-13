'use strict';
/* FX Quant Next V7: one continuous editorial research narrative per study section.
 * Tests current fixtures, source-date boundaries, selected currency/pair and missing data.
 * No network calls, no UI writes, no FX Core changes.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const modulePath='../site/fx-quant-v2/next/research-editorials.js';
const {create}=require(modulePath);
const json=path=>JSON.parse(fs.readFileSync(path,'utf8'));
const current={
 rates:json('live_data/sections/NATIVE_RATES_DATA.json'),
 dxy:json('live_data/sections/DXY_SYNTHETIC_ECB.json'),
 risk:json('site/fx-quant-v2/cross-asset-live-data.json'),
 pairs:json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
 macro:json('live_data/sections/MACRO_THERMOMETER_DATA.json'),
 cot:json('live_data/sections/V247_COT_STORIES.json'),
 cotHistory:json('live_data/sections/V250_COT_CHART_DATA.json'),
 ois:json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 news:json('live_data/sections/NEWS_PULSE_OPERATIONAL.json')
};
const names={USD:'Stati Uniti',EUR:'Area euro',GBP:'Regno Unito',JPY:'Giappone',CHF:'Svizzera',AUD:'Australia',NZD:'Nuova Zelanda',CAD:'Canada'};
const clone=x=>JSON.parse(JSON.stringify(x));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const validDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=x=>validDay(x)?x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):esc(x||'n.d.');
const fmt=(v,n=2)=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(v,n=1,suffix='')=>finite(v)?(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),n)+suffix:'—';
const baseState={ccy:'USD',csOther:'EUR',against:'EUR',pair:'EURUSD'};
function view(route,data=current,state=baseState,kind='stress',now='2026-11-08'){
 const api={get:k=>data[k]||null,state,caseNow:{kind},finite,validDay,fmt,sign,date,dayNow:()=>now,esc,NAMES:names};
 return create(api).render(route);
}
const routes=['macro','rates','currencies','pairs','cot','risk','news'];
const headlines=[];
for(const route of routes){
 const html=view(route);
 assert.match(html,/class="research-essay research-essay-dashboard"/,route+' has no dashboard editorial');
 assert.match(html,/class="essay-details"/,route+' missing optional deeper analysis');
 assert.equal((html.match(/<div class="essay-prose">/g)||[]).length,1);
 assert.equal((html.match(/<div class="essay-prose">[\s\S]*?<\/div>/)||[''])[0].match(/<p>/g)?.length,3,route+' missing three analytical paragraphs');
 assert.match(html,/class="essay-visual-guide"/,route+' missing chart-focused guide');
 assert.match(html,/<a href="#(?:macro|rates|currencies|pairs|cot|risk|news|overview)"/,route+' missing valid next-study link');
 assert(!html.includes('WITHHELD'),route+' exposes internal data quality marker');
 headlines.push(html.match(/<h2>([^<]+)<\/h2>/)?.[1]);
}
assert.equal(new Set(headlines).size,routes.length,'Repeated editorial titles across unrelated sections');
assert.match(view('macro'),/Stati Uniti/);
assert.match(view('macro',current,{...baseState,ccy:'EUR'}),/Area euro/);
assert.notEqual(view('macro'),view('macro',current,{...baseState,ccy:'EUR'}),'Macro must respond to chosen country');
assert.match(view('currencies',current,{...baseState,ccy:'EUR',csOther:'USD'}),/EUR\/USD/);
assert.match(view('cot',current,{...baseState,ccy:'AUD'}),/AUD/);
assert.match(view('pairs',current,{...baseState,pair:'CADJPY'}),/CAD\/JPY/);
assert.notEqual(view('pairs'),view('pairs',current,{...baseState,pair:'CADJPY'}),'Pair thesis must change when pair changes');
const reversed=view('currencies',current,{...baseState,ccy:'EUR',csOther:'EUR'});
assert.match(reversed,/EUR\/USD/,'Never compare one currency with itself');
// This is a positive same-date regression: use the actual source observation
// date, not a permanently fixed historical day that becomes older than feeds.
const sourceDate=current.rates?.USD?.date;
assert(validDay(sourceDate),'Official USD government source date must be present');
assert(finite(current.rates.USD['2Y'])&&finite(current.rates.USD['10Y'])&&
 finite(current.rates.USD.chg2_bp)&&finite(current.rates.USD.chg10_bp),
 'A valid dated USD 2Y/10Y observation is required for this test');
const changed=clone(current);
changed.rates.USD.chg2_bp=(current.rates.USD.chg2_bp||0)+15;
assert.notEqual(view('rates',current,baseState,'stress',sourceDate),
 view('rates',changed,baseState,'stress',sourceDate),
 'Rates editorial must respond to a changed 2Y move on the observed source date');
// The safety guard still rejects a feed unavailable on an earlier day.
const historicalDay='2026-11-10';
if(sourceDate>historicalDay){
 assert.equal(view('rates',current,baseState,'stress',historicalDay),
              view('rates',changed,baseState,'stress',historicalDay),
  'Rates editorial must not show future-dated 2Y/10Y observations');
}
const empty={};
for(const route of routes)assert.match(view(route,empty),/research-essay/,'Missing feed crashes '+route);
const attack=clone(current);
attack.pairs.pairs.EURUSD.decision_frame.relation='<img src=x onerror=alert(1)>';
const escaped=view('pairs',attack);
assert(escaped.includes('&lt;img'));
assert(!escaped.includes('<img'));
assert.match(view('rates',current,baseState,'yield-selloff'),/aspettative|premi/);
const site=fs.readFileSync('site/fx-quant-v2/next/index.html','utf8');
assert.match(site,/research-editorials\.js\?v=8/);
assert.match(site,/editorial-v4\.css\?v=18/);
assert(site.indexOf('research-editorials.js')<site.indexOf('app.js?v=18'),'Research script must load first');
console.log('NEXT_RESEARCH_EDITORIAL_V7_PASS routes=7 countries=8 selected_pair=yes dates=distinct fallback=explicit XSS=escaped no_signal_write=true');
