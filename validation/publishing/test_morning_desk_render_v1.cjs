'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const api={window:{},URL}; // URL is a browser global used by strict issuer-source validation
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
assert(html.indexOf('class="morning-first-read"')<html.indexOf('class="morning-prose"'),
 'Home must explain the observed FX evidence before the full research narrative');
assert(html.includes('class="morning-deep-reading"')&&html.includes('class="morning-deep-body"'),
 'Full four-paragraph research must remain available inside an expandable panel');
assert(html.includes(safe(feed.watch)),'Next evidence to monitor must stay explicit');
assert(html.includes('class="morning-first-links"')&&html.includes('Verifica Tassi &amp; OIS'),
 'First read must link FX interpretation to paired rates evidence');
assert(html.indexOf('class="morning-first-read"')<html.indexOf('class="morning-evidence"'),
 'First read must come before supporting charts');
assert(html.includes(safe(feed.headline)),'Rendered headline must match the dated editorial source');
assert.equal(chartN,2,'Only two economically relevant charts must support the narrative');
const badRelative={...feed,relative_evidence:{...feed.relative_evidence,aligned_to:feed.edition_date}};
const badRelativeHtml=build({...args,feed:badRelative});
assert(!badRelativeHtml.includes('Dal '+date(feed.relative_evidence.aligned_from)+
 ' al '+date(feed.edition_date)),
 'Do not display a same-day or future pair/rates comparison as pre-opening evidence');
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
assert(html.includes('Tassi &amp; OIS')&&html.includes('28 coppie FX'));
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
const asOf='2026-11-11T10:15:00Z';
const getPost=(edition,items,date,now=asOf)=>
 api.window.FXQuantMorningDesk.postRelease(edition,{items},safe,()=>date,now);
const post=getPost(todayFeed,[official],'2026-11-11');
assert(post.includes('NUOVI DATI MACRO UFFICIALI')&&post.includes('Fonte ufficiale'));
assert(post.includes('EUR/USD')&&post.includes('USD/JPY'));
assert(post.includes('Il briefing originale resta invariato'));
assert.equal(getPost(todayFeed,[{...official,first_runner_observed_at_utc:'2026-11-11T08:20:15Z'}],'2026-11-11'),'');
assert.equal(getPost(todayFeed,[{...official,quality:'UNVERIFIED'}],'2026-11-11'),'');
assert.equal(getPost(todayFeed,[official],'2026-11-12'),'');
assert.equal(getPost(todayFeed,[{...official,source_url:'https://example.org/forged'}],'2026-11-11'),'');
assert.equal(getPost(todayFeed,[{...official,as_of:'2026-11-12'}],'2026-11-11'),'');
assert.equal(getPost(todayFeed,[{...official,event_type:'SYNTHETIC_TRADE'}],'2026-11-11'),'');
const ukFeed={...todayFeed,edition_date:'2026-11-12',observation_cutoff_exclusive:'2026-11-12',
 created_at_utc:'2026-11-12T06:50:00Z'};
const ukActual={...official,ccy:'GBP',as_of:'2026-11-12',event_type:'GROWTH',
 quality:'ISSUER_GDP_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT',
 title:'Regno Unito · PIL preliminare: +0,5%',
 source_url:'https://www.ons.gov.uk/economy/grossdomesticproductgdp/bulletins/gdpfirstquarterlyestimateuk/julytoseptember2026',
 first_runner_observed_at_utc:'2026-11-12T07:05:00Z'};
const gdp=getPost(ukFeed,[ukActual],'2026-11-12','2026-11-12T07:06:00Z');
assert(gdp.includes('BoE')&&gdp.includes('GBP/USD')&&gdp.includes('EUR/GBP'),'UK policy/FX relative lens');
assert.equal(getPost(ukFeed,[ukActual],'2026-11-12','2026-11-12T07:02:00Z'),'',
 'future runner observation must not leak into the past');
const late={...ukFeed,created_at_utc:'2026-11-12T08:29:00Z'};
assert(getPost(late,[ukActual],'2026-11-12','2026-11-12T09:00:00Z').includes('PIL preliminare'),
 'same-day result must survive a delayed frozen morning edition');
const invalidCB={...ukActual,ccy:'NZD',event_type:'CENTRAL_BANK_DECISION'};
assert.equal(getPost(ukFeed,[invalidCB],'2026-11-12','2026-11-12T09:00:00Z'),'',
 'CB headlines without a structured validated issuer actual must not be promoted');
console.log('MORNING_FX_DESK_RENDER_V1_PASS: narrative-before-charts, 2 dated plots, archives and no lookahead');
