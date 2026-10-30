'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const first=read('validation/fixtures/rbnz_b2_official_table_2026-10-23_first_review_ONLY.json');
const second=read('validation/fixtures/rbnz_b2_separate_official_web_reread_2026-10-23.json');
const ctx=read('live_data/sections/NZD_B2_GOVT_WEB_REVIEW_CONTEXT.json');
const raw=read('live_data/sections/NATIVE_RATES_DATA.json');
assert.deepEqual(first.observations,second.source_rows,'two RBNZ public HTML reads match exactly');
const last=first.observations.at(-1);
assert.equal(ctx.as_of,last.date);
assert.equal(ctx['2Y'],last['2Y']);
assert.equal(ctx['10Y'],last['10Y']);
assert.equal(ctx.curve_bp,Math.round((last['10Y']-last['2Y'])*1000)/10);
assert.equal(ctx.evidence.independent_xlsx_review_completed,false);
assert.equal(ctx.evidence.independent_human_reviewer_confirmed,false);
assert.equal(ctx.governance.live_data_promotion_allowed,false);
const source=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const start=source.indexOf('function nzdWebReviewCandidate(canonical,c){');
const end=source.indexOf('function renderYieldStudy(',start);
assert(start>=0&&end>start,'pure guarded NZD study helper not found');
const num=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
const today=Date.parse('2026-10-23T00:00:00Z');
const age=s=>{
 if(typeof s!=='string'||!/^20\d{2}-\d{2}-\d{2}$/.test(s))return null;
 const t=Date.parse(s+'T00:00:00Z');
 return Number.isFinite(t)?Math.round((today-t)/86400000):null;
};
const build=new Function('num','romeCalendarAge',source.slice(start,end)+';return nzdWebReviewCandidate;')(num,age);
const c=build(raw,ctx);
if(raw.NZD.date==='2026-10-16'){
 assert(c&&c.v2===3.91&&c.v10===4.98&&c.slopeBp===107);
 assert.equal(c.approval,'PENDING');
} else {
 assert(raw.NZD.date>='2026-10-22','canonical NZD date regressed');
 assert.equal(c,null,'candidate must disappear once canonical NZD updated');
}
function reject(edit){
 const r=structuredClone(raw),v=structuredClone(ctx);
 r.NZD.date='2026-10-16';
 r.NZD['2Y']=ctx.canonical_at_review['2Y'];r.NZD['10Y']=ctx.canonical_at_review['10Y'];
 edit(r,v);
 assert.equal(build(r,v),null,'an unverified mutation must fail closed');
}
reject((r,c)=>{c['2Y']=3.92});
reject((r,c)=>{c.evidence.independent_xlsx_review_completed=true});
reject((r,c)=>{c.evidence.independent_human_reviewer_confirmed=true});
reject((r,c)=>{c.governance.eligible_for_automatic_promotion=true});
reject((r,c)=>{c.governance.eligible_for_rate_spreads=true});
reject((r,c)=>{c.as_of='2026-10-24'});
reject((r,c)=>{r.NZD.date='2026-10-22'});
reject((r,c)=>{c.canonical_at_review['2Y']=0});
const overdue=new Function('num','romeCalendarAge',source.slice(start,end)+';return nzdWebReviewCandidate;')(num,()=>15);
assert.equal(overdue({...raw,NZD:{...raw.NZD,date:'2026-10-16','2Y':3.89,'10Y':5}},ctx),null,
 'expired unapproved source cannot be shown as current context');
assert(source.includes("host.dataset.coreEffect='NONE'"));
assert(source.includes("data-nzd-web-review=\"RESEARCH_UNAPPROVED\""));
assert(source.includes("renderYieldStudy(doc,feeds[2],feeds[3],feeds[5],feeds[6])"),
 'NZD reviewed web source remains the sixth feed; secondary market 2Y is separate seventh');
console.log('NZD_B2_TWO_WEB_READS_STUDY_ONLY_NO_PROMOTION_PASS');
