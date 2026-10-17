// Isolated regression test: node tests/website_v1/test_weekly_market_focus.cjs
// Uses only Node built-ins; no DOM/browser dependency. Browser screenshot QA is separate.
const fs=require('node:fs'), vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('site/website-v1/market-snapshot.js','utf8');
const rates=JSON.parse(fs.readFileSync('live_data/sections/NATIVE_RATES_DATA.json','utf8'));
const fx=JSON.parse(fs.readFileSync('live_data/sections/ECB_G8_PRICE_HISTORY.json','utf8'));
const fixedToday=Date.parse('2026-10-17T12:00:00Z');
class FixedDate extends Date {constructor(...args){super(...(args.length?args:[fixedToday]));}static now(){return fixedToday;}}
async function scenario(tf,rateFeed,fxFeed){
  const strip={innerHTML:'',children:[]},attrs={},events={},warnings=[];
  const rank=Array.from({length:8},()=>({querySelector:()=>null}));
  const document={
    readyState:'complete',
    querySelector:s=>s==='.ticker-strip'?strip:null,
    querySelectorAll:s=>s==='.hierarchy .rankrow'?rank:[],
    documentElement:{setAttribute:(k,v)=>attrs[k]=v},
    addEventListener:(name,cb)=>events[name]=cb
  };
  const urls={search:'?tf='+tf,href:'https://example.test/?tf='+tf};
  const context={document,location:urls,history:{},URL,URLSearchParams,Date:FixedDate,
    console:{warn:(...args)=>warnings.push(args.map(String).join(' '))},
    MutationObserver:class{observe(){}},
    queueMicrotask,
    addEventListener:()=>{},
    fetch:async url=>({ok:true,json:async()=>String(url).includes('NATIVE_RATES')?rateFeed:fxFeed})};
  vm.runInNewContext(source,context,{filename:'market-snapshot.js',timeout:3000});
  for(let i=0;i<25;i++)await Promise.resolve();
  const labels=[...strip.innerHTML.matchAll(/<small>([^<]+)<\/small>/g)].map(x=>x[1]);
  const cardCount=(strip.innerHTML.match(/class="ticker"/g)||[]).length;
  const chartCount=(strip.innerHTML.match(/<polyline/g)||[]).length;
  return {labels,cardCount,chartCount,attrs,warnings,html:strip.innerHTML};
}
(async()=>{
  let base;
  for(const tf of ['1D','1W','1M','3M','YTD']){
    const r=await scenario(tf,rates,fx);
    assert.equal(r.cardCount,8,tf+' cards');
    assert.equal(r.chartCount,8,tf+' charts');
    assert.equal(r.attrs['data-hierarchy-period'],'1D',tf+' Forza FX');
    assert.deepEqual(r.warnings,[],tf+' warnings');
    assert(!r.html.includes('NaN'),tf+' NaN');
    if(base)assert.deepEqual(r.labels,base,'Weekly selection must not change with display timeframe');
    else base=r.labels;
  }
  const stale=await scenario('1D',rates,{...fx,last_as_of:'2026-09-01'});
  assert.equal(stale.cardCount,8);
  assert.equal(stale.attrs['data-fx-freshness'],'WITHHELD');
  const absent=await scenario('1D',null,null);
  assert.equal(absent.cardCount,8,'fallback');
  assert.equal(absent.attrs['data-market-snapshot'],'FAIL');
  console.log('PASS weekly Market Focus: 5 timeframes, Forza FX, stale FX, no feeds');
})().catch(err=>{console.error(err);process.exitCode=1});
