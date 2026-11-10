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
assert(html.includes('Il CPI mette alla prova')&&html.includes('Fed'));
assert.equal(chartN,2,'Only two economically relevant charts must support the narrative');
assert(html.indexOf('class="morning-prose"')<html.indexOf('class="morning-evidence"'),
 'Narrative must come before charts');
assert(html.indexOf('class="morning-evidence"')<html.indexOf('class="morning-outlook"'),
 'Charts must come before scenario boxes');
assert(html.includes('RECONSTRUCTION_NOT_POINT_IN_TIME'),
 'Historical trial cannot claim certified 08:00 publication');
assert(html.includes('non certificata come fotografia point-in-time'));
assert(html.includes('EUR/USD')&&html.includes('USD/JPY'));
assert(html.includes('Tassi & OIS')&&html.includes('28 coppie FX'));
const last={...feed,edition_date:'2026-11-09',observation_cutoff_exclusive:'2026-11-09',
sources:{...feed.sources,fx_fixing:'2026-11-08',rates:'2026-11-08'},
charts:feed.charts.map(c=>({...c,as_of:'2026-11-08',points:c.points.filter(p=>p.date<'2026-11-09')}))};
assert(sound(last));
const stale=build({...args,feed:last,dayNow:()=> '2026-11-10'});
assert(stale.includes('edizione archiviata'),'Old edition must be visibly historical');
assert.equal(build({...args,dayNow:()=> '2026-11-09'}),null,'Future publication rejected');
const corrupt={...feed,charts:feed.charts.map((c,i)=>i?c:{...c,points:c.points.concat([{date:'2026-11-10',value:100}])})};
assert.equal(sound(corrupt),false,'No event-day or future observations in frozen morning');
const signal={...feed,eligible_for_fx_signal:true};
assert.equal(sound(signal),false);
console.log('MORNING_FX_DESK_RENDER_V1_PASS: narrative-before-charts, 2 dated plots, archives and no lookahead');
