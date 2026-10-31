'use strict';
// Regression checks for the actual production Preview dateHistory implementation.
// No mocked rate series: load the exact main NATIVE_RATES_DATA.json contract.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const js=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const a=js.indexOf('function normalizeHistoryDate(raw){');
const b=js.indexOf('function estimate(target,ref,which){',a);
assert(a>=0&&b>a,'Preview dateHistory source changed: review before release');
const functions=vm.runInNewContext(
  js.slice(a,b)+'\n({normalizeHistoryDate,dateHistory})',
  {num:v=>typeof v==='number'&&Number.isFinite(v)?v:null,Date},
  {timeout:1000});
const {normalizeHistoryDate,dateHistory}=functions;

assert.equal(normalizeHistoryDate('2025-5-8'),'2025-05-08');
assert.equal(normalizeHistoryDate('2026-10-23'),'2026-10-23');
assert.equal(normalizeHistoryDate('2024-2-29'),'2024-02-29');
for(const d of ['2025-2-29','2026-02-30','2026-13-1','2026-0-1',
                '2026-1-0','25-1-1','2026/01/02','2026-1-1T00:00:00Z',null])
  assert.equal(normalizeHistoryDate(d),null,'invalid date accepted: '+String(d));

const raw=JSON.parse(fs.readFileSync('live_data/sections/NATIVE_RATES_DATA.json','utf8'));
const g8=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
let checks=0;
for(const ccy of g8){
  const data=raw[ccy];
  assert(data,'Missing '+ccy+' rates source');
  for(const tenor of ['history2','history10']){
    const h=data[tenor];
    assert(Array.isArray(h?.dates)&&Array.isArray(h?.values));
    assert.equal(h.dates.length,h.values.length,ccy+' '+tenor+' paired count');
    const normalized=dateHistory(data,tenor);
    assert.equal(normalized.length,h.dates.length,ccy+' '+tenor+' lost history');
    const original=new Map();
    for(let i=0;i<h.dates.length;i++){
      const d=normalizeHistoryDate(h.dates[i]);
      assert(d,'bad source date '+ccy+': '+h.dates[i]);
      assert(!original.has(d),'duplicate source day '+ccy+': '+d);
      original.set(d,h.values[i]);
    }
    let last='';
    for(const row of normalized){
      assert(row.date>last,ccy+' '+tenor+' not chronologically sorted');
      assert.equal(row.v,original.get(row.date),ccy+' '+tenor+' value/date association changed');
      assert(row.date<=data.date,ccy+' '+tenor+' future relative to feed as-of');
      last=row.date;
    }
    assert.equal(normalized.at(-1).date,data.date,ccy+' '+tenor+' top-day mismatch');
    assert.equal(normalized.at(-1).v,data[tenor==='history2'?'2Y':'10Y'],
      ccy+' '+tenor+' end-of-history wrong yield');
    checks++;
  }
}
const jpy=raw.JPY;
for(const tenor of ['history2','history10']){
  const dates=jpy[tenor].dates;
  const oldUsable=dates.filter(d=>/^\d{4}-\d{2}-\d{2}$/.test(d)).length;
  const newUsable=dateHistory(jpy,tenor).length;
  // Current incident: raw lexical date sort is not an economic time series.
  // Test values stay dynamically sourced if the upstream adapter is fixed.
  assert(newUsable>=oldUsable,'normalization must not drop source points');
  assert(newUsable>20,'missing JPY chart history');
}
const duplicate={date:'2026-10-23',history2:{dates:['2026-1-2','2026-01-02'],values:[1,2]}};
assert.equal(dateHistory(duplicate,'history2').length,0,'colliding normalized dates must fail closed');
assert.equal(dateHistory({date:'bad-date',history2:{dates:['2026-01-02'],values:[1]}},'history2').length,
  0,'invalid current as-of must not yield a plausible chart');
// Audit original source date versus the independent freshness classification.
// CHF/NZD official histories stay HISTORICAL, not current trading observations.
const audit=JSON.parse(fs.readFileSync('live_data/sections/RATES_AUDIT_METADATA.json','utf8'));
for(const ccy of ['CHF','NZD']){
 assert.equal(audit.rates[ccy].current_as_of,raw[ccy].date,
  ccy+' metadata must refer to exact actual observation day');
 assert.equal(audit.expected_rates[ccy],raw[ccy].date);
 assert.notEqual(audit.rates[ccy].status,'RECENT_OFFICIAL_OBSERVATION');
}
const hhStart=js.indexOf('function mountHistoricalSovereignTable(doc,raw){');
const hhEnd=js.indexOf('function renderYieldStudy(doc,rates',hhStart);
assert(hhStart>=0&&hhEnd>hhStart);
const hh=js.slice(hhStart,hhEnd);
for(const s of ['CERTIFICATO · STORICO','STORICO ','OFFICIAL_HISTORICAL_SAME_DAY_2Y_10Y',
                'non la data del rendimento sopra','NON livelli correnti'])
 assert(hh.includes(s),'historical CHF/NZD original Rates UI guard missing: '+s);
console.log('RATES_CHF_NZD_HISTORICAL_EXPLICIT_SOURCE_GATE');
console.log('JPY_RATES_READ_ONLY_NORMALIZE_PASS',
  JSON.stringify({currencyTenorChecks:checks,jpy2YRecovered:dateHistory(jpy,'history2').length,
    jpy10YRecovered:dateHistory(jpy,'history10').length}));
