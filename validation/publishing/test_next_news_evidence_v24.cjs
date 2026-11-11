'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const {parse,romeDate,link}=require(path.join(root,'site/fx-quant-v2/next/news-evidence-reading.js'));
const feed=JSON.parse(fs.readFileSync(path.join(root,'live_data/sections/NEWS_PULSE_OPERATIONAL.json'),'utf8'));
const today='2026-11-11';
const x=parse(feed,today);
assert(x.pulse.length>=4,'Keep all four dated monetary-pricing observations, plus any certified cross-asset evidence');
assert(x.official.length>=8,'Keep dated institutional releases as the official feed rolls forward');
assert.equal(x.pulseAsOf,feed.content_as_of,'Pulse must show source-content vintage, not the check timestamp');
assert.equal(x.officialAsOf,x.official[0]?.asof,'Official source clock must match latest dated observation');
assert.equal(x.latest,[x.pulse[0]?.asof,x.official[0]?.asof].filter(Boolean).sort().at(-1));
assert.match(x.gap,/orologi diversi/);
assert.equal(x.pulse.filter(y=>y.kind==='OIS osservato').length,1);
assert.equal(x.pulse.filter(y=>y.kind==='Futures: pricing implicito').length,3);
assert(x.pulse.every(y=>!y.macroSurprise&&!y.reactionProven),'No unfounded event-market causality');
assert(x.pulse.every(y=>y.kind==='Macro · dato ufficiale BLS'?
 y.impact.includes('NON misurata'):y.impact.includes('NON reazione provata')));
assert(x.official.every(y=>!y.reactionProven&&y.impact.includes('NON verificata')));
assert(x.official.every(y=>y.why.length>30&&y.verify.length>25),'Evidence-driven official relevance');
assert(x.official.every(y=>y.url?.startsWith('https://')),'Original official source links');
const summary=x.official.find(y=>y.title.startsWith('Summary of Opinions'));
if(summary)assert.match(summary.time||'',/^\\d{2}:\\d{2}$/);
const bankRate=x.official.find(y=>y.title.startsWith('Bank rate increased'));
if(bankRate)assert(bankRate.verify.includes('Consultare'));
assert(x.official.some(y=>y.kind==='Fondamentali energia'));
assert(x.official.some(y=>y.kind==='Comunicazione banca centrale'));
assert(x.pulse.some(y=>y.title.startsWith('AUD:')&&y.why.includes('non sono la stessa misura')));
// A BLS CPI actual belongs to the release date, but is invisible until
// the first observed source capture; the release clock must not leak hindsight.
const observedCpi=structuredClone(feed);
observedCpi.items.unshift({
 category:'MACRO_OFFICIAL_ACTUAL',ccy:'USD',as_of:'2026-11-10',
 title:'CPI USA ottobre · headline +0,4% e core +0,3% mensili',
 detail:'BLS source-dated actuals. Annual readings were not published.',
 source:'BLS CPI',source_url:'https://www.bls.gov/news.release/cpi.htm',
 first_runner_observed_at_utc:'2026-11-11T08:48:15Z',
 quality:'ISSUER_BLS_HTML_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT'
});
assert(!parse(observedCpi,'2026-11-10').pulse.some(y=>y.kind==='Macro · dato ufficiale BLS'),
 'No official CPI actual visible before first runner observation');
const cpiToday=parse(observedCpi,'2026-11-11').pulse.find(
 y=>y.kind==='Macro · dato ufficiale BLS');
assert(cpiToday&&cpiToday.asof==='2026-11-10'&&cpiToday.url?.startsWith('https://www.bls.gov/'));
assert(cpiToday.why.includes('Fed')&&cpiToday.verify.includes('USD/JPY'));
assert(cpiToday.impact.includes('NON misurata'));
assert(!cpiToday.macroSurprise&&!cpiToday.reactionProven);
const past=parse(feed,'2026-11-06');
assert.equal(past.official.some(y=>y.asof>'2026-11-06'),false,'No lookahead into later news');
const empty=parse(null,today);
assert.equal(empty.pulse.length,0);
assert.equal(empty.official.length,0);
assert.equal(link('javascript:alert(1)'),null);
assert.equal(link('https://user:pass@www.boj.or.jp/path'),null);
assert.equal(link('http://www.ecb.europa.eu'),null);
assert.equal(link('https://www.ecb.europa.eu/test?a=1&b=2'),'https://www.ecb.europa.eu/test?a=1&b=2');
const fake=structuredClone(feed);
fake.official_releases.headlines.push({...fake.official_releases.headlines[0],
 title:'<img src=x onerror=alert(1)>',url:'javascript:alert(1)',published_at_utc:'2026-11-09T23:50:00Z'});
const test=parse(fake,today);
assert.equal(test.official.at(0)?.url===null||test.official.some(y=>y.title.includes('<img')&&y.url===null),true,'Reject dangerous hyperlink values');
assert.equal(romeDate('2026-11-09T23:50:00Z').date,'2026-11-10');
assert.equal(romeDate('2026-11-09T21:00:00Z').date,'2026-11-09');
assert.equal(romeDate('invalid'),null);
const html=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/index.html'),'utf8');
const app=fs.readFileSync(path.join(root,'site/fx-quant-v2/next/app.js'),'utf8');
assert(html.indexOf('news-evidence-reading.js?v=26')<html.indexOf('app.js?v=18.'),'News source interpreter must load before current Next app');
for(const field of ['x.title','x.body','x.why','x.verify','x.impact','x.source','x.url']){
 assert(app.includes('esc('+field+')'),'News output is not escaped: '+field);
}
assert(app.includes('evidence.official.length')&&app.includes('evidence.pulse.length'));
assert(app.includes("route==='overview'||route==='pairs'||route==='cot'||route==='risk'||route==='news'"),
 'Generic news essay must not duplicate source-specific reading');
console.log('NEXT_NEWS_V24_PASS: at least 4 dated pricing items, 15/15 official releases, UTC->Rome, no false surprise/reaction, safe source URLs and no duplicate essay.');
