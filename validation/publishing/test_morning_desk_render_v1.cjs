'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const api={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,'site/fx-quant-v2/next/morning-desk-v1.js'),'utf8'),api,
 {filename:'morning-desk-v1.js',timeout:5000});
const {sound,build}=api.window.FXQuantMorningDesk;
const feed=JSON.parse(fs.readFileSync(path.join(root,'site/fx-quant-v2/next/morning-desk-current.json'),'utf8'));
const safe=x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const date=x=>x;
let chartN=0;
const draw=()=>'<div class="chart"><svg><title>VERIFIED CHART</title></svg></div>';
const args={feed,plot:()=>{chartN++;return draw();},esc:safe,date,dayNow:()=>feed.edition_date};
assert.equal(sound(feed),true,'Approved macro briefing source must satisfy contract');
const html=build(args);
assert(html&&html.includes('MORNING MACRO & FX RESEARCH DESK'));
assert(html.includes(safe(feed.headline)),'Rendered headline must match the dated editorial source');
assert.equal(chartN,2,'Only two economically relevant charts must support the narrative');
assert(html.indexOf('class="morning-prose"')<html.indexOf('class="morning-evidence"'),
 'Narrative must come before charts');
assert(html.indexOf('class="morning-evidence"')<html.indexOf('class="morning-outlook"'),
 'Charts must come before scenario boxes');
assert(html.includes(feed.edition_status),'Current edition status must be visible');
if(feed.edition_status==='RECONSTRUCTION_NOT_POINT_IN_TIME')
 assert(html.includes('non certificata come fotografia point-in-time'));
if(feed.edition_status==='LATE_MORNING_SNAPSHOT')
 assert(html.includes('ritardo non viene nascosto'));
assert(html.includes(feed.pair.slice(0,3)+'/'+feed.pair.slice(3)),'Narrative must name the active FX pair');
assert(html.includes('Tassi & OIS')&&html.includes('28 coppie FX'));
const addDays=(iso,n)=>{const d=new Date(iso+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)};
const stale=build({...args,dayNow:()=>addDays(feed.edition_date,1)});
assert(stale.includes('edizione archiviata'),'Old edition must be visibly historical');
assert.equal(build({...args,dayNow:()=>addDays(feed.edition_date,-1)}),null,'Future publication rejected');
const corrupt={...feed,charts:feed.charts.map((c,i)=>i?c:{...c,points:c.points.concat([{date:feed.edition_date,value:100}])})};
assert.equal(sound(corrupt),false,'No event-day or future observations in frozen morning');
const signal={...feed,eligible_for_fx_signal:true};
assert.equal(sound(signal),false);
// A newly observed issuer release appears AFTER the frozen opening article,
// while older observations, unverified provenance and unrelated items are rejected.
const official={
 category:'MACRO_OFFICIAL_ACTUAL',ccy:'USD',as_of:'2026-11-10',
 quality:'ISSUER_BLS_HTML_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT',
 title:'CPI USA ottobre · headline +0,4% e core +0,3% mensili',
 detail:'Dati BLS osservati. Nessun repricing o risposta FX intraday verificata.',
 source_url:'https://www.bls.gov/news.release/cpi.htm',
 first_runner_observed_at_utc:'2026-11-11T08:48:15Z'
};
const todayFeed={...feed,edition_date:'2026-11-11',observation_cutoff_exclusive:'2026-11-11',
 created_at_utc:'2026-11-11T08:29:40Z',edition_status:'LATE_MORNING_SNAPSHOT',
 sources:{...feed.sources,fx_fixing:'2026-11-10',rates:'2026-11-09'},
 charts:feed.charts.map(c=>({...c,as_of:'2026-11-09',
 points:c.points.filter(p=>p.date<'2026-11-11')}))};
const post=api.window.FXQuantMorningDesk.postRelease(todayFeed,{items:[official]},safe,()=> '2026-11-11');
assert(post.includes('AGGIORNAMENTO DOPO IL BRIEFING')&&post.includes('Fonte BLS'));
assert(post.includes('EUR/USD')&&post.includes('USD/JPY'));
assert.equal(api.window.FXQuantMorningDesk.postRelease(todayFeed,
 {items:[{...official,first_runner_observed_at_utc:'2026-11-11T08:20:15Z'}]},safe,()=> '2026-11-11'),'');
assert.equal(api.window.FXQuantMorningDesk.postRelease(todayFeed,
 {items:[{...official,quality:'UNVERIFIED'}]},safe,()=> '2026-11-11'),'');
assert.equal(api.window.FXQuantMorningDesk.postRelease(todayFeed,
 {items:[official]},safe,()=> '2026-11-12'),'');
assert.equal(api.window.FXQuantMorningDesk.postRelease(todayFeed,
 {items:[{...official,source_url:'https://example.org/forged'}]},safe,()=> '2026-11-11'),'');
console.log('MORNING_FX_DESK_RENDER_V1_PASS: narrative-before-charts, 2 dated plots, archives and no lookahead');
