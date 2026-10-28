'use strict';
/**
 * End-to-end synthetic post-release user journey, in a Playwright route only.
 *
 * NOT actual US ECI or Canadian GDP values. Do not write production JSON.
 * Proves that the live news app interprets (a) first-seen official actual,
 * (b) exact pre-release consensus, (c) a genuine numeric ZERO, (d) source
 * links, (e) noncausal dated 2Y/FX context, (f) 2-minute visible-view refresh,
 * (g) a partial first-issuer actual without marking both events as released,
 * (h) fail-closed source host and first-observation clock integrity.
 */
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');

const PATH='live_data/sections/NEWS_PULSE_OPERATIONAL.json';
const original=JSON.parse(fs.readFileSync(PATH,'utf8'));
assert.equal(original.macro_event_market_context.schema,
             'GMFQ_MACRO_EVENT_CONTEXT_DAILY_MATCH_V1');
assert.equal(original.macro_event_market_context.events.length,2);

function baseline(){
  const n=structuredClone(original);
  for(const e of n.macro_event_market_context.events){
    e.state='PENDING_OFFICIAL_RELEASE';
    e.official_actual_percent=null;
    e.actual_minus_frozen_consensus_pp=null;
    e.official_actual_source_url=null;
    e.official_actual_captured_at_utc=null;
    e.official_actual_source_quality=null;
    e.post_event_daily_comparison=null;
    e.event_causality_verified=false;
    e.FX_trade_signal=null;
    e.eligible_for_Core_Beta_Forward=false;
  }
  return n;
}
function release(){
  const n=baseline();
  const expected={USD:0.8,CAD:0.2};
  const actual={USD:0.9,CAD:0.0}; // PURE TEST FIXTURES: invented future values.
  const urls={
    USD:'https://www.bls.gov/news.release/eci.htm',
    CAD:'https://www150.statcan.gc.ca/n1/daily-quotidien/261030/dq261030a-eng.htm'
  };
  for(const e of n.macro_event_market_context.events){
    const c=e.currency;
    assert.equal(e.secondary_consensus_percent,expected[c]);
    e.state='DAILY_CONTEXT_ONLY_NO_EVENT_CAUSALITY';
    e.official_actual_percent=actual[c];
    e.actual_minus_frozen_consensus_pp=Number((actual[c]-expected[c]).toFixed(6));
    e.official_actual_source_url=urls[c];
    e.official_actual_captured_at_utc='2026-10-30T12:38:44Z';
    e.official_actual_source_quality=
      'FIRST_RUNNER_OBSERVATION_NOT_ISSUER_FIRST_RELEASE_PIT';
    e.post_event_daily_comparison={
      '2Y':{
        status:'DESCRIPTIVE_MULTIDAY_CHANGE_NOT_EVENT_CAUSAL',
        from:'2026-10-27',to:'2026-11-02',delta_bp:c==='USD'?4.0:-2.0
      },
      '10Y':{status:'NO_MATCHED_POST_EVENT_SOURCE'},
      SIX_MONTH:{status:c==='USD'?
          'NO_OFFICIAL_PRERELEASE_SOURCE':
          'DESCRIPTIVE_MULTIDAY_CHANGE_NOT_EVENT_CAUSAL',
        from:'2026-10-27',to:'2026-11-02',delta_bp:2.5
      },
      ECB_FX:{status:'DESCRIPTIVE_MULTIDAY_CHANGE_NOT_EVENT_CAUSAL',
        from:'2026-10-27',to:'2026-11-02',
        eur_base_quote_change_pct:c==='USD'?-0.45:0.15}
    };
  }
  n.macro_event_market_context.summary.awaiting_release=0;
  n.macro_event_market_context.summary.awaiting_actual=0;
  n.macro_event_market_context.summary.observed_daily_context=2;
  n.macro_event_market_context.summary.FX_signals=0;
  n.macro_event_market_context.summary.issuer_event_intraday_reactions_certified=0;
  return n;
}
const before=baseline();
const after=release();
const partial=structuredClone(after);
// USD BLS arrives first; the CAD issuer is still genuinely unavailable.
// A partial update must not manufacture a second actual or source URL.
partial.macro_event_market_context.events[1]=structuredClone(
  before.macro_event_market_context.events[1]);
partial.macro_event_market_context.summary.awaiting_release=1;
partial.macro_event_market_context.summary.awaiting_actual=0;
partial.macro_event_market_context.summary.observed_daily_context=1;
assert.equal(partial.macro_event_market_context.events[0].currency,'USD');
assert.equal(partial.macro_event_market_context.events[1].currency,'CAD');
const malformed=structuredClone(after);
malformed.macro_event_market_context.events.find(e=>e.currency==='CAD')
  .actual_minus_frozen_consensus_pp=7.1;
const untrusted=structuredClone(after);
const unsafeCad=untrusted.macro_event_market_context.events.find(e=>e.currency==='CAD');
unsafeCad.official_actual_source_url='https://not-statcan.example.com/fake-gdp';
unsafeCad.state='PENDING_OFFICIAL_ACTUAL_ISSUER_VERIFICATION';
const badClock=structuredClone(after);
const earlyCad=badClock.macro_event_market_context.events.find(e=>e.currency==='CAD');
earlyCad.official_actual_captured_at_utc='2026-10-30T12:29:59Z';
earlyCad.state='OFFICIAL_ACTUAL_PRESENT_PRE_EVENT_MARKET_ANCHOR_ABSENT';

(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    for(const [device,width,height] of [['desktop',1440,1000],['mobile',390,844]]){
      const page=await browser.newPage({viewport:{width,height}});
      const errors=[];
      page.on('pageerror',e=>errors.push(String(e)));
      page.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text())});
      await page.clock.install({time:new Date('2026-10-30T12:36:00Z')});
      let phase='BEFORE';
      let requests=0;
      await page.route('**/live_data/sections/NEWS_PULSE_OPERATIONAL.json',async route=>{
        ++requests;
        const body=phase==='BEFORE'?before:
          phase==='PARTIAL'?partial:phase==='AFTER'?after:malformed;
        await route.fulfill({status:200,contentType:'application/json',
                            body:JSON.stringify(body)});
      });
      await page.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
      await page.waitForFunction(()=>window.GMFQ_CALENDAR_NEWS_OPERATIONAL?.status==='ACTIVE',
                                {timeout:20000});
      await page.evaluate(()=>window.showView&&window.showView('news'));
      await page.waitForSelector('#news .opCard[data-kind="macro-evidence"]',{state:'visible'});
      let status=await page.evaluate(()=>[...document.querySelectorAll(
        '#news .opCard[data-kind="macro-evidence"]')].map(x=>({
          ccy:x.dataset.ccy,text:x.textContent||'',
          links:x.querySelectorAll('a[href]').length
        })));
      assert.equal(status.length,2);
      for(const x of status){
        assert.match(x.text,/In attesa/);
        assert.match(x.text,/Non calcolabile/);
        assert.equal(x.links,0,'No fabricated issuer actual URL before release');
      }

      // First issuer arrives while the other is missing. A fully rendered
      // USD card must coexist with a still-pending CAD card. On both screens.
      phase='PARTIAL';
      await page.clock.fastForward(120500);
      await page.waitForFunction(()=>{
        const usd=document.querySelector('#news .opCard[data-kind="macro-evidence"][data-ccy="USD"]');
        return usd?.textContent.includes('Actual − consenso');
      },null,{timeout:20000});
      const midway=await page.evaluate(()=>[...document.querySelectorAll(
        '#news .opCard[data-kind="macro-evidence"]')].map(card=>({
          ccy:card.dataset.ccy,stage:card.dataset.stage,
          text:card.textContent||'',w:card.scrollWidth,cw:card.clientWidth,
          links:[...card.querySelectorAll('a[href]')].map(a=>a.href)
        })));
      const first=midway.find(x=>x.ccy==='USD');
      const pending=midway.find(x=>x.ccy==='CAD');
      assert.equal(midway.length,2);
      assert(first&&pending);
      assert.equal(first.stage,'DAILY_CONTEXT_ONLY_NO_EVENT_CAUSALITY');
      assert(first.text.includes('+0.9%'),'USD actual visible in partial state');
      assert(first.text.includes('+0.1'),'USD surprise visible in partial state');
      assert.equal(first.links.length,1);
      assert(first.links[0].startsWith('https://www.bls.gov/'));
      assert.equal(pending.stage,'PENDING_OFFICIAL_RELEASE');
      assert.match(pending.text,/In attesa/);
      assert.match(pending.text,/Non calcolabile/);
      assert(!pending.text.includes('Actual − consenso'));
      assert.equal(pending.links.length,0,'No fictitious CAD official link');
      for(const item of midway){
        assert(item.w<=item.cw+2,'Partial card horizontal overflow '+device+'/'+item.ccy);
      }
      // Second issuer appears on the next two-minute visible-view refresh.
      phase='AFTER';
      await page.clock.fastForward(120500);
      await page.waitForFunction(()=>[...document.querySelectorAll(
        '#news .opCard[data-kind="macro-evidence"]')].every(x=>
          x.textContent.includes('Actual − consenso')),null,{timeout:20000});
      const result=await page.evaluate(()=>[...document.querySelectorAll(
        '#news .opCard[data-kind="macro-evidence"]')].map(card=>({
          ccy:card.dataset.ccy,stage:card.dataset.stage,
          text:card.textContent||'',w:card.scrollWidth,cw:card.clientWidth,
          links:[...card.querySelectorAll('a[href]')].map(a=>a.href),
          rates:[...card.querySelectorAll('.opMacroRate')].map(x=>x.textContent)
        })));
      assert.equal(result.length,2);
      const usd=result.find(x=>x.ccy==='USD');
      const cad=result.find(x=>x.ccy==='CAD');
      assert(usd&&cad);
      for(const item of [usd,cad]){
        assert.equal(item.stage,'DAILY_CONTEXT_ONLY_NO_EVENT_CAUSALITY');
        assert.match(item.text,/Reazione evento → mercato non dimostrata/);
        assert.match(item.text,/Variazioni tra osservazioni giornaliere/);
        assert.match(item.text,/2Y/);
        assert.match(item.text,/10Y/);
        assert.match(item.text,/02\/11|2026-11-02/);
        assert(item.w<=item.cw+2,'No card horizontal overflow '+device+'/'+item.ccy);
        assert.equal(item.links.length,1,'Allowlist one official publisher link');
      }
      assert.match(usd.text,/\+0\.9%/);
      assert.match(usd.text,/\+0\.1/);
      assert.match(cad.text,/0\.0%/); // zero is a valid verified actual, no artificial plus sign
      assert.match(cad.text,/-0\.2/);
      assert(usd.links[0].startsWith('https://www.bls.gov/'));
      assert(cad.links[0].startsWith('https://www150.statcan.gc.ca/'));
      assert(!cad.text.includes('INFLATION SIGNAL'));
      assert(!usd.text.includes('TRADE ENTRY'));

      await page.screenshot({
        path:'calendar-news-macro-postrelease-'+device+'.png',
        fullPage:true
      });

      // Adversarial broken actual-minus-forecast evidence must not
      // render CAD's numeric actual or present a forged issuer source URL.
      phase='MALFORMED';
      await page.clock.fastForward(120500);
      await page.waitForFunction(()=>document.querySelector(
        '#news .opCard[data-kind="macro-evidence"][data-ccy="CAD"]'
      )?.textContent.includes('Non calcolabile'),null,{timeout:20000});
      const bad=await page.evaluate(()=>{
        const card=document.querySelector('#news .opCard[data-kind="macro-evidence"][data-ccy="CAD"]');
        return {text:card.textContent,links:card.querySelectorAll('a[href]').length}
      });
      assert.match(bad.text,/In attesa/);
      assert.match(bad.text,/Non calcolabile/);
      assert.equal(bad.links,0);

      assert(requests>=4,'initial + 3 live refresh network reads required');
      assert.deepEqual(errors,[],'No JS runtime errors '+device);
      console.log('MACRO_NEWS_ACTUAL_BROWSER_PASS',device,{
        forecast_only_before:true,partial_actual_first:true,actual_zero_after:true,
        source_links_after:true,malformed_suppressed:true,
        requests,viewport:width
      });
      await page.close();

      // Provenance adversaries run on independent fresh pages. Timer
      // transitions are already proven above; these cases test the consumer's
      // fail-closed gate, not consecutive artificial virtual-clock refreshes.
      for(const [name,fixture] of [['UNTRUSTED_ISSUER',untrusted],
                                  ['BAD_FIRST_SEEN_CLOCK',badClock]]){
        const probe=await browser.newPage({viewport:{width,height}});
        const probeErrors=[];
        probe.on('pageerror',e=>probeErrors.push(String(e)));
        await probe.route('**/live_data/sections/NEWS_PULSE_OPERATIONAL.json',
          async route=>route.fulfill({status:200,contentType:'application/json',
                                     body:JSON.stringify(fixture)}));
        await probe.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
        await probe.waitForFunction(
          ()=>window.GMFQ_CALENDAR_NEWS_OPERATIONAL?.status==='ACTIVE',
          null,{timeout:20000});
        await probe.evaluate(()=>window.showView&&window.showView('news'));
        await probe.waitForSelector(
          '#news .opCard[data-kind="macro-evidence"][data-ccy="CAD"]',
          {state:'visible'});
        const evidence=await probe.evaluate(()=>{
          const c=document.querySelector(
            '#news .opCard[data-kind="macro-evidence"][data-ccy="CAD"]');
          const usd=document.querySelector(
            '#news .opCard[data-kind="macro-evidence"][data-ccy="USD"]');
          return {
            stage:c.dataset.stage,text:c.textContent||'',
            links:c.querySelectorAll('a[href]').length,
            w:c.scrollWidth,cw:c.clientWidth,
            usdActual:usd?.textContent.includes('Actual − consenso')
          };
        });
        assert.equal(evidence.stage,
          fixture.macro_event_market_context.events.find(e=>e.currency==='CAD').state);
        assert(evidence.usdActual,'Unrelated valid USD official actual remains visible');
        assert.match(evidence.text,/In attesa/);
        assert.match(evidence.text,/Non calcolabile/);
        assert(!evidence.text.includes('Actual − consenso'));
        assert.equal(evidence.links,0,name+' must not render CAD issuer actual link');
        assert(evidence.w<=evidence.cw+2,name+' mobile overflow');
        assert.deepEqual(probeErrors,[],name+' JS errors '+device);
        console.log('MACRO_NEWS_PROVENANCE_FAIL_CLOSED_PASS',device,name);
        await probe.close();
      }
    }
  } finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
