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
    const pairs=[...new Set(D.pairs.map(x=>String(x?.pair||'').replace(/[^A-Z]/g,'').slice(0,6)).filter(x=>x.length===6))].sort();
    const rows={};
    for(const pair of pairs){
      const setup=derivePairSetupState(pair);
      const frame=derivePairDecisionFrame(pair);
      const transition=pairTransitionState(pair);
      const relative=derivePairRelativeDynamics(pair);
      const price=(typeof deriveCanonicalPairPriceState==='function')?deriveCanonicalPairPriceState(pair):null;
      rows[pair]={
        setup:clean(setup),
        decision_frame:clean(frame),
        transition:clean(transition),
        relative_dynamics:clean(relative),
        price_state:price==null?null:clean(price)
      };
    }
    const priceDates=(D.pairs||[]).map(x=>x?.price_asof).filter(Boolean).sort();
    const audit=(window.GMFQ_ECB_PRICE_AUDIT&&window.GMFQ_ECB_PRICE_AUDIT.status==='PASS')?clean(window.GMFQ_ECB_PRICE_AUDIT):null;
    return {
      schema:'GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1',
      status:'CURRENT_CANONICAL_ENGINE',
      pair_count:pairs.length,
      price_asof:priceDates.at(-1)||audit?.as_of||null,
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
    if(!row.setup||typeof row.setup!=='object')throw new Error(`${pair}: setup missing`);
    const q=row.setup.quality||row.setup.qualityLabel||row.setup.label||null;
    if(!q)throw new Error(`${pair}: setup quality missing`);
    qualities[q]=(qualities[q]||0)+1;
    if(!row.decision_frame||!row.transition||!row.relative_dynamics)throw new Error(`${pair}: canonical context incomplete`);
  }
  snapshot.quality_distribution=qualities;
  snapshot.browser_page_errors=errors;
  fs.writeFileSync(out,JSON.stringify(snapshot,null,2)+'\n','utf8');
  console.log(JSON.stringify({status:'PAIR_SETUP_EXPORT_PASS',out,pair_count:snapshot.pair_count,price_asof:snapshot.price_asof,quality_distribution:qualities,page_error_count:errors.length},null,2));
} finally {
  await browser.close();
}
