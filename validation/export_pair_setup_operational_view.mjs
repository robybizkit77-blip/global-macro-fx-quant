import { chromium } from 'playwright';
import fs from 'node:fs';

const out=process.argv[2]||'/tmp/PAIR_SETUP_OPERATIONAL_VIEW.json';
const url=process.env.GMFQ_DASHBOARD_URL||'http://127.0.0.1:8000/';

const browser=await chromium.launch({headless:true});
try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e?.message||e)));
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>
    typeof derivePairSetupState==='function' &&
    typeof derivePairDecisionFrame==='function' &&
    typeof pairTransitionState==='function' &&
    typeof derivePairRelativeDynamics==='function' &&
    typeof D==='object' && Array.isArray(D?.pairs) && D.pairs.length===28,
    null,{timeout:120000});
  await page.waitForTimeout(2500);

  const snapshot=await page.evaluate(()=>{
    const clean=v=>JSON.parse(JSON.stringify(v));
    const canonicalPairs=[...new Set((D.pairs||[])
      .map(x=>String(x?.pair||'').trim().toUpperCase())
      .filter(x=>/^[A-Z]{3}\/[A-Z]{3}$/.test(x)))].sort();
    const rows={};
    for(const canonicalPair of canonicalPairs){
      const key=canonicalPair.replace('/','');
      const setup=derivePairSetupState(canonicalPair);
      const frame=derivePairDecisionFrame(canonicalPair);
      const transition=pairTransitionState(canonicalPair);
      const relative=derivePairRelativeDynamics(canonicalPair);
      const price=(typeof deriveCanonicalPairPriceState==='function')?deriveCanonicalPairPriceState(canonicalPair):null;
      rows[key]={
        canonical_pair:canonicalPair,
        setup:clean(setup),
        decision_frame:clean(frame),
        transition:clean(transition),
        relative_dynamics:clean(relative),
        price_state:price==null?null:clean(price)
      };
    }
    const priceDates=(D.pairs||[]).map(x=>x?.price_asof).filter(Boolean);
    const audit=(window.GMFQ_ECB_PRICE_AUDIT&&window.GMFQ_ECB_PRICE_AUDIT.status==='PASS')?clean(window.GMFQ_ECB_PRICE_AUDIT):null;
    if(audit?.as_of) priceDates.push(audit.as_of);
    priceDates.sort();
    return {
      schema:'GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1',
      status:'CURRENT_CANONICAL_ENGINE',
      pair_count:canonicalPairs.length,
      price_asof:priceDates.at(-1)||null,
      price_source:audit?.source||'canonical dashboard runtime',
      rules_source:'derivePairSetupState / derivePairDecisionFrame / pairTransitionState / derivePairRelativeDynamics',
      thesis_is_not_entry:true,
      entry_level_published:false,
      pairs:rows
    };
  });

  if(snapshot.pair_count!==28)throw new Error(`Expected 28 pairs, got ${snapshot.pair_count}`);
  const qualities={};
  for(const [pair,row] of Object.entries(snapshot.pairs)){
    if(!row.canonical_pair||!/^([A-Z]{3})\/([A-Z]{3})$/.test(row.canonical_pair))throw new Error(`${pair}: canonical pair label missing`);
    if(!row.setup||typeof row.setup!=='object')throw new Error(`${pair}: setup missing`);
    const q=row.setup.quality||row.setup.qualityLabel||row.setup.label||null;
    if(!q)throw new Error(`${pair}: setup quality missing`);
    qualities[q]=(qualities[q]||0)+1;
    if(!row.decision_frame||!row.transition||!row.relative_dynamics)throw new Error(`${pair}: canonical context incomplete`);
    const serial=JSON.stringify(row);
    if(serial.includes('undefined'))throw new Error(`${pair}: undefined leaked into canonical setup output`);
  }
  if((qualities['NON VALUTABILE']||0)===snapshot.pair_count)throw new Error('All 28 pairs are NON VALUTABILE; canonical runtime export is not operationally usable');
  snapshot.quality_distribution=qualities;
  snapshot.browser_page_errors=errors;
  fs.writeFileSync(out,JSON.stringify(snapshot,null,2)+'\n','utf8');
  console.log(JSON.stringify({status:'PAIR_SETUP_EXPORT_PASS',out,pair_count:snapshot.pair_count,price_asof:snapshot.price_asof,quality_distribution:qualities,page_error_count:errors.length},null,2));
} finally {
  await browser.close();
}
